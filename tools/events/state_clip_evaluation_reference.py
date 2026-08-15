"""Deterministic absolute-time State Clip evaluation reference.

This is the second event-system execution seam.  It compiles only a safe local
test adapter so absolute-time interval semantics and explicit scrub preview can
be proven before target resolution, Event Anchors, door adapters, RPCs, or any
shared-world mutation exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable


LOCAL_CINEMATIC = "local_cinematic"
LOCAL_TEST_ADAPTER = "local.state_test"
LOCAL_TEST_VERSION = 1
LOCAL_CHANNEL = "local_channel"

RESTORE_POLICIES = frozenset(("none", "restore_captured", "adapter_default"))
CONFLICT_POLICIES = frozenset(("yield", "pause", "abort"))
FAILURE_POLICIES = frozenset(("continue", "pause_retry", "wait_state", "skip", "abort"))
PREVIEW_POLICIES = frozenset(("disabled", "local_explicit"))
LOCAL_TEST_STATES = frozenset(("off", "on", "accent"))

MAXIMUM_CLIPS = 128
MAXIMUM_ACTIVE_CLIPS = 32
MAXIMUM_LEAD_SECONDS = 30.0
MAXIMUM_TIMEOUT_SECONDS = 30.0


class StateClipEvaluationError(ValueError):
    """A State Clip plan or query failed a stable typed contract."""

    def __init__(self, code: str, clip_id: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.clip_id = clip_id


@dataclass(frozen=True)
class StateClipBindingV1:
    binding_id: str
    binding_type: str
    region_id: str
    adapter_id: str
    adapter_version: int
    enabled: bool
    reauthorized_after_clone: bool


@dataclass(frozen=True)
class StateClipV1:
    clip_id: str
    start_time: float
    end_time: float
    desired_state: str
    enter_lead_seconds: float
    exit_lead_seconds: float
    scope: str
    restore_policy: str
    conflict_policy: str
    failure_policy: str
    timeout_seconds: float
    preview_policy: str
    target_binding: StateClipBindingV1


@dataclass(frozen=True)
class CompiledStateClipPlanV1:
    duration_seconds: float
    clips: tuple[StateClipV1, ...]


@dataclass(frozen=True)
class StateClipQueryV1:
    absolute_time: float
    scrubbing: bool
    local_preview_requested: bool


@dataclass(frozen=True)
class StateClipEvaluationV1:
    clip_id: str
    binding_id: str
    adapter_id: str
    adapter_version: int
    desired_state: str
    scope: str
    restore_policy: str
    preview_allowed: bool
    code: str


def _text(value: object, label: str, maximum: int = 96, *, empty: bool = False) -> str:
    if not isinstance(value, str):
        raise StateClipEvaluationError(f"{label}_invalid")
    size = len(value.encode("utf-8"))
    if (not empty and size == 0) or size > maximum:
        raise StateClipEvaluationError(f"{label}_invalid")
    return value


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool):
        raise StateClipEvaluationError(f"{label}_invalid")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise StateClipEvaluationError(f"{label}_invalid") from error
    if not isfinite(result):
        raise StateClipEvaluationError(f"{label}_invalid")
    return result


def _validate_binding(binding: StateClipBindingV1, clip_id: str) -> None:
    _text(binding.binding_id, "state_clip_binding_id")
    if binding.binding_type != LOCAL_CHANNEL:
        raise StateClipEvaluationError("state_clip_binding_type_unsupported", clip_id)
    if binding.region_id != "":
        raise StateClipEvaluationError("local_state_clip_region_not_empty", clip_id)
    if binding.adapter_id != LOCAL_TEST_ADAPTER or binding.adapter_version != LOCAL_TEST_VERSION:
        raise StateClipEvaluationError("state_clip_adapter_unavailable", clip_id)
    if not binding.enabled or not binding.reauthorized_after_clone:
        raise StateClipEvaluationError("local_state_clip_binding_disabled", clip_id)


def compile_state_clip_plan_v1(
    clips: Iterable[StateClipV1], duration_seconds: float
) -> CompiledStateClipPlanV1:
    """Validate and sort a value snapshot of local-test State Clips.

    Active intervals are exactly half-open: ``start <= t < end``.  Lead values
    are preserved scheduling metadata; they never expand the active interval.
    Adjacent clips on one binding are valid, while any active overlap is
    rejected before plan authority can publish.
    """

    duration = _finite(duration_seconds, "state_clip_duration")
    if duration < 0.0:
        raise StateClipEvaluationError("state_clip_duration_invalid")
    source = tuple(clips)
    if len(source) > MAXIMUM_CLIPS:
        raise StateClipEvaluationError("state_clip_count_exceeded")

    accepted: list[StateClipV1] = []
    ids: set[str] = set()
    for clip in source:
        clip_id = _text(clip.clip_id, "state_clip_id")
        if clip_id in ids:
            raise StateClipEvaluationError("duplicate_state_clip_id", clip_id)
        ids.add(clip_id)
        start = _finite(clip.start_time, "state_clip_start")
        end = _finite(clip.end_time, "state_clip_end")
        if start < 0.0 or end <= start or end > duration:
            raise StateClipEvaluationError("state_clip_range_invalid", clip_id)
        enter = _finite(clip.enter_lead_seconds, "state_clip_enter_lead")
        exit_ = _finite(clip.exit_lead_seconds, "state_clip_exit_lead")
        if (
            enter < 0.0
            or enter > MAXIMUM_LEAD_SECONDS
            or enter > start
            or exit_ < 0.0
            or exit_ > MAXIMUM_LEAD_SECONDS
            or exit_ > end - start
        ):
            raise StateClipEvaluationError("state_clip_lead_invalid", clip_id)
        if clip.scope != LOCAL_CINEMATIC:
            raise StateClipEvaluationError("state_clip_scope_unsupported", clip_id)
        if clip.desired_state not in LOCAL_TEST_STATES:
            raise StateClipEvaluationError("state_clip_desired_state_invalid", clip_id)
        if clip.restore_policy not in RESTORE_POLICIES:
            raise StateClipEvaluationError("state_clip_restore_policy_invalid", clip_id)
        if clip.conflict_policy not in CONFLICT_POLICIES:
            raise StateClipEvaluationError("state_clip_conflict_policy_invalid", clip_id)
        if clip.failure_policy not in FAILURE_POLICIES:
            raise StateClipEvaluationError("state_clip_failure_policy_invalid", clip_id)
        timeout = _finite(clip.timeout_seconds, "state_clip_timeout")
        if timeout < 0.0 or timeout > MAXIMUM_TIMEOUT_SECONDS:
            raise StateClipEvaluationError("state_clip_timeout_invalid", clip_id)
        if clip.preview_policy not in PREVIEW_POLICIES:
            raise StateClipEvaluationError("state_clip_preview_policy_invalid", clip_id)
        _validate_binding(clip.target_binding, clip_id)
        accepted.append(clip)

    ordered = tuple(
        sorted(
            accepted,
            key=lambda clip: (
                clip.start_time,
                clip.target_binding.binding_id,
                clip.clip_id,
            ),
        )
    )
    by_binding: dict[tuple[str, str, int], list[StateClipV1]] = {}
    for clip in ordered:
        binding = clip.target_binding
        by_binding.setdefault(
            (binding.binding_id, binding.adapter_id, binding.adapter_version), []
        ).append(clip)
    for clips_for_binding in by_binding.values():
        previous_end = -1.0
        for clip in sorted(clips_for_binding, key=lambda value: (value.start_time, value.clip_id)):
            if clip.start_time < previous_end:
                raise StateClipEvaluationError("state_clip_target_overlap", clip.clip_id)
            previous_end = clip.end_time
    return CompiledStateClipPlanV1(duration, ordered)


def evaluate_state_clips_at_time_v1(
    plan: CompiledStateClipPlanV1, query: StateClipQueryV1
) -> tuple[StateClipEvaluationV1, ...]:
    """Evaluate the complete active local-test state as a history-free query."""

    time = _finite(query.absolute_time, "state_clip_query_time")
    if type(query.scrubbing) is not bool or type(query.local_preview_requested) is not bool:
        raise StateClipEvaluationError("state_clip_query_flags_invalid")
    active = tuple(clip for clip in plan.clips if clip.start_time <= time < clip.end_time)
    if len(active) > MAXIMUM_ACTIVE_CLIPS:
        raise StateClipEvaluationError("state_clip_active_count_exceeded")
    result = []
    for clip in active:
        preview = (
            query.scrubbing
            and query.local_preview_requested
            and clip.preview_policy == "local_explicit"
        )
        if preview:
            code = "local_state_preview_allowed"
        elif query.scrubbing:
            code = "state_predicted_scrub_only"
        else:
            code = "state_predicted_playback"
        binding = clip.target_binding
        result.append(
            StateClipEvaluationV1(
                clip.clip_id,
                binding.binding_id,
                binding.adapter_id,
                binding.adapter_version,
                clip.desired_state,
                clip.scope,
                clip.restore_policy,
                preview,
                code,
            )
        )
    return tuple(result)
