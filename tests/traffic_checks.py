"""Verification independante des gabarits affiches et des distances de suivi."""

from itertools import combinations
from math import cos, hypot, radians, sin
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath, QPolygonF


def assert_spacing(test, simulation):
    for first, second in combinations(simulation.vehicles, 2):
        if (first.kind == second.kind == "car"
                and first.lateral_offset == second.lateral_offset == 0):
            test.assertGreaterEqual(hypot(first.position[0] - second.position[0],
                                         first.position[1] - second.position[1]), 44 - 1e-6,
                                    (simulation.time, first.identifier, second.identifier))
            continue
        paths = []
        for vehicle in (first, second):
            length, width = (28, 15) if vehicle.kind == "car" else (36, 18)
            x, y, angle = vehicle.position
            c, s = cos(radians(angle)), sin(radians(angle))
            points = []
            for a, b in ((-1,-1), (-1,1), (1,1), (1,-1)):
                px, py = a * (length / 2 + 1.49), b * (width / 2 + 1.49)
                points.append(QPointF(x + px * c - py * s, y + px * s + py * c))
            path = QPainterPath()
            path.addPolygon(QPolygonF(points))
            path.closeSubpath()
            paths.append(path)
        test.assertFalse(paths[0].intersects(paths[1]),
                         (simulation.time, first.identifier, second.identifier))
