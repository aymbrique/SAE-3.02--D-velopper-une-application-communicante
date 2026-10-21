"""Travaux et panneaux decoratifs, dessines uniquement avec PyQt6."""

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QBrush, QColor, QPen, QPolygonF

from src.interface.batiments import label, polygon, rectangle
from src.modeles.plan import NODES, ROAD_HALF, STOP_DISTANCE


def draw_barrier(scene, x, y, width):
    """Une barriere blanche et rouge avec deux pieds."""
    for dx in (6, width - 10):
        rectangle(scene, x + dx, y + 8, 4, 16, "#50565a")
    rectangle(scene, x, y, width, 10, "white")
    for index in (0, 2, 4):
        rectangle(scene, x + index * width / 5, y, width / 5, 10, "red")


def draw_works_sign(scene, x, y):
    rectangle(scene, x - 2, y + 14, 4, 24, "#747c80")
    triangle = QPolygonF([QPointF(x, y - 21), QPointF(x - 23, y + 17),
                         QPointF(x + 23, y + 17)])
    scene.addPolygon(triangle, QPen(QColor("#bd3b31"), 4),
                     QBrush(QColor("#ffdf79")))
    # Silhouette simple : une tete, un corps et une pelle.
    pen = QPen(QColor("#343330"), 2.5)
    scene.addEllipse(x - 7, y - 8, 6, 6, pen, QBrush(QColor("#343330")))
    for x1, y1, x2, y2 in ((-4, -1, 0, 5), (0, 5, -8, 12),
                          (0, 5, 3, 12), (-3, 1, 7, 4), (5, 0, 11, 12)):
        scene.addLine(x + x1, y + y1, x + x2, y + y2, pen)
    polygon(scene, [(x + 7, y + 13), (x + 17, y + 13),
                    (x + 13, y + 8)], "#343330")


def draw_roadworks(scene):
    """Habiller la voie descendante R-Q sans changer la circulation."""
    x = NODES["R"][0] - ROAD_HALF
    top = NODES["R"][1] + ROAD_HALF
    bottom = NODES["Q"][1] - ROAD_HALF
    draw_barrier(scene, x + 2, top + 13, ROAD_HALF - 4)
    draw_barrier(scene, x + 2, bottom - 26, ROAD_HALF - 4)
    sign_x = NODES["R"][0] + 45
    draw_works_sign(scene, sign_x, top + 38)
    label(scene, "TRAVAUX", sign_x - 40, top + 80, 80, 12)


def draw_yield_sign(scene, x, y):
    rectangle(scene, x - 2, y + 12, 4, 16, "#747c80")
    triangle = QPolygonF([QPointF(x - 18, y - 14), QPointF(x + 18, y - 14),
                         QPointF(x, y + 14)])
    scene.addPolygon(triangle, QPen(QColor("#bd3b31"), 3.5),
                     QBrush(QColor("#fffaf0")))


def draw_yield_signs(scene):
    """Trois panneaux avant les raccordements sans feux B, D et U."""
    # Arrivees du nord vers la route du milieu et celle du bas.
    for key in ("B", "D"):
        x, y = NODES[key]
        draw_yield_sign(scene, x - ROAD_HALF - 25, y - ROAD_HALF - 28)
        for dx in range(6, ROAD_HALF - 6, 14):
            rectangle(scene, x - ROAD_HALF + dx, y - STOP_DISTANCE, 8, 4, "white")
    # Arrivee de l'est sur le T de la route superieure.
    x, y = NODES["U"]
    draw_yield_sign(scene, x + 110, y - ROAD_HALF - 28)
    for dy in range(6, ROAD_HALF - 6, 14):
        rectangle(scene, x + STOP_DISTANCE, y - ROAD_HALF + dy, 4, 8, "white")
