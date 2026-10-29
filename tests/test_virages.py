"""Virages rapides sans perdre l'espacement ni les controles de conflit."""

from itertools import combinations, product
from math import hypot
import unittest

from src.simulation.moteur import DISTANCE_SECURITE, PAS_TEMPS, Simulation


class TestsVirages(unittest.TestCase):
    def verifier_distances(self, simulation):
        for premier, second in combinations(simulation.vehicules, 2):
            self.assertGreaterEqual(hypot(premier.position[0] - second.position[0],
                                         premier.position[1] - second.position[1]), DISTANCE_SECURITE - 1e-6)

    def test_chaque_virage_degage_pendant_un_vert_normal(self):
        for origine, virage in product("NSEW", ("left", "right")):
            with self.subTest(origine=origine, virage=virage):
                simulation = Simulation(debit=0)
                simulation.feux.axe = "NS" if origine in "NS" else "EW"
                voiture = simulation.ajouter_voiture(origine, virage)
                arret, fin, _ = voiture.passage
                voiture.distance = arret
                for _ in range(150):  # 7,5 s, avant l'orange de 8 s.
                    simulation.avancer(PAS_TEMPS)
                    self.verifier_distances(simulation)
                    if voiture.distance >= fin:
                        break
                self.assertGreaterEqual(voiture.distance, fin)
                self.assertEqual(simulation.feux.signal(simulation.feux.axe), "green")

    def test_convoi_meme_virage_suit_avant_sortie_de_tete(self):
        for virage in ("left", "right"):
            with self.subTest(virage=virage):
                simulation = Simulation(debit=0)
                tete = simulation.ajouter_voiture("N", virage)
                tete.distance = tete.passage[0] + 70
                simulation.vehicules_engages.add(tete.identifiant)
                suivante = simulation.ajouter_voiture("N", virage)
                suivante.distance = suivante.passage[0]
                self.assertTrue(simulation.passages_compatibles(tete, suivante))
                simulation.avancer(PAS_TEMPS)
                self.assertEqual(simulation.vehicules_engages, {tete.identifiant, suivante.identifiant})
                for _ in range(150):
                    simulation.avancer(PAS_TEMPS)
                    self.verifier_distances(simulation)
                self.assertIsNone(tete.passage)
                self.assertIsNone(suivante.passage)

    def test_acceleration_virage_ne_deplace_pas_vehicules_arretes(self):
        simulation = Simulation(debit=0)
        voiture = simulation.ajouter_voiture("N", "left")
        voiture.distance = voiture.trajet.zones_virage[0][0] + 10
        simulation.vehicules_engages.add(voiture.identifiant)
        voiture.vitesse = 0
        avant = voiture.distance
        simulation.avancer(1)
        self.assertEqual(voiture.distance, avant)

    def test_virages_secondaires_rares_finissent_sans_blocage(self):
        for origine, variante, cle in (("N", "lower_west", "D"),
                                     ("W", "middle_north", "B")):
            with self.subTest(variante=variante):
                simulation = Simulation(debit=0)
                voiture = simulation.ajouter_voiture(origine, "straight", variante=variante)
                arret, fin, _ = next(zone for zone in voiture.trajet.raccordements if zone[2] == cle)
                voiture.distance = arret
                voiture.indice_passage = 1
                for _ in range(150):
                    simulation.avancer(PAS_TEMPS)
                    self.verifier_distances(simulation)
                    if voiture.distance >= fin:
                        break
                self.assertGreaterEqual(voiture.distance, fin)
                simulation.avancer(60)
                self.assertEqual(simulation.trajets_termines, 1)


if __name__ == "__main__":
    unittest.main()
