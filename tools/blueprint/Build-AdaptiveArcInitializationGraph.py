"""Build deterministic initial work-stack and candidate state for adaptive arc compilation."""

from __future__ import annotations

import argparse, importlib.util, re, sys
from pathlib import Path


FUNCTION = "InitializeAdaptiveArcBuildV1"
ARRAYS = (
    ("TrajectoryArcBuildWorkU0V1", "real"),
    ("TrajectoryArcBuildWorkU1V1", "real"),
    ("TrajectoryArcBuildWorkP0V1", "vector"),
    ("TrajectoryArcBuildWorkP1V1", "vector"),
    ("TrajectoryArcBuildWorkDepthV1", "int"),
    ("TrajectoryArcBuildCandidateUsV1", "real"),
    ("TrajectoryArcBuildCandidatePositionsV1", "vector"),
    ("TrajectoryArcBuildCandidateDistancesV1", "real"),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_adaptive_arc_initialize_base", path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    return module


def kind(node, pin, value, array=False):
    category, subcategory, obj = {
        "bool": ("bool", "", "None"), "int": ("int", "", "None"),
        "real": ("real", "double", "None"),
        "vector": ("struct", "", '"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"'),
    }[value]
    def mutate(line):
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', f"PinType.PinSubCategoryObject={obj}", line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)
    node.mutate_pin(pin, mutate)


def variable(scalar, node, name, value, array=False):
    scalar.retarget_variable(node, name, "vector" if value == "vector" else "real")
    kind(node, name, value, array)
    if "Output_Get" in node.pins:
        kind(node, "Output_Get", value)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args(); scalar = load(args.project_root); bp = scalar.load_helpers(args.project_root); forms = scalar.load_templates(args.project_root, bp); b = scalar.Builder(bp, forms, FUNCTION)
    reset = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-adaptive-arc-build-v1.eddgraph")
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    clear_form = bp.find_block(reset, r'MemberName="Array_Clear"')
    add_form = bp.find_block(capture, r'MemberName="Array_Add"')

    def add(key, form, x, y):
        match = bp.BLOCK_RE.match(form); cls = match.group("class").rsplit(".", 1)[-1]; index = b.serial.get(cls, 0); b.serial[cls] = index + 1
        node = bp.Node.clone(key, form, f"{cls}_{index}", x, y); b.nodes.append(node); return node
    def array_get(name, value, x, y):
        node = b.get(name, "vector" if value == "vector" else "real", x, y); variable(scalar, node, name, value, True); return node
    def append(target, name, value, x, source=None, source_pin=None, default=None):
        node = add(f"append_{name}", add_form, x, 1344); kind(node, "TargetArray", value, True); kind(node, "NewItem", value); bp.connect(target, name, node, "TargetArray")
        if source is not None: bp.connect(source, source_pin, node, "NewItem")
        elif default is not None: scalar.set_default(node, "NewItem", default)
        return node

    arrays = [array_get(name, value, 0, 160 + index * 160) for index, (name, value) in enumerate(ARRAYS)]
    chain = []
    for index, ((name, value), source) in enumerate(zip(ARRAYS, arrays)):
        clear = add(f"clear_{name}", clear_form, 256 + index * 256, 1344); kind(clear, "TargetArray", value, True); bp.connect(source, name, clear, "TargetArray"); chain.append(clear)
    reset_operations = b.set("TrajectoryArcBuildOperationCountV1", "real", 2304, 1344, "0"); variable(scalar, reset_operations, "TrajectoryArcBuildOperationCountV1", "int"); chain.append(reset_operations)
    reset_length = b.set("TrajectoryArcBuildCandidateLengthV1", "real", 2560, 1344, "0.0"); chain.append(reset_length)
    bp.connect(b.entry, "then", chain[0], "execute")
    for left, right in zip(chain, chain[1:]): bp.connect(left, "then", right, "execute")

    stage = b.get("TrajectoryArcBuildStageValidV1", "bool", 2560, 1120)
    guard = b.add("guard", "branch", 2816, 1344); bp.connect(chain[-1], "then", guard, "execute"); bp.connect(stage, "TrajectoryArcBuildStageValidV1", guard, "Condition")
    start = b.get("TrajectoryArcBuildInputStartPositionV1", "vector", 2816, 240); end = b.get("TrajectoryArcBuildInputEndPositionV1", "vector", 2816, 480)
    appends = (
        append(arrays[0], ARRAYS[0][0], "real", 3072, default="0.0"),
        append(arrays[1], ARRAYS[1][0], "real", 3328, default="1.0"),
        append(arrays[2], ARRAYS[2][0], "vector", 3584, start, "TrajectoryArcBuildInputStartPositionV1"),
        append(arrays[3], ARRAYS[3][0], "vector", 3840, end, "TrajectoryArcBuildInputEndPositionV1"),
        append(arrays[4], ARRAYS[4][0], "int", 4096, default="0"),
        append(arrays[5], ARRAYS[5][0], "real", 4352, default="0.0"),
        append(arrays[6], ARRAYS[6][0], "vector", 4608, start, "TrajectoryArcBuildInputStartPositionV1"),
        append(arrays[7], ARRAYS[7][0], "real", 4864, default="0.0"),
    )
    bp.connect(guard, "then", appends[0], "execute")
    for left, right in zip(appends, appends[1:]): bp.connect(left, "then", right, "execute")

    full = "\n".join(node.text for node in b.nodes) + "\n"; args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in b.nodes[1:]]; args.paste_output.parent.mkdir(parents=True, exist_ok=True); args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__": main()
