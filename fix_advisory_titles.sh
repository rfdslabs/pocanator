#!/bin/bash

# This script runs the management command to update advisory titles
# that might be missing or incorrect (showing "Search code, repositories..." text)

echo "Running update_advisory_titles management command..."

# First, run in dry-run mode to see potential changes
echo "Running in dry-run mode first:"
python manage.py update_advisory_titles --dry-run

# Ask user if they want to proceed with actual update
read -p "Do you want to proceed with updating titles? (y/n): " choice
case "$choice" in 
  y|Y ) 
    echo "Starting title update..."
    python manage.py update_advisory_titles
    ;;
  * ) 
    echo "Update cancelled."
    ;;
esac

echo "Script completed."