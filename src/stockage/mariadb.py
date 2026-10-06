"""Requetes parametrees et transaction : etat courant + historique atomiques."""

from datetime import datetime, timezone

import pymysql
from pymysql.cursors import DictCursor

from src.config import ROOT


class MariaDBStore:
    def __init__(self, config):
        self.config = dict(config)

    def connect(self):
        return pymysql.connect(**self.config, cursorclass=DictCursor)

    def initialize(self):
        with self.connect() as connection:
            with connection.cursor() as cursor:
                for path in sorted((ROOT / "sql").glob("*.sql")):
                    cursor.execute(path.read_text(encoding="utf-8"))
            connection.commit()

    def save(self, message):
        values = (message["id"], message["etat"], message["session"], message["numero"])
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT numero, session_id FROM vehicules WHERE identifiant=%s FOR UPDATE",
                               (message["id"],))
                previous = cursor.fetchone()
                cursor.execute("SELECT MAX(numero) AS dernier FROM historique_etats "
                               "WHERE session_id=%s AND identifiant=%s", (message["session"], message["id"]))
                maximum = cursor.fetchone()["dernier"]
                if maximum is not None and message["numero"] <= maximum:
                    connection.rollback()
                    return False
                if previous and previous["session_id"] == message["session"] and message["numero"] <= previous["numero"]:
                    connection.rollback()
                    return False
                received = datetime.now(timezone.utc).replace(tzinfo=None)
                cursor.execute("INSERT INTO historique_etats "
                               "(identifiant, etat, session_id, numero, recu_le) VALUES (%s,%s,%s,%s,%s)",
                               (*values, received))
                cursor.execute("INSERT INTO vehicules (identifiant, etat, session_id, numero, recu_le) "
                               "VALUES (%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE "
                               "etat=VALUES(etat), session_id=VALUES(session_id), "
                               "numero=VALUES(numero), recu_le=VALUES(recu_le)", (*values, received))
            connection.commit()
        return True

    def snapshot(self):
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM vehicules ORDER BY identifiant")
                vehicles = cursor.fetchall()
                cursor.execute("SELECT * FROM historique_etats ORDER BY id DESC LIMIT 100")
                history = cursor.fetchall()
        return {"vehicles": vehicles, "history": history}
