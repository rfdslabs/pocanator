#!/usr/bin/env python3
"""
Patch Analysis Module for Plurium POCanator
Provides detailed patch analysis and generates HTML reports with comprehensive diff visualization
"""

import os
import re
import time
import json
import argparse
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
import requests
from bs4 import BeautifulSoup
import difflib
import chevron # For Mustache templating

# --- Constants ---
TEMPLATE_PATH = "patch_report_template.html"
DEFAULT_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
REQUEST_TIMEOUT = 20

class CommitDiff:
    """Represents a parsed diff for a single commit"""
    
    def __init__(self, repo_name: str, commit_hash: str, commit_url: str, diff_text: str):
        self.repo_name = repo_name
        self.commit_hash = commit_hash
        self.commit_url = commit_url
        self.raw_diff = diff_text
        self.files: List[Dict[str, Any]] = []
        self.lines_added = 0
        self.lines_removed = 0
        self.parse_diff()
    
    def parse_diff(self) -> None:
        """Parse the raw diff text into structured data"""
        if not self.raw_diff:
            return
        
        current_file = None
        current_lines = []
        
        lines = self.raw_diff.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # New file header
            if line.startswith('diff --git'):
                # Save previous file if exists
                if current_file:
                    current_file['lines'] = current_lines
                    self.files.append(current_file)
                
                # Extract file path from the diff header
                file_path = self._extract_file_path_from_header(lines, i)
                
                current_file = {
                    'file_path': file_path,
                    'is_binary': False,
                    'lines_added': 0,
                    'lines_removed': 0
                }
                current_lines = []
                
                # Skip ahead to find hunk headers
                while i < len(lines) and not lines[i].startswith('@@'):
                    if 'Binary files' in lines[i]:
                        current_file['is_binary'] = True
                    i += 1
                
                if i >= len(lines):
                    break
            
            # Hunk header
            if line.startswith('@@'):
                hunk_header = line
                i += 1
                
                old_line_num = 0
                new_line_num = 0
                
                # Extract line numbers from hunk header
                match = re.search(r'@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@', hunk_header)
                if match:
                    old_line_num = int(match.group(1))
                    new_line_num = int(match.group(2))
                
                # Process lines in this hunk
                while i < len(lines) and not (lines[i].startswith('diff --git') or lines[i].startswith('@@')):
                    content = lines[i]
                    
                    if not content:
                        i += 1
                        continue
                    
                    line_type = content[0] if content else ' '
                    code = content[1:] if content else ''
                    
                    if line_type == '+':
                        current_lines.append({
                            'type': 'add',
                            'old_line_num': '',
                            'new_line_num': new_line_num,
                            'content': code
                        })
                        new_line_num += 1
                        current_file['lines_added'] += 1
                        self.lines_added += 1
                    elif line_type == '-':
                        current_lines.append({
                            'type': 'remove',
                            'old_line_num': old_line_num,
                            'new_line_num': '',
                            'content': code
                        })
                        old_line_num += 1
                        current_file['lines_removed'] += 1
                        self.lines_removed += 1
                    elif line_type == ' ':
                        current_lines.append({
                            'type': 'context',
                            'old_line_num': old_line_num,
                            'new_line_num': new_line_num,
                            'content': code
                        })
                        old_line_num += 1
                        new_line_num += 1
                    
                    i += 1
                
                # Don't increment i if we've reached a new diff or hunk
                continue
            
            i += 1
        
        # Add the last file
        if current_file:
            current_file['lines'] = current_lines
            self.files.append(current_file)
    
    def _extract_file_path_from_header(self, lines: List[str], start_idx: int) -> str:
        """Extract the file path from diff headers"""
        # Try to find the most accurate filename
        file_path = ""
        
        # Look for the a/ and b/ prefixed paths
        for j in range(start_idx, min(start_idx + 5, len(lines))):
            if lines[j].startswith('--- a/'):
                file_path = lines[j][6:]
                break
            elif lines[j].startswith('+++ b/'):
                file_path = lines[j][6:]
                break
        
        # If that failed, try to extract from the diff --git line
        if not file_path and lines[start_idx].startswith('diff --git'):
            match = re.search(r'diff --git a/(.*) b/(.*)', lines[start_idx])
            if match:
                file_path = match.group(2)  # Use the 'b' path as it's the new version
        
        return file_path
    
    def get_template_data(self, index: int) -> Dict[str, Any]:
        """Get template data for this commit"""
        diff_blocks = []
        
        for file in self.files:
            if file['is_binary']:
                # Skip binary files
                continue
                
            lines_data = []
            for line in file['lines']:
                line_class = ""
                if line['type'] == 'add':
                    line_class = "diff-add"
                elif line['type'] == 'remove':
                    line_class = "diff-remove"
                
                lines_data.append({
                    'LINE_CLASS': line_class,
                    'OLD_LINE_NUM': line['old_line_num'],
                    'NEW_LINE_NUM': line['new_line_num'],
                    'CONTENT': line['content']
                })
            
            if lines_data:
                diff_blocks.append({
                    'FILE_PATH': file['file_path'],
                    'LINES': lines_data
                })
        
        return {
            'INDEX': index,
            'ACTIVE_CLASS': 'active' if index == 1 else '',
            'REPO_NAME': self.repo_name,
            'COMMIT_HASH': self.commit_hash[:7],  # Short hash
            'COMMIT_URL': self.commit_url,
            'LINES_ADDED': self.lines_added,
            'LINES_REMOVED': self.lines_removed,
            'DIFF_BLOCKS': diff_blocks
        }

class AdvisoryAnalyzer:
    """Analyzes GitHub security advisories and their patches"""
    
    def __init__(self, advisory_url: str, output_dir: str = '.'):
        self.advisory_url = advisory_url
        self.output_dir = output_dir
        self.advisory_id = self._extract_advisory_id(advisory_url)
        self.severity = "Unknown"
        self.advisory_data = {}
        self.commit_diffs = []
        self.html_content = ""
        self.template_data = {}
    
    def _extract_advisory_id(self, url: str) -> str:
        """Extract the GHSA ID from the URL"""
        match = re.search(r'GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}', url)
        return match.group(0) if match else "unknown-advisory"
    
    def fetch_advisory(self) -> bool:
        """Fetch the advisory page and extract information"""
        print(f"Fetching advisory: {self.advisory_url}")
        
        try:
            headers = {'User-Agent': DEFAULT_USER_AGENT}
            response = requests.get(self.advisory_url, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract severity
            self.severity = self._extract_severity(soup)
            print(f"Advisory severity: {self.severity}")
            
            # Extract advisory metadata
            self.advisory_data = {
                'id': self.advisory_id,
                'url': self.advisory_url,
                'title': self._extract_title(soup),
                'description': self._extract_description(soup),
                'severity': self.severity,
                'cve_id': self._extract_cve_id(soup),
                'cvss_score': self._extract_cvss_score(soup),
                'affected_versions': self._extract_affected_versions(soup),
                'published_date': self._extract_published_date(soup),
                'commit_links': self._extract_commit_links(soup)
            }
            
            print(f"Found {len(self.advisory_data['commit_links'])} commit link(s)")
            return True
            
        except Exception as e:
            print(f"Error fetching advisory: {e}")
            return False
    
    def _extract_severity(self, soup: BeautifulSoup) -> str:
        """Extract the severity level from the advisory page"""
        severity_classes = {
            'color-fg-severe': 'Critical', 
            'color-fg-danger': 'Critical',
            'color-fg-high': 'High', 
            'color-fg-attention': 'High',
            'color-fg-moderate': 'Moderate', 
            'color-fg-warning': 'Moderate',
            'color-fg-subtle': 'Low', 
            'color-text-secondary': 'Low'
        }
        
        # Try from title attribute
        severity_indicator = soup.find(lambda tag: tag.name == 'span' and tag.get('title', '').startswith(
            ('Critical severity', 'High severity', 'Moderate severity', 'Low severity')))
        if severity_indicator:
            title_text = severity_indicator.get('title', '').lower()
            if 'critical' in title_text: return 'Critical'
            if 'high' in title_text: return 'High'
            if 'moderate' in title_text: return 'Moderate'
            if 'low' in title_text: return 'Low'
        
        # Try from CSS classes
        for class_name, severity_level in severity_classes.items():
            severity_span = soup.find('span', class_=class_name)
            if severity_span and severity_span.get_text(strip=True).lower() == severity_level.lower():
                return severity_level
        
        # Try from text in body
        body_text = soup.body.get_text(" ", strip=True) if soup.body else ""
        if "Critical severity" in body_text: return "Critical"
        if "High severity" in body_text: return "High"
        if "Moderate severity" in body_text: return "Moderate"
        if "Low severity" in body_text: return "Low"
        
        return "Unknown"
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract the advisory title"""
        title_elem = soup.find('h1')
        return title_elem.get_text(strip=True) if title_elem else "Unknown Title"
    
    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Extract the advisory description"""
        # Look for common containers for the main description
        main_content_selectors = [
            'div.markdown-body',        # Often holds the rendered markdown
            'article',                  # Semantic tag sometimes used
            'div[data-testid="vuln-description-markdown"]' # More specific test ID
        ]
        
        for selector in main_content_selectors:
            content_div = soup.select_one(selector)
            if content_div:
                return content_div.get_text("\n", strip=True)
        
        return "No description available"
    
    def _extract_cve_id(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract CVE ID if present"""
        cve_pattern = re.compile(r'CVE-\d{4}-\d{4,}')
        for elem in soup.select('a'):
            if elem.text and cve_pattern.search(elem.text):
                return cve_pattern.search(elem.text).group(0)
        return None
    
    def _extract_cvss_score(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract CVSS score if present"""
        cvss_elements = soup.select('.Label[title*="CVSS"]')
        if cvss_elements:
            for element in cvss_elements:
                if 'title' in element.attrs and 'CVSS' in element['title']:
                    return element.get_text(strip=True)
        return None
    
    def _extract_affected_versions(self, soup: BeautifulSoup) -> str:
        """Extract affected versions information"""
        # Look for version headers
        version_headers = soup.find_all(['h3', 'h4', 'strong'], 
                                    string=lambda s: s and 'affected version' in s.lower())
        if version_headers:
            for header in version_headers:
                # Find nearest paragraph or list after header
                sibling = header.find_next(['p', 'ul', 'ol'])
                if sibling:
                    return sibling.get_text(strip=True)
        
        # Alternative: look for specific sections or tables
        affected_section = soup.find(['div', 'section'], string=lambda s: s and 'affected' in s.lower())
        if affected_section:
            return affected_section.get_text(strip=True)
            
        return "Not specified"
    
    def _extract_published_date(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract the published date of the advisory"""
        date_elem = soup.find(['relative-time', 'time-ago', 'time'])
        if date_elem:
            if date_elem.has_attr('datetime'):
                return date_elem['datetime']
            return date_elem.get_text(strip=True)
        return None
    
    def _extract_commit_links(self, soup: BeautifulSoup) -> List[str]:
        """Extract commit links from the advisory page"""
        commit_links = []
        link_elements = soup.find_all('a', class_='commit-link')
        
        processed_commits = set()
        for link_tag in link_elements:
            href = link_tag.get('href')
            if href and 'github.com' in href and '/commit/' in href and href not in processed_commits:
                commit_links.append(href)
                processed_commits.add(href)
                
        return commit_links
    
    def fetch_commit_diffs(self) -> bool:
        """Fetch diffs for each commit"""
        if not self.advisory_data['commit_links']:
            print("No commit links found!")
            return False
            
        for commit_url in self.advisory_data['commit_links'][:3]:  # Limit to 3 commits
            try:
                # Parse commit URL to get repository and commit details
                repo_name, commit_hash = self._parse_commit_url(commit_url)
                
                if not repo_name or not commit_hash:
                    print(f"  Warning: Could not parse commit URL: {commit_url}")
                    continue
                
                # Get the diff URL
                diff_url = commit_url.split("?")[0] + ".diff"
                print(f"Fetching diff from: {diff_url}")
                
                headers = {'User-Agent': DEFAULT_USER_AGENT}
                diff_response = requests.get(diff_url, headers=headers, timeout=REQUEST_TIMEOUT)
                diff_response.raise_for_status()
                
                # Parse the diff
                diff_text = diff_response.text
                commit_diff = CommitDiff(repo_name, commit_hash, commit_url, diff_text)
                self.commit_diffs.append(commit_diff)
                
                print(f"  Processed diff: +{commit_diff.lines_added}/-{commit_diff.lines_removed} lines")
                time.sleep(1)  # Be polite with requests
                
            except Exception as e:
                print(f"  Error fetching diff for {commit_url}: {e}")
        
        return len(self.commit_diffs) > 0
    
    def _parse_commit_url(self, commit_url: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse a GitHub commit URL to extract repo name and commit hash"""
        try:
            parsed = re.search(r'github\.com/([^/]+/[^/]+)/commit/([0-9a-fA-F]{40})', commit_url)
            if parsed:
                repo_name = parsed.group(1)
                commit_hash = parsed.group(2)
                return repo_name, commit_hash
        except Exception:
            pass
        
        return None, None
    
    def generate_html_report(self, metrics: Dict[str, str] = None) -> bool:
        """Generate HTML report from template"""
        try:
            if not os.path.exists(TEMPLATE_PATH):
                print(f"Error: Template file not found at {TEMPLATE_PATH}")
                return False
                
            with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
                template = f.read()
            
            # Prepare template data
            self.template_data = {
                'ADVISORY_ID': self.advisory_id,
                'ADVISORY_URL': self.advisory_url,
                'GENERATION_DATE': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'SEVERITY': self.advisory_data['severity'],
                'CVE_ID': self.advisory_data.get('cve_id', ''),
                'CVSS_SCORE': self.advisory_data.get('cvss_score', ''),
                'AFFECTED_VERSIONS': self.advisory_data.get('affected_versions', 'Not specified'),
                'VULN_TYPE': metrics.get('VULN_TYPE', 'Unknown') if metrics else 'Unknown',
                'COMMITS_COUNT': len(self.commit_diffs),
                'DISCLOSURE_DATE': self.advisory_data.get('published_date', 'Unknown'),
                'PATCH_DATE': 'Unknown',  # Usually not directly available
                'ADVISORY_DATE': self.advisory_data.get('published_date', 'Unknown'),
            }
            
            # Add metrics data if available
            if metrics:
                self.template_data.update({
                    'POC_FEASIBILITY': metrics.get('POC_FEASIBILITY', '?'),
                    'PATCH_EFFECTIVENESS': metrics.get('PATCH_EFFECTIVENESS', '?'),
                    'POC_COMPLEXITY': metrics.get('POC_COMPLEXITY', 'Unknown'),
                    'VULN_EXPLANATION': metrics.get('VULN_EXPLANATION', 'Not available'),
                    'IMPACT_SUMMARY': metrics.get('IMPACT_SUMMARY', 'Not available'),
                    'POC_FEASIBILITY_ANALYSIS': metrics.get('POC_ANALYSIS', 'Not available'),
                    'REQUIRED_SKILLS': metrics.get('REQUIRED_SKILLS', 'Not specified'),
                    'INFORMATION_GAPS': metrics.get('INFORMATION_GAPS', 'Not specified'),
                    'KEY_VULN_INDICATORS': metrics.get('KEY_INDICATORS', 'Not specified'),
                    'PATCH_ANALYSIS': metrics.get('PATCH_ANALYSIS', 'Not available'),
                    'SUMMARY_FINDINGS': metrics.get('SUMMARY', 'Not available'),
                })
            else:
                # Default values if metrics aren't provided
                self.template_data.update({
                    'POC_FEASIBILITY': '?',
                    'PATCH_EFFECTIVENESS': '?',
                    'POC_COMPLEXITY': 'Unknown',
                    'VULN_EXPLANATION': 'Not available',
                    'IMPACT_SUMMARY': 'Not available',
                    'POC_FEASIBILITY_ANALYSIS': 'Not available',
                    'REQUIRED_SKILLS': 'Not specified',
                    'INFORMATION_GAPS': 'Not specified',
                    'KEY_VULN_INDICATORS': 'Not specified',
                    'PATCH_ANALYSIS': 'Not available',
                    'SUMMARY_FINDINGS': 'Not available',
                })
            
            # Add commit data
            self.template_data['COMMITS'] = [
                commit_diff.get_template_data(i+1) 
                for i, commit_diff in enumerate(self.commit_diffs)
            ]
            
            # Render the template
            self.html_content = chevron.render(template, self.template_data)
            
            # Save the HTML file
            output_path = os.path.join(self.output_dir, f"{self.advisory_id}_patch_analysis.html")
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(self.html_content)
                
            print(f"\nGenerated HTML report: {output_path}")
            return True
            
        except Exception as e:
            print(f"Error generating HTML report: {e}")
            return False
    
    def analyze(self, metrics: Dict[str, str] = None) -> bool:
        """Main analysis workflow"""
        success = self.fetch_advisory()
        if not success:
            return False
            
        success = self.fetch_commit_diffs()
        success = self.generate_html_report(metrics)
        
        return success


def parse_markdown_report(markdown_file: str) -> Dict[str, str]:
    """Parse metrics and analysis from a markdown report file"""
    try:
        with open(markdown_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        metrics = {}
        
        # Extract metrics table
        metrics_table = re.search(r'\| Vulnerability Type \| (.*?) \|\s*\n\| Severity \| (.*?) \|\s*\n\| Patch Effectiveness \| (.*?)\/10 \|\s*\n\| PoC Feasibility \| (.*?)\/10 \|\s*\n\| PoC Complexity \| (.*?) \|', content)
        
        if metrics_table:
            metrics['VULN_TYPE'] = metrics_table.group(1)
            metrics['SEVERITY'] = metrics_table.group(2)
            metrics['PATCH_EFFECTIVENESS'] = metrics_table.group(3)
            metrics['POC_FEASIBILITY'] = metrics_table.group(4)
            metrics['POC_COMPLEXITY'] = metrics_table.group(5)
        
        # Look for Markdown report format within code blocks
        markdown_block = re.search(r'```markdown\s*(.*?)\s*```', content, re.DOTALL)
        if markdown_block:
            markdown_content = markdown_block.group(1)
            
            # Extract vulnerability explanation (section 1)
            vuln_section = re.search(r'## 1\.\s*Vulnerability Explanation\s+(.*?)(?=##)', markdown_content, re.DOTALL)
            if vuln_section:
                metrics['VULN_EXPLANATION'] = vuln_section.group(1).strip()
            
            # Extract patch analysis (section 2)
            patch_section = re.search(r'## 2\.\s*Patch Analysis\s+(.*?)(?=##)', markdown_content, re.DOTALL)
            if patch_section:
                metrics['PATCH_ANALYSIS'] = patch_section.group(1).strip()
            
            # Extract impact summary (section 3)
            impact_section = re.search(r'## 3\.\s*Impact Summary\s+(.*?)(?=##)', markdown_content, re.DOTALL)
            if impact_section:
                metrics['IMPACT_SUMMARY'] = impact_section.group(1).strip()
            
            # Extract PoC feasibility analysis (section 5)
            poc_section = re.search(r'## 5\.\s*PoC Feasibility Analysis\s+(.*?)(?=##)', markdown_content, re.DOTALL)
            if poc_section:
                metrics['POC_ANALYSIS'] = poc_section.group(1).strip()
                
                # Extract specific details from PoC analysis
                required_match = re.search(r'\*\*Required Knowledge/Skills[^:]*:\*\*\s*(.*?)(?=\n- \*\*|\n\*\*)', poc_section.group(1), re.DOTALL)
                if required_match:
                    metrics['REQUIRED_SKILLS'] = required_match.group(1).strip()
                
                gaps_match = re.search(r'\*\*Information Gaps[^:]*:\*\*\s*(.*?)(?=\n- \*\*|\n\*\*)', poc_section.group(1), re.DOTALL)
                if gaps_match:
                    metrics['INFORMATION_GAPS'] = gaps_match.group(1).strip()
                
                indicators_match = re.search(r'\*\*Key Vulnerability Components[^:]*:\*\*\s*(.*?)(?=\n- \*\*|\n\*\*|$)', poc_section.group(1), re.DOTALL)
                if indicators_match:
                    metrics['KEY_INDICATORS'] = indicators_match.group(1).strip()
        
        # If no structured markdown block, try to parse from regular sections
        if not metrics.get('VULN_EXPLANATION'):
            # Try to extract from standard section headers
            for section_name, pattern in [
                ('VULN_EXPLANATION', r'(?:##|###)\s*Vulnerability Explanation\s+(.*?)(?=##|$)'),
                ('PATCH_ANALYSIS', r'(?:##|###)\s*Patch Analysis\s+(.*?)(?=##|$)'),
                ('IMPACT_SUMMARY', r'(?:##|###)\s*Impact Summary\s+(.*?)(?=##|$)'),
                ('POC_ANALYSIS', r'(?:##|###)\s*PoC Feasibility(?:\s*Analysis)?\s+(.*?)(?=##|$)')
            ]:
                section_match = re.search(pattern, content, re.DOTALL)
                if section_match:
                    metrics[section_name] = section_match.group(1).strip()
        
            # Try to extract skills, gaps and indicators if we have PoC analysis
            if metrics.get('POC_ANALYSIS'):
                for detail_name, pattern in [
                    ('REQUIRED_SKILLS', r'Required knowledge/skills[^:]*:(.*?)(?=\n\n|\n[A-Z]|$)'),
                    ('INFORMATION_GAPS', r'Information gaps[^:]*:(.*?)(?=\n\n|\n[A-Z]|$)'),
                    ('KEY_INDICATORS', r'Key vulnerability components[^:]*:(.*?)(?=\n\n|\n[A-Z]|$)')
                ]:
                    detail_match = re.search(pattern, metrics['POC_ANALYSIS'], re.DOTALL)
                    if detail_match:
                        metrics[detail_name] = detail_match.group(1).strip()
        
        # Clean up the extracted text (remove bullet points, etc.)
        for key in metrics:
            if isinstance(metrics[key], str):
                # Convert bullet lists to proper format
                metrics[key] = re.sub(r'^\s*- ', '• ', metrics[key], flags=re.MULTILINE)
                # Remove extra whitespace
                metrics[key] = re.sub(r'\n\s*\n', '\n\n', metrics[key])
        
        # Create a summary of findings if not already present
        if not metrics.get('SUMMARY'):
            summary = f"The analyzed vulnerability is a {metrics.get('VULN_TYPE', 'Unknown')} type with {metrics.get('SEVERITY', 'Unknown')} severity. "
            summary += f"PoC development feasibility is rated {metrics.get('POC_FEASIBILITY', '?')}/10 with {metrics.get('POC_COMPLEXITY', 'unknown')} complexity. "
            summary += f"The patch effectiveness is rated {metrics.get('PATCH_EFFECTIVENESS', '?')}/10."
            metrics['SUMMARY'] = summary
        
        return metrics
        
    except Exception as e:
        print(f"Error parsing markdown report: {e}")
        import traceback
        traceback.print_exc()
        return {}


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Generate detailed patch analysis reports for GitHub Security Advisories")
    parser.add_argument("advisory_url", help="URL of the GitHub Security Advisory to analyze")
    parser.add_argument("--markdown", "-m", help="Path to markdown analysis file to include in the report")
    parser.add_argument("--output-dir", "-o", default=".", help="Directory to save output files")
    args = parser.parse_args()
    
    # Validate the URL
    if not args.advisory_url.startswith("https://github.com/advisories/GHSA-"):
        print("Error: Invalid GitHub Advisory URL format. Expected format: https://github.com/advisories/GHSA-xxxx-xxxx-xxxx")
        return 1
    
    # Parse metrics from markdown if provided
    metrics = None
    if args.markdown and os.path.exists(args.markdown):
        metrics = parse_markdown_report(args.markdown)
        print(f"Parsed metrics from markdown file: {len(metrics)} entries")
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Analyze the advisory
    analyzer = AdvisoryAnalyzer(args.advisory_url, args.output_dir)
    success = analyzer.analyze(metrics)
    
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())