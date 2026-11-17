"""Specification simulations; these do not close product acceptance tests."""

import json
import unittest

from detector import Detector


def feed(detector, start, end, distance):
    return [detector.step(t, distance) for t in range(start, end+1, 5)]


class DetectorTests(unittest.TestCase):
    def test_three_new_values_required(self):
        d = Detector(1300)
        self.assertEqual(d.step(0, 130).health, "WARMUP")
        self.assertIsNone(d.step(5, 130).fill_pct)
        self.assertAlmostEqual(d.step(10, 130).fill_pct, 90)

    def test_no_calibration_no_decision(self):
        results = feed(Detector(), 0, 200, 130)
        self.assertTrue(all(r.health == "UNCALIBRATED" for r in results))
        self.assertTrue(all(r.fill_pct is None and not r.full_latched for r in results))

    def test_first_filtered_threshold_starts_sixty_seconds(self):
        d = Detector(1300)
        self.assertFalse(feed(d, 0, 65, 260)[-1].full_latched)
        self.assertEqual(d.step(70, 260).transition, "full_confirmed")

    def test_no_new_event_during_two_hours_full(self):
        results = feed(Detector(1300), 0, 7270, 130)
        self.assertEqual(sum(r.transition == "full_confirmed" for r in results), 1)
        ids = {r.event_id for r in results if r.event_id}
        self.assertEqual(len(ids), 1)

    def test_twenty_short_obstructions_do_not_latch(self):
        d = Detector(1300)
        transitions = []
        t = 0
        for _ in range(20):
            for value in [1300]*5 + [130]*2 + [1300]*5:
                transitions.append(d.step(t, value).transition)
                t += 5
        self.assertNotIn("full_confirmed", transitions)

    def test_clear_requires_one_hundred_twenty_filtered_seconds(self):
        d = Detector(1300)
        feed(d, 0, 70, 130)
        # Median first clears at t=80, not on the first changed raw sample.
        self.assertTrue(feed(d, 75, 195, 1300)[-1].full_latched)
        self.assertEqual(d.step(200, 1300).transition, "cleared")

    def test_new_cycle_has_new_id(self):
        d = Detector(1300)
        first = feed(d, 0, 70, 130)[-1].event_id
        feed(d, 75, 200, 1300)
        second = feed(d, 205, 270, 130)[-1]
        self.assertEqual(second.transition, "full_confirmed")
        self.assertNotEqual(first, second.event_id)

    def test_hysteresis_holds_both_prior_states(self):
        normal = feed(Detector(1300), 0, 500, 520)[-1]
        d = Detector(1300)
        first = feed(d, 0, 70, 130)[-1].event_id
        full = feed(d, 75, 575, 520)[-1]
        self.assertFalse(normal.full_latched)
        self.assertTrue(full.full_latched)
        self.assertEqual(full.event_id, first)

    def test_invalid_resets_full_timer_and_window(self):
        d = Detector(1300)
        feed(d, 0, 35, 130)
        self.assertEqual(d.step(40, None, valid=False).health, "WARMUP")
        self.assertFalse(feed(d, 45, 110, 130)[-1].full_latched)
        self.assertEqual(d.step(115, 130).transition, "full_confirmed")

    def test_invalid_resets_clear_timer_without_dropping_latch(self):
        d = Detector(1300)
        feed(d, 0, 70, 130)
        first = d.event_id
        feed(d, 75, 130, 1300)
        d.step(135, valid=False)
        self.assertEqual(d.event_id, first)
        self.assertTrue(feed(d, 140, 265, 1300)[-1].full_latched)
        self.assertEqual(d.step(270, 1300).transition, "cleared")

    def test_fault_exactly_thirty_seconds_after_last_valid(self):
        d = Detector(1300)
        d.step(0, 1300)
        self.assertNotEqual(d.tick(29).health, "SENSOR_FAULT")
        self.assertEqual(d.tick(30).health, "SENSOR_FAULT")

    def test_fault_without_any_sample(self):
        self.assertEqual(Detector(1300).tick(30).health, "SENSOR_FAULT")

    def test_fault_preserves_full_event_and_requires_new_warmup(self):
        d = Detector(1300)
        first = feed(d, 0, 70, 130)[-1].event_id
        fault = d.tick(100)
        self.assertEqual(fault.health, "SENSOR_FAULT")
        self.assertEqual(fault.event_id, first)
        self.assertTrue(fault.full_latched)
        self.assertEqual(d.step(105, 130).health, "WARMUP")
        self.assertEqual(feed(d, 110, 115, 130)[-1].health, "OK")
        self.assertEqual(d.event_id, first)

    def test_bad_measurements_do_not_become_full(self):
        d = Detector(1300)
        for t, value in enumerate([0, -1, float("nan"), float("inf"), 5000]):
            result = d.step(t*5, value)
            self.assertIsNone(result.fill_pct)
            self.assertFalse(result.full_latched)

    def test_bad_sensor_status_overrides_plausible_distance(self):
        result = Detector(1300).step(0, 130, valid=False)
        self.assertIsNone(result.fill_pct)

    def test_missed_schedule_does_not_count_as_continuous_full(self):
        d = Detector(1300)
        feed(d, 0, 35, 130)
        self.assertEqual(d.step(100, 130).health, "WARMUP")
        self.assertFalse(d.full_latched)

    def test_reboot_preserves_identity_but_not_timers_or_samples(self):
        d = Detector(1300)
        first = feed(d, 0, 70, 130)[-1].event_id
        restored = Detector.restore(json.loads(json.dumps(d.snapshot())), 1000)
        result = restored.step(1000, 130)
        self.assertEqual(result.health, "WARMUP")
        self.assertEqual(result.event_id, first)
        self.assertTrue(result.full_latched)
        self.assertIsNone(restored.clear_since)

    def test_distance_beyond_calibrated_bottom_clamps_to_zero_height(self):
        self.assertEqual(feed(Detector(1300), 0, 10, 1400)[-1].fill_pct, 0)

    def test_rejects_invalid_calibration_and_inconsistent_restore(self):
        for h in [0, -1, float("nan"), float("inf")]:
            with self.assertRaises(ValueError):
                Detector(h)
        with self.assertRaises(ValueError):
            Detector(1300, full_latched=True)

    def test_rejects_reused_or_reversed_sample_time(self):
        d = Detector(1300)
        d.step(10, 130)
        with self.assertRaises(ValueError):
            d.step(10, 130)
        with self.assertRaises(ValueError):
            d.tick(9)


if __name__ == "__main__":
    unittest.main()
