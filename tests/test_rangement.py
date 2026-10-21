"""Les voitures se rangent, s'arretent, puis reprennent apres les secours."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from itertools import combinations
import unittest
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath, QPolygonF

from src.simulation.moteur import GAP, STEP, Simulation
from src.simulation.priorite import PULL_OVER, corners


class RangementTests(unittest.TestCase):
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
        car.distance = car.crossing[0] - 60
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
                    if car.yielding_to and car.lateral_offset >= PULL_OVER - .01:
                        stopped_beside = True
                        self.assertEqual(car.distance, initial)
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
        self.assertLess(frame_car.x, original[0] - 20)
        self.assertAlmostEqual(frame_car.y, original[1])
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
