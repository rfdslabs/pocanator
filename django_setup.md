# Django Web Interface for ReportGPT

## Overview

This document outlines the plan to create a Django-based web interface for ReportGPT with SQLite database storage, all contained in a single Docker container. This will transform the command-line tool into a fully interactive web application for vulnerability analysis.

## Project Structure

```
reportgpt-web/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── manage.py
├── entrypoint.sh
├── static/
│   ├── css/
│   ├── js/
│   └── images/
├── templates/
├── reportgpt_web/  # Django project
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
└── apps/
    ├── advisories/  # Advisory management app
    ├── analysis/    # Analysis management app
    ├── patches/     # Patch analysis app
    └── users/       # User management app
```

## Database Models

### Advisory Model
```python
class Advisory(models.Model):
    github_id = models.CharField(max_length=255, unique=True)  # GHSA-xxxx-xxxx-xxxx
    url = models.URLField()
    title = models.CharField(max_length=255)
    description = models.TextField()
    severity = models.CharField(max_length=50, choices=SEVERITY_CHOICES)
    cve_id = models.CharField(max_length=50, blank=True, null=True)
    cvss_score = models.CharField(max_length=10, blank=True, null=True)
    affected_versions = models.TextField(blank=True, null=True)
    published_date = models.DateTimeField(blank=True, null=True)
    discovered_date = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.github_id}: {self.title}"
```

### Commit Model
```python
class Commit(models.Model):
    advisory = models.ForeignKey(Advisory, on_delete=models.CASCADE, related_name='commits')
    repo_name = models.CharField(max_length=255)
    commit_hash = models.CharField(max_length=40)
    commit_url = models.URLField()
    diff_text = models.TextField()
    lines_added = models.IntegerField(default=0)
    lines_removed = models.IntegerField(default=0)
    fetch_date = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.repo_name}@{self.commit_hash[:7]}"
```

### Analysis Model
```python
class Analysis(models.Model):
    advisory = models.ForeignKey(Advisory, on_delete=models.CASCADE, related_name='analyses')
    vuln_type = models.CharField(max_length=50)
    vuln_explanation = models.TextField()
    patch_analysis = models.TextField()
    impact_summary = models.TextField()
    patch_effectiveness = models.IntegerField()
    poc_feasibility = models.IntegerField()
    poc_complexity = models.CharField(max_length=50)
    required_skills = models.TextField(blank=True, null=True)
    information_gaps = models.TextField(blank=True, null=True)
    key_indicators = models.TextField(blank=True, null=True)
    markdown_report = models.TextField(blank=True, null=True)
    html_report = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Analysis for {self.advisory.github_id}"
```

## Core Features

### 1. Advisory Management
- Search and import advisories from GitHub
- View advisory details and metadata
- List and filter advisories by severity, type, etc.
- Track advisory status (analyzed/not analyzed)

### 2. Analysis Management
- Request and view GPT analysis of advisories
- Store analysis results in the database
- View analysis history
- Export analysis reports (Markdown/HTML)

### 3. Patch Visualization
- Interactive patch diff viewer
- Multi-commit support
- Syntax highlighting
- Line-by-line annotations

### 4. User System (Optional)
- User authentication and authorization
- API key management
- Analysis history per user

## Docker Setup

### Dockerfile
```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Set up environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=reportgpt_web.settings

# Run entrypoint script
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]

# Expose port for the web server
EXPOSE 8000

# Default command
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "reportgpt_web.wsgi:application"]
```

### entrypoint.sh
```bash
#!/bin/bash

# Apply database migrations
python manage.py migrate

# Create superuser if not exists
python manage.py createsuperuser --noinput || true

# Collect static files
python manage.py collectstatic --noinput

# Start server
exec "$@"
```

### docker-compose.yml
```yaml
version: '3.8'

services:
  web:
    build: .
    volumes:
      - .:/app
      - static_volume:/app/static
      - media_volume:/app/media
      - sqlite_data:/app/data
    ports:
      - "8000:8000"
    environment:
      - DJANGO_SUPERUSER_USERNAME=admin
      - DJANGO_SUPERUSER_PASSWORD=admin
      - DJANGO_SUPERUSER_EMAIL=admin@example.com
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    restart: always

volumes:
  static_volume:
  media_volume:
  sqlite_data:
```

## API Integration

### OpenAI API Integration
```python
class AnalysisService:
    def __init__(self, api_key=None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.client = None
        self.setup_client()
    
    def setup_client(self):
        try:
            import openai
            self.client = openai.OpenAI(api_key=self.api_key)
        except ImportError:
            logger.error("OpenAI library not found. Please install it with: pip install openai")
            self.client = None
    
    def analyze_advisory(self, advisory, commit_diffs=None):
        """
        Analyze an advisory using GPT and return the analysis results
        """
        # Implementation adapting from reportgpt.py analyze_advisory_with_gpt
        # ...
```

### GitHub API Integration
```python
class GitHubService:
    def __init__(self, token=None):
        self.token = token or settings.GITHUB_TOKEN
        self.session = requests.Session()
        if self.token:
            self.session.headers.update({"Authorization": f"token {self.token}"})
    
    def fetch_advisory(self, advisory_id):
        """
        Fetch advisory details from GitHub
        """
        # Implementation adapting from reportgpt.py
        # ...
    
    def fetch_commits(self, advisory_url):
        """
        Fetch commits for an advisory
        """
        # Implementation adapting from reportgpt.py
        # ...
```

## Web Interface Design

### Dashboard
- Overview of recent advisories
- Quick stats (counts by severity, type)
- Recent analyses
- Search functionality

### Advisory List View
- Table of advisories with filtering
- Severity indicators
- Quick actions (analyze, view details)
- Pagination

### Advisory Detail View
- Advisory metadata
- Commit list
- Analysis request form
- Analysis results (if available)
- Interactive patch viewer

### Analysis View
- Detailed analysis results
- Metrics visualization
- Patch diff viewer
- Export options

## Implementation Plan

### Phase 1: Setup
- [x] Create Django project structure
- [x] Setup Docker configuration
- [x] Define database models

### Phase 2: Core Functionality
- [ ] Implement advisory fetching from GitHub
- [ ] Implement commit fetching and diff parsing
- [ ] Integrate OpenAI API for analysis
- [ ] Setup basic views and templates

### Phase 3: UI Development
- [ ] Develop dashboard interface
- [ ] Create advisory list and detail views
- [ ] Implement interactive patch viewer
- [ ] Design analysis results display

### Phase 4: Enhancements
- [ ] Add search and filtering capabilities
- [ ] Implement export functionality
- [ ] Add user authentication (optional)
- [ ] Create API endpoints for programmatic access

## Deployment

For local development:
```bash
# Build and start the container
docker-compose up -d

# Create a superuser (if not created by entrypoint)
docker-compose exec web python manage.py createsuperuser

# Access the web interface
# Open http://localhost:8000 in your browser
```

## Technology Stack

- **Backend**: Django, Python
- **Database**: SQLite
- **Frontend**: HTML, CSS, JavaScript (with options for React components)
- **Containerization**: Docker
- **Additional Libraries**:
  - django-rest-framework (for API endpoints)
  - django-crispy-forms (for form styling)
  - pygments (for code syntax highlighting)
  - openai (for GPT integration)
  - requests (for GitHub API)
  - chevron (for Mustache templating)