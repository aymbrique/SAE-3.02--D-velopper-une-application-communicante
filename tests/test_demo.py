"""Tests du scénario visuel, sans interface graphique ni dépendance réseau."""

import unittest
from itertools import combinations
from math import hypot

from src.models.route import Route
from src.simulation.demo import DemoScenario, car_route


class RouteTests(unittest.TestCase):
    def test_interpolation_orientation_and_clamping(self):
        route = Route("Angle", ((0, 0), (10, 0), (10, 10)))
        self.assertEqual(route.sample(-5), (0, 0, 0))
        self.assertEqual(route.sample(5), (5, 0, 0))
        self.assertEqual(route.sample(15), (10, 5, 90))
        self.assertEqual(route.sample(25), (10, 10, 90))

    def test_all_turns_begin_and_end_on_road_edges(self):
        for origin in ("N", "E", "S", "W"):
            for turn in ("straight", "left", "right"):
                with self.subTest(origin=origin, turn=turn):
                    route, stop = car_route(origin, turn)
                    self.assertGreater(stop, 0)
                    self.assertLess(stop, route.length)
                    for x, y in (route.points[0], route.points[-1]):
                        self.assertTrue(x in (25, 1075) or y in (25, 835))
                    self.assertTrue(all(0 <= x <= 1100 and 0 <= y <= 860
                                        for x, y in route.points))

    def test_degenerate_route_is_rejected(self):
        with self.assertRaises(ValueError):
            Route("Vide", ((0, 0),))
        with self.assertRaises(ValueError):
            Route("Doublon", ((0, 0), (0, 0)))


class DemoTests(unittest.TestCase):
    def setUp(self):
        self.scenario = DemoScenario()

    def test_light_transition_boundaries(self):
        for time, expected in ((0, ("green", "red")), (8, ("amber", "red")),
                               (9, ("red", "red")), (10, ("red", "green")),
                               (18, ("red", "amber")), (19, ("red", "red")),
                               (20, ("green", "red"))):
            with self.subTest(time=time):
                frame = self.scenario.frame_at(time)
                self.assertEqual((frame.north_south, frame.east_west), expected)
                self.assertGreater(frame.phase_remaining, 0)

    def test_waiting_car_holds_position_then_leaves(self):
        track = next(track for track in self.scenario.tracks if track.identifier == "C03")
        before = track.state_at(8)
        waiting = track.state_at(10)
        after = track.state_at(11)
        self.assertEqual((before.x, before.y), (waiting.x, waiting.y))
        self.assertTrue(waiting.waiting)
        self.assertNotEqual((waiting.x, waiting.y), (after.x, after.y))

    def test_rescue_states_are_separate_and_return_to_parking(self):
        initial = self.scenario.frame_at(0).rescues
        self.assertTrue(all(not vehicle.busy for vehicle in initial))
        self.assertEqual([vehicle.busy for vehicle in self.scenario.frame_at(5).rescues], [True, False])
        self.assertTrue(all(vehicle.busy for vehicle in self.scenario.frame_at(24).rescues))
        self.assertEqual([vehicle.busy for vehicle in self.scenario.frame_at(30).rescues], [False, True])
        parked = self.scenario.frame_at(50).rescues
        self.assertTrue(all(not vehicle.busy for vehicle in parked))
        self.assertEqual([(vehicle.x, vehicle.y) for vehicle in initial],
                         [(vehicle.x, vehicle.y) for vehicle in parked])

    def test_ten_minutes_remain_bounded_and_repeat_correctly(self):
        previous_completed = 0
        for step in range(2401):
            frame = self.scenario.frame_at(step / 4)
            self.assertLessEqual(len(frame.cars), 25)
            self.assertEqual(len(frame.rescues), 2)
            self.assertGreaterEqual(frame.completed, previous_completed)
            previous_completed = frame.completed
            for vehicle in frame.vehicles:
                self.assertTrue(0 <= vehicle.x <= 1100 and 0 <= vehicle.y <= 860)
                self.assertTrue(0 <= vehicle.progress <= 1)
        for track in self.scenario.tracks:
            first, repeated = track.state_at(track.offset + 1), track.state_at(track.offset + track.period + 1)
            self.assertEqual((first.x, first.y, first.heading), (repeated.x, repeated.y, repeated.heading))

    def test_scripted_paths_keep_a_visual_gap(self):
        # Contrôler les croisements de la chronologie, sans ajouter un moteur
        # d'évitement au programme. Les véhicules ont des dimensions fixes.
        for step in range(3201):
            time = step / 40
            for first, second in combinations(self.scenario.frame_at(time).vehicles, 2):
                distance = hypot(first.x - second.x, first.y - second.y)
                self.assertGreaterEqual(distance, 32,
                                        f"Chevauchement à {time}s : {first.identifier}, {second.identifier}")


if __name__ == "__main__":
    unittest.main()
