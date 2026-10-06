"""Scène 2D : décors fixes, feux et véhicules animés."""

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsScene, QGraphicsView

from src.models.layout import CX, CY, ROAD_HALF, SCENE_HEIGHT, SCENE_WIDTH


SIGNAL_COLORS = {"red": "#f58178", "amber": "#ffd16c", "green": "#6de0b1"}


class VehicleItem(QGraphicsItem):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.flash = False
        self.setZValue(20)
        self.setState(state, 0)

    def boundingRect(self):
        return QRectF(-23, -15, 46, 30)

    def setState(self, state, elapsed):
        self.state = state
        self.flash = int(elapsed * 4) % 2 == 0
        self.setPos(state.x, state.y)
        self.setRotation(state.heading)
        name = "Voiture " + state.identifier if state.kind == "car" else "Secours " + state.identifier
        self.setToolTip(f"{name}\n{state.route.name}\n{state.stage}")
        self.update()

    def paint(self, painter, option, widget=None):
        state = self.state
        rescue = state.kind != "car"
        length, width = (36, 18) if rescue else (28, 15)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(14, 33, 41, 50))
        painter.drawRoundedRect(QRectF(-length / 2 + 2, -width / 2 + 3, length, width), 4, 4)
        painter.setBrush(QColor("#243441"))
        for x in (-length / 2 + 4, length / 2 - 9):
            for y in (-width / 2 - 2, width / 2 - 1):
                painter.drawRoundedRect(QRectF(x, y, 6, 3), 1, 1)
        painter.setPen(QPen(QColor(state.color).darker(120), 0.8))
        painter.setBrush(QColor(state.color))
        painter.drawRoundedRect(QRectF(-length / 2, -width / 2, length, width), 4, 4)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#304c60"))
        painter.drawRoundedRect(QRectF(length / 2 - 12, -width / 2 + 2, 7, width - 4), 2, 2)
        if state.kind == "car":
            painter.setBrush(QColor(state.color).lighter(110))
            painter.drawRoundedRect(QRectF(-8, -5, 9, 10), 2, 2)
        elif state.kind == "fire":
            painter.setBrush(QColor("#f6eddf"))
            painter.drawRect(QRectF(-length / 2 + 2, -2, 17, 4))
            painter.setPen(QPen(QColor("#8f433b"), 1))
            for x in (-12, -7, -2):
                painter.drawLine(QPointF(x, -5), QPointF(x, 5))
        else:
            painter.setBrush(QColor("#de7569"))
            painter.drawRect(QRectF(-11, -2, 11, 4))
            painter.drawRect(QRectF(-7.5, -5.5, 4, 11))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#fff4ce"))
        painter.drawRect(QRectF(length / 2 - 2, -width / 2 + 2, 2, 3))
        painter.drawRect(QRectF(length / 2 - 2, width / 2 - 5, 2, 3))
        if rescue:
            for index, y in enumerate((-5, 2)):
                active = state.busy and (self.flash == (index == 0))
                painter.setBrush(QColor("#62c8ff" if active else "#4b718d"))
                painter.drawRoundedRect(QRectF(1, y, 5, 3), 1, 1)


class MapView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setSceneRect(0, 0, SCENE_WIDTH, SCENE_HEIGHT)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setBackgroundBrush(QColor("#e8efe9"))
        self.setMinimumSize(420, 340)
        self.setAccessibleName("Carte 2D du carrefour de Colmar")
        self.vehicle_items = {}
        self.lights = {}
        self.route_item = None
        self.zoom_factor = 1.0
        self._draw_map()

    def draw_rect(self, x, y, width, height, color, radius=0, z=0):
        pen = QPen(Qt.PenStyle.NoPen)
        if radius:
            path = QPainterPath()
            path.addRoundedRect(QRectF(x, y, width, height), radius, radius)
            item = self.scene().addPath(path, pen, QBrush(QColor(color)))
        else:
            item = self.scene().addRect(x, y, width, height, pen, QBrush(QColor(color)))
        item.setZValue(z)
        return item

    def text(self, text, x, y, color="#637b71", size=13, centered=True):
        item = self.scene().addSimpleText(text, QFont("Arial", size, QFont.Weight.Bold))
        item.setBrush(QColor(color))
        item.setPos(x - item.boundingRect().width() / 2 if centered else x, y)
        item.setZValue(5)
        return item

    def tree(self, x, y):
        pen = QPen(Qt.PenStyle.NoPen)
        for dx, dy, radius, color in ((3, 5, 20, "#c8d7cc"), (0, 0, 19, "#83aa91"),
                                       (-4, -5, 12, "#9bbba3")):
            self.scene().addEllipse(x + dx - radius, y + dy - radius, radius * 2,
                                   radius * 2, pen, QBrush(QColor(color)))

    def _draw_map(self):
        self.draw_rect(0, 0, SCENE_WIDTH, SCENE_HEIGHT, "#e8efe9")
        for x, y, width, height in ((65, 100, 380, 240), (655, 110, 385, 230),
                                   (65, 540, 380, 240), (655, 540, 385, 240)):
            self.draw_rect(x, y, width, height, "#dce8dc", 24)
        # Allées de la caserne et du point d'intervention.
        self.draw_rect(245, 178, 250, 156, "#cad5d2", 12)
        self.draw_rect(495, 192, 86, 46, "#cad5d2")
        self.draw_rect(495, 680, 345, 96, "#cbd6d2", 15)
        # Trottoirs et chaussée, une voie dans chaque sens.
        self.draw_rect(0, CY - ROAD_HALF - 13, SCENE_WIDTH, 2 * ROAD_HALF + 26, "#c7d2d0")
        self.draw_rect(CX - ROAD_HALF - 13, 0, 2 * ROAD_HALF + 26, SCENE_HEIGHT, "#c7d2d0")
        self.draw_rect(0, CY - ROAD_HALF, SCENE_WIDTH, 2 * ROAD_HALF, "#354951")
        self.draw_rect(CX - ROAD_HALF, 0, 2 * ROAD_HALF, SCENE_HEIGHT, "#354951")
        self.draw_rect(CX - ROAD_HALF, CY - ROAD_HALF, 2 * ROAD_HALF, 2 * ROAD_HALF, "#3c5057")
        marking = QPen(QColor("#c6d4d0"), 2)
        marking.setDashPattern([8, 9])
        for a, b in (((0, CY), (CX - ROAD_HALF, CY)),
                     ((CX + ROAD_HALF, CY), (SCENE_WIDTH, CY)),
                     ((CX, 0), (CX, CY - ROAD_HALF)),
                     ((CX, CY + ROAD_HALF), (CX, SCENE_HEIGHT))):
            self.scene().addLine(*a, *b, marking)
        stop = QPen(QColor("#f5f1de"), 4)
        self.scene().addLine(CX - 82, CY + 8, CX - 82, CY + ROAD_HALF - 8, stop)
        self.scene().addLine(CX + 8, CY + 82, CX + ROAD_HALF - 8, CY + 82, stop)
        self.scene().addLine(CX + 82, CY - ROAD_HALF + 8, CX + 82, CY - 8, stop)
        self.scene().addLine(CX - ROAD_HALF + 8, CY - 82, CX - 8, CY - 82, stop)
        arrows = ((210, CY + 34, 0), (890, CY - 34, 180),
                  (CX - 34, 115, 90), (CX + 34, 780, 270))
        polygon = QPolygonF([QPointF(-17, -3), QPointF(4, -3), QPointF(4, -9),
                             QPointF(17, 0), QPointF(4, 9), QPointF(4, 3), QPointF(-17, 3)])
        for x, y, rotation in arrows:
            arrow = self.scene().addPolygon(polygon, QPen(Qt.PenStyle.NoPen), QBrush(QColor("#9cb3b5")))
            arrow.setPos(x, y)
            arrow.setRotation(rotation)
        # Caserne : deux baies avec les places des véhicules de secours.
        self.draw_rect(142, 152, 234, 195, "#c0ccc6", 12)
        self.draw_rect(135, 145, 234, 195, "#f6eee0", 12)
        self.draw_rect(150, 160, 199, 44, "#cb7668", 6)
        self.text("CASERNE", 249, 171, "#fff8ed", 17)
        for y, name in ((228, "01"), (288, "02")):
            self.draw_rect(162, y, 135, 34, "#dddbcf", 5)
            self.draw_rect(319, y, 75, 34, "#42585c", 3)
            self.text(name, 289, y + 9, "#768b83", 11)
        self.text("VÉHICULES DE SECOURS", 249, 115, "#926a5d", 11)
        # Bâtiments et point d'intervention, représentés de façon simplifiée.
        for x, y, width, height in ((738, 154, 240, 105), (119, 582, 210, 106),
                                    (284, 699, 120, 60)):
            self.draw_rect(x + 6, y + 7, width, height, "#c6d3ca", 9)
            self.draw_rect(x, y, width, height, "#f4f4e9", 9)
            self.draw_rect(x + 12, y + 12, width - 24, height - 24, "#e3e8dd", 5)
        self.draw_rect(753, 560, 264, 116, "#c6d3ca", 10)
        self.draw_rect(746, 553, 264, 116, "#f5f6ef", 10)
        self.draw_rect(768, 572, 40, 64, "#d77d71", 6)
        self.draw_rect(777, 600, 22, 8, "#fffaf3")
        self.draw_rect(784, 592, 8, 24, "#fffaf3")
        self.text("POINT D’INTERVENTION", 899, 591, "#71857a", 11)
        self.text("AIRE DE RETOUR", 881, 777, "#81958a", 10)
        for x, y in ((85, 165), (87, 292), (422, 134), (695, 157), (1007, 296),
                      (689, 304), (82, 726), (379, 582), (171, 748), (996, 759),
                      (680, 588), (701, 801)):
            self.tree(x, y)
        self.text("NORD", CX, 26, "#e0e9e5", 14)
        self.text("SUD", CX, 820, "#e0e9e5", 14)
        self.text("OUEST", 73, CY - 59, "#e0e9e5", 12)
        self.text("EST", 1020, CY + 41, "#e0e9e5", 12)
        for origin, (x, y) in {"N": (CX - 96, CY - 113), "E": (CX + 96, CY - 107),
                               "S": (CX + 96, CY + 86), "W": (CX - 96, CY + 90)}.items():
            self.draw_rect(x - 12, y - 17, 24, 56, "#243e46", 7, 6)
            bulbs = {}
            for index, name in enumerate(("red", "amber", "green")):
                bulb = self.scene().addEllipse(x - 6, y - 11 + 15 * index, 12, 12,
                                              QPen(Qt.PenStyle.NoPen), QBrush(QColor("#496169")))
                bulb.setZValue(7)
                bulbs[name] = bulb
            self.lights[origin] = bulbs

    def sync(self, frame, elapsed):
        identifiers = {vehicle.identifier for vehicle in frame.vehicles}
        for identifier in set(self.vehicle_items) - identifiers:
            self.scene().removeItem(self.vehicle_items.pop(identifier))
        for state in frame.vehicles:
            if state.identifier not in self.vehicle_items:
                self.vehicle_items[state.identifier] = VehicleItem(state)
                self.scene().addItem(self.vehicle_items[state.identifier])
            self.vehicle_items[state.identifier].setState(state, elapsed)
        for origin, bulbs in self.lights.items():
            active = frame.north_south if origin in ("N", "S") else frame.east_west
            for name, bulb in bulbs.items():
                bulb.setBrush(QBrush(QColor(SIGNAL_COLORS[name] if name == active else "#496169")))

    def set_route(self, route):
        if self.route_item is not None:
            self.scene().removeItem(self.route_item)
            self.route_item = None
        if route is None:
            return
        path = QPainterPath(QPointF(*route.points[0]))
        for point in route.points[1:]:
            path.lineTo(QPointF(*point))
        pen = QPen(QColor("#f3c666"), 3, Qt.PenStyle.DashLine)
        self.route_item = self.scene().addPath(path, pen)
        self.route_item.setZValue(8)

    def fit_scene(self, reset_zoom=False):
        if reset_zoom:
            self.zoom_factor = 1
        self.resetTransform()
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.scale(self.zoom_factor, self.zoom_factor)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_scene()

    def showEvent(self, event):
        super().showEvent(event)
        self.fit_scene()

    def wheelEvent(self, event):
        self.zoom_factor = max(1.0, min(2.5, self.zoom_factor * (1.15 if event.angleDelta().y() > 0 else 1 / 1.15)))
        self.fit_scene()
        event.accept()
