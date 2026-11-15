# SAE302 — Facture sucrée

**Groupe :** Facture sucrée
**Étudiants :** Aymeri Barbier et Selim Parlak

Ce projet simule la circulation autour d'un carrefour. Des voitures suivent des
trajets, respectent les feux et laissent passer deux véhicules de secours. La
simulation envoie l'état des secours à un centre de coordination par TCP. Le
centre affiche ces états et les conserve dans MariaDB.

Le cahier des charges d'origine est disponible ici :
[Cahier_des_charges_SAE302.pdf](Cahier_des_charges_SAE302.pdf).

## À quoi sert chaque partie du projet ?

- `main.py` lance la simulation graphique.
- `centre.py` lance le centre de coordination qui reçoit les messages TCP et
  utilise MariaDB.
- `init_db.py` crée les tables nécessaires dans MariaDB.
- `requirements.txt` contient les bibliothèques Python à installer. Il est lu
  automatiquement avec la commande `python -m pip install -r requirements.txt`.
- `src/interface/` contient les fenêtres, les boutons et le dessin de la carte.
- `src/modeles/` contient les véhicules, le plan et les trajets.
- `src/simulation/` contient les feux, la circulation, les files et les règles
  de priorité des secours.
- `src/reseau/` contient le client TCP, le serveur TCP et le format des
  messages JSON.
- `src/stockage/` et `sql/` servent à enregistrer les états dans MariaDB.
- `tests/` contient les tests automatiques du projet.

## Installer le projet

Les commandes suivantes sont à taper dans un terminal macOS ou Linux.

```bash
git clone https://github.com/aymbrique/SAE-3.02--D-velopper-une-application-communicante.git SAE302
cd SAE302
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Sous Windows, la commande d'activation est :

```powershell
.venv\Scripts\Activate.ps1
```

## Lancer la simulation dans PyCharm ou sur son ordinateur

Pour essayer uniquement la simulation, sans centre de coordination ni base de
données, lancer :

```bash
python main.py --local
```

Dans la fenêtre :

1. Cliquer sur **Démarrer**.
2. Choisir un véhicule de secours et une destination.
3. Cliquer sur **Envoyer en intervention**.
4. Régler si besoin la vitesse et le nombre de voitures par minute.

Le mode local est utile pour travailler sur l'interface et la circulation. Il
ne teste pas la communication TCP ni MariaDB.

## Déployer le projet avec deux VM Debian

La première machine virtuelle lance la simulation. La seconde lance le centre
de coordination et MariaDB. La simulation se connecte au centre sur le port
TCP `5000`. La base MariaDB est utilisée uniquement par la VM du centre.

### 1. Préparer les deux VM

Dans VirtualBox, utiliser le mode réseau **Accès par pont** sur les deux VM.
Chaque VM doit avoir sa propre adresse MAC. Après le démarrage, relever les
adresses IPv4 avec :

```bash
ip -br -4 addr
```

Ne pas utiliser `127.0.0.1` comme adresse de la VM distante : cette adresse
désigne toujours la machine locale.

### 2. Installer les logiciels

Sur les deux VM :

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip iproute2 iputils-ping netcat-openbsd libegl1 libgl1 libxcb-cursor0 libxkbcommon-x11-0
```

Sur la VM du centre uniquement :

```bash
sudo apt install -y mariadb-server mariadb-client
sudo systemctl enable --now mariadb
```

### 3. Télécharger et installer le projet sur les deux VM

Sur chaque VM :

```bash
cd ~
git clone https://github.com/aymbrique/SAE-3.02--D-velopper-une-application-communicante.git SAE302
cd ~/SAE302
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Pour une mise à jour du projet déjà installé :

```bash
cd ~/SAE302
git pull --ff-only
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 4. Préparer MariaDB sur la VM du centre

Ouvrir MariaDB sur la VM du centre :

```bash
sudo mariadb
```

Puis créer la base et le compte de connexion :

```sql
CREATE DATABASE IF NOT EXISTS sae302 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'sae302'@'127.0.0.1' IDENTIFIED BY 'VOTRE_MOT_DE_PASSE';
GRANT SELECT, INSERT, UPDATE, CREATE ON sae302.* TO 'sae302'@'127.0.0.1';
EXIT;
```

Dans `~/SAE302`, créer le fichier local `config.ini` sur la VM du centre :

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

Le fichier `config.ini` contient le mot de passe de la base. Il est ignoré par
Git et ne doit pas être envoyé sur GitHub.

Créer les tables :

```bash
cd ~/SAE302
source .venv/bin/activate
python init_db.py --config config.ini
```

### 5. Lancer le centre sur la VM du centre

```bash
cd ~/SAE302
source .venv/bin/activate
python centre.py --config config.ini --bind 0.0.0.0 --port 5000
```

Laisser cette fenêtre ouverte pendant la démonstration.

### 6. Lancer la simulation sur la seconde VM

Sur la VM de simulation, saisir l'adresse IPv4 actuelle de la VM du centre :

```bash
read -r -p "Adresse IPv4 de la VM du centre : " IP_CENTRE
```

Tester l'accès au centre :

```bash
ping -c 4 "$IP_CENTRE"
nc -vz -w 3 "$IP_CENTRE" 5000
```

Puis lancer la simulation connectée au centre :

```bash
cd ~/SAE302
source .venv/bin/activate
python main.py --host "$IP_CENTRE" --port 5000
```

Ne pas utiliser `--local` pendant cette démonstration, car cette option désactive
la communication TCP.

### 7. Vérifier la base de données

Après une intervention, le centre doit afficher le passage du secours à l'état
occupé, puis disponible lorsqu'il revient. Sur la VM du centre, les données
peuvent être consultées avec :

```bash
mariadb --protocol=TCP -h 127.0.0.1 -u sae302 -p sae302
```

Puis dans MariaDB :

```sql
SHOW TABLES;
SELECT identifiant, etat, numero, recu_le FROM vehicules;
SELECT id, identifiant, etat, numero, recu_le
FROM historique_etats ORDER BY id DESC LIMIT 20;
EXIT;
```

## Lancer les tests

Depuis la racine du projet, avec l'environnement virtuel activé :

```bash
python -m unittest discover -s tests -v
```

Les deux tests MariaDB sont optionnels. Ils demandent une base de test dédiée,
dont le nom se termine par `_test`. Ils ne doivent jamais être exécutés sur la
base de démonstration.
