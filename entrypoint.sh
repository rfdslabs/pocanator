#!/bin/bash
set -e

# Install specific packages (if needed)
echo "Installing required packages..."
pip install openai==0.28.1 markdown==3.5.2 diff-match-patch==20230430

# Create data directory for SQLite
mkdir -p /app/data

# Fix URL patterns to ensure correct order
echo "Fixing URL patterns..."
cat > /app/apps/advisories/urls.py << 'EOF'
from django.urls import path
from . import views

urlpatterns = [
    path('', views.AdvisoryListView.as_view(), name='advisory-list'),
    path('import/', views.ImportAdvisoryView.as_view(), name='import-advisory'),
    path('batch-import/', views.BatchImportView.as_view(), name='batch-import-advisories'),
    path('search/', views.AdvisorySearchView.as_view(), name='search-advisories'),
    # This is a catch-all pattern, so it should be last
    path('<str:github_id>/', views.AdvisoryDetailView.as_view(), name='advisory-detail'),
]
EOF

# Fix the commit URL parsing regex to handle abbreviated hashes
echo "Updating commit hash regex pattern..."
sed -i "s/github\\.com\/(\[\^\/\]\\+\/\[\^\/\]\\+)\/commit\/(\[0-9a-fA-F\]{40})/github\\.com\/(\[\^\/\]\\+\/\[\^\/\]\\+)\/commit\/(\[0-9a-fA-F\]{7,40})/" /app/apps/advisories/services.py

# Reduce the max diff size to prevent timeouts
echo "Reducing max diff size to prevent timeouts..."
sed -i "s/max_chars = 300000/max_chars = 150000/" /app/apps/analysis/services.py

# Initialize empty database
echo "Initializing database with Django system apps only..."

# Ensure migration directories exist (just to be safe)
for app in advisories analysis patches users pocs; do
    mkdir -p /app/apps/$app/migrations
    touch /app/apps/$app/migrations/__init__.py
done

# Create the SQLite database directory
mkdir -p /app/data

# Set up database with Django system tables only
# For custom apps, migrations are disabled in settings.py using MIGRATION_MODULES
echo "Creating base Django tables..."
python manage.py migrate auth
python manage.py migrate admin
python manage.py migrate contenttypes
python manage.py migrate sessions

# Create superuser if not exists (ignoring errors if user exists)
echo "Ensuring superuser exists..."
python manage.py createsuperuser --noinput || true

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start server
echo "Starting server..."
exec "$@"