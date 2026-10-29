# SAE302 — Déploiement du projet

Guide prévu pour VirtualBox, avec une VM sur chacun de vos deux ordinateurs connectés au même réseau.

## 1. Comprendre le fonctionnement

| Machine | Ce qu’elle lance | Son rôle |
|---|---|---|
| VM 1 — Simulation | `main.py` | Afficher la ville, gérer la circulation, les feux et les interventions |
| VM 2 — Centre | `centre.py` et MariaDB | Recevoir les états des secours et conserver l’état courant et l’historique |

La simulation se connecte au centre par une socket TCP sur le port 5000. Le centre enregistre ensuite les informations dans MariaDB, sur sa propre machine. La VM 1 n’accède pas directement à MariaDB.

Les deux VM permettent de démontrer une communication entre deux systèmes distincts : adressage IP, connexion TCP, réception de messages et stockage.

Les voitures, les feux et les trajectoires sont calculés dans la simulation. Les messages réseau concernent les états des véhicules de secours ; le centre n’exécute pas une deuxième simulation.

## 2. Préparer les VM

Importer le fichier Debian `.ova` dans VirtualBox sur chaque ordinateur : **Fichier > Importer un appareil virtuel**. Nommer les VM `SAE302-Simulation` et `SAE302-Centre` pour les reconnaître.

Lors de l’importation ou du clonage, choisir la génération de nouvelles adresses MAC. Chaque VM doit avoir sa propre adresse MAC.

Repères de configuration proposés, à adapter aux ressources disponibles :

| Réglage | VM 1 | VM 2 |
|---|---|---|
| Système | Debian 13 avec bureau graphique | Debian 13 ; bureau nécessaire pour afficher le centre graphique |
| Mémoire | 4 Go si disponibles | 2 à 4 Go |
| Processeurs | 2 processeurs virtuels si disponibles | 2 processeurs virtuels si disponibles |
| Disque | Conserver le disque de l’OVA et vérifier l’espace libre | Même vérification, avec de la place pour MariaDB |

## 3. Réseau VirtualBox : choisir « Accès par pont »

### Réglages à faire sur chacune des deux VM

Éteindre complètement la VM avant de modifier ses paramètres. Dans **Configuration > Réseau > Adaptateur 1**, régler :

| Champ | Valeur à choisir |
|---|---|
| Activer la carte réseau | Coché |
| Mode d’accès réseau | **Accès par pont** / **Bridged Adapter** |
| Nom | La carte physique de l’ordinateur réellement connectée au réseau |
| Câble branché / connecté | Coché |
| Mode promiscuité | Refuser / valeur par défaut |
| Adresse MAC | Différente de celle de l’autre VM |
| Autres adaptateurs | Désactivés pour ce guide, afin d’éviter de confondre les adresses |

## 4. Relever les adresses réellement attribuées

Dans le terminal de chaque VM :

```bash
ip -br -4 addr
ip -4 route
```

Dans la première commande, repérer l’interface réseau active, souvent `enp0s3`, et son adresse IPv4. Dans la deuxième, la ligne `default ... dev ...` aide à repérer l’interface utilisée pour sortir vers le réseau.

Retenir uniquement les quatre nombres de l’adresse, sans le suffixe `/24`, `/20` ou autre. Ne pas retenir `127.0.0.1`, qui désigne la machine elle-même.

| Information à noter | Valeur à relever sur place |
|---|---|
| IP de la VM 1 | Adresse affichée dans la VM de simulation |
| IP de la VM 2 | Adresse affichée dans la VM du centre |

Une adresse `169.254...` ou l’absence d’IPv4 sur la carte concernée peut indiquer un échec DHCP. Vérifier alors la connexion, le mode pont, la carte physique sélectionnée et l’autorisation du réseau.

## 5. Installer les logiciels sur les deux VM

Les commandes suivantes s’exécutent dans le terminal Debian, pas dans PowerShell Windows.

Sur les deux VM :

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip iproute2 iputils-ping netcat-openbsd libegl1 libgl1 libxcb-cursor0 libxkbcommon-x11-0
```

Sur la VM 2 uniquement :

```bash
sudo apt install -y mariadb-server mariadb-client
sudo systemctl enable --now mariadb
sudo systemctl status mariadb --no-pager
```

MariaDB doit être `active (running)`.

## 6. Télécharger et installer le projet

Sur les deux VM, pour une première installation :

```bash
cd ~
git clone https://github.com/aymbrique/SAE-3.02--D-velopper-une-application-communicante.git SAE302
cd ~/SAE302
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Si le projet est déjà installé dans `~/SAE302`, ne pas refaire `git clone`. Utiliser :

```bash
cd ~/SAE302
git pull --ff-only
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Si Git signale des modifications locales, les sauvegarder avant de poursuivre. Ne pas effacer vos fichiers pour forcer la mise à jour.

Les commandes suivantes supposent que votre projet est dans `~/SAE302`. S’il est ailleurs, adapter le chemin des commandes `cd`.

## 7. Préparer MariaDB sur la VM 2

### Créer la base et le compte de connexion

Sur la VM 2 :

```bash
sudo mariadb
```

Exécuter les commandes SQL suivantes. Remplacer `VOTRE_MOT_DE_PASSE` par un mot de passe choisi et le conserver pour la configuration suivante :

```sql
CREATE DATABASE IF NOT EXISTS sae302 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'sae302'@'127.0.0.1' IDENTIFIED BY 'VOTRE_MOT_DE_PASSE';
GRANT SELECT, INSERT, UPDATE, CREATE ON sae302.* TO 'sae302'@'127.0.0.1';
EXIT;
```

Si le compte existe déjà, `CREATE USER IF NOT EXISTS` ne change pas son mot de passe. Conserver son mot de passe existant ou le modifier volontairement avec `ALTER USER`.

### Configurer le centre

Sur la VM 2 :

```bash
cd ~/SAE302
source .venv/bin/activate
cp -n config.example.ini config.ini
nano config.ini
```

Renseigner :

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

Dans Nano : `Ctrl+O`, Entrée pour enregistrer, puis `Ctrl+X` pour quitter.

La valeur `serveur` de la section `[reseau]` sert à configurer le client. Pour l’écoute de `centre.py`, c’est bien l’option `--bind` de la commande de lancement qui s’applique.

`127.0.0.1` dans la section MariaDB est volontaire : le centre et sa base sont sur la même VM. Cette adresse locale ne dépend pas du DHCP et ne correspond pas à l’IP à fournir à la simulation.

Initialiser les tables :

```bash
python init_db.py --config config.ini
```

Message attendu : `Tables MariaDB pretes : vehicules et historique_etats.`

## 8. Démarrer le centre sur la VM 2

Dans un terminal de la VM 2 :

```bash
cd ~/SAE302
source .venv/bin/activate
python centre.py --config config.ini --bind 0.0.0.0 --port 5000
```

Le centre ouvre son interface graphique et annonce son écoute sur le port 5000. Garder ce terminal ouvert.

## 9. Tester et lancer la simulation avec l’IP réelle

### Saisir l’adresse de la VM 2 sur la VM 1

Sur la VM 2, relever à nouveau l’adresse si besoin :

```bash
ip -br -4 addr
```

Sur la VM 1, ouvrir un terminal dans son bureau graphique. **Copier-coller exactement la commande ci-dessous, sans modifier le texte entre guillemets ni remplacer quoi que ce soit par une adresse IP.** Appuyer sur Entrée :

```bash
read -r -p "Adresse IPv4 actuelle de la VM 2 (centre) : " IP_CENTRE
```

Le terminal affiche alors la question « Adresse IPv4 actuelle de la VM 2 (centre) : » et attend une réponse. **C’est à ce moment-là qu’il faut taper l’adresse IP relevée sur la VM 2**, puis appuyer sur Entrée. Ne pas taper le nom `IP_CENTRE`.

Cette commande ne change aucune adresse réseau. Elle mémorise simplement votre saisie dans une variable du terminal. Elle ne cherche pas automatiquement le centre sur le réseau.

### Tester la communication

Dans ce même terminal de la VM 1 :

```bash
ping -c 4 "$IP_CENTRE"
nc -vz -w 3 "$IP_CENTRE" 5000
```

Le ping teste les réponses ICMP de la VM 2. Il peut être filtré par le réseau : son échec ne suffit pas à conclure que TCP est bloqué.

Le test important pour le projet est `nc` sur le port 5000, à effectuer après le lancement du centre. Un message `succeeded` ou `open` confirme qu’une connexion TCP a pu être ouverte. Cela ne valide pas encore le contenu des messages ni leur enregistrement dans MariaDB.

### Lancer la simulation

Toujours dans le même terminal, après un test TCP réussi :

```bash
cd ~/SAE302
source .venv/bin/activate
python main.py --host "$IP_CENTRE" --port 5000
```

`--host` utilise l’IP que vous venez de saisir et remplace la valeur éventuelle du fichier de configuration. Aucune IP fixe n’est nécessaire dans le code Python. La VM 1 n’a pas besoin du mot de passe MariaDB.

La variable `IP_CENTRE` appartient à ce terminal : si vous le fermez ou en ouvrez un autre, refaire la commande `read`. Ne pas utiliser `--local` pour cette démonstration, car cette option désactive la connexion TCP.

## 10. Vérifier les états et MariaDB

1. Démarrer la simulation.
2. Envoyer un premier secours en intervention.
3. Vérifier dans le centre qu’il passe à l’état occupé.
4. Attendre son retour et vérifier son état disponible.
5. Refaire l’essai avec l’autre secours.
6. Consulter les données sur la VM 2.

Dans un deuxième terminal de la VM 2 :

```bash
mariadb --protocol=TCP -h 127.0.0.1 -u sae302 -p sae302
```

Saisir le mot de passe à la demande, puis :

```sql
SHOW TABLES;
SELECT identifiant, etat, numero, recu_le FROM vehicules;
SELECT id, identifiant, etat, numero, recu_le
FROM historique_etats ORDER BY id DESC LIMIT 20;
EXIT;
```

Vérifier que les informations correspondent aux interventions lancées sur la VM 1. C’est ce test complet qui valide la chaîne simulation, réseau, centre et base de données.

## Références et portée des vérifications

- Documentation officielle Oracle VirtualBox : [Virtual Networking](https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/networkingdetails.html).
- [Projet SAE302 sur GitHub](https://github.com/aymbrique/SAE-3.02--D-velopper-une-application-communicante).

Les options `--host`, `--bind`, `--config`, le script `init_db.py` et les requêtes de consultation ont été vérifiés dans le dépôt le 27 octobre 2026. Le déploiement et la communication entre les deux VM restent à vérifier sur votre réseau.
