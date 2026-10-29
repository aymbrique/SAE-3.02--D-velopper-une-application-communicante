"""Automate des feux : cycle, arbitrage des secours et dette compensatoire."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DemandePriorite:
    identifiant: str
    axe: str
    debut_mission: float
    date_demande: float
    passage: int | None = 0  # None : degagement de la caserne, sans passage a C.
    engage: bool = False


class Feux:
    DUREE_VERT = 8.0
    DUREE_ORANGE = 1.0
    DUREE_TOUT_ROUGE = 1.0
    PART_COMPENSATION = 0.25
    COMPENSATION_MINIMALE = 0.05

    def __init__(self):
        self.axe = "NS"
        self.phase = "green"
        self.temps_ecoule = 0.0
        self.prioritaire = None
        self.priorite_verrouillee = False
        self.vert_prioritaire = False
        self.reserve_temps = {"NS": 0.0, "EW": 0.0}
        self.en_compensation = False
        self.bonus_compensation = 0.0
        self.terminer_vert = False

    @property
    def axe_oppose(self):
        return "EW" if self.axe == "NS" else "NS"

    def signal(self, axe):
        if axe == self.axe and self.phase != "all_red":
            return self.phase
        return "red"

    @property
    def temps_restant(self):
        duree = {"green": self.DUREE_VERT + self.bonus_compensation,
                    "amber": self.DUREE_ORANGE, "all_red": self.DUREE_TOUT_ROUGE}[self.phase]
        return max(0.0, duree - self.temps_ecoule)

    @property
    def description(self):
        axe = "Nord-Sud" if self.axe == "NS" else "Est-Ouest"
        if self.phase == "all_red":
            return "Transition : tout rouge"
        if self.phase == "amber":
            return f"{axe} : orange"
        if self.prioritaire and self.prioritaire.axe == self.axe:
            return f"Priorite secours {self.prioritaire.identifiant} - {axe}"
        if self.en_compensation:
            return f"Compensation - {axe}"
        return f"Cycle normal - {axe}"

    def _ordre_priorite(self, demande):
        return (demande.debut_mission, demande.date_demande, demande.identifiant)

    def _choisir_prioritaire(self, demandes):
        passages = [demande for demande in demandes if demande.passage is not None]
        actuel = None
        if self.prioritaire:
            actuel = next((demande for demande in passages
                            if (demande.identifiant, demande.debut_mission, demande.passage)
                            == (self.prioritaire.identifiant, self.prioritaire.debut_mission, self.prioritaire.passage)), None)
        if actuel and (self.priorite_verrouillee or actuel.engage):
            self.prioritaire = actuel
            self.priorite_verrouillee = True
            return
        # Un secours deja engage doit terminer, meme si l'autre mission est
        # plus ancienne. Sinon arbitrer les demandes presentes au seuil.
        engage = [demande for demande in passages if demande.engage]
        candidats = engage or passages or demandes
        self.prioritaire = min(candidats, key=self._ordre_priorite) if candidats else None
        # Une demande seule peut preparer le vert. Quand deux demandes se
        # confrontent, le choix est fixe jusqu'a la fin du passage selectionne.
        self.priorite_verrouillee = bool(engage or len(passages) > 1)

    def _compenser_reserves(self):
        # Chaque solde appartient a l'axe qui doit recevoir du vert en plus.
        # Deux retards opposes se compensent : seul leur ecart reste du.
        commun = min(self.reserve_temps.values())
        for axe in self.reserve_temps:
            self.reserve_temps[axe] = max(0.0, self.reserve_temps[axe] - commun)
            if self.reserve_temps[axe] < 1e-9:
                self.reserve_temps[axe] = 0.0

    def avancer(self, dt, demandes=(), occupe=False, libre=True):
        # demandes : secours proches du carrefour. occupe reste accepte pour les
        # appelants, mais une mission lointaine n'empeche pas la compensation.
        # libre : aucun vehicule n'est encore engage dans le carrefour.
        self._compenser_reserves()
        precedent = self.prioritaire
        self._choisir_prioritaire(demandes)
        if self.en_compensation and self.prioritaire is not None:
            # Le bonus non encore servi reste en dette. Le temps deja servi
            # ne devient pas retroactivement une prolongation prioritaire.
            self.en_compensation = False
            self.bonus_compensation = 0.0

        if self.phase == "green":
            maintient_priorite = self.prioritaire is not None and self.prioritaire.axe == self.axe
            if maintient_priorite:
                self.vert_prioritaire = True
            libere = precedent is not None and self.vert_prioritaire and not maintient_priorite
            if libere:
                self.terminer_vert = True
            avant = self.temps_ecoule
            self.temps_ecoule += dt
            supplement = max(0.0, self.temps_ecoule - self.DUREE_VERT) - max(0.0, avant - self.DUREE_VERT)
            if maintient_priorite:
                self.reserve_temps[self.axe_oppose] += supplement
            elif self.en_compensation:
                restitue = (min(max(0.0, self.temps_ecoule - self.DUREE_VERT), self.bonus_compensation)
                          - min(max(0.0, avant - self.DUREE_VERT), self.bonus_compensation))
                self.reserve_temps[self.axe] = max(0.0, self.reserve_temps[self.axe] - restitue)
            self._compenser_reserves()
            duree = self.DUREE_VERT + self.bonus_compensation
            termine = self.temps_ecoule >= duree - 1e-9
            interrompu = self.terminer_vert and (self.vert_prioritaire or self.temps_ecoule >= self.DUREE_VERT - 1e-9)
            priorite_autre_axe = self.prioritaire is not None and self.prioritaire.axe != self.axe
            if not maintient_priorite and (termine or interrompu or priorite_autre_axe):
                self.phase = "amber"
                self.temps_ecoule = 0.0
                self.en_compensation = False
        elif self.phase == "amber":
            self.temps_ecoule += dt
            if self.temps_ecoule >= self.DUREE_ORANGE - 1e-9:
                self.phase = "all_red"
                self.temps_ecoule = 0.0
        else:
            self.temps_ecoule += dt
            if self.temps_ecoule >= self.DUREE_TOUT_ROUGE - 1e-9 and libre:
                self.axe = self.prioritaire.axe if self.prioritaire else self.axe_oppose
                self.phase = "green"
                self.temps_ecoule = 0.0
                self.vert_prioritaire = False
                self.terminer_vert = False
                self.en_compensation = self.prioritaire is None and self.reserve_temps[self.axe] > 1e-9
                # Rembourser un quart du solde par vert normal. Le minimum
                # d'un pas de simulation permet de solder les petits residus.
                self.bonus_compensation = (
                    min(self.reserve_temps[self.axe], max(self.COMPENSATION_MINIMALE,
                                                 self.reserve_temps[self.axe] * self.PART_COMPENSATION))
                    if self.en_compensation else 0.0)
