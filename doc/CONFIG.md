# deSEC Qt DNS Manager — Configuration

## Configuration File Location

Each profile stores its own configuration at:

```
~/.config/desecqt/profiles/<profile_name>/config.json
```

The legacy single-profile location (`~/.config/desecqt/config.json`) is migrated automatically to the default profile on first launch.

---

## Configuration Options

All settings are managed through **File → Settings** or by editing the JSON file directly (not recommended).

### API Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `api_url` | string | `https://desec.io/api/v1` | deSEC API endpoint |
| `encrypted_auth_token` | string | *(empty)* | Fernet-encrypted API token |
| `sync_interval_minutes` | integer | `10` | Minutes between automatic zone list syncs |
| `api_rate_limit` | float | `2.0` | Maximum API requests per second (0 = no limit). Lower values reduce 429 errors during bulk operations. |
| `debug_mode` | boolean | `false` | Verbose logging to the Python console |

### Theme Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `theme_type` | string | `system` | `light`, `dark`, or `system` |
| `theme_id` | string | `light_plus` | Active theme ID (set automatically from light/dark selection) |
| `light_theme_id` | string | `light_plus` | Preferred light theme (`light_plus`, `quiet_light`) |
| `dark_theme_id` | string | `dark_plus` | Preferred dark theme (`dark_plus`, `github_dark`, `quiet_dark`) |

### UI State

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `show_log_console` | boolean | `true` | Whether the log console is visible |
| `show_multiline_records` | boolean | `false` | Show all lines for multi-value RRsets in the table |
| `offline_mode` | boolean | `false` | Operate from cache only, skip API calls |

### Internal / Advanced

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `keepalive_interval` | integer | `60` | Seconds between connectivity pings |
| `api_throttle_seconds` | float | `0.5` | Minimum delay between API requests in bulk ops (derived from `api_rate_limit`) |

---

## Sample Configuration File

```json
{
  "api_url": "https://desec.io/api/v1",
  "encrypted_auth_token": "gAAAAABl...",
  "sync_interval_minutes": 10,
  "api_rate_limit": 2.0,
  "debug_mode": false,
  "theme_type": "dark",
  "light_theme_id": "light_plus",
  "dark_theme_id": "github_dark",
  "theme_id": "github_dark",
  "show_log_console": true,
  "show_multiline_records": false,
  "offline_mode": false
}
```

---

## Cache Location

Cache files are stored per-profile:

```
~/.config/desecqt/profiles/<profile_name>/cache/
├── zones.json              # JSON cache of all zones
├── zones.pkl               # Binary (pickle) cache of all zones
├── records_example_com.json
└── records_example_com.pkl
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
2. Add a UI control in `src/config_dialog.py`
3. Read the setting where needed in the application
