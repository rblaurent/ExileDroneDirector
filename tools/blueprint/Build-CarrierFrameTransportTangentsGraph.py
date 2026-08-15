"""Build deterministic nearest-nonzero carrier-frame tangents."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "BuildCarrierFrameTangentsV1"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_carrier_tangent_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name: str, kind: str, array: bool = False) -> None:
    category, subcategory, obj = {
        "bool": ("bool", "", "None"), "int": ("int", "", "None"),
        "real": ("real", "double", "None"), "string": ("string", "", "None"),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
    }[kind]
    def mutate(line: str) -> str:
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f"PinType.PinSubCategoryObject={obj}", line, 1)
        return re.sub(r"PinType.ContainerType=(?:None|Array)", f"PinType.ContainerType={'Array' if array else 'None'}", line, 1)
    node.mutate_pin(pin_name, mutate)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    scalar = load(args.project_root)
    bp = scalar.load_helpers(args.project_root)
    forms = scalar.load_templates(args.project_root, bp)
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    reset = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-carrier-frame-transport-v1.eddgraph")
    loops = bp.read_blocks(args.project_root / "tools/blueprint/templates/adaptive-arc-for-loop-with-break-node-form.eddgraph")
    marker = bp.read_blocks(args.project_root / "tools/blueprint/templates/path-preview-marker-node-forms.eddgraph")
    translation = bp.read_blocks(args.project_root / "tools/blueprint/snippets/apply-translation-input.eddgraph")
    orientation = bp.read_blocks(args.project_root / "tools/blueprint/templates/orientation-compiler-native-node-forms.eddgraph")
    forms.update(
        array_add=bp.find_block(capture, r'MemberName="Array_Add"'),
        array_clear=bp.find_block(reset, r'MemberName="Array_Clear"'),
        array_length=bp.find_block(edit, r'MemberName="Array_Length"'),
        array_item=bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
        loop=bp.find_block(loops, r"StandardMacros:ForLoopWithBreak"),
        make_vector=bp.find_block(marker, r'MemberName="MakeVector"'),
        vector_math=bp.find_block(translation, r'MemberName="Multiply_VectorVector"'),
        vector_size=bp.find_block(orientation, r'MemberName="VSize"'),
    )
    builder = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name: str, kind: str, array: bool = False):
        scalar.retarget_variable(node, name, "real" if kind in ("int", "vector") else kind)
        pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind, array)
    def get(name, kind, x, y, array=False):
        node = builder.add(f"get_{name}_{len(builder.nodes)}", "get", x, y); variable(node, name, kind, array); return node
    def set_value(name, kind, x, y, default=None):
        node = builder.add(f"set_{name}_{len(builder.nodes)}", "set", x, y); variable(node, name, kind)
        if default is not None: scalar.set_default(node, name, default)
        return node
    def retarget(node, name, kinds):
        scalar.retarget_function(node, name)
        for pin, kind in kinds.items(): pin_kind(node, pin, kind)
        return node
    def math(name, left, left_pin, x, y, right=None, right_pin=None, default=None, kind="int"):
        node = builder.add(f"math_{name}_{len(builder.nodes)}", "math", x, y)
        retarget(node, name, {"A":kind,"B":kind,"ReturnValue":kind}); bp.connect(left, left_pin, node, "A")
        if right is None: scalar.set_default(node, "B", default)
        else: bp.connect(right, right_pin, node, "B")
        return node
    def compare(name, left, left_pin, x, y, right=None, right_pin=None, default=None, kind="int"):
        node = builder.add(f"compare_{name}_{len(builder.nodes)}", "compare", x, y)
        retarget(node, name, {"A":kind,"B":kind,"ReturnValue":"bool"}); bp.connect(left, left_pin, node, "A")
        if right is None: scalar.set_default(node, "B", default)
        else: bp.connect(right, right_pin, node, "B")
        return node
    def boolean_and(left, left_pin, right, right_pin, x, y):
        return compare("BooleanAND", left, left_pin, x, y, right, right_pin, kind="bool")
    def array_node(form, source, source_pin, x, y):
        node = builder.add(f"{form}_{len(builder.nodes)}", form, x, y)
        target_pin = "Array" if form == "array_item" else "TargetArray"
        pin_kind(node, target_pin, "vector", True)
        if form == "array_item": pin_kind(node, "Output", "vector")
        elif form == "array_add": pin_kind(node, "NewItem", "vector"); pin_kind(node, "ReturnValue", "int")
        elif form == "array_length": pin_kind(node, "ReturnValue", "int")
        bp.connect(source, source_pin, node, target_pin); return node
    def item(source, source_pin, index, index_pin, x, y):
        node = array_node("array_item", source, source_pin, x, y); bp.connect(index, index_pin, node, "Dimension 1"); return node
    def vector_math(name, left, left_pin, right, right_pin, x, y):
        node = builder.add(f"vector_{name}_{len(builder.nodes)}", "vector_math", x, y)
        retarget(node, name, {"A":"vector","B":"vector","ReturnValue":"vector"}); bp.connect(left,left_pin,node,"A");bp.connect(right,right_pin,node,"B");return node
    def size(value, pin, x, y):
        node = builder.add(f"size_{len(builder.nodes)}", "vector_size", x, y)
        pin_kind(node,"A","vector");pin_kind(node,"ReturnValue","real");bp.connect(value,pin,node,"A");return node
    def normalize(value, pin, magnitude, magnitude_pin, x, y):
        denominator = builder.add(f"denominator_{len(builder.nodes)}", "make_vector", x, y)
        for axis in "XYZ": pin_kind(denominator,axis,"real");bp.connect(magnitude,magnitude_pin,denominator,axis)
        pin_kind(denominator,"ReturnValue","vector")
        return vector_math("Divide_VectorVector",value,pin,denominator,"ReturnValue",x+256,y)
    def candidate(left, left_pin, right, right_pin, x, y):
        delta = vector_math("Subtract_VectorVector",left,left_pin,right,right_pin,x,y)
        magnitude = size(delta,"ReturnValue",x+256,y)
        nonzero = compare("Greater_DoubleDouble",magnitude,"ReturnValue",x+512,y,default="1e-9",kind="real")
        unit = normalize(delta,"ReturnValue",magnitude,"ReturnValue",x+768,y)
        return nonzero, unit

    positions = get("CarrierFrameInputPositionsV1","vector",0,0,True)
    tangents = get("CarrierFrameCandidateTangentsV1","vector",0,224,True)
    validation = get("CarrierFrameScratchValidV1","bool",0,448)
    count = array_node("array_length",positions,"CarrierFrameInputPositionsV1",320,0)
    last = math("Subtract_IntInt",count,"ReturnValue",320,160,default="1")
    clear = array_node("array_clear",tangents,"CarrierFrameCandidateTangentsV1",256,3200)
    stage_guard = builder.add("validation_guard","branch",512,3200)
    bp.connect(builder.entry,"then",clear,"execute");bp.connect(clear,"then",stage_guard,"execute");bp.connect(validation,"CarrierFrameScratchValidV1",stage_guard,"Condition")
    outer = builder.add("outer_loop","loop",768,3200);scalar.set_default(outer,"FirstIndex","0");bp.connect(last,"ReturnValue",outer,"LastIndex");bp.connect(stage_guard,"then",outer,"Execute")
    store_index = set_value("CarrierFrameScratchIndexV1","int",1024,3200);bp.connect(outer,"Index",store_index,"CarrierFrameScratchIndexV1");bp.connect(outer,"LoopBody",store_index,"execute")
    reset_found = set_value("CarrierFrameScratchValidV1","bool",1280,3200,"false");bp.connect(store_index,"then",reset_found,"execute")
    index_value = get("CarrierFrameScratchIndexV1","int",1024,640)
    has_previous = compare("Greater_IntInt",index_value,"CarrierFrameScratchIndexV1",1280,640,default="0")
    has_next = compare("Less_IntInt",index_value,"CarrierFrameScratchIndexV1",1280,800,last,"ReturnValue")
    central_possible = boolean_and(has_previous,"ReturnValue",has_next,"ReturnValue",1536,720)
    central_guard = builder.add("central_possible","branch",1536,3200);bp.connect(reset_found,"then",central_guard,"execute");bp.connect(central_possible,"ReturnValue",central_guard,"Condition")
    previous_index = math("Subtract_IntInt",index_value,"CarrierFrameScratchIndexV1",1792,560,default="1")
    next_index = math("Add_IntInt",index_value,"CarrierFrameScratchIndexV1",1792,880,default="1")
    previous_item = item(positions,"CarrierFrameInputPositionsV1",previous_index,"ReturnValue",2048,560)
    next_item = item(positions,"CarrierFrameInputPositionsV1",next_index,"ReturnValue",2048,880)
    central_nonzero, central_unit = candidate(next_item,"Output",previous_item,"Output",2304,720)
    central_nonzero_guard = builder.add("central_nonzero","branch",3840,3200);bp.connect(central_guard,"then",central_nonzero_guard,"execute");bp.connect(central_nonzero,"ReturnValue",central_nonzero_guard,"Condition")
    store_central = set_value("CarrierFrameScratchForwardV1","vector",4096,3040);bp.connect(central_unit,"ReturnValue",store_central,"CarrierFrameScratchForwardV1");bp.connect(central_nonzero_guard,"then",store_central,"execute")
    accept_central = set_value("CarrierFrameScratchValidV1","bool",4352,3040,"true");bp.connect(store_central,"then",accept_central,"execute")

    inner = builder.add("distance_loop","loop",4096,3360);scalar.set_default(inner,"FirstIndex","1");bp.connect(last,"ReturnValue",inner,"LastIndex")
    bp.connect(central_guard,"else",inner,"Execute");bp.connect(central_nonzero_guard,"else",inner,"Execute")
    found_value = get("CarrierFrameScratchValidV1","bool",4096,1120)
    not_found = compare("EqualEqual_BoolBool",found_value,"CarrierFrameScratchValidV1",4352,1120,default="false",kind="bool")
    search_guard = builder.add("search_guard","branch",4352,3360);bp.connect(inner,"LoopBody",search_guard,"execute");bp.connect(not_found,"ReturnValue",search_guard,"Condition")
    plus_index = math("Add_IntInt",index_value,"CarrierFrameScratchIndexV1",4608,1280,inner,"Index")
    plus_available = compare("Less_IntInt",plus_index,"ReturnValue",4864,1280,count,"ReturnValue")
    plus_guard = builder.add("plus_available","branch",4864,3360);bp.connect(search_guard,"then",plus_guard,"execute");bp.connect(plus_available,"ReturnValue",plus_guard,"Condition")
    current_item = item(positions,"CarrierFrameInputPositionsV1",index_value,"CarrierFrameScratchIndexV1",5120,1120)
    plus_item = item(positions,"CarrierFrameInputPositionsV1",plus_index,"ReturnValue",5120,1440)
    plus_nonzero, plus_unit = candidate(plus_item,"Output",current_item,"Output",5376,1280)
    plus_nonzero_guard = builder.add("plus_nonzero","branch",6912,3280);bp.connect(plus_guard,"then",plus_nonzero_guard,"execute");bp.connect(plus_nonzero,"ReturnValue",plus_nonzero_guard,"Condition")
    store_plus = set_value("CarrierFrameScratchForwardV1","vector",7168,3120);bp.connect(plus_unit,"ReturnValue",store_plus,"CarrierFrameScratchForwardV1");bp.connect(plus_nonzero_guard,"then",store_plus,"execute")
    accept_plus = set_value("CarrierFrameScratchValidV1","bool",7424,3120,"true");bp.connect(store_plus,"then",accept_plus,"execute");bp.connect(accept_plus,"then",inner,"Break")

    minus_index = math("Subtract_IntInt",index_value,"CarrierFrameScratchIndexV1",7168,1760,inner,"Index")
    minus_available = compare("GreaterEqual_IntInt",minus_index,"ReturnValue",7424,1760,default="0")
    minus_guard = builder.add("minus_available","branch",7680,3440)
    bp.connect(plus_guard,"else",minus_guard,"execute");bp.connect(plus_nonzero_guard,"else",minus_guard,"execute");bp.connect(minus_available,"ReturnValue",minus_guard,"Condition")
    minus_item = item(positions,"CarrierFrameInputPositionsV1",minus_index,"ReturnValue",7680,1760)
    minus_nonzero, minus_unit = candidate(current_item,"Output",minus_item,"Output",7936,1760)
    minus_nonzero_guard = builder.add("minus_nonzero","branch",9472,3440);bp.connect(minus_guard,"then",minus_nonzero_guard,"execute");bp.connect(minus_nonzero,"ReturnValue",minus_nonzero_guard,"Condition")
    store_minus = set_value("CarrierFrameScratchForwardV1","vector",9728,3280);bp.connect(minus_unit,"ReturnValue",store_minus,"CarrierFrameScratchForwardV1");bp.connect(minus_nonzero_guard,"then",store_minus,"execute")
    accept_minus = set_value("CarrierFrameScratchValidV1","bool",9984,3280,"true");bp.connect(store_minus,"then",accept_minus,"execute");bp.connect(accept_minus,"then",inner,"Break")

    tangent_ready = get("CarrierFrameScratchValidV1","bool",9984,2400)
    tangent_guard = builder.add("tangent_ready","branch",10240,3360);bp.connect(inner,"Completed",tangent_guard,"execute");bp.connect(tangent_ready,"CarrierFrameScratchValidV1",tangent_guard,"Condition")
    tangent_value = get("CarrierFrameScratchForwardV1","vector",10240,2560)
    append = array_node("array_add",tangents,"CarrierFrameCandidateTangentsV1",10496,3200);bp.connect(tangent_value,"CarrierFrameScratchForwardV1",append,"NewItem")
    bp.connect(accept_central,"then",append,"execute");bp.connect(tangent_guard,"then",append,"execute")
    missing_valid = set_value("CarrierFrameScratchValidV1","bool",10496,3520,"false");missing_failure=set_value("CarrierFrameFailureCodeV1","string",10752,3520,"tangent_missing")
    bp.connect(tangent_guard,"else",missing_valid,"execute");bp.connect(missing_valid,"then",missing_failure,"execute");bp.connect(missing_failure,"then",outer,"Break")

    tangent_count = array_node("array_length",tangents,"CarrierFrameCandidateTangentsV1",11008,2560)
    count_ok = compare("EqualEqual_IntInt",tangent_count,"ReturnValue",11264,2560,count,"ReturnValue")
    final_valid = get("CarrierFrameScratchValidV1","bool",11008,2720)
    complete = boolean_and(count_ok,"ReturnValue",final_valid,"CarrierFrameScratchValidV1",11520,2640)
    complete_guard = builder.add("complete_guard","branch",11776,3200);bp.connect(outer,"Completed",complete_guard,"execute");bp.connect(complete,"ReturnValue",complete_guard,"Condition")
    clear_failure=set_value("CarrierFrameFailureCodeV1","string",12032,3120,"");publish=set_value("CarrierFrameScratchValidV1","bool",12288,3120,"true")
    bp.connect(complete_guard,"then",clear_failure,"execute");bp.connect(clear_failure,"then",publish,"execute")
    fail_valid=set_value("CarrierFrameScratchValidV1","bool",12032,3440,"false");fail_code=set_value("CarrierFrameFailureCodeV1","string",12288,3440,"tangent_build_failed")
    bp.connect(complete_guard,"else",fail_valid,"execute");bp.connect(fail_valid,"then",fail_code,"execute")

    full="\n".join(node.text for node in builder.nodes)+"\n";args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(full,encoding="utf-8")
    if args.paste_output:
        body=[re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",node.text) for node in builder.nodes[1:]]
        args.paste_output.parent.mkdir(parents=True,exist_ok=True);args.paste_output.write_text("\n".join(body)+"\n",encoding="utf-8")


if __name__ == "__main__": main()
