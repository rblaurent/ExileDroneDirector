"""Build the policy-free ordered carrier-frame compilation transaction."""
from __future__ import annotations
import argparse,importlib.util,re,sys
from pathlib import Path
FUNCTION="CompileCarrierFrameTransportV1"
CALLS=("ResetCarrierFrameTransportV1","StageCarrierFrameTransportInputsV1","ValidateCarrierFrameTransportInputsV1","BuildCarrierFrameTangentsV1","BuildCarrierFrameTransportSamplesV1","CommitCompiledCarrierFrameTransportV1")
TARGET='"/Script/Engine.BlueprintGeneratedClass\'/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C\'"'
def main():
 p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--paste-output",type=Path);a=p.parse_args();path=a.project_root/"tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py";spec=importlib.util.spec_from_file_location("edd_carrier_compile_base",path);s=importlib.util.module_from_spec(spec);sys.modules[spec.name]=s;spec.loader.exec_module(s);bp=s.load_helpers(a.project_root);forms=s.load_templates(a.project_root,bp);raw=bp.read_blocks(a.project_root/"tools/blueprint/snippets/activate-drone-view.eddgraph");forms["self_call"]=bp.find_block(raw,r'MemberName="SwitchToDroneView"');b=s.Builder(bp,forms,FUNCTION);calls=[]
 for i,name in enumerate(CALLS):
  node=b.add(f"call_{name}","self_call",256+i*320,0);node.text=re.sub(r"FunctionReference=\([^\n]*\)",f'FunctionReference=(MemberName="{name}",bSelfContext=True)',node.text,1);node.mutate_pin("self",lambda line:re.sub(r'PinType.PinSubCategoryObject="/Script/Engine.BlueprintGeneratedClass\'[^\']+\'"',f"PinType.PinSubCategoryObject={TARGET}",line,1));calls.append(node)
 bp.connect(b.entry,"then",calls[0],"execute");[bp.connect(left,"then",right,"execute") for left,right in zip(calls,calls[1:])];full="\n".join(node.text for node in b.nodes)+"\n";a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(full,encoding="utf-8")
 if a.paste_output:a.paste_output.parent.mkdir(parents=True,exist_ok=True);a.paste_output.write_text("\n".join(re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",node.text) for node in b.nodes[1:])+"\n",encoding="utf-8")
if __name__=="__main__":main()
