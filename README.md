# SAE302 — Circulation et secours

Projet d’Aymeri et Selim.

Simulation 2D d'un carrefour, de voitures et de deux véhicules de secours.
Le centre reçoit les états des secours par TCP et les conserve dans MariaDB.

## Prendre connaissance du projet

Pour comprendre l’architecture du projet, l’organisation des fichiers et le rôle
des différentes parties du programme, consultez le fichier
[architecture.md](docs/architecture.md), situé dans le dossier `docs`.

## Déploiement du projet

Si vous disposez de vos deux machines virtuelles et souhaitez déployer le projet,
suivez le document [deploiement-projet.md](docs/deploiement-projet.md), situé dans
le dossier `docs`. Il présente la configuration réseau, l’installation des logiciels,
la préparation de MariaDB et le lancement de la simulation et du centre de suivi.

## Lancer la simulation sur PyCharm (facultatif)

Si vous souhaitez essayer la simulation dans PyCharm sans connexion au centre de suivi,
vous pouvez utiliser le mode local. Ce mode ne nécessite pas de lancer le serveur
`centre.py` ni MariaDB.

Dans le terminal de PyCharm, avec l’environnement Python `.venv` activé, exécutez :

```bash
python main.py --local
```

Pour le déploiement complet sur deux VM avec le centre de suivi et MariaDB,
suivez le [guide de déploiement](docs/deploiement-projet.md).

Cliquez sur **Démarrer**, choisissez le véhicule de secours et sa destination,
puis cliquez sur **Envoyer en intervention**. Le débit et la vitesse se règlent
en haut de la fenêtre.

## Vérifier le projet

Dans le terminal du projet, avec l’environnement Python activé :

```bash
python -m unittest discover -s tests -v
```

Les essais MariaDB nécessitent une base de test dédiée.
