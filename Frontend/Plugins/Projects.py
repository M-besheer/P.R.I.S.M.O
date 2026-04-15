import os
import sys
import subprocess
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QScrollArea, QFrame, QLineEdit,
                               QComboBox, QFileDialog, QInputDialog, QMessageBox, QLayout, QSizePolicy)
from PySide6.QtCore import Qt, Signal, QRect, QSize, QPoint
from PySide6.QtGui import QFont, QDesktopServices
from PySide6.QtCore import QUrl

# Import the new API Connection
from Frontend.APIs_Conn import PrismoAPI

# --- THEME CONSTANTS ---
ACCENT = "#00ECFF"
BG_PANEL = "#010101"
TEXT_DIM = "#555555"
MONO_FONT = "Consolas"


# ==========================================
# CUSTOM FLOW LAYOUT (For auto-wrapping cards)
# ==========================================
class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=10, spacing=15):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.itemList = []

    def __del__(self):
        item = self.takeAt(0)
        while item: item = self.takeAt(0)

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if 0 <= index < len(self.itemList): return self.itemList[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.itemList): return self.itemList.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.doLayout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        size += QSize(2 * self.contentsMargins().top(), 2 * self.contentsMargins().top())
        return size

    def doLayout(self, rect, testOnly):
        x, y, line_height = rect.x(), rect.y(), 0
        for item in self.itemList:
            wid = item.widget()
            space_x = self.spacing()
            space_y = self.spacing()
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0
            if not testOnly:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = next_x
            line_height = max(line_height, item.sizeHint().height())
        return y + line_height - rect.y()


# ==========================================
# THE PROJECT CARD WIDGET
# ==========================================
class ProjectCard(QFrame):
    def __init__(self, db_data, plugin_ref, available_ides):
        super().__init__()
        self.data = db_data
        self.plugin = plugin_ref

        # Fixed size for uniform grid wrapping
        self.setFixedSize(320, 160)

        # Sleek CSS styling
        self.setStyleSheet(f"""
            ProjectCard {{
                background-color: #0A0A0C;
                border: 1px solid #1A1A1D;
                border-top: 3px solid {ACCENT};
                border-radius: 8px;
            }}
            ProjectCard:hover {{
                background-color: #111115;
                border: 1px solid {ACCENT};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        # --- HEADER (Title & Status) ---
        header_layout = QHBoxLayout()

        title = QLabel(self.data["name"])
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setStyleSheet(f"color: white; border: none; background: transparent;")

        # Active Status Dot
        status_dot = QLabel("●" if self.data.get("is_active", True) else "○")
        color = "#00FF41" if self.data.get("is_active", True) else TEXT_DIM
        status_dot.setStyleSheet(f"color: {color}; font-size: 16px; border: none; background: transparent;")

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(status_dot)

        # --- PATH DISPLAY ---
        display_path = self.truncate_path(self.data["path"])
        path_lbl = QLabel(display_path)
        path_lbl.setFont(QFont(MONO_FONT, 9))
        path_lbl.setStyleSheet("color: #888; border: none; background: transparent;")

        # --- IDE SELECTION ---
        self.ide_combo = QComboBox()
        self.ide_combo.addItem("File Explorer")
        for ide in available_ides:
            self.ide_combo.addItem(ide["name"])

        self.ide_combo.setStyleSheet(f"""
            QComboBox {{ background-color: #050505; color: white; border: 1px solid #222; padding: 4px; border-radius: 4px; }}
            QComboBox::drop-down {{ border: none; }}
        """)

        # --- BUTTONS (Bottom Row) ---
        btn_layout = QHBoxLayout()

        btn_open = QPushButton("OPEN")
        btn_open.setCursor(Qt.PointingHandCursor)
        btn_open.setStyleSheet(
            f"background-color: {ACCENT}; color: black; font-weight: bold; border-radius: 4px; padding: 5px;")
        btn_open.clicked.connect(self.launch_ide)

        btn_term = QPushButton(">_")
        btn_term.setCursor(Qt.PointingHandCursor)
        btn_term.setStyleSheet(
            "background-color: #1A1A1D; color: white; font-weight: bold; border-radius: 4px; padding: 5px;")
        btn_term.clicked.connect(self.launch_terminal)

        btn_del = QPushButton("×")
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.setStyleSheet(
            "background-color: #1A1A1D; color: #FF4444; font-weight: bold; border-radius: 4px; padding: 5px; width: 25px;")
        btn_del.clicked.connect(self.delete_self)

        btn_layout.addWidget(btn_open, stretch=1)
        btn_layout.addWidget(btn_term)
        btn_layout.addWidget(btn_del)

        # Assemble Card
        layout.addLayout(header_layout)
        layout.addWidget(path_lbl)
        layout.addStretch()
        layout.addWidget(self.ide_combo)
        layout.addLayout(btn_layout)

    def truncate_path(self, path, max_chars=35):
        if len(path) <= max_chars: return path
        return "..." + path[-(max_chars - 3):]

    def launch_ide(self):
        ide_name = self.ide_combo.currentText()
        path = self.data["path"]

        if ide_name == "File Explorer":
            if sys.platform == "win32":
                os.startfile(path)
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            return

        exe_path = self.plugin.get_ide_path(ide_name)
        if exe_path:
            try:
                subprocess.Popen([exe_path, path])
            except Exception as e:
                QMessageBox.critical(self, "Execution Error", str(e))

    def launch_terminal(self):
        self.plugin.launch_request.emit(self.data["path"], "", "")

    def delete_self(self):
        # Call Backend to Delete
        success = PrismoAPI.delete_project(self.data["id"])
        if success:
            self.plugin.load_data()  # Refresh the UI


# ==========================================
# THE MAIN PLUGIN WIDGET
# ==========================================
class ProjectsPlugin(QWidget):
    launch_request = Signal(str, str, str)

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(20)

        # --- HEADER & SEARCH BAR ---
        header_layout = QHBoxLayout()

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Search projects by name or path...")
        self.search_bar.setStyleSheet(f"""
            QLineEdit {{
                background-color: #0A0A0C; color: white;
                border: 1px solid #222; border-radius: 15px;
                padding: 8px 15px; font-size: 14px;
            }}
            QLineEdit:focus {{ border: 1px solid {ACCENT}; }}
        """)
        self.search_bar.textChanged.connect(self.filter_projects)

        btn_new = QPushButton("+ NEW PROJECT")
        btn_new.setCursor(Qt.PointingHandCursor)
        btn_new.setStyleSheet(f"""
            QPushButton {{ background-color: #2CC985; color: black; font-weight: bold; padding: 8px 20px; border-radius: 15px; }}
            QPushButton:hover {{ background-color: #35E89A; }}
        """)
        btn_new.clicked.connect(self.add_new_project)

        header_layout.addWidget(self.search_bar, stretch=1)
        header_layout.addSpacing(20)
        header_layout.addWidget(btn_new)

        # --- SCROLL AREA & FLOW LAYOUT ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("background-color: transparent;")

        # Use our custom FlowLayout!
        self.flow_layout = FlowLayout(self.cards_container)
        self.scroll_area.setWidget(self.cards_container)

        self.layout.addLayout(header_layout)
        self.layout.addWidget(self.scroll_area)

        # State Variables
        self.all_projects = []
        self.available_ides = []
        self.card_widgets = []

        self.load_data()

    def load_data(self):
        """Fetches fresh data from FastAPI and renders it."""
        self.all_projects = PrismoAPI.get_projects()
        self.available_ides = PrismoAPI.get_ides()
        self.render_cards(self.all_projects)

    def render_cards(self, projects_to_show):
        """Clears the grid and draws the cards."""
        # Clear existing widgets
        for widget in self.card_widgets:
            self.flow_layout.removeWidget(widget)
            widget.deleteLater()
        self.card_widgets.clear()

        # Draw new widgets
        for proj_data in projects_to_show:
            card = ProjectCard(proj_data, self, self.available_ides)
            self.flow_layout.addWidget(card)
            self.card_widgets.append(card)

    def filter_projects(self, text):
        """Filters the cards based on the search bar text."""
        query = text.lower()
        filtered = [
            p for p in self.all_projects
            if query in p["name"].lower() or query in p["path"].lower()
        ]
        self.render_cards(filtered)

    def add_new_project(self):
        path = QFileDialog.getExistingDirectory(self, "Select Project Directory")
        if not path: return

        default_name = os.path.basename(path)
        name, ok = QInputDialog.getText(self, "New Project", "Enter Project Name:", QLineEdit.Normal, default_name)

        if ok and name:
            # Send to FastAPI Backend!
            result = PrismoAPI.create_project(name, path)
            if result:
                self.search_bar.clear()
                self.load_data()  # Refresh UI
            else:
                QMessageBox.warning(self, "API Error", "Could not save project. Is the backend running?")

    def get_ide_path(self, ide_name):
        """Finds the executable path from the backend IDEs list."""
        for ide in self.available_ides:
            if ide["name"] == ide_name:
                return ide["path"]

        # If it's a new IDE, ask the user to find it
        exe_path, _ = QFileDialog.getOpenFileName(self, f"Select {ide_name} Executable", "",
                                                  "Executables (*.exe);;All Files (*.*)")
        if exe_path:
            PrismoAPI.add_ide(ide_name, exe_path)
            self.load_data()  # Refresh to get the new IDE
            return exe_path

        return None