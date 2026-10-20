"""Destinations, probabilites et partage du carrefour."""

from collections import Counter
from itertools import combinations, product
from math import hypot
import unittest

from src.models.layout import DESTINATIONS, INTERVENTION_POINTS, PARKING_X, PARKING_Y, rescue_route
from src.simulation.engine import GAP, Simulation


class TrafficChangesTests(unittest.TestCase):
    def test_opposite_straight_cars_cross_together_on_both_axes(self):
        for first, second, axis in (("N", "S", "NS"), ("E", "W", "EW")):
            with self.subTest(axis=axis):
                sim = Simulation(rate=0)
                sim.lights.axis = axis
                a = sim.spawn(first, "straight")
                b = sim.spawn(second, "straight")
                for car in (a, b):
                    car.distance = car.crossing[0]
                sim.advance(.5)
                self.assertEqual(sim.crossing_owners, {a.identifier, b.identifier})
                self.assertGreater(a.distance, a.crossing[0])
                self.assertGreater(b.distance, b.crossing[0])
                sim.advance(8)
                self.assertFalse(sim.crossing_owners)

    def test_turn_is_not_allowed_to_share_and_red_still_stops(self):
        sim = Simulation(rate=0)
        first = sim.spawn("N", "straight")
        turn = sim.spawn("S", "left")
        for car in (first, turn):
            car.distance = car.crossing[0]
        sim.advance(.5)
        self.assertEqual(len(sim.crossing_owners), 1)
        self.assertFalse(sim.can_share_crossing(first, turn))
        red = sim.spawn("E", "straight")
        red.distance = red.crossing[0]
        sim.advance(.5)
        self.assertEqual(red.distance, red.crossing[0])

    def test_ninety_five_percent_straight_turn_selection(self):
        sim = Simulation(rate=0)
        counts = Counter(sim.choose_turn() for _ in range(10000))
        self.assertTrue(9350 < counts["straight"] < 9650, counts)
        self.assertTrue(150 < counts["left"] < 350, counts)
        self.assertTrue(150 < counts["right"] < 350, counts)
        # Verifier aussi le tirage utilise lors de la creation de vraies voitures.
        counts = Counter()
        for index in range(1000):
            sim.cars.clear()
            counts[sim.spawn().turn] += 1
        self.assertTrue(920 < counts["straight"] < 980, counts)
        self.assertGreater(counts["left"], 0, counts)
        self.assertGreater(counts["right"], 0, counts)

    def test_routes_reach_all_points_and_return_to_parking(self):
        for identifier, y in PARKING_Y.items():
            for side in DESTINATIONS:
                route, crossings, stop = rescue_route(identifier, y, side)
                self.assertEqual(route.points[0], (PARKING_X, y))
                self.assertEqual(route.points[-1], (PARKING_X, y))
                self.assertEqual(route.sample(stop)[:2], INTERVENTION_POINTS[side])
                self.assertEqual(len(crossings), 2)

    def test_destination_is_fixed_during_a_mission(self):
        sim = Simulation(rate=0)
        self.assertTrue(sim.start_mission("01", "E"))
        route = sim.rescues[0].route
        self.assertFalse(sim.start_mission("01", "W"))
        self.assertIs(sim.rescues[0].route, route)
        with self.assertRaises(ValueError):
            sim.start_mission("02", "invalid")
        self.assertFalse(sim.rescues[1].busy)

    def test_blocked_exit_keeps_green_request_but_prevents_entry(self):
        sim = Simulation(rate=0)
        sim.start_mission("01", "W")
        rescue = sim.rescues[0]
        rescue.visited = True
        rescue.crossing_index = 1
        rescue.distance = rescue.crossing[0]
        car = sim.spawn("S", "straight")
        car.distance = car.crossing[1] + 20  # Voiture sur la sortie Nord commune.
        car.crossing_index = 1
        car.speed = 0
        self.assertFalse(sim._exit_clear(rescue))
        self.assertEqual(len(sim.requests()), 1)
        sim.advance(2.1)
        self.assertEqual(sim.lights.signal(rescue.crossing[2]), "green")
        self.assertEqual(rescue.distance, rescue.crossing[0])
        self.assertNotIn(rescue.identifier, sim.crossing_owners)
        sim.cars.clear()
        sim.advance(.5)
        self.assertIn(rescue.identifier, sim.crossing_owners)

    def test_all_pairs_finish_without_overlaps_with_traffic(self):
        for first, second in product(DESTINATIONS, repeat=2):
            with self.subTest(first=first, second=second):
                sim = Simulation(rate=40)
                sim.start_mission("01", first)
                sim.start_mission("02", second)
                for index in range(1200):
                    sim.advance(.5)
                    for a, b in combinations(sim.vehicles, 2):
                        ax, ay, angle = a.position
                        bx, by, angle = b.position
                        self.assertGreaterEqual(hypot(ax-bx, ay-by), GAP-1e-6,
                                                (sim.time, a.identifier, b.identifier))
                    inside = []
                    for vehicle in sim.vehicles:
                        if vehicle.identifier in sim.crossing_owners:
                            inside.append(vehicle)
                            if vehicle.kind != "car":
                                self.assertEqual(sim.lights.signal(vehicle.crossing[2]), "green",
                                                 (sim.time, vehicle.identifier, vehicle.visited))
                    for a, b in combinations(inside, 2):
                        self.assertTrue(sim.can_share_crossing(a, b))
                    if all(not v.busy for v in sim.rescues):
                        break
                self.assertTrue(all(not v.busy for v in sim.rescues))
                self.assertIn(("01", "disponible"), sim.events)
                self.assertIn(("02", "disponible"), sim.events)
                before = sim.completed
                sim.advance(40)
                self.assertGreater(sim.completed, before)
