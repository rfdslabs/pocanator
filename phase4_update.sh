#!/bin/bash

# This script updates the running container with Phase 4 changes
echo "Applying Phase 4 changes to the ReportGPT Web container..."

# Check if the container is running
if ! docker ps | grep -q reportgpt-web; then
    echo "Container 'reportgpt-web' is not running. Please start it first with ./start.sh"
    exit 1
fi

# Create migrations for the PoCs app
echo "Creating migrations for Phase 4 changes..."
docker exec reportgpt-web python manage.py makemigrations pocs

# Apply migrations
echo "Applying migrations..."
docker exec reportgpt-web python manage.py migrate

echo "Phase 4 changes have been applied successfully!"
echo "You can now access the updated application at http://localhost:8000"