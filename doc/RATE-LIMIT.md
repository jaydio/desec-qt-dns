# API Rate Limiting

This document explains the API rate limiting functionality in the deSEC Qt DNS Manager, which prevents API timeouts and ensures reliable operation during bulk operations.

## Overview

The deSEC Qt DNS Manager implements intelligent API rate limiting to:
- **Prevent API timeouts** during bulk import/export operations
- **Respect deSEC API limits** to avoid throttling and errors
- **Provide configurable control** for different use cases and connection speeds
- **Ensure reliable operation** across all application components

## How It Works

### Rate Limiting Architecture

All API requests in the application go through a centralized rate limiting system:

```
Any Component → APIClient.method() → _make_request() → _apply_rate_limit() → HTTP Request
```

The rate limiting is implemented at the lowest level (`_make_request()`) ensuring that **every single API call** is automatically rate-limited, including:
- Manual user actions (create/edit/delete records)
- Bulk import operations (hundreds of records)
- Background synchronization (periodic updates)
- Zone management operations
- Authentication and connectivity checks

### Rate Limiting Algorithm

The system uses a token bucket-style algorithm:

1. **Calculate minimum interval** between requests based on configured rate
2. **Track last request time** with thread-safe locking
3. **Wait if necessary** to maintain the configured rate limit
4. **Update timestamp** after each request

```python
# Example: 2.0 req/sec = 0.5 second minimum interval
min_interval = 1.0 / rate_limit

# Wait if we're going too fast
if time_since_last < min_interval:
    sleep_time = min_interval - time_since_last
    time.sleep(sleep_time)
```

## Configuration

### Accessing Rate Limit Settings

1. **Open Configuration Dialog**: `File → Configuration...`
2. **Locate API Rate Limit**: Find the "API Rate Limit" field
3. **Adjust Value**: Use the spinner or type directly
4. **Apply Changes**: Click "OK" to save

### Rate Limit Options

| Setting | Behavior | Use Case |
|---------|----------|----------|
| **0.5 req/sec** | Very conservative, 2-second delays | Large bulk imports, slow connections |
| **1.0 req/sec** | Conservative, 1-second delays | Standard bulk imports |
| **2.0 req/sec** | **Default**, 0.5-second delays | Balanced performance and reliability |
| **5.0 req/sec** | Aggressive, 0.2-second delays | Small imports, fast connections |
| **10.0 req/sec** | Maximum, 0.1-second delays | Testing, very fast connections |
| **0 (No limit)** | Unlimited, no delays | Local development, testing only |

### Recommended Settings

#### For Different Operations

- **Large Bulk Imports (>100 records)**: 0.5-1.0 req/sec
- **Standard Operations**: 2.0 req/sec (default)
- **Quick Manual Edits**: 5.0-10.0 req/sec
- **Development/Testing**: 0 (no limit)

#### For Different Connection Types

- **Slow/Unstable Internet**: 0.5-1.0 req/sec
- **Standard Broadband**: 2.0 req/sec
- **High-Speed Connection**: 5.0-10.0 req/sec
- **Local Development**: 0 (no limit)

## Impact on Operations

### Bulk Import Operations

Rate limiting is especially important for bulk imports:

```
Example: Importing 100 records at 2.0 req/sec
- Time required: ~50 seconds
- Without rate limiting: Likely to fail with timeouts
- With rate limiting: Reliable completion
```

### Real-Time Operations

For interactive operations, the impact is minimal:

```
Example: Creating a single record at 2.0 req/sec
- Delay: 0.5 seconds maximum
- User experience: Barely noticeable
```

### Background Synchronization

Background operations automatically respect rate limits:
- Zone list updates are throttled
- Record synchronization is controlled
- Keepalive checks are rate-limited

## Components Affected

### All API Operations Are Rate-Limited

The centralized implementation ensures consistent rate limiting across:

#### Import/Export Operations
- Zone creation during import
- Record creation during bulk import
- Record updates during merge operations
- Record deletion during replace operations
- Zone record retrieval for conflict resolution

#### Zone Management
- Zone creation from UI
- Zone deletion from UI
- Zone listing and refresh operations

#### Record Management
- Individual record creation
- Individual record updates
- Individual record deletion
- Record retrieval and refresh

#### Background Operations
- Periodic zone synchronization
- Periodic record synchronization
- Background cache updates
- Connectivity checks
- Authentication validation

## Troubleshooting

### Common Issues and Solutions

#### Import Operations Timing Out
**Symptoms**: Import fails with "Request timed out" errors
**Solution**: Lower the rate limit to 0.5-1.0 req/sec

#### Application Feels Slow
**Symptoms**: Noticeable delays in UI operations
**Solution**: Increase rate limit to 5.0-10.0 req/sec

#### API Errors During Bulk Operations
**Symptoms**: HTTP 429 (Too Many Requests) errors
**Solution**: Lower the rate limit to respect API limits

#### Development/Testing Issues
**Symptoms**: Want to disable rate limiting for testing
**Solution**: Set rate limit to 0 (no limit)

### Monitoring Rate Limiting

Rate limiting activity is logged at debug level:
```
2025-08-10 21:35:07,123 - api_client - DEBUG - Rate limiting: sleeping for 0.234s
```

Enable debug logging to monitor rate limiting behavior:
1. Open Configuration Dialog
2. Enable "Debug mode"
3. Check application logs for rate limiting messages

## Technical Details

### Thread Safety

The rate limiting implementation is thread-safe:
- Uses `threading.Lock()` to prevent race conditions
- Ensures accurate timing across concurrent operations
- Safe for multi-threaded import/export operations

### Performance Impact

Rate limiting has minimal performance overhead:
- **CPU Usage**: Negligible (simple time calculations)
- **Memory Usage**: Minimal (single timestamp and lock)
- **Network Impact**: Positive (prevents overwhelming the API)

### Configuration Storage

Rate limit settings are:
- **Stored**: In user configuration file (`~/.config/desecqt/config.json`)
- **Persistent**: Survives application restarts
- **Profile-Specific**: Different settings per profile
- **Default**: 2.0 requests per second

## Best Practices

### General Guidelines

1. **Start Conservative**: Begin with default 2.0 req/sec
2. **Adjust Based on Usage**: Lower for bulk operations, higher for interactive use
3. **Monitor Performance**: Watch for timeouts or slowness
4. **Test Changes**: Verify rate limit changes work for your use case

### For Different Scenarios

#### Production Use
- Use default 2.0 req/sec for reliability
- Lower to 1.0 req/sec for large bulk operations
- Monitor logs for any API errors

#### Development/Testing
- Use 0 (no limit) for rapid testing
- Use higher rates (5.0-10.0) for quick iterations
- Remember to reset for production use

#### Bulk Data Migration
- Start with 0.5 req/sec for safety
- Monitor progress and adjust if needed
- Plan for longer completion times

## API Compliance

The rate limiting system helps ensure compliance with deSEC API guidelines:
- **Respects API Limits**: Stays within reasonable request rates
- **Prevents Abuse**: Avoids overwhelming the API service
- **Improves Reliability**: Reduces likelihood of rate limit errors
- **Good Citizenship**: Shares API resources fairly with other users

## Future Enhancements

Potential improvements to the rate limiting system:
- **Adaptive Rate Limiting**: Automatically adjust based on API response times
- **Per-Operation Limits**: Different rates for different types of operations
- **Burst Allowance**: Allow short bursts while maintaining average rate
- **API Response Monitoring**: Adjust rates based on API health indicators

---

For more information about API operations, see:
- [Import/Export Documentation](IMPORT_EXPORT.md)
- [Configuration Guide](../README.md#configuration)
- [Troubleshooting Guide](../README.md#troubleshooting)
