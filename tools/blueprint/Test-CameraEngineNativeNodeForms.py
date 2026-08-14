"""Structural contracts for Enhanced camera engine property and struct node forms."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


def load(root: Path):
    path = root / "tools/blueprint/Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_camera_engine_native_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member(node) -> str | None:
    match = re.search(r'MemberName="([^"]+)"', node.text)
    return match.group(1) if match else None


def parent(node) -> str | None:
    match = re.search(r'MemberParent="([^"]+)"', node.text)
    return match.group(1) if match else None


def struct_type(node) -> str | None:
    match = re.search(r'StructType="/Script/CoreUObject\.ScriptStruct\'([^\']+)\'"', node.text)
    return match.group(1) if match else None


def require_float(contracts, pin, label: str) -> None:
    contracts.require('PinType.PinCategory="real"' in pin.body, f"{label} category")
    contracts.require('PinType.PinSubCategory="float"' in pin.body, f"{label} precision")


def assert_basic(contracts, path: Path) -> None:
    nodes = contracts.parse_graph(path)
    contracts.require(len(nodes) == 12, f"basic native form node count: {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    contracts.require(len(entries) == 1, "one basic function entry")

    component_nodes = [node for node in nodes.values() if member(node) == "DroneCamera"]
    contracts.require(len(component_nodes) == 1, "one DroneCamera component getter")
    component = component_nodes[0]
    contracts.require("K2Node_VariableGet" in component.node_class, "DroneCamera must be a getter")
    contracts.require(set(component.pins) == {"DroneCamera", "self"}, "exact DroneCamera getter pins")

    identities = {
        ("/Script/CoreUObject.Class'/Script/CinematicCamera.CineCameraComponent'", "Filmback"): "struct",
        ("/Script/CoreUObject.Class'/Script/CinematicCamera.CineCameraComponent'", "FocusSettings"): "struct",
        ("/Script/CoreUObject.Class'/Script/Engine.CameraComponent'", "PostProcessSettings"): "struct",
        ("/Script/CoreUObject.Class'/Script/CinematicCamera.CineCameraComponent'", "CurrentFocalLength"): "float",
        ("/Script/CoreUObject.Class'/Script/CinematicCamera.CineCameraComponent'", "CurrentAperture"): "float",
    }
    engine_nodes = [node for node in nodes.values() if (parent(node), member(node)) in identities]
    contracts.require(len(engine_nodes) == 10, "five native getters and five native setters")
    for identity, kind in identities.items():
        matches = [node for node in engine_nodes if (parent(node), member(node)) == identity]
        getters = [node for node in matches if "K2Node_VariableGet" in node.node_class]
        setters = [node for node in matches if "K2Node_VariableSet" in node.node_class]
        contracts.require(len(getters) == 1 and len(setters) == 1, f"getter/setter pair for {identity[1]}")
        getter, setter = getters[0], setters[0]
        contracts.require("self" in getter.pins and "self" in setter.pins, f"{identity[1]} target pins")
        contracts.require_link(component, "DroneCamera", getter, "self", f"{identity[1]} getter targets DroneCamera")
        contracts.require_link(component, "DroneCamera", setter, "self", f"{identity[1]} setter targets DroneCamera")
        if kind == "float":
            require_float(contracts, getter.pins[identity[1]], f"{identity[1]} getter")
            require_float(contracts, setter.pins[identity[1]], f"{identity[1]} setter")


def assert_structs(contracts, path: Path) -> None:
    nodes = contracts.parse_graph(path)
    contracts.require(len(nodes) == 7, f"struct native form node count: {len(nodes)}")
    contracts.require(sum("K2Node_FunctionEntry" in node.node_class for node in nodes.values()) == 1, "one struct function entry")
    breaks = [node for node in nodes.values() if "K2Node_BreakStruct" in node.node_class]
    sets = [node for node in nodes.values() if "K2Node_SetFieldsInStruct" in node.node_class]
    contracts.require(len(breaks) == 3 and len(sets) == 3, "three native breaks and three native set-members nodes")

    expected_breaks = {
        "/Script/CinematicCamera.CameraFilmbackSettings": {
            "CameraFilmbackSettings", "SensorWidth", "SensorHeight", "SensorHorizontalOffset", "SensorVerticalOffset", "SensorAspectRatio"
        },
        "/Script/CinematicCamera.CameraFocusSettings": {
            "CameraFocusSettings", "FocusMethod", "ManualFocusDistance", "TrackingFocusSettings", "bSmoothFocusChanges", "FocusSmoothingInterpSpeed", "FocusOffset"
        },
        "/Script/Engine.PostProcessSettings": {
            "PostProcessSettings", "SceneFringeIntensity", "BloomIntensity", "AutoExposureBias", "VignetteIntensity", "MotionBlurAmount"
        },
    }
    expected_sets = {
        "/Script/CinematicCamera.CameraFilmbackSettings": {"execute", "then", "StructRef", "StructOut", "SensorWidth", "SensorHeight"},
        "/Script/CinematicCamera.CameraFocusSettings": {"execute", "then", "StructRef", "StructOut", "ManualFocusDistance"},
        "/Script/Engine.PostProcessSettings": {
            "execute", "then", "StructRef", "StructOut", "SceneFringeIntensity", "BloomIntensity", "AutoExposureBias", "VignetteIntensity", "MotionBlurAmount"
        },
    }
    for expected, group in ((expected_breaks, breaks), (expected_sets, sets)):
        actual = {struct_type(node): node for node in group}
        contracts.require(set(actual) == set(expected), f"exact native struct identities: {set(actual)}")
        for identity, pins in expected.items():
            node = actual[identity]
            contracts.require(set(node.pins) == pins, f"exact {identity} pins")
            contracts.require("bMadeAfterOverridePinRemoval=True" in node.text, f"{identity} override-removal serialization")

    post_process_nodes = [node for node in breaks + sets if struct_type(node) == "/Script/Engine.PostProcessSettings"]
    pp_fields = {"SceneFringeIntensity", "BloomIntensity", "AutoExposureBias", "VignetteIntensity", "MotionBlurAmount"}
    for node in post_process_nodes:
        contracts.require(not any(name.startswith("bOverride_") for name in node.pins), "override bits must not masquerade as readable pins")
        for field in pp_fields:
            entry = re.search(rf'ShowPinForProperties\(\d+\)=\(PropertyName="{field}"[^\n]+', node.text)
            contracts.require(entry is not None, f"{field} visibility metadata")
            contracts.require("bShowPin=True" in entry.group(0) and "bHasOverridePin=True" in entry.group(0), f"{field} implicit override ownership")
            require_float(contracts, node.pins[field], f"{field} native pin")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--basic", type=Path, required=True)
    parser.add_argument("--structs", type=Path, required=True)
    args = parser.parse_args()
    contracts = load(args.project_root)
    assert_basic(contracts, args.basic)
    assert_structs(contracts, args.structs)
    print("Camera engine native node-form contracts passed")


if __name__ == "__main__":
    main()
