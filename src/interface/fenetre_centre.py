"""Vue du centre : seules les donnees recues et enregistrees sont affichees."""

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QHeaderView, QLabel, QMainWindow, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)


class FenetreCentre(QMainWindow):
    def __init__(self, serveur):
        super().__init__()
        self.serveur = serveur
        self.setWindowTitle("SAE302 - Centre de coordination")
        self.resize(1020, 720)
        page = QWidget()
        disposition = QVBoxLayout(page)
        self.setCentralWidget(page)
        titre = QLabel("Centre de coordination")
        disposition.addWidget(titre)
        self.etiquette_connexion = QLabel()
        self.etiquette_connexion.setWordWrap(True)
        disposition.addWidget(self.etiquette_connexion)
        self.etats = self._creer_tableau(("Secours", "Dernier etat", "Mise a jour", "Recu le (UTC)", "Liaison"))
        self.etats.setRowCount(2)
        self.etats.setMaximumHeight(145)
        disposition.addWidget(self.etats)
        disposition.addWidget(QLabel("Historique MariaDB - 100 dernieres mises a jour"))
        self.historique = self._creer_tableau(("Recu le (UTC)", "Secours", "Etat", "Numero", "Session"))
        disposition.addWidget(self.historique, 1)
        self.dernier_historique = None
        self.minuteur = QTimer(self)
        self.minuteur.timeout.connect(self.actualiser)
        self.minuteur.start(300)
        self.actualiser()

    @staticmethod
    def _creer_tableau(entetes):
        table = QTableWidget(0, len(entetes))
        table.setHorizontalHeaderLabels(entetes)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        table.verticalHeader().setVisible(False)
        return table

    @staticmethod
    def _remplir_ligne(table, ligne, valeurs):
        for colonne, valeur in enumerate(valeurs):
            affichage = valeur.strftime("%Y-%m-%d %H:%M:%S") if hasattr(valeur, "strftime") else str(valeur)
            element = QTableWidgetItem(affichage)
            element.setToolTip(str(valeur))
            table.setItem(ligne, colonne, element)

    def actualiser(self):
        instantane = self.serveur.instantane()
        self.etiquette_connexion.setText(f"Ecoute sur {self.serveur.hote}:{self.serveur.port} - {instantane['status']}")
        lignes = {ligne["identifiant"]: ligne for ligne in instantane["vehicles"]}
        for index, identifiant in enumerate(("01", "02")):
            ligne = lignes.get(identifiant)
            liaison_active = instantane["connected"] and identifiant in instantane["seen"]
            self._remplir_ligne(self.etats, index, (identifiant,
                ligne["etat"] if ligne else "Inconnu", ligne["numero"] if ligne else "-",
                ligne["recu_le"] if ligne else "-", "Active" if liaison_active else "Liaison interrompue"))
        historique = instantane["history"]
        plus_recent = historique[0]["id"] if historique else None
        if plus_recent != self.dernier_historique:
            self.dernier_historique = plus_recent
            self.historique.setRowCount(len(historique))
            for index, ligne in enumerate(historique):
                self._remplir_ligne(self.historique, index, (ligne["recu_le"], ligne["identifiant"], ligne["etat"],
                                                ligne["numero"], ligne["session_id"]))

    def closeEvent(self, evenement):
        self.minuteur.stop()
        self.serveur.fermer()
        super().closeEvent(evenement)
