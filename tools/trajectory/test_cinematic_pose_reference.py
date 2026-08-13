"""Executable contracts for atomic position/orientation pose composition."""

from __future__ import annotations

from dataclasses import replace
import math
import random
import unittest

from cinematic_pose_reference import (
    CinematicPoseError,
    CompiledCinematicPose,
    compile_cinematic_pose,
    evaluate_cinematic_pose,
)
from cinematic_reference import AuthoredSegment, evaluate_position
from orientation_reference import evaluate_orientation, normalize


IDENTITY = (0.0, 0.0, 0.0, 1.0)


def random_quaternion(rng: random.Random):
    while True:
        value = tuple(rng.uniform(-1.0, 1.0) for _ in range(4))
        try:
            return normalize(value)
        except ValueError:
            pass


class CinematicPoseContracts(unittest.TestCase):
    def setUp(self):
        self.points = ((0.0, 0.0, 0.0), (100.0, 20.0, 10.0), (250.0, -30.0, 80.0))
        self.rotations = (IDENTITY, normalize((0.0, 0.25, 0.1, 0.95)), normalize((0.2, 0.1, 0.5, 0.8)))
        self.segments = (
            AuthoredSegment(0.75, "auto_cinematic", "smoothstep"),
            AuthoredSegment(3.25, "linear", "brake_into"),
        )
        self.compiled = compile_cinematic_pose(self.points, self.rotations, self.segments)

    def test_compile_publishes_one_exact_shared_timeline(self):
        self.assertEqual(self.compiled.total_seconds, 4.0)
        self.assertEqual(
            [(s.start_seconds, s.duration_seconds) for s in self.compiled.position.segments],
            [(s.start_seconds, s.duration_seconds) for s in self.compiled.orientation.segments],
        )

    def test_compile_is_deterministic_and_rejects_authored_shape_mismatch(self):
        self.assertEqual(self.compiled, compile_cinematic_pose(self.points, self.rotations, self.segments))
        with self.assertRaises(CinematicPoseError):
            compile_cinematic_pose(self.points, self.rotations[:-1], self.segments)
        with self.assertRaises(CinematicPoseError):
            compile_cinematic_pose(self.points, self.rotations, self.segments[:-1])

    def test_evaluation_is_atomic_and_matches_both_accepted_components(self):
        for elapsed in (-10.0, 0.0, 0.25, 0.75, 1.5, 3.999, 4.0, 50.0):
            pose = evaluate_cinematic_pose(self.compiled, elapsed)
            position = evaluate_position(self.compiled.position, elapsed)
            orientation = evaluate_orientation(self.compiled.orientation, elapsed)
            self.assertEqual(pose.position, position.position)
            self.assertEqual(pose.rotation, orientation.rotation)
            self.assertEqual(pose.segment_index, position.segment_index)
            self.assertEqual(pose.local_time_alpha, position.local_time_alpha)
            self.assertEqual(pose.complete, position.complete)

    def test_direct_scrubbing_is_history_independent(self):
        queries = (4.0, 0.0, 0.75, 2.125, -2.0, 3.999, 2.125)
        first = {query: evaluate_cinematic_pose(self.compiled, query) for query in queries}
        second = {query: evaluate_cinematic_pose(self.compiled, query) for query in reversed(queries)}
        self.assertEqual(first, second)

    def test_nonfinite_elapsed_fails_before_any_pose_is_returned(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value), self.assertRaises(CinematicPoseError):
                evaluate_cinematic_pose(self.compiled, value)

    def test_every_cross_track_timeline_corruption_fails_closed(self):
        position = self.compiled.position
        orientation = self.compiled.orientation
        corruptions = (
            replace(self.compiled, total_seconds=5.0),
            CompiledCinematicPose(replace(position, total_seconds=5.0), orientation, 4.0),
            CompiledCinematicPose(position, replace(orientation, total_seconds=5.0), 4.0),
            CompiledCinematicPose(position, replace(orientation, segments=orientation.segments[:-1]), 4.0),
            CompiledCinematicPose(position, replace(orientation, segments=(replace(orientation.segments[0], duration_seconds=1.0), orientation.segments[1])), 4.0),
            CompiledCinematicPose(position, replace(orientation, segments=(orientation.segments[0], replace(orientation.segments[1], start_seconds=0.5))), 4.0),
        )
        for track in corruptions:
            with self.subTest(track=track), self.assertRaises(CinematicPoseError):
                evaluate_cinematic_pose(track, 0.25)

    def test_seeded_tracks_match_components_at_shuffled_absolute_times(self):
        rng = random.Random(0xEDD080)
        for _case in range(80):
            count = rng.randint(2, 12)
            points = []
            current = [0.0, 0.0, 0.0]
            for _ in range(count):
                current = [value + rng.uniform(-500.0, 500.0) for value in current]
                points.append(tuple(current))
            rotations = tuple(random_quaternion(rng) for _ in range(count))
            segments = tuple(
                AuthoredSegment(
                    10 ** rng.uniform(-2.0, 1.0),
                    "linear" if index % 3 == 0 else "auto_cinematic",
                    ("linear", "smoothstep", "smootherstep", "cinematic_s_curve", "accelerate_through", "brake_into")[index % 6],
                )
                for index in range(count - 1)
            )
            track = compile_cinematic_pose(tuple(points), rotations, segments)
            queries = [track.total_seconds * rng.random() for _ in range(30)] + [-1.0, track.total_seconds, track.total_seconds + 1.0]
            rng.shuffle(queries)
            for elapsed in queries:
                pose = evaluate_cinematic_pose(track, elapsed)
                self.assertTrue(all(math.isfinite(value) for value in pose.position + pose.rotation))
                self.assertEqual(pose.position, evaluate_position(track.position, elapsed).position)
                self.assertEqual(pose.rotation, evaluate_orientation(track.orientation, elapsed).rotation)


if __name__ == "__main__":
    unittest.main(verbosity=2)
