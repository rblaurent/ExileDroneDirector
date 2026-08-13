"""Build exact canonical flight-profile preset resolution."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTION = "ResolveFlightProfilePresetV1"
FIELDS = (
    ("Id", "string", "profile_id"),
    ("PathFollowWeight", "real", "path_follow_weight"),
    ("HorizonStabilizationWeight", "real", "horizon_stabilization_weight"),
    ("LookAheadSeconds", "real", "look_ahead_seconds"),
    ("BankGain", "real", "bank_gain"),
    ("MaxBankDegrees", "real", "max_bank_degrees"),
    ("CameraUptiltDegrees", "real", "camera_uptilt_degrees"),
    ("MaxAngularRateDegreesPerSecond", "real", "max_angular_rate_degrees_per_second"),
    ("MaxAccelerationCmPerSecondSquared", "real", "max_acceleration_cm_per_second_squared"),
    ("MaxJerkCmPerSecondCubed", "real", "max_jerk_cm_per_second_cubed"),
    ("MinimumTurnRadiusCm", "real", "minimum_turn_radius_cm"),
    ("Valid", "bool", None),
)


def load(root: Path):
    path = root / "tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_flight_profile_resolver_base", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--paste-output", type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.project_root / "tools" / "trajectory"))
    from flight_profile_reference import PROFILE_ORDER, PROFILES

    scalar = load(args.project_root)
    bp = scalar.load_helpers(args.project_root)
    forms = scalar.load_templates(args.project_root, bp)
    builder = scalar.Builder(bp, forms, FUNCTION)
    source = builder.get("FlightProfileResolveInputIdV1", "string", 0, 256)

    def setter(field, kind, value, x, y):
        name = f"FlightProfileResolveResult{field}V1"
        return builder.set(name, kind, x, y, value)

    resets = []
    for index, (field, kind, _attribute) in enumerate(FIELDS):
        resets.append(setter(field, kind, "false" if kind == "bool" else ("" if kind == "string" else "0.0"), 256 + index * 352, 0))
    bp.connect(builder.entry, "then", resets[0], "execute")
    for left, right in zip(resets, resets[1:]):
        bp.connect(left, "then", right, "execute")

    comparisons = []
    branches = []
    preset_chains = []
    base_x = 4672
    for profile_index, profile_id in enumerate(PROFILE_ORDER):
        profile = PROFILES[profile_id]
        y = profile_index * 1024
        comparison = builder.equal_string(base_x, y + 256, profile_id)
        bp.connect(source, "FlightProfileResolveInputIdV1", comparison, "A")
        branch = builder.add(f"profile_branch_{profile_index}", "branch", base_x + 256, y)
        bp.connect(comparison, "ReturnValue", branch, "Condition")
        chain = []
        for field_index, (field, kind, attribute) in enumerate(FIELDS):
            if attribute is None:
                value = "true"
            else:
                raw = getattr(profile, attribute)
                value = raw if isinstance(raw, str) else repr(float(raw))
            chain.append(setter(field, kind, value, base_x + 512 + field_index * 352, y))
        bp.connect(branch, "then", chain[0], "execute")
        for left, right in zip(chain, chain[1:]):
            bp.connect(left, "then", right, "execute")
        comparisons.append(comparison)
        branches.append(branch)
        preset_chains.append(chain)
    bp.connect(resets[-1], "then", branches[0], "execute")
    for left, right in zip(branches, branches[1:]):
        bp.connect(left, "else", right, "execute")

    full = "\n".join(node.text for node in builder.nodes) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full, encoding="utf-8")
    if args.paste_output:
        body = [re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", node.text) for node in builder.nodes[1:]]
        args.paste_output.parent.mkdir(parents=True, exist_ok=True)
        args.paste_output.write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
