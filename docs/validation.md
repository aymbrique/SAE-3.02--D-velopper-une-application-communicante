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
| `test_simulation.py` - 11 tests | Feux, transitions, degagement, arbitrage, seuils, ETA, compensation, interruption/reprise, files, arret au rouge et passage au vert. |
| Essais longs inclus dans la simulation | Dix minutes a 12/min et a 40/min, maximum de 25 voitures, controle des espacements, une seule traversee et progression du trafic. |
| `test_network.py` - 4 tests | Vraies sockets loopback, messages fragmentes/regroupes, validation, erreurs, coupures et redemarrages sans doublons. |
| `test_mariadb.py` - 2 tests | Transactions reelles, historique, numeros anciens, sessions, TCP avec MariaDB et redemarrage du centre. |

## Verification sur vos deux VM

### Resultats locaux du 6 octobre 2026

- 25 tests passes avec MariaDB 10.11.14 reelle, sous Python 3.12 puis Python 3.13.15.
- PyQt6 6.11.0, Qt 6.11.2 et PyMySQL 1.2.3 utilises pour ces essais.
- Verification des deux fenetres en mode graphique hors ecran : etats transmis, reset, minuteur, pause/reprise et vitesse.
- Lancement des points d'entree `init_db.py`, `centre.py --headless` et `main.py` en processus distincts, avec controle des etats en base MariaDB.
- Essais supplementaires sur trois graines de trafic a 35 voitures/minute, avec missions repetees sur dix minutes : progression conservee et aucun chevauchement detecte.

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

Les tests automatises de demandes opposees utilisent des positions initiales controlees. En demonstration libre, les deux missions empruntent le meme trajet aller/retour, decale dans le temps ; le chevauchement entre un aller et un retour depend de l'instant de depart choisi.

Les essais locaux utilisent le reseau loopback : ils prouvent les echanges entre programmes mais ne valident pas le reseau virtuel, le pare-feu ou l'affichage graphique de vos propres VM.
