# Changelog

All notable changes to the deSEC Qt DNS Manager will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0-beta] - 2025-08-10

### Added in 0.5.0-beta

- **Multi-Profile Support** - Complete implementation of user profiles for managing multiple deSEC accounts or environments
  - Create, switch, rename, and delete profiles through intuitive UI (Profile → Manage Profiles...)
  - Complete data isolation per profile (API tokens, cache, configuration settings)
  - Automatic legacy configuration migration to "Default Profile" for existing users
  - Profile management dialog with safety checks and confirmation prompts
  - Application restart on profile switch ensures complete isolation
  - Each profile stored in separate directory: `~/.config/desecqt/profiles/{profile_name}/`
- Added comprehensive documentation in `doc/PROFILES.md` covering usage, best practices, and troubleshooting
- Added Profile menu to main window showing current active profile
- Added profile switching functionality with automatic application restart
- Updated README.md with multi-profile support information and quick start guide

### Technical Improvements in 0.5.0-beta

- Implemented `ProfileManager` class for centralized profile operations
- Implemented `ProfileDialog` with full profile management capabilities
- Enhanced `ConfigManager` and `CacheManager` to work with profile-specific directories
- Added profile metadata management with `profiles.json` configuration file
- Improved application architecture to support multiple isolated configurations

### Use Cases Enabled in 0.5.0-beta

- Manage multiple deSEC accounts from a single application instance
- Separate work and personal DNS configurations
- Environment-specific profiles (production, staging, development)
- Team collaboration with individual member profiles
- Complete data isolation between different use cases

## [0.4.0-beta] - 2025-06-09

### Added in 0.4.0-beta

- Added dedicated Quit action to File menu with standard Ctrl+Q shortcut
- Added Escape key support to clear active search filters
- Added status bar messages for user actions

### Improved in 0.4.0-beta

- When in offline mode the add/edit/delete buttons are now grayed out even on startup
- Enhanced menu item mnemonics for better keyboard navigation
- Reorganized Help menu for better flow and removed unnecessary separators
- Improved visual feedback and consistency across UI elements

## [0.3.4-beta] - 2025-06-08

### Added in 0.3.4-beta

- Added comprehensive theme support with light, dark, and system modes
- Added automatic system theme detection that follows OS dark/light mode
- Added ROADMAP.md with planned features and current progress

### Fixed in 0.3.4-beta

- Fixed menu structure to maintain clear cache and sync options

## [0.3.3-beta] - 2025-06-08

### Added in 0.3.3-beta

- Added "Validate DNSSEC" button to easily check domain DNSSEC configuration using Verisign Labs debugger

## [0.3.2-beta] - 2025-06-08

### Added in 0.3.2-beta

- Added Changelog to Help menu as separate menu item for improved accessibility
- Added automatic cache clearing when API token is changed for enhanced security
- Added log file purging when API token is changed to prevent information leakage
- Added "Validate DNSSEC" button to easily check domain DNSSEC configuration using Verisign Labs debugger
- Updated README with complete feature list

## [0.3.1-beta] - 2025-06-08

### Added in 0.3.1-beta

- Added new screenshots to README.md
- Added documentation files: CACHING.md, RECORD-MANAGEMENT.md, UI-FEATURES.md
- Added alternative instructions for exiting virtual environment

## [0.3.0-beta] - 2025-06-08

### Added in 0.3.0-beta

- Made multiline DNS records the default display mode for better readability

### Fixed in 0.3.0-beta

- Fixed application crashes caused by pressing the Delete key on zones and records
- Fixed Ctrl+F shortcut to cycle correctly between zone and record search fields
- Fixed Escape key behavior to clear only the currently focused search field
- Fixed log console to appear within the main window instead of as a separate window
- Fixed connection status to show OFFLINE at startup when offline mode is enabled

### Changed in 0.3.0-beta

- Renamed DNS Records label to "DNS Records (RRsets)" for technical accuracy
- Hidden log console by default for new users and during initial setup
- Disabled (grayed out) Add Zone and Delete Zone buttons in offline mode

## [0.2.1] - 2025-06-07

### Fixed in 0.2.1

- Corrected changelog URL in About dialog to point to the correct GitHub repository

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
