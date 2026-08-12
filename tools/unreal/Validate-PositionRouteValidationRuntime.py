"""Execute compiled position-route validation across valid and malformed inputs."""
from __future__ import annotations
import math,random
import unreal

PREFIX="EDD_POSITION_ROUTE_VALIDATION_RUNTIME";CLASS="/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector.BPC_EDD_ClientDirector_C"
INPUTS=("PositionRouteInputWaypointPositionsV1","PositionRouteInputDurationsV1","PositionRouteInputSpatialCurveTypesV1","PositionRouteInputTimeProfilesV1","PositionRouteInputArcToleranceV1","PositionRouteInputMaxArcDepthV1","PositionRouteInputMaxArcOperationsV1")
ROUTE_STATE=("PositionRouteStageValidV1",)
PRIMITIVE=("TrajectoryInputStartPositionVectorV1","TrajectoryInputEndPositionVectorV1","TrajectoryInputStartVelocityUVectorV1","TrajectoryInputEndVelocityUVectorV1","TrajectoryInputStartAccelerationUVectorV1","TrajectoryInputEndAccelerationUVectorV1","TrajectoryInputAlphaV1","TrajectoryInputProfileV1","TrajectoryResultValueV1","TrajectoryResultDerivativeUV1","TrajectoryResultSecondDerivativeUV1","TrajectoryResultValidV1","TrajectoryResultPositionVectorV1","TrajectoryResultDerivativeUVectorV1","TrajectoryResultSecondDerivativeUVectorV1","TrajectoryResultVectorValidV1")
SPATIAL=("linear","auto_cinematic");PROFILES=("linear","smoothstep","smootherstep","cinematic_s_curve","accelerate_through","brake_into")
def emit(label,value):unreal.log(f"{PREFIX}|{label}|{value}")
def require(condition,message):
 if not condition:raise RuntimeError(f"{PREFIX}|FAIL|{message}")
def variants(name):
 snake="".join(("_"+c.lower()) if c.isupper() else c for c in name).lstrip("_");return name,unreal.Name(name),snake,unreal.Name(snake)
def get(obj,name):
 for candidate in variants(name):
  try:return obj.get_editor_property(candidate)
  except Exception:pass
 raise RuntimeError(name)
def set_(obj,name,value):
 for candidate in variants(name):
  try:obj.set_editor_property(candidate,value);return
  except Exception:pass
 raise RuntimeError(name)
def vector(values):return unreal.Vector(*(float(v) for v in values))
def finite_vector(value):return all(math.isfinite(float(v)) for v in (value.x,value.y,value.z))

generated=unreal.load_class(None,CLASS);require(generated is not None,"class");obj=unreal.get_default_object(generated);touched=tuple(dict.fromkeys((*INPUTS,*ROUTE_STATE,*PRIMITIVE)));saved={name:get(obj,name) for name in touched}
def stage(points,durations,curves,profiles,tolerance=.01,depth=12,operations=8191):
 set_(obj,INPUTS[0],[vector(v) for v in points]);set_(obj,INPUTS[1],[float(v) for v in durations]);set_(obj,INPUTS[2],list(curves));set_(obj,INPUTS[3],list(profiles));set_(obj,INPUTS[4],float(tolerance));set_(obj,INPUTS[5],int(depth));set_(obj,INPUTS[6],int(operations))
def validate(expected,label):
 set_(obj,"PositionRouteStageValidV1",not expected);obj.call_method("ValidatePositionRouteInputsV1");actual=bool(get(obj,"PositionRouteStageValidV1"));require(actual is expected,f"{label}:{actual}!={expected}")
def route(count,seed=0):
 rng=random.Random(0xEDD072+seed);points=[(rng.uniform(-1e6,1e6),rng.uniform(-1e6,1e6),rng.uniform(-1e6,1e6)) for _ in range(count)];durations=[10**rng.uniform(-3,3) for _ in range(count-1)];curves=[SPATIAL[i%len(SPATIAL)] for i in range(count-1)];profiles=[PROFILES[i%len(PROFILES)] for i in range(count-1)];return points,durations,curves,profiles
try:
 valid=invalid=sanitized=0
 for count in (2,3,8,64,512):
  values=route(count,count);stage(*values);validate(True,f"valid-{count}");valid+=1
 base=route(4,99)
 for args,label in (
  (([],[],[],[]),"empty"),(([base[0][0]],[],[],[]),"one-waypoint"),
  ((base[0],[1.0],base[2],base[3]),"duration-shape"),((base[0],base[1],["linear"],base[3]),"curve-shape"),((base[0],base[1],base[2],["linear"]),"profile-shape"),
 ):
  stage(*args);validate(False,label);invalid+=1
 oversized=route(513,513);stage(*oversized);validate(False,"too-many-waypoints");invalid+=1
 for tolerance,depth,operations,label in ((0.0,12,8191,"zero-tolerance"),(-1.0,12,8191,"negative-tolerance"),(math.nan,12,8191,"nan-tolerance"),(math.inf,12,8191,"inf-tolerance"),(.01,0,8191,"depth-low"),(.01,13,8191,"depth-high"),(.01,12,0,"operations-low"),(.01,12,8192,"operations-high")):
  stage(*base,tolerance,depth,operations);validate(False,label);invalid+=1
 for index,bad in enumerate((0.0,-1.0,math.nan,math.inf,-math.inf)):
  durations=list(base[1]);durations[1]=bad;stage(base[0],durations,base[2],base[3]);validate(False,f"duration-{index}");invalid+=1
 for index,bad in enumerate(("","spline","LINEAR")):
  curves=list(base[2]);curves[1]=bad;stage(base[0],base[1],curves,base[3]);validate(False,f"curve-{index}");invalid+=1
 for index,bad in enumerate(("","bounce","Linear")):
  profiles=list(base[3]);profiles[1]=bad;stage(base[0],base[1],base[2],profiles);validate(False,f"profile-{index}");invalid+=1
 # A later valid element may not heal an earlier rejection.
 curves=["bad","linear","auto_cinematic"];stage(base[0],base[1],curves,base[3]);validate(False,"sticky-curve");invalid+=1
 profiles=["bad","linear","cinematic_s_curve"];stage(base[0],base[1],base[2],profiles);validate(False,"sticky-profile");invalid+=1
 durations=[-1.0,1.0,2.0];stage(base[0],durations,base[2],base[3]);validate(False,"sticky-duration");invalid+=1
 for point_index in range(len(base[0])):
  for component_index in range(3):
   points=[list(v) for v in base[0]];points[point_index][component_index]=math.nan;stage(points,base[1],base[2],base[3]);reflected=get(obj,INPUTS[0])
   if finite_vector(reflected[point_index]):sanitized+=1
   else:validate(False,f"point-{point_index}-{component_index}");invalid+=1
 emit("VALID_CASES",valid);emit("INVALID_CASES",invalid);emit("REFLECTION_SANITIZED_VECTOR_CASES",sanitized);emit("MAX_WAYPOINTS_PROVED",512);emit("COMPLETE","PASS")
finally:
 for name,value in saved.items():set_(obj,name,value)
 emit("STATE_RESTORED",True)
