"""Build fail-closed structural validation for the packed camera-channel ABI."""
from __future__ import annotations
import argparse,importlib.util,re,sys
from pathlib import Path

FUNCTION="ValidateCameraChannelInputsV1"
CHANNEL_IDS=("focal_length_mm","aperture_fstop","focus_distance_cm","focus_influence","exposure_ev","bloom_weight","vignette_weight","color_grading_weight","tint_weight","motion_blur_weight","chromatic_aberration_weight","sharpening_weight","matte_weight")
ARRAYS=(("CameraChannelInputChannelIdsV1","string"),("CameraChannelInputKeyOffsetsV1","int"),("CameraChannelInputKeyCountsV1","int"),("CameraChannelInputKeyTimesV1","real"),("CameraChannelInputKeyValuesV1","real"),("CameraChannelInputInterpolationModesV1","string"),("CameraChannelInputArriveTangentsV1","real"),("CameraChannelInputLeaveTangentsV1","real"),("CameraChannelInputDomainsV1","string"))

def load(root):
 p=root/"tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py";s=importlib.util.spec_from_file_location("edd_camera_channel_validation_base",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def pin_kind(node,pin_name,kind,array=False):
 category,subcategory={"bool":("bool",""),"int":("int",""),"real":("real","double"),"string":("string","")}[kind]
 def mutate(line):
  line=re.sub(r'PinType.PinCategory="[^"]*"',f'PinType.PinCategory="{category}"',line,1);line=re.sub(r'PinType.PinSubCategory="[^"]*"',f'PinType.PinSubCategory="{subcategory}"',line,1);line=re.sub(r'PinType.PinSubCategoryObject=(?:None|"[^"]*")','PinType.PinSubCategoryObject=None',line,1);return re.sub(r'PinType.ContainerType=(?:None|Array)',f'PinType.ContainerType={"Array" if array else "None"}',line,1)
 node.mutate_pin(pin_name,mutate)

def main():
 a=argparse.ArgumentParser();a.add_argument("--project-root",type=Path,required=True);a.add_argument("--output",type=Path,required=True);a.add_argument("--paste-output",type=Path);x=a.parse_args();scalar=load(x.project_root);bp=scalar.load_helpers(x.project_root);forms=scalar.load_templates(x.project_root,bp)
 sync=bp.read_blocks(x.project_root/"tools/blueprint/templates/waypoint-struct-sync-node-forms.eddgraph");edit=bp.read_blocks(x.project_root/"tools/blueprint/templates/waypoint-edit-node-forms.eddgraph");playback=bp.read_blocks(x.project_root/"tools/blueprint/snippets/update-linear-playback.eddgraph");find_graph=bp.read_blocks(x.project_root/"tools/blueprint/snippets/find-record-index-v1.eddgraph")
 forms.update(foreach=bp.find_block(sync,r"K2Node_MacroInstance"),length=bp.find_block(edit,r'MemberName="Array_Length"'),item=bp.find_block(playback,r"^Begin Object Class=/Script/BlueprintGraph.K2Node_GetArrayItem"),find=bp.find_block(find_graph,r'MemberName="Array_Find"'))
 b=scalar.Builder(bp,forms,FUNCTION)
 def variable(node,name,kind,array=False):
  scalar.retarget_variable(node,name,"real" if kind=="int" else kind);pin_kind(node,name,kind,array)
  if "Output_Get" in node.pins:pin_kind(node,"Output_Get",kind)
 def get(name,kind,px,py,array=False):
  n=b.add(f"get_{name}_{len(b.nodes)}","get",px,py);variable(n,name,kind,array);return n
 def set_(name,kind,px,py,value=None):
  n=b.add(f"set_{name}_{len(b.nodes)}","set",px,py);variable(n,name,kind)
  if value is not None:scalar.set_default(n,name,value)
  return n
 def add_form(key,form,px,py):
  match=bp.BLOCK_RE.match(forms[form]);cls=match.group("class").rsplit(".",1)[-1];index=b.serial.get(cls,0);b.serial[cls]=index+1;n=bp.Node.clone(key,forms[form],f"{cls}_{index}",px,py);b.nodes.append(n);return n
 def length(source,source_pin,kind,px,py):
  n=add_form(f"length_{source_pin}_{len(b.nodes)}","length",px,py);pin_kind(n,"TargetArray",kind,True);pin_kind(n,"ReturnValue","int");bp.connect(source,source_pin,n,"TargetArray");return n
 def foreach(source,source_pin,kind,px,py):
  n=add_form(f"foreach_{source_pin}_{len(b.nodes)}","foreach",px,py);pin_kind(n,"Array",kind,True);pin_kind(n,"Array Element",kind);pin_kind(n,"Array Index","int");bp.connect(source,source_pin,n,"Array");return n
 def item(source,source_pin,kind,index,index_pin,px,py):
  n=add_form(f"item_{source_pin}_{len(b.nodes)}","item",px,py);pin_kind(n,"Array",kind,True);pin_kind(n,"Output",kind);bp.connect(source,source_pin,n,"Array");bp.connect(index,index_pin,n,"Dimension 1");return n
 def find_first(source,source_pin,value,value_pin,px,py):
  n=add_form(f"find_{source_pin}_{len(b.nodes)}","find",px,py);pin_kind(n,"TargetArray","string",True);pin_kind(n,"ItemToFind","string");pin_kind(n,"ReturnValue","int");bp.connect(source,source_pin,n,"TargetArray");bp.connect(value,value_pin,n,"ItemToFind");return n
 def retarget(n,member,kinds):
  scalar.retarget_function(n,member)
  if member in ("EqualEqual_StrStr","NotEqual_StrStr"):
   n.text=n.text.replace("KismetMathLibrary","KismetStringLibrary")
  for pin,kind in kinds.items():pin_kind(n,pin,kind)
  return n
 def compare(member,left,left_pin,px,py,right=None,right_pin=None,default_b=None,kind="int"):
  n=b.add(f"{member}_{len(b.nodes)}","compare",px,py);retarget(n,member,{"A":kind,"B":kind,"ReturnValue":"bool"});bp.connect(left,left_pin,n,"A")
  if right is not None:bp.connect(right,right_pin,n,"B")
  else:scalar.set_default(n,"B",default_b)
  return n
 def math(member,left,left_pin,px,py,right=None,right_pin=None,default_b=None):
  n=b.math("Add_IntInt",px,py);retarget(n,member,{"A":"int","B":"int","ReturnValue":"int"});bp.connect(left,left_pin,n,"A")
  if right is not None:bp.connect(right,right_pin,n,"B")
  else:scalar.set_default(n,"B",default_b)
  return n
 def combine(member,conditions,px,py):
  current=conditions[0]
  for i,condition in enumerate(conditions[1:]):current=compare(member,current,"ReturnValue",px+i*208,py,condition,"ReturnValue",kind="bool")
  return current

 stage_false=set_("CameraChannelScratchValidV1","bool",256,3040,"false");index_zero=set_("CameraChannelScratchKeyIndexV1","int",480,3040,"0");channel_zero=set_("CameraChannelScratchChannelIndexV1","int",704,3040,"0");failure=set_("CameraChannelFailureCodeV1","string",928,3040,"validation_failed");bp.connect(b.entry,"then",stage_false,"execute");bp.connect(stage_false,"then",index_zero,"execute");bp.connect(index_zero,"then",channel_zero,"execute");bp.connect(channel_zero,"then",failure,"execute")
 arrays={name:get(name,kind,0,i*160,True) for i,(name,kind) in enumerate(ARRAYS)};lengths={name:length(arrays[name],name,kind,256,i*160) for i,(name,kind) in enumerate(ARRAYS)};channel_count=lengths["CameraChannelInputChannelIdsV1"];key_total=lengths["CameraChannelInputKeyTimesV1"]
 duration=get("CameraChannelInputDurationV1","real",0,1600);preset=get("CameraChannelInputFilmbackPresetIdV1","string",0,1760);width=get("CameraChannelInputFilmbackSensorWidthMmV1","real",0,1920);height=get("CameraChannelInputFilmbackSensorHeightMmV1","real",0,2080)
 shape=[compare("GreaterEqual_IntInt",channel_count,"ReturnValue",512,0,default_b="0"),compare("LessEqual_IntInt",channel_count,"ReturnValue",512,160,default_b="13")]
 for i,name in enumerate(("CameraChannelInputKeyOffsetsV1","CameraChannelInputKeyCountsV1","CameraChannelInputDomainsV1")):shape.append(compare("EqualEqual_IntInt",lengths[name],"ReturnValue",736,320+i*160,channel_count,"ReturnValue"))
 for i,name in enumerate(("CameraChannelInputKeyValuesV1","CameraChannelInputArriveTangentsV1","CameraChannelInputLeaveTangentsV1")):shape.append(compare("EqualEqual_IntInt",lengths[name],"ReturnValue",944,320+i*160,key_total,"ReturnValue"))
 shape.extend([b.finite(duration,"CameraChannelInputDurationV1",512,1600),compare("GreaterEqual_DoubleDouble",duration,"CameraChannelInputDurationV1",736,1600,default_b="0.0",kind="real"),compare("NotEqual_StrStr",preset,"CameraChannelInputFilmbackPresetIdV1",512,1760,default_b="",kind="string"),b.finite(width,"CameraChannelInputFilmbackSensorWidthMmV1",512,1920),compare("Greater_DoubleDouble",width,"CameraChannelInputFilmbackSensorWidthMmV1",736,1920,default_b="0.0",kind="real"),b.finite(height,"CameraChannelInputFilmbackSensorHeightMmV1",512,2080),compare("Greater_DoubleDouble",height,"CameraChannelInputFilmbackSensorHeightMmV1",736,2080,default_b="0.0",kind="real")])
 shape_valid=combine("BooleanAND",shape,1312,1280);shape_branch=b.add("shape_branch","branch",4848,3040);bp.connect(failure,"then",shape_branch,"execute");bp.connect(shape_valid,"ReturnValue",shape_branch,"Condition");stage_true=set_("CameraChannelScratchValidV1","bool",5072,3040,"true");bp.connect(shape_branch,"then",stage_true,"execute")
 loop=foreach(arrays["CameraChannelInputChannelIdsV1"],"CameraChannelInputChannelIdsV1","string",5296,3040);bp.connect(stage_true,"then",loop,"Exec");offset=item(arrays["CameraChannelInputKeyOffsetsV1"],"CameraChannelInputKeyOffsetsV1","int",loop,"Array Index",5552,1600);count=item(arrays["CameraChannelInputKeyCountsV1"],"CameraChannelInputKeyCountsV1","int",loop,"Array Index",5552,1760);domain=item(arrays["CameraChannelInputDomainsV1"],"CameraChannelInputDomainsV1","string",loop,"Array Index",5552,1920);first=find_first(arrays["CameraChannelInputChannelIdsV1"],"CameraChannelInputChannelIdsV1",loop,"Array Element",5552,2080);expected=get("CameraChannelScratchKeyIndexV1","int",5552,2240)
 supported=combine("BooleanOR",[compare("EqualEqual_StrStr",loop,"Array Element",5808+i*208,0,default_b=value,kind="string") for i,value in enumerate(CHANNEL_IDS)],8512,0);unique=compare("EqualEqual_IntInt",first,"ReturnValue",5808,2080,loop,"Array Index");offset_ok=compare("EqualEqual_IntInt",offset,"Output",5808,2240,expected,"CameraChannelScratchKeyIndexV1");count_low=compare("GreaterEqual_IntInt",count,"Output",5808,2400,default_b="1");count_high=compare("LessEqual_IntInt",count,"Output",6016,2400,default_b="512")
 is_focus=compare("EqualEqual_StrStr",loop,"Array Element",5808,2560,default_b="focus_distance_cm",kind="string");linear=compare("EqualEqual_StrStr",domain,"Output",6016,2560,default_b="linear",kind="string");reciprocal=compare("EqualEqual_StrStr",domain,"Output",6224,2560,default_b="reciprocal",kind="string");focus_domain=combine("BooleanOR",[linear,reciprocal],6432,2560);not_focus=compare("NotEqual_StrStr",loop,"Array Element",5808,2720,default_b="focus_distance_cm",kind="string");nonfocus_linear=combine("BooleanAND",[not_focus,linear],6016,2720);domain_ok=combine("BooleanOR",[combine("BooleanAND",[is_focus,focus_domain],6848,2560),nonfocus_linear],7264,2640)
 valid=combine("BooleanAND",[supported,unique,offset_ok,count_low,count_high,domain_ok],7680,2080);branch=b.add("channel_branch","branch",8720,3040);bp.connect(loop,"LoopBody",branch,"execute");bp.connect(valid,"ReturnValue",branch,"Condition");reject=set_("CameraChannelScratchValidV1","bool",8944,3200,"false");bp.connect(branch,"else",reject,"execute");next_offset=math("Add_IntInt",expected,"CameraChannelScratchKeyIndexV1",8944,2400,count,"Output");store_offset=set_("CameraChannelScratchKeyIndexV1","int",9168,3040);bp.connect(next_offset,"ReturnValue",store_offset,"CameraChannelScratchKeyIndexV1");bp.connect(branch,"then",store_offset,"execute")
 prior=get("CameraChannelScratchValidV1","bool",9408,2240);final_keys=get("CameraChannelScratchKeyIndexV1","int",9408,2400);key_exact=compare("EqualEqual_IntInt",final_keys,"CameraChannelScratchKeyIndexV1",9632,2400,key_total,"ReturnValue");mode_expected=math("Subtract_IntInt",final_keys,"CameraChannelScratchKeyIndexV1",9632,2560,channel_count,"ReturnValue");mode_exact=compare("EqualEqual_IntInt",mode_expected,"ReturnValue",9856,2560,lengths["CameraChannelInputInterpolationModesV1"],"ReturnValue");prior_and_keys=compare("BooleanAND",prior,"CameraChannelScratchValidV1",10080,2400,key_exact,"ReturnValue",kind="bool");final_valid=compare("BooleanAND",prior_and_keys,"ReturnValue",10288,2400,mode_exact,"ReturnValue",kind="bool");final_branch=b.add("final_branch","branch",10528,3040);bp.connect(loop,"Completed",final_branch,"execute");bp.connect(final_valid,"ReturnValue",final_branch,"Condition");final_reject=set_("CameraChannelScratchValidV1","bool",10752,3200,"false");success=set_("CameraChannelFailureCodeV1","string",10752,3040,"");bp.connect(final_branch,"else",final_reject,"execute");bp.connect(final_branch,"then",success,"execute")
 full="\n".join(n.text for n in b.nodes)+"\n";x.output.parent.mkdir(parents=True,exist_ok=True);x.output.write_text(full,encoding="utf-8")
 if x.paste_output:x.paste_output.parent.mkdir(parents=True,exist_ok=True);x.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",n.text) for n in b.nodes[1:])+"\n",encoding="utf-8")
if __name__=="__main__":main()
