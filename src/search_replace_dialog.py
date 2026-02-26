#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Global Search & Replace dialog for deSEC Qt DNS Manager.
Searches across all DNS zones and allows bulk replacing content,
subnames, and TTL values, or deleting matched records.
"""

import csv
import json
import logging
import re
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QFileDialog
from qfluentwidgets import (PushButton, PrimaryPushButton, LineEdit, CheckBox,
                             ProgressBar, PlainTextEdit, TableWidget,
                             StrongBodyLabel, CaptionLabel)
from fluent_styles import container_qss, SPLITTER_QSS
from confirm_drawer import DeleteConfirmDrawer, ConfirmDrawer
from notify_drawer import NotifyDrawer
from api_queue import QueueItem, PRIORITY_NORMAL

logger = logging.getLogger(__name__)

DNS_RECORD_TYPES = [
    'A', 'AAAA', 'AFSDB', 'APL', 'CAA', 'CDNSKEY', 'CDS', 'CERT', 'CNAME',
    'DHCID', 'DNAME', 'DNSKEY', 'DLV', 'DS', 'EUI48', 'EUI64', 'HINFO',
    'HTTPS', 'KX', 'L32', 'L64', 'LOC', 'LP', 'MX', 'NAPTR', 'NID', 'NS',
    'OPENPGPKEY', 'PTR', 'RP', 'SMIMEA', 'SPF', 'SRV', 'SSHFP', 'SVCB',
    'TLSA', 'TXT', 'URI',
]

COL_ZONE    = 0
COL_SUBNAME = 1
COL_TYPE    = 2
COL_TTL     = 3
COL_CONTENT = 4


# ---------------------------------------------------------------------------
# Search worker
# ---------------------------------------------------------------------------

class _SearchWorker(QThread):
    progress_update = Signal(int, str)
    finished        = Signal(bool, str, list)

    def __init__(self, api_client, cache_manager,
                 filter_subname, filter_type, filter_content,
                 filter_ttl, filter_zone, use_regex):
        super().__init__()
        self.api_client     = api_client
        self.cache_manager  = cache_manager
        self.filter_subname = filter_subname.strip()
        self.filter_type    = filter_type
        self.filter_content = filter_content.strip()
        self.filter_ttl     = filter_ttl.strip()
        self.filter_zone    = filter_zone.strip()
        self.use_regex      = use_regex
        self._skipped       = 0

    def run(self):
        try:
            zones_result = self.cache_manager.get_cached_zones()
            if zones_result and isinstance(zones_result, tuple):
                zones_data, _ = zones_result
            else:
                zones_data = []

            if not zones_data:
                if self.api_client.is_online:
                    success, zones_data = self.api_client.get_zones()
                    if not success:
                        self.finished.emit(False, "Could not load zones.", [])
                        return
                else:
                    self.finished.emit(False, "No cached zones available and offline.", [])
                    return

            all_zone_names = [z.get('name', '') for z in zones_data if z.get('name')]

            # Apply zone scope filter
            zone_names = []
            for zn in all_zone_names:
                if self.filter_zone:
                    if self.use_regex:
                        try:
                            if not re.search(self.filter_zone, zn, re.IGNORECASE):
                                continue
                        except re.error:
                            continue
                    else:
                        if self.filter_zone.lower() not in zn.lower():
                            continue
                zone_names.append(zn)

            total   = len(zone_names)
            matches = []

            for idx, zone_name in enumerate(zone_names):
                pct = int((idx / total) * 100) if total else 100
                self.progress_update.emit(pct, f"Searching {zone_name}…")
                for record in self._load_records(zone_name):
                    if self._matches(record):
                        matches.append({'zone': zone_name, **record})

            self.progress_update.emit(100, "Done.")
            zones_hit = len({m['zone'] for m in matches})
            msg = f"{len(matches)} record(s) found across {zones_hit} zone(s)."
            if self._skipped:
                msg += f" ({self._skipped} zone(s) skipped — not cached)"
            self.finished.emit(True, msg, matches)
        except Exception as e:
            logger.error(f"Search worker error: {e}")
            self.finished.emit(False, f"Search failed: {e}", [])

    def _load_records(self, zone_name):
        cached = self.cache_manager.get_cached_records(zone_name)
        if cached and isinstance(cached, tuple):
            records, _ = cached
            if records:
                return records
        self._skipped += 1
        return []

    def _matches(self, record):
        subname = record.get('subname', '') or ''
        rtype   = record.get('type', '')
        ttl     = record.get('ttl', 0)
        content = '\n'.join(record.get('records', []))
        # Truncate content to 10KB to bound regex execution time
        content = content[:10240]

        if self.use_regex:
            try:
                if self.filter_subname and not re.search(self.filter_subname, subname, re.IGNORECASE):
                    return False
                if self.filter_content and not re.search(self.filter_content, content, re.IGNORECASE):
                    return False
            except re.error:
                return False
        else:
            if self.filter_subname and self.filter_subname.lower() not in subname.lower():
                return False
            if self.filter_content and self.filter_content.lower() not in content.lower():
                return False

        if self.filter_type and self.filter_type != rtype:
            return False
        if self.filter_ttl:
            try:
                if int(self.filter_ttl) != ttl:
                    return False
            except ValueError:
                pass
        return True


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------

class SearchReplaceInterface(QtWidgets.QWidget):
    """
    Global Search & Replace page (Fluent sidebar navigation).
    Searches records across all zones by subname/type/content/TTL/zone,
    previews matches with checkboxes, then applies bulk replacements or deletions.
    """

    def __init__(self, api_client, cache_manager, parent=None, api_queue=None):
        super().__init__(parent)
        self.setObjectName("searchReplaceInterface")
        self.api_client      = api_client
        self.cache_manager   = cache_manager
        self.api_queue       = api_queue
        self._search_worker  = None
        self._search_generation = 0
        self._setup_ui()
        self._delete_drawer = DeleteConfirmDrawer(parent=self)
        self._confirm_drawer = ConfirmDrawer(parent=self)
        self._notify_drawer = NotifyDrawer(parent=self)

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

        # ==============================================================
        # Left pane — Search + Results
        # ==============================================================
        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(6)

        # ── Title row ─────────────────────────────────────────────────
        title_row = QtWidgets.QHBoxLayout()
        title_row.addWidget(StrongBodyLabel("Search & Replace"))
        title_row.addStretch()
        self._results_count_label = CaptionLabel("0 results")
        title_row.addWidget(self._results_count_label)
        left_layout.addLayout(title_row)

        # ── Search Filters group ──────────────────────────────────────
        search_group = QtWidgets.QGroupBox("Search Filters")
        search_grid  = QtWidgets.QGridLayout(search_group)

        search_grid.addWidget(QtWidgets.QLabel("Subname:"), 0, 0)
        self._sub_edit = LineEdit()
        self._sub_edit.setPlaceholderText("e.g. www  (blank = any)")
        self._sub_edit.returnPressed.connect(self._run_search)
        search_grid.addWidget(self._sub_edit, 0, 1)

        search_grid.addWidget(QtWidgets.QLabel("Type:"), 0, 2)
        self._type_combo = QtWidgets.QComboBox()
        self._type_combo.addItem("(Any)")
        for t in DNS_RECORD_TYPES:
            self._type_combo.addItem(t)
        search_grid.addWidget(self._type_combo, 0, 3)

        search_grid.addWidget(QtWidgets.QLabel("Content:"), 1, 0)
        self._content_edit = LineEdit()
        self._content_edit.setPlaceholderText("e.g. 1.2.3.4  (blank = any)")
        self._content_edit.returnPressed.connect(self._run_search)
        search_grid.addWidget(self._content_edit, 1, 1)

        search_grid.addWidget(QtWidgets.QLabel("TTL:"), 1, 2)
        self._ttl_edit = LineEdit()
        self._ttl_edit.setPlaceholderText("e.g. 3600  (blank = any)")
        self._ttl_edit.setMaximumWidth(120)
        self._ttl_edit.returnPressed.connect(self._run_search)
        search_grid.addWidget(self._ttl_edit, 1, 3)

        search_grid.addWidget(QtWidgets.QLabel("Zone:"), 2, 0)
        self._zone_edit = LineEdit()
        self._zone_edit.setPlaceholderText("e.g. example.com  (blank = all zones)")
        self._zone_edit.returnPressed.connect(self._run_search)
        search_grid.addWidget(self._zone_edit, 2, 1)

        self._regex_check = CheckBox("Use regex")

        _regex_help = QtWidgets.QLabel("(?)")
        _regex_help.setToolTip(
            "<html><body>"
            "When enabled, Subname / Content / Zone filters are treated as "
            "Python regular expressions (case-insensitive).<br><br>"
            "<b>Examples:</b><br>"
            "<table cellspacing='2'>"
            "<tr><td><tt>^mail</tt></td><td>&nbsp;— subname starts with 'mail'</td></tr>"
            "<tr><td><tt>^(www|ftp)$</tt></td><td>&nbsp;— subname is exactly 'www' or 'ftp'</td></tr>"
            "<tr><td><tt>^_</tt></td><td>&nbsp;— subname starts with underscore (e.g. _dmarc, _domainkey)</td></tr>"
            "<tr><td><tt>^$</tt></td><td>&nbsp;— apex/root record (empty subname)</td></tr>"
            "<tr><td><tt>\\d+</tt></td><td>&nbsp;— contains one or more digits</td></tr>"
            "<tr><td><tt>1\\.2\\.3\\.\\d+</tt></td><td>&nbsp;— IPs like 1.2.3.4 – 1.2.3.255</td></tr>"
            "<tr><td><tt>v=spf1</tt></td><td>&nbsp;— content contains SPF record</td></tr>"
            "<tr><td><tt>\\.de$</tt></td><td>&nbsp;— zones ending in .de (zone filter)</td></tr>"
            "<tr><td><tt>\\.(com|net|org)$</tt></td><td>&nbsp;— zones with a specific TLD</td></tr>"
            "</table><br><br>"
            "Invalid patterns are rejected before the search starts."
            "</body></html>"
        )

        _regex_row = QtWidgets.QWidget()
        _regex_layout = QtWidgets.QHBoxLayout(_regex_row)
        _regex_layout.setContentsMargins(0, 0, 0, 0)
        _regex_layout.setSpacing(4)
        _regex_layout.addWidget(self._regex_check)
        _regex_layout.addWidget(_regex_help)
        _regex_layout.addStretch()
        search_grid.addWidget(_regex_row, 2, 2, 1, 2)

        # Search button — row 3, spanning full width, right-aligned
        self._search_btn = PrimaryPushButton("Search All Zones")
        self._search_btn.setDefault(True)
        self._search_btn.clicked.connect(self._run_search)
        search_grid.addWidget(self._search_btn, 3, 0, 1, 4,
                               Qt.AlignmentFlag.AlignRight)

        search_grid.setColumnStretch(1, 1)
        search_grid.setColumnStretch(3, 0)
        left_layout.addWidget(search_group)

        # ── Results label ─────────────────────────────────────────────
        self._results_label = QtWidgets.QLabel("Run a search to see matching records.")
        left_layout.addWidget(self._results_label)

        # ── Results table ─────────────────────────────────────────────
        self._table = TableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["Zone", "Subname", "Type", "TTL", "Content"]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._table.setAlternatingRowColors(True)
        for col in (COL_ZONE, COL_SUBNAME, COL_TYPE, COL_TTL):
            self._table.horizontalHeader().setSectionResizeMode(
                col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
            )
        self._table.horizontalHeader().setSectionResizeMode(
            COL_CONTENT, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self._table.itemSelectionChanged.connect(self._update_action_btns)
        left_layout.addWidget(self._table, 1)

        # ── Selection row ─────────────────────────────────────────────
        sel_row = QtWidgets.QHBoxLayout()
        self._select_all_btn = PushButton("Select All")
        self._select_all_btn.clicked.connect(self._select_all)
        sel_row.addWidget(self._select_all_btn)

        self._select_none_btn = PushButton("Select None")
        self._select_none_btn.clicked.connect(self._select_none)
        sel_row.addWidget(self._select_none_btn)

        sel_row.addStretch()

        self._export_btn = PushButton("Export Results…")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._export_results)
        sel_row.addWidget(self._export_btn)
        left_layout.addLayout(sel_row)

        # ── Progress row ──────────────────────────────────────────────
        progress_row = QtWidgets.QHBoxLayout()
        self._progress_bar = ProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setVisible(False)
        progress_row.addWidget(self._progress_bar)
        self._status_label = QtWidgets.QLabel("")
        progress_row.addWidget(self._status_label)
        left_layout.addLayout(progress_row)

        splitter.addWidget(left_widget)

        # ==============================================================
        # Right pane — Actions
        # ==============================================================
        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        right_layout.setContentsMargins(6, 6, 6, 6)
        right_layout.setSpacing(6)

        # ── Title row ─────────────────────────────────────────────────
        actions_title_row = QtWidgets.QHBoxLayout()
        actions_title_row.addWidget(StrongBodyLabel("Actions"))
        actions_title_row.addStretch()
        right_layout.addLayout(actions_title_row)

        # ── Replace Content group ─────────────────────────────────────
        self._replace_group = QtWidgets.QGroupBox("Replace Content")
        replace_form = QtWidgets.QFormLayout(self._replace_group)

        self._find_edit = LineEdit()
        self._find_edit.setPlaceholderText("Find…")
        replace_form.addRow("Find:", self._find_edit)

        self._replace_edit = LineEdit()
        self._replace_edit.setPlaceholderText("Replace with…")
        replace_form.addRow("Replace:", self._replace_edit)

        self._new_sub_edit = LineEdit()
        self._new_sub_edit.setPlaceholderText("New subname  (blank = no change)")
        replace_form.addRow("Subname:", self._new_sub_edit)

        self._new_ttl_edit = LineEdit()
        self._new_ttl_edit.setPlaceholderText("New TTL  (blank = no change)")
        self._new_ttl_edit.setMaximumWidth(140)
        replace_form.addRow("TTL:", self._new_ttl_edit)

        apply_btn_row = QtWidgets.QHBoxLayout()
        apply_btn_row.addStretch()
        self._apply_btn = PrimaryPushButton("Apply to Selected")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._run_replace)
        apply_btn_row.addWidget(self._apply_btn)
        replace_form.addRow(apply_btn_row)

        right_layout.addWidget(self._replace_group)

        # ── Delete Records group ──────────────────────────────────────
        self._delete_group = QtWidgets.QGroupBox("Delete Records")
        delete_layout = QtWidgets.QVBoxLayout(self._delete_group)
        delete_layout.addWidget(QtWidgets.QLabel(
            "Permanently delete the selected records from their zones."
        ))
        delete_btn_row = QtWidgets.QHBoxLayout()
        delete_btn_row.addStretch()
        self._delete_btn = PushButton("Delete Selected")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._run_delete)
        delete_btn_row.addWidget(self._delete_btn)
        delete_layout.addLayout(delete_btn_row)
        right_layout.addWidget(self._delete_group)

        # ── Change Log group ──────────────────────────────────────────
        self._log_group = QtWidgets.QGroupBox("Change Log")
        log_layout = QtWidgets.QVBoxLayout(self._log_group)
        self._log_edit = PlainTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setFont(QtGui.QFont("Monospace", 9))
        log_layout.addWidget(self._log_edit)

        log_btn_row = QtWidgets.QHBoxLayout()
        log_btn_row.addStretch()
        clear_log_btn = PushButton("Clear Log")
        clear_log_btn.clicked.connect(self._log_edit.clear)
        log_btn_row.addWidget(clear_log_btn)
        log_layout.addLayout(log_btn_row)
        right_layout.addWidget(self._log_group, 1)

        splitter.addWidget(right_widget)

        # ── Splitter sizing ───────────────────────────────────────────
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([760, 340])

        self.setStyleSheet(container_qss())
        self._set_replace_enabled(False)

    def showEvent(self, event):
        super().showEvent(event)
        self.setStyleSheet(container_qss())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_delete_drawer'):
            self._delete_drawer.reposition(event.size())
        if hasattr(self, '_confirm_drawer'):
            self._confirm_drawer.reposition(event.size())
        if hasattr(self, '_notify_drawer'):
            self._notify_drawer.reposition(event.size())

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _run_search(self):
        filter_type = self._type_combo.currentText()
        if filter_type.startswith('('):
            filter_type = ''

        # Validate regex before starting worker
        if self._regex_check.isChecked():
            for label, text in [
                ("Subname", self._sub_edit.text()),
                ("Content", self._content_edit.text()),
                ("Zone",    self._zone_edit.text()),
            ]:
                if text.strip():
                    try:
                        re.compile(text)
                    except re.error as e:
                        self._notify_drawer.warning(
                            "Invalid Regex",
                            f"{label} filter contains an invalid regular expression:\n{e}"
                        )
                        return
                    # Reject patterns with nested quantifiers (ReDoS risk)
                    if re.search(r'[+*]\)?[+*]', text):
                        self._notify_drawer.warning(
                            "Unsafe Regex",
                            f"{label} filter contains nested quantifiers (e.g. (a+)+) "
                            f"which can cause catastrophic backtracking. "
                            f"Please simplify the pattern."
                        )
                        return

        self._table.setRowCount(0)
        self._results_label.setText("Searching…")
        self._search_btn.setEnabled(False)
        self._set_replace_enabled(False)
        self._export_btn.setEnabled(False)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._status_label.setText("")

        # Bump generation to invalidate stale prefetch callbacks
        self._search_generation += 1

        # Determine which zones need pre-fetching
        self._pending_search_args = (
            self._sub_edit.text(), filter_type,
            self._content_edit.text(), self._ttl_edit.text(),
            self._zone_edit.text(), self._regex_check.isChecked(),
        )

        queue_online = self.api_queue and not self.api_queue.is_paused

        if queue_online:
            # Find zones that don't have cached records yet
            zones_result = self.cache_manager.get_cached_zones()
            if zones_result and isinstance(zones_result, tuple):
                zones_data, _ = zones_result
            else:
                zones_data = []

            zone_filter = self._zone_edit.text().strip()
            use_regex = self._regex_check.isChecked()
            uncached = []
            for z in zones_data:
                zn = z.get('name', '')
                if not zn:
                    continue
                if zone_filter:
                    if use_regex:
                        try:
                            if not re.search(zone_filter, zn, re.IGNORECASE):
                                continue
                        except re.error:
                            continue
                    else:
                        if zone_filter.lower() not in zn.lower():
                            continue
                cached = self.cache_manager.get_cached_records(zn)
                if not cached or not cached[0]:
                    uncached.append(zn)

            if uncached:
                self._prefetch_remaining = len(uncached)
                gen = self._search_generation
                self._status_label.setText(f"Pre-fetching {len(uncached)} uncached zone(s)…")
                for zn in uncached:
                    def _make_cb(zone_name, generation):
                        def _cb(success, data):
                            # Ignore stale callbacks from a superseded search
                            if generation != self._search_generation:
                                return
                            if success and isinstance(data, list):
                                self.cache_manager.cache_records(zone_name, data)
                            self._prefetch_remaining -= 1
                            if self._prefetch_remaining <= 0:
                                self._start_search_worker()
                        return _cb

                    item = QueueItem(
                        priority=PRIORITY_NORMAL,
                        category="records",
                        action=f"Pre-fetch records for {zn}",
                        callable=self.api_client.get_records,
                        args=(zn,),
                        callback=_make_cb(zn, gen),
                    )
                    self.api_queue.enqueue(item)
                return

        self._start_search_worker()

    def _start_search_worker(self):
        """Launch the search worker using the saved search arguments."""
        args = self._pending_search_args
        self._search_worker = _SearchWorker(
            self.api_client, self.cache_manager,
            args[0], args[1], args[2], args[3], args[4], args[5],
        )
        self._search_worker.progress_update.connect(self._on_progress)
        self._search_worker.finished.connect(self._on_search_done)
        self._search_worker.start()

    def _on_search_done(self, success, message, matches):
        self._search_btn.setEnabled(True)
        self._progress_bar.setVisible(False)
        self._status_label.setText("")

        if not success:
            self._results_label.setText(message)
            self._results_count_label.setText("0 results")
            return

        self._results_label.setText(message)
        self._results_count_label.setText(f"{len(matches)} results")
        self._populate_table(matches)
        self._set_replace_enabled(bool(matches))
        self._export_btn.setEnabled(bool(matches))

    def _populate_table(self, matches):
        self._table.setRowCount(0)
        self._results_count_label.setText(f"{len(matches)} results")

        for match in matches:
            row = self._table.rowCount()
            self._table.insertRow(row)

            zone_item = QtWidgets.QTableWidgetItem(match['zone'])
            zone_item.setData(Qt.ItemDataRole.UserRole, match)
            self._table.setItem(row, COL_ZONE,    zone_item)
            self._table.setItem(row, COL_SUBNAME, QtWidgets.QTableWidgetItem(match.get('subname', '') or '@'))
            self._table.setItem(row, COL_TYPE,    QtWidgets.QTableWidgetItem(match.get('type', '')))
            self._table.setItem(row, COL_TTL,     QtWidgets.QTableWidgetItem(str(match.get('ttl', ''))))

            content_str  = '  |  '.join(match.get('records', []))
            content_item = QtWidgets.QTableWidgetItem(
                content_str[:80] + ('…' if len(content_str) > 80 else '')
            )
            content_item.setToolTip(content_str)
            self._table.setItem(row, COL_CONTENT, content_item)

        self._update_action_btns()

    # ------------------------------------------------------------------
    # Replace
    # ------------------------------------------------------------------

    def _run_replace(self):
        items = self._checked_items()
        if not items:
            self._notify_drawer.info("No Selection", "No rows are selected.")
            return
        if not self.api_queue or self.api_queue.is_paused:
            self._notify_drawer.warning("Offline", "Cannot apply changes while offline.")
            return

        content_find = self._find_edit.text()
        content_replace = self._replace_edit.text()
        new_sub      = self._new_sub_edit.text().strip()
        new_ttl      = self._new_ttl_edit.text().strip()

        if not content_find and not new_sub and not new_ttl:
            self._notify_drawer.warning(
                "Nothing to Replace",
                "Specify at least one replacement: content find, subname, or TTL."
            )
            return

        # Validate TTL before enqueuing
        if new_ttl:
            try:
                int(new_ttl)
            except ValueError:
                self._notify_drawer.warning("Invalid TTL", f"'{new_ttl}' is not a valid integer.")
                return

        # Capture items for use in the confirmation callback
        confirmed_items = items

        def _do_replace():
            self._execute_replace(confirmed_items)

        self._confirm_drawer.ask(
            title="Confirm Replace",
            message=f"Apply changes to {len(items)} checked record(s)?\n\nThis cannot be undone.",
            on_confirm=_do_replace,
            confirm_text="Apply Changes",
        )

    def _execute_replace(self, items):
        self._set_busy(True)

        total = len(items)
        state = {'updated': 0, 'failed': 0, 'done': 0, 'dirty_zones': set()}

        def _finish_check():
            state['done'] += 1
            pct = int((state['done'] / total) * 100) if total else 100
            self._progress_bar.setValue(pct)
            if state['done'] >= total:
                for zone in state['dirty_zones']:
                    self.cache_manager.clear_domain_cache(zone)
                self._on_operation_done(state['updated'], state['failed'], "Replace")

        for row_idx, match in items:
            zone = match['zone']
            sub = match.get('subname', '') or ''
            rtype = match['type']
            ttl = match['ttl']
            records_list = list(match.get('records', []))
            label = f"[{zone}] {sub or '@'} {rtype}"

            # Compute new values locally
            new_records = records_list
            if content_find:
                new_records = [v.replace(content_find, content_replace) for v in records_list]
                if any(v.strip() == '' for v in new_records):
                    self._on_record_done(row_idx, False, "Replacement would produce empty record values")
                    self._append_log(f"SKIPPED  {label} — empty content after replace")
                    state['failed'] += 1
                    _finish_check()
                    continue

            effective_ttl = ttl
            if new_ttl:
                effective_ttl = int(new_ttl)

            is_rename = bool(new_sub and new_sub != sub)

            if is_rename:
                # Subname rename: create new + delete old, chained via callback
                def _make_rename_cb(r_idx, lbl, z, old_sub, rt):
                    def _on_create(success, result):
                        if not success:
                            msg = result.get('message', str(result)) if isinstance(result, dict) else str(result)
                            self._on_record_done(r_idx, False, f"Create failed: {msg}")
                            state['failed'] += 1
                            state['dirty_zones'].add(z)
                            _finish_check()
                            return
                        # Chain: delete old record
                        del_item = QueueItem(
                            priority=PRIORITY_NORMAL,
                            category="records",
                            action=f"Delete old {lbl} (rename)",
                            callable=self.api_client.delete_record,
                            args=(z, old_sub, rt),
                            callback=_make_delete_after_rename_cb(r_idx, lbl, z),
                        )
                        self.api_queue.enqueue(del_item)
                    return _on_create

                def _make_delete_after_rename_cb(r_idx, lbl, z):
                    def _on_del(success, result):
                        state['dirty_zones'].add(z)
                        if not success:
                            msg = result.get('message', str(result)) if isinstance(result, dict) else str(result)
                            logger.warning(f"Delete old rrset failed after rename: {msg}")
                        state['updated'] += 1
                        self._on_record_done(r_idx, True, "Renamed")
                        self._append_log(f"RENAME   {lbl} → {new_sub}")
                        _finish_check()
                    return _on_del

                create_item = QueueItem(
                    priority=PRIORITY_NORMAL,
                    category="records",
                    action=f"Create {new_sub}.{zone} {rtype} (rename)",
                    callable=self.api_client.create_record,
                    args=(zone, new_sub, rtype, effective_ttl, new_records),
                    callback=_make_rename_cb(row_idx, label, zone, sub, rtype),
                )
                self.api_queue.enqueue(create_item)
            elif new_records != records_list or effective_ttl != ttl:
                # Content / TTL update
                def _make_update_cb(r_idx, lbl, z, old_ttl, old_records):
                    def _on_update(success, result):
                        state['dirty_zones'].add(z)
                        if success:
                            state['updated'] += 1
                            self._on_record_done(r_idx, True, "Updated")
                            if content_find:
                                old_c = '  |  '.join(old_records)
                                new_c = '  |  '.join(
                                    v.replace(content_find, content_replace) for v in old_records
                                )
                                self._append_log(
                                    f"CONTENT  {lbl}\n         old: {old_c}\n         new: {new_c}"
                                )
                            if new_ttl and int(new_ttl) != old_ttl:
                                self._append_log(f"TTL      {lbl}: {old_ttl} → {new_ttl}")
                        else:
                            state['failed'] += 1
                            msg = result.get('message', str(result)) if isinstance(result, dict) else str(result)
                            self._on_record_done(r_idx, False, msg)
                        _finish_check()
                    return _on_update

                update_item = QueueItem(
                    priority=PRIORITY_NORMAL,
                    category="records",
                    action=f"Update {sub or '@'}.{zone} {rtype}",
                    callable=self.api_client.update_record,
                    args=(zone, sub, rtype, effective_ttl, new_records),
                    callback=_make_update_cb(row_idx, label, zone, ttl, records_list),
                )
                self.api_queue.enqueue(update_item)
            else:
                # No actual change needed
                self._on_record_done(row_idx, True, "No change")
                state['updated'] += 1
                _finish_check()

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def _run_delete(self):
        items = self._checked_items()
        if not items:
            self._notify_drawer.info("No Selection", "No rows are selected.")
            return
        if not self.api_queue or self.api_queue.is_paused:
            self._notify_drawer.warning("Offline", "Cannot delete records while offline.")
            return

        count = len(items)
        record_labels = [
            f"[{match['zone']}] {match.get('subname', '') or '@'} {match['type']}"
            for _, match in items
        ]

        def _do_delete():
            self._set_busy(True)
            total = len(items)
            state = {'deleted': 0, 'failed': 0, 'done': 0, 'dirty_zones': set()}

            def _make_cb(r_idx, lbl, z, sub, rtype):
                def _on_del(success, result):
                    state['dirty_zones'].add(z)
                    state['done'] += 1
                    pct = int((state['done'] / total) * 100) if total else 100
                    self._progress_bar.setValue(pct)
                    if success:
                        state['deleted'] += 1
                        self._on_record_done(r_idx, True, "Deleted")
                        self._append_log(f"DELETED  {lbl}")
                    else:
                        state['failed'] += 1
                        msg = result.get('message', str(result)) if isinstance(result, dict) else str(result)
                        self._on_record_done(r_idx, False, msg)
                    if state['done'] >= total:
                        for zone in state['dirty_zones']:
                            self.cache_manager.clear_domain_cache(zone)
                        self._on_operation_done(state['deleted'], state['failed'], "Delete")
                return _on_del

            for row_idx, match in items:
                zone = match['zone']
                sub = match.get('subname', '') or ''
                rtype = match['type']
                label = f"[{zone}] {sub or '@'} {rtype}"

                del_item = QueueItem(
                    priority=PRIORITY_NORMAL,
                    category="records",
                    action=f"Delete {sub or '@'}.{zone} {rtype}",
                    callable=self.api_client.delete_record,
                    args=(zone, sub, rtype),
                    callback=_make_cb(row_idx, label, zone, sub, rtype),
                )
                self.api_queue.enqueue(del_item)

        self._delete_drawer.ask(
            title="Delete Records",
            message=f"Permanently delete {count} checked record(s)? This cannot be undone.",
            items=record_labels,
            on_confirm=_do_delete,
            confirm_text=f"Delete {count} Records",
        )

    # ------------------------------------------------------------------
    # Export results
    # ------------------------------------------------------------------

    def _export_results(self):
        rows = self._all_rows()
        if not rows:
            return

        path, selected_filter = QFileDialog.getSaveFileName(
            self, "Export Results", "search_results",
            "CSV Files (*.csv);;JSON Files (*.json)"
        )
        if not path:
            return

        try:
            if path.endswith('.json') or 'JSON' in selected_filter:
                self._export_json(path, rows)
            else:
                self._export_csv(path, rows)
            self._status_label.setText(f"Exported {len(rows)} record(s) to {path}")
        except Exception as e:
            self._notify_drawer.error("Export Failed", f"Could not write file:\n{e}")

    def _export_json(self, path, rows):
        data = [
            {
                'zone':    r['zone'],
                'subname': r.get('subname', '') or '@',
                'type':    r.get('type', ''),
                'ttl':     r.get('ttl', ''),
                'records': r.get('records', []),
            }
            for r in rows
        ]
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def _export_csv(self, path, rows):
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Zone', 'Subname', 'Type', 'TTL', 'Content'])
            for r in rows:
                writer.writerow([
                    r['zone'],
                    r.get('subname', '') or '@',
                    r.get('type', ''),
                    r.get('ttl', ''),
                    '  |  '.join(r.get('records', [])),
                ])

    def _all_rows(self):
        result = []
        for row in range(self._table.rowCount()):
            item = self._table.item(row, COL_ZONE)
            if item:
                match = item.data(Qt.ItemDataRole.UserRole)
                if match:
                    result.append(match)
        return result

    # ------------------------------------------------------------------
    # Shared operation callbacks
    # ------------------------------------------------------------------

    def _on_record_done(self, row_idx, success, msg):
        base = self._table.palette().color(QtGui.QPalette.ColorRole.Base)
        tint = QtGui.QColor(0, 180, 0) if success else QtGui.QColor(200, 0, 0)
        color = QtGui.QColor(
            int(tint.red()   * 0.20 + base.red()   * 0.80),
            int(tint.green() * 0.20 + base.green() * 0.80),
            int(tint.blue()  * 0.20 + base.blue()  * 0.80),
        )
        for col in range(self._table.columnCount()):
            item = self._table.item(row_idx, col)
            if item:
                item.setBackground(color)
                if not success and col == COL_CONTENT:
                    item.setToolTip(f"Error: {msg}")

    def _on_operation_done(self, count, failed, op_name):
        self._set_busy(False)
        summary = f"{count} {op_name.lower()}d"
        if failed:
            summary += f", {failed} failed"
        self._status_label.setText(summary)
        self._results_label.setText(
            f"{op_name} complete — {summary}. Re-run search to refresh results."
        )

    def _append_log(self, entry):
        self._log_edit.appendPlainText(entry)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _on_progress(self, pct, msg):
        self._progress_bar.setValue(pct)
        self._status_label.setText(msg)

    def _select_all(self):
        self._table.selectAll()

    def _select_none(self):
        self._table.clearSelection()

    def _checked_items(self):
        result = []
        seen = set()
        for idx in self._table.selectedIndexes():
            row = idx.row()
            if row in seen:
                continue
            seen.add(row)
            item = self._table.item(row, COL_ZONE)
            if item:
                match = item.data(Qt.ItemDataRole.UserRole)
                if match:
                    result.append((row, match))
        return result

    def _update_action_btns(self):
        has_sel   = len(set(idx.row() for idx in self._table.selectedIndexes())) > 0
        is_online = self.api_queue and not self.api_queue.is_paused
        can_act   = has_sel and is_online
        self._apply_btn.setEnabled(can_act)
        self._delete_btn.setEnabled(can_act)
        tip = "Cannot modify records while offline." if (has_sel and not is_online) else ""
        self._apply_btn.setToolTip(tip)
        self._delete_btn.setToolTip(tip)

    def _set_replace_enabled(self, enabled):
        self._replace_group.setEnabled(enabled)
        self._delete_group.setEnabled(enabled)
        if not enabled:
            self._apply_btn.setEnabled(False)
            self._delete_btn.setEnabled(False)

    def _set_busy(self, busy):
        self._search_btn.setEnabled(not busy)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(busy)
        if not busy:
            self._update_action_btns()

    def hideEvent(self, event):
        if self._search_worker and self._search_worker.isRunning():
            self._search_worker.quit()
            self._search_worker.wait(2000)
        super().hideEvent(event)
