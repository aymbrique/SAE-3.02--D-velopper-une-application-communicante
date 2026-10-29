"""Controle du rendu : aires hors chaussee et routes jusqu'aux bords."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QApplication

from src.interface.carte import VueCarte
from src.modeles.plan import CX, CY, NOEUDS, DEMI_LARGEUR_ROUTE, HAUTEUR_SCENE, LARGEUR_SCENE, ENTREES_SITES


class TestsCarte(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def dessiner_carte(self):
        vue = VueCarte()
        self.addCleanup(vue.close)
        image = QImage(LARGEUR_SCENE, HAUTEUR_SCENE, QImage.Format.Format_RGB32)
        image.fill(QColor("#a8cf8a"))
        peintre = QPainter(image)
        vue.scene().render(peintre, QRectF(0, 0, LARGEUR_SCENE, HAUTEUR_SCENE), vue.sceneRect())
        peintre.end()
        return image

    def test_terrains_arretes_au_bord_chaussee(self):
        image = self.dessiner_carte()
        for cote, entree in ENTREES_SITES.items():
            with self.subTest(site=cote):
                x, y = NOEUDS[entree]
                self.assertEqual(image.pixelColor(x + 20, y - DEMI_LARGEUR_ROUTE + 4), QColor("gray"))
                self.assertEqual(image.pixelColor(x + 20, y - DEMI_LARGEUR_ROUTE - 4), QColor("lightgray"))
        self.assertEqual(image.pixelColor(CX - DEMI_LARGEUR_ROUTE + 4, 200), QColor("gray"))
        self.assertEqual(image.pixelColor(CX - DEMI_LARGEUR_ROUTE - 4, 200), QColor("lightgray"))

    def test_routes_rejoignent_sept_bords_ouverts(self):
        image = self.dessiner_carte()
        for x, y in ((CX + 34, 0), (850 + 34, 0), (0, CY + 34),
                     (LARGEUR_SCENE - 1, CY + 34), (0, 950 + 34),
                     (LARGEUR_SCENE - 1, 950 + 34), (LARGEUR_SCENE - 1, 240 + 34)):
            with self.subTest(x=x, y=y):
                self.assertEqual(image.pixelColor(x, y), QColor("gray"))
        # Les carrefours du bas ne deviennent pas de nouvelles sorties Sud.
        self.assertEqual(image.pixelColor(CX + 34, HAUTEUR_SCENE - 1), QColor("#a8cf8a"))
