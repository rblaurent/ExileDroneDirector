"""Structural and executable contracts for carrier-frame absolute evaluation."""
from __future__ import annotations
import argparse, importlib.util, math, random, re, sys
from pathlib import Path

TANGENTS = "CarrierFrameCompiledTangentsV1"; QUATS = "CarrierFrameCompiledQuatsV1"
COMPILE_VALID = "CarrierFrameCompileValidV1"; ELAPSED = "CarrierFrameInputElapsedSecondsV1"
TOTAL = "CarrierFrameCompiledTotalSecondsV1"; STEP = "CarrierFrameCompiledFixedStepSecondsV1"
SEGMENT = "CarrierFrameResultSegmentIndexV1"; ALPHA = "CarrierFrameResultAlphaV1"; QUAT = "CarrierFrameResultQuatV1"
COMPLETE = "CarrierFrameResultCompleteV1"; VALID = "CarrierFrameResultValidV1"; SCRATCH = "CarrierFrameScratchValidV1"
IDENTITY = (0.0, 0.0, 0.0, 1.0)
READS = {TANGENTS, QUATS, COMPILE_VALID, ELAPSED, TOTAL, STEP, SCRATCH}
WRITES = {SEGMENT, ALPHA, QUAT, COMPLETE, VALID, SCRATCH}
FORBIDDEN = ("BodyQuat", "GimbalQuat", "CameraTransform", "CameraOperator", "AirframeDesired", "AirframePrebake", "DeltaSeconds", "PlaybackTime", "Event", "Repository", "Server")


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module); return module
def member(node):
    match = re.search(r'MemberName="([^"]+)"', node.text); return None if match is None else match.group(1)
def variable(node):
    match = re.search(r'VariableReference=\(MemberName="([^"]+)"', node.text); return None if match is None else match.group(1)
def default(node, pin):
    match = re.search(r'(?:^|,)DefaultValue="([^"]*)"', node.pins[pin].body); return "" if match is None else match.group(1)
def parse_default(text):
    if text == "true": return True
    if text == "false": return False
    named = re.fullmatch(r"\(X=([^,]+),Y=([^,]+),Z=([^,]+),W=([^)]+)\)", text)
    if named: return tuple(float(value) for value in named.groups())
    if "," in text: return tuple(float(value.strip()) for value in text.split(","))
    try: return int(text) if re.fullmatch(r"-?\d+", text) else float(text)
    except ValueError: return text
def dot(left, right): return sum(a * b for a, b in zip(left, right))
def length(value): return math.sqrt(dot(value, value))
def rotate(quat, vector):
    x, y, z, w = quat
    def multiply(left, right):
        lx, ly, lz, lw = left; rx, ry, rz, rw = right
        return (lw*rx+lx*rw+ly*rz-lz*ry, lw*ry-lx*rz+ly*rw+lz*rx, lw*rz+lx*ry-ly*rx+lz*rw, lw*rw-lx*rx-ly*ry-lz*rz)
    return multiply(multiply(quat, (*vector, 0.0)), (-x, -y, -z, w))[:3]
def close_quat(left, right, tolerance=3e-9): return max(abs(a-b) for a,b in zip(left,right)) <= tolerance


class Interpreter:
    def __init__(self, nodes, state, oracle):
        self.nodes = nodes; self.state = dict(state); self.oracle = oracle; self.loop_values = {}; self.pin_owner = {}
        for node in nodes.values():
            for pin in node.pins.values():
                match = re.search(r"PinId=([0-9A-F]{32})", pin.body)
                if match: self.pin_owner[(node.name, match.group(1))] = (node, pin)
    def source(self, node, pin_name):
        for link in node.pins[pin_name].links:
            target = self.pin_owner.get(link)
            if target is not None and 'Direction="EGPD_Output"' in target[1].body: return target[0], target[1].name
        return None
    def value(self, node, pin_name):
        source = self.source(node, pin_name); return self.output(*source) if source else parse_default(default(node, pin_name))
    def output(self, node, pin_name):
        if "K2Node_Variable" in node.node_class: return self.state[variable(node)]
        if "K2Node_MacroInstance" in node.node_class:
            element, index = self.loop_values[node.name]
            if pin_name == "Array Element": return element
            if pin_name == "Array Index": return index
            raise RuntimeError(f"loop output {node.name}.{pin_name}")
        name = member(node)
        if "K2Node_GetArrayItem" in node.node_class: return self.value(node, "Array")[int(self.value(node, "Dimension 1"))]
        if name == "Array_Length": return len(self.value(node, "TargetArray"))
        if name == "IsFinite": return math.isfinite(self.value(node, "A"))
        if name == "Quat_IsFinite": return all(math.isfinite(value) for value in self.value(node, "Q"))
        if name == "Quat_Size": return length(self.value(node, "Q"))
        if name == "Quat_GetAxisX": return rotate(self.value(node, "Q"), (1.0, 0.0, 0.0))
        if name == "BreakQuat": return self.value(node, "InQuat")["XYZW".index(pin_name)]
        if name == "VSize": return length(self.value(node, "A"))
        if name == "BooleanAND": return bool(self.value(node, "A")) and bool(self.value(node, "B"))
        if name == "Conv_IntToDouble": return float(self.value(node, "InInt"))
        if name == "FFloor": return math.floor(self.value(node, "A"))
        if name == "FClamp": return min(max(self.value(node, "Value"), self.value(node, "Min")), self.value(node, "Max"))
        if name == "SelectFloat": return self.value(node, "A") if self.value(node, "bPickA") else self.value(node, "B")
        if name == "Quat_Slerp": return self.oracle._slerp(self.value(node, "A"), self.value(node, "B"), self.value(node, "Alpha"))
        if "A" not in node.pins or "B" not in node.pins: raise RuntimeError(f"unsupported output {node.name}:{name}.{pin_name}")
        left, right = self.value(node, "A"), self.value(node, "B")
        operations = {
            "GreaterEqual_IntInt": lambda: int(left) >= int(right), "LessEqual_IntInt": lambda: int(left) <= int(right), "EqualEqual_IntInt": lambda: int(left) == int(right),
            "Greater_DoubleDouble": lambda: left > right, "GreaterEqual_DoubleDouble": lambda: left >= right, "Less_DoubleDouble": lambda: left < right, "LessEqual_DoubleDouble": lambda: left <= right,
            "Subtract_IntInt": lambda: int(left)-int(right), "Add_IntInt": lambda: int(left)+int(right), "Multiply_DoubleDouble": lambda: left*right,
            "Add_DoubleDouble": lambda: left+right, "Subtract_DoubleDouble": lambda: left-right, "Divide_DoubleDouble": lambda: left/right,
            "Subtract_VectorVector": lambda: tuple(a-b for a,b in zip(left,right)),
        }
        if name in operations: return operations[name]()
        raise RuntimeError(f"unsupported output {node.name}:{name}.{pin_name}")
    def exec_target(self, node, pin_name="then"):
        if pin_name not in node.pins: return None
        for link in node.pins[pin_name].links:
            target = self.pin_owner.get(link)
            if target is not None and target[1].name in ("execute", "Exec"): return target[0]
        return None
    def execute_chain(self, current):
        visits = 0
        while current is not None:
            visits += 1
            if visits > 64: raise RuntimeError("execution cycle")
            if "K2Node_VariableSet" in current.node_class:
                name = variable(current); self.state[name] = self.value(current, name); current = self.exec_target(current)
            elif "K2Node_IfThenElse" in current.node_class:
                current = self.exec_target(current, "then" if self.value(current, "Condition") else "else")
            elif "K2Node_MacroInstance" in current.node_class:
                for index, element in enumerate(self.value(current, "Array")):
                    self.loop_values[current.name] = (element, index); body = self.exec_target(current, "LoopBody")
                    if body is not None: self.execute_chain(body)
                current = self.exec_target(current, "Completed")
            else: raise RuntimeError(f"unsupported execution {current.name}:{member(current)}")
    def run(self):
        entries = [node for node in self.nodes.values() if "K2Node_FunctionEntry" in node.node_class]
        if entries: current = self.exec_target(entries[0])
        else:
            roots = [node for node in self.nodes.values() if "execute" in node.pins and not node.pins["execute"].links]
            if len(roots) != 1: raise RuntimeError(f"paste root count {len(roots)}")
            current = roots[0]
        self.execute_chain(current); return self.state


def state_from(track, elapsed):
    return {TANGENTS:list(track.tangents), QUATS:list(track.rotations), COMPILE_VALID:True, ELAPSED:elapsed, TOTAL:track.total_seconds, STEP:track.fixed_step_seconds,
            SEGMENT:777, ALPHA:777.0, QUAT:(7.0,7.0,7.0,7.0), COMPLETE:True, VALID:True, SCRATCH:True}
def assert_invalid(contracts, nodes, oracle, state, label):
    result = Interpreter(nodes, state, oracle).run(); contracts.require(result[SEGMENT] == -1 and result[ALPHA] == 0.0 and result[QUAT] == IDENTITY, f"{label}: result reset")
    contracts.require(result[COMPLETE] is False and result[VALID] is False and result[SCRATCH] is False, f"{label}: invalid")


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--graph", type=Path, required=True); parser.add_argument("--paste", action="store_true"); args = parser.parse_args()
    contracts = load(args.project_root / "tools/blueprint/Test-WaypointCaptureContracts.py", "edd_carrier_eval_contract_base")
    oracle = load(args.project_root / "tools/trajectory/carrier_frame_transport_reference.py", "edd_carrier_eval_oracle")
    nodes = contracts.parse_graph(args.graph); contracts.require(len(nodes) == (116 if args.paste else 117), f"evaluator node count {len(nodes)}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]; contracts.require(len(entries) == (0 if args.paste else 1), "entry count")
    getters = [node for node in nodes.values() if "K2Node_VariableGet" in node.node_class]; setters = [node for node in nodes.values() if "K2Node_VariableSet" in node.node_class]
    contracts.require({variable(node) for node in getters} == READS, "exact evaluator reads"); contracts.require({variable(node) for node in setters} == WRITES, "exact evaluator writes")
    text = args.graph.read_text(encoding="utf-8"); contracts.require(not any(token in text for token in FORBIDDEN), "authored/external ownership forbidden")
    contracts.require("K2Node_Knot" not in text and "SubPins=(" not in text and "ParentPin=" not in text, "safe graph form")
    counts = {name:sum(member(node)==name for node in nodes.values()) for name in ("Array_Length","Quat_IsFinite","Quat_Size","Quat_GetAxisX","VSize","BreakQuat","Quat_Slerp","FFloor","FClamp","SelectFloat")}
    contracts.require(counts == {"Array_Length":2,"Quat_IsFinite":1,"Quat_Size":1,"Quat_GetAxisX":1,"VSize":2,"BreakQuat":2,"Quat_Slerp":1,"FFloor":1,"FClamp":1,"SelectFloat":1}, f"native forms {counts}")
    contracts.require(sum("K2Node_MacroInstance" in node.node_class for node in nodes.values()) == 1, "one full-track scan")
    for name in (TANGENTS, QUATS, COMPILE_VALID, ELAPSED, TOTAL, STEP):
        contracts.require(not any(variable(node)==name for node in setters), f"immutable input mutated: {name}")
    publications = [node for node in setters if variable(node)==VALID and default(node, VALID)=="true"]
    contracts.require(len(publications)==2 and all(not node.pins["then"].links for node in publications), "validity publishes last on active/complete paths")
    reset_valid = [node for node in setters if variable(node)==VALID and default(node, VALID)=="false"]
    contracts.require(len(reset_valid)==1, "result validity reset once")
    known = set(nodes); external = {target for node in nodes.values() for pin in node.pins.values() for target,_ in pin.links if target not in known}; contracts.require(not external, f"external links {external}")
    for token in ('DefaultValue="0.004166666666666667"','DefaultValue="3600.0"','DefaultValue="65536"','DefaultValue="0.999999"','DefaultValue="1.000001"','DefaultValue="0.000001"','DefaultValue="-0.000001"'):
        contracts.require(token in text, f"frozen evaluator token {token}")

    rng = random.Random(0xC4A11E2); tracks = []
    for _ in range(20):
        step = rng.choice((1/120,1/60,1/30,0.1,0.3)); intervals = rng.randint(1,40); total = (intervals-1)*step + rng.uniform(step*0.05,step)
        times = oracle.fixed_sample_times_v1(total,step); points=[(0.0,0.0,0.0)]
        for index in range(1,len(times)):
            points.append(points[-1] if index%11==0 else tuple(value+rng.uniform(-4.0,4.0) for value in points[-1]))
        tracks.append(oracle.compile_carrier_frame_transport_v1(points,total,step))
    evaluations = 0
    for track_index, track in enumerate(tracks):
        times=[-1.0,0.0,track.total_seconds,track.total_seconds+1.0,math.nextafter(track.total_seconds,0.0)]
        times.extend(index*track.fixed_step_seconds for index in range(min(len(track.rotations)-1,6))); times.extend(rng.uniform(0.0,track.total_seconds) for _ in range(10))
        canonical={}
        for elapsed in times:
            initial=state_from(track,elapsed); tangent_identity=initial[TANGENTS]; quat_identity=initial[QUATS]; actual=Interpreter(nodes,initial,oracle).run(); expected=oracle.evaluate_carrier_frame_transport_v1(track,elapsed)
            contracts.require(actual[VALID]==expected.valid and actual[COMPLETE]==expected.complete, f"track {track_index} time {elapsed}: flags")
            contracts.require(actual[SEGMENT]==expected.segment_index and abs(actual[ALPHA]-expected.alpha)<=2e-9, f"track {track_index} time {elapsed}: coordinates")
            contracts.require(close_quat(actual[QUAT],expected.rotation), f"track {track_index} time {elapsed}: rotation")
            contracts.require(actual[TANGENTS] is tangent_identity and actual[QUATS] is quat_identity, f"track {track_index}: immutable snapshot")
            canonical[elapsed]=(actual[SEGMENT],actual[ALPHA],actual[QUAT],actual[COMPLETE],actual[VALID]); evaluations += 1
        poisoned=state_from(track,0.0)
        for elapsed in reversed(times):
            poisoned[ELAPSED]=elapsed; poisoned.update({SEGMENT:999,ALPHA:999.0,QUAT:(9.0,9.0,9.0,9.0),COMPLETE:not canonical[elapsed][3],VALID:False,SCRATCH:not poisoned[SCRATCH]})
            poisoned=Interpreter(nodes,poisoned,oracle).run(); contracts.require((poisoned[SEGMENT],poisoned[ALPHA],poisoned[QUAT],poisoned[COMPLETE],poisoned[VALID])==canonical[elapsed], f"track {track_index} time {elapsed}: history dependence")

    baseline=tracks[0]; invalids=[]
    state=state_from(baseline,0.1); state[COMPILE_VALID]=False; invalids.append(("compile validity",state))
    state=state_from(baseline,float("nan")); invalids.append(("elapsed finite",state))
    state=state_from(baseline,0.1); state[TANGENTS]=[]; state[QUATS]=[]; invalids.append(("empty publication",state))
    state=state_from(baseline,0.1); state[QUATS]=state[QUATS][:-1]; invalids.append(("cardinality",state))
    state=state_from(baseline,0.1); state[TANGENTS][0]=(2.0,0.0,0.0); invalids.append(("tangent unit",state))
    state=state_from(baseline,0.1); state[TANGENTS][-1]=(float("nan"),0.0,0.0); invalids.append(("off-query tangent finite",state))
    state=state_from(baseline,0.1); state[QUATS][0]=(0.0,0.0,0.0,0.0); invalids.append(("quaternion unit",state))
    state=state_from(baseline,0.1); state[QUATS][-1]=(float("nan"),0.0,0.0,1.0); invalids.append(("off-query quaternion finite",state))
    state=state_from(baseline,0.1); state[TANGENTS][0]=(0.0,1.0,0.0); invalids.append(("forward alignment",state))
    state=state_from(baseline,0.1); state[QUATS][1]=tuple(-value for value in state[QUATS][1]); invalids.append(("hemisphere continuity",state))
    state=state_from(baseline,0.1); state[STEP]=0.001; invalids.append(("fixed step",state))
    state=state_from(baseline,0.1); state[TOTAL]=3601.0; invalids.append(("total",state))
    state=state_from(baseline,0.1); state[TOTAL]+=state[STEP]*2.0; invalids.append(("schedule",state))
    for label,state in invalids: assert_invalid(contracts,nodes,oracle,state,label)
    print(f"Carrier-frame evaluator contracts passed ({'paste' if args.paste else 'full'}): {evaluations} oracle-equivalent evaluations, arbitrary-order replay, {len(invalids)} corrupt states")


if __name__ == "__main__": main()
