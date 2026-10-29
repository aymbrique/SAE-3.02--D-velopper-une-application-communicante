"""Batiments et petits parkings dessines avec les formes de QGraphicsScene."""

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPen, QPolygonF

from src.modeles.plan import POINTS_INTERVENTION, NOEUDS, DEMI_LARGEUR_ROUTE, ENTREES_SITES


def rectangle(scene, x, y, largeur, hauteur, couleur):
    return scene.addRect(x, y, largeur, hauteur, QPen(Qt.PenStyle.NoPen),
                         QBrush(QColor(couleur)))


def polygone(scene, points, couleur):
    return scene.addPolygon(QPolygonF([QPointF(x, y) for x, y in points]),
                            QPen(Qt.PenStyle.NoPen), QBrush(QColor(couleur)))


def etiquette(scene, valeur, x, y, largeur, taille=13, couleur="#26343b"):
    police = QFont()
    police.setPixelSize(taille)
    police.setBold(True)
    element = scene.addSimpleText(valeur, police)
    element.setBrush(QBrush(QColor(couleur)))
    element.setPos(x + (largeur - element.boundingRect().width()) / 2, y)
    return element


def dessiner_mairie(scene, x, y):
    rectangle(scene, x, y, 150, 100, "#eee2c9")
    polygone(scene, [(x, y), (x + 75, y - 30), (x + 150, y)], "#946752")
    etiquette(scene, "MAIRIE", x, y + 9, 150, 15)
    for dx in (18, 102):
        rectangle(scene, x + dx, y + 36, 30, 30, "#91b6c5")
        rectangle(scene, x + dx + 14, y + 36, 2, 30, "#f8f3e9")
    for dx in (8, 52, 88, 132):
        rectangle(scene, x + dx, y + 32, 10, 62, "#fff6e4")
    rectangle(scene, x + 63, y + 57, 24, 43, "#705b4c")
    rectangle(scene, x + 65, y - 18, 7, 12, "#2454a6")
    rectangle(scene, x + 72, y - 18, 7, 12, "white")
    rectangle(scene, x + 79, y - 18, 7, 12, "#d54b43")


def dessiner_restaurant(scene, x, y):
    rectangle(scene, x, y, 150, 100, "#f0d5b3")
    polygone(scene, [(x, y), (x + 16, y - 22),
                    (x + 134, y - 22), (x + 150, y)], "#b66045")
    etiquette(scene, "RESTAURANT", x, y + 9, 150)
    rectangle(scene, x + 14, y + 50, 76, 38, "#a2c5c8")
    rectangle(scene, x + 102, y + 50, 32, 50, "#775948")
    rectangle(scene, x + 108, y + 56, 20, 26, "#a2c5c8")
    for index in range(10):
        couleur = "#b7493e" if index % 2 == 0 else "#fff3df"
        rectangle(scene, x + 10 + index * 13, y + 32, 13, 20, couleur)


def dessiner_supermarche(scene, x, y):
    rectangle(scene, x, y, 220, 108, "#eee9de")
    rectangle(scene, x, y, 220, 10, "#566a7c")
    rectangle(scene, x + 12, y + 18, 196, 30, "#245c9e")
    rectangle(scene, x + 18, y + 24, 8, 18, "#ef9d38")
    etiquette(scene, "E.Leclerc", x + 30, y + 23, 170, 20, "white")
    for dx in (16, 62, 156):
        rectangle(scene, x + dx, y + 62, 38, 32, "#9fc4d2")
    rectangle(scene, x + 110, y + 60, 32, 48, "#496578")
    rectangle(scene, x + 114, y + 64, 24, 40, "#a9d0dd")
    rectangle(scene, x + 125, y + 64, 2, 40, "#496578")


def dessiner_iut(scene, x, y):
    rectangle(scene, x, y, 220, 108, "#e3e2d8")
    rectangle(scene, x, y, 220, 8, "#456477")
    rectangle(scene, x + 12, y + 16, 196, 28, "#397a87")
    etiquette(scene, "IUT de Colmar", x + 12, y + 21, 196, 17, "white")
    for dx in (16, 56, 136, 176):
        rectangle(scene, x + dx, y + 54, 28, 18, "#8fb4c9")
        rectangle(scene, x + dx, y + 80, 28, 18, "#8fb4c9")
    rectangle(scene, x + 96, y + 54, 28, 54, "#456477")
    rectangle(scene, x + 101, y + 60, 18, 43, "#aecdd5")


def dessiner_sites_intervention(scene):
    """Garder l'acces des secours libre entre chaque parking et la route."""
    batiments = {"W": dessiner_mairie, "S": dessiner_restaurant,
                 "E": dessiner_supermarche, "N": dessiner_iut}
    numeros = {"W": 1, "S": 2, "N": 3, "E": 4}
    for cote, entree in ENTREES_SITES.items():
        x, y = POINTS_INTERVENTION[cote]
        bord_route = NOEUDS[entree][1] - DEMI_LARGEUR_ROUTE
        # Le parking entoure le demi-tour existant ; l'allee rejoint le bord
        # de la chaussee. Aucun decor ne coupe le trajet aller ou retour.
        rectangle(scene, x - 56, y - 24, 112, 88, "lightgray")
        rectangle(scene, x - 48, y + 64, 96, bord_route - y - 64, "lightgray")
        scene.addRect(x - 24, y - 15, 48, 30,
                      QPen(QColor("white"), 2), QBrush(QColor("#ffe091")))
        etiquette(scene, "P", x - 15, y + 34, 30, 18, "#526a80")
        etiquette(scene, f"Point {numeros[cote]}", x - 56, y - 45, 112, 12)

        # A l'ouest, le batiment est a droite du parking. A l'est, il est
        # a gauche : les quatre emplacements restent hors des routes.
        if cote in ("W", "S"):
            batiments[cote](scene, x + 56, y - 30)
        else:
            batiments[cote](scene, x - 56 - 220, y - 28)
