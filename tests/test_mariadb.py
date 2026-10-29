"""Integration optionnelle : base dediee dont le nom doit finir par _test."""

import os
import unittest
from uuid import uuid4

from src.reseau.client import ClientEtats
from src.reseau.serveur import ServeurCentre
from src.stockage.mariadb import StockageMariaDB
from test_reseau import attendre


@unittest.skipUnless(os.environ.get("SAE_TEST_DB_NAME"), "Configurer une base MariaDB de test dediee")
class TestsMariaDB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        nom = os.environ["SAE_TEST_DB_NAME"]
        if not nom.endswith("_test"):
            raise ValueError("Les tests effacent leurs tables : utiliser une base terminee par _test")
        cls.configuration = {
            "host": os.environ.get("SAE_TEST_DB_HOST", "127.0.0.1"),
            "port": int(os.environ.get("SAE_TEST_DB_PORT", "3306")),
            "user": os.environ.get("SAE_TEST_DB_USER", "sae302_test"),
            "password": os.environ["SAE_TEST_DB_PASSWORD"],
            "database": nom, "charset": "utf8mb4",
            "connect_timeout": 3, "read_timeout": 3, "write_timeout": 3,
        }
        cls.stockage = StockageMariaDB(cls.configuration)
        cls.stockage.initialiser()

    def setUp(self):
        with self.stockage.ouvrir_connexion() as liaison:
            with liaison.cursor() as curseur:
                curseur.execute("DELETE FROM historique_etats")
                curseur.execute("DELETE FROM vehicules")
            liaison.commit()

    def test_persistance_refus_anciens_etats_et_nouvelle_session(self):
        session = str(uuid4())
        message = {"type": "etat", "id": "01", "etat": "occupe", "numero": 2, "session": session}
        self.assertTrue(self.stockage.enregistrer(message))
        self.assertFalse(self.stockage.enregistrer(message))
        self.assertFalse(self.stockage.enregistrer({**message, "numero": 1, "etat": "disponible"}))
        self.stockage.enregistrer({**message, "id": "02", "etat": "disponible"})
        rouvert = StockageMariaDB(self.configuration)
        instantane = rouvert.instantane()
        self.assertEqual(len(instantane["history"]), 2)
        self.assertEqual([(r["identifiant"], r["etat"]) for r in instantane["vehicles"]],
                         [("01", "occupe"), ("02", "disponible")])
        self.assertTrue(rouvert.enregistrer({**message, "session": str(uuid4()), "numero": 1, "etat": "disponible"}))
        self.assertEqual(len(rouvert.instantane()["history"]), 3)

    def test_tcp_reel_et_reouverture_base(self):
        serveur = ServeurCentre(self.stockage, "127.0.0.1", 0)
        serveur.demarrer()
        self.addCleanup(serveur.fermer)
        client = ClientEtats("127.0.0.1", serveur.port)
        client.publier("01", "occupe")
        client.publier("02", "disponible")
        client.demarrer()
        self.addCleanup(client.fermer)
        attendre(lambda: client.instantane()[1] == 0 and serveur.instantane()["seen"] == {"01", "02"})
        self.assertEqual(len(self.stockage.instantane()["history"]), 2)
        serveur.fermer()
        client.publier("01", "disponible")
        client.publier("02", "occupe")
        remplacant = ServeurCentre(StockageMariaDB(self.configuration), "127.0.0.1", serveur.port)
        remplacant.demarrer()
        self.addCleanup(remplacant.fermer)
        attendre(lambda: client.instantane()[1] == 0 and remplacant.instantane()["seen"] == {"01", "02"})
        instantane = self.stockage.instantane()
        self.assertEqual(len(instantane["history"]), 4)
        self.assertEqual([r["etat"] for r in instantane["vehicles"]], ["disponible", "occupe"])
        client.fermer()
        attendre(lambda: not remplacant.instantane()["connected"])
        self.assertEqual([r["etat"] for r in self.stockage.instantane()["vehicles"]], ["disponible", "occupe"])
