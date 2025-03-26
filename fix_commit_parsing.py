"""
Script to fix commit URL parsing in GitHubAdvisoryService.
"""
import re
import logging

logger = logging.getLogger(__name__)

def fix_advisory_service():
    """
    Update the _parse_commit_url method in GitHubAdvisoryService to handle abbreviated hashes.
    """
    # Import the service
    from apps.advisories.services import GitHubAdvisoryService
    
    # Define the fixed method
    def _parse_commit_url(self, commit_url):
        """Parse a GitHub commit URL to extract repo name and commit hash"""
        try:
            # Match both full and abbreviated commit hashes (7+ characters)
            parsed = re.search(r'github\.com/([^/]+/[^/]+)/commit/([0-9a-fA-F]{7,40})', commit_url)
            if parsed:
                repo_name = parsed.group(1)
                commit_hash = parsed.group(2)
                return repo_name, commit_hash
        except Exception as e:
            logger.warning(f"Error parsing commit URL {commit_url}: {str(e)}")
        
        return None, None
    
    # Patch the method
    GitHubAdvisoryService._parse_commit_url = _parse_commit_url
    
    print("GitHubAdvisoryService._parse_commit_url has been patched to handle abbreviated commit hashes.")

if __name__ == "__main__":
    fix_advisory_service()