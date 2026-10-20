"""Sens du raccordement Est et mouvements des carrefours secondaires."""

from itertools import product
from math import hypot
import unittest

from src.models.layout import (
    CLEARANCE, DESTINATIONS, NODES, PARKING_X, PARKING_Y, ROAD_SEGMENTS,
    SCENE_HEIGHT, SCENE_WIDTH, SITE_ENTRANCES, STOP_DISTANCE, TURN_DISTANCE,
    build_route, car_route, direction, lane_point, rescue_route,
)


class RouteRulesTests(unittest.TestCase):
    def assert_legal_edges(self, route):
        allowed = {frozenset(edge) for edge in ROAD_SEGMENTS}
        allowed.add(frozenset(("depot", "F")))
        for side, entrance in SITE_ENTRANCES.items():
            allowed.add(frozenset((entrance, "site_" + side)))
        for first, second in zip(route.nodes, route.nodes[1:]):
            self.assertIn(frozenset((first, second)), allowed)
            self.assertNotEqual((first, second), ("Q", "R"))
        for movement in zip(route.nodes, route.nodes[1:], route.nodes[2:]):
            self.assertNotEqual(movement, ("E", "R", "Q"))

    def assert_movements_match_geometry(self, route):
        expected = {}
        for index, key in enumerate(route.nodes[1:-1], 1):
            if key == "C" or key.startswith("site_"):
                continue
            incoming = direction(NODES[route.nodes[index - 1]], NODES[key])
            outgoing = direction(NODES[key], NODES[route.nodes[index + 1]])
            expected.setdefault(key, []).append((incoming, outgoing))
        movement_keys = set()
        for stop, end, key in route.junctions:
            if key == "parking" or key.startswith("site_"):
                self.assertNotIn((stop, key), route.junction_movements)
                continue
            movement_keys.add((stop, key))
            incoming, outgoing = route.junction_movements[(stop, key)]
            self.assertEqual((incoming, outgoing), expected[key].pop(0))
            self.assertAlmostEqual(hypot(*incoming), 1)
            self.assertAlmostEqual(hypot(*outgoing), 1)
            for actual, wanted in zip(route.sample(stop)[:2],
                                      lane_point(NODES[key], incoming, -STOP_DISTANCE)):
                self.assertAlmostEqual(actual, wanted)
            for actual, wanted in zip(route.sample(end - CLEARANCE)[:2],
                                      lane_point(NODES[key], outgoing, TURN_DISTANCE)):
                self.assertAlmostEqual(actual, wanted)
        self.assertEqual(set(route.junction_movements), movement_keys)
        self.assertTrue(all(not movements for movements in expected.values()))

    def test_all_twelve_car_routes_follow_allowed_roads_and_leave_at_edges(self):
        for origin, turn in product("NSEW", ("straight", "left", "right")):
            with self.subTest(origin=origin, turn=turn):
                route, stop = car_route(origin, turn)
                self.assertIsInstance(route.nodes, tuple)
                self.assertEqual(route.nodes.count("C"), 1)
                self.assertEqual(stop, route.crossings[0][0])
                self.assert_legal_edges(route)
                self.assert_movements_match_geometry(route)
                for x, y in (route.points[0], route.points[-1]):
                    self.assertTrue(x < 0 or x > SCENE_WIDTH or y < 0 or y > SCENE_HEIGHT)

    def test_southbound_cars_continue_on_lower_road_to_east_edge(self):
        for origin, turn in (("N", "straight"), ("W", "right"), ("E", "left")):
            with self.subTest(origin=origin, turn=turn):
                route, _ = car_route(origin, turn)
                self.assertEqual(route.nodes[-4:], ("C", "D", "Q", "low_east"))
                self.assertGreater(route.points[-1][0], SCENE_WIDTH)
                self.assertNotIn("R", route.nodes)

    def test_rescue_routes_preserve_destinations_parking_and_allowed_directions(self):
        for (identifier, parking_y), destination in product(PARKING_Y.items(), DESTINATIONS):
            with self.subTest(identifier=identifier, destination=destination):
                route, crossings, hospital = rescue_route(identifier, parking_y, destination)
                self.assertEqual(route.nodes[0], "depot")
                self.assertEqual(route.nodes[-1], "depot")
                self.assertEqual(route.nodes.count("site_" + destination), 1)
                self.assertEqual(route.points[0], (PARKING_X, parking_y))
                self.assertEqual(route.points[-1], (PARKING_X, parking_y))
                self.assertEqual(len(crossings), 2)
                self.assertIsNotNone(hospital)
                self.assert_legal_edges(route)
                self.assert_movements_match_geometry(route)
                # Le retour F et l'allee de stationnement partagent leur distance
                # d'entree ; le nom fait partie de la cle pour les distinguer.
                returning_f = [zone for zone in route.junctions if zone[2] == "F"][-1]
                self.assertIn((returning_f[0], "F"), route.junction_movements)
                self.assertIn((returning_f[0], route.length, "parking"), route.junctions)

    def test_permitted_west_to_south_branch_keeps_its_turn_direction(self):
        route = build_route("Raccordement vers le bas", ["B", "R", "Q", "low_east"])
        self.assert_legal_edges(route)
        self.assert_movements_match_geometry(route)
        stop, _, key = next(zone for zone in route.junctions if zone[2] == "R")
        self.assertEqual(route.junction_movements[(stop, key)], ((1, 0), (0, 1)))

    def test_forbidden_branch_directions_are_rejected_when_building_routes(self):
        for nodes, reason in ((["low_east", "Q", "R", "E"], "Sens interdit"),
                              (["east", "E", "R", "Q", "low_east"], "Virage interdit")):
            with self.subTest(nodes=nodes):
                with self.assertRaisesRegex(ValueError, reason):
                    build_route("Trajet interdit", nodes)

    def test_west_to_east_straight_branch_is_still_allowed(self):
        route = build_route("Raccordement tout droit", ["B", "R", "E"])
        self.assert_legal_edges(route)
        self.assert_movements_match_geometry(route)
        stop, _, key = next(zone for zone in route.junctions if zone[2] == "R")
        self.assertEqual(route.junction_movements[(stop, key)], ((1, 0), (1, 0)))


if __name__ == "__main__":
    unittest.main()
