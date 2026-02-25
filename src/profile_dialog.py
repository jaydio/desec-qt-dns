#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Profile management dialog for deSEC Qt DNS Manager.
Allows users to create, switch, rename, and delete profiles.
"""

import logging
from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import Qt, Signal
from qfluentwidgets import PushButton, PrimaryPushButton, ListWidget, LineEdit, LargeTitleLabel
from fluent_styles import container_qss
from confirm_drawer import DeleteConfirmDrawer
from notify_drawer import NotifyDrawer

logger = logging.getLogger(__name__)


class ProfileInterface(QtWidgets.QWidget):
    """Profile management page for the Fluent sidebar navigation."""

    # Signal emitted when profile is switched
    profile_switched = Signal(str)  # profile_name

    def __init__(self, profile_manager, parent=None):
        """
        Initialize the profile management page.

        Args:
            profile_manager: ProfileManager instance
            parent: Parent widget, if any
        """
        super().__init__(parent)
        self.setObjectName("profileInterface")

        self.profile_manager = profile_manager
        self.setup_ui()
        self._delete_drawer = DeleteConfirmDrawer(parent=self)
        self._notify_drawer = NotifyDrawer(parent=self)
        self.refresh_profiles()

    def showEvent(self, event):
        """Refresh profile list and theme-aware styles whenever the page becomes visible."""
        super().showEvent(event)
        self.setStyleSheet(container_qss())
        self.refresh_profiles()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_delete_drawer'):
            self._delete_drawer.reposition(event.size())
        if hasattr(self, '_notify_drawer'):
            self._notify_drawer.reposition(event.size())

    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
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

        # Left side - profiles list
        left_layout = QtWidgets.QVBoxLayout()

        profiles_label = QtWidgets.QLabel("Available Profiles:")
        left_layout.addWidget(profiles_label)

        self.profiles_list = ListWidget()
        self.profiles_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.profiles_list.itemSelectionChanged.connect(self.on_profile_selection_changed)
        self.profiles_list.itemDoubleClicked.connect(self.switch_profile)
        left_layout.addWidget(self.profiles_list)

        content_layout.addLayout(left_layout, 2)

        # Right side - controls
        controls_layout = QtWidgets.QVBoxLayout()

        # Profile actions
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
        """Refresh the profiles list."""
        self.profiles_list.clear()

        profiles = self.profile_manager.get_available_profiles()
        current_profile_name = self.profile_manager.get_current_profile_name()

        for profile in profiles:
            item = QtWidgets.QListWidgetItem()

            # Create display text
            display_text = profile["display_name"]
            if profile["is_current"]:
                display_text += " (Current)"

            item.setText(display_text)
            item.setData(Qt.ItemDataRole.UserRole, profile)

            # Bold font for current profile
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
        """Handle profile selection change."""
        current_item = self.profiles_list.currentItem()

        if current_item:
            profile_data = current_item.data(Qt.ItemDataRole.UserRole)

            # Update profile info
            self.info_name.setText(profile_data["name"])
            self.info_display_name.setText(profile_data["display_name"])

            created_at = profile_data.get("created_at", "Unknown")
            if created_at and created_at != "Unknown":
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    created_at = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    pass
            self.info_created.setText(created_at)

            last_used = profile_data.get("last_used", "Never")
            if last_used and last_used != "Never":
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(last_used.replace('Z', '+00:00'))
                    last_used = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    pass
            self.info_last_used.setText(last_used)

            # Update button states
            is_current = profile_data["is_current"]
            is_default = profile_data["name"] == self.profile_manager.DEFAULT_PROFILE_NAME

            self.switch_button.setEnabled(not is_current)
            self.rename_button.setEnabled(True)
            self.delete_button.setEnabled(not is_default and not is_current)
        else:
            # Clear info
            self.info_name.setText("-")
            self.info_display_name.setText("-")
            self.info_created.setText("-")
            self.info_last_used.setText("-")

            # Disable buttons
            self.switch_button.setEnabled(False)
            self.rename_button.setEnabled(False)
            self.delete_button.setEnabled(False)

    def create_profile(self):
        """Show dialog to create a new profile."""
        dialog = CreateProfileDialog(self.profile_manager, self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.refresh_profiles()

    def switch_profile(self):
        """Switch to the selected profile."""
        current_item = self.profiles_list.currentItem()
        if not current_item:
            return

        profile_data = current_item.data(Qt.ItemDataRole.UserRole)
        profile_name = profile_data["name"]

        if profile_data["is_current"]:
            self._notify_drawer.info("Already Current",
                                     f"'{profile_data['display_name']}' is already the current profile.")
            return

        # Confirm switch
        reply = QtWidgets.QMessageBox.question(
            self, "Switch Profile",
            f"Switch to profile '{profile_data['display_name']}'?\n\n"
            "This will close the current session and reload with the new profile's settings.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.Yes
        )

        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            success = self.profile_manager.switch_to_profile(profile_name)
            if success:
                self.profile_switched.emit(profile_name)
                self._notify_drawer.success("Profile Switched",
                                            f"Successfully switched to '{profile_data['display_name']}'.")
                self.refresh_profiles()
            else:
                self._notify_drawer.error("Switch Failed",
                                          f"Failed to switch to profile '{profile_data['display_name']}'.")

    def rename_profile(self):
        """Show dialog to rename the selected profile."""
        current_item = self.profiles_list.currentItem()
        if not current_item:
            return

        profile_data = current_item.data(Qt.ItemDataRole.UserRole)

        dialog = RenameProfileDialog(profile_data, self.profile_manager, self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.refresh_profiles()

    def delete_profile(self):
        """Delete the selected profile after confirmation."""
        current_item = self.profiles_list.currentItem()
        if not current_item:
            return

        profile_data = current_item.data(Qt.ItemDataRole.UserRole)
        profile_name = profile_data["name"]

        if profile_name == self.profile_manager.DEFAULT_PROFILE_NAME:
            self._notify_drawer.warning("Cannot Delete",
                                        "The default profile cannot be deleted.")
            return

        if profile_data["is_current"]:
            self._notify_drawer.warning("Cannot Delete",
                                        "Cannot delete the currently active profile. "
                                        "Switch to another profile first.")
            return

        def _do_delete():
            success = self.profile_manager.delete_profile(profile_name)
            if success:
                self.refresh_profiles()
            else:
                self._notify_drawer.error("Delete Failed",
                                          f"Failed to delete profile '{profile_data['display_name']}'.")

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


class CreateProfileDialog(QtWidgets.QDialog):
    """Dialog for creating a new profile."""

    def __init__(self, profile_manager, parent=None):
        super(CreateProfileDialog, self).__init__(parent)
        self.profile_manager = profile_manager
        self.setup_ui()
        self._notify_drawer = NotifyDrawer(parent=self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_notify_drawer'):
            self._notify_drawer.reposition(event.size())

    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("Create New Profile")
        self.setModal(True)
        self.setFixedSize(400, 200)

        layout = QtWidgets.QVBoxLayout(self)

        # Header
        header = QtWidgets.QLabel("Create New Profile")
        layout.addWidget(header)

        # Form
        form_layout = QtWidgets.QFormLayout()

        self.name_input = LineEdit()
        self.name_input.setPlaceholderText("e.g., work, personal, staging")
        self.name_input.textChanged.connect(self.validate_input)
        form_layout.addRow("Profile Name:", self.name_input)

        self.display_name_input = LineEdit()
        self.display_name_input.setPlaceholderText("e.g., Work Account, Personal DNS")
        form_layout.addRow("Display Name:", self.display_name_input)

        layout.addLayout(form_layout)

        # Help text
        help_text = QtWidgets.QLabel(
            "Profile name is used internally and cannot contain spaces or special characters. "
            "Display name is shown in the interface."
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = PushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        self.ok_button = PrimaryPushButton("Create")
        self.ok_button.setEnabled(False)
        self.ok_button.clicked.connect(self.accept)
        btn_row.addWidget(self.ok_button)
        layout.addLayout(btn_row)

        self.name_input.setFocus()
        self.setStyleSheet(container_qss())

    def validate_input(self):
        """Validate the input and enable/disable OK button."""
        name = self.name_input.text().strip()

        # Check if name is valid (alphanumeric and underscores only)
        is_valid = bool(name and name.replace('_', '').replace('-', '').isalnum())

        # Check if name already exists
        if is_valid:
            existing_profiles = self.profile_manager.get_available_profiles()
            is_valid = name not in [p["name"] for p in existing_profiles]

        self.ok_button.setEnabled(is_valid)

    def accept(self):
        """Handle dialog acceptance."""
        name = self.name_input.text().strip()
        display_name = self.display_name_input.text().strip() or name

        if not name:
            self._notify_drawer.warning("Invalid Input", "Please enter a profile name.")
            return

        success = self.profile_manager.create_profile(name, display_name)
        if success:
            super(CreateProfileDialog, self).accept()
        else:
            self._notify_drawer.error("Creation Failed",
                                      f"Failed to create profile '{name}'. "
                                      "It may already exist or there was a file system error.")


class RenameProfileDialog(QtWidgets.QDialog):
    """Dialog for renaming a profile."""

    def __init__(self, profile_data, profile_manager, parent=None):
        super(RenameProfileDialog, self).__init__(parent)
        self.profile_data = profile_data
        self.profile_manager = profile_manager
        self.setup_ui()
        self._notify_drawer = NotifyDrawer(parent=self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_notify_drawer'):
            self._notify_drawer.reposition(event.size())

    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("Rename Profile")
        self.setModal(True)
        self.setFixedSize(400, 200)

        layout = QtWidgets.QVBoxLayout(self)

        # Header
        header = QtWidgets.QLabel(f"Rename Profile: {self.profile_data['display_name']}")
        layout.addWidget(header)

        # Form
        form_layout = QtWidgets.QFormLayout()

        # For default profile, only allow changing display name
        is_default = self.profile_data["name"] == self.profile_manager.DEFAULT_PROFILE_NAME

        if not is_default:
            self.name_input = LineEdit()
            self.name_input.setText(self.profile_data["name"])
            self.name_input.textChanged.connect(self.validate_input)
            form_layout.addRow("Profile Name:", self.name_input)
        else:
            # Show read-only name for default profile
            name_label = QtWidgets.QLabel(self.profile_data["name"])
            form_layout.addRow("Profile Name:", name_label)
            self.name_input = None

        self.display_name_input = LineEdit()
        self.display_name_input.setText(self.profile_data["display_name"])
        self.display_name_input.textChanged.connect(self.validate_input)
        form_layout.addRow("Display Name:", self.display_name_input)

        layout.addLayout(form_layout)

        if is_default:
            help_text = QtWidgets.QLabel(
                "The default profile's internal name cannot be changed, "
                "but you can update its display name."
            )
        else:
            help_text = QtWidgets.QLabel(
                "Profile name is used internally and cannot contain spaces or special characters."
            )

        help_text.setWordWrap(True)
        layout.addWidget(help_text)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = PushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        self.ok_button = PrimaryPushButton("Save")
        self.ok_button.clicked.connect(self.accept)
        btn_row.addWidget(self.ok_button)
        layout.addLayout(btn_row)

        # Focus on display name input
        self.display_name_input.setFocus()
        self.display_name_input.selectAll()

        # Initial validation
        self.validate_input()
        self.setStyleSheet(container_qss())

    def validate_input(self):
        """Validate the input and enable/disable OK button."""
        display_name = self.display_name_input.text().strip()

        if self.name_input:  # Not default profile
            name = self.name_input.text().strip()
            is_valid = bool(name and name.replace('_', '').replace('-', '').isalnum())

            # Check if name changed and already exists
            if is_valid and name != self.profile_data["name"]:
                existing_profiles = self.profile_manager.get_available_profiles()
                is_valid = name not in [p["name"] for p in existing_profiles]
        else:  # Default profile
            is_valid = True

        # Must have display name
        is_valid = is_valid and bool(display_name)

        self.ok_button.setEnabled(is_valid)

    def accept(self):
        """Handle dialog acceptance."""
        display_name = self.display_name_input.text().strip()

        if self.name_input:  # Not default profile
            new_name = self.name_input.text().strip()
        else:  # Default profile
            new_name = self.profile_data["name"]

        if not display_name:
            self._notify_drawer.warning("Invalid Input", "Please enter a display name.")
            return

        success = self.profile_manager.rename_profile(
            self.profile_data["name"],
            new_name,
            display_name
        )

        if success:
            super(RenameProfileDialog, self).accept()
        else:
            self._notify_drawer.error("Rename Failed",
                                      "Failed to rename profile. "
                                      "The new name may already exist or there was a file system error.")
