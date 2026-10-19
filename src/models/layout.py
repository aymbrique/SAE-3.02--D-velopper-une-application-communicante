"""Trajets fixes de la carte. Une unite de scene represente 0,5 metre."""

from src.models.route import Route, bezier

CX, CY = 550, 430
LANE, ROAD_HALF = 34, 70
SCENE_WIDTH, SCENE_HEIGHT = 1100, 860
METRES_PER_UNIT = 0.5
DESTINATIONS = {"N": "Nord", "S": "Sud", "E": "Est", "W": "Ouest"}
INTERVENTION_POINTS = {"N": (770, 130), "S": (770, 700),
                       "E": (820, 210), "W": (280, 650)}
OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}


def car_route(origin, turn):
    rotations = {"W": 0, "N": 1, "E": 2, "S": 3}
    points = [(-525, LANE), (-96, LANE), (-80, LANE)]
    if turn == "straight":
        points.extend([(80, LANE), (525, LANE)])
    else:
        end = (LANE, -80) if turn == "left" else (-LANE, 80)
        corner = (LANE, LANE) if turn == "left" else (-LANE, LANE)
        points.extend(bezier(points[-1], corner, corner, end))
        points.append((LANE, -405) if turn == "left" else (-LANE, 405))
    transformed = []
    for x, y in points:
        for _ in range(rotations[origin]):
            x, y = -y, x
        transformed.append((CX + x, CY + y))
    transformed[0] = {"W": (25, CY + LANE), "N": (CX - LANE, 25),
                      "E": (1075, CY - LANE), "S": (CX + LANE, 835)}[origin]
    end_x, end_y = transformed[-1]
    prev_x, prev_y = transformed[-2]
    # Prolonger le dernier segment jusqu'au bord de la carte.
    if abs(end_x - prev_x) > abs(end_y - prev_y):
        if end_x > prev_x:
            end_x = 1075
        else:
            end_x = 25
    else:
        if end_y > prev_y:
            end_y = 835
        else:
            end_y = 25
    transformed[-1] = (end_x, end_y)
    names = {"N": "Nord", "S": "Sud", "E": "Est", "W": "Ouest"}
    movements = {"straight": "tout droit", "left": "a gauche", "right": "a droite"}
    route = Route(f"{names[origin]} - {movements[turn]}", tuple(transformed))
    return route, route.distances[1]


def rescue_route(identifier, parking_y, destination="S"):
    """Aller au point choisi, attendre sur place, puis revenir a la caserne.

    accesses contient (debut de reservation, ligne d'attente, fin, cote).
    Les distances sont calculees apres avoir construit la liste des points.
    """
    if destination not in DESTINATIONS:
        raise ValueError("Point d'intervention inconnu")
    points = [(350, parking_y), (457, parking_y)]
    access_indexes = []
    crossing_indexes = []

    if destination == "N":
        # Le point Nord est du cote de la caserne : inutile de traverser le carrefour.
        points.extend([(584, parking_y), (584, 130), (770, 130)])
        hospital = len(points) - 1
        points.extend([(770, 70), (516, 70), (516, 160), (457, 160)])
        access_indexes.append((0, 1, len(points) - 1, "N"))
        points.extend([(280, 160), (280, parking_y), (350, parking_y)])
    else:
        points.extend(bezier(points[-1], (516, parking_y), (516, 315), (516, 326)))
        turn = {"S": "straight", "E": "left", "W": "right"}[destination]
        outward, stop = car_route("N", turn)
        outward_index = len(points)
        points.extend(outward.points[1:-1])
        crossing_indexes.append((outward_index, len(points) - 1, "NS"))
        access_indexes.append((0, 1, outward_index, "N"))

        # Meme aire d'intervention, tournee vers le Sud, l'Est ou l'Ouest.
        loop = [(516, 650)]
        loop.extend(bezier(loop[-1], (516, 700), (550, 700), (610, 700)))
        loop.append((770, 700))
        hospital = len(points) + len(loop) - 1
        loop.extend(bezier(loop[-1], (835, 700), (835, 760), (770, 760)))
        loop.append((620, 760))
        loop.extend(bezier(loop[-1], (584, 760), (584, 720), (584, 680)))
        loop_start = len(points)
        rotations = {"S": 0, "E": 3, "W": 1}
        for x, y in loop:
            x, y = x - CX, y - CY
            for rotation in range(rotations[destination]):
                x, y = -y, x
            points.append((CX + x, CY + y))
        access_indexes.append((loop_start, loop_start, len(points) - 1, destination))

        turn = {"S": "straight", "E": "right", "W": "left"}[destination]
        inward, stop = car_route(destination, turn)
        inward_index = len(points)
        points.extend(inward.points[1:-1])
        axis = "NS" if destination == "S" else "EW"
        crossing_indexes.append((inward_index, len(points) - 1, axis))
        return_guard = len(points)
        points.append((584, 270))
        points.extend(bezier(points[-1], (584, 190), (530, 190), (457, 190)))
        access_indexes.append((return_guard, return_guard, len(points) - 1, "N"))
        points.append((280, 190))
        points.extend(bezier(points[-1], (250, 190), (250, parking_y), (280, parking_y)))
        points.append((350, parking_y))

    route = Route(f"Secours {identifier} - {DESTINATIONS[destination]} - aller/retour", points)
    crossings = []
    for start, end, axis in crossing_indexes:
        crossings.append((route.distances[start], route.distances[end] + 26, axis))
    route.accesses = []
    for start, guard, end, side in access_indexes:
        # Reserver un peu avant d'arriver afin de laisser sortir les voitures presentes.
        reserve = max(0, route.distances[start] - 100)
        route.accesses.append((reserve, route.distances[guard], route.distances[end], side))
    return route, tuple(crossings), route.distances[hospital]


def car_exit(route):
    # Dernier point de la courbe centrale, puis marge de degagement de 26 unites.
    return route.distances[-2] + 26
