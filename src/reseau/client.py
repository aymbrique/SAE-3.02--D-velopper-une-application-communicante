"""Client TCP en thread : file ordonnee, accuse de reception et reconnexion."""

from collections import deque
import socket
from threading import Event, Lock, Thread
from time import monotonic
from uuid import uuid4

from src.reseau.protocole import Decodeur, encoder


class ClientEtats:
    """Client TCP qui garde les états en attente jusqu'à leur confirmation."""

    def __init__(self, hote="127.0.0.1", port=5000):
        """Prépare la session, la file des messages et les outils du thread réseau."""
        self.hote = hote
        self.port = port
        self.session = str(uuid4())
        self.numeros = {"01": 0, "02": 0}
        self.en_attente_envoi = deque()
        self.derniers_etats = {}
        self.verrou = Lock()
        self.arret_demande = Event()
        self.thread_reseau = None
        self.connexion = None
        self.statut = "Liaison interrompue"

    def publier(self, identifiant, etat):
        """Numérote et ajoute un état à envoyer sans bloquer l'interface."""
        with self.verrou:
            self.numeros[identifiant] += 1
            message = {"type": "etat", "session": self.session, "id": identifiant,
                       "etat": etat, "numero": self.numeros[identifiant]}
            self.en_attente_envoi.append(message)
            self.derniers_etats[identifiant] = message

    def instantane(self):
        """Renvoie le statut réseau et le nombre de messages en attente sous verrou."""
        with self.verrou:
            return self.statut, len(self.en_attente_envoi)

    def _modifier_statut(self, valeur):
        """Modifie le statut de connexion sous verrou."""
        with self.verrou:
            self.statut = valeur

    def demarrer(self):
        """Lance les échanges TCP dans un thread séparé."""
        # Le thread execute le reseau en parallele pour ne pas figer les boutons.
        self.thread_reseau = Thread(target=self._executer, name="client-tcp", daemon=True)
        self.thread_reseau.start()

    def fermer(self):
        """Demande l'arrêt, débloque la socket et attend le thread jusqu'à 4 secondes."""
        self.arret_demande.set()
        if self.connexion:
            try:
                self.connexion.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        if self.thread_reseau:
            self.thread_reseau.join(timeout=4)

    def _echanger(self, canal, message, decodeur):
        """Envoie un message et attend la réponse correspondante.

        Args:
            canal: Socket connectée au centre.
            message: État ou ping à envoyer.
            decodeur: Décodeur utilisé pour les réponses de cette connexion.

        Raises:
            ConnectionError: Si la connexion ferme ou si la réponse est inattendue.
            TimeoutError: Si aucune confirmation n'arrive dans le délai de 5 secondes.
        """
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
        """Envoie les états, attend leurs confirmations et retente les connexions coupées."""
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
                                # Retirer un état seulement après sa confirmation par le centre.
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
