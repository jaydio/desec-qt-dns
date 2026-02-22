#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Token management dialog for deSEC Qt DNS Manager.
Provides UI for creating, viewing, editing, and deleting API tokens,
as well as managing per-token RRset policies.
"""

import logging
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt, QThreadPool, QRunnable, QObject, pyqtSignal
from PyQt6.QtWidgets import QMessageBox

logger = logging.getLogger(__name__)

# All DNS record types (matches record_widget.py)
DNS_RECORD_TYPES = [
    'A', 'AAAA', 'AFSDB', 'APL', 'CAA', 'CDNSKEY', 'CDS', 'CERT', 'CNAME',
    'DHCID', 'DNAME', 'DNSKEY', 'DLV', 'DS', 'EUI48', 'EUI64', 'HINFO',
    'HTTPS', 'KX', 'L32', 'L64', 'LOC', 'LP', 'MX', 'NAPTR', 'NID', 'NS',
    'OPENPGPKEY', 'PTR', 'RP', 'SMIMEA', 'SPF', 'SRV', 'SSHFP', 'SVCB',
    'TLSA', 'TXT', 'URI',
]


# ---------------------------------------------------------------------------
# Background worker helpers
# ---------------------------------------------------------------------------

class _WorkerSignals(QObject):
    done = pyqtSignal(bool, object)   # success, data


class _Worker(QRunnable):
    """Generic background worker that calls a callable and emits done signal."""

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = _WorkerSignals()

    def run(self):
        try:
            success, data = self.fn(*self.args, **self.kwargs)
            self.signals.done.emit(success, data)
        except Exception as e:
            logger.error(f"Worker error: {e}")
            self.signals.done.emit(False, str(e))


# ---------------------------------------------------------------------------
# TokenSecretDialog — one-time secret display after token creation
# ---------------------------------------------------------------------------

class TokenSecretDialog(QtWidgets.QDialog):
    """
    Shown immediately after a token is created.
    Displays the secret value exactly once and requires acknowledgement
    before the dialog can be closed.
    """

    def __init__(self, token_value, parent=None):
        super().__init__(parent)
        self.token_value = token_value
        self.setWindowTitle("Token Created — Save Your Token")
        self.setModal(True)
        self.setMinimumWidth(580)
        self.setMinimumHeight(260)
        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)

        # Header
        header = QtWidgets.QLabel("Token Created Successfully")
        header.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(header)

        # Warning
        warning = QtWidgets.QLabel(
            "This is the only time the token value will be shown. "
            "Store it securely before closing this dialog."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #c62828; font-weight: bold;")
        layout.addWidget(warning)

        # Token value row
        token_row = QtWidgets.QHBoxLayout()
        self._token_field = QtWidgets.QLineEdit(self.token_value)
        self._token_field.setReadOnly(True)
        self._token_field.setFont(QtGui.QFont("Monospace", 10))
        self._token_field.setMinimumWidth(380)
        token_row.addWidget(self._token_field)

        self._copy_btn = QtWidgets.QPushButton("Copy to Clipboard")
        self._copy_btn.clicked.connect(self._copy_token)
        token_row.addWidget(self._copy_btn)
        layout.addLayout(token_row)

        # Acknowledgement checkbox
        self._ack_checkbox = QtWidgets.QCheckBox(
            "I have securely stored my token value"
        )
        self._ack_checkbox.stateChanged.connect(self._on_ack_changed)
        layout.addWidget(self._ack_checkbox)

        # Close button (disabled until checkbox is checked)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        self._close_btn = QtWidgets.QPushButton("Close")
        self._close_btn.setEnabled(False)
        self._close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._close_btn)
        layout.addLayout(btn_row)

    def _copy_token(self):
        QtWidgets.QApplication.clipboard().setText(self.token_value)
        self._copy_btn.setText("Copied!")

    def _on_ack_changed(self):
        self._close_btn.setEnabled(self._ack_checkbox.isChecked())


# ---------------------------------------------------------------------------
# TokenPolicyDialog — add / edit an RRset policy
# ---------------------------------------------------------------------------

class TokenPolicyDialog(QtWidgets.QDialog):
    """Dialog for creating or editing a single RRset policy on a token."""

    def __init__(self, api_client, token_id, policy=None, parent=None):
        """
        Args:
            api_client: APIClient instance
            token_id (str): Token UUID this policy belongs to
            policy (dict or None): Existing policy dict for editing; None = create new
        """
        super().__init__(parent)
        self.api_client = api_client
        self.token_id = token_id
        self.policy = policy  # None → create mode
        self.setWindowTitle("Edit Policy" if policy else "Add Policy")
        self.setModal(True)
        self.setMinimumSize(480, 300)
        self._setup_ui()
        if policy:
            self._populate(policy)

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)

        desc = QtWidgets.QLabel(
            "Define a fine-grained access rule for this token. "
            "Leave fields blank to create a default (catch-all) policy."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #555;")
        layout.addWidget(desc)

        form = QtWidgets.QFormLayout()
        form.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.DontWrapRows)

        self._domain_edit = QtWidgets.QLineEdit()
        self._domain_edit.setPlaceholderText("e.g. example.com  (blank = default policy)")
        form.addRow("Domain:", self._domain_edit)

        self._subname_edit = QtWidgets.QLineEdit()
        self._subname_edit.setPlaceholderText("e.g. www  (blank = match all subnames)")
        form.addRow("Subname:", self._subname_edit)

        self._type_combo = QtWidgets.QComboBox()
        self._type_combo.addItem("(Any / null — match all types)")
        for t in DNS_RECORD_TYPES:
            self._type_combo.addItem(t)
        form.addRow("Type:", self._type_combo)

        self._perm_write_check = QtWidgets.QCheckBox("Allow write (create/update/delete records)")
        form.addRow("Write:", self._perm_write_check)

        layout.addLayout(form)
        layout.addStretch()

        # Buttons
        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._save)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _populate(self, policy):
        self._domain_edit.setText(policy.get('domain') or '')
        self._subname_edit.setText(policy.get('subname') or '')
        type_val = policy.get('type')
        if type_val and type_val in DNS_RECORD_TYPES:
            idx = self._type_combo.findText(type_val)
            if idx >= 0:
                self._type_combo.setCurrentIndex(idx)
        self._perm_write_check.setChecked(bool(policy.get('perm_write', False)))

    def _save(self):
        domain = self._domain_edit.text().strip() or None
        subname = self._subname_edit.text().strip() or None
        type_text = self._type_combo.currentText()
        type_ = None if type_text.startswith('(') else type_text
        perm_write = self._perm_write_check.isChecked()

        if self.policy:
            # Edit existing
            success, result = self.api_client.update_token_policy(
                self.token_id, self.policy['id'],
                domain=domain, subname=subname, type=type_, perm_write=perm_write
            )
        else:
            # Create new
            success, result = self.api_client.create_token_policy(
                self.token_id, domain=domain, subname=subname,
                type_=type_, perm_write=perm_write
            )

        if success:
            self.accept()
        else:
            msg = result.get('message', str(result)) if isinstance(result, dict) else str(result)
            QMessageBox.critical(self, "Error", f"Failed to save policy:\n{msg}")


# ---------------------------------------------------------------------------
# CreateTokenDialog — form for creating a new token
# ---------------------------------------------------------------------------

class CreateTokenDialog(QtWidgets.QDialog):
    """Dialog for creating a new API token."""

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.created_token_value = None  # set on success
        self.setWindowTitle("Create New Token")
        self.setModal(True)
        self.setMinimumSize(600, 460)
        self.resize(600, 750)
        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)

        desc = QtWidgets.QLabel(
            "Create a new API token. After creation, the token value will be "
            "shown once — make sure to copy it before closing."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #555;")
        layout.addWidget(desc)

        # --- Basic settings ---
        basic_group = QtWidgets.QGroupBox("Token Settings")
        basic_form = QtWidgets.QFormLayout(basic_group)

        self._name_edit = QtWidgets.QLineEdit()
        self._name_edit.setPlaceholderText("e.g. My App Token")
        basic_form.addRow("Name:", self._name_edit)

        self._perm_create = QtWidgets.QCheckBox("perm_create_domain — allow creating domains")
        self._perm_create.setChecked(False)
        basic_form.addRow("", self._perm_create)

        self._perm_delete = QtWidgets.QCheckBox("perm_delete_domain — allow deleting domains")
        self._perm_delete.setChecked(False)
        basic_form.addRow("", self._perm_delete)

        self._perm_manage = QtWidgets.QCheckBox("perm_manage_tokens — allow managing tokens")
        self._perm_manage.setChecked(False)
        basic_form.addRow("", self._perm_manage)

        self._auto_policy = QtWidgets.QCheckBox(
            "auto_policy — auto-create permissive RRset policy on domain creation"
        )
        self._auto_policy.setChecked(False)
        basic_form.addRow("", self._auto_policy)

        layout.addWidget(basic_group)

        # --- Expiration ---
        exp_group = QtWidgets.QGroupBox("Expiration (optional)")
        exp_form = QtWidgets.QFormLayout(exp_group)

        self._max_age_edit = QtWidgets.QLineEdit()
        self._max_age_edit.setPlaceholderText("e.g. 30 00:00:00 (30 days)   blank = no limit")
        exp_form.addRow("Max Age:", self._max_age_edit)

        self._max_unused_edit = QtWidgets.QLineEdit()
        self._max_unused_edit.setPlaceholderText("e.g. 7 00:00:00 (7 days)    blank = no limit")
        exp_form.addRow("Max Unused Period:", self._max_unused_edit)

        layout.addWidget(exp_group)

        # --- Allowed subnets ---
        subnet_group = QtWidgets.QGroupBox("Allowed Subnets (one CIDR per line)")
        subnet_layout = QtWidgets.QVBoxLayout(subnet_group)
        self._subnets_edit = QtWidgets.QPlainTextEdit()
        self._subnets_edit.setPlainText("0.0.0.0/0\n::/0")
        self._subnets_edit.setFixedHeight(72)
        subnet_layout.addWidget(self._subnets_edit)
        layout.addWidget(subnet_group)

        layout.addStretch()

        # Buttons
        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self._create_btn = QtWidgets.QPushButton("Create Token")
        self._create_btn.setDefault(True)
        btn_box.addButton(self._create_btn, QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole)
        self._create_btn.clicked.connect(self._create)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _create(self):
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Please enter a name for the token.")
            return

        max_age = self._max_age_edit.text().strip() or None
        max_unused = self._max_unused_edit.text().strip() or None
        subnet_lines = [
            s.strip() for s in self._subnets_edit.toPlainText().splitlines() if s.strip()
        ]
        allowed_subnets = subnet_lines if subnet_lines else None

        self._create_btn.setEnabled(False)
        self._create_btn.setText("Creating…")

        success, result = self.api_client.create_token(
            name=name,
            perm_create_domain=self._perm_create.isChecked(),
            perm_delete_domain=self._perm_delete.isChecked(),
            perm_manage_tokens=self._perm_manage.isChecked(),
            max_age=max_age,
            max_unused_period=max_unused,
            allowed_subnets=allowed_subnets,
            auto_policy=self._auto_policy.isChecked(),
        )

        self._create_btn.setEnabled(True)
        self._create_btn.setText("Create Token")

        if success:
            token_id = result.get('id', '')
            token_value = result.get('token', '')
            self.created_token_value = token_value

            # Create a default (catch-all) policy with no write access.
            # The API requires the first policy to be the default, and this
            # provides a secure baseline — no access unless explicitly granted.
            if token_id:
                pol_success, pol_result = self.api_client.create_token_policy(
                    token_id,
                    domain=None, subname=None, type_=None, perm_write=False,
                )
                if not pol_success:
                    pol_msg = (
                        pol_result.get('message', str(pol_result))
                        if isinstance(pol_result, dict) else str(pol_result)
                    )
                    logger.warning(f"Default policy creation failed: {pol_msg}")

            # Show secret dialog — must be closed before returning Accepted
            secret_dlg = TokenSecretDialog(token_value, self)
            secret_dlg.exec()
            self.accept()
        else:
            msg = result.get('message', str(result)) if isinstance(result, dict) else str(result)
            QMessageBox.critical(self, "Create Failed", f"Failed to create token:\n{msg}")


# ---------------------------------------------------------------------------
# TokenManagerDialog — main token management window
# ---------------------------------------------------------------------------

class TokenManagerDialog(QtWidgets.QDialog):
    """
    Main dialog for managing deSEC API tokens.

    Left panel: table listing all tokens.
    Right panel: tab widget with Details and Policies tabs.
    """

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self._current_token_id = None   # token currently shown in detail panel
        self._policies = []             # policies for current token
        self.setWindowTitle("Token Manager")
        self.setModal(True)
        self.setMinimumSize(960, 640)
        self.resize(1280, 820)
        self._setup_ui()
        self._load_tokens()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setSpacing(8)

        # Header
        header = QtWidgets.QLabel("API Token Manager")
        header.setStyleSheet("font-size: 15px; font-weight: bold;")
        outer.addWidget(header)

        # Main splitter
        splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(6)
        outer.addWidget(splitter, 1)

        # ---- Left panel ----
        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 4, 0)

        left_label = QtWidgets.QLabel("Tokens")
        left_label.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(left_label)

        self._token_table = QtWidgets.QTableWidget()
        self._token_table.setColumnCount(5)
        self._token_table.setHorizontalHeaderLabels(
            ["Name", "Created", "Last Used", "Valid", "Perms"]
        )
        self._token_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._token_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self._token_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._token_table.verticalHeader().setVisible(False)
        self._token_table.horizontalHeader().setStretchLastSection(False)
        self._token_table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        for col in (1, 2, 3, 4):
            self._token_table.horizontalHeader().setSectionResizeMode(
                col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
            )
        self._token_table.selectionModel().selectionChanged.connect(
            self._on_token_selection_changed
        )
        left_layout.addWidget(self._token_table)

        # Buttons below token table
        tbl_btn_row = QtWidgets.QHBoxLayout()
        self._new_btn = QtWidgets.QPushButton("New Token")
        self._new_btn.clicked.connect(self._new_token)
        tbl_btn_row.addWidget(self._new_btn)

        self._delete_btn = QtWidgets.QPushButton("Delete")
        self._delete_btn.setEnabled(False)
        self._delete_btn.setStyleSheet("QPushButton { color: #c62828; }")
        self._delete_btn.clicked.connect(self._delete_token)
        tbl_btn_row.addWidget(self._delete_btn)

        self._refresh_btn = QtWidgets.QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self._load_tokens)
        tbl_btn_row.addWidget(self._refresh_btn)

        left_layout.addLayout(tbl_btn_row)
        splitter.addWidget(left_widget)

        # ---- Right panel ----
        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        right_layout.setContentsMargins(4, 0, 0, 0)

        self._tab_widget = QtWidgets.QTabWidget()
        right_layout.addWidget(self._tab_widget)

        self._tab_widget.addTab(self._build_details_tab(), "Details")
        self._tab_widget.addTab(self._build_policies_tab(), "RRset Policies")

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([500, 500])

        # Bottom close button
        bottom_row = QtWidgets.QHBoxLayout()
        bottom_row.addStretch()
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        bottom_row.addWidget(close_btn)
        outer.addLayout(bottom_row)

        # Initially show placeholder in both tabs
        self._set_detail_enabled(False)
        self._set_policies_enabled(False)

    def _build_details_tab(self):
        """Build and return the Details tab widget."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setSpacing(10)

        self._detail_placeholder = QtWidgets.QLabel(
            "Select a token to view and edit details."
        )
        self._detail_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._detail_placeholder.setStyleSheet("color: palette(placeholdertext);")
        layout.addWidget(self._detail_placeholder)

        # --- Read-only info ---
        self._info_group = QtWidgets.QGroupBox("Token Info")
        info_form = QtWidgets.QFormLayout(self._info_group)

        id_row = QtWidgets.QHBoxLayout()
        self._info_id = QtWidgets.QLineEdit()
        self._info_id.setReadOnly(True)
        self._info_id.setStyleSheet("background: transparent; border: none;")
        id_row.addWidget(self._info_id)
        copy_id_btn = QtWidgets.QPushButton("Copy")
        copy_id_btn.setFixedWidth(54)
        copy_id_btn.clicked.connect(lambda: (
            QtWidgets.QApplication.clipboard().setText(self._info_id.text()),
            copy_id_btn.setText("✓")
        ))
        id_row.addWidget(copy_id_btn)
        info_form.addRow("ID:", id_row)

        self._info_owner = QtWidgets.QLabel()
        info_form.addRow("Owner:", self._info_owner)

        self._info_created = QtWidgets.QLabel()
        info_form.addRow("Created:", self._info_created)

        self._info_last_used = QtWidgets.QLabel()
        info_form.addRow("Last Used:", self._info_last_used)

        self._info_valid = QtWidgets.QLabel()
        info_form.addRow("Valid:", self._info_valid)

        self._info_mfa = QtWidgets.QLabel()
        info_form.addRow("MFA:", self._info_mfa)

        layout.addWidget(self._info_group)

        # --- Editable settings ---
        self._settings_group = QtWidgets.QGroupBox("Settings")
        settings_form = QtWidgets.QFormLayout(self._settings_group)

        self._edit_name = QtWidgets.QLineEdit()
        self._edit_name.setPlaceholderText("Token name")
        settings_form.addRow("Name:", self._edit_name)

        self._edit_perm_create = QtWidgets.QCheckBox("perm_create_domain")
        settings_form.addRow("", self._edit_perm_create)

        self._edit_perm_delete = QtWidgets.QCheckBox("perm_delete_domain")
        settings_form.addRow("", self._edit_perm_delete)

        self._edit_perm_manage = QtWidgets.QCheckBox("perm_manage_tokens")
        settings_form.addRow("", self._edit_perm_manage)

        self._edit_auto_policy = QtWidgets.QCheckBox("auto_policy")
        self._edit_auto_policy.setToolTip(
            "When enabled, automatically creates a permissive RRset policy\n"
            "for each domain created with this token."
        )
        settings_form.addRow("", self._edit_auto_policy)

        self._edit_max_age = QtWidgets.QLineEdit()
        self._edit_max_age.setPlaceholderText(
            "e.g. 30 00:00:00 (30 days)   blank = no limit"
        )
        settings_form.addRow("Max Age:", self._edit_max_age)

        self._edit_max_unused = QtWidgets.QLineEdit()
        self._edit_max_unused.setPlaceholderText(
            "e.g. 7 00:00:00 (7 days)    blank = no limit"
        )
        settings_form.addRow("Max Unused Period:", self._edit_max_unused)

        self._edit_subnets = QtWidgets.QPlainTextEdit()
        self._edit_subnets.setFixedHeight(72)
        self._edit_subnets.setPlaceholderText("One CIDR per line, e.g. 0.0.0.0/0")
        settings_form.addRow("Allowed Subnets:", self._edit_subnets)

        layout.addWidget(self._settings_group)

        # Save button
        save_row = QtWidgets.QHBoxLayout()
        save_row.addStretch()
        self._save_btn = QtWidgets.QPushButton("Save Changes")
        self._save_btn.clicked.connect(self._save_token)
        save_row.addWidget(self._save_btn)
        layout.addLayout(save_row)

        layout.addStretch()
        return widget

    def _build_policies_tab(self):
        """Build and return the RRset Policies tab widget."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setSpacing(8)

        self._policy_placeholder = QtWidgets.QLabel(
            "Select a token to view and manage its RRset policies."
        )
        self._policy_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._policy_placeholder.setStyleSheet("color: palette(placeholdertext);")
        layout.addWidget(self._policy_placeholder)

        desc = QtWidgets.QLabel(
            "RRset policies define fine-grained write access per domain, subname, "
            "and record type. Policies with all-null fields act as a default catch-all."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: palette(placeholdertext); font-size: 11px;")
        layout.addWidget(desc)

        self._policy_table = QtWidgets.QTableWidget()
        self._policy_table.setColumnCount(4)
        self._policy_table.setHorizontalHeaderLabels(
            ["Domain", "Subname", "Type", "Write"]
        )
        self._policy_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._policy_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self._policy_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._policy_table.verticalHeader().setVisible(False)
        self._policy_table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        for col in (1, 2, 3):
            self._policy_table.horizontalHeader().setSectionResizeMode(
                col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
            )
        self._policy_table.selectionModel().selectionChanged.connect(
            self._on_policy_selection_changed
        )
        layout.addWidget(self._policy_table)

        # Policy buttons
        pol_btn_row = QtWidgets.QHBoxLayout()
        self._add_policy_btn = QtWidgets.QPushButton("Add Policy")
        self._add_policy_btn.clicked.connect(self._add_policy)
        pol_btn_row.addWidget(self._add_policy_btn)

        self._edit_policy_btn = QtWidgets.QPushButton("Edit Policy")
        self._edit_policy_btn.setEnabled(False)
        self._edit_policy_btn.clicked.connect(self._edit_policy)
        pol_btn_row.addWidget(self._edit_policy_btn)

        self._delete_policy_btn = QtWidgets.QPushButton("Delete Policy")
        self._delete_policy_btn.setEnabled(False)
        self._delete_policy_btn.setStyleSheet("QPushButton { color: #c62828; }")
        self._delete_policy_btn.clicked.connect(self._delete_policy)
        pol_btn_row.addWidget(self._delete_policy_btn)

        pol_btn_row.addStretch()
        layout.addLayout(pol_btn_row)
        return widget

    # ------------------------------------------------------------------
    # Enable / disable panels
    # ------------------------------------------------------------------

    def _set_detail_enabled(self, enabled):
        self._detail_placeholder.setVisible(not enabled)
        self._info_group.setVisible(enabled)
        self._settings_group.setVisible(enabled)
        self._save_btn.setVisible(enabled)

    def _set_policies_enabled(self, enabled):
        self._policy_placeholder.setVisible(not enabled)
        self._policy_table.setVisible(enabled)
        self._add_policy_btn.setEnabled(enabled)
        self._edit_policy_btn.setEnabled(False)
        self._delete_policy_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # Token table loading
    # ------------------------------------------------------------------

    def _load_tokens(self):
        self._token_table.setRowCount(0)
        self._token_table.setEnabled(False)
        self._refresh_btn.setEnabled(False)
        self._new_btn.setEnabled(False)

        worker = _Worker(self.api_client.list_tokens)
        worker.signals.done.connect(self._on_tokens_loaded)
        QThreadPool.globalInstance().start(worker)

    def _on_tokens_loaded(self, success, data):
        self._token_table.setEnabled(True)
        self._refresh_btn.setEnabled(True)
        self._new_btn.setEnabled(True)

        if not success:
            msg = data.get('message', str(data)) if isinstance(data, dict) else str(data)
            QMessageBox.warning(self, "Load Failed", f"Could not load tokens:\n{msg}")
            return

        tokens = data if isinstance(data, list) else []
        self._token_table.setRowCount(0)

        for token in tokens:
            row = self._token_table.rowCount()
            self._token_table.insertRow(row)

            name_item = QtWidgets.QTableWidgetItem(token.get('name', ''))
            name_item.setData(Qt.ItemDataRole.UserRole, token)
            self._token_table.setItem(row, 0, name_item)

            created = _format_ts(token.get('created'))
            self._token_table.setItem(row, 1, QtWidgets.QTableWidgetItem(created))

            last_used = _format_ts(token.get('last_used')) or 'Never'
            self._token_table.setItem(row, 2, QtWidgets.QTableWidgetItem(last_used))

            is_valid = token.get('is_valid', True)
            valid_item = QtWidgets.QTableWidgetItem('Yes' if is_valid else 'No')
            valid_item.setForeground(
                QtGui.QColor('#2e7d32') if is_valid else QtGui.QColor('#c62828')
            )
            self._token_table.setItem(row, 3, valid_item)

            perms = _perm_flags(token)
            perm_item = QtWidgets.QTableWidgetItem(perms)
            perm_item.setToolTip(
                "C = perm_create_domain\n"
                "D = perm_delete_domain\n"
                "M = perm_manage_tokens"
            )
            self._token_table.setItem(row, 4, perm_item)

    # ------------------------------------------------------------------
    # Token table selection
    # ------------------------------------------------------------------

    def _on_token_selection_changed(self):
        rows = self._token_table.selectedItems()
        if not rows:
            self._current_token_id = None
            self._delete_btn.setEnabled(False)
            self._set_detail_enabled(False)
            self._set_policies_enabled(False)
            return

        token = self._token_table.item(
            self._token_table.currentRow(), 0
        ).data(Qt.ItemDataRole.UserRole)

        self._current_token_id = token.get('id')
        self._delete_btn.setEnabled(True)
        self._set_detail_enabled(True)
        self._populate_details(token)
        self._set_policies_enabled(True)
        self._load_policies(self._current_token_id)

    # ------------------------------------------------------------------
    # Details tab — populate / save
    # ------------------------------------------------------------------

    def _populate_details(self, token):
        self._info_id.setText(token.get('id', ''))
        self._info_owner.setText(token.get('owner', ''))
        self._info_created.setText(_format_ts(token.get('created')) or '—')
        self._info_last_used.setText(_format_ts(token.get('last_used')) or 'Never')

        is_valid = token.get('is_valid', True)
        self._info_valid.setText('Yes' if is_valid else 'No')
        self._info_valid.setStyleSheet(
            f"color: {'#2e7d32' if is_valid else '#c62828'};"
        )

        mfa = token.get('mfa')
        self._info_mfa.setText(
            'N/A (API token)' if mfa is None else ('Yes' if mfa else 'No')
        )

        self._edit_name.setText(token.get('name', ''))
        self._edit_perm_create.setChecked(bool(token.get('perm_create_domain', False)))
        self._edit_perm_delete.setChecked(bool(token.get('perm_delete_domain', False)))
        self._edit_perm_manage.setChecked(bool(token.get('perm_manage_tokens', False)))
        self._edit_auto_policy.setChecked(bool(token.get('auto_policy', False)))
        self._edit_max_age.setText(token.get('max_age') or '')
        self._edit_max_unused.setText(token.get('max_unused_period') or '')

        subnets = token.get('allowed_subnets') or []
        self._edit_subnets.setPlainText('\n'.join(subnets))

    def _save_token(self):
        if not self._current_token_id:
            return

        name = self._edit_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Token name cannot be empty.")
            return

        max_age = self._edit_max_age.text().strip() or None
        max_unused = self._edit_max_unused.text().strip() or None
        subnet_lines = [
            s.strip()
            for s in self._edit_subnets.toPlainText().splitlines()
            if s.strip()
        ]
        allowed_subnets = subnet_lines if subnet_lines else None

        self._save_btn.setEnabled(False)
        self._save_btn.setText("Saving…")

        success, result = self.api_client.update_token(
            self._current_token_id,
            name=name,
            perm_create_domain=self._edit_perm_create.isChecked(),
            perm_delete_domain=self._edit_perm_delete.isChecked(),
            perm_manage_tokens=self._edit_perm_manage.isChecked(),
            auto_policy=self._edit_auto_policy.isChecked(),
            max_age=max_age,
            max_unused_period=max_unused,
            allowed_subnets=allowed_subnets,
        )

        self._save_btn.setEnabled(True)
        self._save_btn.setText("Save Changes")

        if success:
            # Update the stored token data in the table row
            row = self._token_table.currentRow()
            if row >= 0:
                name_item = self._token_table.item(row, 0)
                if name_item:
                    name_item.setText(result.get('name', name))
                    name_item.setData(Qt.ItemDataRole.UserRole, result)
                    perm_item = self._token_table.item(row, 4)
                    if perm_item:
                        perm_item.setText(_perm_flags(result))
        else:
            msg = result.get('message', str(result)) if isinstance(result, dict) else str(result)
            QMessageBox.critical(self, "Save Failed", f"Failed to save token:\n{msg}")

    # ------------------------------------------------------------------
    # New / Delete token
    # ------------------------------------------------------------------

    def _new_token(self):
        dlg = CreateTokenDialog(self.api_client, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._load_tokens()

    def _delete_token(self):
        if not self._current_token_id:
            return

        row = self._token_table.currentRow()
        name_item = self._token_table.item(row, 0)
        token_name = name_item.text() if name_item else self._current_token_id

        confirm = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete token '{token_name}'?\n\n"
            "Warning: if this is the token you are currently using, "
            "the application will lose API access and you will need to "
            "re-authenticate.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        success, result = self.api_client.delete_token(self._current_token_id)
        if success:
            self._load_tokens()
            self._current_token_id = None
            self._set_detail_enabled(False)
            self._set_policies_enabled(False)
        else:
            msg = result.get('message', str(result)) if isinstance(result, dict) else str(result)
            QMessageBox.critical(self, "Delete Failed", f"Failed to delete token:\n{msg}")

    # ------------------------------------------------------------------
    # Policies tab loading
    # ------------------------------------------------------------------

    def _load_policies(self, token_id):
        self._policy_table.setRowCount(0)
        self._policies = []

        worker = _Worker(self.api_client.list_token_policies, token_id)
        worker.signals.done.connect(self._on_policies_loaded)
        QThreadPool.globalInstance().start(worker)

    def _on_policies_loaded(self, success, data):
        if not success:
            return

        self._policies = data if isinstance(data, list) else []
        self._policy_table.setRowCount(0)

        for policy in self._policies:
            row = self._policy_table.rowCount()
            self._policy_table.insertRow(row)

            domain_item = QtWidgets.QTableWidgetItem(
                policy.get('domain') or '(default)'
            )
            if not policy.get('domain'):
                _italicize(domain_item)
            self._policy_table.setItem(row, 0, domain_item)

            sub = policy.get('subname')
            sub_item = QtWidgets.QTableWidgetItem(sub if sub is not None else '(default)')
            if sub is None:
                _italicize(sub_item)
            self._policy_table.setItem(row, 1, sub_item)

            type_val = policy.get('type')
            type_item = QtWidgets.QTableWidgetItem(type_val or '(default)')
            if not type_val:
                _italicize(type_item)
            self._policy_table.setItem(row, 2, type_item)

            write_item = QtWidgets.QTableWidgetItem(
                'Yes' if policy.get('perm_write') else 'No'
            )
            if policy.get('perm_write'):
                write_item.setForeground(QtGui.QColor('#2e7d32'))
            self._policy_table.setItem(row, 3, write_item)

    # ------------------------------------------------------------------
    # Policy table selection
    # ------------------------------------------------------------------

    def _on_policy_selection_changed(self):
        has_sel = bool(self._policy_table.selectedItems())
        self._edit_policy_btn.setEnabled(has_sel)
        self._delete_policy_btn.setEnabled(has_sel)

    def _get_selected_policy(self):
        row = self._policy_table.currentRow()
        if row < 0 or row >= len(self._policies):
            return None
        return self._policies[row]

    # ------------------------------------------------------------------
    # Policy CRUD
    # ------------------------------------------------------------------

    def _add_policy(self):
        if not self._current_token_id:
            return
        dlg = TokenPolicyDialog(self.api_client, self._current_token_id, parent=self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._load_policies(self._current_token_id)

    def _edit_policy(self):
        policy = self._get_selected_policy()
        if not policy or not self._current_token_id:
            return
        dlg = TokenPolicyDialog(
            self.api_client, self._current_token_id, policy=policy, parent=self
        )
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._load_policies(self._current_token_id)

    def _delete_policy(self):
        policy = self._get_selected_policy()
        if not policy or not self._current_token_id:
            return

        confirm = QMessageBox.question(
            self, "Confirm Delete",
            "Delete this RRset policy?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        success, result = self.api_client.delete_token_policy(
            self._current_token_id, policy['id']
        )
        if success:
            self._load_policies(self._current_token_id)
        else:
            msg = result.get('message', str(result)) if isinstance(result, dict) else str(result)
            QMessageBox.critical(self, "Delete Failed", f"Failed to delete policy:\n{msg}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_ts(ts_str):
    """Format an ISO-8601 timestamp string to a shorter readable form."""
    if not ts_str:
        return None
    try:
        # Strip sub-second precision and timezone suffix for brevity
        ts = ts_str[:19].replace('T', ' ')
        return ts
    except Exception:
        return ts_str


def _perm_flags(token):
    """Return abbreviated permission flags string, e.g. 'CDM'."""
    flags = ''
    if token.get('perm_create_domain'):
        flags += 'C'
    if token.get('perm_delete_domain'):
        flags += 'D'
    if token.get('perm_manage_tokens'):
        flags += 'M'
    return flags or '—'


def _italicize(item):
    """Apply italic font to a QTableWidgetItem."""
    font = item.font()
    font.setItalic(True)
    item.setFont(font)
    item.setForeground(QtGui.QColor('#888'))
