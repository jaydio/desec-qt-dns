# deSEC Qt DNS Manager — Architecture

## Overview

The deSEC Qt DNS Manager is a desktop application built with **PyQt6** and Python 3 that provides a full-featured GUI for managing DNS zones and records through the deSEC API. The application follows a modular architecture to ensure maintainability and separation of concerns.

## Source Modules

| Module | Role |
|--------|------|
| `main.py` | Entry point, application bootstrap |
| `main_window.py` | Main window, menu bar, sync loop, status bar |
| `api_client.py` | deSEC REST API client with rate limiting |
| `config_manager.py` | JSON config, Fernet-encrypted token storage |
| `cache_manager.py` | Three-layer cache (memory → pickle → JSON) |
| `profile_manager.py` | Multi-profile isolation |
| `workers.py` | Background QRunnable workers (zones, records) |
| `theme_manager.py` | Light / Dark / System theme switching |
| `zone_list_widget.py` | Zone list with search and account limit display |
| `record_widget.py` | Records table, batch select/delete, record dialog |
| `log_widget.py` | In-window log console, colour-coded severity |
| `search_replace_dialog.py` | Global Search & Replace across all zones |
| `token_manager_dialog.py` | API token management, RRset policies |
| `import_export_dialog.py` | Import/Export UI with progress tracking |
| `import_export_manager.py` | JSON/YAML/BIND/djbdns format handlers |
| `config_dialog.py` | Configuration settings editor |
| `profile_dialog.py` | Profile management UI |
| `auth_dialog.py` | Initial API token entry |

## Core Components

### 1. Configuration Management (`config_manager.py`)

- Reads/writes `~/.config/desecqt/profiles/<name>/config.json`
- API tokens encrypted with Fernet AES-128, PBKDF2 key derivation (100k iterations)
- Settings include: API URL, sync interval, rate limit, theme, debug mode, UI preferences

### 2. API Client (`api_client.py`)

- Full deSEC REST API coverage: zones, records, tokens, token policies, account info
- Configurable rate limiting (default 2 req/sec) to avoid 429 responses during bulk ops
- Connectivity checking with `is_online` flag
- `get_account_info()` returns `limit_domains` used for the zone count display

### 3. Cache System (`cache_manager.py`)

Three-layer hierarchy — see [CACHING.md](./CACHING.md) for full detail:

1. **L1 — Memory**: O(1) indexed lookups, session-lifetime
2. **L2 — Binary (pickle)**: Fast disk persistence, 3–10× faster than JSON parsing
3. **L3 — JSON**: Human-readable fallback, robust across version changes

### 4. UI Components

#### Main Window

- Two-pane layout: zone list (left) / record panel (right)
- Menu bar: File, Profile, Connection, View, Help
- Background sync timer with configurable interval
- Status bar: last sync time, ONLINE/OFFLINE indicator

#### Zone List (`zone_list_widget.py`)

- `QAbstractListModel` for efficient virtual rendering
- Real-time search filter
- Account domain limit: fetches `limit_domains` via `GET /auth/account/` in a background thread and displays `"Total zones: N/limit"` in the header

#### Record Management (`record_widget.py`)

- Sortable `QTableWidget` with columns: ☐ | Name | Type | TTL | Content | Actions
- Checkbox column (col 0) uses native `QCheckBox` via `setCellWidget` for correct rendering
- **Batch actions**: Select All, Select None, Delete Selected (N) with confirmation
- `_BulkDeleteWorker(QThread)` runs deletes in background with per-record logging
- Per-row Edit / Delete buttons plus Delete-key single-record deletion
- Record dialog: 38 DNS record types with format hints, examples, validation, and DNSSEC warnings
- `RECORD_TYPE_GUIDANCE` dict provides tooltip, format string, example, and optional regex for each type
- Column index constants: `COL_CHECK=0`, `COL_NAME=1`, `COL_TYPE=2`, `COL_TTL=3`, `COL_CONTENT=4`, `COL_ACTIONS=5`

#### Global Search & Replace (`search_replace_dialog.py`)

- Searches across all zones simultaneously
- Filters: subname (contains), type, content (contains), TTL (exact), zone name
- Optional regex mode for subname, content, and zone filters
- Results table with per-row checkboxes and Select All / Select None
- Content find & replace, subname rename, TTL update, and bulk delete
- Change log panel showing old → new values for each applied change
- Export Results for archiving search output

#### Token Manager (`token_manager_dialog.py`)

- Lists all API tokens with name, creation date, last used, validity, and permission summary
- Details panel: editable name, permissions (perm_create_domain, perm_delete_domain, perm_manage_tokens, auto_policy), expiration, allowed subnets
- RRset Policies tab: add/edit/delete fine-grained access rules per domain/subname/type/write
- Create New Token dialog with all settings in one place
- Requires `perm_manage_tokens` on the active token; availability checked in background on every sync

#### Import/Export (`import_export_dialog.py` + `import_export_manager.py`)

- Four formats: JSON (API-compatible), YAML, BIND zone files, djbdns/tinydns
- Single zone export or bulk ZIP export with progress tracking
- Import modes: Append, Merge, Replace (with destructive-action warning)
- Target zone auto-creation if zone doesn't exist
- Preview before import showing record count and sample data

#### Log Console (`log_widget.py`)

- Collapsible panel at the bottom of the main window
- Colour-coded severity: success (green), warning (orange), error (red), info (palette text)
- Timestamps in muted palette colour; 500-line rolling limit
- Message count label; Clear button

#### Configuration Dialog (`config_dialog.py`)

- Theme mode: Light / Dark / System Default with independent light and dark theme selectors
- API URL, token (masked with show toggle), sync interval (1–60 min), rate limit (0–10 req/sec)
- Debug mode toggle

## Data Flow

### Authentication
1. On startup, check profile config for API token
2. If missing, show `AuthDialog`
3. Token stored encrypted; decrypted only in memory when needed

### Sync Flow
1. Timer fires (or user triggers manual sync)
2. `LoadZonesWorker` fetches zones in background → updates cache + zone list
3. After sync: `_check_token_management_permission()` and `_fetch_account_limit()` run in parallel background workers
4. When zone selected: `LoadRecordsWorker` fetches records → updates table

### Record Mutation
1. User edits/creates/deletes via dialog or batch action
2. Optimistic UI update; API call made in background
3. Domain cache cleared; table refreshed from API

## Design Patterns

| Pattern | Where used |
|---------|-----------|
| **Model-View** | `ZoneListModel` / `QListView` for zone list |
| **Observer (signals/slots)** | All inter-component communication |
| **Proxy** | `CacheManager` transparent fallback chain |
| **Repository** | Centralised data access through cache/API |
| **Worker** | `QRunnable` + `QThreadPool` for all background I/O |

## Security

- API tokens encrypted (Fernet AES-128, PBKDF2, 100k iterations, user-derived salt)
- No plaintext credentials stored or logged
- Confirmation dialogs for all destructive actions (delete zone, delete record, bulk delete, replace-mode import)
- DNSSEC-related record types (`DNSKEY`, `DS`, `CDNSKEY`) carry in-UI warnings; `CDS` removed entirely as the API rejects writes

## Error Handling

1. `api_client._make_request` catches and categorises HTTP errors; returns `(success, data_or_message)` tuples
2. Dialogs show user-friendly messages; details logged to console and log widget
3. Bulk operations (import, bulk delete, search & replace) continue on per-record failures; summary logged on completion
4. Rate-limit errors (429) surfaced clearly; configurable throttle reduces occurrence
