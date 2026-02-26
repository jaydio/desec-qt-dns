#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Token management dialog for deSEC Qt DNS Manager.
Provides UI for creating, viewing, editing, and deleting API tokens,
as well as managing per-token RRset policies.
"""

import logging
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt, QTimer, QThreadPool, QRunnable, QObject, Signal, QPropertyAnimation, QEasingCurve
from qfluentwidgets import (PushButton, PrimaryPushButton, LineEdit, CheckBox,
                             PlainTextEdit, TableWidget, StrongBodyLabel, CaptionLabel,
                             isDarkTheme, SubtitleLabel)
from fluent_styles import container_qss, SPLITTER_QSS
from notify_drawer import NotifyDrawer
from api_queue import QueueItem, PRIORITY_NORMAL

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
    done = Signal(bool, object)   # success, data


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
        header = StrongBodyLabel("Token Created Successfully")
        layout.addWidget(header)

        # Warning
        warning = QtWidgets.QLabel(
            "This is the only time the token value will be shown. "
            "Store it securely before closing this dialog."
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)

        # Token value row
        token_row = QtWidgets.QHBoxLayout()
        self._token_field = LineEdit()
        self._token_field.setText(self.token_value)
        self._token_field.setReadOnly(True)
        self._token_field.setFont(QtGui.QFont("Monospace", 10))
        self._token_field.setMinimumWidth(380)
        token_row.addWidget(self._token_field)

        self._copy_btn = PushButton("Copy to Clipboard")
        self._copy_btn.clicked.connect(self._copy_token)
        token_row.addWidget(self._copy_btn)
        layout.addLayout(token_row)

        # Acknowledgement checkbox
        self._ack_checkbox = CheckBox("I have securely stored my token value")
        self._ack_checkbox.stateChanged.connect(self._on_ack_changed)
        layout.addWidget(self._ack_checkbox)

        # Close button (disabled until checkbox is checked)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        self._close_btn = PushButton("Close")
        self._close_btn.setEnabled(False)
        self._close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._close_btn)
        layout.addLayout(btn_row)

        self.setStyleSheet(container_qss())

    def _copy_token(self):
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(self.token_value)
        self._copy_btn.setText("Copied! (clears in 30s)")

        # Auto-clear clipboard after 30 seconds if it still contains the token
        token_val = self.token_value
        def _clear_clipboard():
            if clipboard.text() == token_val:
                clipboard.clear()
                logger.info("Clipboard auto-cleared after token copy timeout")
        QTimer.singleShot(30000, _clear_clipboard)

    def _on_ack_changed(self):
        self._close_btn.setEnabled(self._ack_checkbox.isChecked())


# ---------------------------------------------------------------------------
# TokenPolicyPanel — slide-in drawer for add / edit RRset policy
# ---------------------------------------------------------------------------

class TokenPolicyPanel(QtWidgets.QWidget):
    """Slide-in right panel for adding or editing an RRset policy."""

    PANEL_WIDTH = 400

    save_done = QtCore.Signal()
    cancelled = QtCore.Signal()

    def __init__(self, api_client, parent=None, api_queue=None):
        super().__init__(parent)
        self.api_client = api_client
        self.api_queue = api_queue
        self._token_id = None
        self._policy = None
        self._animation = None
        self.setObjectName("tokenPolicyPanel")
        self.hide()
        self._setup_ui()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        bg = QtGui.QColor(32, 32, 32) if isDarkTheme() else QtGui.QColor(243, 243, 243)
        painter.fillRect(self.rect(), bg)

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Header row: title + close button
        header_row = QtWidgets.QHBoxLayout()
        self._title = SubtitleLabel("Add Policy")
        header_row.addWidget(self._title, 1)
        close_btn = PushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setToolTip("Close (Esc)")
        close_btn.clicked.connect(self._on_cancel)
        header_row.addWidget(close_btn)
        layout.addLayout(header_row)

        # Escape shortcut
        esc = QtGui.QShortcut(QtGui.QKeySequence(Qt.Key.Key_Escape), self)
        esc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        esc.activated.connect(self._on_cancel)

        desc = QtWidgets.QLabel(
            "Define a fine-grained access rule for this token. "
            "Leave fields blank for a default catch-all policy."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        form = QtWidgets.QFormLayout()
        form.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.DontWrapRows)

        self._domain_edit = LineEdit()
        self._domain_edit.setPlaceholderText("e.g. example.com  (blank = default policy)")
        form.addRow("Domain:", self._domain_edit)

        self._subname_edit = LineEdit()
        self._subname_edit.setPlaceholderText("e.g. www  (blank = match all)")
        form.addRow("Subname:", self._subname_edit)

        self._type_combo = QtWidgets.QComboBox()
        self._type_combo.addItem("(Any — match all types)")
        for t in DNS_RECORD_TYPES:
            self._type_combo.addItem(t)
        form.addRow("Type:", self._type_combo)

        self._perm_write = CheckBox("Allow write access")
        form.addRow("Write:", self._perm_write)

        layout.addLayout(form)

        self._error_label = QtWidgets.QLabel("")
        self._error_label.setWordWrap(True)
        layout.addWidget(self._error_label)

        layout.addStretch()

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = PushButton("Cancel")
        cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(cancel_btn)
        self._save_btn = PrimaryPushButton("Save")
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self._save_btn)
        layout.addLayout(btn_row)

    def open_for_add(self, token_id):
        self._token_id = token_id
        self._policy = None
        self._title.setText("Add Policy")
        self._domain_edit.clear()
        self._subname_edit.clear()
        self._type_combo.setCurrentIndex(0)
        self._perm_write.setChecked(False)
        self._error_label.setText("")
        self.slide_in()

    def open_for_edit(self, token_id, policy):
        self._token_id = token_id
        self._policy = policy
        self._title.setText("Edit Policy")
        self._domain_edit.setText(policy.get('domain') or '')
        self._subname_edit.setText(policy.get('subname') or '')
        type_val = policy.get('type')
        if type_val and type_val in DNS_RECORD_TYPES:
            idx = self._type_combo.findText(type_val)
            self._type_combo.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            self._type_combo.setCurrentIndex(0)
        self._perm_write.setChecked(bool(policy.get('perm_write', False)))
        self._error_label.setText("")
        self.slide_in()

    def _on_save(self):
        domain = self._domain_edit.text().strip() or None
        subname = self._subname_edit.text().strip() or None
        type_text = self._type_combo.currentText()
        type_ = None if type_text.startswith('(') else type_text
        perm_write = self._perm_write.isChecked()

        self._save_btn.setEnabled(False)
        self._save_btn.setText("Saving…")

        is_edit = bool(self._policy)

        if self.api_queue:
            if is_edit:
                api_method = self.api_client.update_token_policy
                args = (self._token_id, self._policy['id'])
                kwargs = dict(domain=domain, subname=subname, type=type_, perm_write=perm_write)
                action = f"Update policy for token {self._token_id}"
            else:
                api_method = self.api_client.create_token_policy
                args = (self._token_id,)
                kwargs = dict(domain=domain, subname=subname, type_=type_, perm_write=perm_write)
                action = f"Create policy for token {self._token_id}"

            def _on_done(success, result):
                self._save_btn.setEnabled(True)
                self._save_btn.setText("Save")
                if success:
                    self.slide_out()
                    self.save_done.emit()
                else:
                    msg = result.get('message', str(result)) if isinstance(result, dict) else str(result)
                    self._error_label.setText(f"Error: {msg}")

            item = QueueItem(
                priority=PRIORITY_NORMAL,
                category="tokens",
                action=action,
                callable=api_method,
                args=args,
                kwargs=kwargs,
                callback=_on_done,
            )
            self.api_queue.enqueue(item)

            if self.api_queue.is_paused:
                self._save_btn.setEnabled(True)
                self._save_btn.setText("Save")
                self._error_label.setText("Queued — will be sent when back online.")
                self.slide_out()
        else:
            if is_edit:
                success, result = self.api_client.update_token_policy(
                    self._token_id, self._policy['id'],
                    domain=domain, subname=subname, type=type_, perm_write=perm_write
                )
            else:
                success, result = self.api_client.create_token_policy(
                    self._token_id, domain=domain, subname=subname,
                    type_=type_, perm_write=perm_write
                )

            self._save_btn.setEnabled(True)
            self._save_btn.setText("Save")

            if success:
                self.slide_out()
                self.save_done.emit()
            else:
                msg = result.get('message', str(result)) if isinstance(result, dict) else str(result)
                self._error_label.setText(f"Error: {msg}")

    def _on_cancel(self):
        self.slide_out()
        self.cancelled.emit()

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


# ---------------------------------------------------------------------------
# CreateTokenPanel — slide-in drawer for creating a new token
# ---------------------------------------------------------------------------

class CreateTokenPanel(QtWidgets.QWidget):
    """Slide-in right panel for creating a new API token."""

    PANEL_WIDTH = 460

    token_created = QtCore.Signal()
    cancelled = QtCore.Signal()

    def __init__(self, api_client, parent=None, api_queue=None):
        super().__init__(parent)
        self.api_client = api_client
        self.api_queue = api_queue
        self._animation = None
        self.setObjectName("createTokenPanel")
        self.hide()
        self._setup_ui()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        bg = QtGui.QColor(32, 32, 32) if isDarkTheme() else QtGui.QColor(243, 243, 243)
        painter.fillRect(self.rect(), bg)

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Header row: title + close button
        header_row = QtWidgets.QHBoxLayout()
        header_row.addWidget(SubtitleLabel("New Token"), 1)
        close_btn = PushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setToolTip("Close (Esc)")
        close_btn.clicked.connect(self._on_cancel)
        header_row.addWidget(close_btn)
        layout.addLayout(header_row)

        # Escape shortcut
        esc = QtGui.QShortcut(QtGui.QKeySequence(Qt.Key.Key_Escape), self)
        esc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        esc.activated.connect(self._on_cancel)

        desc = QtWidgets.QLabel(
            "After creation the token value is shown once — copy it before closing."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        form = QtWidgets.QFormLayout()
        self._name_edit = LineEdit()
        self._name_edit.setPlaceholderText("e.g. My App Token")
        form.addRow("Name:", self._name_edit)
        layout.addLayout(form)

        self._perm_create = CheckBox("Create Domains")
        self._perm_delete = CheckBox("Delete Domains")
        self._perm_manage = CheckBox("Manage Tokens")
        self._auto_policy = CheckBox("Auto Policy")
        layout.addWidget(self._perm_create)
        layout.addWidget(self._perm_delete)
        layout.addWidget(self._perm_manage)
        layout.addWidget(self._auto_policy)

        exp_form = QtWidgets.QFormLayout()
        self._max_age_edit = LineEdit()
        self._max_age_edit.setPlaceholderText("e.g. 30 00:00:00  (blank = no limit)")
        exp_form.addRow("Max Age:", self._max_age_edit)

        self._max_unused_edit = LineEdit()
        self._max_unused_edit.setPlaceholderText("e.g. 7 00:00:00  (blank = no limit)")
        exp_form.addRow("Max Unused:", self._max_unused_edit)
        layout.addLayout(exp_form)

        layout.addWidget(QtWidgets.QLabel("Allowed Subnets (one CIDR per line):"))
        self._subnets_edit = PlainTextEdit()
        self._subnets_edit.setPlainText("0.0.0.0/0\n::/0")
        self._subnets_edit.setFixedHeight(72)
        layout.addWidget(self._subnets_edit)

        self._error_label = QtWidgets.QLabel("")
        self._error_label.setWordWrap(True)
        layout.addWidget(self._error_label)

        layout.addStretch()

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = PushButton("Cancel")
        cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(cancel_btn)
        self._create_btn = PrimaryPushButton("Create Token")
        self._create_btn.clicked.connect(self._on_create)
        btn_row.addWidget(self._create_btn)
        layout.addLayout(btn_row)

    def open(self):
        self._name_edit.clear()
        self._perm_create.setChecked(False)
        self._perm_delete.setChecked(False)
        self._perm_manage.setChecked(False)
        self._auto_policy.setChecked(False)
        self._max_age_edit.clear()
        self._max_unused_edit.clear()
        self._subnets_edit.setPlainText("0.0.0.0/0\n::/0")
        self._error_label.setText("")
        self.slide_in()

    def _on_create(self):
        name = self._name_edit.text().strip()
        if not name:
            self._error_label.setText("Token name cannot be empty.")
            return

        max_age = self._max_age_edit.text().strip() or None
        max_unused = self._max_unused_edit.text().strip() or None
        subnet_lines = [
            s.strip() for s in self._subnets_edit.toPlainText().splitlines() if s.strip()
        ]
        allowed_subnets = subnet_lines if subnet_lines else None

        self._create_btn.setEnabled(False)
        self._create_btn.setText("Creating…")

        create_kwargs = dict(
            name=name,
            perm_create_domain=self._perm_create.isChecked(),
            perm_delete_domain=self._perm_delete.isChecked(),
            perm_manage_tokens=self._perm_manage.isChecked(),
            max_age=max_age,
            max_unused_period=max_unused,
            allowed_subnets=allowed_subnets,
            auto_policy=self._auto_policy.isChecked(),
        )

        if self.api_queue:
            def _on_done(success, result):
                self._create_btn.setEnabled(True)
                self._create_btn.setText("Create Token")
                if success:
                    token_id = result.get('id', '')
                    token_value = result.get('token', '')
                    if token_id:
                        # Create default policy via queue too
                        policy_item = QueueItem(
                            priority=PRIORITY_NORMAL,
                            category="tokens",
                            action=f"Create default policy for token {token_id}",
                            callable=self.api_client.create_token_policy,
                            args=(token_id,),
                            kwargs=dict(domain=None, subname=None, type_=None, perm_write=False),
                        )
                        self.api_queue.enqueue(policy_item)
                    secret_dlg = TokenSecretDialog(token_value, self.window())
                    secret_dlg.exec()
                    self.slide_out()
                    self.token_created.emit()
                else:
                    msg = result.get('message', str(result)) if isinstance(result, dict) else str(result)
                    self._error_label.setText(f"Error: {msg}")

            item = QueueItem(
                priority=PRIORITY_NORMAL,
                category="tokens",
                action=f"Create token '{name}'",
                callable=self.api_client.create_token,
                kwargs=create_kwargs,
                callback=_on_done,
            )
            self.api_queue.enqueue(item)
        else:
            success, result = self.api_client.create_token(**create_kwargs)

            self._create_btn.setEnabled(True)
            self._create_btn.setText("Create Token")

            if success:
                token_id = result.get('id', '')
                token_value = result.get('token', '')
                if token_id:
                    self.api_client.create_token_policy(
                        token_id, domain=None, subname=None, type_=None, perm_write=False,
                    )
                secret_dlg = TokenSecretDialog(token_value, self.window())
                secret_dlg.exec()
                self.slide_out()
                self.token_created.emit()
            else:
                msg = result.get('message', str(result)) if isinstance(result, dict) else str(result)
                self._error_label.setText(f"Error: {msg}")

    def _on_cancel(self):
        self.slide_out()
        self.cancelled.emit()

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


# ---------------------------------------------------------------------------
# TokenManagerDialog — main token management window
# ---------------------------------------------------------------------------

class TokenManagerInterface(QtWidgets.QWidget):
    """
    Token management page for the Fluent sidebar navigation.

    Left panel: table listing all tokens.
    Right panel: tab widget with Details and Policies tabs.
    """

    def __init__(self, api_client, parent=None, api_queue=None, cache_manager=None):
        super().__init__(parent)
        self.setObjectName("tokenManagerInterface")
        self.api_client = api_client
        self.api_queue = api_queue
        self.cache_manager = cache_manager
        self._current_token_id = None   # token currently shown in detail panel
        self._policies = []             # policies for current token
        self._setup_ui()

    def showEvent(self, event):
        """Load tokens and refresh theme-aware styles whenever the page becomes visible."""
        super().showEvent(event)
        self.setStyleSheet(container_qss())
        self._load_tokens()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Main splitter
        splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(SPLITTER_QSS)
        outer.addWidget(splitter, 1)

        # ---- Left panel ----
        self._left_widget = left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(6)

        title_layout = QtWidgets.QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.addWidget(StrongBodyLabel("Tokens"))
        title_layout.addStretch()
        self._token_count_label = CaptionLabel("Total tokens: 0")
        title_layout.addWidget(self._token_count_label)
        left_layout.addLayout(title_layout)

        self._token_table = TableWidget()
        self._token_table.setColumnCount(4)
        self._token_table.setHorizontalHeaderLabels(
            ["Name", "Created", "Last Used", "Perms"]
        )
        self._token_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._token_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._token_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._token_table.verticalHeader().setVisible(False)
        self._token_table.horizontalHeader().setStretchLastSection(False)
        self._token_table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Interactive
        )
        self._token_table.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.Interactive
        )
        self._token_table.horizontalHeader().setSectionResizeMode(
            2, QtWidgets.QHeaderView.ResizeMode.Interactive
        )
        self._token_table.horizontalHeader().setSectionResizeMode(
            3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self._token_table.setColumnWidth(0, 180)
        self._token_table.setColumnWidth(1, 155)
        self._token_table.setColumnWidth(2, 155)
        self._token_table.setAlternatingRowColors(True)
        self._token_table.selectionModel().selectionChanged.connect(
            self._on_token_selection_changed
        )
        left_layout.addWidget(self._token_table)

        # Buttons below token table
        tbl_btn_row = QtWidgets.QHBoxLayout()
        self._new_btn = PushButton("New Token")
        self._new_btn.clicked.connect(self._new_token)
        tbl_btn_row.addWidget(self._new_btn)

        self._delete_btn = PushButton("Delete")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._delete_token)
        tbl_btn_row.addWidget(self._delete_btn)

        self._refresh_btn = PushButton("Refresh")
        self._refresh_btn.clicked.connect(self._load_tokens)
        tbl_btn_row.addWidget(self._refresh_btn)

        left_layout.addLayout(tbl_btn_row)
        splitter.addWidget(left_widget)

        # ---- Right panel ----
        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        right_layout.setContentsMargins(6, 6, 6, 6)
        right_layout.setSpacing(6)

        right_title_layout = QtWidgets.QHBoxLayout()
        right_title_layout.setContentsMargins(0, 0, 0, 0)
        right_title_layout.addWidget(StrongBodyLabel("Token Details"))
        right_title_layout.addStretch()
        right_layout.addLayout(right_title_layout)

        self._tab_widget = QtWidgets.QTabWidget()
        right_layout.addWidget(self._tab_widget)

        self._tab_widget.addTab(self._build_details_tab(), "Details")
        self._tab_widget.addTab(self._build_policies_tab(), "RRset Policies")

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([340, 760])

        # Initially show placeholder in both tabs
        self._set_detail_enabled(False)
        self._set_policies_enabled(False)

        self.setStyleSheet(container_qss())

        # Slide-in drawer panels (absolutely positioned overlays)
        self._policy_panel = TokenPolicyPanel(self.api_client, parent=self, api_queue=self.api_queue)
        self._policy_panel.save_done.connect(lambda: self._load_policies(self._current_token_id))

        self._create_panel = CreateTokenPanel(self.api_client, parent=self, api_queue=self.api_queue)
        self._create_panel.token_created.connect(self._load_tokens)

        # Delete confirmation drawer (slides from top, scoped to left panel)
        from confirm_drawer import DeleteConfirmDrawer
        self._delete_drawer = DeleteConfirmDrawer(parent=self._left_widget)

        # Notification drawer (slides from top, full page width)
        self._notify_drawer = NotifyDrawer(parent=self)

    def _build_details_tab(self):
        """Build and return the Details tab widget."""
        widget = QtWidgets.QWidget()
        widget.setStyleSheet("background: transparent;")
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setSpacing(10)

        self._detail_placeholder = QtWidgets.QLabel(
            "Select a token to view and edit details."
        )
        self._detail_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._detail_placeholder)

        # --- Read-only info ---
        self._info_group = QtWidgets.QGroupBox("Token Info")
        info_form = QtWidgets.QFormLayout(self._info_group)

        id_row = QtWidgets.QHBoxLayout()
        self._info_id = LineEdit()
        self._info_id.setReadOnly(True)
        id_row.addWidget(self._info_id)
        copy_id_btn = PushButton("Copy")
        copy_id_btn.setFixedWidth(72)
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

        self._edit_name = LineEdit()
        self._edit_name.setPlaceholderText("Token name")
        settings_form.addRow("Name:", self._edit_name)

        self._edit_perm_create = CheckBox("Create Domains")
        settings_form.addRow("", self._edit_perm_create)

        self._edit_perm_delete = CheckBox("Delete Domains")
        settings_form.addRow("", self._edit_perm_delete)

        self._edit_perm_manage = CheckBox("Manage Tokens")
        settings_form.addRow("", self._edit_perm_manage)

        self._edit_auto_policy = CheckBox("Auto Policy")
        self._edit_auto_policy.setToolTip(
            "When enabled, automatically creates a permissive RRset policy\n"
            "for each domain created with this token."
        )
        settings_form.addRow("", self._edit_auto_policy)

        self._edit_max_age = LineEdit()
        self._edit_max_age.setPlaceholderText(
            "e.g. 30 00:00:00 (30 days)   blank = no limit"
        )
        settings_form.addRow("Max Age:", self._edit_max_age)

        self._edit_max_unused = LineEdit()
        self._edit_max_unused.setPlaceholderText(
            "e.g. 7 00:00:00 (7 days)    blank = no limit"
        )
        settings_form.addRow("Max Unused Period:", self._edit_max_unused)

        self._edit_subnets = PlainTextEdit()
        self._edit_subnets.setFixedHeight(72)
        self._edit_subnets.setPlaceholderText("One CIDR per line, e.g. 0.0.0.0/0")
        settings_form.addRow("Allowed Subnets:", self._edit_subnets)

        layout.addWidget(self._settings_group)

        # Save button
        save_row = QtWidgets.QHBoxLayout()
        save_row.addStretch()
        self._save_btn = PushButton("Save Changes")
        self._save_btn.clicked.connect(self._save_token)
        save_row.addWidget(self._save_btn)
        layout.addLayout(save_row)

        layout.addStretch()
        return widget

    def _build_policies_tab(self):
        """Build and return the RRset Policies tab widget."""
        widget = QtWidgets.QWidget()
        widget.setStyleSheet("background: transparent;")
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setSpacing(8)

        self._policy_placeholder = QtWidgets.QLabel(
            "Select a token to view and manage its RRset policies."
        )
        self._policy_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._policy_placeholder)

        desc = QtWidgets.QLabel(
            "RRset policies define fine-grained write access per domain, subname, "
            "and record type. Policies with all-null fields act as a default catch-all."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self._policy_table = TableWidget()
        self._policy_table.setColumnCount(4)
        self._policy_table.setHorizontalHeaderLabels(
            ["Domain", "Subname", "Type", "Write"]
        )
        self._policy_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._policy_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
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
        self._policy_table.setAlternatingRowColors(True)
        self._policy_table.selectionModel().selectionChanged.connect(
            self._on_policy_selection_changed
        )
        self._policy_table.cellDoubleClicked.connect(self._on_policy_double_clicked)
        layout.addWidget(self._policy_table)

        # Policy buttons
        pol_btn_row = QtWidgets.QHBoxLayout()
        self._add_policy_btn = PushButton("Add Policy")
        self._add_policy_btn.clicked.connect(self._add_policy)
        pol_btn_row.addWidget(self._add_policy_btn)

        self._edit_policy_btn = PushButton("Edit Policy")
        self._edit_policy_btn.setEnabled(False)
        self._edit_policy_btn.clicked.connect(self._edit_policy)
        pol_btn_row.addWidget(self._edit_policy_btn)

        self._delete_policy_btn = PushButton("Delete Policy")
        self._delete_policy_btn.setEnabled(False)
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

        # Cache-first: show cached data immediately while API fetches in background
        if self.cache_manager:
            cached, _ = self.cache_manager.get_cached_tokens()
            if cached:
                self._on_tokens_loaded(True, cached)
                # If offline, stop here — don't enqueue an API call
                if self.api_queue and self.api_queue.is_paused:
                    return
                # Otherwise fall through to enqueue a background refresh

        # If offline with no cache, show empty state and stop
        if self.api_queue and self.api_queue.is_paused:
            self._on_tokens_loaded(False, "Offline — no cached tokens available")
            return

        if self.api_queue:
            def _on_done(success, data):
                self._on_tokens_loaded(success, data)

            item = QueueItem(
                priority=PRIORITY_NORMAL,
                category="tokens",
                action="Load tokens",
                callable=self.api_client.list_tokens,
                callback=_on_done,
            )
            self.api_queue.enqueue(item)
        else:
            worker = _Worker(self.api_client.list_tokens)
            worker.signals.done.connect(self._on_tokens_loaded)
            QThreadPool.globalInstance().start(worker)

    def _on_tokens_loaded(self, success, data):
        self._token_table.setEnabled(True)
        self._refresh_btn.setEnabled(True)
        self._new_btn.setEnabled(True)

        if not success:
            msg = data.get('message', str(data)) if isinstance(data, dict) else str(data)
            self._notify_drawer.error("Load Failed", f"Could not load tokens:\n{msg}")
            return

        tokens = data if isinstance(data, list) else []
        if tokens and self.cache_manager:
            self.cache_manager.cache_tokens(tokens)
        self._token_count_label.setText(f"Total tokens: {len(tokens)}")
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

            perms = _perm_flags(token)
            perm_item = QtWidgets.QTableWidgetItem(perms)
            perm_item.setToolTip(
                "C = perm_create_domain\n"
                "D = perm_delete_domain\n"
                "M = perm_manage_tokens"
            )
            self._token_table.setItem(row, 3, perm_item)

    # ------------------------------------------------------------------
    # Token table selection
    # ------------------------------------------------------------------

    def _on_token_selection_changed(self):
        selected_rows = set(idx.row() for idx in self._token_table.selectedIndexes())
        if not selected_rows:
            self._current_token_id = None
            self._delete_btn.setEnabled(False)
            self._delete_btn.setText("Delete")
            self._set_detail_enabled(False)
            self._set_policies_enabled(False)
            return

        n = len(selected_rows)
        self._delete_btn.setEnabled(True)
        self._delete_btn.setText(f"Delete ({n})" if n > 1 else "Delete")

        # Show details for the most-recently-focused row
        current_row = self._token_table.currentRow()
        if current_row < 0:
            current_row = min(selected_rows)
        name_item = self._token_table.item(current_row, 0)
        if name_item is None:
            return
        token = name_item.data(Qt.ItemDataRole.UserRole)
        if token is None:
            return

        self._current_token_id = token.get('id')
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
            self._notify_drawer.warning("Missing Name", "Token name cannot be empty.")
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

        update_kwargs = dict(
            name=name,
            perm_create_domain=self._edit_perm_create.isChecked(),
            perm_delete_domain=self._edit_perm_delete.isChecked(),
            perm_manage_tokens=self._edit_perm_manage.isChecked(),
            auto_policy=self._edit_auto_policy.isChecked(),
            max_age=max_age,
            max_unused_period=max_unused,
            allowed_subnets=allowed_subnets,
        )
        token_id = self._current_token_id

        def _handle_result(success, result):
            self._save_btn.setEnabled(True)
            self._save_btn.setText("Save Changes")
            if success:
                row = self._token_table.currentRow()
                if row >= 0:
                    name_item = self._token_table.item(row, 0)
                    if name_item:
                        name_item.setText(result.get('name', name))
                        name_item.setData(Qt.ItemDataRole.UserRole, result)
                        perm_item = self._token_table.item(row, 3)
                        if perm_item:
                            perm_item.setText(_perm_flags(result))
            else:
                msg = result.get('message', str(result)) if isinstance(result, dict) else str(result)
                self._notify_drawer.error("Save Failed", f"Failed to save token:\n{msg}")

        if self.api_queue:
            item = QueueItem(
                priority=PRIORITY_NORMAL,
                category="tokens",
                action=f"Update token '{name}'",
                callable=self.api_client.update_token,
                args=(token_id,),
                kwargs=update_kwargs,
                callback=_handle_result,
            )
            self.api_queue.enqueue(item)

            if self.api_queue.is_paused:
                self._save_btn.setEnabled(True)
                self._save_btn.setText("Save Changes")
                self._notify_drawer.info(
                    "Queued",
                    f"Token update queued — will be sent when back online.",
                )
        else:
            success, result = self.api_client.update_token(token_id, **update_kwargs)
            _handle_result(success, result)

    # ------------------------------------------------------------------
    # New / Delete token
    # ------------------------------------------------------------------

    def _new_token(self):
        self._create_panel.open()

    def _delete_token(self):
        selected_rows = sorted(set(idx.row() for idx in self._token_table.selectedIndexes()))
        if not selected_rows:
            return

        tokens_to_delete = []
        for row in selected_rows:
            name_item = self._token_table.item(row, 0)
            if name_item:
                token = name_item.data(Qt.ItemDataRole.UserRole)
                if token:
                    tokens_to_delete.append(token)

        if not tokens_to_delete:
            return

        count = len(tokens_to_delete)
        token_names = [t.get('name', t.get('id', '')) for t in tokens_to_delete]

        if count == 1:
            message = (
                f"Delete token '{token_names[0]}'?\n\n"
                "Warning: if this is the token you are currently using, "
                "the application will lose API access."
            )
        else:
            message = (
                f"Delete {count} tokens?\n\n"
                "Warning: if any of these is the token you are currently using, "
                "the application will lose API access."
            )

        def _do_delete():
            if self.api_queue:
                pending = len(tokens_to_delete)
                errors_list = []

                def _make_cb(token_name):
                    def _cb(success, result):
                        nonlocal pending
                        if not success:
                            msg = result.get('message', str(result)) if isinstance(result, dict) else str(result)
                            errors_list.append(msg)
                        pending -= 1
                        if pending <= 0:
                            self._load_tokens()
                            self._current_token_id = None
                            self._set_detail_enabled(False)
                            self._set_policies_enabled(False)
                            if errors_list:
                                self._notify_drawer.error("Delete Failed", "\n".join(errors_list))
                    return _cb

                for token in tokens_to_delete:
                    item = QueueItem(
                        priority=PRIORITY_NORMAL,
                        category="tokens",
                        action=f"Delete token '{token.get('name', token['id'])}'",
                        callable=self.api_client.delete_token,
                        args=(token['id'],),
                        callback=_make_cb(token.get('name', '')),
                    )
                    self.api_queue.enqueue(item)
            else:
                errors = []
                for token in tokens_to_delete:
                    success, result = self.api_client.delete_token(token['id'])
                    if not success:
                        msg = result.get('message', str(result)) if isinstance(result, dict) else str(result)
                        errors.append(msg)
                self._load_tokens()
                self._current_token_id = None
                self._set_detail_enabled(False)
                self._set_policies_enabled(False)
                if errors:
                    self._notify_drawer.error("Delete Failed", "\n".join(errors))

        self._delete_drawer.ask(
            title="Delete Token" if count == 1 else f"Delete {count} Tokens",
            message=message,
            items=token_names if count > 1 else None,
            on_confirm=_do_delete,
            confirm_text=f"Delete {count} Token{'s' if count > 1 else ''}",
        )

    # ------------------------------------------------------------------
    # Policies tab loading
    # ------------------------------------------------------------------

    def _load_policies(self, token_id):
        self._policy_table.setRowCount(0)
        self._policies = []

        # Cache-first: show cached policies immediately
        if self.cache_manager:
            cached, _ = self.cache_manager.get_cached_token_policies(token_id)
            if cached:
                self._on_policies_loaded(True, cached)
                if self.api_queue and self.api_queue.is_paused:
                    return

        # Offline with no cache — show empty state
        if self.api_queue and self.api_queue.is_paused:
            self._on_policies_loaded(True, [])
            return

        if self.api_queue:
            def _on_done(success, data):
                self._on_policies_loaded(success, data, token_id=token_id)

            item = QueueItem(
                priority=PRIORITY_NORMAL,
                category="tokens",
                action=f"Load policies for token {token_id}",
                callable=self.api_client.list_token_policies,
                args=(token_id,),
                callback=_on_done,
            )
            self.api_queue.enqueue(item)
        else:
            worker = _Worker(self.api_client.list_token_policies, token_id)
            worker.signals.done.connect(
                lambda success, data: self._on_policies_loaded(success, data, token_id=token_id)
            )
            QThreadPool.globalInstance().start(worker)

    def _on_policies_loaded(self, success, data, token_id=None):
        if not success:
            return

        self._policies = data if isinstance(data, list) else []
        if self._policies and self.cache_manager and token_id:
            self.cache_manager.cache_token_policies(token_id, self._policies)
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
                write_item.setForeground(QtGui.QColor('#66BB6A' if isDarkTheme() else '#2e7d32'))
            self._policy_table.setItem(row, 3, write_item)

    # ------------------------------------------------------------------
    # Policy table selection
    # ------------------------------------------------------------------

    def _on_policy_selection_changed(self):
        selected_rows = len(set(idx.row() for idx in self._policy_table.selectedIndexes()))
        self._edit_policy_btn.setEnabled(selected_rows == 1)
        self._delete_policy_btn.setEnabled(selected_rows > 0)

    def _get_selected_policy(self):
        row = self._policy_table.currentRow()
        if row < 0 or row >= len(self._policies):
            return None
        return self._policies[row]

    def _on_policy_double_clicked(self, row, column):
        if not self._current_token_id or row < 0 or row >= len(self._policies):
            return
        self._policy_panel.open_for_edit(self._current_token_id, self._policies[row])

    # ------------------------------------------------------------------
    # Policy CRUD
    # ------------------------------------------------------------------

    def _add_policy(self):
        if not self._current_token_id:
            return
        self._policy_panel.open_for_add(self._current_token_id)

    def _edit_policy(self):
        policy = self._get_selected_policy()
        if not policy or not self._current_token_id:
            return
        self._policy_panel.open_for_edit(self._current_token_id, policy)

    def _delete_policy(self):
        if not self._current_token_id:
            return

        selected_rows = sorted(set(idx.row() for idx in self._policy_table.selectedIndexes()))
        if not selected_rows:
            return

        policies_to_delete = [
            self._policies[row] for row in selected_rows if row < len(self._policies)
        ]
        if not policies_to_delete:
            return

        count = len(policies_to_delete)
        policy_labels = [
            f"{p.get('domain') or '(default)'} / {p.get('subname') if p.get('subname') is not None else '(any)'} / {p.get('type') or '(any)'}"
            for p in policies_to_delete
        ]

        token_id = self._current_token_id

        def _do_delete():
            if self.api_queue:
                pending = len(policies_to_delete)
                errors_list = []

                def _make_cb():
                    def _cb(success, result):
                        nonlocal pending
                        if not success:
                            msg = result.get('message', str(result)) if isinstance(result, dict) else str(result)
                            errors_list.append(msg)
                        pending -= 1
                        if pending <= 0:
                            self._load_policies(token_id)
                            if errors_list:
                                self._notify_drawer.error("Delete Failed", "\n".join(errors_list))
                    return _cb

                for policy in policies_to_delete:
                    item = QueueItem(
                        priority=PRIORITY_NORMAL,
                        category="tokens",
                        action=f"Delete policy {policy['id']}",
                        callable=self.api_client.delete_token_policy,
                        args=(token_id, policy['id']),
                        callback=_make_cb(),
                    )
                    self.api_queue.enqueue(item)
            else:
                errors = []
                for policy in policies_to_delete:
                    success, result = self.api_client.delete_token_policy(
                        token_id, policy['id']
                    )
                    if not success:
                        msg = result.get('message', str(result)) if isinstance(result, dict) else str(result)
                        errors.append(msg)
                self._load_policies(token_id)
                if errors:
                    self._notify_drawer.error("Delete Failed", "\n".join(errors))

        self._delete_drawer.ask(
            title=f"Delete {'Policy' if count == 1 else f'{count} Policies'}",
            message=f"Delete {count} selected {'policy' if count == 1 else 'policies'}?",
            items=policy_labels,
            on_confirm=_do_delete,
            confirm_text=f"Delete {'Policy' if count == 1 else f'{count} Policies'}",
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_policy_panel'):
            self._policy_panel.reposition(event.size())
        if hasattr(self, '_create_panel'):
            self._create_panel.reposition(event.size())
        if hasattr(self, '_delete_drawer'):
            self._delete_drawer.reposition(self._left_widget.size())
        if hasattr(self, '_notify_drawer'):
            self._notify_drawer.reposition(event.size())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_ts(ts_str, short=False):
    """Format an ISO-8601 timestamp string to a shorter readable form."""
    if not ts_str:
        return None
    try:
        ts = ts_str[:16].replace('T', ' ')  # YYYY-MM-DD HH:MM
        return ts
    except Exception:
        return ts_str[:16] if ts_str else ts_str


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
    item.setForeground(QtGui.QColor('#aaa' if isDarkTheme() else '#888'))
