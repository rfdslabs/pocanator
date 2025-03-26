"""
Deep Thinking Service for PoC Generation

This service enhances the generation of proof-of-concept exploits through
advanced chain-of-thought reasoning and multi-step problem solving.
"""
import logging
import json
from django.conf import settings
from apps.analysis.openai_compat import OpenAIClient
from apps.pocs.models import ProofOfConcept

logger = logging.getLogger(__name__)

class PoCDeepThinkingService:
    """
    Service for implementing enhanced deep thinking approaches to PoC generation.
    """
    
    # Default tokens for deep thinking mode
    DEFAULT_DEEP_THINKING_TOKENS = 8000
    
    # Chain of thought reasoning steps
    REASONING_STEPS = [
        "vulnerability_analysis", 
        "exploitation_vectors",
        "constraints_assessment",
        "approach_planning",
        "implementation_strategy",
        "review_and_verification"
    ]
    
    def __init__(self, api_key=None):
        """Initialize the deep thinking service."""
        self.api_key = api_key or getattr(settings, 'OPENAI_API_KEY', None)
        
        # Initialize the OpenAI client when needed
        self._client = None
    
    @property
    def client(self):
        """Lazy-load the OpenAI client."""
        if not self._client:
            if not self.api_key:
                raise ValueError('OpenAI API key is required for deep thinking')
            self._client = OpenAIClient(api_key=self.api_key)
        return self._client
    
    def enhance_prompt_with_deep_thinking(self, system_prompt, user_prompt, vulnerability_type):
        """
        Enhance prompts with deep thinking instructions.
        
        Args:
            system_prompt: Original system prompt
            user_prompt: Original user prompt
            vulnerability_type: Type of vulnerability
            
        Returns:
            Tuple of (enhanced_system_prompt, enhanced_user_prompt)
        """
        # Enhanced system prompt with chain-of-thought instructions
        enhanced_system = f"""
{system_prompt}

IMPORTANT: Use a chain-of-thought approach to solve this problem step by step:

1. VULNERABILITY ANALYSIS: First, thoroughly analyze the vulnerability details, including:
   - The exact type and nature of the vulnerability
   - The affected components and their interactions
   - The conditions required for exploitation
   - The expected impact when successfully exploited

2. EXPLOITATION VECTORS: Identify all possible exploitation vectors, considering:
   - Entry points into the vulnerable system
   - Data flow paths that trigger the vulnerability
   - Any specific input formats or protocols required
   - Potential filters or sanitization to bypass

3. CONSTRAINTS ASSESSMENT: Evaluate all constraints and requirements, including:
   - The specified target environment and language versions
   - Any timing or privilege requirements
   - Network or filesystem access limitations
   - Defensive measures that might interfere with exploitation

4. APPROACH PLANNING: Develop a comprehensive plan for exploitation that:
   - Chooses the most reliable vector based on constraints
   - Outlines each step in the exploitation process
   - Addresses potential points of failure
   - Offers alternatives where appropriate

5. IMPLEMENTATION STRATEGY: Design the implementation with:
   - Clean, focused code targeting the specific vulnerability
   - Proper error handling and feedback mechanisms
   - Clear documentation of each component's purpose
   - Modular structure for easy understanding and modification

6. REVIEW AND VERIFICATION: Finally, review your solution to ensure:
   - The code correctly demonstrates the vulnerability
   - All necessary setup instructions are provided
   - Security warnings are comprehensive
   - The approach is minimal and focused on the specific vulnerability
"""
        
        # Enhanced user prompt with additional guidance
        # Add vulnerability-specific deep thinking guidance
        specific_guidance = self.get_vulnerability_specific_guidance(vulnerability_type)
        
        enhanced_user = f"""
{user_prompt}

## Deep Thinking Mode

This task is being processed in Deep Thinking Mode. Please follow this structured approach:

{specific_guidance}

## Expected Output Structure

1. Chain of Thought Analysis:
   - First present your step-by-step reasoning process
   - Document each decision point and your rationale
   - Identify any challenges and how you overcame them
   - Note any assumptions you made and why

2. Solution:
   - Proof of Concept Code (with detailed comments)
   - Comprehensive Explanation
   - Complete Setup Instructions
   - Security Warnings and Responsible Use Guidelines

Use clear section headers to organize your response.
"""
        
        return enhanced_system.strip(), enhanced_user.strip()
    
    def get_vulnerability_specific_guidance(self, vulnerability_type):
        """
        Get vulnerability-specific deep thinking guidance.
        
        Args:
            vulnerability_type: Type of vulnerability
            
        Returns:
            String with specific guidance for this vulnerability type
        """
        guidance = {
            'RCE': """
For Remote Code Execution vulnerabilities, pay special attention to:
- Command construction and parameter handling
- Environment variable interactions
- Process spawning mechanisms
- Input sanitization bypasses
- Context-specific encoding requirements
- Shell command interpretation differences across platforms
- Command output capture and error handling
            """,
            
            'XSS': """
For Cross-Site Scripting vulnerabilities, pay special attention to:
- DOM manipulation vectors
- Context-specific encoding requirements (HTML, JS, URL, etc.)
- Content-Security-Policy bypass techniques
- Event handler registration methods
- Browser parsing inconsistencies
- Sanitization and filtering bypasses
- Storage vs. reflection mechanisms
            """,
            
            'SQLI': """
For SQL Injection vulnerabilities, pay special attention to:
- Database-specific syntax and quirks
- Query construction and parameter handling
- Type casting and conversion issues
- Comment syntax and query termination
- Error-based vs. blind techniques
- Defense bypass strategies
- Transaction and execution context
            """,
            
            'SSRF': """
For Server-Side Request Forgery vulnerabilities, pay special attention to:
- URL parsing inconsistencies
- Protocol handler behaviors
- Internal network addressing
- DNS rebinding opportunities
- Redirect following behavior
- Response processing peculiarities
- Firewall and filter bypasses
            """,
            
            'PATH_TRAVERSAL': """
For Path Traversal vulnerabilities, pay special attention to:
- Path normalization differences
- Directory separator handling
- Encoding and decoding behaviors
- Filesystem permission boundaries
- Symbolic link handling
- Path validation bypass techniques
- Operating system specific quirks
            """,
            
            'DESERIALIZATION': """
For Deserialization vulnerabilities, pay special attention to:
- Serialization format specifics
- Object graph manipulation
- Gadget chain construction
- Class loading mechanisms
- Type conversion during deserialization
- Trust boundaries within the application
- Execution flow during object reconstruction
            """,
            
            'DEFAULT': """
For this vulnerability, pay special attention to:
- Exact code patterns that expose the vulnerability
- Input handling and validation mechanisms
- Environment-specific behaviors
- Defensive measure bypasses
- Edge cases that trigger the vulnerability
- Exploitation reliability factors
- Minimizing unintended side effects
            """
        }
        
        return guidance.get(vulnerability_type, guidance['DEFAULT']).strip()
    
    def perform_deep_thinking_analysis(self, poc_id):
        """
        Perform a multi-step deep thinking analysis for a PoC.
        
        Args:
            poc_id: ID of the ProofOfConcept to analyze
            
        Returns:
            Dictionary with analysis results, or None if failed
        """
        try:
            poc = ProofOfConcept.objects.get(id=poc_id)
            
            # Only applicable for deep thinking mode
            if not poc.use_deep_thinking:
                logger.warning(f"Deep thinking analysis requested for PoC {poc_id} but it's not in deep thinking mode")
                return None
                
            # Get vulnerability type and context
            analysis = poc.analysis
            vuln_type = self.determine_vulnerability_type(analysis)
            
            # Extract advisory information
            advisory_text = analysis.advisory.description if analysis.advisory else "No advisory available"
            
            # Prepare the analysis object
            context = {
                "vulnerability_type": vuln_type,
                "advisory_id": analysis.advisory.github_id if analysis.advisory else "Unknown",
                "target_os": poc.target_os,
                "target_language_version": poc.target_language_version,
                "exploitation_goal": poc.exploitation_goal,
                "advisory_summary": advisory_text[:500] + ("..." if len(advisory_text) > 500 else "")
            }
            
            # Perform chain-of-thought reasoning for each step
            results = {}
            
            for step in self.REASONING_STEPS:
                step_result = self.process_reasoning_step(step, context, poc)
                if step_result:
                    results[step] = step_result
                    
                    # Update context with results from this step for next steps
                    if isinstance(step_result, dict) and 'summary' in step_result:
                        context[step] = step_result['summary']
                    else:
                        context[step] = str(step_result)[:300]  # Limit context size
            
            return results
            
        except ProofOfConcept.DoesNotExist:
            logger.error(f"PoC {poc_id} not found for deep thinking analysis")
            return None
        except Exception as e:
            logger.error(f"Error during deep thinking analysis for PoC {poc_id}: {str(e)}")
            return None
    
    def process_reasoning_step(self, step, context, poc):
        """
        Process a single reasoning step in the chain of thought.
        
        Args:
            step: The reasoning step to process
            context: Context information including previous steps
            poc: ProofOfConcept object
            
        Returns:
            Result of this reasoning step or None if failed
        """
        # Construct a specialized prompt for this reasoning step
        system_prompt = self.get_step_system_prompt(step)
        user_prompt = self.get_step_user_prompt(step, context)
        
        try:
            # Send to LLM for processing
            response = self.client.chat_completion(
                model=getattr(settings, 'POC_DEFAULT_MODEL', 'gpt-4o'),
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ],
                temperature=0.7,
                max_tokens=1500  # Smaller context for each step
            )
            
            content = response['content']
            
            # Process the result
            processed_result = self.process_step_result(step, content)
            return processed_result
            
        except Exception as e:
            logger.error(f"Error processing reasoning step {step}: {str(e)}")
            return None
    
    def get_step_system_prompt(self, step):
        """
        Get the system prompt for a specific reasoning step.
        
        Args:
            step: The reasoning step
            
        Returns:
            System prompt for this step
        """
        prompts = {
            "vulnerability_analysis": """
You are a vulnerability researcher specializing in vulnerability analysis.
Focus solely on understanding the nature of the vulnerability - its type, affected components, 
conditions for exploitation, and potential impact. 
Provide a detailed breakdown that would help someone develop a proof-of-concept.
            """,
            
            "exploitation_vectors": """
You are a penetration tester specializing in identifying exploitation vectors.
Focus solely on identifying all possible ways to exploit the vulnerability.
For each vector, consider entry points, data flow paths, input requirements, and bypasses needed.
Provide a clear, concise assessment to guide proof-of-concept development.
            """,
            
            "constraints_assessment": """
You are a security engineer specializing in understanding environmental constraints.
Focus solely on identifying all constraints and requirements that could impact exploitation.
Consider the target environment, language version, privileges, timing, and defensive measures.
Provide a practical assessment to guide proof-of-concept development.
            """,
            
            "approach_planning": """
You are a vulnerability researcher specializing in exploitation planning.
Focus solely on developing a comprehensive plan for exploitation based on the analysis so far.
Outline each step in the process, address potential failures, and offer alternatives where appropriate.
Provide a clear, structured plan that will guide the implementation.
            """,
            
            "implementation_strategy": """
You are a security developer specializing in proof-of-concept implementation.
Focus solely on designing the code implementation strategy based on the approach plan.
Consider code structure, error handling, documentation needs, and modular design.
Provide a blueprint for implementation that emphasizes clarity and focus.
            """,
            
            "review_and_verification": """
You are a security auditor specializing in code review and verification.
Focus solely on reviewing the planned approach and implementation strategy.
Identify potential issues, ensure completeness, and verify the approach demonstrates the vulnerability.
Provide a critical assessment with suggestions for improvement.
            """
        }
        
        return prompts.get(step, "You are a security researcher analyzing a vulnerability.").strip()
    
    def get_step_user_prompt(self, step, context):
        """
        Get the user prompt for a specific reasoning step.
        
        Args:
            step: The reasoning step
            context: Context information including previous steps
            
        Returns:
            User prompt for this step
        """
        # Base information to include
        base_info = f"""
Vulnerability Information:
- Type: {context.get('vulnerability_type', 'Unknown')}
- Advisory ID: {context.get('advisory_id', 'Unknown')}
- Target OS: {context.get('target_os', 'Unknown')}
- Target Language/Framework: {context.get('target_language_version', 'Unknown')}
- Exploitation Goal: {context.get('exploitation_goal', 'Unknown')}

Advisory Summary:
{context.get('advisory_summary', 'No summary available')}
        """
        
        # Include previous step results in context
        previous_context = ""
        for prev_step in self.REASONING_STEPS:
            if prev_step == step:
                break
            if prev_step in context:
                previous_context += f"\n## Previous Step: {prev_step.replace('_', ' ').title()}\n"
                previous_context += context[prev_step]
        
        prompts = {
            "vulnerability_analysis": f"""
{base_info}

Your task is to analyze this vulnerability in depth. Please provide:

1. A detailed classification of the vulnerability type and subtype
2. Identification of affected components and how they interact
3. The specific conditions required for successful exploitation
4. The expected impact when successfully exploited
5. Any notable features or characteristics of this vulnerability

Format your response as a structured analysis with clear sections.
            """,
            
            "exploitation_vectors": f"""
{base_info}
{previous_context}

Based on the vulnerability analysis, identify all possible exploitation vectors. Please provide:

1. The main entry points that could be used to trigger the vulnerability
2. The specific data flow paths that lead to the vulnerable code
3. Any required input formats, protocols, or structures
4. Potential filters, sanitization, or defenses that need to be bypassed
5. A ranking of vectors from most to least promising

Format your response as a structured analysis of each vector.
            """,
            
            "constraints_assessment": f"""
{base_info}
{previous_context}

Based on the exploitation vectors identified, assess all constraints that could impact exploitation. Please provide:

1. Environment-specific requirements or limitations
2. Language version or framework constraints
3. Timing, privilege, or access requirements
4. Defensive measures that might interfere with exploitation
5. Any other technical constraints to consider

Format your response as a structured assessment of each constraint category.
            """,
            
            "approach_planning": f"""
{base_info}
{previous_context}

Based on the vulnerability analysis, vectors, and constraints, develop a comprehensive exploitation plan. Please provide:

1. The selected primary exploitation vector with justification
2. A step-by-step approach to exploiting the vulnerability
3. Handling of identified constraints and requirements
4. Contingency measures for potential failures
5. Alternative approaches if the primary approach fails

Format your response as a structured, step-by-step plan.
            """,
            
            "implementation_strategy": f"""
{base_info}
{previous_context}

Based on the exploitation plan, design the implementation strategy for the proof-of-concept. Please provide:

1. The overall code structure and key components
2. Error handling and feedback mechanisms
3. Required documentation and comments
4. Modular breakdown for clarity and maintainability
5. Any libraries, tools, or external resources needed

Format your response as a structured implementation blueprint.
            """,
            
            "review_and_verification": f"""
{base_info}
{previous_context}

Review the complete approach to ensure the proof-of-concept will effectively demonstrate the vulnerability. Please provide:

1. Critical assessment of the approach and implementation strategy
2. Potential gaps or weaknesses in the planned approach
3. Verification methods to confirm successful exploitation
4. Suggestions for improving reliability or clarity
5. Final recommendations for implementation

Format your response as a structured review with clear recommendations.
            """
        }
        
        return prompts.get(step, f"{base_info}\n\nAnalyze this vulnerability step by step.").strip()
    
    def process_step_result(self, step, content):
        """
        Process the result from a reasoning step.
        
        Args:
            step: The reasoning step
            content: Content returned from the LLM
            
        Returns:
            Processed result (typically a dict with sections)
        """
        # Parse sections using common headers
        sections = {}
        current_section = "main"
        sections[current_section] = []
        
        for line in content.split('\n'):
            # Check if this line is a section header
            if line.strip().startswith(('#', '##', '###')) or any(line.strip().lower().startswith(f"{i}.") for i in range(1, 10)):
                # Extract the section name
                section_name = line.strip().lstrip('#').strip()
                if section_name.startswith(tuple(str(i) + "." for i in range(1, 10))):
                    section_name = section_name.split(".", 1)[1].strip()
                    
                # Convert to snake_case for consistency
                section_name = section_name.lower().replace(' ', '_')
                current_section = section_name
                sections[current_section] = []
            else:
                sections[current_section].append(line)
        
        # Join the lines in each section
        for section in sections:
            sections[section] = '\n'.join(sections[section]).strip()
        
        # Extract a summary for context in future steps
        summary = sections.get('summary', sections.get('main', content[:300]))
        
        # Create the result object
        result = {
            'step': step,
            'content': content,
            'sections': sections,
            'summary': summary
        }
        
        return result
    
    def determine_vulnerability_type(self, analysis):
        """
        Determine the vulnerability type based on analysis.
        
        Args:
            analysis: Analysis object for the vulnerability
            
        Returns:
            String with the vulnerability type
        """
        # First check if the analysis has a vuln_type field
        if hasattr(analysis, 'vuln_type') and analysis.vuln_type:
            vuln_type = analysis.vuln_type.lower()
            if 'rce' in vuln_type or 'remote code execution' in vuln_type:
                return 'RCE'
            elif 'xss' in vuln_type or 'cross-site scripting' in vuln_type:
                return 'XSS'
            elif 'sqli' in vuln_type or 'sql injection' in vuln_type:
                return 'SQLI'
            elif 'ssrf' in vuln_type or 'server-side request forgery' in vuln_type:
                return 'SSRF'
            elif 'path traversal' in vuln_type or 'directory traversal' in vuln_type:
                return 'PATH_TRAVERSAL'
            elif 'deserialization' in vuln_type:
                return 'DESERIALIZATION'
        
        # Get advisory text and analysis fields to search for vulnerability types
        advisory_text = analysis.advisory.description.lower() if analysis.advisory and analysis.advisory.description else ''
        
        # Combine relevant analysis fields
        analysis_texts = []
        for field in ['vuln_explanation', 'patch_analysis', 'impact_summary', 'markdown_report']:
            if hasattr(analysis, field) and getattr(analysis, field):
                analysis_texts.append(getattr(analysis, field).lower())
        
        combined_text = advisory_text + ' ' + ' '.join(analysis_texts)
        
        # Check for common vulnerability types
        if any(term in combined_text for term in ['rce', 'remote code execution', 'command injection', 'command execution']):
            return 'RCE'
        elif any(term in combined_text for term in ['xss', 'cross-site scripting', 'cross site scripting', 'script injection']):
            return 'XSS'
        elif any(term in combined_text for term in ['sqli', 'sql injection', 'sql-injection']):
            return 'SQLI'
        elif any(term in combined_text for term in ['ssrf', 'server-side request forgery', 'server side request forgery']):
            return 'SSRF'
        elif any(term in combined_text for term in ['path traversal', 'directory traversal', 'path manipulation']):
            return 'PATH_TRAVERSAL'
        elif any(term in combined_text for term in ['deserialization', 'deserialize', 'object deserialization']):
            return 'DESERIALIZATION'
        
        # Default if no specific type is detected
        return 'DEFAULT'
    
    def integrate_deep_thinking_results(self, poc_id, deep_thinking_results):
        """
        Integrate deep thinking results into the final PoC.
        
        Args:
            poc_id: ID of the ProofOfConcept
            deep_thinking_results: Results from deep thinking analysis
            
        Returns:
            Boolean indicating success
        """
        try:
            poc = ProofOfConcept.objects.get(id=poc_id)
            
            # Skip if not in deep thinking mode or already completed
            if not poc.use_deep_thinking or poc.status == 'completed':
                return False
                
            # Format the chain of thought results
            cot_explanation = self.format_chain_of_thought(deep_thinking_results)
            
            # Extract insights for the final prompting
            insights = self.extract_deep_thinking_insights(deep_thinking_results)
            
            # Store the insights in the PoC for later use
            poc.additional_context = json.dumps(insights)
            poc.save()
            
            return True
            
        except ProofOfConcept.DoesNotExist:
            logger.error(f"PoC {poc_id} not found for deep thinking integration")
            return False
        except Exception as e:
            logger.error(f"Error integrating deep thinking results for PoC {poc_id}: {str(e)}")
            return False
    
    def format_chain_of_thought(self, results):
        """
        Format chain of thought results into a coherent explanation.
        
        Args:
            results: Deep thinking results dictionary
            
        Returns:
            Formatted chain of thought explanation
        """
        if not results:
            return "No chain of thought analysis available."
            
        explanation = "# Chain of Thought Analysis\n\n"
        
        for step in self.REASONING_STEPS:
            if step in results:
                step_result = results[step]
                
                step_title = step.replace('_', ' ').title()
                explanation += f"## {step_title}\n\n"
                
                # If the result is a dictionary with sections, extract relevant parts
                if isinstance(step_result, dict):
                    if 'summary' in step_result:
                        explanation += step_result['summary'] + "\n\n"
                    elif 'content' in step_result:
                        explanation += step_result['content'] + "\n\n"
                else:
                    explanation += str(step_result) + "\n\n"
        
        return explanation
    
    def extract_deep_thinking_insights(self, results):
        """
        Extract key insights from deep thinking results.
        
        Args:
            results: Deep thinking results dictionary
            
        Returns:
            Dictionary with key insights
        """
        insights = {}
        
        if not results:
            return insights
            
        # Extract most valuable information from each step
        if 'vulnerability_analysis' in results:
            insights['vulnerability_type'] = self.extract_section_value(results['vulnerability_analysis'], 'classification')
            insights['affected_components'] = self.extract_section_value(results['vulnerability_analysis'], 'affected_components')
            
        if 'exploitation_vectors' in results:
            insights['primary_vector'] = self.extract_section_value(results['exploitation_vectors'], 'primary_vector')
            insights['entry_points'] = self.extract_section_value(results['exploitation_vectors'], 'entry_points')
            
        if 'constraints_assessment' in results:
            insights['key_constraints'] = self.extract_section_value(results['constraints_assessment'], 'constraints')
            
        if 'approach_planning' in results:
            insights['exploitation_steps'] = self.extract_section_value(results['approach_planning'], 'steps')
            
        if 'implementation_strategy' in results:
            insights['code_structure'] = self.extract_section_value(results['implementation_strategy'], 'structure')
            
        if 'review_and_verification' in results:
            insights['verification_methods'] = self.extract_section_value(results['review_and_verification'], 'verification')
            
        return insights
    
    def extract_section_value(self, step_result, section_key):
        """
        Extract a value from a section in step results.
        
        Args:
            step_result: Result from a reasoning step
            section_key: Section key to look for
            
        Returns:
            Extracted value or None
        """
        if isinstance(step_result, dict):
            # Try to find the section in the sections dict
            if 'sections' in step_result:
                for key, value in step_result['sections'].items():
                    if section_key in key.lower():
                        return value
                        
            # If not found, try to find it in the content
            if 'content' in step_result:
                content = step_result['content']
                lines = content.split('\n')
                
                # Look for section headers
                for i, line in enumerate(lines):
                    if section_key in line.lower() and i < len(lines) - 1:
                        # Extract the content after this header
                        section_content = []
                        for j in range(i + 1, min(i + 10, len(lines))):
                            if lines[j].strip() and not lines[j].strip().startswith(('#', '##', '###')):
                                section_content.append(lines[j])
                            elif lines[j].strip().startswith(('#', '##', '###')) and j > i + 1:
                                break
                                
                        if section_content:
                            return '\n'.join(section_content)
        
        return None