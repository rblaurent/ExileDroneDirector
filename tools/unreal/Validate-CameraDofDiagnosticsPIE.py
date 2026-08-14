"""Automatic multi-session PIE acceptance for saved camera DOF diagnostics."""
from __future__ import annotations

import json
import time
import traceback
from pathlib import Path

import unreal


PREFIX = "EDD_CAMERA_DOF_PIE"
SOURCE_LEVEL_PATH = "/Game/Dev/AlmostEmpty"
WORLD_PATH = "/Game/Dev/UEDPIE_0_AlmostEmpty.AlmostEmpty"
CLIENT_CLASS_PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
TIMEOUT_SECONDS = 120.0
SCENARIOS = ("bounded", "unbounded", "fail_closed")
ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "tools/trajectory/camera_dof_diagnostics_blueprint_schema.json").read_text(encoding="utf-8"))
NAMES = tuple(spec["name"] for spec in SCHEMA["variables"])
UPSTREAM = ("CameraChannelResultValuesV1", "CameraChannelResultFilmbackSensorWidthMmV1", "CameraChannelResultFilmbackSensorHeightMmV1", "CameraChannelResultValidV1")


def emit(label, value): unreal.log(f"{PREFIX}|{label}|{value}")
def require(condition, message):
    if not condition: raise RuntimeError(f"{PREFIX}|FAIL|{message}")
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
def clone(value):
    if isinstance(value, (list, tuple)): return [clone(item) for item in value]
    return value
def normalized(value):
    if isinstance(value, (list, tuple)): return tuple(normalized(item) for item in value)
    return value
def close(left, right): return abs(float(left) - float(right)) <= 4e-4 * max(1.0, abs(float(left)), abs(float(right)))
def defaults():
    cls = unreal.load_class(None, CLIENT_CLASS_PATH); require(cls is not None, "class")
    return unreal.get_default_object(cls)
def pie_world():
    value = unreal.find_object(None, WORLD_PATH); require(value is not None, "PIE world")
    return value
def director(world):
    controller = unreal.GameplayStatics.get_player_controller(world, 0); require(controller is not None, "controller")
    cls = unreal.load_class(None, CLIENT_CLASS_PATH)
    values = controller.get_components_by_class(cls); require(len(values) == 1, f"director count:{len(values)}")
    return values[0]


def stage_scenario(obj, scenario):
    if scenario == "bounded": values = [85.0, 1.4, 250.0, *([0.0] * 10)]; width, height, valid = 22.2, 14.8, True
    elif scenario == "unbounded": values = [24.0, 16.0, 100000.0, *([0.0] * 10)]; width, height, valid = 36.0, 24.0, True
    elif scenario == "fail_closed": values = [50.0, 2.8, 1000.0, *([0.0] * 9)]; width, height, valid = 36.0, 24.0, True
    else: raise RuntimeError("unknown scenario:" + scenario)
    set_(obj, "CameraChannelResultValuesV1", values); set_(obj, "CameraChannelResultFilmbackSensorWidthMmV1", width)
    set_(obj, "CameraChannelResultFilmbackSensorHeightMmV1", height); set_(obj, "CameraChannelResultValidV1", valid)


def run_scenario(component, scenario):
    before = tuple(normalized(get(component, name)) for name in UPSTREAM)
    component.call_method("EvaluateCameraDofDiagnosticsV1")
    require(tuple(normalized(get(component, name)) for name in UPSTREAM) == before, "upstream mutated")
    if scenario == "fail_closed":
        require(not bool(get(component, "CameraDofResultValidV1")), "invalid frame accepted")
        require(str(get(component, "CameraDofFailureCodeV1")) == "camera_dof_compute_failed", "failure code")
        emit("FAIL_CLOSED_RESULT", "PASS")
    else:
        require(bool(get(component, "CameraDofResultValidV1")), "valid frame rejected")
        require(bool(get(component, "CameraDofFarUnboundedV1")) == (scenario == "unbounded"), "far domain")
        require(float(get(component, "CameraDofNearLimitCmV1")) > 0.0, "near limit")
        if scenario == "unbounded":
            require(close(get(component, "CameraDofFarLimitCmV1"), 0.0) and close(get(component, "CameraDofRearDepthCmV1"), 0.0), "unbounded sentinel")
        else:
            require(float(get(component, "CameraDofFarLimitCmV1")) > float(get(component, "CameraDofFocalPlaneDistanceCmV1")), "bounded far")
        if scenario == "bounded": emit("BOUNDED_RESULT", "PASS")
        else: emit("UNBOUNDED_RESULT", "PASS")
    emit("SCENARIO_RESULT", scenario + ":PASS")


def restore(state):
    if state.get("restored") or not state.get("originals"): return
    target = defaults()
    for name, value in state["originals"].items(): set_(target, name, clone(value))
    require(all(normalized(get(target, name)) == normalized(value) for name, value in state["originals"].items()), "current defaults restore")
    state["restored"] = True; emit("DEFAULTS_RESTORED", True)
def finish(success):
    state = globals().get("_EDD_CAMERA_DOF_PIE_STATE"); restore(state)
    if state and state.get("callback") is not None:
        unreal.unregister_slate_post_tick_callback(state["callback"]); state["callback"] = None
    if success: emit("GAME_WORLD_RESULT", "PASS")
    emit("AUTOMATIC_RESULT", "PASS" if success else "FAIL")


def tick(_delta):
    state = globals()["_EDD_CAMERA_DOF_PIE_STATE"]
    try:
        subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        require(time.monotonic() - state["armed_at"] < TIMEOUT_SECONDS, "overall timeout")
        if state["stage"] == "prepare":
            require(not subsystem.is_in_play_in_editor(), "PIE already running"); require(subsystem.load_level(SOURCE_LEVEL_PATH), "load level")
            target = defaults(); state["originals"] = {name: clone(get(target, name)) for name in (*NAMES, *UPSTREAM)}
            stage_scenario(target, SCENARIOS[0]); state["stage"] = "request"; state["stage_at"] = time.monotonic(); emit("SOURCE_LEVEL_READY", SOURCE_LEVEL_PATH); return
        if state["stage"] == "request":
            if time.monotonic() - state["stage_at"] < 0.5: return
            subsystem.editor_request_begin_play(); state["stage"] = "wait"; emit("PIE_START_REQUESTED", SCENARIOS[state["scenario_index"]]); return
        if state["stage"] == "wait":
            try:
                component = director(pie_world()); require(component.get_owner().has_actor_begun_play(), "BeginPlay")
            except Exception: return
            state["stage"] = "settle"; state["stage_at"] = time.monotonic(); return
        if state["stage"] == "settle":
            if time.monotonic() - state["stage_at"] < 1.0: return
            run_scenario(director(pie_world()), SCENARIOS[state["scenario_index"]]); subsystem.editor_request_end_play(); state["stage"] = "end"; return
        if state["stage"] == "end":
            if subsystem.is_in_play_in_editor(): return
            state["scenario_index"] += 1
            if state["scenario_index"] == len(SCENARIOS): state["stage"] = "complete"; finish(True); return
            stage_scenario(defaults(), SCENARIOS[state["scenario_index"]]); state["stage"] = "request"; state["stage_at"] = time.monotonic()
    except Exception as error:
        unreal.log_error(f"{PREFIX}|AUTOMATIC_EXCEPTION|{error}\n{traceback.format_exc()}")
        try: unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
        finally: state["stage"] = "failed"; finish(False)


old = globals().get("_EDD_CAMERA_DOF_PIE_STATE")
if old and old.get("callback") is not None: unreal.unregister_slate_post_tick_callback(old["callback"])
_EDD_CAMERA_DOF_PIE_STATE = {"stage":"prepare", "armed_at":time.monotonic(), "stage_at":time.monotonic(), "scenario_index":0, "callback":None, "originals":None, "restored":False}
_EDD_CAMERA_DOF_PIE_STATE["callback"] = unreal.register_slate_post_tick_callback(tick)
emit("ARMED", True)
