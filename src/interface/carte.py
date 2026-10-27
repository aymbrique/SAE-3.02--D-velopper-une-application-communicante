"""Carte simple : rectangles pour les routes et vehicules, ronds pour les feux."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QPen
from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsScene, QGraphicsView

from src.interface.batiments import draw_intervention_sites
from src.interface.signalisation import draw_roadworks, draw_yield_signs
from src.modeles.plan import (CX, CY, LANE, ROAD_HALF, SCENE_HEIGHT, SCENE_WIDTH,
                               NODES, ROAD_SEGMENTS, PARKING_Y)


SIGNAL_COLORS = {"red": "red", "amber": "orange", "green": "green"}


class VehicleItem(QGraphicsRectItem):
    """Un vehicule est un rectangle que l'on deplace et tourne."""

    def __init__(self, state):
        super().__init__()
        self.setZValue(20)
        self.setState(state)

    def setState(self, state):
        if state.kind == "car":
            self.setRect(-14, -7.5, 28, 15)
            color = "blue"
        else:
            self.setRect(-18, -9, 36, 18)
            if state.kind == "fire":
                color = "red"
            else:
                color = "white"
        self.setBrush(QBrush(QColor(color)))
        self.setPen(QPen(QColor("black")))
        self.setPos(state.x, state.y)
        self.setRotation(state.heading)


class MapView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setSceneRect(0, 0, SCENE_WIDTH, SCENE_HEIGHT)
        self.setBackgroundBrush(QColor("#a8cf8a"))
        self.setMinimumSize(420, 340)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setInteractive(False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.vehicle_items = {}
        self.lights = {}
        self._draw_map()

    def rectangle(self, x, y, width, height, color):
        return self.scene().addRect(x, y, width, height,
                                   QPen(Qt.PenStyle.NoPen), QBrush(QColor(color)))

    def text(self, text, x, y):
        item = self.scene().addSimpleText(text)
        item.setPos(x, y)
        return item

    def _draw_map(self):
        # Dessiner le reseau du croquis avec le style de la simulation existante.
        road_pen = QPen(QColor("gray"), 2 * ROAD_HALF)
        road_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        marking = QPen(QColor("white"), 2, Qt.PenStyle.DashLine)
        roads = []
        for first, second in ROAD_SEGMENTS:
            # Continuer aussi dans les marges visibles lorsque la fenetre n'a
            # pas les proportions du plan. Les trajets restent dans la scene.
            points = []
            for key in (first, second):
                x, y = NODES[key]
                if x == 0:
                    x -= SCENE_WIDTH
                elif x == SCENE_WIDTH:
                    x += SCENE_WIDTH
                if y == 0:
                    y -= SCENE_HEIGHT
                points.append((x, y))
            (x1, y1), (x2, y2) = points
            if (first, second) == ("R", "Q"):
                # Une seule voie descendante : la moitie droite reste en herbe.
                self.rectangle(x1 - ROAD_HALF, y1, ROAD_HALF, y2 - y1, "gray")
                continue
            roads.append((x1, y1, x2, y2))
            self.scene().addLine(x1, y1, x2, y2, road_pen)
        for x1, y1, x2, y2 in roads:
            self.scene().addLine(x1, y1, x2, y2, marking)
        # Enlever les pointilles au milieu des raccordements.
        for key in ("C", "F", "W", "B", "R", "E", "D", "L", "Q", "U", "H"):
            x, y = NODES[key]
            self.rectangle(x - ROAD_HALF, y - ROAD_HALF,
                           2 * ROAD_HALF, 2 * ROAD_HALF, "gray")

        # Ce raccordement ne se prend que vers le bas, depuis la gauche de R.
        x = NODES["R"][0] - LANE
        y = (NODES["R"][1] + NODES["Q"][1]) / 2
        arrow = QPen(QColor("white"), 3)
        for x1, y1, x2, y2 in ((x, y - 24, x, y + 24),
                               (x - 9, y + 12, x, y + 24),
                               (x + 9, y + 12, x, y + 24)):
            self.scene().addLine(x1, y1, x2, y2, arrow)
        draw_roadworks(self.scene())

        # Caserne et allee d'acces, a gauche de l'axe vertical principal.
        self.rectangle(190, 80, 180, 190, "lightgray")
        self.rectangle(340, 130, CX - ROAD_HALF - 340, 140, "lightgray")
        self.text("CASERNE", 225, 55)
        for identifier, y in PARKING_Y.items():
            self.text("Place " + identifier, 197, y - 9)

        draw_intervention_sites(self.scene())
        draw_yield_signs(self.scene())

        # Un seul carrefour a feux, a l'emplacement de la croix verte du croquis.
        stop = QPen(QColor("white"), 4)
        self.scene().addLine(CX - 82, CY + 8, CX - 82, CY + ROAD_HALF - 8, stop)
        self.scene().addLine(CX + 8, CY + 82, CX + ROAD_HALF - 8, CY + 82, stop)
        self.scene().addLine(CX + 82, CY - ROAD_HALF + 8, CX + 82, CY - 8, stop)
        self.scene().addLine(CX - ROAD_HALF + 8, CY - 82, CX - 8, CY - 82, stop)
        positions = {"N": (CX - 100, CY - 105), "S": (CX + 90, CY + 90),
                     "E": (CX + 90, CY - 105), "W": (CX - 100, CY + 90)}
        for origin, (x, y) in positions.items():
            self.lights[origin] = self.scene().addEllipse(
                x, y, 20, 20, QPen(QColor("black")), QBrush(QColor("red")))
        self.text("NORD", CX - 20, 5)
        self.text("OUEST", 25, CY - 58)
        self.text("EST", 1510, CY + 40)

    def sync(self, frame):
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
            self.vehicle_items[state.identifier].setState(state)

        for origin, light in self.lights.items():
            if origin in ("N", "S"):
                signal = frame.north_south
            else:
                signal = frame.east_west
            light.setBrush(QBrush(QColor(SIGNAL_COLORS[signal])))

    def fit_scene(self):
        self.resetTransform()
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def traffic_bounds(self):
        visible = self.mapToScene(self.viewport().rect()).boundingRect()
        return (min(0, visible.left()), min(0, visible.top()),
                max(SCENE_WIDTH, visible.right()), max(SCENE_HEIGHT, visible.bottom()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_scene()

    def showEvent(self, event):
        super().showEvent(event)
        self.fit_scene()

    def wheelEvent(self, event):
        # Garder le cadrage fixe, y compris avec la molette et le pavé tactile.
        event.accept()
