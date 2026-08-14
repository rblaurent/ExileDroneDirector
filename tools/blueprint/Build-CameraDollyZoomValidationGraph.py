"""Build dolly-zoom shape, reference-index, and reference-lens preflight."""
from __future__ import annotations
import argparse, importlib.util, re, sys
from pathlib import Path

FUNCTION = "ValidateCameraDollyZoomInputsV1"


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_dolly_validation_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin: str, kind: str, array: bool = False) -> None:
    category, subcategory, obj = {
        "bool": ("bool", "", "None"), "int": ("int", "", "None"),
        "real": ("real", "double", "None"),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
    }[kind]
    def mutate(line: str) -> str:
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f'PinType.PinSubCategoryObject={obj}', line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)
    node.mutate_pin(pin, mutate)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    scalar = load(args.project_root)
    bp = scalar.load_helpers(args.project_root)
    forms = scalar.load_templates(args.project_root, bp)
    b = scalar.Builder(bp, forms, FUNCTION)
    edit = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-edit-node-forms.eddgraph")
    length_form = bp.find_block(edit, r'MemberName="Array_Length"')

    def add_form(key, form, x, y):
        match = bp.BLOCK_RE.match(form); cls = match.group("class").rsplit(".", 1)[-1]
        index = b.serial.get(cls, 0); b.serial[cls] = index + 1
        node = bp.Node.clone(key, form, f"{cls}_{index}", x, y); b.nodes.append(node); return node
    def get_var(name, kind, x, y, array=False):
        node = b.get(name, "real", x, y); scalar.retarget_variable(node, name, "real" if kind == "int" else kind)
        pin_kind(node, name, kind, array); return node
    def length(source, name, kind, x, y):
        node = add_form(f"length_{name}", length_form, x, y)
        pin_kind(node, "TargetArray", kind, True); pin_kind(node, "ReturnValue", "int")
        bp.connect(source, name, node, "TargetArray"); return node
    def compare(member, left, left_pin, x, y, kind="int", right=None, right_pin=None, default=None):
        node = b.add(f"compare_{len(b.nodes)}", "compare", x, y); scalar.retarget_function(node, member)
        for pin in ("A", "B"): pin_kind(node, pin, kind)
        pin_kind(node, "ReturnValue", "bool")
        bp.connect(left, left_pin, node, "A")
        if right is not None: bp.connect(right, right_pin, node, "B")
        else: scalar.set_default(node, "B", default)
        return node
    def boolean(left, right, x, y):
        node = b.add(f"boolean_{len(b.nodes)}", "compare", x, y); scalar.retarget_function(node, "BooleanAND")
        for pin in ("A", "B", "ReturnValue"): pin_kind(node, pin, "bool")
        bp.connect(left, "ReturnValue", node, "A"); bp.connect(right, "ReturnValue", node, "B"); return node
    def combine(items, x, y):
        current = items[0]
        for index, item in enumerate(items[1:]): current = boolean(current, item, x + index * 192, y)
        return current

    invalidate = b.set("CameraDollyValidationValidV1", "bool", 256, 2368, "false")
    failure = b.set("CameraDollyFailureCodeV1", "string", 480, 2368, "validation_failed")
    bp.connect(b.entry, "then", invalidate, "execute"); bp.connect(invalidate, "then", failure, "execute")
    times = get_var("CameraDollyInputTimesSecondsV1", "real", 0, 0, True)
    positions = get_var("CameraDollyInputCameraPositionsV1", "vector", 0, 224, True)
    time_count = length(times, "CameraDollyInputTimesSecondsV1", "real", 320, 0)
    position_count = length(positions, "CameraDollyInputCameraPositionsV1", "vector", 320, 224)
    reference = get_var("CameraDollyInputReferenceSampleIndexV1", "int", 0, 512)
    focal = get_var("CameraDollyInputReferenceFocalLengthMmV1", "real", 0, 736)
    conditions = (
        compare("GreaterEqual_IntInt", time_count, "ReturnValue", 640, 0, default="2"),
        compare("LessEqual_IntInt", time_count, "ReturnValue", 864, 0, default="65536"),
        compare("EqualEqual_IntInt", position_count, "ReturnValue", 1088, 224, right=time_count, right_pin="ReturnValue"),
        compare("GreaterEqual_IntInt", reference, "CameraDollyInputReferenceSampleIndexV1", 640, 512, default="0"),
        compare("Less_IntInt", reference, "CameraDollyInputReferenceSampleIndexV1", 864, 512, right=time_count, right_pin="ReturnValue"),
        b.finite(focal, "CameraDollyInputReferenceFocalLengthMmV1", 640, 736),
        compare("GreaterEqual_DoubleDouble", focal, "CameraDollyInputReferenceFocalLengthMmV1", 1088, 736, "real", default="1.0"),
        compare("LessEqual_DoubleDouble", focal, "CameraDollyInputReferenceFocalLengthMmV1", 1312, 736, "real", default="1000.0"),
    )
    ready = combine(conditions, 640, 1248)
    guard = b.add("validation_guard", "branch", 2048, 2368)
    bp.connect(failure, "then", guard, "execute"); bp.connect(ready, "ReturnValue", guard, "Condition")
    clear = b.set("CameraDollyFailureCodeV1", "string", 2272, 2368, "")
    publish = b.set("CameraDollyValidationValidV1", "bool", 2496, 2368, "true")
    bp.connect(guard, "then", clear, "execute"); bp.connect(clear, "then", publish, "execute")
    full = "\n".join(node.text for node in b.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
