"""MetaSounds tab: world map, soundboard, locomotion, event/zone/emitter inspectors,
attenuation editor, mixer and Unreal export."""
from __future__ import annotations

import copy
import datetime as _dt
import json
import logging
import math
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from PySide6.QtCore import QEvent, QMimeData, QObject, QPointF, QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QButtonGroup, QCheckBox, QColorDialog, QComboBox,
                               QDoubleSpinBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMenu, QMessageBox, QPlainTextEdit, QPushButton,
                               QScrollArea, QSizePolicy, QSlider, QSpinBox, QSplitter, QStackedWidget, QTabWidget,
                               QTextEdit, QToolButton, QVBoxLayout, QWidget)

import meta_engine as me
from meta_export import export_unreal
from meta_map import MapView
from meta_model import (BUS_COLORS, BUSES, DISTANCE_MODELS, FILTERS, GAITS, KIND_LABELS, KINDS, REVERBS, RULE_LABELS,
                        RULES, SELECTION_LABELS, SELECTIONS, SHAPES, Attenuation, Bed, Binding, Duck, Emitter, Event,
                        Layer, Parameter, Spot, Zone, load_project, new_id, problems, save_project, starter_project)

LOG = logging.getLogger('metasounds')
MOVE_KEYS = {Qt.Key.Key_W: 'f', Qt.Key.Key_Up: 'f', Qt.Key.Key_S: 'b', Qt.Key.Key_Down: 'b',
             Qt.Key.Key_A: 'l', Qt.Key.Key_Left: 'l', Qt.Key.Key_D: 'r', Qt.Key.Key_Right: 'r',
             Qt.Key.Key_Q: 'ccw', Qt.Key.Key_E: 'cw'}
RESERVED = set('WASDQE ')
ZONE_COLORS = ['#5fc9a8', '#e3b26b', '#d29bf0', '#8fb3ff', '#ef6f6c', '#f2d16b', '#7fd8f0']

EXTRA_STYLE = '''
QFrame#card { background:#2c2f34; border:1px solid #4b5058; border-radius:7px; }
QFrame#board { background:#2c2f34; border:1px solid #4b5058; border-radius:9px; }
QPushButton#pad { min-height:38px; text-align:left; padding:6px 10px; }
QPushButton#danger { color:#f2b8c1; }
QPushButton#record:checked { background:#963e51; border-color:#c06a7c; color:white; }
QLabel#warn { color:#f0c28c; font-size:11px; }
QLabel#hint { color:#959aa4; font-size:11px; }
QLabel#metaTitle { font-size:18px; font-weight:650; color:#e5e7eb; }
QToolButton { color:#e5e7eb; background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #494e57,stop:1 #363b43);
              border:1px solid #626975; border-radius:5px; padding:4px 8px; font-weight:600; }
QToolButton::menu-indicator { image:none; }
'''


# ====================================================================== small widgets
class _NoWheel(QObject):
    """Scrolling the inspector must not change values under the pointer."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel and not obj.hasFocus():
            event.ignore()
            return True
        return False


NO_WHEEL = _NoWheel()


def _guard(widget):
    widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    widget.installEventFilter(NO_WHEEL)
    return widget


def label(text, kind=None, wrap=False):
    w = QLabel(text)
    if kind:
        w.setObjectName(kind)
    if wrap:
        w.setWordWrap(True)
    return w


def button(text, fn, kind=None, checkable=False):
    w = QPushButton(text)
    if checkable:
        w.setCheckable(True)
    w.clicked.connect(fn)
    if kind:
        w.setObjectName(kind)
    return w


def dspin(value, low, high, step=1., decimals=0, suffix='', width=78):
    w = QDoubleSpinBox()
    w.setRange(low, high)
    w.setDecimals(decimals)
    w.setSingleStep(step)
    w.setSuffix(suffix)
    w.setKeyboardTracking(False)
    w.setValue(value)
    if width:
        w.setFixedWidth(width)
    return _guard(w)


def combo(items, current, labels=None, width=None):
    w = QComboBox()
    for key in items:
        w.addItem((labels or {}).get(key, str(key)), key)
    index = w.findData(current)
    w.setCurrentIndex(max(0, index))
    if width:
        w.setFixedWidth(width)
    return _guard(w)


def dot_icon(color):
    pixmap = QPixmap(12, 12)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(1, 1, 10, 10)
    painter.end()
    return QIcon(pixmap)


def section(text):
    w = QLabel(text)
    w.setObjectName('section')
    return w


def card():
    frame = QFrame()
    frame.setObjectName('card')
    layout = QGridLayout(frame)
    layout.setContentsMargins(9, 8, 9, 8)
    layout.setHorizontalSpacing(6)
    layout.setVerticalSpacing(5)
    return frame, layout


class LibraryList(QListWidget):
    """Drag source: file paths travel as URLs, so layers and Explorer drops share one path."""

    def __init__(self):
        super().__init__()
        self.setDragEnabled(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

    def mimeData(self, items):
        data = QMimeData()
        data.setUrls([QUrl.fromLocalFile(i.data(Qt.ItemDataRole.UserRole)) for i in items])
        return data


class FileDropList(QListWidget):
    dropped = Signal(list)
    removed = Signal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DragDropMode.DropOnly)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls()]
        paths = [p for p in paths if p.lower().endswith(('.wav', '.wave'))]
        if paths:
            self.dropped.emit(paths)
            event.acceptProposedAction()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            rows = sorted({self.row(i) for i in self.selectedItems()})
            if rows:
                self.removed.emit(rows)
                return
        super().keyPressEvent(event)


class Meter(QWidget):
    def __init__(self):
        super().__init__()
        self.value = 0.
        self.peak_hold = 0.
        self.setFixedHeight(8)
        self.setMinimumWidth(60)

    def set_level(self, peak):
        db = 20 * math.log10(max(peak, 1e-6))
        value = min(1., max(0., (db + 60) / 60))
        self.value = max(value, self.value * .8)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#25282d'))
        w = self.width() * self.value
        color = QColor('#68e0c3') if self.value < .85 else QColor('#ffbd77') if self.value < .98 else QColor('#ff7a8a')
        painter.fillRect(QRectF(0, 0, w, self.height()), color)


class AttenuationGraph(QWidget):
    """Gain vs distance past the inner shape; draggable points for the Custom model."""
    edited = Signal()

    def __init__(self):
        super().__init__()
        self.att = None
        self.drag = None
        self.setMinimumHeight(170)

    def set_attenuation(self, att):
        self.att = att
        self.update()

    def span(self):
        return max(100., self.att.falloff * 1.12)

    def area(self):
        return QRectF(36, 26, max(10, self.width() - 46), max(10, self.height() - 50))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor('#25282d'))
        if self.att is None:
            return
        att, r, span = self.att, self.area(), self.span()
        painter.setPen(QPen(QColor('#3a3e45'), 1))
        for i in range(5):
            y = r.top() + r.height() * i / 4
            painter.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
        fx = r.left() + r.width() * att.falloff / span
        painter.setPen(QPen(QColor('#5a606a'), 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(fx, r.top()), QPointF(fx, r.bottom()))

        def curve(fn, color, style=Qt.PenStyle.SolidLine, width=2.):
            path = QPainterPath()
            for i in range(121):
                d = span * i / 120
                y = r.bottom() - r.height() * fn(d)
                x = r.left() + r.width() * i / 120
                path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
            painter.setPen(QPen(QColor(color), width, style))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

        if att.reverb_send:
            curve(lambda d: me.reverb_send_level(att, d), '#bba9fb', Qt.PenStyle.DotLine, 1.5)
        if att.air_absorption:
            lo, hi = math.log(20), math.log(20000)
            curve(lambda d: (math.log(max(20, me.air_filters(att, d)[0])) - lo) / (hi - lo), '#68e0c3',
                  Qt.PenStyle.DashLine, 1.5)
        curve(lambda d: me.falloff_gain(att, d) if att.attenuate else 1., '#f4f7ff')
        if att.model == 'Custom':
            painter.setBrush(QColor('#ffbd77'))
            painter.setPen(QPen(QColor('#25282d'), 1.5))
            for x, y in att.custom_curve:
                painter.drawEllipse(QPointF(r.left() + r.width() * x * att.falloff / span, r.bottom() - r.height() * y), 4.5, 4.5)
        painter.setPen(QColor('#b0b4bd'))
        font = painter.font()
        font.setPointSizeF(8)
        painter.setFont(font)
        painter.drawText(QPointF(4, r.top() + 8), '1.0')
        painter.drawText(QPointF(4, r.bottom()), '0')
        painter.drawText(QRectF(r.left(), r.bottom() + 4, r.width(), 16), Qt.AlignmentFlag.AlignLeft,
                         'inner edge')
        painter.drawText(QRectF(r.left(), r.bottom() + 4, r.width(), 16), Qt.AlignmentFlag.AlignRight,
                         f'{span / 100:.0f} m past inner shape')
        legend = [('#f4f7ff', 'volume')]
        if att.air_absorption:
            legend.append(('#68e0c3', 'air low-pass (log Hz)'))
        if att.reverb_send:
            legend.append(('#bba9fb', 'reverb send'))
        x = r.right() - 8
        for color, text in reversed(legend):
            width = painter.fontMetrics().horizontalAdvance(text) + 18
            x -= width
            painter.setPen(QPen(QColor(color), 2))
            painter.drawLine(QPointF(x, 10), QPointF(x + 10, 10))
            painter.setPen(QColor('#98a9bc'))
            painter.drawText(QPointF(x + 13, 14), text)

    def _point(self, pos):
        r, span, att = self.area(), self.span(), self.att
        x = (pos.x() - r.left()) / r.width() * span / max(att.falloff, 1.)
        y = (r.bottom() - pos.y()) / r.height()
        return min(1., max(0., x)), min(1., max(0., y))

    def mousePressEvent(self, event):
        if not self.att or self.att.model != 'Custom':
            return
        r, span = self.area(), self.span()
        pts = self.att.custom_curve
        for index, (x, y) in enumerate(pts):
            screen = QPointF(r.left() + r.width() * x * self.att.falloff / span, r.bottom() - r.height() * y)
            if (screen - event.position()).manhattanLength() < 10:
                if event.button() == Qt.MouseButton.RightButton and 0 < index < len(pts) - 1:
                    pts.pop(index)
                    self.edited.emit()
                    self.update()
                    return
                self.drag = index
                return

    def mouseDoubleClickEvent(self, event):
        if self.att and self.att.model == 'Custom':
            x, y = self._point(event.position())
            self.att.custom_curve.append([x, y])
            self.att.custom_curve.sort()
            self.edited.emit()
            self.update()

    def mouseMoveEvent(self, event):
        if self.drag is None:
            return
        pts = self.att.custom_curve
        x, y = self._point(event.position())
        if self.drag == 0:
            x = 0.
        elif self.drag == len(pts) - 1:
            x = 1.
        else:
            x = min(max(x, pts[self.drag - 1][0] + .01), pts[self.drag + 1][0] - .01)
        pts[self.drag] = [round(x, 3), round(y, 3)]
        self.update()

    def mouseReleaseEvent(self, event):
        if self.drag is not None:
            self.drag = None
            self.edited.emit()


# ====================================================================== the tab
class MetaSoundsTab(QWidget):
    def __init__(self, window, home, libraries):
        super().__init__()
        self.window = window
        self.home = Path(home)
        self.libraries = libraries
        self.setObjectName('canvas')
        self.setStyleSheet(EXTRA_STYLE)
        self.prefs_path = Path(window.state_dir) / 'metasounds.json'
        prefs = {}
        try:
            prefs = json.loads(self.prefs_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            pass
        self.project_path = Path(prefs.get('project') or self.home / 'Prophecy.metasounds.json')
        self.library_folder = prefs.get('library') or str(libraries[0][1])
        self.export_folder = prefs.get('export') or str(self.home)
        self.project = None
        try:
            if self.project_path.is_file():
                self.project = load_project(self.project_path)
        except Exception as error:
            LOG.exception('Could not open MetaSounds project')
            self.project_error = str(error)
        if self.project is None:
            self.project = starter_project()
        self.engine = me.Engine(self.project)
        self.engine.clips.request(self.project.referenced_files())
        self.pad_values = {}
        self.selected_event = ''
        self.selected_pad = ''
        self.selection = ('', '')
        self.keys = set()
        self.dirty = False
        self.active = False
        self.last_move = time.monotonic()
        self.att_selected = self.project.attenuations[0].id if self.project.attenuations else ''
        self.build()
        world = self.project.world
        self.map.listener = [world.start_x, world.start_y]
        self.engine.set_listener(world.start_x, world.start_y, 0.)

        self.push_timer = self.timer(120, self.push, True)
        self.save_timer = self.timer(1500, self.save, True)
        self.ui_timer = self.timer(40, self.tick)
        self.move_timer = self.timer(16, self.move_tick)
        self.problem_timer = self.timer(400, self.refresh_problems, True)
        self.refresh_all()
        QApplication.instance().installEventFilter(self)

    def timer(self, interval, fn, single=False):
        t = QTimer(self)
        t.setInterval(interval)
        t.setSingleShot(single)
        t.timeout.connect(fn)
        return t

    # ------------------------------------------------------------ building
    def build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 8, 14, 8)
        outer.setSpacing(8)
        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(label('MetaSounds', 'metaTitle'))
        self.audio_button = button('Audio on', self.toggle_audio, checkable=True)
        self.audio_button.setChecked(True)
        header.addWidget(self.audio_button)
        header.addSpacing(6)
        self.state_combos = {}
        for group in ('TimeOfDay', 'Weather'):
            header.addWidget(label({'TimeOfDay': 'Time', 'Weather': 'Weather'}[group], 'muted'))
            box = QComboBox()
            box.currentIndexChanged.connect(lambda _, g=group: self.state_changed(g))
            self.state_combos[group] = _guard(box)
            header.addWidget(box)
        self.status = label('', 'muted')
        self.status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.status, 1)
        self.voice_label = label('', 'muted')
        header.addWidget(self.voice_label)
        self.record_button = button('● Record', self.toggle_record, 'record', checkable=True)
        header.addWidget(self.record_button)
        header.addWidget(button('Export for Unreal', self.export, 'primary'))
        outer.addLayout(header)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        split.addWidget(self.build_left())
        split.addWidget(self.build_center())
        self.right = QTabWidget()
        self.right.setMinimumWidth(425)
        self.inspector_scroll = QScrollArea()
        self.inspector_scroll.setWidgetResizable(True)
        self.right.addTab(self.inspector_scroll, 'Inspector')
        self.att_page = QScrollArea()
        self.att_page.setWidgetResizable(True)
        self.right.addTab(self.att_page, 'Attenuation')
        self.mixer_page = QScrollArea()
        self.mixer_page.setWidgetResizable(True)
        self.right.addTab(self.mixer_page, 'Mixer')
        self.project_page = QScrollArea()
        self.project_page.setWidgetResizable(True)
        self.right.addTab(self.project_page, 'Project')
        split.addWidget(self.right)
        split.setStretchFactor(1, 1)
        split.setSizes([220, 790, 455])
        for scroll in (self.inspector_scroll, self.att_page, self.mixer_page, self.project_page):
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(split, 1)

    def build_left(self):
        left = QWidget()
        left.setMinimumWidth(205)
        left.setMaximumWidth(330)
        layout = QVBoxLayout(left)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        events = QFrame()
        events.setObjectName('panel')
        el = QVBoxLayout(events)
        el.setContentsMargins(10, 9, 10, 9)
        el.setSpacing(6)
        el.addWidget(section('EVENTS'))
        self.event_list = QListWidget()
        self.event_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.event_list.currentItemChanged.connect(self.event_picked)
        el.addWidget(self.event_list, 1)
        row = QHBoxLayout()
        row.addWidget(button('+ New', self.new_event))
        row.addWidget(button('Copy', self.duplicate_event))
        row.addWidget(button('Delete', self.delete_event, 'danger'))
        el.addLayout(row)
        layout.addWidget(events, 3)

        library = QFrame()
        library.setObjectName('panel')
        ll = QVBoxLayout(library)
        ll.setContentsMargins(10, 9, 10, 9)
        ll.setSpacing(6)
        ll.addWidget(section('LIBRARY'))
        self.folder_combo = QComboBox()
        self.folder_combo.activated.connect(self.folder_chosen)
        ll.addWidget(_guard(self.folder_combo))
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText('Filter sounds')
        self.filter_edit.textChanged.connect(self.fill_library)
        ll.addWidget(self.filter_edit)
        self.library = LibraryList()
        self.library.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.library.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.library.itemDoubleClicked.connect(lambda item: self.preview(item.data(Qt.ItemDataRole.UserRole)))
        ll.addWidget(self.library, 1)
        row = QHBoxLayout()
        row.addWidget(button('▶', self.preview_selected))
        row.addWidget(button('■', self.engine.stop_preview))
        row.addWidget(button('Add to layer', self.add_selected_to_layer), 1)
        ll.addLayout(row)
        ll.addWidget(label('Drag sounds onto a layer.', 'hint'))
        layout.addWidget(library, 4)
        return left

    def build_center(self):
        center = QWidget()
        layout = QVBoxLayout(center)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        tools = QHBoxLayout()
        tools.setSpacing(5)
        self.mode_group = QButtonGroup(self)
        self.mode_buttons = {}
        for mode, text in (('move', 'Move'), ('edit', 'Edit'), ('zone', 'Draw zone'),
                           ('emitter', 'Place emitter'), ('play', 'Play at point')):
            b = button(text, lambda _=False, m=mode: self.set_mode(m), checkable=True)
            self.mode_group.addButton(b)
            self.mode_buttons[mode] = b
            tools.addWidget(b)
        self.mode_buttons['move'].setChecked(True)
        tools.addStretch()
        tools.addWidget(button('Fit map', lambda: self.map.fit()))
        layout.addLayout(tools)
        self.map = MapView()
        self.map.listenerMoved.connect(self.listener_moved)
        self.map.cameraTurned.connect(self.camera_turned)
        self.map.selectionChanged.connect(self.map_selected)
        self.map.geometryEdited.connect(lambda: self.changed())
        self.map.zoneDrawn.connect(self.zone_drawn)
        self.map.emitterPlaced.connect(self.emitter_placed)
        self.map.playAt.connect(self.play_at)
        self.map.deleteRequested.connect(self.delete_selection)
        layout.addWidget(self.map, 1)

        board = QFrame()
        board.setObjectName('board')
        bl = QVBoxLayout(board)
        bl.setContentsMargins(10, 8, 10, 8)
        bl.setSpacing(7)
        loco = QHBoxLayout()
        loco.setSpacing(5)
        loco.addWidget(section('LOCOMOTION'))
        self.gait_group = QButtonGroup(self)
        self.gait_buttons = {}
        for gait in GAITS:
            b = button(gait, lambda _=False, g=gait: self.set_gait(g), 'gait', checkable=True)
            self.gait_group.addButton(b)
            self.gait_buttons[gait] = b
            loco.addWidget(b)
        self.gait_buttons['Idle'].setChecked(True)
        loco.addWidget(button('Jump', self.jump))
        self.surface_label = label('', 'muted')
        hint = label('WASD move · Q/E turn · Space jump · Esc stop', 'hint')
        hint.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        hint.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        loco.addWidget(hint, 1)
        bl.addLayout(loco)
        pads_row = QHBoxLayout()
        pads_row.setSpacing(10)
        pad_column = QVBoxLayout()
        pad_column.setSpacing(4)
        pad_column.addWidget(section('SOUNDBOARD'))
        self.pad_grid = QGridLayout()
        self.pad_grid.setSpacing(5)
        pad_column.addLayout(self.pad_grid)
        pad_column.addStretch()
        pads_row.addLayout(pad_column, 3)
        self.pad_params = QVBoxLayout()
        self.pad_params.setSpacing(4)
        holder = QWidget()
        holder.setLayout(self.pad_params)
        holder.setMinimumWidth(220)
        holder.setMaximumWidth(320)
        pads_row.addWidget(holder, 1)
        bl.addLayout(pads_row)
        layout.addWidget(board)
        return center

    # ------------------------------------------------------------ refresh helpers
    def refresh_all(self):
        self.map.set_project(self.project)
        self.fill_states()
        self.fill_events()
        self.fill_pads()
        self.fill_folders()
        self.fill_library()
        self.build_attenuation_page()
        self.build_mixer_page()
        self.build_project_page()
        self.show_inspector(*self.selection)
        self.refresh_problems()

    def fill_states(self):
        for group, box in self.state_combos.items():
            box.blockSignals(True)
            box.clear()
            for value in self.project.states.get(group, []):
                box.addItem(value)
            index = box.findText(self.project.state_values.get(group, ''))
            box.setCurrentIndex(max(0, index))
            box.blockSignals(False)
            if box.count() and self.project.state_values.get(group) != box.currentText():
                self.project.state_values[group] = box.currentText()

    def fill_events(self):
        current = self.selected_event
        self.event_list.blockSignals(True)
        self.event_list.clear()
        order = {b: i for i, b in enumerate(BUSES)}
        found = getattr(self, 'problems', {})
        for event in sorted(self.project.events, key=lambda e: (order.get(e.bus, 99), e.name.lower())):
            text = event.name + ('   ⚠' if event.id in found else '')
            sub = f"{KIND_LABELS[event.kind]} · {event.spatial}"
            item = QListWidgetItem(dot_icon(BUS_COLORS.get(event.bus, '#8fb3ff')), f'{text}\n{sub}')
            item.setData(Qt.ItemDataRole.UserRole, event.id)
            self.event_list.addItem(item)
            if event.id == current:
                self.event_list.setCurrentItem(item)
        self.event_list.blockSignals(False)

    def fill_pads(self):
        while self.pad_grid.count():
            widget = self.pad_grid.takeAt(0).widget()
            if widget:
                widget.deleteLater()
        self.pad_buttons = {}
        pads = [e for e in self.project.events if e.pad]
        if not pads:
            self.pad_grid.addWidget(label('Tick "Show on soundboard" on any event to add a pad.', 'hint'), 0, 0)
        for index, event in enumerate(pads):
            key = event.hotkey.upper()[:1]
            text = (f'{key}   ' if key else '') + event.name
            b = button(text, lambda _=False, e=event.id: self.pad_pressed(e), 'pad', checkable=event.kind != 'oneshot')
            self.pad_buttons[event.id] = b
            self.pad_grid.addWidget(b, index // 4, index % 4)
        if self.selected_pad not in {e.id for e in pads}:
            self.selected_pad = pads[0].id if pads else ''
        self.fill_pad_params()

    def fill_pad_params(self):
        while self.pad_params.count():
            item = self.pad_params.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        event = self.project.event(self.selected_pad)
        if event is None:
            return
        self.pad_params.addWidget(section(event.name.upper()))
        values = self.pad_values.setdefault(event.id, {})
        shown = 0
        for p in event.parameters:
            if p.kind != 'float' or p.automatic:
                continue
            shown += 1
            row = QHBoxLayout()
            row.addWidget(label(p.name, 'muted'))
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 1000)
            span = (p.maximum - p.minimum) or 1.
            value = values.get(p.name, p.default)
            slider.setValue(round((value - p.minimum) / span * 1000))
            readout = label(f'{value:.2f}', 'muted')
            readout.setFixedWidth(34)

            def moved(v, p=p, readout=readout, span=span):
                val = p.minimum + span * v / 1000
                self.pad_values[event.id][p.name] = val
                readout.setText(f'{val:.2f}')
            slider.valueChanged.connect(moved)
            row.addWidget(_guard(slider), 1)
            row.addWidget(readout)
            holder = QWidget()
            holder.setLayout(row)
            self.pad_params.addWidget(holder)
        if not shown:
            self.pad_params.addWidget(label('No sliders: add a Float parameter in the inspector.', 'hint', True))
        self.pad_params.addStretch()

    def fill_folders(self):
        self.folder_combo.blockSignals(True)
        self.folder_combo.clear()
        known = [(name, str(path)) for name, path in self.libraries]
        if self.library_folder not in [p for _, p in known]:
            known.append((Path(self.library_folder).name or self.library_folder, self.library_folder))
        for name, path in known:
            self.folder_combo.addItem(name, path)
        self.folder_combo.addItem('Choose folder…', '')
        self.folder_combo.setCurrentIndex(max(0, self.folder_combo.findData(self.library_folder)))
        self.folder_combo.blockSignals(False)

    def fill_library(self):
        self.library.clear()
        root = Path(self.library_folder)
        needle = self.filter_edit.text().strip().lower()
        try:
            files = sorted((p for p in root.rglob('*') if p.suffix.lower() in ('.wav', '.wave') and p.is_file()),
                           key=lambda p: str(p.relative_to(root)).lower())
        except OSError:
            files = []
        for path in files[:4000]:
            name = str(path.relative_to(root))
            if needle and needle not in name.lower():
                continue
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.library.addItem(item)
        if not files:
            item = QListWidgetItem('No WAV files in this folder yet')
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.library.addItem(item)

    def refresh_problems(self):
        self.problems = problems(self.project, self.engine.clips.info)
        self.fill_events()

    # ------------------------------------------------------------ change plumbing
    def changed(self, lists=False, inspector=False, pads=False):
        self.dirty = True
        self.push_timer.start()
        self.save_timer.start()
        self.problem_timer.start()
        self.map.update()
        if lists:
            self.fill_events()
        if pads or lists:
            self.fill_pads()
        if inspector:
            QTimer.singleShot(0, lambda: self.show_inspector(*self.selection))

    def push(self):
        self.engine.clips.retain(set(self.project.referenced_files()))
        self.engine.set_project(self.project)

    def save(self):
        try:
            save_project(self.project, self.project_path)
            self.project_path.parent.mkdir(parents=True, exist_ok=True)
            self.prefs_path.parent.mkdir(parents=True, exist_ok=True)
            self.prefs_path.write_text(json.dumps({'project': str(self.project_path), 'library': self.library_folder,
                                                   'export': self.export_folder}), encoding='utf-8')
            self.dirty = False
        except OSError as error:
            self.say(f'Could not save the project: {error}', True)

    def say(self, text, problem=False):
        self.status.setText(text)
        self.status.setStyleSheet(f"color:{'#f0c28c' if problem else '#b0b4bd'};font-size:11px;")

    # ------------------------------------------------------------ activation and timers
    def activate(self):
        self.active = True
        self.ui_timer.start()
        self.move_timer.start()
        if self.audio_button.isChecked():
            self.start_audio()

    def deactivate(self):
        self.active = False
        self.keys.clear()
        self.engine.set_moving(False)
        self.ui_timer.stop()
        self.move_timer.stop()
        self.engine.stop_output()

    def start_audio(self):
        try:
            self.engine.start_output()
            self.say('Audio running. Click the map to move; pads and WASD are live.')
        except Exception as error:
            LOG.exception('MetaSounds audio failed to start')
            self.audio_button.setChecked(False)
            self.say(f'Audio device unavailable: {error}', True)

    def toggle_audio(self):
        if self.audio_button.isChecked():
            self.start_audio()
        else:
            self.engine.stop_output()
            self.say('Audio paused.')

    def tick(self):
        snap = self.engine.snapshot
        if not snap:
            return
        self.map.set_snapshot(snap)
        self.voice_label.setText(f"{snap['audible']} audible / {snap['count']} voices · CPU {snap['cpu'] * 100:.0f}%")
        running = snap.get('pads', set())
        for ident, b in getattr(self, 'pad_buttons', {}).items():
            if b.isCheckable() and b.isChecked() != (ident in running):
                b.setChecked(ident in running)
        for name, meter in getattr(self, 'meters', {}).items():
            meter.set_level(snap['master'] if name == '__master__' else snap['peaks'].get(name, 0.))
        if hasattr(self, 'reduction_label'):
            self.reduction_label.setText(f"Limiter {snap['reduction_db']:.1f} dB")
        if snap.get('recording') is not None:
            self.record_button.setText(f"● {snap['recording']:.0f} s")
        if snap['unavailable']:
            names = ', '.join(Path(p).name for p in snap['unavailable'][-3:])
            self.say(f'Could not play: {names}', True)
            self.engine.unavailable.clear()
        if self.engine.error:
            self.say(f'Audio error: {self.engine.error}', True)
            self.engine.error = ''

    def move_tick(self):
        now = time.monotonic()
        dt = min(.05, now - self.last_move)
        self.last_move = now
        if not self.keys:
            return
        camera = self.map.camera
        if 'ccw' in self.keys:
            camera -= 2.2 * dt
        if 'cw' in self.keys:
            camera += 2.2 * dt
        forward = ('f' in self.keys) - ('b' in self.keys)
        side = ('r' in self.keys) - ('l' in self.keys)
        moving = bool(forward or side)
        x, y = self.map.listener
        if moving:
            gait = self.engine.gait if self.engine.gait != 'Idle' else 'Walk'
            speed = float(self.project.locomotion.speed.get(gait, 170.))
            length = math.hypot(forward, side)
            dx = (math.cos(camera) * forward - math.sin(camera) * side) / length
            dy = (math.sin(camera) * forward + math.cos(camera) * side) / length
            w = self.project.world
            x = min(max(x + dx * speed * dt, w.min_x), w.max_x)
            y = min(max(y + dy * speed * dt, w.min_y), w.max_y)
        self.map.listener = [x, y]
        self.map.camera = camera
        self.engine.set_listener(x, y, camera)
        self.engine.set_moving(moving)
        self.map.update()

    def eventFilter(self, obj, event):
        kind = event.type()
        if kind not in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            return False
        if not self.active or not self.isVisible() or not self.window.isActiveWindow():
            return False
        focus = QApplication.focusWidget()
        if isinstance(focus, (QLineEdit, QAbstractSpinBox, QTextEdit, QPlainTextEdit)) or \
                (isinstance(focus, QComboBox) and focus.isEditable()):
            return False
        if focus is not None and focus is not self and not self.isAncestorOf(focus):
            return False
        key = event.key()
        if key in MOVE_KEYS and not event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if not event.isAutoRepeat():
                (self.keys.add if kind == QEvent.Type.KeyPress else self.keys.discard)(MOVE_KEYS[key])
                if not any(k in self.keys for k in 'fblr'):
                    self.engine.set_moving(False)
            return True
        if kind != QEvent.Type.KeyPress or event.isAutoRepeat():
            return False
        if key == Qt.Key.Key_Space:
            self.jump()
            return True
        if key == Qt.Key.Key_Escape and self.map.mode != 'zone':
            self.engine.stop_all()
            return True
        text = event.text().upper()
        if text and event.modifiers() in (Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.KeypadModifier):
            for e in self.project.events:
                if e.pad and e.hotkey.upper()[:1] == text:
                    self.pad_pressed(e.id)
                    return True
        return False

    # ------------------------------------------------------------ world interactions
    def set_mode(self, mode):
        self.map.set_mode(mode)
        self.mode_buttons[mode].setChecked(True)

    def listener_moved(self, x, y):
        self.engine.set_listener(x, y, self.map.camera)

    def camera_turned(self, yaw):
        x, y = self.map.listener
        self.engine.set_listener(x, y, yaw)

    def set_gait(self, gait):
        self.engine.set_gait(gait)
        self.gait_buttons[gait].setChecked(True)

    def jump(self):
        self.engine.jump()

    def state_changed(self, group):
        value = self.state_combos[group].currentText()
        if value and self.project.state_values.get(group) != value:
            self.project.state_values[group] = value
            self.engine.set_states({group: value})
            self.changed()

    def pad_pressed(self, event_id):
        event = self.project.event(event_id)
        if event is None:
            return
        if self.selected_pad != event_id:
            self.selected_pad = event_id
            self.fill_pad_params()
        params = dict(self.pad_values.get(event_id, {}))
        if event.kind == 'oneshot':
            self.engine.trigger(event_id, params)
        else:
            self.engine.toggle_loop(event_id, params)
        if not self.engine.running:
            self.say('Audio is paused: switch "Audio on" to hear the pads.', True)

    def play_at(self, x, y):
        ident = self.selected_pad or self.selected_event
        event = self.project.event(ident)
        if event is None:
            self.say('Select a pad or event first.', True)
            return
        self.engine.trigger(event.id, dict(self.pad_values.get(event.id, {})), (x, y, 0.))

    def map_selected(self, kind, ident):
        self.selection = (kind, ident)
        self.show_inspector(kind, ident)
        if kind:
            self.right.setCurrentIndex(0)

    def zone_drawn(self, points):
        n = len([z for z in self.project.zones if not z.is_default]) + 1
        zone = Zone(id=new_id('zone'), name=f'Zone {n}', color=ZONE_COLORS[n % len(ZONE_COLORS)],
                    points=points, priority=1)
        self.project.zones.append(zone)
        self.set_mode('edit')
        self.selection = ('zone', zone.id)
        self.map.select('zone', zone.id)
        self.show_inspector('zone', zone.id)
        self.right.setCurrentIndex(0)
        self.changed()

    def emitter_placed(self, x, y):
        event = self.project.event(self.selected_event)
        if event is None or event.kind == 'oneshot':
            event = next((e for e in self.project.events if e.kind != 'oneshot'), None)
        emitter = Emitter(id=new_id('emt'), name=event.name if event else 'Emitter',
                          event=event.id if event else '', x=x, y=y)
        self.project.emitters.append(emitter)
        self.set_mode('edit')
        self.selection = ('emitter', emitter.id)
        self.map.select('emitter', emitter.id)
        self.show_inspector('emitter', emitter.id)
        self.right.setCurrentIndex(0)
        self.changed()

    def delete_selection(self):
        kind, ident = self.selection
        if kind == 'zone':
            zone = self.project.zone(ident)
            if zone is None or zone.is_default:
                return
            self.project.zones.remove(zone)
        elif kind == 'emitter':
            emitter = self.project.emitter(ident)
            if emitter is None:
                return
            self.project.emitters.remove(emitter)
        else:
            return
        self.selection = ('', '')
        self.map.select('', '')
        self.show_inspector('', '')
        self.changed()

    # ------------------------------------------------------------ events list
    def event_picked(self, item, _previous=None):
        if item is None:
            return
        ident = item.data(Qt.ItemDataRole.UserRole)
        self.selected_event = ident
        event = self.project.event(ident)
        if event and event.pad and self.selected_pad != ident:
            self.selected_pad = ident
            self.fill_pad_params()
        self.selection = ('event', ident)
        self.map.select('', '')
        self.show_inspector('event', ident)
        self.right.setCurrentIndex(0)

    def new_event(self):
        att = self.project.attenuations[0].id if self.project.attenuations else ''
        event = Event(id=new_id('evt'), name='New event', attenuation=att, layers=[Layer('Layer 1')])
        self.project.events.append(event)
        self.selected_event = event.id
        self.selection = ('event', event.id)
        self.changed(lists=True, inspector=True)

    def duplicate_event(self):
        event = self.project.event(self.selected_event)
        if event is None:
            return
        twin = copy.deepcopy(event)
        twin.id, twin.name, twin.hotkey = new_id('evt'), event.name + ' copy', ''
        self.project.events.append(twin)
        self.selected_event = twin.id
        self.selection = ('event', twin.id)
        self.changed(lists=True, inspector=True)

    def delete_event(self):
        event = self.project.event(self.selected_event)
        if event is None:
            return
        users = [z.name for z in self.project.zones if any(b.event == event.id for b in z.beds + z.spots)]
        users += [e.name for e in self.project.emitters if e.event == event.id]
        if QMessageBox.question(self, 'Delete event', f'Delete "{event.name}"?' +
                                (f'\nIt is used by: {", ".join(users)}.' if users else '')) != \
                QMessageBox.StandardButton.Yes:
            return
        self.project.events.remove(event)
        self.selected_event = ''
        self.selection = ('', '')
        self.changed(lists=True, inspector=True)

    # ------------------------------------------------------------ library
    def folder_chosen(self, index):
        path = self.folder_combo.itemData(index)
        if not path:
            chosen = QFileDialog.getExistingDirectory(self, 'Sound folder', self.library_folder)
            if not chosen:
                self.fill_folders()
                return
            path = chosen
        self.library_folder = path
        self.fill_folders()
        self.fill_library()
        self.save_timer.start()

    def preview(self, path):
        if path:
            self.engine.preview(path)
            if not self.engine.running:
                self.say('Audio is paused: switch "Audio on" to preview.', True)

    def preview_selected(self):
        items = self.library.selectedItems()
        if items:
            self.preview(items[0].data(Qt.ItemDataRole.UserRole))

    def add_selected_to_layer(self):
        paths = [i.data(Qt.ItemDataRole.UserRole) for i in self.library.selectedItems() if i.data(Qt.ItemDataRole.UserRole)]
        target = getattr(self, 'focused_layer', None)
        event = self.project.event(self.selected_event)
        if not paths:
            self.say('Select sounds in the library first.', True)
            return
        if event is None or not event.layers:
            self.say('Select an event with a layer first.', True)
            return
        layer = target if target in event.layers else event.layers[0]
        self.add_files(layer, paths)

    def add_files(self, layer, paths):
        added = [p for p in paths if p not in layer.files]
        layer.files.extend(added)
        self.engine.clips.request(added)
        self.say(f'Added {len(added)} sound{"s" if len(added) != 1 else ""} to "{layer.name}".')
        self.changed(lists=True, inspector=True)

    # ------------------------------------------------------------ bound field helpers
    def f(self, obj, attr, low, high, step=1., decimals=0, suffix='', scale=1., width=78, after=None):
        w = dspin(getattr(obj, attr) * scale, low, high, step, decimals, suffix, width)

        def on(value):
            setattr(obj, attr, value / scale)
            self.changed()
            if after:
                after()
        w.valueChanged.connect(on)
        return w

    def fd(self, mapping, key, low, high, step=1., decimals=0, suffix='', width=78):
        w = dspin(float(mapping.get(key, 0.)), low, high, step, decimals, suffix, width)

        def on(value):
            mapping[key] = value
            self.changed()
        w.valueChanged.connect(on)
        return w

    def i(self, obj, attr, low, high, width=64):
        w = QSpinBox()
        w.setRange(low, high)
        w.setValue(getattr(obj, attr))
        w.setKeyboardTracking(False)
        w.setFixedWidth(width)
        _guard(w)

        def on(value):
            setattr(obj, attr, value)
            self.changed()
        w.valueChanged.connect(on)
        return w

    def b(self, obj, attr, text, rebuild=False, after=None):
        w = QCheckBox(text)
        w.setChecked(bool(getattr(obj, attr)))

        def on(value):
            setattr(obj, attr, bool(value))
            self.changed(inspector=rebuild, pads=attr == 'pad')
            if after:
                after()
        w.toggled.connect(on)
        return w

    def c(self, obj, attr, items, labels=None, rebuild=False, lists=False, width=None, after=None):
        w = combo(items, getattr(obj, attr), labels, width)

        def on(_):
            setattr(obj, attr, w.currentData())
            self.changed(inspector=rebuild, lists=lists)
            if after:
                after()
        w.currentIndexChanged.connect(on)
        return w

    def t(self, obj, attr, lists=False, after=None):
        w = QLineEdit(getattr(obj, attr))

        def on():
            if w.text() != getattr(obj, attr):
                setattr(obj, attr, w.text())
                self.changed(lists=lists, pads=lists)
                if after:
                    after()
        w.editingFinished.connect(on)
        return w

    def event_choice(self, obj, attr, kinds=None, allow_none=False, rebuild=False):
        events = [e for e in self.project.events if kinds is None or e.kind in kinds]
        items = ([''] if allow_none else []) + [e.id for e in events]
        labels = {e.id: e.name for e in events}
        labels[''] = '— none —'
        if getattr(obj, attr) not in items:
            items.insert(0, getattr(obj, attr))
            labels[getattr(obj, attr)] = '— missing —' if getattr(obj, attr) else '— none —'
        return self.c(obj, attr, items, labels, rebuild=rebuild)

    def when_button(self, holder, groups):
        """groups: {name: [options]} -> checkable menu writing holder.when."""
        tool = QToolButton()
        tool.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(tool)

        def summary():
            parts = [f"{k}: {', '.join(v)}" for k, v in holder.when.items() if v]
            tool.setText('When: ' + ('; '.join(parts) if parts else 'always'))
        for group, options in groups.items():
            header = menu.addAction(group)
            header.setEnabled(False)
            for option in options:
                action = QAction(f'   {option}', menu)
                action.setCheckable(True)
                action.setChecked(option in holder.when.get(group, []))

                def toggled(checked, group=group, option=option):
                    allowed = holder.when.setdefault(group, [])
                    if checked and option not in allowed:
                        allowed.append(option)
                    elif not checked and option in allowed:
                        allowed.remove(option)
                    if not allowed:
                        holder.when.pop(group, None)
                    summary()
                    self.changed()
                action.toggled.connect(toggled)
                menu.addAction(action)
        if not groups:
            none = menu.addAction('Add an Enum parameter to filter layers')
            none.setEnabled(False)
        tool.setMenu(menu)
        summary()
        return tool

    def form_row(self, grid, row, *pairs):
        column = 0
        for text, widget in pairs:
            if text:
                grid.addWidget(label(text, 'muted'), row, column)
            grid.addWidget(widget, row, column + 1)
            column += 2

    # ------------------------------------------------------------ inspectors
    def show_inspector(self, kind, ident):
        page = QWidget()
        page.setObjectName('canvas')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        if kind == 'event' and self.project.event(ident):
            self.event_inspector(layout, self.project.event(ident))
        elif kind == 'zone' and self.project.zone(ident):
            self.zone_inspector(layout, self.project.zone(ident))
        elif kind == 'emitter' and self.project.emitter(ident):
            self.emitter_inspector(layout, self.project.emitter(ident))
        else:
            layout.addWidget(section('INSPECTOR'))
            layout.addWidget(label('Select an event on the left, or switch the map to Edit and click a zone or '
                                   'emitter.\n\nDefault zone settings: ', 'muted', True))
            default = next((z for z in self.project.zones if z.is_default), None)
            if default:
                layout.addWidget(button(f'Edit "{default.name}" (default zone)',
                                        lambda: self.map_selected('zone', default.id)))
        layout.addStretch()
        old = self.inspector_scroll.takeWidget()
        self.inspector_scroll.setWidget(page)
        if old is not None:
            old.deleteLater()

    def event_inspector(self, layout, event):
        layout.addWidget(section('EVENT  ·  MetaSound Source'))
        top, grid = card()
        name = self.t(event, 'name', lists=True)
        grid.addWidget(name, 0, 0, 1, 2)
        play = button('▶ Play', lambda: self.audition(event))
        grid.addWidget(play, 0, 2)
        grid.addWidget(button('■', lambda: self.engine.stop_event(event.id)), 0, 3)
        self.form_row(grid, 1, ('Bus', self.c(event, 'bus', BUSES, lists=True, after=lambda: self.map.update())),
                      ('Type', self.c(event, 'kind', KINDS, KIND_LABELS, rebuild=True, lists=True)))
        spatial = self.c(event, 'spatial', ('2D', '3D'), {'2D': '2D (no position)', '3D': '3D (positioned)'},
                         rebuild=True, lists=True)
        if event.spatial == '3D':
            atts = [a.id for a in self.project.attenuations]
            labels = {a.id: a.name for a in self.project.attenuations}
            if event.attenuation not in atts:
                atts.insert(0, event.attenuation)
                labels[event.attenuation] = '— none —'
            self.form_row(grid, 2, ('Space', spatial), ('Attenuation', self.c(event, 'attenuation', atts, labels)))
        else:
            self.form_row(grid, 2, ('Space', spatial))
        self.form_row(grid, 3, ('Volume', self.f(event, 'volume_db', -60, 12, .5, 1, ' dB')),
                      ('Pitch', self.f(event, 'pitch_st', -24, 24, .1, 1, ' st')))
        row = 4
        if event.kind == 'repeat':
            self.form_row(grid, row, ('Every', self.f(event, 'repeat_min', .05, 120, .1, 2, ' s')),
                          ('to', self.f(event, 'repeat_max', .05, 120, .1, 2, ' s')))
            row += 1
        if event.kind == 'loop':
            grid.addWidget(self.b(event, 'random_start', 'Start each loop at a random point'), row, 0, 1, 4)
            row += 1
        if event.spatial == '2D':
            self.form_row(grid, row, ('Reverb send', self.f(event, 'reverb_send', 0, 100, 5, 0, ' %', 100)))
            row += 1
        notes = getattr(self, 'problems', {}).get(event.id)
        if notes:
            grid.addWidget(label('⚠ ' + '\n⚠ '.join(dict.fromkeys(notes)), 'warn', True), row, 0, 1, 4)
        layout.addWidget(top)

        layout.addWidget(section('LAYERS'))
        layout.addWidget(label('Each layer is one ingredient with its own pool of takes. Every play picks a take '
                               'per layer.', 'hint', True))
        enums = {p.name: p.options for p in event.parameters if p.kind == 'enum'}
        for index, layer in enumerate(event.layers):
            layout.addWidget(self.layer_card(event, index, layer, enums))
        layout.addWidget(button('+ Add layer', lambda: self.add_layer(event)))

        layout.addWidget(section('PARAMETERS  ·  MetaSound Inputs'))
        params, pgrid = card()
        for row, p in enumerate(event.parameters):
            self.parameter_row(event, pgrid, row, p)
        pgrid.addWidget(button('+ Float', lambda: self.add_parameter(event, 'float')), len(event.parameters), 0)
        pgrid.addWidget(button('+ Enum', lambda: self.add_parameter(event, 'enum')), len(event.parameters), 1)
        layout.addWidget(params)

        layout.addWidget(section('MAPPINGS  ·  parameter → target'))
        maps, mgrid = card()
        targets = [('event:volume', 'Event volume ×'), ('event:pitch', 'Event pitch st'),
                   ('event:cutoff', 'Event filter Hz'), ('event:drive', 'Event drive')]
        for i, layer in enumerate(event.layers):
            targets += [(f'{i}:gain', f'{layer.name} gain ×'), (f'{i}:pitch', f'{layer.name} pitch st'),
                        (f'{i}:chance', f'{layer.name} chance ×')]
        floats = [p.name for p in event.parameters if p.kind == 'float']
        for row, b in enumerate(event.bindings):
            self.binding_row(event, mgrid, row * 2, b, floats, targets)
        add = button('+ Mapping', lambda: self.add_binding(event))
        add.setEnabled(bool(floats))
        mgrid.addWidget(add, len(event.bindings) * 2, 0, 1, 2)
        if not floats:
            mgrid.addWidget(label('Add a Float parameter first.', 'hint'), len(event.bindings) * 2, 2, 1, 4)
        layout.addWidget(maps)

        layout.addWidget(section('PROCESSING'))
        dsp, dgrid = card()
        d = event.dsp
        self.form_row(dgrid, 0, ('Attack', self.f(d, 'attack_ms', 0, 10000, 5, 0, ' ms')),
                      ('Hold', self.f(d, 'hold_ms', 0, 30000, 10, 0, ' ms')))
        self.form_row(dgrid, 1, ('Release', self.f(d, 'release_ms', 5, 10000, 10, 0, ' ms')),
                      ('Filter', self.c(d, 'filter', FILTERS)))
        self.form_row(dgrid, 2, ('Cutoff', self.f(d, 'cutoff', 20, 20000, 50, 0, ' Hz')),
                      ('Q', self.f(d, 'q', .1, 12, .1, 2)))
        self.form_row(dgrid, 3, ('Drive', self.f(d, 'drive', 0, 100, 5, 0, ' %', 100)),
                      ('Delay', self.f(d, 'delay_ms', 0, 2000, 10, 0, ' ms')))
        self.form_row(dgrid, 4, ('Feedback', self.f(d, 'feedback', 0, 95, 5, 0, ' %', 100)),
                      ('Wet', self.f(d, 'delay_mix', 0, 100, 5, 0, ' %', 100)))
        dgrid.addWidget(self.b(d, 'limiter', 'Limiter (safety)'), 5, 0, 1, 2)
        dgrid.addWidget(label('Hold 0 = play to the end. Delay below 30 ms is off.', 'hint', True), 5, 2, 1, 2)
        layout.addWidget(dsp)

        layout.addWidget(section('LIMITS & SOUNDBOARD'))
        lim, lgrid = card()
        self.form_row(lgrid, 0, ('Max voices', self.i(event, 'max_count', 1, 64)),
                      ('When full', self.c(event, 'rule', RULES, RULE_LABELS)))
        lgrid.addWidget(self.b(event, 'pad', 'Show on soundboard'), 1, 0, 1, 2)
        hotkey = QLineEdit(event.hotkey)
        hotkey.setMaxLength(1)
        hotkey.setFixedWidth(40)

        def set_hotkey():
            text = hotkey.text().upper()[:1]
            if text in RESERVED:
                self.say('W A S D Q E and Space are used for movement.', True)
                hotkey.setText(event.hotkey)
                return
            for other in self.project.events:
                if other is not event and other.hotkey.upper() == text and text:
                    other.hotkey = ''
            event.hotkey = text
            self.changed(pads=True)
        hotkey.editingFinished.connect(set_hotkey)
        self.form_row(lgrid, 1, (None, QWidget()), ('Hotkey', hotkey))
        layout.addWidget(lim)

    def audition(self, event):
        params = dict(self.pad_values.get(event.id, {}))
        if event.kind == 'oneshot':
            self.engine.trigger(event.id, params)
        else:
            self.engine.toggle_loop(event.id, params)
        if not self.engine.running:
            self.say('Audio is paused: switch "Audio on" to listen.', True)

    def layer_card(self, event, index, layer, enums):
        frame, grid = card()
        name = self.t(layer, 'name', after=lambda: self.changed(inspector=True))
        grid.addWidget(name, 0, 0, 1, 2)
        grid.addWidget(button('▶', lambda: self.preview(layer.files[0] if len(layer.files) == 1 else
                                                         (layer.files[int(np.random.randint(len(layer.files)))]
                                                          if layer.files else ''))), 0, 2)
        grid.addWidget(button('✕', lambda: self.remove_layer(event, index), 'danger'), 0, 3)
        self.form_row(grid, 1, ('Delay', self.f(layer, 'delay_ms', 0, 10000, 10, 0, ' ms')),
                      ('Gain', self.f(layer, 'gain_db', -60, 12, .5, 1, ' dB')))
        self.form_row(grid, 2, ('Chance', self.f(layer, 'chance', 0, 100, 5, 0, ' %', 100)),
                      ('Pitch', self.f(layer, 'pitch_st', -24, 24, .1, 1, ' st')))
        self.form_row(grid, 3, ('± pitch', self.f(layer, 'pitch_random', 0, 12, .1, 1, ' st')),
                      ('± volume', self.f(layer, 'volume_random', 0, 24, .5, 1, ' dB')))
        grid.addWidget(label('Pick', 'muted'), 4, 0)
        grid.addWidget(self.c(layer, 'selection', SELECTIONS, SELECTION_LABELS), 4, 1, 1, 3)
        grid.addWidget(self.when_button(layer, enums), 5, 0, 1, 4)
        files = FileDropList()
        files.setMinimumHeight(48)
        files.setMaximumHeight(46 + 22 * min(5, max(1, len(layer.files))))
        for path in layer.files:
            item = QListWidgetItem(Path(path).name)
            item.setData(Qt.ItemDataRole.UserRole, path)
            state = self.engine.clips.state(path)
            if state == 'missing' or not Path(path).is_file():
                item.setForeground(QColor('#ff98a6'))
                item.setText(Path(path).name + '  (missing)')
            files.addItem(item)
        if not layer.files:
            hint = QListWidgetItem('Drop WAVs here')
            hint.setFlags(Qt.ItemFlag.NoItemFlags)
            hint.setForeground(QColor('#959aa4'))
            files.addItem(hint)
        files.dropped.connect(lambda paths: self.add_files(layer, paths))
        files.removed.connect(lambda rows: self.remove_files(layer, rows))
        files.itemDoubleClicked.connect(lambda item: self.preview(item.data(Qt.ItemDataRole.UserRole)))
        files.itemPressed.connect(lambda *_: setattr(self, 'focused_layer', layer))
        grid.addWidget(files, 6, 0, 1, 4)
        row = QHBoxLayout()

        def from_library():
            self.focused_layer = layer
            self.add_selected_to_layer()
        row.addWidget(button('+ From library', from_library))
        row.addWidget(button('Remove selected', lambda: self.remove_files(
            layer, sorted({files.row(i) for i in files.selectedItems()}))))
        row.addStretch()
        row.addWidget(label(f'{len(layer.files)} take{"s" if len(layer.files) != 1 else ""}', 'hint'))
        holder = QWidget()
        holder.setLayout(row)
        row.setContentsMargins(0, 0, 0, 0)
        grid.addWidget(holder, 7, 0, 1, 4)
        return frame

    def remove_files(self, layer, rows):
        for row in sorted(rows, reverse=True):
            if 0 <= row < len(layer.files):
                layer.files.pop(row)
        self.changed(lists=True, inspector=True)

    def add_layer(self, event):
        event.layers.append(Layer(f'Layer {len(event.layers) + 1}'))
        self.changed(inspector=True)

    def remove_layer(self, event, index):
        if index >= len(event.layers):
            return
        event.layers.pop(index)
        bindings = []
        for b in event.bindings:
            if b.layer == index:
                continue
            if b.layer > index:
                b.layer -= 1
            bindings.append(b)
        event.bindings = bindings
        self.changed(lists=True, inspector=True)

    def parameter_row(self, event, grid, row, p):
        name = QLineEdit(p.name)
        name.setFixedWidth(88)

        def rename():
            new = name.text().strip()
            if not new or new == p.name or event.parameter(new):
                name.setText(p.name)
                return
            old, p.name = p.name, new
            for b in event.bindings:
                if b.parameter == old:
                    b.parameter = new
            for layer in event.layers:
                if old in layer.when:
                    layer.when[new] = layer.when.pop(old)
            self.changed(inspector=True, pads=True)
        name.editingFinished.connect(rename)
        grid.addWidget(name, row, 0)
        if p.kind == 'float':
            grid.addWidget(self.f(p, 'minimum', -10000, 10000, .1, 2, width=58), row, 1)
            grid.addWidget(self.f(p, 'maximum', -10000, 10000, .1, 2, width=58), row, 2)
            grid.addWidget(self.f(p, 'default', -10000, 10000, .05, 2, width=58), row, 3)
        else:
            options = QLineEdit(', '.join(p.options))

            def set_options():
                p.options = [o.strip() for o in options.text().split(',') if o.strip()]
                self.changed(inspector=True)
            options.editingFinished.connect(set_options)
            grid.addWidget(options, row, 1, 1, 3)
        grid.addWidget(label('auto' if p.automatic else ('Float' if p.kind == 'float' else 'Enum'), 'hint'), row, 4)
        grid.addWidget(button('✕', lambda: self.remove_parameter(event, p), 'danger'), row, 5)

    def add_parameter(self, event, kind):
        base = 'Intensity' if kind == 'float' else 'Variant'
        name, n = base, 2
        while event.parameter(name):
            name, n = f'{base}{n}', n + 1
        event.parameters.append(Parameter(name, kind, options=['A', 'B'] if kind == 'enum' else []))
        self.changed(inspector=True, pads=True)

    def remove_parameter(self, event, p):
        event.parameters.remove(p)
        event.bindings = [b for b in event.bindings if b.parameter != p.name]
        for layer in event.layers:
            layer.when.pop(p.name, None)
        self.changed(inspector=True, pads=True)

    def binding_row(self, event, grid, row, b, floats, targets):
        params = combo(floats if b.parameter in floats else [b.parameter] + floats, b.parameter, width=96)
        params.currentIndexChanged.connect(lambda _: (setattr(b, 'parameter', params.currentData()), self.changed()))
        key = f'event:{b.target}' if b.layer < 0 else f'{b.layer}:{b.target}'
        keys = [k for k, _ in targets]
        target = combo(keys if key in keys else [key] + keys, key, dict(targets))

        def set_target(_):
            where, what = target.currentData().split(':')
            b.layer, b.target = (-1 if where == 'event' else int(where)), what
            self.changed()
        target.currentIndexChanged.connect(set_target)
        grid.addWidget(params, row, 0)
        grid.addWidget(target, row, 1, 1, 4)
        grid.addWidget(button('✕', lambda: (event.bindings.remove(b), self.changed(inspector=True)), 'danger'), row, 5)
        line = QHBoxLayout()
        line.setSpacing(4)
        for text, attr in (('from', 'x0'), ('→', 'y0'), ('to', 'x1'), ('→', 'y1')):
            line.addWidget(label(text, 'muted'))
            line.addWidget(self.f(b, attr, -20000, 20000, .05, 2, width=60))
        line.addStretch()
        holder = QWidget()
        line.setContentsMargins(0, 0, 0, 0)
        holder.setLayout(line)
        grid.addWidget(holder, row + 1, 0, 1, 6)

    def add_binding(self, event):
        floats = [p.name for p in event.parameters if p.kind == 'float']
        if floats:
            event.bindings.append(Binding(floats[0], 'gain', 0 if event.layers else -1, 0, 1, 0, 1)
                                  if event.layers else Binding(floats[0], 'volume', -1, 0, 1, .5, 1))
            self.changed(inspector=True)

    def zone_inspector(self, layout, zone):
        layout.addWidget(section('ZONE  ·  Audio Gameplay Volume + Soundscape palette'))
        top, grid = card()
        grid.addWidget(self.t(zone, 'name', after=lambda: self.map.update()), 0, 0, 1, 3)
        color = QPushButton('Colour')
        color.setStyleSheet(f'background:{zone.color};color:#202225;border-color:{zone.color};')

        def pick():
            chosen = QColorDialog.getColor(QColor(zone.color), self, 'Zone colour')
            if chosen.isValid():
                zone.color = chosen.name()
                self.changed(inspector=True)
        color.clicked.connect(pick)
        grid.addWidget(color, 0, 3)
        if zone.is_default:
            grid.addWidget(label('Default zone: plays wherever no other zone covers the character.', 'hint', True),
                           1, 0, 1, 4)
        else:
            self.form_row(grid, 1, ('Priority', self.i(zone, 'priority', -100, 100)),
                          ('Edge blend', self.f(zone, 'edge_blend', 0, 20000, 50, 0, ' cm')))
        self.form_row(grid, 2, ('Fade in', self.f(zone, 'fade_in', 0, 30, .1, 1, ' s')),
                      ('Fade out', self.f(zone, 'fade_out', 0, 30, .1, 1, ' s')))
        surfaces = self.surface_options()
        surface = QComboBox()
        surface.setEditable(True)
        surface.addItems([''] + surfaces)
        surface.setCurrentText(zone.surface)
        surface.currentTextChanged.connect(lambda text: (setattr(zone, 'surface', text), self.changed()))
        self.form_row(grid, 3, ('Ground', _guard(surface)),
                      ('Reverb', self.c(zone, 'reverb', list(REVERBS))))
        self.form_row(grid, 4, ('Reverb level', self.f(zone, 'reverb_wet_db', -40, 6, .5, 1, ' dB')))
        layout.addWidget(top)

        if not zone.is_default:
            interior, igrid = card()
            igrid.addWidget(self.b(zone, 'interior', 'Interior (walls muffle sound in and out)', rebuild=True,
                                   after=lambda: self.map.update()), 0, 0, 1, 4)
            if zone.interior:
                igrid.addWidget(label('Outside sounds, heard from inside', 'hint'), 1, 0, 1, 4)
                self.form_row(igrid, 2, ('Low-pass', self.f(zone, 'outside_lpf', 100, 20000, 100, 0, ' Hz')),
                              ('Volume', self.f(zone, 'outside_db', -60, 0, .5, 1, ' dB')))
                igrid.addWidget(label('Inside sounds, heard from outside', 'hint'), 3, 0, 1, 4)
                self.form_row(igrid, 4, ('Low-pass', self.f(zone, 'inside_lpf', 100, 20000, 100, 0, ' Hz')),
                              ('Volume', self.f(zone, 'inside_db', -60, 0, .5, 1, ' dB')))
            layout.addWidget(interior)

        states = dict(self.project.states)
        layout.addWidget(section('BEDS  ·  2D loops while you are in the zone'))
        beds, bgrid = card()
        for row, bed in enumerate(zone.beds):
            bgrid.addWidget(self.event_choice(bed, 'event', ('loop', 'repeat')), row * 2, 0, 1, 3)
            bgrid.addWidget(self.f(bed, 'gain_db', -60, 12, .5, 1, ' dB', width=70), row * 2, 3)
            bgrid.addWidget(button('✕', lambda _=False, b=bed: (zone.beds.remove(b), self.changed(inspector=True)),
                                   'danger'), row * 2, 4)
            bgrid.addWidget(self.when_button(bed, states), row * 2 + 1, 0, 1, 5)
        loops = [e for e in self.project.events if e.kind != 'oneshot']
        bgrid.addWidget(button('+ Bed', lambda: (zone.beds.append(Bed(loops[0].id if loops else '')),
                                                 self.changed(inspector=True))), len(zone.beds) * 2, 0)
        layout.addWidget(beds)

        layout.addWidget(section('SPOTS  ·  one-shots spawned around you (Soundscape)'))
        for spot in zone.spots:
            frame, sgrid = card()
            sgrid.addWidget(self.event_choice(spot, 'event', ('oneshot',)), 0, 0, 1, 3)
            sgrid.addWidget(self.f(spot, 'gain_db', -60, 12, .5, 1, ' dB', width=70), 0, 3)
            sgrid.addWidget(button('✕', lambda _=False, s=spot: (zone.spots.remove(s), self.changed(inspector=True)),
                                   'danger'), 0, 4)
            self.form_row(sgrid, 1, ('Every', self.f(spot, 'interval_min', .1, 600, .5, 1, ' s', width=70)),
                          ('to', self.f(spot, 'interval_max', .1, 600, .5, 1, ' s', width=70)))
            self.form_row(sgrid, 2, ('Distance', self.f(spot, 'distance_min', 0, 50000, 100, 0, ' cm', width=80)),
                          ('to', self.f(spot, 'distance_max', 0, 50000, 100, 0, ' cm', width=80)))
            self.form_row(sgrid, 3, ('Max alive', self.i(spot, 'max_active', 1, 32)),
                          ('Chance', self.f(spot, 'chance', 0, 100, 5, 0, ' %', 100, width=70)))
            sgrid.addWidget(self.b(spot, 'inside_only', 'Only inside the zone'), 4, 0, 1, 2)
            sgrid.addWidget(self.when_button(spot, states), 4, 2, 1, 3)
            layout.addWidget(frame)
        shots = [e for e in self.project.events if e.kind == 'oneshot' and e.spatial == '3D']
        layout.addWidget(button('+ Spot', lambda: (zone.spots.append(Spot(shots[0].id if shots else '')),
                                                   self.changed(inspector=True))))
        if not zone.is_default:
            layout.addWidget(button('Delete zone', self.delete_selection, 'danger'))

    def surface_options(self):
        event = self.project.event(self.project.locomotion.footstep_event)
        p = event.parameter('Surface') if event else None
        return list(p.options) if p else []

    def emitter_inspector(self, layout, emitter):
        layout.addWidget(section('EMITTER  ·  Ambient Sound actor'))
        top, grid = card()
        grid.addWidget(self.t(emitter, 'name', after=lambda: self.map.update()), 0, 0, 1, 4)
        grid.addWidget(label('Event', 'muted'), 1, 0)
        grid.addWidget(self.event_choice(emitter, 'event', ('loop', 'repeat')), 1, 1, 1, 3)
        self.form_row(grid, 2, ('X', self.f(emitter, 'x', -10 ** 7, 10 ** 7, 10, 0, ' cm', width=92, after=self.map.update)),
                      ('Y', self.f(emitter, 'y', -10 ** 7, 10 ** 7, 10, 0, ' cm', width=92, after=self.map.update)))
        self.form_row(grid, 3, ('Yaw', self.f(emitter, 'yaw', -360, 360, 5, 0, '°', after=self.map.update)),
                      ('Volume', self.f(emitter, 'gain_db', -60, 12, .5, 1, ' dB')))
        atts = [''] + [a.id for a in self.project.attenuations]
        labels = {a.id: a.name for a in self.project.attenuations}
        labels[''] = "Event's own"
        grid.addWidget(label('Attenuation', 'muted'), 4, 0)
        grid.addWidget(self.c(emitter, 'attenuation', atts, labels, after=self.map.update), 4, 1, 1, 3)
        grid.addWidget(self.when_button(emitter, dict(self.project.states)), 5, 0, 1, 4)
        layout.addWidget(top)
        layout.addWidget(label('Only Loop and Timed-repeat events can be emitters. Drag it on the map in Edit mode.',
                               'hint', True))
        layout.addWidget(button('Delete emitter', self.delete_selection, 'danger'))

    # ------------------------------------------------------------ attenuation page
    def build_attenuation_page(self):
        page = QWidget()
        page.setObjectName('canvas')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(section('ATTENUATION PROFILES  ·  Sound Attenuation assets'))
        row = QHBoxLayout()
        ids = [a.id for a in self.project.attenuations]
        if self.att_selected not in ids:
            self.att_selected = ids[0] if ids else ''
        chooser = combo(ids, self.att_selected, {a.id: a.name for a in self.project.attenuations})
        chooser.currentIndexChanged.connect(lambda _: (setattr(self, 'att_selected', chooser.currentData()),
                                                       self.build_attenuation_page()))
        row.addWidget(chooser, 1)
        row.addWidget(button('+ New', self.new_attenuation))
        row.addWidget(button('Duplicate', self.duplicate_attenuation))
        row.addWidget(button('Delete', self.delete_attenuation, 'danger'))
        layout.addLayout(row)
        att = self.project.attenuation(self.att_selected)
        if att is None:
            layout.addWidget(label('No profiles yet.', 'muted'))
            layout.addStretch()
            self._swap(self.att_page, page)
            return
        users = [e.name for e in self.project.events if e.attenuation == att.id]
        layout.addWidget(label('Used by: ' + (', '.join(users) if users else 'nothing yet'), 'hint', True))
        graph = AttenuationGraph()
        graph.set_attenuation(att)
        graph.edited.connect(self.changed)
        layout.addWidget(graph)
        rebuild = lambda: (graph.update(), self.map.update())

        frame, grid = card()
        grid.addWidget(self.t(att, 'name', after=lambda: self.changed(inspector=True)), 0, 0, 1, 4)
        grid.addWidget(self.b(att, 'attenuate', 'Volume falls off with distance', after=rebuild), 1, 0, 1, 4)
        shape = self.c(att, 'shape', SHAPES, after=self.build_attenuation_page)
        self.form_row(grid, 2, ('Shape', shape),
                      ('Model', self.c(att, 'model', DISTANCE_MODELS, after=self.build_attenuation_page)))
        if att.shape in ('Sphere', 'Cone'):
            self.form_row(grid, 3, ('Inner radius', self.f(att, 'inner_radius', 0, 100000, 25, 0, ' cm', width=84, after=rebuild)))
        if att.shape == 'Box':
            self.form_row(grid, 3, ('Half X', self.f(att, 'box_x', 0, 100000, 25, 0, ' cm', width=84, after=rebuild)),
                          ('Half Y', self.f(att, 'box_y', 0, 100000, 25, 0, ' cm', width=84, after=rebuild)))
        if att.shape == 'Capsule':
            self.form_row(grid, 3, ('Half length', self.f(att, 'capsule_half_height', 0, 100000, 50, 0, ' cm', width=84, after=rebuild)),
                          ('Radius', self.f(att, 'capsule_radius', 0, 100000, 25, 0, ' cm', width=84, after=rebuild)))
        if att.shape == 'Cone':
            self.form_row(grid, 4, ('Cone angle', self.f(att, 'cone_angle', 0, 180, 1, 0, '°', after=rebuild)),
                          ('Edge fade', self.f(att, 'cone_falloff_angle', 0, 180, 1, 0, '°', after=rebuild)))
        falloff = ('Falloff', self.f(att, 'falloff', 1, 200000, 100, 0, ' cm', width=84, after=rebuild))
        if att.model == 'NaturalSound':
            self.form_row(grid, 5, falloff, ('At edge', self.f(att, 'db_at_max', -100, 0, 1, 0, ' dB', after=rebuild)))
        else:
            self.form_row(grid, 5, falloff)
        if att.model == 'Custom':
            grid.addWidget(label('Drag the orange points · double-click adds · right-click removes', 'hint', True),
                           6, 0, 1, 4)
        layout.addWidget(frame)

        layout.addWidget(section('SPATIALISATION'))
        frame, grid = card()
        grid.addWidget(self.b(att, 'spatialize', 'Pan by direction from the camera', after=rebuild), 0, 0, 1, 4)
        self.form_row(grid, 1, ('Stereo spread', self.f(att, 'stereo_spread', 0, 10000, 25, 0, ' cm', width=84)),
                      ('Wrap radius', self.f(att, 'nonspatial_radius', 0, 20000, 25, 0, ' cm', width=84)))
        grid.addWidget(label('Wrap radius: closer than this the sound spreads around you (Non-Spatialized Radius).',
                             'hint', True), 2, 0, 1, 4)
        layout.addWidget(frame)

        layout.addWidget(section('AIR ABSORPTION'))
        frame, grid = card()
        grid.addWidget(self.b(att, 'air_absorption', 'Distant sounds lose their highs', after=rebuild), 0, 0, 1, 4)
        self.form_row(grid, 1, ('From', self.f(att, 'air_min', 0, 200000, 100, 0, ' cm', width=84, after=rebuild)),
                      ('to', self.f(att, 'air_max', 0, 200000, 100, 0, ' cm', width=84, after=rebuild)))
        self.form_row(grid, 2, ('Low-pass near', self.f(att, 'lpf_at_min', 20, 20000, 100, 0, ' Hz', width=84, after=rebuild)),
                      ('far', self.f(att, 'lpf_at_max', 20, 20000, 100, 0, ' Hz', width=84, after=rebuild)))
        self.form_row(grid, 3, ('High-pass near', self.f(att, 'hpf_at_min', 0, 5000, 10, 0, ' Hz', width=84)),
                      ('far', self.f(att, 'hpf_at_max', 0, 5000, 10, 0, ' Hz', width=84)))
        grid.addWidget(self.b(att, 'log_frequency', 'Logarithmic frequency scaling', after=rebuild), 4, 0, 1, 4)
        layout.addWidget(frame)

        layout.addWidget(section('REVERB SEND'))
        frame, grid = card()
        grid.addWidget(self.b(att, 'reverb_send', 'Farther sounds are wetter', after=rebuild), 0, 0, 1, 4)
        self.form_row(grid, 1, ('Send near', self.f(att, 'reverb_min', 0, 100, 5, 0, ' %', 100, after=rebuild)),
                      ('far', self.f(att, 'reverb_max', 0, 100, 5, 0, ' %', 100, after=rebuild)))
        self.form_row(grid, 2, ('From', self.f(att, 'reverb_dist_min', 0, 200000, 100, 0, ' cm', width=84, after=rebuild)),
                      ('to', self.f(att, 'reverb_dist_max', 0, 200000, 100, 0, ' cm', width=84, after=rebuild)))
        layout.addWidget(frame)
        layout.addStretch()
        self._swap(self.att_page, page)

    def _swap(self, scroll, page):
        old = scroll.takeWidget()
        scroll.setWidget(page)
        if old is not None:
            old.deleteLater()

    def new_attenuation(self):
        att = Attenuation(id=new_id('att'), name=f'Profile {len(self.project.attenuations) + 1}')
        self.project.attenuations.append(att)
        self.att_selected = att.id
        self.build_attenuation_page()
        self.changed(inspector=True)

    def duplicate_attenuation(self):
        att = self.project.attenuation(self.att_selected)
        if att is None:
            return
        twin = copy.deepcopy(att)
        twin.id, twin.name = new_id('att'), att.name + ' copy'
        self.project.attenuations.append(twin)
        self.att_selected = twin.id
        self.build_attenuation_page()
        self.changed(inspector=True)

    def delete_attenuation(self):
        att = self.project.attenuation(self.att_selected)
        if att is None:
            return
        users = [e.name for e in self.project.events if e.attenuation == att.id]
        if users:
            self.say(f'"{att.name}" is used by {", ".join(users)}. Pick another profile for them first.', True)
            return
        self.project.attenuations.remove(att)
        for emitter in self.project.emitters:
            if emitter.attenuation == att.id:
                emitter.attenuation = ''
        self.att_selected = ''
        self.build_attenuation_page()
        self.changed(inspector=True)

    # ------------------------------------------------------------ mixer page
    def build_mixer_page(self):
        page = QWidget()
        page.setObjectName('canvas')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(section('BUSES  ·  Sound Classes / Submixes'))
        frame, grid = card()
        self.meters = {}
        for row, bus in enumerate(self.project.buses):
            name = label(bus.name)
            name.setStyleSheet(f'color:{BUS_COLORS.get(bus.name, "#e5e7eb")};font-weight:600;')
            grid.addWidget(name, row, 0)
            grid.addWidget(self.f(bus, 'volume_db', -60, 12, .5, 1, ' dB', width=76), row, 1)
            mute = self.b(bus, 'mute', 'M')
            solo = self.b(bus, 'solo', 'S')
            grid.addWidget(mute, row, 2)
            grid.addWidget(solo, row, 3)
            meter = Meter()
            self.meters[bus.name] = meter
            grid.addWidget(meter, row, 4)
        grid.setColumnStretch(4, 1)
        layout.addWidget(frame)
        layout.addWidget(section('MASTER'))
        frame, grid = card()
        self.form_row(grid, 0, ('Master', self.f(self.project, 'master_db', -60, 12, .5, 1, ' dB')),
                      ('Reverb return', self.f(self.project, 'reverb_return_db', -60, 12, .5, 1, ' dB')))
        self.form_row(grid, 1, ('Limiter ceiling', self.f(self.project, 'limiter_ceiling_db', -12, 0, .1, 1, ' dB')))
        self.reduction_label = label('Limiter 0.0 dB', 'muted')
        grid.addWidget(self.reduction_label, 1, 2, 1, 2)
        meter = Meter()
        self.meters['__master__'] = meter
        grid.addWidget(meter, 2, 0, 1, 4)
        layout.addWidget(frame)
        layout.addWidget(section('DUCKING  ·  Control Bus Mixes'))
        layout.addWidget(label('While the source bus plays, the target bus dips.', 'hint', True))
        for duck in self.project.ducks:
            frame, grid = card()
            self.form_row(grid, 0, ('When', self.c(duck, 'source', BUSES)), ('dip', self.c(duck, 'target', BUSES)))
            self.form_row(grid, 1, ('By', self.f(duck, 'amount_db', -60, 0, .5, 1, ' dB')),
                          ('Attack', self.f(duck, 'attack_ms', 1, 5000, 5, 0, ' ms')))
            self.form_row(grid, 2, ('Hold', self.f(duck, 'hold_ms', 0, 10000, 10, 0, ' ms')),
                          ('Release', self.f(duck, 'release_ms', 1, 20000, 10, 0, ' ms')))
            grid.addWidget(button('✕', lambda _=False, d=duck: (self.project.ducks.remove(d), self.changed(),
                                                               self.build_mixer_page()), 'danger'), 0, 4)
            layout.addWidget(frame)
        layout.addWidget(button('+ Duck', lambda: (self.project.ducks.append(Duck()), self.changed(),
                                                   self.build_mixer_page())))
        layout.addStretch()
        self._swap(self.mixer_page, page)

    # ------------------------------------------------------------ project page
    def build_project_page(self):
        page = QWidget()
        page.setObjectName('canvas')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(section('PROJECT'))
        frame, grid = card()
        grid.addWidget(label(str(self.project_path), 'muted', True), 0, 0, 1, 4)
        grid.addWidget(button('Open…', self.open_project), 1, 0)
        grid.addWidget(button('Save as…', self.save_project_as), 1, 1)
        grid.addWidget(button('New from template', self.new_project), 1, 2, 1, 2)
        layout.addWidget(frame)

        layout.addWidget(section('WORLD MAP  ·  Unreal units (cm)'))
        frame, grid = card()
        w = self.project.world
        refit = lambda: (self.map.fit(), self.map.update())
        self.form_row(grid, 0, ('Min X', self.f(w, 'min_x', -10 ** 7, 10 ** 7, 100, 0, width=90, after=refit)),
                      ('Max X', self.f(w, 'max_x', -10 ** 7, 10 ** 7, 100, 0, width=90, after=refit)))
        self.form_row(grid, 1, ('Min Y', self.f(w, 'min_y', -10 ** 7, 10 ** 7, 100, 0, width=90, after=refit)),
                      ('Max Y', self.f(w, 'max_y', -10 ** 7, 10 ** 7, 100, 0, width=90, after=refit)))
        self.form_row(grid, 2, ('Start X', self.f(w, 'start_x', -10 ** 7, 10 ** 7, 100, 0, width=90)),
                      ('Start Y', self.f(w, 'start_y', -10 ** 7, 10 ** 7, 100, 0, width=90)))
        grid.addWidget(button('Map image…', self.choose_map_image), 3, 0, 1, 2)
        grid.addWidget(button('Clear image', lambda: (setattr(w, 'image', ''), self.map.set_project(self.project),
                                                      self.changed())), 3, 2, 1, 2)
        grid.addWidget(label('A top-down screenshot of the level, stretched over the bounds above.', 'hint', True),
                       4, 0, 1, 4)
        layout.addWidget(frame)

        layout.addWidget(section('GAME STATES'))
        frame, grid = card()
        for row, (group, values) in enumerate(self.project.states.items()):
            grid.addWidget(label(group, 'muted'), row, 0)
            edit = QLineEdit(', '.join(values))

            def set_values(group=group, edit=edit):
                options = [v.strip() for v in edit.text().split(',') if v.strip()]
                if options:
                    self.project.states[group] = options
                    self.fill_states()
                    self.changed()
            edit.editingFinished.connect(set_values)
            grid.addWidget(edit, row, 1, 1, 3)
        layout.addWidget(frame)

        layout.addWidget(section('LOCOMOTION'))
        frame, grid = card()
        loco = self.project.locomotion
        for row, (text, attr) in enumerate((('Footsteps', 'footstep_event'), ('Cloth / gear', 'cloth_event'),
                                            ('Start moving', 'start_event'), ('Stop moving', 'stop_event'),
                                            ('Jump', 'jump_event'), ('Land', 'land_event'))):
            grid.addWidget(label(text, 'muted'), row, 0)
            grid.addWidget(self.event_choice(loco, attr, ('oneshot',), allow_none=True), row, 1, 1, 3)
        row = 6
        self.form_row(grid, row, ('Cloth chance', self.f(loco, 'cloth_chance', 0, 100, 5, 0, ' %', 100)),
                      ('Air time', self.f(loco, 'air_time_ms', 100, 3000, 10, 0, ' ms')))
        surface = QComboBox()
        surface.setEditable(True)
        surface.addItems(self.surface_options())
        surface.setCurrentText(loco.default_surface)
        surface.currentTextChanged.connect(lambda text: (setattr(loco, 'default_surface', text), self.changed()))
        self.form_row(grid, row + 1, ('Default ground', _guard(surface)))
        grid.addWidget(label('Gait', 'hint'), row + 2, 0)
        grid.addWidget(label('Steps / s', 'hint'), row + 2, 1)
        grid.addWidget(label('Speed cm/s', 'hint'), row + 2, 2)
        grid.addWidget(label('Gain', 'hint'), row + 2, 3)
        for i, gait in enumerate(('Walk', 'Run', 'Sprint')):
            grid.addWidget(label(gait, 'muted'), row + 3 + i, 0)
            grid.addWidget(self.fd(loco.cadence, gait, .3, 8, .05, 2, width=70), row + 3 + i, 1)
            grid.addWidget(self.fd(loco.speed, gait, 10, 2000, 10, 0, width=70), row + 3 + i, 2)
            grid.addWidget(self.fd(loco.gain_db, gait, -30, 12, .5, 1, ' dB', width=70), row + 3 + i, 3)
        layout.addWidget(frame)

        layout.addWidget(section('UNREAL EXPORT'))
        frame, grid = card()
        self.export_label = label(self.export_folder, 'muted', True)
        grid.addWidget(self.export_label, 0, 0, 1, 4)
        grid.addWidget(button('Choose folder…', self.choose_export_folder), 1, 0, 1, 2)
        grid.addWidget(button('Export for Unreal', self.export, 'primary'), 1, 2, 1, 2)
        grid.addWidget(label('Copies every WAV with Unreal names and writes unreal_manifest.json: MetaSound Sources, '
                             'attenuations, concurrency, zones (Audio Gameplay Volumes + Soundscape), emitters, '
                             'buses and ducking, with Unreal property names.', 'hint', True), 2, 0, 1, 4)
        layout.addWidget(frame)
        layout.addStretch()
        self._swap(self.project_page, page)

    def choose_map_image(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Map image', str(self.home), 'Images (*.png *.jpg *.jpeg *.bmp)')
        if path:
            self.project.world.image = path
            self.map.set_project(self.project)
            self.changed()

    def choose_export_folder(self):
        path = QFileDialog.getExistingDirectory(self, 'Export folder', self.export_folder)
        if path:
            self.export_folder = path
            self.export_label.setText(path)
            self.save_timer.start()

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Open MetaSounds project', str(self.project_path.parent),
                                              'MetaSounds project (*.json)')
        if path:
            self.load(Path(path))

    def load(self, path):
        try:
            project = load_project(path)
        except Exception as error:
            self.say(f'Could not open {Path(path).name}: {error}', True)
            return
        self.save()
        self.project, self.project_path = project, Path(path)
        self.reset_after_load()
        self.save()

    def save_project_as(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Save MetaSounds project', str(self.project_path),
                                              'MetaSounds project (*.json)')
        if path:
            self.project_path = Path(path)
            self.save()
            self.build_project_page()

    def new_project(self):
        if QMessageBox.question(self, 'New project', 'Start a new project from the template? The current project '
                                'stays saved at ' + str(self.project_path)) != QMessageBox.StandardButton.Yes:
            return
        self.save()
        stamp = _dt.datetime.now().strftime('%Y-%m-%d %H%M')
        self.project, self.project_path = starter_project(), self.home / f'Prophecy {stamp}.metasounds.json'
        self.reset_after_load()
        self.save()

    def reset_after_load(self):
        self.selection = ('', '')
        self.selected_event = ''
        self.selected_pad = ''
        self.pad_values = {}
        self.map.fitted = False
        self.map.select('', '')
        world = self.project.world
        self.map.listener = [world.start_x, world.start_y]
        self.engine.set_listener(world.start_x, world.start_y, self.map.camera)
        self.engine.set_project(self.project)
        self.refresh_all()
        self.map.fit()

    # ------------------------------------------------------------ record and export
    def toggle_record(self):
        if self.record_button.isChecked():
            if not self.engine.running:
                self.record_button.setChecked(False)
                self.say('Turn audio on to record.', True)
                return
            self.engine.start_recording()
            self.say('Recording everything you hear…')
            return
        data = self.engine.stop_recording()
        self.record_button.setText('● Record')
        if not len(data):
            return
        folder = self.home / 'Recordings'
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"MetaSounds {_dt.datetime.now().strftime('%Y-%m-%d %H%M%S')}.wav"
        sf.write(str(path), data, me.SR, subtype='PCM_24')
        self.say(f'Saved {len(data) / me.SR:.1f} s to {path}')

    def export(self):
        self.save()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            folder, report = export_unreal(self.project, self.export_folder, self.engine.clips.info)
        except Exception as error:
            LOG.exception('Unreal export failed')
            self.say(f'Export failed: {error}', True)
            return
        finally:
            QApplication.restoreOverrideCursor()
        warn = f" · {len(report['warnings'])} warnings in README" if report['warnings'] else ''
        self.say(f"Exported {report['sources']} MetaSounds, {report['waves']} WAVs to {folder.name}{warn}",
                 bool(report['warnings']))
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def shutdown(self):
        QApplication.instance().removeEventFilter(self)
        self.ui_timer.stop()
        self.move_timer.stop()
        if self.engine.recording is not None:
            self.record_button.setChecked(False)
            self.toggle_record()
        if self.dirty:
            self.save()
        self.engine.shutdown()


def attach(window, home, libraries):
    """Optional: embed MetaSounds as a second tab of Sound Studio (call after studio_layout.build).

    Not used while MetaSounds ships as its own app; kept so it can be merged later.
    The studio's eventFilter must then ignore keys while tab 1 is active."""
    studio = window.takeCentralWidget()
    tabs = QTabWidget()
    tabs.setObjectName('modeTabs')
    tabs.setDocumentMode(True)
    tabs.addTab(studio, 'Sound Studio')
    meta = MetaSoundsTab(window, home, libraries)
    tabs.addTab(meta, 'MetaSounds')
    window.setCentralWidget(tabs)
    window.tabs = tabs
    window.metasounds = meta

    def switched(index):
        if index == 1:
            if getattr(window, 'play_mode', None) and not window.player.paused:
                window.toggle_play()
            meta.activate()
        else:
            meta.deactivate()
    tabs.currentChanged.connect(switched)
    return meta
