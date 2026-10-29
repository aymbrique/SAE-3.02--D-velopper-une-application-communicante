"""Files sans depassement, manoeuvres en roulant et degagement sous forte charge."""

import unittest
from math import cos, radians

from src.simulation.moteur import DISTANCE_SECURITE, PAS_TEMPS, VITESSE_SECOURS, Simulation
from src.simulation.priorite import DECALAGE_RANGEMENT
from controles_circulation import verifier_espacement


class TestsPrioriteFluide(unittest.TestCase):
    def test_ordre_file_conserve_pendant_rangement_et_reinsertion(self):
        simulation = Simulation(debit=0)
        simulation.demarrer_mission("02", "W")
        secours = simulation.obtenir_secours("02")
        secours.distance = secours.passage[0] - 240
        tete = simulation.ajouter_voiture("N", "straight")
        tete.distance = tete.passage[0] - 100
        tete.decalage_lateral = DECALAGE_RANGEMENT
        tete.cede_aux = ("02",)
        suivante = simulation.ajouter_voiture("N", "straight")
        suivante.distance = tete.distance - DISTANCE_SECURITE
        initiale = suivante.distance
        maintenu = False
        for _ in range(1200):
            simulation.avancer(PAS_TEMPS)
            self.assertGreaterEqual(tete.distance - suivante.distance, DISTANCE_SECURITE - 1e-6)
            maintenu |= suivante.en_attente
            verifier_espacement(self, simulation)
        self.assertTrue(maintenu)
        self.assertGreater(suivante.distance, initiale + 200)
        self.assertEqual(tete.decalage_lateral, 0)
        self.assertEqual(suivante.decalage_lateral, 0)

    def test_rangement_en_avancant_avec_braquage_visible(self):
        simulation = Simulation(debit=0)
        simulation.demarrer_mission("02", "W")
        secours = simulation.obtenir_secours("02")
        secours.distance = secours.passage[0] - 120
        voiture = simulation.ajouter_voiture("N", "straight")
        voiture.distance = voiture.passage[0] - voiture.longueur_manoeuvre
        secours.distance = secours.passage[0] - voiture.longueur_manoeuvre - 120
        a_tourne = False
        gare = False
        for _ in range(300):
            precedent = voiture.distance, voiture.decalage_lateral
            simulation.avancer(PAS_TEMPS)
            if abs(voiture.decalage_lateral - precedent[1]) > 1e-7:
                self.assertGreater(voiture.distance, precedent[0])
                orientation = voiture.trajet.position_a(voiture.distance)[2]
                a_tourne |= cos(radians(voiture.position[2] - orientation)) < .99
            if voiture.cede_aux and voiture.debut_manoeuvre is None:
                gare |= voiture.en_attente and voiture.vitesse_actuelle == 0
            verifier_espacement(self, simulation)
        self.assertTrue(a_tourne)
        self.assertTrue(gare)
        self.assertEqual(voiture.decalage_lateral, 0)

    def test_secours_plus_rapides_meme_en_virage(self):
        simulation = Simulation(debit=0)
        voiture = simulation.ajouter_voiture("N", "right")
        self.assertGreater(VITESSE_SECOURS, 40)
        for secours in simulation.secours:
            self.assertGreater(secours.vitesse, voiture.vitesse)
            self.assertGreater(secours.vitesse, 40)
        simulation.demarrer_mission("01", "N")
        secours = simulation.obtenir_secours("01")
        self.assertAlmostEqual(secours.duree_estimee, secours.trajet.longueur / secours.vitesse + 8)

    def test_secours_entre_si_voiture_engagee_hors_trajectoire(self):
        simulation = Simulation(debit=0)
        simulation.demarrer_mission("01", "W")
        secours = simulation.obtenir_secours("01")
        secours.distance = secours.passage[0]
        voiture = simulation.ajouter_voiture("N", "straight")
        voiture.distance = voiture.passage[1] - 40
        simulation.vehicules_engages.add(voiture.identifiant)
        simulation.avancer(PAS_TEMPS)
        self.assertIn(voiture.identifiant, simulation.vehicules_engages)
        self.assertIn(secours.identifiant, simulation.vehicules_engages)
        self.assertGreater(secours.vitesse_actuelle, 0)
        verifier_espacement(self, simulation)

    def test_file_rangee_en_sortie_degage_avant_vert_prioritaire(self):
        simulation = Simulation(debit=0)
        simulation.demarrer_mission("01", "E")
        secours = simulation.obtenir_secours("01")
        secours.intervention_effectuee = True
        secours.indice_passage = 1
        secours.distance = secours.passage[0]
        tete = simulation.ajouter_voiture("S", "straight")
        tete.distance = tete.passage[1] + 34
        tete.indice_passage = 1
        tete.decalage_lateral = DECALAGE_RANGEMENT
        tete.cede_aux = ("01",)
        suivante = simulation.ajouter_voiture("S", "straight")
        suivante.distance = suivante.passage[1] - 10
        simulation.vehicules_engages.add(suivante.identifiant)
        est_entre = False
        for _ in range(200):
            simulation.avancer(PAS_TEMPS)
            verifier_espacement(self, simulation)
            est_entre |= secours.identifiant in simulation.vehicules_engages
        self.assertNotIn(suivante.identifiant, simulation.vehicules_engages)
        self.assertTrue(est_entre)

    def test_secours_retour_quitte_raccordement_avec_suivante_proche(self):
        simulation = Simulation(debit=0)
        simulation.demarrer_mission("02", "N")
        secours = simulation.obtenir_secours("02")
        secours.intervention_effectuee = True
        secours.indice_passage = 2
        arret, fin, cle = [zone for zone in secours.trajet.raccordements if zone[2] == "F"][-1]
        secours.distance = arret
        voiture = simulation.ajouter_voiture("S", "straight")
        voiture.indice_passage = 1
        distance_sortie = voiture.passages[0][1]
        voiture.distance = distance_sortie + voiture.trajet.position_a(distance_sortie)[1] - 332
        self.assertTrue(simulation._raccordement_libre(secours, arret, fin, cle))
        for _ in range(160):
            simulation.avancer(PAS_TEMPS)
            verifier_espacement(self, simulation)
        self.assertFalse(secours.occupe)

    def test_arrivee_intervention_avec_residu_flottant(self):
        simulation = Simulation(debit=0)
        simulation.demarrer_mission("02", "N")
        secours = simulation.obtenir_secours("02")
        secours.distance = secours.arret_intervention - 1e-10
        secours.indice_passage = 1
        simulation.avancer(PAS_TEMPS)
        self.assertTrue(secours.intervention_effectuee)
        self.assertEqual(secours.distance, secours.arret_intervention)
        self.assertEqual(secours.temps_intervention_restant, 8)
        simulation.avancer(8 + 2 * PAS_TEMPS)
        self.assertGreater(secours.distance, secours.arret_intervention)

    def test_retour_caserne_avec_residu_flottant(self):
        simulation = Simulation(debit=0)
        simulation.demarrer_mission("01", "E")
        secours = simulation.obtenir_secours("01")
        secours.intervention_effectuee = True
        secours.indice_passage = 2
        secours.distance = secours.trajet.longueur - 1e-10
        simulation.avancer(PAS_TEMPS)
        self.assertFalse(secours.occupe)
        self.assertEqual(secours.distance, 0)
        self.assertIn(("01", "disponible"), simulation.recuperer_evenements())

    def test_trafic_dense_et_missions_repetees_sans_blocage_rouge(self):
        programme_missions = {60: ("02", "N"), 62: ("01", "E"),
                    230: ("02", "S"), 232: ("01", "W"),
                    400: ("02", "E"), 402: ("01", "N")}
        for graine in (51, 302):
            with self.subTest(graine=graine):
                simulation = Simulation(debit=60, graine=graine)
                demarre = {}
                for pas in range(1200):
                    second = pas / 2
                    if second in programme_missions:
                        identifiant, destination = programme_missions[second]
                        self.assertTrue(simulation.demarrer_mission(identifiant, destination))
                        demarre[identifiant] = simulation.temps
                    simulation.avancer(.5)
                    verifier_espacement(self, simulation)
                    if simulation.feux.phase == "all_red":
                        self.assertLess(simulation.feux.temps_ecoule, 20, (simulation.temps, simulation.vehicules_engages))
                    for secours in simulation.secours:
                        if secours.occupe:
                            self.assertLess(simulation.temps - demarre[secours.identifiant], 165,
                                            (simulation.temps, secours.identifiant, secours.destination))
                self.assertTrue(all(not secours.occupe for secours in simulation.secours))
                avant = simulation.trajets_termines
                simulation.avancer(40)
                self.assertGreater(simulation.trajets_termines, avant)


if __name__ == "__main__":
    unittest.main()
