# Vérifier le projet

Depuis la racine du projet, avec l'environnement Python activé :

```bash
python -m unittest discover -s tests -v
```

## Tests conservés

La suite conserve les fichiers suivants, soit **1 000 lignes** au total,
commentaires et lignes vides compris.

| Fichier | Lignes | Vérifications principales |
|---|---:|---|
| `test_simulation.py` | 334 | Cycle des feux, priorités, compensation et simulation générale |
| `test_circulation.py` | 234 | Files, espacement, entrée au carrefour et passage des secours |
| `test_arbitrage_secours.py` | 89 | Ordre de passage de deux secours et maintien de la priorité |
| `test_arrivees.py` | 80 | Apparition des voitures et choix des trajets |
| `test_reseau.py` | 108 | Messages TCP, coupures et reconnexion |
| `test_mariadb.py` | 76 | Persistance des états et échanges TCP avec la base de test |
| `test_carte.py` | 48 | Rendu de certains éléments de la carte |
| `controles_circulation.py` | 31 | Vérification commune des distances et des carrosseries |
| **Total** | **1 000** | |

`controles_circulation.py` fournit une fonction utilisée par plusieurs tests.
`test_mariadb.py` utilise également une fonction de `test_reseau.py`.

Cette sélection remplace la suite plus étendue. Certains cas particuliers de
rangement, de circulation secondaire, de retour à la caserne et de commandes
de l'interface ne disposent plus de leurs fichiers de tests dédiés. Les essais
manuels restent utiles pour vérifier ces situations.

## MariaDB

Les deux essais de `test_mariadb.py` sont optionnels et demandent une base
spécialement créée pour les tests, dont le nom se termine par `_test`.
Ils vident les tables de cette base : ne pas leur donner la base du projet.
Définir SAE_TEST_DB_NAME, SAE_TEST_DB_PASSWORD et, si nécessaire,
SAE_TEST_DB_HOST, SAE_TEST_DB_PORT et SAE_TEST_DB_USER avant de lancer la suite.

Le renommage des classes et attributs ne change ni les tables ni le protocole TCP.
Sans base de test configurée, les deux essais SQL sont signalés comme ignorés.

## Essai manuel dans PyCharm

1. Ouvrir `PycharmProjects/SAE302-GitHub`, puis `main.py`.
2. Lancer `python main.py --local` et cliquer sur Démarrer.
3. Augmenter le trafic, puis envoyer un secours : les voitures proches se rangent.
4. Vérifier qu'elles avancent en biais pour se ranger, s'arrêtent, puis reprennent sans se doubler.
5. Envoyer le second secours et essayer les quatre destinations.
6. À 25 voitures/minute, envoyer l'ambulance à l'ouest, puis le camion lorsqu'elle revient près de la caserne : les deux missions doivent se terminer.
7. Observer une voiture qui tourne : une suivante de la même approche peut entrer en ralentissant.
8. Vérifier pause, reprise, vitesse et Recommencer.

Sur Debian, vérifier aussi le centre, MariaDB et la communication selon
le guide de déploiement. Un essai local ne remplace pas la vérification sur la VM.
