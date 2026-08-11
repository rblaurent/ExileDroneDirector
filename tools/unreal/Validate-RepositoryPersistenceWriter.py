"""Execute the compiled repository writer against an isolated SaveGame slot.

This is deliberately not a native-API surrogate.  It spawns the real compiled
``BP_EDD_FlypathRepository`` actor, stages a candidate snapshot, invokes the
Blueprint ``PersistRepositoryV1`` coordinator, and verifies both its promoted
authority state and the physical SaveGame payload.  The automation slot is
is deliberately preserved only after a successful write so a second fresh
process can verify it.  Any failed run removes the slot in ``finally``.
"""

from __future__ import annotations

import unreal


PREFIX = "EDD_PERSISTENCE_WRITER_RUNTIME"
CLASS_PATH = (
    "/Game/Mods/ExileDroneDirector/Server/Repository/"
    "BP_EDD_FlypathRepository.BP_EDD_FlypathRepository_C"
)
SLOT = "EDD_Repository_PersistenceWriter_Automation"
USER = 0
GENERATION = 42
RECORDS = ["writer-record-alpha", "writer-record-unicode-北風"]
TOMBSTONES = ["writer-deleted-flight"]


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}|{label}|{value}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(f"{PREFIX}|FAIL|{message}")


def candidates(name: str):
    snake = "".join(("_" + c.lower()) if c.isupper() else c for c in name).lstrip("_")
    return (name, unreal.Name(name), snake, unreal.Name(snake))


def prop(obj, name: str):
    errors = []
    for candidate in candidates(name):
        try:
            return obj.get_editor_property(candidate)
        except Exception as error:
            errors.append(f"{candidate}:{error}")
    raise RuntimeError(f"{PREFIX}|FAIL|could not read {name}: {'; '.join(errors)}")


def set_prop(obj, name: str, value) -> None:
    errors = []
    for candidate in candidates(name):
        try:
            obj.set_editor_property(candidate, value)
            return
        except Exception as error:
            errors.append(f"{candidate}:{error}")
    raise RuntimeError(f"{PREFIX}|FAIL|could not set {name}: {'; '.join(errors)}")


actor = None
passed = False
try:
    if unreal.GameplayStatics.does_save_game_exist(SLOT, USER):
        require(
            unreal.GameplayStatics.delete_game_in_slot(SLOT, USER),
            "could not remove stale automation slot",
        )

    repository_class = unreal.load_class(None, CLASS_PATH)
    require(repository_class is not None, "repository generated class missing")
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    require(actor_subsystem is not None, "EditorActorSubsystem unavailable")
    actor = actor_subsystem.spawn_actor_from_class(
        repository_class,
        unreal.Vector(0.0, 0.0, -100000.0),
        unreal.Rotator(),
        False,
    )
    require(actor is not None, "could not spawn repository actor")

    # Seed visibly different authority so a no-op cannot satisfy the probe.
    set_prop(actor, "RepositoryLoadedV1", True)
    set_prop(actor, "ActiveGenerationV1", 41)
    set_prop(actor, "ActiveSlotV1", "writer-prior-authority")
    set_prop(actor, "ActiveRecordEnvelopesV1", ["writer-prior-record"])
    set_prop(actor, "ActiveTombstoneFlypathIdsV1", ["writer-prior-delete"])

    set_prop(actor, "CandidateGenerationV1", GENERATION)
    set_prop(actor, "CandidateTargetSlotV1", SLOT)
    set_prop(actor, "CandidateSnapshotHashV1", "")
    set_prop(actor, "CandidateRecordEnvelopesV1", RECORDS)
    set_prop(actor, "CandidateTombstoneFlypathIdsV1", TOMBSTONES)

    actor.call_method("PersistRepositoryV1")

    require(bool(prop(actor, "ScratchPersistenceStorageCreatedV1")), "storage was not created")
    require(bool(prop(actor, "ScratchPersistenceStageSavedV1")), "stage write did not succeed")
    require(bool(prop(actor, "ScratchPersistenceCommitSavedV1")), "commit write did not succeed")
    require(prop(actor, "ResultCodeV1") == "Success", f"unexpected result code {prop(actor, 'ResultCodeV1')!r}")
    require(prop(actor, "ResultDetailV1") == "", f"unexpected result detail {prop(actor, 'ResultDetailV1')!r}")
    require(int(prop(actor, "ActiveGenerationV1")) == GENERATION, "authority generation was not promoted")
    require(prop(actor, "ActiveSlotV1") == SLOT, "authority slot was not promoted")
    require(list(prop(actor, "ActiveRecordEnvelopesV1")) == RECORDS, "authority records mismatch")
    require(list(prop(actor, "ActiveTombstoneFlypathIdsV1")) == TOMBSTONES, "authority tombstones mismatch")

    require(unreal.GameplayStatics.does_save_game_exist(SLOT, USER), "writer did not create its slot")
    loaded = unreal.GameplayStatics.load_game_from_slot(SLOT, USER)
    require(loaded is not None, "writer slot could not be loaded")
    actual = (
        int(prop(loaded, "RepositorySchemaVersion")),
        int(prop(loaded, "Generation")),
        bool(prop(loaded, "Committed")),
        prop(loaded, "SnapshotHash"),
        list(prop(loaded, "RecordEnvelopes")),
        list(prop(loaded, "TombstoneFlypathIds")),
    )
    expected = (1, GENERATION, True, "", RECORDS, TOMBSTONES)
    require(actual == expected, f"physical payload mismatch: {actual!r}")
    emit("AUTHORITY_VERIFIED", GENERATION)
    emit("PHYSICAL_PAYLOAD_VERIFIED", actual)
    passed = True
    emit("PRESERVED_FOR_FRESH_READ", SLOT)
    emit("RESULT", "PASS")
finally:
    if actor is not None:
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        if subsystem is not None:
            subsystem.destroy_actor(actor)
    if not passed and unreal.GameplayStatics.does_save_game_exist(SLOT, USER):
        require(
            unreal.GameplayStatics.delete_game_in_slot(SLOT, USER),
            "could not clean failed automation fixture",
        )
        emit("FAILURE_CLEANUP", "PASS")
