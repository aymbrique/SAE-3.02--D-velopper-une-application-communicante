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

Les secours roulent à 56 unités/s, plus vite que les voitures même dans les
virages. `priorite.py` repère les voitures devant un secours proche. Sur une
portion droite, hors des accès à dégager, elles se rangent de 22 unités en
avançant sur 72 unités. Le braquage reste inférieur à 25 degrés. La courbe commence et finit parallèlement à la voie ;
l'orientation dessinée suit le déplacement. Une voiture bloquée ne glisse pas
sur le côté. Une fois rangée, elle attend le passage du secours, puis rejoint
sa voie avec la même manœuvre.

L'ordre de la file est conservé sur la voie habituelle, avec 44 unités entre
les centres, même si le véhicule de tête s'est rangé. Les suivantes attendent
et lui rendent sa place. Si une manœuvre reste inachevée faute de place, les
voitures devant avancent assez pour qu'elle se termine. Seul le secours peut
dépasser par le milieu de la route, sur les portions droites assez longues
pour se décaler et revenir avant un raccordement.

La position décalée et l'angle servent au dessin et aux collisions. Les
rectangles orientés sont vérifiés avec une marge de 3 unités entre carrosseries.
Une réinsertion attend si le secours se trouve à côté ; un secours qui suit
une voiture déjà en réinsertion garde la distance nécessaire. Avant de
commencer une manœuvre, son gabarit est vérifié sur toute la courbe.

Au vert, le secours peut avancer derrière une voiture ou dans une branche
libre sans attendre la libération de tout le carrefour. Chaque déplacement
reste contrôlé. Aux raccordements, les trajets qui se coupent gardent une
réservation jusqu'au dernier conflit géométrique.

Un secours qui tourne laisse terminer la réinsertion d'une voiture déjà engagée
si sa courbe lui coupe la route. Il entre dès que le dernier conflit est dégagé,
même si cette voiture n'a pas encore quitté tout le carrefour.

À la caserne, un départ et un retour peuvent partager l'allée lorsque leurs
carrosseries restent séparées. Si le véhicule sortant barre la fin du retour,
il dégage d'abord l'accès ; les deux secours ne s'attendent plus mutuellement.
Le véhicule entrant attend toujours si le départ est réellement immobilisé
sur son trajet.

Une voiture rangée en sortie continue à dégager la file si des véhicules sont
encore engagés derrière elle, au carrefour ou dans un accès de secours. Cela
permet de finir la traversée et de quitter le tout rouge sans ouvrir un axe
sur un carrefour occupé. Les arrivées à une borne de trajet sont arrondies à
une tolérance de 0,000001 unité pour éviter un arrêt dû aux calculs flottants.

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
