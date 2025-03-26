import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, unquote
import time
import random
import math
import html
import re
import os
import argparse # For command-line arguments
from collections import Counter
from dotenv import load_dotenv # To load .env file

# --- OpenAI ---
try:
    import openai
except ImportError:
    print("OpenAI library not found. Please install it: pip install openai")
    openai = None # Set to None if import fails

# --- Load Environment Variables ---
load_dotenv() # Load variables from .env file

# --- Configuration ---
BASE_SEARCH_URL = "https://github.com/advisories"
BASE_QUERY_PARAMS = {'query': 'rce type:reviewed rce'}
REQUEST_TIMEOUT = 20
MIN_DELAY = 0.8
MAX_DELAY = 2.0
MAX_PAGES_ALLOWED = 50
OUTPUT_HTML_FILE = "github_advisory_report.html"
SEVERITY_ORDER = {"Critical": 4, "High": 3, "Moderate": 2, "Low": 1, "Unknown": 0}

# Limits for text sent to OpenAI to avoid large bills/token limits
MAX_ADVISORY_TEXT_CHARS = 8000
MAX_DIFF_TEXT_CHARS = 10000

# --- Helper Functions ---
# (get_polite_delay, find_severity, parse_commit_url remain the same as previous version)
def get_polite_delay():
    return random.uniform(MIN_DELAY, MAX_DELAY)

def find_severity(soup):
    # ... (same as previous version - include the full function here) ...
    severity_classes = {
        'color-fg-severe': 'Critical', 'color-fg-danger': 'Critical',
        'color-fg-high': 'High', 'color-fg-attention': 'High',
        'color-fg-moderate': 'Moderate', 'color-fg-warning': 'Moderate',
        'color-fg-subtle': 'Low', 'color-text-secondary': 'Low'
    }
    severity_indicator = soup.find(lambda tag: tag.name == 'span' and tag.get('title', '').startswith(('Critical severity', 'High severity', 'Moderate severity', 'Low severity')))
    if severity_indicator:
        title_text = severity_indicator.get('title', '').lower()
        if 'critical' in title_text: return 'Critical'
        if 'high' in title_text: return 'High'
        if 'moderate' in title_text: return 'Moderate'
        if 'low' in title_text: return 'Low'
    for class_name, severity_level in severity_classes.items():
        severity_span = soup.find('span', class_=class_name)
        if severity_span and severity_span.get_text(strip=True).lower() == severity_level.lower():
            return severity_level
    body_text = soup.body.get_text(" ", strip=True) if soup.body else ""
    if "Critical severity" in body_text: return "Critical"
    if "High severity" in body_text: return "High"
    if "Moderate severity" in body_text: return "Moderate"
    if "Low severity" in body_text: return "Low"
    return "Unknown"

def parse_commit_url(commit_url):
    # ... (same as previous version - include the full function here) ...
    try:
        parsed = urlparse(commit_url)
        if parsed.netloc.lower() != 'github.com': return None, None, None
        match = re.search(r'/([^/]+)/([^/]+)/commit/([0-9a-fA-F]{40})', parsed.path)
        if match:
            repo_user, repo_name, commit_hash_full = match.groups()
            repo_full_name = f"{repo_user}/{repo_name}"
            commit_hash_short = commit_hash_full[:7]
            return repo_full_name, commit_hash_full, commit_hash_short
        else:
            parts = parsed.path.strip('/').split('/')
            if len(parts) >= 4 and parts[-2] == 'commit':
                 repo_full_name = f"{parts[0]}/{parts[1]}"
                 commit_hash_full = parts[-1]
                 if all(c in '0123456789abcdefABCDEF' for c in commit_hash_full):
                      commit_hash_short = commit_hash_full[:7]
                      return repo_full_name, commit_hash_full, commit_hash_short
    except Exception as e:
        print(f"  Warning: Could not parse commit URL '{commit_url}': {e}")
    return None, None, None

def extract_advisory_main_text(soup):
    """Extracts relevant descriptive text from the advisory page soup."""
    # Look for common containers for the main description
    main_content_selectors = [
        'div.markdown-body',        # Often holds the rendered markdown
        'article',                  # Semantic tag sometimes used
        'div[data-testid="vuln-description-markdown"]' # More specific test ID if available
    ]
    text_parts = []
    found_specific = False
    
    # First try to extract metadata separately
    metadata = {}
    try:
        # Try to extract CVSS score
        cvss_elements = soup.select('.Label[title*="CVSS"]')
        if cvss_elements:
            for element in cvss_elements:
                if 'title' in element.attrs and 'CVSS' in element['title']:
                    metadata['CVSS'] = element.get_text(strip=True)
        
        # Look for affected versions
        version_headers = soup.find_all(['h3', 'h4', 'strong'], string=lambda s: s and 'affected version' in s.lower())
        if version_headers:
            for header in version_headers:
                # Look for the nearest paragraph or list after the header
                sibling = header.find_next(['p', 'ul', 'ol'])
                if sibling:
                    metadata['Affected Versions'] = sibling.get_text(strip=True)
        
        # Extract CVE ID if present
        cve_pattern = re.compile(r'CVE-\d{4}-\d{4,}')
        for elem in soup.select('a'):
            if elem.text and cve_pattern.search(elem.text):
                metadata['CVE ID'] = cve_pattern.search(elem.text).group(0)
                break
                
    except Exception as e:
        print(f"  Warning: Error extracting metadata: {e}")
    
    # Then extract main content
    for selector in main_content_selectors:
        content_div = soup.select_one(selector)
        if content_div:
            # Prioritize more specific selectors if found
            if selector == main_content_selectors[-1] or selector == main_content_selectors[0]:
                text = content_div.get_text(separator="\n", strip=True)
                if text:
                    text_parts = [text] # Use this specific content
                    found_specific = True
                    break # Found a good candidate, stop searching
            elif not found_specific: # Use broader selectors only if specific ones fail
                text = content_div.get_text(separator="\n", strip=True)
                if text:
                    text_parts.append(text)

    if not text_parts and soup.body: # Fallback: grab more text if specific sections fail
        text_parts.append(soup.body.get_text(separator="\n", strip=True))

    full_text = "\n\n".join(text_parts)
    
    # Add metadata at the beginning if found
    if metadata:
        metadata_text = "### ADVISORY METADATA:\n"
        for key, value in metadata.items():
            metadata_text += f"- {key}: {value}\n"
        full_text = metadata_text + "\n\n" + full_text
    
    # Limit the text length
    if len(full_text) > MAX_ADVISORY_TEXT_CHARS:
        print(f"  Warning: Advisory text truncated from {len(full_text)} to {MAX_ADVISORY_TEXT_CHARS} characters.")
        full_text = full_text[:MAX_ADVISORY_TEXT_CHARS] + "\n... [TRUNCATED]"
    return full_text


# --- Core Fetching Functions ---
# (fetch_advisory_links_page remains the same)
def fetch_advisory_links_page(page_num, base_url, query_params):
    # ... (same as previous version - include the full function here) ...
    advisory_links = []
    headers = { 'User-Agent': 'Mozilla/5.0 ... Safari/537.36' } # Use your full UA
    current_query_params = query_params.copy()
    if page_num > 1: current_query_params['page'] = str(page_num)
    target_url = f"{base_url}?{urlencode(current_query_params)}"
    try:
        print(f"Fetching advisory list page {page_num} from: {target_url}")
        response = requests.get(target_url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        print(f"Parsing advisory list page {page_num}...")
        soup = BeautifulSoup(response.text, 'lxml')
        all_links = soup.find_all('a')
        processed_hrefs_on_page = set()
        for link_tag in all_links:
            href = link_tag.get('href')
            if href and href.startswith('/advisories/GHSA-') and href not in processed_hrefs_on_page:
                full_url = urljoin("https://github.com", href)
                advisory_links.append(full_url)
                processed_hrefs_on_page.add(href)
        if not advisory_links: print(f"Warning: Could not find any advisory links on page {page_num}.")
        return advisory_links
    except requests.exceptions.RequestException as e:
        print(f"Error fetching advisory list page {page_num} from {target_url}: {e}")
        return None
    except ImportError:
        print("Error: 'lxml' parser not found. Please install it using: pip install lxml"); return None
    except Exception as e:
        print(f"An unexpected error occurred while fetching page {page_num}: {e}")
        return None

# (fetch_severity_and_commits remains largely the same)
def fetch_severity_and_commits(advisory_url):
    # ... (same as previous version - include the full function here) ...
    commit_links = []
    severity = "Unknown"
    headers = { 'User-Agent': 'Mozilla/5.0 ... Safari/537.36' } # Use your full UA
    try:
        response = requests.get(advisory_url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        severity = find_severity(soup)
        link_elements = soup.find_all('a', class_='commit-link')
        processed_commits = set()
        for link_tag in link_elements:
            href = link_tag.get('href')
            if href and 'github.com' in href and '/commit/' in href and href not in processed_commits:
                commit_links.append(href)
                processed_commits.add(href)
        # Also return the parsed soup object for text extraction if needed later
        return severity, commit_links, soup
    except requests.exceptions.RequestException as e:
        print(f"  Error during requests to {advisory_url}: {e}")
        return None, None, None
    except ImportError:
        print("Error: 'lxml' parser not found. Please install it using: pip install lxml"); return None, None, None
    except Exception as e:
        print(f"  An unexpected error occurred processing {advisory_url}: {e}")
        return None, None, None

# New function to check if an advisory has commits without fetching all details
def has_commits(advisory_url, quick_check=True):
    """
    Checks if an advisory has any associated commits.
    
    Args:
        advisory_url (str): The URL of the GitHub advisory
        quick_check (bool): If True, will only check for commit links without parsing the entire page
                           If False, will use the full fetch_severity_and_commits function
    
    Returns:
        bool: True if advisory has commits, False otherwise
    """
    if quick_check:
        headers = { 'User-Agent': 'Mozilla/5.0 ... Safari/537.36' } # Use your full UA
        try:
            response = requests.get(advisory_url, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            # Use a simple string check first for efficiency
            if '/commit/' not in response.text and 'commit-link' not in response.text:
                return False
                
            # If potential commits exist, do a more thorough check
            soup = BeautifulSoup(response.text, 'lxml')
            link_elements = soup.find_all('a', class_='commit-link')
            
            for link_tag in link_elements:
                href = link_tag.get('href')
                if href and 'github.com' in href and '/commit/' in href:
                    return True
            return False
        except Exception as e:
            print(f"  Error checking for commits in {advisory_url}: {e}")
            return False
    else:
        # Use the full function for a more thorough check
        _, commits, _ = fetch_severity_and_commits(advisory_url)
        return commits is not None and len(commits) > 0


# --- HTML Report Generation ---
# (generate_html_report remains the same)
def generate_html_report(report_data, stats):
    """Generates the interactive HTML report file."""

    # Display filtering info if applicable
    filtered_info = ""
    if stats.get('filtered_by_commits'):
        filtered_info = f"""
        <div class="filter-info">
            <p><strong>Note:</strong> This report only includes advisories with associated commits.</p>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GitHub Advisory Commit Report</title>
    <style>
        body {{ font-family: sans-serif; margin: 20px; }}
        h1, h2 {{ color: #333; }}
        #stats {{ background-color: #f0f0f0; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        #stats p {{ margin: 5px 0; }}
        .filter-info {{ background-color: #e6f7ff; padding: 10px; border-left: 4px solid #1890ff; margin-bottom: 20px; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; font-size: 0.9em; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #e9e9e9; cursor: pointer; position: relative; }}
        th::after {{ content: ''; position: absolute; right: 8px; top: 50%; transform: translateY(-50%); border: 4px solid transparent; }}
        th.sort-asc::after {{ border-bottom-color: #333; }}
        th.sort-desc::after {{ border-top-color: #333; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
        a {{ color: #0366d6; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .severity-Critical {{ color: #d73a49; font-weight: bold; }}
        .severity-High {{ color: #cb2431; }}
        .severity-Moderate {{ color: #f66a0a; }}
        .severity-Low {{ color: #6a737d; }}
        .severity-Unknown {{ color: #999; font-style: italic; }}
        code {{ background-color: #f1f1f1; padding: 2px 4px; border-radius: 3px; font-family: monospace; }}
        .footer {{ margin-top: 20px; font-size: 0.8em; color: #666; }}
    </style>
</head>
<body>
    <h1>GitHub Advisory Commit Report</h1>
    
    {filtered_info}

    <div id="stats">
        <h2>Summary Statistics</h2>
        <p><strong>Pages Scanned:</strong> {stats.get('pages_scanned', 'N/A')}</p>
        <p><strong>Total Unique Advisories Scanned:</strong> {stats.get('advisories_scanned', 'N/A')}</p>
        <p><strong>Advisories with Fetching/Parsing Errors:</strong> {stats.get('advisories_error', 'N/A')}</p>
        <p><strong>Advisories with Commits Found:</strong> {stats.get('advisories_with_commits', 'N/A')}</p>
        <p><strong>Total Commits Found:</strong> {stats.get('total_commits', 'N/A')}</p>
        <p><strong>Commits by Advisory Severity:</strong></p>
        <ul>
"""
    # Add severity counts to stats list
    for severity, count in sorted(stats.get('severity_counts', {}).items(), key=lambda item: SEVERITY_ORDER.get(item[0], 0), reverse=True):
        html_content += f"            <li><span class=\"severity-{html.escape(severity)}\">{html.escape(severity)}</span>: {count}</li>\n"
    if not stats.get('severity_counts'):
         html_content += "            <li>No commits found to categorize by severity.</li>\n"

    html_content += f"""
        </ul>
    </div>

    <h2>Advisory Commits</h2>
    <p>Click column headers to sort.</p>
    <table id="commitTable">
        <thead>
            <tr>
                <th data-column-index="0" data-sort-type="severity">Severity</th>
                <th data-column-index="1" data-sort-type="text">Advisory</th>
                <th data-column-index="2" data-sort-type="text">Repository</th>
                <th data-column-index="3" data-sort-type="text">Commit Hash</th>
            </tr>
        </thead>
        <tbody>
"""

    # Add table rows from report_data
    if report_data:
        for item in report_data:
            adv_id = item['advisory_url'].split('/')[-1] # Get GHSA-xxxx-xxxx-xxxx part
            html_content += f"""
            <tr>
                <td class="severity-{html.escape(item['severity'])}">{html.escape(item['severity'])}</td>
                <td><a href="{html.escape(item['advisory_url'])}" target="_blank">{html.escape(adv_id)}</a></td>
                <td>{html.escape(item.get('repo_name', 'N/A'))}</td>
                <td><a href="{html.escape(item['commit_url'])}" target="_blank"><code>{html.escape(item.get('commit_hash_short', 'N/A'))}</code></a></td>
            </tr>"""
    else:
        html_content += '<tr><td colspan="4">No advisories with associated commits were found.</td></tr>'


    html_content += f"""
        </tbody>
    </table>

    <div class="footer">
        Report generated on: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}
        {" | Filtered by commits only" if stats.get('filtered_by_commits') else ""}
    </div>

    <script>
        const severityOrder = {{ "Critical": 4, "High": 3, "Moderate": 2, "Low": 1, "Unknown": 0 }};

        function sortTable(columnIndex, sortType) {{
            const table = document.getElementById("commitTable");
            const tbody = table.tBodies[0];
            const rows = Array.from(tbody.querySelectorAll("tr"));
            const header = table.tHead.querySelectorAll("th")[columnIndex];
            const currentIsAscending = header.classList.contains("sort-asc");
            const direction = currentIsAscending ? -1 : 1; // -1 for desc, 1 for asc

            // Remove previous sort indicators
            table.tHead.querySelectorAll("th").forEach(th => th.classList.remove("sort-asc", "sort-desc"));

            // Add new sort indicator
            header.classList.toggle("sort-asc", !currentIsAscending);
            header.classList.toggle("sort-desc", currentIsAscending);

            rows.sort((rowA, rowB) => {{
                let valA = rowA.querySelectorAll("td")[columnIndex].textContent.trim();
                let valB = rowB.querySelectorAll("td")[columnIndex].textContent.trim();

                // Custom sort logic based on type
                if (sortType === 'severity') {{
                    valA = severityOrder[valA] || 0;
                    valB = severityOrder[valB] || 0;
                    return (valA - valB) * direction;
                }} else {{ // Default: text sort (case-insensitive)
                     return valA.localeCompare(valB) * direction;
                }}

            }});

            // Re-append sorted rows
            tbody.innerHTML = ""; // Clear existing rows
            rows.forEach(row => tbody.appendChild(row));
        }}

        // Add click listeners to headers
        document.querySelectorAll("#commitTable th").forEach(header => {{
            header.addEventListener("click", () => {{
                const columnIndex = parseInt(header.getAttribute("data-column-index"));
                const sortType = header.getAttribute("data-sort-type") || 'text'; // Default to text sort
                sortTable(columnIndex, sortType);
            }});
        }});
    </script>
</body>
</html>
"""
    try:
        with open(OUTPUT_HTML_FILE, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"\nSuccessfully generated HTML report: {OUTPUT_HTML_FILE}")
    except IOError as e:
        print(f"\nError: Could not write HTML report file '{OUTPUT_HTML_FILE}': {e}")

# --- NEW: OpenAI Analysis Function ---
def analyze_advisory_with_gpt(advisory_url):
    """Fetches advisory, patch, and uses OpenAI to analyze them."""
    if not openai:
        print("OpenAI library is not available. Cannot perform analysis.")
        return

    print(f"\n--- Analyzing Advisory: {advisory_url} ---")

    # 1. Validate URL (basic check)
    if not advisory_url.startswith("https://github.com/advisories/GHSA-"):
        print("Error: Invalid GitHub Advisory URL format.")
        return

    # 1.5. Quick check for commits to save time and resources
    has_commits_found = has_commits(advisory_url)
    if not has_commits_found:
        print("Warning: No commits found for this advisory. Analysis of patches will be limited.")
        print("Feasibility score for PoC generation may be lower without patch information.")
    else:
        print("Found commits associated with this advisory. Proceeding with full analysis.")

    # 2. Fetch Advisory Page Content & Commits
    print("Fetching advisory details and commit links...")
    severity, commit_urls, soup = fetch_severity_and_commits(advisory_url)

    if soup is None:
        print("Error: Failed to fetch or parse the advisory page.")
        return

    print(f"Advisory Severity Found: {severity}")
    advisory_description_text = extract_advisory_main_text(soup)
    if not advisory_description_text:
        print("Warning: Could not extract main description text from the advisory page.")
        advisory_description_text = "[Extraction Failed]"
        
    # Check for related CVEs that might provide more information
    cve_refs = []
    cve_pattern = re.compile(r'CVE-\d{4}-\d{4,}')
    try:
        for a_tag in soup.select('a'):
            if a_tag.text and cve_pattern.search(a_tag.text):
                cve_id = cve_pattern.search(a_tag.text).group(0)
                if cve_id not in [ref['id'] for ref in cve_refs]:
                    cve_refs.append({
                        'id': cve_id,
                        'url': a_tag.get('href') if a_tag.get('href') and a_tag.get('href').startswith('http') else None
                    })

        if cve_refs:
            print(f"Found {len(cve_refs)} related CVE reference(s):")
            for ref in cve_refs:
                print(f"  - {ref['id']}: {ref['url'] or 'No direct URL'}")
                
            # Add CVE information to the advisory text
            if not "### ADVISORY METADATA:" in advisory_description_text:
                cve_text = "\n### ADVISORY METADATA:\n"
                for ref in cve_refs:
                    cve_text += f"- CVE ID: {ref['id']}\n"
                advisory_description_text = cve_text + "\n" + advisory_description_text
            
    except Exception as e:
        print(f"Warning: Error extracting CVE references: {e}")

    # 3. Fetch Patches/Diffs
    all_patch_diffs = []
    commit_urls_used = []
    
    if commit_urls:
        print(f"Found {len(commit_urls)} commit links")
        
        # Process each commit URL to fetch its diff
        for i, commit_url in enumerate(commit_urls[:3]):  # Limit to first 3 commits to avoid token limits
            diff_url = commit_url.split("?")[0] + ".diff"  # Ensure clean URL and add .diff
            print(f"Fetching patch diff {i+1}/{min(len(commit_urls), 3)} from: {diff_url}")
            
            try:
                headers = { 'User-Agent': 'Mozilla/5.0 ... Safari/537.36' }  # Use your full UA
                diff_response = requests.get(diff_url, headers=headers, timeout=REQUEST_TIMEOUT)
                diff_response.raise_for_status()  # Check for HTTP errors (like 404)
                
                # Parse the commit URL to get repository and commit details
                repo_name, commit_hash_full, commit_hash_short = parse_commit_url(commit_url)
                repo_info = f"{repo_name or 'Unknown Repo'} ({commit_hash_short or 'Unknown Hash'})"
                
                # Add this diff to our collection with metadata
                patch_diff = diff_response.text
                if len(patch_diff) > MAX_DIFF_TEXT_CHARS // min(len(commit_urls), 3):  # Divide max chars among patches
                    max_chars = MAX_DIFF_TEXT_CHARS // min(len(commit_urls), 3)
                    print(f"  Warning: Diff text truncated from {len(patch_diff)} to {max_chars} characters.")
                    patch_diff = patch_diff[:max_chars] + "\n... [TRUNCATED]"
                
                all_patch_diffs.append(f"--- PATCH {i+1}: {repo_info} ---\n{patch_diff}")
                commit_urls_used.append(commit_url)
                
                # Add delay between requests to be polite
                if i < min(len(commit_urls), 3) - 1:
                    time.sleep(get_polite_delay() / 2)
                    
            except requests.exceptions.RequestException as e:
                print(f"  Warning: Could not fetch diff file for {commit_url}: {e}")
                all_patch_diffs.append(f"--- PATCH {i+1}: [Diff Fetch Failed for {commit_url}] ---")
    else:
        print("No commit links found associated with this advisory.")
        all_patch_diffs.append("[No Patches Found]")
    
    # Combine all patches into a single text with separators
    patch_diff_text = "\n\n".join(all_patch_diffs)

    # 4. Check for OpenAI API Key
    api_key = os.getenv("openaikey")
    if not api_key:
        print("\nError: OpenAI API key not found.")
        print("Please set the 'openaikey' environment variable (e.g., in a .env file).")
        return

    # 5. Construct the Prompt
    prompt = f"""You are a cybersecurity analyst reviewing a GitHub Security Advisory and its associated patch (if available).

**Advisory URL:** {advisory_url}
**Advisory Severity:** {severity}

**Advisory Information:**
--- START ADVISORY ---
{advisory_description_text}
--- END ADVISORY ---

**Patch Information ({len(commit_urls_used) if commit_urls_used else 0} commits found):**
--- START PATCHES ---
{patch_diff_text}
--- END PATCHES ---

**Your Task:**
Based ONLY on the information provided above:
1.  **Vulnerability Explanation:** Briefly explain the vulnerability in clear, concise terms. What type of vulnerability is it (e.g., RCE, XSS, SQLi)? How could it potentially be triggered?
2.  **Patch Analysis:** If a patch was provided and fetched successfully, describe how it fixes the vulnerability based on the diff. What specific changes address the issue? If no patch was found or fetched, state that.
3.  **Impact Summary:** Briefly summarize the potential impact if this vulnerability were exploited, according to the advisory text.
4.  **Confidence Score (Patch Effectiveness):** If a patch was provided and fetched, provide a confidence score (Low/Medium/High) on how well the patch seems to address the described vulnerability, based *only* on the provided text and diff. Briefly justify the score. If no patch, state N/A.
5.  **PoC Feasibility Analysis:** Based ONLY on the information provided, analyze the feasibility of creating a proof-of-concept (PoC) exploit. Include:
   - Confidence level (0-10 scale)
   - Complexity assessment (Low/Medium/High)
   - Required knowledge/skills for exploitation
   - Availability of target environment information in the advisory
   - Information gaps that would need to be filled to create a working PoC
   - Key vulnerability components exposed by the patch that would be helpful for exploitation
   - DO NOT create or describe any actual exploit code.

6.  **Generate Report:** Combine points 1-5 into a structured report. Use markdown formatting.

7.  **Summary Table:** At the end of your report, include a simple machine-readable summary table in this exact format:
```
SEVERITY: [Critical/High/Moderate/Low/Unknown]
VULN_TYPE: [RCE/XSS/SQLI/etc]
PATCH_EFFECTIVENESS: [0-10]
POC_FEASIBILITY: [0-10]
POC_COMPLEXITY: [Low/Medium/High]
```

**Important:** Do not invent information. Stick strictly to the provided advisory text and patch diff. Clearly state if information (like the patch) is missing or could not be analyzed. Do NOT create or include any actual exploit code in your analysis, even if you have high confidence in your ability to create a PoC.
"""

    # 6. Call OpenAI API
    print("\nSending request to OpenAI API...")
    try:
        # Prepare API parameters
        api_params = {
            "model": "gpt-4o", # Full model for better analysis capabilities
            "messages": [
                {"role": "system", "content": "You are an expert cybersecurity analyst specializing in vulnerability assessment and exploit development. You have extensive experience analyzing patches and determining exploit feasibility. You can identify key vulnerability indicators in code changes and assess how difficult it would be to create a PoC based solely on patches, advisories, and technical expertise."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3, # Lower temperature for more focused, factual output
            "max_tokens": 2500 # Increased token limit for detailed analysis
        }
        
        # Handle different OpenAI library versions
        try:
            # Try modern initialization - v1.0.0+
            if hasattr(openai, 'OpenAI'):
                client = openai.OpenAI(api_key=api_key)
                response = client.chat.completions.create(**api_params)
            elif hasattr(openai, 'Client'):
                # Alternative modern initialization
                client = openai.Client(api_key=api_key)
                response = client.chat.completions.create(**api_params)
            else:
                # Legacy initialization - v0.x.x
                openai.api_key = api_key
                response = openai.ChatCompletion.create(**api_params)
        except TypeError as e:
            # Handle TypeError for unsupported parameters
            print(f"API initialization error, trying fallback method: {e}")
            openai.api_key = api_key
            response = openai.ChatCompletion.create(**api_params)

        # Handle different response formats
        try:
            # Modern client response format
            if hasattr(response, 'choices') and hasattr(response.choices[0], 'message'):
                analysis_result = response.choices[0].message.content
            # Legacy client response format
            elif isinstance(response, dict) and 'choices' in response:
                analysis_result = response['choices'][0]['message']['content']
            else:
                # Fallback if we can't determine the structure
                print("Warning: Unable to determine OpenAI response structure, using string representation")
                analysis_result = str(response)
        except Exception as e:
            print(f"Error extracting data from OpenAI response: {e}")
            raise

        # 7. Extract and format results
        analysis_result_full = analysis_result
        
        # Extract key metrics from the summary table if present
        summary_metrics = {}
        metrics_display = ""
        try:
            if "```" in analysis_result and "SEVERITY:" in analysis_result:
                # Find the summary table section
                table_section = analysis_result.split("```")
                for section in table_section:
                    if "SEVERITY:" in section and "POC_FEASIBILITY:" in section:
                        metrics_text = section.strip()
                        # Parse each line
                        for line in metrics_text.split('\n'):
                            if ':' in line:
                                key, value = line.split(':', 1)
                                summary_metrics[key.strip()] = value.strip()
                
                # Format metrics for display
                if summary_metrics:
                    metrics_display = "\n--- KEY METRICS ---"
                    if 'VULN_TYPE' in summary_metrics:
                        metrics_display += f"\nVulnerability Type: {summary_metrics['VULN_TYPE']}"
                    if 'SEVERITY' in summary_metrics:
                        metrics_display += f"\nSeverity: {summary_metrics['SEVERITY']}"
                    if 'PATCH_EFFECTIVENESS' in summary_metrics:
                        metrics_display += f"\nPatch Effectiveness: {summary_metrics['PATCH_EFFECTIVENESS']}/10"
                    if 'POC_FEASIBILITY' in summary_metrics:
                        metrics_display += f"\nPoC Feasibility: {summary_metrics['POC_FEASIBILITY']}/10"
                    if 'POC_COMPLEXITY' in summary_metrics:
                        metrics_display += f"\nPoC Complexity: {summary_metrics['POC_COMPLEXITY']}"
        except Exception as e:
            print(f"Warning: Error parsing summary metrics: {e}")
        
        # 8. Display Results
        print("\n--- OpenAI Analysis Report ---")
        
        # Display metrics first if available
        if summary_metrics:
            print(metrics_display)
            print("\n--- FULL REPORT ---")
            
        print(analysis_result_full)
        print("--- End of Report ---")
        
        # 9. Optionally save results to file
        try:
            ghsa_id = advisory_url.split('/')[-1]
            report_filename = f"{ghsa_id}_analysis.md"
            with open(report_filename, 'w', encoding='utf-8') as f:
                f.write(f"# Analysis Report for {ghsa_id}\n\n")
                
                # Add advisory and commit info
                f.write(f"**Advisory URL:** {advisory_url}\n")
                f.write(f"**Severity:** {severity}\n")
                if commit_urls_used:
                    f.write(f"**Commits Analyzed:** {len(commit_urls_used)}\n")
                    for i, url in enumerate(commit_urls_used):
                        repo_name, _, commit_hash_short = parse_commit_url(url)
                        f.write(f"  - [{repo_name or 'Unknown'} @ {commit_hash_short or 'Unknown'}]({url})\n")
                f.write("\n")
                
                # Add metrics section
                if summary_metrics:
                    f.write("## Key Metrics\n\n")
                    f.write("| Metric | Value |\n")
                    f.write("| ------ | ----- |\n")
                    if 'VULN_TYPE' in summary_metrics:
                        f.write(f"| Vulnerability Type | {summary_metrics['VULN_TYPE']} |\n")
                    if 'SEVERITY' in summary_metrics:
                        f.write(f"| Severity | {summary_metrics['SEVERITY']} |\n")
                    if 'PATCH_EFFECTIVENESS' in summary_metrics:
                        f.write(f"| Patch Effectiveness | {summary_metrics['PATCH_EFFECTIVENESS']}/10 |\n")
                    if 'POC_FEASIBILITY' in summary_metrics:
                        f.write(f"| PoC Feasibility | {summary_metrics['POC_FEASIBILITY']}/10 |\n")
                    if 'POC_COMPLEXITY' in summary_metrics:
                        f.write(f"| PoC Complexity | {summary_metrics['POC_COMPLEXITY']} |\n")
                    f.write("\n")
                
                # Add full report
                f.write("## Full Report\n\n")
                f.write(analysis_result_full)
                
                # Add timestamp
                f.write(f"\n\n---\n*Generated on: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}*")
            
            print(f"\nReport saved to: {report_filename}")
        except Exception as e:
            print(f"Error saving report file: {e}")
            
    except openai.APIConnectionError as e:
        print(f"OpenAI API request failed: Connection error - {e}")
    except openai.RateLimitError as e:
        print(f"OpenAI API request failed: Rate limit exceeded - {e}")
    except openai.AuthenticationError as e:
        print(f"OpenAI API request failed: Authentication error - {e}")
        print("Please check your API key.")
    except openai.APIError as e:
        print(f"OpenAI API request failed: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


# --- Main Execution ---
if __name__ == "__main__":

    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Fetch GitHub Advisory data and optionally analyze with OpenAI.")
    parser.add_argument(
        "--gpthack",
        metavar="ADVISORY_URL",
        type=str,
        help="Analyze a single GitHub Advisory URL using OpenAI."
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=0, # Default to 0, indicating prompt is needed if not gpthack
        help=f"Number of advisory list pages to fetch for HTML report (1-{MAX_PAGES_ALLOWED}). Overrides interactive prompt if > 0."
    )
    parser.add_argument(
        "--only-with-commits",
        action="store_true",
        help="Only process advisories that have associated commits. This improves efficiency for PoC generation."
    )
    parser.add_argument(
        "--query",
        type=str,
        help=f"Custom search query to use instead of the default '{BASE_QUERY_PARAMS['query']}'"
    )

    args = parser.parse_args()

    # --- Mode Selection ---
    if args.gpthack:
        # Execute OpenAI analysis mode
        analyze_advisory_with_gpt(args.gpthack)
    else:
        # Execute original HTML report generation mode

        # --- Get User Input for Pagination (if not provided via args) ---
        num_pages_to_fetch = args.pages
        if not (1 <= num_pages_to_fetch <= MAX_PAGES_ALLOWED):
            while True:
                try:
                    num_pages_str = input(f"How many pages of advisories do you want to fetch for the HTML report? (1-{MAX_PAGES_ALLOWED}): ")
                    num_pages_to_fetch = int(num_pages_str)
                    if 1 <= num_pages_to_fetch <= MAX_PAGES_ALLOWED:
                        break
                    else:
                        print(f"Please enter a number between 1 and {MAX_PAGES_ALLOWED}.")
                except ValueError:
                    print("Invalid input. Please enter a whole number.")
                except EOFError:
                    print("Input stream closed. Exiting.")
                    exit()

        # Determine whether to filter by commits
        filter_by_commits = args.only_with_commits
        if not filter_by_commits and args.only_with_commits is None:  # If not specified via args
            try:
                filter_choice = input("Only process advisories with associated commits? (y/n, default=n): ").strip().lower()
                filter_by_commits = filter_choice in ('y', 'yes', 'true')
            except EOFError:
                print("Input stream closed. Exiting.")
                exit()
        
        if filter_by_commits:
            print("Note: Only advisories with commits will be processed. This may significantly reduce the number of processed advisories.")

        # Setup query parameters
        query_params = BASE_QUERY_PARAMS.copy()
        if args.query:
            query_params['query'] = args.query
            print(f"Using custom search query: {args.query}")

        # --- Step 1: Fetch Advisory Links ---
        print("\n--- Step 1: Fetching Advisory Links for HTML Report ---")
        all_advisory_urls = []
        failed_pages = []
        master_processed_hrefs = set()
        for page in range(1, num_pages_to_fetch + 1):
            page_links = fetch_advisory_links_page(page, BASE_SEARCH_URL, query_params)
            # ... (rest of link aggregation logic same as previous version) ...
            if page_links is None: failed_pages.append(page)
            elif page_links:
                 new_links_count = 0
                 for link in page_links:
                     path = urlparse(link).path
                     if path not in master_processed_hrefs:
                         all_advisory_urls.append(link)
                         master_processed_hrefs.add(path)
                         new_links_count += 1
                 print(f"  Added {new_links_count} unique links from page {page}.")
            else: print(f"  No new links found on page {page}.")
            if page < num_pages_to_fetch: time.sleep(get_polite_delay() / 2)

        if failed_pages: print(f"\nWarning: Failed to fetch or parse lists for page(s): {', '.join(map(str, failed_pages))}")
        if not all_advisory_urls: print("\nNo advisory links retrieved. Cannot generate report."); exit()

        # --- Step 1.5: Pre-filter advisories by commits if requested ---
        filtered_advisory_urls = []
        if filter_by_commits:
            print(f"\n--- Pre-filtering {len(all_advisory_urls)} advisories to find those with commits ---")
            filtered_count = 0
            for i, adv_url in enumerate(all_advisory_urls):
                print(f"Checking for commits ({i+1}/{len(all_advisory_urls)}): {adv_url}")
                if has_commits(adv_url):
                    filtered_advisory_urls.append(adv_url)
                    filtered_count += 1
                    print(f"  Found commits!")
                time.sleep(get_polite_delay() / 2)  # Use a shorter delay for quick checks
            
            print(f"\nFound {filtered_count} out of {len(all_advisory_urls)} advisories with commits ({filtered_count/len(all_advisory_urls)*100:.1f}%)")
            all_advisory_urls = filtered_advisory_urls
            
            if not all_advisory_urls:
                print("\nNo advisories with commits found. Cannot generate report.")
                exit()

        # --- Step 2: Process Advisories for Report ---
        print(f"\n--- Step 2: Processing {len(all_advisory_urls)} Unique Advisories for HTML Report ---")
        report_data = []
        advisory_fetch_errors = 0
        advisories_with_commits_count = 0
        severity_counts_with_commits = Counter()
        for i, adv_url in enumerate(all_advisory_urls):
            print(f"Processing ({i+1}/{len(all_advisory_urls)}): {adv_url}")
            # Note: fetch_severity_and_commits now returns soup too, but we discard it here
            severity, commit_urls, _ = fetch_severity_and_commits(adv_url)
            # ... (rest of data aggregation for HTML report same as previous version) ...
            if severity is None and commit_urls is None: advisory_fetch_errors += 1
            elif commit_urls:
                 advisories_with_commits_count += 1
                 severity_counts_with_commits[severity] += len(commit_urls)
                 for commit_url in commit_urls:
                     repo_name, commit_hash_full, commit_hash_short = parse_commit_url(commit_url)
                     report_data.append({
                         'advisory_url': adv_url, 'severity': severity, 'commit_url': commit_url,
                         'repo_name': repo_name or "Parse Error",
                         'commit_hash_full': commit_hash_full or "Parse Error",
                         'commit_hash_short': commit_hash_short or "Parse Error",
                     })
            time.sleep(get_polite_delay())

        # --- Step 3: Generate HTML Report ---
        print("\n--- Step 3: Generating HTML Report ---")
        stats = {
            'pages_scanned': num_pages_to_fetch, 'advisories_scanned': len(all_advisory_urls),
            'advisories_error': advisory_fetch_errors, 'advisories_with_commits': advisories_with_commits_count,
            'total_commits': len(report_data), 'severity_counts': dict(severity_counts_with_commits),
            'filtered_by_commits': filter_by_commits
        }
        generate_html_report(report_data, stats)

    print("\nDone.")
