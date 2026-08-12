"""Create and verify the staged vector seam for the quintic scalar kernel."""

from __future__ import annotations

import unreal


PREFIX = "EDD_TRAJECTORY_VECTOR_CONFIG"
CLIENT_PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector"
VECTOR_NAMES = (
    "TrajectoryInputStartPositionVectorV1",
    "TrajectoryInputStartVelocityUVectorV1",
    "TrajectoryInputStartAccelerationUVectorV1",
    "TrajectoryInputEndPositionVectorV1",
    "TrajectoryInputEndVelocityUVectorV1",
    "TrajectoryInputEndAccelerationUVectorV1",
    "TrajectoryResultPositionVectorV1",
    "TrajectoryResultDerivativeUVectorV1",
    "TrajectoryResultSecondDerivativeUVectorV1",
)
REAL_NAMES = tuple(
    f"TrajectoryVectorScratch{channel}{axis}V1"
    for axis in "XYZ"
    for channel in ("Value", "Derivative", "SecondDerivative")
)
BOOL_NAMES = ("TrajectoryResultVectorValidV1",)
FUNCTION_NAME = "EvaluateQuinticVectorV1"


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}|{label}|{value}")


def candidates(name: str):
    snake = "".join(("_" + char.lower()) if char.isupper() else char for char in name).lstrip("_")
    return name, unreal.Name(name), snake, unreal.Name(snake)


def blueprint_class():
    value = unreal.EditorAssetLibrary.load_blueprint_class(CLIENT_PATH)
    if value is None:
        raise RuntimeError(CLIENT_PATH)
    return value


def default_object():
    return unreal.get_default_object(blueprint_class())


def get_property(name: str):
    last = None
    for candidate in candidates(name):
        try:
            return default_object().get_editor_property(candidate)
        except Exception as error:
            last = error
    raise RuntimeError(f"missing {name}: {last}")


def has_property(name: str) -> bool:
    try:
        get_property(name)
        return True
    except Exception:
        return False


blueprint = unreal.EditorAssetLibrary.load_asset(CLIENT_PATH)
if blueprint is None:
    raise RuntimeError(CLIENT_PATH)
vector_struct = unreal.load_object(None, "/Script/CoreUObject.Vector")
if vector_struct is None:
    raise RuntimeError("native Vector ScriptStruct is unavailable")
groups = (
    (VECTOR_NAMES, unreal.BlueprintEditorLibrary.get_struct_type(vector_struct)),
    (REAL_NAMES, unreal.BlueprintEditorLibrary.get_basic_type_by_name("real")),
    (BOOL_NAMES, unreal.BlueprintEditorLibrary.get_basic_type_by_name("bool")),
)
for names, pin_type in groups:
    for name in names:
        if has_property(name):
            emit("VARIABLE_ALREADY_PRESENT", name)
            continue
        if not unreal.BlueprintEditorLibrary.add_member_variable(blueprint, name, pin_type):
            raise RuntimeError(f"failed to add {name}")
        unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
        emit("VARIABLE_CREATED", name)

if unreal.BlueprintEditorLibrary.find_graph(blueprint, unreal.Name(FUNCTION_NAME)) is None:
    if unreal.BlueprintEditorLibrary.add_function_graph(blueprint, FUNCTION_NAME) is None:
        raise RuntimeError(f"failed to add {FUNCTION_NAME}")
    emit("FUNCTION_CREATED", FUNCTION_NAME)
else:
    emit("FUNCTION_ALREADY_PRESENT", FUNCTION_NAME)

unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
default = default_object()
for name in VECTOR_NAMES:
    for candidate in candidates(name):
        try:
            default.set_editor_property(candidate, unreal.Vector(0.0, 0.0, 0.0))
            break
        except Exception:
            continue
    else:
        raise RuntimeError(f"could not default {name}")
for name in REAL_NAMES:
    for candidate in candidates(name):
        try:
            default.set_editor_property(candidate, 0.0)
            break
        except Exception:
            continue
    else:
        raise RuntimeError(f"could not default {name}")
for name in BOOL_NAMES:
    for candidate in candidates(name):
        try:
            default.set_editor_property(candidate, False)
            break
        except Exception:
            continue
    else:
        raise RuntimeError(f"could not default {name}")

unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
if not unreal.EditorAssetLibrary.save_asset(CLIENT_PATH, only_if_is_dirty=False):
    raise RuntimeError("save failed")
for name in (*VECTOR_NAMES, *REAL_NAMES, *BOOL_NAMES):
    emit("DEFAULT_VERIFIED", f"{name}|{get_property(name)}")
if unreal.BlueprintEditorLibrary.find_graph(blueprint, unreal.Name(FUNCTION_NAME)) is None:
    raise RuntimeError(f"missing {FUNCTION_NAME}")
unreal.BlueprintEditorLibrary.refresh_open_editors_for_blueprint(blueprint)
emit("FUNCTION_VERIFIED", FUNCTION_NAME)
emit("COMPLETE", True)
