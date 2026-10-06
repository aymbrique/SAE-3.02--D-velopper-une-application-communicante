"""Centre TCP et MariaDB - VM 2. Lancer apres init_db.py."""

import argparse
import sys

import pymysql

from src.config import database_config, network_config, read_config
from src.reseau.server import CoordinationServer
from src.stockage.mariadb import MariaDBStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config")
    parser.add_argument("--bind", default="0.0.0.0", help="Adresse locale d'ecoute TCP")
    parser.add_argument("--port", type=int)
    parser.add_argument("--headless", action="store_true", help="Serveur sans fenetre")
    args = parser.parse_args()
    server = None
    try:
        config = read_config(args.config)
        store = MariaDBStore(database_config(config))
        port = args.port if args.port is not None else network_config(config)["port"]
        if not 1 <= port <= 65535:
            raise ValueError("Port TCP invalide")
        server = CoordinationServer(store, args.bind, port)
        server.start()
        print(f"Centre pret sur {args.bind}:{server.port} ; stockage MariaDB actif.", flush=True)
        if args.headless:
            try:
                while not server.stop_event.wait(0.5):
                    pass
            except KeyboardInterrupt:
                return 0
        else:
            from PyQt6.QtWidgets import QApplication
            from src.interface.coordination_window import CoordinationWindow
            app = QApplication(sys.argv)
            app.setStyle("Fusion")
            window = CoordinationWindow(server)
            window.show()
            return app.exec()
    except (ValueError, OSError, pymysql.MySQLError) as error:
        print(f"Centre indisponible : {error}\nVerifier config.ini, MariaDB et lancer init_db.py.", file=sys.stderr)
        return 1
    finally:
        if server:
            server.close()


if __name__ == "__main__":
    sys.exit(main())
