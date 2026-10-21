# Organisation du projet

## Trois programmes

- `main.py` ouvre la simulation et, sauf avec `--local`, démarre le client TCP.
- `centre.py` reçoit les états des secours et les fait enregistrer dans MariaDB.
- `init_db.py` prépare les tables, puis se termine.

Sur la VM unique, les échanges utilisent 127.0.0.1 : port 5000 pour le centre,
3306 pour MariaDB. Les paramètres sont lus par `src/configuration.py`.

## Modèles et affichage

`src/modeles/vehicules.py` contient les données modifiables des véhicules et
les instantanés transmis à l'interface. `plan.py` décrit les routes et construit
les parcours ; `trajet.py` retrouve la position à partir d'une distance parcourue.

`src/interface/fenetre_simulation.py` possède le moteur et un minuteur Qt.
`carte.py` dessine les états qu'elle reçoit. `fenetre_centre.py` affiche les
derniers états et l'historique fournis par le serveur ; elle ne pilote pas les feux.

## Avancement et priorité

Le moteur découpe le temps en pas de 0,05 seconde. Une voiture roule normalement
à 28 unités/s, et à 40 dans une courbe. Une suivante peut entrer pendant le virage
d'un véhicule de la même approche ; elle ralentit à 18 unités/s si celui-ci est
encore proche. Les mouvements opposés qui se coupent restent successifs.

`priorite.py` repère les voitures situées devant ou sur la voie opposée à un
secours proche. Sur une portion droite, hors des zones à dégager, le moteur
cherche une place complète au bord de la voie. La voiture se décale de 26 unités,
à 30 unités/s latéralement, s'immobilise et attend que le secours l'ait dépassée
d'environ 65 unités. Elle reprend ensuite sa marche en rejoignant sa voie ; la suivante ralentit pour lui rendre sa place.

La position décalée sert à la fois au dessin et aux collisions : ce n'est pas
une animation superposée. Le suivi normal garde 44 unités entre centres.
Près d'une voiture rangée, les rectangles orientés sont contrôlés avec une marge
de 3 unités entre carrosseries. Chaque mouvement, y compris latéral, est vérifié.

Les réservations de raccordement utilisent la position réelle des voitures
rangées. Une file ne doit pas immobiliser un secours à cause de l'ancienne
position d'une voiture qui a libéré sa voie.

`feux.py` conserve le cycle 8 s de vert, 1 s d'orange et au moins 1 s de tout rouge.
Le départ demande NS dès l'envoi en intervention. Le retour conserve NS après
le dernier passage du carrefour, jusqu'au dégagement de l'accès caserne.
Les deux réserves de temps se compensent ; un quart du solde est rendu au prochain
vert normal bénéficiaire. Un bonus interrompu reste dû pour sa partie non servie.

## Réseau et base

`client.py` envoie des objets JSON terminés par un saut de ligne. Chaque état
possède un numéro et une session. Le client garde les messages jusqu'à leur ACK
et se reconnecte après une coupure.

`serveur.py` reçoit et valide les messages, puis appelle `MariaDBStore`.
L'enregistrement du dernier état et de l'historique se fait dans une transaction.
Les doublons sont confirmés sans ajouter de ligne. Une coupure de liaison ne
transforme pas un état occupé en disponible.

Le réseau possède ses threads ; le calcul de simulation reste dans le thread Qt.
La base conserve les états et l'historique, pas les positions de toutes les voitures.
