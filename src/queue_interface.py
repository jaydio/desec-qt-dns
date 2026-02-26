#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Queue sidebar page — shows pending and completed API operations.

Left pane:  pending queue items (priority, action, status)
Right pane: completed / failed history with batch retry
Detail drawer: right-sliding panel with full request/response JSON
"""

import json
import logging
from datetime import datetime

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve

from qfluentwidgets import (
    PushButton, PrimaryPushButton, TableWidget,
    StrongBodyLabel, CaptionLabel, TogglePushButton,
    SubtitleLabel, TextEdit, SearchLineEdit, ComboBox,
    isDarkTheme,
)

from fluent_styles import container_qss, SPLITTER_QSS
from api_queue import APIQueue, QueueItem

logger = logging.getLogger(__name__)

_PRIORITY_LABELS = {0: "High", 1: "Normal", 2: "Low"}


# ======================================================================
# Detail drawer — slides in from the right to show full item details
# ======================================================================

class QueueDetailPanel(QtWidgets.QWidget):
    """Right-sliding panel showing full details of a queue history item."""

    PANEL_WIDTH = 480

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("queueDetailPanel")
        self.setAutoFillBackground(True)
        self._animation = None
        self._item = None
        self.hide()
        self._setup_ui()

    # ── Paint — opaque background so content beneath doesn't bleed through
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        bg = QtGui.QColor(32, 32, 32) if isDarkTheme() else QtGui.QColor(243, 243, 243)
        painter.fillRect(self.rect(), bg)

    # ── UI ────────────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Header row
        header_row = QtWidgets.QHBoxLayout()
        self._title_label = SubtitleLabel("Queue Item Details")
        header_row.addWidget(self._title_label, 1)
        close_btn = PushButton("\u2715")
        close_btn.setFixedSize(32, 32)
        close_btn.setToolTip("Close (Esc)")
        close_btn.clicked.connect(self.slide_out)
        header_row.addWidget(close_btn)
        layout.addLayout(header_row)

        # Escape shortcut
        esc = QtGui.QShortcut(QtGui.QKeySequence(Qt.Key.Key_Escape), self)
        esc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        esc.activated.connect(self.slide_out)

        # Metadata grid
        meta = QtWidgets.QFormLayout()
        meta.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.DontWrapRows)
        meta.setSpacing(6)

        self._status_label = QtWidgets.QLabel()
        meta.addRow("Status:", self._status_label)

        self._category_label = QtWidgets.QLabel()
        meta.addRow("Category:", self._category_label)

        self._priority_label = QtWidgets.QLabel()
        meta.addRow("Priority:", self._priority_label)

        self._created_label = QtWidgets.QLabel()
        meta.addRow("Created:", self._created_label)

        self._completed_label = QtWidgets.QLabel()
        meta.addRow("Completed:", self._completed_label)

        self._duration_label = QtWidgets.QLabel()
        meta.addRow("Duration:", self._duration_label)

        layout.addLayout(meta)

        # Error section (only visible for failed items)
        self._error_header = CaptionLabel("Error:")
        self._error_header.hide()
        layout.addWidget(self._error_header)

        self._error_text = QtWidgets.QLabel()
        self._error_text.setWordWrap(True)
        self._error_text.setStyleSheet("color: #e74c3c;")
        self._error_text.hide()
        layout.addWidget(self._error_text)

        # Request section
        mono = QtGui.QFont("Consolas, Monaco, Courier New, monospace")
        mono.setStyleHint(QtGui.QFont.StyleHint.Monospace)

        layout.addWidget(CaptionLabel("Request:"))
        self._request_edit = TextEdit()
        self._request_edit.setReadOnly(True)
        self._request_edit.setFont(mono)
        self._request_edit.setFixedHeight(120)
        layout.addWidget(self._request_edit)

        # Response section
        layout.addWidget(CaptionLabel("Response:"))
        self._response_edit = TextEdit()
        self._response_edit.setReadOnly(True)
        self._response_edit.setFont(mono)
        layout.addWidget(self._response_edit, 1)

        # Copy button
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        copy_btn = PushButton("Copy Response")
        copy_btn.clicked.connect(self._copy_response)
        btn_row.addWidget(copy_btn)
        layout.addLayout(btn_row)

    # ── Public API ────────────────────────────────────────────────────

    def show_item(self, item: QueueItem):
        """Populate and slide in with the given queue item's details."""
        self._item = item
        self._title_label.setText(item.action or "Queue Item Details")

        # Status
        status_map = {
            "completed": ("\u2714 Completed", "#2ecc71"),
            "failed": ("\u2718 Failed", "#e74c3c"),
            "cancelled": ("\u2014 Cancelled", "#888888"),
            "pending": ("\u25cf Pending", "#f0ad4e"),
            "running": ("\u25b6 Running", "#3498db"),
        }
        text, color = status_map.get(item.status, (item.status, ""))
        self._status_label.setText(text)
        self._status_label.setStyleSheet(f"color: {color}; font-weight: bold;")

        self._category_label.setText(item.category or "\u2014")
        self._priority_label.setText(
            _PRIORITY_LABELS.get(item.priority, str(item.priority))
        )

        # Timestamps
        if item.created_at:
            self._created_label.setText(item.created_at.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            self._created_label.setText("\u2014")

        if item.completed_at:
            self._completed_label.setText(item.completed_at.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            self._completed_label.setText("\u2014")

        # Duration
        if item.completed_at and item.created_at:
            delta = (item.completed_at - item.created_at).total_seconds()
            if delta < 1:
                self._duration_label.setText(f"{delta * 1000:.0f}ms")
            else:
                self._duration_label.setText(f"{delta:.2f}s")
        else:
            self._duration_label.setText("\u2014")

        # Error
        if item.status == "failed" and item.error:
            self._error_header.show()
            self._error_text.setText(item.error)
            self._error_text.show()
        else:
            self._error_header.hide()
            self._error_text.hide()

        # Request info
        if item.request_info:
            self._request_edit.setText(
                json.dumps(item.request_info, indent=2, ensure_ascii=False)
            )
        else:
            self._request_edit.setText("(no request data available)")

        # Response data
        if item.response_data is not None:
            try:
                formatted = json.dumps(
                    item.response_data, indent=2, ensure_ascii=False
                )
            except (TypeError, ValueError):
                formatted = repr(item.response_data)
            self._response_edit.setText(formatted)
        else:
            self._response_edit.setText("(no response data available)")

        self.slide_in()

    # ── Animation ─────────────────────────────────────────────────────

    def slide_in(self):
        self.setStyleSheet(
            "QWidget#queueDetailPanel { border-left: 1px solid rgba(128,128,128,0.35); }"
            + container_qss()
        )
        parent = self.parent()
        if parent is None:
            return
        pw, ph = parent.width(), parent.height()
        self.setGeometry(pw, 0, self.PANEL_WIDTH, ph)
        self.show()
        self.raise_()
        self._run_animation(
            QtCore.QPoint(pw, 0),
            QtCore.QPoint(pw - self.PANEL_WIDTH, 0),
            QEasingCurve.Type.OutCubic,
        )

    def slide_out(self):
        parent = self.parent()
        if parent is None:
            self.hide()
            return
        pw = parent.width()
        anim = self._run_animation(
            self.pos(),
            QtCore.QPoint(pw, 0),
            QEasingCurve.Type.InCubic,
        )
        anim.finished.connect(self.hide)

    def _run_animation(self, start, end, easing):
        if self._animation and self._animation.state() == QPropertyAnimation.State.Running:
            self._animation.stop()
        anim = QPropertyAnimation(self, b"pos")
        anim.setDuration(220)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(easing)
        self._animation = anim
        anim.start()
        return anim

    def reposition(self, parent_size):
        if not self.isVisible():
            return
        x = parent_size.width() - self.PANEL_WIDTH
        self.setGeometry(x, 0, self.PANEL_WIDTH, parent_size.height())

    # ── Helpers ───────────────────────────────────────────────────────

    def _copy_response(self):
        text = self._response_edit.toPlainText()
        if text:
            QtWidgets.QApplication.clipboard().setText(text)


# ======================================================================
# Queue Interface — main sidebar page
# ======================================================================

class QueueInterface(QtWidgets.QWidget):
    """Sidebar page showing queue state and history."""

    def __init__(self, api_queue: APIQueue, parent=None):
        super().__init__(parent)
        self.setObjectName("queueInterface")
        self._queue = api_queue
        self._setup_ui()
        self._connect_signals()

    def showEvent(self, event):
        super().showEvent(event)
        self.setStyleSheet(container_qss())
        self._refresh()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_detail_panel'):
            self._detail_panel.reposition(event.size())

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(SPLITTER_QSS)
        outer.addWidget(splitter, 1)

        # ── Left pane: pending queue ──────────────────────────────────
        left = QtWidgets.QWidget()
        left.setMinimumWidth(220)
        left_lay = QtWidgets.QVBoxLayout(left)
        left_lay.setContentsMargins(6, 6, 6, 6)
        left_lay.setSpacing(6)

        title_row = QtWidgets.QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.addWidget(StrongBodyLabel("Queue"))
        title_row.addStretch()
        self._pending_label = CaptionLabel("0 pending")
        title_row.addWidget(self._pending_label)
        left_lay.addLayout(title_row)

        self._pending_table = TableWidget()
        self._pending_table.setColumnCount(3)
        self._pending_table.setHorizontalHeaderLabels(["P", "Action", "Status"])
        self._pending_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._pending_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._pending_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._pending_table.verticalHeader().setVisible(False)
        hdr_left = self._pending_table.horizontalHeader()
        hdr_left.setStretchLastSection(True)
        hdr_left.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Interactive)
        hdr_left.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Interactive)
        hdr_left.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self._pending_table.setColumnWidth(0, 28)
        self._pending_table.setColumnWidth(1, 180)
        self._pending_table.setAlternatingRowColors(True)
        left_lay.addWidget(self._pending_table)

        # Buttons under pending
        btn_row = QtWidgets.QHBoxLayout()
        self._cancel_btn = PushButton("Cancel Selected")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._cancel_selected)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()
        self._pause_btn = TogglePushButton("Pause")
        self._pause_btn.setFixedWidth(90)
        self._pause_btn.clicked.connect(self._toggle_pause)
        btn_row.addWidget(self._pause_btn)
        left_lay.addLayout(btn_row)

        splitter.addWidget(left)

        # ── Right pane: history ───────────────────────────────────────
        right = QtWidgets.QWidget()
        right_lay = QtWidgets.QVBoxLayout(right)
        right_lay.setContentsMargins(6, 6, 6, 6)
        right_lay.setSpacing(6)

        right_title = QtWidgets.QHBoxLayout()
        right_title.setContentsMargins(0, 0, 0, 0)
        right_title.addWidget(StrongBodyLabel("History"))
        right_title.addStretch()
        self._history_label = CaptionLabel("0 completed")
        right_title.addWidget(self._history_label)
        right_lay.addLayout(right_title)

        # Filter row: text search + category combo
        filter_row = QtWidgets.QHBoxLayout()
        filter_row.setSpacing(6)
        self._search_edit = SearchLineEdit()
        self._search_edit.setPlaceholderText("Filter by domain or action...")
        self._search_edit.textChanged.connect(self._refresh_history)
        filter_row.addWidget(self._search_edit, 1)

        self._category_combo = ComboBox()
        self._category_combo.setFixedWidth(120)
        self._category_combo.addItem("All")
        self._category_combo.addItem("zones")
        self._category_combo.addItem("records")
        self._category_combo.addItem("tokens")
        self._category_combo.addItem("general")
        self._category_combo.currentIndexChanged.connect(self._refresh_history)
        filter_row.addWidget(self._category_combo)
        right_lay.addLayout(filter_row)

        self._history_table = TableWidget()
        self._history_table.setColumnCount(4)
        self._history_table.setHorizontalHeaderLabels(
            ["Action", "Status", "Duration", "Time"]
        )
        self._history_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._history_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._history_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._history_table.verticalHeader().setVisible(False)
        hdr = self._history_table.horizontalHeader()
        hdr.setStretchLastSection(True)
        hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Interactive)
        self._history_table.setColumnWidth(0, 420)
        self._history_table.setColumnWidth(1, 80)
        self._history_table.setColumnWidth(2, 80)
        self._history_table.setColumnWidth(3, 90)
        self._history_table.setAlternatingRowColors(True)
        right_lay.addWidget(self._history_table)

        # Buttons under history
        hist_btn_row = QtWidgets.QHBoxLayout()
        self._retry_btn = PushButton("Retry Failed")
        self._retry_btn.setEnabled(False)
        self._retry_btn.clicked.connect(self._retry_selected_failed)
        hist_btn_row.addWidget(self._retry_btn)

        self._clear_btn = PushButton("Clear History")
        self._clear_btn.clicked.connect(self._clear_history)
        hist_btn_row.addWidget(self._clear_btn)
        hist_btn_row.addStretch()
        right_lay.addLayout(hist_btn_row)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([340, 760])

        # Enable cancel button when selection changes
        self._pending_table.selectionModel().selectionChanged.connect(
            lambda: self._cancel_btn.setEnabled(
                len(self._pending_table.selectionModel().selectedRows()) > 0
            )
        )

        # Update retry button when history selection changes
        self._history_table.selectionModel().selectionChanged.connect(
            self._update_retry_button
        )

        # Double-click on history row opens detail drawer
        self._history_table.doubleClicked.connect(self._on_history_double_click)

        # Detail drawer (created last, overlays on top)
        self._detail_panel = QueueDetailPanel(parent=self)

    # ------------------------------------------------------------------
    # Signal connections
    # ------------------------------------------------------------------

    def _connect_signals(self):
        self._queue.queue_changed.connect(self._refresh)
        self._queue.item_started.connect(self._on_item_started)
        self._queue.item_finished.connect(self._on_item_finished)

    def _on_item_started(self, item_id: str):
        self._refresh()

    def _on_item_finished(self, item_id: str, success: bool, data: object):
        self._refresh()

    # ------------------------------------------------------------------
    # Refresh tables
    # ------------------------------------------------------------------

    def _refresh(self):
        """Rebuild both tables from current queue state."""
        self._refresh_pending()
        self._refresh_history()

    def _refresh_pending(self):
        """Rebuild pending table from the queue's internal PQ snapshot."""
        with self._queue._lock:
            pending = [
                i for i in self._queue._items.values()
                if i.status in ("pending", "running")
            ]
        pending.sort(key=lambda i: (i.priority, i._seq))

        self._pending_table.setRowCount(len(pending))
        for row, item in enumerate(pending):
            prio_text = {0: "\u25b2", 1: "\u25cf", 2: "\u25bd"}.get(item.priority, "?")
            prio_item = QtWidgets.QTableWidgetItem(prio_text)
            prio_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            prio_item.setData(Qt.ItemDataRole.UserRole, item.id)
            self._pending_table.setItem(row, 0, prio_item)

            action_item = QtWidgets.QTableWidgetItem(item.action)
            self._pending_table.setItem(row, 1, action_item)

            status_text = "\u25b6 Running" if item.status == "running" else "Pending"
            status_item = QtWidgets.QTableWidgetItem(status_text)
            self._pending_table.setItem(row, 2, status_item)

        self._pending_label.setText(f"{len(pending)} pending")

    def _refresh_history(self):
        all_history = self._queue.get_history()

        # Apply filters
        search_text = self._search_edit.text().strip().lower() if hasattr(self, '_search_edit') else ""
        category_filter = self._category_combo.currentText() if hasattr(self, '_category_combo') else "All"

        history = []
        for item in all_history:
            if category_filter != "All" and item.category != category_filter:
                continue
            if search_text and search_text not in item.action.lower():
                continue
            history.append(item)

        self._history_table.setRowCount(len(history))
        completed_count = 0
        failed_count = 0

        for row, item in enumerate(history):
            action_item = QtWidgets.QTableWidgetItem(item.action)
            action_item.setData(Qt.ItemDataRole.UserRole, item.id)
            self._history_table.setItem(row, 0, action_item)

            if item.status == "completed":
                status_text = "\u2714 OK"
                completed_count += 1
            elif item.status == "failed":
                status_text = "\u2718 Failed"
                failed_count += 1
            else:
                status_text = "\u2014 Cancelled"

            status_item = QtWidgets.QTableWidgetItem(status_text)
            if item.status == "failed":
                status_item.setForeground(QtGui.QColor("#e74c3c"))
                if item.error:
                    status_item.setToolTip(item.error)
            elif item.status == "completed":
                status_item.setForeground(QtGui.QColor("#2ecc71"))
            self._history_table.setItem(row, 1, status_item)

            duration = ""
            if item.completed_at and item.created_at:
                delta = (item.completed_at - item.created_at).total_seconds()
                if delta < 1:
                    duration = f"{delta * 1000:.0f}ms"
                else:
                    duration = f"{delta:.1f}s"
            dur_item = QtWidgets.QTableWidgetItem(duration)
            dur_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._history_table.setItem(row, 2, dur_item)

            ts = item.completed_at or item.created_at
            time_str = ts.strftime("%H:%M:%S") if ts else ""
            time_item = QtWidgets.QTableWidgetItem(time_str)
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._history_table.setItem(row, 3, time_item)

        parts = []
        if completed_count:
            parts.append(f"{completed_count} completed")
        if failed_count:
            parts.append(f"{failed_count} failed")
        total = len(all_history)
        if len(history) < total:
            parts.append(f"showing {len(history)}/{total}")
        self._history_label.setText(", ".join(parts) if parts else "No history")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _toggle_pause(self):
        if self._pause_btn.isChecked():
            self._queue.pause()
            self._pause_btn.setText("Resume")
        else:
            self._queue.resume()
            self._pause_btn.setText("Pause")

    def _cancel_selected(self):
        rows = self._pending_table.selectionModel().selectedRows()
        for idx in rows:
            item = self._pending_table.item(idx.row(), 0)
            if item:
                item_id = item.data(Qt.ItemDataRole.UserRole)
                if item_id:
                    self._queue.cancel(item_id)
        self._refresh()

    def _update_retry_button(self):
        """Update the retry button label and enabled state based on selection."""
        failed_ids = self._get_selected_failed_ids()
        count = len(failed_ids)
        if count > 0:
            self._retry_btn.setEnabled(True)
            self._retry_btn.setText(f"Retry Failed ({count})")
        else:
            self._retry_btn.setEnabled(False)
            self._retry_btn.setText("Retry Failed")

    def _get_selected_failed_ids(self):
        """Return item IDs for selected rows that have 'failed' status."""
        ids = []
        for idx in self._history_table.selectionModel().selectedRows():
            row = idx.row()
            action_item = self._history_table.item(row, 0)
            status_item = self._history_table.item(row, 1)
            if action_item and status_item:
                item_id = action_item.data(Qt.ItemDataRole.UserRole)
                if item_id and "\u2718" in (status_item.text() or ""):
                    ids.append(item_id)
        return ids

    def _retry_selected_failed(self):
        """Retry only the selected failed items."""
        for item_id in self._get_selected_failed_ids():
            self._queue.retry(item_id)
        self._refresh()

    def _clear_history(self):
        self._queue.clear_history()
        self._refresh()

    # ------------------------------------------------------------------
    # Detail drawer
    # ------------------------------------------------------------------

    def _on_history_double_click(self, index):
        """Open the detail drawer for the double-clicked history row."""
        row = index.row()
        action_item = self._history_table.item(row, 0)
        if not action_item:
            return

        item_id = action_item.data(Qt.ItemDataRole.UserRole)
        if not item_id:
            return

        with self._queue._lock:
            queue_item = self._queue._items.get(item_id)

        if queue_item:
            self._detail_panel.show_item(queue_item)
