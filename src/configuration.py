"""Configuration locale, distincte du code versionne."""

from configparser import ConfigParser, Error
from pathlib import Path
import os

RACINE = Path(__file__).resolve().parents[1]


def lire_configuration(chemin=None):
    analyseur = ConfigParser(interpolation=None)
    candidat = Path(chemin) if chemin else RACINE / "config.ini"
    if chemin and not candidat.is_file():
        raise ValueError(f"Configuration introuvable : {candidat}")
    try:
        analyseur.read(candidat, encoding="utf-8")
    except Error as error:
        raise ValueError(f"Fichier INI invalide : {candidat}") from error
    return analyseur


def configuration_reseau(analyseur):
    port = analyseur.getint("reseau", "port", fallback=5000)
    if not 1 <= port <= 65535:
        raise ValueError("Le port TCP doit etre compris entre 1 et 65535")
    return {"host": analyseur.get("reseau", "serveur", fallback="127.0.0.1"), "port": port}


def configuration_base(analyseur):
    mot_de_passe = os.environ.get("SAE_DB_PASSWORD", analyseur.get("mariadb", "password", fallback=""))
    if not mot_de_passe:
        raise ValueError("Renseigner le mot de passe MariaDB dans config.ini ou SAE_DB_PASSWORD")
    return {
        "host": analyseur.get("mariadb", "host", fallback="127.0.0.1"),
        "port": analyseur.getint("mariadb", "port", fallback=3306),
        "user": analyseur.get("mariadb", "user", fallback="sae302"),
        "password": mot_de_passe,
        "database": analyseur.get("mariadb", "database", fallback="sae302"),
        "charset": "utf8mb4", "connect_timeout": 3, "read_timeout": 3, "write_timeout": 3,
    }
