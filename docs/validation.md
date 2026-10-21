# Vérifier le projet

Depuis la racine du projet, avec l'environnement Python activé :

```bash
python -m unittest discover -s tests -v
```

## Ce qui est vérifié

- Déplacements par pas fixes, rouge/orange, files, espacement et reprise du trafic.
- Passage des voitures compatibles au vert, y compris derrière un virage.
- Rangement en avançant, orientation pendant la manœuvre, arrêt et réinsertion.
- Conservation de l'ordre dans la file pendant le rangement et la reprise.
- Secours plus rapides et passage au vert sans réservation inutile de tout le carrefour.
- Absence de contact entre les rectangles orientés, vérifiée avec les polygones Qt.
- Départ dans une file de onze voitures au nord et retour à la caserne.
- Deux secours simultanés et les seize couples de destinations à 40 voitures/minute.
- Dix minutes à 60 voitures/minute, six interventions successives, graines 51 et 302.
- Retour des missions, progression du trafic et durée limitée du tout rouge dans ces scénarios.
- Arrivée à un point d'intervention ou en fin de trajet à une erreur flottante près.
- Annulation des réserves opposées et restitution par quarts aux prochains verts.
- Boutons, minuteur, affichage des trajets et échanges TCP réels sur l'ordinateur.

Les régressions se trouvent dans `tests/test_rangement.py` et
`tests/test_priorite_fluide.py`.
Les contrôles géométriques communs sont dans `tests/traffic_checks.py`.

## MariaDB

Les deux essais de `test_mariadb.py` sont optionnels et demandent une base
spécialement créée pour les tests, dont le nom se termine par `_test`.
Ils vident les tables de cette base : ne pas leur donner la base du projet.
Définir SAE_TEST_DB_NAME, SAE_TEST_DB_PASSWORD et, si nécessaire,
SAE_TEST_DB_HOST, SAE_TEST_DB_PORT et SAE_TEST_DB_USER avant de lancer la suite.

Le rangement des voitures et la réorganisation des fichiers ne changent pas
les tables ni le protocole TCP. Les essais SQL ne sont pas rejoués pour cette modification.

## Essai manuel dans PyCharm

1. Ouvrir `PycharmProjects/SAE302-GitHub`, puis `main.py`.
2. Lancer `python main.py --local` et cliquer sur Démarrer.
3. Augmenter le trafic, puis envoyer un secours : les voitures proches se rangent.
4. Vérifier qu'elles avancent en biais pour se ranger, s'arrêtent, puis reprennent sans se doubler.
5. Envoyer le second secours et essayer les quatre destinations.
6. Observer une voiture qui tourne : une suivante de la même approche peut entrer en ralentissant.
7. Vérifier pause, reprise, vitesse et Recommencer.

Sur Debian, vérifier aussi le centre, MariaDB et la communication selon
le guide de déploiement. Un essai local ne remplace pas la vérification sur la VM.
