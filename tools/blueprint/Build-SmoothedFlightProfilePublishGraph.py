"""Build canonical validation and atomic publication of a smoothed profile."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "PublishSmoothedFlightProfileV1"
TARGET_CLASS = '"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'
PARAMETERS = (
    "PathFollowWeight", "HorizonStabilizationWeight", "LookAheadSeconds",
    "BankGain", "MaxBankDegrees", "CameraUptiltDegrees",
    "MaxAngularRateDegreesPerSecond", "MaxAccelerationCmPerSecondSquared",
    "MaxJerkCmPerSecondCubed", "MinimumTurnRadiusCm",
)
BOUNDS = (
    ("0.0", "1.0", True), ("0.0", "1.0", True), ("0.0", "5.0", True),
    ("0.0", "2.0", True), ("0.0", "85.0", True), ("-45.0", "45.0", True),
    ("0.0", "720.0", False), ("0.0", "10000.0", False),
    ("0.0", "50000.0", False), ("0.0", "100000.0", False),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_smoothed_flight_profile_publish_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin: str, value: str):
    category, subcategory = {
        "bool": ("bool", ""), "real": ("real", "double"), "string": ("string", ""),
    }[value]

    def mutate(line: str) -> str:
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', 'PinType.PinSubCategoryObject=None', line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', 'PinType.ContainerType=None', line, 1)

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
    public_list = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/list-public-v1.eddgraph")
    repository = bp.read_blocks(args.project_root / "tools/blueprint/live-snippets/create-private-flypath-v1.eddgraph")
    forms.update({
        "select": bp.find_block(public_list, r'^Begin Object Class=/Script/BlueprintGraph.K2Node_Select '),
        "call": bp.find_block(repository, r'MemberName="ValidateRecordV1"'),
    })
    b = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name: str, value: str):
        scalar.retarget_variable(node, name, value)
        pin_kind(node, name, value)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", value)

    def get(name: str, value: str, x: int, y: int):
        node = b.add(f"get_{name}_{len(b.nodes)}", "get", x, y)
        variable(node, name, value)
        return node

    def set_value(name: str, value: str, x: int, y: int, default=None):
        node = b.add(f"set_{name}_{len(b.nodes)}", "set", x, y)
        variable(node, name, value)
        if default is not None:
            scalar.set_default(node, name, default)
        return node

    def compare(member: str, left, left_pin: str, right, right_pin: str, value: str, x: int, y: int):
        node = b.add(f"compare_{member}_{len(b.nodes)}", "compare", x, y)
        scalar.retarget_function(node, member)
        if member == "EqualEqual_StrStr":
            node.text = node.text.replace("/Script/Engine.KismetMathLibrary", "/Script/Engine.KismetStringLibrary")
        for pin in ("A", "B"):
            pin_kind(node, pin, value)
        pin_kind(node, "ReturnValue", "bool")
        bp.connect(left, left_pin, node, "A")
        if right is None:
            scalar.set_default(node, "B", right_pin)
        else:
            bp.connect(right, right_pin, node, "B")
        return node

    def combine(member: str, guards, x: int, y: int):
        node, output = guards[0]
        for index, (guard, guard_pin) in enumerate(guards[1:]):
            node = compare(member, node, output, guard, guard_pin, "bool", x + index * 224, y)
            output = "ReturnValue"
        return node, output

    def select(condition, false_source, false_pin: str, true_source, true_pin: str, value: str, x: int, y: int, false_default=None, true_default=None):
        node = b.add(f"select_{value}_{len(b.nodes)}", "select", x, y)
        for pin in ("Option 0", "Option 1", "ReturnValue"):
            pin_kind(node, pin, value)
        pin_kind(node, "Index", "bool")
        bp.connect(condition, "ReturnValue", node, "Index")
        if false_source is None:
            scalar.set_default(node, "Option 0", false_default)
        else:
            bp.connect(false_source, false_pin, node, "Option 0")
        if true_source is None:
            scalar.set_default(node, "Option 1", true_default)
        else:
            bp.connect(true_source, true_pin, node, "Option 1")
        return node

    def call(member: str, x: int, y: int):
        node = b.add(f"call_{member}_{len(b.nodes)}", "call", x, y)
        node.text = re.sub(r'FunctionReference=\([^\n]*\)', f'FunctionReference=(MemberName="{member}",bSelfContext=True)', node.text, 1)
        node.mutate_pin(
            "self",
            lambda line: re.sub(
                r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"',
                f"PinType.PinSubCategoryObject={TARGET_CLASS}", line, 1,
            ),
        )
        return node

    invalidate = set_value("SmoothedFlightProfileResultValidV1", "bool", 256, 2240, "false")
    bp.connect(b.entry, "then", invalidate, "execute")
    stage_valid = get("SmoothedFlightProfileStageValidV1", "bool", 0, 1760)
    weight = get("SmoothedFlightProfileNeighborWeightV1", "real", 0, 1920)
    weight_finite = b.finite(weight, "SmoothedFlightProfileNeighborWeightV1", 320, 1920)
    weight_lower = compare("GreaterEqual_DoubleDouble", weight, "SmoothedFlightProfileNeighborWeightV1", None, "0.0", "real", 768, 1920)
    weight_upper = compare("LessEqual_DoubleDouble", weight, "SmoothedFlightProfileNeighborWeightV1", None, "0.5", "real", 768, 2080)
    pre_valid, pre_pin = combine("BooleanAND", ((stage_valid, "SmoothedFlightProfileStageValidV1"), (weight_finite, "ReturnValue"), (weight_lower, "ReturnValue"), (weight_upper, "ReturnValue")), 1024, 1920)
    pre_branch = b.add("pre_branch", "branch", 1696, 2240)
    bp.connect(invalidate, "then", pre_branch, "execute")
    bp.connect(pre_valid, pre_pin, pre_branch, "Condition")

    current_id = get("SmoothedFlightProfileCurrentIdV1", "string", 0, 0)
    neighbor_id = get("SmoothedFlightProfileNeighborIdV1", "string", 0, 160)
    current_values = [get(f"SmoothedFlightProfileCurrent{name}V1", "real", 0, 320 + i * 144) for i, name in enumerate(PARAMETERS)]
    neighbor_values = [get(f"SmoothedFlightProfileNeighbor{name}V1", "real", 320, 320 + i * 144) for i, name in enumerate(PARAMETERS)]

    stage_current_id = set_value("FlightProfileResolveInputIdV1", "string", 1952, 2240)
    bp.connect(pre_branch, "then", stage_current_id, "execute")
    bp.connect(current_id, "SmoothedFlightProfileCurrentIdV1", stage_current_id, "FlightProfileResolveInputIdV1")
    current_resolve = call("ResolveFlightProfilePresetV1", 2208, 2240)
    bp.connect(stage_current_id, "then", current_resolve, "execute")
    resolve_valid = get("FlightProfileResolveResultValidV1", "bool", 2464, 1760)
    resolve_id = get("FlightProfileResolveResultIdV1", "string", 2464, 1920)
    current_id_equal = compare("EqualEqual_StrStr", resolve_id, "FlightProfileResolveResultIdV1", current_id, "SmoothedFlightProfileCurrentIdV1", "string", 2720, 1920)
    current_guards = [(resolve_valid, "FlightProfileResolveResultValidV1"), (current_id_equal, "ReturnValue")]
    for index, (name, staged) in enumerate(zip(PARAMETERS, current_values)):
        resolved_name = f"FlightProfileResolveResult{name}V1"
        resolved = get(resolved_name, "real", 2464, index * 144)
        equal = compare("EqualEqual_DoubleDouble", staged, f"SmoothedFlightProfileCurrent{name}V1", resolved, resolved_name, "real", 2944, index * 144)
        current_guards.append((equal, "ReturnValue"))
    current_valid, current_pin = combine("BooleanAND", current_guards, 3200, 1760)
    current_branch = b.add("current_branch", "branch", 5664, 2240)
    bp.connect(current_resolve, "then", current_branch, "execute")
    bp.connect(current_valid, current_pin, current_branch, "Condition")

    stage_neighbor_id = set_value("FlightProfileResolveInputIdV1", "string", 5920, 2240)
    bp.connect(current_branch, "then", stage_neighbor_id, "execute")
    bp.connect(neighbor_id, "SmoothedFlightProfileNeighborIdV1", stage_neighbor_id, "FlightProfileResolveInputIdV1")
    neighbor_resolve = call("ResolveFlightProfilePresetV1", 6176, 2240)
    bp.connect(stage_neighbor_id, "then", neighbor_resolve, "execute")
    neighbor_id_equal = compare("EqualEqual_StrStr", resolve_id, "FlightProfileResolveResultIdV1", neighbor_id, "SmoothedFlightProfileNeighborIdV1", "string", 6432, 1920)
    neighbor_guards = [(resolve_valid, "FlightProfileResolveResultValidV1"), (neighbor_id_equal, "ReturnValue")]
    for index, (name, staged) in enumerate(zip(PARAMETERS, neighbor_values)):
        resolved_name = f"FlightProfileResolveResult{name}V1"
        resolved = get(resolved_name, "real", 6176, index * 144)
        equal = compare("EqualEqual_DoubleDouble", staged, f"SmoothedFlightProfileNeighbor{name}V1", resolved, resolved_name, "real", 6688, index * 144)
        neighbor_guards.append((equal, "ReturnValue"))
    neighbor_valid, neighbor_pin = combine("BooleanAND", neighbor_guards, 6944, 1760)
    neighbor_branch = b.add("neighbor_branch", "branch", 9408, 2240)
    bp.connect(neighbor_resolve, "then", neighbor_branch, "execute")
    bp.connect(neighbor_valid, neighbor_pin, neighbor_branch, "Condition")

    zero_weight = compare("EqualEqual_DoubleDouble", weight, "SmoothedFlightProfileNeighborWeightV1", None, "0.0", "real", 9632, 320)
    same_id = compare("EqualEqual_StrStr", current_id, "SmoothedFlightProfileCurrentIdV1", neighbor_id, "SmoothedFlightProfileNeighborIdV1", "string", 9632, 480)
    normalize, normalize_pin = combine("BooleanOR", ((zero_weight, "ReturnValue"), (same_id, "ReturnValue")), 9856, 400)
    effective_id = select(normalize, neighbor_id, "SmoothedFlightProfileNeighborIdV1", current_id, "SmoothedFlightProfileCurrentIdV1", "string", 10080, 320)
    effective_weight = select(normalize, weight, "SmoothedFlightProfileNeighborWeightV1", None, "", "real", 10080, 480, true_default="0.0")

    blended = []
    blend_guards = []
    for index, (name, current, neighbor, bounds) in enumerate(zip(PARAMETERS, current_values, neighbor_values, BOUNDS)):
        y = index * 176
        delta = b.math("Subtract_DoubleDouble", 10336, y)
        bp.connect(neighbor, f"SmoothedFlightProfileNeighbor{name}V1", delta, "A")
        bp.connect(current, f"SmoothedFlightProfileCurrent{name}V1", delta, "B")
        scaled = b.math("Multiply_DoubleDouble", 10560, y)
        bp.connect(delta, "ReturnValue", scaled, "A")
        bp.connect(effective_weight, "ReturnValue", scaled, "B")
        value = b.math("Add_DoubleDouble", 10784, y)
        bp.connect(current, f"SmoothedFlightProfileCurrent{name}V1", value, "A")
        bp.connect(scaled, "ReturnValue", value, "B")
        blended.append(value)
        lower, upper, inclusive = bounds
        low = compare("GreaterEqual_DoubleDouble" if inclusive else "Greater_DoubleDouble", value, "ReturnValue", None, lower, "real", 11008, y)
        high = compare("LessEqual_DoubleDouble", value, "ReturnValue", None, upper, "real", 11232, y)
        blend_guards.extend(((low, "ReturnValue"), (high, "ReturnValue")))
    result_valid, result_pin = combine("BooleanAND", blend_guards, 11456, 1760)
    result_branch = b.add("result_branch", "branch", 15712, 2240)
    bp.connect(neighbor_branch, "then", result_branch, "execute")
    bp.connect(result_valid, result_pin, result_branch, "Condition")

    publications = [
        set_value("SmoothedFlightProfileResultCurrentIdV1", "string", 15968, 2240),
        set_value("SmoothedFlightProfileResultNeighborIdV1", "string", 16224, 2240),
        set_value("SmoothedFlightProfileResultNeighborWeightV1", "real", 16480, 2240),
    ]
    bp.connect(current_id, "SmoothedFlightProfileCurrentIdV1", publications[0], "SmoothedFlightProfileResultCurrentIdV1")
    bp.connect(effective_id, "ReturnValue", publications[1], "SmoothedFlightProfileResultNeighborIdV1")
    bp.connect(effective_weight, "ReturnValue", publications[2], "SmoothedFlightProfileResultNeighborWeightV1")
    for index, (name, value) in enumerate(zip(PARAMETERS, blended)):
        publication = set_value(f"SmoothedFlightProfileResult{name}V1", "real", 16736 + index * 256, 2240)
        bp.connect(value, "ReturnValue", publication, f"SmoothedFlightProfileResult{name}V1")
        publications.append(publication)
    bp.connect(result_branch, "then", publications[0], "execute")
    for left, right in zip(publications, publications[1:]):
        bp.connect(left, "then", right, "execute")
    publish_valid = set_value("SmoothedFlightProfileResultValidV1", "bool", 19328, 2240, "true")
    bp.connect(publications[-1], "then", publish_valid, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
