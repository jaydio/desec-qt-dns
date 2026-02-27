# deSEC Qt DNS Manager — Configuration

## Configuration File Location

Each profile stores its own configuration at:

```
~/.config/desecqt/profiles/<profile_name>/config.json
```

The legacy single-profile location (`~/.config/desecqt/config.json`) is migrated automatically to the default profile on first launch.

---

## Configuration Options

All settings are managed through the **Settings** sidebar page or by editing the JSON file directly (not recommended).

### API Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `api_url` | string | `https://desec.io/api/v1` | deSEC API endpoint |
| `encrypted_auth_token` | string | *(empty)* | Fernet-encrypted API token |
| `sync_interval_minutes` | integer | `15` | Minutes between automatic zone list syncs |
| `api_rate_limit` | float | `1.0` | Maximum API requests per second (0 = no limit). Lower values reduce 429 errors during bulk operations. |
| `debug_mode` | boolean | `false` | Verbose logging to the Python console |

### Theme Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `theme_type` | string | `auto` | `light`, `dark`, or `auto` (follows OS setting) |

Theme is managed by PySide6-FluentWidgets via `setTheme()`. No per-theme ID selectors are needed.

### UI State

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `show_log_console` | boolean | `true` | Whether the log console is visible |
| `show_multiline_records` | boolean | `true` | Show all lines for multi-value RRsets in the table |
| `offline_mode` | boolean | `false` | Operate from cache only, skip API calls |

### Queue Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `queue_history_persist` | boolean | `true` | Save completed/failed queue items to disk |
| `queue_history_limit` | integer | `5000` | Maximum queue history entries retained |

### Internal / Advanced

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `keepalive_interval` | integer | `60` | Seconds between connectivity checks |

---

## Sample Configuration File

```json
{
  "api_url": "https://desec.io/api/v1",
  "encrypted_auth_token": "gAAAAABl...",
  "sync_interval_minutes": 15,
  "api_rate_limit": 1.0,
  "debug_mode": false,
  "theme_type": "auto",
  "show_log_console": true,
  "show_multiline_records": true,
  "offline_mode": false,
  "queue_history_persist": true,
  "queue_history_limit": 5000
}
```

---

## Data Locations

All application data is stored per-profile under `~/.config/desecqt/`:

```
~/.config/desecqt/
├── profiles.json                           # Profile metadata
├── queue_history.json                      # API queue history (optional)
├── versions/                               # Git repo for zone versioning
│   └── zones/
│       ├── example.com.json
│       └── other.example.com.json
├── logs/
│   └── desecqt.log
└── profiles/
    └── <profile_name>/
        ├── config.json                     # Profile configuration
        ├── salt                            # Fernet encryption salt
        └── cache/
            ├── zones.json                  # Cached zone list
            ├── records_example_com.json    # Per-domain record cache
            ├── tokens.json                 # Cached token list
            └── token_policies_*.json       # Per-token policy cache
```

Cache is invalidated:
- **Time-based**: zone list every `sync_interval_minutes`; records after 5 minutes of staleness
- **Event-based**: domain cache cleared immediately after any record add/edit/delete

---

## Resetting Configuration

To reset to defaults:

1. Close the application
2. Delete `~/.config/desecqt/profiles/<profile_name>/config.json`
3. Restart — the app will prompt for a new API token

To clear all profiles and start fresh:

```bash
rm -rf ~/.config/desecqt/
```

---

## Extending the Configuration

To add a new setting:
1. Add a getter/setter in `src/config_manager.py`
2. Add a UI control in `src/settings_interface.py`
3. Read the setting where needed in the application
