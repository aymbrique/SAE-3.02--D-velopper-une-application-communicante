# SAE302 - Circulation, secours et coordination

Projet de **Aymeri et Selim**, BUT Reseaux & Telecommunications : une simulation de circulation a Colmar, un centre de coordination TCP et une base **MariaDB**.

L'interface utilise des formes simples et les boutons standards de Qt. Pour comprendre le code progressivement : [guide de la version simplifiee](docs/code-simple.md).

Le plan du croquis est integre directement dans `main.py` : routes grises, terrain vert, carrefour a feux a gauche, caserne au nord-ouest et quatre aires d'intervention. Les routes existantes vont jusqu'aux bords ; les aires gris clair s'arretent au bord de la chaussee. Les vehicules empruntent les routes de ce plan.

![Plan de la simulation principale](docs/apercu_plan.png)

## Commencer

**Suivre le [guide de deploiement sur une VM Linux](docs/deploiement-une-vm.md).** Il explique le fonctionnement, les sockets locales, MariaDB, l'installation, PyCharm et les verifications.

Une seule VM avec bureau graphique heberge tout le projet :

| Element | Commande | Role |
|---|---|---|
| Simulation | `python main.py` | Carte et client TCP |
| Centre | `python centre.py` | Serveur TCP et affichage du suivi |
| MariaDB | Service Linux `mariadb` | Derniers etats et historique durable |

Les programmes restent separes : le client joint le centre sur **127.0.0.1:5000**, puis le centre joint MariaDB sur **127.0.0.1:3306**. Le centre ecoute en local par defaut. Les sockets fonctionnent aussi entre deux programmes d'une meme machine.

## Fonctions implementees

- Carte 2D sur fond vert, zoom, deplacement, affichage des trajets et compteurs.
- Generation de voitures depuis l'exterieur des bords visibles : 12/min par defaut, reglage de 0 a 60/min, 25 voitures au maximum. 50 % des tirages viennent du Nord, le reste est reparti entre les trois autres origines. Les virages gardent 95 % tout droit, 2,5 % a gauche et 2,5 % a droite.
- Deplacement calcule a chaque pas de simulation, arret aux feux, files et espacement minimal. Une voiture engagee finit sa traversee.
- Cycle normal 8 s de vert, 1 s d'orange, au moins 1 s de rouge simultane. Les voitures allant tout droit sur le meme axe peuvent traverser ensemble, en sens opposes et en file avec un ecart minimal de 44 unites. Les virages et les secours restent exclusifs.
- Choix du secours 01 ou 02 et du point Ouest (1), Sud-Ouest (2), Nord-Est (3) ou Est (4) ; trajet aller/intervention/retour, etats disponibles/occupes et estimations de duree. Chaque trajet franchit le carrefour principal a l'aller et au retour.
- Demande de priorite au feu a 150 m ou moins **ou** 10 s d'arrivee ou moins, aller et retour compris. L'autre vert est interrompu des la demande : 1 s d'orange, au moins 1 s de tout rouge et degagement des vehicules engages, puis vert pour le secours jusqu'a sa sortie. Arbitrage par anciennete de mission, puis de demande, puis identifiant. Aux raccordements sans feux, les voitures cedent egalement le passage aux secours occupes ; un vehicule deja engage ou devant le secours peut degager.
- Temps d'accumulation affiche par ligne horizontale et verticale : tout depassement du vert prioritaire au-dela de 8 s est conserve pour l'autre ligne. Compensation uniquement quand tous les secours sont disponibles, au plus 8 s supplementaires par vert (16 s au total), avec report du solde sur les cycles suivants et suspension/reprise lors d'une nouvelle mission.
- TCP en threads, JSON delimite par lignes, numeros de mise a jour, accuses de reception, reconnexion et suivi des coupures sans changement automatique de l'etat metier.
- MariaDB : transactions, historique, rejet des doublons et des anciens numeros d'une meme session. Le centre affiche les 100 dernieres mises a jour.

## Essayer uniquement la simulation

Avec Python 3.13 et les bibliotheques graphiques Linux installees :

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py --local
```

Cliquer sur **Demarrer**, choisir le vehicule et le point d'intervention, puis **Envoyer en intervention**. Le mode `--local` n'a besoin ni de MariaDB ni du centre, mais ne valide pas la communication.

Pour une installation complete ou un essai des deux programmes sur un seul PC, suivre le [guide](docs/deploiement-une-vm.md).

## Organisation

```text
main.py                          Application de simulation (VM unique)
centre.py                        Centre TCP, graphique ou sans fenetre (meme VM)
init_db.py                       Creation des tables MariaDB
config.example.ini               Exemple de configuration sans mot de passe
src/config.py                    Lecture de la configuration locale
src/models/layout.py             Geometrie de la carte et des trajets
src/models/vehicle.py            Vehicules et instantanes pour le dessin
src/models/route.py              Interpolation des trajets
src/simulation/engine.py         Deplacements, files, missions et temps simule
src/simulation/lights.py         Automate des feux, priorite et compensation
src/interface/                   Fenetres de simulation et de coordination
src/reseau/                      Client, serveur et protocole TCP/JSON
src/stockage/mariadb.py           Requetes SQL et transactions
sql/                             Creation des tables
tests/                           Tests metier, TCP et integration MariaDB
docs/                            Installation, architecture, utilisation et validation
```

L'ancien `src/simulation/demo.py` est conserve comme scenario historique avec ses tests. Il n'est plus utilise par l'application.

## Tests et limites

```bash
python -m unittest discover -s tests -v
```

Les tests MariaDB sont actives uniquement avec une base de test dediee : voir [validation](docs/validation.md). Les essais automatises ne remplacent pas la verification du reseau, de l'affichage et du pare-feu sur votre VM.

Le modele reste volontairement simple : partage du carrefour limite aux files de voitures allant tout droit sur le meme axe, raccordements sans feux traverses un vehicule a la fois, vitesses constantes et durees estimees hors attente. Le protocole est destine au reseau de TP, sans authentification ni chiffrement. Les messages non confirmes restent en memoire du client jusqu'a la reconnexion ; fermer ce client avant leur envoi perd cette file.

Le [cahier des charges](docs/Cahier_des_charges_SAE302.pdf) reste la reference. Le stockage MariaDB et le lancement sur une VM completent ce document a la demande du binome.

- [Utiliser les deux interfaces](docs/interface.md)
- [Comprendre le code et les changements](docs/architecture.md)
- [Tests et verification sur la VM](docs/validation.md)
