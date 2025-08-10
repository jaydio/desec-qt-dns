#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Import/Export Dialog for DNS zones and records.
Provides UI for importing and exporting zones in various formats.
"""

import os
from datetime import datetime
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import pyqtSignal, QThread
from import_export_manager import ImportExportManager
import logging

logger = logging.getLogger(__name__)

class ImportExportWorker(QThread):
    """Worker thread for import/export operations."""
    
    finished = pyqtSignal(bool, str, object)  # success, message, data
    progress = pyqtSignal(str)  # progress message
    progress_update = pyqtSignal(int, str)  # percentage, status message
    
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

class ImportExportDialog(QtWidgets.QDialog):
    """Dialog for importing and exporting DNS zones."""
    
    # Signal emitted when import completes successfully
    import_completed = pyqtSignal()
    
    def __init__(self, import_export_manager, available_zones=None, parent=None):
        super().__init__(parent)
        self.import_export_manager = import_export_manager
        self.available_zones = available_zones or []
        self.worker = None
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("Import/Export DNS Zones")
        self.setMinimumSize(600, 500)
        self.setModal(True)
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # Tab widget for Import/Export
        self.tab_widget = QtWidgets.QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Export tab
        self.export_tab = self.create_export_tab()
        self.tab_widget.addTab(self.export_tab, "Export")
        
        # Import tab
        self.import_tab = self.create_import_tab()
        self.tab_widget.addTab(self.import_tab, "Import")
        
        # Progress bar
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        self.close_button = QtWidgets.QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
    def create_export_tab(self):
        """Create the export tab."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # Bulk export toggle
        self.bulk_export_cb = QtWidgets.QCheckBox("Enable Bulk Export")
        self.bulk_export_cb.setToolTip("Export multiple zones to a ZIP archive")
        self.bulk_export_cb.toggled.connect(self.on_bulk_export_toggled)
        layout.addWidget(self.bulk_export_cb)
        
        # Zone selection
        zone_group = QtWidgets.QGroupBox("Zone Selection")
        zone_layout = QtWidgets.QVBoxLayout(zone_group)
        
        # Single zone selection (default mode)
        single_zone_layout = QtWidgets.QFormLayout()
        self.export_zone_combo = QtWidgets.QComboBox()
        self.export_zone_combo.addItems(self.available_zones)
        single_zone_layout.addRow("Zone to Export:", self.export_zone_combo)
        self.single_zone_widget = QtWidgets.QWidget()
        self.single_zone_widget.setLayout(single_zone_layout)
        zone_layout.addWidget(self.single_zone_widget)
        
        # Bulk zone selection (hidden by default)
        self.bulk_zone_widget = QtWidgets.QWidget()
        bulk_zone_layout = QtWidgets.QVBoxLayout(self.bulk_zone_widget)
        
        # Calculate zone count for UI adjustments
        zone_count = len(self.available_zones)
        
        # Select all/none buttons
        bulk_controls_layout = QtWidgets.QHBoxLayout()
        self.select_all_btn = QtWidgets.QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all_zones)
        self.select_none_btn = QtWidgets.QPushButton("Select None")
        self.select_none_btn.clicked.connect(self.select_no_zones)
        bulk_controls_layout.addWidget(self.select_all_btn)
        bulk_controls_layout.addWidget(self.select_none_btn)
        bulk_controls_layout.addStretch()
        
        # Add helpful message for few zones
        if zone_count <= 3:
            zone_info_label = QtWidgets.QLabel(f"📁 {zone_count} zone{'s' if zone_count != 1 else ''} available for bulk export")
            zone_info_label.setStyleSheet("QLabel { color: #666; font-style: italic; padding: 5px; }")
            bulk_controls_layout.addWidget(zone_info_label)
        
        bulk_zone_layout.addLayout(bulk_controls_layout)
        
        # Scrollable zone list with checkboxes
        self.zone_list_scroll = QtWidgets.QScrollArea()
        self.zone_list_scroll.setWidgetResizable(True)
        
        # Adjust height based on number of zones for better appearance
        if zone_count <= 3:
            # For few zones, use a smaller, more compact height
            scroll_height = min(120, max(60, zone_count * 35 + 20))
        else:
            # For many zones, use the larger scrollable area
            scroll_height = 200
        
        self.zone_list_scroll.setMaximumHeight(scroll_height)
        self.zone_list_scroll.setMinimumHeight(scroll_height)
        
        self.zone_list_widget = QtWidgets.QWidget()
        self.zone_list_layout = QtWidgets.QVBoxLayout(self.zone_list_widget)
        self.zone_list_layout.setSpacing(8)  # Better spacing between checkboxes
        self.zone_list_layout.setContentsMargins(10, 10, 10, 10)  # Add some padding
        
        # Create checkboxes for each zone
        self.zone_checkboxes = []
        for zone in self.available_zones:
            checkbox = QtWidgets.QCheckBox(zone)
            checkbox.setStyleSheet("QCheckBox { padding: 4px; }")  # Add padding to checkboxes
            self.zone_checkboxes.append(checkbox)
            self.zone_list_layout.addWidget(checkbox)
        
        # Add stretch to push checkboxes to the top if there are few zones
        if zone_count <= 3:
            self.zone_list_layout.addStretch()
        
        self.zone_list_scroll.setWidget(self.zone_list_widget)
        bulk_zone_layout.addWidget(self.zone_list_scroll)
        
        zone_layout.addWidget(self.bulk_zone_widget)
        self.bulk_zone_widget.setVisible(False)  # Hidden by default
        
        layout.addWidget(zone_group)
        
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
        
        self.include_metadata_cb = QtWidgets.QCheckBox("Include metadata (timestamps, etc.)")
        self.include_metadata_cb.setChecked(True)
        options_layout.addWidget(self.include_metadata_cb)
        
        layout.addWidget(options_group)
        
        # File selection
        file_group = QtWidgets.QGroupBox("Output File")
        file_layout = QtWidgets.QHBoxLayout(file_group)
        
        self.export_file_edit = QtWidgets.QLineEdit()
        self.export_file_edit.setPlaceholderText("Auto-generated filename will be used if empty...")
        file_layout.addWidget(self.export_file_edit)
        
        self.export_browse_btn = QtWidgets.QPushButton("Browse...")
        self.export_browse_btn.clicked.connect(self.browse_export_file)
        file_layout.addWidget(self.export_browse_btn)
        
        self.auto_filename_btn = QtWidgets.QPushButton("Auto-Generate")
        self.auto_filename_btn.clicked.connect(self.auto_generate_export_filename)
        file_layout.addWidget(self.auto_filename_btn)
        
        layout.addWidget(file_group)
        
        # Export button
        self.export_btn = QtWidgets.QPushButton("Export Zone")
        self.export_btn.clicked.connect(self.start_export)
        layout.addWidget(self.export_btn)
        
        layout.addStretch()
        return widget
    
    def create_import_tab(self):
        """Create the import tab."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # File selection
        file_group = QtWidgets.QGroupBox("Import File")
        file_layout = QtWidgets.QHBoxLayout(file_group)
        
        self.import_file_edit = QtWidgets.QLineEdit()
        self.import_file_edit.setPlaceholderText("Select file to import...")
        self.import_file_edit.textChanged.connect(self.on_import_file_changed)
        file_layout.addWidget(self.import_file_edit)
        
        self.import_browse_btn = QtWidgets.QPushButton("Browse...")
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
        target_help.setStyleSheet("color: #666; font-size: 11px;")
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
        
        existing_help = QtWidgets.QLabel(
            "• Append: Existing records remain unchanged, imported records are added\n"
            "• Merge: Update records that exist in both the zone and import file\n"
            "• Replace: Delete all existing records (except NS/SOA) before importing"
        )
        existing_help.setWordWrap(True)
        existing_help.setStyleSheet("color: #666; font-size: 11px;")
        existing_layout.addWidget(existing_help)
        
        layout.addWidget(existing_group)
        
        # Preview area
        preview_group = QtWidgets.QGroupBox("Import Preview")
        preview_layout = QtWidgets.QVBoxLayout(preview_group)
        
        self.preview_text = QtWidgets.QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(200)
        self.preview_text.setPlaceholderText("Select a file to preview import data...")
        preview_layout.addWidget(self.preview_text)
        
        layout.addWidget(preview_group)
        
        # Import buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        self.preview_btn = QtWidgets.QPushButton("Preview Import")
        self.preview_btn.clicked.connect(self.preview_import)
        self.preview_btn.setEnabled(False)
        button_layout.addWidget(self.preview_btn)
        
        self.import_btn = QtWidgets.QPushButton("Import Zone")
        self.import_btn.clicked.connect(self.start_import)
        self.import_btn.setEnabled(False)
        button_layout.addWidget(self.import_btn)
        
        layout.addLayout(button_layout)
        
        layout.addStretch()
        return widget
    
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
    
    def browse_import_file(self):
        """Browse for import file."""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Zone File", "", 
            "All Supported (*.json *.yaml *.yml *.zone *.data *.txt);;JSON Files (*.json);;YAML Files (*.yaml *.yml);;Zone Files (*.zone *.txt);;Data Files (*.data *.txt);;All Files (*)"
        )
        
        if file_path:
            self.import_file_edit.setText(file_path)
    
    def get_selected_export_format(self):
        """Get the selected export format."""
        for button in self.export_format_group.buttons():
            if button.isChecked():
                return button.property('format')
        return 'json'
    
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
    
    def on_bulk_export_toggled(self, checked):
        """Handle bulk export checkbox toggle."""
        self.single_zone_widget.setVisible(not checked)
        self.bulk_zone_widget.setVisible(checked)
        
        # Update export button text
        if checked:
            self.export_btn.setText("Export Selected Zones (ZIP)")
        else:
            self.export_btn.setText("Export Zone")
    
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
        """Auto-generate export filename based on zone and format."""
        if self.bulk_export_cb.isChecked():
            # For bulk export, generate ZIP filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bulk_export_{timestamp}.zip"
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Save Bulk Export ZIP", filename, "ZIP files (*.zip)"
            )
        else:
            # Single zone export
            zone_name = self.export_zone_combo.currentText()
            if not zone_name:
                self.show_error("Please select a zone first.")
                return
            
            format_type = self.get_selected_export_format()
            filename = self.import_export_manager.generate_export_filename(zone_name, format_type)
            
            # Get save location from user
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Save Export File", filename, self._get_file_filter(format_type)
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
    
    def on_import_file_changed(self):
        """Handle import file path change."""
        has_file = bool(self.import_file_edit.text().strip())
        self.preview_btn.setEnabled(has_file)
        self.import_btn.setEnabled(has_file)
        
        if not has_file:
            self.preview_text.clear()
    
    def start_export(self):
        """Start the export operation."""
        if self.bulk_export_cb.isChecked():
            # Bulk export mode
            selected_zones = self.get_selected_zones()
            if not selected_zones:
                self.show_error("Please select at least one zone to export.")
                return
            
            file_path = self.export_file_edit.text().strip()
            format_type = self.get_selected_export_format()
            
            # Auto-generate ZIP filename if not provided
            if not file_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"bulk_export_{timestamp}.zip"
                file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                    self, "Save Bulk Export ZIP", filename, "ZIP files (*.zip)"
                )
                if not file_path:
                    return  # User cancelled
            
            include_metadata = self.include_metadata_cb.isChecked()
            
            # Start worker thread for bulk export
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
        else:
            # Single zone export mode
            zone_name = self.export_zone_combo.currentText()
            if not zone_name:
                self.show_error("Please select a zone to export.")
                return
            
            file_path = self.export_file_edit.text().strip()
            format_type = self.get_selected_export_format()
            
            # Auto-generate filename if not provided
            if not file_path:
                filename = self.import_export_manager.generate_export_filename(zone_name, format_type)
                file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                    self, "Save Export File", filename, self._get_file_filter(format_type)
                )
                if not file_path:
                    return  # User cancelled
            
            include_metadata = self.include_metadata_cb.isChecked()
            
            # Start worker thread
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
    
    def on_export_finished(self, success, message, data):
        """Handle export completion."""
        self.set_operation_running(False)
        
        if success:
            self.show_success(f"Export completed successfully!\n{message}")
        else:
            self.show_error(f"Export failed:\n{message}")
    
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
    
    def on_progress_update(self, percentage, status):
        """Handle progress updates during import."""
        self.progress_bar.setValue(percentage)
        self.progress_bar.setFormat(f"{percentage}% - {status}")
    
    def on_import_finished(self, success, message, data):
        """Handle import completion."""
        self.set_operation_running(False)
        
        if success:
            self.show_success(f"Import completed successfully!\n{message}")
            # Emit signal to trigger sync in main window
            self.import_completed.emit()
        else:
            self.show_error(f"Import failed:\n{message}")
    
    def set_operation_running(self, running):
        """Set UI state for running operation."""
        self.progress_bar.setVisible(running)
        if running:
            self.progress_bar.setRange(0, 100)  # Determinate progress (0-100%)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("0% - Starting import...")
        
        # Disable/enable controls
        self.export_btn.setEnabled(not running)
        self.import_btn.setEnabled(not running and bool(self.import_file_edit.text().strip()))
        self.preview_btn.setEnabled(not running and bool(self.import_file_edit.text().strip()))
        
        if not running:
            self.status_label.clear()
    
    def show_success(self, message):
        """Show success message."""
        QtWidgets.QMessageBox.information(self, "Success", message)
        self.status_label.setText("Operation completed successfully.")
        self.status_label.setStyleSheet("color: green;")
    
    def show_error(self, message):
        """Show error message."""
        QtWidgets.QMessageBox.critical(self, "Error", message)
        self.status_label.setText("Operation failed.")
        self.status_label.setStyleSheet("color: red;")
    
    def closeEvent(self, event):
        """Handle dialog close event."""
        if self.worker and self.worker.isRunning():
            reply = QtWidgets.QMessageBox.question(
                self, "Operation in Progress",
                "An operation is currently running. Are you sure you want to close?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
            )
            
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                self.worker.terminate()
                self.worker.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
