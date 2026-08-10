"""Create and verify the live transactional document-sync state seam.

The graph body is installed separately from a deterministic, reviewed native
Blueprint clipboard snippet. Scratch members are explicit because this
Enhanced build's Python API cannot create function-local variables. They are
private runtime implementation state; only ``DraftSegmentsV1`` and
``DraftDocumentV1`` are document storage.
"""

from __future__ import annotations

import unreal


PREFIX = "EDD_DOCUMENT_SYNC"
CLIENT_PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector"
SEGMENT_PATH = "/Game/Mods/ExileDroneDirector/Data/Structs/ST_EDD_Segment"
FUNCTION_NAME = "SyncDraftDocumentV1"
SCALAR_VARIABLES = (
    ("DocumentSyncValidV1", "bool", False),
    ("DocumentTotalDurationV1", "real", 0.0),
    ("DocumentNextSegmentIdV1", "int", 1),
    ("DocumentMatchFoundV1", "bool", False),
)
INT_ARRAY_VARIABLE = "DocumentUsedSegmentIdsV1"
SEGMENT_ARRAY_VARIABLE = "DocumentSegmentsScratchV1"
SEGMENT_VALUE_VARIABLE = "DocumentCandidateSegmentV1"


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}|{label}|{value}")


def require_asset(path: str):
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if asset is None:
        raise RuntimeError(f"Required asset could not be loaded: {path}")
    return asset


def require_class(path: str):
    generated_class = unreal.EditorAssetLibrary.load_blueprint_class(path)
    if generated_class is None:
        raise RuntimeError(f"Required Blueprint class could not be loaded: {path}")
    return generated_class


def property_candidates(variable_name: str) -> tuple[object, ...]:
    snake = "".join(
        ("_" + character.lower()) if character.isupper() else character
        for character in variable_name
    ).lstrip("_")
    return variable_name, unreal.Name(variable_name), snake, unreal.Name(snake)


def generated_value(variable_name: str):
    default_object = unreal.get_default_object(require_class(CLIENT_PATH))
    last_error = None
    for candidate in property_candidates(variable_name):
        try:
            return default_object.get_editor_property(candidate)
        except Exception as error:
            last_error = error
    raise RuntimeError(f"Generated class is missing {variable_name}: {last_error}")


def has_generated_property(variable_name: str) -> bool:
    try:
        generated_value(variable_name)
        return True
    except Exception:
        return False


def ensure_variable(blueprint, variable_name: str, pin_type) -> None:
    if has_generated_property(variable_name):
        emit("VARIABLE_ALREADY_PRESENT", variable_name)
        return
    if not unreal.BlueprintEditorLibrary.add_member_variable(
        blueprint, variable_name, pin_type
    ):
        raise RuntimeError(f"Failed to add {variable_name}")
    emit("VARIABLE_CREATED", variable_name)
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)


def set_default(variable_name: str, expected) -> None:
    default_object = unreal.get_default_object(require_class(CLIENT_PATH))
    last_error = None
    for candidate in property_candidates(variable_name):
        try:
            default_object.set_editor_property(candidate, expected)
            actual = default_object.get_editor_property(candidate)
            if isinstance(expected, float):
                if abs(float(actual) - expected) > 0.0001:
                    raise RuntimeError(f"expected {expected}, received {actual}")
            elif actual != expected:
                raise RuntimeError(f"expected {expected}, received {actual}")
            emit("DEFAULT_VERIFIED", f"{variable_name}|{actual}")
            return
        except Exception as error:
            last_error = error
    raise RuntimeError(f"Could not configure {variable_name}: {last_error}")


client = require_asset(CLIENT_PATH)
segment = require_asset(SEGMENT_PATH)
segment_type = unreal.BlueprintEditorLibrary.get_struct_type(segment)

for name, type_name, _ in SCALAR_VARIABLES:
    ensure_variable(
        client,
        name,
        unreal.BlueprintEditorLibrary.get_basic_type_by_name(type_name),
    )

int_type = unreal.BlueprintEditorLibrary.get_basic_type_by_name("int")
ensure_variable(
    client,
    INT_ARRAY_VARIABLE,
    unreal.BlueprintEditorLibrary.get_array_type(int_type),
)
ensure_variable(
    client,
    SEGMENT_ARRAY_VARIABLE,
    unreal.BlueprintEditorLibrary.get_array_type(segment_type),
)
ensure_variable(client, SEGMENT_VALUE_VARIABLE, segment_type)

graph = unreal.BlueprintEditorLibrary.find_graph(client, unreal.Name(FUNCTION_NAME))
if graph is None:
    graph = unreal.BlueprintEditorLibrary.add_function_graph(client, FUNCTION_NAME)
    if graph is None:
        raise RuntimeError(f"Failed to create {FUNCTION_NAME}")
    emit("FUNCTION_CREATED", FUNCTION_NAME)
else:
    emit("FUNCTION_ALREADY_PRESENT", FUNCTION_NAME)

unreal.BlueprintEditorLibrary.compile_blueprint(client)
for name, _, expected in SCALAR_VARIABLES:
    set_default(name, expected)

for name in (INT_ARRAY_VARIABLE, SEGMENT_ARRAY_VARIABLE):
    value = generated_value(name)
    if len(value) != 0:
        raise RuntimeError(f"{name} default must be empty")
    emit("EMPTY_ARRAY_VERIFIED", f"{name}|0")

if generated_value(SEGMENT_VALUE_VARIABLE) is None:
    raise RuntimeError(f"{SEGMENT_VALUE_VARIABLE} default was not constructed")
emit("STRUCT_DEFAULT_VERIFIED", SEGMENT_VALUE_VARIABLE)

unreal.BlueprintEditorLibrary.compile_blueprint(client)
if not unreal.EditorAssetLibrary.save_asset(CLIENT_PATH, only_if_is_dirty=False):
    raise RuntimeError(f"Failed to save {CLIENT_PATH}")
if unreal.BlueprintEditorLibrary.find_graph(client, unreal.Name(FUNCTION_NAME)) is None:
    raise RuntimeError(f"Blueprint is missing {FUNCTION_NAME}")
emit("FUNCTION_VERIFIED", FUNCTION_NAME)
unreal.BlueprintEditorLibrary.refresh_open_editors_for_blueprint(client)
emit("COMPLETE", True)
