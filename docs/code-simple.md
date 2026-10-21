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

`exemples/ancienne_animation.py` est une ancienne démonstration à horaires fixes.
Elle n'est pas utilisée par `main.py`.
