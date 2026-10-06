"""Client TCP en thread : file ordonnee, accuse de reception et reconnexion."""

from collections import deque
import socket
from threading import Event, Lock, Thread
from time import monotonic
from uuid import uuid4

from src.reseau.protocol import Decoder, encode


class StateClient:
    def __init__(self, host="127.0.0.1", port=5000):
        self.host, self.port = host, port
        self.session = str(uuid4())
        self.numbers = {"01": 0, "02": 0}
        self.pending = deque()
        self.latest = {}
        self.lock = Lock()
        self.stop_event = Event()
        self.thread = None
        self.socket = None
        self.status = "Liaison interrompue"

    def publish(self, identifier, state):
        with self.lock:
            self.numbers[identifier] += 1
            message = {"type": "etat", "session": self.session, "id": identifier,
                       "etat": state, "numero": self.numbers[identifier]}
            self.pending.append(message)
            self.latest[identifier] = message

    def snapshot(self):
        with self.lock:
            return self.status, len(self.pending)

    def _status(self, value):
        with self.lock:
            self.status = value

    def start(self):
        self.thread = Thread(target=self._run, name="client-tcp", daemon=True)
        self.thread.start()

    def close(self):
        self.stop_event.set()
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        if self.thread:
            self.thread.join(timeout=4)

    def _exchange(self, sock, message, decoder):
        sock.sendall(encode(message))
        deadline = monotonic() + 5
        while not self.stop_event.is_set() and monotonic() < deadline:
            try:
                data = sock.recv(4096)
            except socket.timeout:
                continue
            if not data:
                raise ConnectionError("Connexion fermee")
            for reply in decoder.feed(data):
                if message["type"] == "ping" and reply.get("type") == "pong":
                    return
                if (reply.get("type") == "ack" and reply.get("session") == message.get("session")
                        and reply.get("id") == message.get("id") and reply.get("numero") == message.get("numero")):
                    return
                raise ConnectionError("Reponse inattendue du centre")
        raise TimeoutError("Centre sans reponse")

    def _run(self):
        while not self.stop_event.is_set():
            try:
                with socket.create_connection((self.host, self.port), timeout=1) as sock:
                    self.socket = sock
                    sock.settimeout(0.5)
                    decoder = Decoder()
                    next_ping = 0
                    with self.lock:
                        # Renvoie l'etat courant apres redemarrage du centre, sans creer de doublon SQL.
                        for message in self.latest.values():
                            if message not in self.pending:
                                self.pending.append(message)
                    while not self.stop_event.is_set():
                        with self.lock:
                            message = self.pending[0] if self.pending else None
                        if message:
                            self._exchange(sock, message, decoder)
                            with self.lock:
                                self.pending.popleft()
                            self._status("Connecte au centre")
                        elif monotonic() >= next_ping:
                            self._exchange(sock, {"type": "ping"}, decoder)
                            self._status("Connecte au centre")
                            next_ping = monotonic() + 1
                        else:
                            self.stop_event.wait(0.05)
            except (OSError, ValueError):
                self._status("Liaison interrompue - reconnexion")
                self.stop_event.wait(1)
            finally:
                self.socket = None
