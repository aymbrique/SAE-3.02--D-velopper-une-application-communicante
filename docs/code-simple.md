# Comprendre la version simplifiee

Cette version conserve les fonctions du projet avec une presentation plus sobre et du code plus explicite. Le lancement reste identique : `python main.py --local` pour la simulation seule, ou les deux programmes selon le guide Linux.

## Ce qui a ete simplifie

- Carte : deux routes grises, des lignes blanches et quatre ronds colores pour les feux, sur un fond vert.
- Vehicules : rectangles bleus pour les voitures, rouge pour le pompier 01, blanc pour l'ambulance 02. Le survol indique leur situation.
- Fenetre : boutons Qt standards, sans feuille de style, ombres, arbres, facades ou dessins detailles de vehicules.
- Informations : trois onglets Trafic, Secours et Reseau, plutot qu'une longue barre laterale.
- Code : plusieurs expressions compactes deviennent des boucles `for` et des conditions `if` / `else`.
- Trajet : une classe avec un constructeur ordinaire ; une boucle cherche le segment sur lequel se trouve le vehicule.
- Moteur : les controles des acces lateraux ont leurs propres fonctions. Les callbacks des boutons sont des methodes nommees.

Les missions proposent maintenant quatre destinations ; la circulation permet aux voitures allant tout droit sur le meme axe de traverser en sens opposes et de se suivre sans attendre la sortie complete du leader, avec le meme espacement de securite. Les vitesses et la compensation sont conservees. Le reseau conserve la reconnexion et les confirmations de reception. MariaDB conserve l'etat courant et l'historique. Le dessin n'utilise plus les couleurs individuelles des voitures, ni le clignotement decoratif des gyrophares.

## Dans quel ordre lire les fichiers ?

1. `main.py` : choisir le mode local ou connecte et ouvrir la fenetre.
2. `src/interface/main_window.py` : creer les boutons et brancher leurs actions.
3. `src/interface/map_view.py` : dessiner la carte et deplacer les rectangles.
4. `src/models/vehicle.py` : lire les informations qui decrivent un vehicule.
5. `src/simulation/engine.py` : faire avancer les voitures et les missions.
6. `src/simulation/lights.py` : choisir les couleurs des feux.
7. `src/reseau/protocol.py`, puis `client.py` et `server.py` : envoyer et recevoir les etats.
8. `src/stockage/mariadb.py` : enregistrer les etats avec des requetes SQL.
9. `src/models/route.py` et `layout.py` : comprendre les coordonnees et les calculs de trajet.

## Les notions utiles

| Notion | Exemple dans le projet |
|---|---|
| Variable | `playing` indique si la simulation avance. |
| Condition | Si le feu est rouge, le vehicule attend. |
| Boucle | Parcourir les voitures pour mettre leurs positions a jour. |
| Liste | `cars` contient les voitures presentes. |
| Dictionnaire | `NODES["C"]` retrouve les coordonnees du carrefour a feux. |
| Fonction / methode | `start_mission("01")` declenche une mission. |
| Classe | `Simulation` regroupe les donnees et les actions du moteur. |
| `self` | Designe l'objet courant, par exemple la fenetre ouverte. |
| Signal Qt | `button.clicked.connect(...)` relie un clic a une methode. |
| Minuteur | `QTimer` appelle `_tick` environ toutes les 30 millisecondes. |
| Socket TCP | Transporte les etats entre les deux programmes sur la meme VM. |
| JSON | Transforme un dictionnaire Python en texte transmissible. |
| SQL | Insere et lit les etats dans MariaDB. |

## Suivre une mission dans le code

1. Choisir un vehicule et une destination, puis cliquer sur Envoyer appelle `_send_selected`.
2. Cette methode appelle `start_mission("01", "E")` dans la fenetre pour les pompiers vers l'Est.
3. La fenetre demande au moteur de marquer le secours occupe.
4. Le moteur ajoute un evenement `("01", "occupe")` dans sa liste.
5. `_publish_events` transmet cet evenement au client TCP si le mode connecte est actif.
6. Le serveur recoit le message et demande son enregistrement dans MariaDB.
7. Apres l'enregistrement, le serveur confirme la reception et le centre affiche l'etat.
8. Pendant la lecture, `_tick` fait avancer le moteur et rafraichit les rectangles.
9. Au retour a la caserne, le moteur produit l'evenement disponible ; il suit le meme chemin.

Une mission peut etre declenchee pendant la pause : son etat devient occupe, mais le deplacement attend la reprise.

## Quelques notions restent plus avancees

Conserver toutes les fonctions demande quelques mecanismes a apprendre progressivement :

- `dataclass` cree le constructeur des petites fiches de donnees. `frozen=True` empeche de modifier directement un instantane d'affichage.
- `@property` permet d'obtenir une valeur calculee comme `vehicle.position` sans ecrire de parentheses.
- Un thread fait fonctionner le reseau en parallele de la fenetre. Un verrou (`Lock`) protege leurs donnees communes.
- La file `deque` conserve les messages jusqu'a leur confirmation : le premier ajoute est le premier envoye.
- `select` permet au serveur d'attendre soit une nouvelle connexion, soit des donnees du client.
- Une transaction SQL valide l'historique et le dernier etat ensemble avec `commit()`.
- La formule de Bezier dessine les virages arrondis. Elle reste isolee dans `route.py` ; elle n'est pas necessaire pour comprendre les boutons ou les messages TCP.

La simplification rend les etapes plus visibles ; elle ne transforme pas les sockets, les calculs de trajectoire et la gestion des priorites en notions deja acquises en premiere annee.

## Modifier le plan de la simulation

Il n'y a qu'une application de simulation : `main.py`. Le plan est dans `src/models/layout.py` et son dessin dans `src/interface/map_view.py`.

- `NODES` associe un nom court a une position `(x, y)` ; `C` est le carrefour a feux, `F` l'acces de la caserne.
- `ROAD_SEGMENTS` liste les paires de points relies par une route.
- `car_route` et `rescue_route` donnent la liste des points a suivre.
- `build_route` decale les vehicules sur la voie de droite, arrondit les virages et note les zones de passage.
- `engine.py` fait avancer les vehicules sur ces parcours et les retient avant une zone occupee.

Le dessin et les deplacements utilisent donc les memes coordonnees. Pour ajouter une route utilisee, il faut l'ajouter a `ROAD_SEGMENTS` puis l'inclure dans un parcours. Les lettres historiques `W`, `S`, `N`, `E` identifient les destinations ; leurs libelles sont maintenant Ouest, Sud-Ouest, Nord-Est et Est.
