# Changelog

All notable changes to the deSEC Qt DNS Manager will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0-beta] - 2026-02-27

### Added in 1.0.0-beta

- **DNSSEC sidebar page** (`dnssec_interface.py`) — read-only DS + DNSKEY key viewer for any zone
  - Zone selector dropdown; data fetched on demand via API queue (never cached)
  - DS Format card: all digest variants (SHA-256, SHA-384, etc.) in a single card with bold digest-type labels when multiple variants are present
  - DNSKEY Format card: Flags, Protocol, Algorithm, and full Public Key field
  - Copy button per card copies the full record string to clipboard
  - Validate DNSSEC setup shortcuts to Verisign Debugger and DNSViz
  - `get_zone()` added to `APIClient` for fetching full zone data including DNSSEC key material

- **InfoBar toasts** — auto-dismissing colour-coded notifications anchored to the top-centre of the main window
  - Replaces `NotifyDrawer` for all API operation feedback across every sidebar page
  - Variants: success (green, 4 s), info (blue, 3 s), warning (amber, 5 s), error (red, 8 s)
  - All calls use `parent=self.window()` for consistent top-centre positioning regardless of which sub-widget triggers them

- **Type and TTL filter fields** — two dedicated inputs added to the right of the main record search bar
  - Type filter (≈ 90 px): narrows records by type (e.g. "A", "MX", "TXT")
  - TTL filter (≈ 80 px): narrows records by TTL value
  - All three filters AND'd via `_apply_filters()`; each field is independent

- **Alphabetical sorting** — all list views now sorted A→Z on load
  - Zone list (`ZoneListModel.update_zones()`)
  - Version history zone list (`HistoryInterface._refresh_zones()`)
  - Token list (`TokenManagerInterface._on_tokens_loaded()`)

- **Fluent Design UI overhaul** — complete migration from PyQt6 to PySide6 + PySide6-FluentWidgets
  - FluentWindow shell with sidebar navigation replaces the traditional menu bar
  - Sidebar items: DNS, DNSSEC, Search, Import, Export, Queue, History, Profile, Tokens, Settings (top); About, Log Console, Sync, Connection Status, Last Sync (bottom)
  - Configurable sidebar width (180 px expanded)

- **Slide-in panels** — all form dialogs replaced with animated right-side overlay panels (220 ms, QPropertyAnimation)
  - RecordEditPanel (440 px) for adding and editing DNS records
  - AddZonePanel (340 px) for creating zones
  - CreateTokenPanel (460 px) for creating API tokens
  - TokenPolicyPanel (400 px) for adding/editing RRset policies
  - ProfileFormPanel (400 px) for creating and renaming profiles
  - QueueDetailPanel (480 px) for inspecting request/response data
  - AuthPanel (440 px) for API token entry

- **Confirmation drawers** — two-step top-sliding drawers replace all QMessageBox popups
  - DeleteConfirmDrawer (red) for destructive actions: delete zone, delete record, delete profile, clear cache
  - RestoreConfirmDrawer (amber) for restore/overwrite actions: restore zone version
  - ConfirmDrawer (blue) for general confirmations: quit, switch profile, apply replace, import records
  - Two-step confirmation with button-swap prevents accidental destructive clicks

- **Central API queue** (`api_queue.py`) — all API calls processed through a background QThread
  - QueueItem dataclass with priority (HIGH=0, NORMAL=1, LOW=2), category, action, callable, callback
  - Sequential processing with FIFO ordering within priority tier
  - Auto-retry on transient HTTP 429 responses (retry_after ≤ 60 s, up to 3 retries)
  - Cooldown mode for extended rate limits (retry_after > 60 s): pauses queue, stops timers, auto-resumes
  - Adaptive rate limiting: `adapt_rate_limit()` halves rate on 429 (floor 0.25 req/s)
  - Callback dispatch to main thread via Qt Signal for thread-safe UI updates
  - Pause/resume support (used by offline mode and rate-limit cooldown)

- **Queue monitor** (`queue_interface.py`) — sidebar page for observing and managing the API queue
  - Pending queue table with priority icon, action, and status
  - History table with filtering by category, search, and status (completed/failed/cancelled)
  - QueueDetailPanel slide-in showing full request/response JSON for any history item
  - Pause/Resume, Cancel Selected, Retry Failed, Clear History actions

- **Git-based zone version history** (`version_manager.py`) — automatic versioning at `~/.config/desecqt/versions/`
  - Snapshot committed on every record mutation (create, update, delete)
  - `get_history()` returns commit timeline per zone (hash, date, message)
  - `restore()` retrieves records from any historical version

- **Version history browser** (`history_interface.py`) — sidebar page for browsing and restoring zone versions
  - Zone list showing all versioned zones (sorted alphabetically)
  - Commit timeline with date, message, and truncated hash
  - Record preview in BIND-style format for any selected version
  - Restore button with RestoreConfirmDrawer confirmation; uses bulk PUT via API queue
  - Delete version history per zone

- **Settings sidebar page** (`settings_interface.py`) — replaces the modal configuration dialog
  - Two-column layout with Fluent SettingCard groups
  - Left: Connection (API URL, token button), Synchronization (sync interval, rate limit)
  - Right: Appearance (theme), Queue (persist history, retention limit), Advanced (debug mode, token manager)

- **Shared Fluent styles** (`fluent_styles.py`) — extracted theme-aware QSS constants
  - `container_qss()` for QTabWidget, QGroupBox, QLabel with dark/light detection
  - `combo_qss()` for native QComboBox styling
  - `SCROLL_AREA_QSS` and `SPLITTER_QSS` constants

- **New documentation** — `doc/API-NOTES.md` covering the API queue, rate limiting, 429 handling, and all deSEC endpoints used

### Changed in 1.0.0-beta

- **Tech stack** — migrated from PyQt6 to PySide6 + PySide6-FluentWidgets
- **Notifications** — `NotifyDrawer` superseded by `InfoBar` toasts; `notify_drawer.py` retained for reference
- **Navigation** — sidebar replaces the traditional menu bar; "Search & Replace" renamed to "Search"; DNSSEC page added between DNS and Search; Tokens moved below Profile
- **Token policy save** — panel slides out immediately on submit; errors surfaced via InfoBar toast
- **Token list** — sorted alphabetically; policy table sortable by any column; Delete Policy button shows selected row count
- **Record editing** — slide-in RecordEditPanel replaces the Record QDialog popup
- **Profile management** — ProfileFormPanel slide-in replaces CreateProfileDialog and RenameProfileDialog popups; ConfirmDrawer replaces QMessageBox for switch confirmation
- **Import/Export/Search/Settings confirmations** — ConfirmDrawer and DeleteConfirmDrawer replace all QMessageBox popups
- **Default sync interval** — changed from 10 to 15 minutes
- **Default rate limit** — changed from 2.0 to 1.0 req/sec
- **Cache layers** — simplified to memory + JSON (pickle layer removed)
- **Theme system** — simplified to dark/light/auto via `qfluentwidgets.setTheme()`

### Technical Improvements in 1.0.0-beta

- 26 source modules (up from 18), all under `src/`
- `config_dialog.py` deleted — superseded by `settings_interface.py`
- `auth_dialog.py` deprecated — replaced by `AuthPanel` in `main_window.py`
- All `pyqtSignal` → `Signal`, all `PyQt6` imports → `PySide6`
- `QDialogButtonBox` removed everywhere; replaced with explicit PushButton/PrimaryPushButton pairs
- Hardcoded hex colours removed from all stylesheets; replaced with palette references and `isDarkTheme()` checks
- Shared QSS extracted to `fluent_styles.py` (was copy-pasted in 4+ files)
- `RecordDialog` QDialog → `RecordEditPanel` slide-in overlay with `QPropertyAnimation`
- Thread-safe callback dispatch in APIQueue via `_callback_dispatch` Signal
- Atomic file writes (tempfile + os.replace) in config, cache, and queue history persistence

## [0.12.1-beta] - 2026-02-23

### Fixed in 0.12.1-beta

- **Documentation** — screenshot widths in `img/README.md` adjusted; full-width screenshots (main window, search & replace, token manager) now display at 100% while smaller dialogs remain pinned to relative widths to avoid upscaling on GitHub

## [0.12.0-beta] - 2026-02-23

### Added in 0.12.0-beta

- **Account domain limit** — zone list header now shows `Total zones: N/100` where 100 is the maximum domains allowed on the account, fetched from `GET /auth/account/` after every successful sync. Falls back gracefully to `Total zones: N` when offline or if the API call fails.

### Fixed in 0.12.0-beta

- **DNSSEC record types** — removed `CDS` from the record type list entirely (deSEC auto-manages it; the API returns 403 on any write attempt). Added prominent warnings to `DNSKEY`, `DS`, and `CDNSKEY` tooltips explaining they are also auto-managed and that adding extra values is only safe for advanced multi-signer DNSSEC setups.
- **Record type guidance** — eliminated duplicate `CAA` and `SSHFP` definitions that were silently overwriting each other. Normalised all 38 record type entries to consistent `<field>` placeholder style with more useful tooltips and realistic examples.
- **Theme consistency** — removed all remaining hardcoded colour values across the UI; every widget now uses Qt palette references (`palette(highlight)`, `palette(mid)`, `palette(placeholdertext)`) so the app renders correctly in light, dark, and system themes:
  - Log console: removed hardcoded `#f8f8f8` background; info messages adapt to the active palette
  - Search & Replace row highlights: palette-blended tints instead of fixed pastel colours
  - Zone list, token manager, import/export, profile, and config dialogs: grey hex values replaced with semantic palette references
  - Status indicator colours changed to Material-style values (`#4caf50`, `#ef5350`, `#ffa726`) that are legible in both themes
- **Navigation** — removed the separate Account menu; *Manage Tokens* moved into the File menu with surrounding separators
- **Default window sizes** — set sensible opening sizes for the main window (1280 × 860), Record dialog (560 × 640), Import/Export dialog (600 × 740), and Create New Token dialog (600 × 750)
- **Records table column widths** — widened the Name column default from 120 px to 220 px so long subnames like `_acme-challenge.sub` are visible without truncation on first launch

## [0.11.0-beta] - 2026-02-23

### Added in 0.11.0-beta

- **Batch Actions via Selectable List** — multi-select checkboxes on the DNS records table for bulk operations
  - New leftmost checkbox column on the records table; all rows start unchecked
  - **Select All** / **Select None** buttons in the toolbar for one-click selection management
  - **Delete Selected (N)** button with live count; red-styled to signal destructive action
  - Confirmation dialog before bulk delete listing the record count
  - Background `_BulkDeleteWorker` thread keeps the UI responsive during large deletes
  - Per-record success/failure logged individually; summary logged on completion
  - Cache invalidated and table refreshed automatically after bulk delete
  - All bulk controls disabled in offline mode
  - Per-row Edit/Delete buttons and Delete-key single-record deletion remain fully functional

### Technical Improvements in 0.11.0-beta

- Added `COL_CHECK`, `COL_NAME`, `COL_TYPE`, `COL_TTL`, `COL_CONTENT`, `COL_ACTIONS` module-level constants replacing all hardcoded column indices in `record_widget.py`
- New `_BulkDeleteWorker(QThread)` class with `progress_update`, `record_done`, and `finished` signals
- New methods on `RecordWidget`: `_on_item_changed`, `_update_bulk_btn`, `_select_all_records`, `_select_none_records`, `_get_checked_records`, `delete_selected_records`, `_set_bulk_busy`, `_on_bulk_record_done`, `_on_bulk_delete_finished`
- `blockSignals(True/False)` wraps checkbox population in `update_records_table()` to prevent spurious state updates

## [0.10.0-beta] - 2026-02-23

### Added in 0.10.0-beta

- **Global Search & Replace** — search across all DNS zones simultaneously and apply bulk changes
  - Filter by any combination of subname (contains), record type, content (contains), TTL (exact), and zone name
  - **Regex mode** — toggle "Use regex" to use Python regular expressions for subname, content, and zone filters; includes an inline `(?)` help icon with examples
  - Results table with per-row checkboxes — select exactly which records to update
  - Select All / Select None buttons for quick selection management
  - Content find & replace: string substitution within record values (e.g. replace an old IP)
  - Subname rename: transparently creates new rrset and deletes the old one
  - TTL bulk update: set a new TTL across all matched records in one operation
  - Content and TTL changes can be combined in a single pass
  - **Delete Selected** — permanently delete all checked records with a confirmation dialog
  - **Export Results** — save the current results table to CSV or JSON
  - **Change Log panel** — collapsible log showing every CONTENT / RENAME / TTL / DELETED change with old→new values; Clear Log button resets it
  - Row-level feedback: rows turn green on success, red on failure with error tooltip
  - Progress bar with per-zone status during both search and replace phases
  - Offline-safe: search works against cache when offline; Apply and Delete buttons disabled when offline
  - Confirmation dialog before any destructive replace or delete operation
  - Auto-refreshes the currently open zone's records after the dialog closes
  - File → Global Search & Replace... in the menu

### Technical Improvements in 0.10.0-beta

- New `src/search_replace_dialog.py` with `SearchReplaceDialog`, `_SearchWorker(QThread)`, `_ReplaceWorker(QThread)`, `_DeleteWorker(QThread)`
- Search loads records from cache first, falls back to API per zone — no blocking the UI
- Replace and delete workers invalidate per-domain cache after each zone's records are updated
- Subname rename uses create-then-delete pattern against the rrset API endpoints
- Empty replacement guard: replacements that would produce empty record values are rejected
- Regex patterns pre-validated before worker starts; invalid patterns shown with a clear error

## [0.9.0-beta] - 2026-02-23

### Added in 0.9.0-beta

- **Token Management Interface** — full API token lifecycle management via a new Account menu
  - View all tokens associated with the account in a sortable table (name, created, last used, validity, permission flags)
  - Create new tokens with configurable permissions, expiration, and subnet restrictions
  - Edit existing token settings: name, permissions, max age, max unused period, allowed subnets, auto-policy
  - Delete tokens with a safety confirmation warning
  - Secure one-time secret display: token value shown exactly once after creation, requires explicit acknowledgement before the dialog closes
  - Copy-to-clipboard button for both token IDs and newly created secrets
- **Per-Token RRset Policy Management** — fine-grained domain/record access control
  - View all RRset policies for any selected token
  - Add, edit, and delete policies with domain, subname, type, and write-permission fields
  - Null/default fields displayed in italics as "(default)" for clarity
- **Account Menu** — new top-level menu between Profile and Connection
  - "Manage Tokens..." action gated behind a background permission check
  - Automatically enabled/disabled based on whether the current token has `perm_manage_tokens`
  - Tooltip explains why the action is disabled when permissions are insufficient

### Technical Improvements in 0.9.0-beta

- Added 9 new API methods to `APIClient`: `list_tokens`, `create_token`, `get_token`, `update_token`, `delete_token`, `list_token_policies`, `create_token_policy`, `update_token_policy`, `delete_token_policy`
- New `src/token_manager_dialog.py` with four dialog classes: `TokenManagerDialog`, `CreateTokenDialog`, `TokenSecretDialog`, `TokenPolicyDialog`
- Background permission check (`_check_token_management_permission`) triggered after successful sync and connectivity checks — non-blocking, uses existing QThreadPool
- All token/policy API calls inside the dialog run in background workers to keep the UI responsive

## [0.8.0-beta] - 2025-08-11

### Added in 0.8.0-beta

- **Bulk Export Functionality** - Export multiple DNS zones simultaneously with ZIP compression
  - Bulk export toggle with adaptive UI that switches between single and multiple zone selection modes
  - Scrollable zone selection list with checkboxes for easy multi-zone selection
  - Select All/Select None buttons for convenient zone management
  - ZIP compression automatically packages multiple zone files into a single archive
  - Real-time progress tracking during bulk export operations with detailed status updates
  - Support for all existing export formats (JSON, YAML, BIND, djbdns) in bulk mode
  - Graceful error handling that continues processing other zones if one fails
  - Auto-generated ZIP filenames with timestamp for better organization
  - Optimized UI layout that dynamically adapts based on the number of available zones

### Technical Improvements in 0.8.0-beta

- Enhanced ImportExportManager with `export_zones_bulk()` method for multi-zone operations
- Updated ImportExportWorker to handle bulk export operations with progress callbacks
- Improved ImportExportDialog UI with dynamic zone count-based layout adjustments
- Added ZIP file creation using Python's zipfile module with compression
- Enhanced error handling and logging for bulk operations
- Optimized UI spacing and padding for better visual appearance with few zones

### Documentation in 0.8.0-beta

- Updated `doc/IMPORT_EXPORT.md` with comprehensive bulk export documentation
- Enhanced ROADMAP.md with completed v0.8.0-beta features
- Added detailed usage instructions for bulk export functionality

### User Experience Improvements in 0.8.0-beta

- Contextual UI messages showing zone count ("📁 1 zone available for bulk export")
- Dynamic button text changes ("Export Zone" vs "Export Selected Zones (ZIP)")
- Improved visual hierarchy and spacing for single-zone scenarios
- Enhanced file dialog integration with format-specific filters

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
