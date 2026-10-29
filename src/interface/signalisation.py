"""Travaux et panneaux decoratifs, dessines uniquement avec PyQt6."""

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QBrush, QColor, QPen, QPolygonF

from src.interface.batiments import etiquette, polygone, rectangle
from src.modeles.plan import NOEUDS, DEMI_LARGEUR_ROUTE, DISTANCE_ARRET


def dessiner_barriere(scene, x, y, largeur):
    """Une barriere blanche et rouge avec deux pieds."""
    for dx in (6, largeur - 10):
        rectangle(scene, x + dx, y + 8, 4, 16, "#50565a")
    rectangle(scene, x, y, largeur, 10, "white")
    for index in (0, 2, 4):
        rectangle(scene, x + index * largeur / 5, y, largeur / 5, 10, "red")


def dessiner_panneau_travaux(scene, x, y):
    rectangle(scene, x - 2, y + 14, 4, 24, "#747c80")
    triangle = QPolygonF([QPointF(x, y - 21), QPointF(x - 23, y + 17),
                         QPointF(x + 23, y + 17)])
    scene.addPolygon(triangle, QPen(QColor("#bd3b31"), 4),
                     QBrush(QColor("#ffdf79")))
    # Silhouette simple : une tete, un corps et une pelle.
    crayon = QPen(QColor("#343330"), 2.5)
    scene.addEllipse(x - 7, y - 8, 6, 6, crayon, QBrush(QColor("#343330")))
    for x1, y1, x2, y2 in ((-4, -1, 0, 5), (0, 5, -8, 12),
                          (0, 5, 3, 12), (-3, 1, 7, 4), (5, 0, 11, 12)):
        scene.addLine(x + x1, y + y1, x + x2, y + y2, crayon)
    polygone(scene, [(x + 7, y + 13), (x + 17, y + 13),
                    (x + 13, y + 8)], "#343330")


def dessiner_travaux(scene):
    """Habiller la voie descendante R-Q sans changer la circulation."""
    x = NOEUDS["R"][0] - DEMI_LARGEUR_ROUTE
    haut = NOEUDS["R"][1] + DEMI_LARGEUR_ROUTE
    bas = NOEUDS["Q"][1] - DEMI_LARGEUR_ROUTE
    dessiner_barriere(scene, x + 2, haut + 13, DEMI_LARGEUR_ROUTE - 4)
    dessiner_barriere(scene, x + 2, bas - 26, DEMI_LARGEUR_ROUTE - 4)
    panneau_x = NOEUDS["R"][0] + 45
    dessiner_panneau_travaux(scene, panneau_x, haut + 38)
    etiquette(scene, "TRAVAUX", panneau_x - 40, haut + 80, 80, 12)


def dessiner_cedez_passage(scene, x, y):
    rectangle(scene, x - 2, y + 12, 4, 16, "#747c80")
    triangle = QPolygonF([QPointF(x - 18, y - 14), QPointF(x + 18, y - 14),
                         QPointF(x, y + 14)])
    scene.addPolygon(triangle, QPen(QColor("#bd3b31"), 3.5),
                     QBrush(QColor("#fffaf0")))


def dessiner_panneaux_priorite(scene):
    """Trois panneaux avant les raccordements sans feux B, D et U."""
    # Arrivees du nord vers la route du milieu et celle du bas.
    for cle in ("B", "D"):
        x, y = NOEUDS[cle]
        dessiner_cedez_passage(scene, x - DEMI_LARGEUR_ROUTE - 25, y - DEMI_LARGEUR_ROUTE - 28)
        for dx in range(6, DEMI_LARGEUR_ROUTE - 6, 14):
            rectangle(scene, x - DEMI_LARGEUR_ROUTE + dx, y - DISTANCE_ARRET, 8, 4, "white")
    # Arrivee de l'est sur le T de la route superieure.
    x, y = NOEUDS["U"]
    dessiner_cedez_passage(scene, x + 110, y - DEMI_LARGEUR_ROUTE - 28)
    for dy in range(6, DEMI_LARGEUR_ROUTE - 6, 14):
        rectangle(scene, x + DISTANCE_ARRET, y - DEMI_LARGEUR_ROUTE + dy, 4, 8, "white")
