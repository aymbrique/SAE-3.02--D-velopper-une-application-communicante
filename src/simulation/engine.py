"""Simulation a pas fixe. Les files tout droit compatibles peuvent passer ensemble."""

from math import cos, hypot, inf, isfinite, radians, sin
from random import Random

from src.models.layout import (DESTINATIONS, OPPOSITE, METRES_PER_UNIT, PARKING_Y,
                               SCENE_WIDTH, SCENE_HEIGHT, car_exit, car_route, rescue_route)
from src.models.vehicle import Frame, Vehicle, VehicleState
from src.simulation.lights import Lights, Request

STEP = 0.05  # Duree d'un calcul de deplacement, en secondes simulees.
GAP = 44.0  # Distance minimale entre les centres des vehicules.
MAX_CARS = 25
DWELL = 8.0  # Temps passe sur le lieu de l'intervention.
JUNCTION_LOOKAHEAD = 120.0  # Anticiper la priorite 3 s avant un raccordement.


class Simulation:
    def __init__(self, rate=12, seed=302):
        self.random = Random(seed)
        self.rate = rate
        self.time = 0.0
        self.accumulator = 0.0
        self.spawn_clock = 0.0
        self.completed = 0
        self.next_id = 1
        self.traffic_bounds = (0, 0, SCENE_WIDTH, SCENE_HEIGHT)
        self.lights = Lights()
        self.crossing_owners = set()
        self.junction_conflicts = {}
        self.cars = []
        self.rescues = []
        self.events = []
        for identifier, kind, y, color in (("01", "fire", PARKING_Y["01"], "#db6758"),
                                            ("02", "ambulance", PARKING_Y["02"], "#f8faf9")):
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
        # Une arrivee sur deux vient du Nord ; les trois autres se partagent le reste.
        origin = origin or self.random.choice(("N", "N", "N", "S", "E", "W"))
        turn = turn or self.choose_turn()
        route, stop = car_route(origin, turn, self.traffic_bounds)
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
                # Demander le vert des l'approche, meme si la sortie est encore
                # occupee. Le controle d'entree impose toujours sa liberation.
                if vehicle.identifier not in self.crossing_owners:
                    # Deux secours peuvent rejoindre la meme file au retour.
                    # Le suiveur ne doit pas verrouiller le vert devant celui
                    # qui le bloque physiquement et doit passer en premier.
                    if any(other is not vehicle and other.busy and other.crossing
                           and other.crossing[2] == vehicle.crossing[2]
                           and self._blocks_approach(other, vehicle, vehicle.crossing[0])
                           for other in self.rescues):
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
        """Suivi tout droit et mouvements opposes sans croisement de trajectoire."""
        if first.kind != "car" or second.kind != "car" or first.origin not in OPPOSITE:
            return False
        if second.origin == first.origin:
            return first.turn == second.turn == "straight"
        return (second.origin == OPPOSITE[first.origin]
                and first.turn in ("straight", "right")
                and second.turn in ("straight", "right"))

    def _exit_clear(self, vehicle):
        stop, end, axis = vehicle.crossing
        departed = self._departed_crossing(vehicle, end)
        for offset in range(0, 46, 6):
            if not self._clear_path(vehicle, end + offset, departed):
                return False
        return True

    def _following_exit(self, vehicle, end, other, other_end):
        """Un leader deja sorti peut etre suivi dans la meme voie, a distance."""
        if other.distance < other_end or other.speed <= 0 or other.waiting:
            return False
        x, y, heading = vehicle.route.sample(end)
        ox, oy, other_heading = other.position
        dx, dy = cos(radians(heading)), sin(radians(heading))
        same_heading = cos(radians(other_heading - heading)) > 0.999
        ahead = (ox - x) * dx + (oy - y) * dy
        lateral = abs((ox - x) * dy - (oy - y) * dx)
        return same_heading and ahead >= 0 and lateral < 1e-6

    def _departed_crossing(self, vehicle, end):
        departed = set()
        for other in self.vehicles:
            if other is vehicle or other.identifier in self.crossing_owners:
                continue
            for _, other_end, _ in other.crossings:
                if self._following_exit(vehicle, end, other, other_end):
                    departed.add(other.identifier)
                    break
        return departed

    def _can_enter(self, vehicle):
        stop, end, axis = vehicle.crossing
        for other in self.vehicles:
            if other.identifier in self.crossing_owners and other is not vehicle:
                if not self.can_share_crossing(vehicle, other):
                    return False
        if self.lights.signal(axis) != "green":
            return False
        if vehicle.kind == "car" and self.lights.owner:
            rescue = self.get_rescue(self.lights.owner.identifier)
            if rescue.crossing and not self._blocks_approach(vehicle, rescue, rescue.crossing[0]):
                return False
        if vehicle.kind != "car" and self.lights.owner and self.lights.owner.identifier != vehicle.identifier:
            return False
        if vehicle.kind != "car" and not self._exit_clear(vehicle):
            return False
        # Une voiture deja engagee et en mouvement ne bouche pas tout le trajet
        # des suivantes tout droit. Cela vaut aussi lorsqu'elle vient de sortir.
        # Les vehicules arretes, les virages et les secours restent des obstacles.
        following = self._departed_crossing(vehicle, end)
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
        target = self._limit_at_junctions(vehicle, old, target)
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

    def _limit_at_junctions(self, vehicle, old, target):
        """Aux raccordements sans feux, reserver un passage puis le liberer."""
        for stop, end, key in vehicle.route.junctions:
            if old <= stop < target:
                if not self._junction_clear(vehicle, stop, end, key):
                    target = stop
        return target

    def _junction_clear(self, vehicle, stop, end, key):
        priority = self._junction_priority(key)
        if priority and priority[0] is not vehicle:
            rescue, rescue_stop = priority
            # Une voiture sur la voie devant le secours doit d'abord degager,
            # sinon le secours resterait bloque derriere sa propre priorite.
            if not self._blocks_approach(vehicle, rescue, rescue_stop):
                return False
        following = set()
        for other in self.vehicles:
            if other is vehicle or (other.kind != "car" and not other.busy):
                continue
            for other_stop, other_end, other_key in other.route.junctions:
                if key != other_key:
                    continue
                if self.can_share_junction(vehicle, stop, key, other, other_stop):
                    # La file peut avancer dans la zone jusqu'au vrai feu,
                    # meme si son leader y attend. GAP reste controle a chaque pas.
                    if other.distance >= other_stop:
                        following.add(other.identifier)
                elif self._following_exit(vehicle, end, other, other_end):
                    following.add(other.identifier)
                elif other_stop < other.distance < other_end:
                    if self._junction_still_conflicts(
                            vehicle, stop, end, key, other, other_stop, other_end):
                        return False
        # Controler aussi la sortie avant d'engager le vehicule.
        for offset in range(0, int(end - stop) + 46, 6):
            if not self._clear_path(vehicle, stop + offset, following):
                return False
        return True

    def _junction_still_conflicts(self, vehicle, stop, end, key, other, other_stop, other_end):
        """Liberer un passage des que l'autre a depasse le dernier point de conflit."""
        first_move = vehicle.route.junction_movements.get((stop, key))
        other_move = other.route.junction_movements.get((other_stop, key))
        if first_move is None or other_move is None:
            return True  # Les aires et le stationnement restent exclusifs.
        # Inclure la fin du balayage : au retour F, les deux places divergent
        # juste apres le raccordement, meme si leur mouvement est identique.
        cache_key = (key, first_move, other_move, vehicle.route.sample(end + 46)[:2])
        if cache_key not in self.junction_conflicts:
            # Les memes mouvements au meme raccordement ont la meme geometrie.
            # Calculer une seule fois ou l'autre vehicule finit de nous couper
            # la route ; ajouter une marge pour l'echantillonnage de 3 unites.
            path = [vehicle.route.sample(stop + offset)[:2]
                    for offset in range(0, int(end - stop) + 47, 3)]
            last_conflict = -inf
            offsets = list(range(0, int(other_end - other_stop) + 1, 3))
            offsets.append(other_end - other_stop)
            for offset in offsets:
                x, y, _ = other.route.sample(other_stop + offset)
                if any(hypot(x - px, y - py) < GAP + 3 for px, py in path):
                    last_conflict = offset + 3
            self.junction_conflicts[cache_key] = last_conflict
        return other.distance - other_stop <= self.junction_conflicts[cache_key]

    def can_share_junction(self, first, stop, key, second, other_stop):
        """Partager une meme voie locale ou deux voies tout droit opposees."""
        if first.kind != "car" or second.kind != "car":
            return False
        first_move = first.route.junction_movements.get((stop, key))
        second_move = second.route.junction_movements.get((other_stop, key))
        if first_move is None or second_move is None:
            return False
        incoming, outgoing = first_move
        other_incoming, other_outgoing = second_move
        return (first_move == second_move
                or (incoming == outgoing and other_incoming == other_outgoing
                    and incoming == (-other_incoming[0], -other_incoming[1])))

    def _junction_priority(self, key):
        """Priorite tant que le secours est occupe, aller ET retour compris."""
        candidates = []
        for rescue in self.rescues:
            if not rescue.busy:
                continue
            for stop, end, other_key in rescue.route.junctions:
                if (other_key == key and rescue.distance < end
                        and stop - rescue.distance <= JUNCTION_LOOKAHEAD):
                    candidates.append((rescue, stop))
                    break
        if not candidates:
            return None
        return min(candidates, key=lambda item: (item[0].started_at, item[0].identifier))

    def _blocks_approach(self, vehicle, rescue, stop):
        """Autoriser les vehicules devant le secours a liberer sa voie d'arrivee."""
        x, y, _ = vehicle.position
        distance = rescue.distance
        while distance <= stop + 1e-9:
            rx, ry, _ = rescue.route.sample(distance)
            if hypot(x - rx, y - ry) < GAP:
                return True
            distance += 6
        rx, ry, _ = rescue.route.sample(stop)
        return hypot(x - rx, y - ry) < GAP

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
