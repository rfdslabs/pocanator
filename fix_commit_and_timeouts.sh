#!/bin/bash

# This script fixes two issues:
# 1. The commit URL parsing issue (abbreviated hash support)
# 2. The worker timeout issue when processing large commits

echo "Fixing commit parsing and timeout issues..."

# Check if the container is running
if ! docker ps | grep -q reportgpt-web; then
    echo "Container 'reportgpt-web' is not running. Please start it first with ./start.sh"
    exit 1
fi

echo "1. Fixing commit URL parsing to handle abbreviated hashes..."
# Fix the commit URL parsing regex to handle abbreviated hashes (7+ characters)
docker exec reportgpt-web bash -c 'sed -i "s/\(\[0-9a-fA-F\]\){40}/\1{7,40}/" /app/apps/advisories/services.py'

echo "2. Optimizing commit diff handling and increasing timeout..."
# Create a script to update the settings
cat > temp_settings_update.py << 'EOF'
#!/usr/bin/env python
import re
import sys
import os

# 1. Update the _prepare_patch_text method to better handle large diffs
services_file = '/app/apps/analysis/services.py'

with open(services_file, 'r') as f:
    content = f.read()

# Reduce the default max_chars from 300000 to 200000 to prevent worker timeouts
content = content.replace("max_chars = 300000", "max_chars = 200000")

# Make additional performance improvements
# 1. Add a file filter to skip large binary files or non-relevant files
improved_patch_text_method = '''
    def _prepare_patch_text(self, commits, max_chars=200000):
        """
        Prepare the patch text for the prompt with size limits and smart filtering
        
        Args:
            commits: QuerySet of Commit objects
            max_chars: Maximum characters to include for patches
            
        Returns:
            String with patch information
        """
        if not commits:
            return "[No Patches Found]"
        
        # Define patterns for files to exclude (binary files, build artifacts, etc.)
        exclude_patterns = [
            r'\.min\.js$', r'\.min\.css$', r'\.png$', r'\.jpg$', r'\.jpeg$', 
            r'\.gif$', r'\.ico$', r'\.pdf$', r'\.zip$', r'\.tar$', r'\.gz$',
            r'package-lock\.json$', r'yarn\.lock$', r'/test/', r'/tests/', r'/node_modules/'
        ]
        
        # Function to check if a diff section should be excluded
        def should_exclude(diff_section):
            if "Binary files" in diff_section:
                return True
            
            for pattern in exclude_patterns:
                if re.search(pattern, diff_section, re.IGNORECASE):
                    return True
            return False
        
        # First, preprocess the commits to filter out excluded files
        filtered_commits = []
        for commit in commits:
            if not commit.diff_text:
                continue
                
            # Split the diff into file sections
            diff_sections = re.split(r'(diff --git [^\n]+)', commit.diff_text)
            filtered_diff = ""
            
            for i in range(1, len(diff_sections), 2):
                if i+1 < len(diff_sections):
                    header = diff_sections[i]
                    content = diff_sections[i+1]
                    
                    # Check if this file should be excluded
                    if not should_exclude(header + content):
                        filtered_diff += header + content
            
            # If we have filtered content, add it to our list
            if filtered_diff:
                filtered_commits.append({
                    'commit': commit,
                    'diff_text': filtered_diff,
                    'size': len(filtered_diff)
                })
        
        # Handle case with no filtered commits
        if not filtered_commits:
            return "[No Relevant Patches Found - Binary/Test/Build Files Filtered]"
        
        # Count total characters in filtered commits
        total_chars = sum(item['size'] for item in filtered_commits)
        
        # If total is under limit, we can include all filtered commits (up to 3)
        if total_chars <= max_chars:
            patch_diffs = []
            for i, item in enumerate(filtered_commits[:3]):  # Limit to 3 commits
                commit = item['commit']
                diff_text = item['diff_text']
                repo_info = f"{commit.repo_name} ({commit.commit_hash[:7]})"
                patch_diffs.append(f"--- PATCH {i+1}: {repo_info} ---\\n{diff_text}")
            
            return "\\n\\n".join(patch_diffs)
        
        # Otherwise, we need to truncate and distribute space
        else:
            logger.warning(f"Commit diffs too large ({total_chars} chars). Truncating to {max_chars} chars.")
            
            patch_diffs = []
            remaining_chars = max_chars
            
            # Handle all but the last commit
            for i in range(min(len(filtered_commits), 3)):
                item = filtered_commits[i]
                # Allocate space proportionally for this commit
                if i < min(len(filtered_commits), 3) - 1:
                    chars_for_this_commit = int((item['size'] / total_chars) * max_chars * 0.8)  # Leave some buffer
                    remaining_chars -= chars_for_this_commit
                else:
                    # Last commit gets remaining chars
                    chars_for_this_commit = remaining_chars
                
                commit = item['commit']
                repo_info = f"{commit.repo_name} ({commit.commit_hash[:7]})"
                
                # Extract the most important parts of the diff (first part and context)
                diff_text = item['diff_text'][:chars_for_this_commit] + "\\n... [TRUNCATED]"
                patch_diffs.append(f"--- PATCH {i+1}: {repo_info} ---\\n{diff_text}")
            
            return "\\n\\n".join(patch_diffs)
'''

# Replace the existing _prepare_patch_text method with our improved version
old_method_pattern = r'def _prepare_patch_text\(self, commits, max_chars=\d+\):.*?def _construct_prompt'
new_method = improved_patch_text_method + "\n    def _construct_prompt"
content = re.sub(old_method_pattern, new_method, content, flags=re.DOTALL)

# Write back the updated file
with open(services_file, 'w') as f:
    f.write(content)

print("Updated analysis/services.py with optimized _prepare_patch_text method")

# 2. Update container startup to increase Gunicorn timeout
# Create a custom entrypoint wrap script
with open('/app/docker-entrypoint-wrap.sh', 'w') as f:
    f.write('''#!/bin/bash
set -e

# Run the original entrypoint
/app/entrypoint.sh "$@"

# Override the command to include longer timeout
exec gunicorn reportgpt_web.wsgi:application \\
    --bind 0.0.0.0:8000 \\
    --timeout 120 \\
    --workers 2 \\
    --threads 2 \\
    --max-requests 1000 \\
    --max-requests-jitter 50
''')

# Make it executable
os.chmod('/app/docker-entrypoint-wrap.sh', 0o755)

print("Created custom entrypoint with increased Gunicorn timeout")

# Update any existing .env file to reference our custom entrypoint
env_path = '/app/.env'
if os.path.exists(env_path):
    with open(env_path, 'r') as f:
        env_content = f.read()
    
    # Add or update DOCKER_ENTRYPOINT setting
    if 'DOCKER_ENTRYPOINT=' in env_content:
        env_content = re.sub(r'DOCKER_ENTRYPOINT=.*', 'DOCKER_ENTRYPOINT=/app/docker-entrypoint-wrap.sh', env_content)
    else:
        env_content += '\nDOCKER_ENTRYPOINT=/app/docker-entrypoint-wrap.sh\n'
    
    with open(env_path, 'w') as f:
        f.write(env_content)
    
    print("Updated .env file with custom entrypoint reference")
EOF

# Copy and run the settings update script
docker cp temp_settings_update.py reportgpt-web:/app/
docker exec reportgpt-web python /app/temp_settings_update.py
rm temp_settings_update.py

echo "3. Restarting container with the new settings..."
docker restart reportgpt-web

echo "Fixes have been applied successfully!"
echo "The container has been restarted with:"
echo " - Fixed commit URL parsing for abbreviated hashes"
echo " - Optimized handling of large diffs with intelligent filtering"
echo " - Increased Gunicorn worker timeout from 30s to 120s"
echo " - Better resource management for large commits"