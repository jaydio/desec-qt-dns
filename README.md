# deSEC Qt DNS Manager

![deSEC DNS Manager - Main Window](img/main_window.png)

📸 **[View all screenshots →](img/README.md)**

A Qt6 desktop application for managing DNS zones and records via the [deSEC](https://desec.io) DNS API.

---

## ✨ Features

### DNS Management
- **Zone management** — create and delete DNS zones; zone list shows `Total zones: N/limit` using your account's domain quota fetched live from the API
- **Record management** — full CRUD for 37 DNS record types with format hints, examples, and inline validation
- **Batch actions** — select multiple records with checkboxes, then bulk-delete with one click; Select All / Select None shortcuts
- **Multiline records** — enter multiple values per RRset (one per line); toggle full display via View menu

### Search & Organisation
- **Global Search & Replace** — search records across all zones by subname, type, content, TTL, or zone name (plain text or regex); bulk-replace content, rename subnames, update TTLs, delete records, or export results — with a full change log
- **Record filtering** — real-time search within a zone across all fields
- **Sortable table** — click any column header to sort; third click returns to default

### Token Management
- **Full token lifecycle** — create, view, edit, and delete API tokens
- **Per-token permissions** — `perm_create_domain`, `perm_delete_domain`, `perm_manage_tokens`, `auto_policy`
- **RRset policies** — fine-grained per-domain/subname/type write access rules
- **Expiration controls** — max age and max unused period
- **Subnet restrictions** — limit token use to specific CIDR ranges
- Accessible via **File → Manage Tokens** (enabled only when the active token has `perm_manage_tokens`)

### Import / Export
- **Formats** — JSON (API-compatible), YAML (Infrastructure-as-Code), BIND zone files, djbdns/tinydns
- **Bulk export** — export multiple zones to a single ZIP archive
- **Import modes** — Append, Merge, or Replace with preview before commit
- **Progress tracking** — real-time progress bar and per-record status

### Multi-Profile Support
- Each profile has isolated API token, cache, and settings
- Create, rename, switch, and delete profiles via **Profile → Manage Profiles…**
- Application restarts on profile switch for complete isolation

### Themes & UI
- Light, Dark, and System Default theme modes with independent light/dark theme selectors
- Collapsible log console with colour-coded severity (green / orange / red / palette text)
- Status bar showing last sync time and ONLINE / OFFLINE state

### Performance & Reliability
- Three-layer cache (memory → pickle → JSON) with O(1) indexed lookups
- All API I/O in background threads — UI never blocks
- Configurable API rate limit (0–10 req/sec) to avoid 429 errors during bulk operations
- Authentication failures (HTTP 401) surfaced immediately with a dialog prompt

---

## DNSSEC Record Types

deSEC auto-manages DNSSEC records server-side:

| Type | API behaviour |
|------|--------------|
| `CDS` | Fully managed — API returns 403 on any write; not shown in type list |
| `RRSIG`, `NSEC3PARAM` | Fully managed — not exposed in the UI |
| `DNSKEY`, `DS`, `CDNSKEY` | Auto-managed but the API allows adding extra values for advanced **multi-signer DNSSEC** setups. Use with caution — misuse can break DNSSEC. The app shows a warning tooltip on these types. |

---

## Supported Record Types (37)

`A` `AAAA` `AFSDB` `APL` `CAA` `CDNSKEY` `CERT` `CNAME` `DHCID` `DNAME` `DNSKEY` `DLV` `DS` `EUI48` `EUI64` `HINFO` `HTTPS` `KX` `L32` `L64` `LOC` `LP` `MX` `NAPTR` `NID` `NS` `OPENPGPKEY` `PTR` `RP` `SMIMEA` `SPF` `SRV` `SSHFP` `SVCB` `TLSA` `TXT` `URI`

---

## TTL Limits

The deSEC API enforces a TTL range of **3600–86400 seconds** (1–24 hours) for standard accounts. Contact [support@desec.io](mailto:support@desec.io) for account-specific adjustments.

---

## Setup

### 1. Create and activate a virtual environment

```bash
python -m venv venv

# Linux / macOS
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run

```bash
python src/main.py
```

### 4. Enter your deSEC API token when prompted

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `F5` | Sync now |
| `Delete` | Delete selected record (with confirmation) |
| `Ctrl+F` | Focus zone / record search field |
| `Escape` | Clear search filter |
| `Ctrl+Q` | Quit |

---

## Configuration

Settings are stored per-profile at:

```
~/.config/desecqt/profiles/<profile_name>/config.json
```

Key settings (all editable via **File → Settings**):

| Setting | Default | Description |
|---------|---------|-------------|
| API URL | `https://desec.io/api/v1` | deSEC endpoint |
| API Token | — | Fernet-encrypted |
| Sync Interval | 10 min | Zone list refresh rate |
| API Rate Limit | 2.0 req/sec | Throttle for bulk ops |
| Theme Mode | System | Light / Dark / System Default |
| Debug Mode | off | Verbose console logging |

---

## Documentation

| Document | Description |
|----------|-------------|
| [doc/ARCHITECTURE.md](doc/ARCHITECTURE.md) | Module structure, data flow, design patterns |
| [doc/UI-FEATURES.md](doc/UI-FEATURES.md) | Complete UI reference — all dialogs and controls |
| [doc/RECORD-MANAGEMENT.md](doc/RECORD-MANAGEMENT.md) | Record types, TTL, batch actions, troubleshooting |
| [doc/CONFIG.md](doc/CONFIG.md) | All configuration keys and cache locations |
| [doc/CACHING.md](doc/CACHING.md) | Three-layer cache implementation |
| [doc/PROFILES.md](doc/PROFILES.md) | Multi-profile setup and usage |
| [doc/IMPORT_EXPORT.md](doc/IMPORT_EXPORT.md) | Import/Export formats, modes, and workflows |
| [doc/LOGS-AND-NOTIFICATIONS.md](doc/LOGS-AND-NOTIFICATIONS.md) | Log console, severity levels, file logging |
| [doc/RELEASE-PROCESS.md](doc/RELEASE-PROCESS.md) | Release checklist and versioning guide |
| [CHANGELOG.md](CHANGELOG.md) | Full version history |
| [ROADMAP.md](ROADMAP.md) | Planned features |

---

## License

GPL v3 — see [LICENSE](LICENSE) for details.
