"""Programmatic three-session PIE acceptance for independent carrier frames."""
from __future__ import annotations
import importlib,json,math,sys,time,traceback
from pathlib import Path
import unreal

PREFIX="EDD_CARRIER_FRAME_PIE";SOURCE_LEVEL_PATH="/Game/Dev/AlmostEmpty";WORLD_PATH="/Game/Dev/UEDPIE_0_AlmostEmpty.AlmostEmpty";CLIENT_CLASS_PATH="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C";TIMEOUT_SECONDS=120.;SCENARIOS=("partial_terminal","vertical_transport","fail_closed");ROOT=Path(__file__).resolve().parents[2];SCHEMA=json.loads((ROOT/"tools/trajectory/carrier_frame_transport_blueprint_schema.json").read_text(encoding="utf-8"));UPSTREAM=("AirframeDesiredStreamCompileValidV1","AirframeDesiredStreamInputPositionsV1","AirframeDesiredStreamInputTotalSecondsV1","AirframeDesiredStreamInputFixedStepSecondsV1");NAMES=tuple(spec["name"] for spec in SCHEMA["variables"])+UPSTREAM;AUTHORSHIP=("AirframePrebakeCompiledBodyQuatsV1","AirframePrebakeCompiledGimbalQuatsV1","AirframePrebakeCompiledBodyAngularRatesDegreesPerSecondV1","AirframePrebakeCompiledGimbalAngularRatesDegreesPerSecondV1");DOWNSTREAM=("CameraOperatorInputCarrierFrameQuatV1","CameraOperatorResultBodyQuatV1","CameraOperatorResultGimbalQuatV1")
CASES={"partial_terminal":(((0.,0.,0.),(2.,1.,.2),(4.,1.5,.4),(6.,1.,.8),(7.,.5,1.)),.65,.2,.64),"vertical_transport":(((0.,0.,0.),(0.,0.,2.),(0.,0.,4.),(0.,0.,7.)),.6,.2,.3)}
def emit(label,value):unreal.log(f"{PREFIX}|{label}|{value}")
def require(condition,message):
    if not condition:raise RuntimeError(f"{PREFIX}|FAIL|{message}")
def variants(name):snake="".join(("_"+char.lower()) if char.isupper() else char for char in name).lstrip("_");return name,unreal.Name(name),snake,unreal.Name(snake)
def get(obj,name):
    for candidate in variants(name):
        try:return obj.get_editor_property(candidate)
        except Exception:pass
    raise RuntimeError("missing property:"+name)
def set_(obj,name,value):
    for candidate in variants(name):
        try:obj.set_editor_property(candidate,value);return
        except Exception:pass
    raise RuntimeError("could not set property:"+name)
def clone(value):
    if isinstance(value,(list,tuple)):return [clone(item) for item in value]
    return value.copy() if hasattr(value,"copy") else value
def normalized(value):
    if isinstance(value,(list,tuple)):return tuple(normalized(item) for item in value)
    if isinstance(value,unreal.Vector):return float(value.x),float(value.y),float(value.z)
    if isinstance(value,unreal.Quat):return float(value.x),float(value.y),float(value.z),float(value.w)
    return value
def snapshot(obj,names):return tuple(normalized(get(obj,name)) for name in names)
def close(left,right,tolerance=7.5e-4):return abs(float(left)-float(right))<=tolerance*max(1.,abs(float(left)),abs(float(right)))
def vector_close(value,wanted):return all(close(a,b) for a,b in zip(normalized(value),wanted))
def same_rotation(value,wanted,tolerance=7.5e-4):
    actual=normalized(value);al=math.sqrt(sum(v*v for v in actual));bl=math.sqrt(sum(v*v for v in wanted));return al>0. and bl>0. and abs(sum(a*b for a,b in zip(actual,wanted))/(al*bl))>=1.-tolerance
def defaults():cls=unreal.load_class(None,CLIENT_CLASS_PATH);require(cls is not None,"class");return unreal.get_default_object(cls)
def pie_world():value=unreal.find_object(None,WORLD_PATH);require(value is not None,"PIE world");return value
def director(world):controller=unreal.GameplayStatics.get_player_controller(world,0);require(controller is not None,"controller");cls=unreal.load_class(None,CLIENT_CLASS_PATH);values=controller.get_components_by_class(cls);require(len(values)==1,f"director count:{len(values)}");return values[0]

sys.path.insert(0,str(ROOT/"tools/trajectory"));import carrier_frame_transport_reference as oracle;oracle=importlib.reload(oracle)
def stage_case(obj,scenario,originals):
    for name,value in originals.items():set_(obj,name,clone(value))
    if scenario=="fail_closed":positions,total,step=CASES["partial_terminal"][:3];valid=False
    else:positions,total,step,_elapsed=CASES[scenario];valid=True
    set_(obj,UPSTREAM[0],valid);set_(obj,UPSTREAM[1],[unreal.Vector(*point) for point in positions]);set_(obj,UPSTREAM[2],total);set_(obj,UPSTREAM[3],step)
def run_scenario(component,scenario):
    before_upstream=snapshot(component,UPSTREAM);before_external=snapshot(component,AUTHORSHIP+DOWNSTREAM);component.call_method("CompileCarrierFrameTransportV1");require(snapshot(component,UPSTREAM)==before_upstream,"upstream mutated");require(snapshot(component,AUTHORSHIP+DOWNSTREAM)==before_external,"external state mutated")
    if scenario=="fail_closed":
        require(not bool(get(component,"CarrierFrameCompileValidV1")),"invalid source compiled");require(not bool(get(component,"CarrierFrameResultValidV1")),"invalid source result");require(len(get(component,"CarrierFrameCompiledQuatsV1"))==0,"invalid publication");emit("FAIL_CLOSED_RESULT","PASS")
    else:
        positions,total,step,elapsed=CASES[scenario];track=oracle.compile_carrier_frame_transport_v1(positions,total,step);require(bool(get(component,"CarrierFrameCompileValidV1")),"compile invalid");require(len(get(component,"CarrierFrameCompiledTangentsV1"))==len(track.tangents),"tangent count");require(len(get(component,"CarrierFrameCompiledQuatsV1"))==len(track.rotations),"quat count")
        for index,(actual,wanted) in enumerate(zip(get(component,"CarrierFrameCompiledTangentsV1"),track.tangents)):require(vector_close(actual,wanted),f"tangent:{index}")
        set_(component,"CarrierFrameInputElapsedSecondsV1",elapsed);compiled=snapshot(component,("CarrierFrameCompiledTangentsV1","CarrierFrameCompiledQuatsV1","CarrierFrameCompiledTotalSecondsV1","CarrierFrameCompiledFixedStepSecondsV1","CarrierFrameCompileValidV1"));component.call_method("EvaluateCompiledCarrierFrameTransportV1");expected=oracle.evaluate_carrier_frame_transport_v1(track,elapsed)
        require(bool(get(component,"CarrierFrameResultValidV1")),"evaluation invalid");require(bool(get(component,"CarrierFrameResultCompleteV1"))==expected.complete,"complete");require(int(get(component,"CarrierFrameResultSegmentIndexV1"))==expected.segment_index,"segment");require(close(get(component,"CarrierFrameResultAlphaV1"),expected.alpha),"alpha");require(same_rotation(get(component,"CarrierFrameResultQuatV1"),expected.rotation),"rotation");require(snapshot(component,("CarrierFrameCompiledTangentsV1","CarrierFrameCompiledQuatsV1","CarrierFrameCompiledTotalSecondsV1","CarrierFrameCompiledFixedStepSecondsV1","CarrierFrameCompileValidV1"))==compiled,"compiled mutated");require(snapshot(component,AUTHORSHIP+DOWNSTREAM)==before_external,"evaluation external state")
        emit("PARTIAL_TERMINAL_RESULT" if scenario=="partial_terminal" else "VERTICAL_TRANSPORT_RESULT","PASS")
    emit("DISTINCT_BODY_GIMBAL_AUTHORSHIP_PRESERVED",True);emit("SCENARIO_RESULT",scenario+":PASS")
def restore(state):
    if state.get("restored") or not state.get("originals"):return
    target=defaults()
    for name,value in state["originals"].items():set_(target,name,clone(value))
    require(all(normalized(get(target,name))==normalized(value) for name,value in state["originals"].items()),"defaults not restored");state["restored"]=True;emit("DEFAULTS_RESTORED",True)
def finish(success):
    state=globals().get("_EDD_CARRIER_FRAME_PIE_STATE");restore(state)
    if state and state.get("callback") is not None:unreal.unregister_slate_post_tick_callback(state["callback"]);state["callback"]=None
    if success:emit("GAME_WORLD_RESULT","PASS")
    emit("AUTOMATIC_RESULT","PASS" if success else "FAIL")
def tick(_delta):
    state=globals()["_EDD_CARRIER_FRAME_PIE_STATE"]
    try:
        subsystem=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);require(time.monotonic()-state["armed_at"]<TIMEOUT_SECONDS,"overall timeout")
        if state["stage"]=="prepare":require(not subsystem.is_in_play_in_editor(),"PIE already running");require(subsystem.load_level(SOURCE_LEVEL_PATH),"load level");target=defaults();state["originals"]={name:clone(get(target,name)) for name in NAMES};stage_case(target,SCENARIOS[0],state["originals"]);state["stage"]="request";state["stage_at"]=time.monotonic();emit("SOURCE_LEVEL_READY",SOURCE_LEVEL_PATH);return
        if state["stage"]=="request":
            if time.monotonic()-state["stage_at"]<.5:return
            subsystem.editor_request_begin_play();state["stage"]="wait";emit("PIE_START_REQUESTED",SCENARIOS[state["scenario_index"]]);return
        if state["stage"]=="wait":
            try:component=director(pie_world());require(component.get_owner().has_actor_begun_play(),"BeginPlay")
            except Exception:return
            state["stage"]="settle";state["stage_at"]=time.monotonic();return
        if state["stage"]=="settle":
            if time.monotonic()-state["stage_at"]<1.:return
            run_scenario(director(pie_world()),SCENARIOS[state["scenario_index"]]);subsystem.editor_request_end_play();state["stage"]="end";return
        if state["stage"]=="end":
            if subsystem.is_in_play_in_editor():return
            state["scenario_index"]+=1
            if state["scenario_index"]==len(SCENARIOS):state["stage"]="complete";finish(True);return
            target=defaults();stage_case(target,SCENARIOS[state["scenario_index"]],state["originals"]);state["stage"]="request";state["stage_at"]=time.monotonic()
    except Exception as error:
        unreal.log_error(f"{PREFIX}|AUTOMATIC_EXCEPTION|{error}\n{traceback.format_exc()}")
        try:unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
        finally:state["stage"]="failed";finish(False)
old=globals().get("_EDD_CARRIER_FRAME_PIE_STATE")
if old and old.get("callback") is not None:unreal.unregister_slate_post_tick_callback(old["callback"])
_EDD_CARRIER_FRAME_PIE_STATE={"stage":"prepare","armed_at":time.monotonic(),"stage_at":time.monotonic(),"scenario_index":0,"callback":None,"originals":None,"restored":False};_EDD_CARRIER_FRAME_PIE_STATE["callback"]=unreal.register_slate_post_tick_callback(tick);emit("ARMED",True)
