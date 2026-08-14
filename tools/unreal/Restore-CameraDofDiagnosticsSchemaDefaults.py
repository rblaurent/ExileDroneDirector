"""Restore DOF and temporarily staged camera-frame defaults after PIE."""
from __future__ import annotations

import json
from pathlib import Path

import unreal


PREFIX = "EDD_CAMERA_DOF_DEFAULTS"
CLIENT = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector"
ROOT = Path(__file__).resolve().parents[2]
DOF = json.loads((ROOT / "tools/trajectory/camera_dof_diagnostics_blueprint_schema.json").read_text(encoding="utf-8"))
CHANNEL = json.loads((ROOT / "tools/trajectory/camera_channel_assembly_blueprint_schema.json").read_text(encoding="utf-8"))
UPSTREAM_NAMES = {
    "CameraChannelResultValuesV1", "CameraChannelResultFilmbackSensorWidthMmV1",
    "CameraChannelResultFilmbackSensorHeightMmV1", "CameraChannelResultValidV1",
}
SPECS = tuple(DOF["variables"]) + tuple(spec for spec in CHANNEL["variables"] if spec["name"] in UPSTREAM_NAMES)


def emit(label, value): unreal.log(f"{PREFIX}|{label}|{value}")
def variants(name):
    snake = "".join(("_" + char.lower()) if char.isupper() else char for char in name).lstrip("_")
    return name, unreal.Name(name), snake, unreal.Name(snake)
def get(obj, name):
    for candidate in variants(name):
        try: return obj.get_editor_property(candidate)
        except Exception: pass
    raise RuntimeError("missing property:" + name)
def set_(obj, name, value):
    for candidate in variants(name):
        try: obj.set_editor_property(candidate, value); return
        except Exception: pass
    raise RuntimeError("could not set property:" + name)
def expected(spec):
    if spec["container"] == "Array": return []
    value = spec.get("default", 0.0)
    if spec["type"] == "String": return str(value)
    if spec["type"] == "Boolean": return bool(value)
    if spec["type"] == "Integer": return int(value)
    if spec["type"] == "Float": return float(value)
    raise RuntimeError("unsupported type:" + spec["type"])
def normalized(value):
    if isinstance(value, (list, tuple)): return tuple(normalized(item) for item in value)
    return value


blueprint = unreal.EditorAssetLibrary.load_asset(CLIENT)
if blueprint is None: raise RuntimeError(CLIENT)
unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
generated = unreal.EditorAssetLibrary.load_blueprint_class(CLIENT)
if generated is None: raise RuntimeError(CLIENT + "_C")
obj = unreal.get_default_object(generated)
for spec in SPECS: set_(obj, spec["name"], expected(spec))
for spec in SPECS:
    actual, wanted = normalized(get(obj, spec["name"])), normalized(expected(spec))
    if actual != wanted: raise RuntimeError(f"default mismatch:{spec['name']}:{actual}:{wanted}")
    emit("VERIFIED", spec["name"])
if not unreal.EditorAssetLibrary.save_asset(CLIENT, only_if_is_dirty=False): raise RuntimeError("save failed")
emit("VARIABLE_COUNT", len(SPECS)); emit("COMPLETE", True)
