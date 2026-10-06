# SAE302 - Circulation, secours et coordination

Projet de **Aymeri et Selim**, BUT Reseaux & Telecommunications : une simulation de circulation a Colmar, un centre de coordination distant et une base **MariaDB**.

## Commencer

**Suivre le [guide de lancement des deux VM Linux](docs/lancement-linux.md).** Il contient l'installation de Python, MariaDB, la creation de la base, les reglages reseau et les commandes exactes.

| Machine | Programme | Role |
|---|---|---|
| VM 1 | `python main.py --host IP_VM2` | Simulation graphique et client TCP |
| VM 2 | `python centre.py` | Centre de coordination, serveur TCP et acces MariaDB |
| VM 2 | Service MariaDB | Dernier etat des secours et historique durable |

Le port applicatif est **5000/TCP**. MariaDB reste sur **127.0.0.1:3306**, accessible localement par le centre. La VM 1 ne se connecte pas directement a MariaDB.

## Fonctions implementees

- Carte 2D, zoom, deplacement, affichage des trajets et compteurs.
- Generation de voitures : 12/min par defaut, reglage de 0 a 60/min, 25 voitures au maximum, trois directions possibles.
- Deplacement calcule a chaque pas de simulation, arret aux feux, files et espacement minimal. Une voiture engagee finit sa traversee.
- Cycle normal 8 s de vert, 1 s d'orange, au moins 1 s de rouge simultane. Un seul vehicule traverse le carrefour a la fois.
- Deux secours declenchables separement, trajet aller/intervention/retour, etats disponibles/occupes et estimations de duree.
- Demande de priorite a 150 m ou moins **ou** 10 s d'arrivee ou moins. Arbitrage par anciennete de mission, puis de demande, puis identifiant ; maintien jusqu'a la sortie.
- Memorisation du vert supplementaire, compensation uniquement quand tous les secours sont disponibles, vert compensatoire de 16 s maximum et suspension/reprise lors d'une nouvelle mission.
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

Cliquer sur **Demarrer**, puis sur **Envoyer le secours 01** ou **02**. Le mode `--local` n'a besoin ni de MariaDB ni du centre, mais ne valide pas la communication.

Pour une installation complete ou un essai des deux programmes sur un seul PC, suivre le [guide](docs/lancement-linux.md).

## Organisation

```text
main.py                          Application de simulation (VM 1)
centre.py                        Centre TCP, graphique ou sans fenetre (VM 2)
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

Les tests MariaDB sont actives uniquement avec une base de test dediee : voir [validation](docs/validation.md). Les essais automatises ne remplacent pas la verification du reseau, de l'affichage et du pare-feu sur vos deux VM.

Le modele reste volontairement simple : un seul passage dans le carrefour, acces lateraux reserves temporairement pour les secours, vitesses constantes et durees estimees hors attente. Le protocole est destine au reseau de TP, sans authentification ni chiffrement. Les messages non confirmes restent en memoire du client jusqu'a la reconnexion ; fermer ce client avant leur envoi perd cette file.

Le [cahier des charges](docs/Cahier_des_charges_SAE302.pdf) reste la reference. Le stockage MariaDB et le lancement sur deux VM completent ce document a la demande du binome.

- [Utiliser les deux interfaces](docs/interface.md)
- [Comprendre le code et les changements](docs/architecture.md)
- [Tests et verification sur les VM](docs/validation.md)
