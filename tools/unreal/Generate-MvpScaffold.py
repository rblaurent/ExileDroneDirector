"""Generate the first idempotent Exile Drone Director Unreal asset scaffold.

Run only with the interactive editor closed. The script writes exclusively below
/Game/Mods/ExileDroneDirector, which DreamworldMods redirects into the active
mod's Local directory.
"""

from __future__ import annotations

from pathlib import Path

import unreal


PREFIX = "EDD_SCAFFOLD"
ROOT = "/Game/Mods/ExileDroneDirector"
PHYSICAL_MOD_ROOT = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir())) / "Mods" / "ExileDroneDirector"

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
editor_assets = unreal.EditorAssetLibrary
blueprint_library = unreal.BlueprintEditorLibrary
created: list[str] = []
reused: list[str] = []
warnings: list[str] = []


def log(message: str) -> None:
    unreal.log(f"{PREFIX}|{message}")


def warn(message: str) -> None:
    warnings.append(message)
    unreal.log_warning(f"{PREFIX}|WARNING|{message}")


def split_asset_path(asset_path: str) -> tuple[str, str]:
    package_path, asset_name = asset_path.rsplit("/", 1)
    return package_path, asset_name


def ensure_directory(package_path: str) -> None:
    if not editor_assets.does_directory_exist(package_path):
        if not editor_assets.make_directory(package_path):
            raise RuntimeError(f"Could not create Unreal directory: {package_path}")


def create_blueprint(asset_path: str, parent_class):
    existing = editor_assets.load_asset(asset_path) if editor_assets.does_asset_exist(asset_path) else None
    if existing:
        reused.append(asset_path)
        return existing

    package_path, asset_name = split_asset_path(asset_path)
    ensure_directory(package_path)
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", parent_class)
    blueprint = asset_tools.create_asset(asset_name, package_path, unreal.Blueprint, factory)
    if blueprint is None:
        raise RuntimeError(f"Could not create Blueprint: {asset_path}")
    created.append(asset_path)
    return blueprint


def create_widget_blueprint(asset_path: str):
    existing = editor_assets.load_asset(asset_path) if editor_assets.does_asset_exist(asset_path) else None
    if existing:
        reused.append(asset_path)
        return existing

    package_path, asset_name = split_asset_path(asset_path)
    ensure_directory(package_path)
    factory = unreal.WidgetBlueprintFactory()
    factory.set_editor_property("parent_class", unreal.UserWidget)
    widget = asset_tools.create_asset(asset_name, package_path, unreal.WidgetBlueprint, factory)
    if widget is None:
        raise RuntimeError(f"Could not create Widget Blueprint: {asset_path}")
    created.append(asset_path)
    return widget


def create_struct(asset_path: str):
    existing = editor_assets.load_asset(asset_path) if editor_assets.does_asset_exist(asset_path) else None
    if existing:
        reused.append(asset_path)
        return existing

    package_path, asset_name = split_asset_path(asset_path)
    ensure_directory(package_path)
    struct = asset_tools.create_asset(asset_name, package_path, unreal.UserDefinedStruct, unreal.StructureFactory())
    if struct is None:
        raise RuntimeError(f"Could not create user-defined struct: {asset_path}")
    created.append(asset_path)
    return struct


def create_data_asset(asset_path: str, asset_class):
    existing = editor_assets.load_asset(asset_path) if editor_assets.does_asset_exist(asset_path) else None
    if existing:
        reused.append(asset_path)
        return existing

    package_path, asset_name = split_asset_path(asset_path)
    ensure_directory(package_path)
    factory = unreal.DataAssetFactory()
    factory.set_editor_property("data_asset_class", asset_class)
    asset = asset_tools.create_asset(asset_name, package_path, asset_class, factory)
    if asset is None:
        raise RuntimeError(f"Could not create data asset: {asset_path}")
    created.append(asset_path)
    return asset


def add_variable(blueprint, variable_name: str, type_name: str) -> None:
    try:
        pin_type = blueprint_library.get_basic_type_by_name(type_name)
        if blueprint_library.add_member_variable(blueprint, variable_name, pin_type):
            log(f"VARIABLE_CREATED|{blueprint.get_path_name()}|{variable_name}|{type_name}")
    except Exception as error:
        warn(f"Could not add variable {variable_name} to {blueprint.get_path_name()}: {error}")


def add_component(blueprint, component_class, component_name: str):
    try:
        subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
        handles = subsystem.k2_gather_subobject_data_for_blueprint(blueprint)
        if not handles:
            raise RuntimeError("Blueprint returned no subobject handles")
        for existing_handle in handles:
            data = subsystem.k2_find_subobject_data_from_handle(existing_handle)
            variable_name = str(unreal.SubobjectDataBlueprintFunctionLibrary.get_variable_name(data))
            if variable_name == component_name:
                log(f"COMPONENT_REUSED|{blueprint.get_path_name()}|{component_name}")
                return existing_handle
        params = unreal.AddNewSubobjectParams(
            parent_handle=handles[0],
            new_class=component_class,
            blueprint_context=blueprint,
        )
        result = subsystem.add_new_subobject(params=params)
        if isinstance(result, tuple):
            handle = result[0]
            failure_reason = str(result[1]) if len(result) > 1 else ""
        else:
            handle = result
            failure_reason = ""
        if not unreal.SubobjectDataBlueprintFunctionLibrary.is_handle_valid(handle):
            raise RuntimeError(f"Invalid component handle: {failure_reason}")
        subsystem.rename_subobject(handle, unreal.Text(component_name))
        log(f"COMPONENT_CREATED|{blueprint.get_path_name()}|{component_name}|{component_class}")
        return handle
    except Exception as error:
        warn(f"Could not add {component_name} to {blueprint.get_path_name()}: {error}")
        return None


for directory in (
    ROOT,
    f"{ROOT}/Core",
    f"{ROOT}/Core/Camera",
    f"{ROOT}/Core/Client",
    f"{ROOT}/Data/Structs",
    f"{ROOT}/Input",
    f"{ROOT}/Trajectory",
    f"{ROOT}/UI/Editor",
):
    ensure_directory(directory)

mod_controller = create_blueprint(f"{ROOT}/BP_EDD_ModController", unreal.ModController)
client_director = create_blueprint(f"{ROOT}/Core/Client/BPC_EDD_ClientDirector", unreal.ActorComponent)
drone_camera = create_blueprint(f"{ROOT}/Core/Camera/BP_EDD_DroneCamera", unreal.SpectatorPawn)
path_preview = create_blueprint(f"{ROOT}/Trajectory/BP_EDD_PathPreview", unreal.Actor)

for blueprint in (client_director, drone_camera, path_preview):
    try:
        blueprint_library.remove_unused_variables(blueprint)
    except Exception as error:
        warn(f"Could not clear unused scaffold variables from {blueprint.get_path_name()}: {error}")

for variable_name, type_name in (
    ("DroneModeActive", "bool"),
    ("FreeLookEnabled", "bool"),
    ("CarrierFreecamEnabled", "bool"),
    ("ActiveFlypathId", "string"),
    ("PlaybackTime", "real"),
):
    add_variable(client_director, variable_name, type_name)

for variable_name, type_name in (
    ("BaseMoveSpeed", "real"),
    ("CruiseMoveSpeed", "real"),
    ("CurrentMoveSpeed", "real"),
    ("BoostMultiplier", "real"),
    ("PrecisionMultiplier", "real"),
    ("SpeedTrimRatio", "real"),
    ("MinMoveSpeed", "real"),
    ("MaxMoveSpeed", "real"),
    ("SpeedResponse", "real"),
    ("LookSensitivity", "real"),
    ("ManualRollSpeed", "real"),
    ("CurrentRollSpeed", "real"),
    ("RollInputResponse", "real"),
    ("HorizonLockResponse", "real"),
    ("FocalLength", "real"),
    ("Aperture", "real"),
    ("ManualFocusDistance", "real"),
):
    add_variable(drone_camera, variable_name, type_name)
add_variable(drone_camera, "HorizonLockEnabled", "bool")

add_variable(path_preview, "PreviewEnabled", "bool")
add_component(drone_camera, unreal.CineCameraComponent, "DroneCamera")
add_component(path_preview, unreal.SplineComponent, "PathSpline")

create_struct(f"{ROOT}/Data/Structs/ST_EDD_FlypathDocument")
create_struct(f"{ROOT}/Data/Structs/ST_EDD_Waypoint")
create_struct(f"{ROOT}/Data/Structs/ST_EDD_Segment")
create_widget_blueprint(f"{ROOT}/UI/Editor/WBP_EDD_DroneHUD")

input_specs = (
    ("IA_EDD_ToggleDrone", unreal.InputActionValueType.BOOLEAN),
    ("IA_EDD_Move", unreal.InputActionValueType.AXIS3D),
    ("IA_EDD_Look", unreal.InputActionValueType.AXIS2D),
    ("IA_EDD_Boost", unreal.InputActionValueType.BOOLEAN),
    ("IA_EDD_AddWaypoint", unreal.InputActionValueType.BOOLEAN),
)
for asset_name, value_type in input_specs:
    action = create_data_asset(f"{ROOT}/Input/{asset_name}", unreal.InputAction)
    try:
        action.set_editor_property("value_type", value_type)
    except Exception as error:
        warn(f"Could not set value type on {asset_name}: {error}")

create_data_asset(f"{ROOT}/Input/IMC_EDD_Drone", unreal.InputMappingContext)

try:
    client_class = editor_assets.load_blueprint_class(f"{ROOT}/Core/Client/BPC_EDD_ClientDirector")
    controller_class = editor_assets.load_blueprint_class("/Game/Systems/FunCombat_PlayerController")
    rule_names = [
        name
        for name in dir(unreal.AdditionalComponentRules)
        if name.isupper() and "CLIENT" in name and "SERVER" not in name
    ]
    log(f"CLIENT_RULE_CANDIDATES|{rule_names}")
    if not client_class or not controller_class:
        raise RuntimeError("Could not resolve generated client component or Conan player controller class")
    if not rule_names:
        raise RuntimeError("No client-only AdditionalComponentRules enum value was exposed")

    rule = getattr(unreal.AdditionalComponentRules, rule_names[0])
    attachment = unreal.AdditionalClassComponent(
        addition_rule=rule,
        component_tag=unreal.Name("EDD_ClientDirector"),
        component_to_add=client_class,
        target_actor_class=controller_class,
    )
    mod_class = editor_assets.load_blueprint_class(f"{ROOT}/BP_EDD_ModController")
    mod_cdo = unreal.get_default_object(mod_class)
    mod_cdo.set_editor_property("additional_class_components", [attachment])
    log(f"MOD_CONTROLLER_ATTACHMENT|{rule_names[0]}|{controller_class.get_path_name()}|{client_class.get_path_name()}")
except Exception as error:
    warn(f"Could not configure ModController client attachment: {error}")

for blueprint in (mod_controller, client_director, drone_camera, path_preview):
    try:
        blueprint_library.compile_blueprint(blueprint)
    except Exception as error:
        warn(f"Blueprint compile call failed for {blueprint.get_path_name()}: {error}")

if not editor_assets.save_directory(ROOT, only_if_is_dirty=False, recursive=True):
    raise RuntimeError(f"Could not save generated assets below {ROOT}")

physical_assets = sorted(
    str(path.relative_to(PHYSICAL_MOD_ROOT))
    for path in PHYSICAL_MOD_ROOT.rglob("*")
    if path.is_file() and path.suffix.lower() in {".uasset", ".umap", ".uexp", ".ubulk"}
)
log(f"CREATED|{created}")
log(f"REUSED|{reused}")
log(f"WARNINGS|{warnings}")
log(f"PHYSICAL_ASSETS|{physical_assets}")
log("COMPLETE")
