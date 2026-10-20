"""Afficher uniquement la nouvelle maquette, sans simulation ni connexion reseau."""

import sys
from PyQt6.QtWidgets import QApplication
from src.interface.maquette_window import MaquetteWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MaquetteWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
