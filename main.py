"""Point d'entrée de l'interface graphique de la SAÉ 3.02."""

import sys
import argparse

from PyQt6.QtWidgets import QApplication

from src.interface.fenetre_simulation import FenetreSimulation
from src.configuration import lire_configuration, configuration_reseau
from src.reseau.client import ClientEtats


def main():
    analyseur = argparse.ArgumentParser(description="Simulation de trafic - connexion TCP locale")
    analyseur.add_argument("--config", dest="configuration", help="Fichier INI local")
    analyseur.add_argument("--host", dest="hote", help="Adresse IP du centre")
    analyseur.add_argument("--port", type=int, help="Port TCP du centre")
    analyseur.add_argument("--local", action="store_true", help="Simulation sans connexion TCP")
    arguments = analyseur.parse_args()
    try:
        configuration = configuration_reseau(lire_configuration(arguments.configuration))
    except ValueError as error:
        analyseur.error(str(error))
    hote = arguments.hote or configuration["host"]
    port = arguments.port if arguments.port is not None else configuration["port"]
    if not 1 <= port <= 65535:
        analyseur.error("Port TCP invalide")
    application = QApplication(sys.argv)
    application.setApplicationName("SAE302 - Circulation")
    application.setStyle("Fusion")
    client = None
    if not arguments.local:
        client = ClientEtats(hote, port)
        client.publier("01", "disponible")
        client.publier("02", "disponible")
        client.demarrer()
    fenetre = FenetreSimulation(client)
    fenetre.show()

    sys.exit(application.exec())


if __name__ == "__main__":
    main()
