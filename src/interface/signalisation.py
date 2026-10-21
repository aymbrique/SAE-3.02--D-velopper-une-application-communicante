"""Travaux et panneaux decoratifs, dessines uniquement avec PyQt6."""

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QBrush, QColor, QPen, QPolygonF

from src.interface.batiments import label, polygon, rectangle
from src.modeles.plan import NODES, ROAD_HALF, STOP_DISTANCE


def draw_barrier(scene, x, y, width):
    """Une barriere blanche et rouge avec deux pieds."""
    for dx in (6, width - 10):
        rectangle(scene, x + dx, y + 8, 4, 16, "#50565a")
    rectangle(scene, x, y, width, 10, "#fff5e7")
    for dx in range(0, int(width) - 12, 16):
        polygon(scene, [(x + dx, y + 10), (x + dx + 5, y),
                        (x + dx + 13, y), (x + dx + 8, y + 10)], "#ce4d3d")


def draw_cone(scene, x, y):
    rectangle(scene, x - 7, y + 10, 14, 3, "#514b43")
    polygon(scene, [(x, y - 5), (x - 5, y + 10), (x + 5, y + 10)], "#ed8b32")
    rectangle(scene, x - 3, y + 3, 6, 3, "#fff5e7")


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
    rectangle(scene, x + 4, top + 8, ROAD_HALF - 8, bottom - top - 16, "#c3ad87")
    for y in range(int(top) + 55, int(bottom) - 25, 52):
        polygon(scene, [(x + 16, y - 10), (x + 42, y - 14),
                        (x + 55, y + 4), (x + 38, y + 13),
                        (x + 12, y + 8)], "#8d7355")
        draw_cone(scene, x + 8, y)
        draw_cone(scene, x + ROAD_HALF - 8, y + 18)
    draw_barrier(scene, x + 2, top + 13, ROAD_HALF - 4)
    draw_barrier(scene, x + 2, bottom - 26, ROAD_HALF - 4)
    sign_x = NODES["R"][0] + 45
    draw_works_sign(scene, sign_x, top + 38)
    rectangle(scene, sign_x - 53, top + 78, 106, 22, "#fff5e7")
    label(scene, "ROUTE BARRÉE", sign_x - 53, top + 82, 106, 11)


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
