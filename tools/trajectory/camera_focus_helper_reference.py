"""Deterministic reference for camera focus authoring helpers.

Interactive traces are normalized into fixed markers before this boundary.
Actor tracking and autofocus are compiled onto the accepted absolute-time
schedule, so playback and scrubbing never depend on query history.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil, exp, isfinite, sqrt
from typing import Sequence


class CameraFocusHelperError(ValueError):
    pass


MODES_V1=("manual_distance","fixed_world","rack_fixed","track_prebaked","smoothed_autofocus")
DOMAINS_V1=("linear","reciprocal")
MINIMUM_DISTANCE_CM_V1=1.0
MAXIMUM_SAMPLES_V1=65536


@dataclass(frozen=True)
class FocusMarkerStateV1:
    valid: bool=False
    position: tuple[float,float,float]=(0.0,0.0,0.0)
    revision: int=0


@dataclass(frozen=True)
class FocusDistanceSamplesV1:
    mode: str
    domain: str
    times_seconds: tuple[float,...]
    distances_cm: tuple[float,...]


@dataclass(frozen=True)
class FocusChannelPublicationV1:
    channel_id: str
    domain: str
    key_times_seconds: tuple[float,...]
    key_values_cm: tuple[float,...]
    interpolation_modes: tuple[str,...]


def _number(value, field):
    if isinstance(value,bool):raise CameraFocusHelperError(f"invalid_{field}")
    try:result=float(value)
    except (TypeError,ValueError,OverflowError) as error:raise CameraFocusHelperError(f"invalid_{field}") from error
    if not isfinite(result):raise CameraFocusHelperError(f"invalid_{field}")
    return result


def _point(value, field):
    if not isinstance(value,(tuple,list)) or len(value)!=3:raise CameraFocusHelperError(f"invalid_{field}")
    return tuple(_number(item,field) for item in value)


def _distance(left,right):
    value=sqrt(sum((a-b)**2 for a,b in zip(left,right)))
    if value<MINIMUM_DISTANCE_CM_V1:raise CameraFocusHelperError("focus_target_too_close")
    return value


def set_focus_here_v1(state:FocusMarkerStateV1,hit_valid:bool,hit_position:Sequence[float]):
    """Commit one trace hit atomically; a miss preserves the prior marker."""
    if not isinstance(state,FocusMarkerStateV1) or isinstance(state.revision,bool) or state.revision<0:raise CameraFocusHelperError("invalid_marker_state")
    if state.valid:_point(state.position,"marker_position")
    if not isinstance(hit_valid,bool):raise CameraFocusHelperError("invalid_trace_validity")
    if not hit_valid:return state,False
    point=_point(hit_position,"trace_position")
    return FocusMarkerStateV1(True,point,state.revision+1),True


def _validate_schedule(times,fixed_step):
    step=_number(fixed_step,"fixed_step")
    if step<=0.0:raise CameraFocusHelperError("invalid_fixed_step")
    values=tuple(_number(value,"time") for value in times)
    if not 2<=len(values)<=MAXIMUM_SAMPLES_V1:raise CameraFocusHelperError("invalid_sample_count")
    if values[0]!=0.0 or any(right<=left for left,right in zip(values,values[1:])):raise CameraFocusHelperError("invalid_time_order")
    total=values[-1];expected=ceil(total/step)+1
    if len(values)!=expected:raise CameraFocusHelperError("invalid_schedule_shape")
    for index,value in enumerate(values):
        wanted=min(index*step,total)
        if abs(value-wanted)>1e-9*max(1.0,abs(value),abs(wanted)):raise CameraFocusHelperError("invalid_absolute_schedule")
    return values,step


def _rack(left,right,weight,domain):
    if domain=="linear":return left+(right-left)*weight
    return 1.0/((1.0-weight)/left+weight/right)


def compile_focus_distance_samples_v1(
    mode:str,domain:str,times_seconds:Sequence[float],fixed_step_seconds:float,
    camera_positions:Sequence[Sequence[float]],*,manual_distances_cm:Sequence[float]=(),
    target_positions:Sequence[Sequence[float]]=(),rack_target_a=(0.0,0.0,0.0),
    rack_target_b=(0.0,0.0,0.0),rack_blend_weights:Sequence[float]=(),
    smoothing_response_seconds:float=0.0,
):
    if mode not in MODES_V1:raise CameraFocusHelperError("unsupported_focus_mode")
    if domain not in DOMAINS_V1:raise CameraFocusHelperError("unsupported_focus_domain")
    if mode!="manual_distance" and len(manual_distances_cm):raise CameraFocusHelperError("ambiguous_manual_authorship")
    if mode not in ("fixed_world","track_prebaked","smoothed_autofocus") and len(target_positions):raise CameraFocusHelperError("ambiguous_target_authorship")
    if mode!="rack_fixed" and len(rack_blend_weights):raise CameraFocusHelperError("ambiguous_rack_authorship")
    if mode!="smoothed_autofocus" and _number(smoothing_response_seconds,"smoothing_response")!=0.0:raise CameraFocusHelperError("ambiguous_smoothing_policy")
    times,step=_validate_schedule(times_seconds,fixed_step_seconds);count=len(times)
    cameras=tuple(_point(value,"camera_position") for value in camera_positions)
    if len(cameras)!=count:raise CameraFocusHelperError("camera_position_shape")
    if mode=="manual_distance":
        distances=tuple(_number(value,"manual_distance") for value in manual_distances_cm)
        if len(distances)!=count:raise CameraFocusHelperError("manual_distance_shape")
    elif mode=="fixed_world":
        targets=tuple(_point(value,"target_position") for value in target_positions)
        if len(targets)!=1:raise CameraFocusHelperError("fixed_target_shape")
        distances=tuple(_distance(camera,targets[0]) for camera in cameras)
    elif mode=="rack_fixed":
        target_a=_point(rack_target_a,"rack_target_a");target_b=_point(rack_target_b,"rack_target_b")
        weights=tuple(_number(value,"rack_weight") for value in rack_blend_weights)
        if len(weights)!=count or any(value<0.0 or value>1.0 for value in weights):raise CameraFocusHelperError("rack_weight_shape_or_range")
        distances=tuple(_rack(_distance(camera,target_a),_distance(camera,target_b),weight,domain) for camera,weight in zip(cameras,weights))
    else:
        targets=tuple(_point(value,"target_position") for value in target_positions)
        if len(targets)!=count:raise CameraFocusHelperError("tracked_target_shape")
        raw=tuple(_distance(camera,target) for camera,target in zip(cameras,targets))
        if mode=="track_prebaked":distances=raw
        else:
            response=_number(smoothing_response_seconds,"smoothing_response")
            if response<=0.0:raise CameraFocusHelperError("invalid_smoothing_response")
            built=[raw[0]]
            for index in range(1,count):
                alpha=1.0-exp(-(times[index]-times[index-1])/response)
                built.append(built[-1]+(raw[index]-built[-1])*alpha)
            distances=tuple(built)
    if any(not isfinite(value) or value<MINIMUM_DISTANCE_CM_V1 for value in distances):raise CameraFocusHelperError("invalid_compiled_distance")
    return FocusDistanceSamplesV1(mode,domain,times,tuple(distances))


def commit_focus_distance_channel_v1(samples:FocusDistanceSamplesV1):
    if not isinstance(samples,FocusDistanceSamplesV1):raise CameraFocusHelperError("invalid_focus_samples")
    if len(samples.times_seconds)!=len(samples.distances_cm) or len(samples.times_seconds)<2:raise CameraFocusHelperError("invalid_focus_sample_shape")
    if samples.mode not in MODES_V1 or samples.domain not in DOMAINS_V1:raise CameraFocusHelperError("invalid_focus_sample_identity")
    times=tuple(_number(value,"compiled_time") for value in samples.times_seconds);distances=tuple(_number(value,"compiled_distance") for value in samples.distances_cm)
    if times[0]!=0.0 or any(right<=left for left,right in zip(times,times[1:])):raise CameraFocusHelperError("invalid_compiled_time_order")
    if any(value<MINIMUM_DISTANCE_CM_V1 for value in distances):raise CameraFocusHelperError("invalid_compiled_distance")
    return FocusChannelPublicationV1("focus_distance_cm",samples.domain,times,distances,("linear",)*(len(times)-1))
