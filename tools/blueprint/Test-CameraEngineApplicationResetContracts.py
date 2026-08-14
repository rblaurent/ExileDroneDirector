"""Exact ownership and execution contracts for application-result reset."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


ARRAYS = ("CameraApplyUnavailableTargetIdsV1",)
SCALARS = (
    "CameraApplyFailureCodeV1",
    "CameraApplyResultValidV1",
    "CameraApplyScratchTargetIndexV1",
    "CameraApplyScratchStageValidV1",
)
PRESERVED = (
    "CameraApplyCapabilityEngineVersionV1",
    "CameraApplyCapabilityManifestIdV1",
    "CameraApplyCapabilityAvailableV1",
    "CameraApplyInputFilmbackPresetIdV1",
    "CameraApplyInputTargetValuesV1",
    "CameraApplyInputValidV1",
    "CameraApplyBaselineFilmbackPresetIdV1",
    "CameraApplyBaselineTargetValuesV1",
    "CameraApplyBaselineOverrideFlagsV1",
    "CameraApplyCurrentFilmbackPresetIdV1",
    "CameraApplyCurrentTargetValuesV1",
    "CameraApplyCurrentOverrideFlagsV1",
    "CameraApplySessionActiveV1",
    "CameraApplyAppliedFrameCountV1",
)


def load(path: Path):
    spec = importlib.util.spec_from_file_location("edd_camera_apply_reset_contract_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return None if match is None else match.group(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py")
    nodes = contracts.parse_graph(args.graph)
    contracts.require(len(nodes) == (6 if args.paste else 7), f"node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    root = nodes["K2Node_CallArrayFunction_0"]
    if args.paste:
        contracts.require(not root.pins["execute"].links, "paste execution root")
    else:
        contracts.require_link(
            entries[0], "then", root, "execute", "native entry to application reset root"
        )
    getters = {member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class}
    setters = {member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class}
    contracts.require(getters == set(ARRAYS), "exact diagnostic arrays cleared")
    contracts.require(setters == set(SCALARS), "exact result and scratch scalars reset")
    text = args.graph.read_text(encoding="utf-8")
    contracts.require(
        not any(name in text for name in PRESERVED),
        "capability/input/baseline/current/session state must be preserved",
    )

    state = {name: ["poison"] for name in ARRAYS}
    state.update({name: "poison" for name in SCALARS})
    state.update({name: object() for name in PRESERVED})
    before = {name: state[name] for name in PRESERVED}
    state["CameraApplyUnavailableTargetIdsV1"] = []
    state.update(
        CameraApplyFailureCodeV1="",
        CameraApplyResultValidV1=False,
        CameraApplyScratchTargetIndexV1=0,
        CameraApplyScratchStageValidV1=False,
    )
    contracts.require(state["CameraApplyUnavailableTargetIdsV1"] == [], "diagnostics clear")
    contracts.require(not state["CameraApplyResultValidV1"], "result invalidated")
    contracts.require(
        all(state[name] is before[name] for name in PRESERVED),
        "application session and baseline preserve object identity",
    )
    print(
        f"Camera engine application reset contracts passed "
        f"({'paste' if args.paste else 'full'}): session baseline preserved"
    )


if __name__ == "__main__":
    main()
