"""Fenetre standard Qt : commandes, carte et trois onglets d'informations."""

from math import ceil
from PyQt6.QtCore import QElapsedTimer, QTimer
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel, QMainWindow,
    QProgressBar, QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from src.interface.map_view import MapView
from src.interface.maquette_window import MaquetteWindow
from src.models.layout import DESTINATIONS, car_route, rescue_route
from src.simulation.engine import Simulation


class MainWindow(QMainWindow):
    def __init__(self, client=None):
        super().__init__()
        self.setWindowTitle("SAE302 - Simulation")
        self.resize(1100, 720)
        self.scenario = Simulation()
        self.client = client
        self.elapsed = 0.0
        self.playing = False
        self.speed = 1.0
        self.maquette_window = None
        self._build_ui()

        # Qt appelle _tick regulierement. Le moteur calcule les deplacements.
        self.clock = QElapsedTimer()
        self.clock.start()
        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self.refresh()

    def _build_ui(self):
        page = QWidget()
        self.setCentralWidget(page)
        layout = QVBoxLayout(page)
        self._build_controls(layout)

        body = QHBoxLayout()
        self.view = MapView()
        body.addWidget(self.view, 1)
        tabs = QTabWidget()
        tabs.setMinimumWidth(300)
        tabs.setMaximumWidth(360)
        tabs.addTab(self._build_traffic_tab(), "Trafic")
        tabs.addTab(self._build_rescue_tab(), "Secours")
        tabs.addTab(self._build_network_tab(), "Reseau")
        body.addWidget(tabs)
        layout.addLayout(body, 1)
        self._build_routes(layout)
        layout.addWidget(QLabel("Voiture : bleu | Pompier 01 : rouge | Ambulance 02 : blanc"))
        layout.addWidget(QLabel("Zoom : molette | Deplacement : glisser | Details : survol du vehicule"))
        self.footer = QLabel()
        layout.addWidget(self.footer)

    def _build_controls(self, layout):
        row = QHBoxLayout()
        self.play_button = QPushButton("Demarrer")
        self.play_button.clicked.connect(self.toggle_play)
        row.addWidget(self.play_button)
        self.reset_button = QPushButton("Recommencer")
        self.reset_button.clicked.connect(self.reset)
        row.addWidget(self.reset_button)
        row.addWidget(QLabel("Vitesse"))
        self.speed_input = QComboBox()
        for speed in (0.5, 1, 2):
            self.speed_input.addItem(f"x{speed:g}", speed)
        self.speed_input.setCurrentIndex(1)
        self.speed_input.currentIndexChanged.connect(self._change_speed)
        row.addWidget(self.speed_input)
        row.addWidget(QLabel("Voitures / minute"))
        self.rate_input = QSpinBox()
        self.rate_input.setRange(0, 60)
        self.rate_input.setValue(self.scenario.rate)
        self.rate_input.valueChanged.connect(self._change_rate)
        row.addWidget(self.rate_input)
        row.addStretch()
        self.clock_label = QLabel("00:00")
        row.addWidget(self.clock_label)
        layout.addLayout(row)

        missions = QHBoxLayout()
        missions.addWidget(QLabel("Vehicule"))
        self.rescue_combo = QComboBox()
        self.rescue_combo.addItem("01 - Pompiers", "01")
        self.rescue_combo.addItem("02 - Ambulance", "02")
        missions.addWidget(self.rescue_combo)
        missions.addWidget(QLabel("Intervention"))
        self.destination_combo = QComboBox()
        for side, name in DESTINATIONS.items():
            self.destination_combo.addItem(name, side)
        self.destination_combo.setCurrentIndex(self.destination_combo.findData("S"))
        missions.addWidget(self.destination_combo)
        self.send_button = QPushButton("Envoyer en intervention")
        self.send_button.clicked.connect(self._send_selected)
        missions.addWidget(self.send_button)
        self.rescue_combo.currentIndexChanged.connect(self._update_send_button)
        missions.addStretch()
        layout.addLayout(missions)

    def _build_traffic_tab(self):
        page = QWidget()
        form = QFormLayout(page)
        self.car_count = QLabel()
        self.waiting_count = QLabel()
        self.completed_count = QLabel()
        form.addRow("Voitures presentes", self.car_count)
        form.addRow("Voitures en attente", self.waiting_count)
        form.addRow("Trajets termines", self.completed_count)
        self.signal_labels = {}
        for axis in ("Nord-Sud", "Est-Ouest"):
            self.signal_labels[axis] = QLabel()
            form.addRow(axis, self.signal_labels[axis])
        self.phase_label = QLabel()
        self.phase_label.setWordWrap(True)
        form.addRow(self.phase_label)
        self.debt_label = QLabel()
        self.debt_label.setWordWrap(True)
        form.addRow(self.debt_label)
        return page

    def _build_rescue_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.rescue_widgets = {}
        self.estimate_labels = {}
        for identifier in ("01", "02"):
            layout.addWidget(QLabel("Secours " + identifier))
            status = QLabel()
            stage = QLabel()
            progress = QProgressBar()
            progress.setRange(0, 100)
            estimates = QLabel()
            estimates.setWordWrap(True)
            layout.addWidget(status)
            layout.addWidget(stage)
            layout.addWidget(progress)
            layout.addWidget(estimates)
            self.rescue_widgets[identifier] = (status, stage, progress)
            self.estimate_labels[identifier] = estimates
        layout.addStretch()
        return page

    def _build_network_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.network_label = QLabel()
        self.network_label.setWordWrap(True)
        layout.addWidget(self.network_label)
        layout.addStretch()
        return page

    def _build_routes(self, layout):
        row = QHBoxLayout()
        self.route_checkbox = QCheckBox("Afficher un trajet")
        self.route_checkbox.toggled.connect(self._update_route)
        row.addWidget(self.route_checkbox)
        self.route_combo = QComboBox()
        for rescue in self.scenario.rescues:
            for side in DESTINATIONS:
                route, crossings, hospital = rescue_route(rescue.identifier, rescue.route.points[0][1], side)
                self.route_combo.addItem(route.name, route)
        for origin in ("N", "S", "E", "W"):
            for turn in ("straight", "left", "right"):
                route, stop = car_route(origin, turn)
                self.route_combo.addItem(route.name, route)
        self.route_combo.setEnabled(False)
        self.route_combo.currentIndexChanged.connect(self._update_route)
        row.addWidget(self.route_combo, 1)
        fit_button = QPushButton("Vue complete")
        fit_button.clicked.connect(self._fit_map)
        row.addWidget(fit_button)
        self.maquette_button = QPushButton("Nouvelle maquette")
        self.maquette_button.clicked.connect(self._show_maquette)
        row.addWidget(self.maquette_button)
        layout.addLayout(row)

    def _send_selected(self):
        self.start_mission(self.rescue_combo.currentData(), self.destination_combo.currentData())

    def _update_send_button(self):
        rescue = self.scenario.get_rescue(self.rescue_combo.currentData())
        self.send_button.setEnabled(not rescue.busy)
        self.destination_combo.setEnabled(not rescue.busy)
        if rescue.busy:
            self.destination_combo.setCurrentIndex(self.destination_combo.findData(rescue.destination))
            self.send_button.setText("Ce secours est deja en mission")
        else:
            self.send_button.setText("Envoyer en intervention")

    def _show_maquette(self):
        if self.maquette_window is None:
            self.maquette_window = MaquetteWindow(self)
        self.maquette_window.show()
        self.maquette_window.raise_()

    def _fit_map(self):
        self.view.fit_scene(reset_zoom=True)

    def _change_speed(self):
        self.set_speed(self.speed_input.currentData())

    def set_speed(self, value):
        self.speed = value
        self.clock.restart()

    def _change_rate(self, value):
        self.scenario.rate = value

    def toggle_play(self):
        self.playing = not self.playing
        self.clock.restart()
        self.refresh()

    def reset(self):
        self.scenario = Simulation(rate=self.rate_input.value())
        if self.client:
            self.client.publish("01", "disponible")
            self.client.publish("02", "disponible")
        self.elapsed = 0
        self.playing = False
        self.clock.restart()
        self.refresh()

    def _tick(self):
        # Temps reel depuis le dernier appel, limite en cas de fenetre bloquee.
        dt = min(self.clock.restart() / 1000, 0.1)
        if self.playing:
            self.scenario.advance(dt * self.speed)
            self.elapsed = self.scenario.time
        self._publish_events()
        self.refresh()

    def start_mission(self, identifier, destination="S"):
        started = self.scenario.start_mission(identifier, destination)
        if started:
            # Le trajet affiche correspond a la mission qui vient d'etre envoyee.
            name = self.scenario.get_rescue(identifier).route.name
            self.route_combo.setCurrentIndex(self.route_combo.findText(name))
        self._publish_events()
        self.refresh()

    def _publish_events(self):
        for identifier, state in self.scenario.drain_events():
            if self.client:
                self.client.publish(identifier, state)

    def _update_route(self):
        enabled = self.route_checkbox.isChecked()
        self.route_combo.setEnabled(enabled)
        if enabled:
            self.view.set_route(self.route_combo.currentData())
        else:
            self.view.set_route(None)

    def refresh(self):
        frame = self.scenario.frame()
        self.view.sync(frame, self.elapsed)
        seconds = int(self.elapsed)
        self.clock_label.setText(f"{seconds // 60:02d}:{seconds % 60:02d}")
        self.car_count.setText(str(len(frame.cars)))
        waiting = 0
        for car in frame.cars:
            if car.waiting:
                waiting += 1
        self.waiting_count.setText(str(waiting))
        self.completed_count.setText(str(frame.completed))
        names = {"red": "Rouge", "amber": "Orange", "green": "Vert"}
        self.signal_labels["Nord-Sud"].setText(names[frame.north_south])
        self.signal_labels["Est-Ouest"].setText(names[frame.east_west])
        if frame.phase_remaining > 0:
            remaining = f"{ceil(frame.phase_remaining)} s de cycle restantes"
        else:
            remaining = "Passage en cours"
        self.phase_label.setText(f"{frame.phase_name}\n{remaining}")
        debt = self.scenario.lights.debt
        self.debt_label.setText(f"Compensation en attente :\nNord-Sud : {debt['NS']:.1f} s\nEst-Ouest : {debt['EW']:.1f} s")
        self._update_send_button()
        for rescue in frame.rescues:
            self._refresh_rescue(rescue)
        if self.playing:
            self.play_button.setText("Mettre en pause")
            self.footer.setText("Simulation en cours")
        elif self.elapsed > 0:
            self.play_button.setText("Reprendre")
            self.footer.setText("Simulation en pause")
        else:
            self.play_button.setText("Demarrer")
            self.footer.setText("Pret a demarrer")
        if self.client:
            status, pending = self.client.snapshot()
            self.network_label.setText(f"{status}\n{self.client.host}:{self.client.port}\nMises a jour en attente : {pending}")
        else:
            self.network_label.setText("Mode local : centre non connecte")

    def _refresh_rescue(self, rescue):
        status, stage, progress = self.rescue_widgets[rescue.identifier]
        if rescue.busy:
            status.setText("Occupe")
        else:
            status.setText("Disponible")
        stage.setText(rescue.stage)
        progress.setValue(round(rescue.progress * 100))
        model = self.scenario.get_rescue(rescue.identifier)
        if not model.busy:
            text = f"Duree prevue hors attentes : {model.total_estimate:.0f} s"
        else:
            distance, eta = self.scenario.approach(model)
            text = "Carrefour franchi"
            if distance is not None:
                text = f"Carrefour : {distance:.0f} m / {eta:.1f} s"
            remaining = (model.route.length - model.distance) / model.speed
            if model.visited:
                remaining += model.dwell_remaining
            else:
                remaining += 8
            text += f"\nMission : {self.elapsed - model.started_at:.0f} s ecoulees"
            text += f"\nHors attentes : {remaining:.0f} s restantes"
            text += f"\nPrevision au depart : {model.total_estimate:.0f} s"
        self.estimate_labels[rescue.identifier].setText(text)

    def closeEvent(self, event):
        if self.maquette_window is not None:
            self.maquette_window.close()
        self.timer.stop()
        if self.client:
            self.client.close()
        super().closeEvent(event)
