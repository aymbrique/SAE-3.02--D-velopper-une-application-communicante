"""Simulation a pas fixe. Les files tout droit compatibles peuvent passer ensemble."""

from math import hypot, inf, isfinite
from random import Random

from src.models.layout import DESTINATIONS, OPPOSITE, METRES_PER_UNIT, car_exit, car_route, rescue_route
from src.models.vehicle import Frame, Vehicle, VehicleState
from src.simulation.lights import Lights, Request

STEP = 0.05  # Duree d'un calcul de deplacement, en secondes simulees.
GAP = 44.0  # Distance minimale entre les centres des vehicules.
MAX_CARS = 25
DWELL = 8.0  # Temps passe sur le lieu de l'intervention.


class Simulation:
    def __init__(self, rate=12, seed=302):
        self.random = Random(seed)
        self.rate = rate
        self.time = 0.0
        self.accumulator = 0.0
        self.spawn_clock = 0.0
        self.completed = 0
        self.next_id = 1
        self.lights = Lights()
        self.crossing_owners = set()
        self.cars = []
        self.rescues = []
        self.events = []
        for identifier, kind, y, color in (("01", "fire", 245, "#db6758"),
                                            ("02", "ambulance", 305, "#f8faf9")):
            route, crossings, hospital = rescue_route(identifier, y)
            self.rescues.append(Vehicle(identifier, kind, route, crossings, color, 40,
                                        hospital=hospital, total_estimate=route.length / 40 + DWELL))

    @property
    def vehicles(self):
        return self.cars + self.rescues

    def get_rescue(self, identifier):
        for vehicle in self.rescues:
            if vehicle.identifier == identifier:
                return vehicle
        raise ValueError("Secours inconnu : " + identifier)

    def start_mission(self, identifier, destination="S"):
        vehicle = self.get_rescue(identifier)
        if vehicle.busy:
            return False
        parking_y = vehicle.route.points[0][1]
        route, crossings, hospital = rescue_route(identifier, parking_y, destination)
        vehicle.route = route
        vehicle.crossings = crossings
        vehicle.hospital = hospital
        vehicle.destination = destination
        vehicle.total_estimate = route.length / vehicle.speed + DWELL
        vehicle.waiting = False
        vehicle.busy = True
        vehicle.started_at = self.time
        vehicle.distance = 0.0
        vehicle.crossing_index = 0
        vehicle.requested_at = None
        vehicle.visited = False
        vehicle.dwell_remaining = 0.0
        self.events.append((identifier, "occupe"))
        return True

    def drain_events(self):
        events = self.events
        self.events = []
        return events

    def choose_turn(self):
        # 95 % tout droit ; les 5 % restants sont repartis entre les virages.
        choice = self.random.randrange(200)
        if choice < 190:
            return "straight"
        if choice < 195:
            return "left"
        return "right"

    def spawn(self, origin=None, turn=None):
        if len(self.cars) >= MAX_CARS:
            return None
        origin = origin or self.random.choice(("N", "S", "E", "W"))
        turn = turn or self.choose_turn()
        route, stop = car_route(origin, turn)
        x, y, _ = route.sample(0)
        for other in self.vehicles:
            other_x, other_y, angle = other.position
            if hypot(x - other_x, y - other_y) < GAP:
                return None
        axis = "NS" if origin in ("N", "S") else "EW"
        color = self.random.choice(("#5eb9cc", "#e9bc65", "#9a8ed4", "#78b89c", "#e7967f"))
        vehicle = Vehicle(f"C{self.next_id:04}", "car", route,
                          ((stop, car_exit(route), axis),), color, 28, origin=origin, turn=turn)
        self.next_id += 1
        self.cars.append(vehicle)
        return vehicle

    def approach(self, vehicle):
        if not vehicle.busy or vehicle.crossing is None:
            return None, None
        remaining = max(0.0, vehicle.crossing[0] - vehicle.distance)
        distance_metres = remaining * METRES_PER_UNIT
        eta = inf
        if vehicle.speed > 0:
            eta = remaining / vehicle.speed
        return distance_metres, eta

    def requests(self):
        result = []
        for vehicle in self.rescues:
            distance, eta = self.approach(vehicle)
            if distance is not None and (distance <= 150 or eta <= 10):
                # Ne pas bloquer l'autre axe au vert si la sortie est bouchee.
                # Un secours deja engage garde sa priorite jusqu'au degagement.
                if vehicle.identifier not in self.crossing_owners and not self._exit_clear(vehicle):
                    continue
                if vehicle.requested_at is None:
                    vehicle.requested_at = self.time
                result.append(Request(vehicle.identifier, vehicle.crossing[2],
                                      vehicle.started_at, vehicle.requested_at))
        return result

    def advance(self, duration):
        if not isfinite(duration) or duration < 0:
            raise ValueError("Duree invalide")
        self.accumulator += duration
        while self.accumulator >= STEP - 1e-9:
            self._step()
            self.accumulator -= STEP

    def _step(self):
        self.time += STEP
        rescue_busy = False
        for rescue in self.rescues:
            if rescue.busy:
                rescue_busy = True
        self.lights.advance(STEP, self.requests(), rescue_busy,
                            not self.crossing_owners)
        if self.rate > 0:
            self.spawn_clock += STEP
            if self.spawn_clock >= 60 / self.rate:
                self.spawn_clock %= 60 / self.rate
                self.spawn()
        # Degager le carrefour en premier, puis les vehicules en tete de file.
        ordered = sorted(self.vehicles, key=self._movement_order)
        for vehicle in ordered:
            self._move(vehicle)
        remaining_cars = []
        for car in self.cars:
            if car.distance >= car.route.length:
                self.completed += 1
            else:
                remaining_cars.append(car)
        self.cars = remaining_cars

    def _movement_order(self, vehicle):
        # Degager d'abord les sorties aussi : un leader deja sorti doit avancer
        # avant la voiture qui le suit encore dans le carrefour, sans micro-arret.
        clearing = (vehicle.identifier in self.crossing_owners
                    or (vehicle.kind == "car" and vehicle.crossing is None))
        return (not clearing, -vehicle.distance, vehicle.identifier)

    def _clear_path(self, vehicle, target, ignored=()):
        x, y, _ = vehicle.route.sample(target)
        for other in self.vehicles:
            if other is vehicle or other.identifier in ignored:
                continue
            ox, oy, _ = other.position
            if hypot(x - ox, y - oy) < GAP - 1e-7:
                return False
        return True

    def can_share_crossing(self, first, second):
        """Les files tout droit du meme axe peuvent avancer en parallele."""
        return (first.kind == "car" and second.kind == "car"
                and first.turn == "straight" and second.turn == "straight"
                and first.origin in OPPOSITE
                and second.origin in (first.origin, OPPOSITE[first.origin]))

    def _exit_clear(self, vehicle):
        # Avant l'aller, degager aussi la voie que le secours croisera pres de
        # son intervention. Sinon il pourrait attendre sur la sortie, retenir
        # tout un convoi dans le carrefour et empecher cette voie de passer au vert.
        if (vehicle.kind != "car" and vehicle.crossing_index == 0
                and self._side_access_occupied(vehicle.destination)):
            return False
        stop, end, axis = vehicle.crossing
        for offset in range(0, 46, 6):
            if not self._clear_path(vehicle, end + offset):
                return False
        return True

    def _can_enter(self, vehicle):
        stop, end, axis = vehicle.crossing
        for other in self.vehicles:
            if other.identifier in self.crossing_owners and other is not vehicle:
                if not self.can_share_crossing(vehicle, other):
                    return False
        if self.lights.signal(axis) != "green":
            return False
        if vehicle.kind != "car" and self.lights.owner and self.lights.owner.identifier != vehicle.identifier:
            return False
        if vehicle.kind != "car" and not self._exit_clear(vehicle):
            return False
        # Une voiture deja engagee et en mouvement ne bouche pas tout le trajet
        # des suivantes tout droit. Cela vaut aussi lorsqu'elle vient de sortir.
        # Les vehicules arretes, les virages et les secours restent des obstacles.
        following = set()
        for other in self.vehicles:
            if (other is not vehicle and self.can_share_crossing(vehicle, other)
                    and other.speed > 0 and not other.waiting
                    and other.distance > other.crossings[0][0]):
                following.add(other.identifier)
        # Ce controle global reserve toujours une sortie non bouchee. Le controle
        # de chaque deplacement dans _move ne saute aucun vehicule : GAP reste
        # obligatoire, meme avec plusieurs voitures engagees sur la meme voie.
        for offset in range(0, int(end - stop) + 46, 6):
            if not self._clear_path(vehicle, stop + offset, following):
                return False
        return True

    def _move(self, vehicle):
        if vehicle.kind != "car" and not vehicle.busy:
            return
        if vehicle.dwell_remaining > 0:
            vehicle.dwell_remaining = max(0.0, vehicle.dwell_remaining - STEP)
            vehicle.waiting = True
            return
        old = vehicle.distance
        target = min(old + vehicle.speed * STEP, vehicle.route.length)
        target = self._limit_at_side_access(vehicle, old, target)
        crossing = vehicle.crossing
        entering = crossing is not None and old <= crossing[0] and target > crossing[0]
        if entering and not self._can_enter(vehicle):
            target = crossing[0]
        if vehicle.hospital is not None and not vehicle.visited:
            target = min(target, vehicle.hospital)
        if target > old and self._clear_path(vehicle, target):
            vehicle.distance = target
            if entering and target > crossing[0]:
                self.crossing_owners.add(vehicle.identifier)
        vehicle.waiting = vehicle.distance <= old + 1e-9
        if crossing and vehicle.distance >= crossing[1]:
            self.crossing_owners.discard(vehicle.identifier)
            vehicle.crossing_index += 1
            vehicle.requested_at = None
        if vehicle.hospital is not None and not vehicle.visited and vehicle.distance >= vehicle.hospital:
            vehicle.visited = True
            vehicle.dwell_remaining = DWELL
        if vehicle.kind != "car" and vehicle.distance >= vehicle.route.length:
            vehicle.busy = False
            vehicle.distance = 0.0
            vehicle.waiting = False
            self.completed += 1
            self.events.append((vehicle.identifier, "disponible"))

    def _access_owner(self, side):
        """Un seul secours manoeuvre a la fois dans un acces lateral."""
        candidates = []
        for rescue in self.rescues:
            if not rescue.busy:
                continue
            for start, guard, end, access_side in rescue.route.accesses:
                preparing = (side == rescue.destination and bool(rescue.crossings)
                             and not rescue.visited and rescue.distance < start)
                if access_side == side and (preparing or start <= rescue.distance < end):
                    # Un secours deja engage finit avant celui qui attend.
                    engaged = rescue.distance > guard
                    candidates.append((not engaged, rescue.started_at, rescue.identifier))
        if candidates:
            return min(candidates)[2]
        return None

    def _limit_at_side_access(self, vehicle, old, target):
        if vehicle.kind == "car":
            # Retenir les nouvelles arrivees en amont de l'acces reserve.
            if self._access_owner(vehicle.origin) is not None:
                gate = 0 if vehicle.origin == "N" else 25
                if old <= gate:
                    target = min(target, gate)
        else:
            for start, guard, end, side in vehicle.route.accesses:
                if old <= guard < target:
                    owner = self._access_owner(side)
                    if owner != vehicle.identifier or self._side_access_occupied(side):
                        target = guard
        return target

    def _side_access_occupied(self, side):
        # Verifier seulement la voie entrante ; la voie sortante peut se degager.
        for car in self.cars:
            x, y, angle = car.position
            if side == "N" and 490 < x < 540 and 25.001 < y < 365:
                return True
            if side == "S" and 560 < x < 610 and 495 < y < 809.999:
                return True
            if side == "E" and 580 < x < 1049.999 and 370 < y < 420:
                return True
            if side == "W" and 50.001 < x < 520 and 440 < y < 490:
                return True
        return False

    def frame(self):
        states = []
        for vehicle in self.vehicles:
            x, y, heading = vehicle.position
            stage = "A l'arret" if vehicle.waiting else "En circulation"
            if vehicle.kind != "car":
                if not vehicle.busy:
                    stage = "A la caserne"
                elif vehicle.dwell_remaining > 0:
                    stage = "Intervention - " + DESTINATIONS[vehicle.destination]
                elif vehicle.visited:
                    stage = "Retour a la caserne"
                else:
                    stage = "Vers le point " + DESTINATIONS[vehicle.destination]
            states.append(VehicleState(vehicle.identifier, vehicle.kind, vehicle.color,
                                       vehicle.route, x, y, heading, vehicle.waiting,
                                       vehicle.busy, vehicle.distance / vehicle.route.length, stage))
        return Frame(tuple(states), self.lights.signal("NS"), self.lights.signal("EW"),
                     self.lights.description, self.lights.remaining, self.completed)
