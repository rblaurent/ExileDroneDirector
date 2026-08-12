"""Executable acceptance for immutable published playback fetch."""

from __future__ import annotations

import unreal


PREFIX = "EDD_PUBLISHED_FETCH_RUNTIME"
CLASS_PATH = (
    "/Game/Mods/ExileDroneDirector/Server/Repository/"
    "BP_EDD_FlypathRepository.BP_EDD_FlypathRepository_C"
)
SLOTS = ("EDD_Repository_A", "EDD_Repository_B")
FLYPATH_ID = "published-fetch-runtime"
OWNER = "owner-fetch"
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


def emit(label, value):
    unreal.log(f"{PREFIX}|{label}|{value}")


def require(condition, message):
    if not condition:
        raise RuntimeError(f"{PREFIX}|FAIL|{message}")


def names(value):
    snake = "".join(("_" + c.lower()) if c.isupper() else c for c in value).lstrip("_")
    return value, unreal.Name(value), snake, unreal.Name(snake)


def prop(obj, name):
    for candidate in names(name):
        try:
            return obj.get_editor_property(candidate)
        except Exception:
            pass
    raise RuntimeError(f"could not read {name}")


def set_prop(obj, name, value):
    for candidate in names(name):
        try:
            obj.set_editor_property(candidate, value)
            return
        except Exception:
            pass
    raise RuntimeError(f"could not set {name}")


def doc_prop(document, name):
    for candidate in DOCUMENT_FIELDS[name]:
        try:
            return document.get_editor_property(candidate)
        except Exception:
            pass
    raise RuntimeError(f"could not read document {name}")


def set_doc(document, name, value):
    for candidate in DOCUMENT_FIELDS[name]:
        try:
            document.set_editor_property(candidate, value)
            return
        except Exception:
            pass
    raise RuntimeError(f"could not set document {name}")


def cleanup():
    for slot in SLOTS:
        if unreal.GameplayStatics.does_save_game_exist(slot, 0):
            require(unreal.GameplayStatics.delete_game_in_slot(slot, 0), f"delete failed: {slot}")


def stage_document(actor, duration, revision):
    document = prop(actor, "RequestDraftDocumentV1")
    for name, value in (
        ("SchemaVersion", 1), ("TrajectoryEngineVersion", 1), ("RevisionNumber", revision),
        ("RegionId", "ExiledLands"), ("DurationSeconds", duration),
        ("DefaultFlightProfile", "cinematic_drone"), ("Waypoints", []),
        ("Segments", []), ("ContentHash", ""),
    ):
        set_doc(document, name, value)
    set_prop(actor, "ScratchDocumentV1", document)
    actor.call_method("EncodeDocumentV1")
    actor.call_method("DecodeDocumentV1")
    require(bool(prop(actor, "ScratchValidV1")), "document round-trip failed")
    set_prop(actor, "RequestDraftDocumentV1", prop(actor, "ScratchDocumentV1"))


def authority(actor):
    return (
        int(prop(actor, "ActiveGenerationV1")), str(prop(actor, "ActiveSlotV1")),
        tuple(prop(actor, "ActiveRecordEnvelopesV1")), tuple(prop(actor, "ActiveTombstoneFlypathIdsV1")),
        tuple(prop(actor, "ActiveFlypathIdsV1")), tuple(prop(actor, "ActiveOwnerAccountIdsV1")),
        tuple(prop(actor, "ActiveVisibilitiesV1")), tuple(prop(actor, "ActiveUpdatedUtcV1")),
    )


def physical():
    result = []
    for slot in SLOTS:
        if not unreal.GameplayStatics.does_save_game_exist(slot, 0):
            result.append((slot, False))
            continue
        storage = unreal.GameplayStatics.load_game_from_slot(slot, 0)
        result.append((slot, True, int(prop(storage, "Generation")), bool(prop(storage, "Committed")),
                       tuple(prop(storage, "RecordEnvelopes")), tuple(prop(storage, "TombstoneFlypathIds"))))
    return tuple(result)


def invoke(actor, flypath_id, revision, label):
    before_authority, before_physical = authority(actor), physical()
    set_prop(actor, "RequestFlypathIdV1", flypath_id)
    set_prop(actor, "RequestExpectedRevisionV1", revision)
    actor.call_method("FetchPublishedRevisionV1")
    require(authority(actor) == before_authority, f"{label} mutated authority")
    require(physical() == before_physical, f"{label} mutated SaveGame")


def no_payload(actor, label):
    require(not bool(prop(actor, "ResultHasCurrentRevisionV1")), f"{label} leaked revision flag")
    require(int(prop(actor, "ResultCurrentRevisionV1")) == 0, f"{label} leaked revision")
    require(prop(actor, "ResultRecordEnvelopeV1") == "", f"{label} leaked record envelope")
    require(int(doc_prop(prop(actor, "ResultDraftDocumentV1"), "RevisionNumber")) == 0, f"{label} leaked draft")
    require(int(doc_prop(prop(actor, "ResultPublishedDocumentV1"), "RevisionNumber")) == 0, f"{label} leaked published payload")


actor = None
try:
    cleanup()
    repository_class = unreal.load_class(None, CLASS_PATH)
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = subsystem.spawn_actor_from_class(repository_class, unreal.Vector(0, 0, -100000), unreal.Rotator(), False)
    require(actor is not None, "spawn failed")

    for name, value in (
        ("RequestRequesterAccountIdV1", OWNER), ("RequestRequesterDisplayNameV1", "Owner Fetch"),
        ("RequestFlypathIdV1", FLYPATH_ID), ("RequestTitleV1", "Immutable Fetch"),
        ("RequestDescriptionV1", "must-not-cross-fetch"), ("RequestRegionIdV1", "ExiledLands"),
        ("RequestNowUtcV1", "2026-08-12T02:00:00Z"),
    ):
        set_prop(actor, name, value)
    stage_document(actor, 12.5, 1)
    actor.call_method("CreatePrivateFlypathV1")
    require(prop(actor, "ResultCodeV1") == "Success", "create failed")

    invoke(actor, FLYPATH_ID, 0, "PRIVATE_HIDDEN")
    require((prop(actor, "ResultCodeV1"), prop(actor, "ResultDetailV1")) == ("NotFound", "FlypathNotFound"), "private fetch boundary changed")
    no_payload(actor, "private")
    emit("PRIVATE_HIDDEN", "PASS")

    set_prop(actor, "RequestRequesterAccountIdV1", OWNER)
    set_prop(actor, "RequestFlypathIdV1", FLYPATH_ID)
    set_prop(actor, "RequestExpectedRevisionV1", 1)
    set_prop(actor, "RequestNowUtcV1", "2026-08-12T02:01:00Z")
    actor.call_method("PublishDraftV1")
    require(prop(actor, "ResultCodeV1") == "Success", "publish failed")

    invoke(actor, FLYPATH_ID, 0, "LATEST")
    require(prop(actor, "ResultCodeV1") == "Success", "latest fetch failed")
    require(bool(prop(actor, "ResultHasCurrentRevisionV1")), "latest omitted revision")
    require(int(prop(actor, "ResultCurrentRevisionV1")) == 1, "latest revision changed")
    published = prop(actor, "ResultPublishedDocumentV1")
    require(int(doc_prop(published, "RevisionNumber")) == 1, "published typed revision changed")
    require(abs(float(doc_prop(published, "DurationSeconds")) - 12.5) < 0.001, "published duration changed")
    require(prop(actor, "ResultRecordEnvelopeV1") == "", "success leaked record envelope")
    require(int(doc_prop(prop(actor, "ResultDraftDocumentV1"), "RevisionNumber")) == 0, "success leaked draft")
    emit("LATEST", "PASS")

    invoke(actor, FLYPATH_ID, 1, "EXACT")
    require(prop(actor, "ResultCodeV1") == "Success" and int(prop(actor, "ResultCurrentRevisionV1")) == 1, "exact fetch failed")
    emit("EXACT", "PASS")

    # Save a materially different private draft. Published revision 1 must remain immutable.
    set_prop(actor, "RequestRequesterAccountIdV1", OWNER)
    set_prop(actor, "RequestFlypathIdV1", FLYPATH_ID)
    set_prop(actor, "RequestExpectedRevisionV1", 1)
    set_prop(actor, "RequestNowUtcV1", "2026-08-12T02:02:00Z")
    stage_document(actor, 44.0, 999)
    actor.call_method("SaveDraftV1")
    require(prop(actor, "ResultCodeV1") == "Success", "save failed")
    invoke(actor, FLYPATH_ID, 1, "IMMUTABLE_AFTER_SAVE")
    require(abs(float(doc_prop(prop(actor, "ResultPublishedDocumentV1"), "DurationSeconds")) - 12.5) < 0.001, "draft save mutated published snapshot")
    emit("IMMUTABLE_AFTER_SAVE", "PASS")

    for revision, code, detail, label in (
        (-1, "ValidationFailed", "InvalidPublishedRevisionRequest", "NEGATIVE_REVISION"),
        (2, "NotFound", "PublishedRevisionNotFound", "WRONG_REVISION"),
    ):
        invoke(actor, FLYPATH_ID, revision, label)
        require((prop(actor, "ResultCodeV1"), prop(actor, "ResultDetailV1")) == (code, detail), f"{label} result changed")
        no_payload(actor, label)
        emit(label, "PASS")

    invoke(actor, "missing", 0, "MISSING")
    require((prop(actor, "ResultCodeV1"), prop(actor, "ResultDetailV1")) == ("NotFound", "FlypathNotFound"), "missing result changed")
    no_payload(actor, "missing")
    emit("MISSING", "PASS")

    ids = list(prop(actor, "ActiveFlypathIdsV1"))
    index = ids.index(FLYPATH_ID)
    envelopes = list(prop(actor, "ActiveRecordEnvelopesV1"))
    saved_envelope = envelopes[index]
    envelopes[index] = "not-json"
    set_prop(actor, "ActiveRecordEnvelopesV1", envelopes)
    invoke(actor, FLYPATH_ID, 0, "CORRUPT_PUBLIC")
    require(prop(actor, "ResultDetailV1") == "StoredRecordDecodeFailed", "corrupt public detail changed")
    no_payload(actor, "corrupt public")
    envelopes[index] = saved_envelope
    set_prop(actor, "ActiveRecordEnvelopesV1", envelopes)
    emit("CORRUPT_PUBLIC", "PASS")

    visibilities = list(prop(actor, "ActiveVisibilitiesV1"))
    visibilities[index] = "private"
    set_prop(actor, "ActiveVisibilitiesV1", visibilities)
    invoke(actor, FLYPATH_ID, 0, "DERIVED_PRIVATE")
    require((prop(actor, "ResultCodeV1"), prop(actor, "ResultDetailV1")) == ("NotFound", "FlypathNotFound"), "derived private leaked")
    no_payload(actor, "derived private")
    visibilities[index] = "public"
    set_prop(actor, "ActiveVisibilitiesV1", visibilities)
    emit("DERIVED_PRIVATE", "PASS")

    set_prop(actor, "ActiveVisibilitiesV1", [])
    invoke(actor, FLYPATH_ID, 0, "MISALIGNED")
    require(prop(actor, "ResultDetailV1") == "MetadataIndexMisaligned", "misalignment detail changed")
    no_payload(actor, "misaligned")
    set_prop(actor, "ActiveVisibilitiesV1", visibilities)
    emit("MISALIGNED", "PASS")

    emit("RESTART_FIXTURE", f"{prop(actor, 'ActiveGenerationV1')}|{prop(actor, 'ActiveSlotV1')}")
    emit("RESULT", "PASS")
finally:
    if actor is not None:
        unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(actor)
