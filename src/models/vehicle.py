"""Etat metier et instantane de dessin, sans dependance a Qt."""

# dataclass cree le constructeur de ces simples fiches de donnees.
from dataclasses import dataclass
from src.models.route import Route


@dataclass
class Vehicle:
    identifier: str
    kind: str
    route: Route
    crossings: tuple
    color: str
    speed: float
    distance: float = 0.0
    crossing_index: int = 0
    busy: bool = False
    started_at: float = 0.0
    requested_at: float | None = None
    waiting: bool = False
    hospital: float | None = None
    dwell_remaining: float = 0.0
    visited: bool = False
    total_estimate: float = 0.0

    @property
    def crossing(self):
        if self.crossing_index < len(self.crossings):
            return self.crossings[self.crossing_index]
        return None

    @property
    def position(self):
        return self.route.sample(self.distance)


@dataclass(frozen=True)
class VehicleState:
    identifier: str
    kind: str
    color: str
    route: Route
    x: float
    y: float
    heading: float
    waiting: bool
    busy: bool
    progress: float
    stage: str


@dataclass(frozen=True)
class Frame:
    vehicles: tuple[VehicleState, ...]
    north_south: str
    east_west: str
    phase_name: str
    phase_remaining: float
    completed: int

    @property
    def cars(self):
        cars = []
        for vehicle in self.vehicles:
            if vehicle.kind == "car":
                cars.append(vehicle)
        return tuple(cars)

    @property
    def rescues(self):
        rescues = []
        for vehicle in self.vehicles:
            if vehicle.kind != "car":
                rescues.append(vehicle)
        return tuple(rescues)
