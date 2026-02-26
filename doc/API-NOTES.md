# deSEC Qt DNS Manager -- API Notes

## Overview

All API communication goes through a two-layer system: the central API Queue (`api_queue.py`) handles sequencing and retry, while the API Client (`api_client.py`) handles HTTP requests and per-request rate limiting.

## Request Flow

```
User Action (UI)
  -> QueueItem created (priority, category, action, callable, callback)
  -> api_queue.enqueue(item)
  -> APIQueue background thread processes sequentially
  -> api_client.<method>() called
  -> api_client._make_request() called
  -> api_client._apply_rate_limit() enforces delay
  -> HTTP request sent (requests library)
  -> Response handled
```

## Central API Queue (api_queue.py)

- APIQueue is a QThread running a processing loop.
- Uses stdlib PriorityQueue (thread-safe).
- Three priority levels:
  - PRIORITY_HIGH (0): Zone list loads, connectivity checks.
  - PRIORITY_NORMAL (1): Interactive CRUD (record add/edit/delete, token ops).
  - PRIORITY_LOW (2): Background sync, refresh.
- FIFO ordering within same priority (monotonic sequence counter).
- Sequential processing: one request at a time.
- Pause/resume support (e.g., during offline mode).

## Rate Limit Enforcement (api_client.py)

- `_apply_rate_limit()` called BEFORE every HTTP request.
- Uses `threading.Lock` for thread safety.
- Calculates `min_interval = 1.0 / rate_limit` (configurable, default 1.0 req/sec).
- Sleeps if elapsed time since last request < min_interval.
- Setting rate_limit to 0 disables rate limiting entirely.

## HTTP 429 Handling

When the deSEC API returns HTTP 429 (Too Many Requests):

1. `api_client._make_request()` returns a `RateLimitResponse` sentinel object (NOT a normal error).
   - Contains: `retry_after` (seconds), `message`, `raw_response`.

2. APIQueue detects `RateLimitResponse` and applies one of two strategies:

   **Auto-retry (retry_after <= 60 seconds):**
   - If `item.retry_count < max_retries` (default 3):
     - Sleep for `retry_after` seconds.
     - Re-enqueue the item.
     - Increment `retry_count`.
   - If retries exhausted: fail the item, move to history.

   **Cooldown mode (retry_after > 60 seconds):**
   - Item marked as failed immediately.
   - `rate_limited` signal emitted -> `MainWindow._on_rate_limited()`.
   - MainWindow enters rate-limit cooldown:
     - API queue paused.
     - Sync timers stopped.
     - Connection status set to offline (red).
     - NotifyDrawer shows warning with `retry_after` duration.
     - `QTimer.singleShot` schedules auto-resume after `retry_after` seconds.
   - When timer fires: queue resumed, timers restarted, connectivity checked.

3. Adaptive rate limiting:
   - `api_client.adapt_rate_limit(retry_after)` halves the current rate limit.
   - Floor: 0.25 req/sec (4-second intervals).
   - New rate persisted in config until next settings save.

## Queue History and Persistence

- Completed/failed items stored in history list (configurable limit, default 5000).
- History optionally persisted to `~/.config/desecqt/queue_history.json` (atomic writes).
- QueueInterface sidebar page shows pending + history with batch retry.
- QueueDetailPanel shows full request/response JSON for debugging.

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| api_rate_limit | 1.0 | Requests per second (0 = unlimited) |
| queue_history_persist | true | Save queue history to disk |
| queue_history_limit | 5000 | Maximum history entries retained |
| keepalive_interval | 60 | Seconds between connectivity checks |
| sync_interval_minutes | 15 | Minutes between automatic zone syncs |

## deSEC API Endpoints Used

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | /domains/ | List zones |
| POST | /domains/ | Create zone |
| DELETE | /domains/{name}/ | Delete zone |
| GET | /domains/{name}/rrsets/ | List records |
| POST | /domains/{name}/rrsets/ | Create record |
| PATCH | /domains/{name}/rrsets/{sub}.../{type}/ | Update record |
| DELETE | /domains/{name}/rrsets/{sub}.../{type}/ | Delete record |
| PUT | /domains/{name}/rrsets/ | Bulk replace all records |
| GET | /auth/account/ | Account info (domain limit) |
| GET/POST/PATCH/DELETE | /auth/tokens/... | Token management |
| GET/POST/PATCH/DELETE | /auth/tokens/{id}/policies/rrsets/... | Token policy management |

## Best Practices

- Default rate limit (1.0 req/sec) is safe for normal usage.
- For large bulk operations (>50 records), consider lowering to 0.5 req/sec.
- The API queue handles retry automatically -- no user intervention needed for transient 429s.
- Queue page provides visibility into pending/failed requests.
- Adaptive rate limiting ensures the app self-heals after hitting limits.
