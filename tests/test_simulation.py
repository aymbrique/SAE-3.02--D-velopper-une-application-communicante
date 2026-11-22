"""Cycle des feux, compensation et départ d'un secours."""

import unittest

from src.simulation.feux import DemandePriorite, Feux
from src.simulation.moteur import Simulation


def avancer_feux(feux, duree, demandes=(), libre=True):
    """Fait passer la durée demandée sans attendre en temps réel."""
    for _ in range(round(duree / 0.05)):
        feux.avancer(0.05, demandes, libre=libre)


class TestsSimulation(unittest.TestCase):
    """Vérifie les feux et le déroulement d'une mission."""

    def test_cycle_feux(self):
        """Le feu opposé attend que le carrefour soit libre."""
        feux = Feux()
        avancer_feux(feux, 8)
        self.assertEqual(feux.signal("NS"), "orange")
        avancer_feux(feux, 1)
        self.assertEqual(feux.phase, "tout_rouge")
        avancer_feux(feux, 2, libre=False)
        self.assertEqual(feux.phase, "tout_rouge")
        avancer_feux(feux, 0.05)
        self.assertEqual(feux.signal("EO"), "vert")

    def test_compensation(self):
        """Douze secondes de retard donnent trois secondes de vert en plus."""
        feux = Feux()
        demande = DemandePriorite("01", "NS", 0, 0)
        avancer_feux(feux, 20, [demande])
        self.assertAlmostEqual(feux.reserve_temps["EO"], 12)
        avancer_feux(feux, 2.05)
        self.assertEqual(feux.signal("EO"), "vert")
        self.assertAlmostEqual(feux.bonus_compensation, 3)

    def test_mission(self):
        """Le camion devient occupé au départ et disponible à son retour."""
        simulation = Simulation(debit=0)
        camion = simulation.obtenir_secours("01")
        self.assertTrue(simulation.demarrer_mission("01", "S"))
        self.assertTrue(camion.occupe)
        self.assertEqual(simulation.recuperer_evenements(), [("01", "occupe")])

        simulation.avancer(240)
        self.assertFalse(camion.occupe)
        self.assertEqual(simulation.recuperer_evenements(), [("01", "disponible")])
