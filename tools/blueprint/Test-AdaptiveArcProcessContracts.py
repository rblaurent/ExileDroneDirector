"""Exact executable topology contracts for bounded adaptive arc processing."""
from __future__ import annotations
import argparse,importlib.util,re,sys
from pathlib import Path

def load(root):
 p=root/"tools/blueprint/Test-WaypointCaptureContracts.py";s=importlib.util.spec_from_file_location("edd_arc_process_contract_base",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m

def main():
 p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--graph",type=Path,required=True);p.add_argument("--paste",action="store_true");a=p.parse_args();c=load(a.project_root);nodes=c.parse_graph(a.graph)
 expected=117 if not a.paste else 116;c.require(len(nodes)==expected,f"exact {expected}-node process graph")
 def all_(text):return [n for n in nodes.values() if text in n.text]
 def one(text):return next(n for n in nodes.values() if text in n.text)
 c.require(len(all_("StandardMacros:ForLoopWithBreak"))==1,"one bounded breakable for-loop")
 c.require(not [n for n in nodes.values() if "StandardMacros:ForLoop'" in n.text],"non-breakable bounded loop absent")
 loop=one("StandardMacros:ForLoopWithBreak");match=re.search(r'DefaultValue="([^"]+)"',loop.pins["FirstIndex"].body);c.require(match is None or match.group(1)=="0","loop starts at typed zero")
 c.require(len(all_('MemberName="Array_Length"'))==10,"eight preflight lengths plus active and final lengths")
 c.require(len(all_('MemberName="Array_Remove"'))==5,"five synchronized stack pops")
 c.require(len([n for n in nodes.values() if "K2Node_GetArrayItem" in n.node_class])==5,"five synchronized last-item reads")
 c.require(len(all_('MemberName="Array_Add"'))==13,"ten right/left pushes and three candidate appends")
 for node in all_('MemberName="Array_Add"'):
  c.require(len(node.pins["NewItem"].links)<=1,f"{node.name} NewItem has at most one source")
 c.require(len(all_('MemberName="EvaluateQuinticVectorV1"'))==1,"one proven quintic primitive call")
 c.require(len(all_('MemberName="TrajectoryResultPositionVectorV1"'))==1,"one exact quintic result-position getter")
 c.require(not all_('MemberName="TrajectoryResultPositionV1"'),"legacy nonexistent result-position getter absent")
 c.require(len(all_('MemberName="Vector_Distance"'))==3,"chord and two polyline distances")
 c.require(not all_('MemberName="Add_VectorVector"'),"redundant linear midpoint vector sum absent")
 c.require(not all_('MemberName="Multiply_VectorVector"'),"redundant linear midpoint vector half absent")
 c.require(not [n for n in nodes.values() if "K2Node_Select" in n.node_class],"redundant linear/quintic midpoint select absent")
 c.require(len(all_('MemberName="EqualEqual_IntInt"'))==9,"eight exact preflight cardinalities and final empty check")
 c.require(len(all_('MemberName="BooleanAND"'))==13,"sticky preflight, active, refinement, and completion conjunctions")
 c.require(len(all_('MemberName="BooleanOR"'))==1,"minimum-depth or error refinement reason")
 c.require(len(all_('MemberName="Less_IntInt"'))==2,"maximum and minimum depth comparisons")
 c.require(len(all_('MemberName="Greater_DoubleDouble"'))==1,"error tolerance comparison")
 # Right five pushes must precede left five in the executable chain. This is
 # what makes a LIFO stack reproduce recursive left-first sample ordering.
 adds=all_('MemberName="Array_Add"');candidate_getters=[one(name) for name in ("TrajectoryArcBuildCandidateUsV1","TrajectoryArcBuildCandidatePositionsV1","TrajectoryArcBuildCandidateDistancesV1")];candidate_adds={n.name for n in adds if any(c.linked(g,next(pin for pin in g.pins if pin.startswith("TrajectoryArcBuildCandidate")),n,"TargetArray") for g in candidate_getters)};pushes=[n for n in adds if n.name not in candidate_adds]
 c.require(len(pushes)==10,"ten work-stack pushes")
 # U0 owns the pure Array_Length feeding every remove index. It must be the
 # final impure removal, otherwise later reads reevaluate after U0 shrinks.
 work_names=("TrajectoryArcBuildWorkU0V1","TrajectoryArcBuildWorkU1V1","TrajectoryArcBuildWorkP0V1","TrajectoryArcBuildWorkP1V1","TrajectoryArcBuildWorkDepthV1")
 work_getters={name:one(name) for name in work_names};removes=all_('MemberName="Array_Remove"')
 remove_for={name:next(n for n in removes if c.linked(getter,name,n,"TargetArray")) for name,getter in work_getters.items()}
 pop_order=("TrajectoryArcBuildWorkU1V1","TrajectoryArcBuildWorkP0V1","TrajectoryArcBuildWorkP1V1","TrajectoryArcBuildWorkDepthV1","TrajectoryArcBuildWorkU0V1")
 for left,right in zip(pop_order,pop_order[1:]):c.require(c.linked(remove_for[left],"then",remove_for[right],"execute"),f"stable pop order {left} before {right}")
 # Every failure writes stage-valid false; only final completion can write a
 # computed value back to it.
 stage_sets=[n for n in nodes.values() if "K2Node_VariableSet" in n.node_class and 'MemberName="TrajectoryArcBuildStageValidV1"' in n.text]
 c.require(len(stage_sets)==3,"preflight, primitive, and completion stage writes")
 entries=[n for n in nodes.values() if "K2Node_FunctionEntry" in n.node_class];c.require(len(entries)==(0 if a.paste else 1),"entry count")
 root_branches=[n for n in nodes.values() if "K2Node_IfThenElse" in n.node_class and c.linked(n,"then",loop,"Execute")]
 c.require(len(root_branches)==1,"unique preflight branch feeds bounded loop")
 root=root_branches[0]
 active_guards=[n for n in nodes.values() if "K2Node_IfThenElse" in n.node_class and c.linked(n,"else",loop,"Break")]
 c.require(len(active_guards)==1,"inactive or empty work breaks the bounded loop")
 linear_get=one('MemberName="TrajectoryArcBuildInputLinearV1"')
 linear_branches=[n for n in nodes.values() if "K2Node_IfThenElse" in n.node_class and c.linked(linear_get,"TrajectoryArcBuildInputLinearV1",n,"Condition")]
 c.require(len(linear_branches)==1,"one explicit linear fast-path branch")
 linear_branch=linear_branches[0]
 primitive=one('MemberName="EvaluateQuinticVectorV1"')
 c.require(c.linked(linear_branch,"else",primitive,"execute"),"only nonlinear work calls the quintic primitive")
 candidate_u=one('MemberName="TrajectoryArcBuildCandidateUsV1"')
 linear_accept=[n for n in all_('MemberName="Array_Add"') if c.linked(candidate_u,"TrajectoryArcBuildCandidateUsV1",n,"TargetArray")]
 c.require(len(linear_accept)==1 and c.linked(linear_branch,"then",linear_accept[0],"execute"),"linear work accepts its exact endpoint directly")
 # The native seam must remain independently selectable after paste. Exact
 # branch/loop overlap with the synchronized current-value setters made a
 # one-link operation select and move the hidden setter instead.
 def pos(node):
  x=re.search(r'(?m)^\s*NodePosX=(-?\d+)\s*$',node.text)
  y=re.search(r'(?m)^\s*NodePosY=(-?\d+)\s*$',node.text)
  return (int(x.group(1)) if x else 0,int(y.group(1)) if y else 0)
 for node in nodes.values():
  if "K2Node_VariableSet" in node.node_class:
   c.require(pos(node)!=pos(root),f"{node.name} must not overlap preflight root")
   c.require(pos(node)!=pos(loop),f"{node.name} must not overlap bounded loop")
 if a.paste:
  c.require(not root.pins["execute"].links,"paste root intentionally has no native entry seam")
 else:
  entry=entries[0]
  c.require(c.linked(entry,"then",root,"execute"),"native entry feeds preflight branch")
  root_execute_id=re.search(r"PinId=([0-9A-F]{32})",root.pins["execute"].body).group(1)
  entry_then_id=re.search(r"PinId=([0-9A-F]{32})",entry.pins["then"].body).group(1)
  c.require(entry.pins["then"].links==((root.name,root_execute_id),),"entry has one exact outgoing seam")
  c.require(root.pins["execute"].links==((entry.name,entry_then_id),),"preflight branch has one reciprocal incoming seam")
 print(f"adaptive arc process contracts passed: {a.graph} ({len(nodes)} nodes)")
if __name__=="__main__":main()
