# Déployer SAE302 sur une seule VM Linux

Ce guide explique d'abord le fonctionnement, puis l'installation et le lancement. Il cible **Debian 13 avec un bureau graphique**, sur une VM x86-64. Les programmes utilisent Python, PyQt6 et MariaDB. Les commandes sont à saisir dans le terminal de la VM, pas dans celui de l'ordinateur hôte.

## 1. Comprendre ce qui fonctionne dans la VM

Une seule VM héberge trois éléments distincts :

| Élément | Rôle | Lancement |
|---|---|---|
| Simulation | Affiche la carte, déplace les voitures, gère les feux et les missions | `python main.py` |
| Centre de coordination | Reçoit les états par socket TCP et affiche le suivi | `python centre.py` |
| Serveur MariaDB | Conserve les derniers états et leur historique sur disque | Service Linux `mariadb` |

La simulation et le centre restent **deux programmes séparés**, même sur une seule machine. Les sockets restent utilisées : la simulation se connecte au centre à l'adresse **127.0.0.1, port 5000**. Le centre se connecte ensuite à MariaDB à **127.0.0.1, port 3306**.

`127.0.0.1` désigne la machine sur laquelle le programme s'exécute. Le port indique à quel service parler : 5000 pour notre application, 3306 pour MariaDB. Aucune adresse IP de seconde VM n'est nécessaire. Aucun transfert de port VirtualBox n'est nécessaire pour ces échanges locaux. Un accès Internet sert à installer les logiciels et à récupérer le dépôt.

### Exemple : envoyer l'ambulance à l'Est

1. Dans la simulation, choisir **02 - Ambulance**, puis **Est** et cliquer sur **Envoyer en intervention**.
2. Le moteur mémorise la destination et passe le secours à l'état `occupe`.
3. Le client envoie au centre un message JSON contenant l'identifiant, l'état, un numéro de mise à jour et une session.
4. Le centre enregistre le dernier état et ajoute une ligne d'historique dans MariaDB.
5. Après l'enregistrement, il confirme la réception au client : c'est l'ACK.
6. Le secours suit son trajet, demande la priorité près du carrefour, attend 8 secondes simulées au point d'intervention puis retourne à la caserne.
7. Au retour, l'état `disponible` suit le même chemin jusqu'à MariaDB.

**La destination et les positions restent dans la simulation.** Le protocole et la base enregistrent actuellement les états disponible/occupé, pas les destinations ni un historique de toutes les coordonnées. Le centre ne pilote pas les feux.

### Circulation et missions

- Quatre points : Nord, Sud, Est et Ouest. Les deux véhicules peuvent être envoyés vers n'importe lequel.
- Le point Nord est du côté de la caserne : son trajet ne traverse pas le carrefour central.
- Une mission déjà commencée conserve sa destination. Un véhicule occupé ne peut pas être envoyé de nouveau.
- À chaque choix aléatoire de direction : 95 % tout droit, 2,5 % à gauche et 2,5 % à droite. Un petit échantillon n'aura pas forcément exactement ces proportions.
- Les voitures allant tout droit sur le même axe peuvent traverser ensemble au vert, dans les deux sens et en file. Chaque suivante conserve au moins 44 unités entre centres, sans attendre la sortie complète de son leader. Les virages et les secours restent contrôlés séparément.
- Une sortie encombrée ou un accès réservé peut obliger à attendre même au vert. Un secours ne maintient pas une priorité avant d'entrer si sa sortie est bloquée.
- Pause, reprise, vitesse, débit, affichage des trajets et remise à zéro restent disponibles.

### Ce qui est conservé et ce qui ne l'est pas

| Donnée | Où ? | Après fermeture ? |
|---|---|---|
| Positions, destination et progression des missions | Mémoire de la simulation | Perdues : la scène repart à zéro |
| Dernier état reçu de chaque secours | Table `vehicules` | Conservé |
| Historique des changements acceptés | Table `historique_etats` | Conservé |
| Messages pas encore confirmés | File en mémoire du client | Conservés pendant une coupure, perdus si le client est fermé |

Recommencer la scène annule les missions et envoie disponible pour les deux secours ; cela n'efface pas l'historique. Fermer la simulation indique une liaison interrompue au centre sans transformer automatiquement les derniers états occupés en disponibles. Au nouveau lancement, la nouvelle simulation annonce ses deux secours disponibles.

## 2. Préparer la VM

Prévoir un bureau graphique, un compte autorisé à utiliser `sudo` et Internet. Une allocation de départ raisonnable pour le TP est 2 processeurs virtuels, 4 Go de RAM et 20 Go de disque ; ce sont des indications pratiques, pas des minima mesurés.

Vérifier le système :

```bash
cat /etc/os-release
python3 --version
```

Les commandes ci-dessous utilisent les paquets de Debian 13, dont Python 3.13. Ne pas remplacer le Python système sur une autre distribution pour suivre ce guide.

```bash
sudo apt update
sudo apt install git python3 python3-venv python3-pip nano mariadb-server mariadb-client libegl1 libgl1 libxcb-cursor0 libxkbcommon-x11-0
sudo systemctl enable --now mariadb
sudo systemctl status mariadb --no-pager
```

Le résultat attendu pour MariaDB est `active (running)`. `enable` prévoit son démarrage avec la VM ; `--now` le lance immédiatement. Les fenêtres Python devront être lancées depuis la session graphique.

## 3. Récupérer le projet

Première installation, depuis votre dossier personnel :

```bash
cd ~
git clone https://github.com/aymbrique/SAE-3.02--D-velopper-une-application-communicante.git SAE302
cd ~/SAE302
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

`.venv` contient les bibliothèques Python de ce projet. L'activer permet à `python` de les retrouver, sans installer les bibliothèques dans le Python système. Ne pas utiliser `sudo pip`.

Si le dépôt est déjà présent, entrer dans son dossier réel, enregistrer vos changements dans Git puis utiliser `git pull --ff-only`. Ne pas recloner par-dessus un projet existant. Les exemples suivants supposent le dossier `~/SAE302` : adapter ce chemin si votre dossier porte un autre nom.

## 4. Créer la base et le compte applicatif

Pour une première installation, ouvrir la console SQL :

```bash
sudo mariadb
```

Dans cette console, exécuter les instructions ci-dessous en remplaçant `VOTRE_MOT_DE_PASSE` par un mot de passe choisi pour le projet :

```sql
CREATE DATABASE sae302 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'sae302'@'127.0.0.1' IDENTIFIED BY 'VOTRE_MOT_DE_PASSE';
GRANT SELECT, INSERT, UPDATE, CREATE ON sae302.* TO 'sae302'@'127.0.0.1';
EXIT;
```

Le compte applicatif s'appelle `sae302` ; il travaille uniquement sur la base `sae302`. L'application n'utilise pas `root`. Le suffixe `@'127.0.0.1'` correspond à la connexion TCP locale utilisée par Python.

**Si vous avez déjà créé cette base et ce compte, les conserver.** Ne pas supprimer une base pour répéter ces commandes. Si vous devez changer un mot de passe existant :

```sql
ALTER USER 'sae302'@'127.0.0.1' IDENTIFIED BY 'NOUVEAU_MOT_DE_PASSE';
```

Cette commande se saisit dans `sudo mariadb` ; reporter ensuite le même mot de passe dans la configuration.

## 5. Configurer et initialiser les tables

Dans le terminal du projet :

```bash
cd ~/SAE302
source .venv/bin/activate
cp -n config.example.ini config.ini
nano config.ini
```

`cp -n` conserve un fichier déjà existant. Voici le contenu à utiliser :

```ini
[reseau]
serveur = 127.0.0.1
port = 5000

[mariadb]
host = 127.0.0.1
port = 3306
database = sae302
user = sae302
password = VOTRE_MOT_DE_PASSE
```

Mettre le mot de passe réel, sans guillemets autour de la valeur INI. Dans nano : **Ctrl+O**, Entrée, puis **Ctrl+X**. `config.ini` est exclu de Git ; il ne doit pas être ajouté au dépôt. Si `SAE_DB_PASSWORD` est définie dans le terminal, elle remplace le mot de passe du fichier.

```bash
python init_db.py
```

Résultat attendu : `Tables MariaDB pretes : vehicules et historique_etats.` Cette commande peut être relancée : elle crée les tables absentes, sans vider celles qui existent.

## 6. Lancer les deux programmes sur cette même VM

**Terminal 1 : centre**

```bash
cd ~/SAE302
source .venv/bin/activate
python centre.py --bind 127.0.0.1 --port 5000
```

Laisser cette fenêtre et ce terminal ouverts. Au premier lancement, le centre peut afficher des états inconnus, puis attend la simulation. Les lancements suivants affichent les derniers états conservés en base.

**Terminal 2 : simulation**

```bash
cd ~/SAE302
source .venv/bin/activate
python main.py --host 127.0.0.1 --port 5000
```

Le centre doit recevoir les deux états `disponible`. Dans la simulation, l'onglet **Reseau** doit indiquer une connexion au centre. Cliquer sur **Demarrer** pour faire avancer les voitures.

Les deux fenêtres sont celles de deux processus Python distincts sur une seule VM. MariaDB fonctionne en arrière-plan comme troisième service. Ne pas ajouter `--local` pour une démonstration complète : cette option désactive la connexion TCP.

Pour un centre sans fenêtre, remplacer sa commande par :

```bash
python centre.py --bind 127.0.0.1 --headless
```

Ce mode conserve les données dans MariaDB mais n'affiche pas le tableau. L'arrêter avec Ctrl+C. Le mode simulation seul reste disponible pour travailler sur la carte : `python main.py --local`.

## 7. Vérifier le fonctionnement

1. Démarrer le trafic. Vérifier que la zone hors routes est verte.
2. Choisir 01, puis Est et envoyer. Vérifier que seul 01 devient occupé au centre.
3. Choisir 02, puis Ouest et envoyer pendant la première mission.
4. Dans **Secours**, lire les destinations et les étapes. Dans **Afficher un trajet**, sélectionner un des huit parcours de secours pour le visualiser.
5. Attendre les retours : les deux états redeviennent disponibles. Tester aussi Nord et Sud.
6. Observer les files allant tout droit : les voitures opposées et leurs suivantes peuvent être engagées simultanément, avec les distances de sécurité conservées. Un arrêt au rouge, une file ou un secours peut naturellement empêcher cette situation à un instant donné.
7. Tester pause/reprise, vitesses et Recommencer. Les feux et les missions restent cohérents.
8. Fermer puis rouvrir le centre en laissant la simulation ouverte : elle se reconnecte et renvoie les messages en attente.
9. Consulter l'historique SQL pour vérifier la persistance.

Ouvrir un troisième terminal pour consulter MariaDB :

```bash
mariadb --protocol=TCP -h 127.0.0.1 -u sae302 -p sae302
```

Après saisie du mot de passe :

```sql
SHOW TABLES;
SELECT identifiant, etat, numero, recu_le FROM vehicules;
SELECT id, identifiant, etat, numero, recu_le
FROM historique_etats ORDER BY id DESC LIMIT 20;
EXIT;
```

Les dates SQL sont en UTC et correspondent au temps réel. Les durées de mission affichées sont en temps simulé : à x2, elles avancent deux fois plus vite.

Les tests automatiques se lancent dans l'environnement du projet :

```bash
python -m unittest discover -s tests -v
```

Les tests graphiques utilisent un rendu hors écran. Les deux tests MariaDB sont ignorés sans base de test dédiée : ce n'est pas une validation de la base de démonstration. Voir [validation.md](validation.md) pour les activer sur une base distincte, dont les tables de test seront vidées.

## 8. Utiliser PyCharm dans la VM

1. Ouvrir le dossier `SAE302` dans PyCharm.
2. Choisir comme interpréteur le fichier `~/SAE302/.venv/bin/python`.
3. Utiliser la racine du projet comme répertoire de travail.
4. Lancer `init_db.py` une fois après la configuration.
5. Lancer `centre.py`, puis `main.py` dans deux exécutions distinctes. Garder le centre actif.
6. Avec `config.ini` réglé sur `127.0.0.1`, aucun argument n'est nécessaire : le centre écoute localement par défaut.

PyCharm peut aussi être remplacé par les deux terminaux : l'application n'en dépend pas.

## 9. Mettre à jour et relancer

Fermer les deux applications avant une mise à jour du code. Dans le projet :

```bash
git status
```

Si vous avez des modifications personnelles, les enregistrer dans un commit avant la mise à jour. Puis :

```bash
git pull --ff-only
source .venv/bin/activate
python -m pip install -r requirements.txt
python init_db.py
```

En cas de refus Git ou de conflit, ne pas forcer ni effacer les fichiers : résoudre les différences avec votre binôme. La mise à jour ne remplace pas votre `config.ini` et ne supprime pas les données MariaDB.

Après chaque démarrage de la VM, vérifier MariaDB puis relancer le centre et la simulation dans les deux terminaux. Les programmes Python ne se lancent pas automatiquement avec la VM.

## 10. Dépannage

| Problème | Que vérifier ? |
|---|---|
| `No module named PyQt6` ou `pymysql` | Activer `.venv`, réinstaller `requirements.txt` et vérifier l'interpréteur PyCharm. |
| Erreur `xcb`, aucune fenêtre | Ouvrir une session graphique, installer les bibliothèques Qt de l'étape 2. Diagnostic : `QT_DEBUG_PLUGINS=1 python main.py --local`. |
| MariaDB inaccessible | `sudo systemctl status mariadb --no-pager`, puis `sudo systemctl start mariadb` si nécessaire. |
| `Access denied` | Vérifier utilisateur, mot de passe et compte `sae302@127.0.0.1`. Tester la connexion SQL manuellement. |
| Base ou table inconnue | Créer la base à l'étape 4, puis exécuter `python init_db.py`. |
| Port 5000 déjà utilisé | Une autre instance du centre tourne peut-être. La fermer ; ne garder qu'un centre. |
| Liaison interrompue | Centre ouvert, même port des deux côtés, adresse `127.0.0.1`, absence de `--local`. |
| Bouton d'envoi désactivé | Le véhicule sélectionné est occupé. Sélectionner l'autre ou attendre son retour. |
| Mission immobile | Cliquer sur Demarrer/Reprendre ; une mission peut être envoyée pendant la pause. |
| Voitures arrêtées au vert | Sortie occupée, espacement, virage incompatible ou accès de secours réservé. |

Pour vérifier les ports en écoute :

```bash
ss -ltn
```

Chercher `127.0.0.1:5000` pour le centre et le port `3306` pour MariaDB. Il n'est pas nécessaire d'ouvrir ces ports à l'extérieur pour ce déploiement.

## 11. Références et portée de la validation

- [Paquet Python venv sur Debian 13](https://packages.debian.org/trixie/python3-venv)
- [Paquet MariaDB Server sur Debian 13](https://packages.debian.org/trixie/mariadb-server)
- [Dépendances graphiques Qt sous Linux](https://doc.qt.io/qt-6/linux-requirements.html)
- [Création de comptes MariaDB](https://mariadb.com/docs/server/reference/sql-statements/account-management-sql-statements/create-user)
- [Droits SQL MariaDB](https://mariadb.com/docs/server/reference/sql-statements/account-management-sql-statements/grant)

Les essais locaux contrôlent le code, les échanges TCP et MariaDB. Ils ne constituent pas une installation effectuée sur votre VM personnelle. La grille de l'étape 7 sert à valider cette dernière.
