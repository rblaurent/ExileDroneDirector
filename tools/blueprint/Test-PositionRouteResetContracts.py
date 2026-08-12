"""Exact semantic contracts for the position-route reset transaction."""
from __future__ import annotations
import argparse,importlib.util,re,sys
from pathlib import Path

INPUTS=("PositionRouteInputWaypointPositionsV1","PositionRouteInputDurationsV1","PositionRouteInputSpatialCurveTypesV1","PositionRouteInputTimeProfilesV1","PositionRouteInputArcToleranceV1","PositionRouteInputMaxArcDepthV1","PositionRouteInputMaxArcOperationsV1","PositionRouteInputElapsedSecondsV1")
def load(path,name):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module
def main():
 p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--graph",type=Path,required=True);p.add_argument("--paste",action="store_true");a=p.parse_args()
 generator=load(a.project_root/"tools/blueprint/Build-PositionRouteResetGraph.py","edd_position_reset_spec");c=load(a.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py","edd_position_reset_contract_base");nodes=c.parse_graph(a.graph)
 c.require(len(nodes)==(51 if not a.paste else 50),f"reset node count {len(nodes)}");entries=[n for n in nodes.values() if "K2Node_FunctionEntry" in n.node_class];c.require(len(entries)==(0 if a.paste else 1),"reset entry count")
 clears=[]
 for name,_kind in generator.ARRAYS:
  getter=c.one(nodes,f'MemberName="{name}"');clear=next((node for node in nodes.values() if 'MemberName="Array_Clear"' in node.text and any(target==getter.name for pin in node.pins.values() for target,_ in pin.links)),None);c.require(clear is not None,f"{name} clear missing");c.require_link(getter,name,clear,"TargetArray",f"{name} must be cleared");clears.append(clear)
 setters=[]
 for name,_kind,value in generator.SCALARS:
  setter=c.one(nodes,f'MemberName="{name}"');line=setter.pins[name].body;explicit=re.search(r'(?:^|,)DefaultValue="([^"]*)"',line);c.require(explicit and explicit.group(1)==value,f"{name} reset changed");setters.append(setter)
 chain=[*clears,*setters]
 if a.paste:c.require(not chain[0].pins["execute"].links,"paste root must be exposed")
 else:c.require_link(entries[0],"then",chain[0],"execute","entry must reach first clear")
 for left,right in zip(chain,chain[1:]):c.require_link(left,"then",right,"execute","reset order changed")
 for name in INPUTS:c.require(not any(f'MemberName="{name}"' in node.text for node in nodes.values()),f"authored input must remain untouched: {name}")
 known=set(nodes);external={target for node in nodes.values() for pin in node.pins.values() for target,_ in pin.links if target not in known};c.require(not external,f"external links {external}")
 print(f"Position route reset contracts passed ({'paste' if a.paste else 'full'}): {len(nodes)} nodes")
if __name__=="__main__":main()
