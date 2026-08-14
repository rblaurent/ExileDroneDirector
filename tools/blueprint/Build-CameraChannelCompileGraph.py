"""Build the policy-free camera channel assembly compile coordinator."""
from __future__ import annotations
import argparse,importlib.util,re,sys
from pathlib import Path
FUNCTION="CompileCameraChannelAssemblyV1";TARGET='"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'
def load(root):p=root/"tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py";s=importlib.util.spec_from_file_location("edd_camera_channel_compile_base",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def kind(n,p,k):
 cat,sub={"bool":("bool",""),"int":("int","")}[k]
 def f(line):line=re.sub(r'PinType.PinCategory="[^"]*"',f'PinType.PinCategory="{cat}"',line,1);line=re.sub(r'PinType.PinSubCategory="[^"]*"',f'PinType.PinSubCategory="{sub}"',line,1);return re.sub(r'PinType.ContainerType=(?:None|Array)','PinType.ContainerType=None',line,1)
 n.mutate_pin(p,f)
def main():
 p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--paste-output",type=Path);a=p.parse_args();s=load(a.project_root);bp=s.load_helpers(a.project_root);forms=s.load_templates(a.project_root,bp);b=s.Builder(bp,forms,FUNCTION);calls=bp.read_blocks(a.project_root/"tools/blueprint/snippets/activate-drone-view.eddgraph");loops=bp.read_blocks(a.project_root/"tools/blueprint/templates/adaptive-arc-forloop-node-form.eddgraph");call_form=bp.find_block(calls,r'MemberName="SwitchToDroneView"');loop_form=bp.find_block(loops,r"StandardMacros:ForLoop")
 def addform(key,raw,x,y):m=bp.BLOCK_RE.match(raw);cls=m.group("class").rsplit(".",1)[-1];i=b.serial.get(cls,0);b.serial[cls]=i+1;n=bp.Node.clone(key,raw,f"{cls}_{i}",x,y);b.nodes.append(n);return n
 def call(name,x,y):n=addform(f"call_{name}",call_form,x,y);n.text=re.sub(r"FunctionReference=\([^\n]*\)",f'FunctionReference=(MemberName="{name}",bSelfContext=True)',n.text,1);n.mutate_pin("self",lambda line:re.sub(r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"',f"PinType.PinSubCategoryObject={TARGET}",line,1));return n
 def var(n,name,k):s.retarget_variable(n,name,"real" if k=="int" else k);kind(n,name,k);kind(n,"Output_Get",k) if "Output_Get" in n.pins else None
 reset=call("ResetCameraChannelCompileV1",256,0);validate=call("ValidateCameraChannelInputsV1",512,0);stage=b.add("stage_get","get",512,-256);var(stage,"CameraChannelScratchValidV1","bool");guard=b.add("validation_guard","branch",768,0);bp.connect(b.entry,"then",reset,"execute");bp.connect(reset,"then",validate,"execute");bp.connect(validate,"then",guard,"execute");bp.connect(stage,"CameraChannelScratchValidV1",guard,"Condition")
 loop=addform("channel_loop",loop_form,1024,0);s.set_default(loop,"FirstIndex","0");s.set_default(loop,"LastIndex","12");bp.connect(guard,"then",loop,"execute");set_index=b.add("set_index","set",1280,0);var(set_index,"CameraChannelScratchChannelIndexV1","int");bp.connect(loop,"Index",set_index,"CameraChannelScratchChannelIndexV1");bp.connect(loop,"LoopBody",set_index,"execute");candidate=call("CompileCameraChannelCandidateV1",1536,0);bp.connect(set_index,"then",candidate,"execute")
 final_stage=b.add("final_stage_get","get",1536,-256);var(final_stage,"CameraChannelScratchValidV1","bool");commit_guard=b.add("commit_guard","branch",1792,0);bp.connect(loop,"Completed",commit_guard,"execute");bp.connect(final_stage,"CameraChannelScratchValidV1",commit_guard,"Condition");commit=call("CommitCameraChannelAssemblyV1",2048,0);bp.connect(commit_guard,"then",commit,"execute")
 full="\n".join(n.text for n in b.nodes)+"\n";a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(full,encoding="utf-8")
 if a.paste_output:a.paste_output.parent.mkdir(parents=True,exist_ok=True);a.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",n.text) for n in b.nodes[1:])+"\n",encoding="utf-8")
if __name__=="__main__":main()

