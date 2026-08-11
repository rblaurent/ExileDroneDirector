"""Executable repository, authority, and recovery contracts."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
import unittest

from flypath_document import (
    DocumentValidationError,
    RevisionDocument,
    Segment,
    Waypoint,
    deserialize_record,
    seal_document,
    serialize_record,
)
from flypath_repository import (
    FlypathRepository,
    RecoverableMemoryStorage,
    RepositoryLimits,
    ResultCode,
)


NOW = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 8, 10, 13, 0, tzinfo=timezone.utc)
IDENTITY = (0.0, 0.0, 0.0, 1.0)


def candidate(region: str = "ExiledLands", count: int = 2) -> RevisionDocument:
    waypoints = tuple(
        Waypoint(index + 1, (float(index * 100), 0.0, 100.0), IDENTITY, IDENTITY)
        for index in range(count)
    )
    segments = tuple(
        Segment(index + 1, index + 1, index + 2, 3.0)
        for index in range(max(0, count - 1))
    )
    return seal_document(
        RevisionDocument(
            revision_number=1,
            region_id=region,
            waypoints=waypoints,
            segments=segments,
            duration_seconds=float(len(segments) * 3),
        )
    )


class FlypathRepositoryContracts(unittest.TestCase):
    def setUp(self) -> None:
        self.storage = RecoverableMemoryStorage()
        self.repository = FlypathRepository(self.storage)
        self.assertTrue(self.repository.load().succeeded)

    def create(self, flypath_id: str = "path-a", owner: str = "owner-a"):
        result = self.repository.create(
            requester_account_id=owner,
            requester_display_name=owner.title(),
            flypath_id=flypath_id,
            title=f"Title {flypath_id}",
            region_id="ExiledLands",
            now=NOW,
        )
        self.assertEqual(result.code, ResultCode.SUCCESS)
        return result.value

    def save(self, flypath_id: str = "path-a", owner: str = "owner-a"):
        result = self.repository.save(
            requester_account_id=owner,
            flypath_id=flypath_id,
            expected_revision=1,
            candidate=candidate(),
            now=LATER,
        )
        self.assertEqual(result.code, ResultCode.SUCCESS)
        return result.value

    def test_complete_record_round_trip_is_canonical(self) -> None:
        record = self.create()
        encoded = serialize_record(record)
        self.assertEqual(deserialize_record(encoded), record)
        self.assertEqual(serialize_record(deserialize_record(encoded)), encoded)

    def test_record_rejects_non_object_and_noncanonical_or_reversed_timestamps(self) -> None:
        with self.assertRaisesRegex(DocumentValidationError, "record root"):
            deserialize_record("[]")
        record = self.create()
        envelope = json.loads(serialize_record(record))
        envelope["record"]["updatedUtc"] = "2026-08-10T11:59:59Z"
        with self.assertRaisesRegex(DocumentValidationError, "precede"):
            deserialize_record(json.dumps(envelope))
        envelope["record"]["updatedUtc"] = "2026-08-10T12:00:00+00:00"
        with self.assertRaisesRegex(DocumentValidationError, "canonical UTC"):
            deserialize_record(json.dumps(envelope))

    def test_record_envelope_rejects_unknown_integrity_or_claimed_hash(self) -> None:
        record = self.create()
        envelope = json.loads(serialize_record(record))
        envelope["integrityMode"] = "sha256-v1"
        with self.assertRaisesRegex(DocumentValidationError, "integrity mode"):
            deserialize_record(json.dumps(envelope))
        envelope["integrityMode"] = "structural-v1"
        envelope["recordContentHash"] = "fake"
        with self.assertRaisesRegex(DocumentValidationError, "reserved"):
            deserialize_record(json.dumps(envelope))

    def test_record_envelope_rejects_missing_and_unknown_fields(self) -> None:
        envelope = json.loads(serialize_record(self.create()))
        del envelope["record"]["visibility"]
        with self.assertRaisesRegex(DocumentValidationError, "missing"):
            deserialize_record(json.dumps(envelope))
        envelope = json.loads(serialize_record(self.repository.records["path-a"]))
        envelope["unexpected"] = True
        with self.assertRaisesRegex(DocumentValidationError, "extra"):
            deserialize_record(json.dumps(envelope))

    def test_record_envelope_rejects_duplicate_json_fields(self) -> None:
        encoded = serialize_record(self.create())
        duplicate = encoded.replace(
            '"integrityMode":"structural-v1"',
            '"integrityMode":"structural-v1","integrityMode":"structural-v1"',
            1,
        )
        with self.assertRaisesRegex(DocumentValidationError, "duplicate JSON field integrityMode"):
            deserialize_record(duplicate)

    def test_record_envelope_rejects_noncanonical_json(self) -> None:
        encoded = serialize_record(self.create())
        with self.assertRaisesRegex(DocumentValidationError, "not canonical"):
            deserialize_record(encoded.replace(":", ": ", 1))

    def test_create_save_restart_and_load_preserve_exact_record(self) -> None:
        self.create()
        saved = self.save()
        restarted = FlypathRepository(self.storage)
        self.assertEqual(restarted.load().code, ResultCode.SUCCESS)
        self.assertEqual(restarted.records["path-a"], saved)
        loaded = restarted.get_draft(requester_account_id="owner-a", flypath_id="path-a")
        self.assertEqual(loaded.code, ResultCode.SUCCESS)
        self.assertEqual(loaded.value, saved.draft)

    def test_private_record_is_invisible_and_uneditable_to_other_account(self) -> None:
        self.create()
        self.assertEqual(
            self.repository.get_draft(requester_account_id="viewer-b", flypath_id="path-a").code,
            ResultCode.FORBIDDEN,
        )
        self.assertEqual(
            self.repository.save(
                requester_account_id="viewer-b",
                flypath_id="path-a",
                expected_revision=1,
                candidate=candidate(),
                now=LATER,
            ).code,
            ResultCode.FORBIDDEN,
        )
        self.assertEqual(self.repository.list_public().value.total, 0)

    def test_stale_save_returns_current_revision_without_overwrite(self) -> None:
        self.create()
        saved = self.save()
        stale = self.repository.save(
            requester_account_id="owner-a",
            flypath_id="path-a",
            expected_revision=1,
            candidate=candidate(count=3),
            now=LATER,
        )
        self.assertEqual(stale.code, ResultCode.REVISION_CONFLICT)
        self.assertEqual(stale.current_revision, 2)
        self.assertEqual(self.repository.records["path-a"], saved)

    def test_publish_is_snapshot_and_unpublish_hides_without_destroying_it(self) -> None:
        self.create()
        saved = self.save()
        published = self.repository.publish(
            requester_account_id="owner-a",
            flypath_id="path-a",
            expected_revision=2,
            now=LATER,
        )
        self.assertEqual(published.code, ResultCode.SUCCESS)
        snapshot = published.value.published
        changed = self.repository.save(
            requester_account_id="owner-a",
            flypath_id="path-a",
            expected_revision=2,
            candidate=candidate(count=3),
            now=LATER,
        )
        self.assertEqual(changed.code, ResultCode.SUCCESS)
        self.assertEqual(changed.value.published, snapshot)
        self.assertEqual(self.repository.get_published(flypath_id="path-a").value, snapshot)
        hidden = self.repository.unpublish(
            requester_account_id="owner-a",
            flypath_id="path-a",
            expected_revision=3,
            now=LATER,
        )
        self.assertEqual(hidden.code, ResultCode.SUCCESS)
        self.assertEqual(hidden.value.published, snapshot)
        self.assertEqual(self.repository.get_published(flypath_id="path-a").code, ResultCode.NOT_FOUND)

    def test_clone_is_private_owned_independent_and_revision_pinned(self) -> None:
        self.create()
        self.save()
        self.repository.publish(
            requester_account_id="owner-a", flypath_id="path-a", expected_revision=2, now=LATER
        )
        wrong = self.repository.clone(
            requester_account_id="owner-b",
            requester_display_name="Viewer",
            source_flypath_id="path-a",
            source_revision=1,
            clone_flypath_id="clone-b",
            now=LATER,
        )
        self.assertEqual(wrong.code, ResultCode.REVISION_CONFLICT)
        clone = self.repository.clone(
            requester_account_id="owner-b",
            requester_display_name="Viewer",
            source_flypath_id="path-a",
            source_revision=2,
            clone_flypath_id="clone-b",
            now=LATER,
        )
        self.assertEqual(clone.code, ResultCode.SUCCESS)
        self.assertEqual(clone.value.visibility, "private")
        self.assertEqual(clone.value.owner_account_id, "owner-b")
        self.assertEqual(clone.value.source_attribution.flypath_id, "path-a")
        self.assertEqual(self.repository.list_public().value.total, 1)
        self.assertEqual(self.repository.list_mine(requester_account_id="owner-b").value.total, 1)

    def test_committed_candidate_recovers_even_if_active_pointer_was_not_updated(self) -> None:
        original = self.create()
        staged_record = replace(original, title="Committed candidate", updated_utc="2026-08-10T12:30:00Z")
        generation = self.storage.stage("path-a", serialize_record(staged_record))
        self.storage.commit("path-a", generation)
        restarted = FlypathRepository(self.storage)
        self.assertTrue(restarted.load().succeeded)
        self.assertEqual(restarted.records["path-a"].title, "Committed candidate")

    def test_uncommitted_candidate_is_ignored_after_restart(self) -> None:
        original = self.create()
        staged_record = replace(original, title="Incomplete candidate", updated_utc="2026-08-10T12:30:00Z")
        self.storage.stage("path-a", serialize_record(staged_record))
        restarted = FlypathRepository(self.storage)
        self.assertTrue(restarted.load().succeeded)
        self.assertEqual(restarted.records["path-a"], original)

    def test_corrupt_latest_committed_generation_falls_back_to_previous_valid(self) -> None:
        original = self.create()
        envelope = json.loads(serialize_record(original))
        envelope["record"]["draft"]["revisionNumber"] = 999
        generation = self.storage.stage("path-a", json.dumps(envelope))
        self.storage.commit("path-a", generation)
        self.storage.activate("path-a", generation)
        restarted = FlypathRepository(self.storage)
        self.assertTrue(restarted.load().succeeded)
        self.assertEqual(restarted.records["path-a"], original)

    def test_committed_delete_tombstone_prevents_resurrection_after_restart(self) -> None:
        self.create()
        deleted = self.repository.delete(
            requester_account_id="owner-a", flypath_id="path-a", expected_revision=1
        )
        self.assertEqual(deleted.code, ResultCode.SUCCESS)
        restarted = FlypathRepository(self.storage)
        self.assertTrue(restarted.load().succeeded)
        self.assertNotIn("path-a", restarted.records)

    def test_failed_persistence_never_mutates_authoritative_memory(self) -> None:
        original = self.create()
        self.storage.available = False
        failed = self.repository.save(
            requester_account_id="owner-a",
            flypath_id="path-a",
            expected_revision=1,
            candidate=candidate(),
            now=LATER,
        )
        self.assertEqual(failed.code, ResultCode.PERSISTENCE_UNAVAILABLE)
        self.assertEqual(self.repository.records["path-a"], original)

    def test_limits_and_region_policy_fail_before_storage_mutation(self) -> None:
        storage = RecoverableMemoryStorage()
        repository = FlypathRepository(
            storage,
            limits=RepositoryLimits(
                max_paths_per_owner=1,
                max_waypoints_per_path=1,
                max_serialized_bytes=2_000_000,
                max_title_chars=4,
                allowed_regions=("ExiledLands",),
            ),
        )
        too_long = repository.create(
            requester_account_id="owner-a",
            requester_display_name="Owner",
            flypath_id="long",
            title="Too long",
            region_id="ExiledLands",
            now=NOW,
        )
        self.assertEqual(too_long.code, ResultCode.LIMIT_EXCEEDED)
        wrong_region = repository.create(
            requester_account_id="owner-a",
            requester_display_name="Owner",
            flypath_id="wrong",
            title="Fine",
            region_id="Unknown",
            now=NOW,
        )
        self.assertEqual(wrong_region.code, ResultCode.REGION_FORBIDDEN)
        created = repository.create(
            requester_account_id="owner-a",
            requester_display_name="Owner",
            flypath_id="one",
            title="Fine",
            region_id="ExiledLands",
            now=NOW,
        )
        self.assertEqual(created.code, ResultCode.SUCCESS)
        path_limit = repository.create(
            requester_account_id="owner-a",
            requester_display_name="Owner",
            flypath_id="two",
            title="Fine",
            region_id="ExiledLands",
            now=NOW,
        )
        self.assertEqual(path_limit.code, ResultCode.LIMIT_EXCEEDED)
        waypoint_limit = repository.save(
            requester_account_id="owner-a",
            flypath_id="one",
            expected_revision=1,
            candidate=candidate(count=2),
            now=LATER,
        )
        self.assertEqual(waypoint_limit.code, ResultCode.LIMIT_EXCEEDED)

    def test_metadata_queries_are_bounded_sorted_and_payload_free(self) -> None:
        for index in range(3):
            self.create(flypath_id=f"path-{index}")
        page = self.repository.list_mine(requester_account_id="owner-a", offset=1, limit=1).value
        self.assertEqual(page.total, 3)
        self.assertEqual(len(page.items), 1)
        self.assertTrue(page.has_more)
        self.assertFalse(hasattr(page.items[0], "draft"))

if __name__ == "__main__":
    unittest.main(verbosity=2)
