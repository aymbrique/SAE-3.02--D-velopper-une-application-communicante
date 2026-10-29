"""Etat metier et instantane de dessin, sans dependance a Qt."""

# dataclass cree le constructeur de ces simples fiches de donnees.
from dataclasses import dataclass
from math import atan, cos, degrees, radians, sin
from src.modeles.trajet import Trajet


@dataclass
class Vehicule:
    identifiant: str
    type_vehicule: str
    trajet: Trajet
    passages: tuple
    couleur: str
    vitesse: float
    distance: float = 0.0
    indice_passage: int = 0
    occupe: bool = False
    debut_mission: float = 0.0
    date_demande: float | None = None
    en_attente: bool = False
    arret_intervention: float | None = None
    temps_intervention_restant: float = 0.0
    intervention_effectuee: bool = False
    duree_estimee: float = 0.0
    origine: str = ""
    virage: str = ""
    destination: str = "S"
    decalage_lateral: float = 0.0
    cede_aux: tuple[str, ...] = ()
    vitesse_actuelle: float = 0.0
    debut_manoeuvre: float | None = None
    decalage_initial: float = 0.0
    decalage_cible: float = 0.0
    longueur_manoeuvre: float = 72.0

    @property
    def passage(self):
        if self.indice_passage < len(self.passages):
            return self.passages[self.indice_passage]
        return None

    def decalage_lateral_a(self, distance):
        if self.debut_manoeuvre is None:
            return self.decalage_lateral, 0.0
        progression = min(1.0, max(0.0,
                       (distance - self.debut_manoeuvre) / self.longueur_manoeuvre))
        variation = self.decalage_cible - self.decalage_initial
        # Courbe douce : les roues commencent et finissent paralleles a la voie.
        decalage = self.decalage_initial + variation * progression ** 2 * (3 - 2 * progression)
        pente = variation * 6 * progression * (1 - progression) / self.longueur_manoeuvre
        return decalage, degrees(atan(pente))

    def position_a(self, distance, decalage=None):
        x, y, orientation = self.trajet.position_a(distance)
        braquage = 0.0
        if decalage is None:
            decalage, braquage = self.decalage_lateral_a(distance)
        angle = radians(orientation)
        return (x - sin(angle) * decalage,
                y + cos(angle) * decalage, orientation + braquage)

    @property
    def position(self):
        return self.position_a(self.distance)


@dataclass(frozen=True)
class EtatVehicule:
    identifiant: str
    type_vehicule: str
    couleur: str
    trajet: Trajet
    x: float
    y: float
    orientation: float
    en_attente: bool
    occupe: bool
    progression: float
    etape: str


@dataclass(frozen=True)
class EtatSimulation:
    vehicules: tuple[EtatVehicule, ...]
    nord_sud: str
    est_ouest: str
    nom_phase: str
    temps_phase_restant: float
    trajets_termines: int

    @property
    def voitures(self):
        voitures = []
        for vehicule in self.vehicules:
            if vehicule.type_vehicule == "car":
                voitures.append(vehicule)
        return tuple(voitures)

    @property
    def secours(self):
        secours = []
        for vehicule in self.vehicules:
            if vehicule.type_vehicule != "car":
                secours.append(vehicule)
        return tuple(secours)
