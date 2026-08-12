"""Fresh-process recovery and resumed-write acceptance for PublishDraftV1.

Run after ``Validate-RepositoryPublishDraft.py`` leaves generation 4 in slot B
and after the interactive editor has exited cleanly.  The oracle proves that
the public snapshot survives a true process boundary, remains immutable while
the draft advances, can be republished, and is physically committed before
both acceptance slots are cleaned.
"""

from __future__ import annotations

import json
import unreal


PREFIX = "EDD_PUBLISH_DRAFT_RESTART"
CLASS_PATH = (
    "/Game/Mods/ExileDroneDirector/Server/Repository/"
    "BP_EDD_FlypathRepository.BP_EDD_FlypathRepository_C"
)
SLOTS = ("EDD_Repository_A", "EDD_Repository_B")
FLYPATH_ID = "publish-runtime-a"
OWNER = "owner-a"
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
    require(bool(prop(actor, "ScratchValidV1")), "restart document did not round-trip")
    set_prop(actor, "RequestDraftDocumentV1", prop(actor, "ScratchDocumentV1"))


def decode_active(actor) -> None:
    envelopes = list(prop(actor, "ActiveRecordEnvelopesV1"))
    require(len(envelopes) == 1, "active record count changed")
    set_prop(actor, "ScratchEncodedRecordV1", envelopes[0])
    actor.call_method("DecodeRecordV1")
    require(bool(prop(actor, "ScratchValidV1")), "active record did not decode")


def physical(slot: str):
    require(unreal.GameplayStatics.does_save_game_exist(slot, 0), f"fixture missing: {slot}")
    storage = unreal.GameplayStatics.load_game_from_slot(slot, 0)
    require(storage is not None, f"could not load {slot}")
    return (
        int(prop(storage, "Generation")),
        bool(prop(storage, "Committed")),
        tuple(prop(storage, "RecordEnvelopes")),
        tuple(prop(storage, "TombstoneFlypathIds")),
    )


def cleanup() -> None:
    for slot in SLOTS:
        if unreal.GameplayStatics.does_save_game_exist(slot, 0):
            require(unreal.GameplayStatics.delete_game_in_slot(slot, 0), f"could not delete {slot}")
        require(not unreal.GameplayStatics.does_save_game_exist(slot, 0), f"slot survived cleanup: {slot}")


actor = None
try:
    require(all(unreal.GameplayStatics.does_save_game_exist(slot, 0) for slot in SLOTS), "publication fixtures missing")
    repository_class = unreal.load_class(None, CLASS_PATH)
    require(repository_class is not None, "repository generated class missing")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    require(subsystem is not None, "EditorActorSubsystem unavailable")
    actor = subsystem.spawn_actor_from_class(repository_class, unreal.Vector(0, 0, -100000), unreal.Rotator(), False)
    require(actor is not None, "could not spawn repository actor")
    actor.call_method("LoadRepositoryV1")

    require(bool(prop(actor, "RepositoryLoadedV1")), "repository did not recover")
    require(int(prop(actor, "ActiveGenerationV1")) == 4, "recovered generation changed")
    require(str(prop(actor, "ActiveSlotV1")) == "EDD_Repository_B", "recovered slot changed")
    require(list(prop(actor, "ActiveFlypathIdsV1")) == [FLYPATH_ID], "recovered ID changed")
    require(list(prop(actor, "ActiveOwnerAccountIdsV1")) == [OWNER], "recovered owner changed")
    require(list(prop(actor, "ActiveVisibilitiesV1")) == ["public"], "recovered visibility changed")
    require(list(prop(actor, "ActiveUpdatedUtcV1")) == ["2026-08-12T00:14:00Z"], "recovered timestamp changed")
    require(list(prop(actor, "ActiveTombstoneFlypathIdsV1")) == [], "recovered tombstones changed")
    require(physical("EDD_Repository_B")[0:2] == (4, True), "generation 4 authority changed")
    decode_active(actor)
    require(int(prop(actor, "ScratchRecordDraftRevisionNumberV1")) == 2, "recovered draft revision changed")
    require(bool(prop(actor, "ScratchRecordHasPublishedRevisionV1")), "recovered published flag missing")
    require(int(prop(actor, "ScratchRecordPublishedRevisionNumberV1")) == 2, "recovered published revision changed")
    require(int(document_prop(prop(actor, "ScratchRecordPublishedDocumentV1"), "RevisionNumber")) == 2, "recovered snapshot revision changed")
    require(abs(float(document_prop(prop(actor, "ScratchRecordPublishedDocumentV1"), "DurationSeconds"))) < 0.001, "recovered snapshot payload changed")
    emit("RECOVERY", "PASS")

    set_prop(actor, "RequestRequesterAccountIdV1", OWNER)
    set_prop(actor, "RequestFlypathIdV1", FLYPATH_ID)
    actor.call_method("LoadDraftV1")
    require(prop(actor, "ResultCodeV1") == "Success", "owner load failed after restart")
    require(int(prop(actor, "ResultCurrentRevisionV1")) == 2, "owner load revision changed")
    require(int(document_prop(prop(actor, "ResultDraftDocumentV1"), "RevisionNumber")) == 2, "owner typed draft changed")
    emit("OWNER_LOAD", "PASS")

    set_prop(actor, "RequestOffsetV1", 0)
    set_prop(actor, "RequestLimitV1", 20)
    actor.call_method("ListMineV1")
    require(prop(actor, "ResultCodeV1") == "Success", "owner list failed after restart")
    metadata = [json.loads(value) for value in prop(actor, "ResultMetadataEnvelopesV1")]
    require(len(metadata) == 1, "metadata count changed")
    require(metadata[0]["visibility"] == "public", "metadata visibility changed")
    require(metadata[0]["draftRevisionNumber"] == 2, "metadata draft revision changed")
    require(metadata[0]["hasPublishedRevision"] is True, "metadata published flag changed")
    require(metadata[0]["publishedRevisionNumber"] == 2, "metadata published revision changed")
    emit("METADATA", "PASS")

    stage_document(actor, 44.0, "restart-draft-v3")
    set_prop(actor, "RequestRequesterAccountIdV1", OWNER)
    set_prop(actor, "RequestFlypathIdV1", FLYPATH_ID)
    set_prop(actor, "RequestExpectedRevisionV1", 2)
    set_prop(actor, "RequestNowUtcV1", "2026-08-12T00:16:00Z")
    actor.call_method("SaveDraftV1")
    require(prop(actor, "ResultCodeV1") == "Success", f"restart save failed: {prop(actor, 'ResultCodeV1')}|{prop(actor, 'ResultDetailV1')}")
    require(int(prop(actor, "ActiveGenerationV1")) == 5, "restart save generation changed")
    require(str(prop(actor, "ActiveSlotV1")) == "EDD_Repository_A", "restart save slot changed")
    decode_active(actor)
    require(int(prop(actor, "ScratchRecordDraftRevisionNumberV1")) == 3, "restart draft did not advance")
    require(abs(float(document_prop(prop(actor, "ScratchRecordDraftDocumentV1"), "DurationSeconds")) - 44.0) < 0.001, "restart draft payload changed")
    require(int(prop(actor, "ScratchRecordPublishedRevisionNumberV1")) == 2, "restart save changed published revision")
    require(int(document_prop(prop(actor, "ScratchRecordPublishedDocumentV1"), "RevisionNumber")) == 2, "restart save changed snapshot revision")
    require(abs(float(document_prop(prop(actor, "ScratchRecordPublishedDocumentV1"), "DurationSeconds"))) < 0.001, "restart save changed snapshot payload")
    require(physical("EDD_Repository_A")[0:2] == (5, True), "generation 5 commit changed")
    emit("RESUMED_SAVE", "PASS")

    set_prop(actor, "RequestExpectedRevisionV1", 3)
    set_prop(actor, "RequestNowUtcV1", "2026-08-12T00:17:00Z")
    actor.call_method("PublishDraftV1")
    require(prop(actor, "ResultCodeV1") == "Success", f"restart publish failed: {prop(actor, 'ResultCodeV1')}|{prop(actor, 'ResultDetailV1')}")
    require(int(prop(actor, "ActiveGenerationV1")) == 6, "restart publish generation changed")
    require(str(prop(actor, "ActiveSlotV1")) == "EDD_Repository_B", "restart publish slot changed")
    require(list(prop(actor, "ActiveUpdatedUtcV1")) == ["2026-08-12T00:17:00Z"], "restart publish timestamp changed")
    decode_active(actor)
    require(int(prop(actor, "ScratchRecordDraftRevisionNumberV1")) == 3, "restart publish advanced draft")
    require(int(prop(actor, "ScratchRecordPublishedRevisionNumberV1")) == 3, "restart publish revision changed")
    published = prop(actor, "ScratchRecordPublishedDocumentV1")
    require(int(document_prop(published, "RevisionNumber")) == 3, "restart publish snapshot revision changed")
    require(abs(float(document_prop(published, "DurationSeconds")) - 44.0) < 0.001, "restart publish snapshot payload changed")
    slot_b = physical("EDD_Repository_B")
    require(slot_b[0:2] == (6, True), "generation 6 commit changed")
    require(slot_b[2] == tuple(prop(actor, "ActiveRecordEnvelopesV1")), "generation 6 physical payload changed")
    emit("RESUMED_PUBLISH", "PASS")

    actor.call_method("LoadRepositoryV1")
    require(bool(prop(actor, "RepositoryLoadedV1")), "post-publish reload failed")
    require(int(prop(actor, "ActiveGenerationV1")) == 6, "post-publish reload generation changed")
    require(str(prop(actor, "ActiveSlotV1")) == "EDD_Repository_B", "post-publish reload slot changed")
    decode_active(actor)
    require(int(prop(actor, "ScratchRecordPublishedRevisionNumberV1")) == 3, "post-publish reload revision changed")
    require(abs(float(document_prop(prop(actor, "ScratchRecordPublishedDocumentV1"), "DurationSeconds")) - 44.0) < 0.001, "post-publish reload payload changed")
    emit("FINAL_RELOAD", "PASS")
    emit("RESULT", "PASS")
finally:
    if actor is not None:
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        if subsystem is not None:
            subsystem.destroy_actor(actor)
    cleanup()
    emit("CLEANUP", "PASS")
