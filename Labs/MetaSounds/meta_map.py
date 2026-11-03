"""Top-down world map: listener, camera, zones, emitters and live voices."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QWidget

from meta_model import BUS_COLORS, point_in_polygon

MODES = ('move', 'edit', 'zone', 'emitter', 'play')
HINTS = {
    'move': 'Click or drag to move the character · right-drag to aim the camera · wheel to zoom',
    'edit': 'Drag zones, corners and emitters · double-click an edge to add a corner · Delete removes',
    'zone': 'Click to add corners · double-click or Enter to finish · Esc cancels',
    'emitter': 'Click to place an emitter for the selected loop event',
    'play': 'Click to play the selected pad at that spot',
}


class MapView(QWidget):
    listenerMoved = Signal(float, float)
    cameraTurned = Signal(float)
    selectionChanged = Signal(str, str)      # kind, id
    geometryEdited = Signal()
    zoneDrawn = Signal(list)
    emitterPlaced = Signal(float, float)
    playAt = Signal(float, float)
    deleteRequested = Signal()

    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(360, 240)
        self.project = None
        self.snapshot = {}
        self.listener = [0., 0.]
        self.camera = 0.
        self.mode = 'move'
        self.selection = ('', '')
        self.draft = []
        self.scale = .05          # pixels per centimetre
        self.center = [0., 0.]
        self.background = None
        self.background_path = ''
        self.drag = None
        self.hover = None
        self.fitted = False

    # ------------------------------------------------------------ setup
    def set_project(self, project):
        self.project = project
        image = project.world.image
        if image != self.background_path:
            self.background_path = image
            pixmap = QPixmap(image) if image else QPixmap()
            self.background = None if pixmap.isNull() else pixmap
        if not self.fitted:
            self.fit()
        self.update()

    def fit(self):
        if not self.project or self.width() < 10:
            return
        w = self.project.world
        span_x, span_y = max(100., w.max_x - w.min_x), max(100., w.max_y - w.min_y)
        self.scale = min((self.width() - 40) / span_x, (self.height() - 40) / span_y)
        self.center = [(w.min_x + w.max_x) / 2, (w.min_y + w.max_y) / 2]
        self.fitted = True
        self.update()

    def resizeEvent(self, event):
        if not self.fitted:
            self.fit()
        super().resizeEvent(event)

    def set_mode(self, mode):
        self.mode = mode
        self.draft = []
        self.setCursor(Qt.CursorShape.CrossCursor if mode in ('zone', 'emitter', 'play') else Qt.CursorShape.ArrowCursor)
        self.update()

    def select(self, kind, ident):
        self.selection = (kind, ident)
        self.update()

    def set_snapshot(self, snapshot):
        self.snapshot = snapshot
        self.update()

    # ------------------------------------------------------------ coordinates
    def to_screen(self, x, y):
        return QPointF((x - self.center[0]) * self.scale + self.width() / 2,
                       (y - self.center[1]) * self.scale + self.height() / 2)

    def to_world(self, point):
        return ((point.x() - self.width() / 2) / self.scale + self.center[0],
                (point.y() - self.height() / 2) / self.scale + self.center[1])

    # ------------------------------------------------------------ painting
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor('#1c1e21'))
        if not self.project:
            return
        world = self.project.world
        top_left, bottom_right = self.to_screen(world.min_x, world.min_y), self.to_screen(world.max_x, world.max_y)
        bounds = QRectF(top_left, bottom_right)
        painter.fillRect(bounds, QColor('#26292d'))
        if self.background is not None:
            painter.setOpacity(.55)
            painter.drawPixmap(bounds, self.background, QRectF(self.background.rect()))
            painter.setOpacity(1.)
        self.paint_grid(painter, bounds)
        painter.setPen(QPen(QColor('#4b5058'), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(bounds)
        weights = self.snapshot.get('zones', {})
        self.labels = []
        for zone in sorted(self.project.zones, key=lambda z: z.priority):
            if not zone.is_default and len(zone.points) >= 3:
                self.paint_zone(painter, zone, weights.get(zone.id, 0.))
        for emitter in self.project.emitters:
            self.paint_emitter(painter, emitter)
        self.paint_voices(painter)
        self.paint_listener(painter)
        if self.draft:
            pen = QPen(QColor('#ffffff'), 1.5, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            points = [self.to_screen(*p) for p in self.draft]
            if self.hover:
                points.append(self.to_screen(*self.hover))
            painter.drawPolyline(QPolygonF(points))
            painter.setBrush(QColor('#ffffff'))
            for point in points[:len(self.draft)]:
                painter.drawEllipse(point, 3, 3)
        self.paint_overlay(painter, weights)

    def paint_grid(self, painter, bounds):
        for step, color in ((100., '#2c2f34'), (1000., '#373b41')):
            if step * self.scale < 9:
                continue
            painter.setPen(QPen(QColor(color), 1))
            world = self.project.world
            x = math.ceil(world.min_x / step) * step
            while x <= world.max_x:
                sx = self.to_screen(x, 0).x()
                painter.drawLine(QPointF(sx, bounds.top()), QPointF(sx, bounds.bottom()))
                x += step
            y = math.ceil(world.min_y / step) * step
            while y <= world.max_y:
                sy = self.to_screen(0, y).y()
                painter.drawLine(QPointF(bounds.left(), sy), QPointF(bounds.right(), sy))
                y += step

    def paint_zone(self, painter, zone, weight):
        color = QColor(zone.color)
        polygon = QPolygonF([self.to_screen(*p) for p in zone.points])
        fill = QColor(color)
        fill.setAlpha(int(22 + 70 * weight))
        selected = self.selection == ('zone', zone.id)
        painter.setBrush(fill)
        outline = QColor(color)
        outline.setAlpha(255 if selected else 150)
        pen = QPen(outline, 2.2 if selected else 1.2)
        if zone.interior:
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawPolygon(polygon)
        if selected:
            painter.setBrush(QColor('#ffffff'))
            painter.setPen(QPen(outline, 1.5))
            for point in polygon:
                painter.drawEllipse(point, 4.5, 4.5)
        cx = sum(p[0] for p in zone.points) / len(zone.points)
        cy = sum(p[1] for p in zone.points) / len(zone.points)
        centre = self.to_screen(cx, cy)
        painter.setPen(QColor(color).lighter(140))
        font = QFont(self.font())
        font.setPointSizeF(9)
        font.setBold(True)
        painter.setFont(font)
        text = zone.name + (f'  {weight * 100:.0f}%' if weight > .005 else '')
        width = painter.fontMetrics().horizontalAdvance(text) + 6
        box = QRectF(centre.x() - width / 2, centre.y() - 9, width, 18)
        while any(box.intersects(taken) for taken in self.labels):
            box.translate(0, 15)
        self.labels.append(box)
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)

    def attenuation_for(self, emitter):
        p = self.project
        event = p.event(emitter.event)
        att = p.attenuation(emitter.attenuation) or (p.attenuation(event.attenuation) if event else None)
        return event, att

    def paint_emitter(self, painter, emitter):
        event, att = self.attenuation_for(emitter)
        centre = self.to_screen(emitter.x, emitter.y)
        color = QColor(BUS_COLORS.get(event.bus if event else 'SFX', '#8fb3ff'))
        selected = self.selection == ('emitter', emitter.id)
        if att is not None and event is not None and event.spatial == '3D':
            painter.save()
            painter.translate(centre)
            painter.rotate(emitter.yaw)
            inner = QColor(color)
            inner.setAlpha(40 if selected else 22)
            outer = QColor(color)
            outer.setAlpha(150 if selected else 70)
            s = self.scale
            for grow, brush, style in ((0., inner, Qt.PenStyle.SolidLine), (att.falloff, Qt.BrushStyle.NoBrush, Qt.PenStyle.DashLine)):
                painter.setBrush(brush)
                painter.setPen(QPen(outer, 1, style))
                if att.shape in ('Sphere', 'Cone'):
                    r = (att.inner_radius + grow) * s
                    if att.shape == 'Cone':
                        span = att.cone_angle + (att.cone_falloff_angle if grow else 0.)
                        path = QPainterPath(QPointF(0, 0))
                        path.arcTo(QRectF(-r, -r, 2 * r, 2 * r), span, -2 * span)
                        path.closeSubpath()
                        painter.drawPath(path)
                    else:
                        painter.drawEllipse(QPointF(0, 0), r, r)
                elif att.shape == 'Box':
                    painter.drawRoundedRect(QRectF(-(att.box_x + grow) * s, -(att.box_y + grow) * s,
                                                   2 * (att.box_x + grow) * s, 2 * (att.box_y + grow) * s),
                                            grow * s, grow * s)
                else:
                    h, r = att.capsule_half_height * s, (att.capsule_radius + grow) * s
                    painter.drawRoundedRect(QRectF(-h - r, -r, 2 * (h + r), 2 * r), r, r)
            painter.restore()
        painter.setPen(QPen(QColor('#1c1e21'), 1.5))
        painter.setBrush(color if event else QColor('#7b818b'))
        size = 7 if selected else 5.5
        painter.drawPolygon(QPolygonF([QPointF(centre.x(), centre.y() - size), QPointF(centre.x() + size, centre.y()),
                                       QPointF(centre.x(), centre.y() + size), QPointF(centre.x() - size, centre.y())]))
        painter.setPen(QColor('#e5e7eb' if selected else '#b0b4bd'))
        font = QFont(self.font())
        font.setPointSizeF(8)
        painter.setFont(font)
        box = QRectF(centre.x() + 9, centre.y() - 8, painter.fontMetrics().horizontalAdvance(emitter.name) + 4, 15)
        while any(box.intersects(taken) for taken in self.labels):
            box.translate(0, 14)
        self.labels.append(box)
        painter.drawText(box, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, emitter.name)

    def paint_voices(self, painter):
        for x, y, level, bus, virtual, name, owner in self.snapshot.get('voices', ()):
            if owner == 'emitter':
                continue
            point = self.to_screen(x, y)
            color = QColor(BUS_COLORS.get(bus, '#8fb3ff'))
            if virtual:
                painter.setPen(QPen(QColor('#6a707a'), 1))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(point, 3, 3)
                continue
            radius = 3 + min(14., 60 * level)
            glow = QColor(color)
            glow.setAlpha(70)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(point, radius + 3, radius + 3)
            painter.setBrush(color)
            painter.drawEllipse(point, 3, 3)
        for x, y, level, bus, virtual, name, owner in self.snapshot.get('voices', ()):
            if owner == 'emitter' and not virtual and level > 1e-4:
                point = self.to_screen(x, y)
                color = QColor(BUS_COLORS.get(bus, '#8fb3ff'))
                color.setAlpha(110)
                painter.setPen(QPen(color, 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                r = 9 + min(12., 50 * level)
                painter.drawEllipse(point, r, r)

    def paint_listener(self, painter):
        point = self.to_screen(*self.listener)
        painter.save()
        painter.translate(point)
        painter.rotate(math.degrees(self.camera))
        cone = QPainterPath(QPointF(0, 0))
        cone.arcTo(QRectF(-90, -90, 180, 180), 35, -70)
        cone.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(217, 220, 225, 34))
        painter.drawPath(cone)
        # camera body sits behind the character (third person)
        painter.setBrush(QColor('#c4cbd6'))
        painter.drawRoundedRect(QRectF(-34, -6, 12, 12), 3, 3)
        painter.setPen(QPen(QColor('#c4cbd6'), 1, Qt.PenStyle.DotLine))
        painter.drawLine(QPointF(-22, 0), QPointF(-9, 0))
        painter.restore()
        painter.setPen(QPen(QColor('#1c1e21'), 2))
        painter.setBrush(QColor('#f4f7ff'))
        painter.drawEllipse(point, 8, 8)
        tip = QPointF(point.x() + math.cos(self.camera) * 13, point.y() + math.sin(self.camera) * 13)
        painter.setPen(QPen(QColor('#f4f7ff'), 2.5))
        painter.drawLine(point, tip)

    def paint_overlay(self, painter, weights):
        font = QFont(self.font())
        font.setPointSizeF(8.5)
        painter.setFont(font)
        lines = []
        for zone in sorted(self.project.zones, key=lambda z: -weights.get(z.id, 0)):
            w = weights.get(zone.id, 0.)
            if w > .005:
                lines.append((zone.color, f'{zone.name}  {w * 100:.0f}%'))
        y = 18
        for color, text in lines[:5]:
            painter.setPen(QColor(color))
            painter.drawText(QPointF(12, y), text)
            y += 15
        surface = self.snapshot.get('surface')
        if surface:
            painter.setPen(QColor('#b0b4bd'))
            painter.drawText(QPointF(12, y + 2), f'Ground: {surface}')
        painter.setPen(QColor('#959aa4'))
        hint = HINTS.get(self.mode, '')
        painter.drawText(QRectF(0, 6, self.width() - 12, 18),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, hint)
        # scale bar
        meters = 1
        for candidate in (1, 2, 5, 10, 20, 50, 100, 200, 500):
            if candidate * 100 * self.scale >= 60:
                meters = candidate
                break
        length = meters * 100 * self.scale
        y = self.height() - 14
        painter.setPen(QPen(QColor('#b0b4bd'), 1.5))
        painter.drawLine(QPointF(12, y), QPointF(12 + length, y))
        painter.drawLine(QPointF(12, y - 4), QPointF(12, y + 1))
        painter.drawLine(QPointF(12 + length, y - 4), QPointF(12 + length, y + 1))
        x, yw = self.listener
        painter.drawText(QPointF(18 + length, y + 4), f'{meters} m    X {x:.0f}  Y {yw:.0f} cm')

    # ------------------------------------------------------------ hit testing
    def emitter_at(self, point):
        best, ident = 11., ''
        for emitter in self.project.emitters:
            d = (self.to_screen(emitter.x, emitter.y) - point).manhattanLength()
            if d < best:
                best, ident = d, emitter.id
        return ident

    def vertex_at(self, point):
        kind, ident = self.selection
        if kind != 'zone':
            return None
        zone = self.project.zone(ident)
        if zone is None:
            return None
        for index, p in enumerate(zone.points):
            if (self.to_screen(*p) - point).manhattanLength() < 10:
                return index
        return None

    def zone_at(self, x, y):
        hits = [z for z in self.project.zones if not z.is_default and point_in_polygon(x, y, z.points)]
        if not hits:
            return ''
        return max(hits, key=lambda z: (z.priority, -abs(_area(z.points)))).id

    # ------------------------------------------------------------ mouse
    def mousePressEvent(self, event):
        self.setFocus()
        if not self.project:
            return
        pos = event.position()
        x, y = self.to_world(pos)
        if event.button() == Qt.MouseButton.MiddleButton:
            self.drag = ('pan', pos, list(self.center))
            return
        if event.button() == Qt.MouseButton.RightButton:
            self.drag = ('aim',)
            self.aim(x, y)
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self.mode == 'move':
            self.drag = ('listener',)
            self.move_listener(x, y)
        elif self.mode == 'zone':
            self.draft.append([round(x), round(y)])
            self.update()
        elif self.mode == 'emitter':
            self.emitterPlaced.emit(round(x), round(y))
        elif self.mode == 'play':
            self.playAt.emit(x, y)
        else:
            vertex = self.vertex_at(pos)
            if vertex is not None:
                self.drag = ('vertex', vertex)
                return
            emitter = self.emitter_at(pos)
            if emitter:
                self.select('emitter', emitter)
                self.selectionChanged.emit('emitter', emitter)
                self.drag = ('emitter', emitter, x, y)
                return
            zone = self.zone_at(x, y)
            self.select('zone' if zone else '', zone)
            self.selectionChanged.emit('zone' if zone else '', zone)
            if zone:
                self.drag = ('zone', zone, x, y)

    def mouseDoubleClickEvent(self, event):
        pos = event.position()
        if self.mode == 'zone':
            self.finish_zone()
            return
        if self.mode != 'edit' or self.selection[0] != 'zone':
            return
        zone = self.project.zone(self.selection[1])
        if zone is None:
            return
        x, y = self.to_world(pos)
        best, index = 12., None
        for i, a in enumerate(zone.points):
            b = zone.points[(i + 1) % len(zone.points)]
            d = _segment_distance(x, y, a, b) * self.scale
            if d < best:
                best, index = d, i
        if index is not None:
            zone.points.insert(index + 1, [round(x), round(y)])
            self.geometryEdited.emit()
            self.update()

    def mouseMoveEvent(self, event):
        pos = event.position()
        x, y = self.to_world(pos)
        if self.mode == 'zone' and self.draft:
            self.hover = (x, y)
            self.update()
        if not self.drag:
            return
        kind = self.drag[0]
        if kind == 'pan':
            _, start, centre = self.drag
            delta = pos - start
            self.center = [centre[0] - delta.x() / self.scale, centre[1] - delta.y() / self.scale]
            self.update()
        elif kind == 'aim':
            self.aim(x, y)
        elif kind == 'listener':
            self.move_listener(x, y)
        elif kind == 'vertex':
            zone = self.project.zone(self.selection[1])
            if zone is not None:
                zone.points[self.drag[1]] = [round(x), round(y)]
                self.update()
        elif kind in ('emitter', 'zone'):
            _, ident, ox, oy = self.drag
            dx, dy = x - ox, y - oy
            if kind == 'emitter':
                emitter = self.project.emitter(ident)
                if emitter is not None:
                    emitter.x, emitter.y = round(emitter.x + dx), round(emitter.y + dy)
            else:
                zone = self.project.zone(ident)
                if zone is not None:
                    zone.points = [[round(px + dx), round(py + dy)] for px, py in zone.points]
            self.drag = (kind, ident, x, y)
            self.update()

    def mouseReleaseEvent(self, event):
        if self.drag and self.drag[0] in ('vertex', 'emitter', 'zone'):
            self.geometryEdited.emit()
        self.drag = None

    def wheelEvent(self, event):
        steps = event.angleDelta().y() / 120
        if not steps:
            return
        pos = event.position()
        before = self.to_world(pos)
        self.scale = min(3., max(.004, self.scale * (1.18 ** steps)))
        after = self.to_world(pos)
        self.center[0] += before[0] - after[0]
        self.center[1] += before[1] - after[1]
        self.update()

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.mode == 'zone':
            self.finish_zone()
        elif key == Qt.Key.Key_Escape and self.draft:
            self.draft = []
            self.update()
        elif key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self.mode == 'edit':
            self.deleteRequested.emit()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------ actions
    def finish_zone(self):
        points = self.draft
        self.draft = []
        self.hover = None
        if len(points) >= 3:
            self.zoneDrawn.emit(points)
        self.update()

    def move_listener(self, x, y):
        w = self.project.world
        x, y = min(max(x, w.min_x), w.max_x), min(max(y, w.min_y), w.max_y)
        self.listener = [x, y]
        self.listenerMoved.emit(x, y)
        self.update()

    def aim(self, x, y):
        lx, ly = self.listener
        if math.hypot(x - lx, y - ly) * self.scale > 4:
            self.camera = math.atan2(y - ly, x - lx)
            self.cameraTurned.emit(self.camera)
            self.update()


def _area(points):
    return sum(points[i][0] * points[(i + 1) % len(points)][1] - points[(i + 1) % len(points)][0] * points[i][1]
               for i in range(len(points))) / 2


def _segment_distance(x, y, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = dx * dx + dy * dy
    t = 0. if not length else max(0., min(1., ((x - a[0]) * dx + (y - a[1]) * dy) / length))
    return math.hypot(x - a[0] - t * dx, y - a[1] - t * dy)
