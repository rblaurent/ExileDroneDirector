"""Executable acceptance for owner-filtered metadata-only private listing.

The fixture is created through the compiled private-create writer so the list
boundary sees canonical Blueprint records and real A/B SaveGame state.  Every
query proves it is read-only, metadata-only, owner-filtered, deterministically
ordered, and atomic on selected-record failures.
"""

from __future__ import annotations

import json

import unreal


PREFIX = "EDD_PRIVATE_LIST_RUNTIME"
CLASS_PATH = (
    "/Game/Mods/ExileDroneDirector/Server/Repository/"
    "BP_EDD_FlypathRepository.BP_EDD_FlypathRepository_C"
)
SLOTS = ("EDD_Repository_A", "EDD_Repository_B")
METADATA_KEYS = {
    "flypathId",
    "ownerDisplayName",
    "title",
    "visibility",
    "regionId",
    "updatedUtc",
    "draftRevisionNumber",
    "hasPublishedRevision",
    "publishedRevisionNumber",
}
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


def stage_document(actor, region: str = "ExiledLands") -> None:
    document = prop(actor, "RequestDraftDocumentV1")
    for name, value in (
        ("SchemaVersion", 1),
        ("TrajectoryEngineVersion", 1),
        ("RevisionNumber", 777),
        ("RegionId", region),
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


def create_record(actor, *, flypath_id: str, owner: str, display: str, title: str, now: str) -> None:
    for name, value in (
        ("RequestRequesterAccountIdV1", owner),
        ("RequestRequesterDisplayNameV1", display),
        ("RequestFlypathIdV1", flypath_id),
        ("RequestTitleV1", title),
        ("RequestDescriptionV1", f"secret-draft-payload-{flypath_id}"),
        ("RequestRegionIdV1", "ExiledLands"),
        ("RequestNowUtcV1", now),
    ):
        set_prop(actor, name, value)
    stage_document(actor)
    actor.call_method("CreatePrivateFlypathV1")
    require(
        prop(actor, "ResultCodeV1") == "Success",
        f"create {flypath_id} failed: {prop(actor, 'ResultCodeV1')}|{prop(actor, 'ResultDetailV1')}",
    )


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


def metadata(actor):
    values = []
    for encoded in prop(actor, "ResultMetadataEnvelopesV1"):
        require("secret-draft-payload" not in encoded, "metadata leaked description/payload")
        value = json.loads(encoded)
        require(set(value) == METADATA_KEYS, f"metadata keys changed: {sorted(value)}")
        require("ownerAccountId" not in value, "metadata leaked owner account id")
        require("draft" not in value and "published" not in value, "metadata leaked document")
        values.append(value)
    return values


def list_query(actor, *, owner: str, offset: int, limit: int, label: str):
    before_authority = authority_snapshot(actor)
    before_physical = physical_snapshot()
    set_prop(actor, "RequestRequesterAccountIdV1", owner)
    set_prop(actor, "RequestOffsetV1", offset)
    set_prop(actor, "RequestLimitV1", limit)
    actor.call_method("ListMineV1")
    require(authority_snapshot(actor) == before_authority, f"{label} mutated repository authority")
    require(physical_snapshot() == before_physical, f"{label} wrote SaveGame state")
    emit(label, "PASS")
    return metadata(actor)


def publish_record(actor, flypath_id: str, revision: int) -> None:
    ids = list(prop(actor, "ActiveFlypathIdsV1"))
    index = ids.index(flypath_id)
    envelopes = list(prop(actor, "ActiveRecordEnvelopesV1"))
    set_prop(actor, "ScratchEncodedRecordV1", envelopes[index])
    actor.call_method("DecodeRecordV1")
    require(bool(prop(actor, "ScratchValidV1")), "publish fixture decode failed")
    set_prop(actor, "ScratchRecordHasPublishedRevisionV1", True)
    set_prop(actor, "ScratchRecordPublishedRevisionNumberV1", revision)
    actor.call_method("EncodeRecordV1")
    require(bool(prop(actor, "ScratchValidV1")), "publish fixture encode failed")
    envelopes[index] = prop(actor, "ScratchEncodedRecordV1")
    set_prop(actor, "ActiveRecordEnvelopesV1", envelopes)


def set_visibility(actor, flypath_id: str, visibility: str) -> None:
    ids = list(prop(actor, "ActiveFlypathIdsV1"))
    index = ids.index(flypath_id)
    envelopes = list(prop(actor, "ActiveRecordEnvelopesV1"))
    visibilities = list(prop(actor, "ActiveVisibilitiesV1"))
    set_prop(actor, "ScratchEncodedRecordV1", envelopes[index])
    actor.call_method("DecodeRecordV1")
    require(bool(prop(actor, "ScratchValidV1")), "visibility fixture decode failed")
    set_prop(actor, "ScratchRecordVisibilityV1", visibility)
    actor.call_method("EncodeRecordV1")
    require(bool(prop(actor, "ScratchValidV1")), "visibility fixture encode failed")
    envelopes[index] = prop(actor, "ScratchEncodedRecordV1")
    visibilities[index] = visibility
    set_prop(actor, "ActiveRecordEnvelopesV1", envelopes)
    set_prop(actor, "ActiveVisibilitiesV1", visibilities)


def comparator_case(actor, left: str, right: str, expected: bool, label: str) -> None:
    set_prop(actor, "ScratchCompareLeftV1", left)
    set_prop(actor, "ScratchCompareRightV1", right)
    actor.call_method("CompareStringsOrdinalV1")
    require(bool(prop(actor, "ScratchStringGreaterV1")) is expected, f"comparator {label} changed")


actor = None
try:
    delete_slots()
    repository_class = unreal.load_class(None, CLASS_PATH)
    require(repository_class is not None, "repository generated class missing")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    require(subsystem is not None, "EditorActorSubsystem unavailable")
    actor = subsystem.spawn_actor_from_class(repository_class, unreal.Vector(0, 0, -100000), unreal.Rotator(), False)
    require(actor is not None, "could not spawn repository actor")

    for left, right, expected, label in (
        ("", "", False, "EMPTY_EQUAL"),
        ("same", "same", False, "EQUAL"),
        ("prefix-z", "prefix", True, "LONGER_PREFIX"),
        ("prefix", "prefix-z", False, "SHORTER_PREFIX"),
        ("z", "a", True, "ASCII_GREATER"),
        ("a", "z", False, "ASCII_LESS"),
    ):
        comparator_case(actor, left, right, expected, label)
    emit("COMPARATOR", "PASS")

    create_record(actor, flypath_id="owner-old", owner="owner-a", display="Owner A", title="Old", now="2026-08-11T19:00:00Z")
    create_record(actor, flypath_id="owner-middle", owner="owner-a", display="Owner A", title="Middle", now="2026-08-11T19:01:00Z")
    create_record(actor, flypath_id="owner-a-tie", owner="owner-a", display="Owner A", title="A Tie", now="2026-08-11T19:02:00Z")
    create_record(actor, flypath_id="owner-z-tie", owner="owner-a", display="Owner A", title="Z Tie", now="2026-08-11T19:02:00Z")
    create_record(actor, flypath_id="foreign-newest", owner="owner-b", display="Owner B", title="Foreign", now="2026-08-11T19:03:00Z")
    publish_record(actor, "owner-middle", 7)
    set_visibility(actor, "owner-old", "public")
    clean_authority = authority_snapshot(actor)
    emit("FIXTURES", "PASS")

    values = list_query(actor, owner="   ", offset=0, limit=20, label="BLANK_REQUESTER")
    require(prop(actor, "ResultCodeV1") == "ValidationFailed", "blank requester code changed")
    require(prop(actor, "ResultDetailV1") == "InvalidListRequest", "blank requester detail changed")
    require(values == [], "blank requester leaked metadata")

    values = list_query(actor, owner="owner-a", offset=-5, limit=0, label="CLAMP_LOW")
    require(prop(actor, "ResultCodeV1") == "Success", "low clamp did not succeed")
    require(int(prop(actor, "ResultPageOffsetV1")) == 0, "negative offset was not clamped")
    require(int(prop(actor, "ResultTotalCountV1")) == 4, "owner total changed")
    require(bool(prop(actor, "ResultHasMoreV1")), "low clamp hasMore changed")
    require([item["flypathId"] for item in values] == ["owner-z-tie"], "descending tie order changed")

    values = list_query(actor, owner="owner-a", offset=0, limit=1000, label="CLAMP_HIGH_FULL_PAGE")
    expected_ids = ["owner-z-tie", "owner-a-tie", "owner-middle", "owner-old"]
    emit("FULL_ORDER", ",".join(item["flypathId"] for item in values))
    emit("OWNER_INDEXES", ",".join(str(value) for value in prop(actor, "ScratchListOwnerIndexesV1")))
    emit("SORTED_INDEXES", ",".join(str(value) for value in prop(actor, "ScratchListSortedIndexesV1")))
    emit(
        "PAGE_STATE",
        f"limit={prop(actor, 'ScratchListSafeLimitV1')}|end={prop(actor, 'ScratchListEndExclusiveV1')}|"
        f"total={prop(actor, 'ResultTotalCountV1')}",
    )
    require([item["flypathId"] for item in values] == expected_ids, "deterministic ordering changed")
    require(not bool(prop(actor, "ResultHasMoreV1")), "full page hasMore changed")
    require(all(item["flypathId"] != "foreign-newest" for item in values), "foreign owner leaked")
    require(values[-1]["visibility"] == "public", "owner public record was omitted or rewritten")
    middle = next(item for item in values if item["flypathId"] == "owner-middle")
    require(middle["hasPublishedRevision"] is True, "published boolean changed")
    require(middle["publishedRevisionNumber"] == 7, "published revision changed")
    require(next(item for item in values if item["flypathId"] == "owner-old")["hasPublishedRevision"] is False, "unpublished boolean changed")
    require(all(item["draftRevisionNumber"] == 1 for item in values), "draft revision metadata changed")
    emit("OWNER_FILTER_METADATA_ONLY", "PASS")

    values = list_query(actor, owner="owner-a", offset=1, limit=2, label="MIDDLE_PAGE")
    require([item["flypathId"] for item in values] == ["owner-a-tie", "owner-middle"], "middle page changed")
    require(int(prop(actor, "ResultPageOffsetV1")) == 1, "middle offset changed")
    require(int(prop(actor, "ResultTotalCountV1")) == 4, "middle total changed")
    require(bool(prop(actor, "ResultHasMoreV1")), "middle hasMore changed")

    values = list_query(actor, owner="owner-a", offset=50, limit=1000, label="BEYOND_PAGE")
    require(values == [], "beyond page was not empty")
    require(int(prop(actor, "ResultPageOffsetV1")) == 50, "beyond offset changed")
    require(int(prop(actor, "ResultTotalCountV1")) == 4, "beyond total changed")
    require(not bool(prop(actor, "ResultHasMoreV1")), "beyond hasMore changed")

    # A corrupt foreign record must be ignored because only selected owner rows
    # cross the strict decode boundary.
    envelopes = list(prop(actor, "ActiveRecordEnvelopesV1"))
    foreign_index = list(prop(actor, "ActiveFlypathIdsV1")).index("foreign-newest")
    foreign_envelope = envelopes[foreign_index]
    envelopes[foreign_index] = "not-json"
    set_prop(actor, "ActiveRecordEnvelopesV1", envelopes)
    values = list_query(actor, owner="owner-a", offset=0, limit=20, label="FOREIGN_CORRUPTION_IGNORED")
    require([item["flypathId"] for item in values] == expected_ids, "foreign corruption affected owner page")
    envelopes[foreign_index] = foreign_envelope
    set_prop(actor, "ActiveRecordEnvelopesV1", envelopes)

    # A selected record failure must clear even already-appended page entries.
    selected_index = list(prop(actor, "ActiveFlypathIdsV1")).index("owner-middle")
    selected_envelope = envelopes[selected_index]
    envelopes[selected_index] = "not-json"
    set_prop(actor, "ActiveRecordEnvelopesV1", envelopes)
    values = list_query(actor, owner="owner-a", offset=0, limit=20, label="SELECTED_DECODE_FAILURE")
    require(prop(actor, "ResultCodeV1") == "ValidationFailed", "selected decode code changed")
    require(prop(actor, "ResultDetailV1") == "StoredRecordDecodeFailed", "selected decode detail changed")
    require(values == [], "selected decode failure leaked partial page")
    require(int(prop(actor, "ResultTotalCountV1")) == 0, "selected decode failure leaked total")
    envelopes[selected_index] = selected_envelope
    set_prop(actor, "ActiveRecordEnvelopesV1", envelopes)

    updated = list(prop(actor, "ActiveUpdatedUtcV1"))
    saved_updated = updated[selected_index]
    updated[selected_index] = "2026-08-11T18:59:59Z"
    set_prop(actor, "ActiveUpdatedUtcV1", updated)
    values = list_query(actor, owner="owner-a", offset=0, limit=20, label="SELECTED_IDENTITY_FAILURE")
    require(prop(actor, "ResultCodeV1") == "ValidationFailed", "identity mismatch code changed")
    require(prop(actor, "ResultDetailV1") == "StoredRecordIndexMismatch", "identity mismatch detail changed")
    require(values == [], "identity mismatch leaked partial page")
    updated[selected_index] = saved_updated
    set_prop(actor, "ActiveUpdatedUtcV1", updated)

    owners = list(prop(actor, "ActiveOwnerAccountIdsV1"))
    set_prop(actor, "ActiveOwnerAccountIdsV1", owners[:-1])
    values = list_query(actor, owner="owner-a", offset=0, limit=20, label="INDEX_MISALIGNMENT")
    require(prop(actor, "ResultCodeV1") == "ValidationFailed", "misalignment code changed")
    require(prop(actor, "ResultDetailV1") == "MetadataIndexMisaligned", "misalignment detail changed")
    require(values == [], "misalignment leaked metadata")
    set_prop(actor, "ActiveOwnerAccountIdsV1", owners)

    require(authority_snapshot(actor) == clean_authority, "negative-case cleanup did not restore authority")
    emit("AUTHORITY_RESTORED", "PASS")
    emit("RESULT", "PASS")
finally:
    if actor is not None:
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        if subsystem is not None:
            subsystem.destroy_actor(actor)
    delete_slots()
