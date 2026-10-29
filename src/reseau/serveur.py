"""Serveur de coordination. Un seul simulateur actif, deux vehicules distincts."""

import select
import socket
from threading import Event, Lock, Thread
from time import monotonic

from src.reseau.protocole import Decodeur, encoder, valider


class ServeurCentre:
    def __init__(self, stockage, hote="0.0.0.0", port=5000):
        self.stockage = stockage
        self.hote = hote
        self.port = port
        self.arret_demande = Event()
        self.verrou = Lock()
        self.thread_reseau = None
        self.ecouteur = None
        self.connecte = False
        self.recus = set()
        self.statut = "En attente de la simulation"
        self.donnees = {"vehicles": [], "history": []}

    def instantane(self):
        with self.verrou:
            return {"vehicles": self.donnees["vehicles"], "history": self.donnees["history"],
                    "connected": self.connecte, "status": self.statut,
                    "seen": set(self.recus)}

    def _modifier_statut(self, texte, connecte=False):
        with self.verrou:
            self.statut = texte
            self.connecte = connecte

    def demarrer(self):
        self.donnees = self.stockage.instantane()
        self.ecouteur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.ecouteur.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.ecouteur.bind((self.hote, self.port))
            self.ecouteur.listen(4)
            self.port = self.ecouteur.getsockname()[1]
        except OSError:
            self.ecouteur.close()
            raise
        self.thread_reseau = Thread(target=self._executer, name="serveur-tcp", daemon=True)
        self.thread_reseau.start()

    def fermer(self):
        self.arret_demande.set()
        if self.thread_reseau:
            self.thread_reseau.join(timeout=8)

    def _executer(self):
        client_actif = None
        session = None
        decodeur = Decodeur()
        derniere_reception = monotonic()
        try:
            while not self.arret_demande.is_set():
                # Surveiller les nouvelles connexions et le client actif.
                connexions = [self.ecouteur]
                if client_actif is not None:
                    connexions.append(client_actif)
                lisibles, _, _ = select.select(connexions, [], [], 0.2)
                if self.ecouteur in lisibles:
                    candidat, adresse = self.ecouteur.accept()
                    candidat.settimeout(0.5)
                    if client_actif:
                        candidat.close()
                    else:
                        client_actif = candidat
                        decodeur = Decodeur()
                        session = None
                        with self.verrou:
                            self.recus = set()
                        derniere_reception = monotonic()
                        self._modifier_statut(f"Connexion de {adresse[0]} - attente des etats")
                if client_actif and client_actif in lisibles:
                    try:
                        morceau = client_actif.recv(4096)
                        if not morceau:
                            raise ConnectionError("Client deconnecte")
                        for message in decodeur.alimenter(morceau):
                            valider(message)
                            if message["type"] == "ping":
                                client_actif.sendall(encoder({"type": "pong"}))
                            else:
                                if session and session != message["session"]:
                                    raise ValueError("Changement de session sur une connexion")
                                session = message["session"]
                                # Confirmer seulement apres enregistrement dans MariaDB.
                                self.stockage.enregistrer(message)
                                mis_a_jour = self.stockage.instantane()
                                with self.verrou:
                                    self.donnees = mis_a_jour
                                    self.recus.add(message["id"])
                                client_actif.sendall(encoder({"type": "ack", "session": session,
                                                     "id": message["id"], "numero": message["numero"]}))
                                self._modifier_statut("Liaison active", True)
                        derniere_reception = monotonic()
                    except Exception as error:
                        # Aucun ACK si la transaction echoue : le client conservera son message.
                        self._modifier_statut(f"Liaison interrompue : {type(error).__name__}")
                        client_actif.close()
                        client_actif = None
                if client_actif and monotonic() - derniere_reception > 6:
                    self._modifier_statut("Liaison interrompue : delai de reception depasse")
                    client_actif.close()
                    client_actif = None
        finally:
            if client_actif:
                client_actif.close()
            self.ecouteur.close()
            self._modifier_statut("Serveur arrete - liaison interrompue")
