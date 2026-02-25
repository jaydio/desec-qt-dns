#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Settings interface for deSEC Qt DNS Manager.
Provides a Fluent-styled inline settings page as a sidebar nav sub-interface,
replacing the modal ConfigDialog for the main navigation flow.
"""

import logging
from PySide6 import QtWidgets
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from qfluentwidgets import (
    ScrollArea, SettingCard, SettingCardGroup, PushSettingCard,
    FluentIcon, LineEdit, SpinBox, DoubleSpinBox,
    SwitchButton, PrimaryPushButton, LargeTitleLabel,
)
from fluent_styles import SCROLL_AREA_QSS, container_qss, combo_qss
from notify_drawer import NotifyDrawer

logger = logging.getLogger(__name__)

# Parallel list for theme ComboBox — qfluentwidgets ComboBox.currentData() always
# returns None (known bug), so we use currentIndex() against this list instead.
_THEME_OPTIONS = ["auto", "dark", "light"]


# ── Custom single-setting card types ─────────────────────────────────────────
# Each wraps a Fluent input widget on the right side of a SettingCard row.
# Following the same append pattern used by PushSettingCard in qfluentwidgets.

class _LineEditCard(SettingCard):
    """SettingCard with an inline LineEdit on the right."""

    def __init__(self, icon, title, content, parent=None):
        super().__init__(icon, title, content, parent)
        self.line_edit = LineEdit(self)
        self.line_edit.setMinimumWidth(240)
        self.hBoxLayout.addWidget(self.line_edit, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)


class _SpinBoxCard(SettingCard):
    """SettingCard with an inline SpinBox on the right."""

    def __init__(self, icon, title, content, min_val, max_val, suffix, parent=None):
        super().__init__(icon, title, content, parent)
        self.spin_box = SpinBox(self)
        self.spin_box.setRange(min_val, max_val)
        self.spin_box.setSuffix(suffix)
        self.spin_box.setMinimumWidth(130)
        self.hBoxLayout.addWidget(self.spin_box, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)


class _DoubleSpinBoxCard(SettingCard):
    """SettingCard with an inline DoubleSpinBox on the right."""

    def __init__(self, icon, title, content, min_val, max_val, step, decimals, suffix, parent=None):
        super().__init__(icon, title, content, parent)
        self.spin_box = DoubleSpinBox(self)
        self.spin_box.setRange(min_val, max_val)
        self.spin_box.setSingleStep(step)
        self.spin_box.setDecimals(decimals)
        self.spin_box.setSuffix(suffix)
        self.spin_box.setMinimumWidth(130)
        self.hBoxLayout.addWidget(self.spin_box, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)


class _ComboBoxCard(SettingCard):
    """SettingCard with an inline QComboBox on the right."""

    def __init__(self, icon, title, content, parent=None):
        super().__init__(icon, title, content, parent)
        self.combo = QtWidgets.QComboBox(self)
        self.combo.setMinimumWidth(160)
        self.combo.setStyleSheet(combo_qss())
        self.hBoxLayout.addWidget(self.combo, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

    def showEvent(self, event):
        super().showEvent(event)
        self.combo.setStyleSheet(combo_qss())


class _SwitchCard(SettingCard):
    """SettingCard with a SwitchButton on the right."""

    checkedChanged = Signal(bool)

    def __init__(self, icon, title, content, parent=None):
        super().__init__(icon, title, content, parent)
        self.switch = SwitchButton(self)
        self.hBoxLayout.addWidget(self.switch, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)
        self.switch.checkedChanged.connect(self.checkedChanged)

    def isChecked(self):
        return self.switch.isChecked()

    def setChecked(self, checked):
        self.switch.setChecked(checked)


# ── Settings page ─────────────────────────────────────────────────────────────

class SettingsInterface(ScrollArea):
    """
    Fluent-styled inline settings page for application configuration.

    Replaces ConfigDialog as a proper FluentWindow navigation sub-interface.
    Emits signals rather than calling MainWindow methods directly.
    """

    settings_applied = Signal()        # emitted after a successful save
    token_change_requested = Signal()  # user clicked "Change Token"
    token_manager_requested = Signal() # user clicked "Open" on Token Manager card

    def __init__(self, config_manager, theme_manager=None, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.theme_manager = theme_manager
        self.setObjectName("settingsInterface")
        self._build_ui()
        self._load_values()
        self._notify_drawer = NotifyDrawer(parent=self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_notify_drawer'):
            self._notify_drawer.reposition(event.size())

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        container = QWidget(self)
        container.setObjectName("settingsContainer")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(36, 20, 36, 20)
        layout.setSpacing(28)

        layout.addWidget(LargeTitleLabel("Settings", container))

        # ── Two-column layout ────────────────────────────────────────────
        columns = QHBoxLayout()
        columns.setSpacing(24)

        left_col = QVBoxLayout()
        left_col.setSpacing(28)
        right_col = QVBoxLayout()
        right_col.setSpacing(28)

        # ── Left: Connection ─────────────────────────────────────────────
        conn_group = SettingCardGroup("Connection", container)

        self._api_url_card = _LineEditCard(
            FluentIcon.GLOBE, "API URL",
            "deSEC API endpoint URL",
            conn_group,
        )
        self._api_url_card.line_edit.setPlaceholderText("https://desec.io/api/v1")
        conn_group.addSettingCard(self._api_url_card)

        self._token_card = PushSettingCard(
            "Change Token", FluentIcon.CERTIFICATE,
            "API Token",
            "Authentication token for the deSEC API",
            conn_group,
        )
        self._token_card.clicked.connect(self.token_change_requested)
        conn_group.addSettingCard(self._token_card)

        left_col.addWidget(conn_group)

        # ── Left: Synchronization ────────────────────────────────────────
        sync_group = SettingCardGroup("Synchronization", container)

        self._sync_interval_card = _SpinBoxCard(
            FluentIcon.SYNC, "Sync Interval",
            "How often to automatically sync with the API",
            1, 60, " min",
            sync_group,
        )
        sync_group.addSettingCard(self._sync_interval_card)

        self._rate_limit_card = _DoubleSpinBoxCard(
            FluentIcon.HISTORY, "API Rate Limit",
            "Max requests per second to prevent timeouts",
            0.0, 10.0, 0.5, 1, " req/s",
            sync_group,
        )
        sync_group.addSettingCard(self._rate_limit_card)

        left_col.addWidget(sync_group)
        left_col.addStretch()

        # ── Right: Appearance ────────────────────────────────────────────
        appearance_group = SettingCardGroup("Appearance", container)

        self._theme_card = _ComboBoxCard(
            FluentIcon.PALETTE, "Theme",
            "Application color scheme",
            appearance_group,
        )
        self._theme_card.combo.addItem("Follow OS (Auto)", "auto")
        self._theme_card.combo.addItem("Dark", "dark")
        self._theme_card.combo.addItem("Light", "light")
        appearance_group.addSettingCard(self._theme_card)

        right_col.addWidget(appearance_group)

        # ── Right: Advanced ──────────────────────────────────────────────
        advanced_group = SettingCardGroup("Advanced", container)

        self._debug_card = _SwitchCard(
            FluentIcon.DEVELOPER_TOOLS, "Debug Mode",
            "Enable verbose logging for troubleshooting",
            advanced_group,
        )
        advanced_group.addSettingCard(self._debug_card)

        self._token_mgr_card = PushSettingCard(
            "Open", FluentIcon.CERTIFICATE,
            "Token Manager",
            "Manage API tokens and RRset access policies",
            advanced_group,
        )
        self._token_mgr_card.clicked.connect(self.token_manager_requested)
        advanced_group.addSettingCard(self._token_mgr_card)

        right_col.addWidget(advanced_group)
        right_col.addStretch()

        columns.addLayout(left_col, 1)
        columns.addLayout(right_col, 1)
        layout.addLayout(columns)

        # ── Save button ──────────────────────────────────────────────────
        save_row = QHBoxLayout()
        save_row.addStretch()
        self._save_btn = PrimaryPushButton("Save Settings", container)
        self._save_btn.setFixedWidth(140)
        self._save_btn.clicked.connect(self._save)
        save_row.addWidget(self._save_btn)
        layout.addLayout(save_row)

        layout.addStretch()

        self.setWidget(container)
        self.setWidgetResizable(True)
        self.setStyleSheet(SCROLL_AREA_QSS)
        container.setStyleSheet("background: transparent;")

    # ── Value management ──────────────────────────────────────────────────────

    def _load_values(self):
        """Populate all widgets from the current ConfigManager state."""
        self._api_url_card.line_edit.setText(self.config_manager.get_api_url())
        self._sync_interval_card.spin_box.setValue(self.config_manager.get_sync_interval())
        self._rate_limit_card.spin_box.setValue(
            self.config_manager.get_setting('api_rate_limit', 2.0)
        )
        self._debug_card.setChecked(self.config_manager.get_debug_mode())

        if self.theme_manager:
            theme_type = self.config_manager.get_theme_type()
            idx = _THEME_OPTIONS.index(theme_type) if theme_type in _THEME_OPTIONS else 0
            self._theme_card.combo.setCurrentIndex(idx)

        # Show a masked token hint in the card subtitle
        token = self.config_manager.get_auth_token()
        if token:
            masked = token[:6] + "…" if len(token) > 6 else "•••"
            self._token_card.contentLabel.setText(f"Token configured: {masked}")
        else:
            self._token_card.contentLabel.setText("No token configured — click to add one")

    def showEvent(self, event):
        """Reload values whenever the page becomes visible."""
        super().showEvent(event)
        w = self.widget()
        if w:
            w.setStyleSheet("background: transparent;\n" + container_qss())
        self._load_values()

    def _save(self):
        """Validate inputs and persist settings; emit settings_applied on success."""
        api_url = self._api_url_card.line_edit.text().strip()
        if not api_url:
            self._notify_drawer.warning("Invalid API URL", "Please enter a valid API URL.")
            return

        self.config_manager.set_api_url(api_url)
        self.config_manager.set_sync_interval(self._sync_interval_card.spin_box.value())
        self.config_manager.set_setting('api_rate_limit', self._rate_limit_card.spin_box.value())
        self.config_manager.set_debug_mode(self._debug_card.isChecked())

        if self.theme_manager:
            theme_type = _THEME_OPTIONS[self._theme_card.combo.currentIndex()]
            self.config_manager.set_theme_type(theme_type)
            self.theme_manager.apply_theme()

        self.config_manager.save_config()
        logger.info("Settings saved from SettingsInterface")
        self.settings_applied.emit()
