"""Build the fail-closed flight-profile candidate/result reset transaction."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ResetFlightProfileStateV1"
TARGET = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector"
PARAMETERS = (
    "PathFollowWeights", "HorizonStabilizationWeights", "LookAheadSeconds",
    "BankGains", "MaxBankDegrees", "CameraUptiltDegrees",
    "MaxAngularRatesDegreesPerSecond", "MaxAccelerationsCmPerSecondSquared",
    "MaxJerksCmPerSecondCubed", "MinimumTurnRadiiCm",
)
ARRAYS = (
    ("FlightProfileCandidateIdsV1", "string"),
    *((f"FlightProfileCandidate{name}V1", "real") for name in PARAMETERS),
    ("FlightProfileCompiledIdsV1", "string"),
    *((f"FlightProfileCompiled{name}V1", "real") for name in PARAMETERS),
)
SCALARS = (
    ("FlightProfileStageValidV1", "bool", "false"),
    ("FlightProfileCompileValidV1", "bool", "false"),
    ("FlightProfileResultIdV1", "string", ""),
    ("FlightProfileResultPathFollowWeightV1", "real", "0.0"),
    ("FlightProfileResultHorizonStabilizationWeightV1", "real", "0.0"),
    ("FlightProfileResultLookAheadSecondsV1", "real", "0.0"),
    ("FlightProfileResultBankGainV1", "real", "0.0"),
    ("FlightProfileResultMaxBankDegreesV1", "real", "0.0"),
    ("FlightProfileResultCameraUptiltDegreesV1", "real", "0.0"),
    ("FlightProfileResultMaxAngularRateDegreesPerSecondV1", "real", "0.0"),
    ("FlightProfileResultMaxAccelerationCmPerSecondSquaredV1", "real", "0.0"),
    ("FlightProfileResultMaxJerkCmPerSecondCubedV1", "real", "0.0"),
    ("FlightProfileResultMinimumTurnRadiusCmV1", "real", "0.0"),
    ("FlightProfileResultValidV1", "bool", "false"),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-OrientationTrackResetGraph.py"
    spec = importlib.util.spec_from_file_location("edd_flight_profile_reset_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pin_kind(node, pin_name, kind, array=False):
    category, subcategory = {
        "bool": ("bool", ""), "real": ("real", "double"), "string": ("string", ""),
    }[kind]

    def mutate(line):
        line = re.sub(r'PinType.PinCategory="[^"]*"', f'PinType.PinCategory="{category}"', line, 1)
        line = re.sub(r'PinType.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, 1)
        line = re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")', 'PinType.PinSubCategoryObject=None', line, 1)
        return re.sub(r'PinType.ContainerType=(?:None|Array)', f'PinType.ContainerType={"Array" if array else "None"}', line, 1)

    node.mutate_pin(pin_name, mutate)


def variable(node, old, new, kind, array=False):
    node.text = re.sub(
        rf'VariableReference=\(MemberName="{old}"[^)]*\)',
        f'VariableReference=(MemberName="{new}",bSelfContext=True)', node.text, 1,
    )
    node.text = node.text.replace(f'PinName="{old}"', f'PinName="{new}"')
    node.pins[new] = node.pins.pop(old)
    pin_kind(node, new, kind, array)
    if "Output_Get" in node.pins:
        pin_kind(node, "Output_Get", kind)


def default(node, pin, value):
    node.mutate_pin(
        pin,
        lambda line: re.sub(r'DefaultValue="[^"]*"', f'DefaultValue="{value}"', line, 1)
        if "DefaultValue=" in line
        else line.replace(",PersistentGuid=", f',DefaultValue="{value}",PersistentGuid=', 1),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    base = load(args.project_root)
    bp = base.load(args.project_root)
    bp.TARGET_ASSET = TARGET
    bp.TARGET_GRAPH = FUNCTION
    capture = bp.read_blocks(args.project_root / "tools/blueprint/templates/waypoint-capture-node-forms.eddgraph")
    orientation = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-orientation-track-candidate-v1.eddgraph")
    repository = bp.read_blocks(args.project_root / "tools/blueprint/snippets/reset-repository-result-v1.eddgraph")
    playback = bp.read_blocks(args.project_root / "tools/blueprint/snippets/start-linear-playback.eddgraph")
    entry_form = bp.find_block(capture, r"K2Node_FunctionEntry")
    real_getter_form = bp.find_block(orientation, r'MemberName="OrientationTrackCandidateSegmentStartsV1"')
    real_clear_form = bp.find_block(orientation, r'MemberName="Array_Clear"')
    string_getter_form = bp.find_block(repository, r'MemberName="ResultMetadataEnvelopesV1"')
    string_clear_form = bp.find_block(repository, r'MemberName="Array_Clear"')
    scalar_form = bp.find_block(playback, r'K2Node_VariableSet.*MemberName="PlaybackActive"')
    string_setter_form = bp.find_block(repository, r'K2Node_VariableSet.*MemberName="ResultDetailV1"')

    entry = bp.Node.clone("entry", entry_form, "K2Node_FunctionEntry_0", 0, 0)
    entry.text = re.sub(r'FunctionReference=\(MemberName="[^"]+"\)', f'FunctionReference=(MemberName="{FUNCTION}")', entry.text, 1)
    nodes = [entry]
    chain = []
    for index, (name, kind) in enumerate(ARRAYS):
        getter_form = string_getter_form if kind == "string" else real_getter_form
        clear_form = string_clear_form if kind == "string" else real_clear_form
        getter = bp.Node.clone(f"get_{index}", getter_form, f"K2Node_VariableGet_{index}", 256 + index * 416, 256)
        old = "ResultMetadataEnvelopesV1" if kind == "string" else "OrientationTrackCandidateSegmentStartsV1"
        variable(getter, old, name, kind, True)
        clear = bp.Node.clone(f"clear_{index}", clear_form, f"K2Node_CallArrayFunction_{index}", 256 + index * 416, 0)
        pin_kind(clear, "TargetArray", kind, True)
        bp.connect(getter, name, clear, "TargetArray")
        nodes.extend((getter, clear))
        chain.append(clear)
    for index, (name, kind, value) in enumerate(SCALARS):
        form = string_setter_form if kind == "string" else scalar_form
        old = "ResultDetailV1" if kind == "string" else "PlaybackActive"
        setter = bp.Node.clone(f"set_{index}", form, f"K2Node_VariableSet_{index}", 256 + (len(ARRAYS) + index) * 416, 0)
        variable(setter, old, name, kind)
        default(setter, name, value)
        nodes.append(setter)
        chain.append(setter)
    bp.connect(entry, "then", chain[0], "execute")
    for left, right in zip(chain, chain[1:]):
        bp.connect(left, "then", right, "execute")
    full = "\n".join(node.text for node in nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in nodes[1:]]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
