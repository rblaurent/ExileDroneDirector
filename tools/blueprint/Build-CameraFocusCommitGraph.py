"""Atomically publish a complete private focus-distance candidate snapshot."""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "CommitCameraFocusDistanceChannelV1"
MODES = ("manual_distance", "fixed_world", "rack_fixed", "track_prebaked", "smoothed_autofocus")


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_camera_focus_commit_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin: str, kind: str, array=False):
    category, subcategory = {"bool": ("bool", ""), "int": ("int", ""), "real": ("real", "double"), "string": ("string", "")}[kind]

    def mutate(line):
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', "PinType.PinSubCategoryObject=None", line, 1)
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
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    forms["length"] = bp.find_block(edit, r'MemberName="Array_Length"')
    b = scalar.Builder(bp, forms, FUNCTION)

    def variable(node, name, kind, array=False):
        scalar.retarget_variable(node, name, "real" if kind == "int" else kind)
        pin_kind(node, name, kind, array)
        if "Output_Get" in node.pins:
            pin_kind(node, "Output_Get", kind, array)

    def get(name, kind, x, y, array=False):
        node = b.add(f"get_{name}_{len(b.nodes)}", "get", x, y)
        variable(node, name, kind, array)
        return node

    def set_(name, kind, x, y, default=None, array=False):
        node = b.add(f"set_{name}_{len(b.nodes)}", "set", x, y)
        variable(node, name, kind, array)
        if default is not None:
            scalar.set_default(node, name, default)
        return node

    def length(source, source_pin, x, y):
        node = b.add(f"length_{len(b.nodes)}", "length", x, y)
        pin_kind(node, "TargetArray", "real", True)
        pin_kind(node, "ReturnValue", "int")
        bp.connect(source, source_pin, node, "TargetArray")
        return node

    def compare(member, left, left_pin, x, y, right=None, right_pin=None, default=None, kind="int"):
        node = b.add(f"compare_{member}_{len(b.nodes)}", "compare", x, y)
        scalar.retarget_function(node, member)
        for pin in ("A", "B"):
            pin_kind(node, pin, kind)
        pin_kind(node, "ReturnValue", "bool")
        bp.connect(left, left_pin, node, "A")
        if right is None:
            scalar.set_default(node, "B", default)
        else:
            bp.connect(right, right_pin, node, "B")
        return node

    def boolean(member, left, right, x, y):
        return compare(member, left, "ReturnValue", x, y, right, "ReturnValue", kind="bool")

    def combine(items, member, x, y):
        current = items[0]
        for offset, item in enumerate(items[1:]):
            current = boolean(member, current, item, x + offset * 192, y)
        return current

    def equal_string(source, pin, value, x, y):
        node = b.add(f"equal_{value}_{len(b.nodes)}", "string_equal", x, y)
        scalar.set_default(node, "B", value)
        bp.connect(source, pin, node, "A")
        return node

    candidate_valid = get("CameraFocusCandidateValidV1", "bool", 0, 0)
    times = get("CameraFocusInputTimesSecondsV1", "real", 0, 160, True)
    distances = get("CameraFocusCandidateDistancesCmV1", "real", 0, 320, True)
    mode = get("CameraFocusInputModeV1", "string", 0, 480)
    domain = get("CameraFocusInputDomainV1", "string", 0, 640)
    time_count = length(times, "CameraFocusInputTimesSecondsV1", 256, 160)
    distance_count = length(distances, "CameraFocusCandidateDistancesCmV1", 256, 320)
    same_count = compare("EqualEqual_IntInt", time_count, "ReturnValue", 480, 160, distance_count, "ReturnValue")
    enough = compare("GreaterEqual_IntInt", time_count, "ReturnValue", 480, 320, default="2")
    bounded = compare("LessEqual_IntInt", time_count, "ReturnValue", 480, 480, default="65536")
    shape = combine((same_count, enough, bounded), "BooleanAND", 704, 320)
    mode_flags = [equal_string(mode, "CameraFocusInputModeV1", value, 704, 640 + index * 128) for index, value in enumerate(MODES)]
    mode_ok = combine(mode_flags, "BooleanOR", 928, 896)
    domain_flags = [equal_string(domain, "CameraFocusInputDomainV1", value, 704, 1344 + index * 128) for index, value in enumerate(("linear", "reciprocal"))]
    domain_ok = boolean("BooleanOR", domain_flags[0], domain_flags[1], 928, 1408)
    ready = combine((shape, mode_ok, domain_ok), "BooleanAND", 1696, 1152)
    ready = compare("BooleanAND", candidate_valid, "CameraFocusCandidateValidV1", 2080, 1152, ready, "ReturnValue", kind="bool")

    invalidate = set_("CameraFocusCompileValidV1", "bool", 256, 1920, "false")
    failure = set_("CameraFocusFailureCodeV1", "string", 480, 1920, "commit_failed")
    guard = b.add("commit_guard", "branch", 2304, 1920)
    bp.connect(b.entry, "then", invalidate, "execute")
    bp.connect(invalidate, "then", failure, "execute")
    bp.connect(failure, "then", guard, "execute")
    bp.connect(ready, "ReturnValue", guard, "Condition")

    publish_times = set_("CameraFocusCompiledTimesSecondsV1", "real", 2528, 1920, array=True)
    publish_distances = set_("CameraFocusCompiledDistancesCmV1", "real", 2752, 1920, array=True)
    publish_mode = set_("CameraFocusCompiledModeV1", "string", 2976, 1920)
    publish_domain = set_("CameraFocusCompiledDomainV1", "string", 3200, 1920)
    clear_failure = set_("CameraFocusFailureCodeV1", "string", 3424, 1920, "")
    publish_valid = set_("CameraFocusCompileValidV1", "bool", 3648, 1920, "true")
    bp.connect(guard, "then", publish_times, "execute")
    bp.connect(times, "CameraFocusInputTimesSecondsV1", publish_times, "CameraFocusCompiledTimesSecondsV1")
    bp.connect(publish_times, "then", publish_distances, "execute")
    bp.connect(distances, "CameraFocusCandidateDistancesCmV1", publish_distances, "CameraFocusCompiledDistancesCmV1")
    bp.connect(publish_distances, "then", publish_mode, "execute")
    bp.connect(mode, "CameraFocusInputModeV1", publish_mode, "CameraFocusCompiledModeV1")
    bp.connect(publish_mode, "then", publish_domain, "execute")
    bp.connect(domain, "CameraFocusInputDomainV1", publish_domain, "CameraFocusCompiledDomainV1")
    bp.connect(publish_domain, "then", clear_failure, "execute")
    bp.connect(clear_failure, "then", publish_valid, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
