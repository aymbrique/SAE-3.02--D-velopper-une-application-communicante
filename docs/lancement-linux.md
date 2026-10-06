# Guide de lancement sur deux VM Linux

## 1. Repartition

| VM | A lancer | A installer |
|---|---|---|
| VM 1 - simulation | `main.py` | Python, PyQt6 et le depot |
| VM 2 - coordination | `centre.py` et le service MariaDB | Python, PyQt6, PyMySQL, MariaDB et le depot |

Les deux VM utilisent le meme depot GitHub. La VM 1 envoie du JSON au centre sur **5000/TCP**. Le centre ecrit ensuite dans MariaDB sur **127.0.0.1:3306**. Aucun acces direct a MariaDB n'est necessaire depuis la VM 1.

Les commandes d'installation ci-dessous ciblent **Debian 13 avec un bureau graphique et Python 3.13**. Sur une autre distribution, les paquets peuvent porter d'autres noms ; ne remplacez pas le Python du systeme. Le code a aussi ete teste sous Python 3.12.

Les commandes Python se lancent dans le terminal du bureau de la VM, depuis le dossier du projet. Le centre peut aussi fonctionner sans bureau avec `--headless`.

## 2. Preparer le reseau des VM

Deux VM sur le meme ordinateur : les placer sur un meme reseau virtuel qui permet les echanges entre elles. Avec VirtualBox, un adaptateur reseau prive hote commun et un second adaptateur NAT pour Internet conviennent. Deux adaptateurs NAT isoles ne garantissent pas une communication directe entre VM.

Deux VM sur deux ordinateurs differents : utiliser un reseau commun accessible aux deux VM, par exemple des adaptateurs en pont sur le meme LAN si le reseau de TP l'autorise. Deux reseaux prives hotes, un par PC, ne sont pas un reseau commun.

Sur chaque VM, relever les adresses :

```bash
ip -br address
```

Exemple uniquement : VM 1 = `192.168.56.10`, VM 2 = `192.168.56.20`. Remplacer ces valeurs par vos vraies adresses. Ne pas utiliser `127.0.0.1` pour joindre l'autre VM : cette adresse designe toujours la machine locale.

Depuis la VM 1 :

```bash
ping -c 3 192.168.56.20
```

Un ping reussi confirme une connectivite IP. Certains pare-feu bloquent le ping ; le test du port TCP apres demarrage du centre reste decisif.

## 3. Installer les outils sur les deux VM

```bash
sudo apt update
sudo apt install git python3.13 python3.13-venv nano netcat-openbsd libegl1 libgl1 libxcb-cursor0 libxkbcommon-x11-0
python3.13 --version
```

Si `python3.13` est introuvable dans les depots de votre distribution, verifiez la version Linux avec `cat /etc/os-release`. Les commandes ci-dessus sont celles de Debian 13 ; utilisez l'interpreteur 3.13 fourni pour votre environnement de TP.

## 4. Recuperer le projet sur les deux VM

Si le depot est deja clone et sans modifications locales non sauvegardees :

```bash
git pull --ff-only
```

Sinon :

```bash
git clone https://github.com/aymbrique/SAE-3.02--D-velopper-une-application-communicante.git SAE302
cd SAE302
```

Dans le dossier contenant `main.py` et `centre.py`, sur chaque VM :

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp -n config.example.ini config.ini
```

`cp -n` preserve une configuration deja existante. Le fichier `config.ini` et `.venv` sont exclus de Git. Chaque VM a sa propre configuration et son propre environnement Python.

## 5. Installer MariaDB sur la VM 2 seulement

```bash
sudo apt install mariadb-server mariadb-client
sudo systemctl enable --now mariadb
sudo systemctl status mariadb --no-pager
```

Le service doit etre actif. Ouvrir ensuite la console d'administration locale :

```bash
sudo mariadb
```

Dans cette console, executer les instructions suivantes. Remplacer `VOTRE_MOT_DE_PASSE` par un mot de passe choisi pour ce projet et noter cette valeur pour la configuration locale :

```sql
CREATE DATABASE sae302 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'sae302'@'127.0.0.1' IDENTIFIED BY 'VOTRE_MOT_DE_PASSE';
GRANT SELECT, INSERT, UPDATE, CREATE ON sae302.* TO 'sae302'@'127.0.0.1';
EXIT;
```

Ces instructions servent a la premiere installation. Ne pas supprimer une base existante pour les rejouer. Si l'utilisateur existe et que son mot de passe doit changer, utiliser `ALTER USER 'sae302'@'127.0.0.1' IDENTIFIED BY 'nouveau_mot_de_passe';`.

L'utilisateur de l'application est limite a cette base. L'application n'utilise pas le compte administrateur `root`. MariaDB n'a pas besoin d'etre ouverte aux autres machines du reseau.

## 6. Configurer la VM 2 et creer les tables

Depuis le dossier du projet :

```bash
nano config.ini
```

Renseigner la section MariaDB :

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

Utiliser le meme mot de passe que dans `CREATE USER`, sans ajouter de guillemets dans le fichier INI. Dans nano : Ctrl+O, Entree pour enregistrer, puis Ctrl+X pour fermer. Ne pas envoyer ce fichier de configuration sur GitHub.

Activer l'environnement et creer les tables :

```bash
source .venv/bin/activate
python init_db.py
```

Resultat attendu : `Tables MariaDB pretes : vehicules et historique_etats.` Cette commande peut etre relancee sans effacer les donnees existantes.

Le mot de passe peut aussi venir de la variable d'environnement `SAE_DB_PASSWORD` ; si elle existe, elle prend le dessus sur `config.ini`.

## 7. Lancer le centre sur la VM 2

```bash
python centre.py
```

Une fenetre s'ouvre. Elle montre deux secours inconnus lors de la toute premiere utilisation, ou les derniers etats connus si la base contient deja des informations. La liaison reste interrompue jusqu'a reception de messages.

Le centre ecoute par defaut sur toutes les interfaces IPv4 (`0.0.0.0`), port 5000. Pour verifier depuis un autre terminal sur la VM 2 :

```bash
ss -ltn | grep ':5000'
```

Depuis la VM 1 :

```bash
nc -vz 192.168.56.20 5000
```

Si un pare-feu UFW est deja actif sur la VM 2, une regle limitee a l'adresse de la VM 1 suffit :

```bash
sudo ufw allow from 192.168.56.10 to any port 5000 proto tcp
```

Adapter les adresses. Ne pas ouvrir le port 3306 pour cette architecture.

Pour un centre sans interface graphique : `python centre.py --headless`. Les donnees sont toujours stockees ; les consulter alors avec le client MariaDB. Ctrl+C arrete ce mode.

## 8. Lancer la simulation sur la VM 1

Le centre doit deja etre lance. Sur la VM 1, dans le projet :

```bash
source .venv/bin/activate
python main.py --host 192.168.56.20 --port 5000
```

Remplacer l'adresse d'exemple par celle de la VM 2. Les deux secours doivent apparaitre disponibles au centre. La simulation peut aussi demarrer avant le centre : elle retente alors la connexion automatiquement.

Pour ne pas retaper l'adresse, renseigner `serveur` et `port` dans la section `[reseau]` du `config.ini` de la VM 1, puis lancer simplement `python main.py`. La VM 1 n'utilise pas la section MariaDB et n'a pas besoin de son mot de passe.

## 9. Faire une demonstration complete

1. Dans la simulation, cliquer sur **Demarrer** et observer l'arret aux feux.
2. Cliquer sur **Envoyer le secours 01**. Le centre doit afficher `occupe` pour 01 uniquement.
3. Envoyer le secours 02. Verifier que les deux lignes restent independantes.
4. Observer la priorite, les transitions et le retour des secours. Chaque secours redevient disponible a son retour a la caserne.
5. Une fois les deux missions finies, observer la compensation si du vert supplementaire a ete memorise.
6. Fermer la simulation : le centre indique une liaison interrompue en conservant les derniers etats.
7. Relancer la simulation : la liaison se retablit et une nouvelle session apparait dans l'historique.
8. Fermer puis relancer le centre : l'historique reste en base. Si la simulation est ouverte, elle se reconnecte automatiquement.

Pour tester les mises a jour en attente : fermer le centre, declencher une mission dans la simulation, puis relancer le centre. Le client doit rester ouvert pendant cet essai. Les messages en attente sont alors renvoyes et confirmes.

## 10. Consulter MariaDB directement

Sur la VM 2 :

```bash
mariadb --protocol=TCP -h 127.0.0.1 -u sae302 -p sae302
```

Saisir le mot de passe puis :

```sql
SHOW TABLES;
SELECT identifiant, etat, numero, recu_le FROM vehicules;
SELECT id, identifiant, etat, numero, recu_le
FROM historique_etats ORDER BY id DESC LIMIT 20;
EXIT;
```

Les dates sont en UTC. `vehicules` contient le dernier etat par identifiant ; `historique_etats` contient les mises a jour acceptees, pas les pings reseau.

## 11. Lancer depuis PyCharm

Ouvrir le dossier clone et choisir `.venv/bin/python` comme interpreteur du projet. PyCharm doit utiliser l'interpreteur de la VM sur laquelle vous lancez le programme, ou etre execute directement dans cette VM.

Sur la VM 2, lancer une fois `init_db.py`, puis lancer `centre.py`. Sur la VM 1, lancer `main.py` avec l'adresse du centre dans `config.ini`. Les configurations par defaut n'ont alors besoin d'aucun argument PyCharm.

Le repertoire de travail conseille est la racine du projet. Sans `--config`, le programme retrouve `config.ini` a cette racine meme si le repertoire courant differe.

Pour recuperer des changements ensuite : sauvegarder votre travail dans un commit, faire `git pull --ff-only` et relancer `python -m pip install -r requirements.txt` si les dependances ont change. Si Git refuse une fusion automatique, traiter le conflit ; ne pas effacer vos modifications locales.

## 12. Essai sur un seul ordinateur

Installer et configurer MariaDB sur cet ordinateur, puis ouvrir deux terminaux dans le projet :

```bash
# Terminal 1
source .venv/bin/activate
python centre.py
```

```bash
# Terminal 2
source .venv/bin/activate
python main.py --host 127.0.0.1
```

Cela valide les programmes mais pas la configuration reseau des deux VM. Pour travailler uniquement sur la circulation, utiliser `python main.py --local`.

## Depannage

| Symptome | Verification |
|---|---|
| `No module named PyQt6` ou `pymysql` | Activer le bon `.venv` puis installer `requirements.txt`. Verifier l'interpreteur PyCharm. |
| Erreur `xcb` / aucune fenetre | Utiliser un bureau graphique et installer les dependances Qt de l'etape 3. Pour diagnostiquer : `QT_DEBUG_PLUGINS=1 python main.py --local`. |
| `Access denied` MariaDB | Verifier le mot de passe, l'utilisateur, `127.0.0.1` et les droits SQL. |
| `Unknown database` | Creer la base avec la console administrateur de l'etape 5. |
| Table absente | Lancer `python init_db.py` sur la VM 2. |
| Port deja utilise | Arreter l'autre instance du centre, ou choisir le meme autre port des deux cotes avec `--port`. |
| Liaison interrompue | Verifier l'adresse de la VM 2, le reseau virtuel, le centre lance, le port et le pare-feu. |
| Le centre refuse un deuxieme simulateur | Une seule simulation peut etre connectee a la fois ; elle transmet les deux secours. |
| Apres coupure de MariaDB | Relancer le service. Une prochaine mise a jour provoquera une nouvelle tentative de stockage ; aucun ACK n'est envoye si l'ecriture echoue. |
| Voitures arretees au vert | Le carrefour, la sortie ou un acces lateral peuvent etre reserves. Le vert ne supprime pas les regles d'espacement. |

## References officielles

- [Python 3.13 et venv sur Debian 13](https://packages.debian.org/trixie/amd64/python3.13-venv)
- [Dependances Qt sous Linux](https://doc.qt.io/qt-6/linux-requirements.html)
- [Creation d'un utilisateur MariaDB](https://mariadb.com/docs/server/reference/sql-statements/account-management-sql-statements/create-user)
- [Droits MariaDB](https://mariadb.com/docs/server/reference/sql-statements/account-management-sql-statements/grant)
- [Connexion Python avec PyMySQL](https://pymysql.readthedocs.io/en/latest/user/examples.html)
