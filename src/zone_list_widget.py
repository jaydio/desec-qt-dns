#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Zone List Widget for deSEC Qt DNS Manager.
Displays and manages DNS zones.
"""

import logging
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt, pyqtSignal

logger = logging.getLogger(__name__)

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
        self.filtered_zones = []
        self.filter_text = ""
        
        # Set up the UI
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface."""
        layout = QtWidgets.QVBoxLayout(self)
        
        # Title
        title = QtWidgets.QLabel("DNS Zones")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        
        # Zone list
        self.zone_list = QtWidgets.QListWidget()
        self.zone_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.zone_list.itemSelectionChanged.connect(self.on_zone_selection_changed)
        layout.addWidget(self.zone_list)
    
    def load_zones(self):
        """Load zones from the API or cache."""
        if self.api_client.is_online:
            # Online mode - get zones from API
            success, response = self.api_client.get_zones()
            
            if success:
                self.zones = response
                self.cache_manager.cache_zones(self.zones)
                self.update_zone_list()
            else:
                self.log_message.emit(f"Failed to load zones: {response}", "error")
                # Try to load from cache as fallback
                self._load_from_cache()
        else:
            # Offline mode - get zones from cache
            self._load_from_cache()
    
    def _load_from_cache(self):
        """Load zones from cache."""
        cached_zones, timestamp = self.cache_manager.get_cached_zones()
        
        if cached_zones is not None:
            self.zones = cached_zones
            self.update_zone_list()
            self.log_message.emit(f"Loaded {len(cached_zones)} zones from cache", "info")
        else:
            self.log_message.emit("No cached zones available", "warning")
            self.zones = []
            self.update_zone_list()
    
    def update_zone_list(self):
        """Update the zone list with current zones (applying filtering if needed)."""
        self.zone_list.clear()
        
        # Apply filter
        if self.filter_text:
            self.filtered_zones = [
                zone for zone in self.zones
                if self.filter_text.lower() in zone.get('name', '').lower()
            ]
        else:
            self.filtered_zones = self.zones
        
        # Add zones to the list
        for zone in self.filtered_zones:
            name = zone.get('name', '')
            item = QtWidgets.QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, zone)
            self.zone_list.addItem(item)
        
        # Update status
        count = len(self.filtered_zones)
        total = len(self.zones)
        if self.filter_text and count < total:
            self.log_message.emit(f"Showing {count} of {total} zones", "info")
    
    def filter_zones(self, filter_text):
        """
        Filter the zones list by domain name.
        
        Args:
            filter_text (str): Text to filter by
        """
        self.filter_text = filter_text
        self.update_zone_list()
    
    def on_zone_selection_changed(self):
        """Handle zone selection change."""
        selected_items = self.zone_list.selectedItems()
        
        if not selected_items:
            return
            
        zone_item = selected_items[0]
        zone_name = zone_item.text()
        
        # Emit signal with selected zone name
        self.zone_selected.emit(zone_name)
    
    def get_selected_zone(self):
        """
        Get the currently selected zone.
        
        Returns:
            tuple: (zone_name, zone_data) or (None, None) if no zone is selected
        """
        selected_items = self.zone_list.selectedItems()
        
        if not selected_items:
            return None, None
            
        zone_item = selected_items[0]
        zone_name = zone_item.text()
        zone_data = zone_item.data(Qt.ItemDataRole.UserRole)
        
        return zone_name, zone_data
    
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
    
    def delete_zone(self, zone_name):
        """
        Delete a zone.
        
        Args:
            zone_name (str): Zone name to delete
        """
        if not self.api_client.is_online:
            self.log_message.emit("Cannot delete zone in offline mode", "warning")
            return
            
        self.log_message.emit(f"Deleting zone {zone_name}...", "info")
        
        success, response = self.api_client.delete_zone(zone_name)
        
        if success:
            self.log_message.emit(f"Zone {zone_name} deleted successfully", "success")
            self.cache_manager.clear_domain_cache(zone_name)
            self.zone_deleted.emit()
        else:
            self.log_message.emit(f"Failed to delete zone: {response}", "error")
