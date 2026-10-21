# Utilisation des interfaces

## Simulation : main.py

1. Lancer la simulation selon le [guide Linux](deploiement-une-vm.md).
2. Cliquer sur **Demarrer**. Les voitures apparaissent progressivement ; le debit initial est de 12 voitures par minute simulee.
3. **Mettre en pause** fige le temps simule, les vehicules et les feux. La connexion TCP reste active pendant la pause.
4. **Reprendre** continue depuis le meme etat. La liste de vitesse (x0,5, x1, x2) change le rapport entre temps reel et temps simule.
5. Le champ **Voitures / minute** accepte 0 a 60. A 0, les voitures deja presentes finissent leurs trajets, sans nouvelles arrivees.
6. Choisir le **Vehicule** (01 pompiers ou 02 ambulance), puis **Intervention** (Ouest - point 1, Sud-Ouest - point 2, Nord-Est - point 3, Est - point 4). **Envoyer en intervention** demarre sa mission et envoie immediatement son etat occupe. Un secours deja occupe ne peut ni repartir ni changer de destination. Le second secours reste selectionnable et peut partir pendant la premiere mission.
7. **Recommencer** remet le moteur et les compteurs a zero, annule les missions et envoie disponible pour les deux secours. Le debit choisi est conserve. L'historique MariaDB n'est pas efface.

Une mission declenchee pendant la pause devient occupee mais n'avance qu'apres reprise. A l'arrivee au point d'intervention, le secours attend 8 secondes simulees puis revient a la caserne. Il repasse disponible a son retour.

Les deux listes de choix et le bouton d'envoi se trouvent en haut de la fenetre. L'onglet **Secours** montre les deux etats, la progression, la distance jusqu'au prochain passage au carrefour, l'ETA et le temps de mission ecoule.

Les estimations utilisent la longueur du trajet et la vitesse de circulation nominale ; elles n'anticipent pas les files et les feux. L'ETA vise toujours le prochain passage, y compris le passage du retour. Le temps de mission ecoule sert a departager les priorites ; ce n'est pas l'ETA.

L'onglet **Reseau** affiche l'adresse, la liaison et le nombre de mises a jour non confirmees. L'onglet **Trafic** affiche les compteurs, les feux et le **Temps d'accumulation**, avec deux reserves en secondes : ligne horizontale (Est-Ouest) et ligne verticale (Nord-Sud). Un vert prioritaire vertical de 22 s stocke par exemple 14 s pour la ligne horizontale. `--local` desactive le reseau pour travailler uniquement sur la simulation.

## Carte et circulation

La carte est volontairement simple : fond vert hors des routes, quatre points d'intervention, routes grises, feux ronds, voitures bleues, pompier 01 rouge et ambulance 02 blanche. Les vehicules sont des rectangles.

Les points d'intervention sont associés à quatre bâtiments : mairie à l'ouest
(point 1), restaurant au sud-ouest (point 2), IUT de Colmar au nord-est
(point 3) et E.Leclerc à l'est (point 4). Chacun possède un petit parking gris
accolé au bâtiment et une allée jusqu'à la route. Le rectangle jaune indique
l'arrêt du secours. Les bâtiments sont dessinés avec les rectangles, polygones
et textes de PyQt6 dans `src/interface/batiments.py`, sans image importée.

Les voitures arrivent depuis l'exterieur des extremites visibles des routes, y compris les marges dues au format de la fenetre. Elles ne sont pas inserees au milieu d'une voie. La moitie des tirages d'arrivee vient du Nord ; les trois autres origines se partagent l'autre moitie. Une entree occupee peut retarder l'apparition.

Molette : zoom. Glisser : deplacement. **Vue complete** : retour au cadrage initial. **Afficher un trajet** : choix parmi les huit parcours de secours (deux vehicules et quatre destinations) et les dix-huit trajets de voiture (douze de base et six variantes). Survoler un vehicule affiche son identifiant et sa situation.

Les voitures s'arretent au rouge et a l'orange devant le vrai feu. Au vert, les files suivant le meme mouvement, y compris le meme virage, et les mouvements opposes tout droit/a droite peuvent passer ensemble. Les trajectoires qui se croisent attendent ; une sortie reellement bouchee impose l'attente. Les courbes sont parcourues plus vite pour liberer le passage. Une voiture deja engagee finit son passage. L'autre axe n'est ouvert qu'apres degagement et les transitions de securite.

Le carrefour a feux se trouve a gauche du plan. Devant la caserne et aux autres raccordements sans feux, les voitures qui suivent le meme trajet local ou roulent tout droit en sens opposes avancent ensemble. Les voitures du Nord rejoignent la file du feu principal. Elles cedent le passage lorsqu'un secours approche de l'acces a la caserne, et reprennent des que sa trajectoire est degagee. Cette priorite vaut a l'aller comme au retour. Un vehicule deja engage peut terminer son passage ; une voiture devant le secours avance pour liberer sa voie.

Le raccordement entre la route horizontale du milieu et celle du bas, a l'Est, est descendant : on peut le prendre depuis la gauche, ou continuer tout droit. Les voitures du bas ne le remontent pas ; celles venant de droite ne tournent pas vers le bas a cet endroit. Les voitures arrivant du bas a droite restent sur la route inferieure jusqu'a leur parcours autorise.

Cette petite voie conserve son sol gris et sa flèche blanche descendante.
Le décor de travaux se limite à deux barrières rouges et blanches et à un
panneau triangulaire accompagné du texte « Travaux ».
Trois cédez-le-passage sont dessinés aux raccordements sans feux : arrivées du
nord vers les routes du milieu et du bas, et arrivée de l'est sur la route
supérieure. Les panneaux et travaux sont uniquement décoratifs : ils ne
changent pas les trajets ni les règles de circulation. Leur dessin se trouve
dans `src/interface/signalisation.py` et utilise seulement les formes de PyQt6.

Les quatre destinations possedent un passage aller et un passage retour au carrefour principal. Le point 3 se trouve au nord-est, sur la route superieure ; le point 2 est au sud-ouest, sur la route du bas. Des que le secours est a 150 m ou moins ou a 10 s d'arrivee ou moins, son feu est demande au vert, a l'aller comme au retour. Si l'autre axe est vert, il passe immediatement a l'orange, puis au tout rouge avant le vert du secours ; les vehicules deja engages finissent de degager. Une sortie occupee impose l'attente avant d'entrer, mais ne supprime plus la demande du vert.

Les demandes de priorite admissibles sont departagees par mission la plus ancienne, puis demande la plus ancienne, puis identifiant. Une priorite attribuee n'est pas interrompue par l'autre secours. Le second ne passe pas avant le premier, meme si le meme axe est vert.

Des l'envoi en intervention, la ligne verticale est demandee au vert pour vider la file entre caserne et feu. Les voitures en amont de la caserne attendent, celles deja devant degagent. Le secours avance dans l'allee pendant cette vidange et s'insere lorsque le passage est libre. Au retour, il conserve la demande verticale apres le feu principal jusqu'au degagement de l'acces caserne, pour qu'une nouvelle file rouge ne l'enferme pas devant son garage.

Les reserves des deux lignes se compensent en permanence : 17 s verticales et 15 s horizontales deviennent 2 s verticales et 0 s horizontales. Le prochain vert normal vertical dure alors 8 + 0,5 s ; il restera 1,5 s a repartir sur les cycles suivants. Une mission eloignee du carrefour n'empeche pas la restitution. Une demande prioritaire interrompt le bonus sans effacer sa partie non servie ; seuls les bonus effectivement ecoules diminuent le solde. Les petits residus sont soldes avec un dernier bonus d'au plus 0,05 s. Mettre en pause fige les compteurs ; Recommencer les remet a zero.

## Centre : centre.py

La premiere table affiche les secours 01 et 02 separement. Avant le premier message, l'etat est **Inconnu**. Apres un redemarrage, elle charge les derniers etats MariaDB, avec une liaison interrompue jusqu'a reception des donnees du client.

La seconde table montre les 100 dernieres mises a jour, les plus recentes en premier. Les dates de reception sont en **UTC** et en temps reel ; elles sont distinctes du temps simule. La base conserve aussi les lignes plus anciennes.

Une coupure change l'indication de liaison, pas l'etat disponible/occupe. Un message repete lors d'une reconnexion ne cree pas une nouvelle ligne d'historique. Un identifiant de session distingue deux lancements de la simulation, dont les compteurs commencent chacun a 1.

Le centre ne commande pas les feux : ceux-ci appartiennent au moteur de la simulation. Il affiche et conserve les etats recus.

Au feu principal, le choix aleatoire utilise 95 % tout droit, 2,5 % gauche et 2,5 % droite. Une voiture du Nord peut donc aller vers l'Est ou l'Ouest a ce feu. Parmi les parcours qui continuent vers le Sud, 5 % prennent ensuite la route du bas vers l'Ouest. Parmi ceux qui vont vers l'Est, 5 % tournent au raccordement du milieu vers le Nord. Il s'agit de probabilites conditionnelles, pas de quotas par groupe de voitures.

## Fichiers et rangement des voitures

Le code a des noms français : `src/modeles/vehicules.py` pour les véhicules,
`src/modeles/plan.py` pour la géométrie, `src/simulation/moteur.py` pour les
déplacements et `src/interface/carte.py` pour le dessin. Voir ARBORESCENCE.txt.

À l'approche d'un secours, une voiture se décale réellement vers le bord droit
de sa voie, reste arrêtée puis reprend après le passage. Elle finit d'abord
un carrefour ou un virage déjà engagé, et cherche une place assez grande
pour ne pas rester à moitié rangée. Les carrosseries gardent une marge libre.

Les voitures d'une même approche peuvent entrer au vert même si la première
tourne : les suivantes ralentissent. Les trajectoires qui se croisent gardent
un passage successif. Le rouge, l'orange et les secours restent prioritaires.
