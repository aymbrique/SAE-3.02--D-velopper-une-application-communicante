"""Depart des secours au milieu d'une file Nord deja formee au rouge."""

import unittest
from controles_circulation import verifier_espacement

from src.simulation.moteur import DISTANCE_SECURITE, PAS_TEMPS, Simulation
from src.simulation.feux import DemandePriorite
from src.simulation.priorite import DECALAGE_RANGEMENT


class TestsDepartCaserne(unittest.TestCase):
    def preparer_retour_et_depart(self, identifiant_retour="02"):
        simulation = Simulation(debit=0)
        simulation.demarrer_mission(identifiant_retour, "W")
        en_retour = simulation.obtenir_secours(identifiant_retour)
        en_retour.intervention_effectuee = True
        en_retour.indice_passage = 2
        en_retour.distance = [arret for arret, _, cle in en_retour.trajet.raccordements if cle == "F"][-1]
        simulation.temps = 10
        identifiant_depart = "01" if identifiant_retour == "02" else "02"
        simulation.demarrer_mission(identifiant_depart, "W")
        sortie_direction = simulation.obtenir_secours(identifiant_depart)
        sortie_direction.distance = next(arret for arret, _, cle in sortie_direction.trajet.raccordements if cle == "F")
        voitures = []
        for index, y in enumerate((296, 340, 384)):
            voiture = simulation.ajouter_voiture("S", "straight")
            distance_sortie = voiture.passages[0][1]
            voiture.distance = distance_sortie + voiture.trajet.position_a(distance_sortie)[1] - y
            voiture.indice_passage = 1
            if index == 0:
                voiture.decalage_lateral = DECALAGE_RANGEMENT
                voiture.cede_aux = (identifiant_retour,)
            else:
                voiture.debut_manoeuvre = voiture.distance - 36 + 12 * index
                voiture.decalage_cible = DECALAGE_RANGEMENT
                voiture.decalage_lateral, _ = voiture.decalage_lateral_a(voiture.distance)
            voitures.append(voiture)
        return simulation, en_retour, sortie_direction, voitures

    def test_retour_et_depart_liberent_caserne_avec_voitures_en_manoeuvre(self):
        for identifiant in ("01", "02"):
            with self.subTest(en_retour=identifiant):
                simulation, en_retour, sortie_direction, voitures = self.preparer_retour_et_depart(identifiant)
                demarre = simulation.temps
                instant_retour = None
                for _ in range(1600):
                    self.avancer_un_pas_sans_collision(simulation)
                    for tete, suivante in zip(voitures, voitures[1:]):
                        if tete in simulation.voitures and suivante in simulation.voitures:
                            self.assertGreaterEqual(tete.distance - suivante.distance, DISTANCE_SECURITE - 1e-6)
                    if not en_retour.occupe and instant_retour is None:
                        instant_retour = simulation.temps
                    if all(not secours.occupe for secours in simulation.secours):
                        break
                self.assertIsNotNone(instant_retour)
                self.assertLess(instant_retour - demarre, 15)
                self.assertFalse(sortie_direction.occupe)
                self.assertTrue(all(voiture.decalage_lateral == 0 for voiture in voitures))

    def test_retour_attend_depart_bloque(self):
        simulation, en_retour, sortie_direction, _ = self.preparer_retour_et_depart()
        sortie_direction.vitesse = 0
        arret = en_retour.distance
        for _ in range(100):
            self.avancer_un_pas_sans_collision(simulation)
        self.assertEqual(en_retour.distance, arret)
        self.assertTrue(en_retour.en_attente)
        sortie_direction.vitesse = 56
        for _ in range(400):
            self.avancer_un_pas_sans_collision(simulation)
            if not en_retour.occupe:
                break
        self.assertFalse(en_retour.occupe)

    def test_nouvelle_mission_pendant_retour_et_trafic_dense(self):
        simulation = Simulation(debit=60, graine=302)
        simulation.avancer(30)
        simulation.demarrer_mission("02", "W")
        en_retour = simulation.obtenir_secours("02")
        arret_caserne = [arret for arret, _, cle in en_retour.trajet.raccordements if cle == "F"][-1]
        lance = False
        for _ in range(3600):
            if (en_retour.intervention_effectuee and en_retour.distance >= arret_caserne - 250
                    and not lance):
                self.assertTrue(simulation.demarrer_mission("01", "W"))
                lance = True
            self.avancer_un_pas_sans_collision(simulation)
            if lance and all(not secours.occupe for secours in simulation.secours):
                break
        self.assertTrue(lance)
        self.assertTrue(all(not secours.occupe for secours in simulation.secours))

    def creer_file_nord(self):
        simulation = Simulation(debit=0)
        simulation.feux.axe = "EW"
        voitures = []
        for index in range(11):
            voiture = simulation.ajouter_voiture("N", "straight")
            self.assertIsNotNone(voiture)
            voiture.distance = voiture.passage[0] - index * DISTANCE_SECURITE
            voiture.en_attente = True
            voitures.append(voiture)
        arret_caserne = next(arret for arret, _, cle in voitures[0].trajet.raccordements if cle == "F")
        aval = [voiture for voiture in voitures if voiture.distance > arret_caserne]
        amont = [voiture for voiture in voitures if voiture.distance <= arret_caserne]
        self.assertGreater(len(aval), 5)
        self.assertGreaterEqual(len(amont), 2)
        return simulation, voitures, arret_caserne, aval, amont

    def avancer_un_pas_sans_collision(self, simulation):
        avant = [(vehicule, vehicule.distance, vehicule.passage)
                  for vehicule in simulation.vehicules]
        simulation.avancer(PAS_TEMPS)
        for vehicule, precedent, passage in avant:
            if passage and precedent <= passage[0] < vehicule.distance:
                self.assertEqual(simulation.feux.signal(passage[2]), "green",
                                 (simulation.temps, vehicule.identifiant, "entree au rouge"))
        verifier_espacement(self, simulation)

    def premier_acces_caserne(self, secours):
        return next(zone for zone in secours.trajet.raccordements if zone[2] == "F")

    def test_depart_demande_vert_vertical_avant_seuil_normal(self):
        for identifiant in ("01", "02"):
            with self.subTest(secours=identifiant):
                simulation, _, _, aval, _ = self.creer_file_nord()
                simulation.demarrer_mission(identifiant, "W")
                secours = simulation.obtenir_secours(identifiant)
                secours.vitesse = 40  # Verifier le declenchement meme hors seuil usuel.
                metres, delai_arrivee = simulation.approche(secours)
                self.assertGreater(metres, 150)
                self.assertGreater(delai_arrivee, 10)
                precedent = {voiture.identifiant: voiture.distance for voiture in aval}
                self.avancer_un_pas_sans_collision(simulation)
                self.assertIsNotNone(simulation.feux.prioritaire)
                self.assertEqual(simulation.feux.prioritaire.identifiant, identifiant)
                self.assertEqual(simulation.feux.prioritaire.axe, "NS")
                # Conserver la transition orange/tout rouge avant de vider la file.
                self.assertEqual(simulation.feux.signal("NS"), "red")
                for _ in range(60):
                    self.avancer_un_pas_sans_collision(simulation)
                self.assertEqual(simulation.feux.signal("NS"), "green")
                self.assertTrue(all(voiture.distance > precedent[voiture.identifiant] or voiture.decalage_lateral > 0
                                    for voiture in aval))

    def test_amont_attend_vidange_aval_puis_suit_secours(self):
        for identifiant in ("01", "02"):
            with self.subTest(secours=identifiant):
                simulation, _, arret_caserne, aval, amont = self.creer_file_nord()
                precedent = {voiture.identifiant: voiture.distance for voiture in aval}
                simulation.demarrer_mission(identifiant, "W")
                secours = simulation.obtenir_secours(identifiant)
                _, fin_caserne, _ = self.premier_acces_caserne(secours)
                for _ in range(800):
                    self.avancer_un_pas_sans_collision(simulation)
                    if secours.distance >= fin_caserne:
                        break
                    self.assertTrue(all(voiture.distance <= arret_caserne + 1e-6
                                        for voiture in amont))
                self.assertGreaterEqual(secours.distance, fin_caserne)
                self.assertLess(simulation.temps, 40)
                self.assertTrue(all(voiture.distance > precedent[voiture.identifiant] or voiture.decalage_lateral > 0
                                    for voiture in aval))
                for _ in range(100):
                    self.avancer_un_pas_sans_collision(simulation)
                    if all(voiture.distance > arret_caserne for voiture in amont):
                        break
                self.assertTrue(all(voiture.distance > arret_caserne for voiture in amont))
                for _ in range(4000):
                    self.avancer_un_pas_sans_collision(simulation)
                    if not secours.occupe:
                        break
                self.assertFalse(secours.occupe)

    def test_deux_secours_finissent_avec_file_nord_dense(self):
        simulation, _, arret_caserne, _, amont = self.creer_file_nord()
        simulation.demarrer_mission("01", "N")
        simulation.demarrer_mission("02", "E")
        self.avancer_un_pas_sans_collision(simulation)
        self.assertIsNotNone(simulation.feux.prioritaire)
        self.assertEqual(simulation.feux.prioritaire.axe, "NS")
        caserne_degagee = set()
        for _ in range(5000):
            self.avancer_un_pas_sans_collision(simulation)
            for secours in simulation.secours:
                _, fin, _ = self.premier_acces_caserne(secours)
                if secours.distance >= fin or not secours.occupe:
                    caserne_degagee.add(secours.identifiant)
            if len(caserne_degagee) < len(simulation.secours):
                self.assertTrue(all(voiture.distance <= arret_caserne + 1e-6
                                    for voiture in amont))
            if all(not secours.occupe for secours in simulation.secours):
                break
        self.assertEqual(caserne_degagee, {"01", "02"})
        self.assertTrue(all(not secours.occupe for secours in simulation.secours))
        self.assertTrue(all(voiture.distance > arret_caserne for voiture in amont))
        self.assertIn(("01", "disponible"), simulation.evenements)
        self.assertIn(("02", "disponible"), simulation.evenements)

    def test_secours_avance_dans_allee_pendant_vidange_puis_attend_route(self):
        for identifiant in ("01", "02"):
            with self.subTest(secours=identifiant):
                simulation, voitures, _, _, _ = self.creer_file_nord()
                simulation.demarrer_mission(identifiant, "W")
                secours = simulation.obtenir_secours(identifiant)
                arret_secours, fin_secours, _ = self.premier_acces_caserne(secours)
                arret_voiture, fin_voiture, _ = next(zone for zone in voitures[0].trajet.raccordements
                                           if zone[2] == "F")
                for _ in range(20):
                    self.avancer_un_pas_sans_collision(simulation)
                # L'allee est libre meme si des voitures occupent encore la route.
                self.assertGreater(secours.distance, 0)
                self.assertLess(secours.distance, arret_secours)
                self.assertTrue(any(arret_voiture < voiture.distance < fin_voiture for voiture in voitures))
                a_attendu_route = False
                for _ in range(200):
                    self.avancer_un_pas_sans_collision(simulation)
                    if abs(secours.distance - arret_secours) < 1e-6 and secours.en_attente:
                        a_attendu_route = True
                        self.assertTrue(any(arret_voiture < voiture.distance < fin_voiture for voiture in voitures))
                        break
                self.assertTrue(a_attendu_route)
                for _ in range(800):
                    self.avancer_un_pas_sans_collision(simulation)
                    if secours.distance >= fin_secours:
                        break
                self.assertGreaterEqual(secours.distance, fin_secours)

    def test_retour_demande_vert_vertical_jusqu_au_degagement_caserne(self):
        for destination in ("W", "E", "N", "S"):
            with self.subTest(destination=destination):
                simulation = Simulation(debit=0)
                simulation.demarrer_mission("01", destination)
                secours = simulation.obtenir_secours("01")
                secours.intervention_effectuee = True
                secours.indice_passage = 1
                _, fin, axe = secours.passage
                secours.distance = fin - 1
                simulation.vehicules_engages.add(secours.identifiant)
                simulation.feux.axe = axe
                simulation.feux.prioritaire = DemandePriorite(secours.identifiant, axe, 0, 0)
                self.avancer_un_pas_sans_collision(simulation)
                self.assertIsNone(secours.passage)
                demandes = [demande for demande in simulation.demandes()
                            if demande.identifiant == secours.identifiant]
                self.assertEqual(len(demandes), 1)
                self.assertEqual(demandes[0].axe, "NS")
                self.avancer_un_pas_sans_collision(simulation)
                self.assertEqual(simulation.feux.prioritaire.identifiant, secours.identifiant)
                self.assertEqual(simulation.feux.prioritaire.axe, "NS")
                for _ in range(42):
                    self.avancer_un_pas_sans_collision(simulation)
                self.assertEqual(simulation.feux.signal("NS"), "green")
                self.assertTrue(secours.occupe)

    def test_retour_libere_second_secours_puis_deux_degagent_caserne(self):
        simulation, _, _, _, _ = self.creer_file_nord()
        simulation.demarrer_mission("01", "W")
        simulation.demarrer_mission("02", "E")
        premier, second = simulation.secours
        for secours in simulation.secours:
            secours.intervention_effectuee = True
            secours.indice_passage = 1
        premier.distance = premier.passage[1] - 1
        second.distance = second.passage[0]
        arret_second = second.distance
        simulation.vehicules_engages.add(premier.identifiant)
        simulation.feux.axe = "EW"
        simulation.feux.prioritaire = DemandePriorite(premier.identifiant, "EW", 0, 0,
                                   passage=1, engage=True)
        self.avancer_un_pas_sans_collision(simulation)
        self.assertIsNone(premier.passage)
        self.assertEqual(second.distance, arret_second)
        self.avancer_un_pas_sans_collision(simulation)
        self.assertEqual(simulation.feux.prioritaire.identifiant, second.identifiant)
        self.assertEqual(simulation.feux.prioritaire.axe, "EW")
        self.assertGreater(second.distance, arret_second)
        self.assertTrue(premier.occupe)  # Le second n'attend pas le retour complet.
        vert_nord = False
        for _ in range(4000):
            self.avancer_un_pas_sans_collision(simulation)
            if second.identifiant in simulation.vehicules_engages:
                self.assertEqual(simulation.feux.prioritaire.identifiant, second.identifiant)
                self.assertEqual(simulation.feux.signal("EW"), "green")
            vert_nord |= simulation.feux.signal("NS") == "green"
            if all(not secours.occupe for secours in simulation.secours):
                break
        self.assertTrue(vert_nord)
        self.assertTrue(all(not secours.occupe for secours in simulation.secours))


if __name__ == "__main__":
    unittest.main()
