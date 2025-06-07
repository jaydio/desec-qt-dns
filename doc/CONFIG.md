# deSEC Qt DNS Manager Configuration

## Configuration File Location

The deSEC Qt DNS Manager stores its configuration in the following location:

```bash
~/.config/desecqt/config.json
```

This file is automatically created when you first run the application and enter your API token. The configuration can be edited through the application's built-in configuration editor or manually (though manual editing is not recommended).

## Currently Implemented Configuration Options

Below is a list of all currently implemented configuration options:

### Core Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `api_url` | String | `https://desec.io/api/v1` | The URL of the deSEC API endpoint |
| `auth_token` | String | (empty) | Your deSEC API authentication token |
| `sync_interval_minutes` | Integer | `10` | How often to sync with the deSEC API (in minutes) |
| `debug_mode` | Boolean | `false` | Whether to enable debug mode with additional logging |

## Cache Information

The application uses file-based caching with the following characteristics:

* Cache directory: `~/.config/desecqt/cache`
* Cache is enabled by default
* Cache staleness is determined by the sync interval
* Zone data is cached in `~/.config/desecqt/cache/zones.json` and in faster binary format as `zones.pkl`
* Record data is cached in domain-specific files like `~/.config/desecqt/cache/records_example_com.json` and in faster binary format
* O(1) in-memory indexing for both zones and records provides lightning-fast access

## Sample Configuration

Here's a complete sample configuration file with all currently implemented options:

```json
{
  "api_url": "https://desec.io/api/v1",
  "encrypted_auth_token": "gAAAAABl...",
  "sync_interval_minutes": 10,
  "debug_mode": false
}
```

Note: The actual auth token is stored in encrypted form in the configuration file.

## Configuration Status Overview

This section provides clarity on which configuration options are currently implemented and which are planned for future versions.

### Currently Implemented

* Core settings (`api_url`, `auth_token`, `sync_interval_minutes`, `debug_mode`)
* Log console visibility (`show_log_console`)
* Keepalive interval (`keepalive_interval`)
* Offline mode (`offline_mode`)
* Multiline records display (`show_multiline_records`)
* API throttling (`api_throttle_seconds`)

### Planned Future Configuration Options

The following configuration options are planned for future versions of the application:

### UI Settings (Planned)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `ui.auto_expand_zones` | Boolean | `true` | Whether to automatically expand zone nodes when selected |
| `ui.confirm_deletions` | Boolean | `true` | Whether to show confirmation dialogs before deletions |
| `ui.theme` | String | `system` | UI theme (`system`, `light`, or `dark`) |
| `ui.window_width` | Integer | `1024` | Initial window width in pixels |
| `ui.window_height` | Integer | `768` | Initial window height in pixels |

### Cache Settings (Planned)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `cache_enabled` | Boolean | `true` | Whether to enable local caching of DNS data |
| `cache_ttl` | Integer | `3600` | How long to keep cached data (in seconds) before refreshing |

### Logging Settings (Planned)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `logging.level` | String | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `logging.log_to_file` | Boolean | `true` | Whether to save logs to a file |
| `logging.log_file` | String | `~/.config/desecqt/desec_qt.log` | Path to log file |

## Resetting Configuration

If you need to reset your configuration to defaults, you can:

1. Close the application
2. Delete the `~/.config/desecqt/config.json` file
3. Restart the application

The application will prompt you for a new API token and recreate the configuration file with default settings.

## Extending the Configuration

If you want to contribute by implementing additional configuration options, please refer to `src/config_manager.py` and `src/config_dialog.py` to add new settings.
