# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Changed
- **Renamed the project to POCanator.** The Django settings package
  `plurium_pocanator/` is now `pocanator/`, and all module references
  (`DJANGO_SETTINGS_MODULE`, WSGI/ASGI, Docker image/container names, templates)
  were updated accordingly. Remaining legacy "ReportGPT" branding was also
  normalized to POCanator.
- The standalone CLI `reportgpt.py` is now `pocanator.py`.

### Added
- Open-source project scaffolding: `LICENSE` (Apache-2.0), `NOTICE`,
  `SECURITY.md` (responsible-use policy and vulnerability reporting),
  `CONTRIBUTING.md`, and `CODE_OF_CONDUCT.md`.
- Rewritten `README.md` with setup, configuration, and responsible-use guidance.

### Removed
- Dead duplicate Django package `reportgpt_web/` (superseded by `pocanator/`).
- One-off development scripts and artifacts (`fix_*.sh`, `fix_*.py`,
  `phase4_update.sh`, `RENAMING.md`, the oversized `CHANGES.md` dev log,
  duplicate standalone script, orphaned `patch_analysis.py` and its template,
  and sample GHSA analysis outputs).

## [1.0.0] - 2025-03-26

### Added
- Enhanced PoC generation with advanced prompt engineering techniques
  - Multi-stage prompting for structured vulnerability analysis
  - Example-guided generation with concrete code examples for different vulnerability types
  - Framework-specific security guidance for popular frameworks
- Educational focus for security content
  - Side-by-side examples of vulnerable and secure code patterns
  - Clear security best practices
  - Detailed explanations of security concepts
- Fixed advisory title extraction from GitHub
  - Implemented robust title extraction with multiple fallback mechanisms
  - Created Django management command to update existing advisories
- Fixed progress bar display during analysis creation
  - Added proper null checks in JavaScript
  - Improved loading indicator behavior
