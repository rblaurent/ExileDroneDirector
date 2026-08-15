from __future__ import annotations

from dataclasses import replace
import math
import random
import unittest

from state_clip_evaluation_reference import (
    LOCAL_CHANNEL,
    LOCAL_CINEMATIC,
    LOCAL_TEST_ADAPTER,
    CompiledStateClipPlanV1,
    StateClipBindingV1,
    StateClipEvaluationError,
    StateClipQueryV1,
    StateClipV1,
    compile_state_clip_plan_v1,
    evaluate_state_clips_at_time_v1,
)


def binding(name="channel-a", **changes):
    values = dict(
        binding_id=name,
        binding_type=LOCAL_CHANNEL,
        region_id="",
        adapter_id=LOCAL_TEST_ADAPTER,
        adapter_version=1,
        enabled=True,
        reauthorized_after_clone=True,
    )
    values.update(changes)
    return StateClipBindingV1(**values)


def clip(clip_id, start, end, *, target="channel-a", state="on", preview="local_explicit", **changes):
    values = dict(
        clip_id=clip_id,
        start_time=start,
        end_time=end,
        desired_state=state,
        enter_lead_seconds=min(0.25, start),
        exit_lead_seconds=min(0.25, end - start),
        scope=LOCAL_CINEMATIC,
        restore_policy="restore_captured",
        conflict_policy="yield",
        failure_policy="continue",
        timeout_seconds=2.0,
        preview_policy=preview,
        target_binding=binding(target),
    )
    values.update(changes)
    return StateClipV1(**values)


class StateClipEvaluationContracts(unittest.TestCase):
    def test_compile_is_deterministic_sorted_and_immutable(self):
        source = [clip("z", 2.0, 3.0, target="b"), clip("a", 1.0, 2.0)]
        plan = compile_state_clip_plan_v1(source, 4.0)
        self.assertEqual([value.clip_id for value in plan.clips], ["a", "z"])
        source.reverse()
        self.assertEqual([value.clip_id for value in plan.clips], ["a", "z"])
        self.assertEqual(plan, compile_state_clip_plan_v1(tuple(reversed(source)), 4.0))

    def test_empty_zero_duration_plan_is_valid_and_history_free(self):
        plan = compile_state_clip_plan_v1((), 0.0)
        self.assertEqual(plan, CompiledStateClipPlanV1(0.0, ()))
        for time in (-100.0, 0.0, 100.0):
            self.assertEqual(evaluate_state_clips_at_time_v1(plan, StateClipQueryV1(time, True, True)), ())

    def test_half_open_boundaries_and_adjacent_state_replacement_are_exact(self):
        plan = compile_state_clip_plan_v1(
            (clip("first", 1.0, 2.0, state="on"), clip("second", 2.0, 3.0, state="off")),
            3.0,
        )
        self.assertEqual(evaluate_state_clips_at_time_v1(plan, StateClipQueryV1(0.999, False, False)), ())
        self.assertEqual([x.clip_id for x in evaluate_state_clips_at_time_v1(plan, StateClipQueryV1(1.0, False, False))], ["first"])
        self.assertEqual([x.clip_id for x in evaluate_state_clips_at_time_v1(plan, StateClipQueryV1(2.0, False, False))], ["second"])
        self.assertEqual(evaluate_state_clips_at_time_v1(plan, StateClipQueryV1(3.0, False, False)), ())

    def test_simultaneous_distinct_targets_are_stable(self):
        plan = compile_state_clip_plan_v1(
            (clip("b", 1.0, 3.0, target="channel-b"), clip("a", 1.0, 3.0, target="channel-a")),
            4.0,
        )
        result = evaluate_state_clips_at_time_v1(plan, StateClipQueryV1(2.0, False, False))
        self.assertEqual([value.clip_id for value in result], ["a", "b"])
        self.assertEqual([value.binding_id for value in result], ["channel-a", "channel-b"])

    def test_scrub_preview_is_explicit_local_and_non_authoritative(self):
        plan = compile_state_clip_plan_v1((clip("a", 1.0, 3.0),), 4.0)
        cases = (
            (StateClipQueryV1(2.0, True, True), True, "local_state_preview_allowed"),
            (StateClipQueryV1(2.0, True, False), False, "state_predicted_scrub_only"),
            (StateClipQueryV1(2.0, False, True), False, "state_predicted_playback"),
        )
        for query, allowed, code in cases:
            with self.subTest(query=query):
                result = evaluate_state_clips_at_time_v1(plan, query)[0]
                self.assertEqual(result.preview_allowed, allowed)
                self.assertEqual(result.code, code)
                self.assertEqual(result.desired_state, "on")

    def test_same_target_overlap_is_rejected_but_distinct_targets_may_overlap(self):
        with self.assertRaises(StateClipEvaluationError) as caught:
            compile_state_clip_plan_v1((clip("a", 1.0, 3.0), clip("b", 2.0, 4.0)), 5.0)
        self.assertEqual(caught.exception.code, "state_clip_target_overlap")
        plan = compile_state_clip_plan_v1(
            (clip("a", 1.0, 3.0), clip("b", 2.0, 4.0, target="channel-b")), 5.0
        )
        self.assertEqual(len(evaluate_state_clips_at_time_v1(plan, StateClipQueryV1(2.5, False, False))), 2)

    def test_compile_rejects_every_unsafe_or_ambiguous_family(self):
        base = clip("a", 1.0, 2.0)
        failures = (
            ((base,), -1.0, "state_clip_duration_invalid"),
            ((replace(base, clip_id=""),), 3.0, "state_clip_id_invalid"),
            ((base, replace(base, start_time=2.0)), 3.0, "duplicate_state_clip_id"),
            ((replace(base, start_time=math.nan),), 3.0, "state_clip_start_invalid"),
            ((replace(base, end_time=1.0),), 3.0, "state_clip_range_invalid"),
            ((replace(base, enter_lead_seconds=1.1),), 3.0, "state_clip_lead_invalid"),
            ((replace(base, scope="server_world"),), 3.0, "state_clip_scope_unsupported"),
            ((replace(base, desired_state="arbitrary"),), 3.0, "state_clip_desired_state_invalid"),
            ((replace(base, restore_policy="force"),), 3.0, "state_clip_restore_policy_invalid"),
            ((replace(base, conflict_policy="admin_override"),), 3.0, "state_clip_conflict_policy_invalid"),
            ((replace(base, failure_policy="prompt"),), 3.0, "state_clip_failure_policy_invalid"),
            ((replace(base, timeout_seconds=31.0),), 3.0, "state_clip_timeout_invalid"),
            ((replace(base, preview_policy="always"),), 3.0, "state_clip_preview_policy_invalid"),
            ((replace(base, target_binding=binding(binding_type="query")),), 3.0, "state_clip_binding_type_unsupported"),
            ((replace(base, target_binding=binding(adapter_id="door")),), 3.0, "state_clip_adapter_unavailable"),
            ((replace(base, target_binding=binding(enabled=False)),), 3.0, "local_state_clip_binding_disabled"),
        )
        for values, duration, code in failures:
            with self.subTest(code=code), self.assertRaises(StateClipEvaluationError) as caught:
                compile_state_clip_plan_v1(values, duration)
            self.assertEqual(caught.exception.code, code)

    def test_nonfinite_queries_and_nonboolean_flags_fail_closed(self):
        plan = compile_state_clip_plan_v1((clip("a", 1.0, 2.0),), 3.0)
        for query, code in (
            (StateClipQueryV1(math.nan, True, True), "state_clip_query_time_invalid"),
            (StateClipQueryV1(1.5, 1, True), "state_clip_query_flags_invalid"),
        ):
            with self.subTest(code=code), self.assertRaises(StateClipEvaluationError) as caught:
                evaluate_state_clips_at_time_v1(plan, query)
            self.assertEqual(caught.exception.code, code)

    def test_seeded_forward_reverse_query_order_has_no_history(self):
        for seed in range(40):
            rng = random.Random(seed)
            values = []
            for index in range(rng.randint(1, 12)):
                start = rng.uniform(0.0, 8.0)
                end = min(10.0, start + rng.uniform(0.1, 1.5))
                values.append(clip(f"clip-{index}", start, end, target=f"channel-{index}", state=rng.choice(("off", "on", "accent"))))
            plan = compile_state_clip_plan_v1(values, 10.0)
            times = [rng.uniform(-1.0, 11.0) for _ in range(20)]
            forward = {time: evaluate_state_clips_at_time_v1(plan, StateClipQueryV1(time, True, True)) for time in times}
            reverse = {time: evaluate_state_clips_at_time_v1(plan, StateClipQueryV1(time, True, True)) for time in reversed(times)}
            self.assertEqual(forward, reverse)


if __name__ == "__main__":
    unittest.main(verbosity=2)
