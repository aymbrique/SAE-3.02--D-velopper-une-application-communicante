"""Protocole et vrais echanges TCP sur loopback, stockage en memoire de test."""

import socket
from threading import Lock
import time
import unittest
from uuid import uuid4

from src.reseau.client import StateClient
from src.reseau.protocol import Decoder, encode, validate
from src.reseau.server import CoordinationServer


class MemoryStore:
    def __init__(self):
        self.rows = {}
        self.history = []
        self.lock = Lock()

    def save(self, message):
        with self.lock:
            if any(r["session_id"] == message["session"] and r["identifiant"] == message["id"]
                   and r["numero"] >= message["numero"] for r in self.history):
                return False
            row = {"id": len(self.history) + 1, "identifiant": message["id"], "etat": message["etat"],
                   "session_id": message["session"], "numero": message["numero"], "recu_le": "2026-01-01"}
            self.rows[message["id"]] = row
            self.history.append(row)
            return True

    def snapshot(self):
        with self.lock:
            return {"vehicles": list(self.rows.values()), "history": list(reversed(self.history[-100:]))}


def wait_for(predicate, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.02)
    raise AssertionError("Delai depasse")


class ProtocolTests(unittest.TestCase):
    def test_fragmented_and_coalesced_messages(self):
        decoder = Decoder()
        data = encode({"type": "ping"}) + encode({"type": "ping"})
        self.assertEqual(decoder.feed(data[:3]), [])
        self.assertEqual(decoder.feed(data[3:]), [{"type": "ping"}, {"type": "ping"}])

    def test_invalid_messages(self):
        for data in (b'[]\n', b'not json\n', b'x' * 4097):
            with self.assertRaises(ValueError):
                Decoder().feed(data)
        message = {"type": "etat", "id": "01", "etat": "occupe", "numero": 1, "session": str(uuid4())}
        self.assertEqual(validate(message), message)
        for changes in ({"numero": True}, {"numero": -1}, {"id": "99"}, {"etat": "oops"}, {"session": "oops"}):
            with self.assertRaises(ValueError):
                validate({**message, **changes})


class NetworkTests(unittest.TestCase):
    def test_states_disconnect_reconnect_and_no_duplicates(self):
        store = MemoryStore()
        server = CoordinationServer(store, "127.0.0.1", 0)
        server.start()
        self.addCleanup(server.close)
        client = StateClient("127.0.0.1", server.port)
        self.addCleanup(client.close)
        client.publish("01", "occupe")
        client.publish("02", "disponible")
        client.start()
        wait_for(lambda: client.snapshot()[1] == 0 and len(store.history) == 2)
        self.assertEqual(store.rows["01"]["etat"], "occupe")
        server.close()
        self.assertFalse(server.snapshot()["connected"])
        self.assertEqual(store.rows["01"]["etat"], "occupe")
        client.publish("02", "occupe")
        client.publish("01", "disponible")
        replacement = CoordinationServer(store, "127.0.0.1", server.port)
        replacement.start()
        self.addCleanup(replacement.close)
        wait_for(lambda: client.snapshot()[1] == 0 and len(store.history) == 4)
        self.assertEqual(store.rows["01"]["etat"], "disponible")
        self.assertEqual(store.rows["02"]["etat"], "occupe")
        # Redemarrer le serveur sans nouvel evenement doit tout de meme retablir la liaison.
        replacement.close()
        third = CoordinationServer(store, "127.0.0.1", server.port)
        third.start()
        self.addCleanup(third.close)
        wait_for(lambda: third.snapshot()["connected"] and third.snapshot()["seen"] == {"01", "02"})
        self.assertEqual(len(store.history), 4)

    def test_malformed_client_does_not_kill_server(self):
        store = MemoryStore()
        server = CoordinationServer(store, "127.0.0.1", 0)
        server.start()
        self.addCleanup(server.close)
        with socket.create_connection(("127.0.0.1", server.port)) as sock:
            sock.sendall(b'[]\n')
            self.assertEqual(sock.recv(10), b'')
        self.assertTrue(server.thread.is_alive())
        client = StateClient("127.0.0.1", server.port)
        client.publish("01", "disponible")
        self.addCleanup(client.close)
        client.start()
        wait_for(lambda: len(store.history) == 1)
