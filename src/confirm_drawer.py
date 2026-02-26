#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Top-sliding confirmation drawer for destructive actions.

Provides a non-modal, animated drawer that slides down from the top of
its parent widget to confirm delete operations.  Uses a two-step
confirmation with swapped button positions to prevent accidental clicks.

Follows the same architectural pattern as the existing right-sliding
drawer panels (RecordEditPanel, AuthPanel, AddZonePanel, etc.).
"""

import html
import logging

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from qfluentwidgets import (
    PushButton, SubtitleLabel, FluentIcon, isDarkTheme,
)
from fluent_styles import container_qss

logger = logging.getLogger(__name__)

_ITEMS_VISIBLE_LIMIT = 8
_MIN_HEIGHT = 120
_MAX_HEIGHT = 280


class _BaseConfirmDrawer(QtWidgets.QWidget):
    """Base top-sliding two-step confirmation drawer.

    Step 1: [Cancel] [Confirm]  — standard layout
    Step 2: [Confirm] [Cancel]  — swapped to prevent muscle-memory clicks

    Subclasses set ``_icon``, ``_icon_color``, ``_btn_object_name``,
    ``_btn_bg`` / ``_btn_hover`` / ``_btn_pressed`` to theme themselves.
    """

    confirmed = QtCore.Signal()
    cancelled = QtCore.Signal()

    # Subclasses override these class-level attributes
    _object_name = "confirmDrawer"
    _icon = FluentIcon.DELETE
    _icon_color = "#e04040"
    _btn_object_name = "confirmActionBtn"
    _btn_bg = "rgba(200,40,40,0.9)"
    _btn_hover = "rgba(220,50,50,0.95)"
    _btn_pressed = "rgba(170,30,30,0.95)"
    _step2_message = "Are you sure? This action cannot be undone."

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName(self._object_name)
        self._animation = None
        self._on_confirm = None
        self._step = 1
        self._confirm_text = "Confirm"
        self._title = ""
        self._message = ""
        self.hide()
        self._setup_ui()

    # ── painting ───────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        bg = QtGui.QColor(32, 32, 32) if isDarkTheme() else QtGui.QColor(243, 243, 243)
        painter.fillRect(self.rect(), bg)

    # ── UI ─────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(10)

        # ── content row: icon | text ──────────────────────────────────
        content_row = QtWidgets.QHBoxLayout()
        content_row.setSpacing(16)

        icon_label = QtWidgets.QLabel()
        icon_label.setFixedSize(32, 32)
        icon_label.setPixmap(
            self._icon.icon(color=QtGui.QColor(self._icon_color)).pixmap(28, 28)
        )
        icon_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        content_row.addWidget(icon_label)

        text_col = QtWidgets.QVBoxLayout()
        text_col.setSpacing(4)

        self._title_label = SubtitleLabel("")
        text_col.addWidget(self._title_label)

        self._message_label = QtWidgets.QLabel("")
        self._message_label.setWordWrap(True)
        text_col.addWidget(self._message_label)

        self._items_label = QtWidgets.QLabel("")
        self._items_label.setTextFormat(Qt.TextFormat.RichText)
        self._items_label.setWordWrap(True)
        self._items_label.hide()
        text_col.addWidget(self._items_label)

        content_row.addLayout(text_col, 1)
        root.addLayout(content_row, 1)

        # ── button row ────────────────────────────────────────────────
        self._btn_row = QtWidgets.QHBoxLayout()
        self._btn_row.addStretch()

        self._cancel_btn = PushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)

        self._action_btn = PushButton("Confirm")
        self._action_btn.setObjectName(self._btn_object_name)
        self._action_btn.clicked.connect(self._on_action_clicked)

        # Step 1 layout: Cancel | Confirm
        self._btn_row.addWidget(self._cancel_btn)
        self._btn_row.addWidget(self._action_btn)

        root.addLayout(self._btn_row)

        # ── ESC shortcut ──────────────────────────────────────────────
        esc = QtGui.QShortcut(QtGui.QKeySequence(Qt.Key.Key_Escape), self)
        esc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        esc.activated.connect(self._on_cancel_clicked)

    def _set_button_order(self, step):
        """Rearrange buttons: step 1 = Cancel|Action, step 2 = Action|Cancel."""
        self._btn_row.removeWidget(self._cancel_btn)
        self._btn_row.removeWidget(self._action_btn)
        if step == 1:
            self._btn_row.addWidget(self._cancel_btn)
            self._btn_row.addWidget(self._action_btn)
        else:
            self._btn_row.addWidget(self._action_btn)
            self._btn_row.addWidget(self._cancel_btn)

    # ── public API ─────────────────────────────────────────────────────

    def ask(self, title, message, items=None, on_confirm=None, confirm_text="Confirm"):
        """Show the drawer with the given content.

        Args:
            title:        Drawer heading.
            message:      Descriptive text.
            items:        Optional list of item labels to show as bullets.
            on_confirm:   Callable invoked when the user confirms.
            confirm_text: Label for the action button.
        """
        # disconnect any previous callback
        self._disconnect_confirm()
        self._on_confirm = on_confirm
        if on_confirm is not None:
            self.confirmed.connect(on_confirm)

        self._title = title
        self._message = message
        self._confirm_text = confirm_text

        self._title_label.setText(title)
        self._message_label.setText(message)

        # items list
        if items:
            visible = items[:_ITEMS_VISIBLE_LIMIT]
            lines = [f"&nbsp;&nbsp;&#8226;&nbsp;{html.escape(str(item))}" for item in visible]
            remaining = len(items) - len(visible)
            if remaining > 0:
                lines.append(f"&nbsp;&nbsp;... and {remaining} more")
            self._items_label.setText("<br>".join(lines))
            self._items_label.show()
        else:
            self._items_label.hide()

        self._action_btn.setText(confirm_text)
        self._step = 1
        self._set_button_order(1)
        self.slide_in()

    # ── callbacks ──────────────────────────────────────────────────────

    def _on_action_clicked(self):
        if self._step == 1:
            # Advance to step 2: swap buttons, escalate message
            self._step = 2
            self._title_label.setText(f"Confirm {self._title}")
            self._message_label.setText(self._step2_message)
            self._items_label.hide()
            self._set_button_order(2)
            # Resize drawer to fit new (shorter) content
            parent = self.parent()
            if parent:
                dh = self._calculate_height()
                self.setGeometry(0, 0, parent.width(), dh)
        else:
            # Step 2: actually confirm
            self.confirmed.emit()
            self.slide_out()

    def _on_cancel_clicked(self):
        self.cancelled.emit()
        self.slide_out()

    def _disconnect_confirm(self):
        if self._on_confirm is not None:
            try:
                self.confirmed.disconnect(self._on_confirm)
            except (RuntimeError, TypeError):
                pass
            self._on_confirm = None

    # ── height calculation ─────────────────────────────────────────────

    def _calculate_height(self):
        self.layout().activate()
        hint = self.layout().sizeHint().height()
        return max(_MIN_HEIGHT, min(_MAX_HEIGHT, hint + 16))

    # ── animation ──────────────────────────────────────────────────────

    def slide_in(self):
        self.setStyleSheet(
            f"QWidget#{self.objectName()} {{"
            f"  border-bottom: 1px solid rgba(128,128,128,0.35);"
            f"}}"
            + container_qss()
            + f"PushButton#{self._btn_object_name} {{"
            f"  background: {self._btn_bg};"
            f"  color: white;"
            f"  border: none;"
            f"  border-radius: 5px;"
            f"  padding: 5px 16px;"
            f"}}"
            f"PushButton#{self._btn_object_name}:hover {{"
            f"  background: {self._btn_hover};"
            f"}}"
            f"PushButton#{self._btn_object_name}:pressed {{"
            f"  background: {self._btn_pressed};"
            f"}}"
        )

        parent = self.parent()
        if parent is None:
            return
        pw = parent.width()
        dh = self._calculate_height()
        self.setGeometry(0, -dh, pw, dh)
        self.show()
        self.raise_()
        self._run_animation(
            QtCore.QPoint(0, -dh),
            QtCore.QPoint(0, 0),
            QEasingCurve.Type.OutCubic,
        )

    def slide_out(self):
        parent = self.parent()
        if parent is None:
            self.hide()
            self._disconnect_confirm()
            return
        dh = self.height()
        anim = self._run_animation(
            self.pos(),
            QtCore.QPoint(0, -dh),
            QEasingCurve.Type.InCubic,
        )
        anim.finished.connect(self._on_slide_out_finished)

    def _on_slide_out_finished(self):
        self.hide()
        self._disconnect_confirm()

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
        self.setGeometry(0, 0, parent_size.width(), self.height())


class DeleteConfirmDrawer(_BaseConfirmDrawer):
    """Red-themed two-step delete confirmation drawer.

    Usage::

        drawer = DeleteConfirmDrawer(parent=self)

        drawer.ask(
            title="Delete Zone",
            message="Permanently delete 'example.com'?",
            items=["example.com"],
            on_confirm=lambda: self.api.delete_zone("example.com"),
            confirm_text="Delete Zone",
        )
    """

    _object_name = "deleteConfirmDrawer"
    _icon = FluentIcon.DELETE
    _icon_color = "#e04040"
    _btn_object_name = "deleteConfirmBtn"
    _btn_bg = "rgba(200,40,40,0.9)"
    _btn_hover = "rgba(220,50,50,0.95)"
    _btn_pressed = "rgba(170,30,30,0.95)"
    _step2_message = "Are you sure? This action cannot be undone."


class RestoreConfirmDrawer(_BaseConfirmDrawer):
    """Amber-themed two-step restore confirmation drawer.

    Usage::

        drawer = RestoreConfirmDrawer(parent=self)

        drawer.ask(
            title="Restore Version",
            message="Restore 'example.com' to version abc12345?",
            items=["3 A records", "1 MX record"],
            on_confirm=lambda: do_restore(),
            confirm_text="Restore",
        )
    """

    _object_name = "restoreConfirmDrawer"
    _icon = FluentIcon.INFO
    _icon_color = "#e8a838"
    _btn_object_name = "restoreConfirmBtn"
    _btn_bg = "rgba(210,150,30,0.9)"
    _btn_hover = "rgba(230,165,40,0.95)"
    _btn_pressed = "rgba(180,130,20,0.95)"
    _step2_message = "Are you sure? This will overwrite the current live DNS records."


class ConfirmDrawer(_BaseConfirmDrawer):
    """Blue-themed two-step general confirmation drawer.

    Used for non-destructive but consequential confirmations such as
    quit, switch profile, apply bulk changes, or import records.

    Usage::

        drawer = ConfirmDrawer(parent=self)

        drawer.ask(
            title="Switch Profile",
            message="Switch to 'production'? The app will restart.",
            on_confirm=lambda: do_switch(),
            confirm_text="Switch",
        )
    """

    _object_name = "confirmDrawer"
    _icon = FluentIcon.INFO
    _icon_color = "#4a9eff"
    _btn_object_name = "confirmBtn"
    _btn_bg = "rgba(50,120,220,0.9)"
    _btn_hover = "rgba(60,140,240,0.95)"
    _btn_pressed = "rgba(40,100,190,0.95)"
    _step2_message = "Are you sure you want to proceed?"
