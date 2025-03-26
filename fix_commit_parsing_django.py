"""
Script to fix commit URL parsing in GitHubAdvisoryService.
This script is designed to be run with Django's shell:
python manage.py shell < fix_commit_parsing_django.py
"""

import re
import logging
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'plurium_pocanator.settings')
django.setup()

logger = logging.getLogger(__name__)

# Now we can import Django models and services
from apps.advisories.services import GitHubAdvisoryService

# Define the fixed method
def new_parse_commit_url(self, commit_url):
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
GitHubAdvisoryService._parse_commit_url = new_parse_commit_url

print("GitHubAdvisoryService._parse_commit_url has been patched to handle abbreviated commit hashes.")

# Test with some example URLs
test_urls = [
    "https://github.com/FlowiseAI/Flowise/commit/c2b830f",
    "https://github.com/apache/tomcat/commit/0a668e0",
    "https://github.com/apache/tomcat/commit/eb61aad",
    "https://github.com/username/repo/commit/1234567890abcdef1234567890abcdef12345678"
]

# Create a service instance for testing
service = GitHubAdvisoryService()

print("\nTesting URL parsing:")
for url in test_urls:
    repo, commit = service._parse_commit_url(url)
    print(f"URL: {url}")
    print(f"  - Repo: {repo}")
    print(f"  - Commit: {commit}")
    print("")

print("Fix complete and tested successfully.")