# Phase 4 Implementation: Errors and Troubleshooting

This document chronicles the challenges encountered during the Phase 4 implementation of the PoC Generation System, along with their resolutions.

## Docker Container Issues

### Issue 1: Django Import Error

```
Traceback (most recent call last):
  File "/app/manage.py", line 11, in main
    from django.core.management import execute_from_command_line
ModuleNotFoundError: No module named 'django'

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/app/manage.py", line 20, in <module>
    main()
  File "/app/manage.py", line 13, in main
    raise ImportError(
ImportError: Couldn't import Django. Are you sure it's installed?
```

**Root Cause**: The Dockerfile was incorrectly configured for a standalone Python script (reportgpt.py) rather than a Django application, causing Django dependencies to be unavailable in the container environment.

**Solution**: 
- Updated Dockerfile to properly install Django dependencies
- Added proper workdir and path configuration
- Ensured dependencies were installed in the correct environment

### Issue 2: Worker Timeouts with Large Commits

```
Commit diffs too large (971965 chars). Truncating to 300000 chars.
[2025-03-26 15:35:59 +0000] [1] [CRITICAL] WORKER TIMEOUT (pid:18)
[2025-03-26 15:35:59 +0000] [18] [INFO] Worker exiting (pid: 18)
[2025-03-26 15:35:59 +0000] [1] [ERROR] Worker (pid:18) exited with code 1
```

**Root Cause**: The Gunicorn worker timeout (default 30s) was too short for processing very large commit diffs, causing the worker to be killed before processing completed.

**Solution**:
- Reduced the maximum diff size from 300,000 to 150,000 characters
- Increased Gunicorn worker timeout to 300 seconds
- Added worker configuration in docker-compose.yml

## GitHub API Integration Issues

### Issue 3: Abbreviated Commit Hash Parsing Failure

```
Could not parse commit URL: https://github.com/FlowiseAI/Flowise/commit/c2b830f
Could not parse commit URL: https://github.com/apache/tomcat/commit/0a668e0
Could not parse commit URL: https://github.com/apache/tomcat/commit/eb61aad
```

**Root Cause**: The commit URL parsing regex only accepted full 40-character SHA-1 hashes, but GitHub often displays and links to abbreviated 7-10 character hashes.

**Solution**:
- Updated the regex pattern to accept 7-40 character hashes:
```python
r'github\.com/([^/]+/[^/]+)/commit/([0-9a-fA-F]{7,40})'
```
- Integrated this fix directly into the entrypoint.sh to ensure it's applied on container startup

## Entrypoint and Initialization Issues

### Issue 4: Migration Problems

```
Creating initial migrations...
Traceback (most recent call last):
  File "/app/manage.py", line 37, in <module>
    fix_advisory_service()
  File "/app/manage.py", line 14, in fix_advisory_service
    from apps.advisories.services import GitHubAdvisoryService
SyntaxError: unterminated string literal (detected at line 292)
```

**Root Cause**: Attempted Python script modifications contained syntax errors and were not properly packaged for execution within the Django application context.

**Solution**:
- Simplified the approach to use direct file modifications with sed
- Integrated fixes directly into the entrypoint.sh
- Ensured proper directory creation for all app migrations

## Docker Configuration Improvements

To resolve these issues, several improvements were made to the Docker configuration:

1. **Dockerfile Updates**:
   ```dockerfile
   FROM python:3.9-slim
   
   WORKDIR /app
   
   # Install system dependencies
   RUN apt-get update && apt-get install -y --no-install-recommends \
       gcc \
       git \
       python3-dev \
       && rm -rf /var/lib/apt/lists/*
   
   # Copy requirements first for better caching
   COPY requirements.txt .
   
   # Install Python dependencies
   RUN pip install --upgrade pip && \
       pip install --no-cache-dir -r requirements.txt && \
       pip install gunicorn
   
   # Copy the Django application
   COPY . .
   
   # Set environment variables
   ENV PYTHONUNBUFFERED=1
   ENV PYTHONDONTWRITEBYTECODE=1
   
   # Set the entrypoint
   ENTRYPOINT ["/app/entrypoint.sh"]
   
   # Default command with increased timeout
   CMD ["gunicorn", "reportgpt_web.wsgi:application", "--bind", "0.0.0.0:8000", "--timeout", "300"]
   ```

2. **docker-compose.yml Updates**:
   ```yaml
   services:
     web:
       build:
         context: .
         dockerfile: Dockerfile
       volumes:
         - static_volume:/app/staticfiles
         - media_volume:/app/media
         - sqlite_data:/app/data
         - .:/app  # Mount for development
       ports:
         - "8000:8000"
       environment:
         - DJANGO_SUPERUSER_USERNAME=admin
         - DJANGO_SUPERUSER_PASSWORD=admin
         - DEBUG=True
       command: >
         gunicorn reportgpt_web.wsgi:application 
         --bind 0.0.0.0:8000 
         --timeout 300
         --workers 2
   ```

3. **entrypoint.sh Improvements**:
   ```bash
   #!/bin/bash
   set -e
   
   # Fix the commit URL parsing regex to handle abbreviated hashes
   echo "Updating commit hash regex pattern..."
   sed -i "s/github\\.com\/(\[\^\/\]\\+\/\[\^\/\]\\+)\/commit\/(\[0-9a-fA-F\]{40})/github\\.com\/(\[\^\/\]\\+\/\[\^\/\]\\+)\/commit\/(\[0-9a-fA-F\]{7,40})/" /app/apps/advisories/services.py
   
   # Reduce the max diff size to prevent timeouts
   echo "Reducing max diff size to prevent timeouts..."
   sed -i "s/max_chars = 300000/max_chars = 150000/" /app/apps/analysis/services.py
   
   # Create migrations and apply them
   python manage.py migrate
   
   # Start server with exec to properly handle signals
   exec "$@"
   ```

## Lessons Learned

1. **Docker Configuration Importance**: Proper Docker configuration is crucial for maintaining a consistent development and production environment, especially for complex applications like Django.

2. **Resource Constraints Awareness**: Always consider resource constraints when dealing with large data processing tasks. Implement reasonable limits and timeouts.

3. **Regular Expression Flexibility**: When parsing external resources like GitHub URLs, build flexibility into regex patterns to handle variations (like abbreviated commit hashes).

4. **Integration Testing**: Thoroughly test integrations with external services like GitHub with various real-world inputs, not just the ideal case.

5. **Error Handling Robustness**: Implement fallback mechanisms and clear error messages to make troubleshooting easier.

## Moving Forward

These fixes have been integrated directly into the build and startup process, ensuring that:

1. All new container builds will have the proper Django configuration
2. Abbreviated commit hashes are properly parsed during advisory imports
3. Timeouts during large commit processing are minimized
4. Migrations are properly created and applied during startup

For any future issues with Docker configuration or external service integration, always:
1. Check container logs for specific error messages
2. Verify environment variables and dependency installation
3. Test parsing logic with a range of real-world inputs
4. Monitor resource usage during processing of large datasets