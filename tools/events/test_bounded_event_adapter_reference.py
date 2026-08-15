from __future__ import annotations

from dataclasses import replace
import math
import unittest

from bounded_event_adapter_reference import (
    DEFAULT_CAPABILITIES_V1,
    FORWARD,
    LOCAL_CINEMATIC,
    REVERSE,
    SERVER_WORLD,
    SYNCHRONIZED,
    VIEWER_INTERACTION,
    BoundedEventAdapterError,
    CompiledCueV1,
    EventExecutionContextV1,
    EventExecutionLedgerV1,
    TargetBindingV1,
    commit_cue_execution_v1,
    compile_cue_plan_v1,
    plan_cue_crossings_v1,
    reset_manual_cue_v1,
)


def binding(*, enabled=True, rebound=True, region="exiled-lands"):
    return TargetBindingV1("door-main", region, "door", 1, enabled, rebound)


def cue(event_id, time, *, operation="subtitle", scope=LOCAL_CINEMATIC,
        direction="both", repeat="every_loop", target=None, payload="hello"):
    adapter = "local.presentation" if scope == LOCAL_CINEMATIC else "door"
    return CompiledCueV1(
        event_id, time, adapter, 1, operation, scope, payload,
        direction, repeat, "continue", target,
    )


def context(**changes):
    values = dict(
        flypath_id="flypath-7", immutable_revision=4, requested_revision=4,
        session_id="session-9", session_token="token-11", requester_id="player-a",
        playback_started=True, scrubbing=False, previous_time=0.0, current_time=10.0,
        loop_iteration=0, direction=FORWARD, region_id="exiled-lands",
        resolved_binding_ids=("door-main",), target_distances=(("door-main", 100.0),),
        granted_permissions=("door.observe", "door.interact", "door.lease.admin"),
        remaining_rate_budget=8, server_world_events_enabled=False,
        server_world_revision_approved=False,
    )
    values.update(changes)
    return EventExecutionContextV1(**values)


class BoundedEventAdapterContracts(unittest.TestCase):
    def test_compile_is_deterministic_and_rejects_manifest_or_plan_tampering(self):
        source = (cue("z", 2.0), cue("a", 1.0), cue("b", 2.0))
        self.assertEqual(
            [item.event_id for item in compile_cue_plan_v1(source, 3.0)],
            ["a", "b", "z"],
        )
        failures = (
            ((cue("a", 1.0), cue("a", 2.0)), "duplicate_event_id"),
            ((cue("x", math.nan),), "event_time_invalid"),
            ((cue("x", 4.0),), "event_time_out_of_range"),
            ((replace(cue("x", 1.0), operation_id="arbitrary_function"),), "adapter_operation_unavailable"),
            ((replace(cue("x", 1.0), scope=SERVER_WORLD),), "adapter_scope_mismatch"),
            ((replace(cue("x", 1.0), payload="x" * 241),), "payload_too_large"),
        )
        for values, code in failures:
            with self.subTest(code=code), self.assertRaises(BoundedEventAdapterError) as caught:
                compile_cue_plan_v1(values, 3.0)
            self.assertEqual(caught.exception.code, code)

    def test_frame_drop_collects_every_crossing_in_stable_forward_and_reverse_order(self):
        plan = compile_cue_plan_v1(
            (cue("z", 2.0), cue("a", 1.0), cue("b", 2.0)), 3.0
        )
        forward = plan_cue_crossings_v1(plan, context(previous_time=0.5, current_time=2.5), EventExecutionLedgerV1())
        self.assertEqual([item.cue.event_id for item in forward], ["a", "b", "z"])
        reverse = plan_cue_crossings_v1(
            plan,
            context(previous_time=2.5, current_time=0.5, direction=REVERSE),
            EventExecutionLedgerV1(),
        )
        self.assertEqual([item.cue.event_id for item in reverse], ["b", "z", "a"])
        self.assertTrue(all(item.authorized for item in (*forward, *reverse)))

    def test_scrubbing_is_exact_no_dispatch_and_does_not_require_authorization(self):
        remote = cue(
            "door", 1.0, operation="request_normal_interaction",
            scope=VIEWER_INTERACTION, target=binding(), payload="open",
        )
        ledger = EventExecutionLedgerV1()
        decisions = plan_cue_crossings_v1(
            (remote,), context(scrubbing=True, session_token="", granted_permissions=()), ledger
        )
        self.assertEqual(decisions, ())
        self.assertEqual(ledger, EventExecutionLedgerV1())

    def test_repeat_policies_and_success_only_ledger_commit_are_exact(self):
        once = cue("once", 1.0, repeat="once_per_session")
        looped = cue("looped", 2.0, repeat="every_loop")
        manual = cue("manual", 3.0, repeat="manual_reset")
        plan = compile_cue_plan_v1((once, looped, manual), 4.0)
        ledger = EventExecutionLedgerV1()
        first = plan_cue_crossings_v1(plan, context(), ledger)
        for decision in first:
            unchanged = commit_cue_execution_v1(ledger, decision, context(), "adapter_failed")
            self.assertIs(unchanged, ledger)
            ledger = commit_cue_execution_v1(ledger, decision, context(), "executed")
        self.assertEqual(len(ledger.keys), 3)
        second = plan_cue_crossings_v1(plan, context(loop_iteration=1), ledger)
        self.assertEqual([item.cue.event_id for item in second], ["looped"])
        with self.assertRaisesRegex(BoundedEventAdapterError, "manual_reset_policy_invalid"):
            reset_manual_cue_v1(ledger, "once", plan)
        with self.assertRaisesRegex(BoundedEventAdapterError, "manual_reset_policy_invalid"):
            reset_manual_cue_v1(ledger, "missing", plan)
        ledger = reset_manual_cue_v1(ledger, "manual", plan)
        third = plan_cue_crossings_v1(plan, context(loop_iteration=1), ledger)
        self.assertEqual([item.cue.event_id for item in third], ["looped", "manual"])

    def test_remote_authorization_rejects_each_dynamic_boundary(self):
        remote = cue(
            "door", 1.0, operation="request_normal_interaction",
            scope=VIEWER_INTERACTION, target=binding(), payload="open",
        )
        compile_cue_plan_v1((remote,), 2.0)
        failures = (
            (context(session_token=""), "event_session_token_missing"),
            (context(resolved_binding_ids=()), "target_unresolved"),
            (context(region_id="siptah"), "target_region_mismatch"),
            (context(target_distances=(("door-main", 251.0),)), "target_out_of_range"),
            (context(granted_permissions=("door.observe",)), "permission_denied"),
            (context(remaining_rate_budget=0), "event_rate_limited"),
        )
        for execution, code in failures:
            decision = plan_cue_crossings_v1((remote,), execution, EventExecutionLedgerV1())[0]
            with self.subTest(code=code):
                self.assertFalse(decision.authorized)
                self.assertEqual(decision.code, code)
        for target in (binding(enabled=False), binding(rebound=False)):
            changed = replace(remote, target_binding=target)
            decision = plan_cue_crossings_v1((changed,), context(), EventExecutionLedgerV1())[0]
            self.assertEqual(decision.code, "target_binding_requires_rebind")

    def test_revision_and_direction_context_fail_closed_before_dispatch(self):
        plan = compile_cue_plan_v1((cue("a", 1.0),), 2.0)
        failures = (
            (context(requested_revision=3), "immutable_revision_mismatch"),
            (context(playback_started=False), "event_session_inactive"),
            (context(direction=FORWARD, previous_time=2.0, current_time=1.0), "playback_direction_mismatch"),
        )
        for execution, code in failures:
            with self.subTest(code=code), self.assertRaises(BoundedEventAdapterError) as caught:
                plan_cue_crossings_v1(plan, execution, EventExecutionLedgerV1())
            self.assertEqual(caught.exception.code, code)

    def test_server_world_is_disabled_by_default_and_requires_revision_approval(self):
        lease = cue(
            "lease", 1.0, operation="cinematic_state_lease", scope=SERVER_WORLD,
            target=binding(), payload="open",
        )
        plan = compile_cue_plan_v1((lease,), 2.0)
        disabled = plan_cue_crossings_v1(plan, context(), EventExecutionLedgerV1())[0]
        self.assertEqual(disabled.code, "server_world_event_disabled")
        enabled = plan_cue_crossings_v1(
            plan,
            context(server_world_events_enabled=True, server_world_revision_approved=True),
            EventExecutionLedgerV1(),
        )[0]
        self.assertTrue(enabled.authorized)
        self.assertEqual(enabled.code, "authorized_remote")

    def test_manifest_is_closed_and_world_mutation_never_uses_local_scope(self):
        self.assertEqual(len(DEFAULT_CAPABILITIES_V1), 5)
        self.assertTrue(all(cap.adapter_id and cap.operation_id for cap in DEFAULT_CAPABILITIES_V1))
        self.assertFalse(any(cap.scope == LOCAL_CINEMATIC and cap.mutates_world for cap in DEFAULT_CAPABILITIES_V1))
        self.assertNotIn(SYNCHRONIZED, {cap.scope for cap in DEFAULT_CAPABILITIES_V1})


if __name__ == "__main__":
    unittest.main(verbosity=2)
