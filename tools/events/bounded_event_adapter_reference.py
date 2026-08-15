"""Deterministic Cue crossing and bounded adapter authorization reference.

This is the first event-system execution seam.  It deliberately does not expose
arbitrary Blueprint functions or actor classes.  A compiled Cue can select only
an operation from a frozen capability manifest, and every non-local operation
must retain immutable revision/session identity plus an exact target binding.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable, Sequence


LOCAL_CINEMATIC = "local_cinematic"
VIEWER_INTERACTION = "viewer_interaction"
SERVER_WORLD = "server_world"
SYNCHRONIZED = "synchronized_performance"

FORWARD = 1
REVERSE = -1

DIRECTION_POLICIES = frozenset(("forward", "reverse", "both", "reverse_undo"))
REPEAT_POLICIES = frozenset(("once_per_session", "every_loop", "manual_reset"))
FAILURE_POLICIES = frozenset(("continue", "pause_retry", "wait_state", "skip", "abort"))
SUCCESS_CODES = frozenset(("executed", "state_satisfied"))


class BoundedEventAdapterError(ValueError):
    """A Cue or execution request failed a stable typed contract."""

    def __init__(self, code: str, event_id: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.event_id = event_id


@dataclass(frozen=True)
class EventAdapterCapabilityV1:
    adapter_id: str
    adapter_version: int
    operation_id: str
    scope: str
    requires_target: bool
    mutates_world: bool
    required_permission: str
    maximum_payload_bytes: int
    maximum_range: float


@dataclass(frozen=True)
class TargetBindingV1:
    binding_id: str
    region_id: str
    adapter_id: str
    adapter_version: int
    enabled: bool
    reauthorized_after_clone: bool


@dataclass(frozen=True)
class CompiledCueV1:
    event_id: str
    time_seconds: float
    adapter_id: str
    adapter_version: int
    operation_id: str
    scope: str
    payload: str
    direction_policy: str
    repeat_policy: str
    failure_policy: str
    target_binding: TargetBindingV1 | None = None


@dataclass(frozen=True, order=True)
class EventLedgerKeyV1:
    event_id: str
    loop_iteration: int
    direction: int


@dataclass(frozen=True)
class EventExecutionLedgerV1:
    keys: tuple[EventLedgerKeyV1, ...] = ()


@dataclass(frozen=True)
class EventExecutionContextV1:
    flypath_id: str
    immutable_revision: int
    requested_revision: int
    session_id: str
    session_token: str
    requester_id: str
    playback_started: bool
    scrubbing: bool
    previous_time: float
    current_time: float
    loop_iteration: int
    direction: int
    region_id: str
    resolved_binding_ids: tuple[str, ...]
    target_distances: tuple[tuple[str, float], ...]
    granted_permissions: tuple[str, ...]
    remaining_rate_budget: int
    server_world_events_enabled: bool
    server_world_revision_approved: bool


@dataclass(frozen=True)
class EventDispatchDecisionV1:
    cue: CompiledCueV1
    capability: EventAdapterCapabilityV1 | None
    authorized: bool
    code: str


DEFAULT_CAPABILITIES_V1 = (
    EventAdapterCapabilityV1(
        "local.presentation", 1, "subtitle", LOCAL_CINEMATIC,
        False, False, "", 240, 0.0,
    ),
    EventAdapterCapabilityV1(
        "local.recording", 1, "marker", LOCAL_CINEMATIC,
        False, False, "", 96, 0.0,
    ),
    EventAdapterCapabilityV1(
        "door", 1, "wait_until_open", VIEWER_INTERACTION,
        True, False, "door.observe", 0, 5000.0,
    ),
    EventAdapterCapabilityV1(
        "door", 1, "request_normal_interaction", VIEWER_INTERACTION,
        True, True, "door.interact", 64, 250.0,
    ),
    EventAdapterCapabilityV1(
        "door", 1, "cinematic_state_lease", SERVER_WORLD,
        True, True, "door.lease.admin", 64, 250.0,
    ),
)


def _text(value: object, label: str, maximum: int = 96) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > maximum:
        raise BoundedEventAdapterError(f"{label}_invalid")
    return value


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool):
        raise BoundedEventAdapterError(f"{label}_invalid")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise BoundedEventAdapterError(f"{label}_invalid") from error
    if not isfinite(result):
        raise BoundedEventAdapterError(f"{label}_invalid")
    return result


def _capability_map(
    capabilities: Sequence[EventAdapterCapabilityV1],
) -> dict[tuple[str, int, str], EventAdapterCapabilityV1]:
    result: dict[tuple[str, int, str], EventAdapterCapabilityV1] = {}
    for capability in capabilities:
        key = (
            _text(capability.adapter_id, "adapter_id"),
            int(capability.adapter_version),
            _text(capability.operation_id, "operation_id"),
        )
        if key in result or capability.adapter_version <= 0:
            raise BoundedEventAdapterError("capability_manifest_invalid")
        if capability.scope not in (LOCAL_CINEMATIC, VIEWER_INTERACTION, SERVER_WORLD):
            raise BoundedEventAdapterError("capability_manifest_invalid")
        if capability.maximum_payload_bytes < 0 or capability.maximum_payload_bytes > 1024:
            raise BoundedEventAdapterError("capability_manifest_invalid")
        if not isfinite(capability.maximum_range) or capability.maximum_range < 0.0:
            raise BoundedEventAdapterError("capability_manifest_invalid")
        if capability.mutates_world and capability.scope == LOCAL_CINEMATIC:
            raise BoundedEventAdapterError("capability_manifest_invalid")
        result[key] = capability
    return result


def compile_cue_plan_v1(
    cues: Iterable[CompiledCueV1],
    duration_seconds: float,
    capabilities: Sequence[EventAdapterCapabilityV1] = DEFAULT_CAPABILITIES_V1,
) -> tuple[CompiledCueV1, ...]:
    """Validate and deterministically order an immutable Cue execution plan."""

    duration = _finite(duration_seconds, "duration")
    if duration <= 0.0:
        raise BoundedEventAdapterError("duration_invalid")
    manifest = _capability_map(capabilities)
    accepted: list[CompiledCueV1] = []
    event_ids: set[str] = set()
    for cue in cues:
        event_id = _text(cue.event_id, "event_id")
        if event_id in event_ids:
            raise BoundedEventAdapterError("duplicate_event_id", event_id)
        event_ids.add(event_id)
        time_seconds = _finite(cue.time_seconds, "event_time")
        if time_seconds < 0.0 or time_seconds > duration:
            raise BoundedEventAdapterError("event_time_out_of_range", event_id)
        key = (cue.adapter_id, cue.adapter_version, cue.operation_id)
        capability = manifest.get(key)
        if capability is None:
            raise BoundedEventAdapterError("adapter_operation_unavailable", event_id)
        if cue.scope != capability.scope:
            raise BoundedEventAdapterError("adapter_scope_mismatch", event_id)
        if cue.direction_policy not in DIRECTION_POLICIES:
            raise BoundedEventAdapterError("direction_policy_invalid", event_id)
        if cue.repeat_policy not in REPEAT_POLICIES:
            raise BoundedEventAdapterError("repeat_policy_invalid", event_id)
        if cue.failure_policy not in FAILURE_POLICIES:
            raise BoundedEventAdapterError("failure_policy_invalid", event_id)
        if len(cue.payload.encode("utf-8")) > capability.maximum_payload_bytes:
            raise BoundedEventAdapterError("payload_too_large", event_id)
        if capability.requires_target != (cue.target_binding is not None):
            raise BoundedEventAdapterError("target_binding_shape_invalid", event_id)
        accepted.append(cue)
    return tuple(sorted(accepted, key=lambda cue: (cue.time_seconds, cue.event_id)))


def _crossed(cue: CompiledCueV1, context: EventExecutionContextV1) -> bool:
    if context.direction == FORWARD:
        return context.previous_time < cue.time_seconds <= context.current_time
    return context.current_time <= cue.time_seconds < context.previous_time


def _direction_allowed(cue: CompiledCueV1, direction: int) -> bool:
    if cue.direction_policy == "both":
        return True
    if direction == FORWARD:
        return cue.direction_policy == "forward"
    return cue.direction_policy in ("reverse", "reverse_undo")


def _already_executed(
    cue: CompiledCueV1,
    context: EventExecutionContextV1,
    ledger: EventExecutionLedgerV1,
) -> bool:
    if cue.repeat_policy == "every_loop":
        key = EventLedgerKeyV1(cue.event_id, context.loop_iteration, context.direction)
        return key in ledger.keys
    return any(key.event_id == cue.event_id for key in ledger.keys)


def _reject(cue: CompiledCueV1, code: str) -> EventDispatchDecisionV1:
    return EventDispatchDecisionV1(cue, None, False, code)


def authorize_cue_v1(
    cue: CompiledCueV1,
    context: EventExecutionContextV1,
    capabilities: Sequence[EventAdapterCapabilityV1] = DEFAULT_CAPABILITIES_V1,
) -> EventDispatchDecisionV1:
    """Authorize one already-compiled Cue without executing an adapter."""

    manifest = _capability_map(capabilities)
    capability = manifest.get((cue.adapter_id, cue.adapter_version, cue.operation_id))
    if capability is None:
        return _reject(cue, "adapter_operation_unavailable")
    if cue.scope != capability.scope:
        return _reject(cue, "adapter_scope_mismatch")
    if len(cue.payload.encode("utf-8")) > capability.maximum_payload_bytes:
        return _reject(cue, "payload_too_large")
    if capability.scope == LOCAL_CINEMATIC:
        if cue.target_binding is not None or capability.mutates_world:
            return _reject(cue, "local_scope_not_isolated")
        return EventDispatchDecisionV1(cue, capability, True, "authorized_local")

    if not context.session_token:
        return _reject(cue, "event_session_token_missing")
    binding = cue.target_binding
    if binding is None:
        return _reject(cue, "target_binding_missing")
    if not binding.enabled or not binding.reauthorized_after_clone:
        return _reject(cue, "target_binding_requires_rebind")
    if binding.adapter_id != cue.adapter_id or binding.adapter_version != cue.adapter_version:
        return _reject(cue, "target_binding_adapter_mismatch")
    if binding.region_id != context.region_id:
        return _reject(cue, "target_region_mismatch")
    if binding.binding_id not in context.resolved_binding_ids:
        return _reject(cue, "target_unresolved")
    distances = dict(context.target_distances)
    distance = distances.get(binding.binding_id)
    if distance is None or not isfinite(distance) or distance < 0.0:
        return _reject(cue, "target_distance_invalid")
    if distance > capability.maximum_range:
        return _reject(cue, "target_out_of_range")
    if capability.required_permission not in context.granted_permissions:
        return _reject(cue, "permission_denied")
    if context.remaining_rate_budget <= 0:
        return _reject(cue, "event_rate_limited")
    if capability.scope == SERVER_WORLD and (
        not context.server_world_events_enabled
        or not context.server_world_revision_approved
    ):
        return _reject(cue, "server_world_event_disabled")
    return EventDispatchDecisionV1(cue, capability, True, "authorized_remote")


def plan_cue_crossings_v1(
    compiled_cues: Sequence[CompiledCueV1],
    context: EventExecutionContextV1,
    ledger: EventExecutionLedgerV1,
    capabilities: Sequence[EventAdapterCapabilityV1] = DEFAULT_CAPABILITIES_V1,
) -> tuple[EventDispatchDecisionV1, ...]:
    """Return every eligible crossing in stable playback order.

    Scrubbing is an exact no-dispatch path.  It never changes the ledger and
    never invokes authorization, including for shared-world operations.
    """

    if context.scrubbing:
        return ()
    if not context.playback_started:
        raise BoundedEventAdapterError("event_session_inactive")
    _text(context.flypath_id, "flypath_id")
    _text(context.session_id, "session_id")
    _text(context.requester_id, "requester_id")
    if context.immutable_revision <= 0 or context.requested_revision != context.immutable_revision:
        raise BoundedEventAdapterError("immutable_revision_mismatch")
    previous = _finite(context.previous_time, "previous_time")
    current = _finite(context.current_time, "current_time")
    if context.loop_iteration < 0 or context.direction not in (FORWARD, REVERSE):
        raise BoundedEventAdapterError("playback_context_invalid")
    if (context.direction == FORWARD and current < previous) or (
        context.direction == REVERSE and current > previous
    ):
        raise BoundedEventAdapterError("playback_direction_mismatch")

    crossed = [
        cue for cue in compiled_cues
        if _crossed(cue, context)
        and _direction_allowed(cue, context.direction)
        and not _already_executed(cue, context, ledger)
    ]
    crossed.sort(
        key=lambda cue: (
            cue.time_seconds if context.direction == FORWARD else -cue.time_seconds,
            cue.event_id,
        )
    )
    return tuple(authorize_cue_v1(cue, context, capabilities) for cue in crossed)


def commit_cue_execution_v1(
    ledger: EventExecutionLedgerV1,
    decision: EventDispatchDecisionV1,
    context: EventExecutionContextV1,
    adapter_result_code: str,
) -> EventExecutionLedgerV1:
    """Publish ledger authority only after a bounded adapter reports success."""

    if not decision.authorized or adapter_result_code not in SUCCESS_CODES:
        return ledger
    key = EventLedgerKeyV1(
        decision.cue.event_id,
        context.loop_iteration,
        context.direction,
    )
    if key in ledger.keys:
        return ledger
    return EventExecutionLedgerV1(tuple(sorted((*ledger.keys, key))))


def reset_manual_cue_v1(
    ledger: EventExecutionLedgerV1,
    event_id: str,
    compiled_cues: tuple[EventCueV1, ...],
) -> EventExecutionLedgerV1:
    """Explicitly re-arm one manual-reset Cue without affecting other entries."""

    _text(event_id, "event_id")
    matches = tuple(cue for cue in compiled_cues if cue.event_id == event_id)
    if len(matches) != 1 or matches[0].repeat_policy != "manual_reset":
        raise BoundedEventAdapterError("manual_reset_policy_invalid", event_id)
    return EventExecutionLedgerV1(tuple(key for key in ledger.keys if key.event_id != event_id))
