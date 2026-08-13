"""Build policy-free ordered camera scalar-track compilation."""
from __future__ import annotations
import argparse,importlib.util,re,sys
from pathlib import Path
FUNCTION="CompileCameraScalarTrackV1";CALLS=("ResetCameraScalarTrackCompileV1","ValidateCameraScalarTrackInputsV1","BuildCameraScalarTrackCandidatesV1","CommitCameraScalarTrackV1")
TARGET='"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'
def main():
 a=argparse.ArgumentParser();a.add_argument("--project-root",type=Path,required=True);a.add_argument("--output",type=Path,required=True);a.add_argument("--paste-output",type=Path);x=a.parse_args();p=x.project_root/"tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py";s=importlib.util.spec_from_file_location("edd_camera_scalar_compile_base",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);bp=m.load_helpers(x.project_root);forms=m.load_templates(x.project_root,bp);raw=bp.read_blocks(x.project_root/"tools/blueprint/snippets/activate-drone-view.eddgraph");forms["self_call"]=bp.find_block(raw,r'MemberName="SwitchToDroneView"');b=m.Builder(bp,forms,FUNCTION);calls=[]
 for i,name in enumerate(CALLS):
  n=b.add(f"call_{name}","self_call",256+i*320,0);n.text=re.sub(r"FunctionReference=\([^\n]*\)",f'FunctionReference=(MemberName="{name}",bSelfContext=True)',n.text,1);n.mutate_pin("self",lambda line:re.sub(r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"',f"PinType.PinSubCategoryObject={TARGET}",line,1));calls.append(n)
 bp.connect(b.entry,"then",calls[0],"execute");[bp.connect(l,"then",r,"execute") for l,r in zip(calls,calls[1:])];full="\n".join(n.text for n in b.nodes)+"\n";x.output.parent.mkdir(parents=True,exist_ok=True);x.output.write_text(full,encoding="utf-8")
 if x.paste_output:x.paste_output.parent.mkdir(parents=True,exist_ok=True);x.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",n.text) for n in b.nodes[1:])+"\n",encoding="utf-8")
if __name__=="__main__":main()
