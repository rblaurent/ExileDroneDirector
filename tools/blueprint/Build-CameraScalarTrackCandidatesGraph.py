"""Build private compiled candidates for the validated camera scalar track."""
from __future__ import annotations
import argparse,importlib.util,re,sys
from pathlib import Path
FUNCTION="BuildCameraScalarTrackCandidatesV1"
COPIES=(("CameraScalarTrackInputKeyTimesV1","CameraScalarTrackCandidateKeyTimesV1","real"),("CameraScalarTrackInputInterpolationModesV1","CameraScalarTrackCandidateInterpolationModesV1","string"),("CameraScalarTrackInputArriveTangentsV1","CameraScalarTrackCandidateArriveTangentsV1","real"),("CameraScalarTrackInputLeaveTangentsV1","CameraScalarTrackCandidateLeaveTangentsV1","real"))
def load(root):
 p=root/"tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py";s=importlib.util.spec_from_file_location("edd_camera_scalar_candidate_base",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def kind(node,pin,value,array=False):
 category,subcategory,obj={"bool":("bool","","None"),"int":("int","","None"),"real":("real","double","None"),"string":("string","","None")}[value]
 def mutate(line):
  line=re.sub(r'PinType.PinCategory="[^"]*"',f'PinType.PinCategory="{category}"',line,1);line=re.sub(r'PinType.PinSubCategory="[^"]*"',f'PinType.PinSubCategory="{subcategory}"',line,1);line=re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")',f'PinType.PinSubCategoryObject={obj}',line,1);return re.sub(r'PinType.ContainerType=(?:None|Array)',f'PinType.ContainerType={"Array" if array else "None"}',line,1)
 node.mutate_pin(pin,mutate)
def main():
 a=argparse.ArgumentParser();a.add_argument("--project-root",type=Path,required=True);a.add_argument("--output",type=Path,required=True);a.add_argument("--paste-output",type=Path);x=a.parse_args();scalar=load(x.project_root);bp=scalar.load_helpers(x.project_root);forms=scalar.load_templates(x.project_root,bp);capture=bp.read_blocks(x.project_root/"tools/blueprint/templates/waypoint-capture-node-forms.eddgraph");sync=bp.read_blocks(x.project_root/"tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph");forms.update({"foreach":bp.find_block(sync,r"^Begin Object Class=/Script/BlueprintGraph.K2Node_MacroInstance"),"array_add":bp.find_block(capture,r'MemberName="Array_Add"')});b=scalar.Builder(bp,forms,FUNCTION)
 def variable(node,name,value,array=False):scalar.retarget_variable(node,name,value);kind(node,name,value,array);kind(node,"Output_Get",value,array) if "Output_Get" in node.pins else None
 def get(name,value,x,y,array=False):n=b.add(f"get_{name}_{len(b.nodes)}","get",x,y);variable(n,name,value,array);return n
 def set_(name,value,x,y,array=False):n=b.add(f"set_{name}_{len(b.nodes)}","set",x,y);variable(n,name,value,array);return n
 def operation(member,left,left_pin,x,y,right=None,right_pin=None,default_a=None,default_b=None):
  n=b.math("Multiply_DoubleDouble",x,y);scalar.retarget_function(n,member);[kind(n,p,"real") for p in ("A","B","ReturnValue")];bp.connect(left,left_pin,n,"A") if left is not None else scalar.set_default(n,"A",default_a);bp.connect(right,right_pin,n,"B") if right is not None else scalar.set_default(n,"B",default_b);return n
 def array_add(output,pin,item,item_pin,x,y):
  n=b.add(f"append_{len(b.nodes)}","array_add",x,y);kind(n,"TargetArray","real",True);kind(n,"NewItem","real");kind(n,"ReturnValue","int");bp.connect(output,pin,n,"TargetArray");bp.connect(item,item_pin,n,"NewItem");return n
 stage=get("CameraScalarTrackScratchValidV1","bool",0,0);guard=b.add("stage_guard","branch",1152,720);bp.connect(b.entry,"then",guard,"execute");bp.connect(stage,"CameraScalarTrackScratchValidV1",guard,"Condition");chain=[]
 for i,(source,target,value) in enumerate(COPIES):
  g=get(source,value,0,160+i*160,True);s=set_(target,value,512+i*256,1600,True);bp.connect(g,source,s,target);chain.append(s)
 bp.connect(guard,"then",chain[0],"execute");[bp.connect(l,"then",r,"execute") for l,r in zip(chain,chain[1:])]
 values=get("CameraScalarTrackInputKeyValuesV1","real",0,960,True);loop=b.add("value_loop","foreach",1536,1600);kind(loop,"Array","real",True);kind(loop,"Array Element","real");kind(loop,"Array Index","int");bp.connect(values,"CameraScalarTrackInputKeyValuesV1",loop,"Array");bp.connect(chain[-1],"then",loop,"Exec")
 domain=get("CameraScalarTrackInputDomainV1","string",1280,960);is_reciprocal=b.equal_string(1536,960,"reciprocal");bp.connect(domain,"CameraScalarTrackInputDomainV1",is_reciprocal,"A");domain_branch=b.add("domain_branch","branch",1792,1600);bp.connect(loop,"LoopBody",domain_branch,"execute");bp.connect(is_reciprocal,"ReturnValue",domain_branch,"Condition")
 inverse=operation("Divide_DoubleDouble",None,None,2048,1120,loop,"Array Element",default_a="1.0");output=get("CameraScalarTrackCandidateDomainValuesV1","real",1792,1280,True);append_inverse=array_add(output,"CameraScalarTrackCandidateDomainValuesV1",inverse,"ReturnValue",2304,1440);append_linear=array_add(output,"CameraScalarTrackCandidateDomainValuesV1",loop,"Array Element",2304,1760);bp.connect(domain_branch,"then",append_inverse,"execute");bp.connect(domain_branch,"else",append_linear,"execute")
 full="\n".join(n.text for n in b.nodes)+"\n";x.output.parent.mkdir(parents=True,exist_ok=True);x.output.write_text(full,encoding="utf-8")
 if x.paste_output:x.paste_output.parent.mkdir(parents=True,exist_ok=True);x.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",n.text) for n in b.nodes[1:])+"\n",encoding="utf-8")
if __name__=="__main__":main()
