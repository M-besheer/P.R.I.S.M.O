import sys
import psutil
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QPushButton, QFrame,
                               QStackedWidget, QMenu, QSystemTrayIcon, QStyle)
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QAction

# Only importing the refactored Projects Plugin!
from Frontend.Plugins.Projects import ProjectsPlugin

# --- THEME CONSTANTS ---
ACCENT = "#00ECFF"
BG_DARK = "#050505"
TEXT_DIM = "#444444"
MONO_FONT = "Consolas"


class PrismoMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("P.R.I.S.M.O Core")
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
        sys_id.setStyleSheet(f"color: {TEXT_DIM}; font-weight: bold; padding-left: 10px;")

        nav_layout = QHBoxLayout()
        self.btn_projects = QPushButton("PROJECTS")
        self.btn_projects.setStyleSheet(f"border: none; color: {ACCENT}; font-weight: bold; padding: 10px;")

        nav_layout.addWidget(self.btn_projects)

        ribbon_layout.addWidget(sys_id)
        ribbon_layout.addLayout(nav_layout)
        ribbon_layout.addStretch()

        # --- 2. BODY (Sidebar + Main View) ---
        body_layout = QHBoxLayout()

        # Sidebar (System Monitor)
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
        # We keep the StackedWidget so it's easy to add LMS/Directory back later!
        self.view_stack = QStackedWidget()

        # View Index 0: Projects Station
        self.projects_view = ProjectsPlugin()
        self.view_stack.addWidget(self.projects_view)

        body_layout.addWidget(sidebar)
        body_layout.addWidget(self.view_stack, stretch=1)

        main_layout.addWidget(ribbon)
        main_layout.addLayout(body_layout)

        # System Monitor Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(2000)

        self.setup_tray()

    def setup_tray(self):
        """Configures the system tray integration."""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))

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

    def update_stats(self):
        """Updates the CPU and RAM metrics."""
        try:
            self.lbl_cpu.setText(f"CPU_LOAD: {psutil.cpu_percent()}%")
            self.lbl_ram.setText(f"RAM_USAGE: {psutil.virtual_memory().percent}%")
        except (RuntimeError, KeyboardInterrupt):
            pass

    def closeEvent(self, event):
        """Intercepts the X button to minimize to tray instead of quitting."""
        if self.tray_icon.isVisible():
            self.hide()
            self.tray_icon.showMessage(
                "P.R.I.S.M.O Active",
                "Core is running in the background.",
                QSystemTrayIcon.Information,
                500
            )
            event.ignore()
        else:
            event.accept()

    def actual_quit(self):
        """The only way to truly kill the process."""
        print("P.R.I.S.M.O // Initiating Core Shutdown...")
        self.timer.stop()
        QApplication.quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # CRITICAL: This line keeps the app alive even if no windows are open
    app.setQuitOnLastWindowClosed(False)

    window = PrismoMainWindow()
    window.show()
    sys.exit(app.exec())