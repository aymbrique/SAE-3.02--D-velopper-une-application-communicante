"""Simulation a pas fixe. Un seul passage est reserve dans le carrefour."""

from math import hypot, inf, isfinite
from random import Random

from src.models.layout import METRES_PER_UNIT, car_exit, car_route, rescue_route
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
        self.crossing_owner = None
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

    def start_mission(self, identifier):
        vehicle = self.get_rescue(identifier)
        if vehicle.busy:
            return False
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

    def spawn(self, origin=None, turn=None):
        if len(self.cars) >= MAX_CARS:
            return None
        origin = origin or self.random.choice(("N", "S", "E", "W"))
        turn = turn or self.random.choice(("straight", "left", "right"))
        route, stop = car_route(origin, turn)
        x, y, _ = route.sample(0)
        for other in self.vehicles:
            other_x, other_y, angle = other.position
            if hypot(x - other_x, y - other_y) < GAP:
                return None
        axis = "NS" if origin in ("N", "S") else "EW"
        color = self.random.choice(("#5eb9cc", "#e9bc65", "#9a8ed4", "#78b89c", "#e7967f"))
        vehicle = Vehicle(f"C{self.next_id:04}", "car", route,
                          ((stop, car_exit(route), axis),), color, 28)
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
                            self.crossing_owner is None)
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
        # Le vehicule engage passe d'abord, puis celui qui a le plus avance.
        engaged = vehicle.identifier == self.crossing_owner
        return (not engaged, -vehicle.distance, vehicle.identifier)

    def _clear_path(self, vehicle, target):
        x, y, _ = vehicle.route.sample(target)
        for other in self.vehicles:
            if other is vehicle:
                continue
            ox, oy, _ = other.position
            if hypot(x - ox, y - oy) < GAP - 1e-7:
                return False
        return True

    def _can_enter(self, vehicle):
        stop, end, axis = vehicle.crossing
        if self.crossing_owner not in (None, vehicle.identifier):
            return False
        if self.lights.signal(axis) != "green":
            return False
        if vehicle.kind != "car" and self.lights.owner and self.lights.owner.identifier != vehicle.identifier:
            return False
        # Ne pas engager un vehicule si sa sortie est bouchee.
        for offset in range(0, int(end - stop) + 46, 6):
            if not self._clear_path(vehicle, stop + offset):
                return False
        return True

    def _move(self, vehicle):
        if vehicle.kind != "car" and not vehicle.busy:
            return
        if vehicle.kind != "car" and vehicle.distance == 0:
            for other in self.rescues:
                if (other is not vehicle and other.busy
                        and (other.started_at, other.identifier) < (vehicle.started_at, vehicle.identifier)
                        and other.distance < other.crossings[0][0] + GAP):
                    vehicle.waiting = True
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
                self.crossing_owner = vehicle.identifier
        vehicle.waiting = vehicle.distance <= old + 1e-9
        if crossing and vehicle.distance >= crossing[1]:
            if self.crossing_owner == vehicle.identifier:
                self.crossing_owner = None
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

    def _limit_at_side_access(self, vehicle, old, target):
        """Laisser les secours traverser les acces de la caserne et de l'intervention."""
        north_access = False
        south_access = False
        for rescue in self.rescues:
            if not rescue.busy:
                continue
            if (rescue.distance < rescue.crossings[0][0] + GAP
                    or rescue.distance > rescue.crossings[1][1] - 5):
                north_access = True
            if rescue.crossings[0][1] < rescue.distance < rescue.crossings[1][0] - 70:
                south_access = True

        if vehicle.kind == "car":
            start = vehicle.route.points[0]
            gate = None
            if start == (516, 25) and north_access:
                gate = 115
            elif start == (584, 835) and south_access:
                gate = 25
            if gate is not None and old <= gate:
                target = min(target, gate)
        else:
            parking_y = vehicle.route.points[0][1]
            guards = [((457, parking_y), "N"), ((516, 650), "S"), ((584, 270), "N")]
            for point, axis in guards:
                index = vehicle.route.points.index(point)
                guard = vehicle.route.distances[index]
                if old <= guard < target and self._side_access_occupied(axis):
                    target = guard
        return target

    def _side_access_occupied(self, axis):
        for car in self.cars:
            x, y, angle = car.position
            if axis == "N" and 490 < x < 540 and 140.001 < y < 365:
                return True
            if axis == "S" and 560 < x < 610 and 580 < y < 809.999:
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
                    stage = "Sur intervention"
                elif vehicle.visited:
                    stage = "Retour a la caserne"
                else:
                    stage = "Vers l'intervention"
            states.append(VehicleState(vehicle.identifier, vehicle.kind, vehicle.color,
                                       vehicle.route, x, y, heading, vehicle.waiting,
                                       vehicle.busy, vehicle.distance / vehicle.route.length, stage))
        return Frame(tuple(states), self.lights.signal("NS"), self.lights.signal("EW"),
                     self.lights.description, self.lights.remaining, self.completed)
