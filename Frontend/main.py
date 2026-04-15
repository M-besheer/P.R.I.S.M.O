import sys
import psutil
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QPushButton, QTabWidget, QFrame,
                               QStackedWidget, QMenu, QSystemTrayIcon,QStyle)
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QAction

from Frontend.Plugins.Projects import ProjectsPlugin
# Import the Plugins
from Frontend.Plugins.Terminal import TerminalTab, SHELL_CONFIGS, MONO_FONT
from Frontend.Plugins.Directory import DirectoryPlugin
from Frontend.Plugins.LMS import LMSPlugin # <--- NEW: Academic Matrix

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
        self.btn_lms = QPushButton("LMS_MATRIX") # <--- Repurposed for University Data
        self.btn_dir = QPushButton("DIRECTORY")
        self.btn_term = QPushButton("TERMINAL")
        self.btn_projects = QPushButton("PROJECTS")

        # Connect buttons to the view switcher (Indexes: 0=LMS, 1=Directory, 2=Terminal)
        self.btn_lms.clicked.connect(lambda: self.switch_view(0))
        self.btn_dir.clicked.connect(lambda: self.switch_view(1))
        self.btn_term.clicked.connect(lambda: self.switch_view(2))
        self.btn_projects.clicked.connect(lambda: self.switch_view(3))

        nav_layout.addWidget(self.btn_lms)
        nav_layout.addWidget(self.btn_dir)
        nav_layout.addWidget(self.btn_term)
        nav_layout.addWidget(self.btn_projects)

        ribbon_layout.addWidget(sys_id)
        ribbon_layout.addLayout(nav_layout)
        ribbon_layout.addStretch()

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

        # View Index 0: LMS Plugin
        self.lms_view = LMSPlugin()
        self.view_stack.addWidget(self.lms_view)

        # View Index 1: Directory Plugin (Project Nexus)
        self.dir_view = DirectoryPlugin()
        self.view_stack.addWidget(self.dir_view)
        # Listen for the right-click terminal requests
        self.dir_view.terminal_request.connect(self.send_cd_to_terminal)

        # View Index 2: Terminal Matrix
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; }}
            QTabBar::tab {{ background: {BG_DARK}; color: {TEXT_DIM}; padding: 10px 25px; border-right: 1px solid #222; border-bottom: 1px solid #222;}}
            QTabBar::tab:selected {{ background: #010101; color: white; border-bottom: 2px solid {ACCENT}; font-weight: bold; }}
            QTabBar::tab:hover {{ color: {ACCENT}; }}
        """)

        for config in SHELL_CONFIGS:
            self.tabs.addTab(TerminalTab(config), config["name"])

        self.view_stack.addWidget(self.tabs)

        body_layout.addWidget(sidebar)
        body_layout.addWidget(self.view_stack, stretch=1)

        main_layout.addWidget(ribbon)
        main_layout.addLayout(body_layout)

        # Start on Terminal View
        self.switch_view(0)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(2000)

        # View Index 3: Projects Station
        self.projects_view = ProjectsPlugin()
        self.view_stack.addWidget(self.projects_view)

        self.setup_tray()

    def setup_tray(self):
        """Configures the system tray integration."""
        self.tray_icon = QSystemTrayIcon(self)

        # Corrected: Accessing the standard icon through the QStyle enum
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))

        # Create the Right-Click Menu
        tray_menu = QMenu()

        show_action = QAction("Open P.R.I.S.M.O", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)

        quit_action = QAction("Shut Down Core", self)
        quit_action.triggered.connect(self.actual_quit)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        self.tray_icon.activated.connect(self.on_tray_activation)

    def on_tray_activation(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()
            self.raise_()
            self.activateWindow()

    # --- OVERRIDE CLOSE EVENT ---
    def closeEvent(self, event):
        """Intercepts the X button to minimize to tray instead of quitting."""
        if self.tray_icon.isVisible():
            self.hide()  # Just hide the window

            # Optional: Show a message telling the user it's still running
            self.tray_icon.showMessage(
                "P.R.I.S.M.O Background",
                "Core is running in the background. checking for assignments...",
                QSystemTrayIcon.Information,
                500
            )
            event.ignore()  # Ignore the "kill" signal
        else:
            # If no tray icon, actually close (fallback)
            event.accept()
    # --- SIGNAL HANDLERS ---
    def send_cd_to_terminal(self, path, shell_name):
        """Finds the requested terminal tab and paths into the directory."""
        target_index = -1
        target_terminal = None

        for i in range(self.tabs.count()):
            terminal = self.tabs.widget(i)
            if terminal.shell_name == shell_name:
                target_index = i
                target_terminal = terminal
                break

        if target_terminal:
            self.tabs.setCurrentIndex(target_index)
            target_terminal.run_in_directory(path, "")
            self.switch_view(2)

    # --- UI STATE ---
    def switch_view(self, index):
        self.view_stack.setCurrentIndex(index)

        active_style = f"border: none; color: {ACCENT}; font-weight: bold; padding: 10px;"
        inactive_style = "border: none; color: white; padding: 10px;"

        self.btn_lms.setStyleSheet(active_style if index == 0 else inactive_style)
        self.btn_dir.setStyleSheet(active_style if index == 1 else inactive_style)
        self.btn_term.setStyleSheet(active_style if index == 2 else inactive_style)

    def update_stats(self):
        try:
            # We wrap this in a try/except to prevent the traceback you saw
            self.lbl_cpu.setText(f"CPU_LOAD: {psutil.cpu_percent()}%")
            self.lbl_ram.setText(f"RAM_USAGE: {psutil.virtual_memory().percent}%")
        except (RuntimeError, KeyboardInterrupt):
            # If the app is closing, just ignore the error
            pass

    def closeEvent(self, event):
        """Intercepts the X button to minimize to tray."""
        if self.tray_icon.isVisible():
            self.hide()
            self.tray_icon.showMessage(
                "P.R.I.S.M.O Active",
                "Sentinel is monitoring your LMS in the background.",
                QSystemTrayIcon.Information,
                500
            )
            event.ignore()
        else:
            event.accept()

    def actual_quit(self):
        """The only way to truly kill the process."""
        print("P.R.I.S.M.O // Initiating Core Shutdown...")
        self.timer.stop()  # Stop the CPU monitor
        # If your LMSPlugin has a timer, stop it here too
        self.lms_view.bg_timer.stop()
        QApplication.quit()

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # CRITICAL: This line keeps the app alive even if no windows are open
    app.setQuitOnLastWindowClosed(False)

    window = PrismoMainWindow()
    window.show()
    sys.exit(app.exec())