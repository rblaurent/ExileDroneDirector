"""Build staged scalar trajectory evaluators for the client director.

The scalar seam is intentional: the same quintic kernel evaluates position
axes, lens channels, focus, speed, and future continuous camera properties.
All functions fail closed on non-finite input and publish results atomically.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


TARGET_ASSET = (
    "/Game/Mods/ExileDroneDirector/Core/Client/"
    "BPC_EDD_ClientDirector.BPC_EDD_ClientDirector"
)
TARGET_CLASS = (
    "/Script/Engine.BlueprintGeneratedClass'"
    "/Game/Mods/ExileDroneDirector/Core/Client/"
    "BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C'"
)

# The old ``x - x == 0`` predicate is mathematically valid under strict IEEE
# evaluation, but Blueprint bytecode compilation may fold the identical
# operands and incorrectly accept NaN.  Explicit representable-double bounds
# cannot be folded away and reject NaN and both infinities while accepting the
# complete finite binary64 domain.
DOUBLE_MAX_TEXT = "1.7976931348623157e+308"
DOUBLE_MIN_TEXT = "-1.7976931348623157e+308"


def load_helpers(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Build-WaypointCaptureGraph.py"
    spec = importlib.util.spec_from_file_location("edd_trajectory_scalar_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def set_default(node, pin: str, value: str) -> None:
    def mutate(line: str) -> str:
        if "DefaultValue=" in line:
            return re.sub(r'DefaultValue="[^"]*"', f'DefaultValue="{value}"', line, count=1)
        return line.replace(",PersistentGuid=", f',DefaultValue="{value}",PersistentGuid=', 1)
    node.mutate_pin(pin, mutate)


def retarget_function(node, member: str) -> None:
    node.text = re.sub(r'MemberName="[^"]+"', f'MemberName="{member}"', node.text, count=1)


def set_pin_type(node, pin: str, kind: str) -> None:
    category, subcategory = {
        "bool": ("bool", ""), "real": ("real", "double"), "string": ("string", "")
    }[kind]
    def mutate(line: str) -> str:
        line = re.sub(r'PinType\.PinCategory="[^"]+"', f'PinType.PinCategory="{category}"', line, count=1)
        return re.sub(r'PinType\.PinSubCategory="[^"]*"', f'PinType.PinSubCategory="{subcategory}"', line, count=1)
    node.mutate_pin(pin, mutate)


def retarget_variable(node, name: str, kind: str) -> None:
    match = re.search(r'VariableReference=\(MemberName="([^"]+)"', node.text)
    if match is None:
        raise RuntimeError(f"{node.key} has no member variable")
    old = match.group(1)
    node.text = re.sub(
        rf'VariableReference=\(MemberName="{re.escape(old)}"[^)]*\)',
        f'VariableReference=(MemberName="{name}",bSelfContext=True)', node.text, count=1,
    )
    node.text = node.text.replace(f'PinName="{old}"', f'PinName="{name}"')
    node.pins[name] = node.pins.pop(old)
    set_pin_type(node, name, kind)
    if "Output_Get" in node.pins:
        set_pin_type(node, "Output_Get", kind)
    def self_type(line: str) -> str:
        return re.sub(
            r'PinType\.PinSubCategoryObject="/Script/Engine\.BlueprintGeneratedClass\'[^\']+\'"',
            f'PinType.PinSubCategoryObject="{TARGET_CLASS}"', line, count=1,
        )
    node.mutate_pin("self", self_type)


def load_templates(root: Path, bp) -> dict[str, str]:
    blueprint = root / "tools" / "blueprint"
    capture = bp.read_blocks(blueprint / "templates" / "waypoint-capture-node-forms.eddgraph")
    live = bp.read_blocks(blueprint / "live-snippets" / "reset-repository-result-v1.eddgraph")
    sync = bp.read_blocks(blueprint / "snippets" / "sync-draft-waypoints-v1.eddgraph")
    linear = bp.read_blocks(blueprint / "templates" / "linear-playback-node-forms.eddgraph")
    strings = bp.read_blocks(blueprint / "templates" / "repository-decoder-native-node-forms.eddgraph")
    speed = bp.read_blocks(blueprint / "snippets" / "update-speed-controls.eddgraph")
    return {
        "entry": bp.find_block(capture, r"K2Node_FunctionEntry"),
        "get": bp.find_block(live, r"^Begin Object Class=/Script/BlueprintGraph\.K2Node_VariableGet "),
        "set": bp.find_block(live, r"^Begin Object Class=/Script/BlueprintGraph\.K2Node_VariableSet "),
        "branch": bp.find_block(sync, r"^Begin Object Class=/Script/BlueprintGraph\.K2Node_IfThenElse "),
        "math": bp.find_block(linear, r'MemberName="Multiply_DoubleDouble"'),
        "compare": bp.find_block(linear, r'MemberName="GreaterEqual_DoubleDouble"'),
        "string_equal": bp.find_block(strings, r'MemberName="EqualEqual_StrStr"'),
        "clamp": bp.find_block(speed, r'MemberName="FClamp"'),
    }


class Builder:
    def __init__(self, bp, forms, graph: str):
        self.bp, self.forms, self.graph = bp, forms, graph
        self.nodes, self.serial = [], {}
        bp.TARGET_ASSET, bp.TARGET_GRAPH = TARGET_ASSET, graph
        self.entry = self.add("entry", "entry", 0, 0)
        self.entry.text = re.sub(
            r'FunctionReference=\(MemberName="[^"]+"\)',
            f'FunctionReference=(MemberName="{graph}")', self.entry.text, count=1,
        )

    def add(self, key: str, form: str, x: int, y: int):
        block = self.forms[form]
        match = self.bp.BLOCK_RE.match(block)
        if match is None:
            raise RuntimeError(form)
        cls = match.group("class").rsplit(".", 1)[-1]
        index = self.serial.get(cls, 0); self.serial[cls] = index + 1
        name = "K2Node_FunctionEntry_0" if key == "entry" else f"{cls}_{index}"
        node = self.bp.Node.clone(key, block, name, x, y)
        self.nodes.append(node)
        return node

    def get(self, name: str, kind: str, x: int, y: int):
        node = self.add(f"get_{name}_{len(self.nodes)}", "get", x, y)
        retarget_variable(node, name, kind); return node

    def set(self, name: str, kind: str, x: int, y: int, default: str | None = None):
        node = self.add(f"set_{name}_{len(self.nodes)}", "set", x, y)
        retarget_variable(node, name, kind)
        if default is not None: set_default(node, name, default)
        return node

    def math(self, member: str, x: int, y: int, b: str | None = None):
        node = self.add(f"{member}_{len(self.nodes)}", "math", x, y)
        retarget_function(node, member)
        for pin in ("A", "B", "ReturnValue"): set_pin_type(node, pin, "real")
        if b is not None: set_default(node, "B", b)
        return node

    def equal_string(self, x: int, y: int, expected: str):
        node = self.add(f"str_{len(self.nodes)}", "string_equal", x, y)
        set_default(node, "B", expected); return node

    def finite(self, source, pin: str, x: int, y: int):
        lower = self.add(f"finite_lower_{len(self.nodes)}", "compare", x, y)
        retarget_function(lower, "GreaterEqual_DoubleDouble")
        set_default(lower, "B", DOUBLE_MIN_TEXT)
        upper = self.add(f"finite_upper_{len(self.nodes)}", "compare", x, y + 64)
        retarget_function(upper, "LessEqual_DoubleDouble")
        set_default(upper, "B", DOUBLE_MAX_TEXT)
        both = self.add(f"finite_and_{len(self.nodes)}", "compare", x + 208, y)
        retarget_function(both, "BooleanAND")
        for boolean_pin in ("A", "B", "ReturnValue"):
            set_pin_type(both, boolean_pin, "bool")
        self.bp.connect(source, pin, lower, "A")
        self.bp.connect(source, pin, upper, "A")
        self.bp.connect(lower, "ReturnValue", both, "A")
        self.bp.connect(upper, "ReturnValue", both, "B")
        return both

    def clamp(self, source, pin: str, x: int, y: int):
        node = self.add(f"clamp_{len(self.nodes)}", "clamp", x, y)
        set_default(node, "Min", "0.0"); set_default(node, "Max", "1.0")
        self.bp.connect(source, pin, node, "Value"); return node


def mul(b: Builder, left, left_pin, right, right_pin, x, y):
    node = b.math("Multiply_DoubleDouble", x, y)
    b.bp.connect(left, left_pin, node, "A"); b.bp.connect(right, right_pin, node, "B")
    return node


def mul_const(b: Builder, source, pin, value: str, x, y):
    node = b.math("Multiply_DoubleDouble", x, y, value)
    b.bp.connect(source, pin, node, "A"); return node


def add(b: Builder, left, left_pin, right, right_pin, x, y):
    node = b.math("Add_DoubleDouble", x, y)
    b.bp.connect(left, left_pin, node, "A"); b.bp.connect(right, right_pin, node, "B")
    return node


def sub(b: Builder, left, left_pin, right, right_pin, x, y):
    node = b.math("Subtract_DoubleDouble", x, y)
    b.bp.connect(left, left_pin, node, "A"); b.bp.connect(right, right_pin, node, "B")
    return node


def profile_formula(b: Builder, name: str, xnode, x: int, y: int):
    # Generate the accepted closed form with only multiply/add/subtract nodes.
    if name == "linear": return xnode, "ReturnValue"
    x2 = mul(b, xnode, "ReturnValue", xnode, "ReturnValue", x, y)
    if name == "accelerate_through": return x2, "ReturnValue"
    if name == "brake_into":
        two_x = mul_const(b, xnode, "ReturnValue", "2.0", x + 208, y)
        result = sub(b, two_x, "ReturnValue", x2, "ReturnValue", x + 416, y)
        return result, "ReturnValue"
    x3 = mul(b, x2, "ReturnValue", xnode, "ReturnValue", x + 208, y)
    if name == "smoothstep":
        three_x2 = mul_const(b, x2, "ReturnValue", "3.0", x + 416, y)
        two_x3 = mul_const(b, x3, "ReturnValue", "2.0", x + 416, y + 128)
        result = sub(b, three_x2, "ReturnValue", two_x3, "ReturnValue", x + 624, y)
        return result, "ReturnValue"
    x4 = mul(b, x3, "ReturnValue", xnode, "ReturnValue", x + 416, y)
    x5 = mul(b, x4, "ReturnValue", xnode, "ReturnValue", x + 624, y)
    if name == "smootherstep":
        a = mul_const(b, x3, "ReturnValue", "10.0", x + 832, y)
        c = mul_const(b, x4, "ReturnValue", "15.0", x + 832, y + 128)
        d = mul_const(b, x5, "ReturnValue", "6.0", x + 832, y + 256)
        ac = sub(b, a, "ReturnValue", c, "ReturnValue", x + 1040, y)
        result = add(b, ac, "ReturnValue", d, "ReturnValue", x + 1248, y)
        return result, "ReturnValue"
    x6 = mul(b, x5, "ReturnValue", xnode, "ReturnValue", x + 832, y)
    x7 = mul(b, x6, "ReturnValue", xnode, "ReturnValue", x + 1040, y)
    terms = [
        mul_const(b, x4, "ReturnValue", "35.0", x + 1248, y),
        mul_const(b, x5, "ReturnValue", "84.0", x + 1248, y + 128),
        mul_const(b, x6, "ReturnValue", "70.0", x + 1248, y + 256),
        mul_const(b, x7, "ReturnValue", "20.0", x + 1248, y + 384),
    ]
    first = sub(b, terms[0], "ReturnValue", terms[1], "ReturnValue", x + 1456, y)
    second = add(b, first, "ReturnValue", terms[2], "ReturnValue", x + 1664, y)
    result = sub(b, second, "ReturnValue", terms[3], "ReturnValue", x + 1872, y)
    return result, "ReturnValue"


def build_time_profile(bp, forms):
    b = Builder(bp, forms, "EvaluateTimeProfileV1")
    # Keep the one native-entry seam near the pasted body's vertical centre.
    # The entry itself is protected by Unreal and cannot be serialized into an
    # entry-free paste.  A centred seam lets the deterministic workflow frame
    # the lone entry, paste, and make one local exec connection.
    exec_y = 2000
    exec_x = 2080
    reset_value = b.set("TrajectoryResultValueV1", "real", exec_x, exec_y, "0.0")
    reset_d1 = b.set("TrajectoryResultDerivativeUV1", "real", exec_x + 224, exec_y, "0.0")
    reset_d2 = b.set("TrajectoryResultSecondDerivativeUV1", "real", exec_x + 448, exec_y, "0.0")
    reset_valid = b.set("TrajectoryResultValidV1", "bool", exec_x + 672, exec_y, "false")
    alpha = b.get("TrajectoryInputAlphaV1", "real", 0, 400)
    finite = b.finite(alpha, "TrajectoryInputAlphaV1", 224, 400)
    finite_branch = b.add("finite_branch", "branch", exec_x + 896, exec_y)
    profile = b.get("TrajectoryInputProfileV1", "string", 1152, 400)
    clamped = b.clamp(alpha, "TrajectoryInputAlphaV1", 448, 560)
    chain = [b.entry, reset_value, reset_d1, reset_d2, reset_valid, finite_branch]
    for left, right in zip(chain, chain[1:]): bp.connect(left, "then", right, "execute")
    bp.connect(finite, "ReturnValue", finite_branch, "Condition")
    prior_branch = finite_branch
    names = ("linear", "smoothstep", "smootherstep", "cinematic_s_curve", "accelerate_through", "brake_into")
    for index, name in enumerate(names):
        y = 400 + index * 720
        equal = b.equal_string(1376, y, name)
        bp.connect(profile, "TrajectoryInputProfileV1", equal, "A")
        branch = b.add(f"profile_branch_{name}", "branch", 1600, y - 400)
        if index == 0: bp.connect(prior_branch, "then", branch, "execute")
        else: bp.connect(prior_branch, "else", branch, "execute")
        bp.connect(equal, "ReturnValue", branch, "Condition")
        formula, formula_pin = profile_formula(b, name, clamped, 1824, y)
        store = b.set("TrajectoryResultValueV1", "real", 4112, y - 400)
        valid = b.set("TrajectoryResultValidV1", "bool", 4336, y - 400, "true")
        bp.connect(branch, "then", store, "execute")
        bp.connect(formula, formula_pin, store, "TrajectoryResultValueV1")
        bp.connect(store, "then", valid, "execute")
        prior_branch = branch
    return b.nodes


def coefficient(b: Builder, inputs, weights, x: int, y: int):
    terms = []
    for index, (source, pin) in enumerate(inputs):
        weight = weights[index]
        if weight == 0: continue
        terms.append(mul_const(b, source, pin, repr(float(weight)), x, y + len(terms) * 112))
    current = terms[0]
    for index, term in enumerate(terms[1:]):
        current = add(b, current, "ReturnValue", term, "ReturnValue", x + 224 * (index + 1), y)
    return current


def horner(b: Builder, coefficients, u, derivative: int, x: int, y: int):
    values = list(coefficients)
    if derivative == 1: values = [mul_const(b, value, "ReturnValue", repr(float(i)), x, y + i*96) for i, value in enumerate(values)][1:]
    elif derivative == 2: values = [mul_const(b, value, "ReturnValue", repr(float(i*(i-1))), x, y + i*96) for i, value in enumerate(values)][2:]
    current = values[-1]
    for index, value in enumerate(reversed(values[:-1])):
        product = mul(b, current, "ReturnValue", u, "ReturnValue", x + 256*(index+1), y)
        current = add(b, product, "ReturnValue", value, "ReturnValue", x + 256*(index+1)+128, y)
    return current


def build_quintic(bp, forms):
    b = Builder(bp, forms, "EvaluateQuinticScalarV1")
    # Keep the entry/reset seam beside the visual centre of this tall graph.
    # Unreal centres a pasted selection by its whole bounding box; putting the
    # first executable at y=0 makes it land against the toolbar and turns one
    # required native-entry wire into a brittle navigation exercise.
    exec_y = 3000
    reset_value = b.set("TrajectoryResultValueV1", "real", 256, exec_y, "0.0")
    reset_d1 = b.set("TrajectoryResultDerivativeUV1", "real", 480, exec_y, "0.0")
    reset_d2 = b.set("TrajectoryResultSecondDerivativeUV1", "real", 704, exec_y, "0.0")
    reset_valid = b.set("TrajectoryResultValidV1", "bool", 928, exec_y, "false")
    names = (
        "TrajectoryInputAlphaV1", "TrajectoryInputStartValueV1", "TrajectoryInputStartVelocityUV1",
        "TrajectoryInputStartAccelerationUV1", "TrajectoryInputEndValueV1", "TrajectoryInputEndVelocityUV1",
        "TrajectoryInputEndAccelerationUV1",
    )
    inputs = [b.get(name, "real", 0, 480 + i*128) for i, name in enumerate(names)]
    finite = [b.finite(node, name, 256, 480 + i*128) for i, (node, name) in enumerate(zip(inputs, names))]
    conjunction = finite[0]
    for index, condition in enumerate(finite[1:]):
        node = b.add(f"finite_and_{index}", "compare", 736 + index*208, 480)
        retarget_function(node, "BooleanAND")
        for pin in ("A", "B", "ReturnValue"): set_pin_type(node, pin, "bool")
        bp.connect(conjunction, "ReturnValue", node, "A"); bp.connect(condition, "ReturnValue", node, "B")
        conjunction = node
    branch = b.add("finite_branch", "branch", 2400, exec_y)
    chain = [b.entry, reset_value, reset_d1, reset_d2, reset_valid, branch]
    for left, right in zip(chain, chain[1:]): bp.connect(left, "then", right, "execute")
    bp.connect(conjunction, "ReturnValue", branch, "Condition")
    u = b.clamp(inputs[0], names[0], 480, 1440)
    scalar_inputs = [(node, name) for node, name in zip(inputs[1:], names[1:])]
    weights = (
        (1,0,0,0,0,0),
        (0,1,0,0,0,0),
        (0,0,.5,0,0,0),
        (-10,-6,-1.5,10,-4,.5),
        (15,8,1.5,-15,7,-1),
        (-6,-3,-.5,6,-3,.5),
    )
    coefficients = [coefficient(b, scalar_inputs, row, 768, 1600+i*768) for i, row in enumerate(weights)]
    value = horner(b, coefficients, u, 0, 2600, 1600)
    d1 = horner(b, coefficients, u, 1, 2600, 2600)
    d2 = horner(b, coefficients, u, 2, 2600, 3600)
    store_value = b.set("TrajectoryResultValueV1", "real", 4752, exec_y)
    store_d1 = b.set("TrajectoryResultDerivativeUV1", "real", 4976, exec_y)
    store_d2 = b.set("TrajectoryResultSecondDerivativeUV1", "real", 5200, exec_y)
    store_valid = b.set("TrajectoryResultValidV1", "bool", 5424, exec_y, "true")
    bp.connect(branch, "then", store_value, "execute")
    bp.connect(value, "ReturnValue", store_value, "TrajectoryResultValueV1")
    bp.connect(store_value, "then", store_d1, "execute"); bp.connect(d1, "ReturnValue", store_d1, "TrajectoryResultDerivativeUV1")
    bp.connect(store_d1, "then", store_d2, "execute"); bp.connect(d2, "ReturnValue", store_d2, "TrajectoryResultSecondDerivativeUV1")
    bp.connect(store_d2, "then", store_valid, "execute")
    return b.nodes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--paste-dir", type=Path)
    args = parser.parse_args()
    bp = load_helpers(args.project_root); forms = load_templates(args.project_root, bp)
    products = {
        "evaluate-time-profile-v1.eddgraph": build_time_profile(bp, forms),
        "evaluate-quintic-scalar-v1.eddgraph": build_quintic(bp, forms),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.paste_dir: args.paste_dir.mkdir(parents=True, exist_ok=True)
    for name, nodes in products.items():
        (args.output_dir/name).write_text("\n".join(n.text for n in nodes)+"\n", encoding="utf-8")
        if args.paste_dir:
            body = [
                re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', "", n.text)
                for n in nodes[1:]
            ]
            (args.paste_dir/name).write_text("\n".join(body)+"\n", encoding="utf-8")


if __name__ == "__main__": main()
