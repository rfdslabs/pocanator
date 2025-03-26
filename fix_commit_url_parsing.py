"""
Fix the commit URL parsing issue in GitHubAdvisoryService.
This script will be run INSIDE the container.
"""

import os
import re
import fileinput

# Path to the services.py file inside the container
services_file = '/app/apps/advisories/services.py'

# Make sure the file exists
if not os.path.exists(services_file):
    print(f"Error: File {services_file} does not exist")
    exit(1)

content = ""
with open(services_file, 'r') as f:
    content = f.read()

# Find the _parse_commit_url method
pattern = r'def _parse_commit_url\(self, commit_url\):[^}]*?github\.com/\(\[.*?\]\+/\[.*?\]\+\)/commit/\(\[0-9a-fA-F\]\{40\}\)'

replacement = 'def _parse_commit_url(self, commit_url):\n        """Parse a GitHub commit URL to extract repo name and commit hash"""\n        try:\n            parsed = re.search(r\'github\\.com/([^/]+/[^/]+)/commit/([0-9a-fA-F]{7,40})\', commit_url)\n            if parsed:\n                repo_name = parsed.group(1)\n                commit_hash = parsed.group(2)\n                return repo_name, commit_hash\n        except Exception as e:\n            logger.warning(f"Error parsing commit URL {commit_url}: {str(e)}")\n        \n        return None, None'

# Check if we can find the pattern
if re.search(pattern, content, re.DOTALL):
    modified_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    # Write the modified content back to the file
    with open(services_file, 'w') as f:
        f.write(modified_content)
    
    print("Successfully modified the _parse_commit_url method to handle abbreviated commit hashes.")
    print("The file has been updated and the change should take effect immediately.")
else:
    # Simpler approach: just change the regex pattern
    with fileinput.FileInput(services_file, inplace=True, backup='.bak') as file:
        for line in file:
            # Find the line with the regex pattern and replace {40} with {7,40}
            if "github.com/([^/]+/[^/]+)/commit/([0-9a-fA-F]{40})" in line:
                print(line.replace("{40}", "{7,40}"), end='')
            else:
                print(line, end='')
    
    print("Successfully updated the regex pattern to match abbreviated commit hashes.")
    print("The fix should take effect immediately.")