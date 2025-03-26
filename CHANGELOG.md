# Changelog

All notable changes to this project will be documented in this file.

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