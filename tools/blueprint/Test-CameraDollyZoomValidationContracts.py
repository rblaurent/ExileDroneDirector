"""Exact structural and executable contracts for dolly-zoom preflight."""
from __future__ import annotations
import argparse, importlib.util, math, random, re, sys
from pathlib import Path

READS = {"CameraDollyInputTimesSecondsV1", "CameraDollyInputCameraPositionsV1", "CameraDollyInputReferenceSampleIndexV1", "CameraDollyInputReferenceFocalLengthMmV1"}
WRITES = {"CameraDollyValidationValidV1", "CameraDollyFailureCodeV1"}
FORBIDDEN = ("CameraDollyInputSubjectPositionV1", "CameraDollyCandidate", "CameraDollyCompiled", "CameraApply", "Airframe", "Gimbal", "Document", "Playback")


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_dolly_validation_contract_base", path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module); return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text); return None if match is None else match.group(1)


def preflight(times_count, positions_count, reference_index, reference_focal):
    return (2 <= times_count <= 65536 and positions_count == times_count and isinstance(reference_index, int)
            and not isinstance(reference_index, bool) and 0 <= reference_index < times_count
            and isinstance(reference_focal, (int, float)) and not isinstance(reference_focal, bool)
            and math.isfinite(reference_focal) and 1.0 <= reference_focal <= 1000.0)


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--graph", type=Path, required=True); parser.add_argument("--paste", action="store_true"); args = parser.parse_args()
    c = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py"); nodes = c.parse_graph(args.graph)
    c.require(len(nodes) == (28 if args.paste else 29), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]; c.require(len(entries) == (0 if args.paste else 1), "entry count")
    getters = {member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}
    setters = {member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class}
    c.require(getters == READS, "exact preflight reads"); c.require(setters == WRITES, "exact preflight writes")
    text = args.graph.read_text(encoding="utf-8")
    c.require(not any(value in text for value in FORBIDDEN), "subject/sample values, candidates, compiled, engine, motion, and playback forbidden")
    c.require(text.count('MemberName="Array_Length"') == 2, "two source lengths")
    c.require(text.count('DefaultValue="-1.7976931348623157e+308"') == 1 and text.count('DefaultValue="1.7976931348623157e+308"') == 1, "reference focal finite check")
    invalidators = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class and member(node) == "CameraDollyValidationValidV1" and 'DefaultValue="true"' not in node.text]
    c.require(len(invalidators) == 1, "validation invalidated first")
    if not args.paste: c.require(any(any(link[0] == entries[0].name for link in node.pins["execute"].links) for node in invalidators), "native entry seam")
    rng = random.Random(0xD0117A); valid = []
    for _ in range(80):
        count = rng.randint(2, 512); valid.append((count, count, rng.randrange(count), rng.uniform(1.0, 1000.0)))
    c.require(all(preflight(*case) for case in valid), "seeded valid preflight")
    failures = ((1, 1, 0, 35.0), (65537, 65537, 0, 35.0), (4, 3, 0, 35.0), (4, 4, -1, 35.0), (4, 4, 4, 35.0), (4, 4, True, 35.0), (4, 4, 0, math.nan), (4, 4, 0, math.inf), (4, 4, 0, 0.9), (4, 4, 0, 1000.1))
    c.require(all(not preflight(*case) for case in failures), "failure families")
    before = tuple(valid); [preflight(*case) for case in valid]; c.require(tuple(valid) == before, "inputs immutable")
    print(f"Camera dolly validation contracts passed ({'paste' if args.paste else 'full'}): {len(valid)} valid, {len(failures)} failures")


if __name__ == "__main__":
    main()
