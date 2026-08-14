"""Non-persistent Enhanced DevKit probe for camera application properties.

The script spawns one transient BP_EDD_DroneCamera, reads only declared paths,
tests same-value writes on that transient instance, destroys it in ``finally``,
and emits one canonical manifest.  It never saves or modifies an asset.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import unreal


PREFIX = "EDD_CAMERA_PROPERTY_PROBE"
ROOT = Path(__file__).resolve().parents[2]
DRONE_CLASS_PATH = "/Game/Mods/ExileDroneDirector/Core/Camera/BP_EDD_DroneCamera.BP_EDD_DroneCamera_C"


def load_reference():
    path = ROOT / "tools/trajectory/camera_engine_property_probe_reference.py"
    spec = importlib.util.spec_from_file_location("edd_camera_property_probe_reference", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    trajectory_dir = str(path.parent)
    if trajectory_dir not in sys.path:
        sys.path.insert(0, trajectory_dir)
    spec.loader.exec_module(module)
    return module


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}|{label}|{json.dumps(value, sort_keys=True, default=str)}")


def editor_property(value, name: str):
    if hasattr(value, "get_editor_property"):
        return value.get_editor_property(name)
    return getattr(value, name)


def set_editor_property(value, name: str, new_value) -> None:
    if hasattr(value, "set_editor_property"):
        value.set_editor_property(name, new_value)
    else:
        setattr(value, name, new_value)


def read_path(root, dotted_path: str):
    current = root
    for part in dotted_path.split("."):
        current = editor_property(current, part)
    return current


def write_same_path(root, dotted_path: str, original) -> None:
    parts = dotted_path.split(".")
    if len(parts) == 1:
        set_editor_property(root, parts[0], original)
        return
    parent = root
    ancestors = []
    for part in parts[:-1]:
        child = editor_property(parent, part)
        ancestors.append((parent, part, child))
        parent = child
    set_editor_property(parent, parts[-1], original)
    for owner, part, child in reversed(ancestors):
        set_editor_property(owner, part, child)


def value_type(value) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, float):
        return "float"
    if isinstance(value, int):
        return "int"
    return type(value).__name__


def spawn_transient_camera():
    drone_class = unreal.load_class(None, DRONE_CLASS_PATH)
    if drone_class is None:
        raise RuntimeError("Drone camera generated class is unavailable")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = subsystem.spawn_actor_from_class(drone_class, unreal.Vector(), unreal.Rotator())
    if actor is None:
        raise RuntimeError("Could not spawn transient drone camera")
    components = actor.get_components_by_class(unreal.CineCameraComponent)
    if len(components) != 1:
        subsystem.destroy_actor(actor)
        raise RuntimeError(f"Expected one CineCameraComponent, found {len(components)}")
    return subsystem, actor, components[0]


reference = load_reference()
schema = reference.load_camera_engine_property_candidates_v1()
subsystem = actor = component = None
try:
    subsystem, actor, component = spawn_transient_camera()
    observations = {}
    paths = []
    for target in schema["targets"]:
        for candidate in target["candidates"]:
            paths.append(candidate["valuePath"])
            if candidate.get("overridePath"):
                paths.append(candidate["overridePath"])
    for path in dict.fromkeys(paths):
        readable = writable = False
        reflected_type = "missing"
        error = ""
        try:
            original = read_path(component, path)
            readable = True
            reflected_type = value_type(original)
            try:
                write_same_path(component, path, original)
                writable = True
            except Exception as write_error:
                error = f"write:{write_error}"
        except Exception as read_error:
            error = f"read:{read_error}"
        observations[path] = reference.CameraEnginePropertyObservationV1(
            readable, writable, reflected_type
        )
        emit(
            "OBSERVATION",
            {
                "path": path,
                "readable": readable,
                "sameValueWritable": writable,
                "valueType": reflected_type,
                "error": error,
            },
        )
    manifest = reference.resolve_camera_engine_property_manifest_v1(
        unreal.SystemLibrary.get_engine_version(), observations, schema
    )
    emit("MANIFEST", json.loads(manifest.canonical_json))
    emit("MISSING_REQUIRED", list(manifest.missing_required_target_ids))
    emit("RESULT", "PASS" if not manifest.missing_required_target_ids else "MISSING_REQUIRED")
finally:
    if actor is not None and subsystem is not None:
        subsystem.destroy_actor(actor)
        emit("TRANSIENT_DESTROYED", True)
