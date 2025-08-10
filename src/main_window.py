#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Main window implementation for deSEC Qt DNS Manager.
Implements the two-pane layout and coordinates between UI components.
"""

import logging
import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable, Union

from PyQt6 import QtWidgets, QtCore, QtGui, uic
from PyQt6.QtCore import Qt, QThreadPool, QTimer
from PyQt6.QtWidgets import QMessageBox

from workers import LoadRecordsWorker

from auth_dialog import AuthDialog
from config_dialog import ConfigDialog
from profile_dialog import ProfileDialog
from import_export_manager import ImportExportManager
from import_export_dialog import ImportExportDialog
from zone_list_widget import ZoneListWidget
from record_widget import RecordWidget
from log_widget import LogWidget
from theme_manager import ThemeManager

logger = logging.getLogger(__name__)

class MainWindow(QtWidgets.QMainWindow):
    """Main application window with two-pane layout for zones and records."""
    
    def __init__(self, config_manager, api_client, cache_manager, profile_manager=None, parent=None):
        """
        Initialize the main window.
        
        Args:
            config_manager: Configuration manager instance
            api_client: API client instance
            cache_manager: Cache manager instance
            profile_manager: Profile manager instance (optional for backward compatibility)
            parent: Parent widget, if any
        """
        super(MainWindow, self).__init__(parent)
        
        self.config_manager = config_manager
        self.api_client = api_client
        self.cache_manager = cache_manager
        self.profile_manager = profile_manager
        
        # Initialize import/export manager
        self.import_export_manager = ImportExportManager(api_client, cache_manager)
        
        # Initialize theme manager
        self.theme_manager = ThemeManager(config_manager)
        
        # Initialize thread pool for background tasks
        self.thread_pool = QThreadPool()
        
        # Set up the UI
        self.setup_ui()
        
        # Apply the current theme
        self.theme_manager.apply_theme()
        
        # If no auth token is set, prompt for it
        if not self.config_manager.get_auth_token():
            self.show_auth_dialog()
        
        # Start the sync timer
        self.setup_sync_timer()
        
        # Ensure offline mode is properly initialized (default to online mode unless explicitly configured)
        is_offline_mode = self.config_manager.get_offline_mode()
        self.offline_mode_action.setChecked(is_offline_mode)
        
        # Set initial connection status based on offline mode setting
        self.update_connection_status(not is_offline_mode)
        
        # Initial sync (will respect offline mode)
        self.sync_data()
        
        # Update record edit state
        self.update_record_edit_state()
    
    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("deSEC Qt DNS Manager")
        self.resize(1200, 700)
        
        # Create status bar
        self.statusBar().setStyleSheet("QStatusBar { border-top: 1px solid #ccc; }")
        
        # Create widgets for the status bar
        self.last_sync_label = QtWidgets.QLabel("Last sync: Never")
        self.sync_status_label = QtWidgets.QLabel("INITIALIZING")
        
        # Set up status label style
        self.online_style = "QLabel { color: green; font-weight: bold; }"
        self.offline_style = "QLabel { color: red; font-weight: bold; }"
        self.initializing_style = "QLabel { color: orange; font-weight: bold; }"
        self.sync_status_label.setStyleSheet(self.initializing_style)
        
        # Add last sync time to the regular (left) side of the status bar
        self.statusBar().addWidget(self.last_sync_label)
        
        # Add sync status to the permanent (right) side of the status bar
        self.statusBar().addPermanentWidget(self.sync_status_label)
        
        # Set initial connection status
        self.update_connection_status(None)
        
        # Initialize last sync time and timer for elapsed time
        self.last_sync_time = None
        self.sync_timer = QtCore.QTimer(self)
        self.sync_timer.timeout.connect(self.update_elapsed_time)
        self.sync_timer.start(1000)  # Update every second
        
        # Create central widget and main layout
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QtWidgets.QVBoxLayout(central_widget)
        
        # Main layout continues below
        
        # Create splitter for the two-pane layout
        splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        # Set splitter to expand vertically when possible
        size_policy = splitter.sizePolicy()
        size_policy.setVerticalPolicy(QtWidgets.QSizePolicy.Policy.Expanding)
        size_policy.setVerticalStretch(1)
        splitter.setSizePolicy(size_policy)
        main_layout.addWidget(splitter)
        
        # Left pane - Zones
        zones_widget = QtWidgets.QWidget()
        zones_layout = QtWidgets.QVBoxLayout(zones_widget)
        zones_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins for better spacing
        
        # Zone list (now includes search field and action buttons)
        self.zone_list = ZoneListWidget(self.api_client, self.cache_manager)
        self.zone_list.zone_selected.connect(self.on_zone_selected)
        self.zone_list.zone_added.connect(self.sync_data)
        self.zone_list.zone_deleted.connect(self.on_zone_deleted)
        self.zone_list.log_message.connect(self.log_message)
        zones_layout.addWidget(self.zone_list)
        
        # Right pane - Records
        records_widget = QtWidgets.QWidget()
        records_layout = QtWidgets.QVBoxLayout(records_widget)
        records_layout.setContentsMargins(0, 0, 0, 0)  # Match the zones pane margins
        
        # Records view/edit
        self.record_widget = RecordWidget(self.api_client, self.cache_manager, self.config_manager)
        self.record_widget.records_changed.connect(self.on_records_changed)
        self.record_widget.log_message.connect(self.log_message)
        records_layout.addWidget(self.record_widget)
        
        # Add widgets to splitter
        splitter.addWidget(zones_widget)
        splitter.addWidget(records_widget)
        splitter.setStretchFactor(0, 1)  # Left pane (zones)
        splitter.setStretchFactor(1, 2)  # Right pane (records)
        
        # Set consistent splitter handle width for better appearance
        splitter.setHandleWidth(6)
        
        # Create log panel
        self.log_widget = LogWidget()
        
        # Check if this is initial setup (no auth token yet)
        is_initial_setup = not self.config_manager.get_auth_token()
        
        # For initial setup, always hide log console regardless of config
        if is_initial_setup:
            self.log_visible = False
            # Also update config to match this state
            self.config_manager.set_show_log_console(False)
        else:
            # Use configured visibility for existing profiles
            self.log_visible = self.config_manager.get_show_log_console()
            
        # Always add to layout, just control visibility
        main_layout.addWidget(self.log_widget)
        
        # Set initial visibility based on configuration
        if not self.log_visible:
            self.log_widget.hide()  # Keep widget in layout but hidden
        
        # Status bar
        # Show Ready message with a short timeout to avoid overlapping with sync status
        self.statusBar().showMessage("Ready", 2000)  # Show for 2 seconds only
        
        # Create menus
        self.create_menus()
        
    def create_menus(self):
        """Create application menus."""
        # Create menu bar
        menu_bar = self.menuBar()
        
        # File menu
        file_menu = menu_bar.addMenu("&File")
        
        # Add action for reconfiguring
        config_action = QtGui.QAction("&Settings...", self)
        config_action.setStatusTip("Configure API URL and token")
        config_action.triggered.connect(self.show_config_dialog)
        file_menu.addAction(config_action)
        
        # Clear Cache menu item
        clear_cache_action = QtGui.QAction("&Clear Cache", self)
        clear_cache_action.setStatusTip("Clear all cached data and initiate a new sync")
        clear_cache_action.triggered.connect(self.clear_cache)
        file_menu.addAction(clear_cache_action)
        
        # Add separator
        file_menu.addSeparator()
        
        # Import/Export menu item
        import_export_action = QtGui.QAction("&Import/Export...", self)
        import_export_action.setStatusTip("Import or export DNS zones and records")
        import_export_action.triggered.connect(self.show_import_export_dialog)
        file_menu.addAction(import_export_action)
        
        # Add separator
        file_menu.addSeparator()
        
        # Quit action
        quit_action = QtGui.QAction("&Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.setStatusTip("Quit the application")
        quit_action.triggered.connect(self._confirm_quit_dialog)
        file_menu.addAction(quit_action)
        
        # Profile menu (only show if profile manager is available)
        if self.profile_manager:
            profile_menu = menu_bar.addMenu("&Profile")
            
            # Current profile info
            current_profile = self.profile_manager.get_current_profile_info()
            if current_profile:
                current_profile_action = QtGui.QAction(f"Current: {current_profile['display_name']}", self)
                current_profile_action.setEnabled(False)  # Just for display
                profile_menu.addAction(current_profile_action)
                profile_menu.addSeparator()
            
            # Manage profiles action
            manage_profiles_action = QtGui.QAction("&Manage Profiles...", self)
            manage_profiles_action.setStatusTip("Create, switch, rename, or delete profiles")
            manage_profiles_action.triggered.connect(self.show_profile_dialog)
            profile_menu.addAction(manage_profiles_action)
        
        # Connection menu
        connection_menu = menu_bar.addMenu("&Connection")
        
        # Sync now action
        sync_now_action = QtGui.QAction("&Sync Now", self)
        sync_now_action.setToolTip("Manually synchronize with the API")
        sync_now_action.setStatusTip("Manually synchronize with the API")
        sync_now_action.triggered.connect(self.sync_data)
        connection_menu.addAction(sync_now_action)
        
        # Offline mode action
        self.offline_mode_action = QtGui.QAction("&Offline Mode", self)
        self.offline_mode_action.setStatusTip("Work without an internet connection")
        self.offline_mode_action.setCheckable(True)
        self.offline_mode_action.triggered.connect(self.toggle_offline_mode)
        connection_menu.addAction(self.offline_mode_action)
        
        # View menu
        view_menu = menu_bar.addMenu("&View")
        
        # Show log console action
        self.toggle_log_action = QtGui.QAction("Show &Log Console", self)
        self.toggle_log_action.setCheckable(True)
        self.toggle_log_action.setChecked(self.config_manager.get_show_log_console())
        self.toggle_log_action.triggered.connect(self.toggle_log_console)
        view_menu.addAction(self.toggle_log_action)
        
        # Multiline records display toggle
        self.show_multiline_records_action = QtGui.QAction("Show &Multiline Records", self)
        self.show_multiline_records_action.setStatusTip("Display multiline record content in full")
        self.show_multiline_records_action.setCheckable(True)
        # Set checked state based on configuration
        self.show_multiline_records_action.setChecked(self.config_manager.get_show_multiline_records())
        self.show_multiline_records_action.triggered.connect(self.toggle_multiline_records)
        view_menu.addAction(self.show_multiline_records_action)
        
        # Add a separator
        view_menu.addSeparator()
        
        # Help menu
        help_menu = menu_bar.addMenu("&Help")
        
        # Changelog menu item
        changelog_action = QtGui.QAction("&Changelog", self)
        changelog_action.setStatusTip("View the application changelog")
        changelog_action.triggered.connect(self.show_changelog)
        help_menu.addAction(changelog_action)
        
        # Keyboard Shortcuts menu item
        keyboard_shortcuts_action = QtGui.QAction("&Hotkeys", self)
        keyboard_shortcuts_action.setStatusTip("View all keyboard shortcuts")
        keyboard_shortcuts_action.triggered.connect(self.show_keyboard_shortcuts_dialog)
        help_menu.addAction(keyboard_shortcuts_action)

        # About menu item
        about_action = QtGui.QAction("&About", self)
        about_action.setStatusTip("Show information about this application")
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def setup_sync_timer(self):
        """Set up the timer for periodic data synchronization."""
        # Timer for zone/record synchronization
        self.sync_timer_id = QtCore.QTimer(self)
        self.sync_timer_id.timeout.connect(self.sync_data)
        
        # Get sync interval from configuration
        interval_minutes = self.config_manager.get_sync_interval()
        interval_ms = interval_minutes * 60 * 1000
        
        self.sync_timer_id.start(interval_ms)
        logger.info(f"Sync timer started with interval of {interval_minutes} minutes")
        
        # Set up keepalive timer to check API connectivity
        self.keepalive_timer = QtCore.QTimer(self)
        self.keepalive_timer.timeout.connect(self.check_api_connectivity)
        
        # Get keepalive interval from configuration
        keepalive_seconds = self.config_manager.get_keepalive_interval()
        keepalive_ms = keepalive_seconds * 1000
        
        self.keepalive_timer.start(keepalive_ms)
        logger.info(f"Keepalive timer started with interval of {keepalive_seconds} seconds")
    
    def update_sync_interval(self):
        """Update the sync timer interval based on configuration."""
        interval_minutes = self.config_manager.get_sync_interval()
        self.sync_timer_id.setInterval(interval_minutes * 60 * 1000)
        logger.info(f"Sync timer set to {interval_minutes} minutes")
        self.log_message(f"Sync timer set to {interval_minutes} minutes")

    def check_api_connectivity(self, manual_check=False):
        """Check API connectivity and update status display.
        
        Args:
            manual_check (bool): True if this check was manually triggered by the user
        """
        # Skip connectivity check if offline mode is enabled in config
        if self.config_manager.get_offline_mode():
            self.update_connection_status(False)
            if manual_check:
                self.log_message("Connectivity check skipped - Offline mode is enabled", "warning")
                # Show a temporary status bar message
                self.statusBar().showMessage("Offline mode is enabled - Connection check skipped", 3000)
            return
            
        # Show checking status before starting worker
        if manual_check:
            self.statusBar().showMessage("Checking API connectivity...", 3000)
            self.log_message("Checking API connectivity...", "info")
            # Temporarily set status to initializing during the check
            self.sync_status_label.setText("CHECKING")
            self.sync_status_label.setStyleSheet(self.initializing_style)
            # Force immediate UI update
            QtWidgets.QApplication.processEvents()
            
        # Run API connectivity check in a thread to avoid blocking UI
        # Using QObject with signals for thread communication
        class ConnectivitySignals(QtCore.QObject):
            result_ready = QtCore.pyqtSignal(bool, bool)  # is_online, manual_check
            
        class ConnectivityWorker(QtCore.QRunnable):
            def __init__(self, api_client, manual_check):
                super().__init__()
                self.api_client = api_client
                self.manual_check = manual_check
                self.signals = ConnectivitySignals()
                
            def run(self):
                is_online = self.api_client.check_connectivity()
                # Emit signal with result and manual_check flag
                self.signals.result_ready.emit(is_online, self.manual_check)
        
        worker = ConnectivityWorker(self.api_client, manual_check)
        worker.signals.result_ready.connect(self._handle_connectivity_result)
        self.thread_pool.start(worker)
        
    def _handle_connectivity_result(self, is_online, manual_check):
        """Handle connectivity check result.
        
        Args:
            is_online (bool): True if API is online, False otherwise
            manual_check (bool): True if check was manually triggered
        """
        self.update_connection_status(is_online)
        
        if manual_check:
            if is_online:
                self.statusBar().showMessage("API connection successful", 5000)
                self.log_message("API connection check successful", "success")
            else:
                self.statusBar().showMessage("API connection failed", 5000)
                self.log_message("API connection check failed - API is unreachable", "error")
    
    def update_connection_status(self, is_online):
        """Update the connection status display.
        
        Args:
            is_online (bool or None): True for online, False for offline, None for initializing
        """
        if is_online is None:
            # Initializing
            self.sync_status_label.setText("INITIALIZING")
            self.sync_status_label.setStyleSheet(self.initializing_style)
        elif is_online:
            # Online
            self.sync_status_label.setText("ONLINE")
            self.sync_status_label.setStyleSheet(self.online_style)
        else:
            # Offline
            self.sync_status_label.setText("OFFLINE")
            self.sync_status_label.setStyleSheet(self.offline_style)
        
        # Update record widget button states based on online status
        if hasattr(self, 'record_table') and self.record_table is not None:
            self.record_table.set_edit_enabled(is_online is True and not self.config_manager.get_offline_mode())
    
    # Note: Offline indicator banner has been removed
    
    def update_record_edit_state(self):
        """Update the record and zone editing controls based on offline mode and connectivity."""
        # Get the current offline mode setting
        is_offline = self.config_manager.get_offline_mode()
        # Determine if editing should be enabled
        can_edit = not is_offline
        
        # Update the record widget if it exists
        if hasattr(self, 'record_widget'):
            self.record_widget.set_edit_enabled(can_edit)
            
        # Update the zone list widget if it exists
        if hasattr(self, 'zone_list') and hasattr(self.zone_list, 'set_edit_enabled'):
            self.zone_list.set_edit_enabled(can_edit)
        
        # Log the current state
        if is_offline:
            logger.warning("Offline mode enabled - Record and zone editing disabled")
        
        logger.debug(f"Record and zone editing {'enabled' if can_edit else 'disabled'} (offline_mode={is_offline})")
        
        # Update the action in case it was toggled by something other than the menu
        if hasattr(self, 'offline_mode_action'):
            # Only update if there's a mismatch to avoid potential loops
            if self.offline_mode_action.isChecked() != is_offline:
                self.offline_mode_action.setChecked(is_offline)

    def sync_data(self):
        """Synchronize data with the API."""
        if not self.config_manager.get_auth_token():
            self.log_message("No API token configured. Please set up your authentication token.", "warning")
            return
        
        # Skip if offline mode is enabled
        if self.config_manager.get_offline_mode():
            logger.info("Skipping sync while in offline mode")
            # Still load from cache even in offline mode
            self._load_zones_from_cache()
            return

        # Use a worker thread for the API call to avoid blocking the UI
        from workers import LoadZonesWorker
        
        worker = LoadZonesWorker(self.api_client, self.cache_manager)
        
        # Connect signals to handle the result
        worker.signals.finished.connect(self._on_zones_loaded)

        # Execute the worker
        self.thread_pool.start(worker)
        
    def _on_zones_loaded(self, success, zones, message):
        """Handle the result of zones loading.
        
        Args:
            success: Whether the operation was successful
            zones: List of zone objects
            message: Status message
        """
        # Update connection status based on success
        self.update_connection_status(success)
        
        if success:
            # Cache zones for offline access (already done in the worker)
            # Update timestamp for last successful sync
            self.last_sync_time = time.time()
            
            self.log_message(f"Retrieved {len(zones)} zones from API", "success")
            
            # Update zone list with retrieved zones - directly update the model
            self.zone_list.zone_model.update_zones(zones)
            self.zone_list.zone_count_label.setText(f"Total zones: {len(zones)}")
            
            # Select the first zone if available
            if len(zones) > 0 and self.zone_list.zone_list_view.model().rowCount() > 0:
                # QListView doesn't have selectRow, create an index for the first item and select it
                first_index = self.zone_list.zone_list_view.model().index(0, 0)
                self.zone_list.zone_list_view.selectionModel().select(
                    first_index,
                    QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect
                )
                # Also set it as current for keyboard navigation
                self.zone_list.zone_list_view.setCurrentIndex(first_index)
            
            # We'll cache records selectively when zones are selected instead of all at once
        else:
            # API request failed, try to load from cache
            self.log_message(f"Failed to sync with API: {message}", "warning")
            self._load_zones_from_cache()
            
    def _load_zones_from_cache(self):
        """Load zones from cache without API validation."""
        # get_cached_zones() returns a tuple of (zones, timestamp)
        cache_result = self.cache_manager.get_cached_zones()
        
        if cache_result and isinstance(cache_result, tuple) and len(cache_result) == 2:
            zones, timestamp = cache_result
            
            if zones:
                # Define a callback to handle the cached zones
                def handle_cached_zones(success, zones, message):
                    if success:
                        self.log_message("Loaded data from cache", "info")
                    else:
                        self.log_message("Failed to load cached data", "warning")
                
                # The zone_list.handle_zones_result method will be called by the worker
                # with the cached zones, so we just pass our callback for completion
                self.zone_list.handle_zones_result(True, zones, "Loaded from cache")
                handle_cached_zones(True, zones, "Loaded from cache")
                return
            
        # If we get here, there was no valid cache or it was empty
        self.log_message("No cached data available", "warning")
        
    # Removed _cache_all_zone_records method - now using selective caching when zones are selected instead
    
    def on_zone_selected(self, zone_name: str) -> None:
        """Handle zone selection from the zone list with optimized performance.
        
        Args:
            zone_name: The name of the selected zone
        """
        start_time = time.time()
        logger.info(f"Zone selected: {zone_name}")
        
        # Update current zone
        self.current_zone = zone_name
        
        # Update window title
        self.setWindowTitle(f"deSEC DNS Manager - {zone_name}")
        
        # Reset selection in record table
        if hasattr(self, 'record_table') and self.record_table is not None:
            self.record_table.clearSelection()
        
        # Clear record detail form
        if hasattr(self, 'detail_form') and self.detail_form is not None:
            self.detail_form.clear_form()
        
        # Use the optimized cache lookup for zone data if needed
        # This is now an O(1) operation with our new indexing
        zone_data = self.cache_manager.get_zone_by_name(zone_name)
        
        # Load records for the selected zone
        self.load_zone_records(zone_name)
        
        elapsed = (time.time() - start_time) * 1000
        logger.debug(f"Zone selection processing completed in {elapsed:.1f}ms")
    
    def load_zone_records(self, zone_name: str) -> None:
        """Load records for a specific zone with optimized performance.
        
        Args:
            zone_name: Name of the zone to load records for
        """
        start_time = time.time()
        
        # Set the domain name in the record widget - this will use cached records if available
        self.record_widget.set_domain(zone_name)
        
        elapsed = (time.time() - start_time) * 1000
        logger.debug(f"Set domain and loaded records in {elapsed:.1f}ms")
    
    def on_records_changed(self):
        """Handle record changes."""
        # Refresh the currently selected zone's records
        self.record_widget.refresh_records()
    
    def purge_log_file(self):
        """Purge the log file for security reasons when token is changed."""
        try:
            # Get the log file path
            log_dir = os.path.expanduser("~/.config/desecqt/logs")
            log_file = os.path.join(log_dir, "desecqt.log")
            
            # Check if file exists before attempting to delete
            if os.path.exists(log_file):
                # Open and truncate the file rather than deleting it
                # This preserves file permissions and handles if the file is in use
                with open(log_file, 'w') as f:
                    # Truncate to zero length
                    pass
                
                return True
            else:
                # File doesn't exist, nothing to purge
                return True
        except Exception as e:
            logger.warning(f"Failed to purge log file: {str(e)}")
            return False

    def show_auth_dialog(self):
        """Show the authentication dialog to get the API token."""
        dialog = AuthDialog(self.config_manager, self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            # Token was set, clear the cache to ensure security
            self.log_message("API token changed. Clearing cache and logs for security reasons...", "info")
            
            # Clear cache
            cache_success = self.cache_manager.clear_all_cache()
            if cache_success:
                self.log_message("Cache cleared successfully", "success")
            else:
                self.log_message("Failed to clear cache completely. Some files may remain.", "warning")
            
            # Purge log file
            log_success = self.purge_log_file()
            if log_success:
                self.log_message("Log file purged successfully", "success")
            else:
                self.log_message("Failed to purge log file", "warning")
            
            # Initialize API client
            self.api_client.check_connectivity()
            self.sync_data()
        else:
            # User cancelled
            self.log_message("Authentication required to use the application", "warning")
    
    def show_config_dialog(self):
        """Show the configuration dialog."""
        config_dialog = ConfigDialog(self.config_manager, self.theme_manager, self)
        if config_dialog.exec():
            # Update sync interval
            self.update_sync_interval()
            # Apply any theme changes
            self.theme_manager.apply_theme()
            # Perform a fresh check on the API
            self.check_api_connectivity(True)
    
    def show_profile_dialog(self):
        """Show the profile management dialog."""
        if not self.profile_manager:
            self.log_message("Profile management is not available", "warning")
            return
        
        dialog = ProfileDialog(self.profile_manager, self)
        dialog.profile_switched.connect(self.on_profile_switched)
        dialog.exec()
    
    def on_profile_switched(self, profile_name):
        """Handle profile switching.
        
        Args:
            profile_name: Name of the new profile
        """
        self.log_message(f"Profile switched to '{profile_name}'. Restarting application...", "info")
        # Restart the application to load the new profile
        self.restart_application()
    
    def show_import_export_dialog(self):
        """Show the import/export dialog."""
        # Get list of available zones for export
        available_zones = []
        if hasattr(self.zone_list, 'zone_model') and self.zone_list.zone_model.zones:
            available_zones = [zone.get('name', '') for zone in self.zone_list.zone_model.zones]
        
        dialog = ImportExportDialog(self.import_export_manager, available_zones, self)
        # Connect import completion signal to trigger sync
        dialog.import_completed.connect(self.sync_data)
        dialog.exec()
    
    def restart_application(self):
        """Restart the application to apply profile changes."""
        import sys
        import os
        
        try:
            # Save any pending configuration changes
            self.config_manager.save_config()
            
            # Get the current executable and arguments
            python_executable = sys.executable
            script_path = sys.argv[0]
            
            # Close the current application
            QtWidgets.QApplication.quit()
            
            # Start a new instance
            os.execl(python_executable, python_executable, script_path)
            
        except Exception as e:
            logger.error(f"Failed to restart application: {e}")
            QtWidgets.QMessageBox.critical(
                self, "Restart Failed", 
                f"Failed to restart the application: {str(e)}\n\n"
                "Please restart manually to apply profile changes."
            )
    
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
            
    def toggle_offline_mode(self):
        """Toggle offline mode based on menu action."""
        # Get new state from the action
        is_offline = self.offline_mode_action.isChecked()
        
        # Update the configuration
        self.config_manager.set_offline_mode(is_offline)
        self.config_manager.save_config()
        
        # Update UI
        if is_offline:
            self.log_message("Offline mode enabled - Record editing disabled", "warning")
            self.update_connection_status(False)  # Force offline status
        else:
            self.log_message("Offline mode disabled - checking connectivity...", "info")
            self.check_api_connectivity(manual_check=False)  # Check actual connectivity
        
        # Offline mode toggled - no banner to update
        
        # Enable/disable record editing based on offline mode
        self.update_record_edit_state()
    
    def toggle_log_console(self):
        """Toggle the visibility of the log console based on menu action."""
        if hasattr(self, 'log_widget'):
            # Get new state from the action
            is_checked = self.toggle_log_action.isChecked()
            
            # Update the log widget visibility
            # The widget remains in the layout, we just control visibility
            if is_checked:
                self.log_widget.show()
                self.log_visible = True
                self.log_message("Log console shown", "info")
            else:
                self.log_widget.hide()
                self.log_visible = False
                self.log_message("Log console hidden", "info")
                
            # Save state to configuration
            self.config_manager.set_show_log_console(is_checked)
            self.config_manager.save_config()
        else:
            self.log_message("Log console widget not initialized yet", "warning")
            # Reset the action state since we couldn't change the widget
            self.show_log_console_action.setChecked(not self.show_log_console_action.isChecked())
            
    def toggle_multiline_records(self):
        """Toggle display of multiline record content."""
        # Get the current state from the menu item
        show_multiline = self.show_multiline_records_action.isChecked()
        
        # Update the configuration
        self.config_manager.set_show_multiline_records(show_multiline)
        
        # Update the record widget if it exists
        if hasattr(self, 'record_widget') and self.record_widget is not None:
            self.record_widget.set_multiline_display(show_multiline)
            
        # Log the change
        mode = "full" if show_multiline else "condensed"
        logger.debug(f"Multiline record display set to {mode} mode")
        self.statusBar().showMessage(f"Multiline record display: {mode.capitalize()} mode", 3000)
    
    def show_about(self):
        """Show the about dialog."""
        about_text = (
            "<html>"
            "<head><style>body { font-family: sans-serif; margin: 15px; }</style></head>"
            "<body>"
            "<h2 align=\"center\">deSEC Qt DNS Manager</h2>"
            "<p align=\"center\">A desktop application for managing DNS zones and records<br/>"
            "using the deSEC API.</p>"
            "<p align=\"center\"><b>Version 0.6.0-beta</b></p>"
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
    
    def show_changelog(self):
        """Show the changelog in the user's browser."""
        changelog_url = "https://github.com/jaydio/desec-qt6-dns-manager/blob/main/CHANGELOG.md"
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(changelog_url))
        self.log_message("Changelog opened in browser", "info")
    
    def show_keyboard_shortcuts_dialog(self):
        """Show a dialog with keyboard shortcuts."""
        shortcuts_text = (
            "<html>"
            "<head><style>body { font-family: sans-serif; margin: 15px; }</style></head>"
            "<body>"
            "<h2 align=\"center\">Keyboard Shortcuts</h2>"
            "<p align=\"center\">Global shortcuts for deSEC Qt DNS Manager</p>"
            "<hr/>"
            "<table style=\"border-collapse: collapse; width: 100%;\">"
            "<tr><th style=\"text-align: right; width: 10%; padding: 5px;\">Shortcut</th><th style=\"text-align: left; padding: 5px;\">&nbsp;</th><th style=\"text-align: left; padding: 5px;\">Action</th></tr>"
            "<tr><td style=\"text-align: right; padding: 5px;\">F5</td><td style=\"padding: 5px;\">&nbsp;</td><td style=\"text-align: left; padding: 5px;\">Refresh/sync data</td></tr>"
            "<tr><td style=\"text-align: right; padding: 5px;\">Ctrl+F</td><td style=\"padding: 5px;\">&nbsp;</td><td style=\"text-align: left; padding: 5px;\">Cycle through search filter fields</td></tr>"
            "<tr><td style=\"text-align: right; padding: 5px;\">Ctrl+Q</td><td style=\"padding: 5px;\">&nbsp;</td><td style=\"text-align: left; padding: 5px;\">Quit application (with confirmation)</td></tr>"
            "<tr><td style=\"text-align: right; padding: 5px;\">Delete</td><td style=\"padding: 5px;\">&nbsp;</td><td style=\"text-align: left; padding: 5px;\">Delete selected zone or record</td></tr>"
            "<tr><td style=\"text-align: right; padding: 5px;\">Escape</td><td style=\"padding: 5px;\">&nbsp;</td><td style=\"text-align: left; padding: 5px;\">Clear active search filter</td></tr>"
            "<tr><td style=\"text-align: right; padding: 5px;\">Ctrl+Enter</td><td style=\"padding: 5px;\">&nbsp;</td><td style=\"text-align: left; padding: 5px;\">Close record dialogs</td></tr>"
            "</table>"
            "<p>&nbsp;</p>"
            "</body>"
            "</html>"
        )
        
        QMessageBox.information(self, "Keyboard Shortcuts", shortcuts_text)
    
    def update_elapsed_time(self):
        """Update the elapsed time display since last sync."""
        if self.last_sync_time is None:
            self.last_sync_label.setText("Last sync: Never")
            return
            
        elapsed_seconds = int(time.time() - self.last_sync_time)
        
        if elapsed_seconds < 60:
            elapsed_text = f"{elapsed_seconds} sec ago"
        elif elapsed_seconds < 3600:
            minutes = elapsed_seconds // 60
            seconds = elapsed_seconds % 60
            elapsed_text = f"{minutes} min {seconds} sec ago"
        else:
            hours = elapsed_seconds // 3600
            minutes = (elapsed_seconds % 3600) // 60
            elapsed_text = f"{hours} hr {minutes} min ago"
        
        # Update the last sync label with elapsed time
        self.last_sync_label.setText(f"Last sync: {elapsed_text}")
    
    def update_record_table(self, records: List[Dict[str, Any]]) -> None:
        """Update the record table with retrieved records efficiently.
        
        Args:
            records: List of record dictionaries to display
        """
        start_time = time.time()
        
        # If we have no record table yet, create it
        if not hasattr(self, 'record_table') or self.record_table is None:
            return
        
        # Update the records in the table
        self.record_table.set_records(records)
        
        elapsed = (time.time() - start_time) * 1000
        logger.debug(f"Record table update completed in {elapsed:.1f}ms for {len(records)} records")
    
    def handle_records_result(self, success: bool, records: List[Dict[str, Any]], zone_name: str, error_msg: str) -> None:
        """Handle the result of records loading with appropriate UI feedback.
        
        Args:
            success: Whether the operation was successful
            records: List of record dictionaries
            zone_name: Name of the zone
            error_msg: Error message if any
        """
        if success:
            # Update the record table with fetched records
            self.update_record_table(records)
            record_count = len(records)
            self.statusBar().showMessage(f"Loaded {record_count} records for {zone_name}", 5000)
        else:
            if records:  # We got cached records as fallback
                self.statusBar().showMessage(
                    f"Using cached records for {zone_name}. Error: {error_msg}", 
                    5000
                )
            else:
                self.statusBar().showMessage(f"Failed to load records: {error_msg}", 10000)
                
        # Enable appropriate actions based on record availability
        has_records = records and len(records) > 0
        if hasattr(self, 'action_add_record'):
            self.action_add_record.setEnabled(True)  # Always allow adding records to a zone
    
    def keyPressEvent(self, event):
        """Handle key press events for global keyboard shortcuts.
        
        Args:
            event: QKeyEvent containing the key press information
        """
        # F5 shortcut to refresh/sync
        if event.key() == Qt.Key.Key_F5:
            self.log_message("F5 pressed - Refreshing data", "info")
            self.sync_data()
            event.accept()
            return
        # Ctrl+F to cycle through search filter fields
        if event.key() == Qt.Key.Key_F and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self._cycle_through_search_filters()
            event.accept()
            return
        # Ctrl+Q to quit (with confirmation)
        if event.key() == Qt.Key.Key_Q and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self._confirm_quit_dialog()
            event.accept()
            return
        # Delete to delete selected item
        if event.key() == Qt.Key.Key_Delete:
            self._handle_delete_key()
            event.accept()
            return
        # Escape to clear active search filter
        if event.key() == Qt.Key.Key_Escape:
            self._clear_active_search_filter()
            event.accept()
            return
        # Pass event to parent for standard processing
        super(MainWindow, self).keyPressEvent(event)

    
    def _cycle_through_search_filters(self):
        """Cycle focus through available search filter fields."""
        # Get references to all search filter fields
        search_fields = []
        
        # Add zone filter if it exists
        if hasattr(self, 'zone_list') and hasattr(self.zone_list, 'search_field'):
            search_fields.append(self.zone_list.search_field)
            
        # Add record filter if it exists
        if hasattr(self, 'record_widget') and hasattr(self.record_widget, 'filter_edit'):
            search_fields.append(self.record_widget.filter_edit)
            
        if not search_fields:
            self.log_message("No search fields found to cycle through", "warning")
            return
            
        # Find the currently focused widget
        focused_widget = QtWidgets.QApplication.focusWidget()
        
        # If one of our search fields has focus, move to the next one
        if focused_widget in search_fields:
            current_index = search_fields.index(focused_widget)
            next_index = (current_index + 1) % len(search_fields)
        else:
            # Otherwise start with the zone filter
            next_index = 0
            
        # Set focus to the next search field
        next_field = search_fields[next_index]
        next_field.setFocus()
        next_field.selectAll()  # Select all text for easy replacement
        
        # Show a status message based on which field is now active
        field_names = ["Zone filter", "Record filter"]
        self.statusBar().showMessage(f"{field_names[next_index]} active", 2000)
            
    def _handle_delete_key(self):
        """Handle Delete key press by deleting selected zone or record."""
        # Check if zone list has focus and has a selection
        zone_has_focus = (self.zone_list == QtWidgets.QApplication.focusWidget() or 
                          hasattr(self.zone_list, 'zone_list_view') and 
                          self.zone_list.zone_list_view.hasFocus())
        
        # Check if record widget has focus
        record_has_focus = (self.record_widget == QtWidgets.QApplication.focusWidget() or
                           hasattr(self.record_widget, 'records_table') and 
                           self.record_widget.records_table.hasFocus())
                           
        if zone_has_focus:
            # Delete selected zone with confirmation
            zone_name, zone_data = self.zone_list.get_selected_zone()
            if zone_name:  # The method returns a tuple (name, data)
                self._confirm_delete_zone(zone_name)
        elif record_has_focus:
            # Delete selected record with confirmation
            self.record_widget.delete_selected_record()
            
    def _clear_active_search_filter(self):
        """Clear the currently active search filter when Escape is pressed."""
        # Get the currently focused widget
        focused_widget = QtWidgets.QApplication.focusWidget()
        
        # Check if it's a search filter
        cleared = False
        
        # Check zone filter
        if hasattr(self, 'zone_list') and hasattr(self.zone_list, 'search_field'):
            zone_filter = self.zone_list.search_field
            if focused_widget == zone_filter:
                # Clear the zone filter
                zone_filter.clear()
                self.zone_list.filter_zones("")  # Apply empty filter
                cleared = True
                self.statusBar().showMessage("Zone filter cleared", 2000)
            
        # Check record filter    
        if not cleared and hasattr(self, 'record_widget') and hasattr(self.record_widget, 'filter_edit'):
            record_filter = self.record_widget.filter_edit
            if focused_widget == record_filter:
                # Clear the record filter
                record_filter.clear()
                self.record_widget.filter_records("")  # Apply empty filter
                cleared = True
                self.statusBar().showMessage("Record filter cleared", 2000)
                
        # If a filter widget has focus but no text to clear, remove focus
        search_fields = []
        if hasattr(self, 'zone_list') and hasattr(self.zone_list, 'search_field'):
            search_fields.append(self.zone_list.search_field)
        if hasattr(self, 'record_widget') and hasattr(self.record_widget, 'filter_edit'):
            search_fields.append(self.record_widget.filter_edit)
            
        if focused_widget in search_fields and not cleared:
            # If we're in a search field but it's already empty, clear focus
            focused_widget.clearFocus()
            cleared = True
            self.statusBar().showMessage("Search focus cleared", 2000)
                
        # Do NOT clear all filters if no filter had focus - this was causing the bug
        # Only clear the filter of the widget that actually has focus
        
        # Check if the record search field (right side, records_search_input) is focused
        if hasattr(self, 'record_widget') and hasattr(self.record_widget, 'records_search_input'):
            record_search_field = self.record_widget.records_search_input
            if focused_widget == record_search_field:
                # Clear the record search field
                record_search_field.clear()
                self.record_widget.filter_records("")  # Apply empty filter
                cleared = True
                self.statusBar().showMessage("Record search field cleared", 2000)
    
    def _confirm_delete_zone(self, zone_name):
        """Show confirmation dialog before deleting a zone.
        
        Args:
            zone_name: Name of the zone to delete
        """
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete the zone '{zone_name}'?\n\nThis will delete all records in this zone and cannot be undone!",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No
        )
        
        if confirm == QtWidgets.QMessageBox.StandardButton.Yes:
            # Delete the zone
            self.zone_list.delete_zone(zone_name)
    
    def on_zone_deleted(self):
        """Handle zone deletion by syncing data and clearing records view."""
        # Clear the records view by setting domain to None
        self.record_widget.current_domain = None
        self.record_widget.records = []
        self.record_widget.update_records_table()
        
        # Trigger a sync to refresh the zone list
        self.sync_data()
        
        # Log the action
        self.log_message("Zone deleted - records view cleared and data synced", "info")
    
    def _confirm_quit_dialog(self):
        """Show confirmation dialog before quitting."""
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Confirm Quit",
            "Are you sure you want to quit?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No
        )
        
        if confirm == QtWidgets.QMessageBox.StandardButton.Yes:
            # Close the window
            self.close()

    def clear_cache(self):
        """Clear all cached data and initiate a new sync."""
        # Show a confirmation dialog
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Confirm Cache Clear",
            "Are you sure you want to clear all cached data? This will remove all local cache files and require a fresh sync.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No
        )
        
        if confirm == QtWidgets.QMessageBox.StandardButton.Yes:
            # Clear the cache
            success = self.cache_manager.clear_all_cache()
            if success:
                self.log_message("Cache cleared successfully. Initiating new sync...", "success")
                # Perform a new sync
                self.sync_data()
            else:
                self.log_message("Failed to clear cache completely. Some files may remain.", "error")

    def on_theme_type_changed(self, action):
        """Handle theme type change.
        
        Args:
            action: The triggered QAction
        """
        theme_type = action.data()
        if theme_type:
            self.config_manager.set_theme_type(theme_type)
            self.config_manager.save_config()
            self.theme_manager.apply_theme()
    
    def on_theme_changed(self, action, theme_type):
        """Handle theme selection change.
        
        Args:
            action: The triggered QAction
            theme_type: The theme type (light or dark)
        """
        theme_id = action.data()
        if theme_id:
            self.config_manager.set_theme_type(theme_type)
            self.config_manager.set_theme_id(theme_id)
            self.config_manager.save_config()
            self.theme_manager.apply_theme()
    
    def closeEvent(self, event):
        """Handle window close event."""
        # Save any pending changes to configuration
        self.config_manager.save_config()
        event.accept()
