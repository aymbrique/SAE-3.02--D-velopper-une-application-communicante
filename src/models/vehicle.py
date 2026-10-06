"""Etat metier et instantane de dessin, sans dependance a Qt."""

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
        return self.crossings[self.crossing_index] if self.crossing_index < len(self.crossings) else None

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
        return tuple(v for v in self.vehicles if v.kind == "car")

    @property
    def rescues(self):
        return tuple(v for v in self.vehicles if v.kind != "car")
