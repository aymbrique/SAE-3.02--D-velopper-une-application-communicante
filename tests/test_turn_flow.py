"""Virages rapides sans perdre l'espacement ni les controles de conflit."""

from itertools import combinations, product
from math import hypot
import unittest

from src.simulation.engine import GAP, STEP, Simulation


class TurnFlowTests(unittest.TestCase):
    def assert_gaps(self, sim):
        for first, second in combinations(sim.vehicles, 2):
            self.assertGreaterEqual(hypot(first.position[0] - second.position[0],
                                         first.position[1] - second.position[1]), GAP - 1e-6)

    def test_every_main_turn_clears_within_one_normal_green(self):
        for origin, turn in product("NSEW", ("left", "right")):
            with self.subTest(origin=origin, turn=turn):
                sim = Simulation(rate=0)
                sim.lights.axis = "NS" if origin in "NS" else "EW"
                car = sim.spawn(origin, turn)
                stop, end, _ = car.crossing
                car.distance = stop
                for _ in range(150):  # 7,5 s, avant l'orange de 8 s.
                    sim.advance(STEP)
                    self.assert_gaps(sim)
                    if car.distance >= end:
                        break
                self.assertGreaterEqual(car.distance, end)
                self.assertEqual(sim.lights.signal(sim.lights.axis), "green")

    def test_same_turn_convoy_follows_before_leader_leaves(self):
        for turn in ("left", "right"):
            with self.subTest(turn=turn):
                sim = Simulation(rate=0)
                leader = sim.spawn("N", turn)
                leader.distance = leader.crossing[0] + 70
                sim.crossing_owners.add(leader.identifier)
                follower = sim.spawn("N", turn)
                follower.distance = follower.crossing[0]
                self.assertTrue(sim.can_share_crossing(leader, follower))
                sim.advance(STEP)
                self.assertEqual(sim.crossing_owners, {leader.identifier, follower.identifier})
                for _ in range(150):
                    sim.advance(STEP)
                    self.assert_gaps(sim)
                self.assertIsNone(leader.crossing)
                self.assertIsNone(follower.crossing)

    def test_curve_acceleration_keeps_stationary_vehicles_stationary(self):
        sim = Simulation(rate=0)
        car = sim.spawn("N", "left")
        car.distance = car.route.turn_zones[0][0] + 10
        sim.crossing_owners.add(car.identifier)
        car.speed = 0
        before = car.distance
        sim.advance(1)
        self.assertEqual(car.distance, before)

    def test_rare_secondary_turns_finish_without_blocking_traffic(self):
        for origin, variant, key in (("N", "lower_west", "D"),
                                     ("W", "middle_north", "B")):
            with self.subTest(variant=variant):
                sim = Simulation(rate=0)
                car = sim.spawn(origin, "straight", variant=variant)
                stop, end, _ = next(zone for zone in car.route.junctions if zone[2] == key)
                car.distance = stop
                car.crossing_index = 1
                for _ in range(150):
                    sim.advance(STEP)
                    self.assert_gaps(sim)
                    if car.distance >= end:
                        break
                self.assertGreaterEqual(car.distance, end)
                sim.advance(60)
                self.assertEqual(sim.completed, 1)


if __name__ == "__main__":
    unittest.main()
