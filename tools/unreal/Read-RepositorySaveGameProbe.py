"""Read the repository fixture in a fresh editor process and clean it up."""

from __future__ import annotations

import unreal


PREFIX = "EDD_REPOSITORY_SAVEGAME_READ"
SLOT = "EDD_Repository_Automation"
USER = 0
RECORDS = ["{\"flypathId\":\"alpha\"}", "Unicode flight — 北風"]
TOMBSTONES = ["deleted-flight"]


def emit(label, value):
    unreal.log(f"{PREFIX}:{label}:{value}")


def prop(obj, name):
    snake = "".join(("_" + c.lower()) if c.isupper() else c for c in name).lstrip("_")
    last_error = None
    for candidate in (name, unreal.Name(name), snake, unreal.Name(snake)):
        try:
            return obj.get_editor_property(candidate)
        except Exception as error:
            last_error = error
    raise RuntimeError(f"Could not read {name}: {last_error}")


if not unreal.GameplayStatics.does_save_game_exist(SLOT, USER):
    raise RuntimeError("Writer slot does not exist in fresh process")
loaded = unreal.GameplayStatics.load_game_from_slot(SLOT, USER)
if loaded is None:
    raise RuntimeError("LoadGameFromSlot returned null in fresh process")
actual = (
    prop(loaded, "RepositorySchemaVersion"),
    prop(loaded, "Generation"),
    prop(loaded, "Committed"),
    prop(loaded, "SnapshotHash"),
    list(prop(loaded, "RecordEnvelopes")),
    list(prop(loaded, "TombstoneFlypathIds")),
)
expected = (1, 17, True, "a" * 64, RECORDS, TOMBSTONES)
if actual != expected:
    raise RuntimeError(f"Fresh-process round trip mismatch: {actual!r}")
emit("FRESH_PROCESS_VERIFIED", actual)
if not unreal.GameplayStatics.delete_game_in_slot(SLOT, USER):
    raise RuntimeError("Could not clean up automation slot")
if unreal.GameplayStatics.does_save_game_exist(SLOT, USER):
    raise RuntimeError("Automation slot still exists after cleanup")
emit("CLEANUP_VERIFIED", True)
emit("COMPLETE", True)
