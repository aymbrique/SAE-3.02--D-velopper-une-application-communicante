"""Simulation a pas fixe. Les files tout droit compatibles peuvent passer ensemble."""

from math import cos, hypot, inf, isfinite, radians, sin
from random import Random

from src.modeles.plan import (DESTINATIONS, OPPOSITE, METRES_PER_UNIT, PARKING_Y,
                               SCENE_WIDTH, SCENE_HEIGHT, car_exit, car_route, rescue_route, on_road)
from src.modeles.vehicules import Frame, Vehicle, VehicleState
from src.simulation.feux import Lights, Request
from src.simulation.priorite import (PULL_OVER, beside_rescue,
                                     bodies_clear, corners)

STEP = 0.05  # Duree d'un calcul de deplacement, en secondes simulees.
GAP = 44.0  # Distance minimale entre les centres des vehicules.
MAX_CARS = 25
DWELL = 8.0  # Temps passe sur le lieu de l'intervention.
RESCUE_SPEED = 56.0  # Plus rapide que les voitures, y compris dans les virages.
JUNCTION_LOOKAHEAD = 3 * RESCUE_SPEED  # Anticiper la priorite 3 s avant un raccordement.
TURN_SPEED_FACTOR = 40 / 28  # Degager les virages plus vite que l'allure de croisiere.


def car_parked(vehicle):
    return vehicle.manoeuvre_start is None and vehicle.lateral_offset >= PULL_OVER - 1e-6


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
        self.crossing_conflicts = {}
        self.clearing_accesses = set()
        self.cars = []
        self.rescues = []
        self.events = []
        for identifier, kind, y, color in (("01", "fire", PARKING_Y["01"], "#db6758"),
                                            ("02", "ambulance", PARKING_Y["02"], "#f8faf9")):
            route, crossings, hospital = rescue_route(identifier, y)
            self.rescues.append(Vehicle(identifier, kind, route, crossings, color, RESCUE_SPEED,
                                        hospital=hospital, total_estimate=route.length / RESCUE_SPEED + DWELL,
                                        manoeuvre_length=60.0))

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
        vehicle.lateral_offset = 0.0
        vehicle.manoeuvre_start = None
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

    def choose_variant(self, origin, turn):
        # Un trajet sur vingt bifurque au raccordement situe apres le feu.
        if (origin, turn) in (("N", "straight"), ("E", "left"), ("W", "right")):
            return "lower_west" if self.random.randrange(20) == 0 else None
        if (origin, turn) in (("W", "straight"), ("N", "left"), ("S", "right")):
            return "middle_north" if self.random.randrange(20) == 0 else None
        return None

    def spawn(self, origin=None, turn=None, *, variant=None):
        if len(self.cars) >= MAX_CARS:
            return None
        # Une arrivee sur deux vient du Nord ; les trois autres se partagent le reste.
        origin = origin or self.random.choice(("N", "N", "N", "S", "E", "W"))
        automatic_turn = turn is None
        turn = turn or self.choose_turn()
        if automatic_turn and variant is None:
            variant = self.choose_variant(origin, turn)
        route, stop = car_route(origin, turn, self.traffic_bounds, variant=variant)
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
            # Le second passage est le retour : ne pas le reserver en allant
            # au patient, pendant les soins ou encore dans l'allee du parking.
            if vehicle.crossing_index == 1 and (
                    not vehicle.visited or vehicle.dwell_remaining > 0
                    or not on_road(*vehicle.position[:2])):
                continue
            distance, eta = self.approach(vehicle)
            returning_to_station = self._returning_station(vehicle)
            at_threshold = distance is not None and (distance <= 150 or eta <= 10)
            if returning_to_station or at_threshold or self._leaving_station(vehicle):
                # Demander le vert des l'approche, meme si la sortie est encore
                # occupee. Le controle d'entree impose toujours sa liberation.
                if vehicle.crossing and vehicle.identifier not in self.crossing_owners:
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
                axis = "NS" if returning_to_station else vehicle.crossing[2]
                result.append(Request(vehicle.identifier, axis,
                                      vehicle.started_at, vehicle.requested_at,
                                      passage=vehicle.crossing_index if at_threshold else None,
                                      engaged=vehicle.identifier in self.crossing_owners))
        return result

    def _leaving_station(self, vehicle):
        """Des le depart, degager la file Nord avant d'inserer le secours."""
        if not vehicle.busy or vehicle.visited or vehicle.crossing_index != 0:
            return False
        station_exit = next(end for _, end, key in vehicle.route.junctions if key == "F")
        return vehicle.distance < station_exit

    def _returning_station(self, vehicle):
        """Conserver le vert Nord jusqu'au degagement du retour a la caserne.

        Une file Nord au rouge pourrait sinon emprisonner le premier secours
        devant F, boucher la sortie du carrefour et bloquer le second secours.
        """
        if not vehicle.busy or not vehicle.visited or vehicle.crossing is not None:
            return False
        station_end = [end for _, end, key in vehicle.route.junctions if key == "F"][-1]
        return vehicle.distance < station_end

    def advance(self, duration):
        if not isfinite(duration) or duration < 0:
            raise ValueError("Duree invalide")
        self.accumulator += duration
        while self.accumulator >= STEP - 1e-9:
            self._step()
            self.accumulator -= STEP

    def _step(self):
        self.time += STEP
        self._update_clearing_accesses()
        self._update_yielding()
        self._update_rescue_lanes()
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
            if car.distance >= car.route.length - 1e-6:
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

    def _position(self, vehicle, distance, offset=None):
        return vehicle.position_at(distance, offset)

    def _opposite_station_moves(self, first, second):
        """Un retour et un depart utilisent deux voies distinctes dans l'allee."""
        if (first.kind == "car" or second.kind == "car"
                or not first.busy or not second.busy or first.visited == second.visited):
            return False
        return all(any(key == "parking" and stop <= vehicle.distance < end
                       for stop, end, key in vehicle.route.junctions)
                   for vehicle in (first, second))

    def pair_clear(self, first, second, position=None, other_position=None):
        position = first.position if position is None else position
        other_position = second.position if other_position is None else other_position
        distance = hypot(position[0] - other_position[0], position[1] - other_position[1])
        if distance >= GAP - 1e-7:
            return True
        if self._opposite_station_moves(first, second):
            return bodies_clear(first, position, second, other_position)
        if abs(first.lateral_offset) > 1e-6 or abs(second.lateral_offset) > 1e-6:
            return bodies_clear(first, position, second, other_position)
        # Apres une reinsertion, un ecart deja court ne doit pas emprisonner
        # le vehicule de tete : il peut s'eloigner en gardant les gabarits libres.
        previous = hypot(first.position[0] - second.position[0],
                         first.position[1] - second.position[1])
        escaping = distance > previous + 1e-7
        unchanged_rescue = ((first.kind != "car" or second.kind != "car")
                            and distance >= previous - 1e-7)
        return ((escaping or unchanged_rescue)
                and bodies_clear(first, position, second, other_position))

    def _clear_position(self, vehicle, position, ignored=()):
        for other in self.vehicles:
            if other is vehicle or other.identifier in ignored:
                continue
            if not self.pair_clear(vehicle, other, position):
                return False
        return True

    def _clear_path(self, vehicle, target, ignored=()):
        position = self._position(vehicle, target)
        if vehicle.manoeuvre_start is not None:
            if not all(on_road(x, y) for x, y in corners(vehicle, position)):
                return False
        return self._clear_position(vehicle, position, ignored)

    def _can_pull_over(self, car):
        if car.identifier in self.crossing_owners or car.speed <= 0:
            return False
        end = car.distance + car.manoeuvre_length
        if car.crossing and car.distance <= car.crossing[0] < end - 1e-6:
            return False
        _, _, before = car.route.sample(car.distance)
        for distance in (car.distance + 20, car.distance + 40, end):
            _, _, after = car.route.sample(distance)
            if cos(radians(before - after)) < .995:
                return False
        # Ne jamais se garer au milieu d'un raccordement.
        return not any(stop < end and car.distance < finish
                       for stop, finish, _ in car.route.junctions)

    def _update_yielding(self):
        for car in self.cars:
            nearby = tuple(rescue.identifier for rescue in self.rescues
                           if beside_rescue(car, rescue))
            in_junction = any(stop < car.distance < end
                              for stop, end, _ in car.route.junctions)
            can_park = (car.identifier not in self.crossing_owners and not in_junction
                        and (self._can_pull_over(car) or car.lateral_offset > 0
                             or (car.manoeuvre_start is not None
                                 and car.manoeuvre_target == PULL_OVER)))
            car.yielding_to = nearby if can_park else ()
            target = PULL_OVER if car.yielding_to else 0.0
            if (car.manoeuvre_start is not None
                    or abs(car.lateral_offset - target) < 1e-9):
                continue
            if target == 0 and not self._merge_has_room(car):
                continue
            car.manoeuvre_start = car.distance
            car.manoeuvre_from = car.lateral_offset
            car.manoeuvre_target = target
            if not all(on_road(x, y)
                       for distance in range(0, int(car.manoeuvre_length) + 1, 3)
                       for x, y in corners(car, car.position_at(car.distance + distance))):
                car.manoeuvre_start = None
                if target:
                    car.yielding_to = ()

    def _merge_has_room(self, car):
        x, y, heading = car.route.sample(car.distance)
        dx, dy = cos(radians(heading)), sin(radians(heading))
        for rescue in self.rescues:
            if not rescue.busy:
                continue
            rx, ry, other_heading = rescue.route.sample(rescue.distance)
            ahead = (x - rx) * dx + (y - ry) * dy
            lateral = abs((x - rx) * dy - (y - ry) * dx)
            if (cos(radians(heading - other_heading)) > .96
                    and -45 < ahead < 80 and lateral < 40):
                return False
        return True

    def _update_rescue_lanes(self):
        """Seul le secours peut emprunter le milieu de la route pour depasser."""
        active = [rescue for rescue in self.rescues if rescue.busy]
        passing = min(active, key=lambda rescue: (rescue.started_at, rescue.identifier),
                      default=None)
        for rescue in active:
            x, y, heading = rescue.route.sample(rescue.distance)
            dx, dy = cos(radians(heading)), sin(radians(heading))
            target = 0.0
            if rescue is passing and not rescue.dwell_remaining:
                for car in self.cars:
                    ox, oy, other_heading = car.position
                    ahead = (ox - x) * dx + (oy - y) * dy
                    lateral = abs((ox - x) * dy - (oy - y) * dx)
                    if (cos(radians(heading - other_heading)) > .8
                            and -45 < ahead < 180 and lateral < PULL_OVER - .5):
                        target = -PULL_OVER
                        break
            # Garder aussi la place de reintegrer sa voie avant le prochain virage.
            if target and any(stop - 4 * rescue.manoeuvre_length <= rescue.distance < end
                              for stop, end, _ in (*rescue.route.junctions, *rescue.crossings)):
                target = 0.0
            if target and any(cos(radians(heading - rescue.route.sample(
                    rescue.distance + offset)[2])) < .995 for offset in (30, 60, 90, 120)):
                target = 0.0
            if rescue.manoeuvre_start is not None:
                continue
            if rescue.manoeuvre_start is None and abs(rescue.lateral_offset - target) < 1e-9:
                continue
            previous = (rescue.manoeuvre_start, rescue.manoeuvre_from, rescue.manoeuvre_target)
            rescue.manoeuvre_start = rescue.distance
            rescue.manoeuvre_from = rescue.lateral_offset
            rescue.manoeuvre_target = target
            if target and not all(on_road(px, py)
                                  for offset in (15, 30, 45, 60)
                                  for px, py in corners(rescue, rescue.position_at(rescue.distance + offset))):
                rescue.manoeuvre_start, rescue.manoeuvre_from, rescue.manoeuvre_target = previous

    def _update_clearing_accesses(self):
        keys = {key for rescue in self.rescues if rescue.busy
                for stop, end, key in rescue.route.junctions
                if (rescue.distance < end and (stop - rescue.distance <= JUNCTION_LOOKAHEAD
                    or key == "F" and self._leaving_station(rescue)))}
        self.clearing_accesses = {
            vehicle.identifier for vehicle in self.vehicles
            if (vehicle.kind == "car" or vehicle.busy)
            and any(key in keys and (stop < vehicle.distance < end
                    or vehicle.kind != "car" and stop == vehicle.distance)
                    for stop, end, key in vehicle.route.junctions)}

    def _clears_access_queue(self, vehicle):
        """Degager une file encore engagee dans un carrefour ou un acces de secours."""
        x, y, heading = vehicle.route.sample(vehicle.distance)
        dx, dy = cos(radians(heading)), sin(radians(heading))
        for other in self.vehicles:
            if other.kind != "car" and other.identifier not in self.clearing_accesses:
                continue
            manoeuvring = (other.kind == "car" and other.manoeuvre_start is not None
                            and other.manoeuvre_target == PULL_OVER)
            if (other is vehicle or not manoeuvring and other.identifier not in (
                    self.crossing_owners | self.clearing_accesses)):
                continue
            reference = other.distance
            if other.kind != "car":
                # Un secours qui s'insere regarde la voie a la sortie de sa courbe.
                reference = next((end for stop, end, _ in other.route.junctions
                                  if stop <= other.distance < end), reference)
            ox, oy, other_heading = other.route.sample(reference)
            ahead = (x - ox) * dx + (y - oy) * dy
            lateral = abs((x - ox) * dy - (y - oy) * dx)
            minimum = -GAP if reference != other.distance else 0.0
            if (cos(radians(heading - other_heading)) > .96
                    and minimum < ahead < MAX_CARS * GAP and lateral < 18):
                return True
        return False

    def _follow_queue(self, vehicle, target):
        """Conserver l'ordre de la file, meme si son leader est range au bord."""
        x, y, heading = vehicle.route.sample(vehicle.distance)
        dx, dy = cos(radians(heading)), sin(radians(heading))
        for other in self.cars:
            if other is vehicle:
                continue
            if vehicle.kind != "car" and not (other.manoeuvre_start is not None
                                               and other.manoeuvre_target == 0):
                continue
            # La voie habituelle reste reservee au leader pendant sa manoeuvre.
            ox, oy, other_heading = other.route.sample(other.distance)
            if cos(radians(heading - other_heading)) < .96:
                continue
            ahead = (ox - x) * dx + (oy - y) * dy
            lateral = abs((ox - x) * dy - (oy - y) * dx)
            if 0 < ahead < GAP + 150 and lateral < 18:
                target = min(target, vehicle.distance + max(0.0, ahead - GAP))
        return target

    def can_share_crossing(self, first, second):
        """Suivi tout droit et mouvements opposes sans croisement de trajectoire."""
        if (first.kind == "car") != (second.kind == "car"):
            return True  # Le secours se guide sur les carrosseries, sans reserver tout le carrefour.
        if first.kind != "car" or first.origin not in OPPOSITE:
            return False
        if second.origin == first.origin:
            return True
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
        if vehicle.kind == "car" and vehicle.lateral_offset == 0:
            for other in self.cars:
                if (other is not vehicle and other.origin == vehicle.origin
                        and other.lateral_offset > 0 and not other.yielding_to
                        and vehicle.distance - 28 < other.distance < vehicle.distance + 150):
                    return False  # Laisser la voiture rangee reintegrer sa file.
        for other in self.vehicles:
            if other.identifier in self.crossing_owners and other is not vehicle:
                if not self.can_share_crossing(vehicle, other):
                    return False
                if (vehicle.kind != "car" and other.kind == "car"
                        and self._crossing_conflict_ahead(vehicle, other)):
                    return False
                if vehicle.lateral_offset > 0 or other.lateral_offset > 0:
                    point = self._position(vehicle, vehicle.distance + vehicle.speed * STEP)
                    ox, oy, _ = other.position
                    if hypot(point[0] - ox, point[1] - oy) < GAP - 1e-7:
                        return False
        if self.lights.signal(axis) != "green":
            return False
        if vehicle.kind == "car" and self.lights.owner:
            rescue = self.get_rescue(self.lights.owner.identifier)
            if rescue.crossing and not self._blocks_approach(vehicle, rescue, rescue.crossing[0]):
                return False
        if vehicle.kind != "car" and self.lights.owner and self.lights.owner.identifier != vehicle.identifier:
            return False
        if vehicle.kind != "car":
            # Un obstacle lointain ou dans une autre branche ne ferme pas l'entree.
            # Chaque pas reste soumis au controle de collision des carrosseries.
            return self._clear_path(vehicle, vehicle.distance + min(.05, vehicle.speed * STEP))
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

    def _crossing_conflict_ahead(self, rescue, car):
        """Ne pas couper la manoeuvre d'une voiture deja engagee au carrefour."""
        stop, end, _ = rescue.crossing
        car_stop, car_end, _ = car.crossing
        incoming, outgoing = rescue.route.sample(stop), rescue.route.sample(end)
        car_incoming, car_outgoing = car.route.sample(car_stop), car.route.sample(car_end)
        if all(hypot(first[0] - second[0], first[1] - second[1]) < 1
               and cos(radians(first[2] - second[2])) > .999
               for first, second in ((incoming, car_incoming), (outgoing, car_outgoing))):
            return False  # Le suivi dans la meme voie reste possible, a distance.
        manoeuvre = ((car.manoeuvre_start - car_stop, car.manoeuvre_from,
                      car.manoeuvre_target, car.manoeuvre_length)
                     if car.manoeuvre_start is not None else (None, car.lateral_offset))
        key = (incoming, outgoing, car_incoming, car_outgoing, manoeuvre)
        if key not in self.crossing_conflicts:
            path = [rescue.position_at(stop + offset)
                    for offset in range(0, int(end - stop) + 45, 3)]
            last = -inf
            for offset in range(0, int(car_end - car_stop) + 45, 3):
                position = car.position_at(car_stop + offset)
                if any(hypot(position[0] - point[0], position[1] - point[1]) < GAP
                       and not bodies_clear(rescue, point, car, position) for point in path):
                    last = offset + 3
            self.crossing_conflicts[key] = last
        return car.distance - car_stop <= self.crossing_conflicts[key]

    def _move(self, vehicle):
        vehicle.current_speed = 0.0
        if vehicle.kind != "car" and not vehicle.busy:
            return
        if (vehicle.kind == "car" and vehicle.yielding_to
                and car_parked(vehicle) and not self._clears_access_queue(vehicle)):
            vehicle.waiting = True
            return
        if vehicle.dwell_remaining > 0:
            vehicle.dwell_remaining = max(0.0, vehicle.dwell_remaining - STEP)
            vehicle.waiting = True
            return
        old = vehicle.distance
        speed = vehicle.speed
        if vehicle.kind == "car" and any(start <= old < end
                                         for start, end in vehicle.route.turn_zones):
            speed *= TURN_SPEED_FACTOR
        if vehicle.kind == "car":
            x, y, angle = vehicle.position
            dx, dy = cos(radians(angle)), sin(radians(angle))
            for other in self.cars:
                if other is vehicle:
                    continue
                ox, oy, _ = other.position
                ahead = (ox - x) * dx + (oy - y) * dy
                lateral = abs((ox - x) * dy - (oy - y) * dx)
                if (other.lateral_offset > 0 and not other.yielding_to
                        and -20 < ahead < GAP + 12 and lateral < 40):
                    speed = min(speed, 18.0)
                if other.identifier not in self.crossing_owners:
                    continue
                if other.turn == "straight" or other.turn == vehicle.turn:
                    continue
                if 0 < ahead < 150 and lateral < 70:
                    speed = min(speed, 18.0)
        target = min(old + speed * STEP, vehicle.route.length)
        target = self._follow_queue(vehicle, target)
        if (vehicle.kind == "car" and vehicle.yielding_to
                and vehicle.manoeuvre_start is not None):
            target = min(target, vehicle.manoeuvre_start + vehicle.manoeuvre_length)
        target = self._limit_at_junctions(vehicle, old, target)
        crossing = vehicle.crossing
        entering = crossing is not None and old <= crossing[0] and target > crossing[0]
        if entering and not self._can_enter(vehicle):
            target = crossing[0]
        if vehicle.hospital is not None and not vehicle.visited:
            target = min(target, vehicle.hospital)
        if target > old and not self._clear_path(vehicle, target):
            low, high = old, target
            if not self._clear_path(vehicle, old + min(.05, target - old)):
                high = old
            for _ in range(8 if high > old else 0):
                middle = (low + high) / 2
                if self._clear_path(vehicle, middle):
                    low = middle
                else:
                    high = middle
            target = low
        if target > old + 1e-7 and self._clear_path(vehicle, target):
            vehicle.distance = target
            if vehicle.manoeuvre_start is not None:
                vehicle.lateral_offset, _ = vehicle.roadside_offset(target)
                if target >= vehicle.manoeuvre_start + vehicle.manoeuvre_length - 1e-7:
                    vehicle.lateral_offset = vehicle.manoeuvre_target
                    vehicle.manoeuvre_start = None
            vehicle.current_speed = (target - old) / STEP
            if entering and target > crossing[0]:
                self.crossing_owners.add(vehicle.identifier)
        if (vehicle.manoeuvre_start is not None and vehicle.distance >=
                vehicle.manoeuvre_start + vehicle.manoeuvre_length - 1e-6):
            vehicle.distance = vehicle.manoeuvre_start + vehicle.manoeuvre_length
            vehicle.lateral_offset = vehicle.manoeuvre_target
            vehicle.manoeuvre_start = None
        vehicle.waiting = vehicle.distance <= old + 1e-9
        if (vehicle.kind == "car" and vehicle.yielding_to and car_parked(vehicle)
                and not self._clears_access_queue(vehicle)):
            vehicle.waiting = True
            vehicle.current_speed = 0.0
        if crossing and vehicle.distance >= crossing[1]:
            self.crossing_owners.discard(vehicle.identifier)
            vehicle.crossing_index += 1
            vehicle.requested_at = None
        if vehicle.hospital is not None and not vehicle.visited and vehicle.distance >= vehicle.hospital - 1e-6:
            vehicle.distance = vehicle.hospital
            vehicle.visited = True
            vehicle.dwell_remaining = DWELL
        if vehicle.kind != "car" and vehicle.distance >= vehicle.route.length - 1e-6:
            vehicle.busy = False
            vehicle.distance = 0.0
            vehicle.lateral_offset = 0.0
            vehicle.manoeuvre_start = None
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
                    if key == "parking" and self._opposite_station_moves(vehicle, other):
                        # Le secours sortant peut attendre a F sans retenir toute
                        # l'allee du retour. Le balayage controle les gabarits.
                        continue
                    if self._junction_still_conflicts(
                            vehicle, stop, end, key, other, other_stop, other_end):
                        return False
        # Le garage ne reserve que son allee : l'insertion est controlee a F.
        # Sinon une file deja en train de degager F immobilise encore le secours
        # sur sa place, alors que son trajet jusqu'a la ligne d'insertion est libre.
        sweep_end, margin = end, (1 if vehicle.kind != "car" else 46)
        if key == "parking" and stop == 0:
            sweep_end = next(start for start, _, name in vehicle.route.junctions if name == "F")
            margin = 1
        # Controler aussi la sortie avant d'engager le vehicule.
        for offset in range(0, int(sweep_end - stop) + margin, 6):
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
        def manoeuvre_state(item, start):
            return ((item.manoeuvre_start - start, item.manoeuvre_from,
                     item.manoeuvre_target, item.manoeuvre_length)
                    if item.manoeuvre_start is not None else (None, item.lateral_offset))

        adjusted = (vehicle.manoeuvre_start is not None or other.manoeuvre_start is not None
                    or vehicle.lateral_offset != 0 or other.lateral_offset != 0)
        cache_key = (key, first_move, other_move, vehicle.kind, other.kind,
                     vehicle.route.sample(end + 46)[:2],
                     manoeuvre_state(vehicle, stop), manoeuvre_state(other, other_stop))
        if cache_key not in self.junction_conflicts:
            # Les memes mouvements au meme raccordement ont la meme geometrie.
            # Calculer une seule fois ou l'autre vehicule finit de nous couper
            # la route ; ajouter une marge pour l'echantillonnage de 3 unites.
            path = [vehicle.position_at(stop + offset)
                    for offset in range(0, int(end - stop) + 47, 3)]
            last_conflict = -inf
            offsets = list(range(0, int(other_end - other_stop) + 1, 3))
            offsets.append(other_end - other_stop)
            for offset in offsets:
                position = other.position_at(other_stop + offset)
                if any(hypot(position[0] - point[0], position[1] - point[1]) < GAP + 3
                       and (not adjusted or not bodies_clear(vehicle, point, other, position))
                       for point in path):
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
                station_departure = key == "F" and self._leaving_station(rescue)
                if (other_key == key and rescue.distance < end
                        and (stop - rescue.distance <= JUNCTION_LOOKAHEAD or station_departure)):
                    candidates.append((rescue, stop))
                    break
        if not candidates:
            return None
        if key == "F":
            for outgoing, outgoing_stop in candidates:
                if not self._leaving_station(outgoing):
                    continue
                for returning, returning_stop in candidates:
                    if (returning is outgoing or not self._returning_station(returning)
                            or returning.distance > returning_stop):
                        continue
                    # Un depart deja dans l'allee peut barrer la fin du retour.
                    # Le laisser sortir evite que chacun attende l'autre a F.
                    parking_end = returning.route.length
                    if any(not bodies_clear(returning, returning.position_at(distance),
                                            outgoing, outgoing.position)
                           for distance in range(int(returning_stop), int(parking_end) + 1, 6)):
                        return outgoing, outgoing_stop
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
            if vehicle.kind == "car" and vehicle.yielding_to:
                stage = "Range sur le cote - priorite secours " + ", ".join(vehicle.yielding_to)
            elif vehicle.kind == "car" and vehicle.lateral_offset > 1e-6:
                stage = "Reprise apres le passage du secours"
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
