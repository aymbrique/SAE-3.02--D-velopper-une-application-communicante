"""Nouvelle maquette dessinee d'apres le croquis : affichage uniquement."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsView, QLabel, QVBoxLayout, QWidget


class MaquetteView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setSceneRect(0, 0, 730, 530)
        self.setBackgroundBrush(QColor("#dcebd0"))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumSize(500, 370)
        self.draw_map()

    def road(self, x1, y1, x2, y2, color="black"):
        pen = QPen(QColor(color), 6)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        self.scene().addLine(x1, y1, x2, y2, pen)

    def text(self, words, x, y, color="black", size=10):
        item = self.scene().addSimpleText(words, QFont("Sans Serif", size))
        item.setBrush(QBrush(QColor(color)))
        item.setPos(x, y)

    def building(self, x, y, width, height, color):
        self.scene().addRect(x, y, width, height,
                             QPen(QColor(color), 4), QBrush(QColor("white")))

    def traffic_light(self, x, y):
        # Symbole fixe : indique l'emplacement prevu, sans cycle de simulation.
        self.scene().addRect(x, y, 12, 32, QPen(QColor("black")), QBrush(QColor("black")))
        for index, color in enumerate(("red", "orange", "green")):
            self.scene().addEllipse(x + 3, y + 3 + index * 10, 6, 6,
                                    QPen(Qt.PenStyle.NoPen), QBrush(QColor(color)))

    def draw_map(self):
        # Traces noirs du croquis : axe principal, route basse et liaisons a droite.
        self.road(240, 25, 240, 92)
        self.road(210, 92, 240, 92)
        self.road(420, 275, 695, 275)
        self.road(435, 20, 435, 275)
        self.road(435, 118, 690, 118)
        self.road(590, 275, 590, 470)
        self.road(0, 470, 730, 470)

        # Croix verte : seul carrefour prevu avec des feux.
        self.road(50, 275, 420, 275, "#23ae4b")
        self.road(240, 92, 240, 470, "#23ae4b")
        for x, y in ((219, 232), (251, 285), (198, 285), (270, 232)):
            self.traffic_light(x, y)

        self.building(120, 37, 90, 90, "black")
        self.text("CASERNE", 131, 72, size=10)

        # Les quatre carres bleus conservent les positions du dessin fourni.
        points = [(14, 210, "Point 1"), (14, 410, "Point 2"),
                  (650, 70, "Point 3"), (658, 218, "Point 4")]
        for x, y, name in points:
            self.building(x, y, 40, 50, "#00a9e8")
            self.text(name, x - 2, y - 22, "#006d99", size=9)

        self.text("Vert : carrefour a feux", 20, 495, "#167433")
        self.text("Noir : routes et caserne", 260, 495)
        self.text("Bleu : interventions", 520, 495, "#006d99")

    def fit_scene(self):
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_scene()

    def showEvent(self, event):
        super().showEvent(event)
        self.fit_scene()


class MaquetteWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("SAE302 - Nouvelle maquette")
        self.resize(1020, 790)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Nouveau plan : carrefour, caserne et quatre points d'intervention"))
        self.view = MaquetteView()
        layout.addWidget(self.view, 1)
        note = QLabel("Maquette visuelle uniquement. Les deplacements seront adaptes a ces routes dans une prochaine etape.")
        note.setWordWrap(True)
        layout.addWidget(note)
