"""Fresh-process SaveGame acceptance for owner-filtered private listing.

Run after ``Validate-RepositoryPrivateCreate.py`` has committed its canonical
two-record fixture and after the interactive editor has exited cleanly.  This
proves that ``ListMineV1`` consumes recovered A/B SaveGame state, preserves the
owner boundary, returns metadata only in deterministic order, performs no
writes, and cleans both acceptance slots.
"""

from __future__ import annotations

import json

import unreal


PREFIX = "EDD_PRIVATE_LIST_RESTART"
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


def cleanup() -> None:
    for slot in SLOTS:
        if unreal.GameplayStatics.does_save_game_exist(slot, 0):
            require(unreal.GameplayStatics.delete_game_in_slot(slot, 0), f"could not delete {slot}")
        require(not unreal.GameplayStatics.does_save_game_exist(slot, 0), f"slot survived cleanup: {slot}")


def physical_snapshot():
    values = []
    for slot in SLOTS:
        require(unreal.GameplayStatics.does_save_game_exist(slot, 0), f"fixture missing: {slot}")
        storage = unreal.GameplayStatics.load_game_from_slot(slot, 0)
        require(storage is not None, f"could not load {slot}")
        values.append(
            (
                slot,
                int(prop(storage, "Generation")),
                bool(prop(storage, "Committed")),
                tuple(prop(storage, "RecordEnvelopes")),
                tuple(prop(storage, "TombstoneFlypathIds")),
            )
        )
    return tuple(values)


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


def invoke_list(actor, owner: str):
    before_authority = authority_snapshot(actor)
    before_physical = physical_snapshot()
    set_prop(actor, "RequestRequesterAccountIdV1", owner)
    set_prop(actor, "RequestOffsetV1", 0)
    set_prop(actor, "RequestLimitV1", 100)
    actor.call_method("ListMineV1")
    require(authority_snapshot(actor) == before_authority, "list mutated recovered authority")
    require(physical_snapshot() == before_physical, "list wrote recovered SaveGame state")
    return [json.loads(value) for value in prop(actor, "ResultMetadataEnvelopesV1")]


actor = None
try:
    require(all(unreal.GameplayStatics.does_save_game_exist(slot, 0) for slot in SLOTS), "creation fixtures missing")
    repository_class = unreal.load_class(None, CLASS_PATH)
    require(repository_class is not None, "repository generated class missing")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    require(subsystem is not None, "EditorActorSubsystem unavailable")
    actor = subsystem.spawn_actor_from_class(
        repository_class,
        unreal.Vector(0, 0, -100000),
        unreal.Rotator(),
        False,
    )
    require(actor is not None, "could not spawn repository actor")
    actor.call_method("LoadRepositoryV1")

    require(bool(prop(actor, "RepositoryLoadedV1")), "repository did not recover")
    require(int(prop(actor, "ActiveGenerationV1")) == 2, "recovered generation changed")
    require(str(prop(actor, "ActiveSlotV1")) == "EDD_Repository_B", "recovered slot changed")
    require(
        list(prop(actor, "ActiveFlypathIdsV1")) == ["create-runtime-a", "create-runtime-b"],
        "recovered ID order changed",
    )
    require(list(prop(actor, "ActiveOwnerAccountIdsV1")) == ["owner-a", "owner-a"], "owners changed")
    require(list(prop(actor, "ActiveVisibilitiesV1")) == ["private", "private"], "privacy changed")
    emit("RECOVERY", "PASS")

    values = invoke_list(actor, "owner-a")
    require(prop(actor, "ResultCodeV1") == "Success", "owner list failed")
    require(int(prop(actor, "ResultTotalCountV1")) == 2, "owner count changed")
    require(int(prop(actor, "ResultPageOffsetV1")) == 0, "page offset changed")
    require(not bool(prop(actor, "ResultHasMoreV1")), "unexpected additional page")
    require(
        [value["flypathId"] for value in values] == ["create-runtime-b", "create-runtime-a"],
        "fresh-process ordering changed",
    )
    require([value["title"] for value in values] == ["Runtime Beta", "Runtime Alpha"], "titles changed")
    require(
        [value["updatedUtc"] for value in values]
        == ["2026-08-11T18:21:00Z", "2026-08-11T18:20:00Z"],
        "timestamps changed",
    )
    for value in values:
        require(set(value) == METADATA_KEYS, f"metadata keys changed: {sorted(value)}")
        require(value["ownerDisplayName"] == "Owner A", "display owner changed")
        require(value["visibility"] == "private", "private default changed")
        require(value["regionId"] == "ExiledLands", "region changed")
        require(value["draftRevisionNumber"] == 1, "revision changed")
        require(value["hasPublishedRevision"] is False, "publish state changed")
        require(value["publishedRevisionNumber"] == 0, "published revision changed")
        require("ownerAccountId" not in value, "owner account leaked")
        require("description" not in value and "draft" not in value, "record payload leaked")
    emit("OWNER_METADATA", "PASS")

    values = invoke_list(actor, "owner-b")
    require(prop(actor, "ResultCodeV1") == "Success", "foreign empty list failed")
    require(values == [], "foreign owner received metadata")
    require(int(prop(actor, "ResultTotalCountV1")) == 0, "foreign owner received count")
    require(not bool(prop(actor, "ResultHasMoreV1")), "foreign owner received hasMore")
    emit("OWNER_ISOLATION", "PASS")
    emit("READ_ONLY", "PASS")
    emit("RESULT", "PASS")
finally:
    if actor is not None:
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        if subsystem is not None:
            subsystem.destroy_actor(actor)
    cleanup()
    emit("CLEANUP", "PASS")
