"""Build focus mode/domain, schedule-shape, and exclusive-authorship preflight."""
from __future__ import annotations
import argparse,importlib.util,re,sys
from pathlib import Path

FUNCTION="ValidateCameraFocusInputsV1"
MODES=("manual_distance","fixed_world","rack_fixed","track_prebaked","smoothed_autofocus")
def load(root):
 path=root/"tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py";spec=importlib.util.spec_from_file_location("edd_focus_validation_base",path);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module
def pin_kind(node,pin,kind,array=False):
 category,subcategory,obj={"bool":("bool","","None"),"int":("int","","None"),"real":("real","double","None"),"string":("string","","None"),"vector":("struct","",'"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"')}[kind]
 def mutate(line):
  line=re.sub(r'PinType.PinCategory="[^"]*"',f'PinType.PinCategory="{category}"',line,1);line=re.sub(r'PinType.PinSubCategory="[^"]*"',f'PinType.PinSubCategory="{subcategory}"',line,1);line=re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")',f'PinType.PinSubCategoryObject={obj}',line,1);return re.sub(r'PinType.ContainerType=(?:None|Array)',f'PinType.ContainerType={"Array" if array else "None"}',line,1)
 node.mutate_pin(pin,mutate)
def main():
 parser=argparse.ArgumentParser();parser.add_argument("--project-root",type=Path,required=True);parser.add_argument("--output",type=Path,required=True);parser.add_argument("--paste-output",type=Path);args=parser.parse_args();scalar=load(args.project_root);bp=scalar.load_helpers(args.project_root);forms=scalar.load_templates(args.project_root,bp);b=scalar.Builder(bp,forms,FUNCTION);edit=bp.read_blocks(args.project_root/"tools/blueprint/templates/waypoint-edit-node-forms.eddgraph");length_form=bp.find_block(edit,r'MemberName="Array_Length"')
 def add_form(key,form,x,y):
  match=bp.BLOCK_RE.match(form);cls=match.group("class").rsplit(".",1)[-1];index=b.serial.get(cls,0);b.serial[cls]=index+1;node=bp.Node.clone(key,form,f"{cls}_{index}",x,y);b.nodes.append(node);return node
 def get_var(name,kind,x,y,array=False):
  node=b.get(name,"real" if kind in ("int","vector") else kind,x,y);scalar.retarget_variable(node,name,"vector" if kind=="vector" else ("real" if kind=="int" else kind));pin_kind(node,name,kind,array);return node
 def length(source,name,kind,x,y):node=add_form(f"length_{name}",length_form,x,y);pin_kind(node,"TargetArray",kind,True);pin_kind(node,"ReturnValue","int");bp.connect(source,name,node,"TargetArray");return node
 def compare(member,left,left_pin,x,y,kind="int",right=None,right_pin=None,default=None):
  node=b.add(f"compare_{len(b.nodes)}","compare",x,y);scalar.retarget_function(node,member)
  if kind=="string":node.text=node.text.replace("KismetMathLibrary","KismetStringLibrary")
  pin_kind(node,"A",kind);pin_kind(node,"B",kind);pin_kind(node,"ReturnValue","bool");bp.connect(left,left_pin,node,"A");bp.connect(right,right_pin,node,"B") if right is not None else scalar.set_default(node,"B",default);return node
 def boolean(member,left,right,x,y):
  node=b.add(f"boolean_{len(b.nodes)}","compare",x,y);scalar.retarget_function(node,member);[pin_kind(node,pin,"bool") for pin in ("A","B","ReturnValue")];bp.connect(left,"ReturnValue",node,"A");bp.connect(right,"ReturnValue",node,"B");return node
 def combine(items,member,x,y):
  current=items[0]
  for index,item in enumerate(items[1:]):current=boolean(member,current,item,x+index*192,y)
  return current
 invalidate=b.set("CameraFocusCandidateValidV1","bool",256,3520,"false");failure=b.set("CameraFocusFailureCodeV1","string",480,3520,"validation_failed");bp.connect(b.entry,"then",invalidate,"execute");bp.connect(invalidate,"then",failure,"execute")
 mode=get_var("CameraFocusInputModeV1","string",0,0);domain=get_var("CameraFocusInputDomainV1","string",0,160);step=get_var("CameraFocusInputFixedStepSecondsV1","real",0,320);smoothing=get_var("CameraFocusInputSmoothingResponseSecondsV1","real",0,480)
 arrays=(("CameraFocusInputTimesSecondsV1","real"),("CameraFocusInputCameraPositionsV1","vector"),("CameraFocusInputManualDistancesCmV1","real"),("CameraFocusInputTargetPositionsV1","vector"),("CameraFocusInputRackBlendWeightsV1","real"));array_gets=[get_var(name,kind,0,800+i*224,True) for i,(name,kind) in enumerate(arrays)];lengths=[length(source,name,kind,320,800+i*224) for i,(source,(name,kind)) in enumerate(zip(array_gets,arrays))];count=lengths[0]
 mode_flags=[compare("EqualEqual_StrStr",mode,"CameraFocusInputModeV1",640,i*160,"string",default=value) for i,value in enumerate(MODES)];domain_flags=[compare("EqualEqual_StrStr",domain,"CameraFocusInputDomainV1",864,i*160,"string",default=value) for i,value in enumerate(("linear","reciprocal"))];domain_ok=boolean("BooleanOR",domain_flags[0],domain_flags[1],1088,160)
 common=(compare("GreaterEqual_IntInt",count,"ReturnValue",640,800,default="2"),compare("LessEqual_IntInt",count,"ReturnValue",864,800,default="65536"),compare("EqualEqual_IntInt",lengths[1],"ReturnValue",1088,1024,right=count,right_pin="ReturnValue"),b.finite(step,"CameraFocusInputFixedStepSecondsV1",640,320),compare("Greater_DoubleDouble",step,"CameraFocusInputFixedStepSecondsV1",864,320,"real",default="0.0"),domain_ok)
 zero_manual=compare("EqualEqual_IntInt",lengths[2],"ReturnValue",640,1248,default="0");full_manual=compare("EqualEqual_IntInt",lengths[2],"ReturnValue",864,1248,right=count,right_pin="ReturnValue");zero_target=compare("EqualEqual_IntInt",lengths[3],"ReturnValue",640,1472,default="0");one_target=compare("EqualEqual_IntInt",lengths[3],"ReturnValue",864,1472,default="1");full_target=compare("EqualEqual_IntInt",lengths[3],"ReturnValue",1088,1472,right=count,right_pin="ReturnValue");zero_rack=compare("EqualEqual_IntInt",lengths[4],"ReturnValue",640,1696,default="0");full_rack=compare("EqualEqual_IntInt",lengths[4],"ReturnValue",864,1696,right=count,right_pin="ReturnValue");zero_smoothing=compare("EqualEqual_DoubleDouble",smoothing,"CameraFocusInputSmoothingResponseSecondsV1",640,1920,"real",default="0.0");smooth_finite=b.finite(smoothing,"CameraFocusInputSmoothingResponseSecondsV1",864,1920);smooth_positive=compare("Greater_DoubleDouble",smoothing,"CameraFocusInputSmoothingResponseSecondsV1",1088,1920,"real",default="0.0");smooth_ok=combine((smooth_finite,smooth_positive),"BooleanAND",1312,1920)
 policies=((mode_flags[0],full_manual,zero_target,zero_rack,zero_smoothing),(mode_flags[1],zero_manual,one_target,zero_rack,zero_smoothing),(mode_flags[2],zero_manual,zero_target,full_rack,zero_smoothing),(mode_flags[3],zero_manual,full_target,zero_rack,zero_smoothing),(mode_flags[4],zero_manual,full_target,zero_rack,smooth_ok));policy_flags=[combine(items,"BooleanAND",1536,2240+i*192) for i,items in enumerate(policies)];policy_ok=combine(policy_flags,"BooleanOR",2496,3008);ready=combine((*common,policy_ok),"BooleanAND",1344,3296);guard=b.add("validation_guard","branch",2688,3520);bp.connect(failure,"then",guard,"execute");bp.connect(ready,"ReturnValue",guard,"Condition");clear=b.set("CameraFocusFailureCodeV1","string",2912,3520,"");publish=b.set("CameraFocusCandidateValidV1","bool",3136,3520,"true");bp.connect(guard,"then",clear,"execute");bp.connect(clear,"then",publish,"execute")
 full="\n".join(node.text for node in b.nodes)+"\n";args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(full,encoding="utf-8")
 if args.paste_output:args.paste_output.parent.mkdir(parents=True,exist_ok=True);args.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",node.text) for node in b.nodes[1:])+"\n",encoding="utf-8")
if __name__=="__main__":main()
