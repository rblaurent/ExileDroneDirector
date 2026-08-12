"""Fresh-process recovery proof for immutable published playback fetch."""

from __future__ import annotations

import unreal


PREFIX = "EDD_PUBLISHED_FETCH_RESTART"
CLASS_PATH = "/Game/Mods/ExileDroneDirector/Server/Repository/BP_EDD_FlypathRepository.BP_EDD_FlypathRepository_C"
SLOTS = ("EDD_Repository_A", "EDD_Repository_B")
FLYPATH_ID = "published-fetch-runtime"
DOCUMENT_FIELDS = {
    "RevisionNumber": ("RevisionNumber", "revision_number", "RevisionNumber_5_951904BF45A63EADA84E4AB0386D19B4"),
    "DurationSeconds": ("DurationSeconds", "duration_seconds", "DurationSeconds_11_4517680840D3F6CC541E6BBC6AB10DF9"),
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
def authority(actor):
    return (int(prop(actor, "ActiveGenerationV1")), str(prop(actor, "ActiveSlotV1")), tuple(prop(actor, "ActiveRecordEnvelopesV1")), tuple(prop(actor, "ActiveVisibilitiesV1")))
def physical():
    rows = []
    for slot in SLOTS:
        require(unreal.GameplayStatics.does_save_game_exist(slot, 0), f"missing slot {slot}")
        storage = unreal.GameplayStatics.load_game_from_slot(slot, 0)
        rows.append((slot, int(prop(storage, "Generation")), bool(prop(storage, "Committed")), tuple(prop(storage, "RecordEnvelopes")), tuple(prop(storage, "TombstoneFlypathIds"))))
    return tuple(rows)
def cleanup():
    for slot in SLOTS:
        if unreal.GameplayStatics.does_save_game_exist(slot, 0):
            require(unreal.GameplayStatics.delete_game_in_slot(slot, 0), f"delete failed {slot}")
        require(not unreal.GameplayStatics.does_save_game_exist(slot, 0), f"cleanup failed {slot}")


actor = None
try:
    repository_class = unreal.load_class(None, CLASS_PATH)
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = subsystem.spawn_actor_from_class(repository_class, unreal.Vector(0, 0, -100000), unreal.Rotator(), False)
    require(actor is not None, "spawn failed")
    actor.call_method("LoadRepositoryV1")
    require(bool(prop(actor, "RepositoryLoadedV1")), "recovery failed")
    require(int(prop(actor, "ActiveGenerationV1")) == 3, "generation changed")
    require(str(prop(actor, "ActiveSlotV1")) == "EDD_Repository_A", "slot changed")
    emit("RECOVERY", "PASS")

    before_authority, before_physical = authority(actor), physical()
    set_prop(actor, "RequestFlypathIdV1", FLYPATH_ID)
    set_prop(actor, "RequestExpectedRevisionV1", 1)
    actor.call_method("FetchPublishedRevisionV1")
    require(prop(actor, "ResultCodeV1") == "Success", "recovered exact fetch failed")
    require(int(prop(actor, "ResultCurrentRevisionV1")) == 1, "recovered published revision changed")
    document = prop(actor, "ResultPublishedDocumentV1")
    require(int(doc_prop(document, "RevisionNumber")) == 1, "recovered typed revision changed")
    require(abs(float(doc_prop(document, "DurationSeconds")) - 12.5) < 0.001, "recovered immutable duration changed")
    require(authority(actor) == before_authority, "fetch mutated recovered authority")
    require(physical() == before_physical, "fetch mutated recovered SaveGame")
    emit("IMMUTABLE_PUBLIC", "PASS")
    emit("READ_ONLY", "PASS")

    set_prop(actor, "RequestExpectedRevisionV1", 2)
    actor.call_method("FetchPublishedRevisionV1")
    require((prop(actor, "ResultCodeV1"), prop(actor, "ResultDetailV1")) == ("NotFound", "PublishedRevisionNotFound"), "recovered wrong revision changed")
    require(not bool(prop(actor, "ResultHasCurrentRevisionV1")), "denial leaked revision")
    require(int(doc_prop(prop(actor, "ResultPublishedDocumentV1"), "RevisionNumber")) == 0, "denial leaked prior payload")
    require(authority(actor) == before_authority and physical() == before_physical, "denial mutated state")
    emit("STALE_PAYLOAD_RESET", "PASS")
    emit("RESULT", "PASS")
finally:
    if actor is not None:
        unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(actor)
    cleanup()
    emit("CLEANUP", "PASS")
