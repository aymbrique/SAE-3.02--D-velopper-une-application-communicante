"""Depart des secours au milieu d'une file Nord deja formee au rouge."""

from itertools import combinations
from math import hypot
import unittest
from traffic_checks import assert_spacing

from src.simulation.moteur import GAP, STEP, Simulation
from src.simulation.feux import Request


class StationDispatchTests(unittest.TestCase):
    def queued_north(self):
        sim = Simulation(rate=0)
        sim.lights.axis = "EW"
        cars = []
        for index in range(11):
            car = sim.spawn("N", "straight")
            self.assertIsNotNone(car)
            car.distance = car.crossing[0] - index * GAP
            car.waiting = True
            cars.append(car)
        station_stop = next(stop for stop, _, key in cars[0].route.junctions if key == "F")
        downstream = [car for car in cars if car.distance > station_stop]
        upstream = [car for car in cars if car.distance <= station_stop]
        self.assertGreater(len(downstream), 5)
        self.assertGreaterEqual(len(upstream), 2)
        return sim, cars, station_stop, downstream, upstream

    def step_safely(self, sim):
        before = [(vehicle, vehicle.distance, vehicle.crossing)
                  for vehicle in sim.vehicles]
        sim.advance(STEP)
        for vehicle, previous, crossing in before:
            if crossing and previous <= crossing[0] < vehicle.distance:
                self.assertEqual(sim.lights.signal(crossing[2]), "green",
                                 (sim.time, vehicle.identifier, "entree au rouge"))
        assert_spacing(self, sim)

    def first_station_zone(self, rescue):
        return next(zone for zone in rescue.route.junctions if zone[2] == "F")

    def test_each_dispatch_requests_north_south_before_normal_approach_threshold(self):
        for identifier in ("01", "02"):
            with self.subTest(rescue=identifier):
                sim, _, _, downstream, _ = self.queued_north()
                sim.start_mission(identifier, "W")
                rescue = sim.get_rescue(identifier)
                rescue.speed = 40  # Verifier le declenchement meme hors seuil usuel.
                metres, eta = sim.approach(rescue)
                self.assertGreater(metres, 150)
                self.assertGreater(eta, 10)
                previous = {car.identifier: car.distance for car in downstream}
                self.step_safely(sim)
                self.assertIsNotNone(sim.lights.owner)
                self.assertEqual(sim.lights.owner.identifier, identifier)
                self.assertEqual(sim.lights.owner.axis, "NS")
                # Conserver la transition orange/tout rouge avant de vider la file.
                self.assertEqual(sim.lights.signal("NS"), "red")
                for _ in range(60):
                    self.step_safely(sim)
                self.assertEqual(sim.lights.signal("NS"), "green")
                self.assertTrue(all(car.distance > previous[car.identifier] or car.lateral_offset > 0
                                    for car in downstream))

    def test_upstream_yields_while_existing_queue_drains_then_follows_rescue(self):
        for identifier in ("01", "02"):
            with self.subTest(rescue=identifier):
                sim, _, station_stop, downstream, upstream = self.queued_north()
                previous = {car.identifier: car.distance for car in downstream}
                sim.start_mission(identifier, "W")
                rescue = sim.get_rescue(identifier)
                _, station_end, _ = self.first_station_zone(rescue)
                for _ in range(800):
                    self.step_safely(sim)
                    if rescue.distance >= station_end:
                        break
                    self.assertTrue(all(car.distance <= station_stop + 1e-6
                                        for car in upstream))
                self.assertGreaterEqual(rescue.distance, station_end)
                self.assertLess(sim.time, 40)
                self.assertTrue(all(car.distance > previous[car.identifier] or car.lateral_offset > 0
                                    for car in downstream))
                for _ in range(100):
                    self.step_safely(sim)
                    if all(car.distance > station_stop for car in upstream):
                        break
                self.assertTrue(all(car.distance > station_stop for car in upstream))
                for _ in range(4000):
                    self.step_safely(sim)
                    if not rescue.busy:
                        break
                self.assertFalse(rescue.busy)

    def test_two_dispatched_rescues_both_finish_with_dense_north_queue(self):
        sim, _, station_stop, _, upstream = self.queued_north()
        sim.start_mission("01", "N")
        sim.start_mission("02", "E")
        self.step_safely(sim)
        self.assertIsNotNone(sim.lights.owner)
        self.assertEqual(sim.lights.owner.axis, "NS")
        station_exited = set()
        for _ in range(5000):
            self.step_safely(sim)
            for rescue in sim.rescues:
                _, end, _ = self.first_station_zone(rescue)
                if rescue.distance >= end or not rescue.busy:
                    station_exited.add(rescue.identifier)
            if len(station_exited) < len(sim.rescues):
                self.assertTrue(all(car.distance <= station_stop + 1e-6
                                    for car in upstream))
            if all(not rescue.busy for rescue in sim.rescues):
                break
        self.assertEqual(station_exited, {"01", "02"})
        self.assertTrue(all(not rescue.busy for rescue in sim.rescues))
        self.assertTrue(all(car.distance > station_stop for car in upstream))
        self.assertIn(("01", "disponible"), sim.events)
        self.assertIn(("02", "disponible"), sim.events)

    def test_rescue_uses_driveway_while_north_queue_drains_then_waits_at_road(self):
        for identifier in ("01", "02"):
            with self.subTest(rescue=identifier):
                sim, cars, _, _, _ = self.queued_north()
                sim.start_mission(identifier, "W")
                rescue = sim.get_rescue(identifier)
                rescue_stop, rescue_end, _ = self.first_station_zone(rescue)
                car_stop, car_end, _ = next(zone for zone in cars[0].route.junctions
                                           if zone[2] == "F")
                for _ in range(20):
                    self.step_safely(sim)
                # L'allee est libre meme si des voitures occupent encore la route.
                self.assertGreater(rescue.distance, 0)
                self.assertLess(rescue.distance, rescue_stop)
                self.assertTrue(any(car_stop < car.distance < car_end for car in cars))
                waited_at_road = False
                for _ in range(200):
                    self.step_safely(sim)
                    if abs(rescue.distance - rescue_stop) < 1e-6 and rescue.waiting:
                        waited_at_road = True
                        self.assertTrue(any(car_stop < car.distance < car_end for car in cars))
                        break
                self.assertTrue(waited_at_road)
                for _ in range(800):
                    self.step_safely(sim)
                    if rescue.distance >= rescue_end:
                        break
                self.assertGreaterEqual(rescue.distance, rescue_end)

    def test_return_from_main_crossing_requests_north_south_until_station_is_clear(self):
        for destination in ("W", "E", "N", "S"):
            with self.subTest(destination=destination):
                sim = Simulation(rate=0)
                sim.start_mission("01", destination)
                rescue = sim.get_rescue("01")
                rescue.visited = True
                rescue.crossing_index = 1
                _, end, axis = rescue.crossing
                rescue.distance = end - 1
                sim.crossing_owners.add(rescue.identifier)
                sim.lights.axis = axis
                sim.lights.owner = Request(rescue.identifier, axis, 0, 0)
                self.step_safely(sim)
                self.assertIsNone(rescue.crossing)
                requests = [request for request in sim.requests()
                            if request.identifier == rescue.identifier]
                self.assertEqual(len(requests), 1)
                self.assertEqual(requests[0].axis, "NS")
                self.step_safely(sim)
                self.assertEqual(sim.lights.owner.identifier, rescue.identifier)
                self.assertEqual(sim.lights.owner.axis, "NS")
                for _ in range(42):
                    self.step_safely(sim)
                self.assertEqual(sim.lights.signal("NS"), "green")
                self.assertTrue(rescue.busy)

    def test_returning_owner_hands_green_to_north_before_next_rescue_crosses_east_west(self):
        sim, _, _, _, _ = self.queued_north()
        sim.start_mission("01", "W")
        sim.start_mission("02", "E")
        first, second = sim.rescues
        for rescue in sim.rescues:
            rescue.visited = True
            rescue.crossing_index = 1
        first.distance = first.crossing[1] - 1
        second.distance = second.crossing[0]
        second_stop = second.distance
        sim.crossing_owners.add(first.identifier)
        sim.lights.axis = "EW"
        sim.lights.owner = Request(first.identifier, "EW", 0, 0)
        self.step_safely(sim)
        self.assertIsNone(first.crossing)
        self.assertEqual(second.distance, second_stop)
        self.step_safely(sim)
        self.assertEqual(sim.lights.owner.identifier, first.identifier)
        self.assertEqual(sim.lights.owner.axis, "NS")
        _, station_end, _ = [zone for zone in first.route.junctions if zone[2] == "F"][-1]
        cleared_station = False
        for _ in range(1000):
            self.step_safely(sim)
            if not first.busy or first.distance >= station_end:
                cleared_station = True
                break
            self.assertEqual(sim.lights.owner.identifier, first.identifier)
            self.assertEqual(sim.lights.owner.axis, "NS")
            self.assertEqual(second.distance, second_stop)
        self.assertTrue(cleared_station)
        for _ in range(4000):
            self.step_safely(sim)
            if all(not rescue.busy for rescue in sim.rescues):
                break
        self.assertTrue(all(not rescue.busy for rescue in sim.rescues))


if __name__ == "__main__":
    unittest.main()
