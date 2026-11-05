"""
Dynamic Island for Windows  -  v2.3
===================================
A floating, clickable "Dynamic Island" pinned to the top of your screen.

  Collapsed (notch) : time + status glyph (music note when playing, else battery).
  Expanded          : album art + Now Playing (Spotify/any media) with prev/play/
                      next, a Quick Apps launcher, a Quick Notes pad, and
                      clock / date / battery / CPU / RAM.

LOOK
  * Accent colour is pulled from the album art, tinting the panel + play button.
  * Optional acrylic blur lets the wallpaper show through (appearance.blur).

CONTROLS
  Hover            -> expands
  Click the notch  -> pins it open (click again to unpin)
  Drag             -> move it; position is remembered
  Right-click      -> menu (Reset position, Quit)
  Esc              -> collapse (or quit if already collapsed)

Edit config.json (created next to this file) for Quick Apps, position,
appearance, and the auto-update URL.
"""

import os
import sys
import json
import time
import threading
import subprocess
from datetime import datetime

try:
    import psutil
except ImportError:
    psutil = None

import media
import updater
try:
    import win_blur
except Exception:
    win_blur = None

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QRect, QEasingCurve, Signal, QObject
from PySide6.QtGui import (
    QFont, QFontMetrics, QAction, QCursor, QPainter, QColor,
    QPixmap, QPainterPath, QLinearGradient, QBrush,
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QFrame, QLabel, QPushButton,
    QHBoxLayout, QVBoxLayout, QStackedWidget, QSizePolicy, QMenu,
    QDialog, QTextEdit, QLayout,
)

VERSION = "2.3.1"

# ------------------------------- CONFIG -------------------------------
COLLAPSED_W, COLLAPSED_H = 200, 34
EXPANDED_W,  EXPANDED_H  = 468, 272
TOP_MARGIN   = 8
ANIM_MS      = 230
FONT_FAMILY  = "Segoe UI"
DEFAULT_ACCENT = QColor(76, 217, 100)
ACCENT_WARN  = "#ff9500"

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
NOTES_PATH  = os.path.join(BASE_DIR, "notes.txt")

DEFAULT_CONFIG = {
    "position": {"mode": "center", "x": None, "y": TOP_MARGIN},
    "appearance": {"blur": True, "fill_opacity": 0.82, "accent_from_art": True},
    "update": {"auto": True, "url": "https://raw.githubusercontent.com/tomiwa-od/laptop-dynamic-island/main/latest.json"},
    "quick_apps": [
        {"label": "Spotify",  "icon": "\U0001F3B5", "type": "uri", "target": "spotify:"},
        {"label": "Camera",   "icon": "\U0001F4F7", "type": "uri", "target": "microsoft.windows.camera:"},
        {"label": "Clock",    "icon": "⏰",     "type": "uri", "target": "ms-clock:"},
        {"label": "Calc",     "icon": "\U0001F9EE", "type": "exe", "target": "calc"},
        {"label": "Settings", "icon": "⚙",     "type": "uri", "target": "ms-settings:"},
        {"label": "Notes",    "icon": "\U0001F4DD", "type": "notes", "target": ""},
    ],
}
# ----------------------------------------------------------------------


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            return cfg
        except Exception:
            pass
    save_config(DEFAULT_CONFIG)
    return json.loads(json.dumps(DEFAULT_CONFIG))


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


def launch(entry):
    t = entry.get("type")
    target = entry.get("target", "")
    try:
        if t == "uri":
            os.startfile(target)                       # noqa
        elif t == "exe":
            subprocess.Popen(target, shell=True)
    except Exception:
        if entry.get("label") == "Spotify":
            try:
                os.startfile("https://open.spotify.com")  # noqa
            except Exception:
                pass


def rounded_pixmap(pm, size, radius):
    if pm is None or pm.isNull():
        return None
    pm = pm.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    x = max(0, (pm.width() - size) // 2)
    y = max(0, (pm.height() - size) // 2)
    pm = pm.copy(x, y, size, size)
    out = QPixmap(size, size)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing, True)
    path = QPainterPath()
    path.addRoundedRect(0, 0, size, size, radius, radius)
    p.setClipPath(path)
    p.drawPixmap(0, 0, pm)
    p.end()
    return out


def accent_from(pm):
    try:
        img = pm.toImage().scaled(1, 1, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        c = img.pixelColor(0, 0)
        # lift very dark covers so the accent still reads
        h, s, v, a = c.getHsv()
        if v < 90:
            c.setHsv(h, s, 120, a)
        return c
    except Exception:
        return DEFAULT_ACCENT


class MediaWorker(QObject):
    """Polls Windows media (Spotify etc.) on a BACKGROUND thread and emits
    results to the UI. Keeps the slow SMTC / album-art calls off the UI thread
    so the island never freezes."""
    track = Signal(object)   # dict {title,artist,playing} or None
    art = Signal(object)     # image bytes or None (emitted only when the track changes)

    def __init__(self):
        super().__init__()
        self._running = True
        self._last_key = None

    def stop(self):
        self._running = False

    def run(self):
        while self._running:
            try:
                info = media.now_playing()
                if info:
                    self.track.emit(info)
                    key = info["title"] + "|" + info["artist"]
                    if key != self._last_key:
                        self._last_key = key
                        self.art.emit(media.album_art())
                else:
                    if self._last_key is not None:
                        self.art.emit(None)
                    self._last_key = None
                    self.track.emit(None)
            except Exception:
                pass
            time.sleep(1.5)


class NotesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quick Notes")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.resize(360, 320)
        self.setStyleSheet(
            "QDialog{background:#1b1b1f;}"
            "QTextEdit{background:#121214;color:#eee;border:1px solid #333;"
            "border-radius:10px;padding:10px;font-size:13px;}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        self.edit = QTextEdit()
        self.edit.setFont(QFont(FONT_FAMILY, 11))
        lay.addWidget(self.edit)
        try:
            with open(NOTES_PATH, "r", encoding="utf-8") as f:
                self.edit.setPlainText(f.read())
        except FileNotFoundError:
            pass
        self.edit.textChanged.connect(self._save)

    def _save(self):
        try:
            with open(NOTES_PATH, "w", encoding="utf-8") as f:
                f.write(self.edit.toPlainText())
        except Exception:
            pass


class DynamicIsland(QWidget):
    update_ready = Signal(str)

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.appearance = cfg.get("appearance", {})
        self._state = "collapsed"
        self.pinned = False
        self._press_global = None
        self._moved = False
        self._notes = None
        self._media = None
        self._track_key = None
        self._accent = QColor(DEFAULT_ACCENT)
        self._tick_n = 0
        self._blur_done = False

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self._build_ui()

        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(ANIM_MS)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.finished.connect(self._on_anim_finished)

        self._leave_timer = QTimer(self)
        self._leave_timer.setSingleShot(True)
        self._leave_timer.timeout.connect(self._check_leave)

        self.update_ready.connect(self._on_update_ready)

        if psutil is not None:
            psutil.cpu_percent(interval=None)

        self._place_initial()
        self._refresh()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

        # Media runs on its own thread so slow Spotify/art calls never freeze UI.
        self._mworker = MediaWorker()
        self._mworker.track.connect(self._apply_track)
        self._mworker.art.connect(self._apply_art)
        threading.Thread(target=self._mworker.run, daemon=True).start()

    # ---------------- UI ----------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSizeConstraint(QLayout.SetNoConstraint)

        self.card = QFrame()
        self.card.setObjectName("card")
        self.card.setStyleSheet(
            "#card{background:transparent;}"
            "QLabel{color:#f2f2f2;background:transparent;}"
            "QPushButton{background:transparent;color:#f0f0f0;border:none;"
            "border-radius:10px;padding:4px;}"
            "QPushButton:hover{background:rgba(255,255,255,0.14);}"
        )
        self.card.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        root.addWidget(self.card)

        card_lay = QVBoxLayout(self.card)
        card_lay.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        self.stack.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        card_lay.addWidget(self.stack)
        self.stack.addWidget(self._build_collapsed())
        self.stack.addWidget(self._build_expanded())
        self.stack.setCurrentIndex(0)

    def _build_collapsed(self):
        w = QWidget()
        w.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        lay = QHBoxLayout(w)
        lay.setContentsMargins(20, 0, 18, 0)
        self.c_time = QLabel("--:--")
        self.c_time.setFont(QFont(FONT_FAMILY, 12, QFont.DemiBold))
        self.c_status = QLabel("")
        self.c_status.setFont(QFont(FONT_FAMILY, 11))
        lay.addWidget(self.c_time, 0, Qt.AlignVCenter | Qt.AlignLeft)
        lay.addStretch(1)
        lay.addWidget(self.c_status, 0, Qt.AlignVCenter | Qt.AlignRight)
        return w

    def _build_expanded(self):
        w = QWidget()
        w.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(22, 14, 22, 12)
        lay.setSpacing(8)

        # top: clock | date + battery
        top = QHBoxLayout()
        self.e_time = QLabel("--:--")
        self.e_time.setFont(QFont(FONT_FAMILY, 24, QFont.Bold))
        top.addWidget(self.e_time, 0, Qt.AlignVCenter | Qt.AlignLeft)
        top.addStretch(1)
        right = QVBoxLayout()
        right.setSpacing(0)
        self.e_date = QLabel("")
        self.e_date.setFont(QFont(FONT_FAMILY, 9))
        self.e_date.setStyleSheet("color:#9a9a9f;")
        self.e_batt = QLabel("")
        self.e_batt.setFont(QFont(FONT_FAMILY, 11, QFont.DemiBold))
        right.addWidget(self.e_date, 0, Qt.AlignRight)
        right.addWidget(self.e_batt, 0, Qt.AlignRight)
        top.addLayout(right)
        lay.addLayout(top)

        # now playing: art + title/artist
        np = QHBoxLayout()
        self.np_art = QLabel()
        self.np_art.setFixedSize(46, 46)
        self.np_art.hide()
        np.addWidget(self.np_art, 0, Qt.AlignVCenter)
        np.addSpacing(10)
        txt = QVBoxLayout()
        txt.setSpacing(0)
        self.np_title = QLabel("Nothing playing")
        self.np_title.setFont(QFont(FONT_FAMILY, 11, QFont.DemiBold))
        self.np_artist = QLabel("")
        self.np_artist.setFont(QFont(FONT_FAMILY, 9))
        self.np_artist.setStyleSheet("color:#b9b9be;")
        txt.addWidget(self.np_title)
        txt.addWidget(self.np_artist)
        np.addLayout(txt)
        np.addStretch(1)
        lay.addLayout(np)

        # controls
        ctl = QHBoxLayout()
        ctl.addStretch(1)
        self.btn_prev = self._media_btn("⏮", media.skip_previous, 44, 34)
        self.btn_play = self._media_btn("▶", media.toggle_play_pause, 36, 36)
        self.btn_next = self._media_btn("⏭", media.skip_next, 44, 34)
        self.btn_prev.setFont(QFont(FONT_FAMILY, 15))
        self.btn_next.setFont(QFont(FONT_FAMILY, 15))
        self.btn_play.setFont(QFont(FONT_FAMILY, 13))
        ctl.addWidget(self.btn_prev)
        ctl.addWidget(self.btn_play)
        ctl.addWidget(self.btn_next)
        ctl.addStretch(1)
        lay.addLayout(ctl)
        self._style_play_button()

        # quick apps
        qa = QHBoxLayout()
        qa.setSpacing(6)
        qa.addStretch(1)
        for entry in self.cfg.get("quick_apps", []):
            btn = QPushButton(entry.get("icon", "?"))
            btn.setFont(QFont(FONT_FAMILY, 16))
            btn.setFixedSize(42, 42)
            btn.setToolTip(entry.get("label", ""))
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, e=entry: self._on_quick_app(e))
            qa.addWidget(btn)
        qa.addStretch(1)
        lay.addLayout(qa)

        # stats
        stats = QHBoxLayout()
        self.e_cpu = QLabel("CPU --")
        self.e_ram = QLabel("RAM --")
        for s in (self.e_cpu, self.e_ram):
            s.setFont(QFont(FONT_FAMILY, 9, QFont.DemiBold))
            s.setStyleSheet("color:#9a9a9f;")
        stats.addWidget(self.e_cpu, 0, Qt.AlignLeft)
        stats.addStretch(1)
        stats.addWidget(self.e_ram, 0, Qt.AlignRight)
        lay.addLayout(stats)
        lay.addStretch(1)
        return w

    def _media_btn(self, glyph, slot, w, h):
        b = QPushButton(glyph)
        b.setFixedSize(w, h)
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda: self._media_action(slot))
        return b

    def _style_play_button(self):
        a = self._accent
        self.btn_play.setStyleSheet(
            f"QPushButton{{background:{a.name()};color:#ffffff;border-radius:18px;}}"
            f"QPushButton:hover{{background:{a.lighter(118).name()};}}"
        )

    # ------------- paint (rounded + accent gradient) -------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(0, 0, -1, -1)
        radius = min(26, rect.height() / 2.0)
        alpha = int(255 * float(self.appearance.get("fill_opacity", 0.82)))
        alpha = max(120, min(255, alpha))

        top = QColor(self._accent).darker(360)   # subtle tinted top
        top.setAlpha(alpha)
        bottom = QColor(12, 12, 14, alpha)
        grad = QLinearGradient(0, 0, 0, rect.height())
        grad.setColorAt(0.0, top)
        grad.setColorAt(1.0, bottom)

        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(rect, radius, radius)
        p.end()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._blur_done and win_blur is not None and self.appearance.get("blur", True):
            self._blur_done = True
            try:
                win_blur.enable_blur(int(self.winId()), acrylic=True)
            except Exception:
                pass

    # ------------- data / refresh -------------
    def _refresh(self):
        now = datetime.now()
        t = now.strftime("%H:%M")
        self.c_time.setText(t)
        self.e_time.setText(t)
        self.e_date.setText(now.strftime("%a, %d %b"))

        batt_txt, batt_color = self._battery_bits()
        self.e_batt.setText(batt_txt)
        self.e_batt.setStyleSheet(f"color:{batt_color};")

        if psutil is not None:
            self.e_cpu.setText(f"CPU {int(psutil.cpu_percent(interval=None))}%")
            self.e_ram.setText(f"RAM {int(psutil.virtual_memory().percent)}%")

        if self._media and self._media.get("playing"):
            self.c_status.setText("♪")
            self.c_status.setStyleSheet("color:%s;" % self._accent.name())
        else:
            self.c_status.setText(batt_txt)
            self.c_status.setStyleSheet(f"color:{batt_color};")

    def _battery_bits(self):
        if psutil is None:
            return "--", "#f2f2f2"
        b = psutil.sensors_battery()
        if b is None:
            return "--", "#f2f2f2"
        pct = int(b.percent)
        plugged = bool(b.power_plugged)
        color = self._accent.name() if plugged else (ACCENT_WARN if pct <= 20 else "#f2f2f2")
        txt = f"{pct}%" + ("  ⚡" if plugged else "")
        return txt, color

    def _apply_track(self, info):
        """UI-thread slot: update Now Playing text from the worker."""
        self._media = info
        if info:
            fm = QFontMetrics(self.np_title.font())
            self.np_title.setText(fm.elidedText(info["title"], Qt.ElideRight, EXPANDED_W - 150))
            self.np_artist.setText(info["artist"])
            self.btn_play.setText("⏸" if info["playing"] else "▶")
        else:
            self.np_art.hide()
            self._set_accent(QColor(DEFAULT_ACCENT))
            if media.available():
                self.np_title.setText("Nothing playing")
            else:
                self.np_title.setText("Media off — install winrt-Windows.Media.Control")
            self.np_artist.setText("")
            self.btn_play.setText("▶")

    def _apply_art(self, data):
        """UI-thread slot: show the album cover + pull its accent colour."""
        if not data:
            self.np_art.hide()
            self._set_accent(QColor(DEFAULT_ACCENT))
            return
        pm = QPixmap()
        if not pm.loadFromData(data) or pm.isNull():
            self.np_art.hide()
            return
        rp = rounded_pixmap(pm, 46, 10)
        if rp is not None:
            self.np_art.setPixmap(rp)
            self.np_art.show()
        if self.appearance.get("accent_from_art", True):
            self._set_accent(accent_from(pm))

    def _set_accent(self, color):
        if color is None:
            color = QColor(DEFAULT_ACCENT)
        if color.name() == self._accent.name():
            return
        self._accent = color
        self._style_play_button()
        self.update()

    def _tick(self):
        self._refresh()

    def _media_action(self, slot):
        # Run the SMTC control call on a thread so clicking never blocks the UI.
        threading.Thread(target=slot, daemon=True).start()

    def _on_quick_app(self, entry):
        if entry.get("type") == "notes":
            if self._notes is None:
                self._notes = NotesDialog(self)
            self._notes.show()
            self._notes.raise_()
            self._notes.activateWindow()
        else:
            launch(entry)

    # ------------- geometry -------------
    def _screen_geo(self):
        scr = self.screen() or QApplication.primaryScreen()
        return scr.availableGeometry()

    def _place_initial(self):
        geo = QApplication.primaryScreen().availableGeometry()
        pos = self.cfg.get("position", {})
        if pos.get("mode") == "custom" and pos.get("x") is not None:
            x, y = int(pos["x"]), int(pos["y"])
        else:
            x = geo.x() + (geo.width() - COLLAPSED_W) // 2
            y = geo.y() + TOP_MARGIN
        self.setGeometry(x, y, COLLAPSED_W, COLLAPSED_H)

    def _target_rect(self, w, h):
        cur = self.geometry()
        cx = cur.center().x()
        y = cur.y()
        scr = self._screen_geo()
        x = cx - w // 2
        x = max(scr.left() + 4, min(x, scr.right() - w - 4))
        y = max(scr.top() + 4, min(y, scr.bottom() - h - 4))
        return QRect(x, y, w, h)

    def _animate(self, w, h):
        self._anim.stop()
        self._anim.setStartValue(self.geometry())
        self._anim.setEndValue(self._target_rect(w, h))
        self._anim.start()

    def expand(self):
        if self._state == "expanded":
            return
        self._state = "expanded"
        self.stack.setCurrentIndex(1)
        self._animate(EXPANDED_W, EXPANDED_H)

    def collapse(self):
        if self._state == "collapsed":
            return
        self._state = "collapsed"
        self._animate(COLLAPSED_W, COLLAPSED_H)

    def _on_anim_finished(self):
        if self._state == "collapsed":
            self.stack.setCurrentIndex(0)

    # ------------- interaction -------------
    def enterEvent(self, event):
        self._leave_timer.stop()
        self.expand()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._leave_timer.start(140)
        super().leaveEvent(event)

    def _check_leave(self):
        if not self.pinned and not self.geometry().contains(QCursor.pos()):
            self.collapse()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            self._press_winpos = self.pos()
            self._moved = False

    def mouseMoveEvent(self, event):
        if self._press_global is not None and (event.buttons() & Qt.LeftButton):
            delta = event.globalPosition().toPoint() - self._press_global
            if delta.manhattanLength() > 6:
                self._moved = True
                self.move(self._press_winpos + delta)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._press_global is not None:
            if self._moved:
                self._save_position()
            else:
                self.pinned = not self.pinned
                if self.pinned:
                    self.expand()
                elif not self.geometry().contains(QCursor.pos()):
                    self.collapse()
            self._press_global = None

    def _save_position(self):
        g = self.geometry()
        self.cfg["position"] = {"mode": "custom", "x": g.x(), "y": g.y()}
        save_config(self.cfg)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            if self._state == "expanded" or self.pinned:
                self.pinned = False
                self.collapse()
            else:
                QApplication.quit()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu{background:#1b1b1f;color:#eee;border:1px solid #333;"
            "padding:4px;border-radius:8px;}"
            "QMenu::item{padding:6px 18px;border-radius:5px;}"
            "QMenu::item:selected{background:#333;}"
        )
        reset = QAction("Reset position to center", self)
        reset.triggered.connect(self._reset_position)
        quit_a = QAction(f"Quit  (v{VERSION})", self)
        quit_a.triggered.connect(QApplication.quit)
        menu.addAction(reset)
        menu.addSeparator()
        menu.addAction(quit_a)
        menu.exec(event.globalPos())

    def _reset_position(self):
        self.cfg["position"] = {"mode": "center", "x": None, "y": TOP_MARGIN}
        save_config(self.cfg)
        geo = QApplication.primaryScreen().availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        self.move(x, geo.y() + TOP_MARGIN)

    # ------------- updates -------------
    def _on_update_ready(self, new_version):
        updater.relaunch(BASE_DIR)
        QApplication.quit()


def _start_update_check(island, url):
    def work():
        ver = updater.check_and_update(VERSION, url, BASE_DIR)
        if ver:
            island.update_ready.emit(ver)
    threading.Thread(target=work, daemon=True).start()


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    cfg = load_config()
    island = DynamicIsland(cfg)
    island.show()

    up = cfg.get("update", {})
    if up.get("auto") and up.get("url"):
        _start_update_check(island, up["url"])

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
