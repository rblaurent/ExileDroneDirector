"""Write and immediately verify a deterministic repository SaveGame fixture."""

from __future__ import annotations

import unreal


PREFIX = "EDD_REPOSITORY_SAVEGAME_WRITE"
ASSET_PATH = "/Game/Mods/ExileDroneDirector/Server/Persistence/SG_EDD_RepositoryStorage"
SLOT = "EDD_Repository_Automation"
USER = 0
RECORDS = ["{\"flypathId\":\"alpha\"}", "Unicode flight — 北風"]
TOMBSTONES = ["deleted-flight"]


def emit(label, value):
    unreal.log(f"{PREFIX}:{label}:{value}")


def candidates(name):
    snake = "".join(("_" + c.lower()) if c.isupper() else c for c in name).lstrip("_")
    return (name, unreal.Name(name), snake, unreal.Name(snake))


def prop(obj, name):
    last_error = None
    for candidate in candidates(name):
        try:
            return obj.get_editor_property(candidate)
        except Exception as error:
            last_error = error
    raise RuntimeError(f"Could not read {name}: {last_error}")


def set_prop(obj, name, value):
    last_error = None
    for candidate in candidates(name):
        try:
            obj.set_editor_property(candidate, value)
            return
        except Exception as error:
            last_error = error
    raise RuntimeError(f"Could not set {name}: {last_error}")


generated_class = unreal.EditorAssetLibrary.load_blueprint_class(ASSET_PATH)
if generated_class is None:
    raise RuntimeError(f"Missing generated class: {ASSET_PATH}")
if unreal.GameplayStatics.does_save_game_exist(SLOT, USER):
    if not unreal.GameplayStatics.delete_game_in_slot(SLOT, USER):
        raise RuntimeError("Could not delete prior automation slot")

save = unreal.GameplayStatics.create_save_game_object(generated_class)
set_prop(save, "RepositorySchemaVersion", 1)
set_prop(save, "Generation", 17)
set_prop(save, "Committed", True)
set_prop(save, "SnapshotHash", "a" * 64)
set_prop(save, "RecordEnvelopes", RECORDS)
set_prop(save, "TombstoneFlypathIds", TOMBSTONES)
if not unreal.GameplayStatics.save_game_to_slot(save, SLOT, USER):
    raise RuntimeError("SaveGameToSlot returned false")

loaded = unreal.GameplayStatics.load_game_from_slot(SLOT, USER)
if loaded is None:
    raise RuntimeError("LoadGameFromSlot returned null in writer")
expected = (1, 17, True, "a" * 64, RECORDS, TOMBSTONES)
actual = (
    prop(loaded, "RepositorySchemaVersion"),
    prop(loaded, "Generation"),
    prop(loaded, "Committed"),
    prop(loaded, "SnapshotHash"),
    list(prop(loaded, "RecordEnvelopes")),
    list(prop(loaded, "TombstoneFlypathIds")),
)
if actual != expected:
    raise RuntimeError(f"Same-process round trip mismatch: {actual!r}")
emit("SAME_PROCESS_VERIFIED", actual)
emit("COMPLETE", True)
