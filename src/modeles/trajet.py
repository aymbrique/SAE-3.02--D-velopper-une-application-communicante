"""Un trajet contient des points et les distances cumulees entre ces points."""

from math import atan2, degrees, hypot
from bisect import bisect_right


def bezier(start, control1, control2, end, steps=24):
    """Calculer les points d'un virage arrondi avec la formule de Bezier.

    Les deux points de controle fixent la forme du virage. Cette formule
    geometrique evite que la voiture change brutalement de direction.
    """
    result = []
    for index in range(1, steps + 1):
        t = index / steps
        u = 1 - t
        x = (u**3 * start[0] + 3 * u**2 * t * control1[0]
             + 3 * u * t**2 * control2[0] + t**3 * end[0])
        y = (u**3 * start[1] + 3 * u**2 * t * control1[1]
             + 3 * u * t**2 * control2[1] + t**3 * end[1])
        result.append((x, y))
    return result


class Route:
    def __init__(self, name, points):
        if len(points) < 2:
            raise ValueError("Un trajet doit contenir au moins deux points.")
        self.name = name
        self.points = tuple(points)
        self.distances = [0.0]
        for index in range(1, len(points)):
            start = points[index - 1]
            end = points[index]
            length = hypot(end[0] - start[0], end[1] - start[1])
            if length <= 0:
                raise ValueError("Deux points consecutifs doivent etre distincts.")
            self.distances.append(self.distances[-1] + length)
        self.length = self.distances[-1]

    def sample(self, distance):
        """Trouver la position et l'angle du vehicule sur le trajet."""
        distance = max(0.0, min(distance, self.length))
        index = min(len(self.points) - 2, bisect_right(self.distances, distance) - 1)
        start = self.points[index]
        end = self.points[index + 1]
        segment_length = self.distances[index + 1] - self.distances[index]
        fraction = (distance - self.distances[index]) / segment_length
        x = start[0] + fraction * (end[0] - start[0])
        y = start[1] + fraction * (end[1] - start[1])
        angle = degrees(atan2(end[1] - start[1], end[0] - start[0]))
        return x, y, angle
