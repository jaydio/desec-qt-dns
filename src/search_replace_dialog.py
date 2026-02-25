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
from PySide6.QtWidgets import QFileDialog, QMessageBox
from qfluentwidgets import (PushButton, LineEdit, CheckBox,
                             ProgressBar, PlainTextEdit, TableWidget,
                             LargeTitleLabel)
from fluent_styles import container_qss
from confirm_drawer import DeleteConfirmDrawer
from notify_drawer import NotifyDrawer

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
            self.finished.emit(
                True,
                f"{len(matches)} record(s) found across {zones_hit} zone(s).",
                matches,
            )
        except Exception as e:
            logger.error(f"Search worker error: {e}")
            self.finished.emit(False, f"Search failed: {e}", [])

    def _load_records(self, zone_name):
        cached = self.cache_manager.get_cached_records(zone_name)
        if cached and isinstance(cached, tuple):
            records, _ = cached
            if records:
                return records
        if self.api_client.is_online:
            success, data = self.api_client.get_records(zone_name)
            if success and isinstance(data, list):
                self.cache_manager.cache_records(zone_name, data)
                return data
        return []

    def _matches(self, record):
        subname = record.get('subname', '') or ''
        rtype   = record.get('type', '')
        ttl     = record.get('ttl', 0)
        content = '\n'.join(record.get('records', []))

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
# Replace worker
# ---------------------------------------------------------------------------

class _ReplaceWorker(QThread):
    progress_update = Signal(int, str)
    record_done     = Signal(int, bool, str)
    change_logged   = Signal(str)
    finished        = Signal(int, int)

    def __init__(self, api_client, cache_manager, items,
                 content_find, content_replace, new_subname, new_ttl):
        super().__init__()
        self.api_client      = api_client
        self.cache_manager   = cache_manager
        self.items           = items
        self.content_find    = content_find
        self.content_replace = content_replace
        self.new_subname     = new_subname.strip()
        self.new_ttl         = new_ttl.strip()

    def run(self):
        total       = len(self.items)
        updated     = 0
        failed      = 0
        dirty_zones = set()

        for idx, (row_idx, match) in enumerate(self.items):
            pct  = int((idx / total) * 100) if total else 100
            zone = match['zone']
            sub  = match.get('subname', '') or ''
            rtype = match['type']
            ttl  = match['ttl']
            records_list = list(match.get('records', []))
            label = f"[{zone}] {sub or '@'} {rtype}"

            self.progress_update.emit(pct, f"Updating {sub or '@'}.{zone} {rtype}…")

            success, err = self._apply(zone, sub, rtype, ttl, records_list)
            dirty_zones.add(zone)

            if success:
                updated += 1
                self._emit_change_log(label, sub, rtype, ttl, records_list)
                self.record_done.emit(row_idx, True, "Updated")
            else:
                failed += 1
                self.record_done.emit(row_idx, False, err)

        for zone in dirty_zones:
            self.cache_manager.clear_domain_cache(zone)

        self.progress_update.emit(100, "Done.")
        self.finished.emit(updated, failed)

    def _emit_change_log(self, label, sub, rtype, old_ttl, old_records):
        old_content = '  |  '.join(old_records)
        if self.content_find:
            new_content = '  |  '.join(
                v.replace(self.content_find, self.content_replace) for v in old_records
            )
            self.change_logged.emit(
                f"CONTENT  {label}\n"
                f"         old: {old_content}\n"
                f"         new: {new_content}"
            )
        if self.new_subname and self.new_subname != sub:
            self.change_logged.emit(
                f"RENAME   {label} → [{label.split(']')[0].lstrip('[')}"
                f"] {self.new_subname} {rtype}"
            )
        if self.new_ttl:
            try:
                new_ttl = int(self.new_ttl)
                if new_ttl != old_ttl:
                    self.change_logged.emit(
                        f"TTL      {label}: {old_ttl} → {new_ttl}"
                    )
            except ValueError:
                pass

    def _apply(self, zone, sub, rtype, ttl, records_list):
        new_records = records_list
        if self.content_find:
            new_records = [
                v.replace(self.content_find, self.content_replace)
                for v in records_list
            ]
            if any(v.strip() == '' for v in new_records):
                return False, "Replacement would produce empty record values — not allowed."

        new_ttl = ttl
        if self.new_ttl:
            try:
                new_ttl = int(self.new_ttl)
            except ValueError:
                return False, f"Invalid TTL value: {self.new_ttl}"

        if self.new_subname and self.new_subname != sub:
            ok, result = self.api_client.create_record(
                zone, self.new_subname, rtype, new_ttl, new_records
            )
            if not ok:
                msg = result.get('message', str(result)) if isinstance(result, dict) else str(result)
                return False, f"Create failed: {msg}"
            ok2, result2 = self.api_client.delete_record(zone, sub, rtype)
            if not ok2:
                msg2 = result2.get('message', str(result2)) if isinstance(result2, dict) else str(result2)
                logger.warning(f"Delete old rrset failed after rename: {msg2}")
            return True, ""

        if new_records != records_list or new_ttl != ttl:
            ok, result = self.api_client.update_record(zone, sub, rtype, new_ttl, new_records)
            if not ok:
                msg = result.get('message', str(result)) if isinstance(result, dict) else str(result)
                return False, msg

        return True, ""


# ---------------------------------------------------------------------------
# Delete worker
# ---------------------------------------------------------------------------

class _DeleteWorker(QThread):
    progress_update = Signal(int, str)
    record_done     = Signal(int, bool, str)
    change_logged   = Signal(str)
    finished        = Signal(int, int)

    def __init__(self, api_client, cache_manager, items):
        super().__init__()
        self.api_client    = api_client
        self.cache_manager = cache_manager
        self.items         = items

    def run(self):
        total       = len(self.items)
        deleted     = 0
        failed      = 0
        dirty_zones = set()

        for idx, (row_idx, match) in enumerate(self.items):
            pct   = int((idx / total) * 100) if total else 100
            zone  = match['zone']
            sub   = match.get('subname', '') or ''
            rtype = match['type']

            self.progress_update.emit(pct, f"Deleting {sub or '@'}.{zone} {rtype}…")

            ok, result = self.api_client.delete_record(zone, sub, rtype)
            dirty_zones.add(zone)

            if ok:
                deleted += 1
                self.change_logged.emit(f"DELETED  [{zone}] {sub or '@'} {rtype}")
                self.record_done.emit(row_idx, True, "Deleted")
            else:
                failed += 1
                msg = result.get('message', str(result)) if isinstance(result, dict) else str(result)
                self.record_done.emit(row_idx, False, msg)

        for zone in dirty_zones:
            self.cache_manager.clear_domain_cache(zone)

        self.progress_update.emit(100, "Done.")
        self.finished.emit(deleted, failed)


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------

class SearchReplaceInterface(QtWidgets.QWidget):
    """
    Global Search & Replace page (Fluent sidebar navigation).
    Searches records across all zones by subname/type/content/TTL/zone,
    previews matches with checkboxes, then applies bulk replacements or deletions.
    """

    def __init__(self, api_client, cache_manager, parent=None):
        super().__init__(parent)
        self.setObjectName("searchReplaceInterface")
        self.api_client      = api_client
        self.cache_manager   = cache_manager
        self._search_worker  = None
        self._replace_worker = None
        self._delete_worker  = None
        self._setup_ui()
        self._delete_drawer = DeleteConfirmDrawer(parent=self)
        self._notify_drawer = NotifyDrawer(parent=self)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(36, 20, 36, 20)
        outer.setSpacing(8)

        outer.addWidget(LargeTitleLabel("Search & Replace"))

        # ── Search group ──────────────────────────────────────────────
        search_group = QtWidgets.QGroupBox("Search")
        search_grid  = QtWidgets.QGridLayout(search_group)

        search_grid.addWidget(QtWidgets.QLabel("Subname contains:"), 0, 0)
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

        search_grid.addWidget(QtWidgets.QLabel("Content contains:"), 1, 0)
        self._content_edit = LineEdit()
        self._content_edit.setPlaceholderText("e.g. 1.2.3.4  (blank = any)")
        self._content_edit.returnPressed.connect(self._run_search)
        search_grid.addWidget(self._content_edit, 1, 1)

        search_grid.addWidget(QtWidgets.QLabel("TTL equals:"), 1, 2)
        self._ttl_edit = LineEdit()
        self._ttl_edit.setPlaceholderText("e.g. 3600  (blank = any)")
        self._ttl_edit.setMaximumWidth(120)
        self._ttl_edit.returnPressed.connect(self._run_search)
        search_grid.addWidget(self._ttl_edit, 1, 3)

        search_grid.addWidget(QtWidgets.QLabel("Zone contains:"), 2, 0)
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

        self._search_btn = PushButton("Search All Zones")
        self._search_btn.setDefault(True)
        self._search_btn.clicked.connect(self._run_search)
        search_grid.addWidget(self._search_btn, 0, 4, 3, 1,
                               Qt.AlignmentFlag.AlignVCenter)

        search_grid.setColumnStretch(1, 1)
        search_grid.setColumnStretch(3, 0)
        outer.addWidget(search_group)

        # ── Results group ─────────────────────────────────────────────
        results_group = QtWidgets.QGroupBox("Results")
        results_layout = QtWidgets.QVBoxLayout(results_group)

        self._results_label = QtWidgets.QLabel("Run a search to see matching records.")
        results_layout.addWidget(self._results_label)

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
        results_layout.addWidget(self._table)

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

        results_layout.addLayout(sel_row)
        outer.addWidget(results_group, 1)

        # ── Replace group ─────────────────────────────────────────────
        self._replace_group = QtWidgets.QGroupBox("Replace / Delete (applies to selected rows)")
        replace_grid = QtWidgets.QGridLayout(self._replace_group)

        replace_grid.addWidget(QtWidgets.QLabel("Content:"), 0, 0)
        find_row = QtWidgets.QHBoxLayout()
        self._find_edit = LineEdit()
        self._find_edit.setPlaceholderText("Find…")
        find_row.addWidget(self._find_edit)
        find_row.addWidget(QtWidgets.QLabel("→"))
        self._replace_edit = LineEdit()
        self._replace_edit.setPlaceholderText("Replace with…")
        find_row.addWidget(self._replace_edit)
        replace_grid.addLayout(find_row, 0, 1, 1, 3)

        replace_grid.addWidget(QtWidgets.QLabel("Subname:"), 1, 0)
        self._new_sub_edit = LineEdit()
        self._new_sub_edit.setPlaceholderText("New subname  (blank = no change)")
        replace_grid.addWidget(self._new_sub_edit, 1, 1)

        replace_grid.addWidget(QtWidgets.QLabel("TTL:"), 1, 2)
        self._new_ttl_edit = LineEdit()
        self._new_ttl_edit.setPlaceholderText("New TTL  (blank = no change)")
        self._new_ttl_edit.setMaximumWidth(140)
        replace_grid.addWidget(self._new_ttl_edit, 1, 3)

        # Stacked action buttons
        btn_col = QtWidgets.QVBoxLayout()
        btn_col.setSpacing(6)
        self._apply_btn = PushButton("Apply to Selected")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._run_replace)
        btn_col.addWidget(self._apply_btn)

        self._delete_btn = PushButton("Delete Selected")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._run_delete)
        btn_col.addWidget(self._delete_btn)

        replace_grid.addLayout(btn_col, 0, 4, 2, 1,
                                Qt.AlignmentFlag.AlignVCenter)
        replace_grid.setColumnStretch(1, 1)
        outer.addWidget(self._replace_group)

        # ── Change Log group ──────────────────────────────────────────
        self._log_group = QtWidgets.QGroupBox("Change Log")
        log_layout = QtWidgets.QVBoxLayout(self._log_group)
        self._log_edit = PlainTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setFont(QtGui.QFont("Monospace", 9))
        self._log_edit.setFixedHeight(110)
        log_layout.addWidget(self._log_edit)

        log_btn_row = QtWidgets.QHBoxLayout()
        log_btn_row.addStretch()
        clear_log_btn = PushButton("Clear Log")
        clear_log_btn.clicked.connect(self._log_edit.clear)
        log_btn_row.addWidget(clear_log_btn)
        log_layout.addLayout(log_btn_row)

        self._log_group.setVisible(False)
        outer.addWidget(self._log_group)

        # ── Progress + bottom ─────────────────────────────────────────
        progress_row = QtWidgets.QHBoxLayout()
        self._progress_bar = ProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setVisible(False)
        progress_row.addWidget(self._progress_bar)
        self._status_label = QtWidgets.QLabel("")
        progress_row.addWidget(self._status_label)
        outer.addLayout(progress_row)

        self.setStyleSheet(container_qss())
        self._set_replace_enabled(False)

    def showEvent(self, event):
        super().showEvent(event)
        self.setStyleSheet(container_qss())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_delete_drawer'):
            self._delete_drawer.reposition(event.size())
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

        self._table.setRowCount(0)
        self._results_label.setText("Searching…")
        self._search_btn.setEnabled(False)
        self._set_replace_enabled(False)
        self._export_btn.setEnabled(False)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._status_label.setText("")

        self._search_worker = _SearchWorker(
            self.api_client, self.cache_manager,
            self._sub_edit.text(),
            filter_type,
            self._content_edit.text(),
            self._ttl_edit.text(),
            self._zone_edit.text(),
            self._regex_check.isChecked(),
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
            return

        self._results_label.setText(message)
        self._populate_table(matches)
        self._set_replace_enabled(bool(matches))
        self._export_btn.setEnabled(bool(matches))

    def _populate_table(self, matches):
        self._table.setRowCount(0)

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
        if not self.api_client.is_online:
            self._notify_drawer.warning("Offline", "Cannot apply changes in offline mode.")
            return

        content_find = self._find_edit.text()
        new_sub      = self._new_sub_edit.text().strip()
        new_ttl      = self._new_ttl_edit.text().strip()

        if not content_find and not new_sub and not new_ttl:
            self._notify_drawer.warning(
                "Nothing to Replace",
                "Specify at least one replacement: content find, subname, or TTL."
            )
            return

        confirm = QMessageBox.question(
            self, "Confirm Replace",
            f"Apply changes to {len(items)} checked record(s)?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self._set_busy(True)

        self._replace_worker = _ReplaceWorker(
            self.api_client, self.cache_manager, items,
            content_find, self._replace_edit.text(), new_sub, new_ttl,
        )
        self._replace_worker.progress_update.connect(self._on_progress)
        self._replace_worker.record_done.connect(self._on_record_done)
        self._replace_worker.change_logged.connect(self._append_log)
        self._replace_worker.finished.connect(
            lambda u, f: self._on_operation_done(u, f, "Replace")
        )
        self._replace_worker.start()

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def _run_delete(self):
        items = self._checked_items()
        if not items:
            self._notify_drawer.info("No Selection", "No rows are selected.")
            return
        if not self.api_client.is_online:
            self._notify_drawer.warning("Offline", "Cannot delete records in offline mode.")
            return

        count = len(items)
        record_labels = [
            f"[{match['zone']}] {match.get('subname', '') or '@'} {match['type']}"
            for _, match in items
        ]

        def _do_delete():
            self._set_busy(True)
            self._delete_worker = _DeleteWorker(
                self.api_client, self.cache_manager, items
            )
            self._delete_worker.progress_update.connect(self._on_progress)
            self._delete_worker.record_done.connect(self._on_record_done)
            self._delete_worker.change_logged.connect(self._append_log)
            self._delete_worker.finished.connect(
                lambda d, f: self._on_operation_done(d, f, "Delete")
            )
            self._delete_worker.start()

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
        self._log_group.setVisible(True)
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
        is_online = self.api_client.is_online
        can_act   = has_sel and is_online
        self._apply_btn.setEnabled(can_act)
        self._delete_btn.setEnabled(can_act)
        tip = "Cannot modify records while offline." if (has_sel and not is_online) else ""
        self._apply_btn.setToolTip(tip)
        self._delete_btn.setToolTip(tip)

    def _set_replace_enabled(self, enabled):
        self._replace_group.setEnabled(enabled)
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
        for worker in (self._search_worker, self._replace_worker, self._delete_worker):
            if worker and worker.isRunning():
                worker.quit()
                worker.wait(2000)
        super().hideEvent(event)
