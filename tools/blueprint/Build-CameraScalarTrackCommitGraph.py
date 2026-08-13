"""Build atomic publication of complete common camera scalar candidates."""
from __future__ import annotations
import argparse,importlib.util,re,sys
from pathlib import Path
FUNCTION="CommitCameraScalarTrackV1"
ARRAYS=(("CameraScalarTrackCandidateKeyTimesV1","real"),("CameraScalarTrackCandidateDomainValuesV1","real"),("CameraScalarTrackCandidateInterpolationModesV1","string"),("CameraScalarTrackCandidateArriveTangentsV1","real"),("CameraScalarTrackCandidateLeaveTangentsV1","real"))
def load(root):
 p=root/"tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py";s=importlib.util.spec_from_file_location("edd_camera_scalar_commit_base",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def kind(node,pin,value,array=False):
 category,subcategory,obj={"bool":("bool","","None"),"int":("int","","None"),"real":("real","double","None"),"string":("string","","None")}[value]
 def mutate(line):
  line=re.sub(r'PinType.PinCategory="[^"]*"',f'PinType.PinCategory="{category}"',line,1);line=re.sub(r'PinType.PinSubCategory="[^"]*"',f'PinType.PinSubCategory="{subcategory}"',line,1);line=re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")',f'PinType.PinSubCategoryObject={obj}',line,1);return re.sub(r'PinType.ContainerType=(?:None|Array)',f'PinType.ContainerType={"Array" if array else "None"}',line,1)
 node.mutate_pin(pin,mutate)
def main():
 a=argparse.ArgumentParser();a.add_argument("--project-root",type=Path,required=True);a.add_argument("--output",type=Path,required=True);a.add_argument("--paste-output",type=Path);x=a.parse_args();scalar=load(x.project_root);bp=scalar.load_helpers(x.project_root);forms=scalar.load_templates(x.project_root,bp);edit=bp.read_blocks(x.project_root/"tools/blueprint/templates/waypoint-edit-node-forms.eddgraph");forms["length"]=bp.find_block(edit,r'MemberName="Array_Length"');b=scalar.Builder(bp,forms,FUNCTION)
 def variable(node,name,value,array=False):scalar.retarget_variable(node,name,value);kind(node,name,value,array);kind(node,"Output_Get",value,array) if "Output_Get" in node.pins else None
 def get(name,value,x,y,array=False):n=b.add(f"get_{name}_{len(b.nodes)}","get",x,y);variable(n,name,value,array);return n
 def set_(name,value,x,y,default=None):n=b.add(f"set_{name}_{len(b.nodes)}","set",x,y);variable(n,name,value);scalar.set_default(n,name,default) if default is not None else None;return n
 def add_form(key,form,x,y):
  match=bp.BLOCK_RE.match(forms[form]);cls=match.group("class").rsplit(".",1)[-1];i=b.serial.get(cls,0);b.serial[cls]=i+1;n=bp.Node.clone(key,forms[form],f"{cls}_{i}",x,y);b.nodes.append(n);return n
 def length(source,pin,value,x,y):n=add_form(f"length_{pin}_{len(b.nodes)}","length",x,y);kind(n,"TargetArray",value,True);kind(n,"ReturnValue","int");bp.connect(source,pin,n,"TargetArray");return n
 def operation(member,left,left_pin,x,y,right=None,right_pin=None,default=None,value="int"):
  n=b.add(f"op_{member}_{len(b.nodes)}","compare" if member not in ("Subtract_IntInt",) else "math",x,y);scalar.retarget_function(n,member);kind(n,"A",value);kind(n,"B",value);kind(n,"ReturnValue","bool" if member!="Subtract_IntInt" else value);bp.connect(left,left_pin,n,"A");bp.connect(right,right_pin,n,"B") if right is not None else scalar.set_default(n,"B",default);return n
 def and_all(values,x,y):
  current=values[0]
  for i,value in enumerate(values[1:]):current=operation("BooleanAND",current,"ReturnValue",x+i*208,y,value,"ReturnValue",value="bool")
  return current
 invalidate=set_("CameraScalarTrackCompileValidV1","bool",256,1440,"false");bp.connect(b.entry,"then",invalidate,"execute");stage=get("CameraScalarTrackScratchValidV1","bool",0,0);stage_guard=b.add("stage_guard","branch",480,1440);bp.connect(invalidate,"then",stage_guard,"execute");bp.connect(stage,"CameraScalarTrackScratchValidV1",stage_guard,"Condition")
 getters=[get(name,value,0,160+i*160,True) for i,(name,value) in enumerate(ARRAYS)];lengths=[length(g,name,value,256,160+i*160) for i,(g,(name,value)) in enumerate(zip(getters,ARRAYS))];count=lengths[0];segments=operation("Subtract_IntInt",count,"ReturnValue",512,160,default="1")
 conditions=[operation("GreaterEqual_IntInt",count,"ReturnValue",736,0,default="1"),operation("LessEqual_IntInt",count,"ReturnValue",736,160,default="512"),operation("EqualEqual_IntInt",lengths[1],"ReturnValue",736,320,count,"ReturnValue"),operation("EqualEqual_IntInt",lengths[2],"ReturnValue",736,480,segments,"ReturnValue"),operation("EqualEqual_IntInt",lengths[3],"ReturnValue",736,640,count,"ReturnValue"),operation("EqualEqual_IntInt",lengths[4],"ReturnValue",736,800,count,"ReturnValue")];valid=and_all(conditions,960,640);preflight=b.add("preflight","branch",2208,1440);bp.connect(stage_guard,"then",preflight,"execute");bp.connect(valid,"ReturnValue",preflight,"Condition");publish=set_("CameraScalarTrackCompileValidV1","bool",2432,1440,"true");clear_failure=set_("CameraScalarTrackFailureCodeV1","string",2656,1440,"");bp.connect(preflight,"then",publish,"execute");bp.connect(publish,"then",clear_failure,"execute")
 full="\n".join(n.text for n in b.nodes)+"\n";x.output.parent.mkdir(parents=True,exist_ok=True);x.output.write_text(full,encoding="utf-8")
 if x.paste_output:x.paste_output.parent.mkdir(parents=True,exist_ok=True);x.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",n.text) for n in b.nodes[1:])+"\n",encoding="utf-8")
if __name__=="__main__":main()
