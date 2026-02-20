import os
import json
import shutil
import subprocess
import stat
from send2trash import send2trash # <--- ADD THIS LINE
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTreeView,
                               QFileSystemModel, QLineEdit, QPushButton, QHeaderView,
                               QSplitter, QTextEdit, QLabel, QScrollArea, QStackedWidget,
                               QComboBox, QMessageBox, QInputDialog, QFormLayout, QMenu,
                               QAbstractItemView)  # <--- ADDED QAbstractItemView
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont, QGuiApplication

# --- THEME CONSTANTS ---
ACCENT = "#00ECFF"
BG_PANEL = "#010101"
TEXT_DIM = "#444444"
MONO_FONT = "Consolas"
BOOKMARKS_FILE = "prismo_bookmarks.json"
IDE_CONFIG_FILE = "prismo_ides.json"
PROJECTS_DATA_FILE = "prismo_folder_data.json"


class IDEWatcher(QThread):
    finished_signal = Signal(str)

    def __init__(self, process, path):
        super().__init__()
        self.process = process
        self.path = path

    def run(self):
        self.process.wait()
        self.finished_signal.emit(self.path)


class DirectoryPlugin(QWidget):
    terminal_request = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.active_watcher = None

        self.ide_configs = {}
        self.folder_data = {}
        self.bookmarks = []
        self.load_databases()

        # --- 1. Address Bar ---
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(15, 10, 15, 5)

        self.path_input = QLineEdit()
        self.path_input.setStyleSheet(
            f"background-color: #030303; color: {ACCENT}; border: 1px solid #222; padding: 6px;")
        self.path_input.setFont(QFont(MONO_FONT, 10))
        self.path_input.returnPressed.connect(self.load_root)
        self.path_input.textChanged.connect(self.check_pin_status)

        btn_go = QPushButton("NAVIGATE")
        btn_go.setCursor(Qt.PointingHandCursor)
        btn_go.setStyleSheet(
            f"QPushButton {{ color: {ACCENT}; font-weight: bold; border: 1px solid {ACCENT}; padding: 6px 15px; }}")
        btn_go.clicked.connect(self.load_root)

        header_layout.addWidget(self.path_input)
        header_layout.addWidget(btn_go)

        # --- 2. Quick Access Bookmarks ---
        self.bookmark_scroll = QScrollArea()
        self.bookmark_scroll.setFixedHeight(45)
        self.bookmark_scroll.setWidgetResizable(True)
        self.bookmark_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.bookmark_scroll.setStyleSheet(
            "QScrollArea { border: none; background-color: transparent; } QScrollBar:horizontal { height: 0px; }")

        self.bookmark_container = QWidget()
        self.bookmark_layout = QHBoxLayout(self.bookmark_container)
        self.bookmark_layout.setContentsMargins(15, 0, 15, 5)
        self.bookmark_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.btn_pin = QPushButton("★ PIN")
        self.btn_pin.setCursor(Qt.PointingHandCursor)
        self.btn_pin.setStyleSheet(
            f"background-color: transparent; color: {TEXT_DIM}; border: 1px solid {TEXT_DIM}; padding: 4px 10px; border-radius: 10px;")
        self.btn_pin.clicked.connect(self.toggle_pin)
        self.bookmark_scroll.setWidget(self.bookmark_container)

        self.refresh_bookmarks_ui()

        # --- 3. Splitter & FULL-ACCESS FILE TREE ---
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setStyleSheet("QSplitter::handle { background-color: #222; width: 2px; }")

        self.model = QFileSystemModel()
        self.model.setRootPath("")
        self.model.setReadOnly(False)  # <--- Unlocks native file renaming and moving

        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(""))

        # Enable Native Drag & Drop
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        self.tree.setDropIndicatorShown(True)
        self.tree.setDragDropMode(QAbstractItemView.InternalMove)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)  # <--- ADD THIS LINE

        self.tree.setStyleSheet(f"""
            QTreeView {{ background-color: {BG_PANEL}; color: white; border: none; outline: 0; }}
            QTreeView::item:hover {{ background-color: #111; color: {ACCENT}; }}
            QTreeView::item:selected {{ background-color: #002222; color: {ACCENT}; border-left: 2px solid {ACCENT}; }}
            QHeaderView::section {{ background-color: #030303; color: {TEXT_DIM}; border: none; border-bottom: 1px solid #222; padding: 4px; }}
        """)
        self.tree.setFont(QFont(MONO_FONT, 9))
        self.tree.setSortingEnabled(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.setColumnHidden(1, True)
        self.tree.setColumnHidden(2, True)
        self.tree.setColumnHidden(3, True)

        self.tree.clicked.connect(self.on_tree_clicked)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)

        # --- 4. RIGHT PANE INSPECTOR ---
        self.inspector_stack = QStackedWidget()
        self.inspector_stack.setStyleSheet(f"background-color: {BG_PANEL};")

        self.empty_view = QLabel("SELECT NODE TO INSPECT")
        self.empty_view.setAlignment(Qt.AlignCenter)
        self.empty_view.setStyleSheet(f"color: {TEXT_DIM}; font-family: {MONO_FONT};")
        self.inspector_stack.addWidget(self.empty_view)

        # File Previewer
        self.file_preview_widget = QWidget()
        fp_layout = QVBoxLayout(self.file_preview_widget)
        fp_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_header = QLabel("FILE_INSPECTOR")
        self.preview_header.setStyleSheet(
            f"background-color: #030303; color: {TEXT_DIM}; font-weight: bold; padding: 5px 10px; border-bottom: 1px solid #222;")
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setStyleSheet("border: none; padding: 10px; color: #CCC;")
        self.preview_text.setFont(QFont(MONO_FONT, 9))
        self.preview_text.setLineWrapMode(QTextEdit.NoWrap)
        fp_layout.addWidget(self.preview_header)
        fp_layout.addWidget(self.preview_text)
        self.inspector_stack.addWidget(self.file_preview_widget)

        # Folder Dashboard
        self.folder_dashboard_widget = QWidget()
        fd_layout = QVBoxLayout(self.folder_dashboard_widget)

        self.fd_title = QLabel("FOLDER_NAME")
        self.fd_title.setStyleSheet(f"color: {ACCENT}; font-size: 18px; font-weight: bold; font-family: Arial;")
        self.fd_path = QLabel("path...")
        self.fd_path.setStyleSheet(f"color: {TEXT_DIM}; font-family: {MONO_FONT}; font-size: 10px;")

        self.git_status_lbl = QLabel("GIT: Not Initialized")
        self.git_status_lbl.setStyleSheet(
            "color: #FF8800; background-color: #110800; border: 1px solid #331100; padding: 8px; font-family: Consolas;")
        self.git_status_lbl.setWordWrap(True)

        self.snapshot_input = QTextEdit()
        self.snapshot_input.setPlaceholderText("Enter Dev Snapshot (What are you working on?)...")
        self.snapshot_input.setFixedHeight(80)
        self.snapshot_input.setStyleSheet(
            f"background-color: #010201; color: #00FF41; border: 1px solid #113311; padding: 8px; font-family: {MONO_FONT};")

        btn_save_snap = QPushButton("SAVE SNAPSHOT")
        btn_save_snap.setStyleSheet(
            f"background-color: transparent; color: {ACCENT}; border: 1px solid {ACCENT}; padding: 4px;")
        btn_save_snap.clicked.connect(self.save_folder_snapshot)

        ide_row = QHBoxLayout()
        self.ide_combo = QComboBox()
        self.ide_combo.addItems(["VS Code", "Cursor", "PyCharm", "File Explorer"])
        self.ide_combo.setStyleSheet(f"background-color: #030303; color: white; border: 1px solid #222; padding: 6px;")

        btn_launch_ide = QPushButton("</> OPEN IDE")
        btn_launch_ide.setStyleSheet(f"background-color: {ACCENT}; color: black; font-weight: bold; padding: 6px;")
        btn_launch_ide.clicked.connect(self.launch_ide_and_watch)

        ide_row.addWidget(self.ide_combo)
        ide_row.addWidget(btn_launch_ide)

        # Action Buttons
        btn_git_init = QPushButton("GIT INIT")
        btn_git_init.clicked.connect(lambda: self.run_shell("git init"))
        btn_git_add = QPushButton("GIT ADD .")
        btn_git_add.clicked.connect(lambda: self.run_shell("git add ."))
        btn_new_dir = QPushButton("NEW FOLDER")
        btn_new_dir.clicked.connect(lambda: self.create_folder())
        btn_new_file = QPushButton("NEW FILE")
        btn_new_file.clicked.connect(lambda: self.create_file())
        btn_del_dir = QPushButton("DELETE TARGET")
        btn_del_dir.setStyleSheet(
            "color: #FF4444; border: 1px solid #FF4444; background-color: transparent; padding: 6px;")
        btn_del_dir.clicked.connect(lambda: self.delete_target([self.current_inspected_path]))

        for btn in [btn_git_init, btn_git_add, btn_new_dir, btn_new_file]:
            btn.setStyleSheet("background-color: #111; color: white; border: 1px solid #333; padding: 6px;")

        grid = QFormLayout()
        grid.addRow(btn_git_init, btn_git_add)
        grid.addRow(btn_new_dir, btn_new_file)
        grid.addRow(btn_del_dir)

        fd_layout.addWidget(self.fd_title)
        fd_layout.addWidget(self.fd_path)
        fd_layout.addWidget(self.git_status_lbl)
        fd_layout.addWidget(QLabel("SYSTEM_MEMORY:", styleSheet=f"color: {TEXT_DIM};"))
        fd_layout.addWidget(self.snapshot_input)
        fd_layout.addWidget(btn_save_snap)
        fd_layout.addWidget(QLabel("LAUNCH PROTOCOL:", styleSheet=f"color: {TEXT_DIM};"))
        fd_layout.addLayout(ide_row)
        fd_layout.addWidget(QLabel("FILE & GIT OPERATIONS:", styleSheet=f"color: {TEXT_DIM};"))
        fd_layout.addLayout(grid)
        fd_layout.addStretch()

        self.inspector_stack.addWidget(self.folder_dashboard_widget)

        self.splitter.addWidget(self.tree)
        self.splitter.addWidget(self.inspector_stack)
        self.splitter.setSizes([400, 400])

        self.layout.addLayout(header_layout)
        self.layout.addWidget(self.bookmark_scroll)
        self.layout.addWidget(self.splitter)
        self.current_inspected_path = ""

    # --- TREE LOGIC ---
    def load_root(self):
        path = self.path_input.text().strip()
        if os.path.exists(path):
            self.tree.setRootIndex(self.model.index(path))
            self.inspector_stack.setCurrentIndex(0)

    def on_tree_clicked(self, index):
        path = self.model.filePath(index)
        if os.path.isdir(path):
            self.inspect_folder(path)
        else:
            self.preview_file(path)

    def show_context_menu(self, position):
        index = self.tree.indexAt(position)
        if not index.isValid(): return

        # Grab all selected files/folders from the tree
        selected_indexes = self.tree.selectionModel().selectedRows()
        paths = [self.model.filePath(idx) for idx in selected_indexes]

        # Fallback: if you right-click an item you haven't left-clicked yet
        clicked_path = self.model.filePath(index)
        if clicked_path not in paths:
            paths = [clicked_path]

        is_multi = len(paths) > 1

        menu = QMenu()
        menu.setStyleSheet(
            f"QMenu {{ background-color: #030303; color: white; border: 1px solid {ACCENT}; padding: 4px; font-family: {MONO_FONT}; }} QMenu::item:selected {{ background-color: {ACCENT}; color: black; }} QMenu::separator {{ background-color: #222; height: 1px; margin: 4px 0px; }}")

        # Only show single-target actions if one item is selected
        if not is_multi:
            term_menu = menu.addMenu(">_ Open in Terminal...")
            cmd_act = term_menu.addAction("CMD")
            ps_act = term_menu.addAction("POWERSHELL")
            bash_act = term_menu.addAction("GIT BASH")
            ub_act = term_menu.addAction("UBUNTU")

            menu.addSeparator()
            new_file_act = menu.addAction("📄 New File")
            new_dir_act = menu.addAction("📁 New Folder")
            rename_act = menu.addAction("✏️ Rename")

            menu.addSeparator()
            copy_act = menu.addAction("📋 Copy Path")
            menu.addSeparator()

        # Delete action always shows, but updates text based on count
        delete_text = f"🗑️ Recycle ({len(paths)} items)" if is_multi else "🗑️ Recycle"
        delete_act = menu.addAction(delete_text)

        action = menu.exec(self.tree.viewport().mapToGlobal(position))

        if action == delete_act:
            self.delete_target(paths)  # Send the list of paths to the recycler
        elif not is_multi:
            if action == copy_act:
                QGuiApplication.clipboard().setText(clicked_path)
            elif action == cmd_act:
                self.terminal_request.emit(clicked_path, "CMD")
            elif action == ps_act:
                self.terminal_request.emit(clicked_path, "POWERSHELL")
            elif action == bash_act:
                self.terminal_request.emit(clicked_path, "GIT BASH")
            elif action == ub_act:
                self.terminal_request.emit(clicked_path, "UBUNTU")
            elif action == new_file_act:
                self.create_file(clicked_path)
            elif action == new_dir_act:
                self.create_folder(clicked_path)
            elif action == rename_act:
                self.rename_target(clicked_path)
    # --- DATABASES & SNAPSHOTS ---
    def load_databases(self):
        if os.path.exists(BOOKMARKS_FILE):
            with open(BOOKMARKS_FILE, "r") as f: self.bookmarks = json.load(f)
        if os.path.exists(IDE_CONFIG_FILE):
            with open(IDE_CONFIG_FILE, "r") as f: self.ide_configs = json.load(f)
        if os.path.exists(PROJECTS_DATA_FILE):
            with open(PROJECTS_DATA_FILE, "r") as f: self.folder_data = json.load(f)

    def save_folder_snapshot(self):
        if self.current_inspected_path:
            norm_path = self.current_inspected_path.replace("\\", "/")
            if norm_path not in self.folder_data: self.folder_data[norm_path] = {}
            self.folder_data[norm_path]["snapshot"] = self.snapshot_input.toPlainText().strip()
            self.folder_data[norm_path]["ide"] = self.ide_combo.currentText()
            with open(PROJECTS_DATA_FILE, "w") as f:
                json.dump(self.folder_data, f, indent=4)

            btn = self.sender()
            btn.setText("SAVED ✓")
            QThread.msleep(500)
            btn.setText("SAVE SNAPSHOT")

    # --- THE DYNAMIC INSPECTOR ---
    def inspect_folder(self, path):
        self.current_inspected_path = path
        norm_path = path.replace("\\", "/")
        self.fd_title.setText(os.path.basename(path).upper() or path)
        self.fd_path.setText(norm_path)

        data = self.folder_data.get(norm_path, {})
        self.snapshot_input.setPlainText(data.get("snapshot", ""))
        self.ide_combo.setCurrentText(data.get("ide", "VS Code"))

        try:
            result = subprocess.run(["git", "status", "-s", "-b"], cwd=path, capture_output=True, text=True, check=True,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            self.git_status_lbl.setText(f"GIT STATUS:\n{result.stdout.strip()}")
            self.git_status_lbl.setStyleSheet(
                "color: #00FF41; background-color: #010201; border: 1px solid #113311; padding: 8px;")
        except subprocess.CalledProcessError:
            self.git_status_lbl.setText("GIT: Not a git repository.")
            self.git_status_lbl.setStyleSheet(
                "color: #FF8800; background-color: #110800; border: 1px solid #331100; padding: 8px;")
        except Exception:
            self.git_status_lbl.setText("GIT: Not installed or accessible.")
        self.inspector_stack.setCurrentIndex(2)

    def preview_file(self, path):
        self.current_inspected_path = path
        self.preview_header.setText(f"FILE_INSPECTOR // {os.path.basename(path)}")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read(10000)
                if len(content) == 10000: content += "\n\n... [FILE TRUNCATED] ..."
                self.preview_text.setPlainText(content)
        except:
            self.preview_text.setPlainText("[ BINARY OR UNREADABLE ]")
        self.inspector_stack.setCurrentIndex(1)

    # --- IDE LAUNCHER & WATCHER ---
    def get_ide_cmd(self, ide_name):
        if ide_name == "File Explorer": return "explorer" if os.name == "nt" else "xdg-open"
        if ide_name in self.ide_configs and self.ide_configs[ide_name]: return self.ide_configs[ide_name]
        text, ok = QInputDialog.getText(self, "Configure IDE",
                                        f"Enter launch command for '{ide_name}'\n(IMPORTANT: Use wait flags like 'code -w .' for snapshots to work!):")
        if ok and text:
            self.ide_configs[ide_name] = text.strip()
            with open(IDE_CONFIG_FILE, "w") as f: json.dump(self.ide_configs, f, indent=4)
            return text.strip()
        return None

    def launch_ide_and_watch(self):
        ide_name = self.ide_combo.currentText()
        cmd_str = self.get_ide_cmd(ide_name)
        if not cmd_str: return

        try:
            args = cmd_str.split()
            if ide_name != "File Explorer" and "." not in args: args.append(".")
            flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            process = subprocess.Popen(args, cwd=self.current_inspected_path, creationflags=flags)

            if ide_name != "File Explorer":
                self.active_watcher = IDEWatcher(process, self.current_inspected_path)
                self.active_watcher.finished_signal.connect(self.prompt_for_snapshot)
                self.active_watcher.start()
        except Exception as e:
            QMessageBox.critical(self, "Launch Error", f"Failed to launch IDE: {e}")

    def prompt_for_snapshot(self, path):
        text, ok = QInputDialog.getMultiLineText(self, "Dev Session Ended",
                                                 f"Project Closed: {os.path.basename(path)}\nLog your Dev Snapshot:")
        if ok and text:
            norm_path = path.replace("\\", "/")
            if norm_path not in self.folder_data: self.folder_data[norm_path] = {}
            self.folder_data[norm_path]["snapshot"] = text.strip()
            with open(PROJECTS_DATA_FILE, "w") as f:
                json.dump(self.folder_data, f, indent=4)
            if self.current_inspected_path == path:
                self.snapshot_input.setPlainText(text.strip())

    # --- FULL ACCESS FILE OPERATIONS ---
    def run_shell(self, cmd):
        if not self.current_inspected_path: return
        try:
            flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            subprocess.run(cmd.split(), cwd=self.current_inspected_path, check=True, creationflags=flags)
            self.inspect_folder(self.current_inspected_path)
        except Exception as e:
            QMessageBox.warning(self, "Command Failed", str(e))

    def create_folder(self, target_path=None):
        base_path = target_path if target_path else self.current_inspected_path
        if not base_path: return
        if not os.path.isdir(base_path): base_path = os.path.dirname(base_path)

        name, ok = QInputDialog.getText(self, "New Folder", "Enter folder name:")
        if ok and name:
            os.makedirs(os.path.join(base_path, name), exist_ok=True)

    def create_file(self, target_path=None):
        base_path = target_path if target_path else self.current_inspected_path
        if not base_path: return
        if not os.path.isdir(base_path): base_path = os.path.dirname(base_path)

        name, ok = QInputDialog.getText(self, "New File", "Enter file name with extension (e.g., script.py):")
        if ok and name:
            try:
                open(os.path.join(base_path, name), 'a').close()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def rename_target(self, target_path):
        if not target_path: return
        old_name = os.path.basename(target_path)
        new_name, ok = QInputDialog.getText(self, "Rename", "Enter new name:", QLineEdit.Normal, old_name)

        if ok and new_name and new_name != old_name:
            new_path = os.path.join(os.path.dirname(target_path), new_name)
            try:
                os.rename(target_path, new_path)
                if self.current_inspected_path == target_path:
                    self.inspector_stack.setCurrentIndex(0)  # Clear dashboard to prevent ghost paths
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def delete_target(self, paths=None):
        # Allow it to accept a list of paths, or default to the currently inspected path
        targets = paths if paths else [self.current_inspected_path]
        if not targets or not targets[0]: return

        # Format the warning message
        if len(targets) > 1:
            msg = f"Move {len(targets)} items to the Recycle Bin?"
        else:
            msg = f"Move {os.path.basename(targets[0])} to the Recycle Bin?"

        reply = QMessageBox.question(self, "RECYCLE TARGET", msg, QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                for target in targets:
                    # Convert C:/Path/To/File to C:\Path\To\File natively for Windows
                    clean_path = os.path.normpath(target)
                    send2trash(clean_path)

                    # Clear the dashboard if we just recycled the folder we were looking at
                if self.current_inspected_path in targets:
                    self.inspector_stack.setCurrentIndex(0)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to recycle: {e}")
    # --- BOOKMARK LOGIC ---
    def toggle_pin(self):
        current = self.path_input.text().strip().replace("\\", "/")
        if not current or not os.path.exists(current): return
        norm_b = [b.replace("\\", "/") for b in self.bookmarks]
        if current in norm_b:
            for b in self.bookmarks:
                if b.replace("\\", "/") == current: self.bookmarks.remove(b)
        else:
            self.bookmarks.append(current)
        with open(BOOKMARKS_FILE, "w") as f:
            json.dump(self.bookmarks, f)
        self.refresh_bookmarks_ui()

    def refresh_bookmarks_ui(self):
        for i in reversed(range(self.bookmark_layout.count())):
            w = self.bookmark_layout.itemAt(i).widget()
            if w: w.setParent(None)
        self.bookmark_layout.addWidget(self.btn_pin)
        for p in self.bookmarks:
            chip = QPushButton(os.path.basename(p) or p)
            chip.setStyleSheet(
                f"background-color: #111; color: {ACCENT}; border: 1px solid #333; padding: 4px 12px; border-radius: 10px; font-family: {MONO_FONT};")
            chip.clicked.connect(lambda checked=False, path=p: self.jump_to_bookmark(path))
            self.bookmark_layout.addWidget(chip)
        self.check_pin_status()

    def jump_to_bookmark(self, path):
        self.path_input.setText(path)
        self.load_root()

    def check_pin_status(self):
        current = self.path_input.text().strip().replace("\\", "/")
        norm_b = [b.replace("\\", "/") for b in self.bookmarks]
        if current in norm_b:
            self.btn_pin.setText("☆ UNPIN")
            self.btn_pin.setStyleSheet(
                f"background-color: #220000; color: #FF4444; border: 1px solid #FF4444; padding: 4px 10px; font-weight: bold; border-radius: 10px;")
        else:
            self.btn_pin.setText("★ PIN")
            self.btn_pin.setStyleSheet(
                f"background-color: transparent; color: {TEXT_DIM}; border: 1px solid {TEXT_DIM}; padding: 4px 10px; font-weight: bold; border-radius: 10px;")