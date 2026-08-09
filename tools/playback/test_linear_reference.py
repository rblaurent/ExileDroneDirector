"""Executable contracts for the absolute-time linear playback reference."""

from __future__ import annotations

import math
import unittest

from linear_reference import Transform, evaluate_linear


IDENTITY = (0.0, 0.0, 0.0, 1.0)
POINTS = (
    Transform((0.0, 0.0, 0.0), IDENTITY),
    Transform((10.0, 0.0, 0.0), (0.0, 0.0, math.sqrt(0.5), math.sqrt(0.5))),
    Transform((10.0, 30.0, 0.0), (0.0, 0.0, 1.0, 0.0)),
)


class LinearPlaybackContracts(unittest.TestCase):
    def test_rejects_missing_segments_and_non_positive_duration(self) -> None:
        self.assertFalse(evaluate_linear((), 2.0, 0.0).valid)
        self.assertFalse(evaluate_linear(POINTS[:1], 2.0, 0.0).valid)
        self.assertFalse(evaluate_linear(POINTS, 0.0, 0.0).valid)

    def test_clamps_negative_time_to_first_waypoint(self) -> None:
        result = evaluate_linear(POINTS, 2.0, -5.0)
        self.assertTrue(result.valid)
        self.assertEqual(result.segment_index, 0)
        self.assertEqual(result.alpha, 0.0)
        self.assertEqual(result.transform, POINTS[0])

    def test_hits_every_authored_endpoint_exactly(self) -> None:
        middle = evaluate_linear(POINTS, 2.0, 2.0)
        end = evaluate_linear(POINTS, 2.0, 4.0)
        self.assertEqual(middle.transform, POINTS[1])
        self.assertFalse(middle.complete)
        self.assertEqual(end.transform, POINTS[2])
        self.assertTrue(end.complete)
        self.assertEqual(end.total_seconds, 4.0)

    def test_uses_equal_segment_duration_not_equal_world_speed(self) -> None:
        first_half = evaluate_linear(POINTS, 2.0, 1.0)
        second_half = evaluate_linear(POINTS, 2.0, 3.0)
        self.assertEqual(first_half.transform.position, (5.0, 0.0, 0.0))
        self.assertEqual(second_half.transform.position, (10.0, 15.0, 0.0))

    def test_direct_evaluation_is_history_independent(self) -> None:
        direct = evaluate_linear(POINTS, 2.0, 2.75)
        for sample in (0.1, 0.7, 1.9, 2.1, 2.74):
            evaluate_linear(POINTS, 2.0, sample)
        repeated = evaluate_linear(POINTS, 2.0, 2.75)
        self.assertEqual(direct, repeated)

    def test_quaternion_interpolation_takes_shortest_equivalent_path(self) -> None:
        equivalent = (
            Transform((0.0, 0.0, 0.0), IDENTITY),
            Transform((1.0, 0.0, 0.0), tuple(-v for v in IDENTITY)),
        )
        result = evaluate_linear(equivalent, 1.0, 0.5)
        self.assertEqual(result.transform.rotation, IDENTITY)


if __name__ == "__main__":
    unittest.main(verbosity=2)
