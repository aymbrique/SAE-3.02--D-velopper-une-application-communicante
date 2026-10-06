"""Regles metier du cahier des charges, sans interface ni reseau."""

from itertools import combinations
from math import hypot, inf
import unittest

from src.simulation.engine import GAP, Simulation
from src.simulation.lights import Lights, Request


def tick(lights, duration, requests=(), busy=False, clear=True):
    for _ in range(round(duration / 0.05)):
        lights.advance(0.05, requests, busy, clear)


class LightsTests(unittest.TestCase):
    def test_normal_cycle_and_clearance(self):
        lights = Lights()
        tick(lights, 8)
        self.assertEqual(lights.signal("NS"), "amber")
        tick(lights, 1)
        self.assertEqual(lights.phase, "all_red")
        tick(lights, 2, clear=False)
        self.assertEqual(lights.phase, "all_red")
        tick(lights, .05)
        self.assertEqual(lights.signal("EW"), "green")

    def test_arbitration_and_owner_not_preempted(self):
        lights = Lights()
        first = Request("02", "EW", 1, 5)
        second = Request("01", "NS", 2, 4)
        tick(lights, .05, [second, first], True)
        self.assertEqual(lights.owner.identifier, "02")
        older = Request("01", "NS", 0, 4)
        tick(lights, .05, [older, first], True)
        self.assertEqual(lights.owner.identifier, "02")
        tick(lights, .05, [older], True)
        self.assertEqual(lights.owner.identifier, "01")
        lights = Lights()
        tick(lights, .05, [Request("02", "NS", 0, 4), Request("01", "NS", 0, 5)], True)
        self.assertEqual(lights.owner.identifier, "02")
        lights = Lights()
        tick(lights, .05, [Request("02", "NS", 0, 4), Request("01", "NS", 0, 4)], True)
        self.assertEqual(lights.owner.identifier, "01")

    def test_opposite_priority_finishes_current_phase(self):
        lights = Lights()
        request = [Request("01", "EW", 0, 0)]
        tick(lights, 7.95, request, True)
        self.assertEqual(lights.signal("NS"), "green")
        tick(lights, .05, request, True)
        self.assertEqual(lights.phase, "amber")
        tick(lights, 2, request, True)
        self.assertEqual(lights.signal("EW"), "green")

    def test_continuous_priority_debt_and_compensation_cap(self):
        lights = Lights()
        tick(lights, 10, [Request("01", "NS", 0, 0)], True)
        tick(lights, 10, [Request("02", "NS", 1, 1)], True)
        self.assertAlmostEqual(lights.debt["EW"], 8)
        tick(lights, 2.05, busy=True)
        self.assertEqual(lights.signal("EW"), "green")
        self.assertFalse(lights.compensating)
        tick(lights, 20, busy=False)
        self.assertTrue(lights.compensating)
        self.assertEqual(lights.axis, "EW")
        self.assertAlmostEqual(lights.compensation_budget, 8)
        tick(lights, 16)
        self.assertAlmostEqual(lights.debt["EW"], 0)
        self.assertEqual(lights.phase, "amber")

    def test_compensation_only_when_all_available_and_suspend_resume(self):
        lights = Lights()
        tick(lights, 13, [Request("01", "NS", 0, 0)], True)
        self.assertAlmostEqual(lights.debt["EW"], 5)
        tick(lights, 2.05)
        self.assertTrue(lights.compensating)
        tick(lights, 10)
        self.assertAlmostEqual(lights.debt["EW"], 3)
        tick(lights, .05, busy=True)
        self.assertFalse(lights.compensating)
        self.assertEqual(lights.phase, "amber")
        remaining = lights.debt["EW"]
        tick(lights, 22, busy=True)
        self.assertAlmostEqual(lights.debt["EW"], remaining)
        tick(lights, 10)
        self.assertTrue(lights.compensating)
        tick(lights, 11)
        self.assertAlmostEqual(lights.debt["EW"], 0)

    def test_no_debt_for_short_priority(self):
        lights = Lights()
        tick(lights, 5, [Request("01", "NS", 0, 0)], True)
        tick(lights, 2.05)
        self.assertEqual(lights.debt, {"NS": 0, "EW": 0})
        self.assertFalse(lights.compensating)


class SimulationTests(unittest.TestCase):
    def test_distance_eta_and_threshold(self):
        sim = Simulation(rate=0)
        sim.start_mission("01")
        vehicle = sim.rescues[0]
        vehicle.crossings = ((2000, 2200, "NS"),)
        self.assertEqual(sim.requests(), [])
        vehicle.distance = 1700
        self.assertEqual(sim.approach(vehicle), (150, 7.5))
        self.assertEqual(len(sim.requests()), 1)
        vehicle.distance = 1599
        self.assertEqual(sim.requests(), [])
        vehicle.distance = 1600
        self.assertEqual(len(sim.requests()), 1)
        vehicle.speed = 0
        self.assertEqual(sim.approach(vehicle)[1], inf)

    def test_red_stop_then_green_and_completion(self):
        sim = Simulation(rate=0)
        car = sim.spawn("E", "straight")
        car.distance = car.crossing[0] - 2
        sim.advance(3)
        self.assertAlmostEqual(car.distance, car.crossing[0])
        self.assertTrue(car.waiting)
        sim.advance(10)
        self.assertGreater(car.distance, car.crossing[0])
        sim.advance(30)
        self.assertEqual(sim.completed, 1)

    def test_queue_of_five_and_same_axis_second_rescue_waits(self):
        sim = Simulation(rate=0)
        sim.lights.axis = "EW"
        cars = []
        for index in range(5):
            car = sim.spawn("N", "straight")
            car.distance = car.crossing[0] - 50 * index
            cars.append(car)
        sim.advance(5)
        self.assertTrue(all(v.waiting for v in cars))
        self.assertTrue(all(hypot(a.position[0] - b.position[0], a.position[1] - b.position[1]) >= GAP - 1e-6
                            for a, b in combinations(cars, 2)))
        sim = Simulation(rate=0)
        sim.start_mission("01")
        sim.start_mission("02")
        first, second = sim.rescues
        first.distance = first.crossings[0][0]
        second.distance = second.crossings[1][0]
        second.crossing_index = 1
        second.visited = True
        sim.advance(.1)
        self.assertEqual(sim.lights.owner.identifier, "01")
        self.assertEqual(second.distance, second.crossings[1][0])

    def test_ten_minutes_no_overlap_progress_and_two_missions(self):
        for seed, rate in ((302, 12), (51, 40)):
            with self.subTest(seed=seed, rate=rate):
                sim = Simulation(rate=rate, seed=seed)
                sim.start_mission("01")
                sim.start_mission("02")
                previous = 0
                for step in range(1200):
                    sim.advance(.5)
                    self.assertLessEqual(len(sim.cars), 25)
                    for a, b in combinations(sim.vehicles, 2):
                        distance = hypot(a.position[0] - b.position[0], a.position[1] - b.position[1])
                        self.assertGreaterEqual(distance, GAP - 1e-6, (sim.time, a.identifier, b.identifier))
                    inside = [v for v in sim.vehicles if v.crossing and v.crossing[0] < v.distance < v.crossing[1]]
                    self.assertLessEqual(len(inside), 1)
                    if step == 1079:
                        previous = sim.completed
                self.assertGreater(sim.completed, previous)
                self.assertTrue(all(not v.busy for v in sim.rescues))
                self.assertIn(("01", "disponible"), sim.events)
                self.assertIn(("02", "disponible"), sim.events)

    def test_fixed_step_independent_of_render_rate(self):
        first, second = Simulation(), Simulation()
        first.advance(10)
        for _ in range(1000):
            second.advance(.01)
        self.assertAlmostEqual(first.time, second.time)
        self.assertEqual([(v.identifier, v.distance) for v in first.cars],
                         [(v.identifier, v.distance) for v in second.cars])
