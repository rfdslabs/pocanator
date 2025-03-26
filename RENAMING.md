# Application Renaming: ReportGPT to Plurium POCanator

## Overview

This document outlines the changes made to rename the application from "ReportGPT" to "Plurium POCanator". The renaming process involved updating references throughout the codebase, including Python modules, HTML templates, and Docker configuration files.

## Changes Made

### 1. Django Module Reorganization

- Created new module directory `plurium_pocanator` to replace `reportgpt_web`
- Copied and updated key configuration files:
  - `settings.py`: Updated all references to ReportGPT and module paths
  - `urls.py`: Updated root URL configuration
  - `asgi.py` and `wsgi.py`: Updated module references for ASGI/WSGI applications

### 2. Python Script Updates

- Created new script `plurium_pocanator.py` to replace `reportgpt.py`
- Updated references in `patch_analysis.py` from "ReportGPT" to "Plurium POCanator"
- Modified Django management scripts to use the new settings module
- Updated `fix_commit_parsing_django.py` to use the new settings module

### 3. Configuration Updates

- Updated `manage.py` to use the new settings module
- Modified `Dockerfile` to reference the new module for WSGI application
- Updated `docker-compose.yml` for new container and image names

### 4. Template Updates

- Updated `base.html` to display "Plurium POCanator" in titles, headers, and footers
- Modified navigation and branding elements to reflect the new name

## Testing

After making these changes, the application was tested to ensure functionality was maintained:

- Docker container builds successfully with the new name
- Django management commands work correctly
- Web application loads properly with the new branding
- All features continue to function as before

## Next Steps

- The `reportgpt_web` directory can be safely removed once full testing is complete
- The `reportgpt.py` script can be removed after verifying the functionality of `plurium_pocanator.py`
- Any remaining occurrences of "ReportGPT" in documentation should be updated