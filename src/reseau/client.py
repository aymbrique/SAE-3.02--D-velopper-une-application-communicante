"""Client TCP en thread : file ordonnee, accuse de reception et reconnexion."""

from collections import deque
import socket
from threading import Event, Lock, Thread
from time import monotonic
from uuid import uuid4

from src.reseau.protocole import Decodeur, encoder


class ClientEtats:
    def __init__(self, hote="127.0.0.1", port=5000):
        self.hote = hote
        self.port = port
        self.session = str(uuid4())
        self.numeros = {"01": 0, "02": 0}
        self.en_attente_envoi = deque()  # File : premier message ajoute, premier envoye.
        self.derniers_etats = {}
        self.verrou = Lock()  # Protege les donnees partagees avec la fenetre.
        self.arret_demande = Event()
        self.thread_reseau = None
        self.connexion = None
        self.statut = "Liaison interrompue"

    def publier(self, identifiant, etat):
        with self.verrou:
            self.numeros[identifiant] += 1
            message = {"type": "etat", "session": self.session, "id": identifiant,
                       "etat": etat, "numero": self.numeros[identifiant]}
            self.en_attente_envoi.append(message)
            self.derniers_etats[identifiant] = message

    def instantane(self):
        with self.verrou:
            return self.statut, len(self.en_attente_envoi)

    def _modifier_statut(self, valeur):
        with self.verrou:
            self.statut = valeur

    def demarrer(self):
        # Le thread execute le reseau en parallele pour ne pas figer les boutons.
        self.thread_reseau = Thread(target=self._executer, name="client-tcp", daemon=True)
        self.thread_reseau.start()

    def fermer(self):
        self.arret_demande.set()
        if self.connexion:
            try:
                self.connexion.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        if self.thread_reseau:
            self.thread_reseau.join(timeout=4)

    def _echanger(self, canal, message, decodeur):
        canal.sendall(encoder(message))
        echeance = monotonic() + 5
        while not self.arret_demande.is_set() and monotonic() < echeance:
            try:
                donnees = canal.recv(4096)
            except socket.timeout:
                continue
            if not donnees:
                raise ConnectionError("Connexion fermee")
            for reponse in decodeur.alimenter(donnees):
                if message["type"] == "ping" and reponse.get("type") == "pong":
                    return
                if (reponse.get("type") == "ack" and reponse.get("session") == message.get("session")
                        and reponse.get("id") == message.get("id") and reponse.get("numero") == message.get("numero")):
                    return
                raise ConnectionError("Reponse inattendue du centre")
        raise TimeoutError("Centre sans reponse")

    def _executer(self):
        while not self.arret_demande.is_set():
            try:
                with socket.create_connection((self.hote, self.port), timeout=1) as canal:
                    self.connexion = canal
                    canal.settimeout(0.5)
                    decodeur = Decodeur()
                    prochain_ping = 0
                    with self.verrou:
                        # Renvoie l'etat courant apres redemarrage du centre, sans creer de doublon SQL.
                        for message in self.derniers_etats.values():
                            if message not in self.en_attente_envoi:
                                self.en_attente_envoi.append(message)
                    while not self.arret_demande.is_set():
                        with self.verrou:
                            message = None
                            if self.en_attente_envoi:
                                message = self.en_attente_envoi[0]
                        if message:
                            self._echanger(canal, message, decodeur)
                            with self.verrou:
                                self.en_attente_envoi.popleft()
                            self._modifier_statut("Connecte au centre")
                        elif monotonic() >= prochain_ping:
                            self._echanger(canal, {"type": "ping"}, decodeur)
                            self._modifier_statut("Connecte au centre")
                            prochain_ping = monotonic() + 1
                        else:
                            self.arret_demande.wait(0.05)
            except (OSError, ValueError):
                self._modifier_statut("Liaison interrompue - reconnexion")
                self.arret_demande.wait(1)
            finally:
                self.connexion = None
