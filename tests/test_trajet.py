"""Interpolation et validation des trajets utilises par la simulation."""

import unittest
from src.modeles.trajet import Trajet


class TestsTrajet(unittest.TestCase):
    def test_position_orientation_et_bornes(self):
        trajet = Trajet("Angle", ((0, 0), (10, 0), (10, 10)))
        self.assertEqual(trajet.position_a(-5), (0, 0, 0))
        self.assertEqual(trajet.position_a(5), (5, 0, 0))
        self.assertEqual(trajet.position_a(15), (10, 5, 90))
        self.assertEqual(trajet.position_a(25), (10, 10, 90))

    def test_refus_trajet_vide_ou_sans_longueur(self):
        with self.assertRaises(ValueError):
            Trajet("Vide", ((0, 0),))
        with self.assertRaises(ValueError):
            Trajet("Doublon", ((0, 0), (0, 0)))


if __name__ == "__main__":
    unittest.main()
