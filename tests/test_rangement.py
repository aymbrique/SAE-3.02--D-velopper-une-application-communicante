"""Les voitures se rangent, s'arretent, puis reprennent apres les secours."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from itertools import combinations
import unittest
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath, QPolygonF

from src.simulation.moteur import GAP, STEP, Simulation
from src.simulation.priorite import PULL_OVER, corners
from src.modeles.plan import on_road
from traffic_checks import assert_spacing


class RangementTests(unittest.TestCase):
    def test_opposite_lower_turns_finish_after_yielding_before_junction(self):
        for identifier in ("01", "02"):
            for variant in (None, "lower_west"):
                with self.subTest(rescue=identifier, variant=variant):
                    sim = Simulation(rate=0)
                    sim.start_mission(identifier, "S")
                    rescue = sim.get_rescue(identifier)
                    rescue.crossing_index = 1
                    stop = next(stop for stop, _, key in rescue.route.junctions if key == "D")
                    rescue.distance = stop - 300
                    car = sim.spawn("N", "straight", variant=variant)
                    car.crossing_index = 1
                    car_stop, car_end, _ = next(zone for zone in car.route.junctions if zone[2] == "D")
                    car.distance = car_stop - car.manoeuvre_length
                    for _ in range(1800):
                        sim.advance(STEP)
                        assert_spacing(self, sim)
                        self.assertTrue(all(on_road(x, y) for x, y in corners(car, car.position)))
                        if not rescue.busy and car.distance >= car.route.length:
                            break
                    self.assertGreater(car.distance, car_end)
                    self.assertFalse(rescue.busy)
                    self.assertGreaterEqual(car.distance, car.route.length)

    def test_rescue_waits_for_roadside_car_already_in_lower_junction(self):
        sim = Simulation(rate=0)
        sim.start_mission("01", "S")
        rescue = sim.get_rescue("01")
        rescue.crossing_index = 1
        stop, end, _ = next(zone for zone in rescue.route.junctions if zone[2] == "D")
        rescue.distance = stop - 100
        car = sim.spawn("N", "straight")
        car.crossing_index = 1
        car_stop, car_end, _ = next(zone for zone in car.route.junctions if zone[2] == "D")
        car.distance = car_stop + 10
        car.lateral_offset = PULL_OVER
        for _ in range(500):
            sim.advance(STEP)
            assert_spacing(self, sim)
        self.assertGreater(car.distance, car_end)
        self.assertGreater(rescue.distance, end)
        self.assertEqual(car.lateral_offset, 0)

    def test_pull_over_and_merge_keep_a_moderate_angle_inside_road(self):
        sim = Simulation(rate=0)
        car = sim.spawn("N", "straight")
        start = 350
        for first, last in ((0, PULL_OVER), (PULL_OVER, 0)):
            with self.subTest(offsets=(first, last)):
                car.manoeuvre_start = start
                car.manoeuvre_from = first
                car.manoeuvre_target = last
                previous_y = -float("inf")
                for step in range(101):
                    distance = start + car.manoeuvre_length * step / 100
                    x, y, heading = car.position_at(distance)
                    offset, _ = car.roadside_offset(distance)
                    self.assertLessEqual(abs(offset), 22)
                    self.assertLess(abs(heading - 90), 25)
                    self.assertGreater(y, previous_y)
                    self.assertTrue(all(on_road(px, py) for px, py in corners(car, (x, y, heading))))
                    previous_y = y

    def test_pull_over_near_lower_turn_keeps_clear_of_rescue(self):
        sim = Simulation(rate=0)
        sim.start_mission("01", "S")
        rescue = sim.get_rescue("01")
        rescue_stop = next(stop for stop, _, key in rescue.route.junctions if key == "D")
        rescue.distance = rescue_stop - 240
        sim.crossing_owners.add(rescue.identifier)
        cars = []
        for index in range(2):
            car = sim.spawn("N", "straight")
            stop = next(stop for stop, _, key in car.route.junctions if key == "D")
            car.distance = stop - 84 - 60 * index
            car.crossing_index = 1
            cars.append(car)
        max_offset = 0
        for _ in range(1800):
            sim.advance(STEP)
            self.assert_bodies_do_not_touch(sim)
            for car in cars:
                max_offset = max(max_offset, car.lateral_offset)
                self.assertLessEqual(car.lateral_offset, 22)
                self.assertTrue(all(on_road(x, y) for x, y in corners(car, car.position)))
            if not rescue.busy and all(car.distance >= car.route.length for car in cars):
                break
        self.assertEqual(max_offset, PULL_OVER)
        self.assertFalse(rescue.busy)
        self.assertTrue(all(car.distance >= car.route.length for car in cars))

    def assert_bodies_do_not_touch(self, simulation):
        for first, second in combinations(simulation.vehicles, 2):
            polygons = []
            for vehicle in (first, second):
                path = QPainterPath()
                path.addPolygon(QPolygonF([QPointF(x, y) for x, y in corners(vehicle, vehicle.position, 1)]))
                path.closeSubpath()
                polygons.append(path)
            self.assertFalse(polygons[0].intersects(polygons[1]),
                             (simulation.time, first.identifier, second.identifier))

    def prepared(self, origin="N", returning=False):
        sim = Simulation(rate=0)
        sim.start_mission("02", "W")
        rescue = sim.get_rescue("02")
        rescue.visited = returning
        rescue.crossing_index = int(returning)
        if returning:
            origin = "W"
        sim.lights.axis = rescue.crossing[2]
        rescue.distance = rescue.crossing[0] - 120
        car = sim.spawn(origin, "straight")
        car.distance = car.crossing[0] - car.manoeuvre_length
        rescue.distance = rescue.crossing[0] - car.manoeuvre_length - 120
        return sim, rescue, car

    def test_car_pulls_over_stops_and_returns_after_rescue(self):
        for returning in (False, True):
            with self.subTest(returning=returning):
                sim, rescue, car = self.prepared(returning=returning)
                initial = car.distance
                max_offset = 0
                stopped_beside = False
                moved_after = False
                for _ in range(300):
                    sim.advance(STEP)
                    self.assert_bodies_do_not_touch(sim)
                    max_offset = max(max_offset, car.lateral_offset)
                    if car.yielding_to and car.lateral_offset == PULL_OVER:
                        stopped_beside = True
                        self.assertAlmostEqual(car.distance, initial + car.manoeuvre_length)
                        self.assertTrue(car.waiting)
                        self.assertEqual(car.current_speed, 0)
                    if car.distance > initial and car.lateral_offset == 0:
                        moved_after = True
                        break
                self.assertEqual(max_offset, PULL_OVER)
                self.assertTrue(stopped_beside)
                self.assertTrue(moved_after)

    def test_distant_and_available_rescues_do_not_move_cars_to_roadside(self):
        sim = Simulation(rate=0)
        car = sim.spawn("N", "straight")
        car.distance = car.crossing[0] - 60
        sim.advance(1)
        self.assertEqual(car.lateral_offset, 0)
        self.assertFalse(car.yielding_to)

    def test_roadside_car_actually_changes_its_displayed_position(self):
        sim, rescue, car = self.prepared()
        original = car.position
        sim.advance(1)
        frame_car = next(v for v in sim.frame().cars if v.identifier == car.identifier)
        self.assertLess(frame_car.x, original[0])
        self.assertGreater(frame_car.y, original[1])
        self.assertNotEqual(frame_car.heading, original[2])
        self.assertIn("cote", frame_car.stage)
        self.assert_bodies_do_not_touch(sim)

    def test_following_straight_car_enters_while_leader_turns_and_slows(self):
        for turn in ("left", "right"):
            with self.subTest(turn=turn):
                sim = Simulation(rate=0)
                leader = sim.spawn("N", turn)
                leader.distance = leader.crossing[0] + 70
                sim.crossing_owners.add(leader.identifier)
                follower = sim.spawn("N", "straight")
                follower.distance = follower.crossing[0]
                sim.advance(STEP)
                self.assertIn(follower.identifier, sim.crossing_owners)
                self.assertIn(leader.identifier, sim.crossing_owners)
                self.assertGreater(follower.current_speed, 0)
                self.assertLess(follower.current_speed, follower.speed)
                for _ in range(200):
                    sim.advance(STEP)
                    self.assert_bodies_do_not_touch(sim)
                self.assertIsNone(follower.crossing)

    def test_merge_back_with_close_follower_keeps_both_cars_moving(self):
        sim = Simulation(rate=0)
        leader = sim.spawn("N", "straight")
        leader.distance = leader.crossing[0] - 100
        leader.lateral_offset = PULL_OVER
        follower = sim.spawn("N", "straight")
        follower.distance = leader.distance - 32
        initial = (leader.distance, follower.distance)
        for _ in range(160):
            sim.advance(STEP)
            self.assert_bodies_do_not_touch(sim)
        self.assertEqual(leader.lateral_offset, 0)
        self.assertGreater(leader.distance, initial[0] + 100)
        self.assertGreater(follower.distance, initial[1] + 100)

    def test_car_already_crossing_keeps_clearing_instead_of_parking(self):
        sim, rescue, car = self.prepared()
        car.distance = car.crossing[0] + 80
        car.lateral_offset = PULL_OVER
        sim.crossing_owners.add(car.identifier)
        end = car.crossing[1]
        for _ in range(160):
            sim.advance(STEP)
            self.assert_bodies_do_not_touch(sim)
            if car.distance >= end:
                break
            self.assertFalse(car.yielding_to)
            self.assertGreater(car.current_speed, 0)
        self.assertGreaterEqual(car.distance, end)


if __name__ == "__main__":
    unittest.main()
