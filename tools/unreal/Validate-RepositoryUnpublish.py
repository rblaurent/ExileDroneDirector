"""Executable acceptance for owner-only optimistic unpublication.

The compiled repository writers create, publish, and edit the fixture. Every
rejected unpublish must preserve in-memory authority and both physical slots.
An accepted unpublish makes the record private without erasing either draft or
published snapshot, then leaves generation 6 for a true restart proof.
"""

from __future__ import annotations

import json
import unreal


PREFIX = "EDD_UNPUBLISH_RUNTIME"
CLASS_PATH = (
    "/Game/Mods/ExileDroneDirector/Server/Repository/"
    "BP_EDD_FlypathRepository.BP_EDD_FlypathRepository_C"
)
SLOTS = ("EDD_Repository_A", "EDD_Repository_B")
FLYPATH_ID = "unpublish-runtime-a"
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
    return name, unreal.Name(name), snake, unreal.Name(snake)


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


def stage_document(actor, duration: float, content_hash: str) -> None:
    document = prop(actor, "RequestDraftDocumentV1")
    for name, value in (
        ("SchemaVersion", 1),
        ("TrajectoryEngineVersion", 1),
        ("RevisionNumber", 777),
        ("RegionId", "ExiledLands"),
        ("DurationSeconds", duration),
        ("DefaultFlightProfile", "cinematic_drone"),
        ("Waypoints", []),
        ("Segments", []),
        ("ContentHash", content_hash),
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
    result = []
    for slot in SLOTS:
        exists = unreal.GameplayStatics.does_save_game_exist(slot, 0)
        if not exists:
            result.append((slot, False))
            continue
        storage = unreal.GameplayStatics.load_game_from_slot(slot, 0)
        require(storage is not None, f"could not load {slot}")
        result.append((
            slot,
            True,
            int(prop(storage, "Generation")),
            bool(prop(storage, "Committed")),
            tuple(prop(storage, "RecordEnvelopes")),
            tuple(prop(storage, "TombstoneFlypathIds")),
        ))
    return tuple(result)


def seed_stale_results(actor) -> None:
    set_prop(actor, "ResultRecordEnvelopeV1", "stale-envelope")
    set_prop(actor, "ResultMetadataEnvelopesV1", ["stale-metadata"])
    set_prop(actor, "ResultHasCurrentRevisionV1", True)
    set_prop(actor, "ResultCurrentRevisionV1", 999)
    set_prop(actor, "ResultRecordIndexV1", 999)


def assert_rejection_payload(actor, conflict_revision=None) -> None:
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


def rejected(actor, *, owner: str, flypath_id: str, revision: int, now: str,
             code: str, detail: str, label: str, conflict_revision=None) -> None:
    before_authority = authority_snapshot(actor)
    before_physical = physical_snapshot()
    seed_stale_results(actor)
    set_prop(actor, "RequestRequesterAccountIdV1", owner)
    set_prop(actor, "RequestFlypathIdV1", flypath_id)
    set_prop(actor, "RequestExpectedRevisionV1", revision)
    set_prop(actor, "RequestNowUtcV1", now)
    actor.call_method("UnpublishV1")
    require(prop(actor, "ResultCodeV1") == code, f"{label} code changed")
    require(prop(actor, "ResultDetailV1") == detail, f"{label} detail changed")
    assert_rejection_payload(actor, conflict_revision)
    require(authority_snapshot(actor) == before_authority, f"{label} mutated authority")
    require(physical_snapshot() == before_physical, f"{label} wrote SaveGame")
    emit(label, "PASS")


def decode_active(actor) -> None:
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
    actor = subsystem.spawn_actor_from_class(
        repository_class, unreal.Vector(0, 0, -100000), unreal.Rotator(), False
    )
    require(actor is not None, "could not spawn repository actor")

    for name, value in (
        ("RequestRequesterAccountIdV1", OWNER),
        ("RequestRequesterDisplayNameV1", "Owner A"),
        ("RequestFlypathIdV1", FLYPATH_ID),
        ("RequestTitleV1", "Unpublish Runtime"),
        ("RequestDescriptionV1", "unpublication acceptance fixture"),
        ("RequestRegionIdV1", "ExiledLands"),
        ("RequestNowUtcV1", "2026-08-12T01:00:00Z"),
    ):
        set_prop(actor, name, value)
    stage_document(actor, 0.0, "draft-v1")
    actor.call_method("CreatePrivateFlypathV1")
    require(prop(actor, "ResultCodeV1") == "Success", "fixture create failed")
    require(authority_snapshot(actor)[0:2] == (1, "EDD_Repository_A"), "create authority changed")

    set_prop(actor, "RequestExpectedRevisionV1", 1)
    set_prop(actor, "RequestNowUtcV1", "2026-08-12T01:01:00Z")
    actor.call_method("PublishDraftV1")
    require(prop(actor, "ResultCodeV1") == "Success", "fixture publish failed")
    require(authority_snapshot(actor)[0:2] == (2, "EDD_Repository_B"), "publish authority changed")

    stage_document(actor, 22.0, "draft-v2")
    set_prop(actor, "RequestExpectedRevisionV1", 1)
    set_prop(actor, "RequestNowUtcV1", "2026-08-12T01:02:00Z")
    actor.call_method("SaveDraftV1")
    require(prop(actor, "ResultCodeV1") == "Success", "fixture save failed")
    require(authority_snapshot(actor)[0:2] == (3, "EDD_Repository_A"), "save authority changed")
    decode_active(actor)
    require(int(prop(actor, "ScratchRecordDraftRevisionNumberV1")) == 2, "draft did not advance")
    require(abs(float(document_prop(prop(actor, "ScratchRecordDraftDocumentV1"), "DurationSeconds")) - 22.0) < 0.001, "draft payload changed")
    require(bool(prop(actor, "ScratchRecordHasPublishedRevisionV1")), "published flag missing before unpublish")
    require(int(prop(actor, "ScratchRecordPublishedRevisionNumberV1")) == 1, "published revision changed before unpublish")
    require(abs(float(document_prop(prop(actor, "ScratchRecordPublishedDocumentV1"), "DurationSeconds"))) < 0.001, "published snapshot mutated by save")
    emit("FIXTURE", "PASS")

    rejected(actor, owner=OWNER, flypath_id="missing", revision=2, now="2026-08-12T01:03:00Z", code="NotFound", detail="FlypathNotFound", label="NOT_FOUND")
    rejected(actor, owner="owner-b", flypath_id=FLYPATH_ID, revision=2, now="2026-08-12T01:03:00Z", code="Forbidden", detail="OwnerRequired", label="WRONG_OWNER")
    rejected(actor, owner="   ", flypath_id=FLYPATH_ID, revision=2, now="2026-08-12T01:03:00Z", code="Forbidden", detail="OwnerRequired", label="BLANK_OWNER")
    rejected(actor, owner=OWNER, flypath_id=FLYPATH_ID, revision=1, now="2026-08-12T01:03:00Z", code="RevisionConflict", detail="ExpectedRevisionMismatch", label="REVISION_CONFLICT", conflict_revision=2)
    rejected(actor, owner=OWNER, flypath_id=FLYPATH_ID, revision=2, now="   ", code="ValidationFailed", detail="InvalidUnpublishRequest", label="INVALID_REQUEST")

    envelopes = list(prop(actor, "ActiveRecordEnvelopesV1"))
    original_envelope = envelopes[0]
    envelopes[0] = "not-json"
    set_prop(actor, "ActiveRecordEnvelopesV1", envelopes)
    rejected(actor, owner=OWNER, flypath_id=FLYPATH_ID, revision=2, now="2026-08-12T01:03:00Z", code="ValidationFailed", detail="StoredRecordDecodeFailed", label="DECODE_FAILURE")
    envelopes[0] = original_envelope
    set_prop(actor, "ActiveRecordEnvelopesV1", envelopes)

    ids = list(prop(actor, "ActiveFlypathIdsV1"))
    ids[0] = "unpublish-runtime-alias"
    set_prop(actor, "ActiveFlypathIdsV1", ids)
    rejected(actor, owner=OWNER, flypath_id="unpublish-runtime-alias", revision=2, now="2026-08-12T01:03:00Z", code="ValidationFailed", detail="StoredRecordIndexMismatch", label="IDENTITY_FAILURE")
    ids[0] = FLYPATH_ID
    set_prop(actor, "ActiveFlypathIdsV1", ids)

    original_max = int(prop(actor, "MaxSerializedBytesV1"))
    set_prop(actor, "MaxSerializedBytesV1", 1)
    rejected(actor, owner=OWNER, flypath_id=FLYPATH_ID, revision=2, now="2026-08-12T01:03:00Z", code="LimitExceeded", detail="SerializedSize", label="SIZE_LIMIT")
    set_prop(actor, "MaxSerializedBytesV1", original_max)

    set_prop(actor, "RequestRequesterAccountIdV1", OWNER)
    set_prop(actor, "RequestFlypathIdV1", FLYPATH_ID)
    set_prop(actor, "RequestExpectedRevisionV1", 2)
    set_prop(actor, "RequestNowUtcV1", "2026-08-12T01:04:00Z")
    actor.call_method("UnpublishV1")
    require(prop(actor, "ResultCodeV1") == "Success", f"unpublish failed: {prop(actor, 'ResultCodeV1')}|{prop(actor, 'ResultDetailV1')}")
    require(authority_snapshot(actor)[0:2] == (4, "EDD_Repository_B"), "unpublish authority changed")
    require(list(prop(actor, "ActiveVisibilitiesV1")) == ["private"], "unpublish did not make record private")
    require(list(prop(actor, "ActiveUpdatedUtcV1")) == ["2026-08-12T01:04:00Z"], "unpublish timestamp changed")
    require(int(prop(actor, "ResultCurrentRevisionV1")) == 2, "unpublish result revision changed")
    require(document_prop(prop(actor, "ResultDraftDocumentV1"), "RevisionNumber") == 2, "unpublish result draft changed")
    decode_active(actor)
    require(prop(actor, "ScratchRecordVisibilityV1") == "private", "record remained public")
    require(int(prop(actor, "ScratchRecordDraftRevisionNumberV1")) == 2, "unpublish advanced draft")
    require(bool(prop(actor, "ScratchRecordHasPublishedRevisionV1")), "unpublish erased published flag")
    require(int(prop(actor, "ScratchRecordPublishedRevisionNumberV1")) == 1, "unpublish changed published revision")
    require(abs(float(document_prop(prop(actor, "ScratchRecordPublishedDocumentV1"), "DurationSeconds"))) < 0.001, "unpublish changed published snapshot")
    emit("FIRST_UNPUBLISH", "PASS")

    set_prop(actor, "RequestOffsetV1", 0)
    set_prop(actor, "RequestLimitV1", 20)
    actor.call_method("ListMineV1")
    require(prop(actor, "ResultCodeV1") == "Success", "owner list failed")
    metadata = [json.loads(value) for value in prop(actor, "ResultMetadataEnvelopesV1")]
    require(len(metadata) == 1, "metadata count changed")
    require(metadata[0]["visibility"] == "private", "metadata visibility changed")
    require(metadata[0]["draftRevisionNumber"] == 2, "metadata draft revision changed")
    require(metadata[0]["hasPublishedRevision"] is True, "metadata erased history")
    require(metadata[0]["publishedRevisionNumber"] == 1, "metadata published revision changed")
    emit("PRIVATE_METADATA", "PASS")

    set_prop(actor, "RequestExpectedRevisionV1", 2)
    set_prop(actor, "RequestNowUtcV1", "2026-08-12T01:05:00Z")
    actor.call_method("PublishDraftV1")
    require(prop(actor, "ResultCodeV1") == "Success", "republish failed")
    require(authority_snapshot(actor)[0:2] == (5, "EDD_Repository_A"), "republish authority changed")
    decode_active(actor)
    require(prop(actor, "ScratchRecordVisibilityV1") == "public", "republish did not restore public visibility")
    require(int(prop(actor, "ScratchRecordPublishedRevisionNumberV1")) == 2, "republish snapshot revision changed")
    require(abs(float(document_prop(prop(actor, "ScratchRecordPublishedDocumentV1"), "DurationSeconds")) - 22.0) < 0.001, "republish snapshot payload changed")
    emit("REPUBLISH", "PASS")

    set_prop(actor, "RequestExpectedRevisionV1", 2)
    set_prop(actor, "RequestNowUtcV1", "2026-08-12T01:06:00Z")
    actor.call_method("UnpublishV1")
    require(prop(actor, "ResultCodeV1") == "Success", "second unpublish failed")
    require(authority_snapshot(actor)[0:2] == (6, "EDD_Repository_B"), "second unpublish authority changed")
    decode_active(actor)
    require(prop(actor, "ScratchRecordVisibilityV1") == "private", "second unpublish remained public")
    require(int(prop(actor, "ScratchRecordDraftRevisionNumberV1")) == 2, "second unpublish advanced draft")
    require(int(prop(actor, "ScratchRecordPublishedRevisionNumberV1")) == 2, "second unpublish changed history")
    require(abs(float(document_prop(prop(actor, "ScratchRecordPublishedDocumentV1"), "DurationSeconds")) - 22.0) < 0.001, "second unpublish changed snapshot")
    latest = unreal.GameplayStatics.load_game_from_slot("EDD_Repository_B", 0)
    require(latest is not None, "generation 6 physical slot missing")
    require((int(prop(latest, "Generation")), bool(prop(latest, "Committed"))) == (6, True), "generation 6 commit changed")
    require(tuple(prop(latest, "RecordEnvelopes")) == tuple(prop(actor, "ActiveRecordEnvelopesV1")), "generation 6 physical payload changed")
    emit("SECOND_UNPUBLISH", "PASS")

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
