#!/usr/bin/env python3
"""
Commands Center - Desktop Controller
Modern, clean interface for managing Android Commands Center
"""

import sys
import json
import asyncio
import threading
import subprocess
import urllib.request
import os
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Callable
from enum import Enum, auto

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QLineEdit, QLabel, QFrame, QDialog,
    QListWidget, QListWidgetItem, QStyledItemDelegate, QStyle,
    QSystemTrayIcon, QMenu, QColorDialog, QScrollArea, QSizePolicy,
    QGraphicsDropShadowEffect, QSpacerItem, QStackedWidget
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QRect, QTimer, QPropertyAnimation, QEasingCurve, QObject
from PySide6.QtGui import (
    QIcon, QColor, QPalette, QFont, QFontDatabase, QPainter, QBrush,
    QAction, QPixmap, QLinearGradient, QGradient, QFontMetrics
)
import websockets
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

FONT_URL = "https://github.com/google/material-design-icons/raw/master/font/MaterialIcons-Regular.ttf"
CODEPOINTS_URL = "https://github.com/google/material-design-icons/raw/master/font/MaterialIcons-Regular.codepoints"
FONT_PATH = "MaterialIcons-Regular.ttf"
CODEPOINTS_PATH = "MaterialIcons-Regular.codepoints"
ICON_PNG_PATH = "icon.png"

COLORS = {
    'bg_dark': '#0A0C14',
    'bg_card': '#161926',
    'bg_input': '#1A1D2E',
    'border': '#2A2D3E',
    'border_hover': '#3A3D4E',
    'accent': '#00E5FF',
    'accent_hover': '#33EBFF',
    'text': '#E1E3DF',
    'text_muted': '#888B94',
    'success': '#00FF44',
    'error': '#FF4444',
    'warning': '#FFB800'
}

ICON_DATA: Dict[str, str] = {}
APP_FONT_FAMILY = "Material Icons"

@dataclass
class ButtonConfig:
    icon_name: str = "Settings"
    toggle_icon_name: str = ""
    command: str = "echo 'Hello'"
    notification_text: str = "Done"
    is_toggle: bool = False
    check_command: str = ""
    active_color: str = "#00E5FF"
    is_toggled: bool = False

    def to_dict(self) -> dict:
        return {
            'iconName': self.icon_name,
            'toggleIconName': self.toggle_icon_name,
            'command': self.command,
            'notificationText': self.notification_text,
            'isToggle': self.is_toggle,
            'checkCommand': self.check_command,
            'activeColor': self.active_color,
            'isToggled': self.is_toggled
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ButtonConfig':
        return cls(
            icon_name=data.get('iconName', 'Settings'),
            toggle_icon_name=data.get('toggleIconName', ''),
            command=data.get('command', "echo 'Hello'"),
            notification_text=data.get('notificationText', 'Done'),
            is_toggle=data.get('isToggle', False),
            check_command=data.get('checkCommand', ''),
            active_color=data.get('activeColor', '#00E5FF'),
            is_toggled=data.get('isToggled', False)
        )


@dataclass
class AppConfig:
    ip: str = "192.168.1.15"
    password: str = "admin"
    buttons: List[ButtonConfig] = None

    def __post_init__(self):
        if self.buttons is None:
            self.buttons = [ButtonConfig() for _ in range(9)]

    def to_dict(self) -> dict:
        return {
            'ip': self.ip,
            'password': self.password,
            'buttons': [b.to_dict() for b in self.buttons]
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'AppConfig':
        return cls(
            ip=data.get('ip', '192.168.1.15'),
            password=data.get('password', 'admin'),
            buttons=[ButtonConfig.from_dict(b) for b in data.get('buttons', [])]
        )

class ConnectionState(Enum):
    DISCONNECTED = auto()
    CONNECTING = auto()
    AUTHENTICATING = auto()
    CONNECTED = auto()
    ERROR = auto()


class ConnectionManager(QObject):
    """Handles WebSocket connection lifecycle"""
    state_changed = Signal(ConnectionState)
    message_received = Signal(str)
    error_occurred = Signal(str)

    def __init__(self):
        super().__init__()
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._state = ConnectionState.DISCONNECTED
        self._thread: Optional[threading.Thread] = None
        self._ip = ""
        self._password = ""

    @property
    def state(self) -> ConnectionState:
        return self._state

    def _set_state(self, state: ConnectionState):
        self._state = state
        self.state_changed.emit(state)

    def start_connection(self, ip: str, password: str):
        if self._state in (ConnectionState.CONNECTING, ConnectionState.CONNECTED):
            return

        self._ip = ip
        self._password = password
        self._set_state(ConnectionState.CONNECTING)

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def disconnect(self):
        if self.ws:
            asyncio.run_coroutine_threadsafe(self._close_ws(), self.loop)
        self._set_state(ConnectionState.DISCONNECTED)

    def _run_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._ws_worker())
        except websockets.exceptions.ConnectionClosedOK:
            pass
        except Exception as e:
            self.error_occurred.emit(str(e))
            self._set_state(ConnectionState.ERROR)

    async def _ws_worker(self):
        try:
            uri = f"ws://{self._ip}:8080/ws"
            async with websockets.connect(uri) as ws:
                self.ws = ws
                self._set_state(ConnectionState.AUTHENTICATING)

                while True:
                    msg = await ws.recv()
                    self._handle_message(msg)
        except ConnectionClosedOK:
            self._set_state(ConnectionState.DISCONNECTED)
            self.ws = None
        except ConnectionClosedError as e:
            self.error_occurred.emit(f"Connection closed unexpectedly: {e}")
            self._set_state(ConnectionState.ERROR)
            self.ws = None
        except Exception as e:
            self.error_occurred.emit(str(e))
            self._set_state(ConnectionState.ERROR)
            self.ws = None

    def _handle_message(self, msg: str):
        if msg == "AUTH_REQUIRED":
            asyncio.create_task(self.ws.send(f"AUTH:{self._password}"))
        elif msg == "AUTH_SUCCESS":
            self._set_state(ConnectionState.CONNECTED)
        elif msg.startswith("CMD:"):
            self.message_received.emit(msg)

    async def _close_ws(self):
        if self.ws:
            await self.ws.close()
            self.ws = None

    def send(self, data: dict):
        if self.ws and self._state == ConnectionState.CONNECTED:
            asyncio.run_coroutine_threadsafe(
                self.ws.send(json.dumps(data)), self.loop
            )

class ModernButton(QPushButton):
    """Styled button with hover effects"""
    def __init__(self, text: str = "", icon: str = "", parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setCursor(Qt.PointingHandCursor)
        self._icon = icon
        self._setup_style()

    def _setup_style(self):
        self.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLORS['bg_input']}, stop:1 {COLORS['bg_card']});
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
                padding: 12px 24px;
                color: {COLORS['text']};
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLORS['border']}, stop:1 {COLORS['bg_input']});
                border: 1px solid {COLORS['accent']};
            }}
            QPushButton:pressed {{
                background: {COLORS['bg_card']};
            }}
        """)


class ActionButton(QPushButton):
    """Primary action button with accent color"""
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self._is_connected = False
        self._update_style()

    def set_connected(self, connected: bool):
        self._is_connected = connected
        self._update_style()

    def _update_style(self):
        color = COLORS['error'] if self._is_connected else COLORS['accent']
        hover = '#FF6666' if self._is_connected else COLORS['accent_hover']
        text_color = COLORS['bg_dark'] if not self._is_connected else COLORS['text']

        self.setStyleSheet(f"""
            QPushButton {{
                background: {color};
                border: none;
                border-radius: 12px;
                padding: 15px 30px;
                color: {text_color};
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: {hover};
            }}
            QPushButton:pressed {{
                background: {color};
            }}
        """)


class StatusIndicator(QLabel):
    """Animated connection status indicator"""
    def __init__(self, parent=None):
        super().__init__("● Disconnected", parent)
        self._setup_animation()
        self._update_style(COLORS['text_muted'])

    def _setup_animation(self):
        self._animation = QPropertyAnimation(self, b"styleSheet")
        self._animation.setDuration(1000)
        self._animation.setEasingCurve(QEasingCurve.InOutSine)

    def set_status(self, text: str, color: str):
        self.setText(f"● {text}")
        self._update_style(color)

    def _update_style(self, color: str):
        self.setStyleSheet(f"""
            color: {color};
            font-weight: bold;
            font-size: 13px;
            padding: 8px 0;
        """)


class ButtonEditorCard(QFrame):
    """Card for editing a single button"""
    icon_changed = Signal(int, str, str)
    color_changed = Signal(int, str)
    mode_changed = Signal(int, bool)

    def __init__(self, index: int, config: ButtonConfig, parent=None):
        super().__init__(parent)
        self.index = index
        self.config = config
        self._setup_ui()

    def _setup_ui(self):
        self.setObjectName("BtnCard")
        self.setStyleSheet(f"""
            QFrame#BtnCard {{
                background: {COLORS['bg_card']};
                border-radius: 20px;
                border: 1px solid {COLORS['border']};
            }}
            QFrame#BtnCard:hover {{
                border: 1px solid {COLORS['border_hover']};
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()

        self.main_icon_btn = QPushButton()
        self.main_icon_btn.setFixedSize(50, 50)
        self.main_icon_btn.setCursor(Qt.PointingHandCursor)
        self.main_icon_btn.clicked.connect(lambda: self._pick_icon(False))
        self._update_icon_btn(self.main_icon_btn, self.config.icon_name)
        header.addWidget(self.main_icon_btn)

        self.toggle_icon_btn = QPushButton()
        self.toggle_icon_btn.setFixedSize(50, 50)
        self.toggle_icon_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_icon_btn.clicked.connect(lambda: self._pick_icon(True))
        self._update_icon_btn(self.toggle_icon_btn, self.config.toggle_icon_name)
        self.toggle_icon_btn.setVisible(self.config.is_toggle)
        header.addWidget(self.toggle_icon_btn)

        header.addStretch()

        self.mode_btn = QPushButton("⚡ Toggle" if self.config.is_toggle else "🔘 Press")
        self.mode_btn.setFixedWidth(80)
        self.mode_btn.setCursor(Qt.PointingHandCursor)
        self.mode_btn.setStyleSheet(f"""
            QPushButton {{
                background: {'#2A4D3E' if self.config.is_toggle else '#2A2D3E'};
                border-radius: 8px;
                padding: 8px;
                font-size: 10px;
                font-weight: bold;
                color: {COLORS['success'] if self.config.is_toggle else COLORS['text']};
            }}
        """)
        self.mode_btn.clicked.connect(self._toggle_mode)
        header.addWidget(self.mode_btn)

        layout.addLayout(header)

        self.cmd_input = QLineEdit(self.config.command)
        self.cmd_input.setPlaceholderText("Command to execute...")
        self.cmd_input.textChanged.connect(lambda t: self._update_config('command', t))
        self._style_input(self.cmd_input)
        layout.addWidget(self.cmd_input)

        self.notif_input = QLineEdit(self.config.notification_text)
        self.notif_input.setPlaceholderText("Notification message...")
        self.notif_input.textChanged.connect(lambda t: self._update_config('notification_text', t))
        self._style_input(self.notif_input, muted=True)
        layout.addWidget(self.notif_input)

        bottom = QHBoxLayout()

        self.check_input = QLineEdit(self.config.check_command)
        self.check_input.setPlaceholderText("State check command...")
        self.check_input.textChanged.connect(lambda t: self._update_config('check_command', t))
        self._style_input(self.check_input, accent=True)
        bottom.addWidget(self.check_input)

        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(24, 24)
        self.color_btn.setCursor(Qt.PointingHandCursor)
        self._update_color_btn()
        self.color_btn.clicked.connect(self._pick_color)
        bottom.addWidget(self.color_btn)

        layout.addLayout(bottom)

    def _style_input(self, input_field: QLineEdit, muted: bool = False, accent: bool = False):
        color = COLORS['text_muted'] if muted else COLORS['accent'] if accent else COLORS['text']
        input_field.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS['bg_dark']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 8px;
                color: {color};
                font-size: 11px;
                max-height: 28px;
            }}
            QLineEdit:focus {{
                border: 1px solid {COLORS['accent']};
            }}
        """)

    def _update_icon_btn(self, btn: QPushButton, name: str):
        if not name:
            btn.setText("+")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['bg_input']};
                    border: 2px dashed {COLORS['border']};
                    border-radius: 10px;
                    color: {COLORS['text_muted']};
                    font-size: 20px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    border: 2px dashed {COLORS['accent']};
                    color: {COLORS['accent']};
                }}
            """)
        elif ord(name[0]) > 127:
            btn.setText(name)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['bg_input']};
                    border: 2px solid {self.config.active_color};
                    border-radius: 10px;
                    font-size: 22px;
                }}
            """)
        else:
            btn.setText(ICON_DATA.get(name, "?"))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['bg_input']};
                    border: 2px solid {self.config.active_color};
                    border-radius: 10px;
                    color: {self.config.active_color};
                    font-family: '{APP_FONT_FAMILY}';
                    font-size: 22px;
                }}
            """)

    def _update_color_btn(self):
        self.color_btn.setStyleSheet(f"""
            QPushButton {{
                background: {self.config.active_color};
                border-radius: 12px;
                border: 2px solid white;
            }}
            QPushButton:hover {{
                border: 2px solid {COLORS['accent']};
            }}
        """)

    def _toggle_mode(self):
        self.config.is_toggle = not self.config.is_toggle
        self.toggle_icon_btn.setVisible(self.config.is_toggle)
        self.mode_changed.emit(self.index, self.config.is_toggle)

        self.mode_btn.setText("⚡ Toggle" if self.config.is_toggle else "🔘 Press")
        self.mode_btn.setStyleSheet(f"""
            QPushButton {{
                background: {'#2A4D3E' if self.config.is_toggle else '#2A2D3E'};
                border-radius: 8px;
                padding: 8px;
                font-size: 10px;
                font-weight: bold;
                color: {COLORS['success'] if self.config.is_toggle else COLORS['text']};
            }}
        """)

    def _pick_icon(self, is_toggle: bool):
        key = 'toggle_icon_name' if is_toggle else 'icon_name'
        current = getattr(self.config, key)

        picker = IconPicker(initial_text=current, parent=self)
        if picker.exec():
            new_icon = picker.selected_icon
            setattr(self.config, key, new_icon)
            self.icon_changed.emit(self.index, key, new_icon)

            if is_toggle:
                self._update_icon_btn(self.toggle_icon_btn, new_icon)
            else:
                self._update_icon_btn(self.main_icon_btn, new_icon)

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(self.config.active_color), self)
        if color.isValid():
            hex_color = color.name().upper()
            self.config.active_color = hex_color
            self._update_color_btn()
            self._update_icon_btn(self.main_icon_btn, self.config.icon_name)
            self._update_icon_btn(self.toggle_icon_btn, self.config.toggle_icon_name)
            self.color_changed.emit(self.index, hex_color)

    def _update_config(self, key: str, value: str):
        setattr(self.config, key, value)

class CommandsCenterWindow(QMainWindow):
    """Main application window"""
    sync_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Commands Center")
        self.setMinimumSize(800, 600)
        self.resize(800, 600)

        if os.path.exists(ICON_PNG_PATH):
            self.setWindowIcon(QIcon(ICON_PNG_PATH))

        self.config = self._load_config()
        self.conn = ConnectionManager()
        self._setup_ui()
        self._setup_tray()
        self._connect_signals()
        self._start_polling()

    def _load_config(self) -> AppConfig:
        try:
            with open("config.json", "r") as f:
                return AppConfig.from_dict(json.load(f))
        except:
            return AppConfig()

    def _save_config(self):
        with open("config.json", "w") as f:
            json.dump(self.config.to_dict(), f, indent=4)

    def _setup_ui(self):
        self.setStyleSheet(f"""
            QMainWindow {{
                background: {COLORS['bg_dark']};
            }}
            QLabel {{
                color: {COLORS['text']};
                font-weight: bold;
            }}
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: {COLORS['bg_card']};
                width: 12px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['border']};
                border-radius: 6px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {COLORS['accent']};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        header = self._create_header()
        main_layout.addLayout(header)

        content = self._create_content()
        main_layout.addLayout(content, 1)

    def _create_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(15)

        logo = QLabel("COMMANDS CENTER")
        logo.setFont(QFont("Arial", 18, QFont.Bold))
        logo.setStyleSheet(f"color: {COLORS['accent']};")
        layout.addWidget(logo)

        layout.addStretch()

        self.status_indicator = StatusIndicator()
        layout.addWidget(self.status_indicator)

        self.conn_btn = ModernButton("Connection")
        self.conn_btn.clicked.connect(self._show_connection_dialog)
        layout.addWidget(self.conn_btn)

        return layout

    def _show_connection_dialog(self):
        dialog = ConnectionDialog(
            self,
            self.config.ip,
            self.config.password,
            self.conn.state == ConnectionState.CONNECTED
        )
        dialog.connect_clicked.connect(self._on_dialog_connect)
        dialog.disconnect_clicked.connect(self._on_dialog_disconnect)
        dialog.exec()

    def _on_dialog_connect(self, ip: str, password: str):
        self.config.ip = ip
        self.config.password = password
        self._save_config()
        self.conn.start_connection(ip, password)

    def _on_dialog_disconnect(self):
        self.conn.disconnect()

    def _create_content(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(15)

        header = QLabel("Dashboard Preview")
        header.setFont(QFont("Arial", 14, QFont.Bold))
        header.setStyleSheet(f"color: {COLORS['text']};")
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        grid_widget = QWidget()
        self.grid_layout = QGridLayout(grid_widget)
        self.grid_layout.setSpacing(15)
        self.grid_layout.setContentsMargins(5, 5, 5, 5)

        self.button_cards = []
        for i in range(9):
            card = ButtonEditorCard(i, self.config.buttons[i])
            card.icon_changed.connect(self._on_icon_changed)
            card.color_changed.connect(self._on_color_changed)
            card.mode_changed.connect(self._on_mode_changed)
            self.grid_layout.addWidget(card, i // 3, i % 3)
            self.button_cards.append(card)

        scroll.setWidget(grid_widget)
        layout.addWidget(scroll, 1)

        return layout

    def _style_input(self, input_field: QLineEdit):
        input_field.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS['bg_input']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
                padding: 12px;
                color: {COLORS['text']};
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 2px solid {COLORS['accent']};
            }}
        """)

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        if os.path.exists(ICON_PNG_PATH):
            self.tray.setIcon(QIcon(ICON_PNG_PATH))

        menu = QMenu()
        show_action = QAction("Open", self)
        show_action.triggered.connect(self.show)
        quit_action = QAction("Exit", self)
        quit_action.triggered.connect(QApplication.quit)

        menu.addAction(show_action)
        menu.addSeparator()
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.show()

    def _connect_signals(self):
        self.conn.state_changed.connect(self._on_state_changed)
        self.conn.error_occurred.connect(self._on_error)
        self.conn.message_received.connect(self._on_message)

    def _start_polling(self):
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll_states)
        self.poll_timer.start(2000)

    def _on_state_changed(self, state: ConnectionState):
        states = {
            ConnectionState.DISCONNECTED: ("Disconnected", COLORS['text_muted']),
            ConnectionState.CONNECTING: ("Connecting...", COLORS['warning']),
            ConnectionState.AUTHENTICATING: ("Authenticating...", COLORS['warning']),
            ConnectionState.CONNECTED: ("Connected", COLORS['success']),
            ConnectionState.ERROR: ("Error", COLORS['error'])
        }
        text, color = states.get(state, ("Unknown", COLORS['text_muted']))
        self.status_indicator.set_status(text, color)

        if state == ConnectionState.CONNECTED:
            self._sync_config()

    def _on_error(self, msg: str):
        print(f"Connection error: {msg}")

    def _on_message(self, msg: str):
        if msg.startswith("CMD:"):
            parts = msg[4:].split("|NOTIF:")
            subprocess.Popen(parts[0], shell=True)
            if len(parts) > 1:
                subprocess.Popen(f'notify-send "Commands Center" "{parts[1]}"', shell=True)
            QTimer.singleShot(500, self._poll_states)

    def _on_icon_changed(self, index: int, key: str, value: str):
        self._save_config()
        self._sync_config()

    def _on_color_changed(self, index: int, color: str):
        self._save_config()
        self._sync_config()

    def _on_mode_changed(self, index: int, is_toggle: bool):
        self._save_config()
        self._sync_config()

    def _sync_config(self):
        self.conn.send({"buttons": [b.to_dict() for b in self.config.buttons]})

    def _poll_states(self):
        changed = False
        for btn in self.config.buttons:
            if btn.is_toggle and btn.check_command:
                try:
                    result = subprocess.call(
                        btn.check_command,
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    is_on = (result == 0)
                    if btn.is_toggled != is_on:
                        btn.is_toggled = is_on
                        changed = True
                except:
                    pass

        if changed:
            self._save_config()
            self._sync_config()

    def closeEvent(self, event):
        if self.tray.isVisible():
            self.hide()
            event.ignore()
        else:
            self.conn.disconnect()
            event.accept()

class IconPicker(QDialog):
    """Dialog for selecting icons"""
    def __init__(self, initial_text: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Icon Library")
        self.resize(660, 550)
        self.selected_icon = initial_text
        self._setup_ui()
        self.setStyleSheet(f"""
            QDialog {{
                background: {COLORS['bg_dark']};
            }}
            QListWidget {{
                background: transparent;
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                background: transparent;
                border-radius: 12px;
            }}
            QListWidget::item:selected {{
                background: {COLORS['accent']}40;
                border: 2px solid {COLORS['accent']};
            }}
            QListWidget::item:hover {{
                background: {COLORS['border']};
            }}
        """)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        search_layout = QHBoxLayout()
        self.search = QLineEdit(self.selected_icon)
        self.search.setPlaceholderText("🔍 Search icons or paste emoji...")
        self.search.textChanged.connect(self._filter)
        self.search.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS['bg_input']};
                border: 2px solid {COLORS['border']};
                border-radius: 12px;
                padding: 15px;
                color: {COLORS['text']};
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 2px solid {COLORS['accent']};
            }}
        """)
        search_layout.addWidget(self.search, 4)

        custom_btn = ModernButton("Use Custom / Emoji")
        custom_btn.clicked.connect(self._use_custom)
        search_layout.addWidget(custom_btn, 1)

        layout.addLayout(search_layout)

        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.IconMode)
        self.list_widget.setResizeMode(QListWidget.Adjust)
        self.list_widget.setFlow(QListWidget.LeftToRight)
        self.list_widget.setWrapping(True)
        self.list_widget.setItemDelegate(IconItemDelegate())
        self.list_widget.setSpacing(8)
        self.list_widget.itemClicked.connect(self._on_select)
        layout.addWidget(self.list_widget)

        self.all_items = []
        for name in sorted(ICON_DATA.keys()):
            item = QListWidgetItem(name)
            self.list_widget.addItem(item)
            self.all_items.append(item)

        if self.selected_icon in ICON_DATA:
            for item in self.all_items:
                if item.text() == self.selected_icon:
                    self.list_widget.setCurrentItem(item)
                    break

    def _filter(self, text: str):
        search = text.lower()
        self.list_widget.setUpdatesEnabled(False)
        for item in self.all_items:
            item.setHidden(search not in item.text().lower())
        self.list_widget.setUpdatesEnabled(True)

    def _use_custom(self):
        text = self.search.text().strip()
        if text:
            self.selected_icon = text
            self.accept()

    def _on_select(self, item):
        self.selected_icon = item.text()
        self.accept()


class IconItemDelegate(QStyledItemDelegate):
    """Custom rendering for icon items"""
    def paint(self, painter, option, index):
        name = index.data(Qt.DisplayRole)
        is_material = name in ICON_DATA
        glyph = ICON_DATA.get(name, name)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        if option.state & QStyle.State_Selected:
            bg = QColor(COLORS['accent'])
            bg.setAlpha(60)
            border = QColor(COLORS['accent'])
        elif option.state & QStyle.State_MouseOver:
            bg = QColor(COLORS['border'])
            border = QColor(COLORS['border_hover'])
        else:
            bg = QColor(COLORS['bg_card'])
            border = QColor(COLORS['border'])

        rect = option.rect.adjusted(4, 4, -4, -4)
        painter.fillRect(rect, bg)
        painter.setPen(border)
        painter.drawRoundedRect(rect, 12, 12)

        icon_rect = QRect(rect.x(), rect.y(), rect.width(), rect.height() - 30)
        font = QFont(APP_FONT_FAMILY, 28) if is_material else QFont("Arial", 24)
        painter.setFont(font)
        painter.setPen(QColor(COLORS['accent']))
        painter.drawText(icon_rect, Qt.AlignCenter, glyph)

        label_rect = QRect(rect.x() + 2, rect.bottom() - 28, rect.width() - 4, 24)
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor(COLORS['text']))
        painter.drawText(label_rect, Qt.AlignCenter | Qt.TextSingleLine, name)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(110, 100)

def initialize_resources():
    """Download and load Material Icons font"""
    global APP_FONT_FAMILY, ICON_DATA

    if not os.path.exists(FONT_PATH):
        try:
            urllib.request.urlretrieve(FONT_URL, FONT_PATH)
        except Exception as e:
            print(f"Failed to download font: {e}")

    if not os.path.exists(CODEPOINTS_PATH):
        try:
            urllib.request.urlretrieve(CODEPOINTS_URL, CODEPOINTS_PATH)
        except Exception as e:
            print(f"Failed to download codepoints: {e}")

    if os.path.exists(FONT_PATH):
        font_id = QFontDatabase.addApplicationFont(FONT_PATH)
        if font_id != -1:
            APP_FONT_FAMILY = QFontDatabase.applicationFontFamilies(font_id)[0]

    if os.path.exists(CODEPOINTS_PATH):
        with open(CODEPOINTS_PATH, "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 2:
                    name = "".join(x.capitalize() for x in parts[0].lower().split("_"))
                    ICON_DATA[name] = chr(int(parts[1], 16))

class ConnectionDialog(QDialog):
    """Dialog for connection settings"""
    connect_clicked = Signal(str, str)
    disconnect_clicked = Signal()

    def __init__(self, parent=None, ip="", password="", is_connected=False):
        super().__init__(parent)
        self.setWindowTitle("Connection Settings")
        self.resize(400, 300)
        self._is_connected = is_connected
        self._setup_ui(ip, password)
        self.setStyleSheet(f"""
            QDialog {{
                background: {COLORS['bg_dark']};
            }}
        """)

    def _setup_ui(self, ip, password):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Connection")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setStyleSheet(f"color: {COLORS['accent']};")
        layout.addWidget(title)

        ip_layout = QVBoxLayout()
        ip_label = QLabel("Device IP")
        ip_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        ip_layout.addWidget(ip_label)
        self.ip_input = QLineEdit(ip)
        self.ip_input.setPlaceholderText("192.168.1.15")
        self._style_input(self.ip_input)
        ip_layout.addWidget(self.ip_input)
        layout.addLayout(ip_layout)

        pass_layout = QVBoxLayout()
        pass_label = QLabel("Password")
        pass_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        pass_layout.addWidget(pass_label)
        self.pass_input = QLineEdit(password)
        self.pass_input.setPlaceholderText("admin")
        self.pass_input.setEchoMode(QLineEdit.Password)
        self._style_input(self.pass_input)
        pass_layout.addWidget(self.pass_input)
        layout.addLayout(pass_layout)

        self.status_label = QLabel("● Connected" if self._is_connected else "● Disconnected")
        self.status_label.setStyleSheet(f"color: {'#00FF44' if self._is_connected else COLORS['text_muted']}; font-weight: bold;")
        layout.addWidget(self.status_label)

        layout.addStretch()

        btn_layout = QHBoxLayout()

        if self._is_connected:
            self.action_btn = ActionButton("Disconnect")
            self.action_btn.setFixedHeight(40)
            self.action_btn.clicked.connect(self._on_disconnect)
        else:
            self.action_btn = ActionButton("Connect")
            self.action_btn.set_connected(False)
            self.action_btn.setFixedHeight(40)
            self.action_btn.clicked.connect(self._on_connect)

        btn_layout.addWidget(self.action_btn)
        btn_layout.addStretch()

        close_btn = ModernButton("Close")
        close_btn.setFixedHeight(40)
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _style_input(self, input_field: QLineEdit):
        input_field.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS['bg_input']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
                padding: 12px;
                color: {COLORS['text']};
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 2px solid {COLORS['accent']};
            }}
        """)

    def _on_connect(self):
        self.connect_clicked.emit(self.ip_input.text(), self.pass_input.text())
        self.accept()

    def _on_disconnect(self):
        self.disconnect_clicked.emit()
        self.accept()

    def update_status(self, connected: bool, text: str = ""):
        self._is_connected = connected
        self.status_label.setText(f"● {text}")
        self.status_label.setStyleSheet(f"color: {'#00FF44' if connected else COLORS['text_muted']}; font-weight: bold;")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    font = QFont("Segoe UI", 10)
    app.setFont(font)

    initialize_resources()

    window = CommandsCenterWindow()
    window.show()

    sys.exit(app.exec())
