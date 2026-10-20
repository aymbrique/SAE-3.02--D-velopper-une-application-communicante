"""Files et passages compatibles aux raccordements sans feux."""

from itertools import combinations
from math import hypot
import unittest

from src.simulation.engine import GAP, STEP, Simulation


class SecondaryFlowTests(unittest.TestCase):
    def assert_gaps(self, sim):
        for first, second in combinations(sim.vehicles, 2):
            self.assertGreaterEqual(
                hypot(first.position[0] - second.position[0],
                      first.position[1] - second.position[1]),
                GAP - 1e-6, (sim.time, first.identifier, second.identifier))

    def zone(self, car, key):
        return next(zone for zone in car.route.junctions if zone[2] == key)

    def mark_previous_crossings(self, car):
        car.crossing_index = sum(end <= car.distance for _, end, _ in car.crossings)

    def advance_safely(self, sim, seconds):
        for _ in range(round(seconds / STEP)):
            sim.advance(STEP)
            self.assert_gaps(sim)

    def test_north_queue_reaches_red_light_instead_of_waiting_at_fire_station(self):
        sim = Simulation(rate=0)
        sim.lights.axis = "EW"  # Le feu Nord reste rouge pendant les 9 s observees.
        cars = []
        for index in range(6):
            car = sim.spawn("N", "straight")
            self.assertIsNotNone(car)
            if index < 4:
                car.distance = car.crossing[0] - index * GAP
            else:
                station_stop, _, _ = self.zone(car, "F")
                car.distance = station_stop - (index - 4) * GAP
            cars.append(car)
        initial = [car.distance for car in cars]
        self.advance_safely(sim, 9)
        for index, car in enumerate(cars):
            self.assertLessEqual(car.distance, car.crossing[0])
            self.assertAlmostEqual(car.distance, car.crossing[0] - index * GAP,
                                   delta=2 * car.speed * STEP)
        self.assertGreater(cars[4].distance - initial[4], 180)
        self.assertGreater(cars[5].distance - initial[5], 180)
        self.assertFalse(sim.crossing_owners)
        self.assertEqual(sim.lights.signal("NS"), "red")

    def test_opposite_straight_traffic_passes_fire_station_together(self):
        sim = Simulation(rate=0)
        north = sim.spawn("N", "straight")
        north.distance = self.zone(north, "F")[0]
        south = sim.spawn("S", "straight")
        south.distance = self.zone(south, "F")[0] + 30
        self.mark_previous_crossings(south)
        initial = (north.distance, south.distance)
        self.advance_safely(sim, 1)
        for car, previous in zip((north, south), initial):
            self.assertAlmostEqual(car.distance - previous, car.speed)
            self.assertFalse(car.waiting)

    def test_followers_enter_secondary_turns_before_leader_has_left_zone(self):
        for origin, key in (("N", "F"), ("E", "U"), ("E", "B"), ("S", "D")):
            with self.subTest(origin=origin, junction=key):
                sim = Simulation(rate=0)
                leader = sim.spawn(origin, "straight")
                stop, end, _ = self.zone(leader, key)
                leader.distance = stop + 70
                follower = sim.spawn(origin, "straight")
                follower.distance = stop - 1
                for car in (leader, follower):
                    self.mark_previous_crossings(car)
                initial = (leader.distance, follower.distance)
                self.advance_safely(sim, 1)
                self.assertLess(leader.distance, end)
                self.assertGreater(follower.distance, stop)
                for car, previous in zip((leader, follower), initial):
                    self.assertAlmostEqual(car.distance - previous, car.speed)
                    self.assertFalse(car.waiting)

    def test_green_convoy_continues_through_west_junction_after_main_crossing(self):
        sim = Simulation(rate=0)
        sim.lights.axis = "EW"
        cars = []
        for index in range(3):
            car = sim.spawn("E", "straight")
            car.distance = car.crossing[0] - index * GAP
            cars.append(car)
        self.advance_safely(sim, 15)
        for car in cars:
            stop, end, _ = self.zone(car, "W")
            self.assertIsNone(car.crossing)
            self.assertLess(stop, car.distance)
            self.assertLess(car.distance, end)
            self.assertFalse(car.waiting)

    def test_fire_station_yields_to_rescue_then_restarts_as_soon_as_it_is_clear(self):
        sim = Simulation(rate=0)
        sim.start_mission("02", "S")
        rescue = sim.get_rescue("02")
        rescue_stop, rescue_end, _ = self.zone(rescue, "F")
        rescue.distance = rescue_stop
        car = sim.spawn("N", "straight")
        car_stop, _, _ = self.zone(car, "F")
        car.distance = car_stop
        sim.advance(STEP)
        self.assertGreater(rescue.distance, rescue_stop)
        self.assertEqual(car.distance, car_stop)
        for _ in range(200):
            if rescue.distance >= rescue_end:
                break
            sim.advance(STEP)
            self.assert_gaps(sim)
            if rescue.distance < rescue_end:
                self.assertEqual(car.distance, car_stop)
        self.assertGreaterEqual(rescue.distance, rescue_end)
        sim.advance(STEP)
        self.assertGreater(car.distance, car_stop)
        self.assert_gaps(sim)

    def test_compatible_stationary_leader_still_enforces_physical_gap(self):
        sim = Simulation(rate=0)
        leader = sim.spawn("N", "straight")
        stop, _, _ = self.zone(leader, "F")
        leader.distance = stop + GAP
        leader.speed = 0
        follower = sim.spawn("N", "straight")
        follower.distance = stop
        self.advance_safely(sim, 1)
        self.assertEqual(follower.distance, stop)
        self.assertTrue(follower.waiting)

    def test_rescue_can_follow_a_moving_car_already_clear_of_main_crossing(self):
        for moving in (False, True):
            with self.subTest(moving=moving):
                sim = Simulation(rate=0)
                sim.start_mission("02", "W")
                rescue = sim.get_rescue("02")
                rescue.distance = rescue.crossing[0]
                car = sim.spawn("E", "straight")
                car.distance = car.crossing[1] + 70
                self.mark_previous_crossings(car)
                if not moving:
                    car.speed = 0
                stop = rescue.distance
                sim.advance(STEP)
                self.assert_gaps(sim)
                if moving:
                    self.assertGreater(rescue.distance, stop)
                    self.assertIn(rescue.identifier, sim.crossing_owners)
                else:
                    self.assertEqual(rescue.distance, stop)
                    self.assertNotIn(rescue.identifier, sim.crossing_owners)

    def test_returning_rescue_ignores_cars_past_conflict_but_waits_for_real_obstacle(self):
        for positions in ((240, 285), (195,)):
            with self.subTest(north_car_y=positions):
                sim = Simulation(rate=0)
                sim.lights.axis = "EW"
                sim.start_mission("02", "W")
                rescue = sim.get_rescue("02")
                rescue.visited = True
                rescue.crossing_index = len(rescue.crossings)
                stop, _, _ = [zone for zone in rescue.route.junctions if zone[2] == "F"][-1]
                rescue.distance = stop
                cars = []
                for y in positions:
                    car = sim.spawn("N", "straight")
                    station_stop, _, _ = self.zone(car, "F")
                    station_y = car.route.sample(station_stop)[1]
                    car.distance = station_stop + y - station_y
                    car.speed = 0
                    cars.append(car)
                self.advance_safely(sim, 1)
                if positions == (195,):
                    self.assertEqual(rescue.distance, stop)
                    self.assertTrue(rescue.waiting)
                    # Le vrai obstacle degage sa voie ; le secours reprend.
                    cars[0].speed = 28
                else:
                    self.assertGreater(rescue.distance, stop)
                    self.assertFalse(rescue.waiting)
                self.advance_safely(sim, 12)
                self.assertFalse(rescue.busy)

    def test_opposite_straight_and_right_turns_share_green_on_both_axes(self):
        for first_origin, second_origin, axis in (("N", "S", "NS"), ("E", "W", "EW")):
            for turns in (("straight", "right"), ("right", "straight"), ("right", "right")):
                with self.subTest(axis=axis, turns=turns):
                    sim = Simulation(rate=0)
                    sim.lights.axis = axis
                    first = sim.spawn(first_origin, turns[0])
                    first.distance = first.crossing[0]
                    second = sim.spawn(second_origin, turns[1])
                    second.distance = second.crossing[0]
                    self.assertTrue(sim.can_share_crossing(first, second))
                    sim.advance(STEP)
                    self.assertEqual(sim.crossing_owners, {first.identifier, second.identifier})
                    self.advance_safely(sim, 5)

    def test_left_turns_and_same_approach_turns_remain_exclusive(self):
        for first_origin, opposite_origin, axis in (("N", "S", "NS"), ("E", "W", "EW")):
            for first_turn, second_origin, second_turn in (
                    ("straight", opposite_origin, "left"),
                    ("right", first_origin, "straight"),
                    ("left", first_origin, "straight")):
                with self.subTest(axis=axis, first=first_turn,
                                  second_origin=second_origin, second=second_turn):
                    sim = Simulation(rate=0)
                    sim.lights.axis = axis
                    first = sim.spawn(first_origin, first_turn)
                    first.distance = first.crossing[0]
                    if second_origin == first_origin:
                        first.distance += 70
                        sim.crossing_owners.add(first.identifier)
                    second = sim.spawn(second_origin, second_turn)
                    second.distance = second.crossing[0]
                    self.assertFalse(sim.can_share_crossing(first, second))
                    sim.advance(STEP)
                    self.assertEqual(len(sim.crossing_owners), 1)
                    if second_origin == first_origin:
                        self.assertEqual(second.distance, second.crossing[0])
                    self.assert_gaps(sim)


if __name__ == "__main__":
    unittest.main()
