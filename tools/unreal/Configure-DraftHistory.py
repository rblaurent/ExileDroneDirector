"""Create and verify the bounded client-local draft-history state seam.

Graph bodies are installed separately from deterministic Blueprint clipboard
artifacts.  Full document snapshots are intentional for this first history
milestone: they keep stable IDs, segment edits, metadata, selection, the next-ID
counter, legacy authoring channels, and the visible preview in one transaction.
"""

from __future__ import annotations

import unreal


PREFIX = "EDD_DRAFT_HISTORY"
CLIENT_PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector"
DOCUMENT_PATH = "/Game/Mods/ExileDroneDirector/Data/Structs/ST_EDD_FlypathDocument"
DOCUMENT_ARRAYS = (
    "UndoDocumentsV1",
    "RedoDocumentsV1",
)
INT_ARRAYS = (
    "UndoSelectionsV1",
    "UndoNextWaypointIdsV1",
    "RedoSelectionsV1",
    "RedoNextWaypointIdsV1",
)
SCALAR_DEFAULTS = {
    "HistoryLimitV1": 64,
    "HistoryRestoreSelectionV1": -1,
    "HistoryRestoreNextWaypointIdV1": 1,
}
STAGING_DOCUMENT = "HistoryRestoreDocumentV1"
FUNCTIONS = (
    "PushCurrentToUndoV1",
    "PushCurrentToRedoV1",
    "RecordUndoSnapshotV1",
    "ApplyHistorySnapshotV1",
    "UndoDraftV1",
    "RedoDraftV1",
)


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}:{label}:{value}")


def require_asset(path: str):
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if asset is None:
        raise RuntimeError(f"Required asset could not be loaded: {path}")
    return asset


def require_class(path: str):
    value = unreal.EditorAssetLibrary.load_blueprint_class(path)
    if value is None:
        raise RuntimeError(f"Required Blueprint class could not be loaded: {path}")
    return value


def property_candidates(variable_name: str) -> tuple[object, ...]:
    snake = "".join(
        ("_" + character.lower()) if character.isupper() else character
        for character in variable_name
    ).lstrip("_")
    return variable_name, unreal.Name(variable_name), snake, unreal.Name(snake)


def generated_value(variable_name: str):
    defaults = unreal.get_default_object(require_class(CLIENT_PATH))
    last_error = None
    for candidate in property_candidates(variable_name):
        try:
            return defaults.get_editor_property(candidate)
        except Exception as error:
            last_error = error
    raise RuntimeError(f"Generated class is missing {variable_name}: {last_error}")


def has_variable(variable_name: str) -> bool:
    try:
        generated_value(variable_name)
        return True
    except RuntimeError:
        return False


def ensure_variable(blueprint, variable_name: str, pin_type) -> None:
    if has_variable(variable_name):
        emit("VARIABLE_ALREADY_PRESENT", variable_name)
        return
    if not unreal.BlueprintEditorLibrary.add_member_variable(blueprint, variable_name, pin_type):
        raise RuntimeError(f"Failed to add {variable_name}")
    emit("VARIABLE_CREATED", variable_name)
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)


def set_default(variable_name: str, expected: int) -> None:
    defaults = unreal.get_default_object(require_class(CLIENT_PATH))
    last_error = None
    for candidate in property_candidates(variable_name):
        try:
            defaults.set_editor_property(candidate, expected)
            actual = int(defaults.get_editor_property(candidate))
            if actual != expected:
                raise RuntimeError(f"expected {expected}, received {actual}")
            emit("DEFAULT_VERIFIED", f"{variable_name}|{actual}")
            return
        except Exception as error:
            last_error = error
    raise RuntimeError(f"Could not set {variable_name}: {last_error}")


def ensure_function(blueprint, function_name: str) -> None:
    graph = unreal.BlueprintEditorLibrary.find_graph(blueprint, unreal.Name(function_name))
    if graph is not None:
        emit("FUNCTION_ALREADY_PRESENT", function_name)
        return
    graph = unreal.BlueprintEditorLibrary.add_function_graph(blueprint, function_name)
    if graph is None:
        raise RuntimeError(f"Failed to add {function_name}")
    emit("FUNCTION_CREATED", function_name)


client = require_asset(CLIENT_PATH)
document = require_asset(DOCUMENT_PATH)
document_type = unreal.BlueprintEditorLibrary.get_struct_type(document)
document_array_type = unreal.BlueprintEditorLibrary.get_array_type(document_type)
int_type = unreal.BlueprintEditorLibrary.get_basic_type_by_name("int")
int_array_type = unreal.BlueprintEditorLibrary.get_array_type(int_type)

for name in DOCUMENT_ARRAYS:
    ensure_variable(client, name, document_array_type)
for name in INT_ARRAYS:
    ensure_variable(client, name, int_array_type)
for name in SCALAR_DEFAULTS:
    ensure_variable(client, name, int_type)
ensure_variable(client, STAGING_DOCUMENT, document_type)
for function_name in FUNCTIONS:
    ensure_function(client, function_name)

unreal.BlueprintEditorLibrary.compile_blueprint(client)
for name in (*DOCUMENT_ARRAYS, *INT_ARRAYS):
    value = generated_value(name)
    if len(value) != 0:
        raise RuntimeError(f"{name} default must be empty")
    emit("EMPTY_ARRAY_VERIFIED", name)
for name, expected in SCALAR_DEFAULTS.items():
    set_default(name, expected)
if generated_value(STAGING_DOCUMENT) is None:
    raise RuntimeError(f"{STAGING_DOCUMENT} default was not constructed")
emit("STRUCT_DEFAULT_VERIFIED", STAGING_DOCUMENT)

unreal.BlueprintEditorLibrary.compile_blueprint(client)
for function_name in FUNCTIONS:
    if unreal.BlueprintEditorLibrary.find_graph(client, unreal.Name(function_name)) is None:
        raise RuntimeError(f"Blueprint is missing {function_name}")
    emit("FUNCTION_VERIFIED", function_name)
if not unreal.EditorAssetLibrary.save_asset(CLIENT_PATH, only_if_is_dirty=False):
    raise RuntimeError(f"Failed to save {CLIENT_PATH}")
unreal.BlueprintEditorLibrary.refresh_open_editors_for_blueprint(client)
emit("COMPLETE", True)
