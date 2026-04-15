import os
import json
import requests
import datetime
import time
import re
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QScrollArea, QFrame, QStackedWidget,
                               QMessageBox, QGridLayout, QLineEdit, QSystemTrayIcon,
                               QGraphicsOpacityEffect)
from PySide6.QtCore import Qt, QThread, Signal, QUrl, QPropertyAnimation, QTimer
from PySide6.QtGui import QDesktopServices, QColor, QIcon, QPixmap
from click import style

# --- CONFIG & THEME ---
ACCENT = "#00ECFF"
URGENT = "#FF4444"
BG_DARK = "#050505"
MONO_FONT = "Consolas"
CONFIG_FILE = "lms_config.json"
MOODLE_URL = "https://lms.eng.asu.edu.eg"
MOODLE_API = f"{MOODLE_URL}/webservice/rest/server.php"


# ==========================================
# 1. UI COMPONENTS
# ==========================================

class AnimatedButton(QPushButton):
    """Reactive buttons with hover feedback."""

    def __init__(self, text, primary=False, disable=False):
        super().__init__(text)
        self.primary = primary
        self.setCursor(Qt.PointingHandCursor if not disable else Qt.ForbiddenCursor)
        self.setFixedHeight(50 if not primary else 40)
        self.disabled = disable
        self.update_style()

    def update_style(self):
        color = ACCENT if not self.primary else "black"
        bg = "transparent" if not self.primary else ACCENT

        trueStyle = style(f"""
            QPushButton {{
                background-color: {bg}; color: {color}; border: 1px solid {ACCENT};
                padding: 10px; font-weight: bold; border-radius: 4px; text-align: center;
            }}
            QPushButton:hover {{
                background-color: {ACCENT}; color: black;
            }}
        """)
        FalseStyle = style(f"""
            QPushButton {{
                background-color: {ACCENT}; color: black;
                padding: 10px; font-weight: bold; border-radius: 4px; text-align: center;
                    }}
            QPushButton:hover {{
                background-color: #00C8D9 ; color: black; border: 4px solid #FFF;
                padding: 10px; font-weight: bold; border-radius: 4px; text-align: center;
                    }}
                """)
        disableStyle = style(f"""
            QPushButton {{
                background-color: #0090A0 ; color: black; font-weight: bold;
            }}
            """)

        if self.disabled:
            self.setStyleSheet(disableStyle)
        elif self.primary:
            self.setStyleSheet(trueStyle)
        else:
            self.setStyleSheet(FalseStyle)


class InAppToast(QWidget):
    """Non-blocking notification bubble."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.SubWindow)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setStyleSheet(f"""
            background-color: rgba(10, 10, 10, 230); 
            color: {ACCENT}; border: 1px solid {ACCENT}; 
            border-radius: 4px; padding: 8px 15px;
            font-family: {MONO_FONT}; font-weight: bold;
        """)
        self.label = QLabel(self)
        self.label.setStyleSheet("color: white; background: transparent; border: none;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.addWidget(self.label)
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.hide()

    def show_msg(self, text, duration=2000):
        self.label.setText(text)
        self.adjustSize()
        p = self.parent()
        self.move((p.width() - self.width()) // 2, p.height() - 80)
        self.show()
        self.opacity_effect.setOpacity(1)
        QTimer.singleShot(duration, self.fade_out)

    def fade_out(self):
        self.anim.setDuration(500)
        self.anim.setStartValue(1)
        self.anim.setEndValue(0)
        self.anim.finished.connect(self.hide)
        self.anim.start()


class DownloadScreen(QWidget):
    """The Cartoon Modal Loading Screen (The Bear)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setStyleSheet("background-color: rgba(5, 5, 5, 245);")
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignCenter)

        self.char_label = QLabel("ʕ•ᴥ•ʔ")
        self.char_label.setAlignment(Qt.AlignCenter)
        self.char_label.setStyleSheet(f"color: {ACCENT}; font-size: 80px; background: transparent; border: none;")

        self.text_label = QLabel("SYNCING_FILES")
        self.text_label.setStyleSheet(
            f"color: white; font-family: {MONO_FONT}; font-size: 18px; font-weight: bold; margin-top: 20px;")
        self.text_label.setAlignment(Qt.AlignCenter)

        self.layout.addWidget(self.char_label)
        self.layout.addWidget(self.text_label)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.frame = 0
        self.hide()

    def start(self, text="SYNCING_FILES"):
        self.text_label.setText(text)
        self.setGeometry(self.parent().rect())
        self.raise_()
        self.show()
        if not self.timer.isActive(): self.timer.start(500)

    def stop(self):
        self.timer.stop()
        self.hide()

    def animate(self):
        self.frame = (self.frame + 1) % 4
        dots = "." * self.frame
        base = self.text_label.text().rstrip(".")
        self.text_label.setText(f"{base}{dots}")
        self.char_label.setText("ʕ•ᴥ•ʔ" if self.frame % 2 == 0 else "ʕ-ᴥ-ʔ")


class LoadingOverlay(QFrame):
    """Generic API Spinner."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setStyleSheet("background-color: rgba(5, 5, 5, 220); border: none;")
        l = QVBoxLayout(self)
        self.lbl = QLabel("CONNECTING...")
        self.lbl.setStyleSheet(f"color:{ACCENT}; font-family:{MONO_FONT}; font-weight:bold; font-size:16px;")
        l.addWidget(self.lbl, alignment=Qt.AlignCenter)
        self.hide()

    def start(self): self.setGeometry(self.parent().rect()); self.raise_(); self.show()


# ==========================================
# 2. WORKERS (Background Threads)
# ==========================================

class DownloadWorker(QThread):
    finished = Signal()
    error = Signal(str)

    def __init__(self, url, save_path, token):
        super().__init__()
        self.url = url
        self.save_path = save_path
        self.token = token

    def run(self):
        sep = "&" if "?" in self.url else "?"
        final = f"{self.url}{sep}token={self.token}"
        try:
            r = requests.get(final, stream=True, timeout=60)
            if r.status_code == 200:
                with open(self.save_path, 'wb') as f:
                    for chunk in r.iter_content(8192): f.write(chunk)
            else:
                self.error.emit("HTTP_ERROR")
        except:
            self.error.emit("NETWORK_FAIL")
        self.finished.emit()


class MoodleWorker(QThread):
    finished = Signal(dict)

    def __init__(self, params):
        super().__init__()
        self.params = params

    def run(self):
        try:
            res = requests.get(MOODLE_API, params=self.params, timeout=10).json()
            self.finished.emit({"data": res})
        except:
            self.finished.emit({})


# ==========================================
# 3. MAIN PLUGIN LOGIC
# ==========================================

class LMSPlugin(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # State
        self.token = ""
        self.userid = None
        self.course_cache = {}
        self.workers = []
        self.active_tasks = 0

        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)

        # Init Views
        self.setup_login_view()
        # self.setup_grid_view()
        # self.setup_details_view()
        # self.setup_deadlines_view()

        # # Init Overlays
        # self.toast = InAppToast(self)
        # self.loader = LoadingOverlay(self)
        # self.dl_screen = DownloadScreen(self)
        # self.setup_os_notifications()

        # # Start Sentinel
        # self.bg_timer = QTimer(self)
        # self.bg_timer.timeout.connect(self.silent_background_check)
        # self.bg_timer.start(900000)  # 15 mins

        # self.load_and_verify()

    # # --- HELPERS ---
    # def sanitize(self, n):
    #     return re.sub(r'[<>:"/\\|?*]', '_', n)
    #
    # def get_path(self, course_folder, section, filename):
    #     # 1. Resolve Root Directory
    #     root = r"C:\Users\Lenovo\Desktop\Senior-1\Spring 2026"
    #     if os.path.exists(CONFIG_FILE):
    #         try:
    #             root = json.load(open(CONFIG_FILE)).get("base_dir", root)
    #         except:
    #             pass
    #
    #     # 2. Resolve Category (The "Smarter" Sorting Hat)
    #     sec = section.upper()
    #     name = filename.upper()
    #
    #     # PRIORITY 1: ASSIGNMENTS (Look for "Assign", "Homework", "Submission")
    #     if any(x in sec for x in ["ASSIGN", "ASSIGNMENT", "H.W", "HOMEWORK", "SUBMISSION", "DELIVERABLE"]):
    #         cat = "Assignments"
    #
    #     # PRIORITY 2: LECTURES (Look for "Lec", "Week", "Topic", "Slides", "Chapter")
    #     elif any(x in sec for x in ["LEC", "LECTURE", "MATERIAL", "SLIDES", "WEEK", "TOPIC", "CHAPTER", "UNIT"]):
    #         cat = "Lectures"
    #
    #     # PRIORITY 3: PRACTICAL (Look for "Sheet", "Lab", "Tut", "Recitation")
    #     elif any(x in sec for x in ["SHEET", "LAB", "TUT", "RECITATION", "PROBLEM", "SECTION"]):
    #         cat = "Sheets_and_Labs"
    #
    #     # PRIORITY 4: PROJECTS (Look for "Project", "Milestone")
    #     elif any(x in sec for x in ["PROJECT", "MILESTONE", "GROUP"]):
    #         cat = "Projects"
    #
    #     # PRIORITY 5: EXAMS (Look for "Quiz", "Midterm", "Final")
    #     elif any(x in sec for x in ["QUIZ", "EXAM", "MIDTERM", "FINAL", "TEST"]):
    #         cat = "Exams_and_Quizzes"
    #
    #     # FALLBACK: If the section name is generic (e.g. "General"), check the FILE NAME
    #     else:
    #         if "LEC" in name or "SLIDE" in name:
    #             cat = "Lectures"
    #         elif "SHEET" in name or "TUT" in name:
    #             cat = "Sheets_and_Labs"
    #         elif "ASSIGN" in name:
    #             cat = "Assignments"
    #         else:
    #             cat = "Resources"  # The final fallback
    #
    #     # 3. Create Unique Path (Notice we use course_folder instead of code here)
    #     target_dir = os.path.join(root, course_folder, cat)
    #     os.makedirs(target_dir, exist_ok=True)
    #
    #     base, ext = os.path.splitext(self.sanitize(filename))
    #     c = 1
    #     new_name = filename
    #     full = os.path.join(target_dir, new_name)
    #
    #     # Collision Check: If "File.pdf" exists, make "File (1).pdf"
    #     while os.path.exists(full):
    #         new_name = f"{base} ({c}){ext}"
    #         full = os.path.join(target_dir, new_name)
    #         c += 1
    #
    #     return full, cat
    #
    # # --- CORE: DOWNLOAD ENGINE ---
    # def download(self, url, filename, section, course_folder):
    #     save_path, category = self.get_path(course_folder, section, filename)
    #
    #     self.active_tasks += 1
    #     self.dl_screen.start(f"GET: {filename}")
    #
    #     worker = DownloadWorker(url, save_path, self.token)
    #
    #     def on_done():
    #         if worker in self.workers: self.workers.remove(worker)
    #         self.active_tasks -= 1
    #         if self.active_tasks <= 0:
    #             self.active_tasks = 0
    #             self.dl_screen.stop()
    #             self.show_toast(f"SAVED TO {category.upper()}")
    #
    #     worker.finished.connect(on_done)
    #     self.workers.append(worker)
    #     worker.start()
    #
    # def batch_download(self, contents, section, course_folder):
    #     self.show_toast(f"BATCH START: {len(contents)} FILES")
    #     self.dl_screen.start("BATCH PROCESSING...")
    #
    #     if len(contents) == 0:
    #         self.dl_screen.start("No files found in batch...")
    #         self.show_toast("No files found in batch...")
    #         QTimer.singleShot(1000, lambda: self.dl_screen.stop())
    #         return
    #
    #     for i, item in enumerate(contents):
    #         QTimer.singleShot(i * 500, lambda u=item['fileurl'], n=item['filename']:
    #         self.download(u, n, section, course_folder))
    #
    # # --- DEEP FETCH (Assignment PDFs) ---
    # def deep_fetch(self, url, cid, course_folder):
    #     self.active_tasks += 1
    #     self.dl_screen.start("SCANNING...")
    #     try:
    #         cmid = int(url.split("id=")[-1])
    #     except:
    #         self.active_tasks -= 1;
    #         return
    #
    #     def scan_done(res):
    #         found = False
    #         data = res.get('data', {})
    #         for c in data.get('courses', []):
    #             for a in c.get('assignments', []):
    #                 if a['cmid'] == cmid:
    #                     for att in a.get('introattachments', []):
    #                         self.download(att['fileurl'], att['filename'], "Assignments", course_folder)
    #                         found = True
    #
    #         if not found:
    #             self.show_toast("NO PDF ATTACHED")
    #             QDesktopServices.openUrl(QUrl(url))
    #
    #         self.active_tasks -= 1
    #         if self.active_tasks <= 0: self.dl_screen.stop()
    #         if worker in self.workers: self.workers.remove(worker)
    #
    #     worker = MoodleWorker(
    #         {'wstoken': self.token, 'wsfunction': 'mod_assign_get_assignments', 'moodlewsrestformat': 'json',
    #          'courseids[0]': cid})
    #     worker.finished.connect(scan_done)
    #     self.workers.append(worker)
    #     worker.start()

    # --- UI RENDERERS ---
    def setup_login_view(self):
        p = QWidget()
        l = QVBoxLayout(p)
        l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        #ID input field
        u_in = QLineEdit()
        u_in.setPlaceholderText("ENTER ID")
        u_in.setFixedWidth(350)
        #PASSWORD input field
        p_in = QLineEdit()
        p_in.setPlaceholderText("ENTER PASSWORD")
        p_in.setEchoMode(QLineEdit.Password)
        p_in.setFixedWidth(350)
        #STYLE FOR FIELDS
        style = "font-family: 'Century Gothic', 'Futura', 'Montserrat', sans-serif; background:#111; color:white; padding:8px; border:1px solid #333; border-radius:5px;"
        u_in.setStyleSheet(style)
        p_in.setStyleSheet(style)

        timer = QTimer()
        timer.singleShot(1500, lambda: (
            # Credentials
            timer.stop(),
            u_in.setText("22p0223@eng.asu.edu.eg"),
            p_in.setText("Mbesheereng261")
        ))

        btn = AnimatedButton("CONNECT", primary=False, disable=False)
        btn.setFixedWidth(350)

        # btn.clicked.connect(self.perform_login)

        Label = QLabel("LMS GATEWAY", styleSheet=f"color:{ACCENT}; font-size:25px; font-weight:bold;")
        Label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(Label)
        l.addSpacing(20)
        l.addWidget(u_in)
        l.addWidget(p_in)
        l.addWidget(btn)
        self.stack.addWidget(p)
    #
    # def setup_grid_view(self):
    #     p = QWidget()
    #     l = QVBoxLayout(p)
    #     l.setContentsMargins(30, 30, 30, 30)
    #     h = QHBoxLayout()
    #     h.addWidget(QLabel("ACADEMIC GRID", styleSheet=f"color:{ACCENT}; font-size:18px; font-weight:bold;"))
    #     h.addStretch()
    #     btn = AnimatedButton("DEADLINES", primary=True)
    #     btn.clicked.connect(self.fetch_deadlines)
    #     h.addWidget(btn)
    #
    #     scroll = QScrollArea()
    #     scroll.setWidgetResizable(True)
    #     scroll.setStyleSheet("background:transparent; border:none;")
    #     self.grid_cont = QWidget()
    #     self.grid_layout = QGridLayout(self.grid_cont)
    #     self.grid_layout.setSpacing(15)
    #     scroll.setWidget(self.grid_cont)
    #     l.addLayout(h)
    #     l.addSpacing(15)
    #     l.addWidget(scroll)
    #     self.stack.addWidget(p)
    #
    # def setup_details_view(self):
    #     p = QWidget()
    #     l = QVBoxLayout(p)
    #     l.setContentsMargins(30, 30, 30, 30)
    #     h = QHBoxLayout()
    #     btn = AnimatedButton("< BACK")
    #     btn.clicked.connect(lambda: self.stack.setCurrentIndex(1))
    #     h.addWidget(btn)
    #     self.det_title = QLabel("LOADING")
    #     self.det_title.setStyleSheet("color:white; font-weight:bold; font-size:16px;")
    #     h.addSpacing(20)
    #     h.addWidget(self.det_title)
    #     h.addStretch()
    #     scroll = QScrollArea()
    #     scroll.setWidgetResizable(True)
    #     scroll.setStyleSheet("background:transparent; border:none;")
    #     self.det_cont = QWidget()
    #     self.det_layout = QVBoxLayout(self.det_cont)
    #     self.det_layout.setAlignment(Qt.AlignTop)
    #     scroll.setWidget(self.det_cont)
    #     l.addLayout(h)
    #     l.addSpacing(15)
    #     l.addWidget(scroll)
    #     self.stack.addWidget(p)
    #
    # def setup_deadlines_view(self):
    #     p = QWidget()
    #     l = QVBoxLayout(p)
    #     l.setContentsMargins(30, 30, 30, 30)
    #     h = QHBoxLayout()
    #     btn = AnimatedButton("< BACK")
    #     btn.clicked.connect(lambda: self.stack.setCurrentIndex(1))
    #     h.addWidget(btn)
    #     h.addStretch()
    #     scroll = QScrollArea()
    #     scroll.setWidgetResizable(True)
    #     scroll.setStyleSheet("background:transparent; border:none;")
    #     self.dl_cont = QWidget()
    #     self.dl_layout = QVBoxLayout(self.dl_cont)
    #     self.dl_layout.setAlignment(Qt.AlignTop)
    #     scroll.setWidget(self.dl_cont)
    #     l.addLayout(h)
    #     l.addSpacing(15)
    #     l.addWidget(scroll)
    #     self.stack.addWidget(p)
    #
    # # --- LOGIC HANDLING ---
    # def perform_login(self):
    #     u, p = self.u_in.text(), self.p_in.text()
    #     try:
    #         r = requests.post(f"{MOODLE_URL}/login/token.php",
    #                           data={'username': u, 'password': p, 'service': 'moodle_mobile_app'}).json()
    #         if 'token' in r:
    #             self.token = r['token']
    #             with open(CONFIG_FILE, "w") as f: json.dump({"token": self.token}, f)
    #             self.load_and_verify()
    #     except:
    #         pass
    #
    # def load_and_verify(self):
    #     if os.path.exists(CONFIG_FILE):
    #         try:
    #             self.token = json.load(open(CONFIG_FILE)).get('token')
    #         except:
    #             pass
    #         if self.token:
    #             self.fetch_courses();
    #             self.stack.setCurrentIndex(1)
    #         else:
    #             self.stack.setCurrentIndex(0)
    #     else:
    #         self.stack.setCurrentIndex(0)
    #
    # # --- FIX: PROPER HANDSHAKE LOGIC ---
    # def fetch_courses(self):
    #     self.loader.start()
    #
    #     # Step 2: Get Courses using the ID from Step 1
    #     def step2(res):
    #         data = res.get('data', [])
    #         if isinstance(data, dict): data = []  # Handle error case
    #
    #         while self.grid_layout.count(): self.grid_layout.takeAt(0).widget().deleteLater()
    #         r, c = 0, 0
    #
    #         # Show last 6 courses
    #         for d in data[-6:]:
    #             btn = AnimatedButton(d['fullname'])
    #             btn.clicked.connect(lambda chk=False, i=d: self.load_details(i))
    #             self.grid_layout.addWidget(btn, r, c)
    #             c += 1
    #             if c > 1: c = 0; r += 1
    #
    #         self.loader.hide()
    #         if worker in self.workers: self.workers.remove(worker)
    #
    #     # Step 1: Get User Info to verify token and get ID
    #     def step1(res):
    #         if 'userid' in res['data']:
    #             self.userid = res['data']['userid']
    #             # Start Step 2
    #             w2 = MoodleWorker(
    #                 {'wstoken': self.token, 'wsfunction': 'core_enrol_get_users_courses', 'moodlewsrestformat': 'json',
    #                  'userid': self.userid})
    #             w2.finished.connect(step2)
    #             self.workers.append(w2)
    #             w2.start()
    #         else:
    #             self.loader.hide()
    #             # Token invalid or auth failed
    #             self.stack.setCurrentIndex(0)
    #
    #     # Start Step 1
    #     worker = MoodleWorker(
    #         {'wstoken': self.token, 'wsfunction': 'core_webservice_get_site_info', 'moodlewsrestformat': 'json'})
    #     worker.finished.connect(step1)
    #     self.workers.append(worker)
    #     worker.start()
    #
    # def load_details(self, data):
    #     cid = data['id']
    #     self.det_title.setText(data['fullname'].upper())
    #     self.stack.setCurrentIndex(2)
    #     if cid in self.course_cache:
    #         self.render_details(self.course_cache[cid], data['fullname'])
    #         return
    #
    #     self.loader.start()
    #
    #     def on_ready(res):
    #         self.loader.hide()
    #         self.course_cache[cid] = res['data']
    #         self.render_details(res['data'], data['fullname'])
    #         if worker in self.workers: self.workers.remove(worker)
    #
    #     worker = MoodleWorker(
    #         {'wstoken': self.token, 'wsfunction': 'core_course_get_contents', 'moodlewsrestformat': 'json',
    #          'courseid': cid})
    #     worker.finished.connect(on_ready)
    #     self.workers.append(worker)
    #     worker.start()
    #
    # def render_details(self, sections, name):
    #     while self.det_layout.count(): self.det_layout.takeAt(0).widget().deleteLater()
    #
    #     # FIX: We now use the fully sanitized name instead of splitting it!
    #     folder_name = self.sanitize(name)
    #
    #     for sec in sections:
    #         if not sec.get('modules'): continue
    #         h = QLabel(f"// {sec['name'].upper()}", styleSheet=f"color:{ACCENT}; font-weight:bold; margin-top:20px;")
    #         self.det_layout.addWidget(h)
    #
    #         for m in sec['modules']:
    #             row = QFrame(styleSheet="background:#080808; border-bottom:1px solid #222;")
    #             rl = QHBoxLayout(row)
    #             rl.addWidget(QLabel(m['name'], styleSheet="color:#DDD; border:none;"))
    #
    #             btn_dl = QPushButton("SYNC")
    #             btn_dl.setFixedWidth(60)
    #             btn_dl.setStyleSheet(f"color:{ACCENT}; border:1px solid {ACCENT}; font-weight:bold;")
    #
    #             btn_op = QPushButton("OPEN")
    #             btn_op.setFixedWidth(60)
    #             btn_op.setStyleSheet("color:white; border:1px solid #444;")
    #
    #             if m['modname'] == 'resource' and 'contents' in m:
    #                 f = m['contents'][0]
    #                 btn_dl.clicked.connect(
    #                     lambda chk=False, u=f['fileurl'], n=f['filename'], s=sec['name'], c=folder_name: self.download(
    #                         u, n, s, c))
    #             elif m['modname'] == 'folder' and 'contents' in m:
    #                 btn_dl.setText("BATCH")
    #                 btn_dl.clicked.connect(
    #                     lambda chk=False, i=m['contents'], s=sec['name'], c=folder_name: self.batch_download(i, s, c))
    #
    #             if 'url' in m: btn_op.clicked.connect(lambda chk=False, u=m['url']: QDesktopServices.openUrl(QUrl(u)))
    #
    #             rl.addWidget(btn_dl)
    #             rl.addWidget(btn_op)
    #             self.det_layout.addWidget(row)
    #
    # def fetch_deadlines(self):
    #     self.stack.setCurrentIndex(3)
    #     self.loader.start()
    #
    #     def on_dl(res):
    #         self.loader.hide()
    #         while self.dl_layout.count(): self.dl_layout.takeAt(0).widget().deleteLater()
    #         for e in res['data'].get('events', []):
    #             # FIX: Extracting the full name to route the folders properly, while keeping the UI code short.
    #             full_course_name = e.get('course', {}).get('fullname', "GENERIC")
    #             ui_code = full_course_name.split()[0]
    #             folder_name = self.sanitize(full_course_name)
    #
    #             cid = e.get('course', {}).get('id')
    #             dl = datetime.datetime.fromtimestamp(e['timesort'])
    #             diff = (dl - datetime.datetime.now()).days
    #             clr = URGENT if diff < 2 else ACCENT
    #
    #             row = QFrame(styleSheet=f"background:#080808; border-left:4px solid {clr}; padding:10px;")
    #             rl = QHBoxLayout(row)
    #             info = QVBoxLayout()
    #             info.addWidget(
    #                 QLabel(f"[{ui_code}] {e['name']}", styleSheet="color:white; font-weight:bold; border:none;"))
    #             info.addWidget(QLabel(f"DUE: {dl.strftime('%b %d')} (T-{diff}D)",
    #                                   styleSheet=f"color:{clr}; border:none; font-family:{MONO_FONT};"))
    #
    #             btn = AnimatedButton("PORTAL", primary=True)
    #             btn.setFixedWidth(100)
    #             btn.clicked.connect(lambda chk=False, u=e['url'], i=cid, c=folder_name: self.deep_fetch(u, i, c))
    #
    #             rl.addLayout(info)
    #             rl.addStretch()
    #             rl.addWidget(btn)
    #             self.dl_layout.addWidget(row)
    #         if worker in self.workers: self.workers.remove(worker)
    #
    #     worker = MoodleWorker({'wstoken': self.token, 'wsfunction': 'core_calendar_get_action_events_by_timesort',
    #                            'moodlewsrestformat': 'json', 'timesortfrom': int(time.time())})
    #     worker.finished.connect(on_dl)
    #     self.workers.append(worker)
    #     worker.start()
    #
    # # --- SYSTEM ---
    # def setup_os_notifications(self):
    #     self.tray = QSystemTrayIcon(self)
    #     p = QPixmap(32, 32)
    #     p.fill(QColor(ACCENT))
    #     self.tray.setIcon(QIcon(p))
    #     self.tray.show()
    #
    # def show_toast(self, msg):
    #     self.toast.show_msg(msg)
    #
    # def silent_background_check(self):
    #     if not self.token: return
    #     try:
    #         hb = requests.get(MOODLE_API, params={'wstoken': self.token, 'wsfunction': 'core_webservice_get_site_info',
    #                                               'moodlewsrestformat': 'json'}, timeout=5).json()
    #         if 'exception' in hb: self.tray.showMessage("SESSION EXPIRED", "Please Login", QSystemTrayIcon.Critical,
    #                                                     3000); return
    #     except:
    #         return
    #
    #     def on_chk(res):
    #         old = set()
    #         if os.path.exists("lms_cache.json"):
    #             try:
    #                 old = set(e['id'] for e in json.load(open("lms_cache.json")))
    #             except:
    #                 pass
    #
    #         evs = res['data'].get('events', [])
    #         new = [e for e in evs if e['id'] not in old]
    #         if new:
    #             self.tray.showMessage(f"{len(new)} NEW EVENTS", f"Check P.R.I.S.M.O for details",
    #                                   QSystemTrayIcon.Information, 5000)
    #         json.dump(evs, open("lms_cache.json", "w"))
    #         if worker in self.workers: self.workers.remove(worker)
    #
    #     worker = MoodleWorker({'wstoken': self.token, 'wsfunction': 'core_calendar_get_action_events_by_timesort',
    #                            'moodlewsrestformat': 'json', 'timesortfrom': int(time.time())})
    #     worker.finished.connect(on_chk)
    #     self.workers.append(worker)
    #     worker.start()
    #
    # def resizeEvent(self, event):
    #     if self.dl_screen.isVisible(): self.dl_screen.setGeometry(self.rect())
    #     if self.loader.isVisible(): self.loader.setGeometry(self.rect())
    #     if self.toast.isVisible(): self.toast.move((self.width() - self.toast.width()) // 2, self.height() - 80)
    #     super().resizeEvent(event)