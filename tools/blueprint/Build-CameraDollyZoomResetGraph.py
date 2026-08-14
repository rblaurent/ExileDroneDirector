"""Build the fail-closed, compiled-snapshot-preserving dolly-zoom reset."""
from __future__ import annotations
import argparse, importlib.util, re, sys
from pathlib import Path

FUNCTION = "ResetCameraDollyZoomV1"
ARRAYS = ("CameraDollyCandidateSubjectDistancesCmV1", "CameraDollyCandidateFocalLengthsMmV1")
SCALARS = (
    ("CameraDollyValidationValidV1", "bool", "false"),
    ("CameraDollyCandidateValidV1", "bool", "false"),
    ("CameraDollyCompileValidV1", "bool", "false"),
    ("CameraDollyFailureCodeV1", "string", ""),
)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    camera = load(args.project_root / "tools/blueprint/Build-CameraChannelCompileResetGraph.py", "edd_dolly_reset_camera")
    reset = camera.load(args.project_root)
    bp = reset.load(args.project_root)
    bp.TARGET_GRAPH = FUNCTION
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    sync = bp.read_blocks(args.project_root / "tools/blueprint/snippets/sync-draft-waypoints-v1.eddgraph")
    start = bp.read_blocks(args.project_root / "tools/blueprint/snippets/start-linear-playback.eddgraph")
    entry = bp.Node.clone("entry", bp.find_block(capture, r"K2Node_FunctionEntry"), "K2Node_FunctionEntry_0", 0, 0)
    entry.text = re.sub(r'FunctionReference=\(MemberName="[^"]+"\)', f'FunctionReference=(MemberName="{FUNCTION}")', entry.text, 1)
    array_form = bp.find_block(sync, r'MemberName="DraftWaypointIds"')
    clear_form = bp.find_block(sync, r'MemberName="Array_Clear"')
    setter_form = bp.find_block(start, r'K2Node_VariableSet.*MemberName="PlaybackActive"')
    nodes = [entry]
    chain = []
    for index, name in enumerate(ARRAYS):
        getter = bp.Node.clone(f"array_{index}", array_form, f"K2Node_VariableGet_{index}", 256, index * 224)
        reset.variable(getter, "DraftWaypointIds", name, "real", True)
        clear = bp.Node.clone(f"clear_{index}", clear_form, f"K2Node_CallArrayFunction_{index}", 672 + index * 416, 0)
        reset.pin_kind(clear, "TargetArray", "real", True)
        bp.connect(getter, name, clear, "TargetArray")
        nodes.extend((getter, clear))
        chain.append(clear)
    for index, (name, kind, value) in enumerate(SCALARS):
        node = bp.Node.clone(f"set_{index}", setter_form, f"K2Node_VariableSet_{index}", 1504 + index * 416, 0)
        camera.string_variable(node, "PlaybackActive", name) if kind == "string" else reset.variable(node, "PlaybackActive", name, kind)
        reset.default(node, name, value)
        nodes.append(node)
        chain.append(node)
    bp.connect(entry, "then", chain[0], "execute")
    for left, right in zip(chain, chain[1:]):
        bp.connect(left, "then", right, "execute")
    full = "\n".join(node.text for node in nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        paste = "\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in nodes[1:]) + "\n"
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text(paste, encoding="utf-8")


if __name__ == "__main__":
    main()
