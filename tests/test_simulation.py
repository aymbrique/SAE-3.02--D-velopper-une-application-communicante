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

    def test_opposite_priority_interrupts_green_and_waits_for_clearance(self):
        lights = Lights()
        tick(lights, 1)
        request = [Request("01", "EW", 0, 0)]
        tick(lights, .05, request, True)
        self.assertEqual(lights.phase, "amber")
        tick(lights, 1, request, True)
        self.assertEqual(lights.phase, "all_red")
        tick(lights, 2, request, True, clear=False)
        self.assertEqual(lights.phase, "all_red")
        tick(lights, .05, request, True)
        self.assertEqual(lights.signal("EW"), "green")

    def test_same_rescue_request_updates_axis_for_return(self):
        lights = Lights()
        tick(lights, 1, [Request("01", "NS", 0, 0)], True)
        tick(lights, .05, [Request("01", "EW", 0, 1)], True)
        self.assertEqual(lights.owner.axis, "EW")
        self.assertEqual(lights.phase, "amber")
        tick(lights, 2, [Request("01", "EW", 0, 1)], True)
        self.assertEqual(lights.signal("EW"), "green")

    def test_continuous_priority_debt_and_quarter_compensation(self):
        lights = Lights()
        tick(lights, 10, [Request("01", "NS", 0, 0)], True)
        tick(lights, 10, [Request("02", "NS", 1, 1)], True)
        self.assertAlmostEqual(lights.debt["EW"], 12)
        tick(lights, 2.05, busy=True)
        self.assertEqual(lights.signal("EW"), "green")
        self.assertTrue(lights.compensating)
        self.assertAlmostEqual(lights.compensation_budget, 3)
        tick(lights, 8)
        self.assertAlmostEqual(lights.debt["EW"], 12)
        tick(lights, 3)
        self.assertAlmostEqual(lights.debt["EW"], 9)
        self.assertEqual(lights.phase, "amber")
        tick(lights, 2)
        self.assertEqual(lights.axis, "NS")
        self.assertFalse(lights.compensating)
        tick(lights, 10)
        self.assertEqual(lights.axis, "EW")
        self.assertAlmostEqual(lights.compensation_budget, 2.25)
        tick(lights, 10.25)
        self.assertAlmostEqual(lights.debt["EW"], 6.75)
        self.assertEqual(lights.phase, "amber")

    def test_accumulation_on_either_axis_and_no_double_counting(self):
        for axis, opposite in (("NS", "EW"), ("EW", "NS")):
            with self.subTest(axis=axis):
                lights = Lights()
                lights.axis = axis
                request = [Request("02", axis, 0, 0)]
                tick(lights, 8, request, True)
                self.assertAlmostEqual(lights.debt[opposite], 0)
                tick(lights, 14, request, True)
                self.assertAlmostEqual(lights.debt[opposite], 14)
                self.assertEqual(lights.debt[axis], 0)
                tick(lights, 2.05, busy=True)
                self.assertTrue(lights.compensating)
                tick(lights, 8, busy=True)
                self.assertAlmostEqual(lights.debt[opposite], 14)
                tick(lights, 1, busy=True)
                self.assertAlmostEqual(lights.debt[opposite], 13)
                self.assertEqual(lights.debt[axis], 0)

    def test_mission_away_from_crossing_does_not_delay_compensation(self):
        lights = Lights()
        tick(lights, 12, [Request("01", "NS", 0, 0)], True)
        tick(lights, 2.05, busy=True)
        self.assertTrue(lights.compensating)
        self.assertAlmostEqual(lights.compensation_budget, 1)
        tick(lights, 9, busy=True)
        self.assertAlmostEqual(lights.debt["EW"], 3)
        self.assertEqual(lights.phase, "amber")

    def test_opposite_balances_cancel_before_planning_bonus(self):
        lights = Lights()
        lights.debt.update(NS=17, EW=15)
        tick(lights, .05)
        self.assertEqual(lights.debt, {"NS": 2, "EW": 0})
        tick(lights, 9.95)
        self.assertEqual(lights.axis, "EW")
        self.assertFalse(lights.compensating)
        tick(lights, 10)
        self.assertEqual(lights.axis, "NS")
        self.assertAlmostEqual(lights.compensation_budget, .5)
        tick(lights, 8.5)
        self.assertAlmostEqual(lights.debt["NS"], 1.5)

    def test_equal_balances_cancel_completely(self):
        lights = Lights()
        lights.debt.update(NS=15, EW=15)
        tick(lights, 30)
        self.assertEqual(lights.debt, {"NS": 0, "EW": 0})
        self.assertFalse(lights.compensating)

    def test_priority_interrupt_preserves_unserved_bonus(self):
        lights = Lights()
        lights.debt["EW"] = 8
        tick(lights, 10)
        self.assertEqual(lights.axis, "EW")
        self.assertAlmostEqual(lights.compensation_budget, 2)
        tick(lights, 9)
        self.assertAlmostEqual(lights.debt["EW"], 7)
        tick(lights, .05, [Request("01", "NS", 0, 0)], True)
        self.assertEqual(lights.phase, "amber")
        self.assertFalse(lights.compensating)
        self.assertAlmostEqual(lights.debt["EW"], 7)
        tick(lights, 2, [Request("01", "NS", 0, 0)], True)
        self.assertEqual(lights.signal("NS"), "green")
        tick(lights, 1, [Request("01", "NS", 0, 0)], True)
        tick(lights, 2.05)
        self.assertEqual(lights.axis, "EW")
        self.assertTrue(lights.compensating)
        self.assertAlmostEqual(lights.compensation_budget, 1.75)

    def test_same_axis_priority_does_not_recount_served_compensation(self):
        lights = Lights()
        lights.debt["EW"] = 8
        tick(lights, 10)
        tick(lights, 9)
        self.assertAlmostEqual(lights.debt["EW"], 7)
        tick(lights, 1, [Request("01", "EW", 0, 0)], True)
        self.assertFalse(lights.compensating)
        # Une seule seconde de priorite nouvelle compense une seconde du solde.
        # La seconde de bonus deja servie ne doit pas etre recomptee.
        self.assertAlmostEqual(lights.debt["EW"], 6)
        self.assertEqual(lights.debt["NS"], 0)

    def test_small_balance_is_fully_repaid_after_finite_cycles(self):
        lights = Lights()
        lights.debt["EW"] = .12
        for _ in range(1200):
            lights.advance(.05)
            if not any(lights.debt.values()):
                break
        self.assertEqual(lights.debt, {"NS": 0, "EW": 0})
        tick(lights, 20)
        self.assertFalse(lights.compensating)
        self.assertEqual(lights.compensation_budget, 0)

    def test_bonus_does_not_subtract_more_than_its_budget(self):
        lights = Lights()
        lights.debt["EW"] = 1.01
        tick(lights, 10)
        self.assertAlmostEqual(lights.compensation_budget, .2525)
        tick(lights, 8.3)
        self.assertEqual(lights.phase, "amber")
        self.assertAlmostEqual(lights.debt["EW"], .7575)

    def test_priority_before_bonus_keeps_all_unserved_debt(self):
        lights = Lights()
        lights.debt["EW"] = 8
        tick(lights, 10)
        tick(lights, 2)
        tick(lights, .05, [Request("01", "EW", 0, 0)], True)
        self.assertFalse(lights.compensating)
        self.assertAlmostEqual(lights.debt["EW"], 8)
        tick(lights, .05)
        self.assertEqual(lights.phase, "amber")
        tick(lights, 12)
        self.assertEqual(lights.axis, "EW")
        self.assertAlmostEqual(lights.compensation_budget, 2)
        tick(lights, 10)
        self.assertAlmostEqual(lights.debt["EW"], 6)

    def test_short_priority_then_clearance_does_not_pay_during_red(self):
        lights = Lights()
        lights.debt["EW"] = 4
        request = [Request("01", "NS", 0, 0)]
        tick(lights, 1, request, True)
        tick(lights, .05)
        tick(lights, 1)
        self.assertEqual(lights.phase, "all_red")
        tick(lights, 3, clear=False)
        self.assertEqual(lights.phase, "all_red")
        self.assertAlmostEqual(lights.debt["EW"], 4)
        tick(lights, .05)
        self.assertEqual(lights.axis, "EW")
        self.assertAlmostEqual(lights.compensation_budget, 1)
        tick(lights, 9)
        self.assertAlmostEqual(lights.debt["EW"], 3)

    def test_new_priority_accumulation_nets_existing_opposite_balance(self):
        lights = Lights()
        lights.debt["NS"] = 2
        request = [Request("01", "NS", 0, 0)]
        tick(lights, 9, request, True)
        self.assertAlmostEqual(lights.debt["NS"], 1)
        self.assertAlmostEqual(lights.debt["EW"], 0)
        tick(lights, 2, request, True)
        self.assertAlmostEqual(lights.debt["NS"], 0)
        self.assertAlmostEqual(lights.debt["EW"], 1)

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
        # La sortie de caserne demande desormais le vert sans attendre le seuil.
        # Tester la regle d'approche une fois cette sortie deja franchie.
        vehicle.distance = next(end for _, end, key in vehicle.route.junctions if key == "F")
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
                    for a, b in combinations(inside, 2):
                        self.assertTrue(sim.can_share_crossing(a, b))
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
