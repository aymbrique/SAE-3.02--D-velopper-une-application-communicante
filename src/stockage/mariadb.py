"""Requetes parametrees et transaction : etat courant + historique atomiques."""

from datetime import datetime, timezone

import pymysql
from pymysql.cursors import DictCursor

from src.configuration import RACINE


class StockageMariaDB:
    def __init__(self, configuration):
        self.configuration = dict(configuration)

    def ouvrir_connexion(self):
        return pymysql.connect(**self.configuration, cursorclass=DictCursor)

    def initialiser(self):
        with self.ouvrir_connexion() as liaison:
            with liaison.cursor() as curseur:
                for chemin in sorted((RACINE / "sql").glob("*.sql")):
                    curseur.execute(chemin.read_text(encoding="utf-8"))
            liaison.commit()

    def enregistrer(self, message):
        # Une transaction regroupe l'historique et l'etat courant.
        # commit valide ; rollback annule une mise a jour refusee.
        valeurs = (message["id"], message["etat"], message["session"], message["numero"])
        with self.ouvrir_connexion() as liaison:
            with liaison.cursor() as curseur:
                curseur.execute("SELECT numero, session_id FROM vehicules WHERE identifiant=%s FOR UPDATE",
                               (message["id"],))
                precedent = curseur.fetchone()
                curseur.execute("SELECT MAX(numero) AS dernier FROM historique_etats "
                               "WHERE session_id=%s AND identifiant=%s", (message["session"], message["id"]))
                maximum = curseur.fetchone()["dernier"]
                if maximum is not None and message["numero"] <= maximum:
                    liaison.rollback()
                    return False
                if precedent and precedent["session_id"] == message["session"] and message["numero"] <= precedent["numero"]:
                    liaison.rollback()
                    return False
                recu_le = datetime.now(timezone.utc).replace(tzinfo=None)
                # Les %s sont des parametres SQL ; le pilote insere les valeurs.
                curseur.execute("INSERT INTO historique_etats "
                               "(identifiant, etat, session_id, numero, recu_le) VALUES (%s,%s,%s,%s,%s)",
                               (*valeurs, recu_le))
                curseur.execute("INSERT INTO vehicules (identifiant, etat, session_id, numero, recu_le) "
                               "VALUES (%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE "
                               "etat=VALUES(etat), session_id=VALUES(session_id), "
                               "numero=VALUES(numero), recu_le=VALUES(recu_le)", (*valeurs, recu_le))
            liaison.commit()
        return True

    def instantane(self):
        with self.ouvrir_connexion() as liaison:
            with liaison.cursor() as curseur:
                curseur.execute("SELECT * FROM vehicules ORDER BY identifiant")
                vehicules = curseur.fetchall()
                curseur.execute("SELECT * FROM historique_etats ORDER BY id DESC LIMIT 100")
                historique = curseur.fetchall()
        return {"vehicles": vehicules, "history": historique}
