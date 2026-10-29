"""Les voitures se rangent, s'arretent, puis reprennent apres les secours."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from itertools import combinations
import unittest
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath, QPolygonF

from src.simulation.moteur import PAS_TEMPS, Simulation
from src.simulation.priorite import DECALAGE_RANGEMENT, coins_carrosserie
from src.modeles.plan import sur_chaussee
from controles_circulation import verifier_espacement


class TestsRangement(unittest.TestCase):
    def test_virages_opposes_en_bas_finissent_apres_rangement(self):
        for identifiant in ("01", "02"):
            for variante in (None, "lower_west"):
                with self.subTest(secours=identifiant, variante=variante):
                    simulation = Simulation(debit=0)
                    simulation.demarrer_mission(identifiant, "S")
                    secours = simulation.obtenir_secours(identifiant)
                    secours.indice_passage = 1
                    arret = next(arret for arret, _, cle in secours.trajet.raccordements if cle == "D")
                    secours.distance = arret - 300
                    voiture = simulation.ajouter_voiture("N", "straight", variante=variante)
                    voiture.indice_passage = 1
                    arret_voiture, fin_voiture, _ = next(zone for zone in voiture.trajet.raccordements if zone[2] == "D")
                    voiture.distance = arret_voiture - voiture.longueur_manoeuvre
                    for _ in range(1800):
                        simulation.avancer(PAS_TEMPS)
                        verifier_espacement(self, simulation)
                        self.assertTrue(all(sur_chaussee(x, y) for x, y in coins_carrosserie(voiture, voiture.position)))
                        if not secours.occupe and voiture.distance >= voiture.trajet.longueur:
                            break
                    self.assertGreater(voiture.distance, fin_voiture)
                    self.assertFalse(secours.occupe)
                    self.assertGreaterEqual(voiture.distance, voiture.trajet.longueur)

    def test_secours_attend_voiture_rangee_deja_engagee_en_bas(self):
        simulation = Simulation(debit=0)
        simulation.demarrer_mission("01", "S")
        secours = simulation.obtenir_secours("01")
        secours.indice_passage = 1
        arret, fin, _ = next(zone for zone in secours.trajet.raccordements if zone[2] == "D")
        secours.distance = arret - 100
        voiture = simulation.ajouter_voiture("N", "straight")
        voiture.indice_passage = 1
        arret_voiture, fin_voiture, _ = next(zone for zone in voiture.trajet.raccordements if zone[2] == "D")
        voiture.distance = arret_voiture + 10
        voiture.decalage_lateral = DECALAGE_RANGEMENT
        for _ in range(500):
            simulation.avancer(PAS_TEMPS)
            verifier_espacement(self, simulation)
        self.assertGreater(voiture.distance, fin_voiture)
        self.assertGreater(secours.distance, fin)
        self.assertEqual(voiture.decalage_lateral, 0)

    def test_rangement_et_reinsertion_avec_angle_modere_sur_route(self):
        simulation = Simulation(debit=0)
        voiture = simulation.ajouter_voiture("N", "straight")
        debut = 350
        for premier, dernier in ((0, DECALAGE_RANGEMENT), (DECALAGE_RANGEMENT, 0)):
            with self.subTest(decalages=(premier, dernier)):
                voiture.debut_manoeuvre = debut
                voiture.decalage_initial = premier
                voiture.decalage_cible = dernier
                y_precedent = -float("inf")
                for pas in range(101):
                    distance = debut + voiture.longueur_manoeuvre * pas / 100
                    x, y, orientation = voiture.position_a(distance)
                    decalage, _ = voiture.decalage_lateral_a(distance)
                    self.assertLessEqual(abs(decalage), 22)
                    self.assertLess(abs(orientation - 90), 25)
                    self.assertGreater(y, y_precedent)
                    self.assertTrue(all(sur_chaussee(px, py) for px, py in coins_carrosserie(voiture, (x, y, orientation))))
                    y_precedent = y

    def test_rangement_pres_virage_bas_sans_contact_secours(self):
        simulation = Simulation(debit=0)
        simulation.demarrer_mission("01", "S")
        secours = simulation.obtenir_secours("01")
        arret_secours = next(arret for arret, _, cle in secours.trajet.raccordements if cle == "D")
        secours.distance = arret_secours - 240
        simulation.vehicules_engages.add(secours.identifiant)
        voitures = []
        for index in range(2):
            voiture = simulation.ajouter_voiture("N", "straight")
            arret = next(arret for arret, _, cle in voiture.trajet.raccordements if cle == "D")
            voiture.distance = arret - 84 - 60 * index
            voiture.indice_passage = 1
            voitures.append(voiture)
        decalage_max = 0
        for _ in range(1800):
            simulation.avancer(PAS_TEMPS)
            self.verifier_absence_contact(simulation)
            for voiture in voitures:
                decalage_max = max(decalage_max, voiture.decalage_lateral)
                self.assertLessEqual(voiture.decalage_lateral, 22)
                self.assertTrue(all(sur_chaussee(x, y) for x, y in coins_carrosserie(voiture, voiture.position)))
            if not secours.occupe and all(voiture.distance >= voiture.trajet.longueur for voiture in voitures):
                break
        self.assertEqual(decalage_max, DECALAGE_RANGEMENT)
        self.assertFalse(secours.occupe)
        self.assertTrue(all(voiture.distance >= voiture.trajet.longueur for voiture in voitures))

    def verifier_absence_contact(self, simulation):
        for premier, second in combinations(simulation.vehicules, 2):
            polygones = []
            for vehicule in (premier, second):
                chemin = QPainterPath()
                chemin.addPolygon(QPolygonF([QPointF(x, y) for x, y in coins_carrosserie(vehicule, vehicule.position, 1)]))
                chemin.closeSubpath()
                polygones.append(chemin)
            self.assertFalse(polygones[0].intersects(polygones[1]),
                             (simulation.temps, premier.identifiant, second.identifiant))

    def preparer_situation(self, origine="N", en_retour=False):
        simulation = Simulation(debit=0)
        simulation.demarrer_mission("02", "W")
        secours = simulation.obtenir_secours("02")
        secours.intervention_effectuee = en_retour
        secours.indice_passage = int(en_retour)
        if en_retour:
            origine = "W"
        simulation.feux.axe = secours.passage[2]
        secours.distance = secours.passage[0] - 120
        voiture = simulation.ajouter_voiture(origine, "straight")
        voiture.distance = voiture.passage[0] - voiture.longueur_manoeuvre
        secours.distance = secours.passage[0] - voiture.longueur_manoeuvre - 120
        return simulation, secours, voiture

    def test_voiture_se_range_attend_puis_repart_apres_secours(self):
        for en_retour in (False, True):
            with self.subTest(en_retour=en_retour):
                simulation, secours, voiture = self.preparer_situation(en_retour=en_retour)
                initiale = voiture.distance
                decalage_max = 0
                arrete_a_cote = False
                a_bouge_apres = False
                for _ in range(300):
                    simulation.avancer(PAS_TEMPS)
                    self.verifier_absence_contact(simulation)
                    decalage_max = max(decalage_max, voiture.decalage_lateral)
                    if voiture.cede_aux and voiture.decalage_lateral == DECALAGE_RANGEMENT:
                        arrete_a_cote = True
                        self.assertAlmostEqual(voiture.distance, initiale + voiture.longueur_manoeuvre)
                        self.assertTrue(voiture.en_attente)
                        self.assertEqual(voiture.vitesse_actuelle, 0)
                    if voiture.distance > initiale and voiture.decalage_lateral == 0:
                        a_bouge_apres = True
                        break
                self.assertEqual(decalage_max, DECALAGE_RANGEMENT)
                self.assertTrue(arrete_a_cote)
                self.assertTrue(a_bouge_apres)

    def test_secours_lointain_ou_disponible_ne_declenche_pas_rangement(self):
        simulation = Simulation(debit=0)
        voiture = simulation.ajouter_voiture("N", "straight")
        voiture.distance = voiture.passage[0] - 60
        simulation.avancer(1)
        self.assertEqual(voiture.decalage_lateral, 0)
        self.assertFalse(voiture.cede_aux)

    def test_rangement_change_position_affichee(self):
        simulation, secours, voiture = self.preparer_situation()
        origine_avant = voiture.position
        simulation.avancer(1)
        etat_voiture = next(v for v in simulation.etat_simulation().voitures if v.identifiant == voiture.identifiant)
        self.assertLess(etat_voiture.x, origine_avant[0])
        self.assertGreater(etat_voiture.y, origine_avant[1])
        self.assertNotEqual(etat_voiture.orientation, origine_avant[2])
        self.assertIn("cote", etat_voiture.etape)
        self.verifier_absence_contact(simulation)

    def test_suivante_tout_droit_entre_en_ralentissant_pendant_virage(self):
        for virage in ("left", "right"):
            with self.subTest(virage=virage):
                simulation = Simulation(debit=0)
                tete = simulation.ajouter_voiture("N", virage)
                tete.distance = tete.passage[0] + 70
                simulation.vehicules_engages.add(tete.identifiant)
                suivante = simulation.ajouter_voiture("N", "straight")
                suivante.distance = suivante.passage[0]
                simulation.avancer(PAS_TEMPS)
                self.assertIn(suivante.identifiant, simulation.vehicules_engages)
                self.assertIn(tete.identifiant, simulation.vehicules_engages)
                self.assertGreater(suivante.vitesse_actuelle, 0)
                self.assertLess(suivante.vitesse_actuelle, suivante.vitesse)
                for _ in range(200):
                    simulation.avancer(PAS_TEMPS)
                    self.verifier_absence_contact(simulation)
                self.assertIsNone(suivante.passage)

    def test_reinsertion_avec_suivante_proche_sans_blocage(self):
        simulation = Simulation(debit=0)
        tete = simulation.ajouter_voiture("N", "straight")
        tete.distance = tete.passage[0] - 100
        tete.decalage_lateral = DECALAGE_RANGEMENT
        suivante = simulation.ajouter_voiture("N", "straight")
        suivante.distance = tete.distance - 32
        initiale = (tete.distance, suivante.distance)
        for _ in range(160):
            simulation.avancer(PAS_TEMPS)
            self.verifier_absence_contact(simulation)
        self.assertEqual(tete.decalage_lateral, 0)
        self.assertGreater(tete.distance, initiale[0] + 100)
        self.assertGreater(suivante.distance, initiale[1] + 100)

    def test_voiture_deja_engagee_degage_sans_se_ranger(self):
        simulation, secours, voiture = self.preparer_situation()
        voiture.distance = voiture.passage[0] + 80
        voiture.decalage_lateral = DECALAGE_RANGEMENT
        simulation.vehicules_engages.add(voiture.identifiant)
        fin = voiture.passage[1]
        for _ in range(160):
            simulation.avancer(PAS_TEMPS)
            self.verifier_absence_contact(simulation)
            if voiture.distance >= fin:
                break
            self.assertFalse(voiture.cede_aux)
            self.assertGreater(voiture.vitesse_actuelle, 0)
        self.assertGreaterEqual(voiture.distance, fin)


if __name__ == "__main__":
    unittest.main()
