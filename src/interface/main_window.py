"""Commandes de la simulation ; le moteur et le reseau restent independants."""

from math import ceil

from PyQt6.QtCore import QElapsedTimer, QTimer, Qt
from PyQt6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QProgressBar, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from src.interface.map_view import MapView
from src.simulation.engine import Simulation
from src.models.layout import car_route


STYLE = """
QMainWindow, QWidget#page { background: #f2f5f2; color: #24404a; }
QWidget { font-family: 'Arial'; font-size: 13px; color: #24404a; }
QFrame#header { background: #223e46; border-radius: 14px; }
QLabel#eyebrow { color: #93bca9; font-size: 11px; font-weight: bold; }
QLabel#title { color: #ffffff; font-size: 27px; font-weight: bold; }
QLabel#subtitle { color: #c9d9d3; font-size: 12px; }
QLabel#badge { color: #bbe8d2; background: #365750; padding: 10px 14px; border-radius: 8px; font-size: 11px; font-weight: bold; }
QFrame#card { background: #ffffff; border: 1px solid #dce6df; border-radius: 12px; }
QLabel#section { font-size: 14px; font-weight: bold; }
QLabel#muted { color: #7a8e82; font-size: 11px; }
QLabel#metric { font-size: 22px; font-weight: bold; color: #2f6f56; }
QLabel#phase { font-size: 12px; font-weight: bold; color: #44665a; }
QPushButton { background: #ffffff; border: 1px solid #d7e3da; padding: 8px 12px; border-radius: 7px; font-weight: bold; }
QPushButton:hover { background: #eef5ef; }
QPushButton:pressed { background: #dcece0; }
QPushButton#primary { background: #367b5c; border-color: #367b5c; color: #ffffff; padding: 11px; }
QPushButton#primary:hover { background: #2c684d; }
QPushButton:checked { background: #e6f3e9; border-color: #85b79b; color: #2d704f; }
QPushButton:disabled { background: #edf0ed; color: #829087; border-color: #e0e5e1; }
QComboBox { background: white; border: 1px solid #d7e3da; border-radius: 6px; padding: 7px; }
QComboBox::drop-down { border: none; width: 20px; }
QCheckBox { spacing: 6px; font-size: 11px; }
QProgressBar { border: none; border-radius: 3px; background: #edf2ed; max-height: 6px; }
QProgressBar::chunk { background: #6ba68a; border-radius: 3px; }
"""


def label(text, name=None):
    result = QLabel(text)
    if name:
        result.setObjectName(name)
    return result


def card():
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(17, 13, 17, 13)
    layout.setSpacing(9)
    return frame, layout


class MainWindow(QMainWindow):
    def __init__(self, client=None):
        super().__init__()
        self.setWindowTitle("SAE302 · Facture Sucrée · Simulation 2D")
        self.resize(1320, 860)
        self.setMinimumSize(960, 680)
        self.setStyleSheet(STYLE)
        self.scenario = Simulation()
        self.client = client
        self.elapsed = 0.0
        self.playing = False
        self.speed = 1.0
        self._build_ui()
        self.clock = QElapsedTimer()
        self.clock.start()
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self.refresh()

    def _build_ui(self):
        page = QWidget()
        page.setObjectName("page")
        self.setCentralWidget(page)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(22, 18, 22, 15)
        outer.setSpacing(16)
        header = QFrame()
        header.setObjectName("header")
        line = QHBoxLayout(header)
        line.setContentsMargins(25, 18, 25, 18)
        heading = QVBoxLayout()
        heading.setSpacing(5)
        heading.addWidget(label("SAÉ 3.02  /  AYMERI & SELIM", "eyebrow"))
        heading.addWidget(label("Circulation & secours", "title"))
        subtitle = label("Colmar · Un carrefour, deux véhicules de secours, une vue d’ensemble.", "subtitle")
        subtitle.setWordWrap(True)
        heading.addWidget(subtitle)
        line.addLayout(heading)
        line.addStretch()
        line.addWidget(label("SIMULATION · TCP", "badge"))
        outer.addWidget(header)

        body = QHBoxLayout()
        body.setSpacing(16)
        map_card, map_layout = card()
        toolbar = QHBoxLayout()
        toolbar.addWidget(label("SECTEUR DE COLMAR", "section"))
        toolbar.addStretch()
        self.clock_label = label("00:00", "metric")
        toolbar.addWidget(self.clock_label)
        map_layout.addLayout(toolbar)
        map_layout.addWidget(label("Carte simplifiée · circulation à droite", "muted"))
        self.view = MapView()
        map_layout.addWidget(self.view, 1)
        route_row = QHBoxLayout()
        self.route_checkbox = QCheckBox("Afficher un trajet")
        self.route_checkbox.toggled.connect(self._update_route)
        route_row.addWidget(self.route_checkbox)
        self.route_combo = QComboBox()
        self.route_combo.setAccessibleName("Trajet à observer sur la carte")
        for rescue in self.scenario.rescues:
            self.route_combo.addItem(rescue.route.name, rescue.route)
        for origin in ("N", "S", "E", "W"):
            for turn in ("straight", "left", "right"):
                route, _ = car_route(origin, turn)
                self.route_combo.addItem(route.name, route)
        self.route_combo.setEnabled(False)
        self.route_combo.currentIndexChanged.connect(self._update_route)
        route_row.addWidget(self.route_combo, 1)
        fit_button = QPushButton("Vue complète")
        fit_button.clicked.connect(lambda: self.view.fit_scene(reset_zoom=True))
        route_row.addWidget(fit_button)
        map_layout.addLayout(route_row)
        legend = QHBoxLayout()
        for text, color in (("●  Voitures", "#65a8b8"), ("●  Pompiers", "#cf7568"),
                            ("●  Ambulance", "#91a29b")):
            item = label(text, "muted")
            item.setStyleSheet(f"color: {color};")
            legend.addWidget(item)
        legend.addStretch()
        legend.addWidget(label("Zoom : molette · déplacement : glisser", "muted"))
        map_layout.addLayout(legend)
        body.addWidget(map_card, 1)

        sidebar_widget = QWidget()
        sidebar = QVBoxLayout(sidebar_widget)
        sidebar.setContentsMargins(0, 0, 0, 0)
        sidebar.setSpacing(12)
        controls, controls_layout = card()
        controls_layout.addWidget(label("Lecture de la scène", "section"))
        self.play_button = QPushButton("▶  Demarrer")
        self.play_button.setObjectName("primary")
        self.play_button.clicked.connect(self.toggle_play)
        controls_layout.addWidget(self.play_button)
        self.reset_button = QPushButton("↺  Recommencer")
        self.reset_button.clicked.connect(self.reset)
        controls_layout.addWidget(self.reset_button)
        speed_row = QHBoxLayout()
        speed_row.addWidget(label("Vitesse", "muted"))
        self.speed_group = QButtonGroup(self)
        for index, (text, value) in enumerate((("× 0,5", 0.5), ("× 1", 1.0), ("× 2", 2.0))):
            button = QPushButton(text)
            button.setCheckable(True)
            button.setChecked(value == 1)
            button.setAccessibleName(f"Vitesse de lecture {text}")
            button.clicked.connect(lambda checked, speed=value: self.set_speed(speed))
            self.speed_group.addButton(button, index)
            speed_row.addWidget(button)
        controls_layout.addLayout(speed_row)
        traffic_row = QHBoxLayout()
        traffic_row.addWidget(label("Voitures / minute"))
        self.rate_input = QSpinBox()
        self.rate_input.setRange(0, 60)
        self.rate_input.setValue(self.scenario.rate)
        self.rate_input.valueChanged.connect(self._change_rate)
        traffic_row.addWidget(self.rate_input)
        controls_layout.addLayout(traffic_row)
        sidebar.addWidget(controls)

        lights, lights_layout = card()
        lights_layout.addWidget(label("Feux du carrefour", "section"))
        self.signal_labels = {}
        for name in ("Nord–Sud", "Est–Ouest"):
            row = QHBoxLayout()
            row.addWidget(label(name))
            row.addStretch()
            value = label("")
            row.addWidget(value)
            self.signal_labels[name] = value
            lights_layout.addLayout(row)
        self.phase_label = label("", "phase")
        self.phase_label.setWordWrap(True)
        lights_layout.addWidget(self.phase_label)
        sidebar.addWidget(lights)

        metrics, metrics_layout = card()
        metrics_layout.addWidget(label("Le trafic en direct", "section"))
        self.car_count = self._metric(metrics_layout, "Voitures en scène")
        self.waiting_count = self._metric(metrics_layout, "Voitures à l’arrêt")
        self.completed_count = self._metric(metrics_layout, "Trajets terminés")
        sidebar.addWidget(metrics)

        rescue_card, rescue_layout = card()
        rescue_layout.addWidget(label("Interventions", "section"))
        self.rescue_widgets = {}
        self.mission_buttons = {}
        self.estimate_labels = {}
        for identifier, name in (("01", "Pompiers"), ("02", "Ambulance")):
            row = QHBoxLayout()
            row.addWidget(label(f"{name} · {identifier}", "phase"))
            row.addStretch()
            status = label("Disponible")
            row.addWidget(status)
            rescue_layout.addLayout(row)
            stage = label("À la caserne", "muted")
            rescue_layout.addWidget(stage)
            progress = QProgressBar()
            progress.setRange(0, 1000)
            progress.setTextVisible(False)
            progress.setAccessibleName(f"Progression du parcours du secours {identifier}")
            rescue_layout.addWidget(progress)
            estimates = label("", "muted")
            estimates.setWordWrap(True)
            rescue_layout.addWidget(estimates)
            self.estimate_labels[identifier] = estimates
            button = QPushButton(f"Envoyer le secours {identifier}")
            button.clicked.connect(lambda checked, ident=identifier: self.start_mission(ident))
            controls_layout.addWidget(button)
            self.mission_buttons[identifier] = button
            if identifier == "01":
                rescue_layout.addSpacing(8)
            self.rescue_widgets[identifier] = (status, stage, progress)
        sidebar.addWidget(rescue_card)
        network_card, network_layout = card()
        network_layout.addWidget(label("Centre distant", "section"))
        self.network_label = label("", "muted")
        self.network_label.setWordWrap(True)
        network_layout.addWidget(self.network_label)
        self.debt_label = label("", "muted")
        self.debt_label.setWordWrap(True)
        network_layout.addWidget(self.debt_label)
        sidebar.addWidget(network_card)
        sidebar.addStretch()
        # Conserver des commandes lisibles sur un écran moins haut.
        sidebar_widget.setMinimumHeight(672)
        self.sidebar_scroll = QScrollArea()
        self.sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.sidebar_scroll.setWidgetResizable(True)
        self.sidebar_scroll.setFixedWidth(330)
        self.sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sidebar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.sidebar_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.sidebar_scroll.setWidget(sidebar_widget)
        body.addWidget(self.sidebar_scroll)
        outer.addLayout(body, 1)
        self.footer = label("", "muted")
        outer.addWidget(self.footer)

    @staticmethod
    def _metric(layout, text):
        row = QHBoxLayout()
        row.addWidget(label(text, "muted"))
        row.addStretch()
        value = label("0", "metric")
        row.addWidget(value)
        layout.addLayout(row)
        return value

    def toggle_play(self):
        self.playing = not self.playing
        self.clock.restart()
        self.refresh()

    def set_speed(self, value):
        self.speed = value
        self.clock.restart()

    def reset(self):
        self.scenario = Simulation(rate=self.rate_input.value())
        if self.client:
            for identifier in ("01", "02"):
                self.client.publish(identifier, "disponible")
        self.elapsed = 0
        self.playing = False
        self.clock.restart()
        self.refresh()

    def _tick(self):
        dt = min(self.clock.restart() / 1000, 0.1)
        if self.playing:
            self.scenario.advance(dt * self.speed)
            self.elapsed = self.scenario.time
        self._publish_events()
        self.refresh()

    def _change_rate(self, value):
        self.scenario.rate = value

    def start_mission(self, identifier):
        self.scenario.start_mission(identifier)
        self._publish_events()
        self.refresh()

    def _publish_events(self):
        for identifier, state in self.scenario.drain_events():
            if self.client:
                self.client.publish(identifier, state)

    def _update_route(self, *args):
        enabled = self.route_checkbox.isChecked()
        self.route_combo.setEnabled(enabled)
        self.view.set_route(self.route_combo.currentData() if enabled else None)

    def refresh(self):
        frame = self.scenario.frame()
        self.view.sync(frame, self.elapsed)
        total_seconds = int(self.elapsed)
        self.clock_label.setText(f"{total_seconds // 60:02d}:{total_seconds % 60:02d}")
        self.car_count.setText(str(len(frame.cars)))
        self.waiting_count.setText(str(sum(car.waiting for car in frame.cars)))
        self.completed_count.setText(str(frame.completed))
        names = {"red": "Rouge", "amber": "Orange", "green": "Vert"}
        text_colors = {"red": "#bb574f", "amber": "#a87323", "green": "#32835b"}
        for axis, signal in (("Nord–Sud", frame.north_south), ("Est–Ouest", frame.east_west)):
            item = self.signal_labels[axis]
            item.setText("●  " + names[signal])
            item.setStyleSheet(f"color: {text_colors[signal]}; font-weight: bold;")
        remaining = f"{ceil(frame.phase_remaining)} s" if frame.phase_remaining > 0 else "passage en cours"
        self.phase_label.setText(f"{frame.phase_name} · {remaining}")
        for rescue in frame.rescues:
            status, stage, progress = self.rescue_widgets[rescue.identifier]
            status.setText("Occupé" if rescue.busy else "Disponible")
            status.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {'#be7654' if rescue.busy else '#438b63'};")
            stage.setText(rescue.stage)
            progress.setValue(round(rescue.progress * 1000))
            self.mission_buttons[rescue.identifier].setEnabled(not rescue.busy)
            self.mission_buttons[rescue.identifier].setText(
                f"Secours {rescue.identifier} en mission" if rescue.busy else f"Envoyer le secours {rescue.identifier}")
            model = next(v for v in self.scenario.rescues if v.identifier == rescue.identifier)
            distance, eta = self.scenario.approach(model)
            approach = f"Carrefour : {distance:.0f} m / {eta:.1f} s" if distance is not None else "Carrefour franchi"
            remaining_time = ((model.route.length - model.distance) / model.speed
                              + (model.dwell_remaining if model.visited else 8))
            self.estimate_labels[rescue.identifier].setText(
                f"{approach}\nMission : {self.elapsed - model.started_at:.0f} s ecoulees\n"
                f"Estimation hors attentes :\n{remaining_time:.0f} s restantes / {model.total_estimate:.0f} s au depart"
                if model.busy else f"Duree prevue hors attentes : {model.total_estimate:.0f} s")
        self.play_button.setText("Ⅱ  Mettre en pause" if self.playing else
                                 ("▶  Reprendre" if self.elapsed > 0 else "▶  Demarrer"))
        status = "EN COURS" if self.playing else ("EN PAUSE" if self.elapsed > 0 else "PRÊT À DÉMARRER")
        self.footer.setText(f"{status}  ·  25 voitures maximum · Priorite secours · Temps simule")
        if self.client:
            network_status, pending = self.client.snapshot()
            self.network_label.setText(f"{network_status}\n{self.client.host}:{self.client.port}\n"
                                       f"Mises a jour en attente : {pending}")
        else:
            self.network_label.setText("Mode local - centre non connecte")
        debt = self.scenario.lights.debt
        self.debt_label.setText(f"Compensation en attente :\nNord-Sud {debt['NS']:.1f} s / Est-Ouest {debt['EW']:.1f} s")

    def closeEvent(self, event):
        self.timer.stop()
        if self.client:
            self.client.close()
        super().closeEvent(event)
