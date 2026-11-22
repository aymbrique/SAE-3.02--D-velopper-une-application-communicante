"""Priorité des véhicules de secours au carrefour principal."""

import unittest

from src.simulation.feux import DemandePriorite, Feux


class TestsArbitrageSecours(unittest.TestCase):
    """Compare les demandes du camion et de l'ambulance."""

    def test_mission_ancienne(self):
        """Le camion est parti avant l'ambulance mais demande le passage après elle."""
        feux = Feux()
        camion = DemandePriorite("01", "NS", debut_mission=2, date_demande=9)
        ambulance = DemandePriorite("02", "EW", debut_mission=4, date_demande=7)

        feux.avancer(0.05, [ambulance, camion])
        self.assertEqual(feux.prioritaire.identifiant, "01")
        self.assertTrue(feux.priorite_verrouillee)

    def test_secours_engage(self):
        """L'ambulance déjà engagée termine avant de céder le passage au camion."""
        feux = Feux()
        ambulance = DemandePriorite("02", "NS", 5, 8, engage=True)
        camion = DemandePriorite("01", "EW", 1, 9)

        feux.avancer(0.05, [ambulance])
        feux.avancer(0.05, [camion, ambulance])
        self.assertEqual(feux.prioritaire.identifiant, "02")

        # L'ambulance est sortie : seule la demande du camion reste active.
        feux.avancer(0.05, [camion])
        self.assertEqual(feux.prioritaire.identifiant, "01")

    def test_missions_simultanees(self):
        """À début de mission égal, la première demande passe en premier."""
        feux = Feux()
        camion = DemandePriorite("01", "NS", 2, 9)
        ambulance = DemandePriorite("02", "EW", 2, 7)
        feux.avancer(0.05, [camion, ambulance])
        self.assertEqual(feux.prioritaire.identifiant, "02")

    def test_fin_priorite(self):
        """Les feux libèrent la priorité après le passage du dernier secours."""
        feux = Feux()
        camion = DemandePriorite("01", "NS", 1, 2, engage=True)
        feux.avancer(0.05, [camion])
        feux.avancer(0.05, [])
        self.assertIsNone(feux.prioritaire)
        self.assertFalse(feux.priorite_verrouillee)
