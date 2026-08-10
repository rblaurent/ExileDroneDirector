from __future__ import annotations

import math
import unittest

from linear_preview import Vector3, build_linear_preview


class LinearPreviewContracts(unittest.TestCase):
    def test_empty_document_has_no_instances(self):
        preview = build_linear_preview([])
        self.assertEqual(preview.markers, ())
        self.assertEqual(preview.segments, ())

    def test_single_waypoint_has_one_marker_and_no_segment(self):
        preview = build_linear_preview([(10.0, 20.0, 30.0)])
        self.assertEqual(len(preview.markers), 1)
        self.assertEqual(preview.markers[0].location, Vector3(10.0, 20.0, 30.0))
        self.assertEqual(preview.markers[0].scale, Vector3(0.2, 0.2, 0.2))
        self.assertEqual(preview.segments, ())

    def test_segment_is_centered_oriented_and_scaled_along_local_x(self):
        preview = build_linear_preview([(0.0, 0.0, 0.0), (300.0, 400.0, 0.0)])
        self.assertEqual(len(preview.markers), 2)
        self.assertEqual(len(preview.segments), 1)
        segment = preview.segments[0]
        self.assertEqual(segment.location, Vector3(150.0, 200.0, 0.0))
        self.assertAlmostEqual(segment.rotation.pitch, 0.0)
        self.assertAlmostEqual(segment.rotation.yaw, math.degrees(math.atan2(400.0, 300.0)))
        self.assertEqual(segment.scale, Vector3(5.0, 0.03, 0.03))

    def test_vertical_segment_uses_pitch_without_roll(self):
        segment = build_linear_preview([(1.0, 2.0, 3.0), (1.0, 2.0, 203.0)]).segments[0]
        self.assertAlmostEqual(segment.rotation.pitch, 90.0)
        self.assertAlmostEqual(segment.rotation.yaw, 0.0)
        self.assertAlmostEqual(segment.rotation.roll, 0.0)
        self.assertEqual(segment.scale, Vector3(2.0, 0.03, 0.03))

    def test_degenerate_adjacency_keeps_markers_but_skips_segment(self):
        preview = build_linear_preview([(4.0, 5.0, 6.0), (4.0, 5.0, 6.0)])
        self.assertEqual(len(preview.markers), 2)
        self.assertEqual(preview.segments, ())

    def test_projection_is_ordered_and_history_independent(self):
        points = [(0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (100.0, 100.0, 0.0)]
        first = build_linear_preview(points)
        second = build_linear_preview(points)
        self.assertEqual(first, second)
        self.assertEqual([marker.location for marker in first.markers], [Vector3(*point) for point in points])
        self.assertEqual([segment.rotation.yaw for segment in first.segments], [0.0, 90.0])

    def test_invalid_geometry_or_style_is_rejected(self):
        for points, kwargs in (
            ([(float("nan"), 0.0, 0.0)], {}),
            ([], {"marker_scale": 0.0}),
            ([], {"line_thickness_scale": -1.0}),
            ([], {"source_cube_extent": 0.0}),
            ([], {"zero_length_epsilon": -1.0}),
        ):
            with self.subTest(points=points, kwargs=kwargs):
                with self.assertRaises(ValueError):
                    build_linear_preview(points, **kwargs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
