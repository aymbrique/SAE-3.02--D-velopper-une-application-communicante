"""Le stationnement en intervention ne reserve pas les feux du retour."""

import unittest

from src.modeles.plan import DESTINATIONS, on_road
from src.simulation.moteur import DWELL, STEP, Simulation
from traffic_checks import assert_spacing


class ParkingPriorityTests(unittest.TestCase):
    def parked_rescue(self, destination, identifier="01"):
        sim = Simulation(rate=0)
        sim.start_mission(identifier, destination)
        rescue = sim.get_rescue(identifier)
        rescue.distance = rescue.hospital
        rescue.crossing_index = 1
        rescue.visited = True
        rescue.dwell_remaining = DWELL
        return sim, rescue

    def test_no_return_request_while_still_driving_to_intervention(self):
        for destination in DESTINATIONS:
            with self.subTest(destination=destination):
                sim, rescue = self.parked_rescue(destination)
                rescue.visited = False
                rescue.dwell_remaining = 0
                # Apres la sortie du carrefour, le prochain passage est le
                # retour, mais le secours doit d'abord atteindre le patient.
                start = rescue.crossings[0][1]
                for distance in range(int(start) + 1, int(rescue.hospital), 5):
                    rescue.distance = distance
                    self.assertEqual(sim.requests(), [], (destination, distance))

    def test_parked_rescue_neither_holds_lights_nor_increases_debt(self):
        for destination in DESTINATIONS:
            with self.subTest(destination=destination):
                sim, rescue = self.parked_rescue(destination)
                sim.lights.axis = rescue.crossing[2]
                sim.lights.elapsed = 12
                sim.lights.debt.update(NS=3, EW=0)
                debt = dict(sim.lights.debt)
                for _ in range(round(DWELL / STEP)):
                    self.assertEqual(sim.requests(), [])
                    sim.advance(STEP)
                    self.assertIsNone(sim.lights.owner)
                    self.assertEqual(rescue.distance, rescue.hospital)
                    for axis in debt:
                        self.assertLessEqual(sim.lights.debt[axis], debt[axis])
                self.assertTrue(rescue.busy)

    def test_return_requests_only_back_on_road_and_near_crossing(self):
        for destination in DESTINATIONS:
            with self.subTest(destination=destination):
                sim, rescue = self.parked_rescue(destination)
                rescue.dwell_remaining = 0
                saw_driveway = saw_road = saw_request = False
                # Parcourir tout le retour au carrefour, y compris l'allee.
                for distance in range(int(rescue.hospital) + 1, int(rescue.crossing[0])):
                    rescue.distance = distance
                    road = on_road(*rescue.position[:2])
                    metres, eta = sim.approach(rescue)
                    expected = road and (metres <= 150 or eta <= 10)
                    requests = sim.requests()
                    self.assertEqual(bool(requests), expected, (destination, distance))
                    saw_driveway |= not road
                    saw_road |= road
                    saw_request |= bool(requests)
                    if requests:
                        self.assertEqual(requests[0].started_at, rescue.started_at)
                self.assertTrue(saw_driveway and saw_road and saw_request)

    def test_second_rescue_passes_while_older_mission_is_parked_at_town_hall(self):
        for parked_id in ("01", "02"):
            for returning in (False, True):
                with self.subTest(parked=parked_id, second_returning=returning):
                    sim, parked = self.parked_rescue("W", parked_id)
                    sim.time = 30
                    second_id = "02" if parked_id == "01" else "01"
                    sim.start_mission(second_id, "E")
                    second = sim.get_rescue(second_id)
                    second.visited = returning
                    second.crossing_index = int(returning)
                    second.distance = second.crossing[0]
                    sim.lights.axis = "EW"
                    for _ in range(140):
                        sim.advance(STEP)
                        assert_spacing(self, sim)
                        self.assertGreater(parked.dwell_remaining, 0)
                        self.assertEqual(parked.distance, parked.hospital)
                        self.assertEqual(sim.lights.owner.identifier, second_id)
                        if second.identifier in sim.crossing_owners:
                            self.assertEqual(sim.lights.signal(second.crossing[2]), "green")
                            break
                    else:
                        self.fail("Le secours gare a empeche le second de passer.")


if __name__ == "__main__":
    unittest.main()
