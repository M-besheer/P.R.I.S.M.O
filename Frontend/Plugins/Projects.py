import os
import json
import sys
import subprocess
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QScrollArea, QFrame, QLineEdit,
                               QComboBox, QFileDialog, QInputDialog, QMessageBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QDesktopServices
from PySide6.QtCore import QUrl

# --- CONFIG FILES & CONSTANTS ---
ACCENT = "#00ECFF"
BG_PANEL = "#010101"
TEXT_DIM = "#444444"
MONO_FONT = "Consolas"

PROJECTS_FILE = "projects.json"
IDE_CONFIG_FILE = "ide_paths.json"

SUPPORTED_IDES = [
    "File Explorer",
    "VS Code",
    "Visual Studio",
    "IntelliJ IDEA",
    "PyCharm",
    "Eclipse",
    "Arduino",
    "IAR Embedded Workbench",
    "Cursor"
]


class ProjectCard(QFrame):
    """The visual HUD card for a single project."""

    def __init__(self, index, data, plugin_ref):
        super().__init__()
        self.index = index
        self.data = data
        self.plugin = plugin_ref

        self.setStyleSheet(f"""
            QFrame {{ background-color: #050505; border: 1px solid #222; border-left: 3px solid {ACCENT}; border-radius: 5px; margin-bottom: 10px; }}
            QFrame:hover {{ background-color: #0A0A0A; border-left: 4px solid {ACCENT}; }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)

        # --- 1. INFO & SNAPSHOT (Left Side) ---
        info_frame = QVBoxLayout()

        title = QLabel(data["name"].upper())
        title.setStyleSheet(f"color: {ACCENT}; font-weight: bold; font-size: 16px; border: none;")
        title.setFont(QFont("Arial", 12, QFont.Bold))

        display_path = self.truncate_path(data["path"])
        path_lbl = QLabel(display_path)
        path_lbl.setStyleSheet("color: #888888; border: none;")
        path_lbl.setFont(QFont(MONO_FONT, 10))

        # The Snapshot Input (Auto-saves when you click away or hit enter)
        self.snapshot_input = QLineEdit(data.get("snapshot", ""))
        self.snapshot_input.setPlaceholderText("Dev Snapshot: What were you working on last?")
        self.snapshot_input.setStyleSheet(
            f"background-color: #010201; color: #00FF41; border: 1px solid #113311; padding: 4px;")
        self.snapshot_input.setFont(QFont(MONO_FONT, 9))
        self.snapshot_input.editingFinished.connect(self.save_snapshot)

        info_frame.addWidget(title)
        info_frame.addWidget(path_lbl)
        info_frame.addWidget(self.snapshot_input)

        # --- 2. CONTROLS (Right Side) ---
        ctrl_frame = QHBoxLayout()
        ctrl_frame.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # IDE Dropdown
        self.ide_combo = QComboBox()
        self.ide_combo.addItems(SUPPORTED_IDES)
        self.ide_combo.setCurrentText(data.get("default_ide", "File Explorer"))
        self.ide_combo.setStyleSheet(f"""
            QComboBox {{ background-color: #030303; color: white; border: 1px solid #222; padding: 4px; font-family: {MONO_FONT}; width: 150px;}}
            QComboBox QAbstractItemView {{ background-color: #030303; color: {ACCENT}; }}
        """)
        self.ide_combo.currentTextChanged.connect(self.update_ide)

        # Open Button (External Launch)
        btn_open = QPushButton("OPEN")
        btn_open.setCursor(Qt.PointingHandCursor)
        btn_open.setStyleSheet(
            f"background-color: {ACCENT}; color: black; font-weight: bold; padding: 6px 15px; border-radius: 3px;")
        btn_open.clicked.connect(self.launch_ide)

        # Terminal Button (Internal PRISMO Tab)
        btn_term = QPushButton(">_")
        btn_term.setCursor(Qt.PointingHandCursor)
        btn_term.setStyleSheet(
            f"background-color: transparent; color: white; border: 1px solid {TEXT_DIM}; padding: 6px 10px; font-weight: bold;")
        btn_term.clicked.connect(self.launch_terminal)

        # Delete Button
        btn_del = QPushButton("X")
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.setStyleSheet(
            "background-color: transparent; color: #FF4444; border: 1px solid #FF4444; padding: 6px 10px; font-weight: bold;")
        btn_del.clicked.connect(lambda: self.plugin.remove_project(self.index))

        ctrl_frame.addWidget(self.ide_combo)
        ctrl_frame.addWidget(btn_open)
        ctrl_frame.addWidget(btn_term)
        ctrl_frame.addWidget(btn_del)

        layout.addLayout(info_frame, stretch=1)
        layout.addSpacing(20)
        layout.addLayout(ctrl_frame)

    def truncate_path(self, path, max_chars=50):
        if len(path) <= max_chars: return path
        head, tail = os.path.split(path)
        parent = os.path.basename(head)
        short_path = f".../{parent}/{tail}"
        if len(short_path) > max_chars: return "..." + path[-(max_chars - 3):]
        return short_path

    def save_snapshot(self):
        self.data["snapshot"] = self.snapshot_input.text().strip()
        self.plugin.save_projects()

    def update_ide(self, new_ide):
        self.data["default_ide"] = new_ide
        self.plugin.save_projects()

    def launch_ide(self):
        ide_name = self.data.get("default_ide", "File Explorer")
        path = self.data["path"]

        if ide_name == "File Explorer":
            if sys.platform == "win32":
                os.startfile(path)
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            return

        exe_path = self.plugin.get_ide_executable(ide_name)
        if exe_path:
            try:
                # Launch the IDE as a completely detached external process
                subprocess.Popen([exe_path, path])
            except Exception as e:
                QMessageBox.critical(self, "Execution Error", str(e))

    def launch_terminal(self):
        # Emits the path back to main.py to open in PRISMO's internal terminal!
        self.plugin.launch_request.emit(self.data["path"], "", "")


class ProjectsPlugin(QWidget):
    launch_request = Signal(str, str, str)

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)

        # --- HEADER ---
        header_layout = QHBoxLayout()

        btn_reset = QPushButton("RESET PATHS")
        btn_reset.setCursor(Qt.PointingHandCursor)
        btn_reset.setStyleSheet(
            f"background-color: transparent; color: {TEXT_DIM}; border: 1px solid {TEXT_DIM}; padding: 6px 15px; font-weight: bold;")
        btn_reset.clicked.connect(self.reset_ide_paths)

        btn_new = QPushButton("+ NEW PROJECT")
        btn_new.setCursor(Qt.PointingHandCursor)
        btn_new.setStyleSheet(
            "background-color: #2CC985; color: white; font-weight: bold; padding: 6px 15px; border-radius: 15px;")
        btn_new.clicked.connect(self.add_new_project)

        header_layout.addStretch()
        header_layout.addWidget(btn_reset)
        header_layout.addWidget(btn_new)

        # --- SCROLL AREA ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.cards_container)

        self.layout.addLayout(header_layout)
        self.layout.addWidget(self.scroll_area)

        self.projects = []
        self.ide_paths = {}
        self.load_data()

    # --- DATA HANDLING ---
    def load_data(self):
        if os.path.exists(PROJECTS_FILE):
            try:
                with open(PROJECTS_FILE, "r") as f:
                    self.projects = json.load(f)
            except:
                self.projects = []

        if os.path.exists(IDE_CONFIG_FILE):
            try:
                with open(IDE_CONFIG_FILE, "r") as f:
                    self.ide_paths = json.load(f)
            except:
                self.ide_paths = {}

        self.refresh_ui()

    def save_projects(self):
        with open(PROJECTS_FILE, "w") as f: json.dump(self.projects, f, indent=4)

    def save_ide_paths(self):
        with open(IDE_CONFIG_FILE, "w") as f: json.dump(self.ide_paths, f, indent=4)

    def reset_ide_paths(self):
        reply = QMessageBox.question(self, "Reset Paths", "Forget all saved IDE executable locations?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.ide_paths = {}
            self.save_ide_paths()

    # --- ACTIONS ---
    def add_new_project(self):
        # Pops open your OS file explorer to pick the folder!
        path = QFileDialog.getExistingDirectory(self, "Select Project Directory")
        if not path: return

        default_name = os.path.basename(path)
        name, ok = QInputDialog.getText(self, "New Project", "Enter Project Name:", QLineEdit.Normal, default_name)

        if ok and name:
            self.projects.append({
                "name": name,
                "path": path,
                "default_ide": "File Explorer",
                "snapshot": ""
            })
            self.save_projects()
            self.refresh_ui()

    def remove_project(self, index):
        del self.projects[index]
        self.save_projects()
        self.refresh_ui()

    def get_ide_executable(self, ide_name):
        # 1. Check if we already know the path
        if ide_name in self.ide_paths and os.path.exists(self.ide_paths[ide_name]):
            return self.ide_paths[ide_name]

        # 2. If not, ask the user to find the .exe
        QMessageBox.information(self, "Configure IDE",
                                f"Executable for '{ide_name}' not found.\nPlease locate the .exe file.")

        exe_path, _ = QFileDialog.getOpenFileName(self, f"Select {ide_name} Executable", "",
                                                  "Executables (*.exe);;All Files (*.*)")

        # 3. Save it forever
        if exe_path:
            self.ide_paths[ide_name] = exe_path
            self.save_ide_paths()
            return exe_path

        return None

    # --- UI RENDERING ---
    def refresh_ui(self):
        for i in reversed(range(self.cards_layout.count())):
            widget = self.cards_layout.itemAt(i).widget()
            if widget: widget.setParent(None)

        if not self.projects:
            empty_lbl = QLabel("No projects tracked. Click '+ NEW PROJECT' to begin.")
            empty_lbl.setStyleSheet("color: #555555; font-size: 16px;")
            empty_lbl.setAlignment(Qt.AlignCenter)
            self.cards_layout.addWidget(empty_lbl)
            return

        for i, proj in enumerate(self.projects):
            card = ProjectCard(i, proj, self)
            self.cards_layout.addWidget(card)