"""Build fail-closed validation for authored multi-segment position routes."""
from __future__ import annotations
import argparse, importlib.util, re, sys
from pathlib import Path

FUNCTION="ValidatePositionRouteInputsV1"
SPATIAL=("linear","auto_cinematic")

def load(root):
 p=root/"tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py";s=importlib.util.spec_from_file_location("edd_position_validation_base",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def pin_kind(node,pin,kind,array=False):
 category,sub,obj={"bool":("bool","","None"),"int":("int","","None"),"real":("real","double","None"),"string":("string","","None"),"vector":("struct","",'"/Script/CoreUObject.ScriptStruct\'/Script/CoreUObject.Vector\'"')}[kind]
 def mutate(line):
  line=re.sub(r'PinType.PinCategory="[^"]*"',f'PinType.PinCategory="{category}"',line,1);line=re.sub(r'PinType.PinSubCategory="[^"]*"',f'PinType.PinSubCategory="{sub}"',line,1);line=re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")',f'PinType.PinSubCategoryObject={obj}',line,1);return re.sub(r'PinType.ContainerType=(?:None|Array)',f'PinType.ContainerType={"Array" if array else "None"}',line,1)
 node.mutate_pin(pin,mutate)
def retarget(scalar,node,member,kinds):
 scalar.retarget_function(node,member)
 for pin,kind in kinds.items():pin_kind(node,pin,kind)
 return node
def main():
 p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--paste-output",type=Path);a=p.parse_args();scalar=load(a.project_root);bp=scalar.load_helpers(a.project_root);forms=scalar.load_templates(a.project_root,bp);b=scalar.Builder(bp,forms,FUNCTION)
 raw=bp.read_blocks(a.project_root/"tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph");edit=bp.read_blocks(a.project_root/"tools/blueprint/templates/waypoint-edit-node-forms.eddgraph");call_blocks=bp.read_blocks(a.project_root/"tools/blueprint/snippets/activate-drone-view.eddgraph")
 foreach_form=bp.find_block(raw,r"K2Node_MacroInstance");length_form=bp.find_block(edit,r'MemberName="Array_Length"');call_form=bp.find_block(call_blocks,r'MemberName="SwitchToDroneView"')
 def add_form(key,form,x,y):
  match=bp.BLOCK_RE.match(form);cls=match.group("class").rsplit(".",1)[-1];index=b.serial.get(cls,0);b.serial[cls]=index+1;n=bp.Node.clone(key,form,f"{cls}_{index}",x,y);b.nodes.append(n);return n
 def array_get(name,kind,x,y):
  n=b.get(name,"vector" if kind=="vector" else ("string" if kind=="string" else "real"),x,y);pin_kind(n,name,kind,True)
  if "Output_Get" in n.pins:pin_kind(n,"Output_Get",kind)
  return n
 def length(source,name,kind,x,y):
  n=add_form(f"len_{name}",length_form,x,y);pin_kind(n,"TargetArray",kind,True);bp.connect(source,name,n,"TargetArray");return n
 def foreach(source,name,kind,x,y):
  n=add_form(f"foreach_{name}",foreach_form,x,y);pin_kind(n,"Array",kind,True);pin_kind(n,"Array Element",kind);bp.connect(source,name,n,"Array");return n
 def compare(member,x,y,kind="int",default_b=None):
  n=b.add(f"{member}_{len(b.nodes)}","compare",x,y);retarget(scalar,n,member,{"A":kind,"B":kind,"ReturnValue":"bool"})
  if default_b is not None:scalar.set_default(n,"B",default_b)
  return n
 def boolean(member,left,right,x,y):
  n=compare(member,x,y,"bool");bp.connect(left,"ReturnValue",n,"A");bp.connect(right,"ReturnValue",n,"B");return n
 def call(name,x,y):
  index=b.serial.get("K2Node_CallFunction",0);b.serial["K2Node_CallFunction"]=index+1;n=bp.Node.clone(f"call_{name}",call_form,f"K2Node_CallFunction_{index}",x,y);n.text=re.sub(r'FunctionReference=\([^)]*\)',f'FunctionReference=(MemberName="{name}",bSelfContext=True)',n.text,1);b.nodes.append(n);return n
 def setter(name,kind,source,pin,x,y):
  n=b.set(name,kind,x,y);bp.connect(source,pin,n,name);return n

 reset=b.set("PositionRouteStageValidV1","bool",256,1856,"false");bp.connect(b.entry,"then",reset,"execute")
 positions=array_get("PositionRouteInputWaypointPositionsV1","vector",0,128);durations=array_get("PositionRouteInputDurationsV1","real",0,352);curves=array_get("PositionRouteInputSpatialCurveTypesV1","string",0,576);profiles=array_get("PositionRouteInputTimeProfilesV1","string",0,800)
 plen=length(positions,"PositionRouteInputWaypointPositionsV1","vector",288,128);dlen=length(durations,"PositionRouteInputDurationsV1","real",288,352);clen=length(curves,"PositionRouteInputSpatialCurveTypesV1","string",288,576);tlen=length(profiles,"PositionRouteInputTimeProfilesV1","string",288,800)
 minimum=compare("GreaterEqual_IntInt",560,64,"int","2");maximum=compare("LessEqual_IntInt",560,192,"int","512");bp.connect(plen,"ReturnValue",minimum,"A");bp.connect(plen,"ReturnValue",maximum,"A")
 segments=retarget(scalar,b.math("Subtract_DoubleDouble",560,352),"Subtract_IntInt",{"A":"int","B":"int","ReturnValue":"int"});scalar.set_default(segments,"B","1");bp.connect(plen,"ReturnValue",segments,"A")
 shapes=[]
 for index,node in enumerate((dlen,clen,tlen)):
  eq=compare("EqualEqual_IntInt",816,352+index*224,"int");bp.connect(node,"ReturnValue",eq,"A");bp.connect(segments,"ReturnValue",eq,"B");shapes.append(eq)
 valid=boolean("BooleanAND",minimum,maximum,1056,128)
 for index,condition in enumerate(shapes):valid=boolean("BooleanAND",valid,condition,1280+index*224,256+index*112)
 tolerance=b.get("PositionRouteInputArcToleranceV1","real",0,1056);finite=b.finite(tolerance,"PositionRouteInputArcToleranceV1",256,1056);positive=compare("Greater_DoubleDouble",256,1248,"real","0.0");bp.connect(tolerance,"PositionRouteInputArcToleranceV1",positive,"A");valid=boolean("BooleanAND",valid,finite,1952,528);valid=boolean("BooleanAND",valid,positive,2176,640)
 depth=b.get("PositionRouteInputMaxArcDepthV1","real",0,1376);pin_kind(depth,"PositionRouteInputMaxArcDepthV1","int");dmin=compare("GreaterEqual_IntInt",256,1376,"int","1");dmax=compare("LessEqual_IntInt",256,1504,"int","12");bp.connect(depth,"PositionRouteInputMaxArcDepthV1",dmin,"A");bp.connect(depth,"PositionRouteInputMaxArcDepthV1",dmax,"A");valid=boolean("BooleanAND",valid,dmin,2400,752);valid=boolean("BooleanAND",valid,dmax,2624,864)
 operations=b.get("PositionRouteInputMaxArcOperationsV1","real",0,1632);pin_kind(operations,"PositionRouteInputMaxArcOperationsV1","int");omin=compare("GreaterEqual_IntInt",256,1632,"int","1");omax=compare("LessEqual_IntInt",256,1760,"int","8191");bp.connect(operations,"PositionRouteInputMaxArcOperationsV1",omin,"A");bp.connect(operations,"PositionRouteInputMaxArcOperationsV1",omax,"A");valid=boolean("BooleanAND",valid,omin,2848,976);valid=boolean("BooleanAND",valid,omax,3072,1088)
 shape_branch=b.add("shape_branch","branch",3328,1856);bp.connect(reset,"then",shape_branch,"execute");bp.connect(valid,"ReturnValue",shape_branch,"Condition");accept=b.set("PositionRouteStageValidV1","bool",3584,1856,"true");bp.connect(shape_branch,"then",accept,"execute")

 fp=foreach(positions,"PositionRouteInputWaypointPositionsV1","vector",3840,256);bp.connect(accept,"then",fp,"Exec");chain=[]
 primitive=("TrajectoryInputStartPositionVectorV1","TrajectoryInputEndPositionVectorV1","TrajectoryInputStartVelocityUVectorV1","TrajectoryInputEndVelocityUVectorV1","TrajectoryInputStartAccelerationUVectorV1","TrajectoryInputEndAccelerationUVectorV1")
 for index,name in enumerate(primitive):
  node=setter(name,"vector",fp,"Array Element",4096+index*224,1856);chain.append(node)
  if index==0:bp.connect(fp,"LoopBody",node,"execute")
  else:bp.connect(chain[-2],"then",node,"execute")
 alpha=b.set("TrajectoryInputAlphaV1","real",5440,1856,"0.5");bp.connect(chain[-1],"then",alpha,"execute");veval=call("EvaluateQuinticVectorV1",5664,1856);bp.connect(alpha,"then",veval,"execute");vvalid=b.get("TrajectoryResultVectorValidV1","bool",5664,416);vbranch=b.add("vector_branch","branch",5888,1856);bp.connect(veval,"then",vbranch,"execute");bp.connect(vvalid,"TrajectoryResultVectorValidV1",vbranch,"Condition");vreject=b.set("PositionRouteStageValidV1","bool",6112,2016,"false");bp.connect(vbranch,"else",vreject,"execute")

 fd=foreach(durations,"PositionRouteInputDurationsV1","real",6368,640);bp.connect(fp,"Completed",fd,"Exec");dfinite=b.finite(fd,"Array Element",6624,576);dpositive=compare("Greater_DoubleDouble",6624,832,"real","0.0");bp.connect(fd,"Array Element",dpositive,"A");dvalid=boolean("BooleanAND",dfinite,dpositive,7072,704);dbranch=b.add("duration_branch","branch",7296,640);bp.connect(fd,"LoopBody",dbranch,"execute");bp.connect(dvalid,"ReturnValue",dbranch,"Condition");dreject=b.set("PositionRouteStageValidV1","bool",7520,800,"false");bp.connect(dbranch,"else",dreject,"execute")

 fc=foreach(curves,"PositionRouteInputSpatialCurveTypesV1","string",7776,1088);bp.connect(fd,"Completed",fc,"Exec");curve_equal=[]
 for index,name in enumerate(SPATIAL):
  eq=b.equal_string(8032,1024+index*160,name);bp.connect(fc,"Array Element",eq,"A");curve_equal.append(eq)
 curve_valid=boolean("BooleanOR",curve_equal[0],curve_equal[1],8480,1088);cbranch=b.add("curve_branch","branch",8704,1088);bp.connect(fc,"LoopBody",cbranch,"execute");bp.connect(curve_valid,"ReturnValue",cbranch,"Condition");creject=b.set("PositionRouteStageValidV1","bool",8928,1248,"false");bp.connect(cbranch,"else",creject,"execute")

 ft=foreach(profiles,"PositionRouteInputTimeProfilesV1","string",9184,1504);bp.connect(fc,"Completed",ft,"Exec");set_profile=setter("TrajectoryInputProfileV1","string",ft,"Array Element",9440,1856);bp.connect(ft,"LoopBody",set_profile,"execute");set_alpha=b.set("TrajectoryInputAlphaV1","real",9664,1856,"0.5");bp.connect(set_profile,"then",set_alpha,"execute");teval=call("EvaluateTimeProfileV1",9888,1856);bp.connect(set_alpha,"then",teval,"execute");tvalid=b.get("TrajectoryResultValidV1","bool",9888,1536);tbranch=b.add("time_branch","branch",10112,1856);bp.connect(teval,"then",tbranch,"execute");bp.connect(tvalid,"TrajectoryResultValidV1",tbranch,"Condition");treject=b.set("PositionRouteStageValidV1","bool",10336,2016,"false");bp.connect(tbranch,"else",treject,"execute")
 full="\n".join(n.text for n in b.nodes)+"\n";a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(full,encoding="utf-8")
 if a.paste_output:
  body=[re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",n.text) for n in b.nodes[1:]];a.paste_output.parent.mkdir(parents=True,exist_ok=True);a.paste_output.write_text("\n".join(body)+"\n",encoding="utf-8")
if __name__=="__main__":main()
