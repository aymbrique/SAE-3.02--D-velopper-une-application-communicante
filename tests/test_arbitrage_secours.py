"""Arbitrage des deux secours face a face au carrefour principal."""

import unittest

from src.simulation.moteur import STEP, Simulation
from traffic_checks import assert_spacing


class RescueArbitrationTests(unittest.TestCase):
    def opposed_rescues(self, axis, older_id):
        sim = Simulation(rate=0)
        younger_id = "02" if older_id == "01" else "01"
        sim.start_mission(older_id, "S" if axis == "NS" else "W")
        sim.time = 30
        sim.start_mission(younger_id, "E")
        older = sim.get_rescue(older_id)
        younger = sim.get_rescue(younger_id)
        older.visited = True
        older.crossing_index = 1
        younger.visited = axis == "EW"
        younger.crossing_index = int(younger.visited)
        for rescue in (older, younger):
            rescue.distance = rescue.crossing[0]
        sim.lights.axis = axis
        return sim, older, younger

    def finish_in_order(self, sim, first, second):
        first_end = first.crossing[1]
        second_stop = second.crossing[0]
        first_cleared = False
        for _ in range(400):
            sim.advance(STEP)
            assert_spacing(self, sim)
            if not first_cleared:
                self.assertEqual(sim.lights.owner.identifier, first.identifier)
                self.assertLessEqual(second.distance, second_stop)
            first_cleared |= first.distance >= first_end or not first.busy
            if second.identifier in sim.crossing_owners:
                self.assertTrue(first_cleared)
                self.assertEqual(sim.lights.owner.identifier, second.identifier)
                break
        else:
            self.fail("Le second secours n'a pas obtenu le passage apres le premier.")

    def test_oldest_mission_wins_on_both_axes_and_with_either_vehicle(self):
        for axis in ("NS", "EW"):
            for older_id in ("01", "02"):
                with self.subTest(axis=axis, older=older_id):
                    sim, older, younger = self.opposed_rescues(axis, older_id)
                    self.finish_in_order(sim, older, younger)

    def test_two_requests_reconsider_early_single_reservation(self):
        for axis in ("NS", "EW"):
            for older_id in ("01", "02"):
                with self.subTest(axis=axis, older=older_id):
                    sim, older, younger = self.opposed_rescues(axis, older_id)
                    older.distance -= 600  # Hors des deux seuils de demande.
                    younger.distance -= 160
                    sim.advance(STEP)
                    self.assertEqual(sim.lights.owner.identifier, younger.identifier)
                    self.assertFalse(sim.crossing_owners)
                    older.distance = older.crossing[0]
                    self.finish_in_order(sim, older, younger)

    def test_vehicle_already_inside_keeps_control_until_exit(self):
        for axis in ("NS", "EW"):
            with self.subTest(axis=axis):
                sim, older, younger = self.opposed_rescues(axis, "02")
                older.distance -= 600
                sim.advance(STEP)
                self.assertIn(younger.identifier, sim.crossing_owners)
                older.distance = older.crossing[0]
                self.finish_in_order(sim, younger, older)

    def test_returning_vehicle_releases_control_before_reaching_station(self):
        sim, older, younger = self.opposed_rescues("EW", "02")
        sim.advance(STEP)
        self.assertEqual(sim.lights.owner.identifier, older.identifier)
        end = older.crossing[1]
        older.distance = end - 1
        sim.advance(STEP)
        self.assertIsNone(older.crossing)
        sim.advance(STEP)
        self.assertTrue(older.busy)
        self.assertEqual(sim.lights.owner.identifier, younger.identifier)


if __name__ == "__main__":
    unittest.main()
