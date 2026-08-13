"""Build distinct authored-gimbal samples on the accepted source schedule."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "BuildAirframeSourceGimbalSamplesV1"
TARGET_CLASS = '"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_airframe_source_gimbal_samples_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def kind(node, pin, value, array=False):
    category, subcategory, obj = {
        "bool": ("bool", "", "None"), "int": ("int", "", "None"), "real": ("real", "double", "None"),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
        "quat": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Quat\'"'),
    }[value]
    def mutate(line):
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f"PinType.PinSubCategoryObject={obj}", line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)
    node.mutate_pin(pin, mutate)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args(); scalar = load(args.project_root); bp = scalar.load_helpers(args.project_root); forms = scalar.load_templates(args.project_root, bp)
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    reset = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-airframe-source-sampling-v1.eddgraph")
    sync = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph")
    loops = bp.read_blocks(args.project_root / "tools/blueprint/templates/adaptive-arc-for-loop-with-break-node-form.eddgraph")
    calls = bp.read_blocks(args.project_root / "tools/blueprint/snippets/activate-drone-view.eddgraph")
    forms.update({
        "array_add": bp.find_block(capture, r'MemberName="Array_Add"'), "array_clear": bp.find_block(reset, r'MemberName="Array_Clear"'),
        "length": bp.find_block(edit, r'MemberName="Array_Length"'), "item": bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
        "convert": bp.find_block(playback, r'MemberName="Conv_IntToDouble"'), "foreach": bp.find_block(sync, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_MacroInstance"),
        "loop": bp.find_block(loops, r"StandardMacros:ForLoopWithBreak"), "self_call": bp.find_block(calls, r'MemberName="SwitchToDroneView"'),
    })
    b = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name, value, array=False):
        scalar.retarget_variable(node, name, "vector" if value == "quat" else ("real" if value == "int" else value)); kind(node, name, value, array)
        if "Output_Get" in node.pins: kind(node, "Output_Get", value, array)
    def get(name, value, x, y, array=False):
        node = b.add(f"get_{name}_{len(b.nodes)}", "get", x, y); variable(node, name, value, array); return node
    def set_(name, value, x, y, default=None, array=False):
        node = b.add(f"set_{name}_{len(b.nodes)}", "set", x, y); variable(node, name, value, array)
        if default is not None: scalar.set_default(node, name, default)
        return node
    def array_node(form, source, source_pin, value, x, y):
        node = b.add(f"{form}_{len(b.nodes)}", form, x, y); target = "TargetArray" if form in ("array_add", "array_clear", "length") else "Array"; kind(node, target, value, True)
        if form == "array_add": kind(node, "NewItem", value); kind(node, "ReturnValue", "int")
        elif form == "length": kind(node, "ReturnValue", "int")
        elif form == "item": kind(node, "Output", value)
        bp.connect(source, source_pin, node, target); return node
    def item(source, source_pin, value, index, index_pin, x, y):
        node = array_node("item", source, source_pin, value, x, y); bp.connect(index, index_pin, node, "Dimension 1"); return node
    def operation(member, left, left_pin, x, y, right=None, right_pin=None, default_b=None, value="real", result="bool"):
        node = b.add(f"op_{member}_{len(b.nodes)}", "compare" if result == "bool" else "math", x, y)
        scalar.retarget_function(node, member); kind(node, "A", value); kind(node, "B", value); kind(node, "ReturnValue", result)
        bp.connect(left, left_pin, node, "A")
        if right is None: scalar.set_default(node, "B", default_b)
        else: bp.connect(right, right_pin, node, "B")
        return node
    def and_all(values, x, y):
        current, current_pin = values[0]
        for index, (other, other_pin) in enumerate(values[1:]):
            current = operation("BooleanAND", current, current_pin, x + index * 224, y, other, other_pin, value="bool"); current_pin = "ReturnValue"
        return current
    def call(name, x, y):
        node = b.add(f"call_{name}_{len(b.nodes)}", "self_call", x, y); node.text = re.sub(r"FunctionReference=\([^\n]*\)", f'FunctionReference=(MemberName="{name}",bSelfContext=True)', node.text, 1)
        node.mutate_pin("self", lambda line: re.sub(r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"', f"PinType.PinSubCategoryObject={TARGET_CLASS}", line, 1)); return node

    output = get("AirframeSourceCandidateGimbalQuatsV1", "quat", 0, 0, True)
    clear = array_node("array_clear", output, "AirframeSourceCandidateGimbalQuatsV1", "quat", 256, 2880)
    bp.connect(b.entry, "then", clear, "execute")
    stage = get("AirframeSourceStageValidV1", "bool", 0, 160)
    guard = b.add("stage_guard", "branch", 512, 2880); bp.connect(clear, "then", guard, "execute"); bp.connect(stage, "AirframeSourceStageValidV1", guard, "Condition")
    authored = get("AirframeSourceInputGimbalWaypointQuatsV1", "quat", 0, 320, True)
    authored_durations = get("PositionRouteInputDurationsV1", "real", 0, 480, True)
    stage_quats = set_("OrientationTrackInputWaypointQuatsV1", "quat", 768, 2880, array=True)
    stage_durations = set_("OrientationTrackInputDurationsV1", "real", 1024, 2880, array=True)
    bp.connect(authored, "AirframeSourceInputGimbalWaypointQuatsV1", stage_quats, "OrientationTrackInputWaypointQuatsV1"); bp.connect(authored_durations, "PositionRouteInputDurationsV1", stage_durations, "OrientationTrackInputDurationsV1")
    bp.connect(guard, "then", stage_quats, "execute"); bp.connect(stage_quats, "then", stage_durations, "execute")
    compile_track = call("CompileOrientationTrackV1", 1280, 2880); bp.connect(stage_durations, "then", compile_track, "execute")

    orientation_valid = get("OrientationTrackCompileValidV1", "bool", 768, 720)
    source_total = get("AirframeSourceTotalSecondsV1", "real", 768, 880)
    position_total = get("PositionRouteCompiledTotalSecondsV1", "real", 768, 1040)
    orientation_total = get("OrientationTrackCompiledTotalSecondsV1", "real", 768, 1200)
    position_durations = get("PositionRouteCompiledDurationsV1", "real", 768, 1360, True)
    orientation_durations = get("OrientationTrackCompiledDurationsV1", "real", 768, 1520, True)
    position_starts = get("PositionRouteCompiledSegmentStartsV1", "real", 768, 1680, True)
    orientation_starts = get("OrientationTrackCompiledSegmentStartsV1", "real", 768, 1840, True)
    arrays = ((position_durations,"PositionRouteCompiledDurationsV1"),(orientation_durations,"OrientationTrackCompiledDurationsV1"),(position_starts,"PositionRouteCompiledSegmentStartsV1"),(orientation_starts,"OrientationTrackCompiledSegmentStartsV1"))
    lengths = [array_node("length", node, pin, "real", 1536, 1360 + i * 160) for i,(node,pin) in enumerate(arrays)]
    conditions = [
        (orientation_valid,"OrientationTrackCompileValidV1"),
        (operation("EqualEqual_DoubleDouble",source_total,"AirframeSourceTotalSecondsV1",1792,880,position_total,"PositionRouteCompiledTotalSecondsV1"),"ReturnValue"),
        (operation("EqualEqual_DoubleDouble",source_total,"AirframeSourceTotalSecondsV1",1792,1200,orientation_total,"OrientationTrackCompiledTotalSecondsV1"),"ReturnValue"),
        (operation("Greater_IntInt",lengths[0],"ReturnValue",1792,1360,default_b="0",value="int"),"ReturnValue"),
        *((operation("EqualEqual_IntInt",lengths[0],"ReturnValue",1792,1520+i*160,other,"ReturnValue",value="int"),"ReturnValue") for i,other in enumerate(lengths[1:])),
    ]
    valid = and_all(conditions,2240,2640)
    preflight = b.add("preflight", "branch", 3584, 2880); bp.connect(compile_track,"then",preflight,"execute"); bp.connect(valid,"ReturnValue",preflight,"Condition")
    reject = set_("AirframeSourceStageValidV1","bool",3840,3200,"false"); bp.connect(preflight,"else",reject,"execute")
    timeline = b.add("timeline_loop","foreach",3840,2240); kind(timeline,"Array","real",True); kind(timeline,"Array Element","real"); bp.connect(position_durations,"PositionRouteCompiledDurationsV1",timeline,"Array"); bp.connect(preflight,"then",timeline,"Exec")
    other_duration=item(orientation_durations,"OrientationTrackCompiledDurationsV1","real",timeline,"Array Index",4096,2080)
    position_start=item(position_starts,"PositionRouteCompiledSegmentStartsV1","real",timeline,"Array Index",4096,2240)
    orientation_start=item(orientation_starts,"OrientationTrackCompiledSegmentStartsV1","real",timeline,"Array Index",4096,2400)
    duration_equal=operation("EqualEqual_DoubleDouble",timeline,"Array Element",4352,2080,other_duration,"Output")
    start_equal=operation("EqualEqual_DoubleDouble",position_start,"Output",4352,2320,orientation_start,"Output")
    timeline_valid=operation("BooleanAND",duration_equal,"ReturnValue",4608,2240,start_equal,"ReturnValue",value="bool")
    item_guard=b.add("timeline_item_guard","branch",4864,2240); bp.connect(timeline,"LoopBody",item_guard,"execute"); bp.connect(timeline_valid,"ReturnValue",item_guard,"Condition")
    item_reject=set_("AirframeSourceStageValidV1","bool",5120,2480,"false"); bp.connect(item_guard,"else",item_reject,"execute")
    final_stage=get("AirframeSourceStageValidV1","bool",5120,1920); final_guard=b.add("timeline_guard","branch",5376,2240); bp.connect(timeline,"Completed",final_guard,"execute"); bp.connect(final_stage,"AirframeSourceStageValidV1",final_guard,"Condition")

    count=get("AirframeSourceExpectedSampleCountV1","int",5120,2720); last=operation("Subtract_IntInt",count,"AirframeSourceExpectedSampleCountV1",5376,2720,default_b="1",value="int",result="int")
    loop=b.add("sample_loop","loop",5632,2240); scalar.set_default(loop,"FirstIndex","0"); bp.connect(last,"ReturnValue",loop,"LastIndex"); bp.connect(final_guard,"then",loop,"Execute")
    loop_guard=b.add("sample_stage_guard","branch",5888,2240); bp.connect(loop,"LoopBody",loop_guard,"execute"); bp.connect(stage,"AirframeSourceStageValidV1",loop_guard,"Condition")
    set_index=set_("AirframeSourceSampleIndexV1","int",6144,2240); bp.connect(loop,"Index",set_index,"AirframeSourceSampleIndexV1"); bp.connect(loop_guard,"then",set_index,"execute")
    converted=b.add("converted_index","convert",6144,1920); bp.connect(loop,"Index",converted,"InInt")
    step=get("AirframeSourceInputFixedStepSecondsV1","real",5888,1760)
    raw=operation("Multiply_DoubleDouble",converted,"ReturnValue",6400,1920,step,"AirframeSourceInputFixedStepSecondsV1",result="real")
    elapsed=operation("FMin",raw,"ReturnValue",6656,1920,source_total,"AirframeSourceTotalSecondsV1",result="real")
    set_elapsed=set_("AirframeSourceSampleElapsedSecondsV1","real",6400,2240); bp.connect(elapsed,"ReturnValue",set_elapsed,"AirframeSourceSampleElapsedSecondsV1"); bp.connect(set_index,"then",set_elapsed,"execute")
    set_position=set_("PositionRouteInputElapsedSecondsV1","real",6656,2240); set_orientation=set_("OrientationTrackInputElapsedSecondsV1","real",6912,2240)
    bp.connect(elapsed,"ReturnValue",set_position,"PositionRouteInputElapsedSecondsV1"); bp.connect(elapsed,"ReturnValue",set_orientation,"OrientationTrackInputElapsedSecondsV1")
    bp.connect(set_elapsed,"then",set_position,"execute"); bp.connect(set_position,"then",set_orientation,"execute")
    evaluate_position=call("EvaluateCompiledPositionRouteV1",7168,2240); evaluate_gimbal=call("EvaluateCompiledOrientationTrackV1",7424,2240)
    bp.connect(set_orientation,"then",evaluate_position,"execute"); bp.connect(evaluate_position,"then",evaluate_gimbal,"execute")
    position_valid=get("PositionRouteResultValidV1","bool",7168,1120); gimbal_valid=get("OrientationTrackResultValidV1","bool",7424,1120)
    position_segment=get("PositionRouteResultSegmentIndexV1","int",7680,1120); gimbal_segment=get("OrientationTrackResultSegmentIndexV1","int",7680,1280)
    position_alpha=get("PositionRouteResultLocalTimeAlphaV1","real",7680,1440); gimbal_alpha=get("OrientationTrackResultAlphaV1","real",7680,1600)
    position_complete=get("PositionRouteResultCompleteV1","bool",7680,1760); gimbal_complete=get("OrientationTrackResultCompleteV1","bool",7680,1920)
    agreement=and_all([
        (position_valid,"PositionRouteResultValidV1"),(gimbal_valid,"OrientationTrackResultValidV1"),
        (operation("EqualEqual_IntInt",position_segment,"PositionRouteResultSegmentIndexV1",7936,1200,gimbal_segment,"OrientationTrackResultSegmentIndexV1",value="int"),"ReturnValue"),
        (operation("EqualEqual_DoubleDouble",position_alpha,"PositionRouteResultLocalTimeAlphaV1",7936,1520,gimbal_alpha,"OrientationTrackResultAlphaV1"),"ReturnValue"),
        (operation("EqualEqual_BoolBool",position_complete,"PositionRouteResultCompleteV1",7936,1840,gimbal_complete,"OrientationTrackResultCompleteV1",value="bool"),"ReturnValue"),
    ],8384,2080)
    result_guard=b.add("result_guard","branch",9504,2240); bp.connect(evaluate_gimbal,"then",result_guard,"execute"); bp.connect(agreement,"ReturnValue",result_guard,"Condition")
    sample_reject=set_("AirframeSourceStageValidV1","bool",9760,2560,"false"); bp.connect(result_guard,"else",sample_reject,"execute"); bp.connect(sample_reject,"then",loop,"Break")
    result=get("OrientationTrackResultQuatV1","quat",9504,1920)
    append=array_node("array_add",output,"AirframeSourceCandidateGimbalQuatsV1","quat",9760,2240); bp.connect(result,"OrientationTrackResultQuatV1",append,"NewItem"); bp.connect(result_guard,"then",append,"execute")

    full="\n".join(node.text for node in b.nodes)+"\n"; args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(full,encoding="utf-8")
    if args.paste_output:
        body=[re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",node.text) for node in b.nodes[1:]]; args.paste_output.parent.mkdir(parents=True,exist_ok=True); args.paste_output.write_text("\n".join(body)+"\n",encoding="utf-8")


if __name__ == "__main__": main()
