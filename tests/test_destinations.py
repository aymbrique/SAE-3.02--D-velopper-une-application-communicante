"""Destinations, probabilites et partage du carrefour."""

from collections import Counter
from itertools import combinations, product
import unittest
from controles_circulation import verifier_espacement

from src.modeles.plan import DESTINATIONS, POINTS_INTERVENTION, PARKING_X, PARKING_Y, trajet_secours
from src.simulation.moteur import Simulation


class TestsDestinations(unittest.TestCase):
    def test_tout_droit_opposes_passent_ensemble_sur_chaque_axe(self):
        for premier, second, axe in (("N", "S", "NS"), ("E", "W", "EW")):
            with self.subTest(axe=axe):
                simulation = Simulation(debit=0)
                simulation.feux.axe = axe
                a = simulation.ajouter_voiture(premier, "straight")
                b = simulation.ajouter_voiture(second, "straight")
                for voiture in (a, b):
                    voiture.distance = voiture.passage[0]
                simulation.avancer(.5)
                self.assertEqual(simulation.vehicules_engages, {a.identifiant, b.identifiant})
                self.assertGreater(a.distance, a.passage[0])
                self.assertGreater(b.distance, b.passage[0])
                simulation.avancer(8)
                self.assertFalse(simulation.vehicules_engages)

    def test_virage_conflictuel_et_rouge_imposent_attente(self):
        simulation = Simulation(debit=0)
        premier = simulation.ajouter_voiture("N", "straight")
        virage = simulation.ajouter_voiture("S", "left")
        for voiture in (premier, virage):
            voiture.distance = voiture.passage[0]
        simulation.avancer(.5)
        self.assertEqual(len(simulation.vehicules_engages), 1)
        self.assertFalse(simulation.passages_compatibles(premier, virage))
        rouge = simulation.ajouter_voiture("E", "straight")
        rouge.distance = rouge.passage[0]
        simulation.avancer(.5)
        self.assertEqual(rouge.distance, rouge.passage[0])

    def test_tirage_95_pourcent_tout_droit(self):
        simulation = Simulation(debit=0)
        nombres = Counter(simulation.choisir_virage() for _ in range(10000))
        self.assertTrue(9350 < nombres["straight"] < 9650, nombres)
        self.assertTrue(150 < nombres["left"] < 350, nombres)
        self.assertTrue(150 < nombres["right"] < 350, nombres)
        # Verifier aussi le tirage utilise lors de la creation de vraies voitures.
        nombres = Counter()
        for index in range(1000):
            simulation.voitures.clear()
            nombres[simulation.ajouter_voiture().virage] += 1
        self.assertTrue(920 < nombres["straight"] < 980, nombres)
        self.assertGreater(nombres["left"], 0, nombres)
        self.assertGreater(nombres["right"], 0, nombres)

    def test_trajets_desservent_points_et_reviennent_au_parking(self):
        for identifiant, y in PARKING_Y.items():
            for cote in DESTINATIONS:
                trajet, passages, arret = trajet_secours(identifiant, y, cote)
                self.assertEqual(trajet.points[0], (PARKING_X, y))
                self.assertEqual(trajet.points[-1], (PARKING_X, y))
                self.assertEqual(trajet.position_a(arret)[:2], POINTS_INTERVENTION[cote])
                self.assertEqual(len(passages), 2)

    def test_destination_fixe_pendant_mission(self):
        simulation = Simulation(debit=0)
        self.assertTrue(simulation.demarrer_mission("01", "E"))
        trajet = simulation.secours[0].trajet
        self.assertFalse(simulation.demarrer_mission("01", "W"))
        self.assertIs(simulation.secours[0].trajet, trajet)
        with self.assertRaises(ValueError):
            simulation.demarrer_mission("02", "invalid")
        self.assertFalse(simulation.secours[1].occupe)

    def test_sortie_bloquee_garde_demande_et_permet_approche(self):
        simulation = Simulation(debit=0)
        simulation.demarrer_mission("01", "W")
        secours = simulation.secours[0]
        secours.intervention_effectuee = True
        secours.indice_passage = 1
        secours.distance = secours.passage[0]
        voiture = simulation.ajouter_voiture("S", "straight")
        voiture.distance = voiture.passage[1] + 20  # Voiture sur la sortie Nord commune.
        voiture.indice_passage = 1
        voiture.vitesse = 0
        self.assertEqual(len(simulation.demandes()), 1)
        simulation.avancer(2.1)
        self.assertEqual(simulation.feux.signal(secours.passage[2]), "green")
        self.assertGreater(secours.distance, secours.passage[0])
        self.assertIn(secours.identifiant, simulation.vehicules_engages)
        for _ in range(40):
            simulation.avancer(.05)
            verifier_espacement(self, simulation)
        simulation.voitures.clear()
        simulation.avancer(.5)
        self.assertIn(secours.identifiant, simulation.vehicules_engages)

    def test_couples_destinations_finissent_sans_contact_avec_trafic(self):
        for premier, second in product(DESTINATIONS, repeat=2):
            with self.subTest(premier=premier, second=second):
                simulation = Simulation(debit=40)
                simulation.demarrer_mission("01", premier)
                simulation.demarrer_mission("02", second)
                for index in range(1200):
                    simulation.avancer(.5)
                    verifier_espacement(self, simulation)
                    engage = []
                    for vehicule in simulation.vehicules:
                        if vehicule.identifiant in simulation.vehicules_engages:
                            engage.append(vehicule)
                            if vehicule.type_vehicule != "car":
                                self.assertEqual(simulation.feux.signal(vehicule.passage[2]), "green",
                                                 (simulation.temps, vehicule.identifiant, vehicule.intervention_effectuee))
                    for a, b in combinations(engage, 2):
                        self.assertTrue(simulation.passages_compatibles(a, b))
                    if all(not v.occupe for v in simulation.secours):
                        break
                self.assertTrue(all(not v.occupe for v in simulation.secours))
                self.assertIn(("01", "disponible"), simulation.evenements)
                self.assertIn(("02", "disponible"), simulation.evenements)
                avant = simulation.trajets_termines
                simulation.avancer(40)
                self.assertGreater(simulation.trajets_termines, avant)
