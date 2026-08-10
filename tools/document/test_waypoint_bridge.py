"""Executable parity contracts for the six-array-to-struct migration seam."""

from __future__ import annotations

import math
import unittest

from waypoint_bridge import WaypointBridgeError, rebuild_waypoints_v1


class WaypointBridgeContracts(unittest.TestCase):
    def test_empty_channels_rebuild_to_empty_snapshot(self) -> None:
        self.assertEqual(rebuild_waypoints_v1((), (), (), (), (), ()), ())

    def test_rebuild_preserves_exact_order_and_values(self) -> None:
        transforms = ({"position": [1.0, 2.0, 3.0]}, {"position": [4.0, 5.0, 6.0]})
        result = rebuild_waypoints_v1(
            (4, 9), transforms, (35.0, 50.0), (2.8, 4.0), (1000.0, 250.0), (0.0, 1.5)
        )
        self.assertEqual([item.waypoint_id for item in result], [4, 9])
        self.assertEqual(result[1].camera_transform, transforms[1])
        self.assertEqual(result[1].focal_length, 50.0)
        self.assertEqual(result[1].aperture, 4.0)
        self.assertEqual(result[1].manual_focus_distance, 250.0)
        self.assertEqual(result[1].hold_seconds, 1.5)

    def test_rebuild_is_a_value_snapshot_not_a_live_link(self) -> None:
        transform = {"position": [1.0, 2.0, 3.0]}
        result = rebuild_waypoints_v1((1,), (transform,), (35.0,), (2.8,), (1000.0,), (0.0,))
        transform["position"][0] = 999.0
        self.assertEqual(result[0].camera_transform["position"][0], 1.0)

    def test_mismatched_channels_fail_before_returning_a_partial_snapshot(self) -> None:
        with self.assertRaisesRegex(WaypointBridgeError, "not lockstep"):
            rebuild_waypoints_v1((1, 2), ("A",), (35.0, 50.0), (2.8, 4.0), (1000.0, 500.0), (0.0, 0.0))

    def test_duplicate_or_non_positive_ids_are_rejected(self) -> None:
        for ids in ((1, 1), (0, 2), (-1, 2)):
            with self.subTest(ids=ids), self.assertRaisesRegex(WaypointBridgeError, "positive and unique"):
                rebuild_waypoints_v1(ids, ("A", "B"), (35.0, 35.0), (2.8, 2.8), (1.0, 1.0), (0.0, 0.0))

    def test_non_finite_or_invalid_camera_scalars_are_rejected(self) -> None:
        invalid_cases = (
            ((math.nan,), (2.8,), (1.0,), (0.0,), "non-finite"),
            ((0.0,), (2.8,), (1.0,), (0.0,), "positive"),
            ((35.0,), (0.0,), (1.0,), (0.0,), "positive"),
            ((35.0,), (2.8,), (-1.0,), (0.0,), "negative"),
            ((35.0,), (2.8,), (1.0,), (-1.0,), "negative"),
        )
        for focal, aperture, focus, hold, message in invalid_cases:
            with self.subTest(message=message), self.assertRaisesRegex(WaypointBridgeError, message):
                rebuild_waypoints_v1((1,), ("A",), focal, aperture, focus, hold)


if __name__ == "__main__":
    unittest.main(verbosity=2)

