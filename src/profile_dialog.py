#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Profile management dialog for deSEC Qt DNS Manager.
Allows users to create, switch, rename, and delete profiles.
"""

import logging
from typing import Optional, Dict, List
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QMessageBox

logger = logging.getLogger(__name__)


class ProfileDialog(QtWidgets.QDialog):
    """Dialog for managing user profiles."""
    
    # Signal emitted when profile is switched
    profile_switched = pyqtSignal(str)  # profile_name
    
    def __init__(self, profile_manager, parent=None):
        """
        Initialize the profile management dialog.
        
        Args:
            profile_manager: ProfileManager instance
            parent: Parent widget, if any
        """
        super(ProfileDialog, self).__init__(parent)
        
        self.profile_manager = profile_manager
        self.setup_ui()
        self.refresh_profiles()
    
    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("Profile Management")
        self.setModal(True)
        self.setMinimumSize(500, 400)
        self.resize(600, 500)
        
        # Main layout
        layout = QtWidgets.QVBoxLayout(self)
        
        # Header
        header_label = QtWidgets.QLabel("Manage Profiles")
        header_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(header_label)
        
        # Description
        desc_label = QtWidgets.QLabel(
            "Each profile has isolated API tokens, cache, and settings. "
            "Use profiles to manage multiple deSEC accounts or environments."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: palette(placeholdertext); margin-bottom: 15px;")
        layout.addWidget(desc_label)
        
        # Profiles list and controls
        content_layout = QtWidgets.QHBoxLayout()
        
        # Left side - profiles list
        left_layout = QtWidgets.QVBoxLayout()
        
        profiles_label = QtWidgets.QLabel("Available Profiles:")
        profiles_label.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(profiles_label)
        
        self.profiles_list = QtWidgets.QListWidget()
        self.profiles_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.profiles_list.itemSelectionChanged.connect(self.on_profile_selection_changed)
        self.profiles_list.itemDoubleClicked.connect(self.switch_profile)
        left_layout.addWidget(self.profiles_list)
        
        content_layout.addLayout(left_layout, 2)
        
        # Right side - controls
        controls_layout = QtWidgets.QVBoxLayout()
        
        # Profile actions
        self.switch_button = QtWidgets.QPushButton("Switch To")
        self.switch_button.setToolTip("Switch to the selected profile")
        self.switch_button.clicked.connect(self.switch_profile)
        self.switch_button.setEnabled(False)
        controls_layout.addWidget(self.switch_button)
        
        controls_layout.addSpacing(10)
        
        self.create_button = QtWidgets.QPushButton("Create New...")
        self.create_button.setToolTip("Create a new profile")
        self.create_button.clicked.connect(self.create_profile)
        controls_layout.addWidget(self.create_button)
        
        self.rename_button = QtWidgets.QPushButton("Rename...")
        self.rename_button.setToolTip("Rename the selected profile")
        self.rename_button.clicked.connect(self.rename_profile)
        self.rename_button.setEnabled(False)
        controls_layout.addWidget(self.rename_button)
        
        self.delete_button = QtWidgets.QPushButton("Delete")
        self.delete_button.setToolTip("Delete the selected profile")
        self.delete_button.clicked.connect(self.delete_profile)
        self.delete_button.setEnabled(False)
        self.delete_button.setStyleSheet("QPushButton { color: #d32f2f; }")
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
        
        # Bottom buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        self.refresh_button = QtWidgets.QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_profiles)
        button_layout.addWidget(self.refresh_button)
        
        self.close_button = QtWidgets.QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        self.close_button.setDefault(True)
        button_layout.addWidget(self.close_button)
        
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
            
            # Style current profile differently
            if profile["is_current"]:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setBackground(QtGui.QColor(230, 247, 255))
            
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
            QMessageBox.information(self, "Already Current", 
                                  f"'{profile_data['display_name']}' is already the current profile.")
            return
        
        # Confirm switch
        reply = QMessageBox.question(
            self, "Switch Profile",
            f"Switch to profile '{profile_data['display_name']}'?\n\n"
            "This will close the current session and reload with the new profile's settings.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            success = self.profile_manager.switch_to_profile(profile_name)
            if success:
                self.profile_switched.emit(profile_name)
                QMessageBox.information(self, "Profile Switched", 
                                      f"Successfully switched to '{profile_data['display_name']}'.")
                self.accept()  # Close dialog
            else:
                QMessageBox.critical(self, "Switch Failed", 
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
            QMessageBox.warning(self, "Cannot Delete", 
                              "The default profile cannot be deleted.")
            return
        
        if profile_data["is_current"]:
            QMessageBox.warning(self, "Cannot Delete", 
                              "Cannot delete the currently active profile. "
                              "Switch to another profile first.")
            return
        
        # Confirm deletion
        reply = QMessageBox.question(
            self, "Delete Profile",
            f"Are you sure you want to delete profile '{profile_data['display_name']}'?\n\n"
            "This will permanently delete all associated data including:\n"
            "• API tokens and settings\n"
            "• Cached zones and records\n"
            "• All profile-specific configuration\n\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            success = self.profile_manager.delete_profile(profile_name)
            if success:
                QMessageBox.information(self, "Profile Deleted", 
                                      f"Profile '{profile_data['display_name']}' has been deleted.")
                self.refresh_profiles()
            else:
                QMessageBox.critical(self, "Delete Failed", 
                                   f"Failed to delete profile '{profile_data['display_name']}'.")


class CreateProfileDialog(QtWidgets.QDialog):
    """Dialog for creating a new profile."""
    
    def __init__(self, profile_manager, parent=None):
        super(CreateProfileDialog, self).__init__(parent)
        self.profile_manager = profile_manager
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("Create New Profile")
        self.setModal(True)
        self.setFixedSize(400, 200)
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # Header
        header = QtWidgets.QLabel("Create New Profile")
        header.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(header)
        
        # Form
        form_layout = QtWidgets.QFormLayout()
        
        self.name_input = QtWidgets.QLineEdit()
        self.name_input.setPlaceholderText("e.g., work, personal, staging")
        self.name_input.textChanged.connect(self.validate_input)
        form_layout.addRow("Profile Name:", self.name_input)
        
        self.display_name_input = QtWidgets.QLineEdit()
        self.display_name_input.setPlaceholderText("e.g., Work Account, Personal DNS")
        form_layout.addRow("Display Name:", self.display_name_input)
        
        layout.addLayout(form_layout)
        
        # Help text
        help_text = QtWidgets.QLabel(
            "Profile name is used internally and cannot contain spaces or special characters. "
            "Display name is shown in the interface."
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #666; font-size: 11px; margin: 10px 0;")
        layout.addWidget(help_text)
        
        # Buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | 
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.ok_button = button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setEnabled(False)
        
        # Focus on name input
        self.name_input.setFocus()
    
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
            QMessageBox.warning(self, "Invalid Input", "Please enter a profile name.")
            return
        
        success = self.profile_manager.create_profile(name, display_name)
        if success:
            super(CreateProfileDialog, self).accept()
        else:
            QMessageBox.critical(self, "Creation Failed", 
                               f"Failed to create profile '{name}'. "
                               "It may already exist or there was a file system error.")


class RenameProfileDialog(QtWidgets.QDialog):
    """Dialog for renaming a profile."""
    
    def __init__(self, profile_data, profile_manager, parent=None):
        super(RenameProfileDialog, self).__init__(parent)
        self.profile_data = profile_data
        self.profile_manager = profile_manager
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("Rename Profile")
        self.setModal(True)
        self.setFixedSize(400, 200)
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # Header
        header = QtWidgets.QLabel(f"Rename Profile: {self.profile_data['display_name']}")
        header.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(header)
        
        # Form
        form_layout = QtWidgets.QFormLayout()
        
        # For default profile, only allow changing display name
        is_default = self.profile_data["name"] == self.profile_manager.DEFAULT_PROFILE_NAME
        
        if not is_default:
            self.name_input = QtWidgets.QLineEdit()
            self.name_input.setText(self.profile_data["name"])
            self.name_input.textChanged.connect(self.validate_input)
            form_layout.addRow("Profile Name:", self.name_input)
        else:
            # Show read-only name for default profile
            name_label = QtWidgets.QLabel(self.profile_data["name"])
            name_label.setStyleSheet("color: #666;")
            form_layout.addRow("Profile Name:", name_label)
            self.name_input = None
        
        self.display_name_input = QtWidgets.QLineEdit()
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
        help_text.setStyleSheet("color: #666; font-size: 11px; margin: 10px 0;")
        layout.addWidget(help_text)
        
        # Buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | 
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.ok_button = button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        
        # Focus on display name input
        self.display_name_input.setFocus()
        self.display_name_input.selectAll()
        
        # Initial validation
        self.validate_input()
    
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
            QMessageBox.warning(self, "Invalid Input", "Please enter a display name.")
            return
        
        success = self.profile_manager.rename_profile(
            self.profile_data["name"], 
            new_name, 
            display_name
        )
        
        if success:
            super(RenameProfileDialog, self).accept()
        else:
            QMessageBox.critical(self, "Rename Failed", 
                               f"Failed to rename profile. "
                               "The new name may already exist or there was a file system error.")
