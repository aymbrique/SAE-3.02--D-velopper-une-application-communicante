"""Point d'entrée de l'interface graphique de la SAÉ 3.02."""

import sys

from PyQt6.QtWidgets import QApplication

from src.interface.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("SAE302 - Facture Sucrée")
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
