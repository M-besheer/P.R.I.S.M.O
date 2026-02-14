import os
import json
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGraphicsView,
                               QGraphicsScene, QGraphicsObject, QLineEdit, QPushButton,
                               QSplitter, QTextEdit, QLabel, QScrollArea)  # <--- ADDED QScrollArea
from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPainterPath

# --- THEME CONSTANTS ---
ACCENT = "#00ECFF"
BG_PANEL = "#010101"
TEXT_DIM = "#444444"
MONO_FONT = "Consolas"
BOOKMARKS_FILE = "prismo_bookmarks.json"


class Edge(QGraphicsObject):
    def __init__(self, source_node, dest_node):
        super().__init__()
        self.source = source_node
        self.dest = dest_node
        self.setZValue(-1)

    def boundingRect(self):
        if not self.source or not self.dest: return QRectF()
        return QRectF(self.source.pos(), self.dest.pos()).normalized()

    def paint(self, painter, option, widget):
        if not self.source or not self.dest: return
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(TEXT_DIM))
        pen.setWidth(1)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)

        start = self.source.pos() + QPointF(15, self.source.rect.height())
        end = self.dest.pos() + QPointF(0, self.dest.rect.height() / 2)

        path = QPainterPath(start)
        path.cubicTo(start.x(), end.y(), start.x(), end.y(), end.x(), end.y())
        painter.drawPath(path)

    def update_position(self):
        self.prepareGeometryChange()


class Node(QGraphicsObject):
    def __init__(self, path, plugin_ref, parent_node=None):
        super().__init__()
        self.path = path
        self.name = os.path.basename(path) or path
        self.is_dir = os.path.isdir(path)
        self.plugin = plugin_ref
        self.parent_node = parent_node

        self.edges = []
        self.children_nodes = []
        self.is_expanded = False
        self.is_populated = False

        self.width = max(150, len(self.name) * 7 + 20)
        self.height = 30
        self.rect = QRectF(0, 0, self.width, self.height)

    def boundingRect(self):
        return self.rect

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        bg_color = QColor("#050505")
        border_color = QColor(ACCENT) if self.is_dir else QColor(TEXT_DIM)
        text_color = QColor("white") if self.is_dir else QColor("#AAAAAA")

        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(self.rect, 2, 2)

        painter.setPen(QPen(text_color))
        font = QFont(MONO_FONT, 9)
        if self.is_dir: font.setBold(True)
        painter.setFont(font)

        prefix = ""
        if self.is_dir: prefix = "[-] " if self.is_expanded else "[+] "
        painter.drawText(self.rect.adjusted(10, 0, -10, 0), Qt.AlignLeft | Qt.AlignVCenter, f"{prefix}{self.name}")

    def mousePressEvent(self, event):
        if self.is_dir:
            self.is_expanded = not self.is_expanded
            if self.is_expanded and not self.is_populated:
                self.plugin.populate_node(self)
                self.is_populated = True
            self.plugin.recalculate_layout()
        else:
            self.plugin.preview_file(self.path)

        self.update()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.is_dir:
            self.plugin.path_selected.emit(self.path.replace("\\", "/"))
        super().mouseDoubleClickEvent(event)


class GraphDirectoryView(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QBrush(QColor(BG_PANEL)))
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

    def wheelEvent(self, event):
        zoom_in_factor = 1.15
        if event.angleDelta().y() > 0:
            self.scale(zoom_in_factor, zoom_in_factor)
        else:
            self.scale(1 / zoom_in_factor, 1 / zoom_in_factor)


class DirectoryPlugin(QWidget):
    path_selected = Signal(str)

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # --- 1. Address Bar ---
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(15, 10, 15, 5)

        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Enter Root Path (e.g., C:\\Projects)")
        self.path_input.setStyleSheet(
            f"background-color: #030303; color: {ACCENT}; border: 1px solid #222; padding: 6px;")
        self.path_input.setFont(QFont(MONO_FONT, 10))
        self.path_input.returnPressed.connect(self.load_root)
        self.path_input.textChanged.connect(self.check_pin_status)

        btn_go = QPushButton("GENERATE MATRIX")
        btn_go.setCursor(Qt.PointingHandCursor)
        btn_go.setStyleSheet(
            f"QPushButton {{ color: {ACCENT}; font-weight: bold; border: 1px solid {ACCENT}; padding: 6px 15px; }}")
        btn_go.clicked.connect(self.load_root)

        header_layout.addWidget(self.path_input)
        header_layout.addWidget(btn_go)

        # --- 2. Quick Access Bookmarks Ribbon (NOW SCROLLABLE & COMPACT) ---
        self.bookmark_scroll = QScrollArea()
        self.bookmark_scroll.setFixedHeight(45)  # Decreased size of the ribbon
        self.bookmark_scroll.setWidgetResizable(True)
        self.bookmark_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Custom ultra-thin horizontal scrollbar styling
        self.bookmark_scroll.setStyleSheet("""
            QScrollArea { border: none; background-color: transparent; }
            QScrollBar:horizontal { height: 4px; background: transparent; }
            QScrollBar::handle:horizontal { background: #333333; border-radius: 2px; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
        """)

        self.bookmark_container = QWidget()
        self.bookmark_container.setStyleSheet("background-color: transparent;")

        self.bookmark_layout = QHBoxLayout(self.bookmark_container)
        self.bookmark_layout.setContentsMargins(15, 0, 15, 5)
        self.bookmark_layout.setSpacing(8)
        self.bookmark_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.btn_pin = QPushButton("★ PIN")
        self.btn_pin.setCursor(Qt.PointingHandCursor)
        self.btn_pin.setStyleSheet(
            f"background-color: transparent; color: {TEXT_DIM}; border: 1px solid {TEXT_DIM}; padding: 4px 10px; font-weight: bold; border-radius: 10px;")
        self.btn_pin.clicked.connect(self.toggle_pin)

        self.bookmark_scroll.setWidget(self.bookmark_container)

        self.bookmarks = []
        self.load_bookmarks()

        # --- 3. Dual Pane Splitter ---
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setStyleSheet("QSplitter::handle { background-color: #222; width: 2px; }")

        self.scene = QGraphicsScene()
        self.view = GraphDirectoryView(self.scene)
        self.root_node = None

        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)

        self.preview_header = QLabel("FILE_INSPECTOR // NO_TARGET")
        self.preview_header.setStyleSheet(
            f"background-color: #030303; color: {TEXT_DIM}; font-weight: bold; padding: 5px 10px; border-bottom: 1px solid #222;")
        self.preview_header.setFont(QFont(MONO_FONT, 9))

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setStyleSheet(f"background-color: {BG_PANEL}; color: #CCCCCC; border: none; padding: 10px;")
        self.preview_text.setFont(QFont(MONO_FONT, 9))
        self.preview_text.setLineWrapMode(QTextEdit.NoWrap)

        preview_layout.addWidget(self.preview_header)
        preview_layout.addWidget(self.preview_text)

        self.splitter.addWidget(self.view)
        self.splitter.addWidget(preview_container)
        self.splitter.setSizes([500, 500])

        self.layout.addLayout(header_layout)
        self.layout.addWidget(self.bookmark_scroll)  # Added the scroll area here
        self.layout.addWidget(self.splitter)

    # --- BOOKMARK LOGIC ---
    def load_bookmarks(self):
        if not os.path.exists(BOOKMARKS_FILE):
            # REMOVED DUMMY DATA - Starts completely blank now!
            self.bookmarks = []
            self.save_bookmarks()
        else:
            with open(BOOKMARKS_FILE, "r") as f:
                self.bookmarks = json.load(f)
        self.refresh_bookmarks_ui()

    def save_bookmarks(self):
        with open(BOOKMARKS_FILE, "w") as f: json.dump(self.bookmarks, f, indent=4)

    def refresh_bookmarks_ui(self):
        for i in reversed(range(self.bookmark_layout.count())):
            widget = self.bookmark_layout.itemAt(i).widget()
            if widget: widget.setParent(None)

        self.bookmark_layout.addWidget(self.btn_pin)

        for path in self.bookmarks:
            folder_name = os.path.basename(path) or path
            chip = QPushButton(folder_name)
            chip.setToolTip(path)
            chip.setCursor(Qt.PointingHandCursor)
            chip.setStyleSheet(
                f"background-color: #111111; color: {ACCENT}; border: 1px solid #333; padding: 4px 12px; border-radius: 10px; font-family: {MONO_FONT};")
            chip.clicked.connect(lambda checked=False, p=path: self.jump_to_bookmark(p))
            self.bookmark_layout.addWidget(chip)

        self.check_pin_status()

    def jump_to_bookmark(self, path):
        self.path_input.setText(path)
        self.load_root()

    def check_pin_status(self):
        current = self.path_input.text().strip().replace("\\", "/")
        normalized_bookmarks = [b.replace("\\", "/") for b in self.bookmarks]

        if current in normalized_bookmarks:
            self.btn_pin.setText("☆ UNPIN")
            self.btn_pin.setStyleSheet(
                f"background-color: #220000; color: #FF4444; border: 1px solid #FF4444; padding: 4px 10px; font-weight: bold; border-radius: 10px;")
        else:
            self.btn_pin.setText("★ PIN")
            self.btn_pin.setStyleSheet(
                f"background-color: transparent; color: {TEXT_DIM}; border: 1px solid {TEXT_DIM}; padding: 4px 10px; font-weight: bold; border-radius: 10px;")

    def toggle_pin(self):
        current = self.path_input.text().strip().replace("\\", "/")
        if not current or not os.path.exists(current): return

        normalized_bookmarks = [b.replace("\\", "/") for b in self.bookmarks]

        if current in normalized_bookmarks:
            for b in self.bookmarks:
                if b.replace("\\", "/") == current:
                    self.bookmarks.remove(b)
                    break
        else:
            self.bookmarks.append(current)

        self.save_bookmarks()
        self.refresh_bookmarks_ui()

    # --- GRAPH LOGIC ---
    def load_root(self):
        path = self.path_input.text().strip()
        if not os.path.exists(path) or not os.path.isdir(path):
            self.path_input.setText("ERROR: Invalid Directory")
            return

        self.scene.clear()
        self.root_node = Node(path, self)
        self.scene.addItem(self.root_node)
        self.recalculate_layout()
        self.view.centerOn(self.root_node)

    def populate_node(self, parent_node):
        try:
            items = os.listdir(parent_node.path)
        except PermissionError:
            return

        dirs, files = [], []
        for item in items:
            if os.path.isdir(os.path.join(parent_node.path, item)):
                dirs.append(item)
            else:
                files.append(item)

        dirs.sort(key=str.lower)
        files.sort(key=str.lower)
        sorted_items = dirs + files

        for item in sorted_items:
            child_node = Node(os.path.join(parent_node.path, item), self, parent_node)
            self.scene.addItem(child_node)
            parent_node.children_nodes.append(child_node)

            edge = Edge(parent_node, child_node)
            self.scene.addItem(edge)
            parent_node.edges.append(edge)
            child_node.edges.append(edge)

    def recalculate_layout(self):
        if not self.root_node: return
        current_y, x_indent, y_spacing = 0, 40, 40

        def traverse(node, depth):
            nonlocal current_y
            is_visible = (depth == 0) or (
                        node.parent_node and node.parent_node.is_expanded and node.parent_node.isVisible())
            node.setVisible(is_visible)
            for edge in node.edges: edge.setVisible(is_visible)

            if is_visible:
                node.setPos(depth * x_indent, current_y)
                for edge in node.edges: edge.update_position()
                current_y += y_spacing
                for child in node.children_nodes: traverse(child, depth + 1)
            else:
                for child in node.children_nodes: traverse(child, depth + 1)

        traverse(self.root_node, 0)
        self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-50, -50, 50, 50))

    def preview_file(self, path):
        readable_exts = ['.py', '.txt', '.md', '.json', '.c', '.h', '.cpp', '.xml', '.ini', '.bat', '.sh', '.yaml']
        ext = os.path.splitext(path)[1].lower()

        if ext in readable_exts or not ext:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read(10000)
                    if len(content) == 10000: content += "\n\n... [FILE TRUNCATED] ..."
                    self.preview_text.setPlainText(content)
                    self.preview_header.setText(f"FILE_INSPECTOR // {os.path.basename(path)}")
            except Exception as e:
                self.preview_text.setPlainText(f"[ ERROR READING FILE: {e} ]")
        else:
            self.preview_text.setPlainText("[\n  BINARY OR UNSUPPORTED FORMAT\n]")
            self.preview_header.setText("FILE_INSPECTOR // UNREADABLE")