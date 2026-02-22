# deSEC Qt DNS Manager — UI Features Guide

## Main Interface

The application uses a two-pane layout:

| Area | Purpose |
|------|---------|
| Left pane | DNS zone list with search, account limit display, and zone controls |
| Right pane | DNS records table for the selected zone |
| Bottom | Collapsible log console |
| Status bar | Last sync time and ONLINE / OFFLINE indicator |

### Menu Bar

| Menu | Items |
|------|-------|
| **File** | Settings, Clear Cache, —, Import/Export, Global Search & Replace, —, Manage Tokens, —, Quit |
| **Profile** | Current profile name, Manage Profiles… |
| **Connection** | Sync Now, Check Connectivity, Offline Mode toggle |
| **View** | Show Log Console, Show Multiline Records |
| **Help** | About |

---

## Zone Management

### Zone List

- Lists all zones sorted alphabetically
- Header shows **"Total zones: N/limit"** where the limit is fetched live from `GET /auth/account/` — updates to `"Total zones: N"` gracefully when offline
- Real-time search filter (updates as you type); filtered display shows `"Showing M of N/limit zones"`
- Selecting a zone immediately loads its records in the right pane

### Zone Controls

- **Add Zone** — prompts for domain name, creates via API
- **Delete Zone** — confirmation required; removes zone and all its records
- **Validate DNSSEC** — checks DNSSEC chain of trust for the selected zone

---

## Record Management

### Records Table

Columns: ☐ | Name ↑ | Type ↕ | TTL ↕ | Content ↕ | Actions

- **Checkbox column** — native centred checkbox per row for batch selection; selected rows are highlighted with a palette-blended tint
- **Sort** by any column (click header); third click returns to default name-ascending order
- **Search / filter** across all fields (name, type, TTL, content) in real time
- **Double-click** a row to open the Edit Record dialog
- **Delete key** on a selected row triggers single-record deletion with confirmation

### Adding and Editing Records

1. Click **Add Record** or double-click / click **Edit** on an existing row
2. The Record dialog opens (minimum 560 × 640 px):
   - Record type selector (37 types; CDS excluded — API-managed)
   - Subname, TTL (preset options from 60 s to 86400 s), content area
   - Format hint, example, and tooltip for each record type
   - Real-time validation with colour-coded feedback
   - DNSSEC types (DNSKEY, DS, CDNSKEY) show a prominent warning

### Batch Actions

- **Select All** — checks every visible row
- **Select None** — unchecks all rows
- **Delete Selected (N)** — red button; shows count of checked rows, asks for confirmation, then runs `_BulkDeleteWorker` in background
- All batch controls disabled in offline mode or when no rows are loaded

---

## Global Search & Replace

Accessible via **File → Global Search & Replace**.

### Search

| Field | Behaviour |
|-------|-----------|
| Subname contains | Case-insensitive substring (or regex) |
| Content contains | Case-insensitive substring (or regex) |
| Zone contains | Substring match against zone name (or regex) |
| Type | Exact match from dropdown |
| TTL equals | Exact integer match |
| Use regex | Toggles regex mode for subname, content, zone fields; **(?)** icon opens help popover |

Click **Search All Zones** — searches across every cached zone.

### Results Table

- Shows Zone, Subname, Type, TTL, Content for each match
- Per-row checkboxes; **Select All** / **Select None**; match count shown in green
- **Export Results** — saves the table to a file

### Replace / Delete (applies to checked rows)

| Field | Effect |
|-------|--------|
| Content → | Find & replace within record content values |
| Subname | Rename subdomain (creates new RRset, deletes old) |
| TTL | Change TTL value |
| **Apply to Selected** | Applies all non-empty replacement fields |
| **Delete Selected** | Permanently removes checked RRsets |

### Change Log

Shown after each apply operation. Lists old → new values for every modified record. **Clear Log** resets it.

---

## Token Management

Accessible via **File → Manage Tokens** (requires `perm_manage_tokens` on the active token; the menu item is disabled otherwise — checked in background after every sync).

### Token List

Columns: Name | Created | Last Used | Valid | Perms

- Select a token to view/edit its details in the right panel
- **New Token** — opens Create New Token dialog
- **Delete** — removes the selected token (with confirmation)
- **Refresh** — reloads token list from API

### Token Details (right panel)

**Details tab**
- Read-only: ID (with Copy button), owner, created, last used, validity, MFA type
- Editable: name, permission flags (perm_create_domain, perm_delete_domain, perm_manage_tokens, auto_policy), max age, max unused period, allowed subnets

**RRset Policies tab**
- Lists fine-grained access rules: domain, subname, type, write flag
- **Add Policy** / **Edit Policy** / **Delete Policy** buttons

### Create New Token

- Name field
- Permission checkboxes with descriptions
- Expiration: Max Age and Max Unused Period (format: `DD HH:MM:SS`, blank = no limit)
- Allowed Subnets: one CIDR per line (default: `0.0.0.0/0` and `::/0`)
- Token secret shown once after creation — must be copied before closing

---

## Import/Export

Accessible via **File → Import/Export**. Opens at 600 × 740 px.

### Export Tab

- **Zone to Export** — dropdown of all available zones
- **Enable Bulk Export** — switches to multi-zone mode with checkbox list + ZIP output
- **Format** — JSON, YAML, BIND Zone File, djbdns/tinydns
- **Include metadata** — preserves timestamps and API fields
- **Output File** — Browse or Auto-Generate (timestamped filename)
- **Export Zone** / **Export Selected Zones (ZIP)**

### Import Tab

- **Import File** — Browse to select file
- **Import Format** — auto-detected or manually selected
- **Target Zone** — use name from file, select existing, or enter new (auto-created)
- **Existing Records Handling**: Append | Merge | Replace
- **Preview Import** — validates file and shows record count + samples
- **Import Zone** — runs import with progress bar; shows success/failure counts

---

## Configuration

Accessible via **File → Settings**. Controls:

| Setting | Description |
|---------|-------------|
| Theme Mode | Light / Dark / System Default |
| Light Theme | Per-theme selector (Light+, Quiet Light, …) |
| Dark Theme | Per-theme selector (Dark+, GitHub Dark, …) |
| API URL | deSEC API endpoint |
| API Token | Masked; show/hide toggle |
| Sync Interval | 1–60 minutes (default 10) |
| API Rate Limit | 0–10 req/sec (default 2.0) |
| Enable debug mode | Verbose logging to console |

---

## Multi-Profile Support

Accessible via **Profile → Manage Profiles…**. See [PROFILES.md](./PROFILES.md) for full documentation.

Each profile has isolated: API token, cache, configuration, and UI state. Switching profiles restarts the application for complete isolation.

---

## Log Console

- Toggleable via **View → Show Log Console**
- Colour-coded messages: **green** (success), **orange** (warning), **red** (error), **default text** (info)
- Timestamps in muted colour; 500-line rolling limit
- Message count displayed next to "Log Console" heading
- **Clear** button resets the log

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `F5` | Sync now (refresh all data) |
| `Delete` | Delete selected record (with confirmation) |
| `Ctrl+F` | Focus zone search field |
| `Escape` | Clear current search filter |
| `Ctrl+Q` | Quit application |

---

## Offline Mode

When offline (or via **Connection → Offline Mode**):

- Zone and record data served from cache
- All write operations (add, edit, delete, import, search & replace, bulk delete) are disabled
- Status bar shows **OFFLINE** in orange/red
- Batch controls (Select All, Select None, Delete Selected) also disabled
- Zone count shown without limit suffix until connectivity is restored

---

## Performance Features

- Background `QRunnable` workers for all API I/O — UI never blocks
- `QAbstractListModel` + virtual scrolling for the zone list
- Three-layer cache (memory → pickle → JSON) with O(1) indexed lookups
- Incremental search filtering without full list rebuild
- Configurable API rate limiter prevents 429 errors during bulk operations
