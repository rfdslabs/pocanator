#!/bin/bash

# This script fixes the commit URL parsing issue for abbreviated hashes
# and reduces the max commit diff size to prevent timeouts

echo "Fixing commit URL parsing and timeout issues..."

# Check if the container is running
if ! docker ps | grep -q reportgpt-web; then
    echo "Container 'reportgpt-web' is not running. Please start it first with ./start.sh"
    exit 1
fi

# Fix the commit URL parsing regex in advisories/services.py
echo "1. Updating commit hash regex to support abbreviated hashes..."
docker exec reportgpt-web sed -i "s/github\\.com\/(\[\^\/\]\\+\/\[\^\/\]\\+)\/commit\/(\[0-9a-fA-F\]{40})/github\\.com\/(\[\^\/\]\\+\/\[\^\/\]\\+)\/commit\/(\[0-9a-fA-F\]{7,40})/" /app/apps/advisories/services.py

# Reduce the max diff size in analysis/services.py
echo "2. Reducing max diff size to prevent timeouts..."
docker exec reportgpt-web sed -i "s/max_chars = 300000/max_chars = 150000/" /app/apps/analysis/services.py

echo "3. Restarting the container to apply changes..."
docker restart reportgpt-web

echo "Fix complete! Container restarted with the following improvements:"
echo "- Commit URL parsing now supports abbreviated hashes (7-40 characters)"
echo "- Maximum diff size reduced to 150,000 characters to prevent timeouts"
echo ""
echo "You should now be able to import commits with abbreviated hashes without timeouts."