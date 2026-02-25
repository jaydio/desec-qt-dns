#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Top-sliding notification drawer for error, warning, info, and success messages.

Replaces QMessageBox popups with a non-modal, animated drawer that slides
down from the top of its parent widget.  Follows the same architectural
pattern as DeleteConfirmDrawer and the right-sliding drawer panels.
"""

import logging
from enum import Enum, auto

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from qfluentwidgets import PushButton, SubtitleLabel, FluentIcon, isDarkTheme
from fluent_styles import container_qss

logger = logging.getLogger(__name__)

_MIN_HEIGHT = 90
_MAX_HEIGHT = 240


class NotifyLevel(Enum):
    ERROR = auto()
    WARNING = auto()
    INFO = auto()
    SUCCESS = auto()


_LEVEL_ICONS = {
    NotifyLevel.ERROR:   (FluentIcon.CLOSE, "#e04040"),
    NotifyLevel.WARNING: (FluentIcon.INFO,  "#e8a838"),
    NotifyLevel.INFO:    (FluentIcon.INFO,  "#4a9eff"),
    NotifyLevel.SUCCESS: (FluentIcon.ACCEPT, "#4caf50"),
}


class NotifyDrawer(QtWidgets.QWidget):
    """Top-sliding notification drawer.

    Usage::

        drawer = NotifyDrawer(parent=self)
        drawer.show_message("Load Failed", "Could not load tokens.", NotifyLevel.ERROR)
    """

    dismissed = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("notifyDrawer")
        self._animation = None
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

        self._icon_label = QtWidgets.QLabel()
        self._icon_label.setFixedSize(32, 32)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        content_row.addWidget(self._icon_label)

        text_col = QtWidgets.QVBoxLayout()
        text_col.setSpacing(4)

        self._title_label = SubtitleLabel("")
        text_col.addWidget(self._title_label)

        self._message_label = QtWidgets.QLabel("")
        self._message_label.setWordWrap(True)
        text_col.addWidget(self._message_label)

        content_row.addLayout(text_col, 1)
        root.addLayout(content_row, 1)

        # ── button row ────────────────────────────────────────────────
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()

        self._dismiss_btn = PushButton("OK")
        self._dismiss_btn.clicked.connect(self._on_dismiss)
        btn_row.addWidget(self._dismiss_btn)

        root.addLayout(btn_row)

        # ── ESC shortcut ──────────────────────────────────────────────
        esc = QtGui.QShortcut(QtGui.QKeySequence(Qt.Key.Key_Escape), self)
        esc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        esc.activated.connect(self._on_dismiss)

    # ── public API ─────────────────────────────────────────────────────

    def show_message(self, title, message, level=NotifyLevel.ERROR):
        """Show the drawer with the given notification.

        Args:
            title:   Drawer heading (e.g. "Load Failed").
            message: Descriptive text.
            level:   NotifyLevel enum value.
        """
        self._title_label.setText(title)
        self._message_label.setText(message)

        icon_enum, color = _LEVEL_ICONS.get(level, _LEVEL_ICONS[NotifyLevel.ERROR])
        self._icon_label.setPixmap(
            icon_enum.icon(color=QtGui.QColor(color)).pixmap(28, 28)
        )

        self.slide_in()

    # convenience shortcuts
    def error(self, title, message):
        self.show_message(title, message, NotifyLevel.ERROR)

    def warning(self, title, message):
        self.show_message(title, message, NotifyLevel.WARNING)

    def info(self, title, message):
        self.show_message(title, message, NotifyLevel.INFO)

    def success(self, title, message):
        self.show_message(title, message, NotifyLevel.SUCCESS)

    # ── callbacks ──────────────────────────────────────────────────────

    def _on_dismiss(self):
        self.dismissed.emit()
        self.slide_out()

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
            return
        dh = self.height()
        anim = self._run_animation(
            self.pos(),
            QtCore.QPoint(0, -dh),
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
        self.setGeometry(0, 0, parent_size.width(), self.height())
