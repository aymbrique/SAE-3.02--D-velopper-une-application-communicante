"""Plan de la ville et coordonnées utilisées pour le dessin et les trajets."""

from math import hypot
from src.modeles.trajet import Trajet, virage_arrondi

LARGEUR_SCENE, HAUTEUR_SCENE = 1600, 1100
CX, CY = 450, 560
DECALAGE_VOIE, DEMI_LARGEUR_ROUTE = 34, 70
METRES_PAR_UNITE = 0.5
DISTANCE_ARRET = 96
DISTANCE_VIRAGE = 80
MARGE_DEGAGEMENT = 26
MARGE_BORD_VOITURE = 30  # Faire apparaitre/disparaitre le rectangle hors de la vue.
PARKING_X = 270
PARKING_Y = {"01": 150, "02": 210}
DESTINATIONS = {"O": "Mairie", "S": "Restaurant",
                "N": "IUT de Colmar", "E": "Leclerc"}
DIRECTIONS_OPPOSEES = {"N": "S", "S": "N", "E": "O", "O": "E"}

# Les noeuds sont les raccordements des routes. C est le seul carrefour a feux.
NOEUDS = {
    "C": (CX, CY), "F": (CX, 200), "nord": (CX, 0), "depot": (PARKING_X, 200),
    "O": (150, CY), "ouest": (0, CY), "B": (850, CY), "R": (1150, CY),
    "E": (1400, CY), "est": (LARGEUR_SCENE, CY),
    "D": (CX, 950), "L": (150, 950), "Q": (1150, 950),
    "bas_ouest": (0, 950), "bas_est": (LARGEUR_SCENE, 950),
    "U": (850, 240), "haut": (850, 0), "H": (1400, 240), "haut_est": (LARGEUR_SCENE, 240),
    "site_O": (150, 420), "site_S": (150, 810),
    "site_N": (1400, 110), "site_E": (1400, 420),
}
TRONCONS_ROUTES = [
    ("nord", "F"), ("F", "C"), ("C", "D"),
    ("ouest", "O"), ("O", "C"), ("C", "B"), ("B", "R"), ("R", "E"), ("E", "est"),
    ("haut", "U"), ("U", "B"), ("U", "H"), ("H", "haut_est"),
    ("R", "Q"), ("bas_ouest", "L"), ("L", "D"), ("D", "Q"), ("Q", "bas_est"),
]
ENTREES_SITES = {"O": "O", "S": "L", "N": "H", "E": "E"}
POINTS_INTERVENTION = {}
for cote in DESTINATIONS:
    x, y = NOEUDS["site_" + cote]
    POINTS_INTERVENTION[cote] = (x, y - 50)


def direction(debut, fin):
    """Renvoie le vecteur de longueur 1 allant du point début au point fin."""
    dx, dy = fin[0] - debut[0], fin[1] - debut[1]
    longueur = hypot(dx, dy)
    return dx / longueur, dy / longueur


def point_sur_voie(centre, orientation, avance):
    """Place un point sur la voie de droite, à la distance avance du centre."""
    dx, dy = orientation
    return (centre[0] + avance * dx - DECALAGE_VOIE * dy,
            centre[1] + avance * dy + DECALAGE_VOIE * dx)


def construire_trajet(nom, noeuds, parking_y=None, limites_circulation=None):
    """Construit un trajet à partir des nœuds du plan.

    Paramètres :
        nom: Nom du trajet.
        noeuds: Noms des points du plan à relier dans l'ordre.
        parking_y: Ordonnée de la place à la caserne, ou None pour une voiture.
        limites_circulation: Limites visibles à dépasser aux entrées et sorties.

    Résultat :
        Un Trajet avec ses virages, ses passages et ses raccordements.

    Exceptions :
        ValueError: Si le parcours emprunte un sens ou un virage interdit.
    """
    noeuds = tuple(noeuds)
    for premier, second in zip(noeuds, noeuds[1:]):
        if (premier, second) == ("Q", "R"):
            raise ValueError("Sens interdit : le raccordement R-Q se parcourt uniquement de R vers Q.")
    for mouvement in zip(noeuds, noeuds[1:], noeuds[2:]):
        if mouvement == ("E", "R", "Q"):
            raise ValueError("Virage interdit : un vehicule venant de E ne peut pas tourner de R vers Q.")
    premier = direction(NOEUDS[noeuds[0]], NOEUDS[noeuds[1]])
    points = [point_sur_voie(NOEUDS[noeuds[0]], premier, 0)]
    if limites_circulation is not None:
        points.insert(0, point_hors_carte(points[0], premier, limites_circulation, entre=True))
    if parking_y is not None:
        # Contourner les deux places pour ne pas passer sur le vehicule gare.
        points = [(PARKING_X, parking_y), (340, parking_y), (340, 234)]
    indices_passages = []
    indices_raccordements = []
    directions_raccordements = []
    indices_virages = []
    indice_intervention = None
    indice_sortie_caserne = None
    indice_retour_caserne = None

    for index in range(1, len(noeuds) - 1):
        cle = noeuds[index]
        centre = NOEUDS[cle]
        entree_direction = direction(NOEUDS[noeuds[index - 1]], centre)
        sortie_direction = direction(centre, NOEUDS[noeuds[index + 1]])
        if cle.startswith("site_"):
            # Demi-tour dans l'aire, avec arret sur le rectangle d'intervention.
            x, y = centre
            debut = len(points)
            points.extend([(x + DECALAGE_VOIE, y), (x + DECALAGE_VOIE, y - 50), (x, y - 50),
                           (x - DECALAGE_VOIE, y - 50), (x - DECALAGE_VOIE, y)])
            indice_intervention = debut + 2
            indices_raccordements.append((debut, len(points) - 1, 0, cle))
            continue

        debut = len(points)
        points.append(point_sur_voie(centre, entree_direction, -DISTANCE_ARRET))
        points.append(point_sur_voie(centre, entree_direction, -DISTANCE_VIRAGE))
        fin = point_sur_voie(centre, sortie_direction, DISTANCE_VIRAGE)
        if entree_direction == sortie_direction:
            points.append(fin)
        else:
            debut_virage = len(points) - 1
            controle1 = (points[-1][0] + entree_direction[0] * 64,
                        points[-1][1] + entree_direction[1] * 64)
            controle2 = (fin[0] - sortie_direction[0] * 64, fin[1] - sortie_direction[1] * 64)
            points.extend(virage_arrondi(points[-1], controle1, controle2, fin))
            indices_virages.append((debut_virage, len(points) - 1))
        if cle == "C":
            axe = "NS" if entree_direction[0] == 0 else "EO"
            indices_passages.append((debut, len(points) - 1, axe))
        else:
            indices_raccordements.append((debut, len(points) - 1, MARGE_DEGAGEMENT, cle))
            directions_raccordements.append((debut, cle, entree_direction, sortie_direction))
        if parking_y is not None and cle == "F":
            if indice_sortie_caserne is None:
                indice_sortie_caserne = len(points) - 1
            else:
                indice_retour_caserne = debut

    dernier = direction(NOEUDS[noeuds[-2]], NOEUDS[noeuds[-1]])
    if parking_y is None:
        points.append(point_sur_voie(NOEUDS[noeuds[-1]], dernier, 0))
        if limites_circulation is not None:
            points.append(point_hors_carte(points[-1], dernier, limites_circulation))
    else:
        points.extend([(340, 166), (340, parking_y), (PARKING_X, parking_y)])
        indices_raccordements.append((0, indice_sortie_caserne, MARGE_DEGAGEMENT, "stationnement"))
        indices_raccordements.append((indice_retour_caserne, len(points) - 1, 0, "stationnement"))

    # Convertir les indices des points en distances utilisables par la simulation.
    trajet = Trajet(nom, points)
    trajet.noeuds = tuple(noeuds)
    trajet.zones_virage = [(trajet.distances[debut], trajet.distances[fin])
                        for debut, fin in indices_virages]
    trajet.passages = []
    for debut, fin, axe in indices_passages:
        trajet.passages.append((trajet.distances[debut], trajet.distances[fin] + MARGE_DEGAGEMENT, axe))
    trajet.raccordements = []
    for debut, fin, marge, cle in indices_raccordements:
        trajet.raccordements.append((trajet.distances[debut], trajet.distances[fin] + marge, cle))
    trajet.mouvements_raccordements = {}
    for debut, cle, entree_direction, sortie_direction in directions_raccordements:
        trajet.mouvements_raccordements[(trajet.distances[debut], cle)] = (entree_direction, sortie_direction)
    trajet.arret_intervention = None
    if indice_intervention is not None:
        trajet.arret_intervention = trajet.distances[indice_intervention]
    return trajet


def point_hors_carte(point, orientation, limites, entre=False):
    """Renvoie un point au-delà du bord visible pour une entrée ou une sortie."""
    gauche, haut, droite, bas = limites
    x, y = point
    dx, dy = orientation
    if entre:
        dx, dy = -dx, -dy
    if dx < 0:
        x = min(0, gauche) - MARGE_BORD_VOITURE
    elif dx > 0:
        x = max(LARGEUR_SCENE, droite) + MARGE_BORD_VOITURE
    elif dy < 0:
        y = min(0, haut) - MARGE_BORD_VOITURE
    else:
        y = max(HAUTEUR_SCENE, bas) + MARGE_BORD_VOITURE
    return x, y


def trajet_voiture(origine, virage, limites_circulation=(0, 0, LARGEUR_SCENE, HAUTEUR_SCENE), *, variante=None):
    """Prépare le parcours d'une voiture selon son origine et son virage.

    Paramètres :
        origine: Côté d'arrivée, parmi N, S, E et O.
        virage: Mouvement au feu : tout_droit, gauche ou droite.
        limites_circulation: Limites visibles utilisées pour les extrémités du trajet.
        variante: Bifurcation après le feu, ou None pour le parcours habituel.

    Résultat :
        Le trajet et la distance de sa ligne d'arrêt au carrefour principal.
    """
    approches = {
        "N": ["nord", "F", "C"], "O": ["ouest", "O", "C"],
        "E": ["haut_est", "H", "U", "B", "C"],
        "S": ["bas_est", "Q", "D", "C"],
    }
    sorties = {
        "N": ["C", "F", "nord"], "O": ["C", "O", "ouest"],
        "E": ["C", "B", "R", "E", "est"],
        "S": ["C", "D", "Q", "bas_est"],
    }
    destinations = {
        "N": {"tout_droit": "S", "gauche": "E", "droite": "O"},
        "S": {"tout_droit": "N", "gauche": "O", "droite": "E"},
        "O": {"tout_droit": "E", "gauche": "N", "droite": "S"},
        "E": {"tout_droit": "O", "gauche": "S", "droite": "N"},
    }
    noms = {"N": "Nord", "S": "Sud", "E": "Est", "O": "Ouest"}
    mouvements = {"tout_droit": "tout droit", "gauche": "a gauche", "droite": "a droite"}
    destination = destinations[origine][virage]
    noeuds_sortie = sorties[destination]
    suffixe = ""
    if variante == "bifurcation_ouest_bas":
        if destination != "S":
            raise ValueError("La bifurcation Ouest de D exige une sortie Sud au carrefour C.")
        noeuds_sortie = ["C", "D", "L", "bas_ouest"]
        suffixe = " - Ouest par la route du bas"
    elif variante == "bifurcation_nord_milieu":
        if destination != "E":
            raise ValueError("La bifurcation Nord de B exige une sortie Est au carrefour C.")
        noeuds_sortie = ["C", "B", "U", "haut"]
        suffixe = " - Nord par la route du milieu"
    elif variante is not None:
        raise ValueError("Bifurcation de voiture inconnue")
    noeuds = approches[origine] + noeuds_sortie[1:]
    trajet = construire_trajet(f"{noms[origine]} - {mouvements[virage]}{suffixe}", noeuds, limites_circulation=limites_circulation)
    trajet.variante = variante
    return trajet, trajet.passages[0][0]


def trajet_secours(identifiant, parking_y, destination="S"):
    """Construit l'aller-retour d'un secours entre la caserne et sa destination.

    Paramètres :
        identifiant: Identifiant du secours.
        parking_y: Ordonnée de sa place à la caserne.
        destination: Point d'intervention, parmi N, S, E et O.

    Résultat :
        Le trajet, les passages au carrefour et la distance de l'arrêt sur place.
    """
    if destination not in DESTINATIONS:
        raise ValueError("Point d'intervention inconnu")
    chemins = {
        "O": ["depot", "F", "C", "O", "site_O"],
        "S": ["depot", "F", "C", "D", "L", "site_S"],
        "N": ["depot", "F", "C", "B", "U", "H", "site_N"],
        "E": ["depot", "F", "C", "B", "R", "E", "site_E"],
    }
    aller = chemins[destination]
    noeuds = aller + list(reversed(aller[:-1]))
    trajet = construire_trajet(f"Secours {identifiant} - {DESTINATIONS[destination]} - aller/retour", noeuds, parking_y)
    return trajet, tuple(trajet.passages), trajet.arret_intervention


def sortie_voiture(trajet):
    """Renvoie la distance de sortie du carrefour principal sur ce trajet."""
    return trajet.passages[0][1]


def sur_chaussee(x, y):
    """Indique si le point x, y se trouve sur la chaussée du plan."""
    for premier, second in TRONCONS_ROUTES:
        ax, ay = NOEUDS[premier]
        bx, by = NOEUDS[second]
        if ax == bx:
            haut, bas = sorted((ay, by))
            if haut == 0:
                haut = float('-inf')
            gauche, droite = ax - DEMI_LARGEUR_ROUTE, ax + DEMI_LARGEUR_ROUTE
            if (premier, second) == ("R", "Q"):
                droite = ax
            if gauche <= x <= droite and haut <= y <= bas:
                return True
        else:
            gauche, droite = sorted((ax, bx))
            if gauche == 0:
                gauche = float('-inf')
            if droite == LARGEUR_SCENE:
                droite = float('inf')
            if gauche <= x <= droite and ay - DEMI_LARGEUR_ROUTE <= y <= ay + DEMI_LARGEUR_ROUTE:
                return True
    return any(abs(x - NOEUDS[cle][0]) <= DEMI_LARGEUR_ROUTE
               and abs(y - NOEUDS[cle][1]) <= DEMI_LARGEUR_ROUTE
               for cle in ("C", "F", "O", "B", "R", "E", "D", "L", "Q", "U", "H"))
