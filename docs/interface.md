# Utilisation des interfaces

## Simulation : main.py

1. Lancer la simulation selon le [guide Linux](lancement-linux.md).
2. Cliquer sur **Demarrer**. Les voitures apparaissent progressivement ; le debit initial est de 12 voitures par minute simulee.
3. **Mettre en pause** fige le temps simule, les vehicules et les feux. La connexion TCP reste active pendant la pause.
4. **Reprendre** continue depuis le meme etat. Les boutons de vitesse changent le rapport entre temps reel et temps simule.
5. Le champ **Voitures / minute** accepte 0 a 60. A 0, les voitures deja presentes finissent leurs trajets, sans nouvelles arrivees.
6. **Envoyer le secours 01** ou **02** demarre sa mission et envoie immediatement son etat occupe. Un secours deja occupe ne peut pas repartir.
7. **Recommencer** remet le moteur et les compteurs a zero, annule les missions et envoie disponible pour les deux secours. Le debit choisi est conserve. L'historique MariaDB n'est pas efface.

Une mission declenchee pendant la pause devient occupee mais n'avance qu'apres reprise. A l'arrivee au point d'intervention, le secours attend 8 secondes simulees puis revient a la caserne. Il repasse disponible a son retour.

Les commandes de mission se trouvent dans le premier panneau. Le panneau **Interventions**, plus bas dans la barre laterale, montre les deux etats, la progression, la distance jusqu'au prochain passage au carrefour, l'ETA et le temps de mission ecoule. Faire defiler la barre laterale si l'ecran de la VM est petit.

Les estimations utilisent la longueur du trajet et la vitesse de circulation nominale ; elles n'anticipent pas les files et les feux. L'ETA vise toujours le prochain passage, y compris le passage du retour. Le temps de mission ecoule sert a departager les priorites ; ce n'est pas l'ETA.

Le panneau **Centre distant** affiche l'adresse, la liaison, le nombre de mises a jour non confirmees et les compensations en attente. `--local` desactive le reseau pour travailler uniquement sur la simulation.

## Carte et circulation

Molette : zoom. Glisser : deplacement. **Vue complete** : retour au cadrage initial. **Afficher un trajet** : choix parmi les deux parcours de secours et les douze trajets de voiture. Survoler un vehicule affiche son identifiant et sa situation.

Les voitures s'arretent au rouge et a l'orange avant d'entrer. Au vert, elles attendent aussi si le carrefour ou leur sortie sont occupes. Une voiture deja engagee finit son passage. L'autre axe n'est ouvert qu'apres degagement et les transitions de securite.

Les acces lateraux a la caserne et a l'aire d'intervention sont reserves temporairement aux secours. Les voitures peuvent donc attendre en amont de ces acces, meme loin du feu principal. C'est une regle simple de protection des croisements annexes, pas un second systeme de feux.

Les demandes de priorite admissibles sont departagees par mission la plus ancienne, puis demande la plus ancienne, puis identifiant. Une priorite attribuee n'est pas interrompue par l'autre secours. Le second ne passe pas avant le premier, meme si le meme axe est vert.

La compensation ne commence que lorsque tous les secours sont disponibles. Elle ajoute au plus 8 secondes au vert normal de l'axe penalise. Une nouvelle intervention suspend le solde non consomme.

## Centre : centre.py

La premiere table affiche les secours 01 et 02 separement. Avant le premier message, l'etat est **Inconnu**. Apres un redemarrage, elle charge les derniers etats MariaDB, avec une liaison interrompue jusqu'a reception des donnees du client.

La seconde table montre les 100 dernieres mises a jour, les plus recentes en premier. Les dates de reception sont en **UTC** et en temps reel ; elles sont distinctes du temps simule. La base conserve aussi les lignes plus anciennes.

Une coupure change l'indication de liaison, pas l'etat disponible/occupe. Un message repete lors d'une reconnexion ne cree pas une nouvelle ligne d'historique. Un identifiant de session distingue deux lancements de la simulation, dont les compteurs commencent chacun a 1.

Le centre ne commande pas les feux : ceux-ci appartiennent au moteur de la VM 1. Il affiche et conserve les etats recus.
