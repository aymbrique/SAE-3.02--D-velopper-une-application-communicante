"""Arbitrage des deux secours face a face au carrefour principal."""

import unittest

from src.simulation.moteur import PAS_TEMPS, Simulation
from controles_circulation import verifier_espacement


class TestsArbitrageSecours(unittest.TestCase):
    def preparer_secours_opposes(self, axe, identifiant_ancien):
        simulation = Simulation(debit=0)
        identifiant_recent = "02" if identifiant_ancien == "01" else "01"
        simulation.demarrer_mission(identifiant_ancien, "S" if axe == "NS" else "W")
        simulation.temps = 30
        simulation.demarrer_mission(identifiant_recent, "E")
        ancien = simulation.obtenir_secours(identifiant_ancien)
        recent = simulation.obtenir_secours(identifiant_recent)
        ancien.intervention_effectuee = True
        ancien.indice_passage = 1
        recent.intervention_effectuee = axe == "EW"
        recent.indice_passage = int(recent.intervention_effectuee)
        for secours in (ancien, recent):
            secours.distance = secours.passage[0]
        simulation.feux.axe = axe
        return simulation, ancien, recent

    def terminer_dans_ordre(self, simulation, premier, second):
        fin_premier = premier.passage[1]
        arret_second = second.passage[0]
        premier_degage = False
        for _ in range(400):
            simulation.avancer(PAS_TEMPS)
            verifier_espacement(self, simulation)
            if not premier_degage:
                self.assertEqual(simulation.feux.prioritaire.identifiant, premier.identifiant)
                self.assertLessEqual(second.distance, arret_second)
            premier_degage |= premier.distance >= fin_premier or not premier.occupe
            if second.identifiant in simulation.vehicules_engages:
                self.assertTrue(premier_degage)
                self.assertEqual(simulation.feux.prioritaire.identifiant, second.identifiant)
                break
        else:
            self.fail("Le second secours n'a pas obtenu le passage apres le premier.")

    def test_mission_plus_ancienne_prioritaire_sur_chaque_axe(self):
        for axe in ("NS", "EW"):
            for identifiant_ancien in ("01", "02"):
                with self.subTest(axe=axe, ancien=identifiant_ancien):
                    simulation, ancien, recent = self.preparer_secours_opposes(axe, identifiant_ancien)
                    self.terminer_dans_ordre(simulation, ancien, recent)

    def test_deux_demandes_reexaminent_reservation_precoce(self):
        for axe in ("NS", "EW"):
            for identifiant_ancien in ("01", "02"):
                with self.subTest(axe=axe, ancien=identifiant_ancien):
                    simulation, ancien, recent = self.preparer_secours_opposes(axe, identifiant_ancien)
                    ancien.distance -= 600  # Hors des deux seuils de demande.
                    recent.distance -= 160
                    simulation.avancer(PAS_TEMPS)
                    self.assertEqual(simulation.feux.prioritaire.identifiant, recent.identifiant)
                    self.assertFalse(simulation.vehicules_engages)
                    ancien.distance = ancien.passage[0]
                    self.terminer_dans_ordre(simulation, ancien, recent)

    def test_secours_deja_engage_garde_priorite_jusqu_a_sortie(self):
        for axe in ("NS", "EW"):
            with self.subTest(axe=axe):
                simulation, ancien, recent = self.preparer_secours_opposes(axe, "02")
                ancien.distance -= 600
                simulation.avancer(PAS_TEMPS)
                self.assertIn(recent.identifiant, simulation.vehicules_engages)
                ancien.distance = ancien.passage[0]
                self.terminer_dans_ordre(simulation, recent, ancien)

    def test_retour_libere_feux_avant_caserne(self):
        simulation, ancien, recent = self.preparer_secours_opposes("EW", "02")
        simulation.avancer(PAS_TEMPS)
        self.assertEqual(simulation.feux.prioritaire.identifiant, ancien.identifiant)
        fin = ancien.passage[1]
        ancien.distance = fin - 1
        simulation.avancer(PAS_TEMPS)
        self.assertIsNone(ancien.passage)
        simulation.avancer(PAS_TEMPS)
        self.assertTrue(ancien.occupe)
        self.assertEqual(simulation.feux.prioritaire.identifiant, recent.identifiant)


if __name__ == "__main__":
    unittest.main()
