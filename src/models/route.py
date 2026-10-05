"""Géométrie des trajets, indépendante de l'affichage Qt."""

from bisect import bisect_right
from dataclasses import dataclass, field
from math import atan2, degrees, hypot


Point = tuple[float, float]


def bezier(start: Point, control1: Point, control2: Point, end: Point, steps=24):
    """Échantillonner un virage courbe pour orienter les véhicules en douceur."""
    result = []
    for index in range(1, steps + 1):
        t = index / steps
        u = 1 - t
        result.append(tuple(
            u ** 3 * start[axis] + 3 * u ** 2 * t * control1[axis]
            + 3 * u * t ** 2 * control2[axis] + t ** 3 * end[axis]
            for axis in (0, 1)
        ))
    return result


@dataclass(frozen=True)
class Route:
    name: str
    points: tuple[Point, ...]
    distances: tuple[float, ...] = field(init=False)

    def __post_init__(self):
        if len(self.points) < 2:
            raise ValueError("Un trajet doit contenir au moins deux points.")
        distances = [0.0]
        for start, end in zip(self.points, self.points[1:]):
            length = hypot(end[0] - start[0], end[1] - start[1])
            if length <= 0:
                raise ValueError("Deux points consécutifs doivent être distincts.")
            distances.append(distances[-1] + length)
        object.__setattr__(self, "distances", tuple(distances))

    @property
    def length(self):
        return self.distances[-1]

    def sample(self, distance):
        """Obtenir x, y et le cap en degrés à une distance le long du trajet."""
        distance = max(0.0, min(distance, self.length))
        index = min(bisect_right(self.distances, distance) - 1, len(self.points) - 2)
        start, end = self.points[index:index + 2]
        fraction = (distance - self.distances[index]) / (
            self.distances[index + 1] - self.distances[index]
        )
        return (
            start[0] + fraction * (end[0] - start[0]),
            start[1] + fraction * (end[1] - start[1]),
            degrees(atan2(end[1] - start[1], end[0] - start[0])),
        )
