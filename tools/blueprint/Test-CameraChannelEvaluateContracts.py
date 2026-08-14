"""End-to-end offline contracts for absolute-time camera channel evaluation."""
from __future__ import annotations
import argparse,copy,importlib.util,math,random,re,sys
from pathlib import Path
def load(path,name):s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def member(node):m=re.search(r'MemberName="([^"]+)"',node.text);return None if m is None else m.group(1)
def main():
 a=argparse.ArgumentParser();a.add_argument("--project-root",type=Path,required=True);a.add_argument("--graph",type=Path,required=True);a.add_argument("--paste",action="store_true");x=a.parse_args();c=load(x.project_root/"tools/blueprint/Test-WaypointCaptureContracts.py","edd_camera_channel_evaluate_graph_base");nodes=c.parse_graph(x.graph);c.require(len(nodes)==(39 if x.paste else 40),f"node count {len(nodes)}");entries=[n for n in nodes.values() if "K2Node_FunctionEntry" in n.node_class];c.require(len(entries)==(0 if x.paste else 1),"entry count");text=x.graph.read_text(encoding="utf-8");calls=("ResetCameraChannelResultV1","StageCompiledCameraChannelV1","PublishCameraChannelSampleV1");c.require(all(text.count(f'MemberName="{name}"')==1 for name in calls),"exact reset/stage/publish calls");c.require(text.count("StandardMacros:ForLoop")==1 and 'DefaultValue="0"' in text and 'DefaultValue="12"' in text,"canonical 0..12 loop");c.require('MemberName="CompileCameraScalarTrackV1"' not in text and 'MemberName="CompileCameraChannelAssemblyV1"' not in text,"evaluation never compiles");setters=[member(n) for n in nodes.values() if "K2Node_VariableSet" in n.node_class];c.require(set(setters)=={"CameraChannelScratchChannelIndexV1","CameraChannelScratchKeyIndexV1","CameraChannelResultFilmbackPresetIdV1","CameraChannelResultFilmbackSensorWidthMmV1","CameraChannelResultFilmbackSensorHeightMmV1","CameraChannelResultValidV1"},"evaluation setter ownership");c.require(setters[-1]=="CameraChannelResultValidV1","frame validity publishes last")
 sys.path.insert(0,str(x.project_root/"tools/trajectory"));scalar=load(x.project_root/"tools/trajectory/camera_scalar_track_reference.py","camera_scalar_track_reference");ref=load(x.project_root/"tools/trajectory/camera_channel_assembly_reference.py","edd_camera_channel_evaluate_reference");policies={item.channel_id:item for item in ref.CHANNEL_POLICIES_V1}
 def flatten(assembly):
  bank=dict(offsets=[],counts=[],times=[],values=[],modes=[],arrives=[],leaves=[],domains=[],duration=assembly.duration_seconds,filmback=assembly.filmback,valid=True)
  for channel in assembly.channels:bank["offsets"].append(len(bank["times"]));bank["counts"].append(len(channel.track.key_times));bank["times"].extend(channel.track.key_times);bank["values"].extend(channel.track.domain_values);bank["modes"].extend(channel.track.interpolation_modes);bank["arrives"].extend(channel.track.arrive_tangents);bank["leaves"].extend(channel.track.leave_tangents);bank["domains"].append(channel.track.domain)
  return bank
 def evaluate(bank,query):
  if not bank.get("valid") or isinstance(query,bool) or not isinstance(query,(int,float)) or not math.isfinite(float(query)):return None
  outputs=[]
  for index,channel_id in enumerate(ref.CHANNEL_IDS_V1):
   if not all(len(bank[name])==13 for name in ("offsets","counts","domains")):return None
   offset,count,domain=bank["offsets"][index],bank["counts"][index],bank["domains"][index];mode_start=offset-index
   if not isinstance(offset,int) or not isinstance(count,int) or offset<0 or not 1<=count<=512 or mode_start<0:return None
   if domain not in (("linear","reciprocal") if index==2 else ("linear",)):return None
   if any(offset+count>len(bank[name]) for name in ("times","values","arrives","leaves")) or mode_start+count-1>len(bank["modes"]):return None
   policy=policies[channel_id];track=scalar.CompiledCameraScalarTrack(tuple(bank["times"][offset:offset+count]),tuple(bank["values"][offset:offset+count]),tuple(bank["modes"][mode_start:mode_start+count-1]),tuple(bank["arrives"][offset:offset+count]),tuple(bank["leaves"][offset:offset+count]),bank["duration"],domain,True,policy.minimum,True,policy.maximum,policy.clamp_output);outputs.append(scalar.evaluate_camera_scalar_track(track,query))
  if len(outputs)!=13:return None
  return tuple(outputs),bank["filmback"]
 rng=random.Random(0xEDD640)
 for case_index in range(40):
  duration=4.0;authored=[]
  for channel_id in rng.sample(ref.CHANNEL_IDS_V1,rng.randint(0,13)):
   policy=policies[channel_id];low=policy.minimum;high=policy.maximum;keys=(scalar.CameraScalarKey(0.0,rng.uniform(low,high),rng.choice(("linear","smooth","cinematic"))),scalar.CameraScalarKey(duration,rng.uniform(low,high)));authored.append(ref.AuthoredCameraChannelV1(channel_id,keys,rng.choice(policy.permitted_domains)))
  assembly=ref.compile_camera_channel_assembly_v1(duration,ref.FilmbackSnapshotV1(f"filmback_{case_index}",36.0,24.0),authored);bank=flatten(assembly);queries=tuple(index/4.0 for index in range(21));forward={query:evaluate(bank,query) for query in queries};reverse={query:evaluate(bank,query) for query in reversed(queries)};c.require(forward==reverse,"history-free forward/reverse");
  for query,result in forward.items():oracle=ref.evaluate_camera_channel_assembly_v1(assembly,query);c.require(result is not None and tuple(sample for sample in result[0])==tuple(sample for _channel,sample in oracle.samples) and result[1]==oracle.filmback,"oracle frame equality")
 base=flatten(ref.compile_camera_channel_assembly_v1(2.0,ref.FilmbackSnapshotV1("test",36.0,24.0),()));c.require(evaluate(base,math.nan) is None and evaluate(base,math.inf) is None,"non-finite queries");bad=copy.deepcopy(base);bad["valid"]=False;c.require(evaluate(bad,1.0) is None,"invalid compile");bad=copy.deepcopy(base);bad["counts"][6]=0;c.require(evaluate(bad,1.0) is None,"poisoned slice");bad=copy.deepcopy(base);bad["domains"][0]="reciprocal";c.require(evaluate(bad,1.0) is None,"illegal domain");bad=copy.deepcopy(base);bad["values"].pop();c.require(evaluate(bad,1.0) is None,"truncated values")
 print(f"Camera channel evaluation contracts passed ({'paste' if x.paste else 'full'}): 840 forward + reverse frames, 6 failures")
if __name__=="__main__":main()

