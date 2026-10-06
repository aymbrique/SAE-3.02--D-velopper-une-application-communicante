"""Integration optionnelle : base dediee dont le nom doit finir par _test."""

import os
import unittest
from uuid import uuid4

from src.reseau.client import StateClient
from src.reseau.server import CoordinationServer
from src.stockage.mariadb import MariaDBStore
from test_network import wait_for


@unittest.skipUnless(os.environ.get("SAE_TEST_DB_NAME"), "Configurer une base MariaDB de test dediee")
class MariaDBTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        name = os.environ["SAE_TEST_DB_NAME"]
        if not name.endswith("_test"):
            raise ValueError("Les tests effacent leurs tables : utiliser une base terminee par _test")
        cls.config = {
            "host": os.environ.get("SAE_TEST_DB_HOST", "127.0.0.1"),
            "port": int(os.environ.get("SAE_TEST_DB_PORT", "3306")),
            "user": os.environ.get("SAE_TEST_DB_USER", "sae302_test"),
            "password": os.environ["SAE_TEST_DB_PASSWORD"],
            "database": name, "charset": "utf8mb4",
            "connect_timeout": 3, "read_timeout": 3, "write_timeout": 3,
        }
        cls.store = MariaDBStore(cls.config)
        cls.store.initialize()

    def setUp(self):
        with self.store.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM historique_etats")
                cursor.execute("DELETE FROM vehicules")
            connection.commit()

    def test_persistence_stale_updates_and_session_restart(self):
        session = str(uuid4())
        message = {"type": "etat", "id": "01", "etat": "occupe", "numero": 2, "session": session}
        self.assertTrue(self.store.save(message))
        self.assertFalse(self.store.save(message))
        self.assertFalse(self.store.save({**message, "numero": 1, "etat": "disponible"}))
        self.store.save({**message, "id": "02", "etat": "disponible"})
        reopened = MariaDBStore(self.config)
        snapshot = reopened.snapshot()
        self.assertEqual(len(snapshot["history"]), 2)
        self.assertEqual([(r["identifiant"], r["etat"]) for r in snapshot["vehicles"]],
                         [("01", "occupe"), ("02", "disponible")])
        self.assertTrue(reopened.save({**message, "session": str(uuid4()), "numero": 1, "etat": "disponible"}))
        self.assertEqual(len(reopened.snapshot()["history"]), 3)

    def test_real_tcp_and_database_restart(self):
        server = CoordinationServer(self.store, "127.0.0.1", 0)
        server.start()
        self.addCleanup(server.close)
        client = StateClient("127.0.0.1", server.port)
        client.publish("01", "occupe")
        client.publish("02", "disponible")
        client.start()
        self.addCleanup(client.close)
        wait_for(lambda: client.snapshot()[1] == 0 and server.snapshot()["seen"] == {"01", "02"})
        self.assertEqual(len(self.store.snapshot()["history"]), 2)
        server.close()
        client.publish("01", "disponible")
        client.publish("02", "occupe")
        replacement = CoordinationServer(MariaDBStore(self.config), "127.0.0.1", server.port)
        replacement.start()
        self.addCleanup(replacement.close)
        wait_for(lambda: client.snapshot()[1] == 0 and replacement.snapshot()["seen"] == {"01", "02"})
        snapshot = self.store.snapshot()
        self.assertEqual(len(snapshot["history"]), 4)
        self.assertEqual([r["etat"] for r in snapshot["vehicles"]], ["disponible", "occupe"])
        client.close()
        wait_for(lambda: not replacement.snapshot()["connected"])
        self.assertEqual([r["etat"] for r in self.store.snapshot()["vehicles"]], ["disponible", "occupe"])
