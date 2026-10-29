"""Rangement des voitures et espace occupe par les vehicules."""

from math import cos, radians, sin

DECALAGE_RANGEMENT = 22.0
DISTANCE_ANTICIPATION = 220.0
MARGE_DEPASSEMENT = 40.0


def coins_carrosserie(vehicule, position, marge_supplementaire=0.0):
    x, y, angle = position
    longueur, largeur = (28, 15) if vehicule.type_vehicule == "car" else (36, 18)
    avant_vehicule = (cos(radians(angle)), sin(radians(angle)))
    droite = (-avant_vehicule[1], avant_vehicule[0])
    return tuple((x + a * (longueur / 2 + marge_supplementaire) * avant_vehicule[0]
                  + b * (largeur / 2 + marge_supplementaire) * droite[0],
                  y + a * (longueur / 2 + marge_supplementaire) * avant_vehicule[1]
                  + b * (largeur / 2 + marge_supplementaire) * droite[1])
                 for a, b in ((-1, -1), (-1, 1), (1, 1), (1, -1)))


def carrosseries_separees(premier, position, second, position_autre):
    """Rectangles orientes, avec 3 unites libres entre les carrosseries."""
    a = coins_carrosserie(premier, position, 1.5)
    b = coins_carrosserie(second, position_autre, 1.5)
    for angle in (position[2], position[2] + 90,
                  position_autre[2], position_autre[2] + 90):
        dx, dy = cos(radians(angle)), sin(radians(angle))
        projection_premier = [x * dx + y * dy for x, y in a]
        projection_second = [x * dx + y * dy for x, y in b]
        if max(projection_premier) <= min(projection_second) or max(projection_second) <= min(projection_premier):
            return True
    return False


def proche_secours(voiture, secours):
    """Meme route ou voie opposee, devant un secours proche ou juste depasse."""
    if not secours.occupe or secours.temps_intervention_restant > 0:
        return False
    x, y, angle = voiture.trajet.position_a(voiture.distance)
    debut = max(0.0, secours.distance - MARGE_DEPASSEMENT)
    fin = min(secours.trajet.longueur, secours.distance + DISTANCE_ANTICIPATION)
    distance = debut
    while distance <= fin:
        rx, ry, orientation = secours.trajet.position_a(distance)
        dx, dy = cos(radians(orientation)), sin(radians(orientation))
        distance_longitudinale = (x - rx) * dx + (y - ry) * dy
        ecart_lateral = abs((x - rx) * dy - (y - ry) * dx)
        distance_projetee = distance + distance_longitudinale
        if (abs(cos(radians(angle - orientation))) > .96
                and ecart_lateral < 76 and debut <= distance_projetee <= fin
                and (distance_projetee >= secours.distance or secours.identifiant in voiture.cede_aux)):
            return True
        distance += 10
    return False
