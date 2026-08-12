"""Create the staged state seam for trajectory-engine scalar evaluators."""

from __future__ import annotations

import unreal


PREFIX = "EDD_TRAJECTORY_SCALAR_CONFIG"
CLIENT_PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector"
VARIABLE_DEFAULTS = (
    ("TrajectoryInputProfileV1", "string", ""),
    ("TrajectoryInputAlphaV1", "real", 0.0),
    ("TrajectoryInputStartValueV1", "real", 0.0),
    ("TrajectoryInputStartVelocityUV1", "real", 0.0),
    ("TrajectoryInputStartAccelerationUV1", "real", 0.0),
    ("TrajectoryInputEndValueV1", "real", 0.0),
    ("TrajectoryInputEndVelocityUV1", "real", 0.0),
    ("TrajectoryInputEndAccelerationUV1", "real", 0.0),
    ("TrajectoryResultValueV1", "real", 0.0),
    ("TrajectoryResultDerivativeUV1", "real", 0.0),
    ("TrajectoryResultSecondDerivativeUV1", "real", 0.0),
    ("TrajectoryResultValidV1", "bool", False),
)
FUNCTION_NAMES = ("EvaluateTimeProfileV1", "EvaluateQuinticScalarV1")


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}|{label}|{value}")


def require_asset(path: str):
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if asset is None:
        raise RuntimeError(f"Required asset could not be loaded: {path}")
    return asset


def require_class(path: str):
    generated = unreal.EditorAssetLibrary.load_blueprint_class(path)
    if generated is None:
        raise RuntimeError(f"Required Blueprint class could not be loaded: {path}")
    return generated


def candidates(name: str):
    snake = "".join(("_" + c.lower()) if c.isupper() else c for c in name).lstrip("_")
    return name, unreal.Name(name), snake, unreal.Name(snake)


def generated_value(name: str):
    default = unreal.get_default_object(require_class(CLIENT_PATH))
    last_error = None
    for candidate in candidates(name):
        try:
            return default.get_editor_property(candidate)
        except Exception as error:
            last_error = error
    raise RuntimeError(f"Generated class is missing {name}: {last_error}")


def has_property(name: str) -> bool:
    try:
        generated_value(name)
        return True
    except Exception:
        return False


def set_default(name: str, expected) -> None:
    default = unreal.get_default_object(require_class(CLIENT_PATH))
    last_error = None
    for candidate in candidates(name):
        try:
            default.set_editor_property(candidate, expected)
            actual = default.get_editor_property(candidate)
            if isinstance(expected, float):
                if abs(float(actual) - expected) > 0.0001:
                    raise RuntimeError(f"expected {expected}, received {actual}")
            elif actual != expected:
                raise RuntimeError(f"expected {expected!r}, received {actual!r}")
            emit("DEFAULT_VERIFIED", f"{name}|{actual}")
            return
        except Exception as error:
            last_error = error
    raise RuntimeError(f"Could not configure {name}: {last_error}")


blueprint = require_asset(CLIENT_PATH)
for name, kind, _ in VARIABLE_DEFAULTS:
    if has_property(name):
        emit("VARIABLE_ALREADY_PRESENT", name)
        continue
    pin_type = unreal.BlueprintEditorLibrary.get_basic_type_by_name(kind)
    if not unreal.BlueprintEditorLibrary.add_member_variable(blueprint, name, pin_type):
        raise RuntimeError(f"Failed to add Blueprint variable: {name}")
    emit("VARIABLE_CREATED", name)
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)

for name in FUNCTION_NAMES:
    graph = unreal.BlueprintEditorLibrary.find_graph(blueprint, unreal.Name(name))
    if graph is None:
        graph = unreal.BlueprintEditorLibrary.add_function_graph(blueprint, name)
        if graph is None:
            raise RuntimeError(f"Failed to add Blueprint function: {name}")
        emit("FUNCTION_CREATED", name)
    else:
        emit("FUNCTION_ALREADY_PRESENT", name)

unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
for name, _, expected in VARIABLE_DEFAULTS:
    set_default(name, expected)
unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
if not unreal.EditorAssetLibrary.save_asset(CLIENT_PATH, only_if_is_dirty=False):
    raise RuntimeError(f"Failed to save {CLIENT_PATH}")
for name in FUNCTION_NAMES:
    if unreal.BlueprintEditorLibrary.find_graph(blueprint, unreal.Name(name)) is None:
        raise RuntimeError(f"Blueprint is missing function: {name}")
    emit("FUNCTION_VERIFIED", name)
unreal.BlueprintEditorLibrary.refresh_open_editors_for_blueprint(blueprint)
emit("COMPLETE", True)
