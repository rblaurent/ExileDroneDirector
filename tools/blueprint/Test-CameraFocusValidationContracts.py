"""Exact structural and executable contracts for focus preflight."""
from __future__ import annotations
import argparse,importlib.util,math,random,re,sys
from pathlib import Path

READS={"CameraFocusInputModeV1","CameraFocusInputDomainV1","CameraFocusInputFixedStepSecondsV1","CameraFocusInputSmoothingResponseSecondsV1","CameraFocusInputTimesSecondsV1","CameraFocusInputCameraPositionsV1","CameraFocusInputManualDistancesCmV1","CameraFocusInputTargetPositionsV1","CameraFocusInputRackBlendWeightsV1"};WRITES={"CameraFocusCandidateValidV1","CameraFocusFailureCodeV1"};FORBIDDEN=("CameraFocusTraceHit","CameraFocusMarker","CameraFocusCompiled","CameraApply","Airframe","Document")
MODES=("manual_distance","fixed_world","rack_fixed","track_prebaked","smoothed_autofocus")
def load(path):spec=importlib.util.spec_from_file_location("edd_focus_validation_contract_base",path);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module
def member(node):match=re.search(r'MemberName="([^"]+)"',node.text);return None if match is None else match.group(1)
def preflight(case):
 mode,domain,step,smoothing,count,cameras,manual,targets,rack=case
 if mode not in MODES or domain not in ("linear","reciprocal") or not math.isfinite(step) or step<=0 or not 2<=count<=65536 or cameras!=count:return False
 shapes={"manual_distance":(count,0,0,smoothing==0),"fixed_world":(0,1,0,smoothing==0),"rack_fixed":(0,0,count,smoothing==0),"track_prebaked":(0,count,0,smoothing==0),"smoothed_autofocus":(0,count,0,math.isfinite(smoothing) and smoothing>0)}
 wanted=shapes[mode];return (manual,targets,rack,wanted[3])==(wanted[0],wanted[1],wanted[2],True)
def main():
 parser=argparse.ArgumentParser();parser.add_argument("--project-root",type=Path,required=True);parser.add_argument("--graph",type=Path,required=True);parser.add_argument("--paste",action="store_true");args=parser.parse_args();c=load(args.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py");nodes=c.parse_graph(args.graph);c.require(len(nodes)==(77 if args.paste else 78),f"node count {len(nodes)}");entries=[node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class];c.require(len(entries)==(0 if args.paste else 1),"entry count")
 getters={member(node) for node in nodes.values() if "K2Node_VariableGet" in node.node_class};setters={member(node) for node in nodes.values() if "K2Node_VariableSet" in node.node_class};c.require(getters==READS,"exact preflight reads");c.require(setters==WRITES,"exact preflight writes");text=args.graph.read_text(encoding="utf-8");c.require(not any(value in text for value in FORBIDDEN),"trace, marker, compiled, engine, and motion state forbidden");c.require(all(f'DefaultValue="{value}"' in text for value in (*MODES,"linear","reciprocal")),"all exact identities");c.require(text.count('MemberName="Array_Length"')==5,"five source lengths");c.require(text.count('MemberName="EqualEqual_StrStr"')==7,"five modes and two domains");c.require(text.count('DefaultValue="-1.7976931348623157e+308"')==2 and text.count('DefaultValue="1.7976931348623157e+308"')==2,"step and smoothing finite checks")
 invalidators=[node for node in nodes.values() if "K2Node_VariableSet" in node.node_class and member(node)=="CameraFocusCandidateValidV1" and 'DefaultValue="true"' not in node.text];c.require(len(invalidators)>=1,"candidate invalidated first")
 if not args.paste:c.require(any(any(link[0]==entries[0].name for link in node.pins["execute"].links) for node in invalidators),"native entry seam")
 rng=random.Random(0xEDD6F1);valid=[]
 for mode in MODES:
  for _ in range(16):
   count=rng.randint(2,128);source={"manual_distance":(count,0,0,0.0),"fixed_world":(0,1,0,0.0),"rack_fixed":(0,0,count,0.0),"track_prebaked":(0,count,0,0.0),"smoothed_autofocus":(0,count,0,rng.uniform(.01,2.0))}[mode];valid.append((mode,rng.choice(("linear","reciprocal")),rng.uniform(.01,.5),source[3],count,count,source[0],source[1],source[2]))
 c.require(all(preflight(case) for case in valid),"seeded valid preflight")
 base=("manual_distance","linear",.1,0.0,4,4,4,0,0);failures=(("bad",*base[1:]),(base[0],"bad",*base[2:]),(base[0],base[1],0.0,*base[3:]),(base[0],base[1],math.nan,*base[3:]),(*base[:4],1,*base[5:]),(*base[:5],3,*base[6:]),(*base[:6],0,1,0),("fixed_world","linear",.1,0,4,4,0,0,0),("rack_fixed","linear",.1,0,4,4,0,0,3),("track_prebaked","linear",.1,0,4,4,0,3,0),("smoothed_autofocus","linear",.1,0,4,4,0,4,0),("manual_distance","linear",.1,.5,4,4,4,0,0))
 c.require(all(not preflight(case) for case in failures),"failure families");before=tuple(valid);[preflight(case) for case in valid];c.require(tuple(valid)==before,"inputs immutable")
 print(f"Camera focus validation contracts passed ({'paste' if args.paste else 'full'}): {len(valid)} valid, {len(failures)} failures")
if __name__=="__main__":main()
