# deSEC Qt DNS Manager — Logging and Notifications

## Overview

The application uses three complementary notification layers:

1. **InfoBar toasts** — auto-dismissing colour-coded banners at the top-centre of the main window; cover all API operations and user-facing errors
2. **Log Console widget** — sidebar page with persistent colour-coded, timestamped entries
3. **Python `logging` module** — writes structured records to `~/.config/desecqt/logs/` and the console (debug mode)

---

## InfoBar Toasts

InfoBar toasts appear at the top-centre of the main window regardless of which page is active. They auto-dismiss after a type-dependent duration and require no user interaction.

| Variant | Colour | Duration | Typical trigger |
|---------|--------|----------|-----------------|
| `success` | Green | 4 s | Record saved, zone added, token created |
| `info` | Blue | 3 s | Neutral status or advisory |
| `warning` | Amber | 5 s | Offline guard, rate-limit advisory |
| `error` | Red | 8 s | API error, validation failure, network error |

### Implementation

```python
from qfluentwidgets import InfoBar, InfoBarPosition

InfoBar.error(
    title="Record Save Failed",
    content=detail,
    parent=self.window(),     # always self.window() for top-centre positioning
    duration=8000,
    position=InfoBarPosition.TOP,
)
```

All InfoBar calls use `parent=self.window()` to anchor to the top-level `FluentWindow`, ensuring consistent positioning across all nested sub-widgets and sidebar pages.

---

## Log Console

The log console is accessible via the **Log Console** item in the sidebar (bottom section).

### Severity Colours

| Level | Colour | When used |
|-------|--------|-----------|
| `success` | Green (`#4caf50`) | Operation completed successfully |
| `warning` | Orange (`#ffa726`) | Non-fatal issue or advisory |
| `error` | Red (`#ef5350`) | Operation failed |
| `info` | Palette text (adapts to theme) | General status messages |

Timestamps are shown in a muted palette colour so they don't compete with the message text.

### Limits

- Rolling 500-line limit (oldest entries discarded automatically)
- **Clear** button resets the log; entry count shown in the header

---

## Log Message Examples

### Record Operations

```
Successfully created A record for 'www' in domain 'example.com' with content: 192.0.2.1
Successfully updated MX record for '@' in domain 'example.com' — changed content from '10 mail.example.com.' to '20 backup.example.com.'
Deleting TXT record for 'www' with content: "v=spf1 -all"
Successfully deleted TXT record for 'www'
```

### Bulk Delete (batch actions)

```
Deleted: www A
Deleted: mail MX
Failed to delete: _dmarc TXT
Bulk delete: 2 deleted, 1 failed.
```

### Global Search & Replace

```
[test123.com] @ MX — content replaced
Replace complete: 1 replaced, 0 failed.
```

### Zone Operations

```
Adding zone example.com...
Zone example.com added successfully
Deleting zone example.com...
Zone example.com deleted successfully
```

### Sync and Connectivity

```
Retrieved 5 zones from API
Last sync: 35 sec ago
```

### Import/Export

```
Exported example.com to /home/user/example-com.json
Import complete: 12 records created, 0 failed
```

### Token Management

```
Token 'ci-deploy' created successfully
Token 'old-token' deleted
Policy saved for test123.com
```

### Error Messages

```
API Error 400: Another RRset with the same subdomain and type exists for this domain.
API Error 429: Rate limit exceeded — reduce API Rate Limit in Settings
API Error 403: Insufficient permissions (perm_manage_tokens required)
```

---

## File Logging

Python log records are written to:

```
~/.config/desecqt/logs/desec_qt.log
```

Format:
```
2026-02-23 06:05:19,343 - api_client - INFO - GET /domains/ → 200 (0.31 s)
2026-02-23 06:05:19,421 - cache_manager - DEBUG - Cached 5 zones (L1 + L2 + L3)
```

Enable **debug mode** (Settings sidebar page → Debug Mode toggle) to include `DEBUG`-level entries.

---

## Implementation Details

### Log Signal/Slot Chain

```
component.log_signal.emit(message, level)
    → MainWindow.log_message_handler(message, level)
        → LogWidget.add_message(message, level)
```

Workers (bulk delete, search & replace, import) emit `log_signal` signals directly; the main window routes them to the log widget.

### LogWidget API

```python
log_widget.add_message(message, level='info')  # Append a new entry
log_widget.clear_log()                          # Clear all entries
```

### Best Practices

- Always include entity names (zone, subdomain, record type) in log messages
- Show old → new values for update operations
- Log both per-item results and an overall summary for batch operations
- Never log API tokens, passwords, or other credentials
