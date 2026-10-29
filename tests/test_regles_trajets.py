"""Sens du raccordement Est et mouvements des carrefours secondaires."""

from itertools import product
from math import hypot
import unittest

from src.modeles.plan import (
    MARGE_DEGAGEMENT, DESTINATIONS, NOEUDS, PARKING_X, PARKING_Y, TRONCONS_ROUTES,
    DEMI_LARGEUR_ROUTE, HAUTEUR_SCENE, LARGEUR_SCENE, ENTREES_SITES, DISTANCE_ARRET, DISTANCE_VIRAGE,
    construire_trajet, trajet_voiture, direction, point_sur_voie, trajet_secours,
)


class TestsReglesTrajets(unittest.TestCase):
    def verifier_troncons_autorises(self, trajet):
        autorise = {frozenset(troncon) for troncon in TRONCONS_ROUTES}
        autorise.add(frozenset(("depot", "F")))
        for cote, entree in ENTREES_SITES.items():
            autorise.add(frozenset((entree, "site_" + cote)))
        for premier, second in zip(trajet.noeuds, trajet.noeuds[1:]):
            self.assertIn(frozenset((premier, second)), autorise)
            self.assertNotEqual((premier, second), ("Q", "R"))
        for mouvement in zip(trajet.noeuds, trajet.noeuds[1:], trajet.noeuds[2:]):
            self.assertNotEqual(mouvement, ("E", "R", "Q"))

    def verifier_directions_des_mouvements(self, trajet):
        attendu = {}
        virages_attendus = []
        for index, cle in enumerate(trajet.noeuds[1:-1], 1):
            if cle.startswith("site_"):
                continue
            entree_direction = direction(NOEUDS[trajet.noeuds[index - 1]], NOEUDS[cle])
            sortie_direction = direction(NOEUDS[cle], NOEUDS[trajet.noeuds[index + 1]])
            if entree_direction != sortie_direction:
                virages_attendus.append((cle, entree_direction, sortie_direction))
            if cle == "C":
                continue
            attendu.setdefault(cle, []).append((entree_direction, sortie_direction))
        cles_mouvements = set()
        for arret, fin, cle in trajet.raccordements:
            if cle == "parking" or cle.startswith("site_"):
                self.assertNotIn((arret, cle), trajet.mouvements_raccordements)
                continue
            cles_mouvements.add((arret, cle))
            entree_direction, sortie_direction = trajet.mouvements_raccordements[(arret, cle)]
            self.assertEqual((entree_direction, sortie_direction), attendu[cle].pop(0))
            self.assertAlmostEqual(hypot(*entree_direction), 1)
            self.assertAlmostEqual(hypot(*sortie_direction), 1)
            for obtenu, souhaite in zip(trajet.position_a(arret)[:2],
                                      point_sur_voie(NOEUDS[cle], entree_direction, -DISTANCE_ARRET)):
                self.assertAlmostEqual(obtenu, souhaite)
            for obtenu, souhaite in zip(trajet.position_a(fin - MARGE_DEGAGEMENT)[:2],
                                      point_sur_voie(NOEUDS[cle], sortie_direction, DISTANCE_VIRAGE)):
                self.assertAlmostEqual(obtenu, souhaite)
        self.assertEqual(set(trajet.mouvements_raccordements), cles_mouvements)
        self.assertTrue(all(not mouvements for mouvements in attendu.values()))
        self.assertEqual(len(trajet.zones_virage), len(virages_attendus))
        derniere_fin = 0
        for (debut, fin), (cle, entree_direction, sortie_direction) in zip(trajet.zones_virage, virages_attendus):
            self.assertGreaterEqual(debut, derniere_fin)
            self.assertGreater(fin, debut)
            self.assertLessEqual(fin, trajet.longueur)
            for obtenu, souhaite in zip(trajet.position_a(debut)[:2],
                                      point_sur_voie(NOEUDS[cle], entree_direction, -DISTANCE_VIRAGE)):
                self.assertAlmostEqual(obtenu, souhaite)
            for obtenu, souhaite in zip(trajet.position_a(fin)[:2],
                                      point_sur_voie(NOEUDS[cle], sortie_direction, DISTANCE_VIRAGE)):
                self.assertAlmostEqual(obtenu, souhaite)
            derniere_fin = fin

    def test_douze_trajets_sur_routes_autorisees_et_sorties_aux_bords(self):
        for origine, virage in product("NSEW", ("straight", "left", "right")):
            with self.subTest(origine=origine, virage=virage):
                trajet, arret = trajet_voiture(origine, virage)
                self.assertIsInstance(trajet.noeuds, tuple)
                self.assertEqual(trajet.noeuds.count("C"), 1)
                self.assertEqual(arret, trajet.passages[0][0])
                self.verifier_troncons_autorises(trajet)
                self.verifier_directions_des_mouvements(trajet)
                self.verifier_trajet_sur_routes(trajet)
                for x, y in (trajet.points[0], trajet.points[-1]):
                    self.assertTrue(x < 0 or x > LARGEUR_SCENE or y < 0 or y > HAUTEUR_SCENE)

    def test_voitures_vers_sud_sortent_par_est_en_bas(self):
        for origine, virage in (("N", "straight"), ("W", "right"), ("E", "left")):
            with self.subTest(origine=origine, virage=virage):
                trajet, _ = trajet_voiture(origine, virage)
                self.assertEqual(trajet.noeuds[-4:], ("C", "D", "Q", "low_east"))
                self.assertGreater(trajet.points[-1][0], LARGEUR_SCENE)
                self.assertNotIn("R", trajet.noeuds)

    def test_trajets_secours_destinations_parkings_et_sens_autorises(self):
        for (identifiant, parking_y), destination in product(PARKING_Y.items(), DESTINATIONS):
            with self.subTest(identifiant=identifiant, destination=destination):
                trajet, passages, arret_intervention = trajet_secours(identifiant, parking_y, destination)
                self.assertEqual(trajet.noeuds[0], "depot")
                self.assertEqual(trajet.noeuds[-1], "depot")
                self.assertEqual(trajet.noeuds.count("site_" + destination), 1)
                self.assertEqual(trajet.points[0], (PARKING_X, parking_y))
                self.assertEqual(trajet.points[-1], (PARKING_X, parking_y))
                self.assertEqual(len(passages), 2)
                self.assertIsNotNone(arret_intervention)
                self.verifier_troncons_autorises(trajet)
                self.verifier_directions_des_mouvements(trajet)
                # Le retour F et l'allee de stationnement partagent leur distance
                # d'entree ; le nom fait partie de la cle pour les distinguer.
                distance_retour = [zone for zone in trajet.raccordements if zone[2] == "F"][-1]
                self.assertIn((distance_retour[0], "F"), trajet.mouvements_raccordements)
                self.assertIn((distance_retour[0], trajet.longueur, "parking"), trajet.raccordements)

    def test_branche_ouest_sud_garde_sens_du_virage(self):
        trajet = construire_trajet("Raccordement vers le bas", ["B", "R", "Q", "low_east"])
        self.verifier_troncons_autorises(trajet)
        self.verifier_directions_des_mouvements(trajet)
        arret, _, cle = next(zone for zone in trajet.raccordements if zone[2] == "R")
        self.assertEqual(trajet.mouvements_raccordements[(arret, cle)], ((1, 0), (0, 1)))

    def test_refus_des_sens_interdits(self):
        for noeuds, raison in ((["low_east", "Q", "R", "E"], "Sens interdit"),
                              (["east", "E", "R", "Q", "low_east"], "Virage interdit")):
            with self.subTest(noeuds=noeuds):
                with self.assertRaisesRegex(ValueError, raison):
                    construire_trajet("Trajet interdit", noeuds)

    def test_branche_ouest_est_tout_droit_autorisee(self):
        trajet = construire_trajet("Raccordement tout droit", ["B", "R", "E"])
        self.verifier_troncons_autorises(trajet)
        self.verifier_directions_des_mouvements(trajet)
        arret, _, cle = next(zone for zone in trajet.raccordements if zone[2] == "R")
        self.assertEqual(trajet.mouvements_raccordements[(arret, cle)], ((1, 0), (1, 0)))

    def verifier_trajet_sur_routes(self, trajet):
        for distance in range(0, int(trajet.longueur) + 1, 3):
            x, y, _ = trajet.position_a(distance)
            if not (0 <= x <= LARGEUR_SCENE and 0 <= y <= HAUTEUR_SCENE):
                continue
            sur_chaussee = False
            for premier, second in TRONCONS_ROUTES:
                ax, ay = NOEUDS[premier]
                bx, by = NOEUDS[second]
                if ax == bx:
                    sur_chaussee |= abs(x - ax) <= DEMI_LARGEUR_ROUTE and min(ay, by) <= y <= max(ay, by)
                else:
                    sur_chaussee |= abs(y - ay) <= DEMI_LARGEUR_ROUTE and min(ax, bx) <= x <= max(ax, bx)
            # Le dessin prolonge les raccordements par un carre de chaussee.
            sur_chaussee |= any(abs(x - NOEUDS[cle][0]) <= DEMI_LARGEUR_ROUTE and
                           abs(y - NOEUDS[cle][1]) <= DEMI_LARGEUR_ROUTE
                           for cle in ("C", "F", "W", "B", "R", "E", "D", "L", "Q", "U", "H"))
            self.assertTrue(sur_chaussee, (trajet.nom, distance, x, y))

    def test_variantes_sur_routes_et_sorties_hors_carte(self):
        variantes = {
            "lower_west": (("N", "straight"), ("W", "right"), ("E", "left")),
            "middle_north": (("W", "straight"), ("N", "left"), ("S", "right")),
        }
        for variante, choix in variantes.items():
            for origine, virage in choix:
                with self.subTest(variante=variante, origine=origine, virage=virage):
                    trajet, arret = trajet_voiture(origine, virage, variante=variante)
                    self.assertEqual(trajet.variante, variante)
                    self.assertEqual(trajet.noeuds.count("C"), 1)
                    self.assertEqual(len(trajet.passages), 1)
                    self.assertEqual(arret, trajet.passages[0][0])
                    self.verifier_troncons_autorises(trajet)
                    self.verifier_directions_des_mouvements(trajet)
                    self.verifier_trajet_sur_routes(trajet)
                    for x, y in (trajet.points[0], trajet.points[-1]):
                        self.assertTrue(x < 0 or x > LARGEUR_SCENE or y < 0 or y > HAUTEUR_SCENE)
                    if variante == "lower_west":
                        self.assertEqual(trajet.noeuds[-4:], ("C", "D", "L", "low_west"))
                        self.assertLess(trajet.points[-1][0], 0)
                    else:
                        self.assertEqual(trajet.noeuds[-4:], ("C", "B", "U", "top"))
                        self.assertLess(trajet.points[-1][1], 0)

    def test_directions_des_virages_secondaires(self):
        for origine, virage, variante, cle, attendu in (
                ("N", "straight", "lower_west", "D", ((0, 1), (-1, 0))),
                ("W", "straight", "middle_north", "B", ((1, 0), (0, -1)))):
            with self.subTest(variante=variante):
                trajet, _ = trajet_voiture(origine, virage, variante=variante)
                arret, _, _ = next(zone for zone in trajet.raccordements if zone[2] == cle)
                self.assertEqual(trajet.mouvements_raccordements[(arret, cle)], attendu)

    def test_virages_nord_et_est_nord_disponibles(self):
        for origine, virage, attendu in (("N", "left", ("F", "C", "B")),
                                       ("N", "right", ("F", "C", "W")),
                                       ("E", "right", ("B", "C", "F"))):
            with self.subTest(origine=origine, virage=virage):
                trajet, _ = trajet_voiture(origine, virage)
                index = trajet.noeuds.index("C")
                self.assertEqual(trajet.noeuds[index - 1:index + 2], attendu)
                self.assertIsNone(trajet.variante)
                self.verifier_trajet_sur_routes(trajet)

    def test_refus_variantes_inconnues_ou_incompatibles(self):
        for origine, virage, variante in (("N", "right", "lower_west"),
                                      ("E", "straight", "middle_north"),
                                      ("N", "straight", "inconnue")):
            with self.subTest(origine=origine, virage=virage, variante=variante):
                with self.assertRaises(ValueError):
                    trajet_voiture(origine, virage, variante=variante)

    def test_variantes_respectent_limites_visibles_elargies(self):
        limites = (-250, -200, LARGEUR_SCENE + 250, HAUTEUR_SCENE + 200)
        for variante, origine in (("lower_west", "N"), ("middle_north", "W")):
            with self.subTest(variante=variante):
                trajet, _ = trajet_voiture(origine, "straight", limites, variante=variante)
                for x, y in (trajet.points[0], trajet.points[-1]):
                    self.assertTrue(x < limites[0] or x > limites[2] or
                                    y < limites[1] or y > limites[3])


if __name__ == "__main__":
    unittest.main()
