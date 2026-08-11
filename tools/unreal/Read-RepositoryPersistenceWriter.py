"""Verify the compiled writer fixture in a fresh process, then remove it."""

from __future__ import annotations

import unreal


PREFIX = "EDD_PERSISTENCE_WRITER_FRESH_READ"
SLOT = "EDD_Repository_PersistenceWriter_Automation"
USER = 0
EXPECTED = (
    1,
    42,
    True,
    "",
    ["writer-record-alpha", "writer-record-unicode-北風"],
    ["writer-deleted-flight"],
)


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}|{label}|{value}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(f"{PREFIX}|FAIL|{message}")


def prop(obj, name: str):
    snake = "".join(("_" + c.lower()) if c.isupper() else c for c in name).lstrip("_")
    errors = []
    for candidate in (name, unreal.Name(name), snake, unreal.Name(snake)):
        try:
            return obj.get_editor_property(candidate)
        except Exception as error:
            errors.append(f"{candidate}:{error}")
    raise RuntimeError(f"{PREFIX}|FAIL|could not read {name}: {'; '.join(errors)}")


try:
    require(unreal.GameplayStatics.does_save_game_exist(SLOT, USER), "writer fixture is absent")
    loaded = unreal.GameplayStatics.load_game_from_slot(SLOT, USER)
    require(loaded is not None, "writer fixture returned null")
    actual = (
        int(prop(loaded, "RepositorySchemaVersion")),
        int(prop(loaded, "Generation")),
        bool(prop(loaded, "Committed")),
        prop(loaded, "SnapshotHash"),
        list(prop(loaded, "RecordEnvelopes")),
        list(prop(loaded, "TombstoneFlypathIds")),
    )
    require(actual == EXPECTED, f"fresh-process payload mismatch: {actual!r}")
    emit("PHYSICAL_PAYLOAD_VERIFIED", actual)
    emit("RESULT", "PASS")
finally:
    if unreal.GameplayStatics.does_save_game_exist(SLOT, USER):
        require(
            unreal.GameplayStatics.delete_game_in_slot(SLOT, USER),
            "could not clean automation fixture",
        )
        emit("CLEANUP", "PASS")
