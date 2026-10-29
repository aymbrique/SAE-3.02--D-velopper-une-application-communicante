"""Creer les tables dans la base MariaDB deja creee par l'administrateur."""

import argparse
import sys

import pymysql

from src.configuration import configuration_base, lire_configuration
from src.stockage.mariadb import StockageMariaDB


def main():
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--config", dest="configuration")
    arguments = analyseur.parse_args()
    try:
        stockage = StockageMariaDB(configuration_base(lire_configuration(arguments.configuration)))
        stockage.initialiser()
    except (ValueError, pymysql.MySQLError, OSError) as error:
        print(f"Initialisation impossible : {error}", file=sys.stderr)
        return 1
    print("Tables MariaDB pretes : vehicules et historique_etats.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
