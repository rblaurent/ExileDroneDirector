"""Build atomic validation and publication of compiled flight profiles."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "CommitCompiledFlightProfilesV1"
TARGET_CLASS = '"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'
CHANNELS = (
    ("Ids", "string", "Id"), ("PathFollowWeights", "real", "PathFollowWeight"),
    ("HorizonStabilizationWeights", "real", "HorizonStabilizationWeight"),
    ("LookAheadSeconds", "real", "LookAheadSeconds"), ("BankGains", "real", "BankGain"),
    ("MaxBankDegrees", "real", "MaxBankDegrees"), ("CameraUptiltDegrees", "real", "CameraUptiltDegrees"),
    ("MaxAngularRatesDegreesPerSecond", "real", "MaxAngularRateDegreesPerSecond"),
    ("MaxAccelerationsCmPerSecondSquared", "real", "MaxAccelerationCmPerSecondSquared"),
    ("MaxJerksCmPerSecondCubed", "real", "MaxJerkCmPerSecondCubed"),
    ("MinimumTurnRadiiCm", "real", "MinimumTurnRadiusCm"),
)
BOUNDS = (
    ("0.0", "1.0", True), ("0.0", "1.0", True),
    ("0.0", "5.0", True), ("0.0", "2.0", True),
    ("0.0", "85.0", True), ("-45.0", "45.0", True),
    ("0.0", "720.0", False), ("0.0", "10000.0", False),
    ("0.0", "50000.0", False), ("0.0", "100000.0", False),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_flight_profile_commit_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin, kind, array=False):
    category, subcategory = {
        "bool": ("bool", ""), "int": ("int", ""), "real": ("real", "double"), "string": ("string", ""),
    }[kind]
    def mutate(line):
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', 'PinType.PinSubCategoryObject=None', line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)
    node.mutate_pin(pin, mutate)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    scalar = load(args.project_root)
    bp = scalar.load_helpers(args.project_root)
    forms = scalar.load_templates(args.project_root, bp)
    sync = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph")
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/update-linear-playback.eddgraph")
    repository = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/create-private-flypath-v1.eddgraph")
    forms.update({
        "foreach": bp.find_block(sync, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_MacroInstance"),
        "array_length": bp.find_block(edit, r'MemberName="Array_Length"'),
        "array_item": bp.find_block(playback, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),
        "call": bp.find_block(repository, r'MemberName="ValidateRecordV1"'),
    })
    b = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name, kind, array=False):
        scalar.retarget_variable(node, name, "real" if kind == "int" else kind)
        pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins: pin_kind(node, "Output_Get", kind)

    def get(name, kind, x, y, array=False):
        node = b.add(f"get_{name}_{len(b.nodes)}", "get", x, y); variable(node, name, kind, array); return node

    def set_(name, kind, x, y, default=None, array=False):
        node = b.add(f"set_{name}_{len(b.nodes)}", "set", x, y); variable(node, name, kind, array)
        if default is not None: scalar.set_default(node, name, default)
        return node

    def length(source, source_pin, kind, x, y):
        node = b.add(f"length_{len(b.nodes)}", "array_length", x, y); pin_kind(node, "TargetArray", kind, True); bp.connect(source, source_pin, node, "TargetArray"); return node

    def item(source, source_pin, kind, index, index_pin, x, y):
        node = b.add(f"item_{len(b.nodes)}", "array_item", x, y); pin_kind(node, "Array", kind, True); pin_kind(node, "Output", kind); bp.connect(source, source_pin, node, "Array"); bp.connect(index, index_pin, node, "Dimension 1"); return node

    def compare(member, left, left_pin, right, right_pin, kind, x, y):
        node = b.add(f"compare_{len(b.nodes)}", "compare", x, y); scalar.retarget_function(node, member)
        if member == "EqualEqual_StrStr":
            # Retarget the function reference and the hidden self/Target pin.
            # Leaving the latter on KismetMathLibrary compiles in the warm
            # editor but reconstructs with an obsolete-pin warning on a cold
            # load.
            node.text = node.text.replace("/Script/Engine.KismetMathLibrary", "/Script/Engine.KismetStringLibrary")
        for pin in ("A", "B"): pin_kind(node, pin, kind)
        pin_kind(node, "ReturnValue", "bool"); bp.connect(left, left_pin, node, "A")
        if right is None: scalar.set_default(node, "B", right_pin)
        else: bp.connect(right, right_pin, node, "B")
        return node

    def and_(left, left_pin, right, right_pin, x, y): return compare("BooleanAND", left, left_pin, right, right_pin, "bool", x, y)

    def call(member, x, y):
        node = b.add(f"call_{member}", "call", x, y)
        node.text = re.sub(r'FunctionReference=\([^\n]*\)', f'FunctionReference=(MemberName="{member}",bSelfContext=True)', node.text, 1)
        node.mutate_pin("self", lambda line: re.sub(r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"', f"PinType.PinSubCategoryObject={TARGET_CLASS}", line, 1)); return node

    invalidate = set_("FlightProfileCompileValidV1", "bool", 256, 2304, "false")
    bp.connect(b.entry, "then", invalidate, "execute")
    stage = get("FlightProfileStageValidV1", "bool", 0, 1920)
    count = get("FlightProfileInputSegmentCountV1", "int", 0, 2080)
    candidates = []
    lengths = []
    for index, (suffix, kind, _result) in enumerate(CHANNELS):
        name = f"FlightProfileCandidate{suffix}V1"
        getter = get(name, kind, 0, index * 160, True); candidates.append(getter)
        lengths.append(length(getter, name, kind, 320, index * 160))
    minimum = compare("GreaterEqual_IntInt", count, "FlightProfileInputSegmentCountV1", None, "1", "int", 576, 1760)
    maximum = compare("LessEqual_IntInt", count, "FlightProfileInputSegmentCountV1", None, "511", "int", 576, 1920)
    guards = [stage, minimum, maximum]
    guard_pins = ["FlightProfileStageValidV1", "ReturnValue", "ReturnValue"]
    for index, length_node in enumerate(lengths):
        guards.append(compare("EqualEqual_IntInt", length_node, "ReturnValue", count, "FlightProfileInputSegmentCountV1", "int", 832, index * 160))
        guard_pins.append("ReturnValue")
    combined, combined_pin = guards[0], guard_pins[0]
    for index, (guard, guard_pin) in enumerate(zip(guards[1:], guard_pins[1:])):
        combined = and_(combined, combined_pin, guard, guard_pin, 1088 + index * 224, 1760); combined_pin = "ReturnValue"
    pre = b.add("pre_guard", "branch", 4224, 2304)
    bp.connect(invalidate, "then", pre, "execute"); bp.connect(combined, combined_pin, pre, "Condition")
    reject = set_("FlightProfileStageValidV1", "bool", 4480, 2688, "false")
    bp.connect(pre, "else", reject, "execute")
    loop = b.add("candidate_loop", "foreach", 4480, 1920); pin_kind(loop, "Array", "string", True); pin_kind(loop, "Array Element", "string")
    bp.connect(candidates[0], "FlightProfileCandidateIdsV1", loop, "Array"); bp.connect(pre, "then", loop, "Exec")
    stage_resolver = set_("FlightProfileResolveInputIdV1", "string", 4736, 2304)
    bp.connect(loop, "Array Element", stage_resolver, "FlightProfileResolveInputIdV1"); bp.connect(loop, "LoopBody", stage_resolver, "execute")
    resolver = call("ResolveFlightProfilePresetV1", 4992, 2304); bp.connect(stage_resolver, "then", resolver, "execute")
    resolver_valid = get("FlightProfileResolveResultValidV1", "bool", 5248, 1920)
    resolver_id = get("FlightProfileResolveResultIdV1", "string", 5248, 2080)
    id_equal = compare("EqualEqual_StrStr", resolver_id, "FlightProfileResolveResultIdV1", loop, "Array Element", "string", 5504, 2080)
    item_guards = [resolver_valid, id_equal]; item_pins = ["FlightProfileResolveResultValidV1", "ReturnValue"]
    for index, ((suffix, kind, result_suffix), candidate) in enumerate(zip(CHANNELS[1:], candidates[1:])):
        candidate_name = f"FlightProfileCandidate{suffix}V1"
        resolver_name = f"FlightProfileResolveResult{result_suffix}V1"
        candidate_item = item(candidate, candidate_name, kind, loop, "Array Index", 5248, index * 160)
        resolver_value = get(resolver_name, kind, 5504, index * 160)
        equal = compare("EqualEqual_DoubleDouble", candidate_item, "Output", resolver_value, resolver_name, "real", 5760, index * 160)
        lower, upper, inclusive = BOUNDS[index]
        lower_guard = compare("GreaterEqual_DoubleDouble" if inclusive else "Greater_DoubleDouble", candidate_item, "Output", None, lower, "real", 6016, index * 160)
        upper_guard = compare("LessEqual_DoubleDouble", candidate_item, "Output", None, upper, "real", 6240, index * 160)
        item_guards.extend((equal, lower_guard, upper_guard)); item_pins.extend(("ReturnValue", "ReturnValue", "ReturnValue"))
    item_combined, item_pin = item_guards[0], item_pins[0]
    for index, (guard, guard_pin) in enumerate(zip(item_guards[1:], item_pins[1:])):
        item_combined = and_(item_combined, item_pin, guard, guard_pin, 6720 + index * 224, 1760); item_pin = "ReturnValue"
    item_branch = b.add("item_guard", "branch", 13824, 2304)
    bp.connect(resolver, "then", item_branch, "execute"); bp.connect(item_combined, item_pin, item_branch, "Condition"); bp.connect(item_branch, "else", reject, "execute")
    final = b.add("final_guard", "branch", 14080, 2304)
    bp.connect(loop, "Completed", final, "execute"); bp.connect(stage, "FlightProfileStageValidV1", final, "Condition")
    compiled_sets = []
    for index, ((suffix, kind, _result), candidate) in enumerate(zip(CHANNELS, candidates)):
        candidate_name = f"FlightProfileCandidate{suffix}V1"; compiled_name = f"FlightProfileCompiled{suffix}V1"
        setter = set_(compiled_name, kind, 14336 + index * 320, 2304, array=True)
        bp.connect(candidate, candidate_name, setter, compiled_name); compiled_sets.append(setter)
    bp.connect(final, "then", compiled_sets[0], "execute")
    for left, right in zip(compiled_sets, compiled_sets[1:]): bp.connect(left, "then", right, "execute")
    publish = set_("FlightProfileCompileValidV1", "bool", 17920, 2304, "true"); bp.connect(compiled_sets[-1], "then", publish, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"; args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True); args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__": main()
