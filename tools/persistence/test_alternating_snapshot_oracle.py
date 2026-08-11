"""Contracts for the physical two-slot Blueprint repository adapter."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "document"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from alternating_snapshot_oracle import (  # noqa: E402
    MemorySaveGameSlots,
    PersistenceError,
    RecoveryError,
    RecoveredRepository,
    RepositorySnapshot,
    SLOT_A,
    SLOT_B,
    build_candidate,
    persist_candidate,
    recover_slots,
)
from flypath_document import create_private_flypath, serialize_record  # noqa: E402


NOW = datetime(2026, 8, 11, 6, 0, tzinfo=timezone.utc)


def encoded(flypath_id: str, *, title: str | None = None) -> str:
    record = create_private_flypath(
        flypath_id=flypath_id,
        owner_account_id="owner-a",
        owner_display_name="Owner A",
        title=title or flypath_id,
        region_id="ExiledLands",
        now=NOW,
    )
    return serialize_record(record)


class AlternatingSnapshotContracts(unittest.TestCase):
    def test_empty_storage_recovers_an_empty_uninitialized_repository(self) -> None:
        recovered = recover_slots(MemorySaveGameSlots())
        self.assertEqual(recovered.records, {})
        self.assertEqual(recovered.active_generation, 0)
        self.assertEqual(recovered.active_slot, "")

    def test_successive_commits_alternate_slots_and_increment_generation(self) -> None:
        storage = MemorySaveGameSlots()
        first = persist_candidate(
            storage,
            recover_slots(storage),
            record_envelopes={"a": encoded("a")},
            tombstones=frozenset(),
        )
        self.assertEqual((first.active_slot, first.active_generation), (SLOT_A, 1))
        second = persist_candidate(
            storage,
            first,
            record_envelopes={"a": encoded("a"), "b": encoded("b")},
            tombstones=frozenset(),
        )
        self.assertEqual((second.active_slot, second.active_generation), (SLOT_B, 2))
        self.assertEqual(set(second.records), {"a", "b"})

    def test_uncommitted_newest_candidate_is_ignored(self) -> None:
        storage = MemorySaveGameSlots()
        accepted = persist_candidate(
            storage,
            recover_slots(storage),
            record_envelopes={"a": encoded("a")},
            tombstones=frozenset(),
        )
        target, staged = build_candidate(
            accepted,
            record_envelopes={"a": encoded("a"), "b": encoded("b")},
            tombstones=frozenset(),
        )
        storage.save(target, staged)
        restarted = recover_slots(storage)
        self.assertEqual(restarted.active_generation, 1)
        self.assertEqual(set(restarted.records), {"a"})

    def test_corrupt_newest_record_falls_back_without_losing_valid_new_records(self) -> None:
        storage = MemorySaveGameSlots()
        old_a = encoded("a", title="old")
        first = persist_candidate(
            storage,
            recover_slots(storage),
            record_envelopes={"a": old_a},
            tombstones=frozenset(),
        )
        target, staged = build_candidate(
            first,
            record_envelopes={"a": encoded("a", title="new"), "b": encoded("b")},
            tombstones=frozenset(),
        )
        storage.save(
            target,
            replace(staged, committed=True, record_envelopes=("{not-json", encoded("b"))),
        )
        restarted = recover_slots(storage)
        self.assertEqual(restarted.records["a"].title, "old")
        self.assertIn("b", restarted.records)
        self.assertEqual(restarted.active_generation, 2)

    def test_newer_committed_tombstone_masks_every_older_record(self) -> None:
        storage = MemorySaveGameSlots()
        first = persist_candidate(
            storage,
            recover_slots(storage),
            record_envelopes={"a": encoded("a")},
            tombstones=frozenset(),
        )
        deleted = persist_candidate(
            storage,
            first,
            record_envelopes={},
            tombstones=frozenset({"a"}),
        )
        self.assertNotIn("a", deleted.records)
        self.assertIn("a", deleted.tombstones)
        self.assertNotIn("a", recover_slots(storage).records)

    def test_malformed_tombstone_channel_fails_closed_instead_of_resurrecting(self) -> None:
        storage = MemorySaveGameSlots()
        first = persist_candidate(
            storage,
            recover_slots(storage),
            record_envelopes={"a": encoded("a")},
            tombstones=frozenset(),
        )
        target, staged = build_candidate(
            first,
            record_envelopes={},
            tombstones=frozenset({"a"}),
        )
        storage.save(
            target,
            replace(staged, committed=True, tombstone_flypath_ids=("a", "a")),
        )
        with self.assertRaisesRegex(RecoveryError, "duplicate tombstone"):
            recover_slots(storage)

    def test_tombstones_are_monotonic_and_disjoint_from_live_records(self) -> None:
        prior = RecoveredRepository({}, frozenset({"dead"}), 4, SLOT_B)
        with self.assertRaisesRegex(ValueError, "monotonic"):
            build_candidate(prior, record_envelopes={}, tombstones=frozenset())
        with self.assertRaisesRegex(ValueError, "disjoint"):
            build_candidate(
                prior,
                record_envelopes={"dead": encoded("dead")},
                tombstones=frozenset({"dead"}),
            )

    def test_stage_or_commit_failure_does_not_mutate_authoritative_state(self) -> None:
        storage = MemorySaveGameSlots()
        original = persist_candidate(
            storage,
            recover_slots(storage),
            record_envelopes={"a": encoded("a")},
            tombstones=frozenset(),
        )
        storage.fail_next_save = True
        with self.assertRaises(PersistenceError):
            persist_candidate(
                storage,
                original,
                record_envelopes={"b": encoded("b")},
                tombstones=frozenset(),
            )
        self.assertEqual(set(original.records), {"a"})

        target, staged = build_candidate(
            original,
            record_envelopes={"b": encoded("b")},
            tombstones=frozenset(),
        )
        storage.save(target, staged)
        storage.fail_next_save = True
        with self.assertRaises(PersistenceError):
            storage.save(target, replace(staged, committed=True))
        self.assertEqual(set(recover_slots(storage).records), {"a"})

    def test_invalid_headers_are_ignored(self) -> None:
        for snapshot in (
            RepositorySnapshot(generation=1, committed=False),
            RepositorySnapshot(schema_version=99, generation=1, committed=True),
            RepositorySnapshot(generation=0, committed=True),
            RepositorySnapshot(generation=1, committed=True, snapshot_hash="fake"),
        ):
            storage = MemorySaveGameSlots()
            storage.slots[SLOT_A] = snapshot
            self.assertEqual(recover_slots(storage).records, {})

    def test_divergent_equal_generation_is_rejected_as_split_brain(self) -> None:
        storage = MemorySaveGameSlots()
        storage.slots[SLOT_A] = RepositorySnapshot(
            generation=7, committed=True, record_envelopes=(encoded("a"),)
        )
        storage.slots[SLOT_B] = RepositorySnapshot(
            generation=7, committed=True, record_envelopes=(encoded("b"),)
        )
        with self.assertRaisesRegex(RecoveryError, "divergent"):
            recover_slots(storage)

    def test_candidate_serialization_order_is_deterministic(self) -> None:
        target, candidate = build_candidate(
            RecoveredRepository({}, frozenset(), 0, ""),
            record_envelopes={"z": encoded("z"), "a": encoded("a")},
            tombstones=frozenset({"z-dead", "a-dead"}),
        )
        self.assertEqual(target, SLOT_A)
        self.assertIn('"flypathId":"a"', candidate.record_envelopes[0])
        self.assertEqual(candidate.tombstone_flypath_ids, ("a-dead", "z-dead"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
