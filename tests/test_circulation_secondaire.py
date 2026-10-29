"""Files et passages compatibles aux raccordements sans feux."""

import unittest

from src.simulation.moteur import DISTANCE_SECURITE, PAS_TEMPS, Simulation
from controles_circulation import verifier_espacement


class TestsCirculationSecondaire(unittest.TestCase):
    def verifier_distances(self, simulation):
        verifier_espacement(self, simulation)

    def zone(self, voiture, cle):
        return next(zone for zone in voiture.trajet.raccordements if zone[2] == cle)

    def marquer_passages_precedents(self, voiture):
        voiture.indice_passage = sum(fin <= voiture.distance for _, fin, _ in voiture.passages)

    def avancer_sans_collision(self, simulation, secondes):
        for _ in range(round(secondes / PAS_TEMPS)):
            simulation.avancer(PAS_TEMPS)
            self.verifier_distances(simulation)

    def test_file_nord_rejoint_feu_rouge_sans_attendre_caserne(self):
        simulation = Simulation(debit=0)
        simulation.feux.axe = "EW"  # Le feu Nord reste rouge pendant les 9 s observees.
        voitures = []
        for index in range(6):
            voiture = simulation.ajouter_voiture("N", "straight")
            self.assertIsNotNone(voiture)
            if index < 4:
                voiture.distance = voiture.passage[0] - index * DISTANCE_SECURITE
            else:
                arret_caserne, _, _ = self.zone(voiture, "F")
                voiture.distance = arret_caserne - (index - 4) * DISTANCE_SECURITE
            voitures.append(voiture)
        initiale = [voiture.distance for voiture in voitures]
        self.avancer_sans_collision(simulation, 9)
        for index, voiture in enumerate(voitures):
            self.assertLessEqual(voiture.distance, voiture.passage[0])
            self.assertAlmostEqual(voiture.distance, voiture.passage[0] - index * DISTANCE_SECURITE,
                                   delta=2 * voiture.vitesse * PAS_TEMPS)
        self.assertGreater(voitures[4].distance - initiale[4], 180)
        self.assertGreater(voitures[5].distance - initiale[5], 180)
        self.assertFalse(simulation.vehicules_engages)
        self.assertEqual(simulation.feux.signal("NS"), "red")

    def test_sens_opposes_tout_droit_passent_ensemble_devant_caserne(self):
        simulation = Simulation(debit=0)
        nord = simulation.ajouter_voiture("N", "straight")
        nord.distance = self.zone(nord, "F")[0]
        sud = simulation.ajouter_voiture("S", "straight")
        sud.distance = self.zone(sud, "F")[0] + 30
        self.marquer_passages_precedents(sud)
        initiale = (nord.distance, sud.distance)
        self.avancer_sans_collision(simulation, 1)
        for voiture, precedent in zip((nord, sud), initiale):
            self.assertAlmostEqual(voiture.distance - precedent, voiture.vitesse)
            self.assertFalse(voiture.en_attente)

    def test_suivantes_entrent_virages_secondaires_avant_sortie_de_tete(self):
        for origine, cle in (("N", "F"), ("E", "U"), ("E", "B"), ("S", "D")):
            with self.subTest(origine=origine, junction=cle):
                simulation = Simulation(debit=0)
                tete = simulation.ajouter_voiture(origine, "straight")
                arret, fin, _ = self.zone(tete, cle)
                tete.distance = arret + 70
                suivante = simulation.ajouter_voiture(origine, "straight")
                suivante.distance = arret - 1
                for voiture in (tete, suivante):
                    self.marquer_passages_precedents(voiture)
                initiale = (tete.distance, suivante.distance)
                self.avancer_sans_collision(simulation, 1)
                self.assertLess(tete.distance, fin)
                self.assertGreater(suivante.distance, arret)
                for voiture, precedent in zip((tete, suivante), initiale):
                    self.assertGreaterEqual(voiture.distance - precedent + 1e-6, voiture.vitesse)
                    self.assertFalse(voiture.en_attente)

    def test_convoi_continue_raccordement_ouest_apres_carrefour(self):
        simulation = Simulation(debit=0)
        simulation.feux.axe = "EW"
        voitures = []
        for index in range(3):
            voiture = simulation.ajouter_voiture("E", "straight")
            voiture.distance = voiture.passage[0] - index * DISTANCE_SECURITE
            voitures.append(voiture)
        self.avancer_sans_collision(simulation, 15)
        for voiture in voitures:
            arret, fin, _ = self.zone(voiture, "W")
            self.assertIsNone(voiture.passage)
            self.assertLess(arret, voiture.distance)
            self.assertLess(voiture.distance, fin)
            self.assertFalse(voiture.en_attente)

    def test_priorite_caserne_puis_reprise_des_degagement(self):
        simulation = Simulation(debit=0)
        simulation.demarrer_mission("02", "S")
        secours = simulation.obtenir_secours("02")
        arret_secours, fin_secours, _ = self.zone(secours, "F")
        secours.distance = arret_secours
        voiture = simulation.ajouter_voiture("N", "straight")
        arret_voiture, _, _ = self.zone(voiture, "F")
        voiture.distance = arret_voiture
        simulation.avancer(PAS_TEMPS)
        self.assertGreater(secours.distance, arret_secours)
        self.assertEqual(voiture.distance, arret_voiture)
        for _ in range(200):
            if secours.distance >= fin_secours:
                break
            simulation.avancer(PAS_TEMPS)
            self.verifier_distances(simulation)
            if secours.distance < fin_secours:
                self.assertEqual(voiture.distance, arret_voiture)
        self.assertGreaterEqual(secours.distance, fin_secours)
        simulation.avancer(PAS_TEMPS)
        self.assertGreater(voiture.distance, arret_voiture)
        self.verifier_distances(simulation)

    def test_distance_gardee_derriere_tete_arretee(self):
        simulation = Simulation(debit=0)
        tete = simulation.ajouter_voiture("N", "straight")
        arret, _, _ = self.zone(tete, "F")
        tete.distance = arret + DISTANCE_SECURITE
        tete.vitesse = 0
        suivante = simulation.ajouter_voiture("N", "straight")
        suivante.distance = arret
        self.avancer_sans_collision(simulation, 1)
        self.assertEqual(suivante.distance, arret)
        self.assertTrue(suivante.en_attente)

    def test_secours_suit_voiture_ayant_degage_carrefour(self):
        for en_mouvement in (False, True):
            with self.subTest(en_mouvement=en_mouvement):
                simulation = Simulation(debit=0)
                simulation.demarrer_mission("02", "W")
                secours = simulation.obtenir_secours("02")
                secours.distance = secours.passage[0]
                voiture = simulation.ajouter_voiture("E", "straight")
                voiture.distance = voiture.passage[1] + 70
                self.marquer_passages_precedents(voiture)
                if not en_mouvement:
                    voiture.vitesse = 0
                arret = secours.distance
                simulation.avancer(2 if en_mouvement else PAS_TEMPS)
                self.verifier_distances(simulation)
                self.assertGreater(secours.distance, arret)
                self.assertIn(secours.identifiant, simulation.vehicules_engages)

    def test_retour_attend_obstacle_reel_et_ignore_voitures_degagees(self):
        for positions in ((240, 285), (195,)):
            with self.subTest(north_car_y=positions):
                simulation = Simulation(debit=0)
                simulation.feux.axe = "EW"
                simulation.demarrer_mission("02", "W")
                secours = simulation.obtenir_secours("02")
                secours.intervention_effectuee = True
                secours.indice_passage = len(secours.passages)
                arret, _, _ = [zone for zone in secours.trajet.raccordements if zone[2] == "F"][-1]
                secours.distance = arret
                voitures = []
                for y in positions:
                    voiture = simulation.ajouter_voiture("N", "straight")
                    arret_caserne, _, _ = self.zone(voiture, "F")
                    y_caserne = voiture.trajet.position_a(arret_caserne)[1]
                    voiture.distance = arret_caserne + y - y_caserne
                    voiture.vitesse = 0
                    voitures.append(voiture)
                self.avancer_sans_collision(simulation, 1)
                if positions == (195,):
                    self.assertEqual(secours.distance, arret)
                    self.assertTrue(secours.en_attente)
                    # Le vrai obstacle degage sa voie ; le secours reprend.
                    voitures[0].vitesse = 28
                else:
                    self.assertGreater(secours.distance, arret)
                    self.assertFalse(secours.en_attente)
                self.avancer_sans_collision(simulation, 12)
                self.assertFalse(secours.occupe)

    def test_tout_droit_et_droite_opposes_partagent_vert(self):
        for origine_premier, origine_second, axe in (("N", "S", "NS"), ("E", "W", "EW")):
            for virages in (("straight", "right"), ("right", "straight"), ("right", "right")):
                with self.subTest(axe=axe, virages=virages):
                    simulation = Simulation(debit=0)
                    simulation.feux.axe = axe
                    premier = simulation.ajouter_voiture(origine_premier, virages[0])
                    premier.distance = premier.passage[0]
                    second = simulation.ajouter_voiture(origine_second, virages[1])
                    second.distance = second.passage[0]
                    self.assertTrue(simulation.passages_compatibles(premier, second))
                    simulation.avancer(PAS_TEMPS)
                    self.assertEqual(simulation.vehicules_engages, {premier.identifiant, second.identifiant})
                    self.avancer_sans_collision(simulation, 5)

    def test_gauches_opposes_attendent_et_meme_file_suit(self):
        for origine_premier, origine_opposee, axe in (("N", "S", "NS"), ("E", "W", "EW")):
            for virage_premier, origine_second, virage_second in (
                    ("straight", origine_opposee, "left"),
                    ("right", origine_premier, "straight"),
                    ("left", origine_premier, "straight")):
                with self.subTest(axe=axe, premier=virage_premier,
                                  origine_second=origine_second, second=virage_second):
                    simulation = Simulation(debit=0)
                    simulation.feux.axe = axe
                    premier = simulation.ajouter_voiture(origine_premier, virage_premier)
                    premier.distance = premier.passage[0]
                    if origine_second == origine_premier:
                        premier.distance += 70
                        simulation.vehicules_engages.add(premier.identifiant)
                    second = simulation.ajouter_voiture(origine_second, virage_second)
                    second.distance = second.passage[0]
                    self.assertEqual(simulation.passages_compatibles(premier, second), origine_second == origine_premier)
                    simulation.avancer(PAS_TEMPS)
                    if origine_second == origine_premier:
                        self.assertEqual(len(simulation.vehicules_engages), 2)
                        self.assertGreater(second.distance, second.passage[0])
                    else:
                        self.assertEqual(len(simulation.vehicules_engages), 1)
                    self.verifier_distances(simulation)


if __name__ == "__main__":
    unittest.main()
