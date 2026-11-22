"""Messages JSON et transmission des états sur une connexion TCP locale."""
import time
import unittest

from src.reseau.client import ClientEtats
from src.reseau.protocole import Decodeur, encoder
from src.reseau.serveur import ServeurCentre


class StockageMemoire:
    """Remplace MariaDB pour tester le réseau seul."""

    def __init__(self):
        """Prépare une liste vide pour les messages reçus."""
        self.messages = []

    def enregistrer(self, message):
        """Garde le message transmis par le serveur."""
        self.messages.append(message)

    def instantane(self):
        """Fournit au serveur l'historique des messages du test."""
        return {"vehicules": [], "historique": list(self.messages)}


class TestsReseau(unittest.TestCase):
    """Vérifie le décodage et la confirmation d'un état par le centre."""

    def test_decodage_messages(self):
        """Le décodeur attend la fin du premier message et retrouve le suivant."""
        decodeur = Decodeur()
        ping = {"type": "verification_liaison"}
        donnees = encoder(ping)
        self.assertEqual(decodeur.alimenter(donnees[:3]), [])
        self.assertEqual(decodeur.alimenter(donnees[3:] + donnees), [ping, ping])

    def test_envoi_etat(self):
        """Le client retire le message de sa file après confirmation par le centre."""
        serveur = ServeurCentre(StockageMemoire(), "127.0.0.1", 0)
        serveur.demarrer()
        self.addCleanup(serveur.fermer)
        client = ClientEtats("127.0.0.1", serveur.port)
        client.publier("01", "occupe")
        client.demarrer()
        self.addCleanup(client.fermer)
        limite = time.monotonic() + 5
        while client.instantane()[1] and time.monotonic() < limite:
            time.sleep(0.02)
        self.assertEqual(client.instantane()[1], 0)
        self.assertEqual(serveur.instantane()["historique"][0]["etat"], "occupe")
