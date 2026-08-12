"""Fresh-process recovery acceptance for metadata-only public discovery."""

from __future__ import annotations

import json
import unreal


PREFIX = "EDD_PUBLIC_LIST_RESTART"
CLASS_PATH = (
    "/Game/Mods/ExileDroneDirector/Server/Repository/"
    "BP_EDD_FlypathRepository.BP_EDD_FlypathRepository_C"
)
SLOTS = ("EDD_Repository_A", "EDD_Repository_B")
EXPECTED_KEYS = {
    "flypathId", "ownerDisplayName", "title", "visibility", "regionId",
    "updatedUtc", "draftRevisionNumber", "hasPublishedRevision",
    "publishedRevisionNumber",
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
        require(unreal.GameplayStatics.does_save_game_exist(slot, 0), f"missing slot: {slot}")
        storage = unreal.GameplayStatics.load_game_from_slot(slot, 0)
        require(storage is not None, f"load failed: {slot}")
        result.append((
            slot, int(prop(storage, "Generation")), bool(prop(storage, "Committed")),
            tuple(prop(storage, "RecordEnvelopes")), tuple(prop(storage, "TombstoneFlypathIds")),
        ))
    return tuple(result)


def cleanup():
    for slot in SLOTS:
        if unreal.GameplayStatics.does_save_game_exist(slot, 0):
            require(unreal.GameplayStatics.delete_game_in_slot(slot, 0), f"delete failed: {slot}")
        require(not unreal.GameplayStatics.does_save_game_exist(slot, 0), f"cleanup failed: {slot}")


actor = None
try:
    require(all(unreal.GameplayStatics.does_save_game_exist(slot, 0) for slot in SLOTS), "fixtures missing")
    repository_class = unreal.load_class(None, CLASS_PATH)
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = subsystem.spawn_actor_from_class(
        repository_class, unreal.Vector(0, 0, -100000), unreal.Rotator(), False
    )
    require(actor is not None, "spawn failed")
    actor.call_method("LoadRepositoryV1")
    require(bool(prop(actor, "RepositoryLoadedV1")), "recovery failed")
    require(int(prop(actor, "ActiveGenerationV1")) == 9, "generation changed")
    require(str(prop(actor, "ActiveSlotV1")) == "EDD_Repository_A", "slot changed")
    require(list(prop(actor, "ActiveVisibilitiesV1")).count("public") == 2, "visibility recovery changed")
    emit("RECOVERY", "PASS")

    before_authority, before_physical = authority(actor), physical()
    set_prop(actor, "RequestOffsetV1", 0)
    set_prop(actor, "RequestLimitV1", 100)
    actor.call_method("ListPublicV1")
    require(prop(actor, "ResultCodeV1") == "Success", "query failed")
    require(authority(actor) == before_authority, "query mutated recovered authority")
    require(physical() == before_physical, "query wrote recovered SaveGame")
    values = [json.loads(item) for item in prop(actor, "ResultMetadataEnvelopesV1")]
    require(
        [item["flypathId"] for item in values] == ["public-newest", "public-alpha"],
        "recovered discovery order changed",
    )
    require(int(prop(actor, "ResultTotalCountV1")) == 2, "recovered count changed")
    require(not bool(prop(actor, "ResultHasMoreV1")), "recovered hasMore changed")
    for value in values:
        require(set(value) == EXPECTED_KEYS, "metadata keys changed")
        require(value["visibility"] == "public", "private metadata leaked")
        require(value["hasPublishedRevision"] is True, "published history changed")
        require(value["publishedRevisionNumber"] == 1, "published revision changed")
    emit("PUBLIC_METADATA", "PASS")
    emit("READ_ONLY", "PASS")
    emit("RESULT", "PASS")
finally:
    if actor is not None:
        unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(actor)
    cleanup()
    emit("CLEANUP", "PASS")
