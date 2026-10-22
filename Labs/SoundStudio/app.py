"""Prophecy Sound Studio — a native, offline Windows WAV workbench."""
from __future__ import annotations

import argparse
import ctypes
from dataclasses import replace
import json
import logging
import os
from pathlib import Path
import sys
import threading
import time
import traceback

import numpy as np
import sounddevice as sd
from PySide6.QtCore import Qt, QObject, Signal, QRunnable, QThreadPool, QTimer, QUrl, QLockFile, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath, QFont, QIcon, QDesktopServices, QShortcut, QKeySequence
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QSlider, QDoubleSpinBox, QLineEdit, QListWidget,
    QListWidgetItem, QFileDialog, QComboBox, QCheckBox, QScrollArea, QSplitter, QMessageBox,
    QProgressBar, QSizePolicy, QTabWidget)

from audio_engine import (APP_ID, HERE, DEFAULT_SOURCE, DEFAULT_TARGET, DATA_DIR, Settings,
                          load_audio, render, save_render, atomic_json, output_stem, Cancelled)
from visual_audio import analyze, frequency_color

BG, PANEL, FIELD = '#10151d', '#19212d', '#111923'
TEXT, MUTED, LINE, TEAL, GOLD = '#eff4f9', '#98a9bc', '#2e3d50', '#68e0c3', '#ffbd77'

STYLE = f'''
QWidget {{ color:{TEXT}; font-family:'Segoe UI'; font-size:13px; }}
QMainWindow, QScrollArea, QWidget#canvas {{ background:{BG}; }}
QFrame#panel {{ background:{PANEL}; border:1px solid {LINE}; border-radius:10px; }}
QLabel#muted {{ color:{MUTED}; font-size:12px; }}
QLabel#section {{ color:{TEAL}; font-size:11px; font-weight:700; letter-spacing:1px; }}
QLabel#title {{ font-size:24px; font-weight:700; }}
QLabel#clipTitle {{ font-size:19px; font-weight:600; }}
QPushButton {{ background:#253345; border:1px solid #3a4a5e; border-radius:6px; padding:8px 12px; font-weight:600; }}
QPushButton:hover {{ background:#33465b; border-color:{TEAL}; }}
QPushButton:pressed {{ background:#405568; }}
QPushButton:disabled {{ color:#66758a; border-color:#293546; background:#1b2634; }}
QPushButton#primary {{ background:{TEAL}; color:#102a27; border:0; font-size:15px; padding:12px; }}
QPushButton#primary:hover {{ background:#99eed9; }}
QPushButton#primary:disabled {{ background:#304c49; color:#79908c; }}
QPushButton#preview {{ color:{GOLD}; border-color:#755d45; }}
QLineEdit, QComboBox, QDoubleSpinBox {{ background:{FIELD}; border:1px solid {LINE}; border-radius:5px; padding:6px; selection-background-color:#336b65; }}
QDoubleSpinBox QLineEdit {{ border:0; padding:0; background:transparent; }}
QDoubleSpinBox {{ padding:4px; }}
QDoubleSpinBox:disabled {{ color:#8191a5; }}
QLineEdit:focus, QDoubleSpinBox:focus {{ border-color:{TEAL}; }}
QTabWidget::pane {{ border:0; background:{BG}; }}
QTabBar::tab {{ background:{BG}; color:{MUTED}; border:0; padding:10px 14px; margin-bottom:7px; }}
QTabBar::tab:selected {{ color:{TEAL}; border-bottom:2px solid {TEAL}; }}
QTabBar::tab:hover {{ color:{TEXT}; }}
QComboBox QAbstractItemView {{ background:{PANEL}; selection-background-color:#34564f; }}
QListWidget {{ background:{FIELD}; border:1px solid {LINE}; border-radius:6px; padding:4px; outline:0; }}
QListWidget::item {{ padding:10px 6px; border-radius:4px; }}
QListWidget::item:selected {{ background:#254b47; color:#b5ffec; }}
QListWidget::item:hover {{ background:#253345; }}
QSlider::groove:horizontal {{ height:5px; background:#35465a; border-radius:2px; }}
QSlider::sub-page:horizontal {{ background:{TEAL}; border-radius:2px; }}
QSlider::handle:horizontal {{ background:#e4fff8; width:13px; margin:-5px 0; border-radius:6px; }}
QSlider::groove:vertical {{ width:5px; background:#35465a; border-radius:2px; }}
QSlider::handle:vertical {{ background:{GOLD}; height:15px; margin:0 -6px; border-radius:6px; }}
QSlider:disabled {{ opacity:.4; }}
QCheckBox {{ spacing:7px; }}
QCheckBox::indicator {{ width:15px; height:15px; border-radius:3px; border:1px solid #587086; background:{FIELD}; }}
QCheckBox::indicator:checked {{ background:{TEAL}; border-color:{TEAL}; image:url({(HERE / 'check.svg').as_posix()}); }}
QScrollArea {{ border:0; }}
QScrollBar:vertical {{ background:{BG}; width:10px; margin:0; }}
QScrollBar::handle:vertical {{ background:#3d5064; min-height:35px; border-radius:5px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QSplitter::handle {{ background:{BG}; width:9px; }}
QProgressBar {{ background:{FIELD}; border:0; border-radius:3px; max-height:5px; }}
QProgressBar::chunk {{ background:{TEAL}; }}
QToolTip {{ background:#263648; color:{TEXT}; border:1px solid #557087; padding:6px; }}
QWidget {{ font-size:12px; }}
QFrame#surface {{ background:#101621; border:1px solid #283247; border-radius:9px; }}
QFrame#strip {{ background:#161e2d; border:1px solid #263145; border-radius:7px; }}
QFrame#eqStrip {{ background:#141c2a; border:0; border-radius:6px; }}
QDialog {{ background:#101621; }}
QLabel#clipTitle {{ font-size:15px; font-weight:600; }}
QLabel#muted {{ font-size:11px; color:#8393ad; }}
QPushButton {{ padding:5px 9px; border-radius:5px; background:#202c40; border:1px solid #35425a; }}
QPushButton#primary {{ padding:7px 15px; font-size:12px; background:#a0b8fc; color:#14213d; }}
QPushButton#primary:hover {{ background:#c4d2ff; }}
QPushButton#preview {{ color:#bbcaff; border-color:#5c6f9c; background:#25324e; }}
QLineEdit, QComboBox {{ padding:5px; }}
QDoubleSpinBox {{ padding:3px; font-size:11px; }}
QDoubleSpinBox QLineEdit {{ padding:0; border:0; }}
QSlider::groove:horizontal {{ height:3px; background:#344159; }}
QSlider::handle:horizontal {{ width:10px; margin:-4px 0; border-radius:5px; background:#c0d0f7; }}
QSlider::sub-page:horizontal {{ background:#819cd2; }}
QSlider::handle:vertical {{ background:#bba9fb; }}
QListWidget::item {{ padding:9px 4px; font-size:11px; }}
QListWidget::item:selected {{ background:#2b3b59; color:#e1eaff; }}
QScrollBar:horizontal {{ height:7px; background:#101621; }}
QScrollBar::handle:horizontal {{ background:#3d5064; border-radius:3px; }}
QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal {{ width:0; }}
'''


def label(text, kind=None):
    w = QLabel(text)
    if kind:
        w.setObjectName(kind)
    return w


def button(text, fn, kind=None):
    w = QPushButton(text)
    w.clicked.connect(fn)
    if kind:
        w.setObjectName(kind)
    return w


def panel(title=None, subtitle=None):
    frame = QFrame()
    frame.setObjectName('panel')
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(10)
    if title:
        layout.addWidget(label(title, 'section'))
    if subtitle:
        note = label(subtitle, 'muted')
        note.setWordWrap(True)
        layout.addWidget(note)
    return frame, layout


class Control(QWidget):
    changed = Signal()

    def __init__(self, title, low, high, default, step=1, suffix='', tip=''):
        super().__init__()
        self.factor = 1 / step
        self.default = default
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        row = QHBoxLayout()
        row.addWidget(label(title))
        row.addStretch()
        self.spin = QDoubleSpinBox()
        self.spin.setRange(low, high)
        self.spin.setSingleStep(step)
        self.spin.setDecimals(0 if step >= 1 else (3 if step <= .001 else 1))
        self.spin.setSuffix(suffix)
        self.spin.setFixedWidth(108)
        self.spin.setKeyboardTracking(False)
        self.spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.UpDownArrows)
        row.addWidget(self.spin)
        layout.addLayout(row)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(round(low*self.factor), round(high*self.factor))
        self.slider.setSingleStep(1)
        layout.addWidget(self.slider)
        self.spin.valueChanged.connect(self.from_spin)
        self.slider.valueChanged.connect(self.from_slider)
        self.set_value(default)
        self.setToolTip(tip)
        self.slider.mouseDoubleClickEvent = lambda event: self.set_value(self.default)

    def from_spin(self, value):
        self.slider.blockSignals(True)
        self.slider.setValue(round(value*self.factor))
        self.slider.blockSignals(False)
        self.changed.emit()

    def from_slider(self, value):
        self.spin.setValue(value/self.factor)

    def value(self):
        return self.spin.value()

    def set_value(self, value):
        self.spin.setValue(value)
        self.slider.setValue(round(value*self.factor))

    def set_max(self, maximum):
        self.spin.setMaximum(maximum)
        self.slider.setMaximum(round(maximum*self.factor))


class Waveform(QWidget):
    trimChanged = Signal(float, float)
    seekRequested = Signal(float)

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(125)
        self.setMouseTracking(True)
        self.peaks = None
        self.duration = 0
        self.start, self.end = 0., 0.
        self.cursor = None
        self.drag = None
        self.setToolTip('Drag the IN / OUT handles to trim. Click inside the waveform to audition from that point.')

    def set_audio(self, samples, rate):
        self.duration = len(samples)/rate
        self.start, self.end = 0, self.duration
        bins = min(1800, len(samples))
        indices = np.linspace(0, len(samples), bins+1, dtype=int)
        self.peaks = np.stack([(samples[a:b].min(axis=0), samples[a:b].max(axis=0))
                               for a, b in zip(indices[:-1], indices[1:])])
        self.cursor = None
        self.update()

    def xpos(self, seconds):
        return 20 + (self.width()-40)*seconds/max(self.duration, 1e-12)

    def seconds(self, x):
        return np.clip((x-20)/max(1, self.width()-40), 0, 1)*self.duration

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(FIELD))
        p.setPen(QColor(LINE))
        for t in range(9):
            x = 20 + t*(self.width()-40)/8
            p.drawLine(QPointF(x, 30), QPointF(x, self.height()-28))
        if self.peaks is None:
            p.setPen(QColor(MUTED))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 'Select a WAV from the source folder to begin')
            return
        channels = self.peaks.shape[2]
        h = (self.height()-60)/channels
        left, right = self.xpos(self.start), self.xpos(self.end)
        p.fillRect(QRectF(left, 27, right-left, self.height()-54), QColor('#16332f'))
        for ch in range(channels):
            center = 30 + (ch+.5)*h
            p.setPen(QPen(QColor('#29473f'), 1))
            p.drawLine(QPointF(20, center), QPointF(self.width()-20, center))
            p.setPen(QPen(QColor(TEAL if ch == 0 else '#62bcd6'), 1))
            for i in range(len(self.peaks)):
                x = 20 + i*(self.width()-40)/max(1, len(self.peaks)-1)
                lo, hi = self.peaks[i, :, ch]
                p.drawLine(QPointF(x, center-float(hi)*h*.44), QPointF(x, center-float(lo)*h*.44))
        p.fillRect(QRectF(20, 27, max(0,left-20), self.height()-54), QColor(16,21,29,170))
        p.fillRect(QRectF(right, 27, max(0,self.width()-20-right), self.height()-54), QColor(16,21,29,170))
        p.setFont(QFont('Segoe UI', 9, QFont.Weight.Bold))
        for x, text in ((left, 'IN'), (right, 'OUT')):
            p.setPen(QPen(QColor(GOLD), 2))
            p.drawLine(QPointF(x, 23), QPointF(x, self.height()-25))
            p.fillRect(QRectF(x-5, 23, 10, 13), QColor(GOLD))
            p.drawText(QRectF(max(0,min(x-18,self.width()-40)), 2, 40, 20), Qt.AlignmentFlag.AlignCenter, text)
        p.setPen(QColor(MUTED))
        for t in range(5):
            seconds = self.duration*t/4
            x = self.xpos(seconds)
            p.drawText(QRectF(max(0,min(x-30,self.width()-65)), self.height()-22, 65, 20),
                       Qt.AlignmentFlag.AlignCenter, f'{seconds:.2f}s')
        if self.cursor is not None:
            p.setPen(QPen(QColor('#ffffff'), 1))
            x = self.xpos(self.cursor)
            p.drawLine(QPointF(x, 28), QPointF(x, self.height()-27))

    def mousePressEvent(self, event):
        if not self.duration:
            return
        x = event.position().x()
        if abs(x-self.xpos(self.start)) < 14:
            self.drag = 'start'
        elif abs(x-self.xpos(self.end)) < 14:
            self.drag = 'end'
        else:
            self.seekRequested.emit(float(self.seconds(x)))

    def mouseMoveEvent(self, event):
        if not self.drag:
            return
        value = float(self.seconds(event.position().x()))
        gap = min(.001, self.duration/2)
        if self.drag == 'start':
            self.start = min(value, self.end-gap)
        else:
            self.end = max(value, self.start+gap)
        self.trimChanged.emit(self.start, self.end)
        self.update()

    def mouseReleaseEvent(self, event):
        self.drag = None


class WorkerSignals(QObject):
    done = Signal(object)
    error = Signal(str)
    progress = Signal(str)


class Worker(QRunnable):
    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.signals = WorkerSignals()
        self.cancel = threading.Event()

    def run(self):
        try:
            self.signals.done.emit(self.fn(self.cancel, self.signals.progress.emit))
        except Cancelled as error:
            self.signals.error.emit(str(error))
        except Exception as error:
            logging.exception('Sound Studio operation failed')
            self.signals.error.emit(str(error))


class Player:
    """Callback playback; monitor gain never changes rendered/exported samples."""
    def __init__(self):
        self.stream = None
        self.samples = None
        self.index = 0
        self.rate = 48000
        self.volume = .5
        self.loop = False
        self.finished = False
        self.underflow = False

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.finished = False

    def play(self, samples, rate):
        self.stop()
        self.samples, self.rate, self.index = samples, rate, 0
        self.underflow = False

        def callback(outdata, frames, timing, status):
            if status.output_underflow:
                self.underflow = True
            outdata.fill(0)
            filled = 0
            while filled < frames:
                remaining = len(self.samples)-self.index
                n = min(remaining, frames-filled)
                outdata[filled:filled+n] = self.samples[self.index:self.index+n]*self.volume
                self.index += n
                filled += n
                if self.index >= len(self.samples):
                    if self.loop:
                        self.index = 0
                    else:
                        raise sd.CallbackStop()

        def finished():
            self.finished = True

        self.stream = sd.OutputStream(samplerate=rate, channels=samples.shape[1], dtype='float32',
                                      callback=callback, finished_callback=finished, latency='high')
        self.stream.start()


class FolderPane(QFrame):
    chosen = Signal(object)
    directoryChanged = Signal()

    def __init__(self, title, folder, output=False):
        super().__init__()
        self.setObjectName('panel')
        self.folder = Path(folder)
        self.output = output
        self.files = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 16, 14, 14)
        layout.setSpacing(11)
        layout.addWidget(label(title, 'section'))
        self.path_label = label('', 'muted')
        self.path_label.setWordWrap(True)
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.path_label)
        row = QHBoxLayout()
        row.addWidget(button('Choose folder', self.choose))
        reveal = button('↗', self.reveal)
        reveal.setFixedWidth(36)
        reveal.setToolTip('Show this folder in Windows Explorer')
        row.addWidget(reveal)
        layout.addLayout(row)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Filter sounds…')
        self.search.textChanged.connect(self.filter)
        layout.addWidget(self.search)
        row = QHBoxLayout()
        self.recursive = QCheckBox('Subfolders')
        self.recursive.setChecked(not output)
        self.recursive.toggled.connect(self.refresh)
        row.addWidget(self.recursive)
        row.addStretch()
        refresh = button('↻', self.refresh)
        refresh.setFixedWidth(36)
        refresh.setToolTip('Refresh WAV list')
        row.addWidget(refresh)
        layout.addLayout(row)
        self.list = QListWidget()
        self.list.setMinimumWidth(165)
        self.list.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        if output:
            self.list.itemDoubleClicked.connect(self.activate)
        else:
            self.list.currentItemChanged.connect(lambda current, previous: self.activate(current) if current else None)
        layout.addWidget(self.list, 1)
        self.count = label('', 'muted')
        layout.addWidget(self.count)
        note = label('Double-click a saved WAV to remix it.\nEvery loaded sound starts with fresh controls.' if output
                     else 'Select a WAV to edit.\nOriginal files are always preserved.', 'muted')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.refresh()

    def activate(self, item):
        if item:
            self.chosen.emit(Path(item.data(Qt.ItemDataRole.UserRole)))

    def choose(self):
        selected = QFileDialog.getExistingDirectory(self, 'Choose WAV folder', str(self.folder))
        if selected:
            self.folder = Path(selected)
            self.refresh()
            self.directoryChanged.emit()

    def reveal(self):
        if self.folder.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.folder)))

    def refresh(self):
        self.path_label.setText(str(self.folder))
        self.path_label.setToolTip(str(self.folder))
        try:
            iterator = self.folder.rglob('*') if self.recursive.isChecked() else self.folder.iterdir()
            self.files = sorted((p for p in iterator if p.suffix.lower() == '.wav' and p.is_file()),
                                key=lambda p: str(p.relative_to(self.folder)).lower())
            self.filter()
        except OSError as error:
            self.files = []
            self.filter()
            self.count.setText('Folder unavailable')
            self.count.setToolTip(str(error))

    def filter(self):
        previous = self.list.currentItem()
        selected = previous.data(Qt.ItemDataRole.UserRole) if previous else None
        self.list.blockSignals(True)
        self.list.clear()
        query = self.search.text().casefold()
        visible = 0
        for path in self.files:
            name = str(path.relative_to(self.folder))
            if query in name.casefold():
                item = QListWidgetItem(name)
                item.setData(Qt.ItemDataRole.UserRole, str(path))
                item.setToolTip(str(path))
                self.list.addItem(item)
                visible += 1
                if str(path) == selected:
                    self.list.setCurrentItem(item)
        self.list.blockSignals(False)
        self.count.setText(f'{visible} WAV'+('s' if visible != 1 else '') + (' · folder empty' if not self.files else ''))


class Studio(QMainWindow):
    def __init__(self, state_dir=DATA_DIR, source=None, target=None):
        super().__init__()
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.audio = None
        self.result = None
        self.result_settings = None
        self.busy = False
        self.resetting = False
        self.worker = None
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.player = Player()
        self.controls = {}
        self.play_mode = None
        self.play_start = 0
        self.closing = False
        state = {}
        try:
            state = json.loads((self.state_dir/'preferences.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            pass
        self.setWindowTitle('Prophecy Sound Studio')
        self.setWindowIcon(QIcon(str(HERE/'icon.ico')))
        self.resize(1520, 920)
        self.setMinimumSize(1280, 700)
        self.setAcceptDrops(True)
        from studio_layout import build
        build(self, state, source, target, label, button, panel, Control, FolderPane)
        self.revision = 0
        self.live_worker = None
        self.live_timer = QTimer(self)
        self.live_timer.setSingleShot(True)
        self.live_timer.setInterval(220)
        self.live_timer.timeout.connect(self.refresh_live)
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.playback_tick)
        self.identity_timer = QTimer(self)
        self.identity_timer.setSingleShot(True)
        self.identity_timer.timeout.connect(self.record_identity)
        self.identity_timer.start(200)
        self.generate_shortcut = QShortcut(QKeySequence('Ctrl+Return'), self)
        self.generate_shortcut.activated.connect(self.generate)
        self.reset_controls()
        self.update_enabled()

    def add_control(self, layout, row, column, key, *args):
        control = Control(*args)
        self.controls[key] = control
        control.changed.connect(self.edited)
        if row is None:
            layout.addWidget(control)
        else:
            layout.addWidget(control, row, column)

    def current_settings(self):
        v = {key: control.value() for key, control in self.controls.items()}
        v['speed'] /= 100
        for key in ('reverb', 'room', 'polish'):
            v[key] /= 100
        if self.audio and abs(v['end']-self.audio.duration) <= .0011:
            v['end'] = self.audio.duration
        return Settings(**v, pitch=self.pitch_spin.value(), eq=tuple(w.value() for w in self.eq_spins),
                        eq_frequencies=tuple(w.value() for w in self.eq_freqs), eq_q=tuple(w.value() for w in self.eq_widths),
                        normalize=self.normalize.isChecked(), normalize_db=self.normalize_target.value(),
                        protect=self.protect.isChecked(), sample_rate=self.rate.currentData(),
                        subtype=self.format.currentData(), channels=self.channel_mode.currentText(),
                        reverse=self.reverse.isChecked(), formants=self.formants.isChecked())

    def reset_controls(self):
        self.resetting = True
        defaults = Settings()
        for key, control in self.controls.items():
            value = getattr(defaults, key)
            if key in ('speed', 'reverb', 'room', 'polish'):
                value *= 100
            if key in ('start', 'end'):
                duration = self.audio.duration if self.audio else 1
                control.set_max(duration)
                value = duration if key == 'end' else 0
            control.set_value(value)
        for spin in self.eq_spins:
            spin.setValue(0)
        for spin,value in zip(self.eq_freqs,defaults.eq_frequencies):
            spin.setRange(20,min(20000,self.audio.rate*.45) if self.audio else 20000)
            spin.setValue(min(value,spin.maximum()))
        for spin in self.eq_widths:
            spin.setValue(.85)
        self.pitch_spin.setValue(0)
        self.reverse.setChecked(False)
        self.formants.setChecked(False)
        self.rate.setCurrentIndex(0)
        self.format.setCurrentIndex(0)
        self.channel_mode.setCurrentIndex(0)
        self.protect.setChecked(True)
        self.normalize.setChecked(False)
        self.normalize_target.setValue(-3)
        self.loop.setChecked(False)
        self.monitor.setValue(50)
        self.zoom.setCurrentIndex(0)
        self.output_name.setText(self.audio.path.stem+'_mix' if self.audio else '')
        self.resetting = False
        self.edited()

    def edited(self, *args):
        if self.resetting:
            return
        self.stop()
        self.result = None
        self.result_settings = None
        self.preview_info.setText('Updating processed audio…')
        self.normalize_target.setEnabled(self.normalize.isChecked())
        if self.audio:
            start, end = self.controls['start'].value(), self.controls['end'].value()
            if end <= start:
                sender = self.sender()
                self.resetting = True
                if sender is self.controls['start']:
                    self.controls['start'].set_value(max(0, end-.001))
                else:
                    self.controls['end'].set_value(min(self.audio.duration, start+.001))
                self.resetting = False
            s = self.current_settings()
            self.wave.start, self.wave.end = s.start, s.end
            self.wave.settings = s
            self.wave.pending = True
            self.wave.update()
            self.trim_info.setText(f'Kept: {s.end-s.start:.3f} s  →  {(s.end-s.start)/s.speed:.3f} s at this speed, before reverb tail')
            for freq,slider,band in zip(s.eq_frequencies,self.eq_sliders,self.eq_labels):
                color=frequency_color(freq).name()
                slider.setStyleSheet(f'QSlider::sub-page:horizontal {{background:{color};}} QSlider::handle:horizontal {{background:{color};}}')
                band.setStyleSheet(f'color:{color};font-weight:700;')
            self.revision += 1
            if self.live_worker:
                self.live_worker.cancel.set()
            self.live_timer.start()

    def graph_band_changed(self,index,frequency,gain,q):
        self.resetting=True
        self.eq_freqs[index].setValue(frequency)
        self.eq_spins[index].setValue(gain)
        self.eq_widths[index].setValue(q)
        self.resetting=False
        self.edited()

    def toggle_folders(self):
        show=not self.source.isVisible()
        self.source.setVisible(show)
        self.target.setVisible(show)

    def refresh_live(self):
        if not self.audio or self.busy or self.closing:
            return
        if self.live_worker:
            self.live_timer.start(100)
            return
        s,audio,revision=self.current_settings(),self.audio,self.revision
        if self.result is not None and self.result_settings==s:
            return
        self.live_badge.setText('UPDATING…')

        def work(cancel,progress):
            result=render(audio,s,cancel,progress)
            display=analyze(result[0],result[1])
            return result,display

        worker=Worker(work)
        self.live_worker=worker

        def done(value):
            self.live_worker=None
            if self.closing:
                self.close();return
            if revision==self.revision and self.audio is audio and not self.busy:
                self.accept_result(value[0],s,value[1])
                self.live_badge.setText('LIVE PREVIEW')
            else:
                self.live_timer.start(30)

        def error(message):
            self.live_worker=None
            if self.closing:
                self.close();return
            if revision!=self.revision or message.startswith('Cancelled'):
                self.live_timer.start(30)
                return
            if not self.busy:
                self.wave.pending=False
                self.wave.processed=None
                self.wave.update()
                self.preview_info.setText(message.replace('\n',' ')[:200])
                self.live_badge.setText('CHECK SETTINGS')

        worker.signals.done.connect(done)
        worker.signals.error.connect(error)
        self.pool.start(worker)

    def cancel_live(self):
        self.live_timer.stop()
        self.revision+=1
        if self.live_worker:
            self.live_worker.cancel.set()

    def wave_trim(self, start, end):
        self.resetting = True
        self.controls['start'].set_value(start)
        self.controls['end'].set_value(end)
        self.resetting = False
        self.edited()

    def update_enabled(self):
        available = self.audio is not None and not self.busy
        self.editor.setEnabled(available)
        self.wave_panel.setEnabled(available)
        self.export_panel.setEnabled(available)
        self.details.setEnabled(available)
        self.source.setEnabled(not self.busy)
        self.target.setEnabled(not self.busy)
        self.generate_shortcut.setEnabled(available)
        self.progress.setVisible(self.busy)
        self.cancel_button.setVisible(self.busy)

    def job(self, fn, done):
        if self.busy:
            return
        self.stop()
        self.cancel_live()
        self.busy = True
        self.update_enabled()
        worker = Worker(fn)
        self.worker = worker

        def completed(value):
            self.busy = False
            self.worker = None
            self.update_enabled()
            if self.closing:
                self.close()
                return
            try:
                done(value)
            except Exception as error:
                logging.exception('UI result failed')
                self.show_error(str(error))

        def failed(message):
            self.busy = False
            self.worker = None
            self.update_enabled()
            if self.closing:
                self.close()
                return
            self.show_error(message)

        worker.signals.done.connect(completed)
        worker.signals.error.connect(failed)
        worker.signals.progress.connect(self.status.setText)
        self.pool.start(worker)

    def cancel_job(self):
        if self.worker:
            self.worker.cancel.set()
            self.status.setText('Cancelling…')

    def show_error(self, message):
        self.status.setText(message.replace('\n', ' ')[:350])
        if not message.startswith('Cancelled'):
            QMessageBox.warning(self, 'Sound Studio', message)

    def load(self, path):
        if self.busy:
            return
        self.status.setText(f'Loading {Path(path).name}…')

        def loaded(value):
            audio,analysis=value
            self.audio = audio
            self.clip_title.setText(audio.path.name)
            self.clip_title.setToolTip(str(audio.path))
            peak = np.max(np.abs(audio.samples))
            dbfs = 20*np.log10(max(float(peak), 1e-12))
            self.metadata.setText(f'{audio.duration:.2f}s  ·  {audio.rate/1000:g}kHz  ·  '
                f'{"Mono" if audio.samples.shape[1] == 1 else "Stereo"}')
            self.metadata.setToolTip(f'{audio.subtype} · Source peak {dbfs:.1f} dBFS')
            self.wave.set_audio(audio.samples, audio.rate, analysis)
            self.reset_controls()
            self.update_enabled()
            self.status.setText(f'Loaded {audio.path.name}. All sound controls reset to defaults.')

        def read(cancel,progress):
            audio=load_audio(path,cancel)
            return audio,analyze(audio.samples,audio.rate)
        self.job(read,loaded)

    def play_processed_at(self,seconds):
        if not self.audio or self.busy:
            return
        if self.result is None or self.result_settings!=self.current_settings():
            self.preview()
            return
        data,rate,_=self.result
        frame=min(len(data)-1,max(0,round(seconds*rate)))
        self.play_data(data[frame:],rate,'processed',frame/rate)

    def play_original(self):
        if self.audio:
            self.play_original_at(self.current_settings().start)

    def play_original_at(self, seconds):
        if not self.audio or self.busy:
            return
        s = self.current_settings()
        start = max(s.start, min(float(seconds), s.end-1/self.audio.rate))
        data = self.audio.samples[round(start*self.audio.rate):round(s.end*self.audio.rate)]
        self.play_data(data, self.audio.rate, 'original', start)

    def play_data(self, data, rate, mode, start=0):
        if not len(data):
            return
        try:
            self.player.play(data, rate)
            self.play_mode, self.play_start = mode, start
            self.timer.start()
            self.status.setText('Playing '+('original trim' if mode == 'original' else 'processed preview')+' · Space to stop')
        except Exception as error:
            self.stop()
            self.show_error('Audio device could not play this format. Check the Windows output device.\n'+str(error))

    def stop(self):
        was_playing = self.play_mode is not None
        self.player.stop()
        self.play_mode = None
        if hasattr(self, 'timer'):
            self.timer.stop()
        if hasattr(self, 'wave'):
            self.wave.cursor = None
            self.wave.update()
        if was_playing and hasattr(self, 'status'):
            self.status.setText('Playback stopped.')

    def toggle_play(self):
        if isinstance(QApplication.focusWidget(), (QLineEdit, QDoubleSpinBox)):
            return
        if self.player.stream:
            self.stop()
        elif not self.busy:
            self.preview()

    def keyPressEvent(self, event):
        # Text fields consume spaces normally before unhandled events reach the window.
        if event.key() == Qt.Key.Key_Space and not isinstance(QApplication.focusWidget(), (QLineEdit, QDoubleSpinBox)):
            self.toggle_play()
            event.accept()
        else:
            super().keyPressEvent(event)

    def playback_tick(self):
        if self.player.finished:
            underflow = self.player.underflow
            self.stop()
            self.status.setText('Playback finished.' + (' The audio device reported an underrun.' if underflow else ''))
            return
        if self.play_mode == 'original':
            self.wave.cursor = max(0,self.play_start-self.current_settings().start) + self.player.index/self.player.rate
        elif self.play_mode == 'processed' and self.result_settings:
            self.wave.cursor = self.play_start + self.player.index/self.player.rate
        self.wave.update()

    def accept_result(self, result, settings, analysis=None):
        self.result, self.result_settings = result, settings
        self.wave.set_result(analysis if analysis is not None else analyze(result[0],result[1]),settings)
        self.live_badge.setText('LIVE PREVIEW')
        _, rate, metrics = result
        self.preview_info.setText(f'Rendered {metrics["duration"]:.3f} s  ·  {rate/1000:g} kHz  ·  '
            f'Peak {metrics["peak_dbfs"]:.1f} dBFS  ·  Est. true peak {metrics["estimated_true_peak_dbtp"]:.1f} dBTP'
            + (f'  ·  Protection {metrics["protection_gain_db"]:.1f} dB' if metrics['protection_gain_db'] else ''))
        self.preview_info.setToolTip('\n'.join(metrics['notes']) or 'No optional processing enabled.')

    def preview(self):
        if not self.audio or self.busy:
            return
        s = self.current_settings()
        if self.result is not None and s == self.result_settings:
            self.play_data(self.result[0], self.result[1], 'processed')
            return
        audio = self.audio

        def done(result):
            self.accept_result(result, s)
            self.play_data(result[0], result[1], 'processed')

        self.job(lambda cancel, progress: render(audio, s, cancel, progress), done)

    def generate(self):
        if not self.audio or self.busy:
            return
        try:
            name = output_stem(self.output_name.text())
        except ValueError as error:
            self.show_error(str(error))
            return
        s, audio, target = self.current_settings(), self.audio, self.target.folder
        cached = self.result if s == self.result_settings else None

        def work(cancel, progress):
            result = cached if cached is not None else render(audio, s, cancel, progress)
            progress('Saving WAV and processing recipe…')
            destination = save_render(audio, s, result, target, name, cancel)
            return result, destination

        def done(value):
            result, destination = value
            self.accept_result(result, s)
            self.target.refresh()
            for i in range(self.target.list.count()):
                item = self.target.list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == str(destination):
                    self.target.list.setCurrentItem(item)
                    self.target.list.scrollToItem(item)
                    break
            self.status.setText(f'Saved {destination.name} · Double-click it in Your mixes to remix.')
            self.save_preferences()

        self.job(work, done)

    def save_preferences(self):
        atomic_json(self.state_dir/'preferences.json', {'source':str(self.source.folder), 'target':str(self.target.folder)})

    def record_identity(self):
        identity = {'pid':os.getpid(), 'hwnd':int(self.winId()), 'app_id':APP_ID, 'icon':str(HERE/'icon.ico')}
        if os.name == 'nt':
            value = ctypes.c_wchar_p()
            hr = ctypes.windll.shell32.GetCurrentProcessExplicitAppUserModelID(ctypes.byref(value))
            identity['process_identity_result'] = hr
            identity['actual_process_app_id'] = value.value
            ctypes.windll.ole32.CoTaskMemFree(value)
            send = ctypes.windll.user32.SendMessageW
            send.argtypes = [ctypes.c_void_p,ctypes.c_uint,ctypes.c_size_t,ctypes.c_ssize_t]
            send.restype = ctypes.c_ssize_t
            identity['small_icon_handle'] = send(int(self.winId()), 0x7F, 0, 0)
            identity['large_icon_handle'] = send(int(self.winId()), 0x7F, 1, 0)
        atomic_json(self.state_dir/'app-identity.json', identity)

    def guide(self):
        QMessageBox.information(self, 'Quick guide',
            '1. Select a source folder and a WAV on the left. Subfolders are included by default.\n\n'
            '2. Drag IN / OUT on the waveform. Shape tone with EQ, pitch with the tall side slider, '
            'and duration with Speed. Fades are in output milliseconds; reverb tails are retained.\n\n'
            '3. Compare Original and Preview changes. Space plays/stops; Loop repeats. Listen changes '
            'only playback volume. Double-click an effect slider to reset that control.\n\n'
            '4. Name your sound and Generate WAV (Ctrl+Enter). It appears in Your mixes. Double-click '
            'a saved WAV to remix it; every loaded sound starts from defaults. Existing files are never replaced.\n\n'
            'Quality: processing stays local. 48 kHz / dithered 16-bit is the default Unreal export; '
            '24-bit is available for masters. Keep source channels unless intentionally making mono for positioning. '
            'Peak protection lowers the whole clip when needed and preserves dynamics. '
            'The true-peak meter is a 4× estimate, not a certified compliance meter.\n\n'
            'Gentle polish is optional EQ + light compression, not AI restoration. Noise reduction can remove '
            'wanted detail; use a small amount and compare. No processing can recover missing recording detail. '
            'A processing recipe is saved beside each WAV.\n\n'
            'Supports mono/stereo WAV, 8–192 kHz sources, up to 256 MB of decoded samples. '
            'There is no background rendering while the app is idle.')

    def dragEnterEvent(self, event):
        if not self.busy and event.mimeData().hasUrls():
            paths = [u.toLocalFile() for u in event.mimeData().urls()]
            if len(paths) == 1 and paths[0].lower().endswith('.wav'):
                event.acceptProposedAction()

    def dropEvent(self, event):
        self.load(Path(event.mimeData().urls()[0].toLocalFile()))

    def closeEvent(self, event):
        self.live_timer.stop()
        if self.busy or self.live_worker:
            self.closing = True
            self.cancel_job()
            self.cancel_live()
            event.ignore()
            return
        self.stop()
        self.save_preferences()
        event.accept()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-dir', type=Path, default=DATA_DIR)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--target', type=Path)
    parser.add_argument('--open', type=Path)
    args = parser.parse_args()
    args.state_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=args.state_dir/'studio.log', level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s', encoding='utf-8')
    if os.name == 'nt':
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    app = QApplication(sys.argv)
    app.setApplicationName('Prophecy Sound Studio')
    app.setOrganizationName('Prophecy')
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    app.setWindowIcon(QIcon(str(HERE/'icon.ico')))
    lock = QLockFile(str(args.state_dir/'studio.lock'))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        if os.name == 'nt':
            try:
                identity = json.loads((args.state_dir/'app-identity.json').read_text(encoding='utf-8'))
                hwnd = identity['hwnd']
                ctypes.windll.user32.ShowWindow(ctypes.c_void_p(hwnd), 9)
                ctypes.windll.user32.SetForegroundWindow(ctypes.c_void_p(hwnd))
            except (OSError, ValueError, KeyError):
                pass
        return 0
    # Only these two requested default folders are created; no source contents are modified.
    DEFAULT_SOURCE.mkdir(parents=True, exist_ok=True)
    DEFAULT_TARGET.mkdir(parents=True, exist_ok=True)
    window = Studio(args.state_dir, args.source, args.target)
    screen = app.primaryScreen().availableGeometry()
    window.resize(min(1500, screen.width()-50), min(970, screen.height()-60))
    window.show()
    if args.open:
        QTimer.singleShot(100, lambda: window.load(args.open))
    result = app.exec()
    lock.unlock()
    return result


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        logging.exception('Sound Studio startup failed')
        if os.name == 'nt':
            ctypes.windll.user32.MessageBoxW(None, traceback.format_exc()[-2500:], 'Sound Studio could not start', 0x10)
        raise
