# Changelog

All notable changes to the deSEC Qt DNS Manager will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0-beta] - 2025-08-11

### Added in 0.7.0-beta

- **Record Timestamp Tooltips** - Enhanced user experience with hover tooltips showing DNS record metadata
  - Hover tooltips display creation and last modification timestamps for all DNS records
  - Clean timestamp display showing "Created" and "Last Modified" dates in UTC format
  - Available on all record table columns (Name, Type, TTL, Content) for comprehensive coverage
  - Timestamps sourced directly from deSEC API cache data when available

### Technical Improvements in 0.7.0-beta

- Added `_get_timestamp_tooltip()` helper method for consistent timestamp formatting
- Enhanced record table items with timestamp metadata display
- Improved user interface feedback with non-intrusive hover information
- ISO timestamp parsing with graceful fallback for malformed dates

### Documentation in 0.7.0-beta

- Added comprehensive release process documentation (`doc/RELEASE-PROCESS.md`)
- Reorganized README.md Key Features section to eliminate redundancies
- Updated screenshot gallery with new tooltip demonstration (`img/record_list_tooltip.png`)
- Enhanced visual documentation with timestamp tooltip examples
- Improved project organization and maintainability documentation

## [0.6.0-beta] - 2025-08-10

### Added in 0.6.0-beta

- **Enhanced Import/Export Functionality** - Major improvements to DNS zone import/export capabilities
  - Enhanced import modes with clear terminology: "Append", "Merge", "Replace" with detailed descriptions
  - Target zone selection allowing users to specify destination zone with auto-creation if missing
  - Real-time progress tracking with visual progress bar showing actual percentage (0-100%)
  - Auto-generated export filenames with timestamps for better organization
  - Post-import synchronization for immediate UI updates after successful imports
- **API Rate Limiting System** - User-configurable rate limiting to prevent timeouts during bulk operations
  - Configurable rate limiting from 0-10 requests/second (default: 2 req/sec)
  - Centralized implementation with thread-safe design for all API calls
  - Configuration integration with per-profile persistence and UI controls in settings dialog
  - Bulk operation support to prevent timeouts during large import operations
- **Enhanced Progress Tracking** - Professional-grade progress feedback for all operations
  - Determinate progress bar showing actual completion percentage instead of indeterminate spinner
  - Multi-stage progress tracking: File parsing → Zone setup → Record processing → Completion
  - Per-record progress updates during import operations
  - Clear status messages describing current operations ("Creating 25 records...", "Processed 15/25 records...")
  - Support for all import modes: Append, Merge, and Replace
- **Zone Management Improvements** - Enhanced zone operations with better UI consistency
  - Enhanced zone deletion that automatically triggers sync and clears records view
  - Proper UI state management ensuring interface reflects actual API state
  - Automatic cache cleanup and UI updates after zone operations
- **Comprehensive Documentation** - New and updated documentation for all features
  - New `doc/RATE-LIMIT.md` with comprehensive API rate limiting guide
  - Enhanced `doc/IMPORT_EXPORT.md` with new import modes and features
  - Updated `ROADMAP.md` and `README.md` reflecting v0.6.0-beta enhancements

### Fixed in 0.6.0-beta

- **Profile Switching** - Fixed application restart functionality
  - Profile switching now properly restarts the application to load new profile configuration
  - Ensures complete profile isolation with no data mixing between profiles
  - Reliable configuration loading with all components using correct profile settings
- **Import/Export Stability** - Improved error handling and validation
  - Better error messages and recovery during import operations
  - Fixed tuple unpacking errors related to record data processing
  - Enhanced file format validation with better user feedback
- **UI State Management** - Consistent interface behavior after operations
  - Fixed UI consistency issues after zone deletion
  - Proper records view clearing when zones are deleted
  - Improved error handling with graceful failure recovery

### Technical Improvements in 0.6.0-beta

- Enhanced `ImportExportManager` with progress callback support throughout import/export operations
- Improved `APIClient` with centralized rate limiting using thread-safe locks
- Better error handling and logging throughout the application
- Generic configuration accessors (`get_setting`/`set_setting`) for future extensibility
- New `api_rate_limit` setting with proper getter/setter methods
- Enhanced configuration dialog with help text and validation
- Improved UI/UX with clearer import mode descriptions and warnings for destructive operations
- Real-time progress feedback during all operations with consistent terminology

### Use Cases Enhanced in 0.6.0-beta

- **Professional DNS Management** - Enterprise-level features for bulk operations and data migration
- **Reliable Bulk Operations** - Rate limiting prevents API timeouts during large imports
- **Clear Progress Feedback** - Users can see exactly what's happening during operations
- **Flexible Import Options** - Multiple import modes for different use cases and safety requirements
- **Better Zone Management** - Consistent UI state and immediate feedback after operations

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
