#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Main window implementation for deSEC Qt DNS Manager.
Implements the two-pane layout and coordinates between UI components.
"""

import logging
import time

from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt, QTimer

from auth_dialog import AuthDialog
from config_dialog import ConfigDialog
from zone_list_widget import ZoneListWidget
from record_widget import RecordWidget
from log_widget import LogWidget

logger = logging.getLogger(__name__)

class MainWindow(QtWidgets.QMainWindow):
    """Main application window with two-pane layout for zones and records."""
    
    def __init__(self, config_manager, api_client, cache_manager, parent=None):
        """
        Initialize the main window.
        
        Args:
            config_manager: Configuration manager instance
            api_client: API client instance
            cache_manager: Cache manager instance
            parent: Parent widget, if any
        """
        super(MainWindow, self).__init__(parent)
        
        self.config_manager = config_manager
        self.api_client = api_client
        self.cache_manager = cache_manager
        
        # Set up the UI
        self.setup_ui()
        
        # If no auth token is set, prompt for it
        if not self.config_manager.get_auth_token():
            self.show_auth_dialog()
        
        # Start the sync timer
        self.setup_sync_timer()
        
        # Initial sync
        self.sync_data()
    
    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("deSEC Qt DNS Manager")
        self.resize(1000, 700)
        
        # Create central widget and main layout
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QtWidgets.QVBoxLayout(central_widget)
        
        # Offline mode indicator
        self.offline_indicator = QtWidgets.QLabel()
        self.offline_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.offline_indicator)
        
        # Create splitter for the two-pane layout
        splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left pane - Zones
        zones_widget = QtWidgets.QWidget()
        zones_layout = QtWidgets.QVBoxLayout(zones_widget)
        
        # Zone search field
        search_layout = QtWidgets.QHBoxLayout()
        search_label = QtWidgets.QLabel("Search Zones:")
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Enter domain name...")
        self.search_input.textChanged.connect(self.filter_zones)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        zones_layout.addLayout(search_layout)
        
        # Zone list
        self.zone_list = ZoneListWidget(self.api_client, self.cache_manager)
        self.zone_list.zone_selected.connect(self.on_zone_selected)
        self.zone_list.zone_added.connect(self.sync_data)
        self.zone_list.zone_deleted.connect(self.sync_data)
        self.zone_list.log_message.connect(self.log_message)
        zones_layout.addWidget(self.zone_list)
        
        # Zone actions
        zone_actions_layout = QtWidgets.QHBoxLayout()
        self.add_zone_btn = QtWidgets.QPushButton("Add Zone")
        self.add_zone_btn.clicked.connect(self.zone_list.show_add_zone_dialog)
        self.delete_zone_btn = QtWidgets.QPushButton("Delete Zone")
        self.delete_zone_btn.clicked.connect(self.zone_list.delete_selected_zone)
        zone_actions_layout.addWidget(self.add_zone_btn)
        zone_actions_layout.addWidget(self.delete_zone_btn)
        zones_layout.addLayout(zone_actions_layout)
        
        # Right pane - Records
        records_widget = QtWidgets.QWidget()
        records_layout = QtWidgets.QVBoxLayout(records_widget)
        
        # Records view/edit
        self.record_widget = RecordWidget(self.api_client, self.cache_manager)
        self.record_widget.records_changed.connect(self.on_records_changed)
        self.record_widget.log_message.connect(self.log_message)
        records_layout.addWidget(self.record_widget)
        
        # Add widgets to splitter
        splitter.addWidget(zones_widget)
        splitter.addWidget(records_widget)
        splitter.setStretchFactor(0, 1)  # Left pane
        splitter.setStretchFactor(1, 2)  # Right pane
        
        # Log panel
        self.log_widget = LogWidget()
        main_layout.addWidget(self.log_widget)
        
        # Status bar
        self.statusBar().showMessage("Ready")
        
        # Create menus
        self.create_menus()
        
        # Update offline indicator now that all UI elements are initialized
        self.update_offline_indicator()
    
    def create_menus(self):
        """Create application menus."""
        # File menu
        file_menu = self.menuBar().addMenu("&File")
        
        # Sync action
        sync_action = QtGui.QAction("&Sync Now", self)
        sync_action.setShortcut("Ctrl+R")
        sync_action.triggered.connect(self.sync_data)
        file_menu.addAction(sync_action)
        
        # Configuration action
        config_action = QtGui.QAction("&Configuration", self)
        config_action.triggered.connect(self.show_config_dialog)
        file_menu.addAction(config_action)
        
        file_menu.addSeparator()
        
        # Exit action
        exit_action = QtGui.QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Help menu
        help_menu = self.menuBar().addMenu("&Help")
        
        # About action
        about_action = QtGui.QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def setup_sync_timer(self):
        """Set up the timer for periodic data synchronization."""
        self.sync_timer = QtCore.QTimer(self)
        self.sync_timer.timeout.connect(self.sync_data)
        # Set interval from config (in minutes, convert to milliseconds)
        interval_ms = self.config_manager.get_sync_interval() * 60 * 1000
        self.sync_timer.start(interval_ms)
        logger.info(f"Sync timer started with interval of {self.config_manager.get_sync_interval()} minutes")
    
    def update_sync_interval(self):
        """Update the sync timer interval based on configuration."""
        interval_ms = self.config_manager.get_sync_interval() * 60 * 1000
        self.sync_timer.setInterval(interval_ms)
        logger.info(f"Sync interval updated to {self.config_manager.get_sync_interval()} minutes")
    
    def update_offline_indicator(self):
        """Update the offline mode indicator."""
        is_online = self.api_client.is_online
        
        if is_online:
            self.offline_indicator.setText("")
            self.offline_indicator.setVisible(False)
        else:
            self.offline_indicator.setText("⚠️ OFFLINE MODE - Read Only ⚠️")
            self.offline_indicator.setVisible(True)
            self.offline_indicator.setStyleSheet("background-color: #FFF3CD; color: #856404; font-weight: bold; padding: 5px;")
        
        # Update UI components' enabled states
        self.add_zone_btn.setEnabled(is_online)
        self.delete_zone_btn.setEnabled(is_online)
        self.record_widget.set_online_status(is_online)
    
    def sync_data(self):
        """Synchronize data with the API."""
        if not self.config_manager.get_auth_token():
            self.log_message("No API token configured. Please set up your authentication token.", "warning")
            return
        
        # Check connectivity
        if not self.api_client.check_connectivity():
            self.log_message("Offline mode active - using cached data", "warning")
            self.update_offline_indicator()
            return
        
        # Update offline indicator
        self.update_offline_indicator()
        
        # Sync zones
        self.log_message("Syncing data...", "info")
        self.statusBar().showMessage("Syncing data...")
        
        # Reload zone list (which will trigger reloading of records if a zone is selected)
        self.zone_list.load_zones()
        
        # Update status
        last_sync = time.strftime("%H:%M:%S")
        self.statusBar().showMessage(f"Last sync: {last_sync}")
        self.log_message(f"Data synchronized successfully", "success")
    
    def filter_zones(self, filter_text):
        """
        Filter the zones list by domain name.
        
        Args:
            filter_text (str): Text to filter by
        """
        self.zone_list.filter_zones(filter_text)
    
    def on_zone_selected(self, domain_name):
        """
        Handle zone selection.
        
        Args:
            domain_name (str): Selected domain name
        """
        self.record_widget.set_domain(domain_name)
    
    def on_records_changed(self):
        """Handle record changes."""
        # Refresh the currently selected zone's records
        self.record_widget.refresh_records()
    
    def show_auth_dialog(self):
        """Show the authentication dialog to get the API token."""
        dialog = AuthDialog(self.config_manager, self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            # Token was set, initialize API client
            self.api_client.check_connectivity()
            self.update_offline_indicator()
            self.sync_data()
        else:
            # User cancelled
            self.log_message("Authentication required to use the application", "warning")
    
    def show_config_dialog(self):
        """Show the configuration dialog."""
        dialog = ConfigDialog(self.config_manager, self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.update_sync_interval()
            self.api_client.check_connectivity()
            self.update_offline_indicator()
            self.sync_data()
    
    def log_message(self, message, level="info"):
        """
        Add a message to the log panel.
        
        Args:
            message (str): Message to log
            level (str): Message level (info, warning, error, success)
        """
        self.log_widget.add_message(message, level)
        
        # Also log to the application logger
        if level == "info":
            logger.info(message)
        elif level == "warning":
            logger.warning(message)
        elif level == "error":
            logger.error(message)
        elif level == "success":
            logger.info(f"SUCCESS: {message}")
    
    def show_about(self):
        """Show the about dialog."""
        about_text = (
            "<html>"
            "<head><style>body { font-family: sans-serif; margin: 15px; }</style></head>"
            "<body>"
            "<h2 align=\"center\">deSEC Qt DNS Manager</h2>"
            "<p align=\"center\">A desktop application for managing DNS zones and records<br/>"
            "using the deSEC API.</p>"
            "<p align=\"center\"><b>Version 0.2.1</b></p>"
            "<p align=\"center\"><a href=\"https://github.com/jaydio/desec-qt-dns/blob/master/CHANGELOG.md\">View Changelog</a></p>"
            "<hr/>"
            "<p align=\"center\">🚀 Developed by <b>JD Bungart</b></p>"
            "<p align=\"center\">✉️ <a href=\"mailto:me@jdneer.com\">me@jdneer.com</a></p>"
            "<p align=\"center\">💻 <a href=\"https://github.com/jaydio/\">github.com/jaydio</a></p>"
            "<hr/>"
            "<p align=\"center\"><small>Released under MIT License</small></p>"
            "</body>"
            "</html>"
        )
        
        # Create a custom about dialog with rich text support
        about_dialog = QtWidgets.QDialog(self)
        about_dialog.setWindowTitle("About deSEC Qt6 DNS Manager")
        about_dialog.setMinimumWidth(400)
        about_dialog.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Preferred)
        
        layout = QtWidgets.QVBoxLayout(about_dialog)
        
        # Logo/Icon placeholder - could be replaced with actual app icon
        icon_label = QtWidgets.QLabel()
        icon = QtGui.QIcon.fromTheme("network-server")
        icon_label.setPixmap(icon.pixmap(64, 64))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)
        
        # About text - using QLabel instead of QTextBrowser to avoid scrolling
        text = QtWidgets.QLabel()
        text.setTextFormat(QtCore.Qt.TextFormat.RichText)
        text.setText(about_text)
        text.setOpenExternalLinks(True)  # Allow links to be clickable
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text.setWordWrap(True)  # Enable text wrapping
        layout.addWidget(text)
        
        # Set size policy to fit content
        text.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Preferred)
        text.adjustSize()
        
        # Close button
        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(about_dialog.close)
        layout.addWidget(button_box)
        
        # Adjust dialog size to fit content after layout is set
        about_dialog.adjustSize()
        about_dialog.exec()
    
    def closeEvent(self, event):
        """Handle window close event."""
        # Save any pending changes to configuration
        self.config_manager.save_config()
        event.accept()
