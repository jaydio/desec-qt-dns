#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Global Search & Replace dialog for deSEC Qt DNS Manager.
Searches across all DNS zones and allows bulk replacing content,
subnames, and TTL values.
"""

import logging
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QMessageBox

logger = logging.getLogger(__name__)

DNS_RECORD_TYPES = [
    'A', 'AAAA', 'AFSDB', 'APL', 'CAA', 'CDNSKEY', 'CDS', 'CERT', 'CNAME',
    'DHCID', 'DNAME', 'DNSKEY', 'DLV', 'DS', 'EUI48', 'EUI64', 'HINFO',
    'HTTPS', 'KX', 'L32', 'L64', 'LOC', 'LP', 'MX', 'NAPTR', 'NID', 'NS',
    'OPENPGPKEY', 'PTR', 'RP', 'SMIMEA', 'SPF', 'SRV', 'SSHFP', 'SVCB',
    'TLSA', 'TXT', 'URI',
]

# Table column indices
COL_CHECK   = 0
COL_ZONE    = 1
COL_SUBNAME = 2
COL_TYPE    = 3
COL_TTL     = 4
COL_CONTENT = 5


# ---------------------------------------------------------------------------
# Search worker
# ---------------------------------------------------------------------------

class _SearchWorker(QThread):
    """Loads records from all zones and filters them against the given criteria."""

    progress_update = pyqtSignal(int, str)      # pct, status message
    finished        = pyqtSignal(bool, str, list)  # success, message, matches

    def __init__(self, api_client, cache_manager,
                 filter_subname, filter_type, filter_content, filter_ttl):
        super().__init__()
        self.api_client     = api_client
        self.cache_manager  = cache_manager
        self.filter_subname = filter_subname.strip().lower()
        self.filter_type    = filter_type   # '' means any
        self.filter_content = filter_content.strip().lower()
        self.filter_ttl     = filter_ttl.strip()   # '' means any

    def run(self):
        try:
            # Collect zone names
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

            zone_names = [z.get('name', '') for z in zones_data if z.get('name')]
            total      = len(zone_names)
            matches    = []

            for idx, zone_name in enumerate(zone_names):
                pct = int((idx / total) * 100) if total else 100
                self.progress_update.emit(pct, f"Searching {zone_name}…")

                records = self._load_records(zone_name)
                for record in records:
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
        """Return True if the record satisfies all active filters (AND logic)."""
        subname = record.get('subname', '') or ''
        rtype   = record.get('type', '')
        ttl     = record.get('ttl', 0)
        content = '\n'.join(record.get('records', []))

        if self.filter_subname and self.filter_subname not in subname.lower():
            return False
        if self.filter_type and self.filter_type != rtype:
            return False
        if self.filter_content and self.filter_content not in content.lower():
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
    """Applies content/subname/TTL changes to a list of selected records."""

    progress_update = pyqtSignal(int, str)           # pct, status
    record_done     = pyqtSignal(int, bool, str)     # row_idx, success, message
    finished        = pyqtSignal(int, int)           # updated, failed

    def __init__(self, api_client, cache_manager, items,
                 content_find, content_replace, new_subname, new_ttl):
        """
        Args:
            items: list of (row_idx, match_dict)
            content_find: string to find in content ('' = no content change)
            content_replace: replacement string
            new_subname: new subname value ('' = no change)
            new_ttl: new TTL as string ('' = no change)
        """
        super().__init__()
        self.api_client      = api_client
        self.cache_manager   = cache_manager
        self.items           = items
        self.content_find    = content_find
        self.content_replace = content_replace
        self.new_subname     = new_subname.strip()
        self.new_ttl         = new_ttl.strip()

    def run(self):
        total    = len(self.items)
        updated  = 0
        failed   = 0
        dirty_zones = set()

        for idx, (row_idx, match) in enumerate(self.items):
            pct  = int((idx / total) * 100) if total else 100
            zone = match['zone']
            sub  = match.get('subname', '') or ''
            rtype = match['type']
            ttl  = match['ttl']
            records_list = list(match.get('records', []))

            self.progress_update.emit(pct, f"Updating {sub or '@'}.{zone} {rtype}…")

            success, msg = self._apply(zone, sub, rtype, ttl, records_list)
            dirty_zones.add(zone)

            if success:
                updated += 1
                self.record_done.emit(row_idx, True, "Updated")
            else:
                failed += 1
                self.record_done.emit(row_idx, False, msg)

        # Invalidate cache for all touched zones
        for zone in dirty_zones:
            self.cache_manager.clear_domain_cache(zone)

        self.progress_update.emit(100, "Done.")
        self.finished.emit(updated, failed)

    def _apply(self, zone, sub, rtype, ttl, records_list):
        """Apply the requested changes. Returns (success, error_msg)."""
        # --- Content replace ---
        new_records = records_list
        if self.content_find:
            new_records = [
                v.replace(self.content_find, self.content_replace)
                for v in records_list
            ]

        # --- TTL change ---
        new_ttl = ttl
        if self.new_ttl:
            try:
                new_ttl = int(self.new_ttl)
            except ValueError:
                return False, f"Invalid TTL value: {self.new_ttl}"

        # --- Subname rename ---
        if self.new_subname and self.new_subname != sub:
            # Create new rrset first, then delete old one
            ok, result = self.api_client.create_record(
                zone, self.new_subname, rtype, new_ttl, new_records
            )
            if not ok:
                msg = result.get('message', str(result)) if isinstance(result, dict) else str(result)
                return False, f"Create failed: {msg}"

            ok2, result2 = self.api_client.delete_record(zone, sub, rtype)
            if not ok2:
                msg2 = result2.get('message', str(result2)) if isinstance(result2, dict) else str(result2)
                logger.warning(f"Delete old rrset failed after create: {msg2}")
                # New record exists — report success but log the partial state
            return True, ""

        # --- Content / TTL patch (no subname change) ---
        if new_records != records_list or new_ttl != ttl:
            ok, result = self.api_client.update_record(
                zone, sub, rtype, new_ttl, new_records
            )
            if not ok:
                msg = result.get('message', str(result)) if isinstance(result, dict) else str(result)
                return False, msg

        return True, ""


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------

class SearchReplaceDialog(QtWidgets.QDialog):
    """
    Global Search & Replace dialog.
    Searches records across all zones by subname/type/content/TTL,
    previews matches with checkboxes, then applies bulk replacements.
    """

    def __init__(self, api_client, cache_manager, parent=None):
        super().__init__(parent)
        self.api_client    = api_client
        self.cache_manager = cache_manager
        self._search_worker  = None
        self._replace_worker = None
        self.setWindowTitle("Global Search & Replace")
        self.setModal(True)
        self.setMinimumSize(900, 680)
        self.resize(1060, 740)
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setSpacing(8)

        # ── Search group ──────────────────────────────────────────────
        search_group = QtWidgets.QGroupBox("Search")
        search_grid  = QtWidgets.QGridLayout(search_group)

        search_grid.addWidget(QtWidgets.QLabel("Subname contains:"), 0, 0)
        self._sub_edit = QtWidgets.QLineEdit()
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
        self._content_edit = QtWidgets.QLineEdit()
        self._content_edit.setPlaceholderText("e.g. 1.2.3.4  (blank = any)")
        self._content_edit.returnPressed.connect(self._run_search)
        search_grid.addWidget(self._content_edit, 1, 1)

        search_grid.addWidget(QtWidgets.QLabel("TTL equals:"), 1, 2)
        self._ttl_edit = QtWidgets.QLineEdit()
        self._ttl_edit.setPlaceholderText("e.g. 3600  (blank = any)")
        self._ttl_edit.setMaximumWidth(120)
        self._ttl_edit.returnPressed.connect(self._run_search)
        search_grid.addWidget(self._ttl_edit, 1, 3)

        self._search_btn = QtWidgets.QPushButton("Search All Zones")
        self._search_btn.setDefault(True)
        self._search_btn.clicked.connect(self._run_search)
        search_grid.addWidget(self._search_btn, 0, 4, 2, 1,
                               Qt.AlignmentFlag.AlignVCenter)

        search_grid.setColumnStretch(1, 1)
        search_grid.setColumnStretch(3, 0)
        outer.addWidget(search_group)

        # ── Results group ─────────────────────────────────────────────
        results_group = QtWidgets.QGroupBox("Results")
        results_layout = QtWidgets.QVBoxLayout(results_group)

        self._results_label = QtWidgets.QLabel("Run a search to see matching records.")
        self._results_label.setStyleSheet("color: #888;")
        results_layout.addWidget(self._results_label)

        self._table = QtWidgets.QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["", "Zone", "Subname", "Type", "TTL", "Content"]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.NoSelection
        )
        self._table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        # Column sizing
        self._table.horizontalHeader().setSectionResizeMode(
            COL_CHECK, QtWidgets.QHeaderView.ResizeMode.Fixed
        )
        self._table.setColumnWidth(COL_CHECK, 28)
        for col in (COL_ZONE, COL_SUBNAME, COL_TYPE, COL_TTL):
            self._table.horizontalHeader().setSectionResizeMode(
                col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
            )
        self._table.horizontalHeader().setSectionResizeMode(
            COL_CONTENT, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self._table.itemChanged.connect(self._on_item_changed)
        results_layout.addWidget(self._table)

        sel_row = QtWidgets.QHBoxLayout()
        self._select_all_btn = QtWidgets.QPushButton("Select All")
        self._select_all_btn.clicked.connect(self._select_all)
        sel_row.addWidget(self._select_all_btn)

        self._select_none_btn = QtWidgets.QPushButton("Select None")
        self._select_none_btn.clicked.connect(self._select_none)
        sel_row.addWidget(self._select_none_btn)

        sel_row.addStretch()
        results_layout.addLayout(sel_row)
        outer.addWidget(results_group, 1)   # stretch

        # ── Replace group ─────────────────────────────────────────────
        self._replace_group = QtWidgets.QGroupBox("Replace (applies to checked rows)")
        replace_grid = QtWidgets.QGridLayout(self._replace_group)

        replace_grid.addWidget(QtWidgets.QLabel("Content:"), 0, 0)
        find_row = QtWidgets.QHBoxLayout()
        self._find_edit = QtWidgets.QLineEdit()
        self._find_edit.setPlaceholderText("Find…")
        find_row.addWidget(self._find_edit)
        find_row.addWidget(QtWidgets.QLabel("→"))
        self._replace_edit = QtWidgets.QLineEdit()
        self._replace_edit.setPlaceholderText("Replace with…  (blank = delete match)")
        find_row.addWidget(self._replace_edit)
        replace_grid.addLayout(find_row, 0, 1, 1, 3)

        replace_grid.addWidget(QtWidgets.QLabel("Subname:"), 1, 0)
        self._new_sub_edit = QtWidgets.QLineEdit()
        self._new_sub_edit.setPlaceholderText("New subname  (blank = no change)")
        replace_grid.addWidget(self._new_sub_edit, 1, 1)

        replace_grid.addWidget(QtWidgets.QLabel("TTL:"), 1, 2)
        self._new_ttl_edit = QtWidgets.QLineEdit()
        self._new_ttl_edit.setPlaceholderText("New TTL  (blank = no change)")
        self._new_ttl_edit.setMaximumWidth(140)
        replace_grid.addWidget(self._new_ttl_edit, 1, 3)

        self._apply_btn = QtWidgets.QPushButton("Apply to Selected")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._run_replace)
        replace_grid.addWidget(self._apply_btn, 0, 4, 2, 1,
                                Qt.AlignmentFlag.AlignVCenter)

        replace_grid.setColumnStretch(1, 1)
        outer.addWidget(self._replace_group)

        # ── Progress bar ──────────────────────────────────────────────
        progress_row = QtWidgets.QHBoxLayout()
        self._progress_bar = QtWidgets.QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setVisible(False)
        progress_row.addWidget(self._progress_bar)

        self._status_label = QtWidgets.QLabel("")
        self._status_label.setStyleSheet("color: #555;")
        progress_row.addWidget(self._status_label)
        outer.addLayout(progress_row)

        # ── Bottom row ────────────────────────────────────────────────
        bottom = QtWidgets.QHBoxLayout()
        bottom.addStretch()
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        outer.addLayout(bottom)

        self._set_replace_enabled(False)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _run_search(self):
        filter_type = self._type_combo.currentText()
        if filter_type.startswith('('):
            filter_type = ''

        self._table.setRowCount(0)
        self._results_label.setText("Searching…")
        self._results_label.setStyleSheet("color: #888;")
        self._search_btn.setEnabled(False)
        self._set_replace_enabled(False)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._status_label.setText("")

        self._search_worker = _SearchWorker(
            self.api_client, self.cache_manager,
            self._sub_edit.text(),
            filter_type,
            self._content_edit.text(),
            self._ttl_edit.text(),
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
            self._results_label.setStyleSheet("color: #c62828;")
            return

        self._results_label.setText(message)
        self._results_label.setStyleSheet(
            "color: #2e7d32;" if matches else "color: #888;"
        )
        self._populate_table(matches)
        self._set_replace_enabled(bool(matches))

    def _populate_table(self, matches):
        self._table.blockSignals(True)
        self._table.setRowCount(0)

        for match in matches:
            row = self._table.rowCount()
            self._table.insertRow(row)

            # Checkbox col
            chk = QtWidgets.QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(Qt.CheckState.Checked)
            chk.setData(Qt.ItemDataRole.UserRole, match)
            self._table.setItem(row, COL_CHECK, chk)

            self._table.setItem(row, COL_ZONE,    QtWidgets.QTableWidgetItem(match['zone']))
            self._table.setItem(row, COL_SUBNAME, QtWidgets.QTableWidgetItem(match.get('subname', '') or '@'))
            self._table.setItem(row, COL_TYPE,    QtWidgets.QTableWidgetItem(match.get('type', '')))
            self._table.setItem(row, COL_TTL,     QtWidgets.QTableWidgetItem(str(match.get('ttl', ''))))

            content_str = '  |  '.join(match.get('records', []))
            content_item = QtWidgets.QTableWidgetItem(
                content_str[:80] + ('…' if len(content_str) > 80 else '')
            )
            content_item.setToolTip(content_str)
            self._table.setItem(row, COL_CONTENT, content_item)

        self._table.blockSignals(False)
        self._update_apply_btn()

    # ------------------------------------------------------------------
    # Replace
    # ------------------------------------------------------------------

    def _run_replace(self):
        items = self._checked_items()
        if not items:
            QMessageBox.information(self, "No Selection", "No rows are checked.")
            return

        if not self.api_client.is_online:
            QMessageBox.warning(
                self, "Offline",
                "Cannot apply changes in offline mode."
            )
            return

        # Validate at least one replace operation is specified
        content_find = self._find_edit.text()
        new_sub      = self._new_sub_edit.text().strip()
        new_ttl      = self._new_ttl_edit.text().strip()

        if not content_find and not new_sub and not new_ttl:
            QMessageBox.warning(
                self, "Nothing to Replace",
                "Specify at least one replacement: content find, subname, or TTL."
            )
            return

        # Confirm
        confirm = QMessageBox.question(
            self, "Confirm Replace",
            f"Apply changes to {len(items)} checked record(s)?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self._apply_btn.setEnabled(False)
        self._search_btn.setEnabled(False)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)

        self._replace_worker = _ReplaceWorker(
            self.api_client, self.cache_manager,
            items,
            content_find,
            self._replace_edit.text(),
            new_sub,
            new_ttl,
        )
        self._replace_worker.progress_update.connect(self._on_progress)
        self._replace_worker.record_done.connect(self._on_record_done)
        self._replace_worker.finished.connect(self._on_replace_done)
        self._replace_worker.start()

    def _on_record_done(self, row_idx, success, msg):
        color = QtGui.QColor('#c8e6c9') if success else QtGui.QColor('#ffcdd2')
        for col in range(self._table.columnCount()):
            item = self._table.item(row_idx, col)
            if item:
                item.setBackground(color)
                if not success and col == COL_CONTENT:
                    item.setToolTip(f"Error: {msg}")

    def _on_replace_done(self, updated, failed):
        self._search_btn.setEnabled(True)
        self._progress_bar.setVisible(False)
        self._update_apply_btn()

        summary = f"{updated} updated"
        if failed:
            summary += f", {failed} failed"
        self._status_label.setText(summary)
        self._results_label.setText(
            f"Replace complete — {summary}. Re-run search to refresh results."
        )
        self._results_label.setStyleSheet(
            "color: #2e7d32;" if not failed else "color: #e65100;"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _on_progress(self, pct, msg):
        self._progress_bar.setValue(pct)
        self._status_label.setText(msg)

    def _on_item_changed(self, item):
        if item.column() == COL_CHECK:
            self._update_apply_btn()

    def _select_all(self):
        self._table.blockSignals(True)
        for row in range(self._table.rowCount()):
            chk = self._table.item(row, COL_CHECK)
            if chk:
                chk.setCheckState(Qt.CheckState.Checked)
        self._table.blockSignals(False)
        self._update_apply_btn()

    def _select_none(self):
        self._table.blockSignals(True)
        for row in range(self._table.rowCount()):
            chk = self._table.item(row, COL_CHECK)
            if chk:
                chk.setCheckState(Qt.CheckState.Unchecked)
        self._table.blockSignals(False)
        self._update_apply_btn()

    def _checked_items(self):
        """Return list of (row_idx, match_dict) for all checked rows."""
        result = []
        for row in range(self._table.rowCount()):
            chk = self._table.item(row, COL_CHECK)
            if chk and chk.checkState() == Qt.CheckState.Checked:
                match = chk.data(Qt.ItemDataRole.UserRole)
                if match:
                    result.append((row, match))
        return result

    def _update_apply_btn(self):
        has_checked = any(
            self._table.item(row, COL_CHECK) and
            self._table.item(row, COL_CHECK).checkState() == Qt.CheckState.Checked
            for row in range(self._table.rowCount())
        )
        is_online = self.api_client.is_online
        self._apply_btn.setEnabled(has_checked and is_online)
        if has_checked and not is_online:
            self._apply_btn.setToolTip("Cannot replace while offline.")
        else:
            self._apply_btn.setToolTip("")

    def _set_replace_enabled(self, enabled):
        self._replace_group.setEnabled(enabled)
        if not enabled:
            self._apply_btn.setEnabled(False)

    def closeEvent(self, event):
        # Stop any running workers before closing
        for worker in (self._search_worker, self._replace_worker):
            if worker and worker.isRunning():
                worker.quit()
                worker.wait(2000)
        super().closeEvent(event)
