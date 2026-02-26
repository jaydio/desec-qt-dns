# deSEC Qt DNS Manager -- Architecture

## Overview

The deSEC Qt DNS Manager is a desktop application built with **PySide6** and
**PySide6-FluentWidgets** (Python 3) that provides a full-featured GUI for
managing DNS zones and records through the deSEC API. The application follows a
modular architecture organised around a central API queue, cache-first display,
and a sidebar-navigated FluentWindow shell with slide-in panels and top-sliding
drawers instead of traditional dialog popups.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **GUI framework** | PySide6 (Qt 6.5+) |
| **Widget library** | PySide6-FluentWidgets (Fluent Design cards, navigation, controls) |
| **HTTP** | requests |
| **Encryption** | cryptography (Fernet AES-128, PBKDF2) |
| **Serialisation** | PyYAML, json, pickle |
| **Versioning** | git (CLI, invoked by `version_manager.py`) |

## Source Modules (25 files)

| Module | Role |
|--------|------|
| `main.py` | Entry point, application bootstrap |
| `main_window.py` | FluentWindow shell, sidebar navigation, AuthPanel slide-in, status bar |
| `api_client.py` | deSEC REST API client with rate limiting, `RateLimitResponse` sentinel |
| `api_queue.py` | Central API queue (QThread, PriorityQueue, QueueItem, auto-retry 429s) |
| `config_manager.py` | JSON config at `~/.config/desecqt/`, Fernet-encrypted token, per-profile |
| `cache_manager.py` | Three-layer cache (memory, pickle, JSON), O(1) indexed lookups |
| `profile_manager.py` | Multi-profile isolation under `~/.config/desecqt/profiles/` |
| `version_manager.py` | Git-based zone versioning at `~/.config/desecqt/versions/` |
| `theme_manager.py` | Thin wrapper: dark / light / auto via `qfluentwidgets.setTheme()` |
| `workers.py` | Background QRunnable workers (fallback when `api_queue` is unavailable) |
| `zone_list_widget.py` | ZoneListModel + ZoneListWidget + AddZonePanel slide-in |
| `record_widget.py` | RecordWidget + RecordEditPanel slide-in (440 px) + BulkDeleteWorker + validation |
| `search_replace_dialog.py` | SearchReplaceInterface sidebar page + SearchWorker |
| `token_manager_dialog.py` | TokenManagerInterface sidebar page + CreateTokenPanel + TokenPolicyPanel + TokenSecretDialog |
| `import_export_dialog.py` | ExportInterface + ImportInterface sidebar pages |
| `import_export_manager.py` | JSON / YAML / BIND / djbdns format handlers |
| `settings_interface.py` | Fluent SettingCard-based sidebar page (replaces deleted `config_dialog.py`) |
| `profile_dialog.py` | ProfileInterface sidebar page + ProfileFormPanel slide-in |
| `queue_interface.py` | QueueInterface sidebar page + QueueDetailPanel slide-in |
| `history_interface.py` | HistoryInterface sidebar page (version timeline + restore) |
| `log_widget.py` | In-window log console, colour-coded severity |
| `fluent_styles.py` | Shared QSS constants (`CONTAINER_QSS`, `COMBO_QSS`, `SCROLL_AREA_QSS`, `SPLITTER_QSS`) |
| `confirm_drawer.py` | Top-sliding two-step drawers: DeleteConfirmDrawer (red), RestoreConfirmDrawer (amber), ConfirmDrawer (blue) |
| `notify_drawer.py` | Top-sliding notification drawer (error / warning / info / success) |
| `auth_dialog.py` | Legacy token entry dialog (unused; retained for reference, can be removed) |

## Core Components

### 1. Central API Queue (`api_queue.py`)

All API calls flow through a single `APIQueue` QThread that processes requests
sequentially from a `PriorityQueue`. Each request is wrapped in a `QueueItem`
carrying the HTTP method, URL, payload, callback, and priority level.

| Priority | Constant | Usage |
|----------|----------|-------|
| 0 | `PRIORITY_HIGH` | Zone list load, connectivity checks |
| 1 | `PRIORITY_NORMAL` | Interactive CRUD (create / edit / delete records) |
| 2 | `PRIORITY_LOW` | Background sync, periodic refresh |

Key behaviours:

- **Sequential processing** -- one request at a time, respecting the configured
  rate limit from `api_client`.
- **Auto-retry on 429** -- if the `Retry-After` header is 60 seconds or less the
  queue sleeps and retries automatically; longer values trigger a cooldown state.
- **Callback dispatch** -- results are emitted via a Qt signal
  (`_callback_dispatch`) to the main thread, keeping UI updates thread-safe.
- **Pause / resume** -- the queue can be paused globally (e.g. when offline) and
  resumed without losing pending items.

### 2. Configuration Management (`config_manager.py`)

- Reads/writes `~/.config/desecqt/profiles/<name>/config.json`
- API tokens encrypted with Fernet AES-128, PBKDF2 key derivation (100 000 iterations, random salt)
- Settings include: API URL, sync interval, rate limit, theme, debug mode, UI preferences

### 3. API Client (`api_client.py`)

- Full deSEC REST API coverage: zones, records, tokens, token policies, account info
- Configurable rate limiting (default 2 req/sec) enforced by `_apply_rate_limit()`
- Returns `RateLimitResponse` sentinel on 429 so the caller (typically `api_queue`) can decide whether to retry or enter cooldown
- Connectivity checking with `is_online` flag
- `get_account_info()` returns `limit_domains` used for the zone-count display

### 4. Cache System (`cache_manager.py`)

Three-layer hierarchy -- see [CACHING.md](./CACHING.md) for full detail:

1. **L1 -- Memory**: O(1) indexed lookups, session lifetime
2. **L2 -- Binary (pickle)**: Fast disk persistence, 3-10x faster than JSON parsing
3. **L3 -- JSON**: Human-readable fallback, robust across version changes

Display strategy: show cached data immediately, then enqueue an API fetch in the
background via `api_queue`. When the fresh response arrives the cache and UI are
updated transparently.

### 5. Version Manager (`version_manager.py`)

Git-based zone versioning stored at `~/.config/desecqt/versions/`:

- **Snapshot**: on every record mutation (create, edit, delete) the current state
  of the zone is committed as a JSON file inside a bare-ish git repository.
- **History**: `git log` / `git show` are used to build a timeline of changes
  per zone, surfaced in `HistoryInterface`.
- **Restore**: any previous snapshot can be restored, which replays the stored
  record set back through the API queue.

### 6. UI Architecture

#### FluentWindow Shell (`main_window.py`)

The main window is a `FluentWindow` (from PySide6-FluentWidgets) with a
collapsible sidebar providing navigation to all pages. There is no traditional
menu bar.

Sidebar layout:

| Position | Items |
|----------|-------|
| **Top** | DNS (globe), Search and Replace (search), Import (right arrow), Export (left arrow), Tokens (certificate), Queue (send), History (update) |
| **Bottom** | Profile (people), Settings (setting), About (info), Log Console (history), Sync (sync), Connection Status (wifi), Last Sync (history) |

The sidebar expanded width is 180 px (`self.navigationInterface.setExpandWidth(180)`).

The main content area uses a two-pane splitter when the DNS page is active: zone
list on the left, record panel on the right.

#### Slide-in Panels

All record editing, zone creation, token creation, profile editing, and queue
detail views use right-side slide-in overlay panels (440 px wide for
`RecordEditPanel`, other widths as appropriate). Panels animate in/out with
`QPropertyAnimation` on the `pos` property (220 ms duration).

This replaces all former `QDialog` popups with a modern, non-blocking interaction
pattern.

#### Top-sliding Drawers

Two categories of drawers slide down from the top of the window:

| Module | Drawer | Colour | Purpose |
|--------|--------|--------|---------|
| `confirm_drawer.py` | `DeleteConfirmDrawer` | Red | Two-step confirmation for destructive deletes |
| `confirm_drawer.py` | `RestoreConfirmDrawer` | Amber | Two-step confirmation for version restores |
| `confirm_drawer.py` | `ConfirmDrawer` | Blue | Generic two-step confirmation |
| `notify_drawer.py` | `NotifyDrawer` | Varies | Transient notifications (error, warning, info, success) |

These drawers replace all former `QMessageBox` confirmation and notification
popups with animated, contextual overlays.

#### Zone List (`zone_list_widget.py`)

- `ZoneListModel` (`QAbstractListModel`) for efficient virtual rendering
- `SearchLineEdit` for real-time filtering (built-in search icon)
- `AddZonePanel` slide-in for zone creation
- Account domain limit: `"Total zones: N/limit"` displayed in the header

#### Record Management (`record_widget.py`)

- Sortable `TableWidget` with columns: check, Name, Type, TTL, Content, Actions
- Checkbox column uses native `CheckBox` via `setCellWidget`
- **Batch actions**: Select All, Select None, Delete Selected (N) with `DeleteConfirmDrawer`
- `BulkDeleteWorker(QThread)` runs deletes in background with per-record logging
- Per-row Edit / Delete buttons plus Delete-key single-record deletion
- `RecordEditPanel` slide-in: 38+ DNS record types with format hints, examples,
  validation, and DNSSEC warnings
- `RECORD_TYPE_GUIDANCE` dict provides tooltip, format string, example, and optional
  regex for each type
- `_validate_record_content` module-level helper for content validation
- All mutations are enqueued through `api_queue` (PRIORITY_NORMAL); callbacks
  trigger `version_manager.snapshot()`, cache clear, and table refresh

#### Global Search and Replace (`search_replace_dialog.py`)

- `SearchReplaceInterface` is a sidebar page, not a popup dialog
- `SearchWorker` runs the search in a background thread
- Searches across all zones simultaneously
- Filters: subname (contains), type, content (contains), TTL (exact), zone name
- Optional regex mode for subname, content, and zone filters
- Results table with per-row checkboxes and Select All / Select None
- Content find and replace, subname rename, TTL update, and bulk delete
- Change log panel showing old to new values for each applied change
- Export Results for archiving search output

#### Token Manager (`token_manager_dialog.py`)

- `TokenManagerInterface` is a sidebar page
- Lists all API tokens with name, creation date, last used, validity, and permission summary
- Details panel: editable name, permissions (`perm_create_domain`, `perm_delete_domain`,
  `perm_manage_tokens`, `auto_policy`), expiration, allowed subnets
- `CreateTokenPanel` slide-in for new token creation
- `TokenPolicyPanel` slide-in for RRset policy editing (domain / subname / type / write)
- `TokenSecretDialog` for displaying newly created token secrets
- Requires `perm_manage_tokens` on the active token

#### Import / Export (`import_export_dialog.py` + `import_export_manager.py`)

- `ExportInterface` and `ImportInterface` are separate sidebar pages
- Four formats: JSON (API-compatible), YAML, BIND zone files, djbdns/tinydns
- Single zone export or bulk ZIP export with progress tracking
- Import modes: Append, Merge, Replace (with `DeleteConfirmDrawer` for destructive Replace)
- Target zone auto-creation if zone does not exist
- Preview before import showing record count and sample data

#### Queue Interface (`queue_interface.py`)

- `QueueInterface` sidebar page showing pending and completed API requests
- `QueueDetailPanel` slide-in for inspecting individual queue items
- Pause / resume button to halt queue processing
- Batch retry for failed items

#### History Interface (`history_interface.py`)

- `HistoryInterface` sidebar page
- Zone selector with per-zone version timeline
- Each entry shows commit hash, timestamp, and change summary
- Restore action with `RestoreConfirmDrawer` two-step confirmation

#### Settings (`settings_interface.py`)

- Fluent `SettingCardGroup`-based sidebar page (replaces the deleted `config_dialog.py`)
- Theme mode: Light / Dark / Auto (via `qfluentwidgets.setTheme()`)
- API URL, sync interval (1-60 min), rate limit (0-10 req/sec)
- Debug mode toggle
- All settings persisted through `config_manager`

#### Profile Management (`profile_dialog.py`)

- `ProfileInterface` sidebar page
- `ProfileFormPanel` slide-in for creating and renaming profiles
- Each profile is fully isolated under `~/.config/desecqt/profiles/<name>/`

#### Log Console (`log_widget.py`)

- Collapsible panel at the bottom of the main window
- Colour-coded severity: success (green), warning (orange), error (red), info (palette text)
- Timestamps in muted palette colour; 500-line rolling limit
- Message count label; Clear button

#### Shared Styles (`fluent_styles.py`)

- `CONTAINER_QSS` -- transparent `QTabWidget::pane` and `QGroupBox` backgrounds
- `COMBO_QSS` -- ComboBox styling overrides
- `SCROLL_AREA_QSS` -- scroll area background transparency
- `SPLITTER_QSS` -- splitter handle styling

These constants are imported wherever needed, eliminating the copy-pasted QSS
that previously appeared in four separate files.

## Data Flow

### Authentication

1. On startup, check profile config for an encrypted API token.
2. If missing, the `AuthPanel` slides in from the right inside the main window
   (not a separate dialog).
3. User enters the token; it is Fernet-encrypted and stored in the profile config.
4. Token is decrypted only in memory when needed for API calls.

### Sync Flow

1. A `QTimer` fires at the configured interval (or the user triggers manual sync).
2. Cached zone data is displayed immediately (cache-first).
3. A zone-list fetch is enqueued via `api_queue` at `PRIORITY_HIGH`.
4. When the response arrives, the callback updates the cache and zone list UI.
5. After sync: `_check_token_management_permission()` and `_fetch_account_limit()`
   run as additional queued requests.
6. When a zone is selected: a record fetch is enqueued; the callback updates the
   record table.

### Record Mutation

1. User edits, creates, or deletes a record via `RecordEditPanel` or batch action.
2. The API call is enqueued via `api_queue` at `PRIORITY_NORMAL`.
3. On success the callback triggers:
   - `version_manager.snapshot()` to commit the new zone state,
   - domain cache clear,
   - table refresh from the updated cache / API response.

### Rate Limiting

1. `api_client._apply_rate_limit()` enforces the configured requests-per-second
   between consecutive calls.
2. If the API returns HTTP 429, `api_client` wraps it in a `RateLimitResponse`
   sentinel containing the `Retry-After` value.
3. `api_queue` inspects the sentinel:
   - If `Retry-After` is 60 seconds or less, the queue sleeps and retries automatically.
   - If longer than 60 seconds, the queue enters a cooldown state and notifies the UI.

## Design Patterns

| Pattern | Where used |
|---------|-----------|
| **Model-View** | `ZoneListModel` / `ListView` for the zone list |
| **Observer (signals/slots)** | All inter-component communication |
| **Proxy** | `CacheManager` transparent fallback chain |
| **Central Queue** | `APIQueue` sequential processing of all API calls |
| **Worker** | `QRunnable` + `QThreadPool` for non-queue background I/O |
| **Slide-in Panel** | Right-side overlays (`QPropertyAnimation`, 220 ms) for editing |
| **Top-sliding Drawer** | Confirmation and notification overlays (`QPropertyAnimation`) |

## Security

- API tokens encrypted (Fernet AES-128, PBKDF2, 100 000 iterations, random salt)
- No plaintext credentials stored or logged
- Two-step confirmation drawers for all destructive actions (delete zone, delete
  record, bulk delete, replace-mode import, version restore)
- DNSSEC-related record types (`DNSKEY`, `DS`, `CDNSKEY`) carry in-UI warnings;
  `CDS` rejected by the API and handled accordingly

## Error Handling

1. `api_client._make_request` catches and categorises HTTP errors; returns
   `(success, data_or_message)` tuples.
2. The UI shows user-friendly notifications via `NotifyDrawer`; details are logged
   to the log console.
3. Bulk operations (import, bulk delete, search and replace) continue on per-record
   failures; a summary is logged on completion.
4. Rate-limit errors (429) are handled automatically by the central queue with
   retry or cooldown, and surfaced in the queue interface.

## Configuration Location

All persistent state lives under `~/.config/desecqt/`:

| Path | Contents |
|------|----------|
| `config.json` | Global config (active profile, window geometry) |
| `profiles/<name>/config.json` | Per-profile config (token, API URL, settings) |
| `profiles/<name>/cache/` | Pickle and JSON cache files |
| `logs/` | Application log files |
| `versions/` | Git repository for zone version snapshots |
