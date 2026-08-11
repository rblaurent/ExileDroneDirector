"""Fresh-process recovery acceptance for CreatePrivateFlypathV1."""

from __future__ import annotations

import unreal


PREFIX = "EDD_PRIVATE_CREATE_RESTART"
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


actor = None
try:
    require(all(unreal.GameplayStatics.does_save_game_exist(slot, 0) for slot in SLOTS), "creation fixtures missing before restart")
    repository_class = unreal.load_class(None, CLASS_PATH)
    require(repository_class is not None, "repository generated class missing")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    require(subsystem is not None, "EditorActorSubsystem unavailable")
    actor = subsystem.spawn_actor_from_class(repository_class, unreal.Vector(0, 0, -100000), unreal.Rotator(), False)
    require(actor is not None, "could not spawn repository actor")
    actor.call_method("LoadRepositoryV1")

    require(bool(prop(actor, "RepositoryLoadedV1")), "repository did not load")
    require(int(prop(actor, "ActiveGenerationV1")) == 2, "recovered generation changed")
    require(str(prop(actor, "ActiveSlotV1")) == "EDD_Repository_B", "recovered slot changed")
    require(list(prop(actor, "ActiveFlypathIdsV1")) == ["create-runtime-a", "create-runtime-b"], "recovered ID order changed")
    require(list(prop(actor, "ActiveOwnerAccountIdsV1")) == ["owner-a", "owner-a"], "recovered owners changed")
    require(list(prop(actor, "ActiveVisibilitiesV1")) == ["private", "private"], "private defaults did not survive restart")
    require(
        list(prop(actor, "ActiveUpdatedUtcV1"))
        == ["2026-08-11T18:20:00Z", "2026-08-11T18:21:00Z"],
        "recovered timestamps changed",
    )
    require(len(list(prop(actor, "ActiveRecordEnvelopesV1"))) == 2, "recovered record count changed")
    emit("RECOVERY", "PASS")

    for flypath_id in ("create-runtime-a", "create-runtime-b"):
        set_prop(actor, "RequestRequesterAccountIdV1", "owner-a")
        set_prop(actor, "RequestFlypathIdV1", flypath_id)
        actor.call_method("LoadDraftV1")
        require(prop(actor, "ResultCodeV1") == "Success", f"owner could not load {flypath_id}")
        require(bool(prop(actor, "ResultHasCurrentRevisionV1")), f"{flypath_id} omitted revision")
        require(int(prop(actor, "ResultCurrentRevisionV1")) == 1, f"{flypath_id} revision changed")
        require(document_revision(prop(actor, "ResultDraftDocumentV1")) == 1, f"{flypath_id} typed revision changed")
        require(bool(prop(actor, "ResultRecordEnvelopeV1")), f"{flypath_id} envelope missing")
    emit("OWNER_RELOAD", "PASS")

    set_prop(actor, "RequestRequesterAccountIdV1", "owner-b")
    set_prop(actor, "RequestFlypathIdV1", "create-runtime-a")
    actor.call_method("LoadDraftV1")
    require(prop(actor, "ResultCodeV1") == "Forbidden", "wrong owner crossed restart boundary")
    require(not prop(actor, "ResultHasCurrentRevisionV1"), "wrong owner received revision")
    require(prop(actor, "ResultRecordEnvelopeV1") == "", "wrong owner received envelope")
    require(document_revision(prop(actor, "ResultDraftDocumentV1")) == 0, "wrong owner received typed draft")
    emit("OWNER_ISOLATION", "PASS")
    emit("RESULT", "PASS")
finally:
    if actor is not None:
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        if subsystem is not None:
            subsystem.destroy_actor(actor)
    cleanup()
    emit("CLEANUP", "PASS")
