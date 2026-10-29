"""Apparition hors des bords visibles et davantage de trafic venant du Nord."""

from collections import Counter
from itertools import product
import unittest

from src.modeles.plan import HAUTEUR_SCENE, LARGEUR_SCENE, trajet_voiture
from src.simulation.moteur import DISTANCE_SECURITE, Simulation


class TestsArrivees(unittest.TestCase):
    def test_trajets_commencent_et_finissent_hors_bords_visibles(self):
        for limites in ((0, 0, LARGEUR_SCENE, HAUTEUR_SCENE), (-350, -240, 1950, 1340)):
            for origine, virage in product("NSEW", ("straight", "left", "right")):
                with self.subTest(limites=limites, origine=origine, virage=virage):
                    trajet, arret = trajet_voiture(origine, virage, limites)
                    gauche, haut, droite, bas = limites
                    for x, y in (trajet.points[0], trajet.points[-1]):
                        self.assertTrue(x < gauche - 14 or x > droite + 14
                                        or y < haut - 14 or y > bas + 14, (x, y))
                    self.assertGreater(arret, 0)

    def test_arrivees_aux_bords_sans_insertion_dans_file(self):
        simulation = Simulation(debit=0)
        simulation.limites_circulation = (-350, -240, 1950, 1340)
        premier = simulation.ajouter_voiture("N", "straight")
        self.assertLess(premier.position[1] + 14, simulation.limites_circulation[1])
        self.assertIsNone(simulation.ajouter_voiture("N", "straight"))
        premier.distance = DISTANCE_SECURITE
        second = simulation.ajouter_voiture("N", "straight")
        self.assertIsNotNone(second)
        self.assertEqual(second.distance, 0)
        self.assertEqual(second.position[:2], second.trajet.points[0])

    def test_moitie_des_arrivees_vient_du_nord(self):
        simulation = Simulation(debit=0)
        nombres = Counter()
        for _ in range(12000):
            simulation.voitures.clear()
            nombres[simulation.ajouter_voiture().origine] += 1
        self.assertTrue(5700 < nombres["N"] < 6300, nombres)
        for origine in ("S", "E", "W"):
            self.assertTrue(1700 < nombres[origine] < 2300, nombres)

    def test_arrivees_nord_avec_choix_rares_ouest_et_est(self):
        simulation = Simulation(debit=0)
        nombres = Counter()
        for _ in range(6000):
            simulation.voitures.clear()
            voiture = simulation.ajouter_voiture("N")
            nombres[(voiture.virage, voiture.trajet.variante)] += 1
        # Les deux virages au feu restent a 2,5 % chacun.
        for virage in ("left", "right"):
            self.assertTrue(90 < sum(nombre for (mouvement, _), nombre in nombres.items()
                                     if mouvement == virage) < 220, nombres)
        # Le choix Ouest au carrefour du bas represente environ 5 % des tout droit.
        self.assertTrue(200 < nombres[("straight", "lower_west")] < 380, nombres)
        self.assertGreater(nombres[("straight", None)], 5000, nombres)

    def test_voitures_route_milieu_tournent_parfois_au_nord(self):
        simulation = Simulation(debit=0)
        nombres = Counter()
        for _ in range(6000):
            simulation.voitures.clear()
            voiture = simulation.ajouter_voiture("W")
            if voiture.virage == "straight":
                nombres[voiture.trajet.variante] += 1
        self.assertTrue(200 < nombres["middle_north"] < 380, nombres)
        self.assertGreater(nombres[None], 5000, nombres)

    def test_trajets_explicites_previsibles_et_variantes_possibles(self):
        simulation = Simulation(debit=0)
        par_defaut = simulation.ajouter_voiture("N", "straight")
        self.assertIsNone(par_defaut.trajet.variante)
        simulation.voitures.clear()
        ouest = simulation.ajouter_voiture("N", "straight", variante="lower_west")
        self.assertEqual(ouest.trajet.noeuds[-1], "low_west")
        simulation.voitures.clear()
        nord = simulation.ajouter_voiture("W", "straight", variante="middle_north")
        self.assertEqual(nord.trajet.noeuds[-1], "top")
