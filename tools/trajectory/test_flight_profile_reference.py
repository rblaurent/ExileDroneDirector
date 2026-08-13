"""Executable contracts for deterministic flight-profile compilation."""

from __future__ import annotations

from dataclasses import replace
import math
import random
import unittest

from flight_profile_reference import (
    PROFILE_ORDER,
    PROFILES,
    CompiledFlightProfiles,
    FlightProfileError,
    compile_flight_profiles,
    corrupt_parameter,
    evaluate_flight_profile,
)


class FlightProfileContracts(unittest.TestCase):
    def test_all_planned_presets_are_exact_distinct_and_bounded(self):
        self.assertEqual(
            PROFILE_ORDER,
            ("cinematic_drone", "hybrid", "fpv_cinewhoop", "fpv_freestyle", "fpv_long_range"),
        )
        self.assertEqual(tuple(PROFILES), PROFILE_ORDER)
        self.assertEqual(len(set(PROFILES.values())), len(PROFILE_ORDER))
        compiled = compile_flight_profiles("cinematic_drone", PROFILE_ORDER, len(PROFILE_ORDER))
        for index, profile_id in enumerate(PROFILE_ORDER):
            self.assertEqual(evaluate_flight_profile(compiled, index).profile, PROFILES[profile_id])

    def test_empty_override_inherits_default_without_aliasing_authored_input(self):
        overrides = ["", "hybrid", ""]
        compiled = compile_flight_profiles("fpv_long_range", overrides, 3)
        overrides[:] = ["fpv_freestyle"] * 3
        self.assertEqual(
            tuple(profile.profile_id for profile in compiled.profiles),
            ("fpv_long_range", "hybrid", "fpv_long_range"),
        )

    def test_compile_is_deterministic_at_the_511_segment_ceiling(self):
        rng = random.Random(0xEDD090)
        overrides = tuple("" if rng.random() < 0.35 else rng.choice(PROFILE_ORDER) for _ in range(511))
        first = compile_flight_profiles("cinematic_drone", overrides, 511)
        self.assertEqual(first, compile_flight_profiles("cinematic_drone", overrides, 511))
        queries = list(range(511))
        rng.shuffle(queries)
        self.assertEqual(
            {index: evaluate_flight_profile(first, index) for index in queries},
            {index: evaluate_flight_profile(first, index) for index in reversed(queries)},
        )

    def test_every_authored_identifier_is_validated_even_when_not_selected(self):
        bad = ("unknown", " cinematic_drone", "hybrid ", "Cinematic_Drone", None, 3)
        for value in bad:
            with self.subTest(value=value), self.assertRaises(FlightProfileError):
                compile_flight_profiles("cinematic_drone", ("", value), 2)  # type: ignore[arg-type]
        for value in bad:
            with self.subTest(default=value), self.assertRaises(FlightProfileError):
                compile_flight_profiles(value, ("",), 1)  # type: ignore[arg-type]

    def test_invalid_authored_shapes_fail_before_publication(self):
        cases = (
            ("cinematic_drone", (), 1),
            ("cinematic_drone", ("",), 0),
            ("cinematic_drone", ("",) * 512, 512),
            ("cinematic_drone", ("",), True),
            ("cinematic_drone", ("",), 1.0),
        )
        for default_id, overrides, count in cases:
            with self.subTest(count=count), self.assertRaises(FlightProfileError):
                compile_flight_profiles(default_id, overrides, count)  # type: ignore[arg-type]

    def test_corrupt_compiled_cardinality_identity_and_parameters_fail_closed(self):
        valid = compile_flight_profiles("hybrid", ("", "fpv_freestyle"), 2)
        corruptions = [
            replace(valid, segment_count=0),
            replace(valid, segment_count=3),
            replace(valid, profiles=valid.profiles[:-1]),
            replace(valid, profiles=(replace(valid.profiles[0], profile_id="unknown"), valid.profiles[1])),
        ]
        fields = (
            "path_follow_weight",
            "horizon_stabilization_weight",
            "look_ahead_seconds",
            "bank_gain",
            "max_bank_degrees",
            "camera_uptilt_degrees",
            "max_angular_rate_degrees_per_second",
            "max_acceleration_cm_per_second_squared",
            "max_jerk_cm_per_second_cubed",
            "minimum_turn_radius_cm",
        )
        for field in fields:
            corruptions.append(replace(valid, profiles=(corrupt_parameter(valid.profiles[0], field, math.nan), valid.profiles[1])))
            corruptions.append(replace(valid, profiles=(corrupt_parameter(valid.profiles[0], field, 123.456), valid.profiles[1])))
        for compiled in corruptions:
            with self.subTest(compiled=compiled), self.assertRaises(FlightProfileError):
                evaluate_flight_profile(compiled, 0)

    def test_bad_indices_and_types_fail_without_fallback(self):
        compiled = compile_flight_profiles("cinematic_drone", ("",), 1)
        for index in (-1, 1, 2, True, 0.0, math.nan):
            with self.subTest(index=index), self.assertRaises(FlightProfileError):
                evaluate_flight_profile(compiled, index)  # type: ignore[arg-type]

    def test_seeded_mixed_tracks_resolve_exactly(self):
        rng = random.Random(0xEDD091)
        for _case in range(200):
            count = rng.randint(1, 64)
            default_id = rng.choice(PROFILE_ORDER)
            overrides = tuple("" if rng.random() < 0.5 else rng.choice(PROFILE_ORDER) for _ in range(count))
            compiled = compile_flight_profiles(default_id, overrides, count)
            expected = tuple(PROFILES[value or default_id] for value in overrides)
            self.assertEqual(compiled.profiles, expected)
            for index in range(count):
                self.assertEqual(evaluate_flight_profile(compiled, index).profile, expected[index])


if __name__ == "__main__":
    unittest.main(verbosity=2)
