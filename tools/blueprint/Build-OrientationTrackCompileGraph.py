"""Build the ordered end-to-end orientation track compiler."""
from __future__ import annotations
import argparse, importlib.util, re, sys
from pathlib import Path

FUNCTION = "CompileOrientationTrackV1"
STAGES = (
    "ResetOrientationTrackCandidateV1",
    "ValidateOrientationTrackInputsV1",
    "AlignOrientationWaypointsV1",
    "ComputeOrientationForwardDeltasV1",
    "ComputeOrientationTrackTangentRatesV1",
    "BuildOrientationTrackSegmentsV1",
    "CommitCompiledOrientationTrackV1",
)

def load(root):
    path=root/"tools/blueprint/Build-TrajectoryScalarEvaluatorGraphs.py";spec=importlib.util.spec_from_file_location("edd_orientation_compile_base",path);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module

def main():
    p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--paste-output",type=Path);a=p.parse_args()
    scalar=load(a.project_root);bp=scalar.load_helpers(a.project_root);forms=scalar.load_templates(a.project_root,bp);b=scalar.Builder(bp,forms,FUNCTION)
    blocks=bp.read_blocks(a.project_root/"tools/blueprint/snippets/activate-drone-view.eddgraph");template=bp.find_block(blocks,r'MemberName="SwitchToDroneView"')
    calls=[]
    for index,name in enumerate(STAGES):
        node=bp.Node.clone(f"stage_{index}",template,f"K2Node_CallFunction_{index}",256+index*320,0)
        node.text=re.sub(r'FunctionReference=\([^)]*\)',f'FunctionReference=(MemberName="{name}",bSelfContext=True)',node.text,count=1)
        b.nodes.append(node);calls.append(node)
    bp.connect(b.entry,"then",calls[0],"execute")
    for left,right in zip(calls,calls[1:]):bp.connect(left,"then",right,"execute")
    full="\n".join(n.text for n in b.nodes)+"\n";a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(full,encoding="utf-8")
    if a.paste_output:
        body=[re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)',"",n.text) for n in b.nodes[1:]];a.paste_output.parent.mkdir(parents=True,exist_ok=True);a.paste_output.write_text("\n".join(body)+"\n",encoding="utf-8")

if __name__=="__main__":main()
