# deSEC Qt DNS Manager - Logging and Notifications

This document describes the logging and notification system implemented in the deSEC Qt DNS Manager application, including examples of different log message types and their formats.

## Overview

The application uses a multi-layered logging system that combines:

1. Console logging (via Python's `logging` module)
2. UI-based log display (via the Log Console widget)
3. Visual notifications for important events

Logs are categorized by severity (info, success, warning, error) and include timestamps for easy tracking of application events.

## Log Message Formatting

### General Structure

Log messages follow a consistent format:

```
[TIMESTAMP] - MODULE - LEVEL: MESSAGE
```

Example:
```
2025-06-07 03:20:49,343 - config_manager - INFO - Configuration loaded successfully
```

### Contextual Information

Record operation logs include rich contextual information:

- Record type (A, AAAA, MX, TXT, etc.)
- Domain and subdomain information
- Full record content
- For updates: both old and new values

## Log Message Types

### Record Operations

#### Record Creation

When a new DNS record is created:

```
Successfully created A record for 'www' in domain 'example.com' with content: 192.0.2.1
```

#### Record Update

When an existing DNS record is modified:

```
Successfully updated MX record for 'mail' in domain 'example.com' - changed content from '10 mail.example.com.' to '20 backup-mail.example.com.'
```

#### Record Deletion

When a DNS record is deleted:

```
Deleting TXT record for 'www' with content: "v=spf1 -all"
Successfully deleted TXT record for 'www'
```

### Zone Operations

#### Zone Creation

```
Adding zone example.com...
SUCCESS: Zone example.com added successfully
```

#### Zone Deletion

```
Deleting zone example.com...
SUCCESS: Zone example.com deleted successfully
```

### Synchronization Events

```
Syncing data...
Cached 5 zones
SUCCESS: Data synchronized successfully
```

### Error Messages

Error messages include both user-friendly descriptions and technical details:

```
API Error: Error 400: Another RRset with the same subdomain and type exists for this domain. (Try modifying it.)
Details: {'non_field_errors': ['Another RRset with the same subdomain and type exists for this domain. (Try modifying it.)']}
```

## Visual Indicators

The Log Console displays messages with color-coding:
- **Green**: Success messages
- **Blue**: Informational messages
- **Orange**: Warnings
- **Red**: Errors

## Implementation

### Logging Components

1. **Python Logger**: Foundation for console logging
2. **Signal/Slot Mechanism**: Used for emitting log messages from components
3. **LogWidget Class**: Displays and formats log messages in the UI
4. **Message Signal**: `log_message` and `log_signal` used to transmit log data

### Code Example

```python
# Emitting a log message from a component
self.log_message.emit(f"Successfully created {record_type} record for '{subname}' with content: {content_summary}", "success")

# Handling in the main window
def log_message_handler(self, message, level="info"):
    """Handle log messages from components and update the log widget."""
    getattr(logger, level)(message)  # Log to console
    self.log_widget.add_log_entry(message, level)  # Update UI
```

## Best Practices

1. **Meaningful Context**: Always include relevant entity names and identifiers
2. **Before/After State**: For updates, show both old and new values
3. **Clear Outcomes**: Explicitly state if an operation succeeded or failed
4. **Avoid Sensitive Data**: Never log authentication tokens or passwords
5. **Consistent Format**: Follow established message patterns

## Error Handling Integration

The logging system is tightly integrated with error handling:

1. API request errors are parsed for meaningful messages
2. UI components display appropriate error notifications
3. Detailed technical information is available for debugging
4. Common error conditions (like duplicate records) have specialized handling

By providing detailed, context-rich log messages, the application maintains transparency about all operations and helps users understand what actions have been performed on their DNS records.
