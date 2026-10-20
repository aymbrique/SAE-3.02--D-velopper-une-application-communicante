"""Automate des feux : cycle, arbitrage des secours et dette compensatoire."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Request:
    identifier: str
    axis: str
    started_at: float
    requested_at: float


class Lights:
    GREEN = 8.0
    AMBER = 1.0
    ALL_RED = 1.0

    def __init__(self):
        self.axis = "NS"
        self.phase = "green"
        self.elapsed = 0.0
        self.owner = None
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

    def advance(self, dt, requests=(), busy=False, clear=True):
        # requests : demandes proches du carrefour ; busy : un secours est occupe.
        # clear : aucun vehicule n'est encore engage dans le carrefour.
        previous = self.owner
        if self.owner:
            # Garder le meme secours, mais actualiser son axe au prochain passage.
            self.owner = next((request for request in requests
                               if request.identifier == self.owner.identifier), None)
        if self.owner is None and requests:
            # Plus ancienne mission, puis plus ancienne demande, puis identifiant.
            self.owner = min(requests, key=self._priority_order)
        if self.compensating and busy:
            self.compensating = False
            self.compensation_budget = 0.0
            self.finish_green = True

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
                self.debt[self.axis] = max(0.0, self.debt[self.axis] - extra)
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
                self.compensating = not busy and self.debt[self.axis] > 1e-9
                # Conserver tout le solde, mais distribuer au plus 8 s de bonus
                # par vert pour ne pas affamer l'autre axe (16 s au total).
                self.compensation_budget = min(self.GREEN, self.debt[self.axis]) if self.compensating else 0.0
