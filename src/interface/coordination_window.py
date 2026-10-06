"""Vue du centre : seules les donnees recues et enregistrees sont affichees."""

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QHeaderView, QLabel, QMainWindow, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)


class CoordinationWindow(QMainWindow):
    def __init__(self, server):
        super().__init__()
        self.server = server
        self.setWindowTitle("SAE302 - Centre de coordination")
        self.resize(1020, 720)
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        self.setCentralWidget(page)
        title = QLabel("Centre de coordination")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)
        self.connection_label = QLabel()
        self.connection_label.setWordWrap(True)
        layout.addWidget(self.connection_label)
        self.states = self._table(("Secours", "Dernier etat", "Mise a jour", "Recu le (UTC)", "Liaison"))
        self.states.setRowCount(2)
        self.states.setMaximumHeight(145)
        layout.addWidget(self.states)
        layout.addWidget(QLabel("Historique MariaDB - 100 dernieres mises a jour"))
        self.history = self._table(("Recu le (UTC)", "Secours", "Etat", "Numero", "Session"))
        layout.addWidget(self.history, 1)
        self.last_history = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(300)
        self.refresh()

    @staticmethod
    def _table(headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        table.verticalHeader().setVisible(False)
        return table

    @staticmethod
    def _put(table, row, values):
        for column, value in enumerate(values):
            display = value.strftime("%Y-%m-%d %H:%M:%S") if hasattr(value, "strftime") else str(value)
            item = QTableWidgetItem(display)
            item.setToolTip(str(value))
            table.setItem(row, column, item)

    def refresh(self):
        snapshot = self.server.snapshot()
        self.connection_label.setText(f"Ecoute sur {self.server.host}:{self.server.port} - {snapshot['status']}")
        rows = {row["identifiant"]: row for row in snapshot["vehicles"]}
        for index, identifier in enumerate(("01", "02")):
            row = rows.get(identifier)
            live = snapshot["connected"] and identifier in snapshot["seen"]
            self._put(self.states, index, (identifier,
                row["etat"] if row else "Inconnu", row["numero"] if row else "-",
                row["recu_le"] if row else "-", "Active" if live else "Liaison interrompue"))
        history = snapshot["history"]
        newest = history[0]["id"] if history else None
        if newest != self.last_history:
            self.last_history = newest
            self.history.setRowCount(len(history))
            for index, row in enumerate(history):
                self._put(self.history, index, (row["recu_le"], row["identifiant"], row["etat"],
                                                row["numero"], row["session_id"]))

    def closeEvent(self, event):
        self.timer.stop()
        self.server.close()
        super().closeEvent(event)
