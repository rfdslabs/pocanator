"""
Services for analyzing vulnerabilities using OpenAI API.
"""
import logging
import re
import time
import json
from django.conf import settings
from django.utils import timezone
from apps.advisories.models import Advisory, Commit
from .models import Analysis
from apps.users.models import APIUsage
from .openai_compat import OpenAIClient

logger = logging.getLogger(__name__)

class AnalysisService:
    """Service for analyzing vulnerabilities using OpenAI API"""
    
    def __init__(self, api_key=None, user=None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.user = user
        self.openai_client = None
        self.setup_client()
    
    def setup_client(self):
        """Initialize the OpenAI client"""
        try:
            self.openai_client = OpenAIClient(api_key=self.api_key)
            logger.info("OpenAI compatibility client initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing OpenAI compatibility client: {e}")
            self.openai_client = None
    
    def analyze_advisory(self, advisory, model="gpt-4o", save_report=True):
        """
        Analyze an advisory using GPT and return the analysis results
        
        Args:
            advisory: Advisory object
            model: OpenAI model to use
            save_report: Whether to save the report to the database
            
        Returns:
            Analysis object or None if analysis failed
        """
        if not self.openai_client:
            logger.error("OpenAI client not initialized")
            return None
        
        if not advisory:
            logger.error("No advisory provided for analysis")
            return None
            
        # Define fallback model order
        models = [model]  # Start with requested model
        if model == "gpt-4o":
            # Define fallbacks for gpt-4o
            models.extend(["gpt-4-turbo", "gpt-3.5-turbo"])
        elif model == "gpt-4-turbo":
            # Define fallbacks for gpt-4-turbo
            models.extend(["gpt-3.5-turbo"])
        
        # Check if advisory has commits
        commits = advisory.commits.all()
        if not commits.exists():
            logger.warning(f"Advisory {advisory.github_id} has no commits to analyze")
        
        # Prepare the prompts
        try:
            # Construct advisory description
            advisory_text = self._prepare_advisory_text(advisory)
            
            # Construct patch information - start with a reasonable limit
            # Adjust this limit based on the model and available tokens
            max_chars = 150000
            patch_text = self._prepare_patch_text(commits, max_chars=max_chars)
            
            # Full prompt
            prompt = self._construct_prompt(advisory, advisory_text, patch_text)
            
            # Check prompt size
            prompt_size = len(prompt)
            logger.info(f"Prompt size: {prompt_size} characters")
            
            # Reduce patch size if prompt is too large
            if prompt_size > 800000:  # Well below OpenAI's limit but leaves room for response
                logger.warning(f"Prompt too large ({prompt_size} chars). Reducing patch size.")
                # Try again with a smaller patch size
                reduced_max = int(max_chars * 0.5)  # Reduce by 50%
                patch_text = self._prepare_patch_text(commits, max_chars=reduced_max)
                prompt = self._construct_prompt(advisory, advisory_text, patch_text)
                prompt_size = len(prompt)
                logger.info(f"Reduced prompt size to {prompt_size} characters")
                
                # If still too large, try again with even smaller patch
                if prompt_size > 800000:
                    logger.warning("Prompt still too large after reduction. Reducing further.")
                    reduced_max = int(reduced_max * 0.5)  # Reduce further
                    patch_text = self._prepare_patch_text(commits, max_chars=reduced_max)
                    prompt = self._construct_prompt(advisory, advisory_text, patch_text)
                    prompt_size = len(prompt)
                    logger.info(f"Final prompt size: {prompt_size} characters")
            
            # Try each model in order until one succeeds
            last_error = None
            used_model = None
            
            for current_model in models:
                try:
                    # Call OpenAI API via our compatibility layer
                    logger.info(f"Sending request to OpenAI API using model {current_model}")
                    start_time = time.time()
                    
                    response = self.openai_client.chat_completion(
                        model=current_model,
                        messages=[
                            {"role": "system", "content": self._get_system_prompt()},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.3,
                        max_tokens=2500,
                        response_format={"type": "json_object"}
                    )
                    
                    # If we get here, the request succeeded
                    used_model = current_model
                    break
                    
                except Exception as e:
                    last_error = e
                    logger.warning(f"Error with model {current_model}: {e}")
                    
                    # If it's a rate limit error, wait and try again once
                    if "rate limit" in str(e).lower():
                        wait_time = self._extract_wait_time(str(e))
                        if wait_time:
                            logger.info(f"Rate limit hit. Waiting {wait_time} seconds before trying next model.")
                            time.sleep(min(wait_time, 5))  # Wait at most 5 seconds before trying next model
                    
                    # If it's a context length error, reduce patch size and try again
                    if "too long" in str(e).lower() and current_model == models[0]:
                        logger.warning("Context length error. Reducing patch size by 75%")
                        # Try one more time with drastically reduced patch size
                        reduced_max = int(max_chars * 0.25)  # Reduce to 25%
                        patch_text = self._prepare_patch_text(commits, max_chars=reduced_max)
                        prompt = self._construct_prompt(advisory, advisory_text, patch_text)
                        
                        try:
                            response = self.openai_client.chat_completion(
                                model=current_model,
                                messages=[
                                    {"role": "system", "content": self._get_system_prompt()},
                                    {"role": "user", "content": prompt}
                                ],
                                temperature=0.3,
                                max_tokens=2500,
                                response_format={"type": "json_object"}
                            )
                            # If we get here, the retry succeeded
                            used_model = current_model
                            break
                        except:
                            # Continue to next model if retry fails
                            continue
            
            # If all models failed, raise the last error
            if not used_model:
                if last_error:
                    raise last_error
                else:
                    raise Exception("All models failed without specific error")
            
            # Extract information from the standardized response
            analysis_result = response["content"]
            tokens_used = response["tokens"]["total_tokens"]
            cost = self._calculate_cost(used_model, tokens_used)
            
            # Note if we had to use a fallback model. Do NOT mutate
            # analysis_result here: it is the raw JSON the model returned and
            # appending prose would make json.loads fail. The note is added to
            # the human-readable markdown report after parsing instead.
            fallback_note = ""
            if used_model != model:
                logger.info(f"Used fallback model {used_model} instead of requested {model}")
                fallback_note = (
                    f"\n\n*Note: This analysis was generated using {used_model} "
                    f"instead of {model} due to API limitations.*"
                )

            # Log API usage
            if self.user:
                APIUsage.objects.create(
                    user=self.user,
                    endpoint="analyze_advisory",
                    tokens_used=tokens_used,
                    model=used_model,
                    cost=cost
                )
            
            # Parse the structured JSON results
            analysis_data = self._parse_analysis_results(analysis_result)
            if analysis_data is None:
                logger.error("Could not parse analysis JSON for %s", advisory.github_id)
                return None

            # Create or update analysis object
            if save_report:
                analysis = Analysis.objects.create(
                    advisory=advisory,
                    user=self.user,
                    model_used=used_model,  # Use the model that actually succeeded
                    vuln_type=analysis_data.get('vuln_type', 'Unknown'),
                    severity=analysis_data.get('severity', ''),
                    cwe=analysis_data.get('cwe', ''),
                    vuln_explanation=analysis_data.get('vuln_explanation', ''),
                    patch_analysis=analysis_data.get('patch_analysis', ''),
                    impact_summary=analysis_data.get('impact_summary', ''),
                    patch_effectiveness=self._safe_int_conversion(analysis_data.get('patch_effectiveness', 0)),
                    poc_feasibility=self._safe_int_conversion(analysis_data.get('poc_feasibility', 0)),
                    poc_complexity=analysis_data.get('poc_complexity', 'Unknown'),
                    confidence=self._safe_int_conversion(analysis_data.get('confidence', 0)),
                    required_skills=analysis_data.get('required_skills', ''),
                    information_gaps=analysis_data.get('information_gaps', ''),
                    key_indicators=analysis_data.get('key_indicators', ''),
                    tokens_used=tokens_used,
                    estimated_cost=cost,
                    markdown_report=self._build_markdown(analysis_data) + fallback_note,
                )

                # Update the advisory with vulnerability type if not set
                if not advisory.vulnerability_type and analysis_data.get('vuln_type'):
                    advisory.vulnerability_type = analysis_data.get('vuln_type')
                    advisory.save(update_fields=['vulnerability_type'])

                return analysis

            return analysis_data
            
        except Exception as e:
            logger.exception(f"Error analyzing advisory {advisory.github_id}: {e}")
            return None
    
    def _prepare_advisory_text(self, advisory):
        """Prepare the advisory text for the prompt"""
        advisory_text = f"# {advisory.title}\n\n"
        
        # Add metadata
        metadata = []
        if advisory.cve_id:
            metadata.append(f"- CVE ID: {advisory.cve_id}")
        if advisory.cvss_score:
            metadata.append(f"- CVSS Score: {advisory.cvss_score}")
        if advisory.affected_versions:
            metadata.append(f"- Affected Versions: {advisory.affected_versions}")
        
        if metadata:
            advisory_text += "### ADVISORY METADATA:\n"
            advisory_text += "\n".join(metadata) + "\n\n"
        
        # Add description
        advisory_text += advisory.description
        
        return advisory_text
    
    def _prepare_patch_text(self, commits, max_chars=500000):
        """
        Prepare the patch text for the prompt with size limits
        
        Args:
            commits: QuerySet of Commit objects
            max_chars: Maximum characters to include for patches
            
        Returns:
            String with patch information
        """
        if not commits:
            return "[No Patches Found]"
        
        # Count total characters in all commits first
        total_chars = sum(len(commit.diff_text or "") for commit in commits)
        
        # If total is under limit, we can include all commits (up to 3)
        if total_chars <= max_chars:
            patch_diffs = []
            for i, commit in enumerate(commits[:3]):  # Limit to 3 commits
                if not commit.diff_text:
                    continue
                repo_info = f"{commit.repo_name} ({commit.commit_hash[:7]})"
                patch_diffs.append(f"--- PATCH {i+1}: {repo_info} ---\n{commit.diff_text}")
            
            return "\n\n".join(patch_diffs)
        
        # Otherwise, we need to truncate and distribute space
        else:
            logger.warning(f"Commit diffs too large ({total_chars} chars). Truncating to {max_chars} chars.")
            
            # First, get a list of the first 3 commits with their sizes
            commit_info = []
            for i, commit in enumerate(commits[:3]):
                if not commit.diff_text:
                    continue
                commit_info.append({
                    'index': i,
                    'commit': commit,
                    'size': len(commit.diff_text)
                })
            
            if not commit_info:
                return "[No Valid Patches Found]"
                
            # Calculate how much space to allocate to each commit proportionally
            total_size = sum(item['size'] for item in commit_info)
            
            patch_diffs = []
            remaining_chars = max_chars
            
            # Handle all but the last commit
            for i in range(len(commit_info) - 1):
                item = commit_info[i]
                # Allocate space proportionally
                chars_for_this_commit = int((item['size'] / total_size) * max_chars)
                remaining_chars -= chars_for_this_commit
                
                commit = item['commit']
                repo_info = f"{commit.repo_name} ({commit.commit_hash[:7]})"
                diff_text = commit.diff_text[:chars_for_this_commit] + "\n... [TRUNCATED]"
                patch_diffs.append(f"--- PATCH {item['index']+1}: {repo_info} ---\n{diff_text}")
            
            # Handle last commit with remaining chars
            last_item = commit_info[-1]
            commit = last_item['commit']
            repo_info = f"{commit.repo_name} ({commit.commit_hash[:7]})"
            diff_text = commit.diff_text[:remaining_chars] + "\n... [TRUNCATED]"
            patch_diffs.append(f"--- PATCH {last_item['index']+1}: {repo_info} ---\n{diff_text}")
            
            return "\n\n".join(patch_diffs)
    
    def _construct_prompt(self, advisory, advisory_text, patch_text):
        """Construct the full prompt for GPT"""
        # Check if there are any commits
        has_commits = advisory.commits.exists()
        commit_count = advisory.commits.count()
        
        # Adjust the prompt based on whether there are commits
        if not has_commits:
            patch_note = "No patches/commits were found for this advisory."
        else:
            patch_note = f"{commit_count} commit(s) found for this advisory."
        
        return f"""You are a cybersecurity analyst reviewing a GitHub Security Advisory and its associated patch (if available).

**Advisory URL:** {advisory.url}
**Advisory Severity:** {advisory.severity}

**Advisory Information:**
--- START ADVISORY ---
{advisory_text}
--- END ADVISORY ---

**Patch Information ({patch_note}):**
--- START PATCHES ---
{patch_text}
--- END PATCHES ---

**Your Task:**
Based ONLY on the information provided above:
1.  **Vulnerability Explanation:** Briefly explain the vulnerability in clear, concise terms. What type of vulnerability is it (e.g., RCE, XSS, SQLi)? How could it potentially be triggered?
2.  **Patch Analysis:** If a patch was provided and fetched successfully, describe how it fixes the vulnerability based on the diff. What specific changes address the issue? If no patch was found or fetched, state "No patches available" and move on.
3.  **Impact Summary:** Briefly summarize the potential impact if this vulnerability were exploited, according to the advisory text.
4.  **Confidence Score (Patch Effectiveness):** If a patch was provided and fetched, provide a confidence score (0-10) on how well the patch seems to address the described vulnerability, based *only* on the provided text and diff. Briefly justify the score. If no patch, state "N/A" for this section.
5.  **PoC Feasibility Analysis:** Based ONLY on the information provided, analyze the feasibility of creating a proof-of-concept (PoC) exploit. Include:
   - Confidence level (0-10 scale)
   - Complexity assessment (Low/Medium/High)
   - Required knowledge/skills for exploitation
   - Availability of target environment information in the advisory
   - Information gaps that would need to be filled to create a working PoC
   - Key vulnerability components exposed by the patch that would be helpful for exploitation (if patch available)
   - DO NOT create or describe any actual exploit code.

6.  **Generate Report:** Combine points 1-5 into a structured report. Use markdown formatting.

7.  **Summary Table:** At the end of your report, include a simple machine-readable summary table in this exact format:
```
SEVERITY: [{advisory.severity}/Critical/High/Moderate/Low/Unknown]
VULN_TYPE: [RCE/XSS/SQLI/etc]
PATCH_EFFECTIVENESS: [0-10 or N/A if no patches]
POC_FEASIBILITY: [0-10]
POC_COMPLEXITY: [Low/Medium/High]
```

**Important:** Do not invent information. Stick strictly to the provided advisory text and patch diff. Clearly state if information (like the patch) is missing or could not be analyzed. Do NOT create or include any actual exploit code in your analysis, even if you have high confidence in your ability to create a PoC."""
    
    def _get_system_prompt(self):
        """Get the system prompt for GPT"""
        return (
            "You are an expert cybersecurity analyst specializing in vulnerability "
            "assessment and defensive patch analysis. Analyze the provided advisory "
            "and patch and respond ONLY with a single JSON object (no markdown, no "
            "code fences) with exactly these keys: "
            "vuln_type (short string, e.g. 'SQL Injection'), "
            "severity (one of Low/Medium/High/Critical), "
            "cwe (e.g. 'CWE-89' or '' if unknown), "
            "confidence (integer 0-10, your confidence in this analysis), "
            "vuln_explanation (string), patch_analysis (string), "
            "impact_summary (string), "
            "patch_effectiveness (integer 0-10, how well the patch addresses the "
            "vulnerability; 0 if no patch provided), "
            "poc_feasibility (integer 0-10, how feasible an educational PoC is; "
            "0 if not applicable), "
            "poc_complexity (one of Low/Medium/High), "
            "required_skills (string), information_gaps (string), "
            "key_indicators (string)."
        )

    def _build_markdown(self, data):
        """Render a human-readable markdown report from structured analysis data."""
        def g(key):
            return data.get(key, "") or ""
        return (
            f"## 1. Vulnerability Explanation\n\n{g('vuln_explanation')}\n\n"
            f"## 2. Patch Analysis\n\n{g('patch_analysis')}\n\n"
            f"## 3. Impact Summary\n\n{g('impact_summary')}\n\n"
            f"## 4. PoC Feasibility\n\n{g('key_indicators')}\n\n"
            f"- **Required skills:** {g('required_skills')}\n"
            f"- **Information gaps:** {g('information_gaps')}\n\n"
            f"## 5. Metrics\n\n"
            f"| Metric | Value |\n| ------ | ----- |\n"
            f"| Severity | {g('severity')} |\n"
            f"| CWE | {g('cwe')} |\n"
            f"| Patch effectiveness | {data.get('patch_effectiveness', 0)} |\n"
            f"| PoC feasibility | {data.get('poc_feasibility', 0)} |\n"
            f"| PoC complexity | {g('poc_complexity')} |\n"
            f"| Confidence | {data.get('confidence', 0)} |\n"
        )

    def _parse_analysis_results(self, analysis_result):
        """Parse the analysis results (a JSON object string) from GPT.

        Returns a dict on success, or None if the content is not valid JSON.
        """
        try:
            data = json.loads(analysis_result)
        except (ValueError, TypeError) as exc:
            logger.error("Analysis response was not valid JSON: %s", exc)
            return None
        if not isinstance(data, dict):
            logger.error("Analysis JSON was not an object: %r", type(data))
            return None
        return data

    def _parse_analysis_results_legacy(self, analysis_result):
        """Deprecated markdown-scraping parser, kept for reference."""
        metrics = {}
        
        # Extract metrics table
        metrics_table = re.search(r'```\s*\nSEVERITY:\s+([^\n]+)\nVULN_TYPE:\s+([^\n]+)\nPATCH_EFFECTIVENESS:\s+([^\n]+)\nPOC_FEASIBILITY:\s+([^\n]+)\nPOC_COMPLEXITY:\s+([^\n]+)\n```', analysis_result)
        
        if metrics_table:
            metrics['SEVERITY'] = metrics_table.group(1).strip()
            metrics['VULN_TYPE'] = metrics_table.group(2).strip()
            metrics['PATCH_EFFECTIVENESS'] = metrics_table.group(3).strip()
            metrics['POC_FEASIBILITY'] = metrics_table.group(4).strip()
            metrics['POC_COMPLEXITY'] = metrics_table.group(5).strip()
        
        # Look for Markdown report format within code blocks
        markdown_block = re.search(r'```markdown\s*(.*?)\s*```', analysis_result, re.DOTALL)
        if markdown_block:
            markdown_content = markdown_block.group(1)
            
            # Extract sections
            for section_name, pattern in [
                ('VULN_EXPLANATION', r'## 1\.\s*Vulnerability Explanation\s+(.*?)(?=##)'),
                ('PATCH_ANALYSIS', r'## 2\.\s*Patch Analysis\s+(.*?)(?=##)'),
                ('IMPACT_SUMMARY', r'## 3\.\s*Impact Summary\s+(.*?)(?=##)'),
                ('POC_ANALYSIS', r'## 5\.\s*PoC Feasibility Analysis\s+(.*?)(?=##)')
            ]:
                section_match = re.search(pattern, markdown_content, re.DOTALL)
                if section_match:
                    metrics[section_name] = section_match.group(1).strip()
            
            # Extract specific details from PoC analysis
            if metrics.get('POC_ANALYSIS'):
                for detail_name, pattern in [
                    ('REQUIRED_SKILLS', r'\*\*Required Knowledge/Skills[^:]*:\*\*\s*(.*?)(?=\n- \*\*|\n\*\*|$)'),
                    ('INFORMATION_GAPS', r'\*\*Information Gaps[^:]*:\*\*\s*(.*?)(?=\n- \*\*|\n\*\*|$)'),
                    ('KEY_INDICATORS', r'\*\*Key Vulnerability Components[^:]*:\*\*\s*(.*?)(?=\n- \*\*|\n\*\*|$)')
                ]:
                    detail_match = re.search(pattern, metrics['POC_ANALYSIS'], re.DOTALL)
                    if detail_match:
                        metrics[detail_name] = detail_match.group(1).strip()
        
        # If no structured markdown block, try to parse from standard sections
        if not metrics.get('VULN_EXPLANATION'):
            for section_name, pattern in [
                ('VULN_EXPLANATION', r'(?:##|###)\s*Vulnerability Explanation\s+(.*?)(?=##|$)'),
                ('PATCH_ANALYSIS', r'(?:##|###)\s*Patch Analysis\s+(.*?)(?=##|$)'),
                ('IMPACT_SUMMARY', r'(?:##|###)\s*Impact Summary\s+(.*?)(?=##|$)'),
                ('POC_ANALYSIS', r'(?:##|###)\s*PoC Feasibility(?:\s*Analysis)?\s+(.*?)(?=##|$)')
            ]:
                section_match = re.search(pattern, analysis_result, re.DOTALL)
                if section_match:
                    metrics[section_name] = section_match.group(1).strip()
        
        return metrics
    
    def _safe_int_conversion(self, value):
        """Convert a value to a score integer clamped to the 0-10 range.

        Handles 'N/A'-style strings and out-of-range numbers from the model.
        """
        result = 0
        if value is not None:
            try:
                result = int(value)
            except (ValueError, TypeError):
                if isinstance(value, str) and value.upper() in ['N/A', 'NA', 'NONE', 'UNKNOWN']:
                    result = 0
                elif isinstance(value, str):
                    import re
                    digits = re.search(r'\d+', value)
                    if digits:
                        try:
                            result = int(digits.group())
                        except (ValueError, TypeError):
                            result = 0
        # Clamp scores to the documented 0-10 range.
        return max(0, min(10, result))
    
    def _extract_wait_time(self, error_message):
        """
        Extract wait time from rate limit error messages
        
        Args:
            error_message: Error message string from OpenAI API
            
        Returns:
            Wait time in seconds or None if not found
        """
        import re
        wait_match = re.search(r'try again in (\d+[\.\d]*)s', error_message)
        if wait_match:
            try:
                return float(wait_match.group(1))
            except ValueError:
                return None
        return None
    
    def _calculate_cost(self, model, tokens):
        """Calculate the cost of the API call"""
        # Pricing per 1M tokens (as of early 2024)
        model_pricing = {
            "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-4o": {"input": 0.01, "output": 0.03}
        }
        
        # Simplistic calculation (doesn't separate input/output tokens)
        if model in model_pricing:
            # Average of input and output costs since we don't know the split
            avg_cost = (model_pricing[model]["input"] + model_pricing[model]["output"]) / 2
            return (tokens / 1000000) * avg_cost
        
        return 0