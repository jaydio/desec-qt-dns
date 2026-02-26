# deSEC Qt DNS Manager -- UI Features Guide

## Main Interface

The application uses a FluentWindow with sidebar navigation. There is no menu bar. All navigation is through the sidebar.

### Sidebar Navigation

**Top items:**

| Item | Icon | Type |
|------|------|------|
| DNS | globe | Main page (zone list + records) |
| Search & Replace | search | Global search/replace across zones |
| Import | right_arrow | Import records from file |
| Export | left_arrow | Export records to file |
| Tokens | certificate | API token management |
| Queue | send_fill | Central API queue viewer |
| History | update | Git-based version history |
| Profile | people | Multi-profile management |
| Settings | setting | Application settings |

**Bottom items:**

| Item | Icon | Behaviour |
|------|------|-----------|
| About | info | Application info dialog |
| Log Console | history | In-window log viewer |
| Sync | sync | Non-selectable; triggers sync on click |
| Connection Status | wifi | Clickable toggle for online/offline mode |
| Last Sync | history | Non-selectable; displays last sync timestamp |

Sidebar expanded width: 180px.

---

## DNS Page

The main page. Two-pane QSplitter layout with a 25/75 split: zone list on the left, records on the right.

### Zone List (Left Pane)

- QAbstractListModel backed ListView with SearchLineEdit filter
- Header shows "N/limit zones" where the limit comes from `GET /auth/account/`
- Filtered display shows "Showing M of N/limit zones"
- Selecting a zone loads its records in the right pane

### AddZonePanel

Slide-in right panel (340px wide) for zone creation. Activated by clicking the Add Zone button. Replaces the old QInputDialog prompt.

### Records Table (Right Pane)

RecordWidget with a TableWidget. Columns: checkbox, Name, Type (colored by record type), TTL, Content, Actions.

- Sort by any column header; third click returns to default name-ascending order
- Real-time search/filter across all fields
- Double-click a row to open the edit panel
- Delete key on a selected row triggers deletion with DeleteConfirmDrawer

### RecordEditPanel

Slide-in right panel (440px wide) for adding and editing records.

- Record type selector (38+ types; CDS excluded as API-managed)
- Subname, TTL (preset options from 60s to 86400s), content area
- Format hint, example, and tooltip for each record type
- Real-time validation with colour-coded feedback via `_validate_record_content`
- DNSSEC types (DNSKEY, DS, CDNSKEY) show a prominent warning

### Batch Actions

- **Select All** -- checks every visible row
- **Select None** -- unchecks all rows
- **Delete Selected (N)** -- red button; shows count of checked rows, runs BulkDeleteWorker in background
- All batch controls disabled in offline mode or when no rows are loaded
- Deletion confirmation uses DeleteConfirmDrawer (top-sliding, two-step, red)

---

## Search & Replace Page

Accessible via the Search & Replace sidebar item.

### Layout

Splitter layout: left pane (filters + results table), right pane (replace options).

### Search Filters

| Field | Behaviour |
|-------|-----------|
| Subname contains | Case-insensitive substring (or regex) |
| Content contains | Case-insensitive substring (or regex) |
| Zone contains | Substring match against zone name (or regex) |
| Type | Exact match from dropdown |
| TTL equals | Exact integer match |
| Use regex | Toggles regex mode for subname, content, zone fields |

Click **Search All Zones** to search across every cached zone.

### Results Table

- Shows Zone, Subname, Type, TTL, Content for each match
- Per-row checkboxes; Select All / Select None; match count displayed
- Export Results to CSV or JSON

### Replace / Delete (Checked Rows)

| Action | Effect |
|--------|--------|
| Content find/replace | Find and replace within record content values |
| Subname rename | Rename subdomain (creates new RRset, deletes old) |
| TTL update | Change TTL value |
| Delete | Permanently removes checked RRsets |

- Replace confirmation uses ConfirmDrawer (blue-themed, two-step)
- Delete confirmation uses DeleteConfirmDrawer (red, two-step)

---

## Import Page

Accessible via the Import sidebar item.

### Layout

Left pane: file selection and preview. Right pane: target zone and import mode.

### Controls

- **Import File** -- browse to select file
- **Import Format** -- auto-detected or manually selected (JSON, YAML, BIND Zone File, djbdns/tinydns)
- **Target Zone** -- use name from file, select existing, or enter new (auto-created)
- **Existing Records Handling** -- Append, Merge, or Replace
- **Preview Import** -- validates file and shows record count + samples
- **Import Zone** -- runs import with progress tracking; shows success/failure counts

Import confirmation uses ConfirmDrawer (blue-themed, two-step).

---

## Export Page

Accessible via the Export sidebar item.

### Controls

- **Zone selection** -- checkbox list for multi-zone selection
- **Format** -- JSON, YAML, BIND Zone File, djbdns/tinydns
- **Include metadata** -- preserves timestamps and API fields
- **Output File** -- browse or auto-generate (timestamped filename)
- **Bulk ZIP export** -- exports selected zones as a ZIP archive

---

## Token Manager Page

Accessible via the Tokens sidebar item. Requires `perm_manage_tokens` on the active token.

### Layout

Splitter: token list on the left, details tabs on the right (Details + Policies).

### Token List

- Select a token to view/edit its details in the right panel tabs
- Delete removes the selected token (with DeleteConfirmDrawer confirmation)
- Refresh reloads the token list from the API

### Details Tab

- Read-only: ID (with Copy button), owner, created, last used, validity, MFA type
- Editable: name, permission flags (perm_create_domain, perm_delete_domain, perm_manage_tokens, auto_policy), max age, max unused period, allowed subnets

### Policies Tab

- Lists fine-grained RRset access rules: domain, subname, type, write flag
- Add Policy / Edit Policy / Delete Policy controls

### CreateTokenPanel

Slide-in right panel (460px wide) for creating new tokens.

- Name field
- Permission checkboxes with descriptions
- Expiration: Max Age and Max Unused Period (format: `DD HH:MM:SS`, blank = no limit)
- Allowed Subnets: one CIDR per line (default: `0.0.0.0/0` and `::/0`)

### TokenPolicyPanel

Slide-in right panel (400px wide) for adding or editing RRset policies.

### TokenSecretDialog

Modal dialog (security requirement). Displays the token secret once after creation. Must be copied before closing.

---

## Queue Page

Accessible via the Queue sidebar item.

### Layout

Splitter: pending queue on the left (columns: priority, action, status), completed history on the right.

### QueueDetailPanel

Slide-in right panel (480px wide) showing full request/response JSON for a selected queue item.

### Controls

- **Pause / Resume** -- pauses or resumes the central API queue
- **Cancel** -- cancels the selected pending item
- **Retry Failed** -- re-enqueues failed items
- **Clear History** -- removes completed items from the history table

### Priority Levels

| Level | Value | Usage |
|-------|-------|-------|
| PRIORITY_HIGH | 0 | Zone list loading, connectivity checks |
| PRIORITY_NORMAL | 1 | Interactive CRUD operations |
| PRIORITY_LOW | 2 | Background sync |

---

## History Page (Version History)

Accessible via the History sidebar item. Uses Git-based versioning at `~/.config/desecqt/versions/`.

### Layout

Zone list on the left, commit timeline on the right.

### Features

- Snapshots taken automatically on record mutations (add, edit, delete)
- Timeline shows commit history per zone via `git log`
- Record preview for selected version via `git show`
- Restore button opens RestoreConfirmDrawer (amber-themed, two-step) before reverting to a previous version

---

## Profile Page

Accessible via the Profile sidebar item. See [PROFILES.md](./PROFILES.md) for full documentation.

### Layout

Profile list on the left, profile info and controls on the right.

### ProfileFormPanel

Slide-in right panel (400px wide) for creating or renaming profiles.

### Confirmations

- Switch profile uses ConfirmDrawer (blue-themed, two-step)
- Delete profile uses DeleteConfirmDrawer (red, two-step)

Each profile has isolated: API token, cache, configuration, and UI state. Switching profiles restarts the application for complete isolation.

---

## Settings Page

Accessible via the Settings sidebar item.

ScrollArea with SettingCard groups arranged in two columns.

### Left Column

| Group | Settings |
|-------|----------|
| Connection | API URL, token entry button |
| Sync | Sync interval (1--60 min, default 10), API rate limit (0--10 req/sec, default 2.0) |

### Right Column

| Group | Settings |
|-------|----------|
| Appearance | Theme mode (Light / Dark / System Default) |
| Queue | Persist queue across sessions, retention period |
| Advanced | Debug mode (verbose logging), token manager shortcut |

---

## Drawer Patterns

All confirmations and notifications use top-sliding drawers instead of QMessageBox or QDialog popups.

### DeleteConfirmDrawer

- Red themed
- Two-step confirmation: first click changes button text, second click executes
- Used for all destructive actions (delete zone, delete record, delete token, delete profile, bulk delete)

### RestoreConfirmDrawer

- Amber themed
- Two-step confirmation
- Used for restore and overwrite actions (version restore)

### ConfirmDrawer

- Blue themed
- Two-step confirmation
- Used for general confirmations (quit application, switch profile, import records, apply replacements)

### NotifyDrawer

- Supports info, warning, error, and success variants
- Used for non-blocking notifications

---

## Log Console

- Accessible via the Log Console sidebar item
- Colour-coded messages: green (success), orange (warning), red (error), default text (info)
- Timestamps in muted colour; 500-line rolling limit
- Message count displayed next to heading
- Clear button resets the log

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `F5` | Sync now (refresh all data) |
| `Ctrl+F` | Cycle search fields (zone search / record search) |
| `Ctrl+Q` | Quit application (with ConfirmDrawer) |
| `Delete` | Delete selected zone or record |
| `Escape` | Clear search filter / close open drawer |

---

## Offline Mode

Toggle via the Connection Status sidebar item (click to toggle).

When offline:

- API queue is paused, sync timers are stopped
- Zone and record data served from cache only
- All editing and write operations are disabled
- Batch controls (Select All, Select None, Delete Selected) are disabled
- Zone count shown without limit suffix until connectivity is restored

---

## Performance Features

- Central API queue (APIQueue QThread) processes all API calls sequentially with rate limiting
- QAbstractListModel + virtual scrolling for the zone list
- Three-layer cache (memory, pickle, JSON) with O(1) indexed lookups
- Incremental search filtering without full list rebuild
- Configurable API rate limiter prevents 429 errors during bulk operations
- Callback dispatch via signal ensures all UI updates happen on the main thread
