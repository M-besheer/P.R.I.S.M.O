import sys
import psutil
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QPushButton, QTabWidget, QFrame,
                               QStackedWidget)
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont

# Import the Plugins
from Plugins.Terminal import TerminalTab, SHELL_CONFIGS, MONO_FONT
from Plugins.Directory import DirectoryPlugin
from Plugins.Projects import ProjectsPlugin  # <--- NEW: Imported the Projects Station

# --- THEME CONSTANTS ---
ACCENT = "#00ECFF"
BG_DARK = "#050505"
TEXT_DIM = "#444444"


class PrismoMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("P.R.I.S.M.O Core - Multi-Shell Matrix")
        self.resize(1100, 800)
        self.setStyleSheet(f"background-color: {BG_DARK}; color: white;")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- 1. TOP RIBBON ---
        ribbon = QFrame()
        ribbon.setStyleSheet("border-bottom: 1px solid #222; background-color: #030303;")
        ribbon_layout = QHBoxLayout(ribbon)

        sys_id = QLabel("PRISMO_CORE")
        sys_id.setStyleSheet(f"color: {TEXT_DIM}; font-weight: bold;")

        nav_layout = QHBoxLayout()
        self.btn_proj = QPushButton("PROJECTS")  # <--- NEW: Projects Button
        self.btn_dir = QPushButton("DIRECTORY")
        self.btn_term = QPushButton("TERMINAL")

        # Connect buttons to the view switcher (Indexes: 0=Projects, 1=Directory, 2=Terminal)
        self.btn_proj.clicked.connect(lambda: self.switch_view(0))
        self.btn_dir.clicked.connect(lambda: self.switch_view(1))
        self.btn_term.clicked.connect(lambda: self.switch_view(2))

        nav_layout.addWidget(self.btn_proj)
        nav_layout.addWidget(self.btn_dir)
        nav_layout.addWidget(self.btn_term)

        ribbon_layout.addWidget(sys_id)
        ribbon_layout.addLayout(nav_layout)
        ribbon_layout.addStretch()  # Pushes everything to the left cleanly

        # --- 2. BODY (Sidebar + Stacked View) ---
        body_layout = QHBoxLayout()

        # Sidebar
        sidebar = QFrame()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("border-right: 1px solid #222; background-color: #030303;")
        sidebar_layout = QVBoxLayout(sidebar)

        lbl_monitor = QLabel("SYSTEM_MONITOR")
        lbl_monitor.setStyleSheet(f"color: {TEXT_DIM}; font-weight: bold; letter-spacing: 2px;")

        self.lbl_cpu = QLabel("CPU: --")
        self.lbl_ram = QLabel("RAM: --")
        self.lbl_cpu.setFont(QFont(MONO_FONT, 10))
        self.lbl_ram.setFont(QFont(MONO_FONT, 10))

        sidebar_layout.addWidget(lbl_monitor)
        sidebar_layout.addWidget(self.lbl_cpu)
        sidebar_layout.addWidget(self.lbl_ram)
        sidebar_layout.addStretch()

        # --- PLUGIN STACK MANAGER ---
        self.view_stack = QStackedWidget()

        # View Index 0: Projects Station
        self.proj_view = ProjectsPlugin()
        self.view_stack.addWidget(self.proj_view)
        # Wire up the launch signal
        self.proj_view.launch_request.connect(self.execute_project)

        # View Index 1: Directory Plugin
        self.dir_view = DirectoryPlugin()
        self.view_stack.addWidget(self.dir_view)
        # Wire up the double-click path signal (Uncommented and fixed!)
        self.dir_view.path_selected.connect(self.send_cd_to_terminal)

        # View Index 2: Terminal Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; }}
            QTabBar::tab {{ background: {BG_DARK}; color: {TEXT_DIM}; padding: 10px 25px; border-right: 1px solid #222; border-bottom: 1px solid #222;}}
            QTabBar::tab:selected {{ background: #010101; color: white; border-bottom: 2px solid {ACCENT}; font-weight: bold; }}
            QTabBar::tab:hover {{ color: {ACCENT}; }}
        """)

        # Inject Terminals
        for config in SHELL_CONFIGS:
            self.tabs.addTab(TerminalTab(config), config["name"])

        self.view_stack.addWidget(self.tabs)

        # Add Sidebar and Stack to Body
        body_layout.addWidget(sidebar)
        body_layout.addWidget(self.view_stack, stretch=1)

        # Assemble Main Layout
        main_layout.addWidget(ribbon)
        main_layout.addLayout(body_layout)

        # Set Initial State (Start on the Terminal tab, which is now Index 2)
        self.switch_view(2)

        # --- 3. HARDWARE TIMER ---
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(2000)

    # --- SIGNAL HANDLERS ---
    def format_cd_command(self, shell_name, raw_path):
        """Formats the CD command correctly depending on the specific shell OS."""
        clean_path = raw_path.replace("\\", "/")

        # WSL Ubuntu needs /mnt/c/ format
        if shell_name == "UBUNTU" and ":" in clean_path:
            drive, rest = clean_path.split(":", 1)
            clean_path = f"/mnt/{drive.lower()}{rest}"
            return f'cd "{clean_path}"'

        # Windows CMD needs the /d flag to switch hard drives (e.g. C: to D:)
        elif shell_name == "CMD":
            return f'cd /d "{clean_path}"'

        # PowerShell and Git Bash handle standard paths fine
        else:
            return f'cd "{clean_path}"'

    # --- SIGNAL HANDLERS ---
    def send_cd_to_terminal(self, path):
        """Receives a path from the Directory plugin and sets the terminal state."""
        active_terminal = self.tabs.currentWidget()
        if active_terminal:
            # We pass an empty string for the command, it just sets the path
            active_terminal.run_in_directory(path, "")
            self.switch_view(2)

    def execute_project(self, path, command, ide_cmd=None):
        """Receives path and command from the Projects Station and runs them."""
        active_terminal = self.tabs.currentWidget()
        if active_terminal:
            # If an IDE command is provided, prioritize it. Otherwise use normal command.
            cmd_to_run = ide_cmd if ide_cmd else command
            active_terminal.run_in_directory(path, cmd_to_run)
            self.switch_view(2)
    # --- UI STATE ---
    def switch_view(self, index):
        """Swaps the central plugin view and updates all 3 ribbon buttons."""
        self.view_stack.setCurrentIndex(index)

        active_style = f"border: none; color: {ACCENT}; font-weight: bold; padding: 10px;"
        inactive_style = "border: none; color: white; padding: 10px;"

        self.btn_proj.setStyleSheet(active_style if index == 0 else inactive_style)
        self.btn_dir.setStyleSheet(active_style if index == 1 else inactive_style)
        self.btn_term.setStyleSheet(active_style if index == 2 else inactive_style)

    def update_stats(self):
        self.lbl_cpu.setText(f"CPU_LOAD: {psutil.cpu_percent()}%")
        self.lbl_ram.setText(f"RAM_USAGE: {psutil.virtual_memory().percent}%")

    def closeEvent(self, event):
        # Trigger the kill sequence on the plugins cleanly
        for i in range(self.tabs.count()):
            self.tabs.widget(i).stop_process()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PrismoMainWindow()
    window.show()
    sys.exit(app.exec())