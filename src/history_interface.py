#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Version history viewer sidebar page.

Left pane:  zone selector (which zones have version history)
Right pane: timeline of commits for the selected zone + record preview
"""

import json
import logging

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt, Signal

from qfluentwidgets import (
    PushButton, PrimaryPushButton, TableWidget, ListView, ListWidget,
    StrongBodyLabel, CaptionLabel, TextEdit,
    isDarkTheme,
)

from fluent_styles import container_qss, SPLITTER_QSS
from confirm_drawer import DeleteConfirmDrawer, RestoreConfirmDrawer

logger = logging.getLogger(__name__)


class HistoryInterface(QtWidgets.QWidget):
    """Sidebar page for browsing and restoring zone version history."""

    # Emitted when the user requests a restore; MainWindow should push via queue
    restore_requested = Signal(str, str)  # domain_name, commit_hash

    def __init__(self, version_manager, api_queue=None, parent=None):
        super().__init__(parent)
        self.setObjectName("historyInterface")
        self._vm = version_manager
        self._api_queue = api_queue
        self._current_zone = None
        self._history = []
        self._setup_ui()
        self._restore_drawer = RestoreConfirmDrawer(parent=self)
        self._delete_drawer = DeleteConfirmDrawer(parent=self)

    def showEvent(self, event):
        super().showEvent(event)
        self.setStyleSheet(container_qss())
        self._refresh_zones()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_restore_drawer'):
            self._restore_drawer.reposition(event.size())
        if hasattr(self, '_delete_drawer'):
            self._delete_drawer.reposition(event.size())

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

        # ── Left pane: zone list ──────────────────────────────────────
        left = QtWidgets.QWidget()
        left.setMinimumWidth(220)
        left_lay = QtWidgets.QVBoxLayout(left)
        left_lay.setContentsMargins(6, 6, 6, 6)
        left_lay.setSpacing(6)

        title_row = QtWidgets.QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.addWidget(StrongBodyLabel("Zones"))
        title_row.addStretch()
        self._zone_count_label = CaptionLabel("0 zones")
        title_row.addWidget(self._zone_count_label)
        left_lay.addLayout(title_row)

        self._zone_list = ListWidget()
        self._zone_list.setAlternatingRowColors(True)
        self._zone_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._zone_list.currentItemChanged.connect(self._on_zone_selected)
        self._zone_list.itemSelectionChanged.connect(self._update_delete_button)
        left_lay.addWidget(self._zone_list)

        # Delete button under zone list
        left_btn_row = QtWidgets.QHBoxLayout()
        self._delete_btn = PushButton("Delete Selected")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._on_delete_selected)
        left_btn_row.addWidget(self._delete_btn)
        left_btn_row.addStretch()
        left_lay.addLayout(left_btn_row)

        splitter.addWidget(left)

        # ── Right pane: history timeline ──────────────────────────────
        right = QtWidgets.QWidget()
        right_lay = QtWidgets.QVBoxLayout(right)
        right_lay.setContentsMargins(6, 6, 6, 6)
        right_lay.setSpacing(6)

        right_title = QtWidgets.QHBoxLayout()
        right_title.setContentsMargins(0, 0, 0, 0)
        right_title.addWidget(StrongBodyLabel("Version History"))
        right_title.addStretch()
        self._history_label = CaptionLabel("Select a zone")
        right_title.addWidget(self._history_label)
        right_lay.addLayout(right_title)

        self._history_table = TableWidget()
        self._history_table.setColumnCount(3)
        self._history_table.setHorizontalHeaderLabels(["Date", "Message", "Hash"])
        self._history_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._history_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self._history_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._history_table.verticalHeader().setVisible(False)
        hdr = self._history_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self._history_table.setAlternatingRowColors(True)
        self._history_table.selectionModel().selectionChanged.connect(self._on_version_selected)
        right_lay.addWidget(self._history_table)

        # Preview area
        right_lay.addWidget(CaptionLabel("Record preview (read-only):"))
        self._preview = TextEdit()
        self._preview.setReadOnly(True)
        self._preview.setFixedHeight(200)
        right_lay.addWidget(self._preview)

        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        self._restore_btn = PrimaryPushButton("Restore This Version")
        self._restore_btn.setEnabled(False)
        self._restore_btn.clicked.connect(self._on_restore)
        btn_row.addWidget(self._restore_btn)
        btn_row.addStretch()
        right_lay.addLayout(btn_row)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

    # ------------------------------------------------------------------
    # Zone list
    # ------------------------------------------------------------------

    def _refresh_zones(self):
        self._zone_list.clear()
        zones = self._vm.list_versioned_zones()
        for z in zones:
            self._zone_list.addItem(z)
        self._zone_count_label.setText(f"{len(zones)} zone{'s' if len(zones) != 1 else ''}")

    def _on_zone_selected(self, current, previous):
        if current is None:
            self._current_zone = None
            self._history_table.setRowCount(0)
            self._history_label.setText("Select a zone")
            return

        self._current_zone = current.text()
        self._refresh_history()

    def _update_delete_button(self):
        """Enable/disable delete button and show count based on selection."""
        selected = self._zone_list.selectedItems()
        count = len(selected)
        if count > 0:
            self._delete_btn.setEnabled(True)
            self._delete_btn.setText(
                f"Delete Selected ({count})" if count > 1 else "Delete Selected"
            )
        else:
            self._delete_btn.setEnabled(False)
            self._delete_btn.setText("Delete Selected")

    # ------------------------------------------------------------------
    # Delete zone history
    # ------------------------------------------------------------------

    def _on_delete_selected(self):
        """Show delete confirmation drawer for selected zones."""
        selected = self._zone_list.selectedItems()
        if not selected:
            return

        zone_names = [item.text() for item in selected]
        count = len(zone_names)

        self._delete_drawer.ask(
            title="Delete Version History",
            message=(
                f"Permanently delete version history for "
                f"{count} zone{'s' if count != 1 else ''}?\n\n"
                f"This removes all stored snapshots. "
                f"Live DNS records are not affected."
            ),
            items=zone_names,
            on_confirm=lambda: self._do_delete_zones(zone_names),
            confirm_text="Delete History",
        )

    def _do_delete_zones(self, zone_names):
        """Actually delete version history for the given zones."""
        deleted = 0
        for name in zone_names:
            if self._vm.delete_zone_history(name):
                deleted += 1
                logger.info("Deleted version history for %s", name)

        # Clear right pane if current zone was deleted
        if self._current_zone in zone_names:
            self._current_zone = None
            self._history_table.setRowCount(0)
            self._history = []
            self._preview.clear()
            self._restore_btn.setEnabled(False)
            self._history_label.setText("Select a zone")

        self._refresh_zones()
        logger.info("Deleted version history for %d/%d zones", deleted, len(zone_names))

    # ------------------------------------------------------------------
    # History timeline
    # ------------------------------------------------------------------

    def _refresh_history(self):
        if not self._current_zone:
            return

        self._history = self._vm.get_history(self._current_zone)
        self._history_table.setRowCount(len(self._history))

        for row, entry in enumerate(self._history):
            date_str = entry.get("date", "")[:19].replace("T", " ")
            date_item = QtWidgets.QTableWidgetItem(date_str)
            self._history_table.setItem(row, 0, date_item)

            msg_item = QtWidgets.QTableWidgetItem(entry.get("message", ""))
            self._history_table.setItem(row, 1, msg_item)

            hash_item = QtWidgets.QTableWidgetItem(entry.get("hash", "")[:8])
            hash_item.setToolTip(entry.get("hash", ""))
            self._history_table.setItem(row, 2, hash_item)

        self._history_label.setText(f"{len(self._history)} version{'s' if len(self._history) != 1 else ''}")
        self._preview.clear()
        self._restore_btn.setEnabled(False)

    def _on_version_selected(self):
        rows = self._history_table.selectionModel().selectedRows()
        if not rows or not self._current_zone:
            self._preview.clear()
            self._restore_btn.setEnabled(False)
            return

        row = rows[0].row()
        if row >= len(self._history):
            return

        commit_hash = self._history[row]["hash"]
        records = self._vm.get_version(self._current_zone, commit_hash)

        # Show a readable preview
        lines = []
        for rec in records:
            sub = rec.get("subname", "") or "@"
            rtype = rec.get("type", "")
            ttl = rec.get("ttl", "")
            values = rec.get("records", [])
            for v in values:
                lines.append(f"{sub}\t{ttl}\t{rtype}\t{v}")

        self._preview.setText("\n".join(lines) if lines else "(empty)")
        self._restore_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # Restore
    # ------------------------------------------------------------------

    def _on_restore(self):
        rows = self._history_table.selectionModel().selectedRows()
        if not rows or not self._current_zone:
            return

        row = rows[0].row()
        if row >= len(self._history):
            return

        entry = self._history[row]
        commit_hash = entry["hash"]
        date_str = entry.get("date", "")[:19].replace("T", " ")
        msg = entry.get("message", "")
        zone = self._current_zone

        # Count records for the summary
        records = self._vm.get_version(zone, commit_hash)
        rec_count = len(records) if records else 0

        self._restore_drawer.ask(
            title="Restore Version",
            message=(
                f"Restore '{zone}' to version {commit_hash[:8]}?\n\n"
                f"This will overwrite the current live DNS records with "
                f"{rec_count} record set{'s' if rec_count != 1 else ''} "
                f"from {date_str}."
            ),
            items=[msg] if msg else None,
            on_confirm=lambda: self.restore_requested.emit(zone, commit_hash),
            confirm_text="Restore",
        )
