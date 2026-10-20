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

Une unite graphique represente **0,5 metre**. Les voitures roulent a 28 unites/s en croisiere et 40 dans les courbes ; les secours restent a 40. `route.turn_zones` delimite exactement les courbes de Bezier, hors approche et marge de sortie. Une vitesse de voiture forcee a zero reste nulle. Ce sont des choix d'animation, pas une modelisation de conduite reelle.

Le debit indique un intervalle de generation de `60 / debit` secondes. L'origine est tiree avec une probabilite de 50 % au Nord et 1/6 pour chacune des trois autres origines ; le virage utilise toujours 95 % tout droit, 2,5 % gauche et 2,5 % droite avec un generateur pseudoaleatoire reproductible. Une entree occupee ou la limite de 25 voitures reporte la possibilite d'apparition au prochain intervalle ; il n'y a pas de rattrapage en rafale. Ces proportions concernent les tirages : une entree encombree peut refuser une apparition.

`MapView.traffic_bounds()` donne les bords visibles dans les coordonnees du plan, marges comprises. Avant l'avancement, la fenetre transmet ces limites au moteur. `car_route` prolonge le debut et la fin de la voie de 30 unites au-dela de ces limites, de sorte que le rectangle de voiture entre depuis l'exterieur et disparaisse apres sa sortie. Le moteur sans interface utilise les limites de la scene. Les nouvelles voitures restent hors ecran apres redimensionnement et zoom ; aucun raccordement interieur ne sert de point d'apparition.

La distance minimale entre centres est de **44 unites**, superieure aux dimensions des formes dessinees. Le moteur conserve l'ensemble `crossing_owners` des vehicules engages. Les files d'une meme origine suivant le meme mouvement peuvent partager le carrefour, y compris en virage ; en sens opposes, les mouvements tout droit/a droite sont egalement compatibles. Les mouvements qui se croisent et les secours restent exclusifs. Le changement d'axe attend le degagement des vehicules engages. Chaque petit deplacement verifie la distance avec tous les vehicules, sans exception.

Un leader deja sorti et en mouvement sur la meme voie sortante peut etre suivi par une voiture ou un secours. `_following_exit` controle sa sortie effective, son cap, sa position en aval et son alignement ; il ne l'ignore que dans la reservation globale du trajet. Le controle du prochain deplacement continue d'imposer GAP. Un vehicule immobile sur la sortie bloque toujours l'engagement. Les leaders deja sortis sont deplaces avant leurs suivants, pour mettre a jour leur mouvement avant cette decision.

Le plan est defini dans `layout.py` : `NODES` contient les coordonnees des raccordements et `ROAD_SEGMENTS` relie ces points. Le dessin et les trajets partagent ces donnees. Les parcours sont des listes de noms de points, avec un decalage sur la voie de droite et des virages arrondis. Les origines Nord/Sud/Est/Ouest des voitures designent leur branche d'arrivee au carrefour principal ; une voiture venant de l'Est peut apparaitre sur la route superieure avant de rejoindre cette branche.

Seul le point `C` possede des feux. Aux autres raccordements, `route.junction_movements[(distance_entree, nom)]` indique les directions locales d'entree et de sortie. Les voitures ayant le meme mouvement, meme en virage, ou allant tout droit en sens opposes peuvent avancer ensemble en gardant GAP. La file du Nord peut ainsi rejoindre le vrai feu rouge au lieu d'attendre inutilement devant la caserne. Les aires d'intervention et le stationnement restent exclusifs.

Pour des mouvements differents, `_junction_still_conflicts` calcule le dernier point du trajet de l'autre vehicule qui peut encore couper le passage. L'echantillonnage de 3 unites utilise une marge sur GAP ; le resultat est memorise par raccordement, mouvements et extremite du balayage. Cela permet notamment a un secours rentrant a la caserne de tourner derriere des voitures ayant deja depasse son point de conflit, meme si elles attendent plus loin dans la file. Le controle physique de chaque deplacement reste obligatoire.

Un secours occupe reserve la priorite a 120 unites de l'entree (3 s a sa vitesse nominale), a l'aller comme au retour. Les voitures sur les autres branches attendent ; celles deja engagees peuvent degager. Une voiture devant le secours sur sa voie d'approche peut liberer sa voie. Deux secours sont departages par anciennete de mission, puis identifiant. `route.junctions` conserve les distances d'entree et de sortie des zones ; des que le secours les libere, le trafic reprend sans attendre son eloignement de toute la sortie.

`route.nodes` conserve les noeuds parcourus. Le constructeur refuse `Q -> R` et `E -> R -> Q` : le raccordement Est vers la route du bas ne se prend que depuis l'Ouest vers le bas. Une sortie Sud suit normalement `C -> D -> Q -> low_east`, ou rarement `C -> D -> L -> low_west` avec la variante `lower_west`. Une sortie Est peut emprunter `C -> B -> U -> top` avec `middle_north`. Chacune de ces variantes a 5 % de probabilite conditionnelle parmi les sorties compatibles ; `route.variant` garde le choix. Le tirage 95/2,5/2,5 au feu reste identique. Les bifurcations se trouvent apres la zone de C : elles ne changent pas sa compatibilite. La carte montre une fleche descendante sur R-Q.

Les extremites ouvertes du reseau atteignent les limites de la scene. Le dessin les prolonge aussi dans les marges de la vue, sans ajouter de branche. L'allee de la caserne finit a `CX - ROAD_HALF` et les aires d'intervention a `road_y - ROAD_HALF` : leur gris clair ne recouvre pas l'asphalte.

Une voiture peut encore attendre au vert devant un obstacle reel, une file pleine, un mouvement en conflit ou un secours prioritaire.

## Missions et feux

Chaque secours a sa propre heure de depart, sa distance sur le parcours, sa destination et son etat. `rescue_route` construit un trajet vers Ouest (point 1), Sud-Ouest (point 2), Nord-Est (point 3) ou Est (point 4). Tous ont deux passages au carrefour principal, dont le retour peut demander l'axe Est-Ouest. Les deux peuvent etre occupes en meme temps. Le trajet passe par l'intervention, attend 8 secondes puis retourne a la caserne. Le compteur des trajets termines comprend les sorties des voitures et les missions achevees.

L'ETA est la distance restante sur le trajet jusqu'a la prochaine ligne d'arret, divisee par la vitesse nominale. Il n'inclut pas la prediction des files. A vitesse nulle, l'ETA est infini ; le critere de distance reste applicable.

Un secours ayant atteint 150 m ou moins, ou 10 s ou moins, depose une demande. La sortie de caserne fait exception : elle demande immediatement NS et reserve F, pour vider la file en aval tout en retenant les arrivees en amont. L'admission du parking verifie seulement l'allee jusqu'a la ligne F ; F controle ensuite l'insertion. Au retour, apres son dernier passage de C, le meme secours demande NS jusqu'au degagement de F. Ce relais empeche qu'un second secours maintienne EW alors que la file Nord emprisonne le premier devant la caserne et bouche la sortie du second.

L'ordre des demandes est : depart de mission le plus ancien, demande la plus ancienne, identifiant le plus petit. Le choix reste verrouille jusqu'a la sortie pendant la traversee ; les informations de la demande, dont l'axe, sont actualisees a chaque calcul. Une sortie bouchee n'annule plus la demande de vert, mais interdit toujours l'entree dans le carrefour. Une demande plus ancienne ne remplace pas une priorite admissible en cours. Les voitures cedent le passage au secours proprietaire du vert, sauf celles devant lui qui doivent liberer sa voie. Un second secours en sens oppose attend meme si l'axe est vert. L'etat `busy` reste vrai jusqu'a la caserne : la visite du point d'intervention ne desactive donc jamais la priorite du retour.

Si deux secours se rejoignent sur la meme voie avant le feu, le suiveur suspend sa demande tant que le secours devant lui doit passer. Cette exception avant engagement empeche qu'un suiveur deja prioritaire bloque la tete de sa propre file. Elle ne retire jamais la priorite d'un vehicule deja engage.

Une demande sur l'autre axe interrompt immediatement le vert courant, sans attendre ses 8 secondes normales. Le changement passe par 1 seconde d'orange puis au moins 1 seconde de rouge simultane. Le rouge se prolonge si un vehicule est encore engage ; le secours a donc son vert apres 2 secondes de transition lorsque le carrefour est libre. Une priorite sur l'axe deja vert peut prolonger ce vert ; deux secours successifs sur cet axe n'en reinitialisent pas la duree.

Le depassement de 8 secondes du vert prioritaire alimente la dette de l'axe oppose. A chaque pas, le minimum des deux dettes est retranche des deux : 17/15 devient 2/0. A chaque ouverture d'un vert sans demande prioritaire, le bonus est fixe a un quart du solde du beneficiaire. Un minimum de 0,05 s, plafonne au solde, termine les petits residus. Seules les secondes de bonus effectivement servies sont deduites ; une demande de secours annule le budget restant sans effacer la dette ni recompter le bonus deja servi. Le parametre `busy` reste compatible avec les appelants mais une mission lointaine n'interdit plus la compensation. L'onglet Trafic affiche `debt["EW"]` comme reserve horizontale et `debt["NS"]` comme reserve verticale : ces axes designent les beneficiaires du remboursement.

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
