#!/bin/bash

# Set permissions for entrypoint.sh
chmod +x entrypoint.sh

# Create .env file from example if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "Please edit .env to set your API keys"
fi

# Create data directory for SQLite
mkdir -p data

# Create app directories
for app in advisories analysis patches users pocs; do
    mkdir -p "apps/$app/migrations"
    touch "apps/$app/migrations/__init__.py"
done

# Stop any existing containers
docker compose down

# Build and start the containers
echo "Building and starting containers..."
docker compose build
docker compose up -d

# Show logs
echo "Container is starting. You can view logs with:"
echo "docker compose logs -f"

echo "Web interface will be available at: http://localhost:8000"
echo "Username: admin"
echo "Password: admin"