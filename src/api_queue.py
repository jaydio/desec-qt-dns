#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Central API queue engine.

All API calls are funnelled through a single background QThread that
processes them one at a time, respecting deSEC rate limits.  The UI
stays responsive because enqueue() returns immediately.

Signals keep the QueueInterface (and anything else) up to date in
real time.
"""

import json
import logging
import os
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from queue import PriorityQueue, Empty
from threading import Lock
from typing import Any, Callable, Optional, Tuple

from PySide6.QtCore import QThread, Signal, QMutex, QWaitCondition

from api_client import RateLimitResponse

logger = logging.getLogger(__name__)


def _safe_serialise(obj):
    """Best-effort conversion of *obj* to a JSON-safe structure."""
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_safe_serialise(v) for v in obj]
    if isinstance(obj, dict):
        return {str(k): _safe_serialise(v) for k, v in obj.items()}
    return repr(obj)


# Priority constants
PRIORITY_HIGH = 0      # zone list load, connectivity
PRIORITY_NORMAL = 1    # interactive CRUD (records, tokens)
PRIORITY_LOW = 2       # background sync, refresh


@dataclass
class QueueItem:
    """One unit of work for the API queue."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    priority: int = PRIORITY_NORMAL
    category: str = "general"           # "zones", "records", "tokens", …
    action: str = ""                    # human-readable description
    callable: Callable = field(default=None, repr=False)
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    status: str = "pending"             # pending → running → completed | failed
    result: Any = None                  # (success, data) after execution
    error: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    callback: Optional[Callable] = field(default=None, repr=False)

    # Rate-limit retry tracking
    retry_count: int = 0
    max_retries: int = 3

    # Metadata for the detail drawer
    request_info: dict = field(default_factory=dict)   # method name + args
    response_data: Any = None                          # raw API response (JSON-serialisable)

    # For PriorityQueue ordering: (priority, sequence)
    _seq: int = 0

    def __lt__(self, other: "QueueItem") -> bool:
        if self.priority != other.priority:
            return self.priority < other.priority
        return self._seq < other._seq


class APIQueue(QThread):
    """Background thread that processes QueueItem objects sequentially."""

    # Emitted when an item starts executing
    item_started = Signal(str)                    # item_id

    # Emitted when an item finishes (success or failure)
    item_finished = Signal(str, bool, object)     # item_id, success, data

    # Queue state signals
    queue_paused = Signal()
    queue_resumed = Signal()
    queue_empty = Signal()

    # Emitted on every enqueue / finish so the UI can update counts
    queue_changed = Signal()

    # Emitted when a 429 rate-limit response is received
    rate_limited = Signal(float, str)  # retry_after_seconds, message

    # Internal signal for dispatching callbacks on the main thread
    _callback_dispatch = Signal(str, bool, object)  # item_id, success, data

    def __init__(self, parent=None, history_file=None, history_limit=500,
                 persist=False):
        super().__init__(parent)
        self._callback_dispatch.connect(self._invoke_callback)

        # Internal priority queue (thread-safe stdlib PriorityQueue)
        self._pq: PriorityQueue = PriorityQueue()
        self._seq = 0                 # monotonic counter for FIFO within priority

        # Completed / failed items (most-recent first)
        self._history: list[QueueItem] = []
        self._history_limit = history_limit

        # Persistence
        self._history_file = history_file
        self._persist = persist
        if self._persist and self._history_file:
            self._load_history()

        # Lookup by id (covers both pending and history)
        self._items: dict[str, QueueItem] = {}
        # Populate items dict from loaded history
        for item in self._history:
            self._items[item.id] = item

        # Synchronisation
        self._lock = Lock()
        self._mutex = QMutex()
        self._wait = QWaitCondition()

        # Flags
        self._paused = False
        self._stopping = False

    @property
    def is_paused(self) -> bool:
        """Whether the queue is currently paused."""
        return self._paused

    # ── Public API (called from UI thread) ────────────────────────────

    def enqueue(self, item: QueueItem) -> str:
        """Add an item to the queue.  Returns the item id."""
        # Capture request metadata for the detail drawer
        if not item.request_info and item.callable is not None:
            method_name = getattr(item.callable, "__name__", str(item.callable))
            try:
                serialised_args = _safe_serialise(item.args)
            except Exception:
                serialised_args = [repr(a) for a in item.args]
            item.request_info = {
                "method": method_name,
                "args": serialised_args,
            }
            if item.kwargs:
                try:
                    item.request_info["kwargs"] = _safe_serialise(item.kwargs)
                except Exception:
                    item.request_info["kwargs"] = {k: repr(v) for k, v in item.kwargs.items()}
        with self._lock:
            item._seq = self._seq
            self._seq += 1
            item.status = "pending"
            self._items[item.id] = item
            self._pq.put(item)

        logger.debug("Enqueued [%s] %s (priority %d)", item.id, item.action, item.priority)
        self.queue_changed.emit()

        # Wake the processing loop if it's waiting for work
        self._mutex.lock()
        self._wait.wakeOne()
        self._mutex.unlock()
        return item.id

    def pause(self):
        """Pause processing after the current item completes."""
        self._paused = True
        logger.info("Queue paused")
        self.queue_paused.emit()

    def resume(self):
        """Resume processing."""
        self._paused = False
        logger.info("Queue resumed")
        self.queue_resumed.emit()
        # Wake the loop so it checks for work
        self._mutex.lock()
        self._wait.wakeOne()
        self._mutex.unlock()

    def cancel(self, item_id: str):
        """Cancel a pending item (removes it from the queue)."""
        cancelled = False
        with self._lock:
            item = self._items.get(item_id)
            if item and item.status == "pending":
                item.status = "cancelled"
                item.completed_at = datetime.now()
                self._history.insert(0, item)
                self._trim_history()
                cancelled = True
                logger.debug("Cancelled [%s] %s", item.id, item.action)
        if cancelled:
            self._save_history()
            self.queue_changed.emit()

    def retry(self, item_id: str):
        """Re-enqueue a failed or cancelled item."""
        with self._lock:
            item = self._items.get(item_id)
            if not item or item.status not in ("failed", "cancelled"):
                return
            # Remove from history
            try:
                self._history.remove(item)
            except ValueError:
                pass

        # Reset and re-enqueue
        item.status = "pending"
        item.result = None
        item.error = ""
        item.completed_at = None
        item.created_at = datetime.now()
        self.enqueue(item)

    def retry_failed(self):
        """Re-enqueue all failed items."""
        with self._lock:
            failed = [i for i in self._history if i.status == "failed"]
        for item in failed:
            self.retry(item.id)

    def clear_completed(self):
        """Remove all completed (non-failed) items from history."""
        with self._lock:
            self._history = [i for i in self._history if i.status == "failed"]
            # Also clean lookup table
            keep_ids = {i.id for i in self._history}
            # Keep pending items too
            self._items = {
                k: v for k, v in self._items.items()
                if v.status in ("pending", "running") or k in keep_ids
            }
        self._save_history()
        self.queue_changed.emit()

    def clear_history(self):
        """Remove all items from history."""
        with self._lock:
            self._history.clear()
            self._items = {
                k: v for k, v in self._items.items()
                if v.status in ("pending", "running")
            }
        self._save_history()
        self.queue_changed.emit()

    def get_pending_count(self) -> int:
        """Return the number of pending items."""
        return self._pq.qsize()

    def get_history(self) -> list[QueueItem]:
        """Return a copy of the history list."""
        with self._lock:
            return list(self._history)

    def stop(self):
        """Signal the thread to stop and wait for it to finish."""
        self._stopping = True
        self._mutex.lock()
        self._wait.wakeOne()
        self._mutex.unlock()
        self.wait(5000)  # wait up to 5 seconds
        self._save_history()

    # ── Thread run loop ───────────────────────────────────────────────

    def run(self):
        """Main processing loop — runs in background thread."""
        logger.info("API queue thread started")

        while not self._stopping:
            # Wait if paused
            if self._paused:
                self._mutex.lock()
                self._wait.wait(self._mutex)
                self._mutex.unlock()
                continue

            # Try to get next item
            try:
                item: QueueItem = self._pq.get_nowait()
            except Empty:
                # Nothing to do — wait for wake signal
                self.queue_empty.emit()
                self._mutex.lock()
                self._wait.wait(self._mutex, 2000)  # wake every 2s or on signal
                self._mutex.unlock()
                continue

            # Skip cancelled items
            if item.status == "cancelled":
                continue

            # Execute
            item.status = "running"
            self.item_started.emit(item.id)
            self.queue_changed.emit()

            try:
                if item.callable is None:
                    raise ValueError(f"No callable for queue item: {item.action}")

                result = item.callable(*item.args, **item.kwargs)

                # api_client methods return (bool, data)
                if isinstance(result, tuple) and len(result) == 2:
                    success, data = result
                else:
                    success, data = True, result

                # ── Handle 429 rate-limit responses ──
                if not success and isinstance(data, RateLimitResponse):
                    if data.retry_after > 60:
                        # Long wait (daily limit) — fail immediately
                        item.error = (
                            f"Daily rate limit exceeded — retry in "
                            f"{data.retry_after:.0f}s: {data.message}"
                        )
                        self.rate_limited.emit(data.retry_after, item.error)
                        item.result = (False, item.error)
                        item.response_data = data.raw_response
                        item.status = "failed"
                        success, data = False, item.error
                    elif item.retry_count < item.max_retries:
                        # Short wait — auto-retry
                        item.retry_count += 1
                        wait = data.retry_after + 0.5  # small buffer
                        logger.warning(
                            "429 [%s] — retry %d/%d after %.1fs",
                            item.id, item.retry_count, item.max_retries, wait,
                        )
                        if item.retry_count == 1:
                            self.rate_limited.emit(wait, data.message)
                        item.status = "pending"
                        self._interruptible_sleep(wait)
                        with self._lock:
                            self._pq.put(item)
                        self.queue_changed.emit()
                        continue  # skip history / callback / emit
                    else:
                        # Exhausted retries
                        item.error = (
                            f"Rate limited after {item.max_retries} retries: "
                            f"{data.message}"
                        )
                        item.result = (False, item.error)
                        item.response_data = data.raw_response
                        item.status = "failed"
                        success, data = False, item.error
                else:
                    item.result = (success, data)
                    item.response_data = data
                    item.status = "completed" if success else "failed"
                    if not success:
                        if isinstance(data, dict) and "message" in data:
                            item.error = data["message"]
                        elif isinstance(data, str):
                            item.error = data

            except Exception as exc:
                logger.exception("Queue item [%s] raised: %s", item.id, exc)
                item.result = (False, str(exc))
                item.response_data = str(exc)
                item.status = "failed"
                item.error = str(exc)
                success, data = False, str(exc)

            item.completed_at = datetime.now()

            # Move to history
            with self._lock:
                self._history.insert(0, item)
                self._trim_history()

            self._save_history()
            self.item_finished.emit(item.id, success, data)
            self.queue_changed.emit()

            # Dispatch callback on the main/GUI thread via signal
            if item.callback:
                self._callback_dispatch.emit(item.id, success, data)

        logger.info("API queue thread stopped")

    # ── Callback dispatch (runs on main thread) ─────────────────────

    def _invoke_callback(self, item_id: str, success: bool, data: object):
        """Slot that runs on the main thread to safely call item callbacks."""
        with self._lock:
            item = self._items.get(item_id)
        if item and item.callback:
            try:
                item.callback(success, data)
            except Exception as exc:
                logger.exception("Callback for [%s] raised: %s", item_id, exc)

    # ── Configuration (called from UI thread) ──────────────────────

    def set_history_limit(self, limit: int):
        """Update the history retention limit at runtime."""
        with self._lock:
            self._history_limit = limit
            self._trim_history()
        self._save_history()

    def set_persist(self, enabled: bool, history_file: str = None):
        """Enable or disable history persistence at runtime."""
        self._persist = enabled
        if history_file is not None:
            self._history_file = history_file
        if enabled:
            self._save_history()

    # ── Internal helpers ──────────────────────────────────────────────

    def _interruptible_sleep(self, seconds):
        """Sleep in 1-second chunks so _stopping is checked between each."""
        end = time.time() + seconds
        while time.time() < end and not self._stopping:
            time.sleep(min(1.0, end - time.time()))

    def _trim_history(self):
        """Keep history bounded (caller must hold _lock)."""
        if len(self._history) > self._history_limit:
            removed = self._history[self._history_limit:]
            self._history = self._history[:self._history_limit]
            for item in removed:
                self._items.pop(item.id, None)

    def _load_history(self):
        """Load persisted history from JSON file."""
        if not self._history_file or not os.path.exists(self._history_file):
            return
        try:
            with open(self._history_file, "r") as f:
                data = json.load(f)
            for entry in data:
                item = QueueItem(
                    id=entry.get("id", uuid.uuid4().hex[:12]),
                    priority=entry.get("priority", PRIORITY_NORMAL),
                    category=entry.get("category", "general"),
                    action=entry.get("action", ""),
                    status=entry.get("status", "completed"),
                    error=entry.get("error", ""),
                    created_at=datetime.fromisoformat(entry["created_at"])
                        if entry.get("created_at") else datetime.now(),
                    completed_at=datetime.fromisoformat(entry["completed_at"])
                        if entry.get("completed_at") else None,
                    request_info=entry.get("request_info", {}),
                    response_data=entry.get("response_data"),
                )
                self._history.append(item)
            # Trim to current limit
            self._history = self._history[:self._history_limit]
            logger.info("Loaded %d history items from %s", len(self._history), self._history_file)
        except Exception as exc:
            logger.warning("Failed to load queue history: %s", exc)

    def _save_history(self):
        """Persist current history to JSON file."""
        if not self._persist or not self._history_file:
            return
        try:
            os.makedirs(os.path.dirname(self._history_file), exist_ok=True)
            with self._lock:
                data = []
                for item in self._history:
                    entry = {
                        "id": item.id,
                        "priority": item.priority,
                        "category": item.category,
                        "action": item.action,
                        "status": item.status,
                        "error": item.error,
                        "created_at": item.created_at.isoformat()
                            if item.created_at else None,
                        "completed_at": item.completed_at.isoformat()
                            if item.completed_at else None,
                        "request_info": item.request_info or {},
                    }
                    # Persist response_data (best-effort serialisation)
                    if item.response_data is not None:
                        try:
                            entry["response_data"] = _safe_serialise(
                                item.response_data
                            )
                        except Exception:
                            entry["response_data"] = repr(item.response_data)
                    data.append(entry)
            dir_path = os.path.dirname(self._history_file)
            fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(data, f)
                os.replace(tmp_path, self._history_file)
            except BaseException:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as exc:
            logger.warning("Failed to save queue history: %s", exc)
