"""Le stationnement en intervention ne reserve pas les feux du retour."""

import unittest

from src.modeles.plan import DESTINATIONS, sur_chaussee
from src.simulation.moteur import DUREE_INTERVENTION, PAS_TEMPS, Simulation
from controles_circulation import verifier_espacement


class TestsPrioriteParking(unittest.TestCase):
    def secours_gare(self, destination, identifiant="01"):
        simulation = Simulation(debit=0)
        simulation.demarrer_mission(identifiant, destination)
        secours = simulation.obtenir_secours(identifiant)
        secours.distance = secours.arret_intervention
        secours.indice_passage = 1
        secours.intervention_effectuee = True
        secours.temps_intervention_restant = DUREE_INTERVENTION
        return simulation, secours

    def test_aucune_demande_retour_pendant_aller(self):
        for destination in DESTINATIONS:
            with self.subTest(destination=destination):
                simulation, secours = self.secours_gare(destination)
                secours.intervention_effectuee = False
                secours.temps_intervention_restant = 0
                # Apres la sortie du carrefour, le prochain passage est le
                # retour, mais le secours doit d'abord atteindre le patient.
                debut = secours.passages[0][1]
                for distance in range(int(debut) + 1, int(secours.arret_intervention), 5):
                    secours.distance = distance
                    self.assertEqual(simulation.demandes(), [], (destination, distance))

    def test_secours_gare_ne_reserve_pas_feux_ni_temps(self):
        for destination in DESTINATIONS:
            with self.subTest(destination=destination):
                simulation, secours = self.secours_gare(destination)
                simulation.feux.axe = secours.passage[2]
                simulation.feux.temps_ecoule = 12
                simulation.feux.reserve_temps.update(NS=3, EW=0)
                reserve_temps = dict(simulation.feux.reserve_temps)
                for _ in range(round(DUREE_INTERVENTION / PAS_TEMPS)):
                    self.assertEqual(simulation.demandes(), [])
                    simulation.avancer(PAS_TEMPS)
                    self.assertIsNone(simulation.feux.prioritaire)
                    self.assertEqual(secours.distance, secours.arret_intervention)
                    for axe in reserve_temps:
                        self.assertLessEqual(simulation.feux.reserve_temps[axe], reserve_temps[axe])
                self.assertTrue(secours.occupe)

    def test_demande_retour_sur_route_et_proche_carrefour(self):
        for destination in DESTINATIONS:
            with self.subTest(destination=destination):
                simulation, secours = self.secours_gare(destination)
                secours.temps_intervention_restant = 0
                a_vu_allee = a_vu_route = a_vu_demande = False
                # Parcourir tout le retour au carrefour, y compris l'allee.
                for distance in range(int(secours.arret_intervention) + 1, int(secours.passage[0])):
                    secours.distance = distance
                    route = sur_chaussee(*secours.position[:2])
                    metres, delai_arrivee = simulation.approche(secours)
                    attendu = route and (metres <= 150 or delai_arrivee <= 10)
                    demandes = simulation.demandes()
                    self.assertEqual(bool(demandes), attendu, (destination, distance))
                    a_vu_allee |= not route
                    a_vu_route |= route
                    a_vu_demande |= bool(demandes)
                    if demandes:
                        self.assertEqual(demandes[0].debut_mission, secours.debut_mission)
                self.assertTrue(a_vu_allee and a_vu_route and a_vu_demande)

    def test_second_secours_passe_pendant_soins_du_premier_a_mairie(self):
        for identifiant_gare in ("01", "02"):
            for en_retour in (False, True):
                with self.subTest(gare=identifiant_gare, second_returning=en_retour):
                    simulation, gare = self.secours_gare("W", identifiant_gare)
                    simulation.temps = 30
                    identifiant_second = "02" if identifiant_gare == "01" else "01"
                    simulation.demarrer_mission(identifiant_second, "E")
                    second = simulation.obtenir_secours(identifiant_second)
                    second.intervention_effectuee = en_retour
                    second.indice_passage = int(en_retour)
                    second.distance = second.passage[0]
                    simulation.feux.axe = "EW"
                    for _ in range(140):
                        simulation.avancer(PAS_TEMPS)
                        verifier_espacement(self, simulation)
                        self.assertGreater(gare.temps_intervention_restant, 0)
                        self.assertEqual(gare.distance, gare.arret_intervention)
                        self.assertEqual(simulation.feux.prioritaire.identifiant, identifiant_second)
                        if second.identifiant in simulation.vehicules_engages:
                            self.assertEqual(simulation.feux.signal(second.passage[2]), "green")
                            break
                    else:
                        self.fail("Le secours gare a empeche le second de passer.")


if __name__ == "__main__":
    unittest.main()
