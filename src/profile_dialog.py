#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Profile management interface for deSEC Qt DNS Manager.
Allows users to create, switch, rename, and delete profiles.

All interactions use slide-in panels and drawers (no popup dialogs).
"""

import logging
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve
from qfluentwidgets import (
    PushButton, PrimaryPushButton, ListWidget, LineEdit,
    LargeTitleLabel, SubtitleLabel, isDarkTheme,
    InfoBar, InfoBarPosition,
)
from fluent_styles import container_qss
from confirm_drawer import DeleteConfirmDrawer, ConfirmDrawer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ProfileFormPanel — slide-in right panel for create / rename
# ---------------------------------------------------------------------------

class ProfileFormPanel(QtWidgets.QWidget):
    """Slide-in right panel for creating or renaming a profile.

    Follows the same pattern as RecordEditPanel, AddZonePanel, and
    TokenPolicyPanel: overlay on the right side of the parent widget,
    animated with QPropertyAnimation on ``pos``.
    """

    PANEL_WIDTH = 400

    profile_saved = Signal()        # emitted on successful create / rename
    cancelled = Signal()

    def __init__(self, profile_manager, parent=None):
        super().__init__(parent)
        self.profile_manager = profile_manager
        self._mode = "create"       # "create" or "rename"
        self._profile_data = None   # filled in rename mode
        self._animation = None
        self.setObjectName("profileFormPanel")
        self.hide()
        self._setup_ui()

    # ── painting ───────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        bg = QtGui.QColor(32, 32, 32) if isDarkTheme() else QtGui.QColor(243, 243, 243)
        painter.fillRect(self.rect(), bg)

    # ── UI ─────────────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Header row: title + close button
        header_row = QtWidgets.QHBoxLayout()
        self._title = SubtitleLabel("Create New Profile")
        header_row.addWidget(self._title, 1)
        close_btn = PushButton("\u2715")
        close_btn.setFixedSize(32, 32)
        close_btn.setToolTip("Close (Esc)")
        close_btn.clicked.connect(self._on_cancel)
        header_row.addWidget(close_btn)
        layout.addLayout(header_row)

        # Escape shortcut
        esc = QtGui.QShortcut(QtGui.QKeySequence(Qt.Key.Key_Escape), self)
        esc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        esc.activated.connect(self._on_cancel)

        # Form
        form = QtWidgets.QFormLayout()
        form.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.DontWrapRows)

        self._name_input = LineEdit()
        self._name_input.setPlaceholderText("e.g., work, personal, staging")
        self._name_input.textChanged.connect(self._validate)
        form.addRow("Profile Name:", self._name_input)

        self._display_input = LineEdit()
        self._display_input.setPlaceholderText("e.g., Work Account, Personal DNS")
        self._display_input.textChanged.connect(self._validate)
        form.addRow("Display Name:", self._display_input)

        layout.addLayout(form)

        # Help text
        self._help_label = QtWidgets.QLabel(
            "Profile name is used internally and cannot contain spaces or special characters. "
            "Display name is shown in the interface."
        )
        self._help_label.setWordWrap(True)
        layout.addWidget(self._help_label)

        # Error label (hidden by default)
        self._error_label = QtWidgets.QLabel("")
        self._error_label.setWordWrap(True)
        self._error_label.setStyleSheet("color: #e04040;")
        self._error_label.hide()
        layout.addWidget(self._error_label)

        layout.addStretch()

        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = PushButton("Cancel")
        cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(cancel_btn)
        self._save_btn = PrimaryPushButton("Create")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self._save_btn)
        layout.addLayout(btn_row)

    # ── public API ─────────────────────────────────────────────────────

    def open_for_create(self):
        """Open the panel in create mode."""
        self._mode = "create"
        self._profile_data = None
        self._title.setText("Create New Profile")
        self._save_btn.setText("Create")
        self._name_input.setReadOnly(False)
        self._name_input.clear()
        self._display_input.clear()
        self._error_label.hide()
        self._help_label.setText(
            "Profile name is used internally and cannot contain spaces or special characters. "
            "Display name is shown in the interface."
        )
        self._name_input.setFocus()
        self._validate()
        self.slide_in()

    def open_for_rename(self, profile_data):
        """Open the panel in rename mode with pre-filled data."""
        self._mode = "rename"
        self._profile_data = profile_data
        self._title.setText(f"Rename Profile")

        is_default = profile_data["name"] == self.profile_manager.DEFAULT_PROFILE_NAME

        self._save_btn.setText("Save")
        self._name_input.setText(profile_data["name"])
        self._name_input.setReadOnly(is_default)
        self._display_input.setText(profile_data["display_name"])
        self._error_label.hide()

        if is_default:
            self._help_label.setText(
                "The default profile's internal name cannot be changed, "
                "but you can update its display name."
            )
        else:
            self._help_label.setText(
                "Profile name is used internally and cannot contain spaces or special characters."
            )

        self._display_input.setFocus()
        self._display_input.selectAll()
        self._validate()
        self.slide_in()

    # ── validation ─────────────────────────────────────────────────────

    def _validate(self):
        name = self._name_input.text().strip()
        display_name = self._display_input.text().strip()

        if self._mode == "create":
            is_valid = bool(name and name.replace('_', '').replace('-', '').isalnum())
            if is_valid:
                existing = self.profile_manager.get_available_profiles()
                if name in [p["name"] for p in existing]:
                    is_valid = False
            is_valid = is_valid and bool(display_name or name)
        else:
            # rename mode
            is_default = (self._profile_data and
                          self._profile_data["name"] == self.profile_manager.DEFAULT_PROFILE_NAME)
            if is_default:
                is_valid = bool(display_name)
            else:
                is_valid = bool(name and name.replace('_', '').replace('-', '').isalnum())
                if is_valid and name != self._profile_data["name"]:
                    existing = self.profile_manager.get_available_profiles()
                    if name in [p["name"] for p in existing]:
                        is_valid = False
                is_valid = is_valid and bool(display_name)

        self._save_btn.setEnabled(is_valid)

    # ── save ───────────────────────────────────────────────────────────

    def _on_save(self):
        name = self._name_input.text().strip()
        display_name = self._display_input.text().strip() or name

        if self._mode == "create":
            success = self.profile_manager.create_profile(name, display_name)
            if success:
                self.slide_out()
                self.profile_saved.emit()
            else:
                self._error_label.setText(
                    f"Failed to create profile '{name}'. "
                    "It may already exist or there was a file system error."
                )
                self._error_label.show()
        else:
            new_name = name if not self._name_input.isReadOnly() else self._profile_data["name"]
            success = self.profile_manager.rename_profile(
                self._profile_data["name"], new_name, display_name,
            )
            if success:
                self.slide_out()
                self.profile_saved.emit()
            else:
                self._error_label.setText(
                    "Failed to rename profile. "
                    "The new name may already exist or there was a file system error."
                )
                self._error_label.show()

    def _on_cancel(self):
        self.slide_out()
        self.cancelled.emit()

    # ── animation ──────────────────────────────────────────────────────

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

    def reposition(self, parent_size):
        if not self.isVisible():
            return
        pw, ph = parent_size.width(), parent_size.height()
        self.setGeometry(pw - self.PANEL_WIDTH, 0, self.PANEL_WIDTH, ph)

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


# ---------------------------------------------------------------------------
# ProfileInterface — sidebar page
# ---------------------------------------------------------------------------

class ProfileInterface(QtWidgets.QWidget):
    """Profile management page for the Fluent sidebar navigation."""

    profile_switched = Signal(str)  # profile_name

    def __init__(self, profile_manager, parent=None):
        super().__init__(parent)
        self.setObjectName("profileInterface")

        self.profile_manager = profile_manager
        self.setup_ui()

        # Drawers (parent=self so they overlay this page)
        self._delete_drawer = DeleteConfirmDrawer(parent=self)
        self._confirm_drawer = ConfirmDrawer(parent=self)

        # Slide-in form panel (parent=self so it overlays this page)
        self._form_panel = ProfileFormPanel(self.profile_manager, parent=self)
        self._form_panel.profile_saved.connect(self.refresh_profiles)

        self.refresh_profiles()

    def showEvent(self, event):
        super().showEvent(event)
        self.setStyleSheet(container_qss())
        self.refresh_profiles()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_delete_drawer'):
            self._delete_drawer.reposition(event.size())
        if hasattr(self, '_confirm_drawer'):
            self._confirm_drawer.reposition(event.size())
        if hasattr(self, '_form_panel'):
            self._form_panel.reposition(event.size())

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(36, 20, 36, 20)
        layout.setSpacing(16)

        # Header
        layout.addWidget(LargeTitleLabel("Profiles"))

        # Description
        desc_label = QtWidgets.QLabel(
            "Each profile has isolated API tokens, cache, and settings. "
            "Use profiles to manage multiple deSEC accounts or environments."
        )
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Profiles list and controls
        content_layout = QtWidgets.QHBoxLayout()

        # Left side — profiles list
        left_layout = QtWidgets.QVBoxLayout()

        profiles_label = QtWidgets.QLabel("Available Profiles:")
        left_layout.addWidget(profiles_label)

        self.profiles_list = ListWidget()
        self.profiles_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.profiles_list.itemSelectionChanged.connect(self.on_profile_selection_changed)
        self.profiles_list.itemDoubleClicked.connect(self.switch_profile)
        left_layout.addWidget(self.profiles_list)

        content_layout.addLayout(left_layout, 2)

        # Right side — controls
        controls_layout = QtWidgets.QVBoxLayout()

        self.switch_button = PushButton("Switch To")
        self.switch_button.setToolTip("Switch to the selected profile")
        self.switch_button.clicked.connect(self.switch_profile)
        self.switch_button.setEnabled(False)
        controls_layout.addWidget(self.switch_button)

        controls_layout.addSpacing(10)

        self.create_button = PushButton("Create New...")
        self.create_button.setToolTip("Create a new profile")
        self.create_button.clicked.connect(self.create_profile)
        controls_layout.addWidget(self.create_button)

        self.rename_button = PushButton("Rename...")
        self.rename_button.setToolTip("Rename the selected profile")
        self.rename_button.clicked.connect(self.rename_profile)
        self.rename_button.setEnabled(False)
        controls_layout.addWidget(self.rename_button)

        self.delete_button = PushButton("Delete")
        self.delete_button.setToolTip("Delete the selected profile")
        self.delete_button.clicked.connect(self.delete_profile)
        self.delete_button.setEnabled(False)
        controls_layout.addWidget(self.delete_button)

        controls_layout.addStretch()

        # Profile info
        info_group = QtWidgets.QGroupBox("Profile Information")
        info_layout = QtWidgets.QFormLayout(info_group)

        self.info_name = QtWidgets.QLabel("-")
        self.info_display_name = QtWidgets.QLabel("-")
        self.info_created = QtWidgets.QLabel("-")
        self.info_last_used = QtWidgets.QLabel("-")

        info_layout.addRow("Name:", self.info_name)
        info_layout.addRow("Display Name:", self.info_display_name)
        info_layout.addRow("Created:", self.info_created)
        info_layout.addRow("Last Used:", self.info_last_used)

        controls_layout.addWidget(info_group)

        content_layout.addLayout(controls_layout, 1)
        layout.addLayout(content_layout)

        self.setStyleSheet(container_qss())

        # Bottom buttons
        button_layout = QtWidgets.QHBoxLayout()

        self.refresh_button = PushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_profiles)
        button_layout.addWidget(self.refresh_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

    def refresh_profiles(self):
        self.profiles_list.clear()

        profiles = self.profile_manager.get_available_profiles()

        for profile in profiles:
            item = QtWidgets.QListWidgetItem()

            display_text = profile["display_name"]
            if profile["is_current"]:
                display_text += " (Current)"

            item.setText(display_text)
            item.setData(Qt.ItemDataRole.UserRole, profile)

            if profile["is_current"]:
                font = item.font()
                font.setBold(True)
                item.setFont(font)

            self.profiles_list.addItem(item)

        # Select current profile
        for i in range(self.profiles_list.count()):
            item = self.profiles_list.item(i)
            profile_data = item.data(Qt.ItemDataRole.UserRole)
            if profile_data["is_current"]:
                self.profiles_list.setCurrentItem(item)
                break

    def on_profile_selection_changed(self):
        current_item = self.profiles_list.currentItem()

        if current_item:
            profile_data = current_item.data(Qt.ItemDataRole.UserRole)

            self.info_name.setText(profile_data["name"])
            self.info_display_name.setText(profile_data["display_name"])

            created_at = profile_data.get("created_at", "Unknown")
            if created_at and created_at != "Unknown":
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    created_at = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass
            self.info_created.setText(created_at)

            last_used = profile_data.get("last_used", "Never")
            if last_used and last_used != "Never":
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(last_used.replace('Z', '+00:00'))
                    last_used = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass
            self.info_last_used.setText(last_used)

            is_current = profile_data["is_current"]
            is_default = profile_data["name"] == self.profile_manager.DEFAULT_PROFILE_NAME

            self.switch_button.setEnabled(not is_current)
            self.rename_button.setEnabled(True)
            self.delete_button.setEnabled(not is_default and not is_current)
        else:
            self.info_name.setText("-")
            self.info_display_name.setText("-")
            self.info_created.setText("-")
            self.info_last_used.setText("-")

            self.switch_button.setEnabled(False)
            self.rename_button.setEnabled(False)
            self.delete_button.setEnabled(False)

    # ── actions ────────────────────────────────────────────────────────

    def create_profile(self):
        self._form_panel.open_for_create()

    def rename_profile(self):
        current_item = self.profiles_list.currentItem()
        if not current_item:
            return
        profile_data = current_item.data(Qt.ItemDataRole.UserRole)
        self._form_panel.open_for_rename(profile_data)

    def switch_profile(self):
        current_item = self.profiles_list.currentItem()
        if not current_item:
            return

        profile_data = current_item.data(Qt.ItemDataRole.UserRole)
        profile_name = profile_data["name"]

        if profile_data["is_current"]:
            InfoBar.info(
                title="Already Current",
                content=f"'{profile_data['display_name']}' is already the current profile.",
                parent=self.window(),
                duration=3000,
                position=InfoBarPosition.TOP,
            )
            return

        display = profile_data["display_name"]

        def _do_switch():
            success = self.profile_manager.switch_to_profile(profile_name)
            if success:
                self.profile_switched.emit(profile_name)
                InfoBar.success(
                    title="Profile Switched",
                    content=f"Successfully switched to '{display}'.",
                    parent=self.window(),
                    duration=4000,
                    position=InfoBarPosition.TOP,
                )
                self.refresh_profiles()
            else:
                InfoBar.error(
                    title="Switch Failed",
                    content=f"Failed to switch to profile '{display}'.",
                    parent=self.window(),
                    duration=8000,
                    position=InfoBarPosition.TOP,
                )

        self._confirm_drawer.ask(
            title="Switch Profile",
            message=f"Switch to profile '{display}'?\n\n"
                    "This will close the current session and reload with the new profile's settings.",
            on_confirm=_do_switch,
            confirm_text="Switch Profile",
        )

    def delete_profile(self):
        current_item = self.profiles_list.currentItem()
        if not current_item:
            return

        profile_data = current_item.data(Qt.ItemDataRole.UserRole)
        profile_name = profile_data["name"]

        if profile_name == self.profile_manager.DEFAULT_PROFILE_NAME:
            InfoBar.warning(
                title="Cannot Delete",
                content="The default profile cannot be deleted.",
                parent=self.window(),
                duration=5000,
                position=InfoBarPosition.TOP,
            )
            return

        if profile_data["is_current"]:
            InfoBar.warning(
                title="Cannot Delete",
                content="Cannot delete the currently active profile. Switch to another profile first.",
                parent=self.window(),
                duration=5000,
                position=InfoBarPosition.TOP,
            )
            return

        def _do_delete():
            success = self.profile_manager.delete_profile(profile_name)
            if success:
                self.refresh_profiles()
            else:
                InfoBar.error(
                    title="Delete Failed",
                    content=f"Failed to delete profile '{profile_data['display_name']}'.",
                    parent=self.window(),
                    duration=8000,
                    position=InfoBarPosition.TOP,
                )

        self._delete_drawer.ask(
            title="Delete Profile",
            message=f"Permanently delete profile '{profile_data['display_name']}'?\n\nThis action cannot be undone.",
            items=[
                "API tokens and settings",
                "Cached zones and records",
                "All profile-specific configuration",
            ],
            on_confirm=_do_delete,
            confirm_text="Delete Profile",
        )
