"""Trajets fixes de la carte. Une unite de scene represente 0,5 metre."""

from src.models.route import Route, bezier

CX, CY = 550, 430
LANE, ROAD_HALF = 34, 70
SCENE_WIDTH, SCENE_HEIGHT = 1100, 860
METRES_PER_UNIT = 0.5


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
    transformed[-1] = ((1075 if end_x > prev_x else 25, end_y)
                       if abs(end_x - prev_x) > abs(end_y - prev_y)
                       else (end_x, 835 if end_y > prev_y else 25))
    names = {"N": "Nord", "S": "Sud", "E": "Est", "W": "Ouest"}
    movements = {"straight": "tout droit", "left": "a gauche", "right": "a droite"}
    route = Route(f"{names[origin]} - {movements[turn]}", tuple(transformed))
    return route, route.distances[1]


def rescue_route(identifier, parking_y):
    points = [(350, parking_y), (457, parking_y)]
    points.extend(bezier(points[-1], (516, parking_y), (516, 315), (516, 326)))
    points.append((516, 334))
    outward = len(points) - 1
    points.append((516, 650))
    points.extend(bezier(points[-1], (516, 700), (550, 700), (610, 700)))
    points.append((770, 700))
    hospital = len(points) - 1
    points.extend(bezier(points[-1], (835, 700), (835, 760), (770, 760)))
    points.append((620, 760))
    points.extend(bezier(points[-1], (584, 760), (584, 720), (584, 680)))
    points.append((584, 526))
    inward = len(points) - 1
    points.append((584, 270))
    points.extend(bezier(points[-1], (584, 190), (530, 190), (457, 190)))
    points.append((280, 190))
    points.extend(bezier(points[-1], (250, 190), (250, parking_y), (280, parking_y)))
    points.append((350, parking_y))
    route = Route(f"Secours {identifier} - caserne et retour", tuple(points))
    # La sortie est au-dela du carrefour : l'arriere du vehicule doit etre degage.
    crossings = ((route.distances[outward], route.distances[outward] + 202, "NS"),
                 (route.distances[inward], route.distances[inward] + 202, "NS"))
    return route, crossings, route.distances[hospital]


def car_exit(route):
    # Dernier point de la courbe centrale, puis marge de degagement de 26 unites.
    return route.distances[-2] + 26
