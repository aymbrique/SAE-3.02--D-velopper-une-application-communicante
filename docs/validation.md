# Verification et essais

## Tests sans serveur MariaDB

Depuis le dossier du projet, environnement Python active :

```bash
python -m unittest discover -s tests -v
```

Les tests de geometrie, de circulation, de feux et de reseau local s'executent. Les deux tests d'integration MariaDB sont marques `skipped` tant qu'aucune base de test n'est configuree. Ce resultat ne valide donc pas a lui seul la persistance SQL.

## Tests avec MariaDB

Utiliser une base distincte de la base de demonstration. **Ces tests effacent les deux tables de la base de test avant chaque essai.** Le nom doit se terminer par `_test` ; le programme refuse un autre nom.

Dans `sudo mariadb` sur la machine qui heberge MariaDB :

```sql
CREATE DATABASE sae302_test CHARACTER SET utf8mb4;
CREATE USER 'sae302_test'@'127.0.0.1' IDENTIFIED BY 'VOTRE_MOT_DE_PASSE_TEST';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE ON sae302_test.* TO 'sae302_test'@'127.0.0.1';
EXIT;
```

Puis dans le terminal du projet :

```bash
export SAE_TEST_DB_NAME=sae302_test
export SAE_TEST_DB_USER=sae302_test
export SAE_TEST_DB_HOST=127.0.0.1
export SAE_TEST_DB_PORT=3306
read -r -s -p 'Mot de passe de la base de test : ' SAE_TEST_DB_PASSWORD
export SAE_TEST_DB_PASSWORD
python -m unittest discover -s tests -v
unset SAE_TEST_DB_PASSWORD
```

Le `read` masque la saisie du mot de passe. Le compte de test doit avoir le droit DELETE uniquement sur cette base de test. La base de demonstration `sae302` n'est pas concernee.

## Couverture

| Tests | Verification |
|---|---|
| `test_demo.py` - 8 tests historiques | Geometrie et chronologie de l'ancienne demonstration. |
| `test_simulation.py` - 12 tests | Feux, transitions, degagement, arbitrage, seuils, ETA, accumulation sans perte et restitution sur plusieurs cycles, interruption/reprise, files, arret au rouge et passage au vert. |
| Essais longs inclus dans la simulation | Dix minutes a 12/min et a 40/min, maximum de 25 voitures, controle des espacements, plusieurs traversees tout droit compatibles sur le meme axe et progression du trafic. |
| `test_network.py` - 4 tests | Vraies sockets loopback, messages fragmentes/regroupes, validation, erreurs, coupures et redemarrages sans doublons. |
| `test_destinations.py` - 7 tests | Quatre destinations, 16 paires de missions avec trafic, tirage 95/2,5/2,5, passage simultane sur les deux axes, virages exclusifs et sortie bouchee. |
| `test_traffic_flow.py` - 8 tests | Deux files de six voitures sur un seul vert, ecarts, suivi continu a la sortie, rouge/orange, degagement complet, virages et secours exclusifs, sortie bouchee et attente devant un raccordement secondaire occupe. |
| `test_interface.py` - 3 tests | Boutons, pause, vitesse, debit, choix des trajets, missions et reset jusqu'au centre TCP ; compteurs horizontal/vertical, pause et remise a zero. |
| `test_map.py` - 2 tests | Pixels du dessin : gris clair hors de la chaussee, sept extremites ouvertes jusqu'aux bords et absence de nouvelle sortie Sud. |
| `test_rescue_priority.py` - 8 tests | Priorite aller/retour aux raccordements sans feux, vert au retour, voiture deja engagee, degagement de la file devant un secours, deux secours sur la meme voie et missions apres accumulation du trafic a 60/min. |
| `test_mariadb.py` - 2 tests | Transactions reelles, historique, numeros anciens, sessions, TCP avec MariaDB et redemarrage du centre. |

## Verification sur votre VM

### Resultats locaux du 6 octobre 2026

- 25 tests passes avec MariaDB 10.11.14 reelle, sous Python 3.12 puis Python 3.13.15.
- PyQt6 6.11.0, Qt 6.11.2 et PyMySQL 1.2.3 utilises pour ces essais.
- Verification des deux fenetres en mode graphique hors ecran : etats transmis, reset, minuteur, pause/reprise et vitesse.
- Lancement des points d'entree `init_db.py`, `centre.py --headless` et `main.py` en processus distincts, avec controle des etats en base MariaDB.
- Essais supplementaires sur trois graines de trafic a 35 voitures/minute, avec missions repetees sur dix minutes : progression conservee et aucun chevauchement detecte.

### Version simplifiee du 12 octobre 2026

- 27 tests passes sous Python 3.12 avec une vraie base MariaDB de test, sans test ignore.
- Deux tests Qt ajoutent la verification des commandes et des missions jusqu'au centre TCP.
- Essai complementaire des deux fenetres avec TCP et MariaDB : missions, reset, pause/reprise et vitesse verifies.
- Inspection des trois onglets sur une fenetre de 960 x 680 pixels, en rendu hors ecran.
- Les tests de dix minutes de trafic, priorite, compensation et espacement restent valides.
- Les essais ont lieu localement ; le lancement sur les deux VM du binome reste a verifier en TP.

### Version du 19 octobre 2026 : quatre destinations et une VM

- 34 tests verifies sous Python 3.12 : suite de 33 tests passee avec MariaDB reelle, puis regression supplementaire de sortie bouchee passee. Les deux tests Qt ont ete rejoues apres le dernier ajustement des listes de choix.
- Verification des 16 couples de destinations des secours avec 40 voitures/minute : retours a la caserne, absence de chevauchement et poursuite du trafic.
- Verification du partage du carrefour Nord-Sud et Est-Ouest pour les voitures opposees allant tout droit ; maintien de l'exclusion pour les virages et du respect du rouge.
- Verification des probabilites 80/10/10 et de la conservation de la destination d'une mission active.
- Regression pour une sortie bouchee : la demande de priorite attend que la sortie puisse se degager ; un secours deja engage conserve sa priorite.
- Essais des commandes Qt et du lien avec le centre ; lancement des programmes avec MariaDB locale.
- Deploiement retenu : une seule VM, simulation et centre separes, connexion TCP sur 127.0.0.1:5000.

### Fluidification du 19 octobre 2026

- Base de travail : derniere version GitHub `fc1f302f6f5cdb5852efe4b55eeb5d14c4b94e08`, avec les quatre destinations et le deploiement sur une VM.
- Tirage des voitures : 95 % tout droit, 2,5 % gauche et 2,5 % droite.
- 26 tests de circulation passes sous Python 3.13 : 11 tests de simulation/feux, 7 de destinations et 8 nouvelles regressions de fluidite.
- Sur deux files preparees de six voitures tout droit, les 12 voitures s'engagent avant l'orange, contre 2 avec la version precedente. Essai reproduit sur Nord-Sud et Est-Ouest. Il mesure la capacite d'une file preparee, pas le nombre garanti a chaque cycle en trafic aleatoire.
- GAP = 44 reste verifie a chaque pas ; les virages et les secours restent exclusifs. Une sortie arretee retient les nouveaux vehicules et le changement d'axe attend tous les vehicules engages.
- Les 16 couples de destinations des secours ont ete testes avec du trafic a 40/min. La reservation anticipee de l'acces destination evite de bloquer la sortie du carrefour en attendant une voie entrante.
- Verification graphique locale hors ecran : affichage des convois sur les deux axes, lecture, pause et reinitialisation.
- Les modules TCP/MariaDB n'ont pas ete modifies ; les essais d'integration SQL n'ont pas ete rejoues pour cette modification du moteur.

### Plan integre du 20 octobre 2026

- Lancement reel de `init_db.py`, `centre.py --headless` et `main.py` en processus distincts : etats initiaux recus et conserves en base.
- 42 tests passes sous Python 3.12 avec MariaDB 10.11.14 reelle, sans test ignore.
- Verification complementaire des deux fenetres Qt avec TCP/MariaDB : etats, remise a zero, minuteur, vitesse et pause/reprise.
- Plan du croquis integre a la simulation lancee par `main.py` ; suppression de la fenetre et du lanceur de maquette separes.
- Controle graphique de 11 890 positions reparties sur les 20 parcours (12 voitures et 8 secours) : les centres restent sur les routes ou les aires dessinees.
- Controle des 16 couples de destinations a 40 voitures/minute : aucun chevauchement detecte, retour des deux secours et progression du trafic.
- Conservation du tirage 95/2,5/2,5 et des files tout droit simultanees au carrefour principal. Les raccordements secondaires sont exclusifs et peuvent ralentir la sortie des files.
- Regressions adaptees aux nouvelles coordonnees : quatre interventions et deux traversees par mission, sortie Nord bouchee, attente puis reprise devant un raccordement secondaire occupe.
- Inspection graphique locale hors ecran en 1320 x 900 et en 960 x 680, avec et sans affichage du trajet. Capture dans `apercu_plan.png`.

### Priorite sur tout le plan et accumulation du 20 octobre 2026

- Base de travail : derniere version GitHub `cbe0d790d1337daba2722a3fb49a3b43dea86551`, avec le plan du croquis integre.
- 52 tests hors MariaDB passes sous Python 3.13 : simulation/feux, destinations, fluidite, priorite secours, pixels de la carte, commandes Qt, vrais echanges TCP locaux et demonstration historique. Les deux tests SQL n'ont pas ete rejoues ; le stockage n'a pas change.
- Les 16 couples de destinations finissent avec du trafic a 40 voitures/minute, sans chevauchement et avec reprise des voitures apres les missions. Essai supplementaire a 60/min, avec missions Nord-Est et Est declenchees apres une minute de trafic deja accumule.
- Priorite verifiee a l'aller et au retour aux raccordements B/U/H/R/E sans feux, puis aux deux passages au feu principal pour les quatre destinations. Une voiture engagee degage et une voiture devant un secours peut liberer sa voie.
- Regression de deux secours rejoignant la meme file au retour : le suiveur suspend sa demande avant engagement pour laisser passer la tete de file, meme s'il avait demande le vert auparavant.
- Accumulation verifiee sur les deux axes : 22 s de vert prioritaire donnent 14 s de reserve opposee. Une reserve de 12 s est restituee en deux bonus de 8 s puis 4 s, avec un vert normal de l'autre ligne entre les deux. Pause, remise a zero et suspension/reprise de compensation verifiees.
- Controle graphique de 12 046 positions sur les 20 parcours : aucun centre dans l'herbe apres retrait du gris clair des routes. Les sept extremites ouvertes atteignent les bords ; aucune branche ajoutee. Affichage inspecte en 960 x 680 et 1280 x 820 ; capture actualisee dans `apercu_plan.png`.

### Grille a realiser en TP

| Essai | Action | Resultat attendu |
|---|---|---|
| Installation | Lancer les deux programmes | Deux fenetres et aucun traceback. |
| Circulation | Laisser avancer plusieurs voitures | Arret au rouge, files sans chevauchement et trajets termines. |
| Commandes | Pause, reprise, vitesses, reset | Temps et scene coherents ; reset publie disponible pour les deux secours. |
| Mission 01 | Envoyer seulement 01 | 01 occupe au centre ; 02 reste disponible. |
| Deux missions | Envoyer 02 pendant la mission 01 | Deux etats distincts ; aucune interruption de priorite en cours. |
| Compensation | Attendre tous les retours | Compensation seulement apres disponibilite des deux secours. |
| Nouvelle intervention | Declencher pendant la compensation | Solde suspendu et repris plus tard. |
| Liaison | Fermer la simulation | Liaison interrompue, derniers etats conserves. |
| Reconnexion | Relancer le client ou le centre | Reprise automatique et etats a jour. |
| Historique | Relancer le centre puis interroger MariaDB | Lignes historiques toujours presentes. |
| Duree | Laisser tourner dix minutes | Au plus 25 voitures, aucune fermeture ni blocage durable. |

Les tests automatises de demandes opposees utilisent aussi des positions initiales controlees. En demonstration libre, les deux secours peuvent emprunter des destinations differentes ; les demandes et les attentes dependent du trafic et des instants de depart.

Les essais locaux utilisent le reseau loopback : ils prouvent les echanges entre programmes mais ne constituent pas une installation realisee sur votre VM ; verifier son service MariaDB, son environnement Python et son affichage graphique avec le [guide de deploiement](deploiement-une-vm.md).
