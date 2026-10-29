"""Verifier les commandes de la fenetre et leur effet sur le vrai client TCP."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from PyQt6.QtTest import QTest
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QApplication

from src.interface.fenetre_simulation import FenetreSimulation
from src.interface.fenetre_centre import FenetreCentre
from src.reseau.client import ClientEtats
from src.reseau.serveur import ServeurCentre
from test_reseau import StockageMemoire, attendre


class TestsInterface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def test_commandes_limite_debit_pause_vitesse_et_reinitialisation(self):
        fenetre = FenetreSimulation()
        self.addCleanup(fenetre.close)
        fenetre.show()
        self.application.processEvents()
        self.assertEqual(fenetre.choix_vitesse.currentText(), "x1")
        self.assertEqual(fenetre.vitesse, 2)
        fenetre.choix_debit.setValue(30)
        self.assertEqual(fenetre.choix_debit.value(), 25)
        self.assertEqual(fenetre.scenario.debit, 25)
        fenetre.choix_vitesse.setCurrentIndex(2)
        self.assertEqual(fenetre.vitesse, 3)
        fenetre.bouton_demarrer.click()
        QTest.qWait(200)
        self.assertGreater(fenetre.temps_ecoule, 0)
        fenetre.bouton_demarrer.click()
        en_pause = fenetre.temps_ecoule
        QTest.qWait(80)
        self.assertEqual(fenetre.temps_ecoule, en_pause)
        fenetre.bouton_recommencer.click()
        self.assertEqual(fenetre.temps_ecoule, 0)
        self.assertFalse(fenetre.en_cours)
        self.assertEqual(fenetre.scenario.debit, 25)

    def test_compteurs_reserves_horizontale_et_verticale(self):
        fenetre = FenetreSimulation()
        self.addCleanup(fenetre.close)
        feux = fenetre.scenario.feux
        from src.simulation.feux import DemandePriorite
        # Un vert NS prolonge a 22 s doit stocker 14 s sur la ligne horizontale.
        for _ in range(440):
            feux.avancer(.05, [DemandePriorite("02", "NS", 0, 0)], occupe=True)
        fenetre.actualiser()
        self.assertEqual(fenetre.etiquettes_reserves["EW"].text(), "14.0 s stockees")
        self.assertEqual(fenetre.etiquettes_reserves["NS"].text(), "0.0 s stockees")
        # La pause ne consomme rien ; recommencer remet bien les deux a zero.
        QTest.qWait(80)
        fenetre.actualiser()
        self.assertEqual(fenetre.etiquettes_reserves["EW"].text(), "14.0 s stockees")
        fenetre.bouton_recommencer.click()
        self.assertEqual(fenetre.etiquettes_reserves["EW"].text(), "0.0 s stockees")
        self.assertEqual(fenetre.etiquettes_reserves["NS"].text(), "0.0 s stockees")

    def test_arrivees_hors_carte_apres_redimensionnement(self):
        fenetre = FenetreSimulation()
        self.addCleanup(fenetre.close)
        fenetre.minuteur.stop()
        fenetre.show()
        fenetre.en_cours = True
        for largeur, hauteur in ((960, 680), (1600, 680), (1100, 720)):
            fenetre.resize(largeur, hauteur)
            self.application.processEvents()
            fenetre._actualiser_simulation()
            for origine in "NSEW":
                with self.subTest(taille=(largeur, hauteur), origine=origine):
                    fenetre.scenario.voitures.clear()
                    voiture = fenetre.scenario.ajouter_voiture(origine, "straight")
                    point = fenetre.vue.mapFromScene(QPointF(*voiture.position[:2]))
                    self.assertFalse(fenetre.vue.viewport().rect().contains(point))

    def test_envoi_mission_retour_et_reinitialisation_transmis_au_centre(self):
        stockage = StockageMemoire()
        serveur = ServeurCentre(stockage, "127.0.0.1", 0)
        serveur.demarrer()
        self.addCleanup(serveur.fermer)
        client = ClientEtats("127.0.0.1", serveur.port)
        client.demarrer()
        self.addCleanup(client.fermer)
        fenetre = FenetreSimulation(client)
        centre = FenetreCentre(serveur)
        self.addCleanup(centre.close)
        self.addCleanup(fenetre.close)
        for identifiant in ("01", "02"):
            fenetre.choix_secours.setCurrentIndex(fenetre.choix_secours.findData(identifiant))
            destination = "E" if identifiant == "01" else "W"
            fenetre.choix_destination.setCurrentIndex(fenetre.choix_destination.findData(destination))
            fenetre.bouton_envoi.click()
            self.assertFalse(fenetre.bouton_envoi.isEnabled())
            self.assertEqual(fenetre.scenario.obtenir_secours(identifiant).destination, destination)
        attendre(lambda: client.instantane()[1] == 0)
        centre.actualiser()
        self.assertEqual(centre.etats.item(0, 1).text(), "occupe")
        self.assertEqual(centre.etats.item(1, 1).text(), "occupe")
        fenetre.scenario.avancer(300)
        fenetre.temps_ecoule = fenetre.scenario.temps
        fenetre._publier_evenements()
        fenetre.actualiser()
        attendre(lambda: client.instantane()[1] == 0)
        centre.actualiser()
        for index, identifiant in enumerate(("01", "02")):
            self.assertEqual(centre.etats.item(index, 1).text(), "disponible")
            fenetre.choix_secours.setCurrentIndex(fenetre.choix_secours.findData(identifiant))
            self.assertTrue(fenetre.bouton_envoi.isEnabled())
        fenetre.choix_secours.setCurrentIndex(0)
        fenetre.bouton_envoi.click()
        fenetre.bouton_recommencer.click()
        attendre(lambda: client.instantane()[1] == 0)
        centre.actualiser()
        self.assertEqual(centre.etats.item(0, 1).text(), "disponible")
        self.assertEqual(centre.etats.item(1, 1).text(), "disponible")
        self.assertEqual(len(stockage.historique), 7)
