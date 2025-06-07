#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Zone List Widget for deSEC Qt DNS Manager.
Displays and manages DNS zones with optimized performance.
"""

import logging
import webbrowser
from typing import List, Dict, Any, Tuple, Optional, Callable, Union

from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt, pyqtSignal, QThreadPool, QObject

from workers import LoadZonesWorker

logger = logging.getLogger(__name__)

# Custom model for the zones list
class ZoneListModel(QtCore.QAbstractListModel):
    """Custom model for efficiently displaying zone data."""
    
    def __init__(self, zones: Optional[List[Dict[str, Any]]] = None):
        """Initialize the model with zone data.
        
        Args:
            zones: Optional list of zone dictionaries
        """
        super().__init__()
        self.zones = zones or []
        self.filtered_zones: List[Dict[str, Any]] = []
        self.filter_text = ""
        # Cache for zone name lookups to avoid repetitive dictionary access
        self._zone_name_cache: Dict[int, str] = {}
        # Apply initial filtering
        self.apply_filter()
        
    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        """Return the number of rows in the model."""
        return len(self.filtered_zones)
        
    def data(self, index: QtCore.QModelIndex, role: int) -> Any:
        """Return data for the specified index and role."""
        if not index.isValid() or index.row() >= len(self.filtered_zones):
            return None
            
        row = index.row()
        
        if role == Qt.ItemDataRole.DisplayRole:
            # Use cached zone name if available to avoid repeated dictionary lookups
            if row not in self._zone_name_cache:
                self._zone_name_cache[row] = self.filtered_zones[row].get('name', '')
            return self._zone_name_cache[row]
        elif role == Qt.ItemDataRole.UserRole:
            return self.filtered_zones[row]
            
        return None
    
    def update_zones(self, zones: List[Dict[str, Any]]) -> None:
        """Update the model with new zone data.
        
        Args:
            zones: List of zone dictionaries
        """
        self.beginResetModel()
        self.zones = zones
        # Clear the zone name cache when updating zones
        self._zone_name_cache.clear()
        self.apply_filter()
        self.endResetModel()
    
    def apply_filter(self) -> None:
        """Apply current filter to the zone list."""
        if self.filter_text:
            # Convert filter text to lowercase once for efficiency
            filter_lower = self.filter_text.lower()
            
            # Use list comprehension for better performance
            self.filtered_zones = [
                zone for zone in self.zones
                if filter_lower in zone.get('name', '').lower()
            ]
        else:
            # Avoid unnecessary list copy when no filter is applied
            self.filtered_zones = self.zones
        
        # Clear the zone name cache when filter changes
        self._zone_name_cache.clear()
            
    def set_filter(self, filter_text: str) -> bool:
        """Set a new filter and apply it to the model.
        
        Args:
            filter_text: Text to filter zone names by
            
        Returns:
            True if filter changed, False otherwise
        """
        if self.filter_text == filter_text:
            return False  # No change
            
        self.filter_text = filter_text
        self.beginResetModel()
        self.apply_filter()
        self.endResetModel()
        return True  # Filter changed

class ZoneListWidget(QtWidgets.QWidget):
    """Widget for displaying and managing DNS zones."""
    
    # Custom signals
    zone_selected = pyqtSignal(str)  # Emitted when a zone is selected
    zone_added = pyqtSignal()        # Emitted when a zone is added
    zone_deleted = pyqtSignal()      # Emitted when a zone is deleted
    log_message = pyqtSignal(str, str)  # Emitted to log messages (message, level)
    
    def __init__(self, api_client, cache_manager, parent=None):
        """
        Initialize the zone list widget.
        
        Args:
            api_client: API client instance
            cache_manager: Cache manager instance
            parent: Parent widget, if any
        """
        super(ZoneListWidget, self).__init__(parent)
        
        self.api_client = api_client
        self.cache_manager = cache_manager
        self.zones = []
        self.thread_pool = QThreadPool.globalInstance()
        self.loading_indicator = None
        
        # Set up the UI
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)  # Standard 6px margin
        layout.setSpacing(6)  # Standard 6px spacing
        
        # Header section - title, count and search field
        header_layout = QtWidgets.QVBoxLayout()
        header_layout.setSpacing(6)  # Consistent spacing
        
        # Title and count
        title_layout = QtWidgets.QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        title = QtWidgets.QLabel("DNS Zones")
        title.setStyleSheet("font-weight: bold;")
        title.setMinimumWidth(100)  # Fixed width for right alignment
        title_layout.addWidget(title)
        
        title_layout.addStretch()
        
        self.zone_count_label = QtWidgets.QLabel("Total zones: 0")
        title_layout.addWidget(self.zone_count_label)
        
        header_layout.addLayout(title_layout)
        
        # Search field (match spacing with Record widget)
        search_layout = QtWidgets.QHBoxLayout()
        search_layout.setContentsMargins(0, 6, 0, 6)  # Add vertical padding
        
        search_label = QtWidgets.QLabel("Search:")
        search_label.setMinimumWidth(50)  # Fixed width for right alignment
        search_layout.addWidget(search_label)
        
        self.search_field = QtWidgets.QLineEdit()
        self.search_field.setFixedHeight(25)  # Consistent height with record widget
        self.search_field.setPlaceholderText("Type to filter zones...")
        self.search_field.textChanged.connect(self.filter_zones)
        search_layout.addWidget(self.search_field)
        
        header_layout.addLayout(search_layout)
        
        # Add header layout to main layout
        layout.addLayout(header_layout)
        
        # We don't need a loading indicator here as we use the status bar instead
        
        # Use model-view architecture for better performance
        self.zone_model = ZoneListModel()
        self.zone_list_view = QtWidgets.QListView()
        self.zone_list_view.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.zone_list_view.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.zone_list_view.setAlternatingRowColors(True)
        self.zone_list_view.setUniformItemSizes(True)
        self.zone_list_view.setStyleSheet(
            "QListView { border: 1px solid #ccc; }"
            "QListView::item { padding: 5px; }"
            "QListView::item:selected { background-color: #3daee9; color: white; }"
        )
        
        # Set the model for the view
        self.zone_list_view.setModel(self.zone_model)
        
        # Connect selection changed signal
        self.zone_list_view.selectionModel().currentChanged.connect(self.on_zone_selection_changed)
        
        # Add some vertical stretch to push buttons to the bottom
        layout.addWidget(self.zone_list_view, 1)  # Give stretch factor
        
        # Add action buttons (matching the style of record widget)
        actions_layout = QtWidgets.QHBoxLayout()
        actions_layout.setContentsMargins(0, 6, 0, 0)  # Add top margin for spacing
        
        # Store references to buttons to enable/disable in offline mode
        self.add_zone_btn = QtWidgets.QPushButton("Add Zone")
        self.add_zone_btn.clicked.connect(self.show_add_zone_dialog)
        actions_layout.addWidget(self.add_zone_btn)
        
        self.delete_zone_btn = QtWidgets.QPushButton("Delete Zone")
        self.delete_zone_btn.clicked.connect(self.delete_selected_zone)
        actions_layout.addWidget(self.delete_zone_btn)
        
        # Add DNSSEC validation button
        self.validate_dnssec_btn = QtWidgets.QPushButton("Validate DNSSEC")
        self.validate_dnssec_btn.clicked.connect(self.validate_dnssec)
        self.validate_dnssec_btn.setEnabled(False)  # Disabled by default until a zone is selected
        self.validate_dnssec_btn.setToolTip("Validate DNSSEC configuration for the selected domain")
        actions_layout.addWidget(self.validate_dnssec_btn)
        
        # Add spacer to push buttons to the left (same as record widget)
        actions_layout.addStretch()
        
        layout.addLayout(actions_layout)
    
    def load_zones(self, completion_callback=None):
        """Load zones from API or cache in the background.
        
        Args:
            completion_callback: Optional callback function that will be called when
                                zone loading is complete with parameters (success, zones, message)
        """
        # Get cached zones immediately 
        cached_zones, _ = self.cache_manager.get_cached_zones()
        if cached_zones is not None:
            self.zone_model.update_zones(cached_zones)
            # Update the zone count
            self.zone_count_label.setText(f"Total zones: {len(cached_zones)}")
        
        # Then fetch fresh data in the background
        worker = LoadZonesWorker(self.api_client, self.cache_manager)
        worker.signals.finished.connect(self.handle_zones_result)
        
        # Connect completion callback if provided
        if completion_callback:
            worker.signals.finished.connect(completion_callback)
            
        # Start the worker thread
        self.thread_pool.start(worker)
    
    def handle_zones_result(self, success, zones, message):
        """
        Handle the worker result.
        
        Args:
            success (bool): Whether the operation was successful
            zones (list): List of zone dictionaries
            message (str): Message from the worker
        """
        if zones is not None:
            # Check if zones data has actually changed to avoid unnecessary updates
            current_zones = self.zone_model.zones
            if not self._zones_equal(current_zones, zones):
                self.zone_model.update_zones(zones)
            else:
                # Even if zones didn't change, ensure count is updated
                filtered = self.zone_model.rowCount()
                
            # Update the zone count
            total = len(zones) 
            filtered = self.zone_model.rowCount()
            
            # Update zone count with optimized text setting (only when different)
            new_text = f"Showing {filtered} of {total} zones" if self.search_field.text() else f"Total zones: {total}"
            if self.zone_count_label.text() != new_text:
                self.zone_count_label.setText(new_text)
            
            # If we have a selection already, maintain it
            selected_indices = self.zone_list_view.selectedIndexes()
            if selected_indices and selected_indices[0].isValid():
                self.on_zone_selection_changed()
        
        # Show error message if operation failed
        if not success and message:
            self.log_message.emit(message, "error")
            
    def _zones_equal(self, zones1, zones2):
        """Compare two zone lists to see if they're effectively the same."""
        if zones1 is None or zones2 is None:
            return zones1 is zones2
        
        if len(zones1) != len(zones2):
            return False
        
        # Compare using sets of zone names for faster comparison
        names1 = {zone.get('name', '') for zone in zones1}
        names2 = {zone.get('name', '') for zone in zones2}
        return names1 == names2
    
    def filter_zones(self, filter_text):
        """
        Filter the zones list by domain name.
        
        Args:
            filter_text (str): Text to filter by
        """
        if self.zone_model.set_filter(filter_text):
            # Update the status label instead of logging
            count = self.zone_model.rowCount()
            total = len(self.zone_model.zones)
            
            if filter_text:
                self.zone_count_label.setText(f"Showing {count} of {total} zones")
            else:
                self.zone_count_label.setText(f"Total zones: {total}")
    
    def on_zone_selection_changed(self, current: QtCore.QModelIndex, previous: QtCore.QModelIndex) -> None:
        """Handler for zone selection changed event.
        
        Args:
            current: Currently selected index
            previous: Previously selected index
        """
        if not current.isValid():
            return
            
        # Get the zone name from the model
        zone_name = self.zone_model.data(current, Qt.ItemDataRole.DisplayRole)
        
        # Log zone selection
        logger.debug(f"Zone selected: {zone_name}")
        
        # Update button states based on selection
        has_selection = True  # We know we have a valid selection at this point
        self.delete_zone_btn.setEnabled(has_selection)
        self.validate_dnssec_btn.setEnabled(has_selection)
        
        # Emit signal with selected zone name
        self.zone_selected.emit(zone_name)
    
    def get_selected_zone(self) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Get the currently selected zone name and data."""
        indices = self.zone_list_view.selectedIndexes()
        
        if not indices or not indices[0].isValid():
            return None, None
            
        # Get zone data from the user role
        index = indices[0]
        zone_data = self.zone_model.data(index, Qt.ItemDataRole.UserRole)
        zone_name = zone_data.get('name', '')
        
        return zone_name, zone_data
        
    def validate_dnssec(self) -> None:
        """Open DNSSEC validation tool in browser for the selected domain."""
        zone_name, _ = self.get_selected_zone()
        if not zone_name:
            return
        
        try:
            # Construct the URL for the DNSSEC validator
            validation_url = f"https://dnssec-debugger.verisignlabs.com/{zone_name}"
            
            # Open the URL in the default web browser
            webbrowser.open(validation_url)
            
            self.log_message.emit(f"Opening DNSSEC validation for {zone_name}...", "info")
        except Exception as e:
            self.log_message.emit(f"Failed to open DNSSEC validation: {str(e)}", "error")
            logger.error(f"Failed to open DNSSEC validation: {e}")
    
    def show_add_zone_dialog(self):
        """Show dialog to add a new zone."""
        if not self.api_client.is_online:
            self.log_message.emit("Cannot add zone in offline mode", "warning")
            return
            
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Add Zone")
        dialog.setMinimumWidth(400)
        
        layout = QtWidgets.QVBoxLayout(dialog)
        
        # Add form layout
        form_layout = QtWidgets.QFormLayout()
        zone_input = QtWidgets.QLineEdit()
        zone_input.setPlaceholderText("example.com")
        form_layout.addRow("Domain Name:", zone_input)
        layout.addLayout(form_layout)
        
        # Add explanation
        explanation = QtWidgets.QLabel(
            "Enter the domain name you want to manage through deSEC. "
            "You must own this domain or have the rights to manage it."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(explanation)
        
        # Add buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            zone_name = zone_input.text().strip()
            
            if not zone_name:
                self.log_message.emit("Zone name cannot be empty", "warning")
                return
                
            self.add_zone(zone_name)
    
    def add_zone(self, zone_name):
        """
        Add a new zone.
        
        Args:
            zone_name (str): Zone name to add
        """
        if not self.api_client.is_online:
            self.log_message.emit("Cannot add zone in offline mode", "warning")
            return
            
        self.log_message.emit(f"Adding zone {zone_name}...", "info")
        
        success, response = self.api_client.create_zone(zone_name)
        
        if success:
            self.log_message.emit(f"Zone {zone_name} added successfully", "success")
            self.zone_added.emit()
        else:
            self.log_message.emit(f"Failed to add zone: {response}", "error")
    
    def delete_selected_zone(self):
        """Delete the currently selected zone."""
        if not self.api_client.is_online:
            self.log_message.emit("Cannot delete zone in offline mode", "warning")
            return
            
        zone_name, _ = self.get_selected_zone()
        
        if not zone_name:
            self.log_message.emit("No zone selected", "warning")
            return
            
        # Confirm deletion
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete the zone '{zone_name}'?\n\n"
            "This will delete all DNS records for this zone and cannot be undone.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No
        )
        
        if confirm == QtWidgets.QMessageBox.StandardButton.Yes:
            self.delete_zone(zone_name)
    
    def set_edit_enabled(self, enabled: bool) -> None:
        """Enable or disable edit functionality."""
        has_selection = len(self.zone_list_view.selectedIndexes()) > 0
        
        # Enable/disable add zone button
        if hasattr(self, 'add_zone_btn'):
            self.add_zone_btn.setEnabled(enabled)
            # Update the tooltip to explain why it's disabled
            if not enabled:
                self.add_zone_btn.setToolTip("Adding zones is disabled in offline mode")
            else:
                self.add_zone_btn.setToolTip("")
        
        # Enable/disable delete zone button
        if hasattr(self, 'delete_zone_btn'):
            self.delete_zone_btn.setEnabled(enabled and has_selection)
            # Update the tooltip to explain why it's disabled
            if not enabled:
                self.delete_zone_btn.setToolTip("Deleting zones is disabled in offline mode")
            else:
                self.delete_zone_btn.setToolTip("")
                
        # Enable/disable DNSSEC validation button - always available when zone selected
        # regardless of online/offline status since it uses external browser
        if hasattr(self, 'validate_dnssec_btn'):
            self.validate_dnssec_btn.setEnabled(has_selection)
                
    def delete_zone(self, zone_name):
        """Delete a zone.
        
        Args:
            zone_name (str): The name of the zone to delete
        """
        # Log the attempt
        self.log_message.emit(f"Deleting zone: {zone_name}", "info")
        
        # Try to delete the zone
        success, response = self.api_client.delete_zone(zone_name)
        
        if success:
            self.log_message.emit(f"Zone {zone_name} deleted successfully", "success")
            self.cache_manager.clear_domain_cache(zone_name)
            self.zone_deleted.emit()
        else:
            self.log_message.emit(f"Failed to delete zone: {response}", "error")
