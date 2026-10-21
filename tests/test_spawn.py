"""Apparition hors des bords visibles et davantage de trafic venant du Nord."""

from collections import Counter
from itertools import product
import unittest

from src.modeles.plan import SCENE_HEIGHT, SCENE_WIDTH, car_route
from src.simulation.moteur import GAP, Simulation


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

    def test_generated_north_cars_include_rare_west_and_east_choices(self):
        sim = Simulation(rate=0)
        counts = Counter()
        for _ in range(6000):
            sim.cars.clear()
            car = sim.spawn("N")
            counts[(car.turn, car.route.variant)] += 1
        # Les deux virages au feu restent a 2,5 % chacun.
        for turn in ("left", "right"):
            self.assertTrue(90 < sum(count for (movement, _), count in counts.items()
                                     if movement == turn) < 220, counts)
        # Le choix Ouest au carrefour du bas represente environ 5 % des tout droit.
        self.assertTrue(200 < counts[("straight", "lower_west")] < 380, counts)
        self.assertGreater(counts[("straight", None)], 5000, counts)

    def test_generated_middle_road_cars_sometimes_turn_north(self):
        sim = Simulation(rate=0)
        counts = Counter()
        for _ in range(6000):
            sim.cars.clear()
            car = sim.spawn("W")
            if car.turn == "straight":
                counts[car.route.variant] += 1
        self.assertTrue(200 < counts["middle_north"] < 380, counts)
        self.assertGreater(counts[None], 5000, counts)

    def test_explicit_routes_remain_predictable_and_variants_can_be_requested(self):
        sim = Simulation(rate=0)
        default = sim.spawn("N", "straight")
        self.assertIsNone(default.route.variant)
        sim.cars.clear()
        west = sim.spawn("N", "straight", variant="lower_west")
        self.assertEqual(west.route.nodes[-1], "low_west")
        sim.cars.clear()
        north = sim.spawn("W", "straight", variant="middle_north")
        self.assertEqual(north.route.nodes[-1], "top")
