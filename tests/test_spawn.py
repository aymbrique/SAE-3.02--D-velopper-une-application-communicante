"""Apparition hors des bords visibles et davantage de trafic venant du Nord."""

from collections import Counter
from itertools import product
import unittest

from src.models.layout import SCENE_HEIGHT, SCENE_WIDTH, car_route
from src.simulation.engine import GAP, Simulation


class SpawnTests(unittest.TestCase):
    def test_all_car_routes_start_and_finish_outside_visible_edges(self):
        for bounds in ((0, 0, SCENE_WIDTH, SCENE_HEIGHT), (-350, -240, 1950, 1340)):
            for origin, turn in product("NSEW", ("straight", "left", "right")):
                with self.subTest(bounds=bounds, origin=origin, turn=turn):
                    route, stop = car_route(origin, turn, bounds)
                    left, top, right, bottom = bounds
                    for x, y in (route.points[0], route.points[-1]):
                        self.assertTrue(x < left - 14 or x > right + 14
                                        or y < top - 14 or y > bottom + 14, (x, y))
                    self.assertGreater(stop, 0)

    def test_spawn_uses_visible_bounds_and_never_inserts_into_queue(self):
        sim = Simulation(rate=0)
        sim.traffic_bounds = (-350, -240, 1950, 1340)
        first = sim.spawn("N", "straight")
        self.assertLess(first.position[1] + 14, sim.traffic_bounds[1])
        self.assertIsNone(sim.spawn("N", "straight"))
        first.distance = GAP
        second = sim.spawn("N", "straight")
        self.assertIsNotNone(second)
        self.assertEqual(second.distance, 0)
        self.assertEqual(second.position[:2], second.route.points[0])

    def test_half_the_generated_traffic_comes_from_north(self):
        sim = Simulation(rate=0)
        counts = Counter()
        for _ in range(12000):
            sim.cars.clear()
            counts[sim.spawn().origin] += 1
        self.assertTrue(5700 < counts["N"] < 6300, counts)
        for origin in ("S", "E", "W"):
            self.assertTrue(1700 < counts[origin] < 2300, counts)
