"""Carte simple : rectangles pour les routes et vehicules, ronds pour les feux."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QPen
from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsScene, QGraphicsView

from src.interface.batiments import dessiner_sites_intervention
from src.interface.signalisation import dessiner_travaux, dessiner_panneaux_priorite
from src.modeles.plan import (CX, CY, DECALAGE_VOIE, DEMI_LARGEUR_ROUTE, HAUTEUR_SCENE, LARGEUR_SCENE,
                               NOEUDS, TRONCONS_ROUTES, PARKING_Y)


COULEURS_FEUX = {"rouge": "#ff0000", "orange": "#ffa500", "vert": "#008000"}


class DessinVehicule(QGraphicsRectItem):
    """Rectangle représentant une voiture ou un véhicule de secours."""

    def __init__(self, etat):
        """Crée le dessin à partir de l'état du véhicule."""
        super().__init__()
        self.setZValue(20)
        self.actualiser_etat(etat)

    def actualiser_etat(self, etat):
        """Met à jour la taille, la couleur, la position et l'orientation du dessin."""
        if etat.type_vehicule == "voiture":
            self.setRect(-14, -7.5, 28, 15)
            couleur = "#0000ff"
        else:
            self.setRect(-18, -9, 36, 18)
            if etat.type_vehicule == "pompiers":
                couleur = "#ff0000"
            else:
                couleur = "#ffffff"
        self.setBrush(QBrush(QColor(couleur)))
        self.setPen(QPen(QColor("#000000")))
        self.setPos(etat.x, etat.y)
        self.setRotation(etat.orientation)


class VueCarte(QGraphicsView):
    """Vue graphique du plan, des feux et des véhicules."""

    def __init__(self, parent=None):
        """Prépare la scène et dessine les éléments fixes du plan."""
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setSceneRect(0, 0, LARGEUR_SCENE, HAUTEUR_SCENE)
        self.setBackgroundBrush(QColor("#a8cf8a"))
        self.setMinimumSize(420, 340)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setInteractive(False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.dessins_vehicules = {}
        self.feux = {}
        self._dessiner_carte()

    def rectangle(self, x, y, largeur, hauteur, couleur):
        """Ajoute à la carte un rectangle coloré sans bordure et le renvoie."""
        return self.scene().addRect(x, y, largeur, hauteur,
                                   QPen(Qt.PenStyle.NoPen), QBrush(QColor(couleur)))

    def ecrire_texte(self, texte, x, y):
        """Place un texte sur la carte et renvoie l'élément créé."""
        element = self.scene().addSimpleText(texte)
        element.setPos(x, y)
        return element

    def _dessiner_carte(self):
        """Dessine les routes, la caserne, les bâtiments, les panneaux et les feux."""
        # Dessiner le reseau du croquis avec le style de la simulation existante.
        crayon_route = QPen(QColor("#808080"), 2 * DEMI_LARGEUR_ROUTE)
        crayon_route.setCapStyle(Qt.PenCapStyle.FlatCap)
        marquage = QPen(QColor("#ffffff"), 2, Qt.PenStyle.DashLine)
        routes = []
        for premier, second in TRONCONS_ROUTES:
            # Continuer aussi dans les marges visibles lorsque la fenetre n'a
            # pas les proportions du plan. Les trajets restent dans la scene.
            points = []
            for cle in (premier, second):
                x, y = NOEUDS[cle]
                if x == 0:
                    x -= LARGEUR_SCENE
                elif x == LARGEUR_SCENE:
                    x += LARGEUR_SCENE
                if y == 0:
                    y -= HAUTEUR_SCENE
                points.append((x, y))
            (x1, y1), (x2, y2) = points
            if (premier, second) == ("R", "Q"):
                # Une seule voie descendante : la moitie droite reste en herbe.
                self.rectangle(x1 - DEMI_LARGEUR_ROUTE, y1, DEMI_LARGEUR_ROUTE, y2 - y1, "#808080")
                continue
            routes.append((x1, y1, x2, y2))
            self.scene().addLine(x1, y1, x2, y2, crayon_route)
        for x1, y1, x2, y2 in routes:
            self.scene().addLine(x1, y1, x2, y2, marquage)
        # Enlever les pointilles au milieu des raccordements.
        for cle in ("C", "F", "O", "B", "R", "E", "D", "L", "Q", "U", "H"):
            x, y = NOEUDS[cle]
            self.rectangle(x - DEMI_LARGEUR_ROUTE, y - DEMI_LARGEUR_ROUTE,
                           2 * DEMI_LARGEUR_ROUTE, 2 * DEMI_LARGEUR_ROUTE, "#808080")

        # Ce raccordement ne se prend que vers le bas, depuis la gauche de R.
        x = NOEUDS["R"][0] - DECALAGE_VOIE
        y = (NOEUDS["R"][1] + NOEUDS["Q"][1]) / 2
        fleche = QPen(QColor("#ffffff"), 3)
        for x1, y1, x2, y2 in ((x, y - 24, x, y + 24),
                               (x - 9, y + 12, x, y + 24),
                               (x + 9, y + 12, x, y + 24)):
            self.scene().addLine(x1, y1, x2, y2, fleche)
        dessiner_travaux(self.scene())

        # Caserne et allee d'acces, a gauche de l'axe vertical principal.
        self.rectangle(190, 80, 180, 190, "#d3d3d3")
        self.rectangle(340, 130, CX - DEMI_LARGEUR_ROUTE - 340, 140, "#d3d3d3")
        self.ecrire_texte("CASERNE", 225, 55)
        for identifiant, y in PARKING_Y.items():
            self.ecrire_texte("Place " + identifiant, 197, y - 9)

        dessiner_sites_intervention(self.scene())
        dessiner_panneaux_priorite(self.scene())

        # Un seul carrefour a feux, a l'emplacement de la croix verte du croquis.
        arret = QPen(QColor("#ffffff"), 4)
        self.scene().addLine(CX - 82, CY + 8, CX - 82, CY + DEMI_LARGEUR_ROUTE - 8, arret)
        self.scene().addLine(CX + 8, CY + 82, CX + DEMI_LARGEUR_ROUTE - 8, CY + 82, arret)
        self.scene().addLine(CX + 82, CY - DEMI_LARGEUR_ROUTE + 8, CX + 82, CY - 8, arret)
        self.scene().addLine(CX - DEMI_LARGEUR_ROUTE + 8, CY - 82, CX - 8, CY - 82, arret)
        positions = {"N": (CX - 100, CY - 105), "S": (CX + 90, CY + 90),
                     "E": (CX + 90, CY - 105), "O": (CX - 100, CY + 90)}
        for origine, (x, y) in positions.items():
            self.feux[origine] = self.scene().addEllipse(
                x, y, 20, 20, QPen(QColor("#000000")), QBrush(QColor("#ff0000")))
        self.ecrire_texte("NORD", CX - 20, 5)
        self.ecrire_texte("OUEST", 25, CY - 58)
        self.ecrire_texte("EST", 1510, CY + 40)

    def actualiser(self, etat_simulation):
        """Affiche les véhicules et les feux à partir de l'état de la simulation."""
        # Enlever les voitures qui ont fini leur trajet.
        identifiants = []
        for vehicule in etat_simulation.vehicules:
            identifiants.append(vehicule.identifiant)
        for identifiant in list(self.dessins_vehicules):
            if identifiant not in identifiants:
                element = self.dessins_vehicules.pop(identifiant)
                self.scene().removeItem(element)

        # Creer les nouveaux rectangles, puis mettre toutes les positions a jour.
        for etat in etat_simulation.vehicules:
            if etat.identifiant not in self.dessins_vehicules:
                element = DessinVehicule(etat)
                self.dessins_vehicules[etat.identifiant] = element
                self.scene().addItem(element)
            self.dessins_vehicules[etat.identifiant].actualiser_etat(etat)

        for origine, feu in self.feux.items():
            if origine in ("N", "S"):
                signal = etat_simulation.nord_sud
            else:
                signal = etat_simulation.est_ouest
            feu.setBrush(QBrush(QColor(COULEURS_FEUX[signal])))

    def cadrer_plan(self):
        """Adapte le plan à la fenêtre en conservant ses proportions."""
        self.resetTransform()
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def limites_circulation(self):
        """Renvoie les limites visibles du plan, marges comprises."""
        visible = self.mapToScene(self.viewport().rect()).boundingRect()
        return (min(0, visible.left()), min(0, visible.top()),
                max(LARGEUR_SCENE, visible.right()), max(HAUTEUR_SCENE, visible.bottom()))

    def resizeEvent(self, evenement):
        """Recadre le plan après un changement de taille de la fenêtre."""
        super().resizeEvent(evenement)
        self.cadrer_plan()

    def showEvent(self, evenement):
        """Recadre le plan lorsque la vue apparaît."""
        super().showEvent(evenement)
        self.cadrer_plan()

    def wheelEvent(self, evenement):
        """Ignore le zoom à la molette pour conserver le cadrage automatique."""
        # Garder le cadrage fixe, y compris avec la molette et le pavé tactile.
        evenement.accept()
