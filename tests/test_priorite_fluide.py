"""Files sans depassement, manoeuvres en roulant et degagement sous forte charge."""

import unittest
from math import cos, radians

from src.simulation.moteur import GAP, STEP, RESCUE_SPEED, Simulation
from src.simulation.priorite import PULL_OVER
from traffic_checks import assert_spacing


class PrioriteFluideTests(unittest.TestCase):
    def test_followers_keep_order_behind_parked_leader_and_during_merge(self):
        sim = Simulation(rate=0)
        sim.start_mission("02", "W")
        rescue = sim.get_rescue("02")
        rescue.distance = rescue.crossing[0] - 240
        leader = sim.spawn("N", "straight")
        leader.distance = leader.crossing[0] - 100
        leader.lateral_offset = PULL_OVER
        leader.yielding_to = ("02",)
        follower = sim.spawn("N", "straight")
        follower.distance = leader.distance - GAP
        initial = follower.distance
        held = False
        for _ in range(1200):
            sim.advance(STEP)
            self.assertGreaterEqual(leader.distance - follower.distance, GAP - 1e-6)
            held |= follower.waiting
            assert_spacing(self, sim)
        self.assertTrue(held)
        self.assertGreater(follower.distance, initial + 200)
        self.assertEqual(leader.lateral_offset, 0)
        self.assertEqual(follower.lateral_offset, 0)

    def test_lateral_motion_requires_forward_motion_and_visible_steering(self):
        sim = Simulation(rate=0)
        sim.start_mission("02", "W")
        rescue = sim.get_rescue("02")
        rescue.distance = rescue.crossing[0] - 120
        car = sim.spawn("N", "straight")
        car.distance = car.crossing[0] - 60
        turned = False
        parked = False
        for _ in range(300):
            previous = car.distance, car.lateral_offset
            sim.advance(STEP)
            if abs(car.lateral_offset - previous[1]) > 1e-7:
                self.assertGreater(car.distance, previous[0])
                heading = car.route.sample(car.distance)[2]
                turned |= cos(radians(car.position[2] - heading)) < .99
            if car.yielding_to and car.manoeuvre_start is None:
                parked |= car.waiting and car.current_speed == 0
            assert_spacing(self, sim)
        self.assertTrue(turned)
        self.assertTrue(parked)
        self.assertEqual(car.lateral_offset, 0)

    def test_rescues_are_faster_than_cars_even_when_cars_turn(self):
        sim = Simulation(rate=0)
        car = sim.spawn("N", "right")
        self.assertGreater(RESCUE_SPEED, 40)
        for rescue in sim.rescues:
            self.assertGreater(rescue.speed, car.speed)
            self.assertGreater(rescue.speed, 40)
        sim.start_mission("01", "N")
        rescue = sim.get_rescue("01")
        self.assertAlmostEqual(rescue.total_estimate, rescue.route.length / rescue.speed + 8)

    def test_rescue_enters_when_car_still_crossing_is_outside_its_path(self):
        sim = Simulation(rate=0)
        sim.start_mission("01", "W")
        rescue = sim.get_rescue("01")
        rescue.distance = rescue.crossing[0]
        car = sim.spawn("N", "straight")
        car.distance = car.crossing[1] - 40
        sim.crossing_owners.add(car.identifier)
        sim.advance(STEP)
        self.assertIn(car.identifier, sim.crossing_owners)
        self.assertIn(rescue.identifier, sim.crossing_owners)
        self.assertGreater(rescue.current_speed, 0)
        assert_spacing(self, sim)

    def test_parked_exit_queue_clears_carrefour_before_priority_green(self):
        sim = Simulation(rate=0)
        sim.start_mission("01", "E")
        rescue = sim.get_rescue("01")
        rescue.visited = True
        rescue.crossing_index = 1
        rescue.distance = rescue.crossing[0]
        leader = sim.spawn("S", "straight")
        leader.distance = leader.crossing[1] + 34
        leader.crossing_index = 1
        leader.lateral_offset = PULL_OVER
        leader.yielding_to = ("01",)
        follower = sim.spawn("S", "straight")
        follower.distance = follower.crossing[1] - 10
        sim.crossing_owners.add(follower.identifier)
        entered = False
        for _ in range(200):
            sim.advance(STEP)
            assert_spacing(self, sim)
            entered |= rescue.identifier in sim.crossing_owners
        self.assertNotIn(follower.identifier, sim.crossing_owners)
        self.assertTrue(entered)

    def test_returning_rescue_leaves_junction_with_close_follower(self):
        sim = Simulation(rate=0)
        sim.start_mission("02", "N")
        rescue = sim.get_rescue("02")
        rescue.visited = True
        rescue.crossing_index = 2
        stop, end, key = [zone for zone in rescue.route.junctions if zone[2] == "F"][-1]
        rescue.distance = stop
        car = sim.spawn("S", "straight")
        car.crossing_index = 1
        exit_distance = car.crossings[0][1]
        car.distance = exit_distance + car.route.sample(exit_distance)[1] - 332
        self.assertTrue(sim._junction_clear(rescue, stop, end, key))
        for _ in range(160):
            sim.advance(STEP)
            assert_spacing(self, sim)
        self.assertFalse(rescue.busy)

    def test_tiny_remaining_distance_does_not_block_arrival_at_intervention(self):
        sim = Simulation(rate=0)
        sim.start_mission("02", "N")
        rescue = sim.get_rescue("02")
        rescue.distance = rescue.hospital - 1e-10
        rescue.crossing_index = 1
        sim.advance(STEP)
        self.assertTrue(rescue.visited)
        self.assertEqual(rescue.distance, rescue.hospital)
        self.assertEqual(rescue.dwell_remaining, 8)
        sim.advance(8 + 2 * STEP)
        self.assertGreater(rescue.distance, rescue.hospital)

    def test_tiny_remaining_distance_does_not_block_return_to_station(self):
        sim = Simulation(rate=0)
        sim.start_mission("01", "E")
        rescue = sim.get_rescue("01")
        rescue.visited = True
        rescue.crossing_index = 2
        rescue.distance = rescue.route.length - 1e-10
        sim.advance(STEP)
        self.assertFalse(rescue.busy)
        self.assertEqual(rescue.distance, 0)
        self.assertIn(("01", "disponible"), sim.drain_events())

    def test_dense_traffic_with_repeated_missions_keeps_progress_and_clears_red(self):
        schedule = {60: ("02", "N"), 62: ("01", "E"),
                    230: ("02", "S"), 232: ("01", "W"),
                    400: ("02", "E"), 402: ("01", "N")}
        for seed in (51, 302):
            with self.subTest(seed=seed):
                sim = Simulation(rate=60, seed=seed)
                started = {}
                for step in range(1200):
                    second = step / 2
                    if second in schedule:
                        identifier, destination = schedule[second]
                        self.assertTrue(sim.start_mission(identifier, destination))
                        started[identifier] = sim.time
                    sim.advance(.5)
                    assert_spacing(self, sim)
                    if sim.lights.phase == "all_red":
                        self.assertLess(sim.lights.elapsed, 20, (sim.time, sim.crossing_owners))
                    for rescue in sim.rescues:
                        if rescue.busy:
                            self.assertLess(sim.time - started[rescue.identifier], 165,
                                            (sim.time, rescue.identifier, rescue.destination))
                self.assertTrue(all(not rescue.busy for rescue in sim.rescues))
                before = sim.completed
                sim.advance(40)
                self.assertGreater(sim.completed, before)


if __name__ == "__main__":
    unittest.main()
