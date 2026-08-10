"""Executable contracts for Flypath documents, publication, and cloning."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
import math
import unittest

from flypath_document import (
    DocumentValidationError,
    FlypathRecord,
    LensState,
    RevisionConflictError,
    RevisionDocument,
    Segment,
    Waypoint,
    clone_published,
    create_private_flypath,
    deserialize_document,
    owner_may_edit,
    publish,
    readable_revision,
    save_draft,
    seal_document,
    serialize_document,
    validate_document,
    validate_record,
)


NOW = datetime(2026, 8, 10, 1, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 8, 10, 2, 0, tzinfo=timezone.utc)
IDENTITY = (0.0, 0.0, 0.0, 1.0)


def authored_document(revision: int = 1) -> RevisionDocument:
    waypoints = (
        Waypoint(1, (0.0, 0.0, 100.0), IDENTITY, IDENTITY, hold_seconds=0.5),
        Waypoint(
            2,
            (500.0, 100.0, 250.0),
            IDENTITY,
            (0.0, 0.0, math.sqrt(0.5), math.sqrt(0.5)),
            LensState(50.0, 2.0, 800.0),
            hold_seconds=1.0,
        ),
        Waypoint(7, (900.0, -300.0, 400.0), IDENTITY, IDENTITY),
    )
    segments = (
        Segment(10, 1, 2, 3.0, "linear", "linear"),
        Segment(11, 2, 7, 4.5, "auto_cinematic", "ease_in_out"),
    )
    return seal_document(
        RevisionDocument(
            revision_number=revision,
            region_id="ExiledLands",
            waypoints=waypoints,
            segments=segments,
            duration_seconds=9.0,
        )
    )


def source_record() -> FlypathRecord:
    record = create_private_flypath(
        flypath_id="flypath-source",
        owner_account_id="owner-a",
        owner_display_name="Creator",
        title="Citadel Reveal",
        region_id="ExiledLands",
        now=NOW,
    )
    record = save_draft(record, authored_document(), expected_revision=1, now=LATER)
    return publish(record, now=LATER)


class FlypathDocumentContracts(unittest.TestCase):
    def test_canonical_round_trip_and_hash_are_stable(self) -> None:
        document = authored_document()
        encoded = serialize_document(document)
        self.assertEqual(deserialize_document(encoded), document)
        self.assertEqual(serialize_document(deserialize_document(encoded)), encoded)
        self.assertNotIn(" ", encoded)
        self.assertEqual(len(document.content_hash), 64)

    def test_hash_rejects_tampered_payload(self) -> None:
        payload = json.loads(serialize_document(authored_document()))
        payload["waypoints"][0]["position"][0] = 12345.0
        with self.assertRaisesRegex(DocumentValidationError, "content hash"):
            deserialize_document(json.dumps(payload))

    def test_rejects_non_finite_and_non_normalized_camera_state(self) -> None:
        document = authored_document()
        bad_position = replace(document.waypoints[0], position=(math.nan, 0.0, 0.0))
        with self.assertRaisesRegex(DocumentValidationError, "non-finite"):
            seal_document(replace(document, waypoints=(bad_position,) + document.waypoints[1:], content_hash=""))
        bad_rotation = replace(document.waypoints[0], gimbal_rotation=(0.0, 0.0, 0.0, 2.0))
        with self.assertRaisesRegex(DocumentValidationError, "normalized"):
            seal_document(replace(document, waypoints=(bad_rotation,) + document.waypoints[1:], content_hash=""))

    def test_rejects_duplicate_ids_and_broken_segment_adjacency(self) -> None:
        document = authored_document()
        duplicate = replace(document.waypoints[1], waypoint_id=1)
        with self.assertRaisesRegex(DocumentValidationError, "unique"):
            seal_document(replace(document, waypoints=(document.waypoints[0], duplicate, document.waypoints[2]), content_hash=""))
        broken = replace(document.segments[0], to_waypoint_id=7)
        with self.assertRaisesRegex(DocumentValidationError, "adjacent"):
            seal_document(replace(document, segments=(broken, document.segments[1]), content_hash=""))

    def test_new_flypath_is_private_and_owner_editable(self) -> None:
        record = create_private_flypath(
            flypath_id="new-id",
            owner_account_id="owner-a",
            owner_display_name="Creator",
            title="New Flight",
            region_id="ExiledLands",
            now=NOW,
        )
        self.assertEqual(record.visibility, "private")
        self.assertEqual(record.draft_revision_number, 1)
        self.assertIsNone(record.published)
        self.assertTrue(owner_may_edit(record, "owner-a"))
        self.assertFalse(owner_may_edit(record, "viewer-b"))
        self.assertIsNone(readable_revision(record, "viewer-b"))

    def test_save_uses_optimistic_revision_and_preserves_public_snapshot(self) -> None:
        published = source_record()
        old_snapshot = published.published
        changed = replace(authored_document(), waypoints=authored_document().waypoints[:-1], segments=authored_document().segments[:1], duration_seconds=4.5, content_hash="")
        updated = save_draft(published, changed, expected_revision=2, now=LATER)
        self.assertEqual(updated.draft_revision_number, 3)
        self.assertEqual(updated.published, old_snapshot)
        self.assertEqual(readable_revision(updated, "viewer-b"), old_snapshot)
        with self.assertRaises(RevisionConflictError):
            save_draft(updated, authored_document(), expected_revision=2, now=LATER)

    def test_clone_is_private_independent_and_attributed(self) -> None:
        source = source_record()
        clone = clone_published(
            source,
            flypath_id="flypath-clone",
            owner_account_id="owner-b",
            owner_display_name="Remixer",
            now=LATER,
        )
        self.assertEqual(clone.visibility, "private")
        self.assertEqual(clone.owner_account_id, "owner-b")
        self.assertEqual(clone.draft_revision_number, 1)
        self.assertEqual(clone.draft.waypoints, source.published.waypoints)
        self.assertEqual(clone.source_attribution.flypath_id, source.flypath_id)
        self.assertEqual(clone.source_attribution.revision_number, source.published_revision_number)
        self.assertIsNone(readable_revision(clone, "owner-a"))
        remixed_waypoint = replace(clone.draft.waypoints[0], annotation="Remixed framing")
        remixed_document = replace(
            clone.draft,
            waypoints=(remixed_waypoint,) + clone.draft.waypoints[1:],
            content_hash="",
        )
        changed_clone = save_draft(clone, remixed_document, expected_revision=1, now=LATER)
        self.assertEqual(changed_clone.draft.waypoints[0].annotation, "Remixed framing")
        self.assertEqual(source.published.waypoints[0].annotation, "")
        self.assertEqual(source.published, source.draft)

    def test_private_or_unpublished_source_cannot_be_cloned(self) -> None:
        private = create_private_flypath(
            flypath_id="private",
            owner_account_id="owner-a",
            owner_display_name="Creator",
            title="Private",
            region_id="ExiledLands",
            now=NOW,
        )
        with self.assertRaisesRegex(DocumentValidationError, "published"):
            clone_published(
                private,
                flypath_id="clone",
                owner_account_id="owner-b",
                owner_display_name="Viewer",
                now=LATER,
            )

    def test_record_rejects_public_without_snapshot_and_revision_mismatch(self) -> None:
        private = create_private_flypath(
            flypath_id="record",
            owner_account_id="owner-a",
            owner_display_name="Creator",
            title="Record",
            region_id="ExiledLands",
            now=NOW,
        )
        with self.assertRaisesRegex(DocumentValidationError, "published snapshot"):
            validate_record(replace(private, visibility="public"))
        with self.assertRaisesRegex(DocumentValidationError, "draft revision"):
            validate_record(replace(private, draft_revision_number=2))


if __name__ == "__main__":
    unittest.main(verbosity=2)
