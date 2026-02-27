#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Import/Export interfaces for DNS zones and records.

Both use the standard two-pane splitter layout:
  Export — left: zone selection, right: format / options / file
  Import — left: file selection + preview, right: settings / target / mode
"""

import os
from datetime import datetime
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Signal, QThread, Qt
from import_export_manager import ImportExportManager
from qfluentwidgets import (
    PushButton, PrimaryPushButton, ProgressBar, LineEdit, CheckBox,
    TextEdit, ListView, StrongBodyLabel, CaptionLabel,
    InfoBar, InfoBarPosition,
)
import logging
from fluent_styles import container_qss, SPLITTER_QSS
from confirm_drawer import ConfirmDrawer

logger = logging.getLogger(__name__)


class ImportExportWorker(QThread):
    """Worker thread for import/export operations."""

    finished = Signal(bool, str, object)  # success, message, data
    progress = Signal(str)  # progress message
    progress_update = Signal(int, str)  # percentage, status message

    def __init__(self, manager, operation, **kwargs):
        super().__init__()
        self.manager = manager
        self.operation = operation
        self.kwargs = kwargs

    def run(self):
        try:
            if self.operation == 'export':
                success, message = self.manager.export_zone(**self.kwargs)
                self.finished.emit(success, message, None)
            elif self.operation == 'bulk_export':
                self.kwargs['progress_callback'] = self._emit_progress
                success, message = self.manager.export_zones_bulk(**self.kwargs)
                self.finished.emit(success, message, None)
            elif self.operation == 'import':
                self.kwargs['progress_callback'] = self._emit_progress
                success, message, data = self.manager.import_zone(**self.kwargs)
                self.finished.emit(success, message, data)
        except Exception as e:
            self.finished.emit(False, f"Operation failed: {str(e)}", None)

    def _emit_progress(self, percentage, status):
        self.progress_update.emit(percentage, status)


# ======================================================================
# Export Interface
# ======================================================================

class ExportInterface(QtWidgets.QWidget):
    """Export page — left: zone selection, right: settings."""

    zones_refresh_requested = Signal()

    def __init__(self, import_export_manager, available_zones=None, parent=None):
        super().__init__(parent)
        self.setObjectName("exportInterface")
        self.import_export_manager = import_export_manager
        self.available_zones = available_zones or []
        self.worker = None
        self.setup_ui()

    def showEvent(self, event):
        super().showEvent(event)
        self.setStyleSheet(container_qss())
        self.zones_refresh_requested.emit()

    def hideEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
        super().hideEvent(event)

    def setup_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(SPLITTER_QSS)
        outer.addWidget(splitter, 1)

        # ── Left pane: zone selection ─────────────────────────────────
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

        # Zone list view with Ctrl/Shift multi-select (no checkboxes)
        self._zone_model = QtCore.QStringListModel(self.available_zones)
        self._zone_list = ListView()
        self._zone_list.setModel(self._zone_model)
        self._zone_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._zone_list.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._zone_list.setAlternatingRowColors(True)
        self._zone_list.selectionModel().selectionChanged.connect(self._update_export_btn)
        left_lay.addWidget(self._zone_list)

        # Select all / none buttons
        btn_row = QtWidgets.QHBoxLayout()
        self.select_all_btn = PushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all_zones)
        btn_row.addWidget(self.select_all_btn)
        self.select_none_btn = PushButton("Select None")
        self.select_none_btn.clicked.connect(self.select_no_zones)
        btn_row.addWidget(self.select_none_btn)
        btn_row.addStretch()
        left_lay.addLayout(btn_row)

        splitter.addWidget(left)

        # ── Right pane: export settings ───────────────────────────────
        right = QtWidgets.QWidget()
        right_lay = QtWidgets.QVBoxLayout(right)
        right_lay.setContentsMargins(6, 6, 6, 6)
        right_lay.setSpacing(6)

        right_lay.addWidget(StrongBodyLabel("Export Settings"))

        # Format selection
        format_group = QtWidgets.QGroupBox("Format")
        format_layout = QtWidgets.QVBoxLayout(format_group)
        self.export_format_group = QtWidgets.QButtonGroup()
        formats = ImportExportManager.SUPPORTED_FORMATS
        for fmt_key, fmt_desc in formats.items():
            radio = QtWidgets.QRadioButton(fmt_desc)
            radio.setProperty('format', fmt_key)
            self.export_format_group.addButton(radio)
            format_layout.addWidget(radio)
            if fmt_key == 'json':
                radio.setChecked(True)
        right_lay.addWidget(format_group)

        # Options
        options_group = QtWidgets.QGroupBox("Options")
        options_layout = QtWidgets.QVBoxLayout(options_group)
        self.include_metadata_cb = CheckBox("Include metadata (timestamps, etc.)")
        self.include_metadata_cb.setChecked(True)
        options_layout.addWidget(self.include_metadata_cb)
        right_lay.addWidget(options_group)

        # Output file
        file_group = QtWidgets.QGroupBox("Output File")
        file_layout = QtWidgets.QVBoxLayout(file_group)
        self.export_file_edit = LineEdit()
        self.export_file_edit.setPlaceholderText(
            "Auto-generated filename will be used if empty..."
        )
        file_layout.addWidget(self.export_file_edit)
        file_btn_row = QtWidgets.QHBoxLayout()
        self.export_browse_btn = PushButton("Browse...")
        self.export_browse_btn.clicked.connect(self.browse_export_file)
        file_btn_row.addWidget(self.export_browse_btn)
        self.auto_filename_btn = PushButton("Auto-Generate")
        self.auto_filename_btn.clicked.connect(self.auto_generate_export_filename)
        file_btn_row.addWidget(self.auto_filename_btn)
        file_btn_row.addStretch()
        file_layout.addLayout(file_btn_row)
        right_lay.addWidget(file_group)

        right_lay.addStretch()

        # Progress
        self.progress_bar = ProgressBar()
        self.progress_bar.setVisible(False)
        right_lay.addWidget(self.progress_bar)
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setWordWrap(True)
        right_lay.addWidget(self.status_label)

        # Export button
        export_btn_row = QtWidgets.QHBoxLayout()
        export_btn_row.addStretch()
        self.export_btn = PrimaryPushButton("Export")
        self.export_btn.clicked.connect(self.start_export)
        export_btn_row.addWidget(self.export_btn)
        right_lay.addLayout(export_btn_row)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([340, 760])

    # ------------------------------------------------------------------
    # Zone helpers
    # ------------------------------------------------------------------

    def update_zones(self, available_zones):
        self.available_zones = available_zones or []
        self._zone_model.setStringList(self.available_zones)
        self._zone_count_label.setText(
            f"{len(self.available_zones)} zone{'s' if len(self.available_zones) != 1 else ''}"
        )

    def select_all_zones(self):
        sel = self._zone_list.selectionModel()
        model = self._zone_model
        sel.select(
            QtCore.QItemSelection(model.index(0), model.index(model.rowCount() - 1)),
            QtCore.QItemSelectionModel.SelectionFlag.Select,
        )

    def select_no_zones(self):
        self._zone_list.clearSelection()

    def get_selected_zones(self):
        return [idx.data() for idx in self._zone_list.selectedIndexes()]

    def _update_export_btn(self):
        n = len(self._zone_list.selectedIndexes())
        self.export_btn.setText(f"Export ({n})" if n > 0 else "Export")

    # ------------------------------------------------------------------
    # Export logic (unchanged)
    # ------------------------------------------------------------------

    def browse_export_file(self):
        selected_format = self.get_selected_export_format()
        extensions = {
            'json': 'JSON Files (*.json)',
            'yaml': 'YAML Files (*.yaml *.yml)',
            'bind': 'Zone Files (*.zone *.txt)',
            'djbdns': 'Data Files (*.data *.txt)'
        }
        file_filter = extensions.get(selected_format, 'All Files (*)')
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Zone File", "", file_filter
        )
        if file_path:
            self.export_file_edit.setText(file_path)

    def get_selected_export_format(self):
        for button in self.export_format_group.buttons():
            if button.isChecked():
                return button.property('format')
        return 'json'

    def auto_generate_export_filename(self):
        selected = self.get_selected_zones()
        if not selected:
            self.show_error("Please select at least one zone first.")
            return
        format_type = self.get_selected_export_format()
        if len(selected) == 1:
            filename = self.import_export_manager.generate_export_filename(
                selected[0], format_type
            )
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Save Export File", filename,
                self._get_file_filter(format_type)
            )
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bulk_export_{timestamp}.zip"
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Save Bulk Export ZIP", filename, "ZIP files (*.zip)"
            )
        if file_path:
            self.export_file_edit.setText(file_path)

    def _get_file_filter(self, format_type):
        extensions = {
            'json': 'JSON Files (*.json)',
            'yaml': 'YAML Files (*.yaml *.yml)',
            'bind': 'Zone Files (*.zone *.txt)',
            'djbdns': 'Data Files (*.data *.txt)'
        }
        return extensions.get(format_type, 'All Files (*)')

    def start_export(self):
        selected_zones = self.get_selected_zones()
        if not selected_zones:
            self.show_error("Please select at least one zone to export.")
            return
        file_path = self.export_file_edit.text().strip()
        format_type = self.get_selected_export_format()
        include_metadata = self.include_metadata_cb.isChecked()

        if len(selected_zones) == 1:
            zone_name = selected_zones[0]
            if not file_path:
                filename = self.import_export_manager.generate_export_filename(
                    zone_name, format_type
                )
                file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                    self, "Save Export File", filename,
                    self._get_file_filter(format_type)
                )
                if not file_path:
                    return
            self.set_operation_running(True)
            self.worker = ImportExportWorker(
                self.import_export_manager, 'export',
                zone_name=zone_name, format_type=format_type,
                file_path=file_path, include_metadata=include_metadata
            )
            self.worker.finished.connect(self.on_export_finished)
            self.worker.start()
        else:
            if not file_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"bulk_export_{timestamp}.zip"
                file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                    self, "Save Bulk Export ZIP", filename, "ZIP files (*.zip)"
                )
                if not file_path:
                    return
            self.set_operation_running(True)
            self.worker = ImportExportWorker(
                self.import_export_manager, 'bulk_export',
                zone_names=selected_zones, format_type=format_type,
                file_path=file_path, include_metadata=include_metadata
            )
            self.worker.finished.connect(self.on_export_finished)
            self.worker.progress_update.connect(self.on_progress_update)
            self.worker.start()

    def on_export_finished(self, success, message, data):
        self.set_operation_running(False)
        if success:
            self.show_success(f"Export completed successfully!\n{message}")
        else:
            self.show_error(f"Export failed:\n{message}")

    def on_progress_update(self, percentage, status):
        self.progress_bar.setValue(percentage)
        self.status_label.setText(f"{percentage}% \u2014 {status}")

    def set_operation_running(self, running):
        self.progress_bar.setVisible(running)
        if running:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.status_label.setText("Starting...")
        self.export_btn.setEnabled(not running)
        if not running:
            self.status_label.clear()

    def show_success(self, message):
        InfoBar.success(
            title="Success",
            content=message,
            parent=self.window(),
            duration=4000,
            position=InfoBarPosition.TOP,
        )
        self.status_label.setText("Operation completed successfully.")

    def show_error(self, message):
        InfoBar.error(
            title="Error",
            content=message,
            parent=self.window(),
            duration=8000,
            position=InfoBarPosition.TOP,
        )
        self.status_label.setText("Operation failed.")


# ======================================================================
# Import Interface
# ======================================================================

class ImportInterface(QtWidgets.QWidget):
    """Import page — left: file + preview, right: settings."""

    import_completed = Signal()
    zones_refresh_requested = Signal()

    def __init__(self, import_export_manager, available_zones=None, parent=None):
        super().__init__(parent)
        self.setObjectName("importInterface")
        self.import_export_manager = import_export_manager
        self.available_zones = available_zones or []
        self.worker = None
        self.setup_ui()
        self._confirm_drawer = ConfirmDrawer(parent=self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_confirm_drawer'):
            self._confirm_drawer.reposition(event.size())

    def showEvent(self, event):
        super().showEvent(event)
        self.setStyleSheet(container_qss())
        self.zones_refresh_requested.emit()

    def hideEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
        super().hideEvent(event)

    def setup_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(SPLITTER_QSS)
        outer.addWidget(splitter, 1)

        # ── Left pane: file selection + preview ───────────────────────
        left = QtWidgets.QWidget()
        left.setMinimumWidth(220)
        left_lay = QtWidgets.QVBoxLayout(left)
        left_lay.setContentsMargins(6, 6, 6, 6)
        left_lay.setSpacing(6)

        left_lay.addWidget(StrongBodyLabel("Import File"))

        # File selector
        file_row = QtWidgets.QHBoxLayout()
        self.import_file_edit = LineEdit()
        self.import_file_edit.setPlaceholderText("Select file to import...")
        self.import_file_edit.textChanged.connect(self.on_import_file_changed)
        file_row.addWidget(self.import_file_edit)
        self.import_browse_btn = PushButton("Browse...")
        self.import_browse_btn.clicked.connect(self.browse_import_file)
        file_row.addWidget(self.import_browse_btn)
        left_lay.addLayout(file_row)

        # Preview area
        left_lay.addWidget(CaptionLabel("Preview (read-only):"))
        self.preview_text = TextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText(
            "Select a file and click Preview to see import data..."
        )
        left_lay.addWidget(self.preview_text, 1)

        # Preview button
        preview_row = QtWidgets.QHBoxLayout()
        self.preview_btn = PushButton("Preview Import")
        self.preview_btn.clicked.connect(self.preview_import)
        self.preview_btn.setEnabled(False)
        preview_row.addWidget(self.preview_btn)
        preview_row.addStretch()
        left_lay.addLayout(preview_row)

        splitter.addWidget(left)

        # ── Right pane: import settings ───────────────────────────────
        right = QtWidgets.QWidget()
        right_lay = QtWidgets.QVBoxLayout(right)
        right_lay.setContentsMargins(6, 6, 6, 6)
        right_lay.setSpacing(6)

        right_lay.addWidget(StrongBodyLabel("Import Settings"))

        # Format selection
        format_group = QtWidgets.QGroupBox("Format")
        format_layout = QtWidgets.QVBoxLayout(format_group)
        self.import_format_group = QtWidgets.QButtonGroup()
        formats = ImportExportManager.SUPPORTED_FORMATS
        for fmt_key, fmt_desc in formats.items():
            radio = QtWidgets.QRadioButton(fmt_desc)
            radio.setProperty('format', fmt_key)
            self.import_format_group.addButton(radio)
            format_layout.addWidget(radio)
            if fmt_key == 'json':
                radio.setChecked(True)
        right_lay.addWidget(format_group)

        # Target zone
        target_group = QtWidgets.QGroupBox("Target Zone")
        target_layout = QtWidgets.QVBoxLayout(target_group)
        self.target_zone_combo = QtWidgets.QComboBox()
        self.target_zone_combo.setEditable(True)
        self.target_zone_combo.addItem("[Use zone name from file]", "")
        self.target_zone_combo.addItems(self.available_zones)
        target_layout.addWidget(self.target_zone_combo)
        target_help = QtWidgets.QLabel(
            "Select an existing zone or enter a new zone name. "
            "If the zone doesn't exist, it will be created automatically."
        )
        target_help.setWordWrap(True)
        target_layout.addWidget(target_help)
        right_lay.addWidget(target_group)

        # Existing records handling
        existing_group = QtWidgets.QGroupBox("Existing Records Handling")
        existing_layout = QtWidgets.QVBoxLayout(existing_group)
        self.existing_records_group = QtWidgets.QButtonGroup()

        self.append_existing_radio = QtWidgets.QRadioButton(
            "Append \u2014 Add new records, keep existing ones unchanged"
        )
        self.append_existing_radio.setChecked(True)
        self.existing_records_group.addButton(self.append_existing_radio)
        existing_layout.addWidget(self.append_existing_radio)

        self.merge_existing_radio = QtWidgets.QRadioButton(
            "Merge \u2014 Update matching records, preserve non-matching ones"
        )
        self.existing_records_group.addButton(self.merge_existing_radio)
        existing_layout.addWidget(self.merge_existing_radio)

        self.replace_existing_radio = QtWidgets.QRadioButton(
            "Replace \u2014 Replace all existing records with imported ones"
        )
        self.existing_records_group.addButton(self.replace_existing_radio)
        existing_layout.addWidget(self.replace_existing_radio)
        right_lay.addWidget(existing_group)

        right_lay.addStretch()

        # Progress
        self.progress_bar = ProgressBar()
        self.progress_bar.setVisible(False)
        right_lay.addWidget(self.progress_bar)
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setWordWrap(True)
        right_lay.addWidget(self.status_label)

        # Import button
        import_btn_row = QtWidgets.QHBoxLayout()
        import_btn_row.addStretch()
        self.import_btn = PrimaryPushButton("Import Zone")
        self.import_btn.clicked.connect(self.start_import)
        self.import_btn.setEnabled(False)
        import_btn_row.addWidget(self.import_btn)
        right_lay.addLayout(import_btn_row)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([340, 760])

    # ------------------------------------------------------------------
    # Zone helpers
    # ------------------------------------------------------------------

    def update_zones(self, available_zones):
        self.available_zones = available_zones or []
        current = self.target_zone_combo.currentText()
        self.target_zone_combo.clear()
        self.target_zone_combo.addItem("[Use zone name from file]", "")
        self.target_zone_combo.addItems(self.available_zones)
        if current:
            idx = self.target_zone_combo.findText(current)
            if idx >= 0:
                self.target_zone_combo.setCurrentIndex(idx)

    # ------------------------------------------------------------------
    # Import logic (unchanged)
    # ------------------------------------------------------------------

    def browse_import_file(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Zone File", "",
            "All Supported (*.json *.yaml *.yml *.zone *.data *.txt);;"
            "JSON Files (*.json);;YAML Files (*.yaml *.yml);;"
            "Zone Files (*.zone *.txt);;Data Files (*.data *.txt);;"
            "All Files (*)"
        )
        if file_path:
            self.import_file_edit.setText(file_path)

    def get_selected_import_format(self):
        for button in self.import_format_group.buttons():
            if button.isChecked():
                return button.property('format')
        return 'json'

    def get_target_zone(self):
        current_text = self.target_zone_combo.currentText().strip()
        if current_text == "[Use zone name from file]" or not current_text:
            return None
        return current_text

    def get_existing_records_mode(self):
        if self.merge_existing_radio.isChecked():
            return 'merge'
        elif self.replace_existing_radio.isChecked():
            return 'replace'
        return 'append'

    def on_import_file_changed(self):
        has_file = bool(self.import_file_edit.text().strip())
        self.preview_btn.setEnabled(has_file)
        self.import_btn.setEnabled(has_file)
        if not has_file:
            self.preview_text.clear()

    def preview_import(self):
        file_path = self.import_file_edit.text().strip()
        if not file_path:
            return
        format_type = self.get_selected_import_format()
        target_zone = self.get_target_zone()
        existing_records_mode = self.get_existing_records_mode()
        self.set_operation_running(True)
        self.worker = ImportExportWorker(
            self.import_export_manager, 'import',
            file_path=file_path, format_type=format_type,
            dry_run=True, target_zone=target_zone,
            existing_records_mode=existing_records_mode
        )
        self.worker.finished.connect(self.on_preview_finished)
        self.worker.start()

    def start_import(self):
        file_path = self.import_file_edit.text().strip()
        if not file_path:
            self.show_error("Please select a file to import.")
            return
        format_type = self.get_selected_import_format()
        target_zone = self.get_target_zone()
        existing_records_mode = self.get_existing_records_mode()

        items = []
        if target_zone:
            items.append(f"Target zone: {target_zone}")
        else:
            items.append("Zone name: from import file")
        mode_labels = {
            'replace': "Replace (delete existing records first)",
            'merge': "Merge (update matching records)",
        }
        items.append(f"Mode: {mode_labels.get(existing_records_mode, 'Append (keep existing)')}")

        # Capture locals for callback
        _fp, _ft, _tz, _erm = file_path, format_type, target_zone, existing_records_mode

        def _do_import():
            self.set_operation_running(True)
            self.worker = ImportExportWorker(
                self.import_export_manager, 'import',
                file_path=_fp, format_type=_ft,
                dry_run=False, target_zone=_tz,
                existing_records_mode=_erm,
            )
            self.worker.finished.connect(self.on_import_finished)
            self.worker.progress_update.connect(self.on_progress_update)
            self.worker.start()

        self._confirm_drawer.ask(
            title="Confirm Import",
            message="Import records from file? This cannot be undone.",
            items=items,
            on_confirm=_do_import,
            confirm_text="Import",
        )

    def on_preview_finished(self, success, message, data):
        self.set_operation_running(False)
        if success and data:
            zone_info = data.get('zone', {})
            records = data.get('records', [])
            target_zone = data.get(
                'target_zone', zone_info.get('name', 'Unknown')
            )
            existing_records_mode = data.get('existing_records_mode', 'ignore')

            preview_text = f"Target Zone: {target_zone}\n"
            preview_text += f"Records: {len(records)}\n"
            preview_text += f"Existing Records: {existing_records_mode.title()}\n"

            original_zone = zone_info.get('name', 'Unknown')
            if target_zone != original_zone:
                preview_text += f"Original Zone (from file): {original_zone}\n"

            if existing_records_mode == 'replace':
                preview_text += "Will delete all existing records first\n"
            elif existing_records_mode == 'merge':
                preview_text += "Will update matching records only\n"
            else:
                preview_text += "Will preserve existing records\n"

            preview_text += "\n"
            for i, record in enumerate(records[:10]):
                subname = record.get('subname', '@')
                rtype = record.get('type', 'Unknown')
                content = ', '.join(record.get('records', []))
                preview_text += f"{subname:<15} {rtype:<8} {content}\n"
            if len(records) > 10:
                preview_text += f"\n... and {len(records) - 10} more records"

            self.preview_text.setPlainText(preview_text)
            self.status_label.setText(f"Preview: {message}")
        else:
            self.show_error(f"Preview failed:\n{message}")

    def on_import_finished(self, success, message, data):
        self.set_operation_running(False)
        if success:
            self.show_success(f"Import completed successfully!\n{message}")
            self.import_completed.emit()
        else:
            self.show_error(f"Import failed:\n{message}")

    def on_progress_update(self, percentage, status):
        self.progress_bar.setValue(percentage)
        self.status_label.setText(f"{percentage}% \u2014 {status}")

    def set_operation_running(self, running):
        self.progress_bar.setVisible(running)
        if running:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.status_label.setText("Starting...")
        self.import_btn.setEnabled(
            not running and bool(self.import_file_edit.text().strip())
        )
        self.preview_btn.setEnabled(
            not running and bool(self.import_file_edit.text().strip())
        )
        if not running:
            self.status_label.clear()

    def show_success(self, message):
        InfoBar.success(
            title="Success",
            content=message,
            parent=self.window(),
            duration=4000,
            position=InfoBarPosition.TOP,
        )
        self.status_label.setText("Operation completed successfully.")

    def show_error(self, message):
        InfoBar.error(
            title="Error",
            content=message,
            parent=self.window(),
            duration=8000,
            position=InfoBarPosition.TOP,
        )
        self.status_label.setText("Operation failed.")
