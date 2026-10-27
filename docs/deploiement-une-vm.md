# SAE302 — Déploiement sur deux VM Debian à l’université

Version du 27 octobre 2026. Guide prévu pour VirtualBox, avec une VM sur chacun de vos deux ordinateurs connectés au réseau de l’université. Le même mode peut fonctionner si les deux VM sont sur un seul ordinateur, sous réserve des règles du réseau.

## 1. Comprendre le fonctionnement

| Machine | Ce qu’elle lance | Son rôle |
|---|---|---|
| VM 1 — Simulation | `main.py` | Afficher la ville, gérer la circulation, les feux et les interventions |
| VM 2 — Centre | `centre.py` et MariaDB | Recevoir les états des secours et conserver l’état courant et l’historique |

La simulation se connecte au centre par une socket TCP sur le port 5000. Le centre enregistre ensuite les informations dans MariaDB, sur sa propre machine. La VM 1 n’accède pas directement à MariaDB.

Les deux VM permettent de démontrer une communication entre deux systèmes distincts : adressage IP, connexion TCP, réception de messages et stockage. Une seule machine peut servir à développer et tester le programme, mais votre démonstration doit respecter la consigne des deux VM.

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
| Nom | La carte physique de l’ordinateur réellement connectée au réseau universitaire |
| Câble branché / connecté | Coché |
| Mode promiscuité | Refuser / valeur par défaut |
| Adresse MAC | Différente de celle de l’autre VM |
| Autres adaptateurs | Désactivés pour ce guide, afin d’éviter de confondre les adresses |

Si l’ordinateur est branché par câble, choisir sa carte **Ethernet**. Si vous utilisez le Wi-Fi, choisir la carte **Wi-Fi**. Éviter de sélectionner une carte VPN, Bluetooth ou VirtualBox Host-Only. Une connexion Ethernet est à privilégier si elle est disponible et autorisée.

Le pont raccorde chaque VM au réseau physique via la carte de son ordinateur. Le réseau universitaire doit autoriser ces VM et leurs communications. Selon la configuration du campus, le Wi-Fi, l’authentification réseau ou un filtrage peuvent empêcher ce fonctionnement.

### Pourquoi ce choix plutôt que NAT ou réseau privé hôte ?

| Mode | Utilité | Adaptation à votre cas |
|---|---|---|
| Accès par pont | Présenter la VM sur le réseau physique | Choix prévu ici pour deux VM sur deux ordinateurs du réseau universitaire |
| NAT simple | Donner principalement un accès sortant au réseau/à Internet | Ne rend pas directement le serveur de la VM 2 joignable ; nécessiterait une redirection de port |
| Réseau NAT | Relier des VM dans un même réseau NAT VirtualBox | Possible sur un seul hôte ; deux réseaux NAT créés séparément sur deux PC ne sont pas reliés automatiquement |
| Réseau privé hôte / Host-only | Relier l’hôte et ses VM localement | Deux réseaux Host-only sur deux PC différents ne communiquent pas automatiquement |
| Réseau interne | Relier des VM sur un même hôte | Ne convient pas directement à deux VM réparties sur deux ordinateurs |

« Accès Internet » n’est pas un mode séparé : le pont peut aussi donner accès à Internet si le réseau universitaire le permet. Internet sert à installer les logiciels et récupérer GitHub ; la communication du projet utilise surtout le réseau local entre les VM.

**Si l’université bloque le pont ou la communication entre postes**, utiliser avec l’enseignant le réseau de TP autorisé. Ne pas inventer une IP fixe pour essayer de contourner le blocage. Si les deux VM sont finalement sur un seul PC, un réseau Host-only avec DHCP et un adaptateur NAT supplémentaire peut servir d’alternative, avec une configuration adaptée.

## 4. Dans Debian : garder l’attribution automatique des IP

Sur chaque VM, ouvrir les paramètres de sa connexion réseau, puis les réglages **IPv4**. Choisir **Automatique (DHCP)**, enregistrer et reconnecter la connexion si nécessaire. Les intitulés varient selon le bureau Debian.

Si l’OVA contient déjà une adresse fixe configurée par votre ami, repasser sa connexion en automatique. Ne pas réutiliser une ancienne IP provenant de son réseau personnel.

DHCP signifie que la VM demande une adresse au réseau. Dans ce déploiement, c’est le serveur DHCP du réseau universitaire qui lui attribue cette adresse. Vous ne la choisissez pas et vous ne la créez pas dans le code.

### Relever les adresses réellement attribuées

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

**Attention : l’IP du PC Windows n’est pas nécessairement celle de sa VM Debian. Relever les IP à l’intérieur des VM.** Les VM doivent avoir des adresses différentes ; être sur le même Wi-Fi ne garantit pas qu’elles soient autorisées à communiquer.

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

Le fichier `config.ini` contient votre mot de passe local : ne pas le publier sur GitHub.

## 8. Démarrer le centre sur la VM 2

Dans un terminal de la VM 2 :

```bash
cd ~/SAE302
source .venv/bin/activate
python centre.py --config config.ini --bind 0.0.0.0 --port 5000
```

Le centre ouvre son interface graphique et annonce son écoute sur le port 5000. Garder ce terminal ouvert.

Pour une VM 2 sans bureau graphique, utiliser la version sans fenêtre :

```bash
python centre.py --config config.ini --bind 0.0.0.0 --port 5000 --headless
```

**`0.0.0.0` est une adresse d’écoute spéciale : le serveur accepte les connexions sur ses interfaces IPv4 locales. Ce n’est pas une IP attribuée à la VM et ce n’est pas une destination à saisir sur la VM 1.** Le centre n’a donc pas besoin de connaître à l’avance son adresse DHCP pour écouter.

Dans un autre terminal de la VM 2, vérifier :

```bash
ss -ltn 'sport = :5000'
```

La sortie doit indiquer une écoute sur `0.0.0.0:5000`.

## 9. Tester et lancer la simulation avec l’IP réelle

### Saisir l’adresse de la VM 2 sur la VM 1

Sur la VM 2, relever à nouveau l’adresse si besoin :

```bash
ip -br -4 addr
```

Sur la VM 1, ouvrir un terminal dans son bureau graphique et exécuter :

```bash
read -r -p "Adresse IPv4 actuelle de la VM 2 (centre) : " IP_CENTRE
```

À la question affichée, taper l’adresse réellement relevée dans la VM 2, puis Entrée. Ne pas taper le nom `IP_CENTRE` ni une adresse d’exemple.

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

## 10. Pare-feu : uniquement si nécessaire

Si UFW est installé sur la VM 2, consulter son état :

```bash
sudo ufw status
```

S’il est actif et bloque le projet, relever l’IP réelle de la VM 1 avec `ip -br -4 addr`, puis, dans un deuxième terminal de la VM 2 :

```bash
read -r -p "Adresse IPv4 actuelle de la VM 1 (simulation) : " IP_SIMULATION
sudo ufw allow from "$IP_SIMULATION" to any port 5000 proto tcp
```

Cette règle utilise l’adresse saisie, sans l’attribuer à la VM 1. Si son IP change, adapter la règle. Ne pas désactiver globalement le pare-feu et ne pas ouvrir MariaDB sur le réseau : le port 3306 reste local au centre.

UFW n’est pas forcément installé sur Debian. Une erreur « commande introuvable » ne prouve pas l’absence de tout filtrage : un autre pare-feu ou le réseau universitaire peut bloquer les connexions. Dans ce cas, vérifier avec l’enseignant ou le service informatique.

## 11. Vérifier les états et MariaDB

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

## 12. À chaque nouvelle séance à l’université

Les adresses DHCP peuvent changer après un redémarrage, une reconnexion ou un changement de salle. Elles peuvent aussi rester identiques ; il faut les vérifier.

1. Démarrer les deux VM et vérifier leur connexion en pont.
2. Sur la VM 2, relever l’IPv4 actuelle avec `ip -br -4 addr`.
3. Sur la VM 2, démarrer MariaDB et le centre :

```bash
sudo systemctl start mariadb
cd ~/SAE302
source .venv/bin/activate
python centre.py --config config.ini --bind 0.0.0.0 --port 5000
```

4. Sur la VM 1, saisir l’adresse actuelle du centre et lancer :

```bash
read -r -p "Adresse IPv4 actuelle de la VM 2 (centre) : " IP_CENTRE
nc -vz -w 3 "$IP_CENTRE" 5000
cd ~/SAE302
source .venv/bin/activate
python main.py --host "$IP_CENTRE" --port 5000
```

Si `nc` échoue, résoudre la connexion avant la démonstration. Si l’adresse change pendant l’exécution, fermer la simulation, relever la nouvelle IP du centre et relancer avec cette adresse. Vérifier également les éventuelles règles de pare-feu fondées sur l’ancienne IP.

Il n’est pas nécessaire de réinstaller le projet ni de recréer la base à chaque séance.

## 13. Lancer depuis PyCharm dans les VM

Il est possible de lancer les commandes précédentes dans le terminal intégré de PyCharm, à condition d’être dans la VM Debian et d’utiliser son environnement `.venv`.

Pour utiliser le bouton Exécuter, choisir l’interpréteur `~/SAE302/.venv/bin/python` et le dossier de travail `~/SAE302`.

| VM | Script | Paramètres |
|---|---|---|
| VM 2 | `centre.py` | `--config config.ini --bind 0.0.0.0 --port 5000` |
| VM 1 | `main.py` | `--host ADRESSE_ACTUELLE_DU_CENTRE --port 5000` |

Dans la configuration PyCharm de la VM 1, remplacer `ADRESSE_ACTUELLE_DU_CENTRE` par l’IP relevée sur la VM 2. Ce texte n’est pas une adresse utilisable. Le champ de paramètres de PyCharm n’est pas un terminal Bash : ne pas y coller `$IP_CENTRE` en espérant qu’il soit remplacé automatiquement.

## 14. Dépannage

| Symptôme | Vérifications |
|---|---|
| Pas d’IP ou adresse `169.254...` | IPv4 automatique, bonne carte physique en pont, câble connecté et DHCP autorisé |
| Deux VM avec la même IP | Vérifier les MAC différentes, l’absence d’anciennes IP statiques ; reconnecter après correction |
| IP affichée différente de celle de la séance précédente | Normal avec DHCP : reprendre l’adresse actuelle |
| Internet fonctionne mais pas la liaison entre VM | Internet ne garantit pas les communications entre postes ; vérifier le filtrage universitaire et le pont |
| `nc` indique `Connection refused` | Vérifier que le centre écoute, son adresse, le port et un éventuel rejet du pare-feu |
| `nc` expire sans réponse | Vérifier l’IP, le réseau, le filtrage ou l’isolement des postes |
| Le centre écoute sur `127.0.0.1:5000` | Relancer avec `--bind 0.0.0.0` |
| La simulation utilise l’ancienne IP | Relancer avec la nouvelle adresse et `--host` |
| `Access denied` dans MariaDB | Vérifier le compte `sae302@127.0.0.1`, son mot de passe et `config.ini` |
| `No module named ...` | Activer `.venv` et installer `requirements.txt` |
| Fenêtre Qt impossible à ouvrir | Lancer dans le bureau graphique de Debian ; pour le centre seul, utiliser `--headless` si nécessaire |
| Port déjà utilisé | Arrêter l’ancien centre avant de le relancer |

## 15. Ce qui reste fixe et ce qui change

| Élément | Signification |
|---|---|
| IP de la VM 1 | Attribuée par DHCP ; à relever pour un éventuel filtrage |
| IP de la VM 2 | Attribuée par DHCP ; à saisir sur la VM 1 pour joindre le centre |
| Port TCP 5000 | Port du projet, choisi et identique des deux côtés |
| `0.0.0.0` avec `--bind` | Adresse spéciale d’écoute du centre, pas une IP à attribuer |
| `127.0.0.1` pour MariaDB | Adresse locale de la VM 2, car la base et le centre sont ensemble |

Le programme sait déjà recevoir une adresse avec `--host`. L’adaptation au réseau universitaire consiste donc à utiliser les adresses DHCP réelles au lancement. Ce guide ne met pas en place de découverte automatique du centre : son adresse est relevée sur la VM 2 puis saisie sur la VM 1.

## Références et portée des vérifications

- Documentation officielle Oracle VirtualBox : [Virtual Networking](https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/networkingdetails.html).
- [Projet SAE302 sur GitHub](https://github.com/aymbrique/SAE-3.02--D-velopper-une-application-communicante).

Les options `--host`, `--bind`, `--headless`, `--config`, le script `init_db.py` et les requêtes de consultation ont été vérifiés dans le dépôt le 27 octobre 2026. Le déploiement sur vos deux VM et l’autorisation des communications par le réseau universitaire restent à tester sur place.
