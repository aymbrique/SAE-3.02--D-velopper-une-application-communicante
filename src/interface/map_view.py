"""Carte simple : rectangles pour les routes et vehicules, ronds pour les feux."""

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainterPath, QPen
from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsScene, QGraphicsView

from src.models.layout import (CX, CY, ROAD_HALF, SCENE_HEIGHT, SCENE_WIDTH,
                               DESTINATIONS, INTERVENTION_POINTS)

SIGNAL_COLORS = {"red": "red", "amber": "orange", "green": "green"}


class VehicleItem(QGraphicsRectItem):
    """Un vehicule est un rectangle que l'on deplace et tourne."""

    def __init__(self, state):
        super().__init__()
        self.setZValue(20)
        self.setState(state, 0)

    def setState(self, state, elapsed):
        if state.kind == "car":
            self.setRect(-14, -7.5, 28, 15)
            color = "blue"
            name = "Voiture " + state.identifier
        else:
            self.setRect(-18, -9, 36, 18)
            name = "Secours " + state.identifier
            if state.kind == "fire":
                color = "red"
            else:
                color = "white"
        self.setBrush(QBrush(QColor(color)))
        self.setPen(QPen(QColor("black")))
        self.setPos(state.x, state.y)
        self.setRotation(state.heading)
        self.setToolTip(f"{name}\n{state.route.name}\n{state.stage}")


class MapView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setSceneRect(0, 0, SCENE_WIDTH, SCENE_HEIGHT)
        self.setBackgroundBrush(QColor("#a8cf8a"))
        self.setMinimumSize(420, 340)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.vehicle_items = {}
        self.lights = {}
        self.route_item = None
        self.zoom_factor = 1.0
        self._draw_map()

    def rectangle(self, x, y, width, height, color):
        return self.scene().addRect(x, y, width, height,
                                   QPen(Qt.PenStyle.NoPen), QBrush(QColor(color)))

    def text(self, text, x, y):
        item = self.scene().addSimpleText(text)
        item.setPos(x, y)
        return item

    def _draw_map(self):
        # Les deux routes principales et les acces des secours.
        self.rectangle(0, CY - ROAD_HALF, SCENE_WIDTH, 2 * ROAD_HALF, "gray")
        self.rectangle(CX - ROAD_HALF, 0, 2 * ROAD_HALF, SCENE_HEIGHT, "gray")
        self.rectangle(245, 150, 250, 184, "lightgray")
        self.rectangle(495, 192, 86, 46, "lightgray")
        # Quatre aires simples, raccordees aux routes principales.
        self.rectangle(495, 680, 345, 96, "lightgray")
        self.rectangle(800, 145, 96, 345, "lightgray")
        self.rectangle(220, 370, 96, 345, "lightgray")
        self.rectangle(495, 50, 300, 100, "lightgray")

        # Une ligne blanche separe les deux sens de circulation.
        pen = QPen(QColor("white"), 2, Qt.PenStyle.DashLine)
        self.scene().addLine(0, CY, CX - ROAD_HALF, CY, pen)
        self.scene().addLine(CX + ROAD_HALF, CY, SCENE_WIDTH, CY, pen)
        self.scene().addLine(CX, 0, CX, CY - ROAD_HALF, pen)
        self.scene().addLine(CX, CY + ROAD_HALF, CX, SCENE_HEIGHT, pen)
        stop = QPen(QColor("white"), 4)
        self.scene().addLine(CX - 82, CY + 8, CX - 82, CY + ROAD_HALF - 8, stop)
        self.scene().addLine(CX + 8, CY + 82, CX + ROAD_HALF - 8, CY + 82, stop)
        self.scene().addLine(CX + 82, CY - ROAD_HALF + 8, CX + 82, CY - 8, stop)
        self.scene().addLine(CX - ROAD_HALF + 8, CY - 82, CX - 8, CY - 82, stop)

        self.text("CASERNE", 280, 140)
        self.text("Place 01", 280, 235)
        self.text("Place 02", 280, 295)
        for side, (x, y) in INTERVENTION_POINTS.items():
            self.rectangle(x - 22, y - 14, 44, 28, "#ffe091")
            self.text("Intervention " + DESTINATIONS[side], x - 65, y - 43)
        self.text("NORD", 530, 5)
        self.text("SUD", 535, 837)
        self.text("OUEST", 15, 370)
        self.text("EST", 1045, 465)

        positions = {"N": (450, 325), "S": (640, 520),
                     "E": (640, 325), "W": (450, 520)}
        for origin, (x, y) in positions.items():
            self.lights[origin] = self.scene().addEllipse(
                x, y, 20, 20, QPen(QColor("black")), QBrush(QColor("red")))

    def sync(self, frame, elapsed):
        # Enlever les voitures qui ont fini leur trajet.
        identifiers = []
        for vehicle in frame.vehicles:
            identifiers.append(vehicle.identifier)
        for identifier in list(self.vehicle_items):
            if identifier not in identifiers:
                item = self.vehicle_items.pop(identifier)
                self.scene().removeItem(item)

        # Creer les nouveaux rectangles, puis mettre toutes les positions a jour.
        for state in frame.vehicles:
            if state.identifier not in self.vehicle_items:
                item = VehicleItem(state)
                self.vehicle_items[state.identifier] = item
                self.scene().addItem(item)
            self.vehicle_items[state.identifier].setState(state, elapsed)

        for origin, light in self.lights.items():
            if origin in ("N", "S"):
                signal = frame.north_south
            else:
                signal = frame.east_west
            light.setBrush(QBrush(QColor(SIGNAL_COLORS[signal])))

    def set_route(self, route):
        if self.route_item is not None:
            self.scene().removeItem(self.route_item)
            self.route_item = None
        if route is not None:
            path = QPainterPath(QPointF(*route.points[0]))
            for point in route.points[1:]:
                path.lineTo(QPointF(*point))
            pen = QPen(QColor("darkMagenta"), 3, Qt.PenStyle.DashLine)
            self.route_item = self.scene().addPath(path, pen)
            self.route_item.setZValue(8)

    def fit_scene(self, reset_zoom=False):
        if reset_zoom:
            self.zoom_factor = 1.0
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
        if event.angleDelta().y() > 0:
            self.zoom_factor *= 1.15
        else:
            self.zoom_factor /= 1.15
        self.zoom_factor = max(1.0, min(2.5, self.zoom_factor))
        self.fit_scene()
        event.accept()
