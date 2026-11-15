"""Regles metier du cahier des charges, sans interface ni reseau."""

from itertools import combinations
from math import hypot, inf
import unittest
from controles_circulation import verifier_espacement

from src.simulation.moteur import DISTANCE_SECURITE, Simulation
from src.simulation.feux import Feux, DemandePriorite


def avancer_feux(feux, duree, demandes=(), occupe=False, libre=True):
    """Fait avancer les feux par pas de 0,05 seconde avec les demandes données."""
    for _ in range(round(duree / 0.05)):
        feux.avancer(0.05, demandes, occupe, libre)

class TestsFeux(unittest.TestCase):
    """Tests du cycle des feux, des priorités et de la compensation du retard."""


    def test_cycle_feux(self):
        """Vérifie le cycle des feux et le maintien du tout rouge si le carrefour est occupé."""
        feux = Feux()
        avancer_feux(feux, 8)
        self.assertEqual(feux.signal("NS"), "amber")
        avancer_feux(feux, 1)
        self.assertEqual(feux.phase, "all_red")
        avancer_feux(feux, 2, libre=False)
        self.assertEqual(feux.phase, "all_red")
        avancer_feux(feux, .05)
        self.assertEqual(feux.signal("EW"), "green")

    def test_arbitrage_feux(self):
        """Vérifie le choix du secours prioritaire et le maintien de sa priorité."""
        feux = Feux()
        premier = DemandePriorite("02", "EW", 1, 5)
        second = DemandePriorite("01", "NS", 2, 4)
        avancer_feux(feux, .05, [second, premier], True)
        self.assertEqual(feux.prioritaire.identifiant, "02")
        ancien = DemandePriorite("01", "NS", 0, 4)
        avancer_feux(feux, .05, [ancien, premier], True)
        self.assertEqual(feux.prioritaire.identifiant, "02")
        avancer_feux(feux, .05, [ancien], True)
        self.assertEqual(feux.prioritaire.identifiant, "01")
        feux = Feux()
        avancer_feux(feux, .05, [DemandePriorite("02", "NS", 0, 4), DemandePriorite("01", "NS", 0, 5)], True)
        self.assertEqual(feux.prioritaire.identifiant, "02")
        feux = Feux()
        avancer_feux(feux, .05, [DemandePriorite("02", "NS", 0, 4), DemandePriorite("01", "NS", 0, 4)], True)
        self.assertEqual(feux.prioritaire.identifiant, "01")

    def test_priorite_opposee(self):
        """Vérifie la transition vers l'axe prioritaire après dégagement du carrefour."""
        feux = Feux()
        avancer_feux(feux, 1)
        demande = [DemandePriorite("01", "EW", 0, 0)]
        avancer_feux(feux, .05, demande, True)
        self.assertEqual(feux.phase, "amber")
        avancer_feux(feux, 1, demande, True)
        self.assertEqual(feux.phase, "all_red")
        avancer_feux(feux, 2, demande, True, libre=False)
        self.assertEqual(feux.phase, "all_red")
        avancer_feux(feux, .05, demande, True)
        self.assertEqual(feux.signal("EW"), "green")

    def test_axe_retour(self):
        """Vérifie que la demande du secours change d'axe pour son retour."""
        feux = Feux()
        avancer_feux(feux, 1, [DemandePriorite("01", "NS", 0, 0)], True)
        avancer_feux(feux, .05, [DemandePriorite("01", "EW", 0, 1)], True)
        self.assertEqual(feux.prioritaire.axe, "EW")
        self.assertEqual(feux.phase, "amber")
        avancer_feux(feux, 2, [DemandePriorite("01", "EW", 0, 1)], True)
        self.assertEqual(feux.signal("EW"), "green")

    def test_compensation_quart(self):
        """Vérifie l'accumulation du retard et sa restitution par quarts."""
        feux = Feux()
        avancer_feux(feux, 10, [DemandePriorite("01", "NS", 0, 0)], True)
        avancer_feux(feux, 10, [DemandePriorite("02", "NS", 1, 1)], True)
        self.assertAlmostEqual(feux.reserve_temps["EW"], 12)
        avancer_feux(feux, 2.05, occupe=True)
        self.assertEqual(feux.signal("EW"), "green")
        self.assertTrue(feux.en_compensation)
        self.assertAlmostEqual(feux.bonus_compensation, 3)
        avancer_feux(feux, 8)
        self.assertAlmostEqual(feux.reserve_temps["EW"], 12)
        avancer_feux(feux, 3)
        self.assertAlmostEqual(feux.reserve_temps["EW"], 9)
        self.assertEqual(feux.phase, "amber")
        avancer_feux(feux, 2)
        self.assertEqual(feux.axe, "NS")
        self.assertFalse(feux.en_compensation)
        avancer_feux(feux, 10)
        self.assertEqual(feux.axe, "EW")
        self.assertAlmostEqual(feux.bonus_compensation, 2.25)
        avancer_feux(feux, 10.25)
        self.assertAlmostEqual(feux.reserve_temps["EW"], 6.75)
        self.assertEqual(feux.phase, "amber")

    def test_accumulation_axes(self):
        """Vérifie le retard de chaque axe sans compter deux fois les mêmes secondes."""
        for axe, axe_oppose in (("NS", "EW"), ("EW", "NS")):
            with self.subTest(axe=axe):
                feux = Feux()
                feux.axe = axe
                demande = [DemandePriorite("02", axe, 0, 0)]
                avancer_feux(feux, 8, demande, True)
                self.assertAlmostEqual(feux.reserve_temps[axe_oppose], 0)
                avancer_feux(feux, 14, demande, True)
                self.assertAlmostEqual(feux.reserve_temps[axe_oppose], 14)
                self.assertEqual(feux.reserve_temps[axe], 0)
                avancer_feux(feux, 2.05, occupe=True)
                self.assertTrue(feux.en_compensation)
                avancer_feux(feux, 8, occupe=True)
                self.assertAlmostEqual(feux.reserve_temps[axe_oppose], 14)
                avancer_feux(feux, 1, occupe=True)
                self.assertAlmostEqual(feux.reserve_temps[axe_oppose], 13)
                self.assertEqual(feux.reserve_temps[axe], 0)

    def test_mission_lointaine(self):
        """Vérifie qu'une mission éloignée ne retarde pas la compensation."""
        feux = Feux()
        avancer_feux(feux, 12, [DemandePriorite("01", "NS", 0, 0)], True)
        avancer_feux(feux, 2.05, occupe=True)
        self.assertTrue(feux.en_compensation)
        self.assertAlmostEqual(feux.bonus_compensation, 1)
        avancer_feux(feux, 9, occupe=True)
        self.assertAlmostEqual(feux.reserve_temps["EW"], 3)
        self.assertEqual(feux.phase, "amber")

    def test_reserves_opposees(self):
        """Vérifie que les réserves opposées se soustraient avant le calcul du bonus."""
        feux = Feux()
        feux.reserve_temps.update(NS=17, EW=15)
        avancer_feux(feux, .05)
        self.assertEqual(feux.reserve_temps, {"NS": 2, "EW": 0})
        avancer_feux(feux, 9.95)
        self.assertEqual(feux.axe, "EW")
        self.assertFalse(feux.en_compensation)
        avancer_feux(feux, 10)
        self.assertEqual(feux.axe, "NS")
        self.assertAlmostEqual(feux.bonus_compensation, .5)
        avancer_feux(feux, 8.5)
        self.assertAlmostEqual(feux.reserve_temps["NS"], 1.5)

    def test_reserves_egales(self):
        """Vérifie que deux réserves égales s'annulent."""
        feux = Feux()
        feux.reserve_temps.update(NS=15, EW=15)
        avancer_feux(feux, 30)
        self.assertEqual(feux.reserve_temps, {"NS": 0, "EW": 0})
        self.assertFalse(feux.en_compensation)

    def test_bonus_interrompu(self):
        """Vérifie qu'une priorité interrompt le bonus sans perdre le temps encore dû."""
        feux = Feux()
        feux.reserve_temps["EW"] = 8
        avancer_feux(feux, 10)
        self.assertEqual(feux.axe, "EW")
        self.assertAlmostEqual(feux.bonus_compensation, 2)
        avancer_feux(feux, 9)
        self.assertAlmostEqual(feux.reserve_temps["EW"], 7)
        avancer_feux(feux, .05, [DemandePriorite("01", "NS", 0, 0)], True)
        self.assertEqual(feux.phase, "amber")
        self.assertFalse(feux.en_compensation)
        self.assertAlmostEqual(feux.reserve_temps["EW"], 7)
        avancer_feux(feux, 2, [DemandePriorite("01", "NS", 0, 0)], True)
        self.assertEqual(feux.signal("NS"), "green")
        avancer_feux(feux, 1, [DemandePriorite("01", "NS", 0, 0)], True)
        avancer_feux(feux, 2.05)
        self.assertEqual(feux.axe, "EW")
        self.assertTrue(feux.en_compensation)
        self.assertAlmostEqual(feux.bonus_compensation, 1.75)

    def test_bonus_decompte(self):
        """Vérifie qu'une priorité sur le même axe ne recompte pas le bonus déjà rendu."""
        feux = Feux()
        feux.reserve_temps["EW"] = 8
        avancer_feux(feux, 10)
        avancer_feux(feux, 9)
        self.assertAlmostEqual(feux.reserve_temps["EW"], 7)
        avancer_feux(feux, 1, [DemandePriorite("01", "EW", 0, 0)], True)
        self.assertFalse(feux.en_compensation)
        # Une seule seconde de priorite nouvelle compense une seconde du solde.
        # La seconde de bonus deja servie ne doit pas etre recomptee.
        self.assertAlmostEqual(feux.reserve_temps["EW"], 6)
        self.assertEqual(feux.reserve_temps["NS"], 0)

    def test_petite_reserve(self):
        """Vérifie qu'une petite réserve est entièrement restituée."""
        feux = Feux()
        feux.reserve_temps["EW"] = .12
        for _ in range(1200):
            feux.avancer(.05)
            if not any(feux.reserve_temps.values()):
                break
        self.assertEqual(feux.reserve_temps, {"NS": 0, "EW": 0})
        avancer_feux(feux, 20)
        self.assertFalse(feux.en_compensation)
        self.assertEqual(feux.bonus_compensation, 0)

    def test_budget_bonus(self):
        """Vérifie que le bonus ne dépasse pas le temps prévu."""
        feux = Feux()
        feux.reserve_temps["EW"] = 1.01
        avancer_feux(feux, 10)
        self.assertAlmostEqual(feux.bonus_compensation, .2525)
        avancer_feux(feux, 8.3)
        self.assertEqual(feux.phase, "amber")
        self.assertAlmostEqual(feux.reserve_temps["EW"], .7575)

    def test_reserve_conservee(self):
        """Vérifie qu'une priorité avant le bonus conserve la réserve non utilisée."""
        feux = Feux()
        feux.reserve_temps["EW"] = 8
        avancer_feux(feux, 10)
        avancer_feux(feux, 2)
        avancer_feux(feux, .05, [DemandePriorite("01", "EW", 0, 0)], True)
        self.assertFalse(feux.en_compensation)
        self.assertAlmostEqual(feux.reserve_temps["EW"], 8)
        avancer_feux(feux, .05)
        self.assertEqual(feux.phase, "amber")
        avancer_feux(feux, 12)
        self.assertEqual(feux.axe, "EW")
        self.assertAlmostEqual(feux.bonus_compensation, 2)
        avancer_feux(feux, 10)
        self.assertAlmostEqual(feux.reserve_temps["EW"], 6)

    def test_compensation_rouge(self):
        """Vérifie qu'une courte priorité ne restitue pas la réserve pendant le tout rouge."""
        feux = Feux()
        feux.reserve_temps["EW"] = 4
        demande = [DemandePriorite("01", "NS", 0, 0)]
        avancer_feux(feux, 1, demande, True)
        avancer_feux(feux, .05)
        avancer_feux(feux, 1)
        self.assertEqual(feux.phase, "all_red")
        avancer_feux(feux, 3, libre=False)
        self.assertEqual(feux.phase, "all_red")
        self.assertAlmostEqual(feux.reserve_temps["EW"], 4)
        avancer_feux(feux, .05)
        self.assertEqual(feux.axe, "EW")
        self.assertAlmostEqual(feux.bonus_compensation, 1)
        avancer_feux(feux, 9)
        self.assertAlmostEqual(feux.reserve_temps["EW"], 3)

    def test_nouvelle_reserve(self):
        """Vérifie qu'une nouvelle réserve réduit d'abord le solde de l'autre axe."""
        feux = Feux()
        feux.reserve_temps["NS"] = 2
        demande = [DemandePriorite("01", "NS", 0, 0)]
        avancer_feux(feux, 9, demande, True)
        self.assertAlmostEqual(feux.reserve_temps["NS"], 1)
        self.assertAlmostEqual(feux.reserve_temps["EW"], 0)
        avancer_feux(feux, 2, demande, True)
        self.assertAlmostEqual(feux.reserve_temps["NS"], 0)
        self.assertAlmostEqual(feux.reserve_temps["EW"], 1)

    def test_priorite_courte(self):
        """Vérifie qu'une courte priorité ne crée pas de réserve."""
        feux = Feux()
        avancer_feux(feux, 5, [DemandePriorite("01", "NS", 0, 0)], True)
        avancer_feux(feux, 2.05)
        self.assertEqual(feux.reserve_temps, {"NS": 0, "EW": 0})
        self.assertFalse(feux.en_compensation)

class TestsSimulation(unittest.TestCase):
    """Tests de la circulation et des missions sur plusieurs pas de simulation."""


    def test_seuil_priorite(self):
        """Vérifie la distance, le délai d'arrivée et les seuils de demande de priorité."""
        simulation = Simulation(debit=0)
        simulation.demarrer_mission("01")
        vehicule = simulation.secours[0]
        vehicule.vitesse = 40
        vehicule.passages = ((2000, 2200, "NS"),)
        # La sortie de caserne demande desormais le vert sans attendre le seuil.
        # Tester la regle d'approche une fois cette sortie deja franchie.
        vehicule.distance = next(fin for _, fin, cle in vehicule.trajet.raccordements if cle == "F")
        self.assertEqual(simulation.demandes(), [])
        vehicule.distance = 1700
        self.assertEqual(simulation.approche(vehicule), (150, 7.5))
        self.assertEqual(len(simulation.demandes()), 1)
        vehicule.distance = 1599
        self.assertEqual(simulation.demandes(), [])
        vehicule.distance = 1600
        self.assertEqual(len(simulation.demandes()), 1)
        vehicule.vitesse = 0
        self.assertEqual(simulation.approche(vehicule)[1], inf)

    def test_arret_feu(self):
        """Vérifie l'arrêt au rouge, la reprise au vert et la fin du trajet."""
        simulation = Simulation(debit=0)
        voiture = simulation.ajouter_voiture("E", "straight")
        voiture.distance = voiture.passage[0] - 2
        simulation.avancer(3)
        self.assertAlmostEqual(voiture.distance, voiture.passage[0])
        self.assertTrue(voiture.en_attente)
        simulation.avancer(10)
        self.assertGreater(voiture.distance, voiture.passage[0])
        simulation.avancer(30)
        self.assertEqual(simulation.trajets_termines, 1)

    def test_file_secours(self):
        """Vérifie l'espacement de cinq voitures et l'attente du second secours."""
        simulation = Simulation(debit=0)
        simulation.feux.axe = "EW"
        voitures = []
        for index in range(5):
            voiture = simulation.ajouter_voiture("N", "straight")
            voiture.distance = voiture.passage[0] - 50 * index
            voitures.append(voiture)
        simulation.avancer(5)
        self.assertTrue(all(v.en_attente for v in voitures))
        self.assertTrue(all(hypot(a.position[0] - b.position[0], a.position[1] - b.position[1]) >= DISTANCE_SECURITE - 1e-6
                            for a, b in combinations(voitures, 2)))
        simulation = Simulation(debit=0)
        simulation.demarrer_mission("01")
        simulation.demarrer_mission("02")
        premier, second = simulation.secours
        premier.distance = premier.passages[0][0]
        second.distance = second.passages[1][0]
        second.indice_passage = 1
        second.intervention_effectuee = True
        simulation.avancer(.1)
        self.assertEqual(simulation.feux.prioritaire.identifiant, "01")
        self.assertEqual(second.distance, second.passages[1][0])

    def test_simulation_longue(self):
        """Vérifie dix minutes de circulation sans contact et la fin des deux missions."""
        for graine, debit in ((302, 12), (51, 40)):
            with self.subTest(graine=graine, debit=debit):
                simulation = Simulation(debit=debit, graine=graine)
                simulation.demarrer_mission("01")
                simulation.demarrer_mission("02")
                precedent = 0
                for pas in range(1200):
                    simulation.avancer(.5)
                    self.assertLessEqual(len(simulation.voitures), 25)
                    verifier_espacement(self, simulation)
                    engage = [v for v in simulation.vehicules if v.passage and v.passage[0] < v.distance < v.passage[1]]
                    for a, b in combinations(engage, 2):
                        self.assertTrue(simulation.passages_compatibles(a, b))
                    if pas == 1079:
                        precedent = simulation.trajets_termines
                self.assertGreater(simulation.trajets_termines, precedent)
                self.assertTrue(all(not v.occupe for v in simulation.secours))
                self.assertIn(("01", "disponible"), simulation.evenements)
                self.assertIn(("02", "disponible"), simulation.evenements)

    def test_pas_fixe(self):
        """Vérifie que le résultat ne dépend pas de la fréquence de rafraîchissement."""
        premier, second = Simulation(), Simulation()
        premier.avancer(10)
        for _ in range(1000):
            second.avancer(.01)
        self.assertAlmostEqual(premier.temps, second.temps)
        self.assertEqual([(v.identifiant, v.distance) for v in premier.voitures],
                         [(v.identifiant, v.distance) for v in second.voitures])
