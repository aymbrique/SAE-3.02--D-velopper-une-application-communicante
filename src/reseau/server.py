"""Serveur de coordination. Un seul simulateur actif, deux vehicules distincts."""

import select
import socket
from threading import Event, Lock, Thread
from time import monotonic

from src.reseau.protocol import Decoder, encode, validate


class CoordinationServer:
    def __init__(self, store, host="0.0.0.0", port=5000):
        self.store, self.host, self.port = store, host, port
        self.stop_event = Event()
        self.lock = Lock()
        self.thread = None
        self.listener = None
        self.connected = False
        self.seen = set()
        self.status = "En attente de la simulation"
        self.data = {"vehicles": [], "history": []}

    def snapshot(self):
        with self.lock:
            return {**self.data, "connected": self.connected, "status": self.status,
                    "seen": set(self.seen)}

    def _status(self, text, connected=False):
        with self.lock:
            self.status, self.connected = text, connected

    def start(self):
        self.data = self.store.snapshot()
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.listener.bind((self.host, self.port))
            self.listener.listen(4)
            self.port = self.listener.getsockname()[1]
        except OSError:
            self.listener.close()
            raise
        self.thread = Thread(target=self._run, name="serveur-tcp", daemon=True)
        self.thread.start()

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=8)

    def _run(self):
        peer = None
        session = None
        decoder = Decoder()
        last_seen = monotonic()
        try:
            while not self.stop_event.is_set():
                readable, _, _ = select.select([self.listener] + ([peer] if peer else []), [], [], 0.2)
                if self.listener in readable:
                    candidate, address = self.listener.accept()
                    candidate.settimeout(0.5)
                    if peer:
                        candidate.close()
                    else:
                        peer, decoder, session = candidate, Decoder(), None
                        with self.lock:
                            self.seen = set()
                        last_seen = monotonic()
                        self._status(f"Connexion de {address[0]} - attente des etats")
                if peer and peer in readable:
                    try:
                        chunk = peer.recv(4096)
                        if not chunk:
                            raise ConnectionError("Client deconnecte")
                        for message in decoder.feed(chunk):
                            validate(message)
                            if message["type"] == "ping":
                                peer.sendall(encode({"type": "pong"}))
                            else:
                                if session and session != message["session"]:
                                    raise ValueError("Changement de session sur une connexion")
                                session = message["session"]
                                self.store.save(message)
                                updated = self.store.snapshot()
                                with self.lock:
                                    self.data = updated
                                    self.seen.add(message["id"])
                                peer.sendall(encode({"type": "ack", "session": session,
                                                     "id": message["id"], "numero": message["numero"]}))
                                self._status("Liaison active", True)
                        last_seen = monotonic()
                    except Exception as error:
                        # Aucun ACK si la transaction echoue : le client conservera son message.
                        self._status(f"Liaison interrompue : {type(error).__name__}")
                        peer.close()
                        peer = None
                if peer and monotonic() - last_seen > 6:
                    self._status("Liaison interrompue : delai de reception depasse")
                    peer.close()
                    peer = None
        finally:
            if peer:
                peer.close()
            self.listener.close()
            self._status("Serveur arrete - liaison interrompue")
