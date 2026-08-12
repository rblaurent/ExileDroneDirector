"""Build deterministic, compiler-safe orientation-control primitive graphs.

Quaternion logarithms and tangent rates are vectors.  Quaternions remain only
at actual orientation/control boundaries.  Enhanced exposes no Blueprint-safe
Make Quat node, so the two Quat_Exp arguments are assembled in explicit scratch
members through the native by-reference Quat_SetComponents call.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


FUNCTIONS = (
    "ComputeOrientationLogDeltaV1",
    "ComputeOrientationTangentRateV1",
    "BuildOrientationSegmentControlsV1",
)


def load_scalar(root: Path):
    path = root / "tools" / "blueprint" / "Build-TrajectoryScalarEvaluatorGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_orientation_scalar", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def quat_variable(scalar, node, name: str) -> None:
    scalar.retarget_variable(node, name, "vector")
    for pin in (name, "Output_Get"):
        if pin in node.pins:
            node.mutate_pin(pin, lambda line: line.replace(
                "/Script/CoreUObject.Vector'", "/Script/CoreUObject.Quat'"
            ))


def forms(root: Path, scalar, bp):
    result = scalar.load_templates(root, bp)
    templates = root / "tools" / "blueprint" / "templates"
    qeval = bp.read_blocks(templates / "trajectory-quaternion-native-node-forms.eddgraph")
    qcompiler = bp.read_blocks(templates / "orientation-compiler-native-node-forms.eddgraph")
    qbreak = bp.read_blocks(templates / "repository-codec-break-quat-node-form.eddgraph")
    vector = bp.read_blocks(templates / "repository-codec-vector-node-forms.eddgraph")
    marker = bp.read_blocks(templates / "path-preview-marker-node-forms.eddgraph")
    speed = bp.read_blocks(root / "tools" / "blueprint" / "snippets" / "update-speed-controls.eddgraph")
    for key, member, blocks in (
        ("qfinite", "Quat_IsFinite", qeval),
        ("qnormal", "Quat_IsNormalized", qeval),
        ("qnormalize", "Quat_Normalized", qeval),
        ("qslerp", "Quat_Slerp", qeval),
        ("qmul", "Multiply_QuatQuat", qcompiler),
        ("qinverse", "Quat_Inversed", qcompiler),
        ("qlog", "Quat_Log", qcompiler),
        ("qexp", "Quat_Exp", qcompiler),
        ("qsetcomponents", "Quat_SetComponents", qcompiler),
        ("vsize", "VSize", qcompiler),
    ):
        result[key] = bp.find_block(blocks, rf'MemberName="{member}"')
    result["qbreak"] = bp.find_block(qbreak, r'MemberName="BreakQuat"')
    result["vbreak"] = bp.find_block(vector, r'MemberName="BreakVector"')
    result["vmake"] = bp.find_block(marker, r'MemberName="MakeVector"')
    result["select"] = bp.find_block(speed, r'MemberName="SelectFloat"')
    return result


class Compiler:
    def __init__(self, root: Path, function: str):
        self.scalar = load_scalar(root)
        self.bp = self.scalar.load_helpers(root)
        self.b = self.scalar.Builder(self.bp, forms(root, self.scalar, self.bp), function)

    def qget(self, name, x, y):
        n = self.b.get(name, "vector", x, y); quat_variable(self.scalar, n, name); return n

    def qset(self, name, x, y, default=None):
        n = self.b.set(name, "vector", x, y); quat_variable(self.scalar, n, name)
        if default is not None: self.scalar.set_default(n, name, default)
        return n

    def vget(self, name, x, y): return self.b.get(name, "vector", x, y)
    def vset(self, name, x, y, default=None): return self.b.set(name, "vector", x, y, default)
    def call(self, form, x, y): return self.b.add(f"{form}_{len(self.b.nodes)}", form, x, y)
    def math(self, member, x, y, value=None): return self.b.math(member, x, y, value)

    def guard_quat(self, source, pin, normalized, x, y):
        finite = self.call("qfinite", x, y); self.bp.connect(source, pin, finite, "Q")
        if not normalized: return finite
        normal = self.call("qnormal", x, y + 96); self.bp.connect(source, pin, normal, "Q")
        both = self.call("compare", x + 224, y)
        self.scalar.retarget_function(both, "BooleanAND")
        for p in ("A", "B", "ReturnValue"): self.scalar.set_pin_type(both, p, "bool")
        self.bp.connect(finite, "ReturnValue", both, "A"); self.bp.connect(normal, "ReturnValue", both, "B")
        return both

    def guard_vector(self, source, pin, x, y):
        broken = self.call("vbreak", x, y); self.bp.connect(source, pin, broken, "InVec")
        return self.and_all([self.b.finite(broken, axis, x + 224, y + i * 144)
                             for i, axis in enumerate("XYZ")], x + 688, y)

    def and_all(self, guards, x, y):
        current = guards[0]
        for i, guard in enumerate(guards[1:]):
            node = self.call("compare", x + i * 208, y)
            self.scalar.retarget_function(node, "BooleanAND")
            for p in ("A", "B", "ReturnValue"): self.scalar.set_pin_type(node, p, "bool")
            self.bp.connect(current, "ReturnValue", node, "A"); self.bp.connect(guard, "ReturnValue", node, "B")
            current = node
        return current

    def scale_vector(self, source, pin, factor, factor_pin, x, y):
        broken = self.call("vbreak", x, y); self.bp.connect(source, pin, broken, "InVec")
        made = self.call("vmake", x + 480, y)
        for i, axis in enumerate("XYZ"):
            mul = self.math("Multiply_DoubleDouble", x + 224, y + i * 96)
            self.bp.connect(broken, axis, mul, "A"); self.bp.connect(factor, factor_pin, mul, "B")
            self.bp.connect(mul, "ReturnValue", made, axis)
        return made


def build_log_delta(root: Path):
    c = Compiler(root, FUNCTIONS[0]); b, bp = c.b, c.bp
    reset_delta = c.vset("OrientationResultDeltaVectorV1", 256, 1200, "0, 0, 0")
    reset_end = c.qset("OrientationResultAlignedEndQuatV1", 512, 1200, "0, 0, 0, 1")
    reset_valid = b.set("OrientationResultValidV1", "bool", 768, 1200, "false")
    for l, r in zip((b.entry, reset_delta, reset_end), (reset_delta, reset_end, reset_valid)): bp.connect(l, "then", r, "execute")
    start = c.qget("OrientationInputStartQuatV1", 0, 160); end = c.qget("OrientationInputEndQuatV1", 0, 480)
    all_valid = c.and_all([c.guard_quat(start, "OrientationInputStartQuatV1", True, 256, 160),
                           c.guard_quat(end, "OrientationInputEndQuatV1", True, 256, 480)], 768, 160)
    branch = c.call("branch", 1024, 1200); bp.connect(reset_valid, "then", branch, "execute"); bp.connect(all_valid, "ReturnValue", branch, "Condition")
    aligned = c.call("qslerp", 1024, 400); bp.connect(start, "OrientationInputStartQuatV1", aligned, "A"); bp.connect(end, "OrientationInputEndQuatV1", aligned, "B"); c.scalar.set_default(aligned, "Alpha", "1.0")
    inverse = c.call("qinverse", 1280, 160); bp.connect(start, "OrientationInputStartQuatV1", inverse, "Q")
    relative = c.call("qmul", 1536, 320); bp.connect(inverse, "ReturnValue", relative, "A"); bp.connect(aligned, "ReturnValue", relative, "B")
    logged = c.call("qlog", 1792, 320); bp.connect(relative, "ReturnValue", logged, "Q")
    broken = c.call("qbreak", 2048, 320); bp.connect(logged, "ReturnValue", broken, "InQuat")
    delta = c.call("vmake", 2528, 320)
    for i, axis in enumerate("XYZ"):
        mul = c.math("Multiply_DoubleDouble", 2272, 320 + i * 96, "2.0"); bp.connect(broken, axis, mul, "A"); bp.connect(mul, "ReturnValue", delta, axis)
    store_delta = c.vset("OrientationResultDeltaVectorV1", 3072, 1200); store_end = c.qset("OrientationResultAlignedEndQuatV1", 3328, 1200); store_valid = b.set("OrientationResultValidV1", "bool", 3584, 1200, "true")
    bp.connect(branch, "then", store_delta, "execute"); bp.connect(store_delta, "then", store_end, "execute"); bp.connect(store_end, "then", store_valid, "execute")
    bp.connect(delta, "ReturnValue", store_delta, "OrientationResultDeltaVectorV1"); bp.connect(aligned, "ReturnValue", store_end, "OrientationResultAlignedEndQuatV1")
    return bp, b.nodes


def build_tangent(root: Path):
    c = Compiler(root, FUNCTIONS[1]); b, bp = c.b, c.bp
    reset = c.vset("OrientationResultTangentRateVectorV1", 256, 1800, "0, 0, 0"); reset_valid = b.set("OrientationResultValidV1", "bool", 512, 1800, "false")
    bp.connect(b.entry, "then", reset, "execute"); bp.connect(reset, "then", reset_valid, "execute")
    prev = c.vget("OrientationInputPreviousDeltaVectorV1", 0, 160); nxt = c.vget("OrientationInputNextDeltaVectorV1", 0, 480)
    pd = b.get("OrientationInputPreviousDurationV1", "real", 0, 800); nd = b.get("OrientationInputNextDurationV1", "real", 0, 960)
    guards = [c.guard_vector(prev, "OrientationInputPreviousDeltaVectorV1", 256, 160), c.guard_vector(nxt, "OrientationInputNextDeltaVectorV1", 256, 640)]
    for src, name, y in ((pd, "OrientationInputPreviousDurationV1", 1120), (nd, "OrientationInputNextDurationV1", 1280)):
        finite = b.finite(src, name, 1024, y); positive = c.call("compare", 1472, y); c.scalar.retarget_function(positive, "Greater_DoubleDouble"); c.scalar.set_default(positive, "B", "0.0"); bp.connect(src, name, positive, "A"); guards.extend((finite, positive))
    all_valid = c.and_all(guards, 1920, 160); branch = c.call("branch", 3072, 1800); bp.connect(reset_valid, "then", branch, "execute"); bp.connect(all_valid, "ReturnValue", branch, "Condition")
    inv_pd = c.math("Divide_DoubleDouble", 1920, 800); c.scalar.set_default(inv_pd, "A", "1.0"); bp.connect(pd, "OrientationInputPreviousDurationV1", inv_pd, "B")
    inv_nd = c.math("Divide_DoubleDouble", 1920, 960); c.scalar.set_default(inv_nd, "A", "1.0"); bp.connect(nd, "OrientationInputNextDurationV1", inv_nd, "B")
    pr = c.scale_vector(prev, "OrientationInputPreviousDeltaVectorV1", inv_pd, "ReturnValue", 2176, 480); nr = c.scale_vector(nxt, "OrientationInputNextDeltaVectorV1", inv_nd, "ReturnValue", 2176, 960)
    pbr = c.call("vbreak", 2944, 480); nbr = c.call("vbreak", 2944, 960); bp.connect(pr, "ReturnValue", pbr, "InVec"); bp.connect(nr, "ReturnValue", nbr, "InVec")
    candidate = c.call("vmake", 3456, 720)
    for i, axis in enumerate("XYZ"):
        add = c.math("Add_DoubleDouble", 3168, 640 + i * 128); half = c.math("Multiply_DoubleDouble", 3392, 640 + i * 128, "0.5")
        bp.connect(pbr, axis, add, "A"); bp.connect(nbr, axis, add, "B"); bp.connect(add, "ReturnValue", half, "A"); bp.connect(half, "ReturnValue", candidate, axis)
    ps = c.call("vsize", 3712, 400); ns = c.call("vsize", 3712, 560); cs = c.call("vsize", 3712, 800)
    bp.connect(pr, "ReturnValue", ps, "A"); bp.connect(nr, "ReturnValue", ns, "A"); bp.connect(candidate, "ReturnValue", cs, "A")
    less = c.call("compare", 3968, 480); c.scalar.retarget_function(less, "LessEqual_DoubleDouble"); bp.connect(ps, "ReturnValue", less, "A"); bp.connect(ns, "ReturnValue", less, "B")
    choose_min = c.call("select", 4192, 480); bp.connect(ps, "ReturnValue", choose_min, "A"); bp.connect(ns, "ReturnValue", choose_min, "B"); bp.connect(less, "ReturnValue", choose_min, "bPickA")
    limit = c.math("Multiply_DoubleDouble", 4448, 480, "3.0"); bp.connect(choose_min, "ReturnValue", limit, "A")
    over = c.call("compare", 4448, 720); c.scalar.retarget_function(over, "Greater_DoubleDouble"); bp.connect(cs, "ReturnValue", over, "A"); bp.connect(limit, "ReturnValue", over, "B")
    nonzero = c.call("compare", 4448, 880); c.scalar.retarget_function(nonzero, "Greater_DoubleDouble"); c.scalar.set_default(nonzero, "B", "1e-12"); bp.connect(cs, "ReturnValue", nonzero, "A")
    scale_guard = c.call("compare", 4672, 800); c.scalar.retarget_function(scale_guard, "BooleanAND")
    for p in ("A", "B", "ReturnValue"): c.scalar.set_pin_type(scale_guard, p, "bool")
    bp.connect(over, "ReturnValue", scale_guard, "A"); bp.connect(nonzero, "ReturnValue", scale_guard, "B")
    safe_magnitude = c.math("Add_DoubleDouble", 4672, 560, "1e-12"); bp.connect(cs, "ReturnValue", safe_magnitude, "A")
    ratio = c.math("Divide_DoubleDouble", 4896, 560); bp.connect(limit, "ReturnValue", ratio, "A"); bp.connect(safe_magnitude, "ReturnValue", ratio, "B")
    select = c.call("select", 5152, 720); bp.connect(ratio, "ReturnValue", select, "A"); c.scalar.set_default(select, "B", "1.0"); bp.connect(scale_guard, "ReturnValue", select, "bPickA")
    result = c.scale_vector(candidate, "ReturnValue", select, "ReturnValue", 5408, 720)
    store = c.vset("OrientationResultTangentRateVectorV1", 5920, 1800); valid = b.set("OrientationResultValidV1", "bool", 6176, 1800, "true")
    bp.connect(branch, "then", store, "execute"); bp.connect(store, "then", valid, "execute"); bp.connect(result, "ReturnValue", store, "OrientationResultTangentRateVectorV1")
    return bp, b.nodes


def build_controls(root: Path):
    c = Compiler(root, FUNCTIONS[2]); b, bp = c.b, c.bp
    rs = c.qset("OrientationResultStartControlQuatV1", 256, 1800, "0, 0, 0, 1"); re_ = c.qset("OrientationResultEndControlQuatV1", 512, 1800, "0, 0, 0, 1"); rv = b.set("OrientationResultValidV1", "bool", 768, 1800, "false")
    bp.connect(b.entry, "then", rs, "execute"); bp.connect(rs, "then", re_, "execute"); bp.connect(re_, "then", rv, "execute")
    start = c.qget("OrientationInputStartQuatV1", 0, 160); end = c.qget("OrientationInputEndQuatV1", 0, 400)
    sr = c.vget("OrientationInputStartTangentRateVectorV1", 0, 640); er = c.vget("OrientationInputEndTangentRateVectorV1", 0, 880); duration = b.get("OrientationInputDurationV1", "real", 0, 1120)
    guards = [c.guard_quat(start, "OrientationInputStartQuatV1", True, 256, 160), c.guard_quat(end, "OrientationInputEndQuatV1", True, 256, 400), c.guard_vector(sr, "OrientationInputStartTangentRateVectorV1", 256, 640), c.guard_vector(er, "OrientationInputEndTangentRateVectorV1", 256, 1120), b.finite(duration, "OrientationInputDurationV1", 1024, 1600)]
    positive = c.call("compare", 1472, 1600); c.scalar.retarget_function(positive, "Greater_DoubleDouble"); c.scalar.set_default(positive, "B", "0.0"); bp.connect(duration, "OrientationInputDurationV1", positive, "A"); guards.append(positive)
    all_valid = c.and_all(guards, 1920, 160); branch = c.call("branch", 3072, 1800); bp.connect(rv, "then", branch, "execute"); bp.connect(all_valid, "ReturnValue", branch, "Condition")
    sixth = c.math("Divide_DoubleDouble", 3072, 1120, "6.0"); bp.connect(duration, "OrientationInputDurationV1", sixth, "A")
    negative = c.math("Multiply_DoubleDouble", 3296, 1200, "-1.0"); bp.connect(sixth, "ReturnValue", negative, "A")
    sv = c.scale_vector(sr, "OrientationInputStartTangentRateVectorV1", sixth, "ReturnValue", 3552, 480); ev = c.scale_vector(er, "OrientationInputEndTangentRateVectorV1", negative, "ReturnValue", 3552, 960)
    sb = c.call("vbreak", 4320, 480); eb = c.call("vbreak", 4320, 960); bp.connect(sv, "ReturnValue", sb, "InVec"); bp.connect(ev, "ReturnValue", eb, "InVec")
    scratch_s = c.qget("OrientationScratchStartExponentQuatV1", 4320, 720); scratch_e = c.qget("OrientationScratchEndExponentQuatV1", 4320, 1200)
    set_s = c.call("qsetcomponents", 4704, 480); set_e = c.call("qsetcomponents", 4960, 960)
    bp.connect(scratch_s, "OrientationScratchStartExponentQuatV1", set_s, "Q"); bp.connect(scratch_e, "OrientationScratchEndExponentQuatV1", set_e, "Q")
    for axis in "XYZ": bp.connect(sb, axis, set_s, axis); bp.connect(eb, axis, set_e, axis)
    c.scalar.set_default(set_s, "W", "0.0"); c.scalar.set_default(set_e, "W", "0.0")
    bp.connect(branch, "then", set_s, "execute"); bp.connect(set_s, "then", set_e, "execute")
    se = c.call("qexp", 5216, 480); ee = c.call("qexp", 5216, 960); bp.connect(scratch_s, "OrientationScratchStartExponentQuatV1", se, "Q"); bp.connect(scratch_e, "OrientationScratchEndExponentQuatV1", ee, "Q")
    sc = c.call("qmul", 5472, 480); ec = c.call("qmul", 5472, 960); bp.connect(start, "OrientationInputStartQuatV1", sc, "A"); bp.connect(se, "ReturnValue", sc, "B"); bp.connect(end, "OrientationInputEndQuatV1", ec, "A"); bp.connect(ee, "ReturnValue", ec, "B")
    sn = c.call("qnormalize", 5728, 480); en = c.call("qnormalize", 5728, 960); bp.connect(sc, "ReturnValue", sn, "Q"); bp.connect(ec, "ReturnValue", en, "Q")
    ss = c.qset("OrientationResultStartControlQuatV1", 6048, 1800); es = c.qset("OrientationResultEndControlQuatV1", 6304, 1800); vs = b.set("OrientationResultValidV1", "bool", 6560, 1800, "true")
    bp.connect(set_e, "then", ss, "execute"); bp.connect(ss, "then", es, "execute"); bp.connect(es, "then", vs, "execute")
    bp.connect(sn, "ReturnValue", ss, "OrientationResultStartControlQuatV1"); bp.connect(en, "ReturnValue", es, "OrientationResultEndControlQuatV1")
    return bp, b.nodes


BUILDERS = dict(zip(FUNCTIONS, (build_log_delta, build_tangent, build_controls)))


def main():
    p = argparse.ArgumentParser(); p.add_argument("--project-root", type=Path, required=True); p.add_argument("--output-dir", type=Path, required=True); p.add_argument("--paste-dir", type=Path); a = p.parse_args()
    a.output_dir.mkdir(parents=True, exist_ok=True)
    if a.paste_dir: a.paste_dir.mkdir(parents=True, exist_ok=True)
    for function, builder in BUILDERS.items():
        _bp, nodes = builder(a.project_root); stem = re.sub(r"(?<!^)(?=[A-Z])", "-", function).lower()
        (a.output_dir / f"{stem}.eddgraph").write_text("\n".join(n.text for n in nodes) + "\n", encoding="utf-8")
        if a.paste_dir:
            body = [re.sub(r",LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)", "", n.text) for n in nodes[1:]]
            (a.paste_dir / f"{stem}-paste.eddgraph").write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__": main()
