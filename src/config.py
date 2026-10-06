"""Configuration locale, distincte du code versionne."""

from configparser import ConfigParser, Error
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]


def read_config(path=None):
    parser = ConfigParser(interpolation=None)
    candidate = Path(path) if path else ROOT / "config.ini"
    if path and not candidate.is_file():
        raise ValueError(f"Configuration introuvable : {candidate}")
    try:
        parser.read(candidate, encoding="utf-8")
    except Error as error:
        raise ValueError(f"Fichier INI invalide : {candidate}") from error
    return parser


def network_config(parser):
    port = parser.getint("reseau", "port", fallback=5000)
    if not 1 <= port <= 65535:
        raise ValueError("Le port TCP doit etre compris entre 1 et 65535")
    return {"host": parser.get("reseau", "serveur", fallback="127.0.0.1"), "port": port}


def database_config(parser):
    password = os.environ.get("SAE_DB_PASSWORD", parser.get("mariadb", "password", fallback=""))
    if not password:
        raise ValueError("Renseigner le mot de passe MariaDB dans config.ini ou SAE_DB_PASSWORD")
    return {
        "host": parser.get("mariadb", "host", fallback="127.0.0.1"),
        "port": parser.getint("mariadb", "port", fallback=3306),
        "user": parser.get("mariadb", "user", fallback="sae302"),
        "password": password,
        "database": parser.get("mariadb", "database", fallback="sae302"),
        "charset": "utf8mb4", "connect_timeout": 3, "read_timeout": 3, "write_timeout": 3,
    }
