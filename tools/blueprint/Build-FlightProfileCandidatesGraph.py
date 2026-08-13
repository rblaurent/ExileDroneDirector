"""Build per-segment flight-profile candidates through the canonical resolver."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "BuildFlightProfileCandidatesV1"
TARGET_CLASS = '"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'
CHANNELS = (
    ("Ids", "string", "Id"),
    ("PathFollowWeights", "real", "PathFollowWeight"),
    ("HorizonStabilizationWeights", "real", "HorizonStabilizationWeight"),
    ("LookAheadSeconds", "real", "LookAheadSeconds"),
    ("BankGains", "real", "BankGain"),
    ("MaxBankDegrees", "real", "MaxBankDegrees"),
    ("CameraUptiltDegrees", "real", "CameraUptiltDegrees"),
    ("MaxAngularRatesDegreesPerSecond", "real", "MaxAngularRateDegreesPerSecond"),
    ("MaxAccelerationsCmPerSecondSquared", "real", "MaxAccelerationCmPerSecondSquared"),
    ("MaxJerksCmPerSecondCubed", "real", "MaxJerkCmPerSecondCubed"),
    ("MinimumTurnRadiiCm", "real", "MinimumTurnRadiusCm"),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_flight_profile_candidates_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin, kind, array=False):
    category, subcategory = {"bool": ("bool", ""), "real": ("real", "double"), "string": ("string", "")}[kind]

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
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    reset = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-flight-profile-state-v1.eddgraph")
    repository = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/create-private-flypath-v1.eddgraph")
    forms.update({
        "foreach": bp.find_block(sync, r"^Begin Object Class=/Script/BlueprintGraph.K2Node_MacroInstance"),
        "array_add": bp.find_block(capture, r'MemberName="Array_Add"'),
        "array_clear": bp.find_block(reset, r'MemberName="Array_Clear"'),
        "call": bp.find_block(repository, r'MemberName="ValidateRecordV1"'),
    })
    builder = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name, kind, array=False):
        scalar.retarget_variable(node, name, kind)
        pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind)

    def get(name, kind, x, y, array=False):
        node = builder.add(f"get_{name}_{len(builder.nodes)}", "get", x, y)
        variable(node, name, kind, array)
        return node

    def set_(name, kind, x, y):
        node = builder.add(f"set_{name}_{len(builder.nodes)}", "set", x, y)
        variable(node, name, kind)
        return node

    def clear(target, pin, kind, x, y):
        node = builder.add(f"clear_{pin}_{len(builder.nodes)}", "array_clear", x, y)
        pin_kind(node, "TargetArray", kind, True)
        bp.connect(target, pin, node, "TargetArray")
        return node

    def add(target, target_pin, kind, source, source_pin, x, y):
        node = builder.add(f"add_{target_pin}_{len(builder.nodes)}", "array_add", x, y)
        pin_kind(node, "TargetArray", kind, True)
        pin_kind(node, "NewItem", kind)
        bp.connect(target, target_pin, node, "TargetArray")
        bp.connect(source, source_pin, node, "NewItem")
        return node

    def call(member, x, y):
        node = builder.add(f"call_{member}", "call", x, y)
        node.text = re.sub(r'FunctionReference=\([^\n]*\)', f'FunctionReference=(MemberName="{member}",bSelfContext=True)', node.text, 1)
        node.mutate_pin("self", lambda line: re.sub(r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"', f"PinType.PinSubCategoryObject={TARGET_CLASS}", line, 1))
        return node

    candidates = []
    clears = []
    for index, (candidate_suffix, kind, _result_suffix) in enumerate(CHANNELS):
        name = f"FlightProfileCandidate{candidate_suffix}V1"
        getter = get(name, kind, 0, index * 160, True)
        candidates.append(getter)
        clears.append(clear(getter, name, kind, 256 + index * 256, 1920))
    bp.connect(builder.entry, "then", clears[0], "execute")
    for left, right in zip(clears, clears[1:]):
        bp.connect(left, "then", right, "execute")
    stage = get("FlightProfileStageValidV1", "bool", 2816, 1600)
    outer = builder.add("stage_guard", "branch", 3072, 1920)
    bp.connect(clears[-1], "then", outer, "execute")
    bp.connect(stage, "FlightProfileStageValidV1", outer, "Condition")
    overrides = get("FlightProfileInputSegmentOverrideIdsV1", "string", 3072, 1280, True)
    default_id = get("FlightProfileInputDefaultIdV1", "string", 3072, 1440)
    loop = builder.add("override_loop", "foreach", 3328, 1600)
    pin_kind(loop, "Array", "string", True)
    pin_kind(loop, "Array Element", "string")
    bp.connect(overrides, "FlightProfileInputSegmentOverrideIdsV1", loop, "Array")
    bp.connect(outer, "then", loop, "Exec")
    empty = builder.equal_string(3584, 1280, "")
    bp.connect(loop, "Array Element", empty, "A")
    inherit = builder.add("inherit_branch", "branch", 3840, 1600)
    bp.connect(loop, "LoopBody", inherit, "execute")
    bp.connect(empty, "ReturnValue", inherit, "Condition")
    set_default = set_("FlightProfileResolveInputIdV1", "string", 4096, 1440)
    set_override = set_("FlightProfileResolveInputIdV1", "string", 4096, 1760)
    bp.connect(default_id, "FlightProfileInputDefaultIdV1", set_default, "FlightProfileResolveInputIdV1")
    bp.connect(loop, "Array Element", set_override, "FlightProfileResolveInputIdV1")
    bp.connect(inherit, "then", set_default, "execute")
    bp.connect(inherit, "else", set_override, "execute")
    resolver = call("ResolveFlightProfilePresetV1", 4352, 1600)
    bp.connect(set_default, "then", resolver, "execute")
    bp.connect(set_override, "then", resolver, "execute")
    resolver_valid = get("FlightProfileResolveResultValidV1", "bool", 4608, 1440)
    result_guard = builder.add("resolver_guard", "branch", 4864, 1600)
    bp.connect(resolver, "then", result_guard, "execute")
    bp.connect(resolver_valid, "FlightProfileResolveResultValidV1", result_guard, "Condition")
    reject = builder.set("FlightProfileStageValidV1", "bool", 5120, 1920, "false")
    bp.connect(result_guard, "else", reject, "execute")
    results = []
    adds = []
    for index, ((candidate_suffix, kind, result_suffix), candidate) in enumerate(zip(CHANNELS, candidates)):
        result_name = f"FlightProfileResolveResult{result_suffix}V1"
        result = get(result_name, kind, 5120, index * 160)
        results.append(result)
        adds.append(add(candidate, f"FlightProfileCandidate{candidate_suffix}V1", kind, result, result_name, 5376 + index * 256, 1600))
    bp.connect(result_guard, "then", adds[0], "execute")
    for left, right in zip(adds, adds[1:]):
        bp.connect(left, "then", right, "execute")

    full = "\n".join(node.text for node in builder.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in builder.nodes[1:]]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
