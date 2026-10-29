"""Regressions : files tout droit, espacement, degagement et mouvements exclusifs."""

import unittest

from src.simulation.moteur import DISTANCE_SECURITE, PAS_TEMPS, Simulation
from src.simulation.priorite import DECALAGE_RANGEMENT
from controles_circulation import verifier_espacement


class TestsCirculation(unittest.TestCase):
    def creer_file(self, simulation, origine, nombre=6):
        voitures = []
        for index in range(nombre):
            voiture = simulation.ajouter_voiture(origine, "straight")
            self.assertIsNotNone(voiture)
            voiture.distance = voiture.passage[0] - DISTANCE_SECURITE * index
            voitures.append(voiture)
        return voitures

    def verifier_distances(self, simulation):
        verifier_espacement(self, simulation)

    def test_deux_files_passent_pendant_un_vert_sur_chaque_axe(self):
        for premier, second, axe in (("N", "S", "NS"), ("E", "W", "EW")):
            with self.subTest(axe=axe):
                simulation = Simulation(debit=0)
                simulation.feux.axe = axe
                voitures = self.creer_file(simulation, premier) + self.creer_file(simulation, second)
                est_entre = set()
                maximum = 0
                for pas in range(159):
                    simulation.avancer(PAS_TEMPS)
                    est_entre.update(simulation.vehicules_engages)
                    maximum = max(maximum, len(simulation.vehicules_engages))
                    self.verifier_distances(simulation)
                self.assertEqual(est_entre, {voiture.identifiant for voiture in voitures})
                self.assertGreater(maximum, 2)
                # Les files avancent sans s'arreter derriere leurs leaders.
                self.assertTrue(all(not voiture.en_attente for voiture in voitures))
                # Les nouveaux raccordements en aval peuvent ralentir la sortie.
                # Tous les vehicules doivent quand meme finir par degager.
                for pas in range(800):
                    simulation.avancer(PAS_TEMPS)
                    self.verifier_distances(simulation)
                    if not simulation.vehicules_engages:
                        break
                self.assertFalse(simulation.vehicules_engages)

    def test_suivante_avance_apres_sortie_de_tete(self):
        simulation = Simulation(debit=0)
        tete, suivante = self.creer_file(simulation, "N", 2)
        fin = tete.passage[1]
        tete.distance = fin - .5
        simulation.vehicules_engages.add(tete.identifiant)
        suivante.distance = suivante.passage[0]
        simulation.avancer(PAS_TEMPS)
        self.assertNotIn(tete.identifiant, simulation.vehicules_engages)
        self.assertIn(suivante.identifiant, simulation.vehicules_engages)
        self.assertGreater(suivante.distance, suivante.passage[0])
        self.verifier_distances(simulation)

    def test_sortie_bloquee_interdit_entree(self):
        simulation = Simulation(debit=0)
        tete, suivante = self.creer_file(simulation, "N", 2)
        tete.distance = tete.passage[1] + DISTANCE_SECURITE / 2
        tete.indice_passage = 1
        tete.vitesse = 0
        suivante.distance = suivante.passage[0]
        simulation.avancer(1)
        self.assertEqual(suivante.distance, suivante.passage[0])
        self.assertNotIn(suivante.identifiant, simulation.vehicules_engages)
        self.verifier_distances(simulation)

    def test_secours_suit_voiture_qui_vient_de_sortir(self):
        simulation = Simulation(debit=0)
        tete = simulation.ajouter_voiture("N", "straight")
        tete.distance = tete.passage[1] + .5
        tete.indice_passage = 1
        simulation.demarrer_mission("01", "S")
        secours = simulation.obtenir_secours("01")
        arret = secours.passage[0]
        secours.distance = arret
        simulation.avancer(1.5)  # Laisser la voiture se ranger avant le depassement.
        self.assertGreater(secours.distance, arret)
        self.assertIn(secours.identifiant, simulation.vehicules_engages)
        self.verifier_distances(simulation)

    def test_secours_approche_voiture_arretee_sans_contact(self):
        simulation = Simulation(debit=0)
        tete = simulation.ajouter_voiture("N", "straight")
        tete.distance = tete.passage[1] + .5
        tete.indice_passage = 1
        tete.vitesse = 0
        simulation.demarrer_mission("01", "S")
        secours = simulation.obtenir_secours("01")
        arret = secours.passage[0]
        secours.distance = arret
        simulation.avancer(1)
        self.assertGreater(secours.distance, arret)
        self.assertIn(secours.identifiant, simulation.vehicules_engages)
        for _ in range(100):
            simulation.avancer(PAS_TEMPS)
            self.verifier_distances(simulation)

    def test_suivante_proche_continue_pendant_degagement_de_tete(self):
        simulation = Simulation(debit=0)
        tete, suivante = self.creer_file(simulation, "N", 2)
        tete.distance = tete.passage[1] + .5
        tete.indice_passage = 1
        suivante.distance = tete.distance - DISTANCE_SECURITE
        simulation.vehicules_engages.add(suivante.identifiant)
        precedent = suivante.distance
        simulation.avancer(PAS_TEMPS)
        self.assertAlmostEqual(suivante.distance - precedent, suivante.vitesse * PAS_TEMPS)
        self.assertAlmostEqual(tete.distance - suivante.distance, DISTANCE_SECURITE)
        self.assertFalse(suivante.en_attente)

    def test_suivante_tout_droit_ralentit_derriere_virage(self):
        for virage in ("left", "right"):
            with self.subTest(virage=virage):
                simulation = Simulation(debit=0)
                tete = simulation.ajouter_voiture("N", virage)
                tete.distance = tete.passage[0] + 70
                simulation.vehicules_engages.add(tete.identifiant)
                suivante = simulation.ajouter_voiture("N", "straight")
                suivante.distance = suivante.passage[0]
                simulation.avancer(PAS_TEMPS)
                self.assertGreater(suivante.distance, suivante.passage[0])
                self.assertLess(suivante.vitesse_actuelle, suivante.vitesse)
                self.assertTrue(simulation.passages_compatibles(tete, suivante))
                self.assertIn(suivante.identifiant, simulation.vehicules_engages)
                self.assertIn(tete.identifiant, simulation.vehicules_engages)
                for pas in range(200):
                    simulation.avancer(PAS_TEMPS)
                    self.verifier_distances(simulation)
                    if suivante.identifiant in simulation.vehicules_engages:
                        break
                self.assertIn(suivante.identifiant, simulation.vehicules_engages)
                self.verifier_distances(simulation)

    def test_convoi_attend_orange_et_autre_axe_attend_degagement(self):
        simulation = Simulation(debit=0)
        tete, suivante, arrete = self.creer_file(simulation, "N", 3)
        arret = tete.passage[0]
        tete.distance = arret + 2 * DISTANCE_SECURITE
        suivante.distance = arret + DISTANCE_SECURITE
        arrete.distance = arret
        simulation.vehicules_engages.update((tete.identifiant, suivante.identifiant))
        simulation.feux.phase = "amber"
        autre = simulation.ajouter_voiture("E", "straight")
        autre.distance = autre.passage[0]
        for pas in range(200):
            occupe_avant = bool(simulation.vehicules_engages)
            simulation.avancer(PAS_TEMPS)
            self.verifier_distances(simulation)
            self.assertEqual(arrete.distance, arret)
            if occupe_avant:
                self.assertEqual(autre.distance, autre.passage[0])
            if autre.identifiant in simulation.vehicules_engages:
                break
        self.assertIn(autre.identifiant, simulation.vehicules_engages)
        self.assertNotIn(tete.identifiant, simulation.vehicules_engages)
        self.assertNotIn(suivante.identifiant, simulation.vehicules_engages)

    def test_secours_suit_convoi_sans_reserver_tout_carrefour(self):
        simulation = Simulation(debit=0)
        tete, suivante = self.creer_file(simulation, "N", 2)
        simulation.demarrer_mission("01", "S")
        secours = simulation.obtenir_secours("01")
        secours.distance = secours.passage[0]
        tete.distance = tete.passage[0] + 2 * DISTANCE_SECURITE
        suivante.distance = suivante.passage[0] + DISTANCE_SECURITE
        simulation.vehicules_engages.update((tete.identifiant, suivante.identifiant))
        simulation.avancer(PAS_TEMPS)
        self.assertGreater(secours.distance, secours.passage[0])
        self.assertIn(secours.identifiant, simulation.vehicules_engages)
        self.assertTrue(simulation.passages_compatibles(tete, secours))
        for _ in range(150):
            simulation.avancer(PAS_TEMPS)
            self.verifier_distances(simulation)
        self.verifier_distances(simulation)

    def test_virage_secours_attend_reinsertion_engagee(self):
        simulation = Simulation(debit=0)
        voiture = simulation.ajouter_voiture("N", "straight")
        voiture.distance = voiture.passage[0] + 64.8
        voiture.debut_manoeuvre = voiture.distance - 14.4
        voiture.decalage_initial = DECALAGE_RANGEMENT
        voiture.decalage_cible = 0
        voiture.decalage_lateral, _ = voiture.decalage_lateral_a(voiture.distance)
        simulation.vehicules_engages.add(voiture.identifiant)
        simulation.demarrer_mission("01", "W")
        secours = simulation.obtenir_secours("01")
        arret = secours.passage[0]
        secours.distance = arret
        precedent = voiture.distance
        simulation.avancer(.5)
        self.assertEqual(secours.distance, arret)
        self.assertGreater(voiture.distance, precedent)
        est_entre = False
        for _ in range(150):
            simulation.avancer(PAS_TEMPS)
            self.verifier_distances(simulation)
            if not est_entre and secours.distance > arret:
                est_entre = True
                self.assertIn(voiture.identifiant, simulation.vehicules_engages)
        self.assertTrue(est_entre)
        self.assertFalse(simulation.vehicules_engages)
        self.assertEqual(voiture.decalage_lateral, 0)

    def test_secours_attend_raccordement_occupe_puis_repart(self):
        simulation = Simulation(debit=0)
        simulation.demarrer_mission("01", "E")
        secours = simulation.obtenir_secours("01")
        arret, fin, cle = next(zone for zone in secours.trajet.raccordements if zone[2] == "B")
        secours.distance = arret
        secours.indice_passage = 1  # Le carrefour principal est deja franchi.
        obstacle = simulation.ajouter_voiture("W", "straight")
        occupe = next(zone for zone in obstacle.trajet.raccordements if zone[2] == cle)
        obstacle.distance = occupe[0] + 50
        obstacle.vitesse = 0
        simulation.avancer(2)
        self.assertEqual(secours.distance, arret)
        self.verifier_distances(simulation)
        simulation.voitures.remove(obstacle)
        simulation.avancer(1)
        self.assertGreater(secours.distance, arret)
        simulation.avancer(180)
        self.assertFalse(secours.occupe)
        self.verifier_distances(simulation)


if __name__ == "__main__":
    unittest.main()
