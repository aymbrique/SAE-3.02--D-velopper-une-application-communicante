# SAE302 — Facture Sucrée

Projet de simulation de trafic à Colmar d’Aymeri et Selim. La version actuelle contient une fenêtre PyQt6 vide, intitulée **Simulation**, de 1 000 × 700 pixels.

Le [cahier des charges](docs/Cahier_des_charges_SAE302.pdf) décrit les fonctionnalités à développer : circulation, feux, priorité de deux véhicules de secours et communication TCP avec un centre de coordination.

## Récupérer le projet

```bash
git clone https://github.com/aymbrique/SAE-3.02--D-velopper-une-application-communicante.git SAE302-Facture-Sucree
cd SAE302-Facture-Sucree
```

## Prérequis

- Python 3.13.
- PyCharm pour ouvrir et lancer le projet.

## Installation

Depuis le dossier du projet, créer un environnement propre à ce projet puis installer les versions enregistrées dans `requirements.txt`.

### macOS / Linux

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### Windows — PowerShell

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

L’environnement `.venv` se recrée sur chaque ordinateur et reste exclu du dépôt Git.

## Ouvrir et lancer dans PyCharm

1. Ouvrir le dossier `SAE302-Facture-Sucree` comme projet.
2. Sélectionner l’interpréteur Python de l’environnement existant :
   - macOS / Linux : `.venv/bin/python` ;
   - Windows : `.venv\Scripts\python.exe`.
3. Ouvrir `main.py`, puis lancer ce fichier avec **Run**.

Une fenêtre vide **Simulation** doit apparaître. Fermer cette fenêtre pour terminer le programme.

Pour lancer depuis le terminal activé sur macOS / Linux :

```bash
python main.py
```

Sur Windows, sans activation de l’environnement :

```powershell
.\.venv\Scripts\python.exe main.py
```

## Organisation

```text
SAE302-Facture-Sucree/
├── README.md
├── requirements.txt
├── .gitignore
├── main.py
├── src/
│   ├── __init__.py
│   ├── gui/
│   │   └── __init__.py
│   ├── simulation/
│   │   └── __init__.py
│   ├── network/
│   │   └── __init__.py
│   └── models/
│       └── __init__.py
├── tests/
└── docs/
```

| Dossier | Rôle prévu |
| --- | --- |
| `src/gui/` | Fenêtres et affichage PyQt6 |
| `src/simulation/` | Déplacements, circulation et feux |
| `src/models/` | Véhicules, feux et intersections |
| `src/network/` | Sockets TCP et états des véhicules de secours |
| `tests/` | Tests Python |
| `docs/` | Cahier des charges, schémas et documentation |

## État et prochaine étape

Cette première base contient la structure du projet, la fenêtre PyQt6 et le cahier des charges. Elle est publiée dans ce dépôt GitHub. La circulation, les feux, les véhicules de secours et le réseau ne sont pas encore implémentés. Le dossier `tests/` est réservé aux futurs tests ; aucun test automatisé n’est encore présent.

La prochaine étape sera d’afficher un carrefour fixe avec `QGraphicsScene` et `QGraphicsView`. Les véhicules, feux et communications réseau viendront ensuite.
