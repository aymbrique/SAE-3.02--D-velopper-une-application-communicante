"""Plan commun au dessin et aux trajets : coordonnees du croquis utilisateur."""

from math import hypot
from src.modeles.trajet import Route, bezier

SCENE_WIDTH, SCENE_HEIGHT = 1600, 1100
CX, CY = 450, 560
LANE, ROAD_HALF = 34, 70
METRES_PER_UNIT = 0.5
STOP_DISTANCE = 96
TURN_DISTANCE = 80
CLEARANCE = 26
CAR_EDGE_MARGIN = 30  # Faire apparaitre/disparaitre le rectangle hors de la vue.
PARKING_X = 270
PARKING_Y = {"01": 150, "02": 210}
DESTINATIONS = {"W": "Mairie", "S": "Restaurant",
                "N": "IUT de Clermont", "E": "Leclerc"}
OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}

# Les noeuds sont les raccordements des routes. C est le seul carrefour a feux.
NODES = {
    "C": (CX, CY), "F": (CX, 200), "north": (CX, 0), "depot": (PARKING_X, 200),
    "W": (150, CY), "west": (0, CY), "B": (850, CY), "R": (1150, CY),
    "E": (1400, CY), "east": (SCENE_WIDTH, CY),
    "D": (CX, 950), "L": (150, 950), "Q": (1150, 950),
    "low_west": (0, 950), "low_east": (SCENE_WIDTH, 950),
    "U": (850, 240), "top": (850, 0), "H": (1400, 240), "upper_east": (SCENE_WIDTH, 240),
    "site_W": (150, 420), "site_S": (150, 810),
    "site_N": (1400, 110), "site_E": (1400, 420),
}
ROAD_SEGMENTS = [
    ("north", "F"), ("F", "C"), ("C", "D"),
    ("west", "W"), ("W", "C"), ("C", "B"), ("B", "R"), ("R", "E"), ("E", "east"),
    ("top", "U"), ("U", "B"), ("U", "H"), ("H", "upper_east"),
    ("R", "Q"), ("low_west", "L"), ("L", "D"), ("D", "Q"), ("Q", "low_east"),
]
SITE_ENTRANCES = {"W": "W", "S": "L", "N": "H", "E": "E"}
INTERVENTION_POINTS = {}
for side in DESTINATIONS:
    x, y = NODES["site_" + side]
    INTERVENTION_POINTS[side] = (x, y - 50)


def direction(start, end):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = hypot(dx, dy)
    return dx / length, dy / length


def lane_point(center, heading, forward):
    """Decaler un point sur la voie de droite et avancer de forward unites."""
    dx, dy = heading
    return (center[0] + forward * dx - LANE * dy,
            center[1] + forward * dy + LANE * dx)


def build_route(name, nodes, parking_y=None, traffic_bounds=None):
    """Relier les routes, arrondir les virages et noter les zones a reserver."""
    nodes = tuple(nodes)
    for first, second in zip(nodes, nodes[1:]):
        if (first, second) == ("Q", "R"):
            raise ValueError("Sens interdit : le raccordement R-Q se parcourt uniquement de R vers Q.")
    for movement in zip(nodes, nodes[1:], nodes[2:]):
        if movement == ("E", "R", "Q"):
            raise ValueError("Virage interdit : un vehicule venant de E ne peut pas tourner de R vers Q.")
    first = direction(NODES[nodes[0]], NODES[nodes[1]])
    points = [lane_point(NODES[nodes[0]], first, 0)]
    if traffic_bounds is not None:
        points.insert(0, outside_road(points[0], first, traffic_bounds, entering=True))
    if parking_y is not None:
        # Contourner les deux places pour ne pas passer sur le vehicule gare.
        points = [(PARKING_X, parking_y), (340, parking_y), (340, 234)]
    crossing_indexes = []
    junction_indexes = []
    junction_directions = []
    turn_indexes = []
    hospital_index = None
    depot_exit_index = None
    depot_return_index = None

    for index in range(1, len(nodes) - 1):
        key = nodes[index]
        center = NODES[key]
        incoming = direction(NODES[nodes[index - 1]], center)
        outgoing = direction(center, NODES[nodes[index + 1]])
        if key.startswith("site_"):
            # Demi-tour dans l'aire, avec arret sur le rectangle d'intervention.
            x, y = center
            start = len(points)
            points.extend([(x + LANE, y), (x + LANE, y - 50), (x, y - 50),
                           (x - LANE, y - 50), (x - LANE, y)])
            hospital_index = start + 2
            junction_indexes.append((start, len(points) - 1, 0, key))
            continue

        start = len(points)
        points.append(lane_point(center, incoming, -STOP_DISTANCE))
        points.append(lane_point(center, incoming, -TURN_DISTANCE))
        end = lane_point(center, outgoing, TURN_DISTANCE)
        if incoming == outgoing:
            points.append(end)
        else:
            turn_start = len(points) - 1
            control1 = (points[-1][0] + incoming[0] * 64,
                        points[-1][1] + incoming[1] * 64)
            control2 = (end[0] - outgoing[0] * 64, end[1] - outgoing[1] * 64)
            points.extend(bezier(points[-1], control1, control2, end))
            turn_indexes.append((turn_start, len(points) - 1))
        if key == "C":
            axis = "NS" if incoming[0] == 0 else "EW"
            crossing_indexes.append((start, len(points) - 1, axis))
        else:
            junction_indexes.append((start, len(points) - 1, CLEARANCE, key))
            junction_directions.append((start, key, incoming, outgoing))
        if parking_y is not None and key == "F":
            if depot_exit_index is None:
                depot_exit_index = len(points) - 1
            else:
                depot_return_index = start

    last = direction(NODES[nodes[-2]], NODES[nodes[-1]])
    if parking_y is None:
        points.append(lane_point(NODES[nodes[-1]], last, 0))
        if traffic_bounds is not None:
            points.append(outside_road(points[-1], last, traffic_bounds))
    else:
        points.extend([(340, 166), (340, parking_y), (PARKING_X, parking_y)])
        junction_indexes.append((0, depot_exit_index, CLEARANCE, "parking"))
        junction_indexes.append((depot_return_index, len(points) - 1, 0, "parking"))

    route = Route(name, points)
    route.nodes = tuple(nodes)
    route.turn_zones = [(route.distances[start], route.distances[end])
                        for start, end in turn_indexes]
    route.crossings = []
    for start, end, axis in crossing_indexes:
        route.crossings.append((route.distances[start], route.distances[end] + CLEARANCE, axis))
    route.junctions = []
    for start, end, margin, key in junction_indexes:
        route.junctions.append((route.distances[start], route.distances[end] + margin, key))
    route.junction_movements = {}
    for start, key, incoming, outgoing in junction_directions:
        route.junction_movements[(route.distances[start], key)] = (incoming, outgoing)
    route.hospital = None
    if hospital_index is not None:
        route.hospital = route.distances[hospital_index]
    return route


def outside_road(point, heading, bounds, entering=False):
    """Prolonger la voie jusqu'a l'exterieur du plan ET des marges visibles."""
    left, top, right, bottom = bounds
    x, y = point
    dx, dy = heading
    if entering:
        dx, dy = -dx, -dy
    if dx < 0:
        x = min(0, left) - CAR_EDGE_MARGIN
    elif dx > 0:
        x = max(SCENE_WIDTH, right) + CAR_EDGE_MARGIN
    elif dy < 0:
        y = min(0, top) - CAR_EDGE_MARGIN
    else:
        y = max(SCENE_HEIGHT, bottom) + CAR_EDGE_MARGIN
    return x, y


def car_route(origin, turn, traffic_bounds=(0, 0, SCENE_WIDTH, SCENE_HEIGHT), *, variant=None):
    """Choisir le virage a C et, en option, une bifurcation plus loin sur le plan."""
    approaches = {
        "N": ["north", "F", "C"], "W": ["west", "W", "C"],
        "E": ["upper_east", "H", "U", "B", "C"],
        "S": ["low_east", "Q", "D", "C"],
    }
    exits = {
        "N": ["C", "F", "north"], "W": ["C", "W", "west"],
        "E": ["C", "B", "R", "E", "east"],
        "S": ["C", "D", "Q", "low_east"],
    }
    destinations = {
        "N": {"straight": "S", "left": "E", "right": "W"},
        "S": {"straight": "N", "left": "W", "right": "E"},
        "W": {"straight": "E", "left": "N", "right": "S"},
        "E": {"straight": "W", "left": "S", "right": "N"},
    }
    names = {"N": "Nord", "S": "Sud", "E": "Est", "W": "Ouest"}
    movements = {"straight": "tout droit", "left": "a gauche", "right": "a droite"}
    destination = destinations[origin][turn]
    exit_nodes = exits[destination]
    suffix = ""
    if variant == "lower_west":
        if destination != "S":
            raise ValueError("La bifurcation Ouest de D exige une sortie Sud au carrefour C.")
        exit_nodes = ["C", "D", "L", "low_west"]
        suffix = " - Ouest par la route du bas"
    elif variant == "middle_north":
        if destination != "E":
            raise ValueError("La bifurcation Nord de B exige une sortie Est au carrefour C.")
        exit_nodes = ["C", "B", "U", "top"]
        suffix = " - Nord par la route du milieu"
    elif variant is not None:
        raise ValueError("Bifurcation de voiture inconnue")
    nodes = approaches[origin] + exit_nodes[1:]
    route = build_route(f"{names[origin]} - {movements[turn]}{suffix}", nodes, traffic_bounds=traffic_bounds)
    route.variant = variant
    return route, route.crossings[0][0]


def rescue_route(identifier, parking_y, destination="S"):
    if destination not in DESTINATIONS:
        raise ValueError("Point d'intervention inconnu")
    paths = {
        "W": ["depot", "F", "C", "W", "site_W"],
        "S": ["depot", "F", "C", "D", "L", "site_S"],
        "N": ["depot", "F", "C", "B", "U", "H", "site_N"],
        "E": ["depot", "F", "C", "B", "R", "E", "site_E"],
    }
    outward = paths[destination]
    nodes = outward + list(reversed(outward[:-1]))
    route = build_route(f"Secours {identifier} - {DESTINATIONS[destination]} - aller/retour", nodes, parking_y)
    return route, tuple(route.crossings), route.hospital


def car_exit(route):
    return route.crossings[0][1]


def on_road(x, y):
    """Chaussée dessinee, y compris les extremites ouvertes et la voie R-Q."""
    for first, second in ROAD_SEGMENTS:
        ax, ay = NODES[first]
        bx, by = NODES[second]
        if ax == bx:
            top, bottom = sorted((ay, by))
            if top == 0:
                top = float('-inf')
            left, right = ax - ROAD_HALF, ax + ROAD_HALF
            if (first, second) == ("R", "Q"):
                right = ax
            if left <= x <= right and top <= y <= bottom:
                return True
        else:
            left, right = sorted((ax, bx))
            if left == 0:
                left = float('-inf')
            if right == SCENE_WIDTH:
                right = float('inf')
            if left <= x <= right and ay - ROAD_HALF <= y <= ay + ROAD_HALF:
                return True
    return any(abs(x - NODES[key][0]) <= ROAD_HALF
               and abs(y - NODES[key][1]) <= ROAD_HALF
               for key in ("C", "F", "W", "B", "R", "E", "D", "L", "Q", "U", "H"))
