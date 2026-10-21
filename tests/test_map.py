"""Controle du rendu : aires hors chaussee et routes jusqu'aux bords."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QApplication

from src.interface.carte import MapView
from src.modeles.plan import CX, CY, NODES, ROAD_HALF, SCENE_HEIGHT, SCENE_WIDTH, SITE_ENTRANCES


class MapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def render_map(self):
        view = MapView()
        self.addCleanup(view.close)
        image = QImage(SCENE_WIDTH, SCENE_HEIGHT, QImage.Format.Format_RGB32)
        image.fill(QColor("#a8cf8a"))
        painter = QPainter(image)
        view.scene().render(painter, QRectF(0, 0, SCENE_WIDTH, SCENE_HEIGHT), view.sceneRect())
        painter.end()
        return image

    def test_grounds_stop_at_the_edge_of_asphalt(self):
        image = self.render_map()
        for side, entrance in SITE_ENTRANCES.items():
            with self.subTest(site=side):
                x, y = NODES[entrance]
                self.assertEqual(image.pixelColor(x + 20, y - ROAD_HALF + 4), QColor("gray"))
                self.assertEqual(image.pixelColor(x + 20, y - ROAD_HALF - 4), QColor("lightgray"))
        self.assertEqual(image.pixelColor(CX - ROAD_HALF + 4, 200), QColor("gray"))
        self.assertEqual(image.pixelColor(CX - ROAD_HALF - 4, 200), QColor("lightgray"))

    def test_existing_roads_reach_all_seven_open_edges(self):
        image = self.render_map()
        for x, y in ((CX + 34, 0), (850 + 34, 0), (0, CY + 34),
                     (SCENE_WIDTH - 1, CY + 34), (0, 950 + 34),
                     (SCENE_WIDTH - 1, 950 + 34), (SCENE_WIDTH - 1, 240 + 34)):
            with self.subTest(x=x, y=y):
                self.assertEqual(image.pixelColor(x, y), QColor("gray"))
        # Les carrefours du bas ne deviennent pas de nouvelles sorties Sud.
        self.assertEqual(image.pixelColor(CX + 34, SCENE_HEIGHT - 1), QColor("#a8cf8a"))
