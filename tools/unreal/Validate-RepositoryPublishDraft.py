"""Executable acceptance for owner-only optimistic publication.

The fixture is created and edited through the compiled repository writers.
Rejected publishes must preserve authority and both physical slots. Successful
publishes must snapshot the draft without advancing it, survive intervening
draft edits, and leave a generation-4 fixture for fresh-process acceptance.
"""

from __future__ import annotations

import json
import unreal


PREFIX = "EDD_PUBLISH_DRAFT_RUNTIME"
CLASS_PATH = (
    "/Game/Mods/ExileDroneDirector/Server/Repository/"
    "BP_EDD_FlypathRepository.BP_EDD_FlypathRepository_C"
)
SLOTS = ("EDD_Repository_A", "EDD_Repository_B")
FLYPATH_ID = "publish-runtime-a"
OWNER = "owner-a"
DOCUMENT_FIELDS = {
    "SchemaVersion": ("SchemaVersion", "schema_version", "SchemaVersion_16_7F93B5224F25B9BFDAC842BCD5B16D37"),
    "TrajectoryEngineVersion": ("TrajectoryEngineVersion", "trajectory_engine_version", "TrajectoryEngineVersion_3_442F783F41FCAC3B8146EDA9233D191D"),
    "RevisionNumber": ("RevisionNumber", "revision_number", "RevisionNumber_5_951904BF45A63EADA84E4AB0386D19B4"),
    "RegionId": ("RegionId", "region_id", "RegionId_8_BC1B1B9F4515D58E9666939AB30095B4"),
    "DurationSeconds": ("DurationSeconds", "duration_seconds", "DurationSeconds_11_4517680840D3F6CC541E6BBC6AB10DF9"),
    "DefaultFlightProfile": ("DefaultFlightProfile", "default_flight_profile", "DefaultFlightProfile_14_E9663FDD4E006355747CD3B4CD8BD161"),
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
        values.append((slot, True, int(prop(storage, "Generation")), bool(prop(storage, "Committed")), tuple(prop(storage, "RecordEnvelopes")), tuple(prop(storage, "TombstoneFlypathIds"))))
    return tuple(values)


def seed_stale_results(actor) -> None:
    set_prop(actor, "ResultRecordEnvelopeV1", "stale-envelope")
    set_prop(actor, "ResultMetadataEnvelopesV1", ["stale-metadata"])
    set_prop(actor, "ResultHasCurrentRevisionV1", True)
    set_prop(actor, "ResultCurrentRevisionV1", 999)
    set_prop(actor, "ResultRecordIndexV1", 999)


def assert_rejection_payload(actor, *, conflict_revision=None) -> None:
    require(prop(actor, "ResultRecordEnvelopeV1") == "", "rejection leaked envelope")
    require(list(prop(actor, "ResultMetadataEnvelopesV1")) == [], "rejection leaked metadata")
    require(int(prop(actor, "ResultRecordIndexV1")) == -1, "rejection leaked index")
    require(document_prop(prop(actor, "ResultDraftDocumentV1"), "RevisionNumber") == 0, "rejection leaked draft")
    if conflict_revision is None:
        require(not bool(prop(actor, "ResultHasCurrentRevisionV1")), "rejection leaked revision flag")
        require(int(prop(actor, "ResultCurrentRevisionV1")) == 0, "rejection leaked revision")
    else:
        require(bool(prop(actor, "ResultHasCurrentRevisionV1")), "conflict omitted revision flag")
        require(int(prop(actor, "ResultCurrentRevisionV1")) == conflict_revision, "conflict revision changed")


def rejected(actor, *, owner: str, flypath_id: str, revision: int, now: str, code: str, detail: str, label: str, conflict_revision=None) -> None:
    before_authority = authority_snapshot(actor)
    before_physical = physical_snapshot()
    seed_stale_results(actor)
    set_prop(actor, "RequestRequesterAccountIdV1", owner)
    set_prop(actor, "RequestFlypathIdV1", flypath_id)
    set_prop(actor, "RequestExpectedRevisionV1", revision)
    set_prop(actor, "RequestNowUtcV1", now)
    actor.call_method("PublishDraftV1")
    require(prop(actor, "ResultCodeV1") == code, f"{label} code changed")
    require(prop(actor, "ResultDetailV1") == detail, f"{label} detail changed")
    assert_rejection_payload(actor, conflict_revision=conflict_revision)
    require(authority_snapshot(actor) == before_authority, f"{label} mutated authority")
    require(physical_snapshot() == before_physical, f"{label} wrote SaveGame")
    emit(label, "PASS")


def decode_active(actor):
    envelopes = list(prop(actor, "ActiveRecordEnvelopesV1"))
    require(len(envelopes) == 1, "active record count changed")
    set_prop(actor, "ScratchEncodedRecordV1", envelopes[0])
    actor.call_method("DecodeRecordV1")
    require(bool(prop(actor, "ScratchValidV1")), "active record decode failed")


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

    for name, value in (
        ("RequestRequesterAccountIdV1", OWNER),
        ("RequestRequesterDisplayNameV1", "Owner A"),
        ("RequestFlypathIdV1", FLYPATH_ID),
        ("RequestTitleV1", "Publish Runtime"),
        ("RequestDescriptionV1", "publication acceptance fixture"),
        ("RequestRegionIdV1", "ExiledLands"),
        ("RequestNowUtcV1", "2026-08-12T00:10:00Z"),
    ):
        set_prop(actor, name, value)
    stage_document(actor)
    actor.call_method("CreatePrivateFlypathV1")
    require(prop(actor, "ResultCodeV1") == "Success", "fixture create failed")
    require(authority_snapshot(actor)[0:2] == (1, "EDD_Repository_A"), "fixture generation changed")
    emit("FIXTURE", "PASS")

    rejected(actor, owner=OWNER, flypath_id="missing", revision=1, now="2026-08-12T00:11:00Z", code="NotFound", detail="FlypathNotFound", label="NOT_FOUND")
    rejected(actor, owner="owner-b", flypath_id=FLYPATH_ID, revision=1, now="2026-08-12T00:11:00Z", code="Forbidden", detail="OwnerRequired", label="WRONG_OWNER")
    rejected(actor, owner="   ", flypath_id=FLYPATH_ID, revision=1, now="2026-08-12T00:11:00Z", code="Forbidden", detail="OwnerRequired", label="BLANK_OWNER")
    rejected(actor, owner=OWNER, flypath_id=FLYPATH_ID, revision=0, now="2026-08-12T00:11:00Z", code="RevisionConflict", detail="ExpectedRevisionMismatch", label="REVISION_CONFLICT", conflict_revision=1)
    rejected(actor, owner=OWNER, flypath_id=FLYPATH_ID, revision=1, now="   ", code="ValidationFailed", detail="InvalidPublishRequest", label="INVALID_REQUEST")

    envelopes = list(prop(actor, "ActiveRecordEnvelopesV1"))
    original_envelope = envelopes[0]
    envelopes[0] = "not-json"
    set_prop(actor, "ActiveRecordEnvelopesV1", envelopes)
    rejected(actor, owner=OWNER, flypath_id=FLYPATH_ID, revision=1, now="2026-08-12T00:11:00Z", code="ValidationFailed", detail="StoredRecordDecodeFailed", label="DECODE_FAILURE")
    envelopes[0] = original_envelope
    set_prop(actor, "ActiveRecordEnvelopesV1", envelopes)

    ids = list(prop(actor, "ActiveFlypathIdsV1"))
    ids[0] = "publish-runtime-alias"
    set_prop(actor, "ActiveFlypathIdsV1", ids)
    rejected(actor, owner=OWNER, flypath_id="publish-runtime-alias", revision=1, now="2026-08-12T00:11:00Z", code="ValidationFailed", detail="StoredRecordIndexMismatch", label="IDENTITY_FAILURE")
    ids[0] = FLYPATH_ID
    set_prop(actor, "ActiveFlypathIdsV1", ids)

    original_max = int(prop(actor, "MaxSerializedBytesV1"))
    set_prop(actor, "MaxSerializedBytesV1", 1)
    rejected(actor, owner=OWNER, flypath_id=FLYPATH_ID, revision=1, now="2026-08-12T00:11:00Z", code="LimitExceeded", detail="SerializedSize", label="SIZE_LIMIT")
    set_prop(actor, "MaxSerializedBytesV1", original_max)

    set_prop(actor, "RequestRequesterAccountIdV1", OWNER)
    set_prop(actor, "RequestFlypathIdV1", FLYPATH_ID)
    set_prop(actor, "RequestExpectedRevisionV1", 1)
    set_prop(actor, "RequestNowUtcV1", "2026-08-12T00:12:00Z")
    actor.call_method("PublishDraftV1")
    require(prop(actor, "ResultCodeV1") == "Success", f"publish failed: {prop(actor, 'ResultCodeV1')}|{prop(actor, 'ResultDetailV1')}")
    require(authority_snapshot(actor)[0:2] == (2, "EDD_Repository_B"), "publish generation/slot changed")
    require(list(prop(actor, "ActiveVisibilitiesV1")) == ["public"], "visibility was not promoted")
    require(list(prop(actor, "ActiveUpdatedUtcV1")) == ["2026-08-12T00:12:00Z"], "publish timestamp changed")
    require(int(prop(actor, "ResultRecordIndexV1")) == 0, "success index changed")
    require(int(prop(actor, "ResultCurrentRevisionV1")) == 1, "publish advanced draft revision")
    require(document_prop(prop(actor, "ResultDraftDocumentV1"), "RevisionNumber") == 1, "publish result draft changed")
    decode_active(actor)
    require(prop(actor, "ScratchRecordVisibilityV1") == "public", "published record is not public")
    require(bool(prop(actor, "ScratchRecordHasPublishedRevisionV1")), "published flag missing")
    require(int(prop(actor, "ScratchRecordPublishedRevisionNumberV1")) == 1, "published revision changed")
    require(document_prop(prop(actor, "ScratchRecordPublishedDocumentV1"), "RevisionNumber") == 1, "published snapshot revision changed")
    emit("FIRST_PUBLISH", "PASS")

    stage_document(actor)
    set_prop(actor, "RequestRequesterAccountIdV1", OWNER)
    set_prop(actor, "RequestFlypathIdV1", FLYPATH_ID)
    set_prop(actor, "RequestExpectedRevisionV1", 1)
    set_prop(actor, "RequestNowUtcV1", "2026-08-12T00:13:00Z")
    actor.call_method("SaveDraftV1")
    require(prop(actor, "ResultCodeV1") == "Success", "intervening save failed")
    require(authority_snapshot(actor)[0:2] == (3, "EDD_Repository_A"), "save generation/slot changed")
    decode_active(actor)
    require(int(prop(actor, "ScratchRecordDraftRevisionNumberV1")) == 2, "draft did not advance")
    require(bool(prop(actor, "ScratchRecordHasPublishedRevisionV1")), "save erased published flag")
    require(int(prop(actor, "ScratchRecordPublishedRevisionNumberV1")) == 1, "save mutated published revision")
    require(document_prop(prop(actor, "ScratchRecordPublishedDocumentV1"), "RevisionNumber") == 1, "save mutated published snapshot")
    emit("SNAPSHOT_IMMUTABLE", "PASS")

    set_prop(actor, "RequestExpectedRevisionV1", 2)
    set_prop(actor, "RequestNowUtcV1", "2026-08-12T00:14:00Z")
    actor.call_method("PublishDraftV1")
    require(prop(actor, "ResultCodeV1") == "Success", "republish failed")
    require(authority_snapshot(actor)[0:2] == (4, "EDD_Repository_B"), "republish generation/slot changed")
    decode_active(actor)
    require(int(prop(actor, "ScratchRecordDraftRevisionNumberV1")) == 2, "republish advanced draft")
    require(int(prop(actor, "ScratchRecordPublishedRevisionNumberV1")) == 2, "republish revision changed")
    require(document_prop(prop(actor, "ScratchRecordPublishedDocumentV1"), "RevisionNumber") == 2, "republish snapshot changed")
    emit("REPUBLISH", "PASS")

    rejected(actor, owner=OWNER, flypath_id=FLYPATH_ID, revision=1, now="2026-08-12T00:15:00Z", code="RevisionConflict", detail="ExpectedRevisionMismatch", label="STALE_REPUBLISH", conflict_revision=2)
    set_prop(actor, "RequestRequesterAccountIdV1", OWNER)
    set_prop(actor, "RequestOffsetV1", 0)
    set_prop(actor, "RequestLimitV1", 20)
    actor.call_method("ListMineV1")
    require(prop(actor, "ResultCodeV1") == "Success", "owner list failed")
    metadata = [json.loads(value) for value in prop(actor, "ResultMetadataEnvelopesV1")]
    require(len(metadata) == 1, "owner metadata count changed")
    require(metadata[0]["visibility"] == "public", "metadata visibility changed")
    require(metadata[0]["draftRevisionNumber"] == 2, "metadata draft revision changed")
    require(metadata[0]["hasPublishedRevision"] is True, "metadata published flag changed")
    require(metadata[0]["publishedRevisionNumber"] == 2, "metadata published revision changed")
    emit("METADATA", "PASS")

    latest = unreal.GameplayStatics.load_game_from_slot("EDD_Repository_B", 0)
    require(latest is not None and int(prop(latest, "Generation")) == 4 and bool(prop(latest, "Committed")), "physical republish state changed")
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
