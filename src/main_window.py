#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Main window implementation for deSEC Qt DNS Manager.
Implements the FluentWindow shell with sidebar navigation and the two-pane DNS interface.
"""

import logging
import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable, Union

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt, QThreadPool, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QShortcut, QKeySequence

from qfluentwidgets import (
    FluentWindow, NavigationItemPosition, FluentIcon,
    isDarkTheme,
    PushButton, PrimaryPushButton, PasswordLineEdit,
    SubtitleLabel, LargeTitleLabel,
)

from workers import LoadRecordsWorker

from profile_dialog import ProfileInterface
from settings_interface import SettingsInterface
from import_export_manager import ImportExportManager
from import_export_dialog import ExportInterface, ImportInterface
from search_replace_dialog import SearchReplaceInterface
from token_manager_dialog import TokenManagerInterface
from zone_list_widget import ZoneListWidget, AddZonePanel
from fluent_styles import SPLITTER_QSS, container_qss
from notify_drawer import NotifyDrawer
from record_widget import RecordWidget
from log_widget import LogWidget
from theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class AboutInterface(QtWidgets.QWidget):
    """Sidebar page showing application info."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("aboutInterface")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(36, 20, 36, 20)
        layout.setSpacing(14)

        layout.addWidget(LargeTitleLabel("About"))

        info = QtWidgets.QLabel()
        info.setTextFormat(QtCore.Qt.TextFormat.RichText)
        info.setOpenExternalLinks(True)
        info.setWordWrap(True)
        info.setText(
            "<h3>deSEC DNS Manager</h3>"
            "<p>A desktop application for managing DNS zones and records "
            "using the <a href='https://desec.io'>deSEC</a> API.</p>"
            "<p><b>Version</b> 0.12.1-beta</p>"
            "<hr/>"
            "<p><b>Author:</b> JD Bungart<br/>"
            "<a href='mailto:me@jdneer.com'>me@jdneer.com</a><br/>"
            "<a href='https://github.com/jaydio/desec-qt-dns'>github.com/jaydio/desec-qt-dns</a></p>"
            "<hr/>"
            "<p><small>Released under GNU General Public License v3</small></p>"
        )
        layout.addWidget(info)
        layout.addStretch()

    def showEvent(self, event):
        super().showEvent(event)
        from fluent_styles import container_qss
        self.setStyleSheet(container_qss())


class LogInterface(QtWidgets.QWidget):
    """Sidebar page that hosts the application log console."""

    def __init__(self, log_widget, parent=None):
        super().__init__(parent)
        self.setObjectName("logInterface")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(36, 20, 36, 20)
        layout.setSpacing(14)
        layout.addWidget(LargeTitleLabel("Log Console"))
        layout.addWidget(log_widget, 1)

    def showEvent(self, event):
        super().showEvent(event)
        self.setStyleSheet(container_qss())


class DnsInterface(QtWidgets.QWidget):
    """Main DNS two-pane interface: zone list (left) + records (right)."""

    def __init__(self, zone_list, record_widget, config_manager, parent=None):
        super().__init__(parent)
        self.setObjectName("dnsInterface")
        self.config_manager = config_manager

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Splitter ─────────────────────────────────────────────────────────
        splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        sp = splitter.sizePolicy()
        sp.setVerticalPolicy(QtWidgets.QSizePolicy.Policy.Expanding)
        sp.setVerticalStretch(1)
        splitter.setSizePolicy(sp)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(SPLITTER_QSS)

        zones_widget = QtWidgets.QWidget()
        zones_layout = QtWidgets.QVBoxLayout(zones_widget)
        zones_layout.setContentsMargins(0, 0, 4, 0)
        zones_layout.addWidget(zone_list)
        zones_widget.setMinimumWidth(220)

        records_widget = QtWidgets.QWidget()
        records_layout = QtWidgets.QVBoxLayout(records_widget)
        records_layout.setContentsMargins(4, 0, 0, 0)
        records_layout.addWidget(record_widget)

        splitter.addWidget(zones_widget)
        splitter.addWidget(records_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)   # zones ≈ 25%, records ≈ 75%
        splitter.setSizes([340, 760])     # initial pixel sizes

        outer.addWidget(splitter, 1)

        # ── Add Zone panel — slides in from the right edge of the full DNS view ──
        self._add_zone_panel = AddZonePanel(parent=self)
        self._add_zone_panel.zone_added.connect(zone_list.add_zone)
        zone_list.add_zone_requested.connect(self._add_zone_panel.open)


    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_add_zone_panel'):
            self._add_zone_panel.reposition(event.size())


class AuthPanel(QtWidgets.QWidget):
    """Slide-in right panel for entering or changing the API authentication token."""

    PANEL_WIDTH = 440

    token_saved = QtCore.Signal()

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self._animation = None
        self.setObjectName("authPanel")
        self.hide()
        self._setup_ui()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        bg = QtGui.QColor(32, 32, 32) if isDarkTheme() else QtGui.QColor(243, 243, 243)
        painter.fillRect(self.rect(), bg)

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        # Header row: title + close button
        header_row = QtWidgets.QHBoxLayout()
        header_row.addWidget(SubtitleLabel("API Authentication"), 1)
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
            "Please enter your deSEC API token.\n\n"
            "You can obtain a token by logging into your deSEC account at "
            "https://desec.io and generating a token with DNS management permissions."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        form = QtWidgets.QFormLayout()
        self._token_input = PasswordLineEdit()
        self._token_input.setPlaceholderText("Enter your API token here")
        form.addRow("API Token:", self._token_input)
        layout.addLayout(form)

        self._error_label = QtWidgets.QLabel("")
        self._error_label.setWordWrap(True)
        layout.addWidget(self._error_label)

        layout.addStretch()

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = PushButton("Cancel")
        cancel_btn.clicked.connect(self.slide_out)
        btn_row.addWidget(cancel_btn)
        save_btn = PrimaryPushButton("Save Token")
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def open(self):
        self._token_input.setText(self.config_manager.get_auth_token() or "")
        self._error_label.setText("")
        self.slide_in()

    def _on_save(self):
        token = self._token_input.text().strip()
        if not token:
            self._error_label.setText("Please enter a valid API token.")
            return
        self.config_manager.set_auth_token(token)
        self.config_manager.save_config()
        self.slide_out()
        self.token_saved.emit()

    def slide_in(self):
        self.setStyleSheet(
            f"QWidget#{self.objectName()} {{ border-left: 1px solid rgba(128,128,128,0.35); }}"
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


class MainWindow(FluentWindow):
    """Main application window — FluentWindow with sidebar navigation."""

    def __init__(self, config_manager, api_client, cache_manager, profile_manager=None, parent=None):
        super().__init__(parent)

        self.config_manager = config_manager
        self.api_client = api_client
        self.cache_manager = cache_manager
        self.profile_manager = profile_manager

        self.import_export_manager = ImportExportManager(api_client, cache_manager)
        self.theme_manager = ThemeManager(config_manager)
        self.thread_pool = QThreadPool()

        self.setup_ui()

        self.theme_manager.apply_theme()

        if not self.config_manager.get_auth_token():
            self.show_auth_dialog()

        self.setup_sync_timer()
        self._apply_initial_debug_mode()

        is_offline_mode = self.config_manager.get_offline_mode()
        self.update_connection_status(not is_offline_mode)

        self.sync_data()
        self.update_record_edit_state()

    # ── UI setup ──────────────────────────────────────────────────────────────

    def setup_ui(self):
        self.setWindowTitle("deSEC DNS Manager")
        self.resize(1280, 860)

        self.last_sync_time = None
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.timeout.connect(self.update_elapsed_time)
        self._elapsed_timer.start(1000)

        # Create core widgets
        self.log_widget = LogWidget()
        self.log_interface = LogInterface(self.log_widget)
        self.about_interface = AboutInterface()

        self.zone_list = ZoneListWidget(self.api_client, self.cache_manager)
        self.record_widget = RecordWidget(self.api_client, self.cache_manager, self.config_manager)

        self.zone_list.zone_selected.connect(self.on_zone_selected)
        self.zone_list.zone_added.connect(self.sync_data)
        self.zone_list.zone_deleted.connect(self.on_zone_deleted)
        self.zone_list.log_message.connect(self.log_message)
        self.record_widget.records_changed.connect(self.on_records_changed)
        self.record_widget.log_message.connect(self.log_message)

        # DNS interface (main page)
        self.dns_interface = DnsInterface(
            self.zone_list, self.record_widget, self.config_manager,
        )

        # Build sidebar pages
        available_zones = []  # populated when zones load
        self.export_interface = ExportInterface(self.import_export_manager, available_zones)
        self.export_interface.zones_refresh_requested.connect(self._on_import_export_zones_refresh)

        self.import_interface = ImportInterface(self.import_export_manager, available_zones)
        self.import_interface.import_completed.connect(self.sync_data)
        self.import_interface.zones_refresh_requested.connect(self._on_import_export_zones_refresh)

        self.search_replace_interface = SearchReplaceInterface(
            self.api_client, self.cache_manager
        )

        self.token_manager_interface = TokenManagerInterface(self.api_client)

        self.profile_interface = ProfileInterface(self.profile_manager) if self.profile_manager else None
        if self.profile_interface:
            self.profile_interface.profile_switched.connect(self.on_profile_switched)

        self.settings_interface = SettingsInterface(self.config_manager, self.theme_manager)

        # ── Sidebar: Core workflow ──
        self.addSubInterface(self.dns_interface, FluentIcon.GLOBE, "DNS")
        self.addSubInterface(self.search_replace_interface, FluentIcon.SEARCH, "Search & Replace")

        self.navigationInterface.addSeparator()

        # ── Sidebar: Data transfer ──
        self.addSubInterface(self.import_interface, FluentIcon.RIGHT_ARROW, "Import")
        self.addSubInterface(self.export_interface, FluentIcon.LEFT_ARROW, "Export")

        self.navigationInterface.addSeparator()

        # ── Sidebar: Account & config ──
        self.addSubInterface(self.token_manager_interface, FluentIcon.CERTIFICATE, "Tokens")
        if self.profile_interface:
            self.addSubInterface(self.profile_interface, FluentIcon.PEOPLE, "Profile")
        self.addSubInterface(self.settings_interface, FluentIcon.SETTING, "Settings")

        # ── Sidebar: Bottom — info, log, status ──
        self.addSubInterface(
            self.about_interface, FluentIcon.INFO, "About",
            position=NavigationItemPosition.BOTTOM,
        )
        self.addSubInterface(
            self.log_interface, FluentIcon.HISTORY, "Log Console",
            position=NavigationItemPosition.BOTTOM,
        )
        self.navigationInterface.addItem(
            routeKey="syncNow",
            icon=FluentIcon.SYNC,
            text="Sync",
            onClick=self.sync_data,
            selectable=False,
            position=NavigationItemPosition.BOTTOM,
        )

        # Connection status — clickable to toggle offline mode
        self._status_nav_item = self.navigationInterface.addItem(
            routeKey="connectionStatus",
            icon=FluentIcon.WIFI,
            text="Initializing",
            onClick=self.toggle_offline_mode,
            selectable=False,
            position=NavigationItemPosition.BOTTOM,
        )

        # Last sync timer — very bottom of sidebar
        self._sync_nav_item = self.navigationInterface.addItem(
            routeKey="lastSync",
            icon=FluentIcon.HISTORY,
            text="Synced: Never",
            onClick=self.sync_data,
            selectable=False,
            position=NavigationItemPosition.BOTTOM,
        )

        # Wire settings page signals
        self.settings_interface.settings_applied.connect(self.update_sync_interval)
        self.settings_interface.settings_applied.connect(self._apply_debug_mode)
        self.settings_interface.settings_applied.connect(
            lambda: self.check_api_connectivity(True)
        )
        self.settings_interface.token_change_requested.connect(self.show_auth_dialog)
        self.settings_interface.token_manager_requested.connect(
            lambda: self.switchTo(self.token_manager_interface)
        )

        # Sidebar width and default state
        self.navigationInterface.setExpandWidth(180)
        self.navigationInterface.expand(useAni=False)

        # Disable page-switch animation (no slide/whip effect when changing sidebar items)
        self.stackedWidget.setAnimationEnabled(False)

        # Auth panel — slide-in overlay for token entry (covers the full window)
        self._auth_panel = AuthPanel(self.config_manager, parent=self)
        self._auth_panel.token_saved.connect(self._on_token_saved)

        # Notification drawer (slides from top, full window width)
        self._notify_drawer = NotifyDrawer(parent=self)

        # Global keyboard shortcuts
        self._setup_shortcuts()

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Q"), self, self._confirm_quit_dialog)
        QShortcut(QKeySequence("Ctrl+F"), self, self._cycle_through_search_filters)

    # ── Sync / timers ─────────────────────────────────────────────────────────

    def _apply_initial_debug_mode(self):
        """Set logging level at startup based on saved debug_mode."""
        if self.config_manager.get_debug_mode():
            logging.getLogger().setLevel(logging.DEBUG)

    def setup_sync_timer(self):
        self.sync_timer_id = QTimer(self)
        self.sync_timer_id.timeout.connect(self.sync_data)
        interval_minutes = self.config_manager.get_sync_interval()
        self.sync_timer_id.start(interval_minutes * 60 * 1000)
        logger.info(f"Sync timer started with interval of {interval_minutes} minutes")

        self.keepalive_timer = QTimer(self)
        self.keepalive_timer.timeout.connect(self.check_api_connectivity)
        keepalive_seconds = self.config_manager.get_keepalive_interval()
        self.keepalive_timer.start(keepalive_seconds * 1000)
        logger.info(f"Keepalive timer started with interval of {keepalive_seconds} seconds")

    def update_sync_interval(self):
        interval_minutes = self.config_manager.get_sync_interval()
        self.sync_timer_id.setInterval(interval_minutes * 60 * 1000)
        logger.info(f"Sync timer set to {interval_minutes} minutes")
        self.log_message(f"Sync timer set to {interval_minutes} minutes")

    def _apply_debug_mode(self):
        """Toggle root logger level based on the debug_mode setting."""
        enabled = self.config_manager.get_debug_mode()
        level = logging.DEBUG if enabled else logging.INFO
        logging.getLogger().setLevel(level)
        self.log_message(
            f"Debug mode {'enabled' if enabled else 'disabled'} — log level {logging.getLevelName(level)}",
            "info",
        )

    # ── Connectivity ──────────────────────────────────────────────────────────

    def check_api_connectivity(self, manual_check=False):
        if self.config_manager.get_offline_mode():
            self.update_connection_status(False)
            if manual_check:
                self.log_message("Connectivity check skipped - Offline mode is enabled", "warning")
            return

        if manual_check:
            self.log_message("Checking API connectivity...", "info")

        class ConnectivitySignals(QtCore.QObject):
            result_ready = QtCore.Signal(bool, bool)

        class ConnectivityWorker(QtCore.QRunnable):
            def __init__(self, api_client, manual_check):
                super().__init__()
                self.api_client = api_client
                self.manual_check = manual_check
                self.signals = ConnectivitySignals()

            def run(self):
                is_online = self.api_client.check_connectivity()
                self.signals.result_ready.emit(is_online, self.manual_check)

        worker = ConnectivityWorker(self.api_client, manual_check)
        worker.signals.result_ready.connect(self._handle_connectivity_result)
        self.thread_pool.start(worker)

    def _handle_connectivity_result(self, is_online, manual_check):
        self.update_connection_status(is_online)
        if is_online:
            self._check_token_management_permission()
            self._fetch_account_limit()
        if manual_check:
            if is_online:
                self.log_message("API connection check successful", "success")
            else:
                self.log_message("API connection check failed - API is unreachable", "error")

    def _fetch_account_limit(self):
        class _AccountSignals(QtCore.QObject):
            result_ready = QtCore.Signal(object)

        class _AccountWorker(QtCore.QRunnable):
            def __init__(self, api_client):
                super().__init__()
                self.api_client = api_client
                self.signals = _AccountSignals()

            def run(self):
                success, data = self.api_client.get_account_info()
                if success and isinstance(data, dict):
                    self.signals.result_ready.emit(data.get("limit_domains"))
                else:
                    self.signals.result_ready.emit(None)

        worker = _AccountWorker(self.api_client)
        worker.signals.result_ready.connect(self._handle_account_limit)
        self.thread_pool.start(worker)

    def _handle_account_limit(self, limit):
        self.zone_list.set_domain_limit(limit)

    def _check_token_management_permission(self):
        class _PermSignals(QtCore.QObject):
            result_ready = QtCore.Signal(bool)

        class _PermWorker(QtCore.QRunnable):
            def __init__(self, api_client):
                super().__init__()
                self.api_client = api_client
                self.signals = _PermSignals()

            def run(self):
                success, _ = self.api_client.list_tokens()
                self.signals.result_ready.emit(success)

        worker = _PermWorker(self.api_client)
        worker.signals.result_ready.connect(self._handle_token_perm_result)
        self.thread_pool.start(worker)

    def _handle_token_perm_result(self, has_permission):
        # Phase 5i will wire this to the Tokens nav item state
        pass

    def show_token_manager_dialog(self):
        self.switchTo(self.token_manager_interface)

    def update_connection_status(self, is_online):
        if hasattr(self, '_status_nav_item'):
            if is_online is None:
                self._status_nav_item.setText("Initializing")
                self._status_nav_item.setTextColor(
                    QtGui.QColor(120, 120, 120),  # light theme: grey
                    QtGui.QColor(120, 120, 120),  # dark theme: grey
                )
            elif is_online:
                self._status_nav_item.setText("Online")
                self._status_nav_item.setTextColor(
                    QtGui.QColor("#2E7D32"),  # light theme: dark green
                    QtGui.QColor("#4CAF50"),  # dark theme: bright green
                )
            else:
                self._status_nav_item.setText("Offline")
                self._status_nav_item.setTextColor(
                    QtGui.QColor("#C62828"),  # light theme: dark red
                    QtGui.QColor("#F44336"),  # dark theme: bright red
                )

    def update_record_edit_state(self):
        is_offline = self.config_manager.get_offline_mode()
        can_edit = not is_offline
        if hasattr(self, "record_widget"):
            self.record_widget.set_edit_enabled(can_edit)
        if hasattr(self, "zone_list") and hasattr(self.zone_list, "set_edit_enabled"):
            self.zone_list.set_edit_enabled(can_edit)
        if is_offline:
            logger.warning("Offline mode enabled - Record and zone editing disabled")

    # ── Data sync ────────────────────────────────────────────────────────────

    def sync_data(self):
        if not self.config_manager.get_auth_token():
            self.log_message(
                "No API token configured. Please set up your authentication token.", "warning"
            )
            return
        if self.config_manager.get_offline_mode():
            logger.info("Skipping sync while in offline mode")
            self._load_zones_from_cache()
            return

        if hasattr(self, '_sync_nav_item'):
            self._sync_nav_item.setText("Syncing...")

        from workers import LoadZonesWorker
        worker = LoadZonesWorker(self.api_client, self.cache_manager)
        worker.signals.finished.connect(self._on_zones_loaded)
        self.thread_pool.start(worker)

    def _on_zones_loaded(self, success, zones, message):
        self.update_connection_status(success)
        if success:
            self.last_sync_time = time.time()
            self._check_token_management_permission()
            self._fetch_account_limit()
            self.log_message(f"Retrieved {len(zones)} zones from API", "success")
            self.zone_list.zone_model.update_zones(zones)
            self.zone_list.zone_count_label.setText(
                f"Total zones: {self.zone_list._zone_count_text(len(zones))}"
            )
            if len(zones) > 0 and self.zone_list.zone_list_view.model().rowCount() > 0:
                first_index = self.zone_list.zone_list_view.model().index(0, 0)
                self.zone_list.zone_list_view.selectionModel().select(
                    first_index,
                    QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect,
                )
                self.zone_list.zone_list_view.setCurrentIndex(first_index)
        else:
            msg_str = str(message)
            if "401" in msg_str or "Invalid token" in msg_str or "Unauthorized" in msg_str:
                self.log_message(
                    "Authentication failed (401 Invalid token). "
                    "Please update your API token via Settings.",
                    "error",
                )
                self._notify_drawer.error(
                    "Invalid API Token",
                    "The API token was rejected by deSEC (HTTP 401).\n\n"
                    "Please open Settings and enter a valid token.",
                )
            else:
                self.log_message(f"Failed to sync with API: {message}", "warning")
            self._load_zones_from_cache()

    def _load_zones_from_cache(self):
        cache_result = self.cache_manager.get_cached_zones()
        if cache_result and isinstance(cache_result, tuple) and len(cache_result) == 2:
            zones, timestamp = cache_result
            if zones:
                self.zone_list.handle_zones_result(True, zones, "Loaded from cache")
                self.log_message("Loaded data from cache", "info")
                return
        self.log_message("No cached data available", "warning")

    # ── Zone / record handling ────────────────────────────────────────────────

    def on_zone_selected(self, zone_name: str) -> None:
        start_time = time.time()
        logger.info(f"Zone selected: {zone_name}")
        self.current_zone = zone_name
        self.setWindowTitle("deSEC DNS Manager")
        if hasattr(self, "record_table") and self.record_table is not None:
            self.record_table.clearSelection()
        if hasattr(self, "detail_form") and self.detail_form is not None:
            self.detail_form.clear_form()
        self.cache_manager.get_zone_by_name(zone_name)
        self.load_zone_records(zone_name)
        elapsed = (time.time() - start_time) * 1000
        logger.debug(f"Zone selection processing completed in {elapsed:.1f}ms")

    def load_zone_records(self, zone_name: str) -> None:
        start_time = time.time()
        self.record_widget.set_domain(zone_name)
        elapsed = (time.time() - start_time) * 1000
        logger.debug(f"Set domain and loaded records in {elapsed:.1f}ms")

    def on_records_changed(self):
        self.record_widget.refresh_records()

    def on_zone_deleted(self):
        self.record_widget.current_domain = None
        self.record_widget.records = []
        self.record_widget.update_records_table()
        self.sync_data()
        self.log_message("Zone deleted - records view cleared and data synced", "info")

    # ── Dialogs ──────────────────────────────────────────────────────────────

    def show_auth_dialog(self):
        """Open the slide-in auth panel for entering / changing the API token."""
        self._auth_panel.open()

    def _on_token_saved(self):
        """Called when AuthPanel successfully saves a new token."""
        self.log_message(
            "API token changed. Clearing cache and logs for security reasons...", "info"
        )
        if self.cache_manager.clear_all_cache():
            self.log_message("Cache cleared successfully", "success")
        else:
            self.log_message(
                "Failed to clear cache completely. Some files may remain.", "warning"
            )
        if self.purge_log_file():
            self.log_message("Log file purged successfully", "success")
        else:
            self.log_message("Failed to purge log file", "warning")
        self.api_client.check_connectivity()
        self.sync_data()

    def show_config_dialog(self):
        self.switchTo(self.settings_interface)

    def show_profile_dialog(self):
        if not self.profile_interface:
            self.log_message("Profile management is not available", "warning")
            return
        self.switchTo(self.profile_interface)

    def show_search_replace_dialog(self):
        self.switchTo(self.search_replace_interface)

    def show_import_export_interface(self):
        self._on_import_export_zones_refresh()
        self.switchTo(self.export_interface)

    def show_import_export_dialog(self):
        """Alias kept for any remaining call sites."""
        self.show_import_export_interface()

    def _on_import_export_zones_refresh(self):
        """Provide current zones to Export/Import pages whenever either becomes visible."""
        available_zones = []
        if hasattr(self.zone_list, "zone_model") and self.zone_list.zone_model.zones:
            available_zones = [zone.get("name", "") for zone in self.zone_list.zone_model.zones]
        self.export_interface.update_zones(available_zones)
        self.import_interface.update_zones(available_zones)

    def show_changelog(self):
        changelog_url = "https://github.com/jaydio/desec-qt-dns/blob/master/CHANGELOG.md"
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(changelog_url))
        self.log_message("Changelog opened in browser", "info")

    def show_keyboard_shortcuts_dialog(self):
        shortcuts_text = (
            "<html><body>"
            "<h3>Keyboard Shortcuts</h3>"
            "<table>"
            "<tr><td><b>F5</b></td><td>Sync Now</td></tr>"
            "<tr><td><b>Ctrl+F</b></td><td>Cycle search fields</td></tr>"
            "<tr><td><b>Ctrl+Q</b></td><td>Quit</td></tr>"
            "<tr><td><b>Delete</b></td><td>Delete selected zone/record</td></tr>"
            "<tr><td><b>Escape</b></td><td>Clear active search filter</td></tr>"
            "</table>"
            "</body></html>"
        )
        QtWidgets.QMessageBox.information(self, "Keyboard Shortcuts", shortcuts_text)

    # ── Toggle actions ────────────────────────────────────────────────────────

    def toggle_offline_mode(self):
        is_offline = not self.config_manager.get_offline_mode()
        self.config_manager.set_offline_mode(is_offline)
        self.config_manager.save_config()
        if is_offline:
            self.log_message("Offline mode enabled - Record editing disabled", "warning")
            self.update_connection_status(False)
        else:
            self.log_message("Offline mode disabled - syncing...", "info")
            self.sync_data()
        self.update_record_edit_state()

    def toggle_log_console(self):
        self.switchTo(self.log_interface)

    def toggle_multiline_records(self):
        show_multiline = self.config_manager.get_show_multiline_records()
        show_multiline = not show_multiline
        self.config_manager.set_show_multiline_records(show_multiline)
        if hasattr(self, "record_widget") and self.record_widget is not None:
            self.record_widget.set_multiline_display(show_multiline)
        mode = "full" if show_multiline else "condensed"
        self.log_message(f"Multiline record display: {mode.capitalize()} mode", "info")

    # ── Utility ──────────────────────────────────────────────────────────────

    def purge_log_file(self):
        try:
            log_file = os.path.join(
                os.path.expanduser("~/.config/desecqt/logs"), "desecqt.log"
            )
            if os.path.exists(log_file):
                open(log_file, "w").close()
            return True
        except Exception as e:
            logger.warning(f"Failed to purge log file: {str(e)}")
            return False

    def log_message(self, message, level="info"):
        self.log_widget.add_message(message, level)
        if level == "info":
            logger.info(message)
        elif level == "warning":
            logger.warning(message)
        elif level == "error":
            logger.error(message)
        elif level == "success":
            logger.info(f"SUCCESS: {message}")

    def update_elapsed_time(self):
        if not hasattr(self, '_sync_nav_item'):
            return
        if self.last_sync_time is None:
            self._sync_nav_item.setText("Synced: Never")
            return
        elapsed_seconds = int(time.time() - self.last_sync_time)
        if elapsed_seconds < 60:
            self._sync_nav_item.setText(f"Synced: {elapsed_seconds}s ago")
        elif elapsed_seconds < 3600:
            m = elapsed_seconds // 60
            self._sync_nav_item.setText(f"Synced: {m}m ago")
        else:
            h = elapsed_seconds // 3600
            m = (elapsed_seconds % 3600) // 60
            self._sync_nav_item.setText(f"Synced: {h}h {m}m ago")

    def on_profile_switched(self, profile_name):
        self.log_message(f"Profile switched to '{profile_name}'. Restarting application...", "info")
        self.restart_application()

    def restart_application(self):
        import sys
        try:
            self.config_manager.save_config()
            python_executable = sys.executable
            script_path = sys.argv[0]
            QtWidgets.QApplication.quit()
            os.execl(python_executable, python_executable, script_path)
        except Exception as e:
            logger.error(f"Failed to restart application: {e}")
            self._notify_drawer.error(
                "Restart Failed",
                f"Failed to restart the application: {str(e)}\n\n"
                "Please restart manually to apply profile changes.",
            )

    def clear_cache(self):
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Confirm Cache Clear",
            "Are you sure you want to clear all cached data? "
            "This will remove all local cache files and require a fresh sync.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if confirm == QtWidgets.QMessageBox.StandardButton.Yes:
            if self.cache_manager.clear_all_cache():
                self.log_message("Cache cleared successfully. Initiating new sync...", "success")
                self.sync_data()
            else:
                self.log_message(
                    "Failed to clear cache completely. Some files may remain.", "error"
                )

    # ── Keyboard events ──────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F5:
            self.sync_data()
            event.accept()
            return
        if event.key() == Qt.Key.Key_F and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self._cycle_through_search_filters()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Q and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self._confirm_quit_dialog()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Delete:
            self._handle_delete_key()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self._clear_active_search_filter()
            event.accept()
            return
        super().keyPressEvent(event)

    def _cycle_through_search_filters(self):
        search_fields = []
        if hasattr(self, "zone_list") and hasattr(self.zone_list, "search_field"):
            search_fields.append(self.zone_list.search_field)
        if hasattr(self, "record_widget") and hasattr(self.record_widget, "filter_edit"):
            search_fields.append(self.record_widget.filter_edit)
        if not search_fields:
            return
        focused_widget = QtWidgets.QApplication.focusWidget()
        if focused_widget in search_fields:
            next_index = (search_fields.index(focused_widget) + 1) % len(search_fields)
        else:
            next_index = 0
        next_field = search_fields[next_index]
        next_field.setFocus()
        next_field.selectAll()
        # Focus moves to the next search field (no status bar needed)

    def _handle_delete_key(self):
        zone_has_focus = (
            self.zone_list == QtWidgets.QApplication.focusWidget()
            or (
                hasattr(self.zone_list, "zone_list_view")
                and self.zone_list.zone_list_view.hasFocus()
            )
        )
        record_has_focus = (
            self.record_widget == QtWidgets.QApplication.focusWidget()
            or (
                hasattr(self.record_widget, "records_table")
                and self.record_widget.records_table.hasFocus()
            )
        )
        if zone_has_focus:
            self.zone_list.delete_selected_zone()
        elif record_has_focus:
            self.record_widget.delete_selected_record()

    def _clear_active_search_filter(self):
        focused_widget = QtWidgets.QApplication.focusWidget()
        cleared = False
        if hasattr(self, "zone_list") and hasattr(self.zone_list, "search_field"):
            zone_filter = self.zone_list.search_field
            if focused_widget == zone_filter:
                zone_filter.clear()
                self.zone_list.filter_zones("")
                cleared = True
        if not cleared and hasattr(self, "record_widget") and hasattr(
            self.record_widget, "filter_edit"
        ):
            record_filter = self.record_widget.filter_edit
            if focused_widget == record_filter:
                record_filter.clear()
                self.record_widget.filter_records("")
                cleared = True
        if hasattr(self, "record_widget") and hasattr(
            self.record_widget, "records_search_input"
        ):
            record_search_field = self.record_widget.records_search_input
            if focused_widget == record_search_field:
                record_search_field.clear()
                self.record_widget.filter_records("")

    def _confirm_quit_dialog(self):
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Confirm Quit",
            "Are you sure you want to quit?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if confirm == QtWidgets.QMessageBox.StandardButton.Yes:
            self.close()

    def on_theme_type_changed(self, action):
        theme_type = action.data()
        if theme_type:
            self.config_manager.set_theme_type(theme_type)
            self.config_manager.save_config()
            self.theme_manager.apply_theme()

    def on_theme_changed(self, action, theme_type):
        if theme_type:
            self.config_manager.set_theme_type(theme_type)
            self.config_manager.save_config()
            self.theme_manager.apply_theme()

    def update_record_table(self, records: List[Dict[str, Any]]) -> None:
        if not hasattr(self, "record_table") or self.record_table is None:
            return
        self.record_table.set_records(records)

    def handle_records_result(
        self, success: bool, records: List[Dict[str, Any]], zone_name: str, error_msg: str
    ) -> None:
        if success:
            self.update_record_table(records)
        else:
            if records:
                self.log_message(f"Using cached records for {zone_name}. Error: {error_msg}", "warning")
            else:
                self.log_message(f"Failed to load records: {error_msg}", "error")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_auth_panel"):
            self._auth_panel.reposition(event.size())
        if hasattr(self, "_notify_drawer"):
            self._notify_drawer.reposition(event.size())

    def closeEvent(self, event):
        self.config_manager.save_config()
        event.accept()
