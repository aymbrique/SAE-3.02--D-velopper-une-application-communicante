"""Automate des feux : cycle, arbitrage des secours et dette compensatoire."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Request:
    identifier: str
    axis: str
    started_at: float
    requested_at: float
    passage: int | None = 0  # None : degagement de la caserne, sans passage a C.
    engaged: bool = False


class Lights:
    GREEN = 8.0
    AMBER = 1.0
    ALL_RED = 1.0
    COMPENSATION_SHARE = 0.25
    COMPENSATION_MIN = 0.05

    def __init__(self):
        self.axis = "NS"
        self.phase = "green"
        self.elapsed = 0.0
        self.owner = None
        self.owner_locked = False
        self.priority_green = False
        self.debt = {"NS": 0.0, "EW": 0.0}
        self.compensating = False
        self.compensation_budget = 0.0
        self.finish_green = False

    @property
    def opposite(self):
        return "EW" if self.axis == "NS" else "NS"

    def signal(self, axis):
        if axis == self.axis and self.phase != "all_red":
            return self.phase
        return "red"

    @property
    def remaining(self):
        duration = {"green": self.GREEN + self.compensation_budget,
                    "amber": self.AMBER, "all_red": self.ALL_RED}[self.phase]
        return max(0.0, duration - self.elapsed)

    @property
    def description(self):
        axis = "Nord-Sud" if self.axis == "NS" else "Est-Ouest"
        if self.phase == "all_red":
            return "Transition : tout rouge"
        if self.phase == "amber":
            return f"{axis} : orange"
        if self.owner and self.owner.axis == self.axis:
            return f"Priorite secours {self.owner.identifier} - {axis}"
        if self.compensating:
            return f"Compensation - {axis}"
        return f"Cycle normal - {axis}"

    def _priority_order(self, request):
        return (request.started_at, request.requested_at, request.identifier)

    def _select_owner(self, requests):
        crossings = [request for request in requests if request.passage is not None]
        current = None
        if self.owner:
            current = next((request for request in crossings
                            if (request.identifier, request.started_at, request.passage)
                            == (self.owner.identifier, self.owner.started_at, self.owner.passage)), None)
        if current and (self.owner_locked or current.engaged):
            self.owner = current
            self.owner_locked = True
            return
        # Un secours deja engage doit terminer, meme si l'autre mission est
        # plus ancienne. Sinon arbitrer les demandes presentes au seuil.
        engaged = [request for request in crossings if request.engaged]
        candidates = engaged or crossings or requests
        self.owner = min(candidates, key=self._priority_order) if candidates else None
        # Une demande seule peut preparer le vert. Quand deux demandes se
        # confrontent, le choix est fixe jusqu'a la fin du passage selectionne.
        self.owner_locked = bool(engaged or len(crossings) > 1)

    def _net_debt(self):
        # Chaque solde appartient a l'axe qui doit recevoir du vert en plus.
        # Deux retards opposes se compensent : seul leur ecart reste du.
        common = min(self.debt.values())
        for axis in self.debt:
            self.debt[axis] = max(0.0, self.debt[axis] - common)
            if self.debt[axis] < 1e-9:
                self.debt[axis] = 0.0

    def advance(self, dt, requests=(), busy=False, clear=True):
        # requests : demandes proches du carrefour. busy reste accepte pour les
        # appelants, mais une mission lointaine n'empeche pas la compensation.
        # clear : aucun vehicule n'est encore engage dans le carrefour.
        self._net_debt()
        previous = self.owner
        self._select_owner(requests)
        if self.compensating and self.owner is not None:
            # Le bonus non encore servi reste en dette. Le temps deja servi
            # ne devient pas retroactivement une prolongation prioritaire.
            self.compensating = False
            self.compensation_budget = 0.0

        if self.phase == "green":
            holding = self.owner is not None and self.owner.axis == self.axis
            if holding:
                self.priority_green = True
            released = previous is not None and self.priority_green and not holding
            if released:
                self.finish_green = True
            before = self.elapsed
            self.elapsed += dt
            extra = max(0.0, self.elapsed - self.GREEN) - max(0.0, before - self.GREEN)
            if holding:
                self.debt[self.opposite] += extra
            elif self.compensating:
                served = (min(max(0.0, self.elapsed - self.GREEN), self.compensation_budget)
                          - min(max(0.0, before - self.GREEN), self.compensation_budget))
                self.debt[self.axis] = max(0.0, self.debt[self.axis] - served)
            self._net_debt()
            duration = self.GREEN + self.compensation_budget
            ended = self.elapsed >= duration - 1e-9
            interrupted = self.finish_green and (self.priority_green or self.elapsed >= self.GREEN - 1e-9)
            priority_other_axis = self.owner is not None and self.owner.axis != self.axis
            if not holding and (ended or interrupted or priority_other_axis):
                self.phase = "amber"
                self.elapsed = 0.0
                self.compensating = False
        elif self.phase == "amber":
            self.elapsed += dt
            if self.elapsed >= self.AMBER - 1e-9:
                self.phase = "all_red"
                self.elapsed = 0.0
        else:
            self.elapsed += dt
            if self.elapsed >= self.ALL_RED - 1e-9 and clear:
                self.axis = self.owner.axis if self.owner else self.opposite
                self.phase = "green"
                self.elapsed = 0.0
                self.priority_green = False
                self.finish_green = False
                self.compensating = self.owner is None and self.debt[self.axis] > 1e-9
                # Rembourser un quart du solde par vert normal. Le minimum
                # d'un pas de simulation permet de solder les petits residus.
                self.compensation_budget = (
                    min(self.debt[self.axis], max(self.COMPENSATION_MIN,
                                                 self.debt[self.axis] * self.COMPENSATION_SHARE))
                    if self.compensating else 0.0)
