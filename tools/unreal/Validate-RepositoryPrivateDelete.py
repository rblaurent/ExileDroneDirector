"""Executable acceptance for owner-only optimistic Flypath deletion.

The fixtures are created through the compiled private-create writer. Rejected
deletes must preserve in-memory authority and both physical SaveGame slots.
The successful delete is intentionally left committed for the paired fresh-
process restart acceptance.
"""

from __future__ import annotations

import unreal


PREFIX = "EDD_PRIVATE_DELETE_RUNTIME"
CLASS_PATH = (
    "/Game/Mods/ExileDroneDirector/Server/Repository/"
    "BP_EDD_FlypathRepository.BP_EDD_FlypathRepository_C"
)
SLOTS = ("EDD_Repository_A", "EDD_Repository_B")
DOCUMENT_FIELDS = {
    "SchemaVersion": ("SchemaVersion", "schema_version", "SchemaVersion_16_7F93B5224F25B9BFDAC842BCD5B16D37"),
    "TrajectoryEngineVersion": (
        "TrajectoryEngineVersion", "trajectory_engine_version",
        "TrajectoryEngineVersion_3_442F783F41FCAC3B8146EDA9233D191D",
    ),
    "RevisionNumber": ("RevisionNumber", "revision_number", "RevisionNumber_5_951904BF45A63EADA84E4AB0386D19B4"),
    "RegionId": ("RegionId", "region_id", "RegionId_8_BC1B1B9F4515D58E9666939AB30095B4"),
    "DurationSeconds": (
        "DurationSeconds", "duration_seconds", "DurationSeconds_11_4517680840D3F6CC541E6BBC6AB10DF9",
    ),
    "DefaultFlightProfile": (
        "DefaultFlightProfile", "default_flight_profile",
        "DefaultFlightProfile_14_E9663FDD4E006355747CD3B4CD8BD161",
    ),
    "Waypoints": ("Waypoints", "waypoints", "Waypoints_26_1F07C1B24D0D17E4610CDBBAFC5039E5"),
    "Segments": ("Segments", "segments", "Segments_27_C44AF0F54C828C6532348D8A42A4A92B"),
    "ContentHash": ("ContentHash", "content_hash", "ContentHash_28_C376573940EDD8D9F911D9800DB430BC"),
}


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
    raise RuntimeError(f"could not read {name}: {'; '.join(errors)}")


def set_prop(obj, name: str, value) -> None:
    errors = []
    for candidate in candidates(name):
        try:
            obj.set_editor_property(candidate, value)
            return
        except Exception as error:
            errors.append(f"{candidate}:{error}")
    raise RuntimeError(f"could not set {name}: {'; '.join(errors)}")


def document_prop(document, name: str):
    errors = []
    for candidate in DOCUMENT_FIELDS[name]:
        try:
            return document.get_editor_property(candidate)
        except Exception as error:
            errors.append(f"{candidate}:{error}")
    raise RuntimeError(f"could not read document {name}: {'; '.join(errors)}")


def set_document_prop(document, name: str, value) -> None:
    errors = []
    for candidate in DOCUMENT_FIELDS[name]:
        try:
            document.set_editor_property(candidate, value)
            return
        except Exception as error:
            errors.append(f"{candidate}:{error}")
    raise RuntimeError(f"could not set document {name}: {'; '.join(errors)}")


def delete_slots() -> None:
    for slot in SLOTS:
        if unreal.GameplayStatics.does_save_game_exist(slot, 0):
            require(unreal.GameplayStatics.delete_game_in_slot(slot, 0), f"could not delete {slot}")


def stage_document(actor) -> None:
    document = prop(actor, "RequestDraftDocumentV1")
    for name, value in (
        ("SchemaVersion", 1),
        ("TrajectoryEngineVersion", 1),
        ("RevisionNumber", 1),
        ("RegionId", "ExiledLands"),
        ("DurationSeconds", 0.0),
        ("DefaultFlightProfile", "cinematic_drone"),
        ("Waypoints", []),
        ("Segments", []),
        ("ContentHash", ""),
    ):
        set_document_prop(document, name, value)
    set_prop(actor, "ScratchDocumentV1", document)
    actor.call_method("EncodeDocumentV1")
    actor.call_method("DecodeDocumentV1")
    require(bool(prop(actor, "ScratchValidV1")), "document fixture did not round-trip")
    set_prop(actor, "RequestDraftDocumentV1", prop(actor, "ScratchDocumentV1"))


def create_record(actor, flypath_id: str, title: str, now: str) -> None:
    for name, value in (
        ("RequestRequesterAccountIdV1", "owner-a"),
        ("RequestRequesterDisplayNameV1", "Owner A"),
        ("RequestFlypathIdV1", flypath_id),
        ("RequestTitleV1", title),
        ("RequestDescriptionV1", f"private delete fixture {flypath_id}"),
        ("RequestRegionIdV1", "ExiledLands"),
        ("RequestNowUtcV1", now),
    ):
        set_prop(actor, name, value)
    stage_document(actor)
    actor.call_method("CreatePrivateFlypathV1")
    require(prop(actor, "ResultCodeV1") == "Success", f"create failed: {flypath_id}")


def authority_snapshot(actor):
    return (
        int(prop(actor, "ActiveGenerationV1")),
        str(prop(actor, "ActiveSlotV1")),
        tuple(prop(actor, "ActiveRecordEnvelopesV1")),
        tuple(prop(actor, "ActiveTombstoneFlypathIdsV1")),
        tuple(prop(actor, "ActiveFlypathIdsV1")),
        tuple(prop(actor, "ActiveOwnerAccountIdsV1")),
        tuple(prop(actor, "ActiveVisibilitiesV1")),
        tuple(prop(actor, "ActiveUpdatedUtcV1")),
    )


def physical_snapshot():
    values = []
    for slot in SLOTS:
        exists = unreal.GameplayStatics.does_save_game_exist(slot, 0)
        if not exists:
            values.append((slot, False))
            continue
        storage = unreal.GameplayStatics.load_game_from_slot(slot, 0)
        require(storage is not None, f"could not load {slot}")
        values.append(
            (
                slot,
                True,
                int(prop(storage, "Generation")),
                bool(prop(storage, "Committed")),
                tuple(prop(storage, "RecordEnvelopes")),
                tuple(prop(storage, "TombstoneFlypathIds")),
            )
        )
    return tuple(values)


def seed_stale_results(actor) -> None:
    set_prop(actor, "ResultRecordEnvelopeV1", "stale-envelope")
    set_prop(actor, "ResultMetadataEnvelopesV1", ["stale-metadata"])
    set_prop(actor, "ResultHasCurrentRevisionV1", True)
    set_prop(actor, "ResultCurrentRevisionV1", 999)
    set_prop(actor, "ResultRecordIndexV1", 999)
    document = prop(actor, "ResultDraftDocumentV1")
    set_document_prop(document, "RevisionNumber", 999)
    set_prop(actor, "ResultDraftDocumentV1", document)


def assert_payload_cleared(actor, *, conflict_revision: int | None = None) -> None:
    require(prop(actor, "ResultRecordEnvelopeV1") == "", "delete leaked stale envelope")
    require(list(prop(actor, "ResultMetadataEnvelopesV1")) == [], "delete leaked stale metadata")
    require(int(prop(actor, "ResultRecordIndexV1")) == -1, "delete leaked stale index")
    require(document_prop(prop(actor, "ResultDraftDocumentV1"), "RevisionNumber") == 0, "delete leaked typed draft")
    if conflict_revision is None:
        require(not bool(prop(actor, "ResultHasCurrentRevisionV1")), "delete leaked revision flag")
        require(int(prop(actor, "ResultCurrentRevisionV1")) == 0, "delete leaked revision")
    else:
        require(bool(prop(actor, "ResultHasCurrentRevisionV1")), "conflict omitted revision flag")
        require(int(prop(actor, "ResultCurrentRevisionV1")) == conflict_revision, "conflict revision changed")


def rejected(actor, *, owner: str, flypath_id: str, revision: int, code: str, detail: str, label: str, conflict_revision=None) -> None:
    before_authority = authority_snapshot(actor)
    before_physical = physical_snapshot()
    seed_stale_results(actor)
    set_prop(actor, "RequestRequesterAccountIdV1", owner)
    set_prop(actor, "RequestFlypathIdV1", flypath_id)
    set_prop(actor, "RequestExpectedRevisionV1", revision)
    actor.call_method("DeleteFlypathV1")
    require(prop(actor, "ResultCodeV1") == code, f"{label} code changed")
    require(prop(actor, "ResultDetailV1") == detail, f"{label} detail changed")
    assert_payload_cleared(actor, conflict_revision=conflict_revision)
    require(authority_snapshot(actor) == before_authority, f"{label} mutated authority")
    require(physical_snapshot() == before_physical, f"{label} wrote SaveGame")
    emit(label, "PASS")


actor = None
leave_for_restart = False
try:
    delete_slots()
    repository_class = unreal.load_class(None, CLASS_PATH)
    require(repository_class is not None, "repository generated class missing")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    require(subsystem is not None, "EditorActorSubsystem unavailable")
    actor = subsystem.spawn_actor_from_class(repository_class, unreal.Vector(0, 0, -100000), unreal.Rotator(), False)
    require(actor is not None, "could not spawn repository actor")

    create_record(actor, "delete-runtime-a", "Delete Alpha", "2026-08-11T20:00:00Z")
    create_record(actor, "delete-runtime-b", "Delete Beta", "2026-08-11T20:01:00Z")
    require(authority_snapshot(actor)[0:2] == (2, "EDD_Repository_B"), "fixture generation/slot changed")
    require(list(prop(actor, "ActiveFlypathIdsV1")) == ["delete-runtime-a", "delete-runtime-b"], "fixture IDs changed")
    emit("FIXTURES", "PASS")

    rejected(actor, owner="owner-a", flypath_id="missing", revision=1, code="NotFound", detail="FlypathNotFound", label="NOT_FOUND")
    rejected(actor, owner="owner-b", flypath_id="delete-runtime-a", revision=1, code="Forbidden", detail="OwnerRequired", label="WRONG_OWNER")
    rejected(actor, owner="   ", flypath_id="delete-runtime-a", revision=1, code="Forbidden", detail="OwnerRequired", label="BLANK_OWNER")
    rejected(
        actor,
        owner="owner-a",
        flypath_id="delete-runtime-a",
        revision=0,
        code="RevisionConflict",
        detail="ExpectedRevisionMismatch",
        label="REVISION_CONFLICT",
        conflict_revision=1,
    )

    envelopes = list(prop(actor, "ActiveRecordEnvelopesV1"))
    original_envelope = envelopes[0]
    envelopes[0] = "not-json"
    set_prop(actor, "ActiveRecordEnvelopesV1", envelopes)
    rejected(
        actor,
        owner="owner-a",
        flypath_id="delete-runtime-a",
        revision=1,
        code="ValidationFailed",
        detail="StoredRecordDecodeFailed",
        label="DECODE_FAILURE",
    )
    envelopes[0] = original_envelope
    set_prop(actor, "ActiveRecordEnvelopesV1", envelopes)

    ids = list(prop(actor, "ActiveFlypathIdsV1"))
    ids[0] = "delete-runtime-alias"
    set_prop(actor, "ActiveFlypathIdsV1", ids)
    rejected(
        actor,
        owner="owner-a",
        flypath_id="delete-runtime-alias",
        revision=1,
        code="ValidationFailed",
        detail="StoredRecordIndexMismatch",
        label="IDENTITY_FAILURE",
    )
    ids[0] = "delete-runtime-a"
    set_prop(actor, "ActiveFlypathIdsV1", ids)

    before_physical = physical_snapshot()
    set_prop(actor, "RequestRequesterAccountIdV1", "owner-a")
    set_prop(actor, "RequestFlypathIdV1", "delete-runtime-a")
    set_prop(actor, "RequestExpectedRevisionV1", 1)
    actor.call_method("DeleteFlypathV1")
    require(prop(actor, "ResultCodeV1") == "Success", f"delete failed: {prop(actor, 'ResultCodeV1')}|{prop(actor, 'ResultDetailV1')}")
    assert_payload_cleared(actor)
    require(authority_snapshot(actor)[0:2] == (3, "EDD_Repository_A"), "delete generation/slot changed")
    require(list(prop(actor, "ActiveFlypathIdsV1")) == ["delete-runtime-b"], "deleted ID remained")
    require(list(prop(actor, "ActiveOwnerAccountIdsV1")) == ["owner-a"], "owner index misaligned")
    require(list(prop(actor, "ActiveVisibilitiesV1")) == ["private"], "visibility index misaligned")
    require(list(prop(actor, "ActiveUpdatedUtcV1")) == ["2026-08-11T20:01:00Z"], "timestamp index misaligned")
    require(len(list(prop(actor, "ActiveRecordEnvelopesV1"))) == 1, "record envelope was not removed")
    require(list(prop(actor, "ActiveTombstoneFlypathIdsV1")) == ["delete-runtime-a"], "tombstone changed")
    require(physical_snapshot() != before_physical, "successful delete did not write SaveGame")
    emit("DELETE_COMMIT", "PASS")

    latest = unreal.GameplayStatics.load_game_from_slot("EDD_Repository_A", 0)
    require(latest is not None, "committed delete slot missing")
    require(int(prop(latest, "Generation")) == 3, "committed delete generation changed")
    require(bool(prop(latest, "Committed")), "delete slot was not committed")
    require(len(list(prop(latest, "RecordEnvelopes"))) == 1, "physical record removal changed")
    require(list(prop(latest, "TombstoneFlypathIds")) == ["delete-runtime-a"], "physical tombstone changed")
    emit("PHYSICAL_TOMBSTONE", "PASS")

    set_prop(actor, "RequestRequesterAccountIdV1", "owner-a")
    set_prop(actor, "RequestFlypathIdV1", "delete-runtime-a")
    actor.call_method("LoadDraftV1")
    require(prop(actor, "ResultCodeV1") == "NotFound", "deleted draft remained loadable")
    set_prop(actor, "RequestFlypathIdV1", "delete-runtime-b")
    actor.call_method("LoadDraftV1")
    require(prop(actor, "ResultCodeV1") == "Success", "surviving draft became unavailable")
    set_prop(actor, "RequestOffsetV1", 0)
    set_prop(actor, "RequestLimitV1", 20)
    actor.call_method("ListMineV1")
    require(prop(actor, "ResultCodeV1") == "Success", "post-delete list failed")
    require(int(prop(actor, "ResultTotalCountV1")) == 1, "post-delete list count changed")
    require(len(list(prop(actor, "ResultMetadataEnvelopesV1"))) == 1, "post-delete metadata count changed")
    emit("READ_BOUNDARIES", "PASS")

    rejected(actor, owner="owner-a", flypath_id="delete-runtime-a", revision=1, code="NotFound", detail="FlypathNotFound", label="REPEAT_DELETE")
    leave_for_restart = True
    emit("RESTART_REQUIRED", "PASS")
    emit("RESULT", "PASS")
finally:
    if actor is not None:
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        if subsystem is not None:
            subsystem.destroy_actor(actor)
    if not leave_for_restart:
        delete_slots()
