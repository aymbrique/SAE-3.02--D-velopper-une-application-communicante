"""Protocole et vrais echanges TCP sur loopback, stockage en memoire de test."""

import socket
from threading import Lock
import time
import unittest
from uuid import uuid4

from src.reseau.client import ClientEtats
from src.reseau.protocole import Decodeur, encoder, valider
from src.reseau.serveur import ServeurCentre


class StockageMemoire:
    def __init__(self):
        self.lignes = {}
        self.historique = []
        self.verrou = Lock()

    def enregistrer(self, message):
        with self.verrou:
            if any(r["session_id"] == message["session"] and r["identifiant"] == message["id"]
                   and r["numero"] >= message["numero"] for r in self.historique):
                return False
            ligne = {"id": len(self.historique) + 1, "identifiant": message["id"], "etat": message["etat"],
                   "session_id": message["session"], "numero": message["numero"], "recu_le": "2026-01-01"}
            self.lignes[message["id"]] = ligne
            self.historique.append(ligne)
            return True

    def instantane(self):
        with self.verrou:
            return {"vehicles": list(self.lignes.values()), "history": list(reversed(self.historique[-100:]))}


def attendre(condition, delai_max=8):
    echeance = time.monotonic() + delai_max
    while time.monotonic() < echeance:
        if condition():
            return
        time.sleep(.02)
    raise AssertionError("Delai depasse")


class TestsProtocole(unittest.TestCase):
    def test_messages_fragmentes_et_regroupes(self):
        decodeur = Decodeur()
        donnees = encoder({"type": "ping"}) + encoder({"type": "ping"})
        self.assertEqual(decodeur.alimenter(donnees[:3]), [])
        self.assertEqual(decodeur.alimenter(donnees[3:]), [{"type": "ping"}, {"type": "ping"}])

    def test_messages_invalides(self):
        for donnees in (b'[]\n', b'not json\n', b'x' * 4097):
            with self.assertRaises(ValueError):
                Decodeur().alimenter(donnees)
        message = {"type": "etat", "id": "01", "etat": "occupe", "numero": 1, "session": str(uuid4())}
        self.assertEqual(valider(message), message)
        for modifications in ({"numero": True}, {"numero": -1}, {"id": "99"}, {"etat": "oops"}, {"session": "oops"}):
            with self.assertRaises(ValueError):
                valider({**message, **modifications})


class TestsReseau(unittest.TestCase):
    def test_etats_coupure_reconnexion_sans_doublons(self):
        stockage = StockageMemoire()
        serveur = ServeurCentre(stockage, "127.0.0.1", 0)
        serveur.demarrer()
        self.addCleanup(serveur.fermer)
        client = ClientEtats("127.0.0.1", serveur.port)
        self.addCleanup(client.fermer)
        client.publier("01", "occupe")
        client.publier("02", "disponible")
        client.demarrer()
        attendre(lambda: client.instantane()[1] == 0 and len(stockage.historique) == 2)
        self.assertEqual(stockage.lignes["01"]["etat"], "occupe")
        serveur.fermer()
        self.assertFalse(serveur.instantane()["connected"])
        self.assertEqual(stockage.lignes["01"]["etat"], "occupe")
        client.publier("02", "occupe")
        client.publier("01", "disponible")
        remplacant = ServeurCentre(stockage, "127.0.0.1", serveur.port)
        remplacant.demarrer()
        self.addCleanup(remplacant.fermer)
        attendre(lambda: client.instantane()[1] == 0 and len(stockage.historique) == 4)
        self.assertEqual(stockage.lignes["01"]["etat"], "disponible")
        self.assertEqual(stockage.lignes["02"]["etat"], "occupe")
        # Redemarrer le serveur sans nouvel evenement doit tout de meme retablir la liaison.
        remplacant.fermer()
        troisieme = ServeurCentre(stockage, "127.0.0.1", serveur.port)
        troisieme.demarrer()
        self.addCleanup(troisieme.fermer)
        attendre(lambda: troisieme.instantane()["connected"] and troisieme.instantane()["seen"] == {"01", "02"})
        self.assertEqual(len(stockage.historique), 4)

    def test_client_invalide_ne_coupe_pas_serveur(self):
        stockage = StockageMemoire()
        serveur = ServeurCentre(stockage, "127.0.0.1", 0)
        serveur.demarrer()
        self.addCleanup(serveur.fermer)
        with socket.create_connection(("127.0.0.1", serveur.port)) as canal:
            canal.sendall(b'[]\n')
            self.assertEqual(canal.recv(10), b'')
        self.assertTrue(serveur.thread_reseau.is_alive())
        client = ClientEtats("127.0.0.1", serveur.port)
        client.publier("01", "disponible")
        self.addCleanup(client.fermer)
        client.demarrer()
        attendre(lambda: len(stockage.historique) == 1)
