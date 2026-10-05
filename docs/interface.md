# Interface graphique et démonstration 2D

## Ordre conseillé pour développer le projet

1. **Dessiner la scène et construire la fenêtre.** Caserne, carrefour, routes, feux et panneau de suivi.
2. **Définir les véhicules et des trajets fixes.** Séparer les données géométriques de l’affichage.
3. **Animer les déplacements.** Ajouter le minuteur, la pause, la reprise, les vitesses et les indicateurs.
4. **Développer la circulation normale.** Arrêts aux feux, files, espacements et occupation du carrefour, avec des scénarios fixes pour tester les règles.
5. **Ajouter la génération de trafic.** Introduire ensuite les arrivées et choix de directions aléatoires, le débit réglable et la limite de 25 voitures.
6. **Développer les missions et la priorité des secours.** Distance, temps d’arrivée, seuils, arbitrage entre deux demandes et compensation, selon le cahier des charges.
7. **Connecter le centre de coordination par TCP.** Messages JSON, états distincts, numéros de mise à jour et affichage des coupures de liaison.
8. **Valider l’ensemble sur les deux ordinateurs.** Les tests sont ajoutés à chaque étape ; cette dernière étape prépare la démonstration finale.

**Les étapes 1 à 3 sont réalisées dans cette version.** Les autres restent à développer.

## Utiliser l’interface

Lancer `main.py`, puis cliquer sur **Lancer la démonstration**. Le bouton devient **Mettre en pause**, puis **Reprendre**. **Recommencer** remet le temps et les compteurs à zéro et replace les secours à la caserne ; la scène attend un nouveau lancement.

Les boutons de vitesse modifient le temps simulé, sans changer les trajets. La pause fige aussi les feux, les gyrophares et les progressions.

Sur la carte, utiliser la molette pour zoomer et glisser pour déplacer la vue. **Vue complète** rétablit le cadrage. Cocher **Afficher un trajet**, puis choisir une voiture ou un véhicule de secours dans la liste. Survoler un véhicule affiche son identifiant et son parcours.

Le centre de coordination affiche séparément les secours **01** et **02**. Dans cette démonstration, ils partent aux instants prévus, restent occupés pendant leur parcours et reviennent disponibles après leur retour. Les deux missions se chevauchent dans le temps.

## Ce que fait le scénario fixe

Les voitures répètent huit parcours sur une période de 40 secondes. Les deux secours répètent leurs missions sur une période de 80 secondes. Les virages suivent des courbes échantillonnées ; les positions et les orientations sont interpolées pour obtenir des déplacements continus.

Les feux affichent une séquence fixe : Nord–Sud vert 8 s, orange 1 s, rouge simultané 1 s, puis la même séquence pour Est–Ouest. Les temps d’attente des véhicules sont préparés à l’avance dans `src/simulation/demo.py` ; le programme ne décide pas encore s’ils peuvent entrer dans le carrefour.

Il n’y a pas encore de débit de génération de trafic ni de commandes pour déclencher librement une mission : ces commandes dépendront du futur moteur de simulation.

## Séparation du code

- `src/models/route.py` ne dépend pas de Qt : il décrit les points et donne une position et une orientation le long d’un trajet.
- `src/simulation/demo.py` décrit la chronologie fixe et produit un état visuel à un instant donné.
- `src/gui/map_view.py` dessine uniquement cet état.
- `src/gui/main_window.py` gère les commandes, le minuteur et les panneaux.

Le futur moteur pourra remplacer `DemoScenario` sans réécrire toute la scène graphique. Les algorithmes de circulation, d’espacement, de priorité, de compensation et le réseau ne doivent pas être ajoutés dans les fonctions de dessin.

## Vérifications réalisées

- Huit tests `unittest`, dont dix minutes de temps simulé.
- Contrôle des entrées et sorties, des virages et des transitions de couleur des feux.
- Contrôle des états indépendants et du retour des secours.
- Contrôle échantillonné des écarts entre véhicules sur un cycle complet de démonstration.
- Vérification PyQt6 des commandes, du minuteur et de la réinitialisation.
- Inspection de l’aperçu de la fenêtre.

Le [cahier des charges](Cahier_des_charges_SAE302.pdf) définit les exigences des étapes suivantes.
