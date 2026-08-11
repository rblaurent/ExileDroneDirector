"""Executable contract for the Blueprint alternating-slot SaveGame adapter.

The runtime stores complete opaque record-envelope snapshots in two SaveGame
slots. This oracle models that physical layout separately from the higher-level
per-record repository contract.

Recovery is record-granular inside a valid committed snapshot header: a corrupt
newest envelope may fall back to the previous slot, while a newer committed
tombstone masks every older record for that Flypath ID. Authoritative memory
changes only after both the uncommitted stage write and committed rewrite pass.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping

from flypath_document import DocumentValidationError, FlypathRecord, deserialize_record


SCHEMA_VERSION = 1
SLOT_A = "EDD_Repository_A"
SLOT_B = "EDD_Repository_B"
SLOTS = (SLOT_A, SLOT_B)


class PersistenceError(RuntimeError):
    """Raised when a physical SaveGame operation cannot complete."""


class RecoveryError(RuntimeError):
    """Raised when committed storage has an irreconcilable split brain."""


@dataclass(frozen=True)
class RepositorySnapshot:
    schema_version: int = SCHEMA_VERSION
    generation: int = 0
    committed: bool = False
    snapshot_hash: str = ""
    record_envelopes: tuple[str, ...] = ()
    tombstone_flypath_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecoveredRepository:
    records: Mapping[str, FlypathRecord]
    tombstones: frozenset[str]
    active_generation: int
    active_slot: str


class MemorySaveGameSlots:
    """Fault-injectable stand-in for GameplayStatics SaveGame slot calls."""

    def __init__(self) -> None:
        self.slots: dict[str, RepositorySnapshot] = {}
        self.fail_next_save = False

    def save(self, slot: str, snapshot: RepositorySnapshot) -> None:
        if slot not in SLOTS:
            raise ValueError(f"unknown repository slot: {slot}")
        if self.fail_next_save:
            self.fail_next_save = False
            raise PersistenceError("injected SaveGame failure")
        self.slots[slot] = snapshot

    def load(self, slot: str) -> RepositorySnapshot | None:
        return self.slots.get(slot)


def _header_is_valid(snapshot: RepositorySnapshot | None) -> bool:
    return bool(
        snapshot is not None
        and snapshot.schema_version == SCHEMA_VERSION
        and snapshot.generation > 0
        and snapshot.committed
        and snapshot.snapshot_hash == ""
    )


def _valid_tombstones(snapshot: RepositorySnapshot) -> frozenset[str]:
    values = snapshot.tombstone_flypath_ids
    if any(not value or value.strip() != value for value in values):
        raise RecoveryError(
            f"malformed tombstone channel at generation {snapshot.generation}"
        )
    if len(values) != len(set(values)):
        raise RecoveryError(
            f"duplicate tombstone at generation {snapshot.generation}"
        )
    return frozenset(values)


def _records_at_generation(snapshot: RepositorySnapshot) -> dict[str, FlypathRecord]:
    """Return unambiguous valid records; malformed/duplicate IDs fail locally."""

    decoded: dict[str, FlypathRecord] = {}
    ambiguous: set[str] = set()
    for envelope in snapshot.record_envelopes:
        try:
            record = deserialize_record(envelope)
        except DocumentValidationError:
            continue
        if record.flypath_id in decoded:
            ambiguous.add(record.flypath_id)
        else:
            decoded[record.flypath_id] = record
    for flypath_id in ambiguous:
        decoded.pop(flypath_id, None)
    return decoded


def recover_slots(storage: MemorySaveGameSlots) -> RecoveredRepository:
    """Recover newest valid records while preserving committed deletion masks."""

    candidates = [
        (slot, snapshot)
        for slot in SLOTS
        if _header_is_valid(snapshot := storage.load(slot))
    ]
    if not candidates:
        return RecoveredRepository({}, frozenset(), 0, "")

    by_generation: dict[int, list[tuple[str, RepositorySnapshot]]] = {}
    for slot, snapshot in candidates:
        assert snapshot is not None
        by_generation.setdefault(snapshot.generation, []).append((slot, snapshot))
    for generation, peers in by_generation.items():
        if len(peers) > 1 and peers[0][1] != peers[1][1]:
            raise RecoveryError(f"divergent committed snapshots at generation {generation}")

    candidates.sort(key=lambda item: (item[1].generation, item[0]), reverse=True)
    tombstone_generation: dict[str, int] = {}
    for _, snapshot in candidates:
        for flypath_id in _valid_tombstones(snapshot):
            tombstone_generation[flypath_id] = max(
                snapshot.generation,
                tombstone_generation.get(flypath_id, 0),
            )

    recovered: dict[str, FlypathRecord] = {}
    for _, snapshot in candidates:
        for flypath_id, record in _records_at_generation(snapshot).items():
            if flypath_id in recovered:
                continue
            if tombstone_generation.get(flypath_id, 0) >= snapshot.generation:
                continue
            recovered[flypath_id] = record

    active_slot, active = candidates[0]
    return RecoveredRepository(
        records=recovered,
        tombstones=frozenset(tombstone_generation),
        active_generation=active.generation,
        active_slot=active_slot,
    )


def build_candidate(
    recovered: RecoveredRepository,
    *,
    record_envelopes: Mapping[str, str],
    tombstones: frozenset[str],
) -> tuple[str, RepositorySnapshot]:
    """Build the deterministic uncommitted candidate for the inactive slot."""

    if not recovered.tombstones.issubset(tombstones):
        raise ValueError("committed tombstones are monotonic")
    if set(record_envelopes) & set(tombstones):
        raise ValueError("active records and tombstones must be disjoint")
    for flypath_id, envelope in record_envelopes.items():
        record = deserialize_record(envelope)
        if record.flypath_id != flypath_id:
            raise ValueError("record map key does not match envelope Flypath ID")

    target = SLOT_B if recovered.active_slot == SLOT_A else SLOT_A
    candidate = RepositorySnapshot(
        generation=recovered.active_generation + 1,
        committed=False,
        record_envelopes=tuple(record_envelopes[key] for key in sorted(record_envelopes)),
        tombstone_flypath_ids=tuple(sorted(tombstones)),
    )
    return target, candidate


def persist_candidate(
    storage: MemorySaveGameSlots,
    recovered: RecoveredRepository,
    *,
    record_envelopes: Mapping[str, str],
    tombstones: frozenset[str],
) -> RecoveredRepository:
    """Stage then commit one candidate; never mutate the supplied authority."""

    target, staged = build_candidate(
        recovered,
        record_envelopes=record_envelopes,
        tombstones=tombstones,
    )
    storage.save(target, staged)
    storage.save(target, replace(staged, committed=True))
    return recover_slots(storage)
