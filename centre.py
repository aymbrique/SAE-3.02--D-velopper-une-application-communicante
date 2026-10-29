"""Centre TCP et MariaDB - meme VM que la simulation. Lancer apres init_db.py."""

import argparse
import sys

import pymysql

from src.configuration import configuration_base, configuration_reseau, lire_configuration
from src.reseau.serveur import ServeurCentre
from src.stockage.mariadb import StockageMariaDB


def main():
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--config", dest="configuration")
    analyseur.add_argument("--bind", dest="adresse_ecoute", default="127.0.0.1", help="Adresse locale d'ecoute TCP")
    analyseur.add_argument("--port", type=int)
    analyseur.add_argument("--headless", dest="sans_fenetre", action="store_true", help="Serveur sans fenetre")
    arguments = analyseur.parse_args()
    serveur = None
    try:
        configuration = lire_configuration(arguments.configuration)
        stockage = StockageMariaDB(configuration_base(configuration))
        port = arguments.port if arguments.port is not None else configuration_reseau(configuration)["port"]
        if not 1 <= port <= 65535:
            raise ValueError("Port TCP invalide")
        serveur = ServeurCentre(stockage, arguments.adresse_ecoute, port)
        serveur.demarrer()
        print(f"Centre pret sur {arguments.adresse_ecoute}:{serveur.port} ; stockage MariaDB actif.", flush=True)
        if arguments.sans_fenetre:
            try:
                while not serveur.arret_demande.wait(0.5):
                    pass
            except KeyboardInterrupt:
                return 0
        else:
            from PyQt6.QtWidgets import QApplication
            from src.interface.fenetre_centre import FenetreCentre
            application = QApplication(sys.argv)
            application.setStyle("Fusion")
            fenetre = FenetreCentre(serveur)
            fenetre.show()
            return application.exec()
    except (ValueError, OSError, pymysql.MySQLError) as error:
        print(f"Centre indisponible : {error}\nVerifier config.ini, MariaDB et lancer init_db.py.", file=sys.stderr)
        return 1
    finally:
        if serveur:
            serveur.fermer()


if __name__ == "__main__":
    sys.exit(main())
