"""Un trajet contient des points et les distances cumulees entre ces points."""

from math import atan2, degrees, hypot
from bisect import bisect_right


def bezier(debut, controle1, controle2, fin, etapes=24):
    """Calculer les points d'un virage arrondi avec la formule de Bezier.

    Les deux points de controle fixent la forme du virage. Cette formule
    geometrique evite que la voiture change brutalement de direction.
    """
    resultat = []
    for index in range(1, etapes + 1):
        t = index / etapes
        u = 1 - t
        x = (u**3 * debut[0] + 3 * u**2 * t * controle1[0]
             + 3 * u * t**2 * controle2[0] + t**3 * fin[0])
        y = (u**3 * debut[1] + 3 * u**2 * t * controle1[1]
             + 3 * u * t**2 * controle2[1] + t**3 * fin[1])
        resultat.append((x, y))
    return resultat


class Trajet:
    def __init__(self, nom, points):
        if len(points) < 2:
            raise ValueError("Un trajet doit contenir au moins deux points.")
        self.nom = nom
        self.points = tuple(points)
        self.distances = [0.0]
        for index in range(1, len(points)):
            debut = points[index - 1]
            fin = points[index]
            longueur = hypot(fin[0] - debut[0], fin[1] - debut[1])
            if longueur <= 0:
                raise ValueError("Deux points consecutifs doivent etre distincts.")
            self.distances.append(self.distances[-1] + longueur)
        self.longueur = self.distances[-1]

    def position_a(self, distance):
        """Trouver la position et l'angle du vehicule sur le trajet."""
        distance = max(0.0, min(distance, self.longueur))
        index = min(len(self.points) - 2, bisect_right(self.distances, distance) - 1)
        debut = self.points[index]
        fin = self.points[index + 1]
        longueur_segment = self.distances[index + 1] - self.distances[index]
        fraction = (distance - self.distances[index]) / longueur_segment
        x = debut[0] + fraction * (fin[0] - debut[0])
        y = debut[1] + fraction * (fin[1] - debut[1])
        angle = degrees(atan2(fin[1] - debut[1], fin[0] - debut[0]))
        return x, y, angle
