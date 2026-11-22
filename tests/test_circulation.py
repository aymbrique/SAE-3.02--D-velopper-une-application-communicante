"""Passage des voitures au carrefour et distances de sécurité."""

import unittest

from controles_circulation import verifier_espacement
from src.simulation.moteur import DISTANCE_SECURITE, Simulation


class TestsCirculation(unittest.TestCase):
    """Vérifie trois situations que l'on peut observer sur la carte."""

    def test_arret_feu(self):
        """Une voiture s'arrête au rouge et repart au vert."""
        simulation = Simulation(debit=0)
        voiture = simulation.ajouter_voiture("E", "tout_droit")
        arret = voiture.passage[0]
        voiture.distance = arret - 2

        simulation.avancer(3)
        self.assertAlmostEqual(voiture.distance, arret)
        self.assertTrue(voiture.en_attente)
        simulation.avancer(10)
        self.assertGreater(voiture.distance, arret)

    def test_files_opposees(self):
        """Deux voitures allant tout droit en sens opposés passent ensemble."""
        simulation = Simulation(debit=0)
        nord = simulation.ajouter_voiture("N", "tout_droit")
        sud = simulation.ajouter_voiture("S", "tout_droit")
        nord.distance = nord.passage[0]
        sud.distance = sud.passage[0]

        simulation.avancer(0.5)
        self.assertIn(nord.identifiant, simulation.vehicules_engages)
        self.assertIn(sud.identifiant, simulation.vehicules_engages)
        verifier_espacement(self, simulation)

    def test_sortie_bloquee(self):
        """Même au vert, une voiture attend si la sortie est encombrée."""
        simulation = Simulation(debit=0)
        tete = simulation.ajouter_voiture("N", "tout_droit")
        tete.distance = tete.passage[1] + DISTANCE_SECURITE / 2
        tete.indice_passage = 1
        tete.vitesse = 0
        suivante = simulation.ajouter_voiture("N", "tout_droit")
        suivante.distance = suivante.passage[0]

        simulation.avancer(1)
        self.assertEqual(suivante.distance, suivante.passage[0])
        self.assertNotIn(suivante.identifiant, simulation.vehicules_engages)
