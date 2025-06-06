# Changelog

All notable changes to the deSEC Qt DNS Manager will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-06-07

### Added in 0.2.0

- DNS record table sorting by clicking column headers (Name, Type, TTL, Content)
- Double-click to edit records functionality
- Default sorting by Name column for better usability

### Changed in 0.2.0

- Improved TTL column data handling for proper numeric sorting
- Enhanced configuration documentation with clearer distinction between implemented and planned features

### Fixed in 0.2.0

- About dialog improvements:
  - Added email emoticon for better visual appeal
  - Added direct link to changelog on GitHub
  - Fixed dialog layout to dynamically resize without scrollbars
  - Replaced deprecated Qt alignment flags for better PyQt6 compatibility

## [0.1.0] - 2025-06-07

### Added in 0.1.0

- Initial release of deSEC Qt DNS Manager
- PyQt6-based UI for managing DNS records through the deSEC API
- Basic zone management (add, delete, list zones)
- Comprehensive DNS record management:
  - Support for common record types (A, AAAA, CNAME, MX, TXT, etc.)
  - Create, update, and delete records with validation
  - Type-specific validation and guidance
- Detailed logging system with rich contextual information
- Error handling with user-friendly messages
- Cache system for offline support
- Configuration management with secure token storage

### Fixed in 0.1.0

- DNS record creation error handling and validation
- Record dialog sizing to auto-adjust based on content
- Silent failures during record creation process
- Proper handling of duplicate record errors with informative messages
- Log signal connection between dialog and main window

### Documentation in 0.1.0

- Architecture documentation with component descriptions
- Detailed logging and notifications documentation
- Data flow documentation
