# Lire le projet

Commencer par `main.py`, puis suivre ces fichiers :

1. `src/interface/fenetre_simulation.py` : boutons, minuteur et affichage.
2. `src/simulation/moteur.py` : avancement du temps et des véhicules.
3. `src/modeles/vehicules.py` : les données d'une voiture ou d'un secours.
4. `src/modeles/plan.py` et `trajet.py` : routes et positions.
5. `src/simulation/priorite.py` : rangement et contrôle des carrosseries.
6. `src/simulation/feux.py` : priorité et compensation des deux axes.
7. `src/reseau/client.py`, `serveur.py` et `protocole.py` : échanges TCP.
8. `src/stockage/mariadb.py` : enregistrement des états.

Le `QTimer` de la fenêtre appelle le moteur dans le thread graphique.
Le client et le serveur TCP ont chacun leur thread réseau, dans des programmes
séparés. Les tests ne sont pas exécutés par l'application.

Les noms définis dans le projet sont en français, sans accents pour faciliter
leur saisie. Par exemple :

| Classe | Fichier | Rôle |
|---|---|---|
| `Vehicule` | `src/modeles/vehicules.py` | Données d'une voiture ou d'un secours. |
| `EtatVehicule`, `EtatSimulation` | `src/modeles/vehicules.py` | Données transmises au dessin. |
| `Trajet` | `src/modeles/trajet.py` | Positions et orientations sur un parcours. |
| `Feux`, `DemandePriorite` | `src/simulation/feux.py` | Cycle des feux et demandes des secours. |
| `FenetreSimulation` | `src/interface/fenetre_simulation.py` | Fenêtre de la simulation. |
| `VueCarte`, `DessinVehicule` | `src/interface/carte.py` | Plan et rectangles des véhicules. |
| `FenetreCentre` | `src/interface/fenetre_centre.py` | Affichage du centre. |
| `ClientEtats`, `ServeurCentre` | `src/reseau/client.py`, `serveur.py` | Échanges entre les deux programmes. |
| `StockageMariaDB` | `src/stockage/mariadb.py` | Lecture et écriture dans la base. |

Les méthodes s'appellent par exemple `demarrer_mission`, `avancer`, `publier`
et `enregistrer`. Les attributs portent des noms comme `vitesse`, `trajet`,
`debut_mission` ou `reserve_temps`.

Les noms imposés par Python, PyQt6 et les bibliothèques restent inchangés :
`__init__`, `closeEvent`, `setText`, `connect`, `assertEqual`, etc.
Les options de lancement, clés du protocole, paramètres des bibliothèques et
tables SQL restent compatibles avec la configuration existante.

L'ancienne démonstration et ses tests spécifiques ont été retirés, ainsi que
ses captures d'écran. Les tests conservés vérifient le projet actuel :
trajets, circulation, priorités, interface, réseau et stockage. Ils ne sont
pas nécessaires au lancement, mais permettent de vérifier les modifications.
