# SAE302 — Circulation et secours

Projet d’Aymeri et Selim.

Simulation 2D d'un carrefour, de voitures et de deux véhicules de secours.
Le centre reçoit les états des secours par TCP et les conserve dans MariaDB.

## Ouvrir le bon projet

Dans PyCharm, ouvrir le dossier **SAE302-GitHub** dans `PycharmProjects`.
Le dossier `SAE302-Facture-Sucree` présent sur ce poste est une autre copie.

Le modèle des voitures et des secours est dans **`src/modeles/vehicules.py`**.
L'arborescence complète se trouve dans [ARBORESCENCE.txt](ARBORESCENCE.txt).

## Se repérer

| Fichier ou dossier | Rôle |
|---|---|
| `main.py` | Démarre la simulation. |
| `centre.py` | Démarre le centre TCP et son suivi. |
| `init_db.py` | Prépare les tables de la base. |
| `src/modeles/vehicules.py` | État, position, vitesse et rangement des véhicules. |
| `src/modeles/plan.py` | Routes, destinations et trajets. |
| `src/modeles/trajet.py` | Position et orientation le long d'un trajet. |
| `src/simulation/moteur.py` | Déplacements, files et interventions. |
| `src/simulation/priorite.py` | Rangement et gabarits des véhicules. |
| `src/simulation/feux.py` | Feux et secondes de compensation. |
| `src/interface/` | Carte et fenêtres. |
| `src/reseau/` | Client, serveur et messages TCP. |
| `src/stockage/` et `sql/` | Accès MariaDB et tables. |
| `tests/` | Vérifications automatiques. |
| `exemples/` | Ancienne animation, conservée à part. |

## Lancer la simulation seule

Dans le terminal du projet :

```bash
source .venv/bin/activate
python main.py --local
```

Cliquer sur **Démarrer**, choisir le secours et sa destination, puis sur
**Envoyer en intervention**. Le débit et la vitesse se règlent en haut.

Pour installer le projet sur Debian et utiliser le centre avec MariaDB :
[guide pour une VM](docs/deploiement-une-vm.md).

## Circulation

- Les voitures apparaissent aux bords du plan, avec davantage d'arrivées au nord.
- Au feu principal : 95 % tout droit, 2,5 % à gauche et 2,5 % à droite.
  Des bifurcations rares existent aussi sur les routes du bas et du milieu.
- À l'approche d'un secours, les voitures rejoignent une place libre sur le bord
  droit de leur voie, s'arrêtent, puis se réinsèrent après son passage.
  Une voiture engagée dans un carrefour ou un virage finit de le dégager.
- Au vert, une file peut suivre une voiture qui tourne. Les suivantes ralentissent
  pendant la manœuvre. Les trajectoires qui se croisent passent successivement.
- Le départ et le retour à la caserne demandent le vert vertical pour vider la file.
- Les réserves de temps des deux axes s'annulent entre elles. Un quart du solde
  restant prolonge chaque prochain vert normal de l'axe concerné.

Les véhicules gardent 44 unités entre leurs centres en circulation normale.
Lors d'un passage à côté d'une voiture rangée, le contrôle porte sur les
carrosseries orientées, avec une marge de 3 unités : les rectangles ne se touchent pas.

## Vérifier le projet

```bash
python -m unittest discover -s tests -v
```

Les essais MariaDB nécessitent une base de test dédiée. Voir
[validation](docs/validation.md), [architecture](docs/architecture.md) et
[utilisation](docs/interface.md).
