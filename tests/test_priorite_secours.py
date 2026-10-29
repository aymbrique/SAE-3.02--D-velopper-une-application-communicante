"""Priorite sur tout l'aller/retour et degagement des raccordements sans feux."""

import unittest
from controles_circulation import verifier_espacement

from src.simulation.moteur import DISTANCE_SECURITE, PAS_TEMPS, Simulation


class TestsPrioriteSecours(unittest.TestCase):
    def placer_au_raccordement(self, simulation, destination, cle, en_retour):
        simulation.demarrer_mission("02", destination)
        secours = simulation.obtenir_secours("02")
        zones = [zone for zone in secours.trajet.raccordements if zone[2] == cle]
        arret, fin, _ = zones[-1 if en_retour else 0]
        secours.distance = arret
        secours.intervention_effectuee = en_retour
        secours.indice_passage = sum(fin <= arret for _, fin, _ in secours.passages)
        return secours, arret, fin

    def test_priorite_aux_raccordements_nord_est_et_est_aller_retour(self):
        for destination, cle, origine, directions in (
                ("N", "B", "E", (False,)), ("N", "B", "W", (True,)),
                ("N", "U", "E", (False,)), ("N", "H", "E", (False, True)),
                ("E", "R", "W", (True,)),
                ("E", "E", "W", (True,))):
            for en_retour in directions:
                with self.subTest(destination=destination, junction=cle, en_retour=en_retour):
                    simulation = Simulation(debit=0)
                    secours, arret, fin = self.placer_au_raccordement(simulation, destination, cle, en_retour)
                    voiture = simulation.ajouter_voiture(origine, "straight")
                    arret_voiture, fin_voiture, _ = next(zone for zone in voiture.trajet.raccordements if zone[2] == cle)
                    voiture.distance = arret_voiture
                    self.assertFalse(simulation._raccordement_libre(voiture, arret_voiture, fin_voiture, cle))
                    self.assertTrue(simulation._raccordement_libre(secours, arret, fin, cle))
                    simulation.avancer(PAS_TEMPS)
                    self.assertGreater(secours.distance, arret)
                    self.assertEqual(voiture.distance, arret_voiture)

    def test_retour_demande_vert_et_reste_prioritaire_jusqu_au_degagement(self):
        for destination in ("W", "S", "N", "E"):
            with self.subTest(destination=destination):
                simulation = Simulation(debit=0)
                simulation.demarrer_mission("02", destination)
                secours = simulation.obtenir_secours("02")
                secours.intervention_effectuee = True
                secours.indice_passage = 1
                arret, fin, axe = secours.passage
                secours.distance = arret
                simulation.feux.axe = "EW" if axe == "NS" else "NS"
                self.assertEqual([demande.identifiant for demande in simulation.demandes()], ["02"])
                est_entre = False
                for _ in range(500):
                    simulation.avancer(PAS_TEMPS)
                    if secours.identifiant in simulation.vehicules_engages:
                        est_entre = True
                        self.assertTrue(secours.occupe)
                        self.assertEqual(simulation.feux.prioritaire.identifiant, "02")
                        self.assertEqual(simulation.feux.signal(axe), "green")
                    if secours.distance >= fin:
                        break
                self.assertTrue(est_entre)
                self.assertGreaterEqual(secours.distance, fin)
                self.assertTrue(secours.occupe)
                simulation.avancer(60)
                self.assertFalse(secours.occupe)

    def test_vert_pret_avant_arrivee_secours_aller_et_retour(self):
        for identifiant in ("01", "02"):
            for destination in ("W", "S", "N", "E"):
                for en_retour in (False, True):
                    with self.subTest(secours=identifiant, destination=destination, en_retour=en_retour):
                        simulation = Simulation(debit=0)
                        simulation.demarrer_mission(identifiant, destination)
                        secours = simulation.obtenir_secours(identifiant)
                        secours.intervention_effectuee = en_retour
                        secours.indice_passage = int(en_retour)
                        arret, fin, axe = secours.passage
                        secours.distance = arret - 120  # Arrivee dans 3 s.
                        simulation.feux.axe = "EW" if axe == "NS" else "NS"
                        simulation.avancer(2.05)
                        self.assertEqual(simulation.feux.signal(axe), "green")
                        self.assertLess(secours.distance, arret)
                        simulation.avancer(1.5)
                        self.assertIn(identifiant, simulation.vehicules_engages)

    def test_voiture_engagee_termine_avant_secours(self):
        simulation = Simulation(debit=0)
        secours, arret, fin = self.placer_au_raccordement(simulation, "N", "B", True)
        voiture = simulation.ajouter_voiture("E", "straight")
        arret_voiture, fin_voiture, cle = next(zone for zone in voiture.trajet.raccordements if zone[2] == "B")
        voiture.distance = arret_voiture + DISTANCE_SECURITE + 6
        self.assertFalse(simulation._raccordement_libre(secours, arret, fin, cle))
        simulation.avancer(12)
        self.assertGreater(secours.distance, fin)
        self.assertGreater(voiture.distance, fin_voiture)

    def test_voiture_opposee_cede_au_vert_pour_secours_en_retour(self):
        simulation = Simulation(debit=0)
        simulation.demarrer_mission("02", "W")
        secours = simulation.obtenir_secours("02")
        secours.intervention_effectuee = True
        secours.indice_passage = 1
        secours.distance = secours.passage[0]
        simulation.feux.axe = "EW"
        voiture = simulation.ajouter_voiture("E", "straight")
        voiture.distance = voiture.passage[0]
        simulation.avancer(PAS_TEMPS)
        self.assertIn(secours.identifiant, simulation.vehicules_engages)
        self.assertEqual(voiture.distance, voiture.passage[0])
        simulation.avancer(12)
        self.assertGreater(voiture.distance, voiture.passages[0][0])

    def test_deux_secours_en_retour_servent_premier_de_file(self):
        from src.simulation.feux import DemandePriorite
        simulation = Simulation(debit=0)
        simulation.demarrer_mission("01", "N")
        simulation.demarrer_mission("02", "E")
        tete, suivante = simulation.secours
        for secours in simulation.secours:
            secours.intervention_effectuee = True
            secours.indice_passage = 1
            secours.distance = secours.passage[0]
        suivante.distance -= DISTANCE_SECURITE + 1
        simulation.feux.axe = "EW"
        # Le suiveur avait demande avant la jonction des deux trajets.
        simulation.feux.prioritaire = DemandePriorite("02", "EW", 0, 0)
        self.assertEqual([demande.identifiant for demande in simulation.demandes()], ["01"])
        simulation.avancer(PAS_TEMPS)
        self.assertEqual(simulation.feux.prioritaire.identifiant, "01")
        self.assertIn("01", simulation.vehicules_engages)
        simulation.avancer(60)
        self.assertTrue(all(not secours.occupe for secours in simulation.secours))

    def test_voiture_devant_degage_avant_secours(self):
        simulation = Simulation(debit=0)
        secours, arret, fin = self.placer_au_raccordement(simulation, "N", "B", True)
        voiture = simulation.ajouter_voiture("E", "straight")
        arret_voiture, fin_voiture, cle = next(zone for zone in voiture.trajet.raccordements if zone[2] == "B")
        voiture.distance = arret_voiture
        secours.distance = arret - DISTANCE_SECURITE - 2
        self.assertTrue(simulation._raccordement_libre(voiture, arret_voiture, fin_voiture, cle))
        for _ in range(300):
            simulation.avancer(PAS_TEMPS)
            verifier_espacement(self, simulation)
        self.assertGreater(secours.distance, fin)

    def test_secours_disponible_ne_bloque_pas_voitures(self):
        simulation = Simulation(debit=0)
        secours, arret, fin = self.placer_au_raccordement(simulation, "N", "B", True)
        secours.occupe = False
        secours.distance = 0
        voiture = simulation.ajouter_voiture("W", "straight")
        arret_voiture, fin_voiture, cle = next(zone for zone in voiture.trajet.raccordements if zone[2] == "B")
        voiture.distance = arret_voiture
        self.assertTrue(simulation._raccordement_libre(voiture, arret_voiture, fin_voiture, cle))

    def test_missions_apres_formation_des_files(self):
        simulation = Simulation(debit=60, graine=51)
        simulation.avancer(60)
        simulation.demarrer_mission("02", "N")
        simulation.avancer(2)
        simulation.demarrer_mission("01", "E")
        for _ in range(1200):
            simulation.avancer(.5)
            verifier_espacement(self, simulation)
            if all(not secours.occupe for secours in simulation.secours):
                break
        self.assertTrue(all(not secours.occupe for secours in simulation.secours))
        trajets_termines = simulation.trajets_termines
        simulation.avancer(40)
        self.assertGreater(simulation.trajets_termines, trajets_termines)
