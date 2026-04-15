import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
                               QLineEdit, QLabel, QPushButton, QFileDialog)
from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QFont, QTextCursor

# --- THEME & CONFIG CONSTANTS ---
MONO_FONT = "Consolas"

SHELL_CONFIGS = [
    {
        "name": "CMD",
        "exe": "cmd.exe",
        "args": ["/c"],
        "color": "#00ECFF",  # PRISMO Cyan
        "bg": "#010202"  # Subtle cyan tint
    },
    {
        "name": "POWERSHELL",
        "exe": "powershell.exe",
        "args": ["-Command"],
        "color": "#569CD6",  # PowerShell Blue
        "bg": "#010205"  # Subtle blue tint
    },
    {
        "name": "GIT BASH",
        "exe": r"C:\Program Files\Git\bin\bash.exe",
        "args": ["-c"],
        "color": "#00FF41",  # Hacker Green
        "bg": "#010501"  # Subtle green tint
    },
    {
        "name": "UBUNTU",
        "exe": "wsl.exe",
        "args": ["--", "bash", "-c"],
        "color": "#E95420",  # Ubuntu Orange
        "bg": "#050201"  # Subtle orange tint
    }
]


class TerminalTab(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.accent = self.config["color"]
        self.bg_color = self.config["bg"]
        self.shell_name = self.config["name"]

        # --- 1. Tab Header (Save Button) ---
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(15, 8, 15, 8)

        lbl_title = QLabel(f"{self.shell_name}_LINK")
        lbl_title.setStyleSheet(f"color: #444444; font-weight: bold; font-family: {MONO_FONT};")

        btn_save = QPushButton("💾 SAVE LOG")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; 
                color: {self.accent}; 
                font-weight: bold; 
                border: 1px solid #444444;
                border-radius: 3px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background-color: {self.accent};
                color: black;
            }}
        """)
        btn_save.clicked.connect(self.save_log)

        header_layout.addWidget(lbl_title)
        header_layout.addStretch()
        header_layout.addWidget(btn_save)

        # --- 2. Output Log ---
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        # Removed top border so it blends smoothly with the new header
        self.log_view.setStyleSheet(
            f"background-color: {self.bg_color}; color: white; border: 1px solid #222; border-top: none; padding: 10px;")
        self.log_view.setFont(QFont(MONO_FONT, 10))

        # --- 3. Command Input ---
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText(f"PRISMO@{self.shell_name} >")
        self.input_field.setStyleSheet(
            f"background-color: #030303; color: {self.accent}; border: 1px solid #222; padding: 8px;")
        self.input_field.setFont(QFont(MONO_FONT, 10))
        self.input_field.returnPressed.connect(self.execute_cmd)

        # Assemble Layout
        self.layout.addLayout(header_layout)
        self.layout.addWidget(self.log_view)
        self.layout.addWidget(self.input_field)

        # ---> ADD THIS: Persistent Directory State
        self.current_dir = os.path.expanduser("~")  # Starts in your User folder

        # Update placeholder to show current directory
        self.input_field.setPlaceholderText(f"PRISMO@{self.shell_name} [~] >")
        # Process Manager
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)

        self.draw_logo()

    def draw_logo(self):
        logo = f"""
██████╗ ██████╗ ██╗███████╗███╗   ███╗ ██████╗ 
██╔══██╗██╔══██╗██║██╔════╝████╗ ████║██╔═══██╗
██████╔╝██████╔╝██║███████╗██╔████╔██║██║   ██║
██╔═══╝ ██╔══██╗██║╚════██║██║╚██╔╝██║██║   ██║
██║     ██║  ██║██║███████║██║ ╚═╝ ██║╚██████╔╝
╚═╝     ╚═╝  ╚═╝╚═╝╚══════╝╚═╝     ╚═╝ ╚═════╝
[ SYS_OS: PRISMO // {self.shell_name} KERNEL ONLINE ]
_____________________________________________
        """
        self.log_message(logo, self.accent)

    def log_message(self, text, color="white"):
        self.log_view.moveCursor(QTextCursor.End)
        self.log_view.insertHtml(
            f'<pre style="color: {color}; font-family: {MONO_FONT}; margin: 0px;">{text}</pre><br>')
        self.log_view.moveCursor(QTextCursor.End)

    def save_log(self):
        """Triggers native OS Save As dialog and writes text content to file."""
        default_name = f"prismo_{self.shell_name.lower()}_log.txt"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Terminal Log",
            default_name,
            "Text Files (*.txt);;All Files (*)"
        )

        if file_path:
            try:
                # toPlainText strips HTML natively!
                log_content = self.log_view.toPlainText()
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(log_content)
                self.log_message(f"SYSTEM: Log successfully saved to {file_path}", "#00FF41")
            except Exception as e:
                self.log_message(f"SYSTEM_ERROR: Could not save log. {e}", "red")

    def execute_cmd(self, injected_cmd=None):
        """Executes a command using the persistent working directory."""
        # Use injected command if provided, otherwise grab from input field
        cmd = injected_cmd if injected_cmd else self.input_field.text().strip()
        if not cmd: return

        if not injected_cmd:
            self.input_field.clear()

        self.log_message(f">>> {cmd}", self.accent)

        if cmd.lower() == "clear":
            self.log_view.clear()
            self.draw_logo()
            return

        # ---> THE FIX: Intercept 'cd' commands to update our internal state manually
        if cmd.lower().startswith("cd ") or cmd.lower() == "cd..":
            target = cmd[3:].strip().replace('"', '').replace("'", "")
            if cmd.lower() == "cd..": target = ".."

            # Strip Windows /d flag if user typed it out of habit
            if target.lower().startswith("/d "): target = target[3:].strip()

            # Calculate the new path
            if target == "..":
                self.current_dir = os.path.dirname(self.current_dir)
            elif os.path.isabs(target) and os.path.exists(target):
                self.current_dir = target
            else:
                test_path = os.path.abspath(os.path.join(self.current_dir, target))
                if os.path.exists(test_path):
                    self.current_dir = test_path
                else:
                    self.log_message(f"ERR: Directory not found: {test_path}", "#ff4444")
                    return

            # Update UI and exit (no need to spawn a process just to CD!)
            self.log_message(f"SYSTEM_PATH_UPDATED: {self.current_dir}", self.accent)
            self.input_field.setPlaceholderText(f"PRISMO@{self.shell_name} [{os.path.basename(self.current_dir)}] >")
            return

        # ---> Set the working directory BEFORE starting the process!
        self.process.setWorkingDirectory(self.current_dir)

        full_args = self.config["args"] + [cmd]

        if not os.path.exists(self.config["exe"]) and "bash" in self.config["exe"]:
            self.log_message(f"SYSTEM_ERROR: Could not find {self.config['exe']}. Is Git installed here?", "#ff4444")
            return

        self.process.start(self.config["exe"], full_args)

    def run_in_directory(self, path, cmd):
        """Called by the Projects and Directory plugins to cleanly launch things."""
        if os.path.exists(path):
            self.current_dir = os.path.abspath(path)
            self.input_field.setPlaceholderText(f"PRISMO@{self.shell_name} [{os.path.basename(self.current_dir)}] >")
            self.log_message(f"SYSTEM_PATH_UPDATED: {self.current_dir}", self.accent)

            if cmd:
                self.execute_cmd(cmd)
    def handle_stdout(self):
        data = self.process.readAllStandardOutput().data().decode('utf-8', errors='replace')
        for line in data.splitlines():
            if line: self.log_message(line.strip(), "white")

    def handle_stderr(self):
        data = self.process.readAllStandardError().data().decode('utf-8', errors='replace')
        for line in data.splitlines():
            if line: self.log_message(f"ERR: {line.strip()}", "#ff4444")

    def stop_process(self):
        if self.process.state() == QProcess.Running:
            self.process.kill()

    def inject_command(self, cmd):
        """Programmatically inserts and runs a command from another plugin."""
        self.input_field.setText(cmd)
        self.execute_cmd()