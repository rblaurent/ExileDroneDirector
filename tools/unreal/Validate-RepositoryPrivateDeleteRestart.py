"""Fresh-process recovery and second-delete acceptance for DeleteFlypathV1.

Run after ``Validate-RepositoryPrivateDelete.py`` has committed generation 3
with fixture A tombstoned and fixture B surviving, and after the interactive
editor has exited cleanly.  This proves cold A/B recovery, deletion semantics
after restart, the second alternating-slot commit, tombstone accumulation, and
final read boundaries before cleaning both acceptance slots.
"""

from __future__ import annotations

import unreal


PREFIX = "EDD_PRIVATE_DELETE_RESTART"
CLASS_PATH = (
    "/Game/Mods/ExileDroneDirector/Server/Repository/"
    "BP_EDD_FlypathRepository.BP_EDD_FlypathRepository_C"
)
SLOTS = ("EDD_Repository_A", "EDD_Repository_B")
DOCUMENT_REVISION_FIELDS = (
    "RevisionNumber",
    "revision_number",
    "RevisionNumber_5_951904BF45A63EADA84E4AB0386D19B4",
)


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


def document_revision(document) -> int:
    errors = []
    for candidate in DOCUMENT_REVISION_FIELDS:
        try:
            return int(document.get_editor_property(candidate))
        except Exception as error:
            errors.append(f"{candidate}:{error}")
    raise RuntimeError(f"could not read document revision: {'; '.join(errors)}")


def cleanup() -> None:
    for slot in SLOTS:
        if unreal.GameplayStatics.does_save_game_exist(slot, 0):
            require(unreal.GameplayStatics.delete_game_in_slot(slot, 0), f"could not delete {slot}")
        require(not unreal.GameplayStatics.does_save_game_exist(slot, 0), f"slot survived cleanup: {slot}")


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


actor = None
try:
    require(all(unreal.GameplayStatics.does_save_game_exist(slot, 0) for slot in SLOTS), "delete fixtures missing")
    repository_class = unreal.load_class(None, CLASS_PATH)
    require(repository_class is not None, "repository generated class missing")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    require(subsystem is not None, "EditorActorSubsystem unavailable")
    actor = subsystem.spawn_actor_from_class(repository_class, unreal.Vector(0, 0, -100000), unreal.Rotator(), False)
    require(actor is not None, "could not spawn repository actor")
    actor.call_method("LoadRepositoryV1")

    require(bool(prop(actor, "RepositoryLoadedV1")), "repository did not recover")
    require(int(prop(actor, "ActiveGenerationV1")) == 3, "recovered generation changed")
    require(str(prop(actor, "ActiveSlotV1")) == "EDD_Repository_A", "recovered slot changed")
    require(list(prop(actor, "ActiveFlypathIdsV1")) == ["delete-runtime-b"], "recovered ID set changed")
    require(list(prop(actor, "ActiveOwnerAccountIdsV1")) == ["owner-a"], "recovered owner changed")
    require(list(prop(actor, "ActiveVisibilitiesV1")) == ["private"], "recovered privacy changed")
    require(list(prop(actor, "ActiveUpdatedUtcV1")) == ["2026-08-11T20:01:00Z"], "recovered timestamp changed")
    require(len(list(prop(actor, "ActiveRecordEnvelopesV1"))) == 1, "recovered record count changed")
    require(list(prop(actor, "ActiveTombstoneFlypathIdsV1")) == ["delete-runtime-a"], "recovered tombstone changed")
    require(physical("EDD_Repository_A")[0:2] == (3, True), "generation 3 physical authority changed")
    emit("RECOVERY", "PASS")

    set_prop(actor, "RequestRequesterAccountIdV1", "owner-a")
    set_prop(actor, "RequestFlypathIdV1", "delete-runtime-a")
    actor.call_method("LoadDraftV1")
    require(prop(actor, "ResultCodeV1") == "NotFound", "deleted fixture resurrected after restart")
    require(not bool(prop(actor, "ResultHasCurrentRevisionV1")), "deleted fixture leaked revision")
    require(prop(actor, "ResultRecordEnvelopeV1") == "", "deleted fixture leaked envelope")
    require(document_revision(prop(actor, "ResultDraftDocumentV1")) == 0, "deleted fixture leaked draft")

    set_prop(actor, "RequestFlypathIdV1", "delete-runtime-b")
    actor.call_method("LoadDraftV1")
    require(prop(actor, "ResultCodeV1") == "Success", "survivor was not loadable after restart")
    require(bool(prop(actor, "ResultHasCurrentRevisionV1")), "survivor omitted revision")
    require(int(prop(actor, "ResultCurrentRevisionV1")) == 1, "survivor revision changed")
    require(document_revision(prop(actor, "ResultDraftDocumentV1")) == 1, "survivor typed revision changed")

    set_prop(actor, "RequestOffsetV1", 0)
    set_prop(actor, "RequestLimitV1", 20)
    actor.call_method("ListMineV1")
    require(prop(actor, "ResultCodeV1") == "Success", "fresh-process list failed")
    require(int(prop(actor, "ResultTotalCountV1")) == 1, "fresh-process list count changed")
    require(len(list(prop(actor, "ResultMetadataEnvelopesV1"))) == 1, "fresh-process metadata count changed")
    emit("READ_BOUNDARIES", "PASS")

    set_prop(actor, "RequestRequesterAccountIdV1", "owner-a")
    set_prop(actor, "RequestFlypathIdV1", "delete-runtime-b")
    set_prop(actor, "RequestExpectedRevisionV1", 1)
    actor.call_method("DeleteFlypathV1")
    require(prop(actor, "ResultCodeV1") == "Success", f"second delete failed: {prop(actor, 'ResultCodeV1')}|{prop(actor, 'ResultDetailV1')}")
    require(int(prop(actor, "ActiveGenerationV1")) == 4, "second delete generation changed")
    require(str(prop(actor, "ActiveSlotV1")) == "EDD_Repository_B", "second delete slot changed")
    require(list(prop(actor, "ActiveRecordEnvelopesV1")) == [], "second delete left a record")
    require(list(prop(actor, "ActiveFlypathIdsV1")) == [], "second delete left an ID")
    require(list(prop(actor, "ActiveOwnerAccountIdsV1")) == [], "second delete left an owner")
    require(list(prop(actor, "ActiveVisibilitiesV1")) == [], "second delete left visibility")
    require(list(prop(actor, "ActiveUpdatedUtcV1")) == [], "second delete left timestamp")
    require(
        list(prop(actor, "ActiveTombstoneFlypathIdsV1")) == ["delete-runtime-a", "delete-runtime-b"],
        "second tombstone order changed",
    )
    slot_b = physical("EDD_Repository_B")
    require(slot_b[0:2] == (4, True), "second delete physical generation/commit changed")
    require(slot_b[2] == (), "second delete physical records changed")
    require(slot_b[3] == ("delete-runtime-a", "delete-runtime-b"), "second delete physical tombstones changed")
    emit("SECOND_DELETE_COMMIT", "PASS")

    actor.call_method("LoadRepositoryV1")
    require(bool(prop(actor, "RepositoryLoadedV1")), "post-delete reload failed")
    require(int(prop(actor, "ActiveGenerationV1")) == 4, "post-delete reload generation changed")
    require(str(prop(actor, "ActiveSlotV1")) == "EDD_Repository_B", "post-delete reload slot changed")
    require(list(prop(actor, "ActiveRecordEnvelopesV1")) == [], "post-delete reload resurrected records")
    require(
        list(prop(actor, "ActiveTombstoneFlypathIdsV1")) == ["delete-runtime-a", "delete-runtime-b"],
        "post-delete reload tombstones changed",
    )
    for flypath_id in ("delete-runtime-a", "delete-runtime-b"):
        set_prop(actor, "RequestRequesterAccountIdV1", "owner-a")
        set_prop(actor, "RequestFlypathIdV1", flypath_id)
        actor.call_method("LoadDraftV1")
        require(prop(actor, "ResultCodeV1") == "NotFound", f"{flypath_id} resurrected after reload")
    set_prop(actor, "RequestOffsetV1", 0)
    set_prop(actor, "RequestLimitV1", 20)
    actor.call_method("ListMineV1")
    require(prop(actor, "ResultCodeV1") == "Success", "empty post-delete list failed")
    require(int(prop(actor, "ResultTotalCountV1")) == 0, "empty post-delete count changed")
    require(list(prop(actor, "ResultMetadataEnvelopesV1")) == [], "empty post-delete metadata changed")
    emit("FINAL_RELOAD", "PASS")
    emit("RESULT", "PASS")
finally:
    if actor is not None:
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        if subsystem is not None:
            subsystem.destroy_actor(actor)
    cleanup()
    emit("CLEANUP", "PASS")
