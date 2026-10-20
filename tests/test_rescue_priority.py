"""Priorite sur tout l'aller/retour et degagement des raccordements sans feux."""

from itertools import combinations
from math import hypot
import unittest

from src.simulation.engine import GAP, STEP, Simulation


class RescuePriorityTests(unittest.TestCase):
    def at_junction(self, sim, destination, key, returning):
        sim.start_mission("02", destination)
        rescue = sim.get_rescue("02")
        zones = [zone for zone in rescue.route.junctions if zone[2] == key]
        stop, end, _ = zones[-1 if returning else 0]
        rescue.distance = stop
        rescue.visited = returning
        rescue.crossing_index = sum(end <= stop for _, end, _ in rescue.crossings)
        return rescue, stop, end

    def test_cars_yield_at_north_east_and_east_junctions_in_both_directions(self):
        for destination, key, origin, directions in (
                ("N", "B", "E", (False,)), ("N", "B", "W", (True,)),
                ("N", "U", "E", (False,)), ("N", "H", "E", (False, True)),
                ("E", "R", "W", (True,)),
                ("E", "E", "W", (True,))):
            for returning in directions:
                with self.subTest(destination=destination, junction=key, returning=returning):
                    sim = Simulation(rate=0)
                    rescue, stop, end = self.at_junction(sim, destination, key, returning)
                    car = sim.spawn(origin, "straight")
                    car_stop, car_end, _ = next(zone for zone in car.route.junctions if zone[2] == key)
                    car.distance = car_stop
                    self.assertFalse(sim._junction_clear(car, car_stop, car_end, key))
                    self.assertTrue(sim._junction_clear(rescue, stop, end, key))
                    sim.advance(STEP)
                    self.assertGreater(rescue.distance, stop)
                    self.assertEqual(car.distance, car_stop)

    def test_return_requests_green_and_remains_priority_until_clear(self):
        for destination in ("W", "S", "N", "E"):
            with self.subTest(destination=destination):
                sim = Simulation(rate=0)
                sim.start_mission("02", destination)
                rescue = sim.get_rescue("02")
                rescue.visited = True
                rescue.crossing_index = 1
                stop, end, axis = rescue.crossing
                rescue.distance = stop
                sim.lights.axis = "EW" if axis == "NS" else "NS"
                self.assertEqual([request.identifier for request in sim.requests()], ["02"])
                entered = False
                for _ in range(500):
                    sim.advance(STEP)
                    if rescue.identifier in sim.crossing_owners:
                        entered = True
                        self.assertTrue(rescue.busy)
                        self.assertEqual(sim.lights.owner.identifier, "02")
                        self.assertEqual(sim.lights.signal(axis), "green")
                    if rescue.distance >= end:
                        break
                self.assertTrue(entered)
                self.assertGreaterEqual(rescue.distance, end)
                self.assertTrue(rescue.busy)
                sim.advance(60)
                self.assertFalse(rescue.busy)

    def test_green_is_ready_before_rescue_arrives_outward_and_returning(self):
        for identifier in ("01", "02"):
            for destination in ("W", "S", "N", "E"):
                for returning in (False, True):
                    with self.subTest(rescue=identifier, destination=destination, returning=returning):
                        sim = Simulation(rate=0)
                        sim.start_mission(identifier, destination)
                        rescue = sim.get_rescue(identifier)
                        rescue.visited = returning
                        rescue.crossing_index = int(returning)
                        stop, end, axis = rescue.crossing
                        rescue.distance = stop - 120  # Arrivee dans 3 s.
                        sim.lights.axis = "EW" if axis == "NS" else "NS"
                        sim.advance(2.05)
                        self.assertEqual(sim.lights.signal(axis), "green")
                        self.assertLess(rescue.distance, stop)
                        sim.advance(1.5)
                        self.assertIn(identifier, sim.crossing_owners)

    def test_car_already_inside_finishes_before_priority(self):
        sim = Simulation(rate=0)
        rescue, stop, end = self.at_junction(sim, "N", "B", True)
        car = sim.spawn("E", "straight")
        car_stop, car_end, key = next(zone for zone in car.route.junctions if zone[2] == "B")
        car.distance = car_stop + GAP + 6
        self.assertFalse(sim._junction_clear(rescue, stop, end, key))
        sim.advance(12)
        self.assertGreater(rescue.distance, end)
        self.assertGreater(car.distance, car_end)

    def test_opposite_car_yields_at_green_light_for_returning_rescue(self):
        sim = Simulation(rate=0)
        sim.start_mission("02", "W")
        rescue = sim.get_rescue("02")
        rescue.visited = True
        rescue.crossing_index = 1
        rescue.distance = rescue.crossing[0]
        sim.lights.axis = "EW"
        car = sim.spawn("E", "straight")
        car.distance = car.crossing[0]
        sim.advance(STEP)
        self.assertIn(rescue.identifier, sim.crossing_owners)
        self.assertEqual(car.distance, car.crossing[0])
        sim.advance(12)
        self.assertGreater(car.distance, car.crossings[0][0])

    def test_returning_rescues_in_same_queue_serve_front_vehicle_first(self):
        from src.simulation.lights import Request
        sim = Simulation(rate=0)
        sim.start_mission("01", "N")
        sim.start_mission("02", "E")
        leader, follower = sim.rescues
        for rescue in sim.rescues:
            rescue.visited = True
            rescue.crossing_index = 1
            rescue.distance = rescue.crossing[0]
        follower.distance -= GAP + 1
        sim.lights.axis = "EW"
        # Le suiveur avait demande avant la jonction des deux trajets.
        sim.lights.owner = Request("02", "EW", 0, 0)
        self.assertEqual([request.identifier for request in sim.requests()], ["01"])
        sim.advance(STEP)
        self.assertEqual(sim.lights.owner.identifier, "01")
        self.assertIn("01", sim.crossing_owners)
        sim.advance(60)
        self.assertTrue(all(not rescue.busy for rescue in sim.rescues))

    def test_car_ahead_clears_lane_before_rescue(self):
        sim = Simulation(rate=0)
        rescue, stop, end = self.at_junction(sim, "N", "B", True)
        car = sim.spawn("E", "straight")
        car_stop, car_end, key = next(zone for zone in car.route.junctions if zone[2] == "B")
        car.distance = car_stop
        rescue.distance = stop - GAP - 2
        self.assertTrue(sim._junction_clear(car, car_stop, car_end, key))
        for _ in range(300):
            sim.advance(STEP)
            for first, second in combinations(sim.vehicles, 2):
                self.assertGreaterEqual(hypot(first.position[0] - second.position[0],
                                             first.position[1] - second.position[1]), GAP - 1e-6)
        self.assertGreater(rescue.distance, end)

    def test_available_rescue_does_not_stop_cars(self):
        sim = Simulation(rate=0)
        rescue, stop, end = self.at_junction(sim, "N", "B", True)
        rescue.busy = False
        rescue.distance = 0
        car = sim.spawn("W", "straight")
        car_stop, car_end, key = next(zone for zone in car.route.junctions if zone[2] == "B")
        car.distance = car_stop
        self.assertTrue(sim._junction_clear(car, car_stop, car_end, key))

    def test_missions_started_after_traffic_has_already_queued(self):
        sim = Simulation(rate=60, seed=51)
        sim.advance(60)
        sim.start_mission("02", "N")
        sim.advance(2)
        sim.start_mission("01", "E")
        for _ in range(1200):
            sim.advance(.5)
            for first, second in combinations(sim.vehicles, 2):
                self.assertGreaterEqual(hypot(first.position[0] - second.position[0],
                                             first.position[1] - second.position[1]), GAP - 1e-6,
                                        (sim.time, first.identifier, second.identifier))
            if all(not rescue.busy for rescue in sim.rescues):
                break
        self.assertTrue(all(not rescue.busy for rescue in sim.rescues))
        completed = sim.completed
        sim.advance(40)
        self.assertGreater(sim.completed, completed)
