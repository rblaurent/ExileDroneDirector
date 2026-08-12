"""Fresh-process recovery and resumed-write acceptance for UnpublishV1.

Run only after ``Validate-RepositoryUnpublish.py`` leaves generation 6 in
slot B. The oracle proves private visibility and retained published history
survive a real process boundary, then proves resumed publish/unpublish writes,
physical reload, and cleanup.
"""

from __future__ import annotations

import json
import unreal


PREFIX = "EDD_UNPUBLISH_RESTART"
CLASS_PATH = (
    "/Game/Mods/ExileDroneDirector/Server/Repository/"
    "BP_EDD_FlypathRepository.BP_EDD_FlypathRepository_C"
)
SLOTS = ("EDD_Repository_A", "EDD_Repository_B")
FLYPATH_ID = "unpublish-runtime-a"
OWNER = "owner-a"
DOCUMENT_FIELDS = {
    "RevisionNumber": ("RevisionNumber", "revision_number", "RevisionNumber_5_951904BF45A63EADA84E4AB0386D19B4"),
    "DurationSeconds": ("DurationSeconds", "duration_seconds", "DurationSeconds_11_4517680840D3F6CC541E6BBC6AB10DF9"),
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
    require(all(unreal.GameplayStatics.does_save_game_exist(slot, 0) for slot in SLOTS), "unpublish fixtures missing")
    repository_class = unreal.load_class(None, CLASS_PATH)
    require(repository_class is not None, "repository generated class missing")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    require(subsystem is not None, "EditorActorSubsystem unavailable")
    actor = subsystem.spawn_actor_from_class(
        repository_class, unreal.Vector(0, 0, -100000), unreal.Rotator(), False
    )
    require(actor is not None, "could not spawn repository actor")
    actor.call_method("LoadRepositoryV1")

    require(bool(prop(actor, "RepositoryLoadedV1")), "repository did not recover")
    require(int(prop(actor, "ActiveGenerationV1")) == 6, "recovered generation changed")
    require(str(prop(actor, "ActiveSlotV1")) == "EDD_Repository_B", "recovered slot changed")
    require(list(prop(actor, "ActiveFlypathIdsV1")) == [FLYPATH_ID], "recovered ID changed")
    require(list(prop(actor, "ActiveOwnerAccountIdsV1")) == [OWNER], "recovered owner changed")
    require(list(prop(actor, "ActiveVisibilitiesV1")) == ["private"], "recovered visibility changed")
    require(list(prop(actor, "ActiveUpdatedUtcV1")) == ["2026-08-12T01:06:00Z"], "recovered timestamp changed")
    require(physical("EDD_Repository_B")[0:2] == (6, True), "generation 6 authority changed")
    decode_active(actor)
    require(int(prop(actor, "ScratchRecordDraftRevisionNumberV1")) == 2, "recovered draft revision changed")
    require(abs(float(document_prop(prop(actor, "ScratchRecordDraftDocumentV1"), "DurationSeconds")) - 22.0) < 0.001, "recovered draft payload changed")
    require(bool(prop(actor, "ScratchRecordHasPublishedRevisionV1")), "recovered published history missing")
    require(int(prop(actor, "ScratchRecordPublishedRevisionNumberV1")) == 2, "recovered published revision changed")
    require(abs(float(document_prop(prop(actor, "ScratchRecordPublishedDocumentV1"), "DurationSeconds")) - 22.0) < 0.001, "recovered published snapshot changed")
    emit("RECOVERY", "PASS")

    set_prop(actor, "RequestRequesterAccountIdV1", OWNER)
    set_prop(actor, "RequestFlypathIdV1", FLYPATH_ID)
    actor.call_method("LoadDraftV1")
    require(prop(actor, "ResultCodeV1") == "Success", "owner load failed after restart")
    require(int(prop(actor, "ResultCurrentRevisionV1")) == 2, "owner load revision changed")
    require(abs(float(document_prop(prop(actor, "ResultDraftDocumentV1"), "DurationSeconds")) - 22.0) < 0.001, "owner load payload changed")
    emit("OWNER_LOAD", "PASS")

    set_prop(actor, "RequestOffsetV1", 0)
    set_prop(actor, "RequestLimitV1", 20)
    actor.call_method("ListMineV1")
    require(prop(actor, "ResultCodeV1") == "Success", "owner list failed after restart")
    metadata = [json.loads(value) for value in prop(actor, "ResultMetadataEnvelopesV1")]
    require(len(metadata) == 1, "metadata count changed")
    require(metadata[0]["visibility"] == "private", "metadata visibility changed")
    require(metadata[0]["draftRevisionNumber"] == 2, "metadata draft revision changed")
    require(metadata[0]["hasPublishedRevision"] is True, "metadata lost published history")
    require(metadata[0]["publishedRevisionNumber"] == 2, "metadata published revision changed")
    emit("METADATA", "PASS")

    set_prop(actor, "RequestExpectedRevisionV1", 2)
    set_prop(actor, "RequestNowUtcV1", "2026-08-12T01:07:00Z")
    actor.call_method("PublishDraftV1")
    require(prop(actor, "ResultCodeV1") == "Success", f"restart publish failed: {prop(actor, 'ResultCodeV1')}|{prop(actor, 'ResultDetailV1')}")
    require((int(prop(actor, "ActiveGenerationV1")), str(prop(actor, "ActiveSlotV1"))) == (7, "EDD_Repository_A"), "restart publish authority changed")
    require(list(prop(actor, "ActiveVisibilitiesV1")) == ["public"], "restart publish stayed private")
    decode_active(actor)
    require(int(prop(actor, "ScratchRecordDraftRevisionNumberV1")) == 2, "restart publish advanced draft")
    require(int(prop(actor, "ScratchRecordPublishedRevisionNumberV1")) == 2, "restart publish revision changed")
    require(abs(float(document_prop(prop(actor, "ScratchRecordPublishedDocumentV1"), "DurationSeconds")) - 22.0) < 0.001, "restart publish snapshot changed")
    require(physical("EDD_Repository_A")[0:2] == (7, True), "generation 7 commit changed")
    emit("RESUMED_PUBLISH", "PASS")

    set_prop(actor, "RequestExpectedRevisionV1", 2)
    set_prop(actor, "RequestNowUtcV1", "2026-08-12T01:08:00Z")
    actor.call_method("UnpublishV1")
    require(prop(actor, "ResultCodeV1") == "Success", f"restart unpublish failed: {prop(actor, 'ResultCodeV1')}|{prop(actor, 'ResultDetailV1')}")
    require((int(prop(actor, "ActiveGenerationV1")), str(prop(actor, "ActiveSlotV1"))) == (8, "EDD_Repository_B"), "restart unpublish authority changed")
    require(list(prop(actor, "ActiveVisibilitiesV1")) == ["private"], "restart unpublish stayed public")
    decode_active(actor)
    require(int(prop(actor, "ScratchRecordDraftRevisionNumberV1")) == 2, "restart unpublish advanced draft")
    require(int(prop(actor, "ScratchRecordPublishedRevisionNumberV1")) == 2, "restart unpublish erased history")
    require(abs(float(document_prop(prop(actor, "ScratchRecordPublishedDocumentV1"), "DurationSeconds")) - 22.0) < 0.001, "restart unpublish snapshot changed")
    slot_b = physical("EDD_Repository_B")
    require(slot_b[0:2] == (8, True), "generation 8 commit changed")
    require(slot_b[2] == tuple(prop(actor, "ActiveRecordEnvelopesV1")), "generation 8 physical payload changed")
    emit("RESUMED_UNPUBLISH", "PASS")

    actor.call_method("LoadRepositoryV1")
    require(bool(prop(actor, "RepositoryLoadedV1")), "final physical reload failed")
    require((int(prop(actor, "ActiveGenerationV1")), str(prop(actor, "ActiveSlotV1"))) == (8, "EDD_Repository_B"), "final reload authority changed")
    decode_active(actor)
    require(prop(actor, "ScratchRecordVisibilityV1") == "private", "final reload visibility changed")
    require(int(prop(actor, "ScratchRecordPublishedRevisionNumberV1")) == 2, "final reload history changed")
    emit("FINAL_RELOAD", "PASS")
    emit("RESULT", "PASS")
finally:
    if actor is not None:
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        if subsystem is not None:
            subsystem.destroy_actor(actor)
    cleanup()
    emit("CLEANUP", "PASS")
