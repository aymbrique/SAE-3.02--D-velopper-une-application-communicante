"""Verifier les commandes de la fenetre et leur effet sur le vrai client TCP."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from src.interface.main_window import MainWindow
from src.interface.coordination_window import CoordinationWindow
from src.reseau.client import StateClient
from src.reseau.server import CoordinationServer
from test_network import MemoryStore, wait_for


class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_controls_pause_speed_and_routes(self):
        window = MainWindow()
        self.addCleanup(window.close)
        window.show()
        self.app.processEvents()
        window.rate_input.setValue(30)
        self.assertEqual(window.scenario.rate, 30)
        window.speed_input.setCurrentIndex(2)
        self.assertEqual(window.speed, 2)
        window.play_button.click()
        QTest.qWait(200)
        self.assertGreater(window.elapsed, 0)
        window.play_button.click()
        paused = window.elapsed
        QTest.qWait(80)
        self.assertEqual(window.elapsed, paused)
        window.route_checkbox.setChecked(True)
        for index in range(window.route_combo.count()):
            window.route_combo.setCurrentIndex(index)
            self.assertIsNotNone(window.view.route_item)
        window.route_checkbox.setChecked(False)
        self.assertIsNone(window.view.route_item)
        window.reset_button.click()
        self.assertEqual(window.elapsed, 0)
        self.assertFalse(window.playing)
        self.assertEqual(window.scenario.rate, 30)

    def test_horizontal_and_vertical_accumulation_counters(self):
        window = MainWindow()
        self.addCleanup(window.close)
        lights = window.scenario.lights
        from src.simulation.lights import Request
        # Un vert NS prolonge a 22 s doit stocker 14 s sur la ligne horizontale.
        for _ in range(440):
            lights.advance(.05, [Request("02", "NS", 0, 0)], busy=True)
        window.refresh()
        self.assertEqual(window.accumulation_labels["EW"].text(), "14.0 s stockees")
        self.assertEqual(window.accumulation_labels["NS"].text(), "0.0 s stockees")
        # La pause ne consomme rien ; recommencer remet bien les deux a zero.
        QTest.qWait(80)
        window.refresh()
        self.assertEqual(window.accumulation_labels["EW"].text(), "14.0 s stockees")
        window.reset_button.click()
        self.assertEqual(window.accumulation_labels["EW"].text(), "0.0 s stockees")
        self.assertEqual(window.accumulation_labels["NS"].text(), "0.0 s stockees")

    def test_mission_buttons_return_and_reset_reach_the_center(self):
        store = MemoryStore()
        server = CoordinationServer(store, "127.0.0.1", 0)
        server.start()
        self.addCleanup(server.close)
        client = StateClient("127.0.0.1", server.port)
        client.start()
        self.addCleanup(client.close)
        window = MainWindow(client)
        center = CoordinationWindow(server)
        self.addCleanup(center.close)
        self.addCleanup(window.close)
        for identifier in ("01", "02"):
            window.rescue_combo.setCurrentIndex(window.rescue_combo.findData(identifier))
            destination = "E" if identifier == "01" else "W"
            window.destination_combo.setCurrentIndex(window.destination_combo.findData(destination))
            window.send_button.click()
            self.assertFalse(window.send_button.isEnabled())
            self.assertEqual(window.scenario.get_rescue(identifier).destination, destination)
        wait_for(lambda: client.snapshot()[1] == 0)
        center.refresh()
        self.assertEqual(center.states.item(0, 1).text(), "occupe")
        self.assertEqual(center.states.item(1, 1).text(), "occupe")
        window.scenario.advance(300)
        window.elapsed = window.scenario.time
        window._publish_events()
        window.refresh()
        wait_for(lambda: client.snapshot()[1] == 0)
        center.refresh()
        for index, identifier in enumerate(("01", "02")):
            self.assertEqual(center.states.item(index, 1).text(), "disponible")
            window.rescue_combo.setCurrentIndex(window.rescue_combo.findData(identifier))
            self.assertTrue(window.send_button.isEnabled())
        window.rescue_combo.setCurrentIndex(0)
        window.send_button.click()
        window.reset_button.click()
        wait_for(lambda: client.snapshot()[1] == 0)
        center.refresh()
        self.assertEqual(center.states.item(0, 1).text(), "disponible")
        self.assertEqual(center.states.item(1, 1).text(), "disponible")
        self.assertEqual(len(store.history), 7)
