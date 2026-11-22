"""Arrivée des voitures et choix des trajets aux bords de la carte."""

import unittest

from src.modeles.plan import HAUTEUR_SCENE, LARGEUR_SCENE, trajet_voiture
from src.simulation.moteur import DISTANCE_SECURITE, Simulation


class TestsArrivees(unittest.TestCase):
    """Vérifie où apparaissent les voitures et quels chemins elles suivent."""

    def test_bords_trajets(self):
        """Chaque trajet commence et se termine hors de la carte."""
        for origine in ("N", "S", "E", "W"):
            for virage in ("straight", "left", "right"):
                with self.subTest(origine=origine, virage=virage):
                    trajet, arret = trajet_voiture(origine, virage)
                    self.assertGreater(arret, 0)
                    for x, y in (trajet.points[0], trajet.points[-1]):
                        hors_largeur = x < 0 or x > LARGEUR_SCENE
                        hors_hauteur = y < 0 or y > HAUTEUR_SCENE
                        self.assertTrue(hors_largeur or hors_hauteur)

    def test_arrivee_file(self):
        """Une seconde voiture apparaît seulement si son entrée est libre."""
        simulation = Simulation(debit=0)
        premiere = simulation.ajouter_voiture("N", "straight")
        self.assertIsNotNone(premiere)
        self.assertIsNone(simulation.ajouter_voiture("N", "straight"))

        premiere.distance = DISTANCE_SECURITE
        seconde = simulation.ajouter_voiture("N", "straight")
        self.assertIsNotNone(seconde)
        self.assertEqual(seconde.distance, 0)

    def test_choix_virage(self):
        """Sur une série reproductible, la majorité des voitures va tout droit."""
        simulation = Simulation(graine=302)
        choix = [simulation.choisir_virage() for _ in range(1000)]
        self.assertGreater(choix.count("straight"), 900)
        self.assertIn("left", choix)
        self.assertIn("right", choix)

    def test_variantes_trajets(self):
        """Les deux bifurcations mènent aux sorties prévues sur le plan."""
        ouest, _ = trajet_voiture("N", "straight", variante="lower_west")
        nord, _ = trajet_voiture("W", "straight", variante="middle_north")

        self.assertEqual(ouest.noeuds[-1], "low_west")
        self.assertEqual(nord.noeuds[-1], "top")
