"""Tests facultatifs sur une base MariaDB réservée aux essais."""

import os
import unittest
from uuid import uuid4

from src.stockage.mariadb import StockageMariaDB


@unittest.skipUnless(os.environ.get("SAE_TEST_DB_NAME"), "Base de test non configurée")
class TestsMariaDB(unittest.TestCase):
    """Vérifie l'état courant et l'historique réellement écrits en base."""

    def setUp(self):
        """Prépare et vide uniquement une base dont le nom finit par _test."""
        nom = os.environ["SAE_TEST_DB_NAME"]
        if not nom.endswith("_test"):
            raise ValueError("Utiliser une base dédiée dont le nom finit par _test")
        self.stockage = StockageMariaDB({
            "host": os.environ.get("SAE_TEST_DB_HOST", "127.0.0.1"),
            "port": int(os.environ.get("SAE_TEST_DB_PORT", "3306")),
            "user": os.environ.get("SAE_TEST_DB_USER", "sae302_test"),
            "password": os.environ["SAE_TEST_DB_PASSWORD"],
            "database": nom, "charset": "utf8mb4",
            "connect_timeout": 3, "read_timeout": 3, "write_timeout": 3,
        })
        self.stockage.initialiser()
        with self.stockage.ouvrir_connexion() as liaison:
            with liaison.cursor() as curseur:
                curseur.execute("DELETE FROM historique_etats")
                curseur.execute("DELETE FROM vehicules")
            liaison.commit()
        self.message = {"id": "01", "etat": "occupe", "numero": 1, "session": str(uuid4())}

    def test_persistance_etats(self):
        """Deux états successifs donnent un état courant et deux lignes d'historique."""
        self.stockage.enregistrer(self.message)
        retour = dict(self.message, etat="disponible", numero=2)
        self.stockage.enregistrer(retour)
        donnees = self.stockage.instantane()
        self.assertEqual(len(donnees["vehicules"]), 1)
        self.assertEqual(donnees["vehicules"][0]["etat"], "disponible")
        etats = [ligne["etat"] for ligne in donnees["historique"]]
        self.assertEqual(etats, ["disponible", "occupe"])

    def test_doublon(self):
        """Le renvoi du même message n'ajoute pas une ligne à l'historique."""
        self.assertTrue(self.stockage.enregistrer(self.message))
        self.assertFalse(self.stockage.enregistrer(self.message))
        self.assertEqual(len(self.stockage.instantane()["historique"]), 1)
