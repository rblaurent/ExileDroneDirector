"""Create and verify the standalone pooled path-preview actor seam.

Graph bodies are installed separately from reviewed native Blueprint clipboard
forms. This configurator owns only mod-local variables, component templates,
defaults, and empty function seams.
"""

from __future__ import annotations

import unreal


PREFIX = "EDD_PATH_PREVIEW"
PREVIEW_PATH = "/Game/Mods/ExileDroneDirector/Trajectory/BP_EDD_PathPreview"
DOCUMENT_PATH = "/Game/Mods/ExileDroneDirector/Data/Structs/ST_EDD_FlypathDocument"
COMPONENTS = (
    ("WaypointMarkersV1", unreal.HierarchicalInstancedStaticMeshComponent, "/Engine/BasicShapes/Sphere.Sphere"),
    ("SegmentLinesV1", unreal.HierarchicalInstancedStaticMeshComponent, "/Engine/BasicShapes/Cube.Cube"),
)
REAL_DEFAULTS = (
    ("MarkerScaleV1", 0.20),
    ("LineThicknessV1", 0.03),
    ("SourceCubeExtentV1", 100.0),
)
FUNCTIONS = ("ClearPreviewV1", "RebuildPreviewV1")


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


def generated_default():
    return unreal.get_default_object(require_class(PREVIEW_PATH))


def has_property(name: str) -> bool:
    try:
        generated_default().get_editor_property(name)
        return True
    except Exception:
        return False


def ensure_variable(blueprint, name: str, pin_type) -> None:
    if has_property(name):
        emit("VARIABLE_ALREADY_PRESENT", name)
        return
    if not unreal.BlueprintEditorLibrary.add_member_variable(blueprint, name, pin_type):
        raise RuntimeError(f"Failed to add variable: {name}")
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
    emit("VARIABLE_CREATED", name)


def ensure_function(blueprint, name: str) -> None:
    if unreal.BlueprintEditorLibrary.find_graph(blueprint, unreal.Name(name)) is not None:
        emit("FUNCTION_ALREADY_PRESENT", name)
        return
    if unreal.BlueprintEditorLibrary.add_function_graph(blueprint, name) is None:
        raise RuntimeError(f"Failed to create function: {name}")
    emit("FUNCTION_CREATED", name)


def component_handles(blueprint):
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    library = unreal.SubobjectDataBlueprintFunctionLibrary
    result = {}
    for handle in subsystem.k2_gather_subobject_data_for_blueprint(blueprint):
        data = subsystem.k2_find_subobject_data_from_handle(handle)
        name = str(library.get_variable_name(data))
        if name and name != "None":
            result[name] = handle
    return subsystem, result


def ensure_component(blueprint, name: str, component_class, mesh_path: str) -> None:
    subsystem, handles = component_handles(blueprint)
    handle = handles.get(name)
    if handle is None:
        all_handles = subsystem.k2_gather_subobject_data_for_blueprint(blueprint)
        if not all_handles:
            raise RuntimeError("Preview Blueprint returned no subobject handles")
        result = subsystem.add_new_subobject(
            params=unreal.AddNewSubobjectParams(
                parent_handle=all_handles[0],
                new_class=component_class,
                blueprint_context=blueprint,
            )
        )
        handle = result[0] if isinstance(result, tuple) else result
        if not unreal.SubobjectDataBlueprintFunctionLibrary.is_handle_valid(handle):
            raise RuntimeError(f"Failed to add component {name}: {result}")
        subsystem.rename_subobject(handle, unreal.Text(name))
        emit("COMPONENT_CREATED", name)
    else:
        emit("COMPONENT_ALREADY_PRESENT", name)

    data = subsystem.k2_find_subobject_data_from_handle(handle)
    component = unreal.SubobjectDataBlueprintFunctionLibrary.get_associated_object(data)
    if component is None or not isinstance(component, component_class):
        raise RuntimeError(f"Component template {name} has wrong type: {component}")
    mesh = require_asset(mesh_path)
    component.set_static_mesh(mesh)
    component.set_collision_profile_name("NoCollision")
    component.set_editor_property("cast_shadow", False)
    component.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    component.set_editor_property("hidden_in_game", False)
    component.set_editor_property("visible", True)
    emit("COMPONENT_CONFIGURED", f"{name}|{mesh.get_path_name()}")


preview = require_asset(PREVIEW_PATH)
document_struct = require_asset(DOCUMENT_PATH)
ensure_variable(preview, "PreviewDocumentV1", unreal.BlueprintEditorLibrary.get_struct_type(document_struct))
real_type = unreal.BlueprintEditorLibrary.get_basic_type_by_name("real")
for variable_name, _ in REAL_DEFAULTS:
    ensure_variable(preview, variable_name, real_type)
for function_name in FUNCTIONS:
    ensure_function(preview, function_name)
for component_name, component_class, mesh_path in COMPONENTS:
    ensure_component(preview, component_name, component_class, mesh_path)

unreal.BlueprintEditorLibrary.compile_blueprint(preview)
default = generated_default()
default.set_editor_property("PreviewEnabled", True)
default.set_editor_property("replicates", False)
default.set_editor_property("can_be_damaged", False)
for variable_name, expected in REAL_DEFAULTS:
    default.set_editor_property(variable_name, expected)
    actual = float(default.get_editor_property(variable_name))
    if abs(actual - expected) > 0.0001:
        raise RuntimeError(f"Default mismatch for {variable_name}: {actual}")
    emit("DEFAULT_VERIFIED", f"{variable_name}|{actual}")

unreal.BlueprintEditorLibrary.compile_blueprint(preview)
if not unreal.EditorAssetLibrary.save_asset(PREVIEW_PATH, only_if_is_dirty=False):
    raise RuntimeError(f"Failed to save {PREVIEW_PATH}")

for variable_name in ("PreviewDocumentV1", *(name for name, _ in REAL_DEFAULTS)):
    generated_default().get_editor_property(variable_name)
    emit("PROPERTY_VERIFIED", variable_name)
for function_name in FUNCTIONS:
    if unreal.BlueprintEditorLibrary.find_graph(preview, unreal.Name(function_name)) is None:
        raise RuntimeError(f"Missing function: {function_name}")
    emit("FUNCTION_VERIFIED", function_name)
_, verified_handles = component_handles(preview)
for component_name, _, _ in COMPONENTS:
    if component_name not in verified_handles:
        raise RuntimeError(f"Missing component: {component_name}")
    emit("COMPONENT_VERIFIED", component_name)

emit("COMPLETE", True)
