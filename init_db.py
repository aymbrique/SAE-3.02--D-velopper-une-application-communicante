"""Creer les tables dans la base MariaDB deja creee par l'administrateur."""

import argparse
import sys

import pymysql

from src.config import database_config, read_config
from src.stockage.mariadb import MariaDBStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config")
    args = parser.parse_args()
    try:
        store = MariaDBStore(database_config(read_config(args.config)))
        store.initialize()
    except (ValueError, pymysql.MySQLError, OSError) as error:
        print(f"Initialisation impossible : {error}", file=sys.stderr)
        return 1
    print("Tables MariaDB pretes : vehicules et historique_etats.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
