"""Executable contracts for transactional typed Flypath document sync."""

from __future__ import annotations

from dataclasses import replace
import math
import unittest

from document_bridge import (
    DocumentBridgeError,
    FlypathDocumentBridgeV1,
    MAX_BLUEPRINT_INTEGER,
    SegmentBridgeV1,
    sync_draft_document_v1,
)
from waypoint_bridge import WaypointBridgeV1


def waypoint(waypoint_id: int, *, hold: float = 0.0, transform=None) -> WaypointBridgeV1:
    return WaypointBridgeV1(
        waypoint_id=waypoint_id,
        camera_transform=transform if transform is not None else {"location": [waypoint_id, 0, 0]},
        focal_length=35.0,
        aperture=2.8,
        manual_focus_distance=1000.0,
        hold_seconds=hold,
    )


class DocumentBridgeContracts(unittest.TestCase):
    def test_empty_and_single_waypoint_snapshots_need_no_segments(self) -> None:
        segments, document = sync_draft_document_v1(())
        self.assertEqual(segments, ())
        self.assertEqual(document.duration_seconds, 0.0)
        self.assertEqual(document.waypoints, ())
        self.assertEqual(document.segments, ())

        segments, document = sync_draft_document_v1((waypoint(7, hold=1.25),))
        self.assertEqual(segments, ())
        self.assertEqual(document.duration_seconds, 1.25)

    def test_new_adjacencies_receive_ordered_positive_ids_and_defaults(self) -> None:
        segments, document = sync_draft_document_v1(
            (waypoint(4, hold=0.5), waypoint(9), waypoint(20, hold=1.0))
        )
        self.assertEqual(
            segments,
            (
                SegmentBridgeV1(1, 4, 9, 3.0, "linear", "linear"),
                SegmentBridgeV1(2, 9, 20, 3.0, "linear", "linear"),
            ),
        )
        self.assertEqual(document.duration_seconds, 7.5)
        self.assertEqual(document.segments, segments)

    def test_surviving_adjacency_preserves_identity_and_every_authored_edit(self) -> None:
        edited = SegmentBridgeV1(41, 4, 9, 8.5, "auto_cinematic", "ease_in_out")
        segments, document = sync_draft_document_v1(
            (waypoint(4), waypoint(9)),
            (edited,),
            FlypathDocumentBridgeV1(
                revision_number=6,
                region_id="ExiledLands",
                default_flight_profile="fpv_hybrid",
                content_hash="stale",
            ),
        )
        self.assertEqual(segments, (edited,))
        self.assertEqual(document.revision_number, 6)
        self.assertEqual(document.region_id, "ExiledLands")
        self.assertEqual(document.default_flight_profile, "fpv_hybrid")
        self.assertEqual(document.duration_seconds, 8.5)
        self.assertEqual(document.content_hash, "")

    def test_new_adjacency_allocates_above_prior_ids_without_recycling(self) -> None:
        prior = (
            SegmentBridgeV1(12, 1, 2, 4.0, "linear", "linear"),
            SegmentBridgeV1(30, 2, 3, 5.0, "glide", "ease_out"),
        )
        segments, _ = sync_draft_document_v1((waypoint(1), waypoint(3)), prior)
        self.assertEqual(segments, (SegmentBridgeV1(31, 1, 3),))

    def test_invalid_or_duplicate_prior_candidates_are_replaced_safely(self) -> None:
        prior = (
            SegmentBridgeV1(5, 1, 2, -1.0, "linear", "linear"),
            SegmentBridgeV1(9, 1, 2, 2.0, "", "linear"),
            SegmentBridgeV1(11, 1, 2, 2.5, "glide", "ease_in"),
            SegmentBridgeV1(11, 2, 3, 7.0, "glide", "ease_out"),
        )
        segments, _ = sync_draft_document_v1(
            (waypoint(1), waypoint(2), waypoint(3)), prior
        )
        self.assertEqual(segments[0], prior[2])
        self.assertEqual(segments[1], SegmentBridgeV1(12, 2, 3))
        self.assertEqual(len({segment.segment_id for segment in segments}), 2)

    def test_invalid_waypoints_fail_without_mutating_prior_snapshots(self) -> None:
        prior_segments = [SegmentBridgeV1(8, 1, 2, 4.0, "glide", "ease_in")]
        prior_document = FlypathDocumentBridgeV1(
            revision_number=2,
            waypoints=(waypoint(1), waypoint(2)),
            segments=tuple(prior_segments),
            duration_seconds=4.0,
            content_hash="prior",
        )
        with self.assertRaisesRegex(DocumentBridgeError, "positive and unique"):
            sync_draft_document_v1((waypoint(1), waypoint(1)), prior_segments, prior_document)
        self.assertEqual(prior_segments, [SegmentBridgeV1(8, 1, 2, 4.0, "glide", "ease_in")])
        self.assertEqual(prior_document.content_hash, "prior")

    def test_invalid_scalar_metadata_and_duration_are_rejected(self) -> None:
        cases = (
            ((replace(waypoint(1), focal_length=math.nan),), (), None, 3.0, "non-finite"),
            ((replace(waypoint(1), aperture=0.0),), (), None, 3.0, "positive"),
            ((replace(waypoint(1), hold_seconds=-1.0),), (), None, 3.0, "negative"),
            ((waypoint(1), waypoint(2)), (), None, 0.0, "positive"),
            ((waypoint(1),), (), replace(FlypathDocumentBridgeV1(), schema_version=2), 3.0, "schema"),
            ((waypoint(1),), (), replace(FlypathDocumentBridgeV1(), revision_number=-1), 3.0, "revision"),
            ((waypoint(1),), (), replace(FlypathDocumentBridgeV1(), default_flight_profile=" "), 3.0, "profile"),
        )
        for waypoints, segments, document, duration, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(DocumentBridgeError, message):
                sync_draft_document_v1(
                    waypoints,
                    segments,
                    document,
                    default_segment_duration_seconds=duration,
                )

    def test_output_is_a_deep_value_snapshot(self) -> None:
        transform = {"location": [1.0, 2.0, 3.0]}
        source = [waypoint(1, transform=transform)]
        _, document = sync_draft_document_v1(source)
        transform["location"][0] = 999.0
        source.clear()
        self.assertEqual(document.waypoints[0].camera_transform["location"][0], 1.0)

    def test_exhausted_segment_id_space_rejects_transaction(self) -> None:
        prior = (SegmentBridgeV1(MAX_BLUEPRINT_INTEGER, 10, 11),)
        with self.assertRaisesRegex(DocumentBridgeError, "exhausted"):
            sync_draft_document_v1((waypoint(1), waypoint(2)), prior)

        segments, _ = sync_draft_document_v1((waypoint(10), waypoint(11)), prior)
        self.assertEqual(segments, prior)


if __name__ == "__main__":
    unittest.main(verbosity=2)
