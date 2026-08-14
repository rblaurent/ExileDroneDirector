"""Real player-owned PIE acceptance for transactional native camera application."""
from __future__ import annotations

import json
import time
import traceback
from pathlib import Path

import unreal


PREFIX = "EDD_CAMERA_ENGINE_PIE"
SOURCE = "/Game/Dev/AlmostEmpty"
WORLD = "/Game/Dev/UEDPIE_0_AlmostEmpty.AlmostEmpty"
DIRECTOR_CLASS = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "tools/trajectory/camera_engine_application_blueprint_schema.json").read_text(encoding="utf-8"))
CHANNEL_SCHEMA = json.loads((ROOT / "tools/trajectory/camera_channel_assembly_blueprint_schema.json").read_text(encoding="utf-8"))
ENGINE_NAMES = tuple(item["name"] for item in SCHEMA["variables"])
CHANNEL_RESULTS = tuple(item["name"] for item in CHANNEL_SCHEMA["variables"] if item["name"].startswith("CameraChannelResult"))
DEFAULT_NAMES = tuple(dict.fromkeys((*ENGINE_NAMES, *CHANNEL_RESULTS)))
TIMEOUT = 120.0
FRAMES = (
    ("pie_forward", 31.0, 17.0, (52.0, 2.2, 275.0, 1.0, 1.5, 0.25, 0.35, 0.0, 0.0, 0.45, 0.55, 0.0, 0.0)),
    ("pie_reverse", 46.0, 26.0, (85.0, 6.3, 950.0, 1.0, -1.0, 0.75, 0.65, 0.0, 0.0, 0.15, 0.25, 0.0, 0.0)),
)


def emit(label, value): unreal.log(f"{PREFIX}|{label}|{value}")
def require(value, message):
    if not value: raise RuntimeError(f"{PREFIX}|FAIL|{message}")
def variants(name):
    snake = "".join(("_" + char.lower()) if char.isupper() else char for char in name).lstrip("_")
    return name, unreal.Name(name), snake, unreal.Name(snake)
def get(obj, name):
    for candidate in variants(name):
        try: return obj.get_editor_property(candidate)
        except Exception: pass
    raise RuntimeError(f"missing:{name}")
def set_(obj, name, value):
    for candidate in variants(name):
        try: obj.set_editor_property(candidate, value); return
        except Exception: pass
    raise RuntimeError(f"cannot-set:{name}")
def clone(value): return list(value) if isinstance(value, (list, tuple)) else value
def norm(value): return tuple(value) if isinstance(value, (list, tuple)) else value
def close(left, right): return abs(float(left)-float(right)) <= 4e-4*max(1.0,abs(float(left)),abs(float(right)))
def struct_text(value):
    exporter = getattr(value, "export_text", None)
    return exporter() if callable(exporter) else str(value)
def defaults():
    cls = unreal.load_class(None, DIRECTOR_CLASS); require(cls is not None, "class"); return unreal.get_default_object(cls)
def world():
    value = unreal.find_object(None, WORLD); require(value is not None, "world"); return value
def director():
    controller = unreal.GameplayStatics.get_player_controller(world(), 0); require(controller is not None, "controller")
    cls = unreal.load_class(None, DIRECTOR_CLASS); items = controller.get_components_by_class(cls)
    require(len(items) == 1, f"director:{len(items)}"); return items[0]
def camera_component(obj):
    actor = get(obj, "DroneCameraRef"); require(actor is not None, "drone-camera-ref")
    items = actor.get_components_by_class(unreal.CineCameraComponent); require(len(items) == 1, f"camera-components:{len(items)}"); return items[0]
def native_snapshot(camera):
    return (struct_text(get(camera,"filmback")),float(get(camera,"current_focal_length")),float(get(camera,"current_aperture")),struct_text(get(camera,"focus_settings")),struct_text(get(camera,"post_process_settings")))
def stage(obj, frame):
    preset,width,height,values=frame
    for name,value in (("CameraChannelResultFilmbackPresetIdV1",preset),("CameraChannelResultFilmbackSensorWidthMmV1",width),("CameraChannelResultFilmbackSensorHeightMmV1",height),("CameraChannelResultValuesV1",list(values)),("CameraChannelResultVelocitiesV1",[0.0]*13),("CameraChannelResultAccelerationsV1",[0.0]*13),("CameraChannelResultCompleteV1",True),("CameraChannelResultValidV1",True)): set_(obj,name,value)
def assert_native(camera, frame, label):
    _preset,width,height,values=frame; film=get(camera,"filmback"); focus=get(camera,"focus_settings"); post=get(camera,"post_process_settings")
    actual=(get(film,"sensor_width"),get(film,"sensor_height"),get(camera,"current_focal_length"),get(camera,"current_aperture"),get(focus,"manual_focus_distance"),get(post,"auto_exposure_bias"),get(post,"bloom_intensity"),get(post,"vignette_intensity"),get(post,"motion_blur_amount"),get(post,"scene_fringe_intensity"))
    expected=(width,height,values[0],values[1],values[2],values[4],values[5],values[6],values[9],values[10])
    require(all(close(a,b) for a,b in zip(actual,expected)),f"{label}:native:{actual}")
def checks():
    obj=director()
    if bool(get(obj,"DroneModeActive")): obj.call_method("ExitDroneMode")
    obj.call_method("EnterDroneMode")
    camera=camera_component(obj); baseline=native_snapshot(camera)
    for index,frame in enumerate(FRAMES):
        stage(obj,frame); staged=tuple(norm(get(obj,name)) for name in CHANNEL_RESULTS); obj.call_method("ApplyEvaluatedCameraChannelFrameV1")
        require(bool(get(obj,"CameraApplyResultValidV1")),f"frame-{index}:{get(obj,'CameraApplyFailureCodeV1')}")
        require(tuple(norm(get(obj,name)) for name in CHANNEL_RESULTS)==staged,f"frame-{index}:inputs"); assert_native(camera,frame,f"frame-{index}")
    baseline_before=(tuple(struct_text(get(obj,name)) for name in ("CameraApplyBaselineFilmbackSettingsV1","CameraApplyBaselineFocusSettingsV1","CameraApplyBaselinePostProcessSettingsV1")),tuple(get(obj,"CameraApplyBaselineTargetValuesV1")))
    obj.call_method("CaptureCameraEngineStateV1")
    baseline_after=(tuple(struct_text(get(obj,name)) for name in ("CameraApplyBaselineFilmbackSettingsV1","CameraApplyBaselineFocusSettingsV1","CameraApplyBaselinePostProcessSettingsV1")),tuple(get(obj,"CameraApplyBaselineTargetValuesV1")))
    require(baseline_before==baseline_after,"repeated-capture")
    invalid=list(FRAMES[0][3]);invalid[3]=0.25;stage(obj,("unsupported",36.0,24.0,tuple(invalid)));before=native_snapshot(camera);count=int(get(obj,"CameraApplyAppliedFrameCountV1"));obj.call_method("ApplyEvaluatedCameraChannelFrameV1")
    require(not bool(get(obj,"CameraApplyResultValidV1")),"unsupported-accepted");require(native_snapshot(camera)==before,"unsupported-write");require(int(get(obj,"CameraApplyAppliedFrameCountV1"))==count,"unsupported-count")
    obj.call_method("RestoreCameraEngineStateV1");require(native_snapshot(camera)==baseline,"exact-restore");require(not bool(get(obj,"CameraApplySessionActiveV1")),"active-after-restore")
    obj.call_method("RestoreCameraEngineStateV1");require(native_snapshot(camera)==baseline,"repeat-restore")
    obj.call_method("ExitDroneMode");require(not bool(get(obj,"DroneModeActive")),"exit-drone-mode")
    emit("PLAYER_OWNED_DIRECTOR",True);emit("FORWARD_REVERSE_FRAMES",2);emit("UNSUPPORTED_ZERO_WRITE",True);emit("EXACT_NATIVE_RESTORE",True);emit("GAME_WORLD_RESULT","PASS")
def restore(state):
    if state.get("restored") or not state.get("originals"): return
    for name,value in state["originals"].items(): set_(state["defaults"],name,clone(value))
    state["restored"]=True;emit("DEFAULTS_RESTORED",all(norm(get(state["defaults"],name))==norm(value) for name,value in state["originals"].items()))
def finish(success):
    state=globals().get("_EDD_CAMERA_ENGINE_PIE_STATE");restore(state)
    if state and state.get("callback") is not None: unreal.unregister_slate_post_tick_callback(state["callback"]);state["callback"]=None
    emit("AUTOMATIC_RESULT","PASS" if success else "FAIL")
def tick(_delta):
    state=globals()["_EDD_CAMERA_ENGINE_PIE_STATE"]
    try:
        subsystem=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        if state["stage"]=="prepare":
            require(not subsystem.is_in_play_in_editor(),"already-PIE");require(subsystem.load_level(SOURCE),"load");state["defaults"]=defaults();state["originals"]={name:clone(get(state["defaults"],name)) for name in DEFAULT_NAMES};state["stage"]="request";state["at"]=time.monotonic();emit("SOURCE_LEVEL_READY",SOURCE);return
        if state["stage"]=="request":
            if time.monotonic()-state["at"]<.5:return
            subsystem.editor_request_begin_play();state["stage"]="wait";emit("PIE_START_REQUESTED",True);return
        if state["stage"]=="wait":
            try: component=director();require(component.get_owner().has_actor_begun_play(),"BeginPlay")
            except Exception: require(time.monotonic()-state["armed"]<TIMEOUT,"startup-timeout");return
            state["stage"]="settle";state["at"]=time.monotonic();return
        if state["stage"]=="settle":
            if time.monotonic()-state["at"]<1.0:return
            checks();subsystem.editor_request_end_play();state["stage"]="end";return
        if state["stage"]=="end":
            if subsystem.is_in_play_in_editor():require(time.monotonic()-state["armed"]<TIMEOUT,"teardown-timeout");return
            state["stage"]="complete";finish(True)
    except Exception as error:
        unreal.log_error(f"{PREFIX}|AUTOMATIC_EXCEPTION|{error}\n{traceback.format_exc()}")
        try: unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
        finally: state["stage"]="failed";finish(False)
old=globals().get("_EDD_CAMERA_ENGINE_PIE_STATE")
if old and old.get("callback") is not None: unreal.unregister_slate_post_tick_callback(old["callback"])
_EDD_CAMERA_ENGINE_PIE_STATE={"stage":"prepare","armed":time.monotonic(),"at":time.monotonic(),"callback":None,"defaults":None,"originals":None,"restored":False}
_EDD_CAMERA_ENGINE_PIE_STATE["callback"]=unreal.register_slate_post_tick_callback(tick);emit("ARMED",True)
