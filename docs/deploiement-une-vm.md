# Déployer SAE302 sur deux VM Linux

Ce guide respecte la consigne de communication entre deux machines virtuelles Linux.

- **VM 1 – simulation** : lance `main.py`, affiche la carte et envoie les états.
- **VM 2 – centre** : lance `centre.py`, reçoit les messages TCP et les enregistre dans MariaDB.

```text
VM 1 : main.py  ── TCP port 5000 ──>  VM 2 : centre.py  ──> MariaDB port 3306
```

La VM 1 ne se connecte jamais directement à MariaDB.

## 1. Préparer le réseau

Les deux VM doivent être sur le même réseau virtuel. Avec VirtualBox, utiliser un réseau privé hôte commun aux deux VM. Un adaptateur NAT supplémentaire peut servir pour Internet.

Dans chaque VM :

```bash
ip -4 addr
```

Exemple utilisé dans ce guide :

| Machine | Rôle | Adresse exemple |
|---|---|---|
| VM 1 | Simulation avec `main.py` | `192.168.56.11` |
| VM 2 | Centre et MariaDB | `192.168.56.20` |

Remplacer ces adresses par les adresses réelles.

Depuis la VM 1 :

```bash
ping -c 4 192.168.56.20
```

Le ping doit répondre avant de continuer.

## 2. Installer les logiciels

Sur les deux VM :

```bash
sudo apt update
sudo apt install git python3 python3-venv python3-pip libegl1 libgl1 libxcb-cursor0 libxkbcommon-x11-0
```

Sur la VM 2 uniquement :

```bash
sudo apt install mariadb-server mariadb-client
sudo systemctl enable --now mariadb
sudo systemctl status mariadb --no-pager
```

Le service doit afficher `active (running)`.

## 3. Installer le projet

Sur les deux VM :

```bash
cd ~
git clone https://github.com/aymbrique/SAE-3.02--D-velopper-une-application-communicante.git SAE302
cd ~/SAE302
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Si le dépôt est déjà présent :

```bash
cd ~/SAE302
git pull --ff-only
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## 4. Préparer MariaDB sur la VM 2

Sur la VM 2 :

```bash
sudo mariadb
```

Exécuter :

```sql
CREATE DATABASE sae302 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'sae302'@'127.0.0.1' IDENTIFIED BY 'VOTRE_MOT_DE_PASSE';
GRANT SELECT, INSERT, UPDATE, CREATE ON sae302.* TO 'sae302'@'127.0.0.1';
EXIT;
```

Remplacer `VOTRE_MOT_DE_PASSE` par un mot de passe choisi.

Créer `config.ini` sur la VM 2 :

```bash
cd ~/SAE302
source .venv/bin/activate
cp -n config.example.ini config.ini
nano config.ini
```

Configuration de la VM 2 :

```ini
[reseau]
serveur = 0.0.0.0
port = 5000

[mariadb]
host = 127.0.0.1
port = 3306
database = sae302
user = sae302
password = VOTRE_MOT_DE_PASSE
```

`0.0.0.0` permet au centre d’accepter les connexions réseau. MariaDB reste locale à la VM 2.

Initialiser les tables :

```bash
python init_db.py
```

## 5. Configurer la VM 1

Sur la VM 1 :

```bash
cd ~/SAE302
source .venv/bin/activate
cp -n config.example.ini config.ini
nano config.ini
```

Configuration de la VM 1 :

```ini
[reseau]
serveur = 192.168.56.20
port = 5000

[mariadb]
host = 127.0.0.1
port = 3306
database = sae302
user = sae302
password =
```

Remplacer `192.168.56.20` par l’adresse réelle de la VM 2. La partie MariaDB n’est pas utilisée par `main.py`. Ne jamais mettre le mot de passe dans GitHub.

## 6. Ouvrir le port réseau

Si UFW est actif sur la VM 2 :

```bash
sudo ufw allow from 192.168.56.11 to any port 5000 proto tcp
sudo ufw status
```

Remplacer `192.168.56.11` par l’adresse de la VM 1.

Le port 3306 ne doit pas être ouvert entre les VM : MariaDB est utilisée seulement par `centre.py` sur la VM 2.

## 7. Lancer les programmes

Sur la VM 2, dans un premier terminal :

```bash
cd ~/SAE302
source .venv/bin/activate
python centre.py --bind 0.0.0.0 --port 5000
```

Message attendu :

```text
Centre pret sur 0.0.0.0:5000 ; stockage MariaDB actif.
```

Garder ce terminal ouvert.

Sur la VM 1, dans un terminal graphique :

```bash
cd ~/SAE302
source .venv/bin/activate
python main.py --host 192.168.56.20 --port 5000
```

Ne pas utiliser `--local` pendant la démonstration : cette option désactive la communication TCP.

Dans l’onglet **Réseau**, l’adresse du centre doit apparaître et la liaison doit être active.

## 8. Vérifier la communication

Depuis la VM 1 :

```bash
nc -vz 192.168.56.20 5000
```

Le résultat doit contenir `succeeded` ou `open`.

Sur la VM 2 :

```bash
ss -ltn | grep 5000
```

La ligne doit montrer une écoute de type `0.0.0.0:5000`.

Scénario de test :

1. Cliquer sur **Démarrer** dans `main.py`.
2. Choisir le secours 01 et une intervention.
3. Cliquer sur **Envoyer en intervention**.
4. Vérifier sur la VM 2 que 01 devient `occupe`.
5. Attendre son retour et vérifier `disponible`.
6. Refaire le test avec le secours 02.

Sur la VM 2 :

```bash
mariadb --protocol=TCP -h 127.0.0.1 -u sae302 -p sae302
```

Puis :

```sql
SELECT identifiant, etat, numero, recu_le FROM vehicules;
SELECT id, identifiant, etat, numero, recu_le
FROM historique_etats ORDER BY id DESC LIMIT 20;
EXIT;
```

Les états envoyés depuis la VM 1 doivent apparaître dans MariaDB sur la VM 2.

## 9. Utiliser PyCharm

Sur la VM 2, créer une configuration Python :

```text
Script : centre.py
Paramètres : --bind 0.0.0.0 --port 5000
Interpréteur : ~/SAE302/.venv/bin/python
```

Sur la VM 1 :

```text
Script : main.py
Paramètres : --host 192.168.56.20 --port 5000
Interpréteur : ~/SAE302/.venv/bin/python
```

Lancer d’abord `centre.py` sur la VM 2, puis `main.py` sur la VM 1.

## 10. Ce qui se passe

1. `main.py` change le secours en `occupe`.
2. Le client TCP crée un message JSON.
3. Le message traverse le réseau virtuel sur le port 5000.
4. `centre.py` reçoit et valide le message.
5. MariaDB enregistre l’état et l’historique.
6. Le centre renvoie un accusé de réception, appelé ACK.
7. Au retour, le même fonctionnement transmet `disponible`.

Les routes, les feux, les positions et la progression sont calculés sur la VM 1. La VM 2 conserve les états reçus et l’historique.

## 11. Dépannage

| Problème | Vérification |
|---|---|
| `ping` échoue | Les VM ne sont pas sur le même réseau ou l’adresse IP est incorrecte. |
| `nc` échoue | Le centre n’est pas lancé, le port est bloqué ou le pare-feu refuse la connexion. |
| Le centre écoute sur `127.0.0.1` | Relancer avec `python centre.py --bind 0.0.0.0 --port 5000`. |
| Liaison interrompue | Vérifier l’adresse IP de la VM 2, le port 5000 et l’absence de `--local`. |
| MariaDB inaccessible | Vérifier `sudo systemctl status mariadb` sur la VM 2. |
| `Access denied` | Vérifier le mot de passe et le compte `sae302@127.0.0.1`. |
| Port 5000 occupé | Arrêter l’ancien centre avant d’en lancer un nouveau. |

Pour mettre à jour les deux VM :

```bash
cd ~/SAE302
git pull --ff-only
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Ne pas supprimer `config.ini` : chaque VM possède sa configuration locale, qui n’est pas versionnée.
