#!/bin/bash

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create .env file from example if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "Please edit .env to set your API keys"
fi

# Create data directory for SQLite
mkdir -p data

# Create app directories and __init__.py files
for app in advisories analysis patches users; do
    mkdir -p "apps/$app/migrations"
    touch "apps/$app/migrations/__init__.py"
done

# Create migrations
echo "Creating initial migrations..."
python manage.py makemigrations advisories analysis patches users

# Apply migrations
echo "Applying migrations..."
python manage.py migrate

# Create superuser if needed
echo "Creating default superuser (admin/admin)..."
python manage.py shell -c "from django.contrib.auth.models import User; User.objects.create_superuser('admin', 'admin@example.com', 'admin') if not User.objects.filter(username='admin').exists() else None"

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Run server
echo "Starting development server..."
echo "Visit http://127.0.0.1:8000/ in your browser"
echo "Username: admin"
echo "Password: admin"
python manage.py runserver