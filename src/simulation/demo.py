"""Lecture de trajets prédéfinis : aucune génération ni décision de circulation.

Les attentes et les départs sont inscrits dans une chronologie fixe. Les futurs
algorithmes de circulation, de priorité et de réseau remplaceront ce scénario.
"""

from bisect import bisect_right
from dataclasses import dataclass

from src.models.route import Route, bezier


CX, CY = 550, 430
LANE, ROAD_HALF = 34, 70
SCENE_WIDTH, SCENE_HEIGHT = 1100, 860


@dataclass(frozen=True)
class VehicleState:
    identifier: str
    kind: str
    color: str
    route: Route
    x: float
    y: float
    heading: float
    waiting: bool
    busy: bool
    progress: float
    stage: str


@dataclass(frozen=True)
class Track:
    identifier: str
    kind: str
    color: str
    route: Route
    cues: tuple[tuple[float, float], ...]
    offset: float
    period: float
    stages: tuple[tuple[float, str], ...] = ()

    @property
    def duration(self):
        return self.cues[-1][0]

    def state_at(self, elapsed):
        local = (elapsed - self.offset) % self.period if elapsed >= self.offset else None
        active = local is not None and local < self.duration
        if not active:
            if self.kind == "car":
                return None
            x, y, heading = self.route.sample(0)
            return VehicleState(self.identifier, self.kind, self.color, self.route,
                                x, y, heading, False, False, 0, "À la caserne")

        index = min(bisect_right([cue[0] for cue in self.cues], local) - 1,
                    len(self.cues) - 2)
        t0, d0 = self.cues[index]
        t1, d1 = self.cues[index + 1]
        distance = d0 + (d1 - d0) * (local - t0) / (t1 - t0)
        x, y, heading = self.route.sample(distance)
        stage = "En circulation"
        for until, description in self.stages:
            if local < until:
                stage = description
                break
        return VehicleState(self.identifier, self.kind, self.color, self.route,
                            x, y, heading, d0 == d1, self.kind != "car",
                            local / self.duration, stage)

    def completions_at(self, elapsed):
        first_completion = self.offset + self.duration
        if elapsed < first_completion:
            return 0
        return 1 + int((elapsed - first_completion) // self.period)


@dataclass(frozen=True)
class Frame:
    vehicles: tuple[VehicleState, ...]
    north_south: str
    east_west: str
    phase_name: str
    phase_remaining: float
    completed: int

    @property
    def cars(self):
        return tuple(vehicle for vehicle in self.vehicles if vehicle.kind == "car")

    @property
    def rescues(self):
        return tuple(vehicle for vehicle in self.vehicles if vehicle.kind != "car")


def car_route(origin, turn):
    """Construire un trajet en circulation à droite, puis le tourner de 90°."""
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
    # La scène est rectangulaire : garder les entrées et sorties à ses bords.
    transformed[0] = {"W": (25, CY + LANE), "N": (CX - LANE, 25),
                      "E": (1075, CY - LANE), "S": (CX + LANE, 835)}[origin]
    end_x, end_y = transformed[-1]
    prev_x, prev_y = transformed[-2]
    if abs(end_x - prev_x) > abs(end_y - prev_y):
        transformed[-1] = (1075 if end_x > prev_x else 25, end_y)
    else:
        transformed[-1] = (end_x, 835 if end_y > prev_y else 25)
    names = {"N": "Nord", "S": "Sud", "E": "Est", "W": "Ouest"}
    movements = {"straight": "tout droit", "left": "à gauche", "right": "à droite"}
    route = Route(f"{names[origin]} · {movements[turn]}", tuple(transformed))
    return route, route.distances[1]


def rescue_track(identifier, kind, parking_y, offset, release,
                 hospital_at, return_at, return_stop_at, return_release, finish):
    points = [(350, parking_y), (457, parking_y)]
    points.extend(bezier(points[-1], (516, parking_y), (516, 315), (516, 326)))
    points.append((516, 334))
    stop_index = len(points) - 1
    points.append((516, 650))
    points.extend(bezier(points[-1], (516, 700), (550, 700), (610, 700)))
    points.append((770, 700))
    hospital_index = len(points) - 1
    points.extend(bezier(points[-1], (820, 700), (820, 736), (770, 736)))
    points.append((620, 736))
    points.extend(bezier(points[-1], (584, 736), (584, 720), (584, 680)))
    points.append((584, 526))
    return_stop_index = len(points) - 1
    points.append((584, 270))
    points.extend(bezier(points[-1], (584, 210), (530, 210), (457, 210)))
    points.append((320, 210))
    points.extend(bezier(points[-1], (280, 210), (280, parking_y), (320, parking_y)))
    points.append((350, parking_y))
    route = Route(f"Secours {identifier} · caserne et retour", tuple(points))
    approach = 4.0 if offset == 0 else 3.0
    cues = ((0, 0), (approach, route.distances[stop_index]),
            (release, route.distances[stop_index]),
            (hospital_at, route.distances[hospital_index]),
            (return_at, route.distances[hospital_index]),
            (return_stop_at, route.distances[return_stop_index]),
            (return_release, route.distances[return_stop_index]), (finish, route.length))
    stages = ((approach, "Départ de la caserne"), (release, "Approche du carrefour"),
              (hospital_at, "Vers l’intervention"), (return_at, "Sur intervention"),
              (finish, "Retour à la caserne"))
    return Track(identifier, kind, "#db6758" if kind == "fire" else "#f8faf9",
                 route, cues, offset, 80, stages)


class DemoScenario:
    """Scénario répétable avec huit trajets de voitures et deux secours."""

    def __init__(self):
        definitions = (
            ("N", "straight", 0, 3.5, "#5eb9cc"),
            ("S", "straight", 0.8, 4.6, "#e9bc65"),
            ("W", "left", 4, 10.4, "#9a8ed4"),
            ("E", "right", 6, 14.0, "#78b89c"),
            ("N", "right", 14, 20.3, "#e7967f"),
            ("S", "left", 21, 24.5, "#6c9ecf"),
            ("W", "right", 24, 30.3, "#c9a2ce"),
            ("E", "left", 26, 34.0, "#d0d9dd"),
        )
        tracks = []
        for index, (origin, turn, offset, release, color) in enumerate(definitions, 1):
            route, stop = car_route(origin, turn)
            depart = release - offset
            finish = depart + (route.length - stop) / 120
            tracks.append(Track(f"C{index:02d}", "car", color, route,
                                ((0, 0), (3, stop), (depart, stop),
                                 (finish, route.length)), offset, 40))
        tracks.extend([
            rescue_track("01", "fire", 245, 1, 5.0, 10.5, 17.4, 19.8, 21.3, 25.7),
            rescue_track("02", "ambulance", 305, 21.4, 4.6, 10.1, 17.0, 19.6, 20.9, 25.3),
        ])
        self.tracks = tuple(tracks)

    def frame_at(self, elapsed):
        if elapsed < 0:
            raise ValueError("Le temps simulé doit être positif ou nul.")
        phase_time = elapsed % 20
        phases = ((8, "green", "red", "Nord–Sud ouvert"),
                  (9, "amber", "red", "Nord–Sud : orange"),
                  (10, "red", "red", "Transition : tout rouge"),
                  (18, "red", "green", "Est–Ouest ouvert"),
                  (19, "red", "amber", "Est–Ouest : orange"),
                  (20, "red", "red", "Transition : tout rouge"))
        until, ns, ew, name = next(phase for phase in phases if phase_time < phase[0])
        states = tuple(state for track in self.tracks
                       if (state := track.state_at(elapsed)) is not None)
        return Frame(states, ns, ew, name, until - phase_time,
                     sum(track.completions_at(elapsed) for track in self.tracks))
