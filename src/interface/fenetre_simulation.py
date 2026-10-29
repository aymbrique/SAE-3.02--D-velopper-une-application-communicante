"""Fenetre standard Qt : commandes, carte et trois onglets d'informations."""

from math import ceil
from PyQt6.QtCore import QElapsedTimer, QTimer
from PyQt6.QtWidgets import (
    QComboBox, QFormLayout, QHBoxLayout, QLabel, QMainWindow,
    QProgressBar, QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from src.interface.carte import VueCarte
from src.modeles.plan import DESTINATIONS
from src.simulation.moteur import Simulation


class FenetreSimulation(QMainWindow):
    def __init__(self, client=None):
        super().__init__()
        self.setWindowTitle("SAE302 - Simulation")
        self.resize(1100, 720)
        self.scenario = Simulation()
        self.client = client
        self.temps_ecoule = 0.0
        self.en_cours = False
        self.vitesse = 2.0
        self._construire_interface()

        # Qt appelle _actualiser_simulation regulierement. Le moteur calcule les deplacements.
        self.horloge = QElapsedTimer()
        self.horloge.start()
        self.minuteur = QTimer(self)
        self.minuteur.setInterval(30)
        self.minuteur.timeout.connect(self._actualiser_simulation)
        self.minuteur.start()
        self.actualiser()

    def _construire_interface(self):
        page = QWidget()
        self.setCentralWidget(page)
        disposition = QVBoxLayout(page)
        self._construire_commandes(disposition)

        contenu = QHBoxLayout()
        self.vue = VueCarte()
        contenu.addWidget(self.vue, 1)
        onglets = QTabWidget()
        onglets.setMinimumWidth(300)
        onglets.setMaximumWidth(360)
        onglets.addTab(self._construire_onglet_trafic(), "Trafic")
        onglets.addTab(self._construire_onglet_secours(), "Secours")
        onglets.addTab(self._construire_onglet_reseau(), "Reseau")
        contenu.addWidget(onglets)
        disposition.addLayout(contenu, 1)
        disposition.addWidget(QLabel("Voiture : bleu | Pompier 01 : rouge | Ambulance 02 : blanc"))
        self.pied_fenetre = QLabel()
        disposition.addWidget(self.pied_fenetre)

    def _construire_commandes(self, disposition):
        ligne = QHBoxLayout()
        self.bouton_demarrer = QPushButton("Demarrer")
        self.bouton_demarrer.clicked.connect(self.basculer_pause)
        ligne.addWidget(self.bouton_demarrer)
        self.bouton_recommencer = QPushButton("Recommencer")
        self.bouton_recommencer.clicked.connect(self.recommencer)
        ligne.addWidget(self.bouton_recommencer)
        ligne.addWidget(QLabel("Vitesse"))
        self.choix_vitesse = QComboBox()
        for etiquette, vitesse in (("x0.5", 0.5), ("x1", 2.0), ("x2", 3.0)):
            self.choix_vitesse.addItem(etiquette, vitesse)
        self.choix_vitesse.setCurrentIndex(1)
        self.choix_vitesse.currentIndexChanged.connect(self._changer_vitesse)
        ligne.addWidget(self.choix_vitesse)
        ligne.addWidget(QLabel("Voitures / minute"))
        self.choix_debit = QSpinBox()
        self.choix_debit.setRange(0, 25)
        self.choix_debit.setValue(self.scenario.debit)
        self.choix_debit.valueChanged.connect(self._changer_debit)
        ligne.addWidget(self.choix_debit)
        ligne.addStretch()
        self.etiquette_horloge = QLabel("00:00")
        ligne.addWidget(self.etiquette_horloge)
        disposition.addLayout(ligne)

        missions = QHBoxLayout()
        missions.addWidget(QLabel("Vehicule"))
        self.choix_secours = QComboBox()
        self.choix_secours.addItem("01 - Pompiers", "01")
        self.choix_secours.addItem("02 - Ambulance", "02")
        missions.addWidget(self.choix_secours)
        missions.addWidget(QLabel("Intervention"))
        self.choix_destination = QComboBox()
        for cote, nom in DESTINATIONS.items():
            self.choix_destination.addItem(nom, cote)
        self.choix_destination.setCurrentIndex(self.choix_destination.findData("S"))
        missions.addWidget(self.choix_destination)
        self.bouton_envoi = QPushButton("Envoyer en intervention")
        self.bouton_envoi.clicked.connect(self._envoyer_selection)
        missions.addWidget(self.bouton_envoi)
        self.choix_secours.currentIndexChanged.connect(self._actualiser_bouton_envoi)
        missions.addStretch()
        disposition.addLayout(missions)

    def _construire_onglet_trafic(self):
        page = QWidget()
        formulaire = QFormLayout(page)
        self.nombre_voitures = QLabel()
        self.nombre_attentes = QLabel()
        self.nombre_trajets_termines = QLabel()
        formulaire.addRow("Voitures presentes", self.nombre_voitures)
        formulaire.addRow("Voitures en attente", self.nombre_attentes)
        formulaire.addRow("Trajets termines", self.nombre_trajets_termines)
        self.etiquettes_feux = {}
        for axe in ("Nord-Sud", "Est-Ouest"):
            self.etiquettes_feux[axe] = QLabel()
            formulaire.addRow(axe, self.etiquettes_feux[axe])
        self.etiquette_phase = QLabel()
        self.etiquette_phase.setWordWrap(True)
        formulaire.addRow(self.etiquette_phase)
        formulaire.addRow(QLabel("Temps d'accumulation"))
        self.etiquettes_reserves = {}
        for axe, nom in (("EW", "Ligne horizontale"), ("NS", "Ligne verticale")):
            self.etiquettes_reserves[axe] = QLabel()
            formulaire.addRow(nom, self.etiquettes_reserves[axe])
        explication = QLabel("Au-dela de 8 s de vert prioritaire, les secondes sont "
                             "stockees pour l'autre ligne. Les deux reserves se "
                             "compensent ; un quart du solde prolonge chaque "
                             "prochain vert de la ligne concernee, hors priorite.")
        explication.setWordWrap(True)
        formulaire.addRow(explication)
        return page

    def _construire_onglet_secours(self):
        page = QWidget()
        disposition = QVBoxLayout(page)
        self.widgets_secours = {}
        self.etiquettes_estimations = {}
        for identifiant in ("01", "02"):
            disposition.addWidget(QLabel("Secours " + identifiant))
            statut = QLabel()
            etape = QLabel()
            progression = QProgressBar()
            progression.setRange(0, 100)
            estimations = QLabel()
            estimations.setWordWrap(True)
            disposition.addWidget(statut)
            disposition.addWidget(etape)
            disposition.addWidget(progression)
            disposition.addWidget(estimations)
            self.widgets_secours[identifiant] = (statut, etape, progression)
            self.etiquettes_estimations[identifiant] = estimations
        disposition.addStretch()
        return page

    def _construire_onglet_reseau(self):
        page = QWidget()
        disposition = QVBoxLayout(page)
        self.etiquette_reseau = QLabel()
        self.etiquette_reseau.setWordWrap(True)
        disposition.addWidget(self.etiquette_reseau)
        disposition.addStretch()
        return page

    def _envoyer_selection(self):
        self.demarrer_mission(self.choix_secours.currentData(), self.choix_destination.currentData())

    def _actualiser_bouton_envoi(self):
        secours = self.scenario.obtenir_secours(self.choix_secours.currentData())
        self.bouton_envoi.setEnabled(not secours.occupe)
        self.choix_destination.setEnabled(not secours.occupe)
        if secours.occupe:
            self.choix_destination.setCurrentIndex(self.choix_destination.findData(secours.destination))
            self.bouton_envoi.setText("Ce secours est deja en mission")
        else:
            self.bouton_envoi.setText("Envoyer en intervention")

    def _changer_vitesse(self):
        self.regler_vitesse(self.choix_vitesse.currentData())

    def regler_vitesse(self, valeur):
        self.vitesse = valeur
        self.horloge.restart()

    def _changer_debit(self, valeur):
        self.scenario.debit = valeur

    def basculer_pause(self):
        self.en_cours = not self.en_cours
        self.horloge.restart()
        self.actualiser()

    def recommencer(self):
        self.scenario = Simulation(debit=self.choix_debit.value())
        if self.client:
            self.client.publier("01", "disponible")
            self.client.publier("02", "disponible")
        self.temps_ecoule = 0
        self.en_cours = False
        self.horloge.restart()
        self.actualiser()

    def _actualiser_simulation(self):
        # Temps reel depuis le dernier appel, limite en cas de fenetre bloquee.
        dt = min(self.horloge.restart() / 1000, 0.1)
        if self.en_cours:
            self.scenario.limites_circulation = self.vue.limites_circulation()
            self.scenario.avancer(dt * self.vitesse)
            self.temps_ecoule = self.scenario.temps
        self._publier_evenements()
        self.actualiser()

    def demarrer_mission(self, identifiant, destination="S"):
        self.scenario.demarrer_mission(identifiant, destination)
        self._publier_evenements()
        self.actualiser()

    def _publier_evenements(self):
        for identifiant, etat in self.scenario.recuperer_evenements():
            if self.client:
                self.client.publier(identifiant, etat)

    def actualiser(self):
        etat_simulation = self.scenario.etat_simulation()
        self.vue.actualiser(etat_simulation)
        secondes = int(self.temps_ecoule)
        self.etiquette_horloge.setText(f"{secondes // 60:02d}:{secondes % 60:02d}")
        self.nombre_voitures.setText(str(len(etat_simulation.voitures)))
        en_attente = 0
        for voiture in etat_simulation.voitures:
            if voiture.en_attente:
                en_attente += 1
        self.nombre_attentes.setText(str(en_attente))
        self.nombre_trajets_termines.setText(str(etat_simulation.trajets_termines))
        noms = {"red": "Rouge", "amber": "Orange", "green": "Vert"}
        self.etiquettes_feux["Nord-Sud"].setText(noms[etat_simulation.nord_sud])
        self.etiquettes_feux["Est-Ouest"].setText(noms[etat_simulation.est_ouest])
        if etat_simulation.temps_phase_restant > 0:
            temps_restant = f"{ceil(etat_simulation.temps_phase_restant)} s de cycle restantes"
        else:
            temps_restant = "Passage en cours"
        self.etiquette_phase.setText(f"{etat_simulation.nom_phase}\n{temps_restant}")
        reserve_temps = self.scenario.feux.reserve_temps
        for axe, etiquette in self.etiquettes_reserves.items():
            etiquette.setText(f"{reserve_temps[axe]:.1f} s stockees")
        self._actualiser_bouton_envoi()
        for secours in etat_simulation.secours:
            self._actualiser_secours(secours)
        if self.en_cours:
            self.bouton_demarrer.setText("Mettre en pause")
            self.pied_fenetre.setText("Simulation en cours")
        elif self.temps_ecoule > 0:
            self.bouton_demarrer.setText("Reprendre")
            self.pied_fenetre.setText("Simulation en pause")
        else:
            self.bouton_demarrer.setText("Demarrer")
            self.pied_fenetre.setText("Pret a demarrer")
        if self.client:
            statut, en_attente_envoi = self.client.instantane()
            self.etiquette_reseau.setText(f"{statut}\n{self.client.hote}:{self.client.port}\nMises a jour en attente : {en_attente_envoi}")
        else:
            self.etiquette_reseau.setText("Mode local : centre non connecte")

    def _actualiser_secours(self, secours):
        statut, etape, progression = self.widgets_secours[secours.identifiant]
        if secours.occupe:
            statut.setText("Occupe")
        else:
            statut.setText("Disponible")
        etape.setText(secours.etape)
        progression.setValue(round(secours.progression * 100))
        modele = self.scenario.obtenir_secours(secours.identifiant)
        if not modele.occupe:
            texte = f"Duree prevue hors attentes : {modele.duree_estimee:.0f} s"
        else:
            distance, delai_arrivee = self.scenario.approche(modele)
            texte = "Carrefour franchi"
            if distance is not None:
                texte = f"Carrefour : {distance:.0f} m / {delai_arrivee:.1f} s"
            temps_restant = (modele.trajet.longueur - modele.distance) / modele.vitesse
            if modele.intervention_effectuee:
                temps_restant += modele.temps_intervention_restant
            else:
                temps_restant += 8
            texte += f"\nMission : {self.temps_ecoule - modele.debut_mission:.0f} s ecoulees"
            texte += f"\nHors attentes : {temps_restant:.0f} s restantes"
            texte += f"\nPrevision au depart : {modele.duree_estimee:.0f} s"
        self.etiquettes_estimations[secours.identifiant].setText(texte)

    def closeEvent(self, evenement):
        self.minuteur.stop()
        if self.client:
            self.client.fermer()
        super().closeEvent(evenement)
