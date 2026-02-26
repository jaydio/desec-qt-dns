#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Zone List Widget for deSEC Qt DNS Manager.
Displays and manages DNS zones with optimized performance.
"""

import logging
import webbrowser
from typing import List, Dict, Any, Tuple, Optional, Callable, Union

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt, Signal, QThreadPool, QObject, QPropertyAnimation, QEasingCurve
from qfluentwidgets import (
    PushButton, PrimaryPushButton, SearchLineEdit, ListView, LineEdit,
    isDarkTheme, SubtitleLabel, StrongBodyLabel, CaptionLabel,
)

from fluent_styles import container_qss
from confirm_drawer import DeleteConfirmDrawer
from workers import LoadZonesWorker
from api_queue import QueueItem, PRIORITY_HIGH, PRIORITY_NORMAL

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

class AddZonePanel(QtWidgets.QWidget):
    """Slide-in right panel for adding a new DNS zone."""

    PANEL_WIDTH = 340

    zone_added = Signal(str)  # emits the zone name to create

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("addZonePanel")
        self._animation = None
        self.hide()
        self._setup_ui()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        bg = QtGui.QColor(32, 32, 32) if isDarkTheme() else QtGui.QColor(243, 243, 243)
        painter.fillRect(self.rect(), bg)

    def _setup_ui(self):
        self.setStyleSheet(
            "QWidget#addZonePanel { border-left: 1px solid rgba(128,128,128,0.35); }"
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        # Header row: title + close button
        header_row = QtWidgets.QHBoxLayout()
        header_row.addWidget(SubtitleLabel("Add DNS Zone"), 1)
        close_btn = PushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setToolTip("Close (Esc)")
        close_btn.clicked.connect(self.slide_out)
        header_row.addWidget(close_btn)
        layout.addLayout(header_row)

        # Escape shortcut
        esc = QtGui.QShortcut(QtGui.QKeySequence(Qt.Key.Key_Escape), self)
        esc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        esc.activated.connect(self.slide_out)

        explanation = QtWidgets.QLabel(
            "Enter the domain name you want to manage through deSEC.\n\n"
            "You must own this domain or have the rights to manage it."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        layout.addWidget(QtWidgets.QLabel("Domain Name"))
        self._zone_input = LineEdit()
        self._zone_input.setPlaceholderText("example.com")
        layout.addWidget(self._zone_input)

        self._error_label = QtWidgets.QLabel("")
        self._error_label.setWordWrap(True)
        layout.addWidget(self._error_label)

        layout.addStretch()

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = PushButton("Cancel")
        cancel_btn.clicked.connect(self.slide_out)
        btn_row.addWidget(cancel_btn)
        add_btn = PrimaryPushButton("Add Zone")
        add_btn.clicked.connect(self._on_add)
        btn_row.addWidget(add_btn)
        layout.addLayout(btn_row)

    def open(self):
        self._zone_input.clear()
        self._error_label.setText("")
        self.slide_in()

    def _on_add(self):
        zone_name = self._zone_input.text().strip()
        if not zone_name:
            self._error_label.setText("Please enter a domain name.")
            return
        self.slide_out()
        self.zone_added.emit(zone_name)

    def slide_in(self):
        self.setStyleSheet(
            "QWidget#addZonePanel { border-left: 1px solid rgba(128,128,128,0.35); }"
            + container_qss()
        )
        parent = self.parent()
        if parent is None:
            return
        pw, ph = parent.width(), parent.height()
        self.setGeometry(pw, 0, self.PANEL_WIDTH, ph)
        self.show()
        self.raise_()
        self._run_animation(
            QtCore.QPoint(pw, 0),
            QtCore.QPoint(pw - self.PANEL_WIDTH, 0),
            QEasingCurve.Type.OutCubic,
        )

    def slide_out(self):
        parent = self.parent()
        if parent is None:
            self.hide()
            return
        pw = parent.width()
        anim = self._run_animation(
            self.pos(),
            QtCore.QPoint(pw, 0),
            QEasingCurve.Type.InCubic,
        )
        anim.finished.connect(self.hide)

    def _run_animation(self, start, end, easing):
        if self._animation and self._animation.state() == QPropertyAnimation.State.Running:
            self._animation.stop()
        anim = QPropertyAnimation(self, b"pos")
        anim.setDuration(220)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(easing)
        self._animation = anim
        anim.start()
        return anim

    def reposition(self, parent_size):
        if not self.isVisible():
            return
        x = parent_size.width() - self.PANEL_WIDTH
        self.setGeometry(x, 0, self.PANEL_WIDTH, parent_size.height())


class ZoneListWidget(QtWidgets.QWidget):
    """Widget for displaying and managing DNS zones."""

    # Custom signals
    zone_selected = Signal(str)      # Emitted when a zone is selected
    zone_added = Signal()            # Emitted when a zone is added
    zone_deleted = Signal()          # Emitted when a zone is deleted
    add_zone_requested = Signal()    # Emitted when user clicks Add Zone
    log_message = Signal(str, str)   # Emitted to log messages (message, level)

    def __init__(self, api_client, cache_manager, parent=None, api_queue=None,
                 version_manager=None):
        """
        Initialize the zone list widget.

        Args:
            api_client: API client instance
            cache_manager: Cache manager instance
            parent: Parent widget, if any
            api_queue: Central API queue (optional, falls back to direct calls)
            version_manager: Git-based zone versioning (optional)
        """
        super(ZoneListWidget, self).__init__(parent)

        self.api_client = api_client
        self.cache_manager = cache_manager
        self.api_queue = api_queue
        self.version_manager = version_manager
        self.zones = []
        self.thread_pool = QThreadPool.globalInstance()
        self.loading_indicator = None
        self._edit_enabled = True  # Default to enabled
        self._domain_limit = None  # Set once account info is fetched

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

        title = StrongBodyLabel("DNS Zones")
        title.setMinimumWidth(100)
        title_layout.addWidget(title)

        title_layout.addStretch()

        self.zone_count_label = CaptionLabel("Total zones: 0")
        title_layout.addWidget(self.zone_count_label)

        header_layout.addLayout(title_layout)

        # Search field — SearchLineEdit includes built-in icon
        search_layout = QtWidgets.QHBoxLayout()
        search_layout.setContentsMargins(0, 6, 0, 6)

        self.search_field = SearchLineEdit()
        self.search_field.setPlaceholderText("Search zones...")
        self.search_field.textChanged.connect(self.filter_zones)
        search_layout.addWidget(self.search_field)

        header_layout.addLayout(search_layout)

        # Add header layout to main layout
        layout.addLayout(header_layout)

        # Use model-view architecture for better performance
        self.zone_model = ZoneListModel()
        self.zone_list_view = ListView()
        self.zone_list_view.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.zone_list_view.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.zone_list_view.setAlternatingRowColors(True)
        self.zone_list_view.setUniformItemSizes(True)

        # Set the model for the view
        self.zone_list_view.setModel(self.zone_model)

        # Connect selection changed signals
        self.zone_list_view.selectionModel().currentChanged.connect(self.on_zone_selection_changed)
        self.zone_list_view.selectionModel().selectionChanged.connect(self._on_selection_changed)

        # Connect double click signal
        self.zone_list_view.doubleClicked.connect(self.on_zone_double_clicked)

        # Add some vertical stretch to push buttons to the bottom
        layout.addWidget(self.zone_list_view, 1)  # Give stretch factor

        # Add action buttons (matching the style of record widget)
        actions_layout = QtWidgets.QHBoxLayout()
        actions_layout.setContentsMargins(0, 6, 0, 0)  # Add top margin for spacing

        # Store references to buttons to enable/disable in offline mode
        self.add_zone_btn = PushButton("Add Zone")
        self.add_zone_btn.clicked.connect(self.show_add_zone_dialog)
        actions_layout.addWidget(self.add_zone_btn)

        self.delete_zone_btn = PushButton("Delete Zone")
        self.delete_zone_btn.clicked.connect(self.delete_selected_zone)
        actions_layout.addWidget(self.delete_zone_btn)

        # Add DNSSEC validation button
        self.validate_dnssec_btn = PushButton("Validate")
        self.validate_dnssec_btn.clicked.connect(self.validate_dnssec)
        self.validate_dnssec_btn.setEnabled(False)  # Disabled by default until a zone is selected
        self.validate_dnssec_btn.setToolTip("Validate DNSSEC configuration for the selected domain")
        actions_layout.addWidget(self.validate_dnssec_btn)

        # Add spacer to push buttons to the left (same as record widget)
        actions_layout.addStretch()

        layout.addLayout(actions_layout)

        # Note: AddZonePanel is owned by DnsInterface (slides over the full DNS view)

        # Delete confirmation drawer (slides from top)
        self._delete_drawer = DeleteConfirmDrawer(parent=self)

        # Apply theme-aware text colours for standard QLabels
        self.setStyleSheet(container_qss())

    def showEvent(self, event):
        super().showEvent(event)
        self.setStyleSheet(container_qss())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_delete_drawer'):
            self._delete_drawer.reposition(event.size())

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
            self.zone_count_label.setText(f"Total zones: {self._zone_count_text(len(cached_zones))}")

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
            new_text = f"Showing {filtered} of {self._zone_count_text(total)} zones" if self.search_field.text() else f"Total zones: {self._zone_count_text(total)}"
            if self.zone_count_label.text() != new_text:
                self.zone_count_label.setText(new_text)

            # Always update edit buttons after zone list changes
            self.set_edit_enabled(self._edit_enabled)
            selected_indices = self.zone_list_view.selectedIndexes()
            if selected_indices and selected_indices[0].isValid():
                self.on_zone_selection_changed(selected_indices[0], None)

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
                self.zone_count_label.setText(f"Showing {count} of {self._zone_count_text(total)} zones")
            else:
                self.zone_count_label.setText(f"Total zones: {self._zone_count_text(total)}")
            self.set_edit_enabled(self._edit_enabled)

    def set_domain_limit(self, limit):
        """Update the account domain limit and refresh the count label.

        Args:
            limit (int or None): Maximum domains allowed for the account
        """
        self._domain_limit = limit
        total = len(self.zone_model.zones)
        filtered = self.zone_model.rowCount()
        if self.search_field.text():
            self.zone_count_label.setText(f"Showing {filtered} of {self._zone_count_text(total)}")
        else:
            self.zone_count_label.setText(f"Total zones: {self._zone_count_text(total)}")

    def _zone_count_text(self, count):
        """Format zone count, appending limit when known (e.g. '3/100')."""
        if self._domain_limit is not None:
            return f"{count}/{self._domain_limit}"
        return str(count)

    def on_zone_selection_changed(self, current: QtCore.QModelIndex, previous: QtCore.QModelIndex) -> None:
        """Handler for zone selection changed event.
        Args:
            current: Currently selected index
            previous: Previously selected index
        """
        if not current.isValid():
            return
        zone_name = self.zone_model.data(current, Qt.ItemDataRole.DisplayRole)
        logger.debug(f"Zone selected: {zone_name}")
        # Always update all edit buttons after selection changes
        self.set_edit_enabled(self._edit_enabled)
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
        """Signal that the user wants to add a zone (DnsInterface hosts the panel)."""
        if not self._edit_enabled:
            self.log_message.emit("Cannot add zone in offline mode", "warning")
            return
        self.add_zone_requested.emit()

    def add_zone(self, zone_name):
        """
        Add a new zone.
        Args:
            zone_name (str): Zone name to add
        """
        if not self._edit_enabled:
            self.log_message.emit("Cannot add zone in offline mode", "warning")
            return

        self.log_message.emit(f"Adding zone {zone_name}...", "info")

        if self.api_queue:
            def _on_done(success, data):
                if success:
                    self.log_message.emit(f"Zone {zone_name} added successfully", "success")
                    self.zone_added.emit()
                else:
                    self.log_message.emit(f"Failed to add zone: {data}", "error")

            item = QueueItem(
                priority=PRIORITY_NORMAL,
                category="zones",
                action=f"Add zone {zone_name}",
                callable=self.api_client.create_zone,
                args=(zone_name,),
                callback=_on_done,
            )
            self.api_queue.enqueue(item)
        else:
            success, response = self.api_client.create_zone(zone_name)
            if success:
                self.log_message.emit(f"Zone {zone_name} added successfully", "success")
                self.zone_added.emit()
            else:
                self.log_message.emit(f"Failed to add zone: {response}", "error")

    def _on_selection_changed(self):
        """Update button state and counter when zone selection changes."""
        self.set_edit_enabled(self._edit_enabled)

    def _get_selected_zone_names(self):
        """Return a list of all selected zone names."""
        names = []
        for index in self.zone_list_view.selectedIndexes():
            if index.isValid():
                name = self.zone_model.data(index, Qt.ItemDataRole.DisplayRole)
                if name:
                    names.append(name)
        return names

    def delete_selected_zone(self):
        """Delete all selected zones after confirmation via top-sliding drawer."""
        if not self._edit_enabled:
            self.log_message.emit("Cannot delete zones in offline mode", "warning")
            return

        zones = self._get_selected_zone_names()
        if not zones:
            self.log_message.emit("No zone selected", "warning")
            return

        count = len(zones)

        if count == 1:
            title = "Delete Zone"
            message = (
                f"Permanently delete '{zones[0]}'?\n\n"
                "This is IRREVERSIBLE. All DNS records in this zone will be destroyed."
            )
            confirm_text = "Delete Zone"
        else:
            title = f"Delete {count} Zones"
            message = (
                f"Permanently delete {count} zones?\n\n"
                "This is IRREVERSIBLE. All DNS records in every listed zone will be destroyed."
            )
            confirm_text = f"Delete {count} Zones"

        def _execute_delete():
            if self.api_queue:
                # Track completions — only emit zone_deleted once all finish
                pending = [count]

                def _make_cb(zname):
                    def _cb(success, data):
                        if success:
                            self.log_message.emit(f"Zone {zname} deleted successfully", "success")
                            self.cache_manager.clear_domain_cache(zname)
                            self._remove_zone_from_model(zname)
                        else:
                            self.log_message.emit(f"Failed to delete zone: {data}", "error")
                        pending[0] -= 1
                        if pending[0] <= 0:
                            self.zone_deleted.emit()
                    return _cb

                for zone_name in zones:
                    # Snapshot before delete
                    if self.version_manager:
                        cached_records, _ = self.cache_manager.get_cached_records(zone_name)
                        if cached_records:
                            self.version_manager.snapshot(
                                zone_name, cached_records,
                                "Pre-delete snapshot (zone destroyed)",
                            )

                    item = QueueItem(
                        priority=PRIORITY_NORMAL,
                        category="zones",
                        action=f"Delete zone {zone_name}",
                        callable=self.api_client.delete_zone,
                        args=(zone_name,),
                        callback=_make_cb(zone_name),
                    )
                    self.api_queue.enqueue(item)
            else:
                for zone_name in zones:
                    self.delete_zone(zone_name, quiet=True)
                self.zone_deleted.emit()

        self._delete_drawer.ask(
            title=title,
            message=message,
            items=zones,
            on_confirm=_execute_delete,
            confirm_text=confirm_text,
        )

    def set_edit_enabled(self, enabled: bool) -> None:
        """Enable or disable edit functionality."""
        n_selected = len(self.zone_list_view.selectedIndexes())
        self._edit_enabled = enabled
        if hasattr(self, 'add_zone_btn'):
            self.add_zone_btn.setEnabled(enabled)
            if not enabled:
                self.add_zone_btn.setToolTip("Adding zones is disabled in offline mode")
            else:
                self.add_zone_btn.setToolTip("")
        if hasattr(self, 'delete_zone_btn'):
            self.delete_zone_btn.setEnabled(enabled and n_selected > 0)
            if n_selected > 1:
                self.delete_zone_btn.setText(f"Delete ({n_selected})")
            else:
                self.delete_zone_btn.setText("Delete Zone")
            if not enabled:
                self.delete_zone_btn.setToolTip("Deleting zones is disabled in offline mode")
            elif n_selected == 0:
                self.delete_zone_btn.setToolTip("Select a zone to delete")
            else:
                self.delete_zone_btn.setToolTip("")
        if hasattr(self, 'validate_dnssec_btn'):
            self.validate_dnssec_btn.setEnabled(n_selected > 0)


    def _remove_zone_from_model(self, zone_name):
        """Remove a zone from the model by name and refresh the view."""
        self.zone_model.beginResetModel()
        self.zone_model.zones = [
            z for z in self.zone_model.zones if z.get("name") != zone_name
        ]
        self.zone_model._zone_name_cache.clear()
        self.zone_model.apply_filter()
        self.zone_model.endResetModel()

        total = len(self.zone_model.zones)
        filtered = self.zone_model.rowCount()
        if self.search_field.text():
            self.zone_count_label.setText(
                f"Showing {filtered} of {self._zone_count_text(total)} zones"
            )
        else:
            self.zone_count_label.setText(
                f"Total zones: {self._zone_count_text(total)}"
            )

    def on_zone_double_clicked(self, index):
        """Handle double click on a zone item.

        Args:
            index (QModelIndex): The index that was double-clicked
        """
        # Only proceed if editing is enabled (not in offline mode)
        if not self._edit_enabled:
            self.log_message.emit("Editing zones is disabled in offline mode", "warning")
            return

        # Get the zone name from the model
        zone_name = self.zone_model.data(index, Qt.ItemDataRole.DisplayRole)
        if zone_name:
            # Emit the zone selected signal to trigger record loading
            self.zone_selected.emit(zone_name)

    def delete_zone(self, zone_name, quiet=False):
        """Delete a zone.

        Args:
            zone_name (str): The name of the zone to delete
            quiet (bool): If True, skip emitting zone_deleted (caller handles it)
        """
        self.log_message.emit(f"Deleting zone: {zone_name}", "info")

        # Snapshot current records before deletion so the zone can be restored
        if self.version_manager:
            cached_records, _ = self.cache_manager.get_cached_records(zone_name)
            if cached_records:
                self.version_manager.snapshot(
                    zone_name, cached_records,
                    f"Pre-delete snapshot (zone destroyed)",
                )

        if self.api_queue:
            def _on_done(success, data):
                if success:
                    self.log_message.emit(f"Zone {zone_name} deleted successfully", "success")
                    self.cache_manager.clear_domain_cache(zone_name)
                    self._remove_zone_from_model(zone_name)
                    if not quiet:
                        self.zone_deleted.emit()
                else:
                    self.log_message.emit(f"Failed to delete zone: {data}", "error")

            item = QueueItem(
                priority=PRIORITY_NORMAL,
                category="zones",
                action=f"Delete zone {zone_name}",
                callable=self.api_client.delete_zone,
                args=(zone_name,),
                callback=_on_done,
            )
            self.api_queue.enqueue(item)
        else:
            success, response = self.api_client.delete_zone(zone_name)
            if success:
                self.log_message.emit(f"Zone {zone_name} deleted successfully", "success")
                self.cache_manager.clear_domain_cache(zone_name)
                if not quiet:
                    self.zone_deleted.emit()
            else:
                self.log_message.emit(f"Failed to delete zone: {response}", "error")
