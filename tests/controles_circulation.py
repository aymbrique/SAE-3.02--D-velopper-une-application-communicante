"""Verification independante des gabarits affiches et des distances de suivi."""

from itertools import combinations
from math import cos, hypot, radians, sin
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath, QPolygonF


def verifier_espacement(verification, simulation):
    for premier, second in combinations(simulation.vehicules, 2):
        if (premier.type_vehicule == second.type_vehicule == "car"
                and premier.decalage_lateral == second.decalage_lateral == 0):
            verification.assertGreaterEqual(hypot(premier.position[0] - second.position[0],
                                         premier.position[1] - second.position[1]), 44 - 1e-6,
                                    (simulation.temps, premier.identifiant, second.identifiant))
            continue
        chemins = []
        for vehicule in (premier, second):
            longueur, largeur = (28, 15) if vehicule.type_vehicule == "car" else (36, 18)
            x, y, angle = vehicule.position
            c, s = cos(radians(angle)), sin(radians(angle))
            points = []
            for a, b in ((-1,-1), (-1,1), (1,1), (1,-1)):
                px, py = a * (longueur / 2 + 1.49), b * (largeur / 2 + 1.49)
                points.append(QPointF(x + px * c - py * s, y + px * s + py * c))
            chemin = QPainterPath()
            chemin.addPolygon(QPolygonF(points))
            chemin.closeSubpath()
            chemins.append(chemin)
        verification.assertFalse(chemins[0].intersects(chemins[1]),
                         (simulation.temps, premier.identifiant, second.identifiant))
