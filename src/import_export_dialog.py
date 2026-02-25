#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Import/Export Dialog for DNS zones and records.
Provides UI for importing and exporting zones in various formats.
"""

import os
from datetime import datetime
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Signal, QThread
from import_export_manager import ImportExportManager
from qfluentwidgets import PushButton, ProgressBar, LineEdit, CheckBox, TextEdit, LargeTitleLabel, ScrollArea
import logging
from fluent_styles import container_qss
from notify_drawer import NotifyDrawer

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
                # Add progress callback to kwargs
                self.kwargs['progress_callback'] = self._emit_progress
                success, message = self.manager.export_zones_bulk(**self.kwargs)
                self.finished.emit(success, message, None)
            elif self.operation == 'import':
                # Add progress callback to kwargs
                self.kwargs['progress_callback'] = self._emit_progress
                success, message, data = self.manager.import_zone(**self.kwargs)
                self.finished.emit(success, message, data)
        except Exception as e:
            self.finished.emit(False, f"Operation failed: {str(e)}", None)

    def _emit_progress(self, percentage, status):
        """Emit progress update signal."""
        self.progress_update.emit(percentage, status)


class ExportInterface(QtWidgets.QWidget):
    """Export page for the Fluent sidebar navigation."""

    zones_refresh_requested = Signal()

    def __init__(self, import_export_manager, available_zones=None, parent=None):
        super().__init__(parent)
        self.setObjectName("exportInterface")
        self.import_export_manager = import_export_manager
        self.available_zones = available_zones or []
        self.worker = None
        self.zone_checkboxes = []
        self.zone_list_layout = None
        self.setup_ui()
        self._notify_drawer = NotifyDrawer(parent=self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_notify_drawer'):
            self._notify_drawer.reposition(event.size())

    def setup_ui(self):
        """Set up the user interface."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(36, 20, 36, 20)

        layout.addWidget(LargeTitleLabel("Export"))

        # Zone selection — checkbox list (select one or many)
        zone_group = QtWidgets.QGroupBox("Zone Selection")
        zone_layout = QtWidgets.QVBoxLayout(zone_group)

        controls_layout = QtWidgets.QHBoxLayout()
        self.select_all_btn = PushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all_zones)
        self.select_none_btn = PushButton("Select None")
        self.select_none_btn.clicked.connect(self.select_no_zones)
        controls_layout.addWidget(self.select_all_btn)
        controls_layout.addWidget(self.select_none_btn)
        controls_layout.addStretch()
        zone_layout.addLayout(controls_layout)

        # Scrollable zone list with checkboxes
        self.zone_list_scroll = QtWidgets.QScrollArea()
        self.zone_list_scroll.setWidgetResizable(True)
        self.zone_list_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: 1px solid rgba(128,128,128,0.2); }"
        )
        self.zone_list_scroll.setMinimumHeight(160)

        self.zone_list_widget = QtWidgets.QWidget()
        self.zone_list_layout = QtWidgets.QVBoxLayout(self.zone_list_widget)
        self.zone_list_layout.setSpacing(8)
        self.zone_list_layout.setContentsMargins(10, 10, 10, 10)

        self.zone_checkboxes = []
        for zone in self.available_zones:
            checkbox = CheckBox(zone)
            self.zone_checkboxes.append(checkbox)
            self.zone_list_layout.addWidget(checkbox)
        self.zone_list_layout.addStretch()

        self.zone_list_widget.setStyleSheet("background: transparent;")
        self.zone_list_scroll.setWidget(self.zone_list_widget)
        zone_layout.addWidget(self.zone_list_scroll)

        layout.addWidget(zone_group, 1)

        # Format selection
        format_group = QtWidgets.QGroupBox("Export Format")
        format_layout = QtWidgets.QVBoxLayout(format_group)

        self.export_format_group = QtWidgets.QButtonGroup()

        formats = ImportExportManager.SUPPORTED_FORMATS
        for fmt_key, fmt_desc in formats.items():
            radio = QtWidgets.QRadioButton(fmt_desc)
            radio.setProperty('format', fmt_key)
            self.export_format_group.addButton(radio)
            format_layout.addWidget(radio)
            if fmt_key == 'json':  # Default selection
                radio.setChecked(True)

        layout.addWidget(format_group)

        # Options
        options_group = QtWidgets.QGroupBox("Export Options")
        options_layout = QtWidgets.QVBoxLayout(options_group)

        self.include_metadata_cb = CheckBox("Include metadata (timestamps, etc.)")
        self.include_metadata_cb.setChecked(True)
        options_layout.addWidget(self.include_metadata_cb)

        layout.addWidget(options_group)

        # File selection
        file_group = QtWidgets.QGroupBox("Output File")
        file_layout = QtWidgets.QHBoxLayout(file_group)

        self.export_file_edit = LineEdit()
        self.export_file_edit.setPlaceholderText("Auto-generated filename will be used if empty...")
        file_layout.addWidget(self.export_file_edit)

        self.export_browse_btn = PushButton("Browse...")
        self.export_browse_btn.clicked.connect(self.browse_export_file)
        file_layout.addWidget(self.export_browse_btn)

        self.auto_filename_btn = PushButton("Auto-Generate")
        self.auto_filename_btn.clicked.connect(self.auto_generate_export_filename)
        file_layout.addWidget(self.auto_filename_btn)

        layout.addWidget(file_group)

        # Export button
        self.export_btn = PushButton("Export")
        self.export_btn.clicked.connect(self.start_export)
        layout.addWidget(self.export_btn)

        layout.addStretch()

        # Progress bar
        self.progress_bar = ProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def update_zones(self, available_zones):
        """Update available zone lists (call when zones change)."""
        self.available_zones = available_zones or []
        if self.zone_list_layout is not None:
            while self.zone_list_layout.count():
                item = self.zone_list_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        self.zone_checkboxes = []
        for zone in self.available_zones:
            checkbox = CheckBox(zone)
            self.zone_checkboxes.append(checkbox)
            self.zone_list_layout.addWidget(checkbox)
        self.zone_list_layout.addStretch()

    def showEvent(self, event):
        """Refresh zone lists and theme-aware styles whenever the page becomes visible."""
        super().showEvent(event)
        self.setStyleSheet(container_qss())
        self.zones_refresh_requested.emit()

    def hideEvent(self, event):
        """Stop any running worker when the page is hidden."""
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
        super().hideEvent(event)

    def browse_export_file(self):
        """Browse for export file location."""
        selected_format = self.get_selected_export_format()

        # Set file extension based on format
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
        """Get the selected export format."""
        for button in self.export_format_group.buttons():
            if button.isChecked():
                return button.property('format')
        return 'json'

    def select_all_zones(self):
        """Select all zones in the bulk export list."""
        for checkbox in self.zone_checkboxes:
            checkbox.setChecked(True)

    def select_no_zones(self):
        """Deselect all zones in the bulk export list."""
        for checkbox in self.zone_checkboxes:
            checkbox.setChecked(False)

    def get_selected_zones(self):
        """Get list of selected zones for bulk export."""
        selected_zones = []
        for checkbox in self.zone_checkboxes:
            if checkbox.isChecked():
                selected_zones.append(checkbox.text())
        return selected_zones

    def auto_generate_export_filename(self):
        """Auto-generate export filename based on selected zones and format."""
        selected = self.get_selected_zones()
        if not selected:
            self.show_error("Please select at least one zone first.")
            return

        format_type = self.get_selected_export_format()

        if len(selected) == 1:
            filename = self.import_export_manager.generate_export_filename(selected[0], format_type)
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Save Export File", filename, self._get_file_filter(format_type)
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
        """Get file filter for file dialog based on format."""
        extensions = {
            'json': 'JSON Files (*.json)',
            'yaml': 'YAML Files (*.yaml *.yml)',
            'bind': 'Zone Files (*.zone *.txt)',
            'djbdns': 'Data Files (*.data *.txt)'
        }
        return extensions.get(format_type, 'All Files (*)')

    def start_export(self):
        """Start the export operation."""
        selected_zones = self.get_selected_zones()
        if not selected_zones:
            self.show_error("Please select at least one zone to export.")
            return

        file_path = self.export_file_edit.text().strip()
        format_type = self.get_selected_export_format()
        include_metadata = self.include_metadata_cb.isChecked()

        if len(selected_zones) == 1:
            # Single zone export
            zone_name = selected_zones[0]
            if not file_path:
                filename = self.import_export_manager.generate_export_filename(zone_name, format_type)
                file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                    self, "Save Export File", filename, self._get_file_filter(format_type)
                )
                if not file_path:
                    return

            self.set_operation_running(True)
            self.worker = ImportExportWorker(
                self.import_export_manager,
                'export',
                zone_name=zone_name,
                format_type=format_type,
                file_path=file_path,
                include_metadata=include_metadata
            )
            self.worker.finished.connect(self.on_export_finished)
            self.worker.start()
        else:
            # Bulk export — ZIP archive
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
                self.import_export_manager,
                'bulk_export',
                zone_names=selected_zones,
                format_type=format_type,
                file_path=file_path,
                include_metadata=include_metadata
            )
            self.worker.finished.connect(self.on_export_finished)
            self.worker.progress_update.connect(self.on_progress_update)
            self.worker.start()

    def on_export_finished(self, success, message, data):
        """Handle export completion."""
        self.set_operation_running(False)

        if success:
            self.show_success(f"Export completed successfully!\n{message}")
        else:
            self.show_error(f"Export failed:\n{message}")

    def on_progress_update(self, percentage, status):
        """Handle progress updates during export."""
        self.progress_bar.setValue(percentage)
        self.status_label.setText(f"{percentage}% — {status}")

    def set_operation_running(self, running):
        """Set UI state for running operation."""
        self.progress_bar.setVisible(running)
        if running:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.status_label.setText("Starting...")

        # Disable/enable controls
        self.export_btn.setEnabled(not running)

        if not running:
            self.status_label.clear()

    def show_success(self, message):
        """Show success message."""
        self._notify_drawer.success("Success", message)
        self.status_label.setText("Operation completed successfully.")

    def show_error(self, message):
        """Show error message."""
        self._notify_drawer.error("Error", message)
        self.status_label.setText("Operation failed.")


class ImportInterface(QtWidgets.QWidget):
    """Import page for the Fluent sidebar navigation."""

    import_completed = Signal()
    zones_refresh_requested = Signal()

    def __init__(self, import_export_manager, available_zones=None, parent=None):
        super().__init__(parent)
        self.setObjectName("importInterface")
        self.import_export_manager = import_export_manager
        self.available_zones = available_zones or []
        self.worker = None
        self.setup_ui()
        self._notify_drawer = NotifyDrawer(parent=self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_notify_drawer'):
            self._notify_drawer.reposition(event.size())

    def setup_ui(self):
        """Set up the user interface."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(36, 20, 36, 20)

        layout.addWidget(LargeTitleLabel("Import"))

        # File selection
        file_group = QtWidgets.QGroupBox("Import File")
        file_layout = QtWidgets.QHBoxLayout(file_group)

        self.import_file_edit = LineEdit()
        self.import_file_edit.setPlaceholderText("Select file to import...")
        self.import_file_edit.textChanged.connect(self.on_import_file_changed)
        file_layout.addWidget(self.import_file_edit)

        self.import_browse_btn = PushButton("Browse...")
        self.import_browse_btn.clicked.connect(self.browse_import_file)
        file_layout.addWidget(self.import_browse_btn)

        layout.addWidget(file_group)

        # Format selection
        format_group = QtWidgets.QGroupBox("Import Format")
        format_layout = QtWidgets.QVBoxLayout(format_group)

        self.import_format_group = QtWidgets.QButtonGroup()

        formats = ImportExportManager.SUPPORTED_FORMATS
        for fmt_key, fmt_desc in formats.items():
            radio = QtWidgets.QRadioButton(fmt_desc)
            radio.setProperty('format', fmt_key)
            self.import_format_group.addButton(radio)
            format_layout.addWidget(radio)
            if fmt_key == 'json':  # Default selection
                radio.setChecked(True)

        layout.addWidget(format_group)

        # Target zone selection
        target_group = QtWidgets.QGroupBox("Target Zone")
        target_layout = QtWidgets.QFormLayout(target_group)

        self.target_zone_combo = QtWidgets.QComboBox()
        self.target_zone_combo.setEditable(True)
        self.target_zone_combo.addItem("[Use zone name from file]", "")
        self.target_zone_combo.addItems(self.available_zones)
        target_layout.addRow("Import to Zone:", self.target_zone_combo)

        target_help = QtWidgets.QLabel(
            "Select an existing zone or enter a new zone name. "
            "If the zone doesn't exist, it will be created automatically."
        )
        target_help.setWordWrap(True)
        target_layout.addRow(target_help)

        layout.addWidget(target_group)

        # Existing records handling
        existing_group = QtWidgets.QGroupBox("Existing Records Handling")
        existing_layout = QtWidgets.QVBoxLayout(existing_group)

        self.existing_records_group = QtWidgets.QButtonGroup()

        self.append_existing_radio = QtWidgets.QRadioButton("Append - Add new records, keep existing ones unchanged")
        self.append_existing_radio.setChecked(True)  # Default
        self.existing_records_group.addButton(self.append_existing_radio)
        existing_layout.addWidget(self.append_existing_radio)

        self.merge_existing_radio = QtWidgets.QRadioButton("Merge - Update matching records, preserve non-matching ones")
        self.existing_records_group.addButton(self.merge_existing_radio)
        existing_layout.addWidget(self.merge_existing_radio)

        self.replace_existing_radio = QtWidgets.QRadioButton("Replace - Replace all existing records with imported ones")
        self.existing_records_group.addButton(self.replace_existing_radio)
        existing_layout.addWidget(self.replace_existing_radio)

        layout.addWidget(existing_group)

        # Preview area
        preview_group = QtWidgets.QGroupBox("Import Preview")
        preview_layout = QtWidgets.QVBoxLayout(preview_group)

        self.preview_text = TextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(200)
        self.preview_text.setPlaceholderText("Select a file to preview import data...")
        preview_layout.addWidget(self.preview_text)

        layout.addWidget(preview_group)

        # Import buttons
        button_layout = QtWidgets.QHBoxLayout()

        self.preview_btn = PushButton("Preview Import")
        self.preview_btn.clicked.connect(self.preview_import)
        self.preview_btn.setEnabled(False)
        button_layout.addWidget(self.preview_btn)

        self.import_btn = PushButton("Import Zone")
        self.import_btn.clicked.connect(self.start_import)
        self.import_btn.setEnabled(False)
        button_layout.addWidget(self.import_btn)

        layout.addLayout(button_layout)

        layout.addStretch()

        # Progress bar
        self.progress_bar = ProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def update_zones(self, available_zones):
        """Update available zone lists (call when zones change)."""
        self.available_zones = available_zones or []
        current = self.target_zone_combo.currentText()
        self.target_zone_combo.clear()
        self.target_zone_combo.addItem("[Use zone name from file]", "")
        self.target_zone_combo.addItems(self.available_zones)
        if current:
            idx = self.target_zone_combo.findText(current)
            if idx >= 0:
                self.target_zone_combo.setCurrentIndex(idx)

    def showEvent(self, event):
        """Refresh zone lists and theme-aware styles whenever the page becomes visible."""
        super().showEvent(event)
        self.setStyleSheet(container_qss())
        self.zones_refresh_requested.emit()

    def hideEvent(self, event):
        """Stop any running worker when the page is hidden."""
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
        super().hideEvent(event)

    def browse_import_file(self):
        """Browse for import file."""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Zone File", "",
            "All Supported (*.json *.yaml *.yml *.zone *.data *.txt);;JSON Files (*.json);;YAML Files (*.yaml *.yml);;Zone Files (*.zone *.txt);;Data Files (*.data *.txt);;All Files (*)"
        )

        if file_path:
            self.import_file_edit.setText(file_path)

    def get_selected_import_format(self):
        """Get the selected import format."""
        for button in self.import_format_group.buttons():
            if button.isChecked():
                return button.property('format')
        return 'json'

    def get_target_zone(self):
        """Get the selected target zone for import."""
        current_text = self.target_zone_combo.currentText().strip()
        if current_text == "[Use zone name from file]" or not current_text:
            return None
        return current_text

    def get_existing_records_mode(self):
        """Get the selected existing records handling mode."""
        if self.merge_existing_radio.isChecked():
            return 'merge'
        elif self.replace_existing_radio.isChecked():
            return 'replace'
        else:
            return 'append'

    def on_import_file_changed(self):
        """Handle import file path change."""
        has_file = bool(self.import_file_edit.text().strip())
        self.preview_btn.setEnabled(has_file)
        self.import_btn.setEnabled(has_file)

        if not has_file:
            self.preview_text.clear()

    def preview_import(self):
        """Preview the import data."""
        file_path = self.import_file_edit.text().strip()
        if not file_path:
            return

        format_type = self.get_selected_import_format()
        target_zone = self.get_target_zone()
        existing_records_mode = self.get_existing_records_mode()

        # Start worker thread for preview
        self.set_operation_running(True)
        self.worker = ImportExportWorker(
            self.import_export_manager,
            'import',
            file_path=file_path,
            format_type=format_type,
            dry_run=True,
            target_zone=target_zone,
            existing_records_mode=existing_records_mode
        )
        self.worker.finished.connect(self.on_preview_finished)
        self.worker.start()

    def start_import(self):
        """Start the import operation."""
        file_path = self.import_file_edit.text().strip()
        if not file_path:
            self.show_error("Please select a file to import.")
            return

        format_type = self.get_selected_import_format()
        target_zone = self.get_target_zone()
        existing_records_mode = self.get_existing_records_mode()

        # Build confirmation message
        confirm_msg = "This will create new zones and records."
        if target_zone:
            confirm_msg += f"\n\nRecords will be imported to zone: {target_zone}"
            confirm_msg += "\n(Zone will be created if it doesn't exist)"
        else:
            confirm_msg += "\n\nZone name will be taken from the import file."

        # Add existing records handling info
        if existing_records_mode == 'replace':
            confirm_msg += "\n\n⚠️  REPLACE MODE: All existing records (except NS/SOA) will be deleted first!"
        elif existing_records_mode == 'merge':
            confirm_msg += "\n\n🔄 MERGE MODE: Only records that exist in both zone and import file will be updated."
        else:
            confirm_msg += "\n\n✓ APPEND MODE: Existing records will be kept, new records will be added."

        confirm_msg += "\n\nAre you sure you want to proceed?"

        # Confirm import
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm Import", confirm_msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )

        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        # Start worker thread
        self.set_operation_running(True)
        self.worker = ImportExportWorker(
            self.import_export_manager,
            'import',
            file_path=file_path,
            format_type=format_type,
            dry_run=False,
            target_zone=target_zone,
            existing_records_mode=existing_records_mode
        )
        self.worker.finished.connect(self.on_import_finished)
        self.worker.progress_update.connect(self.on_progress_update)
        self.worker.start()

    def on_preview_finished(self, success, message, data):
        """Handle preview completion."""
        self.set_operation_running(False)

        if success and data:
            zone_info = data.get('zone', {})
            records = data.get('records', [])
            target_zone = data.get('target_zone', zone_info.get('name', 'Unknown'))
            existing_records_mode = data.get('existing_records_mode', 'ignore')

            preview_text = f"Target Zone: {target_zone}\n"
            preview_text += f"Records: {len(records)}\n"
            preview_text += f"Existing Records: {existing_records_mode.title()}\n"

            # Show zone creation info if different from file
            original_zone = zone_info.get('name', 'Unknown')
            if target_zone != original_zone:
                preview_text += f"Original Zone (from file): {original_zone}\n"

            # Show existing records handling info
            if existing_records_mode == 'replace':
                preview_text += "⚠️  Will delete all existing records first\n"
            elif existing_records_mode == 'merge':
                preview_text += "🔄 Will update matching records only\n"
            else:
                preview_text += "✓ Will preserve existing records\n"

            preview_text += "\n"

            # Show first few records as preview
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
        """Handle import completion."""
        self.set_operation_running(False)

        if success:
            self.show_success(f"Import completed successfully!\n{message}")
            # Emit signal to trigger sync in main window
            self.import_completed.emit()
        else:
            self.show_error(f"Import failed:\n{message}")

    def on_progress_update(self, percentage, status):
        """Handle progress updates during import."""
        self.progress_bar.setValue(percentage)
        self.status_label.setText(f"{percentage}% — {status}")

    def set_operation_running(self, running):
        """Set UI state for running operation."""
        self.progress_bar.setVisible(running)
        if running:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.status_label.setText("Starting...")

        # Disable/enable controls
        self.import_btn.setEnabled(not running and bool(self.import_file_edit.text().strip()))
        self.preview_btn.setEnabled(not running and bool(self.import_file_edit.text().strip()))

        if not running:
            self.status_label.clear()

    def show_success(self, message):
        """Show success message."""
        self._notify_drawer.success("Success", message)
        self.status_label.setText("Operation completed successfully.")

    def show_error(self, message):
        """Show error message."""
        self._notify_drawer.error("Error", message)
        self.status_label.setText("Operation failed.")
