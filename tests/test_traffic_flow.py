"""Regressions : files tout droit, espacement, degagement et mouvements exclusifs."""

from itertools import combinations
from math import hypot
import unittest

from src.simulation.moteur import GAP, STEP, Simulation
from traffic_checks import assert_spacing


class TrafficFlowTests(unittest.TestCase):
    def queue(self, sim, origin, count=6):
        cars = []
        for index in range(count):
            car = sim.spawn(origin, "straight")
            self.assertIsNotNone(car)
            car.distance = car.crossing[0] - GAP * index
            cars.append(car)
        return cars

    def assert_gaps(self, sim):
        assert_spacing(self, sim)

    def test_two_queues_follow_through_one_green_on_both_axes(self):
        for first, second, axis in (("N", "S", "NS"), ("E", "W", "EW")):
            with self.subTest(axis=axis):
                sim = Simulation(rate=0)
                sim.lights.axis = axis
                cars = self.queue(sim, first) + self.queue(sim, second)
                entered = set()
                maximum = 0
                for step in range(159):
                    sim.advance(STEP)
                    entered.update(sim.crossing_owners)
                    maximum = max(maximum, len(sim.crossing_owners))
                    self.assert_gaps(sim)
                self.assertEqual(entered, {car.identifier for car in cars})
                self.assertGreater(maximum, 2)
                # Les files avancent sans s'arreter derriere leurs leaders.
                self.assertTrue(all(not car.waiting for car in cars))
                # Les nouveaux raccordements en aval peuvent ralentir la sortie.
                # Tous les vehicules doivent quand meme finir par degager.
                for step in range(800):
                    sim.advance(STEP)
                    self.assert_gaps(sim)
                    if not sim.crossing_owners:
                        break
                self.assertFalse(sim.crossing_owners)

    def test_follower_keeps_moving_when_leader_has_just_left_crossing(self):
        sim = Simulation(rate=0)
        leader, follower = self.queue(sim, "N", 2)
        end = leader.crossing[1]
        leader.distance = end - .5
        sim.crossing_owners.add(leader.identifier)
        follower.distance = follower.crossing[0]
        sim.advance(STEP)
        self.assertNotIn(leader.identifier, sim.crossing_owners)
        self.assertIn(follower.identifier, sim.crossing_owners)
        self.assertGreater(follower.distance, follower.crossing[0])
        self.assert_gaps(sim)

    def test_stationary_exit_still_blocks_entry(self):
        sim = Simulation(rate=0)
        leader, follower = self.queue(sim, "N", 2)
        leader.distance = leader.crossing[1] + GAP / 2
        leader.crossing_index = 1
        leader.speed = 0
        follower.distance = follower.crossing[0]
        sim.advance(1)
        self.assertEqual(follower.distance, follower.crossing[0])
        self.assertNotIn(follower.identifier, sim.crossing_owners)
        self.assert_gaps(sim)

    def test_rescue_follows_moving_car_that_has_already_left_crossing(self):
        sim = Simulation(rate=0)
        leader = sim.spawn("N", "straight")
        leader.distance = leader.crossing[1] + .5
        leader.crossing_index = 1
        sim.start_mission("01", "S")
        rescue = sim.get_rescue("01")
        stop = rescue.crossing[0]
        rescue.distance = stop
        sim.advance(1.5)  # Laisser la voiture se ranger avant le depassement.
        self.assertGreater(rescue.distance, stop)
        self.assertIn(rescue.identifier, sim.crossing_owners)
        self.assert_gaps(sim)

    def test_rescue_still_waits_for_stationary_car_on_exit(self):
        sim = Simulation(rate=0)
        leader = sim.spawn("N", "straight")
        leader.distance = leader.crossing[1] + .5
        leader.crossing_index = 1
        leader.speed = 0
        sim.start_mission("01", "S")
        rescue = sim.get_rescue("01")
        stop = rescue.crossing[0]
        rescue.distance = stop
        sim.advance(1)
        self.assertEqual(rescue.distance, stop)
        self.assertNotIn(rescue.identifier, sim.crossing_owners)
        self.assert_gaps(sim)

    def test_close_follower_does_not_pause_when_leader_clears_crossing(self):
        sim = Simulation(rate=0)
        leader, follower = self.queue(sim, "N", 2)
        leader.distance = leader.crossing[1] + .5
        leader.crossing_index = 1
        follower.distance = leader.distance - GAP
        sim.crossing_owners.add(follower.identifier)
        previous = follower.distance
        sim.advance(STEP)
        self.assertAlmostEqual(follower.distance - previous, follower.speed * STEP)
        self.assertAlmostEqual(leader.distance - follower.distance, GAP)
        self.assertFalse(follower.waiting)

    def test_turning_leader_allows_straight_follower_to_enter_slowly(self):
        for turn in ("left", "right"):
            with self.subTest(turn=turn):
                sim = Simulation(rate=0)
                leader = sim.spawn("N", turn)
                leader.distance = leader.crossing[0] + 70
                sim.crossing_owners.add(leader.identifier)
                follower = sim.spawn("N", "straight")
                follower.distance = follower.crossing[0]
                sim.advance(STEP)
                self.assertGreater(follower.distance, follower.crossing[0])
                self.assertLess(follower.current_speed, follower.speed)
                self.assertTrue(sim.can_share_crossing(leader, follower))
                self.assertIn(follower.identifier, sim.crossing_owners)
                self.assertIn(leader.identifier, sim.crossing_owners)
                for step in range(200):
                    sim.advance(STEP)
                    self.assert_gaps(sim)
                    if follower.identifier in sim.crossing_owners:
                        break
                self.assertIn(follower.identifier, sim.crossing_owners)
                self.assert_gaps(sim)

    def test_convoy_waits_at_orange_and_other_axis_waits_until_everyone_leaves(self):
        sim = Simulation(rate=0)
        leader, follower, stopped = self.queue(sim, "N", 3)
        stop = leader.crossing[0]
        leader.distance = stop + 2 * GAP
        follower.distance = stop + GAP
        stopped.distance = stop
        sim.crossing_owners.update((leader.identifier, follower.identifier))
        sim.lights.phase = "amber"
        other = sim.spawn("E", "straight")
        other.distance = other.crossing[0]
        for step in range(200):
            occupied_before = bool(sim.crossing_owners)
            sim.advance(STEP)
            self.assert_gaps(sim)
            self.assertEqual(stopped.distance, stop)
            if occupied_before:
                self.assertEqual(other.distance, other.crossing[0])
            if other.identifier in sim.crossing_owners:
                break
        self.assertIn(other.identifier, sim.crossing_owners)
        self.assertNotIn(leader.identifier, sim.crossing_owners)
        self.assertNotIn(follower.identifier, sim.crossing_owners)

    def test_rescue_does_not_share_the_crossing_with_a_convoy(self):
        sim = Simulation(rate=0)
        leader, follower = self.queue(sim, "N", 2)
        sim.start_mission("01", "S")
        rescue = sim.get_rescue("01")
        rescue.distance = rescue.crossing[0]
        leader.distance = leader.crossing[0] + 2 * GAP
        follower.distance = follower.crossing[0] + GAP
        sim.crossing_owners.update((leader.identifier, follower.identifier))
        sim.advance(STEP)
        self.assertEqual(rescue.distance, rescue.crossing[0])
        self.assertNotIn(rescue.identifier, sim.crossing_owners)
        self.assertFalse(sim.can_share_crossing(leader, rescue))
        self.assert_gaps(sim)

    def test_rescue_waits_at_occupied_secondary_junction_then_continues(self):
        sim = Simulation(rate=0)
        sim.start_mission("01", "E")
        rescue = sim.get_rescue("01")
        stop, end, key = next(zone for zone in rescue.route.junctions if zone[2] == "B")
        rescue.distance = stop
        rescue.crossing_index = 1  # Le carrefour principal est deja franchi.
        blocker = sim.spawn("W", "straight")
        occupied = next(zone for zone in blocker.route.junctions if zone[2] == key)
        blocker.distance = occupied[0] + 50
        blocker.speed = 0
        sim.advance(2)
        self.assertEqual(rescue.distance, stop)
        self.assert_gaps(sim)
        sim.cars.remove(blocker)
        sim.advance(1)
        self.assertGreater(rescue.distance, stop)
        sim.advance(180)
        self.assertFalse(rescue.busy)
        self.assert_gaps(sim)


if __name__ == "__main__":
    unittest.main()
