"""Executable acceptance for bounded, metadata-only public discovery."""

from __future__ import annotations

import json
import unreal


PREFIX = "EDD_PUBLIC_LIST_RUNTIME"
CLASS_PATH = (
    "/Game/Mods/ExileDroneDirector/Server/Repository/"
    "BP_EDD_FlypathRepository.BP_EDD_FlypathRepository_C"
)
SLOTS = ("EDD_Repository_A", "EDD_Repository_B")
METADATA_KEYS = {
    "flypathId", "ownerDisplayName", "title", "visibility", "regionId",
    "updatedUtc", "draftRevisionNumber", "hasPublishedRevision",
    "publishedRevisionNumber",
}
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


def stage_document(actor):
    document = prop(actor, "RequestDraftDocumentV1")
    for name, value in (
        ("SchemaVersion", 1), ("TrajectoryEngineVersion", 1), ("RevisionNumber", 999),
        ("RegionId", "ExiledLands"), ("DurationSeconds", 0.0),
        ("DefaultFlightProfile", "cinematic_drone"), ("Waypoints", []),
        ("Segments", []), ("ContentHash", ""),
    ):
        set_doc(document, name, value)
    set_prop(actor, "ScratchDocumentV1", document)
    actor.call_method("EncodeDocumentV1")
    actor.call_method("DecodeDocumentV1")
    require(bool(prop(actor, "ScratchValidV1")), "document round-trip failed")
    set_prop(actor, "RequestDraftDocumentV1", prop(actor, "ScratchDocumentV1"))


def create(actor, flypath_id, owner, now):
    for name, value in (
        ("RequestRequesterAccountIdV1", owner),
        ("RequestRequesterDisplayNameV1", owner.upper()),
        ("RequestFlypathIdV1", flypath_id),
        ("RequestTitleV1", f"Title {flypath_id}"),
        ("RequestDescriptionV1", f"secret-payload-{flypath_id}"),
        ("RequestRegionIdV1", "ExiledLands"),
        ("RequestNowUtcV1", now),
    ):
        set_prop(actor, name, value)
    stage_document(actor)
    actor.call_method("CreatePrivateFlypathV1")
    require(prop(actor, "ResultCodeV1") == "Success", f"create failed: {flypath_id}")


def publish(actor, flypath_id, owner, now):
    for name, value in (
        ("RequestRequesterAccountIdV1", owner),
        ("RequestFlypathIdV1", flypath_id),
        ("RequestExpectedRevisionV1", 1),
        ("RequestNowUtcV1", now),
    ):
        set_prop(actor, name, value)
    actor.call_method("PublishDraftV1")
    require(prop(actor, "ResultCodeV1") == "Success", f"publish failed: {flypath_id}")


def unpublish(actor, flypath_id, owner, now):
    for name, value in (
        ("RequestRequesterAccountIdV1", owner),
        ("RequestFlypathIdV1", flypath_id),
        ("RequestExpectedRevisionV1", 1),
        ("RequestNowUtcV1", now),
    ):
        set_prop(actor, name, value)
    actor.call_method("UnpublishV1")
    require(prop(actor, "ResultCodeV1") == "Success", f"unpublish failed: {flypath_id}")


def authority(actor):
    return (
        int(prop(actor, "ActiveGenerationV1")), str(prop(actor, "ActiveSlotV1")),
        tuple(prop(actor, "ActiveRecordEnvelopesV1")),
        tuple(prop(actor, "ActiveTombstoneFlypathIdsV1")),
        tuple(prop(actor, "ActiveFlypathIdsV1")),
        tuple(prop(actor, "ActiveOwnerAccountIdsV1")),
        tuple(prop(actor, "ActiveVisibilitiesV1")),
        tuple(prop(actor, "ActiveUpdatedUtcV1")),
    )


def physical():
    result = []
    for slot in SLOTS:
        if not unreal.GameplayStatics.does_save_game_exist(slot, 0):
            result.append((slot, False))
            continue
        storage = unreal.GameplayStatics.load_game_from_slot(slot, 0)
        require(storage is not None, f"load failed: {slot}")
        result.append((
            slot, True, int(prop(storage, "Generation")), bool(prop(storage, "Committed")),
            tuple(prop(storage, "RecordEnvelopes")), tuple(prop(storage, "TombstoneFlypathIds")),
        ))
    return tuple(result)


def query(actor, offset, limit, label):
    before_authority, before_physical = authority(actor), physical()
    set_prop(actor, "RequestOffsetV1", offset)
    set_prop(actor, "RequestLimitV1", limit)
    actor.call_method("ListPublicV1")
    require(authority(actor) == before_authority, f"{label} mutated authority")
    require(physical() == before_physical, f"{label} mutated SaveGame")
    values = []
    for encoded in prop(actor, "ResultMetadataEnvelopesV1"):
        require("secret-payload" not in encoded, "metadata leaked private payload")
        value = json.loads(encoded)
        require(set(value) == METADATA_KEYS, "metadata shape changed")
        require(value["visibility"] == "public", "private metadata leaked")
        values.append(value)
    emit(label, "PASS")
    return values


actor = None
try:
    cleanup()
    repository_class = unreal.load_class(None, CLASS_PATH)
    require(repository_class is not None, "generated class missing")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = subsystem.spawn_actor_from_class(
        repository_class, unreal.Vector(0, 0, -100000), unreal.Rotator(), False
    )
    require(actor is not None, "spawn failed")

    fixtures = (
        ("private-newest", "owner-a", "2026-08-11T22:00:00Z"),
        ("public-alpha", "owner-a", "2026-08-11T20:00:00Z"),
        ("public-zulu", "owner-b", "2026-08-11T20:00:00Z"),
        ("public-newest", "owner-c", "2026-08-11T21:00:00Z"),
        ("private-other", "owner-d", "2026-08-11T19:00:00Z"),
    )
    for item in fixtures:
        create(actor, *item)
    publish(actor, "public-alpha", "owner-a", "2026-08-11T22:01:00Z")
    publish(actor, "public-zulu", "owner-b", "2026-08-11T22:01:00Z")
    publish(actor, "public-newest", "owner-c", "2026-08-11T22:02:00Z")
    emit("FIXTURE_WRITERS", "PASS")

    page = query(actor, -10, 2, "CLAMP_LOW")
    require([v["flypathId"] for v in page] == ["public-newest", "public-zulu"], "page order changed")
    require(int(prop(actor, "ResultPageOffsetV1")) == 0, "offset clamp changed")
    require(int(prop(actor, "ResultTotalCountV1")) == 3, "public total changed")
    require(bool(prop(actor, "ResultHasMoreV1")), "hasMore changed")

    page = query(actor, 0, 1000, "FULL_PAGE")
    require(
        [v["flypathId"] for v in page]
        == ["public-newest", "public-zulu", "public-alpha"],
        "deterministic public order changed",
    )
    require(not bool(prop(actor, "ResultHasMoreV1")), "full hasMore changed")
    require(all(v["hasPublishedRevision"] for v in page), "published metadata flag changed")
    require(all(v["publishedRevisionNumber"] == 1 for v in page), "published revision changed")
    emit("PUBLIC_ONLY_METADATA_ONLY", "PASS")

    page = query(actor, 1, 1, "MIDDLE_PAGE")
    require([v["flypathId"] for v in page] == ["public-zulu"], "middle page changed")
    page = query(actor, 50, 20, "BEYOND_PAGE")
    require(page == [] and not bool(prop(actor, "ResultHasMoreV1")), "beyond page changed")

    ids = list(prop(actor, "ActiveFlypathIdsV1"))
    envelopes = list(prop(actor, "ActiveRecordEnvelopesV1"))
    private_index = ids.index("private-newest")
    saved_private = envelopes[private_index]
    envelopes[private_index] = "not-json"
    set_prop(actor, "ActiveRecordEnvelopesV1", envelopes)
    require(len(query(actor, 0, 20, "PRIVATE_CORRUPTION_IGNORED")) == 3, "private corruption leaked")
    envelopes[private_index] = saved_private
    set_prop(actor, "ActiveRecordEnvelopesV1", envelopes)

    public_index = ids.index("public-zulu")
    saved_public = envelopes[public_index]
    envelopes[public_index] = "not-json"
    set_prop(actor, "ActiveRecordEnvelopesV1", envelopes)
    require(query(actor, 0, 20, "PUBLIC_DECODE_FAILURE") == [], "failure leaked partial page")
    require(prop(actor, "ResultDetailV1") == "StoredRecordDecodeFailed", "decode detail changed")
    envelopes[public_index] = saved_public
    set_prop(actor, "ActiveRecordEnvelopesV1", envelopes)

    visibilities = list(prop(actor, "ActiveVisibilitiesV1"))
    visibilities[public_index] = "private"
    set_prop(actor, "ActiveVisibilitiesV1", visibilities)
    page = query(actor, 0, 20, "DERIVED_PRIVATE_HIDDEN")
    require([v["flypathId"] for v in page] == ["public-newest", "public-alpha"], "derived private leaked")
    visibilities[public_index] = "public"
    set_prop(actor, "ActiveVisibilitiesV1", visibilities)

    updated = list(prop(actor, "ActiveUpdatedUtcV1"))
    saved_updated = updated[public_index]
    updated[public_index] = "2026-08-11T00:00:00Z"
    set_prop(actor, "ActiveUpdatedUtcV1", updated)
    require(query(actor, 0, 20, "PUBLIC_IDENTITY_FAILURE") == [], "identity failure leaked page")
    require(prop(actor, "ResultDetailV1") == "StoredRecordIndexMismatch", "identity detail changed")
    updated[public_index] = saved_updated
    set_prop(actor, "ActiveUpdatedUtcV1", updated)

    owners = list(prop(actor, "ActiveOwnerAccountIdsV1"))
    set_prop(actor, "ActiveOwnerAccountIdsV1", owners[:-1])
    require(query(actor, 0, 20, "INDEX_MISALIGNMENT") == [], "misalignment leaked page")
    require(prop(actor, "ResultDetailV1") == "MetadataIndexMisaligned", "misalignment detail changed")
    set_prop(actor, "ActiveOwnerAccountIdsV1", owners)

    unpublish(actor, "public-zulu", "owner-b", "2026-08-11T22:03:00Z")
    page = query(actor, 0, 20, "UNPUBLISH_HIDES")
    require([v["flypathId"] for v in page] == ["public-newest", "public-alpha"], "unpublish discovery changed")
    require(int(prop(actor, "ResultTotalCountV1")) == 2, "unpublish total changed")
    emit("RESTART_FIXTURE", f"{prop(actor, 'ActiveGenerationV1')}|{prop(actor, 'ActiveSlotV1')}")
    emit("RESULT", "PASS")
finally:
    if actor is not None:
        unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(actor)
