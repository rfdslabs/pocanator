"""
Services for fetching and processing GitHub security advisories.
"""
import re
import logging
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from django.conf import settings
from .models import Advisory, Commit
from apps.patches.models import FileChange, LineChange

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
REQUEST_TIMEOUT = 20


class GitHubAdvisoryService:
    """Service for fetching and processing GitHub security advisories"""
    
    def __init__(self, token=None):
        self.token = token or settings.GITHUB_TOKEN
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': DEFAULT_USER_AGENT,
        })
        if self.token:
            self.session.headers.update({
                'Authorization': f'token {self.token}'
            })
    
    def fetch_advisory(self, advisory_id_or_url):
        """
        Fetch advisory details from GitHub.
        
        Args:
            advisory_id_or_url: Either a GitHub Advisory ID (GHSA-xxxx-xxxx-xxxx) or full URL
        
        Returns:
            Advisory object or None if not found
        """
        # Normalize the input to an advisory URL
        if advisory_id_or_url.startswith('https://'):
            advisory_url = advisory_id_or_url
            advisory_id = self._extract_advisory_id(advisory_url)
        else:
            advisory_id = advisory_id_or_url
            advisory_url = f"https://github.com/advisories/{advisory_id}"
        
        # Check if advisory already exists in database
        try:
            existing_advisory = Advisory.objects.get(github_id=advisory_id)
            logger.info(f"Advisory {advisory_id} already exists in database")
            return existing_advisory
        except Advisory.DoesNotExist:
            pass
        
        # Fetch the advisory page
        try:
            logger.info(f"Fetching advisory: {advisory_url}")
            response = self.session.get(advisory_url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract advisory details
            title = self._extract_title(soup) or "Unknown Title"
            description = self._extract_description(soup) or "No description available"
            severity = self._extract_severity(soup)
            cve_id = self._extract_cve_id(soup)
            cvss_score = self._extract_cvss_score(soup)
            affected_versions = self._extract_affected_versions(soup)
            published_date = self._extract_published_date(soup)
            
            # Create new advisory
            advisory = Advisory.objects.create(
                github_id=advisory_id,
                url=advisory_url,
                title=title,
                description=description,
                severity=severity,
                cve_id=cve_id,
                cvss_score=cvss_score,
                affected_versions=affected_versions,
                published_date=published_date
            )
            
            # Fetch associated commits
            commit_links = self._extract_commit_links(soup)
            if commit_links:
                for commit_url in commit_links:
                    self.fetch_commit(advisory, commit_url)
            
            logger.info(f"Successfully fetched and created advisory {advisory_id}")
            return advisory
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching advisory {advisory_url}: {e}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error processing advisory {advisory_url}: {e}")
            return None
    
    def fetch_commit(self, advisory, commit_url):
        """
        Fetch a commit associated with an advisory.
        
        Args:
            advisory: Advisory object
            commit_url: URL to the commit on GitHub
        
        Returns:
            Commit object or None if not found
        """
        try:
            # Parse commit URL to get repository and commit details
            repo_name, commit_hash = self._parse_commit_url(commit_url)
            
            if not repo_name or not commit_hash:
                logger.warning(f"Could not parse commit URL: {commit_url}")
                return None
            
            # Check if commit already exists
            try:
                existing_commit = Commit.objects.get(
                    advisory=advisory,
                    commit_hash=commit_hash
                )
                logger.info(f"Commit {commit_hash} already exists for advisory {advisory.github_id}")
                return existing_commit
            except Commit.DoesNotExist:
                pass
            
            # Get the diff URL
            diff_url = commit_url.split("?")[0] + ".diff"
            logger.info(f"Fetching diff from: {diff_url}")
            
            # Fetch the diff
            response = self.session.get(diff_url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            diff_text = response.text
            
            # Create commit object
            commit = Commit.objects.create(
                advisory=advisory,
                repo_name=repo_name,
                commit_hash=commit_hash,
                commit_url=commit_url,
                diff_text=diff_text,
                lines_added=diff_text.count('\n+') - diff_text.count('\n+++'),
                lines_removed=diff_text.count('\n-') - diff_text.count('\n---')
            )
            
            # Process the diff to create file and line changes
            self._process_diff(commit)
            
            logger.info(f"Successfully fetched and processed commit {commit_hash}")
            return commit
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching diff for {commit_url}: {e}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error processing commit {commit_url}: {e}")
            return None
    
    def _process_diff(self, commit):
        """
        Process a diff to create file and line changes.
        
        Args:
            commit: Commit object with diff_text
        """
        if not commit.diff_text:
            return
        
        current_file = None
        current_file_path = None
        current_hunk = None
        
        lines = commit.diff_text.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # New file
            if line.startswith('diff --git'):
                # Save previous file if exists
                current_file = None
                current_file_path = None
                current_hunk = None
                
                # Extract file path
                file_path = self._extract_file_path(lines, i)
                if file_path:
                    current_file_path = file_path
                    current_file = FileChange.objects.create(
                        commit=commit,
                        file_path=file_path,
                        is_binary='Binary files' in line
                    )
            
            # Hunk header
            elif line.startswith('@@') and current_file:
                current_hunk = line
                
                # Extract line numbers
                match = re.search(r'@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@', line)
                if match:
                    old_line_num = int(match.group(1))
                    new_line_num = int(match.group(2))
                    
                    # Process lines in this hunk
                    i += 1
                    while i < len(lines) and not (lines[i].startswith('diff --git') or lines[i].startswith('@@')):
                        content = lines[i]
                        
                        if not content:
                            i += 1
                            continue
                        
                        line_type = content[0] if content else ' '
                        code = content[1:] if content else ''
                        
                        if line_type == '+':
                            LineChange.objects.create(
                                file_change=current_file,
                                change_type='add',
                                old_line_num=None,
                                new_line_num=new_line_num,
                                content=code
                            )
                            new_line_num += 1
                            current_file.lines_added += 1
                        elif line_type == '-':
                            LineChange.objects.create(
                                file_change=current_file,
                                change_type='remove',
                                old_line_num=old_line_num,
                                new_line_num=None,
                                content=code
                            )
                            old_line_num += 1
                            current_file.lines_removed += 1
                        elif line_type == ' ':
                            LineChange.objects.create(
                                file_change=current_file,
                                change_type='context',
                                old_line_num=old_line_num,
                                new_line_num=new_line_num,
                                content=code
                            )
                            old_line_num += 1
                            new_line_num += 1
                        
                        i += 1
                    
                    # Save file changes
                    current_file.save()
                    
                    # Don't increment i here as we already did it in the while loop
                    continue
            
            i += 1
    
    def _extract_advisory_id(self, url):
        """Extract the GHSA ID from a URL"""
        match = re.search(r'GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}', url)
        return match.group(0) if match else None
    
    def _extract_title(self, soup):
        """Extract the advisory title"""
        # Look for the title in h2 element with class "Subhead-heading"
        title_elem = soup.find('h2', class_='Subhead-heading')
        if title_elem:
            return title_elem.get_text(strip=True)
            
        # Try other h2 elements that might contain the title
        for h2 in soup.find_all('h2'):
            if h2.text and not 'Search' in h2.text and not h2.has_attr('data-pjax'):
                return h2.get_text(strip=True)
        
        # Try h1 elements as a fallback
        title_elem = soup.find('h1')
        if title_elem and not 'Search' in title_elem.text:
            return title_elem.get_text(strip=True)
            
        return "Unknown Title"
    
    def _extract_description(self, soup):
        """Extract the advisory description"""
        # Look for common containers for the main description
        for selector in ['div.markdown-body', 'article', 'div[data-testid="vuln-description-markdown"]']:
            content_div = soup.select_one(selector)
            if content_div:
                return content_div.get_text("\n", strip=True)
        return None
    
    def _extract_severity(self, soup):
        """Extract the severity level"""
        severity_classes = {
            'color-fg-severe': 'Critical', 'color-fg-danger': 'Critical',
            'color-fg-high': 'High', 'color-fg-attention': 'High',
            'color-fg-moderate': 'Moderate', 'color-fg-warning': 'Moderate',
            'color-fg-subtle': 'Low', 'color-text-secondary': 'Low'
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
            if severity_span:
                return severity_level
        
        # Try from text in body
        body_text = soup.body.get_text(" ", strip=True) if soup.body else ""
        if "Critical severity" in body_text: return "Critical"
        if "High severity" in body_text: return "High"
        if "Moderate severity" in body_text: return "Moderate"
        if "Low severity" in body_text: return "Low"
        
        return "Unknown"
    
    def _extract_cve_id(self, soup):
        """Extract CVE ID if present"""
        cve_pattern = re.compile(r'CVE-\d{4}-\d{4,}')
        for elem in soup.select('a'):
            if elem.text and cve_pattern.search(elem.text):
                return cve_pattern.search(elem.text).group(0)
        return None
    
    def _extract_cvss_score(self, soup):
        """Extract CVSS score if present"""
        cvss_elements = soup.select('.Label[title*="CVSS"]')
        if cvss_elements:
            for element in cvss_elements:
                if 'title' in element.attrs and 'CVSS' in element['title']:
                    return element.get_text(strip=True)
        return None
    
    def _extract_affected_versions(self, soup):
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
        return None
    
    def _extract_published_date(self, soup):
        """Extract the published date of the advisory"""
        date_elem = soup.find(['relative-time', 'time-ago', 'time'])
        if date_elem:
            if date_elem.has_attr('datetime'):
                return datetime.fromisoformat(date_elem['datetime'].replace('Z', '+00:00'))
            try:
                return datetime.strptime(date_elem.get_text(strip=True), '%Y-%m-%d')
            except:
                pass
        return None
    
    def _extract_commit_links(self, soup):
        """Extract commit links from the advisory page"""
        commit_links = []
        processed_commits = set()
        
        # Method 1: Look for direct commit links with 'commit-link' class
        link_elements = soup.find_all('a', class_='commit-link')
        for link_tag in link_elements:
            href = link_tag.get('href')
            if href and 'github.com' in href and '/commit/' in href and href not in processed_commits:
                commit_links.append(href)
                processed_commits.add(href)
        
        # Method 2: Look for repo#issue references that might link to commits
        for link_tag in soup.find_all('a'):
            href = link_tag.get('href')
            text = link_tag.get_text(strip=True)
            
            # Look for links with format username/repo#number
            if href and 'github.com' in href:
                # First check if it's a commit that wasn't caught by class
                if '/commit/' in href and href not in processed_commits:
                    commit_links.append(href)
                    processed_commits.add(href)
                    continue
                
                # Then check for issue/PR links that might contain commits
                if '/pull/' in href or '/issues/' in href:
                    # Fetch the PR/issue page to look for linked commits
                    try:
                        logger.info(f"Checking PR/issue for commits: {href}")
                        pr_commits = self._extract_commits_from_pr_or_issue(href)
                        for commit_url in pr_commits:
                            if commit_url not in processed_commits:
                                commit_links.append(commit_url)
                                processed_commits.add(commit_url)
                    except Exception as e:
                        logger.warning(f"Error extracting commits from PR/issue {href}: {e}")
        
        # Method 3: Look for issue references in the form username/repo#number in text
        for link_tag in soup.find_all('a'):
            text = link_tag.get_text(strip=True)
            # Check for username/repo#issue format in text
            repo_issue_match = re.match(r'([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)#(\d+)', text)
            if repo_issue_match:
                repo, issue_num = repo_issue_match.groups()
                issue_url = f"https://github.com/{repo}/issues/{issue_num}"
                
                # Look for commits in the linked issue
                try:
                    logger.info(f"Checking issue reference from text: {text} -> {issue_url}")
                    issue_commits = self._extract_commits_from_pr_or_issue(issue_url)
                    for commit_url in issue_commits:
                        if commit_url not in processed_commits:
                            commit_links.append(commit_url)
                            processed_commits.add(commit_url)
                except Exception as e:
                    logger.warning(f"Error extracting commits from issue ref {text}: {e}")
        
        # Method 4: Look for text references to commits in the form user/repo@hash
        commit_patterns = [
            # Match "user/repo@hash" format
            r'([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)@([0-9a-f]{7,40})',
            # Match "hash" alone if it looks like a commit hash
            r'\b([0-9a-f]{40})\b'
        ]
        
        for pattern in commit_patterns:
            for match in re.finditer(pattern, soup.get_text()):
                if len(match.groups()) == 2:  # user/repo@hash format
                    repo, commit_hash = match.groups()
                    commit_url = f"https://github.com/{repo}/commit/{commit_hash}"
                    if commit_url not in processed_commits:
                        commit_links.append(commit_url)
                        processed_commits.add(commit_url)
                elif len(match.groups()) == 1:  # lone hash format
                    # Without repo context, we'd need to guess the repo
                    # For now, we skip these to avoid false positives
                    pass
        
        # Method 5: If no commits were found but we have references to issues or PRs, try to get the repo context
        if not commit_links:
            repo_contexts = set()
            # Extract repo context from the advisory
            repo_pattern = r'github\.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)'
            for match in re.finditer(repo_pattern, str(soup)):
                repo_contexts.add(match.group(1))
            
            # Look for references to issues/PRs in the text
            issue_pattern = r'#(\d{3,6})'  # Issue numbers are typically 3-6 digits
            for match in re.finditer(issue_pattern, soup.get_text()):
                issue_num = match.group(1)
                # Try each repo context with this issue number
                for repo in repo_contexts:
                    issue_url = f"https://github.com/{repo}/issues/{issue_num}"
                    try:
                        logger.info(f"Checking inferred issue URL: {issue_url}")
                        issue_commits = self._extract_commits_from_pr_or_issue(issue_url)
                        for commit_url in issue_commits:
                            if commit_url not in processed_commits:
                                commit_links.append(commit_url)
                                processed_commits.add(commit_url)
                    except Exception as e:
                        logger.warning(f"Error checking inferred issue {issue_url}: {e}")
        
        return commit_links
        
    def _extract_commits_from_pr_or_issue(self, pr_or_issue_url):
        """Extract commit URLs from a PR or issue page"""
        commit_urls = []
        
        try:
            # Fetch the PR/issue page
            response = self.session.get(pr_or_issue_url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for commit links
            for link in soup.find_all('a'):
                href = link.get('href')
                if href and '/commit/' in href and 'github.com' in href:
                    # Construct the full URL if it's relative
                    if href.startswith('/'):
                        full_url = f"https://github.com{href}"
                    else:
                        full_url = href
                    commit_urls.append(full_url)
            
            # Also look for references in the format user/repo@hash
            text = soup.get_text()
            for match in re.finditer(r'([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)@([0-9a-f]{7,40})', text):
                repo, commit_hash = match.groups()
                commit_url = f"https://github.com/{repo}/commit/{commit_hash}"
                commit_urls.append(commit_url)
                
        except Exception as e:
            logger.warning(f"Error fetching PR/issue {pr_or_issue_url}: {e}")
        
        return commit_urls
    
    def _parse_commit_url(self, commit_url):
        """Parse a GitHub commit URL to extract repo name and commit hash"""
        try:
            # Match full-length or abbreviated commit hashes (7 or more characters)
            parsed = re.search(r'github\.com/([^/]+/[^/]+)/commit/([0-9a-fA-F]{7,40})', commit_url)
            if parsed:
                repo_name = parsed.group(1)
                commit_hash = parsed.group(2)
                return repo_name, commit_hash
            
            # Also handle paths with query parameters or fragments
            parsed = re.search(r'github\.com/([^/]+/[^/]+)/commit/([0-9a-fA-F]{7,40})(?:[?#].*)?$', commit_url)
            if parsed:
                repo_name = parsed.group(1)
                commit_hash = parsed.group(2)
                return repo_name, commit_hash
        except Exception as e:
            logger.warning(f"Error parsing commit URL {commit_url}: {str(e)}")
        
        return None, None
    
    def _extract_file_path(self, lines, start_idx):
        """Extract the file path from diff headers"""
        # Try to find the most accurate filename
        file_path = ""
        
        # Look for the a/ and b/ prefixed paths
        for j in range(start_idx, min(start_idx + 5, len(lines))):
            if j < len(lines):
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