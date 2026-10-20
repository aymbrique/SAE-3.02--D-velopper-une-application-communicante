# Architecture et changements realises

## Avant et apres

La premiere version etait une animation : chaque vehicule avait des horaires de depart et d'attente prepares dans `demo.py`. Le panneau de coordination lisait les memes objets Python que la simulation.

Le deploiement retenu lance les deux programmes sur une meme VM, relies par TCP sur 127.0.0.1:5000.

Desormais, `main.py` utilise `Simulation` dans `engine.py`. Les positions sont recalculees suivant la vitesse, les feux, les autres vehicules et les reservations de passage. `centre.py` est un autre programme : il apprend les etats uniquement par TCP et les conserve dans MariaDB.

Les dossiers restent `interface` et `reseau`. L'ancien scenario et ses huit tests sont conserves pour reference ; ils ne pilotent plus la simulation.

La version simplifiee utilise des rectangles et les widgets Qt standards. Les expressions les plus compactes ont ete detaillees en boucles et conditions ; voir le [parcours de lecture du code](code-simple.md).

## Repartition des responsabilites

| Module | Responsabilite |
|---|---|
| `models/route.py` | Interpoler une position et une orientation le long d'une suite de points. |
| `models/layout.py` | Decrire les routes, les lignes d'arret, les sorties et les trajets de secours. |
| `models/vehicle.py` | Donnees des vehicules et instantanes immuables pour le dessin. |
| `simulation/engine.py` | Temps simule, generation, deplacement, files, missions et evenements de disponibilite. |
| `simulation/lights.py` | Cycle des feux, selection d'une demande et dette compensatoire. |
| `interface/main_window.py` | Commandes, minuteur Qt, carte et envoi des evenements au client reseau. |
| `interface/coordination_window.py` | Affichage des donnees recues, sans acces au moteur. |
| `reseau/protocol.py` | Decouper et valider les messages JSON. |
| `reseau/client.py` | Envoyer, attendre un ACK et se reconnecter dans un thread. |
| `reseau/server.py` | Recevoir, faire enregistrer en base puis confirmer la reception. |
| `stockage/mariadb.py` | Requetes SQL parametrees, transactions et lectures. |
| `config.py` | Adresses, ports et identifiants SQL locaux. |

## Moteur de circulation

`QTimer` demande des mises a jour d'affichage. Le moteur accumule le temps et avance par pas fixes de **0,05 seconde simulee**. Le resultat ne depend donc pas du nombre d'images affichees. La pause n'appelle plus l'avancement du moteur ; le reseau continue dans son thread.

Une unite graphique represente **0,5 metre**. Les vitesses nominales sont de 28 unites/s pour les voitures (14 m/s) et 40 pour les secours (20 m/s). Ce sont des choix de simulation, pas une modelisation de conduite reelle.

Le debit indique un intervalle de generation de `60 / debit` secondes. L'origine est tiree uniformement ; le virage utilise 95 % tout droit, 2,5 % gauche et 2,5 % droite avec un generateur pseudoaleatoire reproductible. Une entree occupee ou la limite de 25 voitures reporte la possibilite d'apparition au prochain intervalle ; il n'y a pas de rattrapage en rafale.

La distance minimale entre centres est de **44 unites**, superieure aux dimensions des formes dessinees. Le moteur conserve l'ensemble `crossing_owners` des vehicules engages. Les voitures allant tout droit depuis la meme origine ou depuis des origines opposees peuvent partager le carrefour. Plusieurs voitures de chaque file peuvent etre engagees : un suivant avance au vert avec son leader sans attendre sa sortie complete, en conservant GAP = 44 unites entre centres. Les virages et les secours restent exclusifs. Le changement d'axe attend le degagement de tous les vehicules engages. Les voitures tout droit deja engagees ou sur la sortie, encore en mouvement, ne bloquent plus le controle de tout le corridor. Chaque deplacement continue de verifier la distance avec tous les vehicules. Une voiture arretee sur la sortie bloque toujours une nouvelle entree. Les leaders deja sortis sont deplaces avant les voitures qui les suivent encore dans le carrefour, pour eviter un micro-arret a la sortie.

Le plan est defini dans `layout.py` : `NODES` contient les coordonnees des raccordements et `ROAD_SEGMENTS` relie ces points. Le dessin et les trajets partagent ces donnees. Les parcours sont des listes de noms de points, avec un decalage sur la voie de droite et des virages arrondis. Les origines Nord/Sud/Est/Ouest des voitures designent leur branche d'arrivee au carrefour principal ; une voiture venant de l'Est peut apparaitre sur la route superieure avant de rejoindre cette branche.

Seul le point `C` possede des feux. Aux autres raccordements, une reservation simple autorise un vehicule a la fois : le suivant attend avant la zone tant qu'elle est occupee ou que sa sortie est bouchee. `route.junctions` contient les distances d'entree et de sortie de ces zones sur chaque parcours. La sortie de la caserne et les aires d'intervention sont egalement protegees. Les routes supplementaires peuvent donc provoquer une file en aval du carrefour principal.

Ce choix conservateur limite le debit maximal. Une voiture peut attendre au vert pour respecter une reservation ou un espacement.

## Missions et feux

Chaque secours a sa propre heure de depart, sa distance sur le parcours, sa destination et son etat. `rescue_route` construit un trajet vers Ouest (point 1), Sud-Ouest (point 2), Nord-Est (point 3) ou Est (point 4). Tous ont deux passages au carrefour principal, dont le retour peut demander l'axe Est-Ouest. Les deux peuvent etre occupes en meme temps. Le trajet passe par l'intervention, attend 8 secondes puis retourne a la caserne. Le compteur des trajets termines comprend les sorties des voitures et les missions achevees.

L'ETA est la distance restante sur le trajet jusqu'a la prochaine ligne d'arret, divisee par la vitesse nominale. Il n'inclut pas la prediction des files. A vitesse nulle, l'ETA est infini ; le critere de distance reste applicable.

Seuls les secours ayant atteint 150 m ou moins, ou 10 s ou moins, deposent une demande. Sur le nouveau plan, le secours approche du seuil apres avoir quitte sa place de stationnement. Le code et les tests couvrent aussi un secours hors seuil.

L'ordre des demandes est : depart de mission le plus ancien, demande la plus ancienne, identifiant le plus petit. Le choix reste verrouille jusqu'a la sortie pendant la traversee. Avant l'engagement, une sortie bouchee suspend la demande afin que l'autre axe puisse se degager. Une demande plus ancienne ne remplace pas une priorite admissible en cours. Un second secours en sens oppose attend meme si l'axe est vert.

Un changement d'axe passe par 1 seconde d'orange puis au moins 1 seconde de rouge simultane. Le rouge se prolonge si un vehicule est encore engage. Une priorite sur l'axe deja vert peut prolonger ce vert ; deux secours successifs sur cet axe n'en reinitialisent pas la duree.

Le depassement de 8 secondes du vert prioritaire alimente la dette de l'axe oppose. La dette utile est plafonnee a 8 secondes, car une phase compensatoire ne peut depasser 16 secondes. Quand tous les secours sont disponibles, cet axe obtient 8 secondes normales puis la duree compensatoire. Une nouvelle mission suspend la partie compensatoire non consommee ; elle n'est pas effacee.

## Protocole TCP

Une simulation active transmet les deux secours sur une seule connexion au centre. Une seconde connexion de simulation simultanee est refusee pour eviter que deux sources pilotent les memes identifiants.

Exemple de message :

```json
{"type":"etat","id":"01","etat":"occupe","numero":2,"session":"550e8400-e29b-41d4-a716-446655440000"}
```

Chaque objet JSON est encode en UTF-8 et termine par un saut de ligne. TCP peut fragmenter ou regrouper les donnees : `Decoder` conserve les octets incomplets et extrait les lignes completes. Une ligne est limitee a 4096 octets.

Le centre accepte seulement les identifiants 01/02, les etats `occupe`/`disponible`, un numero entier positif et une session UUID. La session change a chaque lancement de la simulation ; les numeros augmentent independamment pour chaque vehicule. Une reinitialisation de la scene n'annule pas ces numeros.

Le centre envoie un `ack` avec session, identifiant et numero **apres le commit SQL**. Un echec SQL n'est donc pas confirme. Le client garde les messages non confirmes dans leur ordre et les renvoie apres reconnexion. Des pings/pongs permettent de detecter une liaison muette ; le serveur ferme une connexion inactive apres environ 6 secondes.

A la reconnexion, le dernier etat connu des deux secours est aussi renvoye. Les doublons sont confirmes sans etre reinseres dans l'historique. Un arret du client ne passe pas automatiquement les secours a disponible au centre.

La file d'attente du client est en memoire : elle survit a une coupure reseau tant que le programme reste ouvert, mais pas a sa fermeture. Le protocole est prevu pour le LAN de TP, sans authentification ni chiffrement.

## MariaDB

PyMySQL est le pilote Python utilise pour joindre **MariaDB**, pas une autre base. MariaDB est un service de la VM unique ; elle n'est pas un simple fichier du depot.

| Table | Contenu | Cle |
|---|---|---|
| `vehicules` | Dernier etat accepte, session, numero et reception UTC pour chaque secours. | `identifiant` |
| `historique_etats` | Toutes les mises a jour acceptees, dans l'ordre de reception. | `id` auto-incremente ; unicite session/identifiant/numero |

Une transaction ajoute l'historique et remplace le dernier etat ensemble. Les valeurs passent comme parametres SQL, sans concatenation dans la requete. Un numero deja recu ou plus ancien pour le meme vehicule et la meme session est ignore. L'etat de 01 ne remplace jamais celui de 02.

La liaison n'est pas un etat metier stocke dans ces tables : elle est calculee par le serveur en fonctionnement. Au redemarrage, les etats restaures sont des **derniers etats connus**, tant que la simulation n'a pas renvoye ses informations.

`init_db.py` execute les deux scripts de `sql/`, chacun contenant une instruction `CREATE TABLE IF NOT EXISTS`. La base et l'utilisateur sont crees au prealable par l'administrateur, selon le guide. Aucun mot de passe n'est present dans le depot.

## Ajouts hors du PDF initial

Le PDF initial ne precisait pas la base de donnees. MariaDB et son historique ont ete ajoutes sur demande du binome. Le centre est maintenant executable separement pour l'utilisation sur une VM Linux. Le systeme reste limite a un carrefour a feux, des raccordements secondaires sans feux, deux secours et un centre.

L'installation de votre VM, la validation sur son environnement reel et la demonstration au professeur restent a effectuer avec le [guide](deploiement-une-vm.md) et la [grille de validation](validation.md).

La destination reste locale au moteur et a l'interface ; le protocole TCP et les tables MariaDB continuent de conserver les etats, les numeros et les sessions.
