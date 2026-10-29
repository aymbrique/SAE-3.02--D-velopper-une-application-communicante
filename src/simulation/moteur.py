"""Simulation a pas fixe. Les files tout droit compatibles peuvent passer ensemble."""

from math import cos, hypot, inf, isfinite, radians, sin
from random import Random

from src.modeles.plan import (DESTINATIONS, DIRECTIONS_OPPOSEES, METRES_PAR_UNITE, PARKING_Y,
                               LARGEUR_SCENE, HAUTEUR_SCENE, sortie_voiture, trajet_voiture, trajet_secours, sur_chaussee)
from src.modeles.vehicules import EtatSimulation, Vehicule, EtatVehicule
from src.simulation.feux import Feux, DemandePriorite
from src.simulation.priorite import (DECALAGE_RANGEMENT, proche_secours,
                                     carrosseries_separees, coins_carrosserie)

PAS_TEMPS = 0.05  # Duree d'un calcul de deplacement, en secondes simulees.
DISTANCE_SECURITE = 44.0  # Distance minimale entre les centres des vehicules.
MAX_VOITURES = 25
DUREE_INTERVENTION = 8.0  # Temps passe sur le lieu de l'intervention.
VITESSE_SECOURS = 56.0  # Plus rapide que les voitures, y compris dans les virages.
ANTICIPATION_RACCORDEMENT = 3 * VITESSE_SECOURS  # Anticiper la priorite 3 s avant un raccordement.
FACTEUR_VITESSE_VIRAGE = 40 / 28  # Degager les virages plus vite que l'allure de croisiere.


def voiture_rangee(vehicule):
    return vehicule.debut_manoeuvre is None and vehicule.decalage_lateral >= DECALAGE_RANGEMENT - 1e-6


class Simulation:
    def __init__(self, debit=12, graine=302):
        self.aleatoire = Random(graine)
        self.debit = debit
        self.temps = 0.0
        self.accumulateur = 0.0
        self.temps_depuis_arrivee = 0.0
        self.trajets_termines = 0
        self.prochain_identifiant = 1
        self.limites_circulation = (0, 0, LARGEUR_SCENE, HAUTEUR_SCENE)
        self.feux = Feux()
        self.vehicules_engages = set()
        self.conflits_raccordements = {}
        self.conflits_carrefour = {}
        self.acces_a_degager = set()
        self.voitures = []
        self.secours = []
        self.evenements = []
        for identifiant, type_vehicule, y, couleur in (("01", "fire", PARKING_Y["01"], "#db6758"),
                                            ("02", "ambulance", PARKING_Y["02"], "#f8faf9")):
            trajet, passages, arret_intervention = trajet_secours(identifiant, y)
            self.secours.append(Vehicule(identifiant, type_vehicule, trajet, passages, couleur, VITESSE_SECOURS,
                                        arret_intervention=arret_intervention, duree_estimee=trajet.longueur / VITESSE_SECOURS + DUREE_INTERVENTION,
                                        longueur_manoeuvre=60.0))

    @property
    def vehicules(self):
        return self.voitures + self.secours

    def obtenir_secours(self, identifiant):
        for vehicule in self.secours:
            if vehicule.identifiant == identifiant:
                return vehicule
        raise ValueError("Secours inconnu : " + identifiant)

    def demarrer_mission(self, identifiant, destination="S"):
        vehicule = self.obtenir_secours(identifiant)
        if vehicule.occupe:
            return False
        parking_y = vehicule.trajet.points[0][1]
        trajet, passages, arret_intervention = trajet_secours(identifiant, parking_y, destination)
        vehicule.trajet = trajet
        vehicule.passages = passages
        vehicule.arret_intervention = arret_intervention
        vehicule.destination = destination
        vehicule.duree_estimee = trajet.longueur / vehicule.vitesse + DUREE_INTERVENTION
        vehicule.en_attente = False
        vehicule.occupe = True
        vehicule.debut_mission = self.temps
        vehicule.distance = 0.0
        vehicule.indice_passage = 0
        vehicule.date_demande = None
        vehicule.decalage_lateral = 0.0
        vehicule.debut_manoeuvre = None
        vehicule.intervention_effectuee = False
        vehicule.temps_intervention_restant = 0.0
        self.evenements.append((identifiant, "occupe"))
        return True

    def recuperer_evenements(self):
        evenements = self.evenements
        self.evenements = []
        return evenements

    def choisir_virage(self):
        # 95 % tout droit ; les 5 % restants sont repartis entre les virages.
        choix = self.aleatoire.randrange(200)
        if choix < 190:
            return "straight"
        if choix < 195:
            return "left"
        return "right"

    def choisir_variante(self, origine, virage):
        # Un trajet sur vingt bifurque au raccordement situe apres le feu.
        if (origine, virage) in (("N", "straight"), ("E", "left"), ("W", "right")):
            return "lower_west" if self.aleatoire.randrange(20) == 0 else None
        if (origine, virage) in (("W", "straight"), ("N", "left"), ("S", "right")):
            return "middle_north" if self.aleatoire.randrange(20) == 0 else None
        return None

    def ajouter_voiture(self, origine=None, virage=None, *, variante=None):
        if len(self.voitures) >= MAX_VOITURES:
            return None
        # Une arrivee sur deux vient du Nord ; les trois autres se partagent le reste.
        origine = origine or self.aleatoire.choice(("N", "N", "N", "S", "E", "W"))
        virage_automatique = virage is None
        virage = virage or self.choisir_virage()
        if virage_automatique and variante is None:
            variante = self.choisir_variante(origine, virage)
        trajet, arret = trajet_voiture(origine, virage, self.limites_circulation, variante=variante)
        x, y, _ = trajet.position_a(0)
        for autre in self.vehicules:
            x_autre, y_autre, angle = autre.position
            if hypot(x - x_autre, y - y_autre) < DISTANCE_SECURITE:
                return None
        axe = "NS" if origine in ("N", "S") else "EW"
        couleur = self.aleatoire.choice(("#5eb9cc", "#e9bc65", "#9a8ed4", "#78b89c", "#e7967f"))
        vehicule = Vehicule(f"C{self.prochain_identifiant:04}", "car", trajet,
                          ((arret, sortie_voiture(trajet), axe),), couleur, 28, origine=origine, virage=virage)
        self.prochain_identifiant += 1
        self.voitures.append(vehicule)
        return vehicule

    def approche(self, vehicule):
        if not vehicule.occupe or vehicule.passage is None:
            return None, None
        temps_restant = max(0.0, vehicule.passage[0] - vehicule.distance)
        distance_metres = temps_restant * METRES_PAR_UNITE
        delai_arrivee = inf
        if vehicule.vitesse > 0:
            delai_arrivee = temps_restant / vehicule.vitesse
        return distance_metres, delai_arrivee

    def demandes(self):
        resultat = []
        for vehicule in self.secours:
            # Le second passage est le retour : ne pas le reserver en allant
            # au patient, pendant les soins ou encore dans l'allee du parking.
            if vehicule.indice_passage == 1 and (
                    not vehicule.intervention_effectuee or vehicule.temps_intervention_restant > 0
                    or not sur_chaussee(*vehicule.position[:2])):
                continue
            distance, delai_arrivee = self.approche(vehicule)
            retour_caserne = self._revient_caserne(vehicule)
            au_seuil = distance is not None and (distance <= 150 or delai_arrivee <= 10)
            if retour_caserne or au_seuil or self._quitte_caserne(vehicule):
                # Demander le vert des l'approche, meme si la sortie est encore
                # occupee. Le controle d'entree impose toujours sa liberation.
                if vehicule.passage and vehicule.identifiant not in self.vehicules_engages:
                    # Deux secours peuvent rejoindre la meme file au retour.
                    # Le suiveur ne doit pas verrouiller le vert devant celui
                    # qui le bloque physiquement et doit passer en premier.
                    if any(autre is not vehicule and autre.occupe and autre.passage
                           and autre.passage[2] == vehicule.passage[2]
                           and self._bloque_approche(autre, vehicule, vehicule.passage[0])
                           for autre in self.secours):
                        continue
                if vehicule.date_demande is None:
                    vehicule.date_demande = self.temps
                axe = "NS" if retour_caserne else vehicule.passage[2]
                resultat.append(DemandePriorite(vehicule.identifiant, axe,
                                      vehicule.debut_mission, vehicule.date_demande,
                                      passage=vehicule.indice_passage if au_seuil else None,
                                      engage=vehicule.identifiant in self.vehicules_engages))
        return resultat

    def _quitte_caserne(self, vehicule):
        """Des le depart, degager la file Nord avant d'inserer le secours."""
        if not vehicule.occupe or vehicule.intervention_effectuee or vehicule.indice_passage != 0:
            return False
        sortie_caserne = next(fin for _, fin, cle in vehicule.trajet.raccordements if cle == "F")
        return vehicule.distance < sortie_caserne

    def _revient_caserne(self, vehicule):
        """Conserver le vert Nord jusqu'au degagement du retour a la caserne.

        Une file Nord au rouge pourrait sinon emprisonner le premier secours
        devant F, boucher la sortie du carrefour et bloquer le second secours.
        """
        if not vehicule.occupe or not vehicule.intervention_effectuee or vehicule.passage is not None:
            return False
        fin_caserne = [fin for _, fin, cle in vehicule.trajet.raccordements if cle == "F"][-1]
        return vehicule.distance < fin_caserne

    def avancer(self, duree):
        if not isfinite(duree) or duree < 0:
            raise ValueError("Duree invalide")
        self.accumulateur += duree
        while self.accumulateur >= PAS_TEMPS - 1e-9:
            self._avancer_un_pas()
            self.accumulateur -= PAS_TEMPS

    def _avancer_un_pas(self):
        self.temps += PAS_TEMPS
        self._actualiser_acces_a_degager()
        self._actualiser_rangement()
        self._actualiser_voies_secours()
        secours_occupe = False
        for secours in self.secours:
            if secours.occupe:
                secours_occupe = True
        self.feux.avancer(PAS_TEMPS, self.demandes(), secours_occupe,
                            not self.vehicules_engages)
        if self.debit > 0:
            self.temps_depuis_arrivee += PAS_TEMPS
            if self.temps_depuis_arrivee >= 60 / self.debit:
                self.temps_depuis_arrivee %= 60 / self.debit
                self.ajouter_voiture()
        # Degager le carrefour en premier, puis les vehicules en tete de file.
        ordonnes = sorted(self.vehicules, key=self._ordre_deplacement)
        for vehicule in ordonnes:
            self._deplacer(vehicule)
        voitures_restantes = []
        for voiture in self.voitures:
            if voiture.distance >= voiture.trajet.longueur - 1e-6:
                self.trajets_termines += 1
            else:
                voitures_restantes.append(voiture)
        self.voitures = voitures_restantes

    def _ordre_deplacement(self, vehicule):
        # Degager d'abord les sorties aussi : un leader deja sorti doit avancer
        # avant la voiture qui le suit encore dans le carrefour, sans micro-arret.
        degage = (vehicule.identifiant in self.vehicules_engages
                    or (vehicule.type_vehicule == "car" and vehicule.passage is None))
        return (not degage, -vehicule.distance, vehicule.identifiant)

    def _position(self, vehicule, distance, decalage=None):
        return vehicule.position_a(distance, decalage)

    def _mouvements_opposes_caserne(self, premier, second):
        """Un retour et un depart utilisent deux voies distinctes dans l'allee."""
        if (premier.type_vehicule == "car" or second.type_vehicule == "car"
                or not premier.occupe or not second.occupe or premier.intervention_effectuee == second.intervention_effectuee):
            return False
        return all(any(cle == "parking" and arret <= vehicule.distance < fin
                       for arret, fin, cle in vehicule.trajet.raccordements)
                   for vehicule in (premier, second))

    def vehicules_separes(self, premier, second, position=None, position_autre=None):
        position = premier.position if position is None else position
        position_autre = second.position if position_autre is None else position_autre
        distance = hypot(position[0] - position_autre[0], position[1] - position_autre[1])
        if distance >= DISTANCE_SECURITE - 1e-7:
            return True
        if self._mouvements_opposes_caserne(premier, second):
            return carrosseries_separees(premier, position, second, position_autre)
        if abs(premier.decalage_lateral) > 1e-6 or abs(second.decalage_lateral) > 1e-6:
            return carrosseries_separees(premier, position, second, position_autre)
        # Apres une reinsertion, un ecart deja court ne doit pas emprisonner
        # le vehicule de tete : il peut s'eloigner en gardant les gabarits libres.
        precedent = hypot(premier.position[0] - second.position[0],
                         premier.position[1] - second.position[1])
        s_eloigne = distance > precedent + 1e-7
        secours_sans_rapprochement = ((premier.type_vehicule != "car" or second.type_vehicule != "car")
                            and distance >= precedent - 1e-7)
        return ((s_eloigne or secours_sans_rapprochement)
                and carrosseries_separees(premier, position, second, position_autre))

    def _position_libre(self, vehicule, position, ignores=()):
        for autre in self.vehicules:
            if autre is vehicule or autre.identifiant in ignores:
                continue
            if not self.vehicules_separes(vehicule, autre, position):
                return False
        return True

    def _trajet_libre(self, vehicule, cible, ignores=()):
        position = self._position(vehicule, cible)
        if vehicule.debut_manoeuvre is not None:
            if not all(sur_chaussee(x, y) for x, y in coins_carrosserie(vehicule, position)):
                return False
        return self._position_libre(vehicule, position, ignores)

    def _peut_se_ranger(self, voiture):
        if voiture.identifiant in self.vehicules_engages or voiture.vitesse <= 0:
            return False
        fin = voiture.distance + voiture.longueur_manoeuvre
        if voiture.passage and voiture.distance <= voiture.passage[0] < fin - 1e-6:
            return False
        _, _, avant = voiture.trajet.position_a(voiture.distance)
        for distance in (voiture.distance + 20, voiture.distance + 40, fin):
            _, _, apres = voiture.trajet.position_a(distance)
            if cos(radians(avant - apres)) < .995:
                return False
        # Ne jamais se garer au milieu d'un raccordement.
        return not any(arret < fin and voiture.distance < arrivee
                       for arret, arrivee, _ in voiture.trajet.raccordements)

    def _actualiser_rangement(self):
        for voiture in self.voitures:
            proches = tuple(secours.identifiant for secours in self.secours
                           if proche_secours(voiture, secours))
            dans_raccordement = any(arret < voiture.distance < fin
                              for arret, fin, _ in voiture.trajet.raccordements)
            peut_se_ranger = (voiture.identifiant not in self.vehicules_engages and not dans_raccordement
                        and (self._peut_se_ranger(voiture) or voiture.decalage_lateral > 0
                             or (voiture.debut_manoeuvre is not None
                                 and voiture.decalage_cible == DECALAGE_RANGEMENT)))
            voiture.cede_aux = proches if peut_se_ranger else ()
            cible = DECALAGE_RANGEMENT if voiture.cede_aux else 0.0
            if (voiture.debut_manoeuvre is not None
                    or abs(voiture.decalage_lateral - cible) < 1e-9):
                continue
            if cible == 0 and not self._reinsertion_possible(voiture):
                continue
            voiture.debut_manoeuvre = voiture.distance
            voiture.decalage_initial = voiture.decalage_lateral
            voiture.decalage_cible = cible
            if not all(sur_chaussee(x, y)
                       for distance in range(0, int(voiture.longueur_manoeuvre) + 1, 3)
                       for x, y in coins_carrosserie(voiture, voiture.position_a(voiture.distance + distance))):
                voiture.debut_manoeuvre = None
                if cible:
                    voiture.cede_aux = ()

    def _reinsertion_possible(self, voiture):
        x, y, orientation = voiture.trajet.position_a(voiture.distance)
        dx, dy = cos(radians(orientation)), sin(radians(orientation))
        for secours in self.secours:
            if not secours.occupe:
                continue
            rx, ry, orientation_autre = secours.trajet.position_a(secours.distance)
            avance_relative = (x - rx) * dx + (y - ry) * dy
            ecart_lateral = abs((x - rx) * dy - (y - ry) * dx)
            if (cos(radians(orientation - orientation_autre)) > .96
                    and -45 < avance_relative < 80 and ecart_lateral < 40):
                return False
        return True

    def _actualiser_voies_secours(self):
        """Seul le secours peut emprunter le milieu de la route pour depasser."""
        actifs = [secours for secours in self.secours if secours.occupe]
        depassant = min(actifs, key=lambda secours: (secours.debut_mission, secours.identifiant),
                      default=None)
        for secours in actifs:
            x, y, orientation = secours.trajet.position_a(secours.distance)
            dx, dy = cos(radians(orientation)), sin(radians(orientation))
            cible = 0.0
            if secours is depassant and not secours.temps_intervention_restant:
                for voiture in self.voitures:
                    ox, oy, orientation_autre = voiture.position
                    avance_relative = (ox - x) * dx + (oy - y) * dy
                    ecart_lateral = abs((ox - x) * dy - (oy - y) * dx)
                    if (cos(radians(orientation - orientation_autre)) > .8
                            and -45 < avance_relative < 180 and ecart_lateral < DECALAGE_RANGEMENT - .5):
                        cible = -DECALAGE_RANGEMENT
                        break
            # Garder aussi la place de reintegrer sa voie avant le prochain virage.
            if cible and any(arret - 4 * secours.longueur_manoeuvre <= secours.distance < fin
                              for arret, fin, _ in (*secours.trajet.raccordements, *secours.passages)):
                cible = 0.0
            if cible and any(cos(radians(orientation - secours.trajet.position_a(
                    secours.distance + decalage)[2])) < .995 for decalage in (30, 60, 90, 120)):
                cible = 0.0
            if secours.debut_manoeuvre is not None:
                continue
            if secours.debut_manoeuvre is None and abs(secours.decalage_lateral - cible) < 1e-9:
                continue
            precedent = (secours.debut_manoeuvre, secours.decalage_initial, secours.decalage_cible)
            secours.debut_manoeuvre = secours.distance
            secours.decalage_initial = secours.decalage_lateral
            secours.decalage_cible = cible
            if cible and not all(sur_chaussee(px, py)
                                  for decalage in (15, 30, 45, 60)
                                  for px, py in coins_carrosserie(secours, secours.position_a(secours.distance + decalage))):
                secours.debut_manoeuvre, secours.decalage_initial, secours.decalage_cible = precedent

    def _actualiser_acces_a_degager(self):
        cles = {cle for secours in self.secours if secours.occupe
                for arret, fin, cle in secours.trajet.raccordements
                if (secours.distance < fin and (arret - secours.distance <= ANTICIPATION_RACCORDEMENT
                    or cle == "F" and self._quitte_caserne(secours)))}
        self.acces_a_degager = {
            vehicule.identifiant for vehicule in self.vehicules
            if (vehicule.type_vehicule == "car" or vehicule.occupe)
            and any(cle in cles and (arret < vehicule.distance < fin
                    or vehicule.type_vehicule != "car" and arret == vehicule.distance)
                    for arret, fin, cle in vehicule.trajet.raccordements)}

    def _degage_file_acces(self, vehicule):
        """Degager une file encore engagee dans un carrefour ou un acces de secours."""
        x, y, orientation = vehicule.trajet.position_a(vehicule.distance)
        dx, dy = cos(radians(orientation)), sin(radians(orientation))
        for autre in self.vehicules:
            if autre.type_vehicule != "car" and autre.identifiant not in self.acces_a_degager:
                continue
            en_manoeuvre = (autre.type_vehicule == "car" and autre.debut_manoeuvre is not None
                            and autre.decalage_cible == DECALAGE_RANGEMENT)
            if (autre is vehicule or not en_manoeuvre and autre.identifiant not in (
                    self.vehicules_engages | self.acces_a_degager)):
                continue
            reference = autre.distance
            if autre.type_vehicule != "car":
                # Un secours qui s'insere regarde la voie a la sortie de sa courbe.
                reference = next((fin for arret, fin, _ in autre.trajet.raccordements
                                  if arret <= autre.distance < fin), reference)
            ox, oy, orientation_autre = autre.trajet.position_a(reference)
            avance_relative = (x - ox) * dx + (y - oy) * dy
            ecart_lateral = abs((x - ox) * dy - (y - oy) * dx)
            minimum = -DISTANCE_SECURITE if reference != autre.distance else 0.0
            if (cos(radians(orientation - orientation_autre)) > .96
                    and minimum < avance_relative < MAX_VOITURES * DISTANCE_SECURITE and ecart_lateral < 18):
                return True
        return False

    def _suivre_file(self, vehicule, cible):
        """Conserver l'ordre de la file, meme si son leader est range au bord."""
        x, y, orientation = vehicule.trajet.position_a(vehicule.distance)
        dx, dy = cos(radians(orientation)), sin(radians(orientation))
        for autre in self.voitures:
            if autre is vehicule:
                continue
            if vehicule.type_vehicule != "car" and not (autre.debut_manoeuvre is not None
                                               and autre.decalage_cible == 0):
                continue
            # La voie habituelle reste reservee au leader pendant sa manoeuvre.
            ox, oy, orientation_autre = autre.trajet.position_a(autre.distance)
            if cos(radians(orientation - orientation_autre)) < .96:
                continue
            avance_relative = (ox - x) * dx + (oy - y) * dy
            ecart_lateral = abs((ox - x) * dy - (oy - y) * dx)
            if 0 < avance_relative < DISTANCE_SECURITE + 150 and ecart_lateral < 18:
                cible = min(cible, vehicule.distance + max(0.0, avance_relative - DISTANCE_SECURITE))
        return cible

    def passages_compatibles(self, premier, second):
        """Suivi tout droit et mouvements opposes sans croisement de trajectoire."""
        if (premier.type_vehicule == "car") != (second.type_vehicule == "car"):
            return True  # Le secours se guide sur les carrosseries, sans reserver tout le carrefour.
        if premier.type_vehicule != "car" or premier.origine not in DIRECTIONS_OPPOSEES:
            return False
        if second.origine == premier.origine:
            return True
        return (second.origine == DIRECTIONS_OPPOSEES[premier.origine]
                and premier.virage in ("straight", "right")
                and second.virage in ("straight", "right"))

    def _suit_sortie(self, vehicule, fin, autre, fin_autre):
        """Un leader deja sorti peut etre suivi dans la meme voie, a distance."""
        if autre.distance < fin_autre or autre.vitesse <= 0 or autre.en_attente:
            return False
        x, y, orientation = vehicule.trajet.position_a(fin)
        ox, oy, orientation_autre = autre.position
        dx, dy = cos(radians(orientation)), sin(radians(orientation))
        meme_orientation = cos(radians(orientation_autre - orientation)) > 0.999
        avance_relative = (ox - x) * dx + (oy - y) * dy
        ecart_lateral = abs((ox - x) * dy - (oy - y) * dx)
        return meme_orientation and avance_relative >= 0 and ecart_lateral < 1e-6

    def _vehicules_sortis(self, vehicule, fin):
        sortis = set()
        for autre in self.vehicules:
            if autre is vehicule or autre.identifiant in self.vehicules_engages:
                continue
            for _, fin_autre, _ in autre.passages:
                if self._suit_sortie(vehicule, fin, autre, fin_autre):
                    sortis.add(autre.identifiant)
                    break
        return sortis

    def _peut_entrer(self, vehicule):
        arret, fin, axe = vehicule.passage
        if vehicule.type_vehicule == "car" and vehicule.decalage_lateral == 0:
            for autre in self.voitures:
                if (autre is not vehicule and autre.origine == vehicule.origine
                        and autre.decalage_lateral > 0 and not autre.cede_aux
                        and vehicule.distance - 28 < autre.distance < vehicule.distance + 150):
                    return False  # Laisser la voiture rangee reintegrer sa file.
        for autre in self.vehicules:
            if autre.identifiant in self.vehicules_engages and autre is not vehicule:
                if not self.passages_compatibles(vehicule, autre):
                    return False
                if (vehicule.type_vehicule != "car" and autre.type_vehicule == "car"
                        and self._conflit_devant_carrefour(vehicule, autre)):
                    return False
                if vehicule.decalage_lateral > 0 or autre.decalage_lateral > 0:
                    point = self._position(vehicule, vehicule.distance + vehicule.vitesse * PAS_TEMPS)
                    ox, oy, _ = autre.position
                    if hypot(point[0] - ox, point[1] - oy) < DISTANCE_SECURITE - 1e-7:
                        return False
        if self.feux.signal(axe) != "green":
            return False
        if vehicule.type_vehicule == "car" and self.feux.prioritaire:
            secours = self.obtenir_secours(self.feux.prioritaire.identifiant)
            if secours.passage and not self._bloque_approche(vehicule, secours, secours.passage[0]):
                return False
        if vehicule.type_vehicule != "car" and self.feux.prioritaire and self.feux.prioritaire.identifiant != vehicule.identifiant:
            return False
        if vehicule.type_vehicule != "car":
            # Un obstacle lointain ou dans une autre branche ne ferme pas l'entree.
            # Chaque pas reste soumis au controle de collision des carrosseries.
            return self._trajet_libre(vehicule, vehicule.distance + min(.05, vehicule.vitesse * PAS_TEMPS))
        # Une voiture deja engagee et en mouvement ne bouche pas tout le trajet
        # des suivantes tout droit. Cela vaut aussi lorsqu'elle vient de sortir.
        # Les vehicules arretes, les virages et les secours restent des obstacles.
        suivants = self._vehicules_sortis(vehicule, fin)
        for autre in self.vehicules:
            if (autre is not vehicule and self.passages_compatibles(vehicule, autre)
                    and autre.vitesse > 0 and not autre.en_attente
                    and autre.distance > autre.passages[0][0]):
                suivants.add(autre.identifiant)
        # Ce controle global reserve toujours une sortie non bouchee. Le controle
        # de chaque deplacement dans _deplacer ne saute aucun vehicule : DISTANCE_SECURITE reste
        # obligatoire, meme avec plusieurs voitures engagees sur la meme voie.
        for decalage in range(0, int(fin - arret) + 46, 6):
            if not self._trajet_libre(vehicule, arret + decalage, suivants):
                return False
        return True

    def _conflit_devant_carrefour(self, secours, voiture):
        """Ne pas couper la manoeuvre d'une voiture deja engagee au carrefour."""
        arret, fin, _ = secours.passage
        arret_voiture, fin_voiture, _ = voiture.passage
        entree_direction, sortie_direction = secours.trajet.position_a(arret), secours.trajet.position_a(fin)
        entree_voiture, sortie_voiture = voiture.trajet.position_a(arret_voiture), voiture.trajet.position_a(fin_voiture)
        if all(hypot(premier[0] - second[0], premier[1] - second[1]) < 1
               and cos(radians(premier[2] - second[2])) > .999
               for premier, second in ((entree_direction, entree_voiture), (sortie_direction, sortie_voiture))):
            return False  # Le suivi dans la meme voie reste possible, a distance.
        manoeuvre = ((voiture.debut_manoeuvre - arret_voiture, voiture.decalage_initial,
                      voiture.decalage_cible, voiture.longueur_manoeuvre)
                     if voiture.debut_manoeuvre is not None else (None, voiture.decalage_lateral))
        cle = (entree_direction, sortie_direction, entree_voiture, sortie_voiture, manoeuvre)
        if cle not in self.conflits_carrefour:
            chemin = [secours.position_a(arret + decalage)
                    for decalage in range(0, int(fin - arret) + 45, 3)]
            dernier = -inf
            for decalage in range(0, int(fin_voiture - arret_voiture) + 45, 3):
                position = voiture.position_a(arret_voiture + decalage)
                if any(hypot(position[0] - point[0], position[1] - point[1]) < DISTANCE_SECURITE
                       and not carrosseries_separees(secours, point, voiture, position) for point in chemin):
                    dernier = decalage + 3
            self.conflits_carrefour[cle] = dernier
        return voiture.distance - arret_voiture <= self.conflits_carrefour[cle]

    def _deplacer(self, vehicule):
        vehicule.vitesse_actuelle = 0.0
        if vehicule.type_vehicule != "car" and not vehicule.occupe:
            return
        if (vehicule.type_vehicule == "car" and vehicule.cede_aux
                and voiture_rangee(vehicule) and not self._degage_file_acces(vehicule)):
            vehicule.en_attente = True
            return
        if vehicule.temps_intervention_restant > 0:
            vehicule.temps_intervention_restant = max(0.0, vehicule.temps_intervention_restant - PAS_TEMPS)
            vehicule.en_attente = True
            return
        ancien = vehicule.distance
        vitesse = vehicule.vitesse
        if vehicule.type_vehicule == "car" and any(debut <= ancien < fin
                                         for debut, fin in vehicule.trajet.zones_virage):
            vitesse *= FACTEUR_VITESSE_VIRAGE
        if vehicule.type_vehicule == "car":
            x, y, angle = vehicule.position
            dx, dy = cos(radians(angle)), sin(radians(angle))
            for autre in self.voitures:
                if autre is vehicule:
                    continue
                ox, oy, _ = autre.position
                avance_relative = (ox - x) * dx + (oy - y) * dy
                ecart_lateral = abs((ox - x) * dy - (oy - y) * dx)
                if (autre.decalage_lateral > 0 and not autre.cede_aux
                        and -20 < avance_relative < DISTANCE_SECURITE + 12 and ecart_lateral < 40):
                    vitesse = min(vitesse, 18.0)
                if autre.identifiant not in self.vehicules_engages:
                    continue
                if autre.virage == "straight" or autre.virage == vehicule.virage:
                    continue
                if 0 < avance_relative < 150 and ecart_lateral < 70:
                    vitesse = min(vitesse, 18.0)
        cible = min(ancien + vitesse * PAS_TEMPS, vehicule.trajet.longueur)
        cible = self._suivre_file(vehicule, cible)
        if (vehicule.type_vehicule == "car" and vehicule.cede_aux
                and vehicule.debut_manoeuvre is not None):
            cible = min(cible, vehicule.debut_manoeuvre + vehicule.longueur_manoeuvre)
        cible = self._limiter_aux_raccordements(vehicule, ancien, cible)
        passage = vehicule.passage
        entre = passage is not None and ancien <= passage[0] and cible > passage[0]
        if entre and not self._peut_entrer(vehicule):
            cible = passage[0]
        if vehicule.arret_intervention is not None and not vehicule.intervention_effectuee:
            cible = min(cible, vehicule.arret_intervention)
        if cible > ancien and not self._trajet_libre(vehicule, cible):
            borne_basse, borne_haute = ancien, cible
            if not self._trajet_libre(vehicule, ancien + min(.05, cible - ancien)):
                borne_haute = ancien
            for _ in range(8 if borne_haute > ancien else 0):
                milieu = (borne_basse + borne_haute) / 2
                if self._trajet_libre(vehicule, milieu):
                    borne_basse = milieu
                else:
                    borne_haute = milieu
            cible = borne_basse
        if cible > ancien + 1e-7 and self._trajet_libre(vehicule, cible):
            vehicule.distance = cible
            if vehicule.debut_manoeuvre is not None:
                vehicule.decalage_lateral, _ = vehicule.decalage_lateral_a(cible)
                if cible >= vehicule.debut_manoeuvre + vehicule.longueur_manoeuvre - 1e-7:
                    vehicule.decalage_lateral = vehicule.decalage_cible
                    vehicule.debut_manoeuvre = None
            vehicule.vitesse_actuelle = (cible - ancien) / PAS_TEMPS
            if entre and cible > passage[0]:
                self.vehicules_engages.add(vehicule.identifiant)
        if (vehicule.debut_manoeuvre is not None and vehicule.distance >=
                vehicule.debut_manoeuvre + vehicule.longueur_manoeuvre - 1e-6):
            vehicule.distance = vehicule.debut_manoeuvre + vehicule.longueur_manoeuvre
            vehicule.decalage_lateral = vehicule.decalage_cible
            vehicule.debut_manoeuvre = None
        vehicule.en_attente = vehicule.distance <= ancien + 1e-9
        if (vehicule.type_vehicule == "car" and vehicule.cede_aux and voiture_rangee(vehicule)
                and not self._degage_file_acces(vehicule)):
            vehicule.en_attente = True
            vehicule.vitesse_actuelle = 0.0
        if passage and vehicule.distance >= passage[1]:
            self.vehicules_engages.discard(vehicule.identifiant)
            vehicule.indice_passage += 1
            vehicule.date_demande = None
        if vehicule.arret_intervention is not None and not vehicule.intervention_effectuee and vehicule.distance >= vehicule.arret_intervention - 1e-6:
            vehicule.distance = vehicule.arret_intervention
            vehicule.intervention_effectuee = True
            vehicule.temps_intervention_restant = DUREE_INTERVENTION
        if vehicule.type_vehicule != "car" and vehicule.distance >= vehicule.trajet.longueur - 1e-6:
            vehicule.occupe = False
            vehicule.distance = 0.0
            vehicule.decalage_lateral = 0.0
            vehicule.debut_manoeuvre = None
            vehicule.en_attente = False
            self.trajets_termines += 1
            self.evenements.append((vehicule.identifiant, "disponible"))

    def _limiter_aux_raccordements(self, vehicule, ancien, cible):
        """Aux raccordements sans feux, reserver un passage puis le liberer."""
        for arret, fin, cle in vehicule.trajet.raccordements:
            if ancien <= arret < cible:
                if not self._raccordement_libre(vehicule, arret, fin, cle):
                    cible = arret
        return cible

    def _raccordement_libre(self, vehicule, arret, fin, cle):
        priorite = self._priorite_raccordement(cle)
        if priorite and priorite[0] is not vehicule:
            secours, arret_secours = priorite
            # Une voiture sur la voie devant le secours doit d'abord degager,
            # sinon le secours resterait bloque derriere sa propre priorite.
            if not self._bloque_approche(vehicule, secours, arret_secours):
                return False
        suivants = set()
        for autre in self.vehicules:
            if autre is vehicule or (autre.type_vehicule != "car" and not autre.occupe):
                continue
            for arret_autre, fin_autre, cle_autre in autre.trajet.raccordements:
                if cle != cle_autre:
                    continue
                if self.raccordements_compatibles(vehicule, arret, cle, autre, arret_autre):
                    # La file peut avancer dans la zone jusqu'au vrai feu,
        # meme si sa tete de file y attend. DISTANCE_SECURITE reste controlee a chaque pas.
                    if autre.distance >= arret_autre:
                        suivants.add(autre.identifiant)
                elif self._suit_sortie(vehicule, fin, autre, fin_autre):
                    suivants.add(autre.identifiant)
                elif arret_autre < autre.distance < fin_autre:
                    if cle == "parking" and self._mouvements_opposes_caserne(vehicule, autre):
                        # Le secours sortant peut attendre a F sans retenir toute
                        # l'allee du retour. Le balayage controle les gabarits.
                        continue
                    if self._conflit_raccordement_restant(
                            vehicule, arret, fin, cle, autre, arret_autre, fin_autre):
                        return False
        # Le garage ne reserve que son allee : l'insertion est controlee a F.
        # Sinon une file deja en train de degager F immobilise encore le secours
        # sur sa place, alors que son trajet jusqu'a la ligne d'insertion est libre.
        fin_balaye, marge = fin, (1 if vehicule.type_vehicule != "car" else 46)
        if cle == "parking" and arret == 0:
            fin_balaye = next(debut for debut, _, nom in vehicule.trajet.raccordements if nom == "F")
            marge = 1
        # Controler aussi la sortie avant d'engager le vehicule.
        for decalage in range(0, int(fin_balaye - arret) + marge, 6):
            if not self._trajet_libre(vehicule, arret + decalage, suivants):
                return False
        return True

    def _conflit_raccordement_restant(self, vehicule, arret, fin, cle, autre, arret_autre, fin_autre):
        """Liberer un passage des que l'autre a depasse le dernier point de conflit."""
        mouvement_premier = vehicule.trajet.mouvements_raccordements.get((arret, cle))
        mouvement_autre = autre.trajet.mouvements_raccordements.get((arret_autre, cle))
        if mouvement_premier is None or mouvement_autre is None:
            return True  # Les aires et le stationnement restent exclusifs.
        # Inclure la fin du balayage : au retour F, les deux places divergent
        # juste apres le raccordement, meme si leur mouvement est identique.
        def etat_manoeuvre(element, debut):
            return ((element.debut_manoeuvre - debut, element.decalage_initial,
                     element.decalage_cible, element.longueur_manoeuvre)
                    if element.debut_manoeuvre is not None else (None, element.decalage_lateral))

        ajuste = (vehicule.debut_manoeuvre is not None or autre.debut_manoeuvre is not None
                    or vehicule.decalage_lateral != 0 or autre.decalage_lateral != 0)
        cle_cache = (cle, mouvement_premier, mouvement_autre, vehicule.type_vehicule, autre.type_vehicule,
                     vehicule.trajet.position_a(fin + 46)[:2],
                     etat_manoeuvre(vehicule, arret), etat_manoeuvre(autre, arret_autre))
        if cle_cache not in self.conflits_raccordements:
            # Les memes mouvements au meme raccordement ont la meme geometrie.
            # Calculer une seule fois ou l'autre vehicule finit de nous couper
            # la route ; ajouter une marge pour l'echantillonnage de 3 unites.
            chemin = [vehicule.position_a(arret + decalage)
                    for decalage in range(0, int(fin - arret) + 47, 3)]
            dernier_conflit = -inf
            decalages = list(range(0, int(fin_autre - arret_autre) + 1, 3))
            decalages.append(fin_autre - arret_autre)
            for decalage in decalages:
                position = autre.position_a(arret_autre + decalage)
                if any(hypot(position[0] - point[0], position[1] - point[1]) < DISTANCE_SECURITE + 3
                       and (not ajuste or not carrosseries_separees(vehicule, point, autre, position))
                       for point in chemin):
                    dernier_conflit = decalage + 3
            self.conflits_raccordements[cle_cache] = dernier_conflit
        return autre.distance - arret_autre <= self.conflits_raccordements[cle_cache]

    def raccordements_compatibles(self, premier, arret, cle, second, arret_autre):
        """Partager une meme voie locale ou deux voies tout droit opposees."""
        if premier.type_vehicule != "car" or second.type_vehicule != "car":
            return False
        mouvement_premier = premier.trajet.mouvements_raccordements.get((arret, cle))
        mouvement_second = second.trajet.mouvements_raccordements.get((arret_autre, cle))
        if mouvement_premier is None or mouvement_second is None:
            return False
        entree_direction, sortie_direction = mouvement_premier
        entree_autre, sortie_autre = mouvement_second
        return (mouvement_premier == mouvement_second
                or (entree_direction == sortie_direction and entree_autre == sortie_autre
                    and entree_direction == (-entree_autre[0], -entree_autre[1])))

    def _priorite_raccordement(self, cle):
        """Priorite tant que le secours est occupe, aller ET retour compris."""
        candidats = []
        for secours in self.secours:
            if not secours.occupe:
                continue
            for arret, fin, cle_autre in secours.trajet.raccordements:
                depart_caserne = cle == "F" and self._quitte_caserne(secours)
                if (cle_autre == cle and secours.distance < fin
                        and (arret - secours.distance <= ANTICIPATION_RACCORDEMENT or depart_caserne)):
                    candidats.append((secours, arret))
                    break
        if not candidats:
            return None
        if cle == "F":
            for sortie_direction, arret_sortie in candidats:
                if not self._quitte_caserne(sortie_direction):
                    continue
                for en_retour, arret_retour in candidats:
                    if (en_retour is sortie_direction or not self._revient_caserne(en_retour)
                            or en_retour.distance > arret_retour):
                        continue
                    # Un depart deja dans l'allee peut barrer la fin du retour.
                    # Le laisser sortir evite que chacun attende l'autre a F.
                    fin_parking = en_retour.trajet.longueur
                    if any(not carrosseries_separees(en_retour, en_retour.position_a(distance),
                                            sortie_direction, sortie_direction.position)
                           for distance in range(int(arret_retour), int(fin_parking) + 1, 6)):
                        return sortie_direction, arret_sortie
        return min(candidats, key=lambda element: (element[0].debut_mission, element[0].identifiant))

    def _bloque_approche(self, vehicule, secours, arret):
        """Autoriser les vehicules devant le secours a liberer sa voie d'arrivee."""
        x, y, _ = vehicule.position
        distance = secours.distance
        while distance <= arret + 1e-9:
            rx, ry, _ = secours.trajet.position_a(distance)
            if hypot(x - rx, y - ry) < DISTANCE_SECURITE:
                return True
            distance += 6
        rx, ry, _ = secours.trajet.position_a(arret)
        return hypot(x - rx, y - ry) < DISTANCE_SECURITE

    def etat_simulation(self):
        etats = []
        for vehicule in self.vehicules:
            x, y, orientation = vehicule.position
            etape = "A l'arret" if vehicule.en_attente else "En circulation"
            if vehicule.type_vehicule == "car" and vehicule.cede_aux:
                etape = "Range sur le cote - priorite secours " + ", ".join(vehicule.cede_aux)
            elif vehicule.type_vehicule == "car" and vehicule.decalage_lateral > 1e-6:
                etape = "Reprise apres le passage du secours"
            if vehicule.type_vehicule != "car":
                if not vehicule.occupe:
                    etape = "A la caserne"
                elif vehicule.temps_intervention_restant > 0:
                    etape = "Intervention - " + DESTINATIONS[vehicule.destination]
                elif vehicule.intervention_effectuee:
                    etape = "Retour a la caserne"
                else:
                    etape = "Vers le point " + DESTINATIONS[vehicule.destination]
            etats.append(EtatVehicule(vehicule.identifiant, vehicule.type_vehicule, vehicule.couleur,
                                       vehicule.trajet, x, y, orientation, vehicule.en_attente,
                                       vehicule.occupe, vehicule.distance / vehicule.trajet.longueur, etape))
        return EtatSimulation(tuple(etats), self.feux.signal("NS"), self.feux.signal("EW"),
                     self.feux.description, self.feux.temps_restant, self.trajets_termines)
