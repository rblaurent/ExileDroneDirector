"""Build fail-closed absolute-time evaluation of compiled carrier frames."""
from __future__ import annotations
import argparse, importlib.util, re, sys
from pathlib import Path

FUNCTION = "EvaluateCompiledCarrierFrameTransportV1"
RESULTS = (
    ("CarrierFrameResultSegmentIndexV1", "int", "-1"),
    ("CarrierFrameResultAlphaV1", "real", "0.0"),
    ("CarrierFrameResultQuatV1", "quat", "0, 0, 0, 1"),
    ("CarrierFrameResultCompleteV1", "bool", "false"),
    ("CarrierFrameResultValidV1", "bool", "false"),
)


def load(root):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_carrier_eval_base", path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    return module


def kind(node, pin, value, array=False):
    category, subcategory, obj = {
        "bool": ("bool", "", "None"), "int": ("int", "", "None"),
        "real": ("real", "double", "None"),
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
    sync = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph")
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    linear = bp.read_blocks(args.project_root / "tools/blueprint/templates/linear-playback-node-forms.eddgraph")
    airframe = bp.read_blocks(args.project_root / "tools/blueprint/templates/airframe-gimbal-native-node-forms.eddgraph")
    quaternion = bp.read_blocks(args.project_root / "tools/blueprint/templates/orientation-compiler-native-node-forms.eddgraph")
    quat_eval = bp.read_blocks(args.project_root / "tools/blueprint/templates/trajectory-quaternion-native-node-forms.eddgraph")
    break_quat = bp.read_blocks(args.project_root / "tools/blueprint/templates/repository-codec-break-quat-node-form.eddgraph")
    translation = bp.read_blocks(args.project_root / "tools/blueprint/snippets/apply-translation-input.eddgraph")
    speed = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-speed-controls.eddgraph")
    forms.update(
        foreach=bp.find_block(sync, r"K2Node_MacroInstance"), length=bp.find_block(edit, r'MemberName="Array_Length"'),
        item=bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
        floor=bp.find_block(linear, r'MemberName="FFloor"'), convert=bp.find_block(playback, r'MemberName="Conv_IntToDouble"'),
        quat_finite=bp.find_block(quat_eval, r'MemberName="Quat_IsFinite"'), quat_size=bp.find_block(quaternion, r'MemberName="Quat_Size"'),
        quat_slerp=bp.find_block(quat_eval, r'MemberName="Quat_Slerp"'), axis_x=bp.find_block(airframe, r'MemberName="Quat_GetAxisX"'),
        break_quat=bp.find_block(break_quat, r'MemberName="BreakQuat"'), vsize=bp.find_block(quaternion, r'MemberName="VSize"'),
        vector_math=bp.find_block(translation, r'MemberName="Multiply_VectorVector"'), select=bp.find_block(speed, r'MemberName="SelectFloat"'),
    )
    b = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name, value, array=False):
        scalar.retarget_variable(node, name, "vector" if value == "quat" else ("real" if value == "int" else value)); kind(node, name, value, array)
        if "Output_Get" in node.pins: kind(node, "Output_Get", value, array)
    def get(name, value, x, y, array=False):
        node = b.add(f"get_{name}_{len(b.nodes)}", "get", x, y); variable(node, name, value, array); return node
    def set_(name, value, x, y, source=None, source_pin=None, default=None):
        node = b.add(f"set_{name}_{len(b.nodes)}", "set", x, y); variable(node, name, value)
        bp.connect(source, source_pin, node, name) if source else scalar.set_default(node, name, default)
        return node
    def retarget(node, name, pins):
        scalar.retarget_function(node, name)
        for pin, value in pins.items(): kind(node, pin, value)
        return node
    def add_form(name, x, y):
        block = forms[name]; match = bp.BLOCK_RE.match(block); node_class = match.group("class").rsplit(".", 1)[-1]; serial = b.serial.get(node_class, 0); b.serial[node_class] = serial + 1
        node = bp.Node.clone(f"{name}_{len(b.nodes)}", block, f"{node_class}_{serial}", x, y); b.nodes.append(node); return node
    def length(source, pin, value, x, y):
        node = add_form("length", x, y); kind(node, "TargetArray", value, True); kind(node, "ReturnValue", "int"); bp.connect(source, pin, node, "TargetArray"); return node
    def item(source, pin, index, index_pin, value, x, y):
        node = add_form("item", x, y); kind(node, "Array", value, True); kind(node, "Output", value); bp.connect(source, pin, node, "Array"); bp.connect(index, index_pin, node, "Dimension 1"); return node
    def compare(name, left, left_pin, x, y, right=None, right_pin=None, default=None, value="real"):
        node = b.add(f"compare_{name}_{len(b.nodes)}", "compare", x, y); retarget(node, name, {"A": value, "B": value, "ReturnValue": "bool"}); bp.connect(left, left_pin, node, "A")
        bp.connect(right, right_pin, node, "B") if right else scalar.set_default(node, "B", default)
        return node
    def math_node(name, left, left_pin, x, y, right=None, right_pin=None, default=None, value="real"):
        node = b.math("Add_DoubleDouble", x, y); retarget(node, name, {"A": value, "B": value, "ReturnValue": value}); bp.connect(left, left_pin, node, "A")
        bp.connect(right, right_pin, node, "B") if right else scalar.set_default(node, "B", default)
        return node
    def and_all(items, x, y):
        current, pin = items[0]
        for index, (other, other_pin) in enumerate(items[1:]):
            current = compare("BooleanAND", current, pin, x + index * 208, y, other, other_pin, value="bool"); pin = "ReturnValue"
        return current, pin

    tangents = get("CarrierFrameCompiledTangentsV1", "vector", 0, 0, True); quats = get("CarrierFrameCompiledQuatsV1", "quat", 0, 192, True)
    tangent_count = length(tangents, "CarrierFrameCompiledTangentsV1", "vector", 320, 0); quat_count = length(quats, "CarrierFrameCompiledQuatsV1", "quat", 320, 192)
    compile_valid = get("CarrierFrameCompileValidV1", "bool", 0, 384); elapsed = get("CarrierFrameInputElapsedSecondsV1", "real", 0, 576)
    total = get("CarrierFrameCompiledTotalSecondsV1", "real", 0, 768); step = get("CarrierFrameCompiledFixedStepSecondsV1", "real", 0, 960)

    resets = [set_(name, value, 256 + index * 256, 3200, default=default) for index, (name, value, default) in enumerate(RESULTS)]
    scratch_reset = set_("CarrierFrameScratchValidV1", "bool", 1536, 3200, default="false")
    bp.connect(b.entry, "then", resets[0], "execute")
    for left, right in zip((*resets, scratch_reset), (*resets[1:], scratch_reset)): bp.connect(left, "then", right, "execute")

    count_minus_two = math_node("Subtract_IntInt", tangent_count, "ReturnValue", 640, 1152, default="2", value="int")
    count_minus_one = math_node("Subtract_IntInt", tangent_count, "ReturnValue", 640, 1312, default="1", value="int")
    convert_minus_two = add_form("convert", 896, 1152); bp.connect(count_minus_two, "ReturnValue", convert_minus_two, "InInt")
    convert_minus_one = add_form("convert", 896, 1312); bp.connect(count_minus_one, "ReturnValue", convert_minus_one, "InInt")
    lower_time = math_node("Multiply_DoubleDouble", convert_minus_two, "ReturnValue", 1152, 1152, step, "CarrierFrameCompiledFixedStepSecondsV1")
    upper_time = math_node("Multiply_DoubleDouble", convert_minus_one, "ReturnValue", 1152, 1312, step, "CarrierFrameCompiledFixedStepSecondsV1")
    shape = [
        (compile_valid, "CarrierFrameCompileValidV1"), (b.finite(elapsed, "CarrierFrameInputElapsedSecondsV1", 640, 576), "ReturnValue"),
        (compare("GreaterEqual_IntInt", tangent_count, "ReturnValue", 640, 0, default="2", value="int"), "ReturnValue"),
        (compare("LessEqual_IntInt", tangent_count, "ReturnValue", 640, 128, default="65536", value="int"), "ReturnValue"),
        (compare("EqualEqual_IntInt", tangent_count, "ReturnValue", 640, 256, quat_count, "ReturnValue", value="int"), "ReturnValue"),
        (b.finite(total, "CarrierFrameCompiledTotalSecondsV1", 640, 768), "ReturnValue"),
        (compare("Greater_DoubleDouble", total, "CarrierFrameCompiledTotalSecondsV1", 864, 768, default="0.0"), "ReturnValue"),
        (compare("LessEqual_DoubleDouble", total, "CarrierFrameCompiledTotalSecondsV1", 1088, 768, default="3600.0"), "ReturnValue"),
        (b.finite(step, "CarrierFrameCompiledFixedStepSecondsV1", 640, 960), "ReturnValue"),
        (compare("GreaterEqual_DoubleDouble", step, "CarrierFrameCompiledFixedStepSecondsV1", 864, 960, default="0.004166666666666667"), "ReturnValue"),
        (compare("LessEqual_DoubleDouble", step, "CarrierFrameCompiledFixedStepSecondsV1", 1088, 960, default="0.5"), "ReturnValue"),
        (compare("Less_DoubleDouble", lower_time, "ReturnValue", 1408, 1152, total, "CarrierFrameCompiledTotalSecondsV1"), "ReturnValue"),
        (compare("LessEqual_DoubleDouble", total, "CarrierFrameCompiledTotalSecondsV1", 1408, 1312, upper_time, "ReturnValue"), "ReturnValue"),
    ]
    shape_ok, shape_pin = and_all(shape, 1792, 1440); shape_guard = b.add("shape_guard", "branch", 4288, 3200)
    bp.connect(scratch_reset, "then", shape_guard, "execute"); bp.connect(shape_ok, shape_pin, shape_guard, "Condition")
    stage_valid = set_("CarrierFrameScratchValidV1", "bool", 4544, 3120, default="true"); bp.connect(shape_guard, "then", stage_valid, "execute")

    loop = add_form("foreach", 4800, 3200); kind(loop, "Array", "vector", True); kind(loop, "Array Element", "vector"); kind(loop, "Array Index", "int")
    bp.connect(tangents, "CarrierFrameCompiledTangentsV1", loop, "Array"); bp.connect(stage_valid, "then", loop, "Exec")
    quat = item(quats, "CarrierFrameCompiledQuatsV1", loop, "Array Index", "quat", 4800, 640)
    tangent_size = add_form("vsize", 5024, 480); kind(tangent_size, "A", "vector"); kind(tangent_size, "ReturnValue", "real"); bp.connect(loop, "Array Element", tangent_size, "A")
    tangent_lower = compare("GreaterEqual_DoubleDouble", tangent_size, "ReturnValue", 5248, 400, default="0.999999")
    tangent_upper = compare("LessEqual_DoubleDouble", tangent_size, "ReturnValue", 5248, 560, default="1.000001")
    quat_finite = add_form("quat_finite", 5024, 720); kind(quat_finite, "Q", "quat"); kind(quat_finite, "ReturnValue", "bool"); bp.connect(quat, "Output", quat_finite, "Q")
    quat_size = add_form("quat_size", 5024, 880); kind(quat_size, "Q", "quat"); kind(quat_size, "ReturnValue", "real"); bp.connect(quat, "Output", quat_size, "Q")
    quat_lower = compare("GreaterEqual_DoubleDouble", quat_size, "ReturnValue", 5248, 800, default="0.999999")
    quat_upper = compare("LessEqual_DoubleDouble", quat_size, "ReturnValue", 5248, 960, default="1.000001")
    axis = add_form("axis_x", 5024, 1120); kind(axis, "Q", "quat"); kind(axis, "ReturnValue", "vector"); bp.connect(quat, "Output", axis, "Q")
    delta = add_form("vector_math", 5248, 1120); retarget(delta, "Subtract_VectorVector", {"A": "vector", "B": "vector", "ReturnValue": "vector"}); bp.connect(axis, "ReturnValue", delta, "A"); bp.connect(loop, "Array Element", delta, "B")
    delta_size = add_form("vsize", 5472, 1120); kind(delta_size, "A", "vector"); kind(delta_size, "ReturnValue", "real"); bp.connect(delta, "ReturnValue", delta_size, "A")
    aligned = compare("LessEqual_DoubleDouble", delta_size, "ReturnValue", 5696, 1120, default="0.000001")
    common, common_pin = and_all(((tangent_lower, "ReturnValue"), (tangent_upper, "ReturnValue"), (quat_finite, "ReturnValue"), (quat_lower, "ReturnValue"), (quat_upper, "ReturnValue"), (aligned, "ReturnValue")), 5920, 1280)
    common_guard = b.add("common_guard", "branch", 7168, 3200); bp.connect(loop, "LoopBody", common_guard, "execute"); bp.connect(common, common_pin, common_guard, "Condition")
    reject = set_("CarrierFrameScratchValidV1", "bool", 7424, 3360, default="false"); bp.connect(common_guard, "else", reject, "execute")
    first = compare("EqualEqual_IntInt", loop, "Array Index", 7168, 1440, default="0", value="int"); first_guard = b.add("first_guard", "branch", 7424, 3120); bp.connect(common_guard, "then", first_guard, "execute"); bp.connect(first, "ReturnValue", first_guard, "Condition")
    previous_index = math_node("Subtract_IntInt", loop, "Array Index", 7424, 1600, default="1", value="int"); previous = item(quats, "CarrierFrameCompiledQuatsV1", previous_index, "ReturnValue", "quat", 7648, 1600)
    breaks = []
    for label, source, y in (("previous", previous, 1440), ("current", quat, 1760)):
        node = add_form("break_quat", 7872, y); kind(node, "InQuat", "quat")
        for pin in "XYZW": kind(node, pin, "real")
        bp.connect(source, "Output", node, "InQuat"); breaks.append(node)
    products = []
    for index, pin in enumerate("XYZW"):
        node = b.add(f"dot_product_{pin}", "math", 8096, 1440 + index * 128); retarget(node, "Multiply_DoubleDouble", {"A": "real", "B": "real", "ReturnValue": "real"}); bp.connect(breaks[0], pin, node, "A"); bp.connect(breaks[1], pin, node, "B"); products.append(node)
    sums = []
    for index, (left, right) in enumerate(((products[0], products[1]), (products[2], products[3]))):
        node = b.add(f"dot_sum_{index}", "math", 8320, 1504 + index * 256); retarget(node, "Add_DoubleDouble", {"A": "real", "B": "real", "ReturnValue": "real"}); bp.connect(left, "ReturnValue", node, "A"); bp.connect(right, "ReturnValue", node, "B"); sums.append(node)
    quat_dot = b.add("quat_dot", "math", 8544, 1632); retarget(quat_dot, "Add_DoubleDouble", {"A": "real", "B": "real", "ReturnValue": "real"}); bp.connect(sums[0], "ReturnValue", quat_dot, "A"); bp.connect(sums[1], "ReturnValue", quat_dot, "B")
    hemisphere = compare("GreaterEqual_DoubleDouble", quat_dot, "ReturnValue", 8768, 1632, default="-0.000001"); hemisphere_guard = b.add("hemisphere_guard", "branch", 7648, 3120)
    bp.connect(first_guard, "else", hemisphere_guard, "execute"); bp.connect(hemisphere, "ReturnValue", hemisphere_guard, "Condition"); bp.connect(hemisphere_guard, "else", reject, "execute")

    sticky = get("CarrierFrameScratchValidV1", "bool", 8992, 1632); content_guard = b.add("content_guard", "branch", 7872, 3200)
    bp.connect(loop, "Completed", content_guard, "execute"); bp.connect(sticky, "CarrierFrameScratchValidV1", content_guard, "Condition")
    complete_test = compare("GreaterEqual_DoubleDouble", elapsed, "CarrierFrameInputElapsedSecondsV1", 8128, 2400, total, "CarrierFrameCompiledTotalSecondsV1")
    complete_guard = b.add("complete_guard", "branch", 8128, 3200); bp.connect(content_guard, "then", complete_guard, "execute"); bp.connect(complete_test, "ReturnValue", complete_guard, "Condition")
    last_quat = item(quats, "CarrierFrameCompiledQuatsV1", count_minus_one, "ReturnValue", "quat", 8352, 2080)
    complete_sets = [
        set_("CarrierFrameResultSegmentIndexV1", "int", 8384, 3040, count_minus_two, "ReturnValue"), set_("CarrierFrameResultAlphaV1", "real", 8640, 3040, default="1.0"),
        set_("CarrierFrameResultQuatV1", "quat", 8896, 3040, last_quat, "Output"), set_("CarrierFrameResultCompleteV1", "bool", 9152, 3040, default="true"),
        set_("CarrierFrameResultValidV1", "bool", 9408, 3040, default="true"),
    ]
    bp.connect(complete_guard, "then", complete_sets[0], "execute")
    for left, right in zip(complete_sets, complete_sets[1:]): bp.connect(left, "then", right, "execute")

    clamped = b.add("clamped_elapsed", "clamp", 8384, 3520); scalar.set_default(clamped, "Min", "0.0"); bp.connect(elapsed, "CarrierFrameInputElapsedSecondsV1", clamped, "Value"); bp.connect(total, "CarrierFrameCompiledTotalSecondsV1", clamped, "Max")
    quotient = math_node("Divide_DoubleDouble", clamped, "ReturnValue", 8640, 3520, step, "CarrierFrameCompiledFixedStepSecondsV1")
    segment = add_form("floor", 8896, 3520); bp.connect(quotient, "ReturnValue", segment, "A")
    segment_real = add_form("convert", 9152, 3520); bp.connect(segment, "ReturnValue", segment_real, "InInt")
    start_time = math_node("Multiply_DoubleDouble", segment_real, "ReturnValue", 9408, 3520, step, "CarrierFrameCompiledFixedStepSecondsV1")
    relative = math_node("Subtract_DoubleDouble", clamped, "ReturnValue", 9664, 3520, start_time, "ReturnValue")
    is_terminal = compare("EqualEqual_IntInt", segment, "ReturnValue", 9408, 3760, count_minus_two, "ReturnValue", value="int")
    terminal_duration = math_node("Subtract_DoubleDouble", total, "CarrierFrameCompiledTotalSecondsV1", 9664, 3760, start_time, "ReturnValue")
    duration = add_form("select", 9920, 3760); bp.connect(terminal_duration, "ReturnValue", duration, "A"); bp.connect(step, "CarrierFrameCompiledFixedStepSecondsV1", duration, "B"); bp.connect(is_terminal, "ReturnValue", duration, "bPickA")
    alpha = math_node("Divide_DoubleDouble", relative, "ReturnValue", 10176, 3520, duration, "ReturnValue")
    next_index = math_node("Add_IntInt", segment, "ReturnValue", 9920, 4000, default="1", value="int")
    start_quat = item(quats, "CarrierFrameCompiledQuatsV1", segment, "ReturnValue", "quat", 10176, 3840); end_quat = item(quats, "CarrierFrameCompiledQuatsV1", next_index, "ReturnValue", "quat", 10176, 4000)
    slerp = add_form("quat_slerp", 10432, 3920); bp.connect(start_quat, "Output", slerp, "A"); bp.connect(end_quat, "Output", slerp, "B"); bp.connect(alpha, "ReturnValue", slerp, "Alpha")
    active_sets = [
        set_("CarrierFrameResultSegmentIndexV1", "int", 10688, 3520, segment, "ReturnValue"), set_("CarrierFrameResultAlphaV1", "real", 10944, 3520, alpha, "ReturnValue"),
        set_("CarrierFrameResultQuatV1", "quat", 11200, 3520, slerp, "ReturnValue"), set_("CarrierFrameResultCompleteV1", "bool", 11456, 3520, default="false"),
        set_("CarrierFrameResultValidV1", "bool", 11712, 3520, default="true"),
    ]
    bp.connect(complete_guard, "else", active_sets[0], "execute")
    for left, right in zip(active_sets, active_sets[1:]): bp.connect(left, "then", right, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"; args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]]; args.paste_output.parent.mkdir(parents=True, exist_ok=True); args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__": main()
