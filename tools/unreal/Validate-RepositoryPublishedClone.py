"""Executable acceptance for private cloning of an immutable published revision.

The test drives only compiled Blueprint public functions and real alternating
SaveGame slots.  It leaves a generation-7 fixture for the fresh-process restart
validator; every failed request proves both authority and physical slots stable.
"""

from __future__ import annotations

import json
import unreal


PREFIX = "EDD_PUBLISHED_CLONE_RUNTIME"
CLASS_PATH = "/Game/Mods/ExileDroneDirector/Server/Repository/BP_EDD_FlypathRepository.BP_EDD_FlypathRepository_C"
SLOTS = ("EDD_Repository_A", "EDD_Repository_B")
SOURCE_ID = "clone-source-a"
CLONE_ID = "clone-target-b"
OWNER_A = "clone-owner-a"
OWNER_B = "clone-owner-b"
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


def emit(label, value): unreal.log(f"{PREFIX}|{label}|{value}")
def require(condition, message):
    if not condition: raise RuntimeError(f"{PREFIX}|FAIL|{message}")
def names(value):
    snake = "".join(("_" + c.lower()) if c.isupper() else c for c in value).lstrip("_")
    return value, unreal.Name(value), snake, unreal.Name(snake)
def prop(obj, name):
    for candidate in names(name):
        try: return obj.get_editor_property(candidate)
        except Exception: pass
    raise RuntimeError(f"could not read {name}")
def set_prop(obj, name, value):
    for candidate in names(name):
        try: obj.set_editor_property(candidate, value); return
        except Exception: pass
    raise RuntimeError(f"could not set {name}")
def doc_prop(document, name):
    for candidate in DOCUMENT_FIELDS[name]:
        try: return document.get_editor_property(candidate)
        except Exception: pass
    raise RuntimeError(f"could not read document {name}")
def set_doc(document, name, value):
    for candidate in DOCUMENT_FIELDS[name]:
        try: document.set_editor_property(candidate, value); return
        except Exception: pass
    raise RuntimeError(f"could not set document {name}")


def cleanup():
    for slot in SLOTS:
        if unreal.GameplayStatics.does_save_game_exist(slot, 0):
            require(unreal.GameplayStatics.delete_game_in_slot(slot, 0), f"delete failed {slot}")


def stage_document(actor, duration, caller_revision=1):
    document = prop(actor, "RequestDraftDocumentV1")
    for name, value in (
        ("SchemaVersion", 1), ("TrajectoryEngineVersion", 1),
        ("RevisionNumber", caller_revision), ("RegionId", "ExiledLands"),
        ("DurationSeconds", duration), ("DefaultFlightProfile", "cinematic_drone"),
        ("Waypoints", []), ("Segments", []), ("ContentHash", "caller-hash-ignored"),
    ): set_doc(document, name, value)
    set_prop(actor, "ScratchDocumentV1", document)
    actor.call_method("EncodeDocumentV1")
    actor.call_method("DecodeDocumentV1")
    require(bool(prop(actor, "ScratchValidV1")), "document fixture round-trip failed")
    set_prop(actor, "RequestDraftDocumentV1", prop(actor, "ScratchDocumentV1"))


def authority(actor):
    return (
        int(prop(actor, "ActiveGenerationV1")), str(prop(actor, "ActiveSlotV1")),
        tuple(prop(actor, "ActiveRecordEnvelopesV1")), tuple(prop(actor, "ActiveTombstoneFlypathIdsV1")),
        tuple(prop(actor, "ActiveFlypathIdsV1")), tuple(prop(actor, "ActiveOwnerAccountIdsV1")),
        tuple(prop(actor, "ActiveVisibilitiesV1")), tuple(prop(actor, "ActiveUpdatedUtcV1")),
    )


def physical():
    rows = []
    for slot in SLOTS:
        if not unreal.GameplayStatics.does_save_game_exist(slot, 0):
            rows.append((slot, False)); continue
        storage = unreal.GameplayStatics.load_game_from_slot(slot, 0)
        rows.append((slot, True, int(prop(storage, "Generation")), bool(prop(storage, "Committed")),
                     tuple(prop(storage, "RecordEnvelopes")), tuple(prop(storage, "TombstoneFlypathIds"))))
    return tuple(rows)


def seed_stale(actor):
    set_prop(actor, "ResultRecordEnvelopeV1", "stale")
    set_prop(actor, "ResultMetadataEnvelopesV1", ["stale"])
    set_prop(actor, "ResultHasCurrentRevisionV1", True)
    set_prop(actor, "ResultCurrentRevisionV1", 999)
    set_prop(actor, "ResultRecordIndexV1", 999)


def no_payload(actor, conflict=None):
    require(prop(actor, "ResultRecordEnvelopeV1") == "", "rejection leaked envelope")
    require(list(prop(actor, "ResultMetadataEnvelopesV1")) == [], "rejection leaked metadata")
    require(int(prop(actor, "ResultRecordIndexV1")) == -1, "rejection leaked index")
    require(int(doc_prop(prop(actor, "ResultDraftDocumentV1"), "RevisionNumber")) == 0, "rejection leaked draft")
    if conflict is None:
        require(not bool(prop(actor, "ResultHasCurrentRevisionV1")), "rejection leaked revision flag")
        require(int(prop(actor, "ResultCurrentRevisionV1")) == 0, "rejection leaked revision")
    else:
        require(bool(prop(actor, "ResultHasCurrentRevisionV1")), "conflict omitted revision flag")
        require(int(prop(actor, "ResultCurrentRevisionV1")) == conflict, "conflict revision changed")


def stage_clone(actor, **overrides):
    values = {
        "RequestRequesterAccountIdV1": OWNER_B,
        "RequestRequesterDisplayNameV1": "Clone Owner B",
        "RequestSourceFlypathIdV1": SOURCE_ID,
        "RequestFlypathIdV1": CLONE_ID,
        "RequestTitleV1": "Private Remix",
        "RequestDescriptionV1": "deep immutable published clone",
        "RequestExpectedRevisionV1": 2,
        "RequestNowUtcV1": "2026-08-12T04:06:00Z",
    }
    values.update(overrides)
    for name, value in values.items(): set_prop(actor, name, value)


def rejected(actor, code, detail, label, conflict=None, **overrides):
    before_authority, before_physical = authority(actor), physical()
    seed_stale(actor); stage_clone(actor, **overrides)
    actor.call_method("ClonePublishedV1")
    require((prop(actor, "ResultCodeV1"), prop(actor, "ResultDetailV1")) == (code, detail), f"{label} result changed")
    no_payload(actor, conflict)
    require(authority(actor) == before_authority, f"{label} mutated authority")
    require(physical() == before_physical, f"{label} wrote SaveGame")
    emit(label, "PASS")


def decode_index(actor, flypath_id):
    index = list(prop(actor, "ActiveFlypathIdsV1")).index(flypath_id)
    set_prop(actor, "ScratchEncodedRecordV1", list(prop(actor, "ActiveRecordEnvelopesV1"))[index])
    actor.call_method("DecodeRecordV1")
    require(bool(prop(actor, "ScratchValidV1")), f"decode failed {flypath_id}")
    return index


actor = None
leave_for_restart = False
try:
    cleanup()
    cls = unreal.load_class(None, CLASS_PATH)
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = subsystem.spawn_actor_from_class(cls, unreal.Vector(0, 0, -100000), unreal.Rotator(), False)
    require(actor is not None, "spawn failed")

    # Source revisions: publish 1, save/publish 2, then edit private draft 3.
    for name, value in (
        ("RequestRequesterAccountIdV1", OWNER_A), ("RequestRequesterDisplayNameV1", "Source Author A"),
        ("RequestFlypathIdV1", SOURCE_ID), ("RequestTitleV1", "Published Original"),
        ("RequestDescriptionV1", "source fixture"), ("RequestRegionIdV1", "ExiledLands"),
        ("RequestNowUtcV1", "2026-08-12T04:00:00Z"),
    ): set_prop(actor, name, value)
    stage_document(actor, 11.0)
    actor.call_method("CreatePrivateFlypathV1"); require(prop(actor, "ResultCodeV1") == "Success", "create source failed")
    set_prop(actor, "RequestExpectedRevisionV1", 1); set_prop(actor, "RequestNowUtcV1", "2026-08-12T04:01:00Z")
    actor.call_method("PublishDraftV1"); require(prop(actor, "ResultCodeV1") == "Success", "publish source r1 failed")
    stage_document(actor, 22.0, 777); set_prop(actor, "RequestExpectedRevisionV1", 1); set_prop(actor, "RequestNowUtcV1", "2026-08-12T04:02:00Z")
    actor.call_method("SaveDraftV1"); require(prop(actor, "ResultCodeV1") == "Success", "save source r2 failed")
    set_prop(actor, "RequestExpectedRevisionV1", 2); set_prop(actor, "RequestNowUtcV1", "2026-08-12T04:03:00Z")
    actor.call_method("PublishDraftV1"); require(prop(actor, "ResultCodeV1") == "Success", "publish source r2 failed")
    stage_document(actor, 99.0, 888); set_prop(actor, "RequestExpectedRevisionV1", 2); set_prop(actor, "RequestNowUtcV1", "2026-08-12T04:04:00Z")
    actor.call_method("SaveDraftV1"); require(prop(actor, "ResultCodeV1") == "Success", "save source r3 failed")
    require(authority(actor)[0:2] == (5, "EDD_Repository_A"), "source fixture generation changed")
    emit("SOURCE_FIXTURE", "PASS")

    for field in ("RequestRequesterAccountIdV1", "RequestSourceFlypathIdV1", "RequestFlypathIdV1", "RequestTitleV1", "RequestNowUtcV1"):
        rejected(actor, "ValidationFailed", "InvalidCloneRequest", f"BLANK_{field}", **{field: "   "})
    for revision in (0, -1):
        rejected(actor, "ValidationFailed", "InvalidPublishedRevisionRequest", f"INVALID_REVISION_{revision}", RequestExpectedRevisionV1=revision)
    set_prop(actor, "MaxTitleCharsV1", 3)
    rejected(actor, "LimitExceeded", "TitleLength", "TITLE_LIMIT")
    set_prop(actor, "MaxTitleCharsV1", 96)
    rejected(actor, "NotFound", "FlypathNotFound", "MISSING_SOURCE", RequestSourceFlypathIdV1="missing")
    rejected(actor, "RevisionConflict", "PublishedRevisionMismatch", "REVISION_CONFLICT", conflict=2, RequestExpectedRevisionV1=1)
    rejected(actor, "AlreadyExists", "FlypathIdCollision", "TARGET_COLLISION", RequestFlypathIdV1=SOURCE_ID)
    set_prop(actor, "AllowedRegionsV1", ["Siptah"])
    rejected(actor, "RegionForbidden", "RegionNotAllowed", "REGION_POLICY")
    set_prop(actor, "AllowedRegionsV1", ["ExiledLands", "Siptah"])
    set_prop(actor, "MaxWaypointsPerPathV1", -1)
    rejected(actor, "LimitExceeded", "WaypointCount", "WAYPOINT_LIMIT")
    set_prop(actor, "MaxWaypointsPerPathV1", 512)
    set_prop(actor, "MaxPathsPerOwnerV1", 0)
    rejected(actor, "LimitExceeded", "OwnerPathLimit", "OWNER_LIMIT")
    set_prop(actor, "MaxPathsPerOwnerV1", 64)
    set_prop(actor, "MaxSerializedBytesV1", 1)
    rejected(actor, "LimitExceeded", "SerializedSize", "SERIALIZED_SIZE")
    set_prop(actor, "MaxSerializedBytesV1", 2000000)

    source_index = list(prop(actor, "ActiveFlypathIdsV1")).index(SOURCE_ID)
    vis = list(prop(actor, "ActiveVisibilitiesV1")); vis[source_index] = "private"; set_prop(actor, "ActiveVisibilitiesV1", vis)
    rejected(actor, "NotFound", "FlypathNotFound", "DERIVED_PRIVATE")
    vis[source_index] = "public"; set_prop(actor, "ActiveVisibilitiesV1", vis)
    envelopes = list(prop(actor, "ActiveRecordEnvelopesV1")); source_envelope = envelopes[source_index]
    envelopes[source_index] = "not-json"; set_prop(actor, "ActiveRecordEnvelopesV1", envelopes)
    rejected(actor, "ValidationFailed", "StoredRecordDecodeFailed", "CORRUPT_SOURCE")
    envelopes[source_index] = source_envelope; set_prop(actor, "ActiveRecordEnvelopesV1", envelopes)
    set_prop(actor, "ActiveVisibilitiesV1", [])
    rejected(actor, "ValidationFailed", "MetadataIndexMisaligned", "MISALIGNED_SOURCE")
    set_prop(actor, "ActiveVisibilitiesV1", vis)

    stage_clone(actor)
    actor.call_method("ClonePublishedV1")
    require(prop(actor, "ResultCodeV1") == "Success", f"clone failed {prop(actor, 'ResultCodeV1')}|{prop(actor, 'ResultDetailV1')}")
    require(authority(actor)[0:2] == (6, "EDD_Repository_B"), "clone generation/slot changed")
    require(list(prop(actor, "ActiveFlypathIdsV1")) == [SOURCE_ID, CLONE_ID], "deterministic clone ID order changed")
    require(list(prop(actor, "ActiveOwnerAccountIdsV1")) == [OWNER_A, OWNER_B], "clone owner index changed")
    require(list(prop(actor, "ActiveVisibilitiesV1")) == ["public", "private"], "clone was not private by default")
    require(int(prop(actor, "ResultRecordIndexV1")) == 1 and int(prop(actor, "ResultCurrentRevisionV1")) == 1, "clone result revision/index changed")
    require(bool(prop(actor, "ResultHasCurrentRevisionV1")), "clone omitted revision flag")
    result_doc = prop(actor, "ResultDraftDocumentV1")
    require(int(doc_prop(result_doc, "RevisionNumber")) == 1, "clone document revision changed")
    require(abs(float(doc_prop(result_doc, "DurationSeconds")) - 22.0) < 0.001, "clone did not copy immutable published r2")
    require(str(doc_prop(result_doc, "ContentHash")) == "", "clone retained source content hash")
    decode_index(actor, CLONE_ID)
    require(prop(actor, "ScratchRecordOwnerAccountIdV1") == OWNER_B, "clone owner changed")
    require(prop(actor, "ScratchRecordVisibilityV1") == "private", "clone visibility changed")
    require(int(prop(actor, "ScratchRecordDraftRevisionNumberV1")) == 1, "clone draft revision changed")
    require(not bool(prop(actor, "ScratchRecordHasPublishedRevisionV1")), "clone inherited published state")
    require(bool(prop(actor, "ScratchRecordHasSourceAttributionV1")), "clone attribution missing")
    require(prop(actor, "ScratchRecordSourceFlypathIdV1") == SOURCE_ID, "source attribution ID changed")
    require(int(prop(actor, "ScratchRecordSourceRevisionNumberV1")) == 2, "source attribution revision changed")
    require(prop(actor, "ScratchRecordSourceTitleV1") == "Published Original", "source attribution title changed")
    require(prop(actor, "ScratchRecordSourceCreatorDisplayNameV1") == "Source Author A", "source attribution creator changed")
    emit("PRIVATE_CLONE", "PASS")
    emit("ATTRIBUTION", "PASS")
    emit("IMMUTABLE_PUBLISHED_COPY", "PASS")

    set_prop(actor, "RequestRequesterAccountIdV1", OWNER_A); set_prop(actor, "RequestFlypathIdV1", CLONE_ID)
    actor.call_method("LoadDraftV1"); require(prop(actor, "ResultCodeV1") == "Forbidden", "source owner loaded clone")
    set_prop(actor, "RequestRequesterAccountIdV1", OWNER_B)
    actor.call_method("LoadDraftV1"); require(prop(actor, "ResultCodeV1") == "Success", "clone owner could not load clone")
    require(abs(float(doc_prop(prop(actor, "ResultDraftDocumentV1"), "DurationSeconds")) - 22.0) < 0.001, "owner load changed clone")
    set_prop(actor, "RequestOffsetV1", 0); set_prop(actor, "RequestLimitV1", 20)
    actor.call_method("ListMineV1")
    mine = [json.loads(x) for x in prop(actor, "ResultMetadataEnvelopesV1")]
    require([x["flypathId"] for x in mine] == [CLONE_ID], "owner list boundary changed")
    actor.call_method("ListPublicV1")
    public = [json.loads(x) for x in prop(actor, "ResultMetadataEnvelopesV1")]
    require([x["flypathId"] for x in public] == [SOURCE_ID], "private clone leaked into public list")
    emit("OWNER_AND_VISIBILITY_BOUNDARY", "PASS")

    # Mutate source draft after cloning; clone payload and attribution must not move.
    set_prop(actor, "RequestRequesterAccountIdV1", OWNER_A); set_prop(actor, "RequestFlypathIdV1", SOURCE_ID)
    set_prop(actor, "RequestExpectedRevisionV1", 3); set_prop(actor, "RequestNowUtcV1", "2026-08-12T04:07:00Z")
    stage_document(actor, 123.0, 999)
    actor.call_method("SaveDraftV1"); require(prop(actor, "ResultCodeV1") == "Success", "post-clone source save failed")
    require(authority(actor)[0:2] == (7, "EDD_Repository_A"), "post-clone generation changed")
    set_prop(actor, "RequestRequesterAccountIdV1", OWNER_B); set_prop(actor, "RequestFlypathIdV1", CLONE_ID)
    actor.call_method("LoadDraftV1"); require(prop(actor, "ResultCodeV1") == "Success", "clone load after source edit failed")
    require(abs(float(doc_prop(prop(actor, "ResultDraftDocumentV1"), "DurationSeconds")) - 22.0) < 0.001, "source edit mutated clone")
    decode_index(actor, CLONE_ID)
    require(int(prop(actor, "ScratchRecordSourceRevisionNumberV1")) == 2, "source edit mutated attribution")
    emit("SOURCE_EDIT_INDEPENDENCE", "PASS")

    latest = unreal.GameplayStatics.load_game_from_slot("EDD_Repository_A", 0)
    require(latest is not None and int(prop(latest, "Generation")) == 7 and bool(prop(latest, "Committed")), "latest SaveGame commit changed")
    require(tuple(prop(latest, "RecordEnvelopes")) == tuple(prop(actor, "ActiveRecordEnvelopesV1")), "physical payload differs from authority")
    leave_for_restart = True
    emit("RESTART_FIXTURE", "7|EDD_Repository_A")
    emit("RESULT", "PASS")
finally:
    if actor is not None:
        unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(actor)
    if not leave_for_restart: cleanup()

