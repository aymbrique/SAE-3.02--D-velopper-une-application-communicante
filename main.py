"""Point d'entrée de l'interface graphique de la SAÉ 3.02."""

import sys
import argparse

from PyQt6.QtWidgets import QApplication

from src.interface.main_window import MainWindow
from src.config import read_config, network_config
from src.reseau.client import StateClient


def main():
    parser = argparse.ArgumentParser(description="Simulation de trafic - VM 1")
    parser.add_argument("--config", help="Fichier INI local")
    parser.add_argument("--host", help="Adresse IP du centre")
    parser.add_argument("--port", type=int, help="Port TCP du centre")
    parser.add_argument("--local", action="store_true", help="Simulation sans connexion TCP")
    args = parser.parse_args()
    try:
        config = network_config(read_config(args.config))
    except ValueError as error:
        parser.error(str(error))
    host = args.host or config["host"]
    port = args.port if args.port is not None else config["port"]
    if not 1 <= port <= 65535:
        parser.error("Port TCP invalide")
    app = QApplication(sys.argv)
    app.setApplicationName("SAE302 - Facture Sucrée")
    app.setStyle("Fusion")
    client = None
    if not args.local:
        client = StateClient(host, port)
        client.publish("01", "disponible")
        client.publish("02", "disponible")
        client.start()
    window = MainWindow(client)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
