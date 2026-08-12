"""Executable contracts for deterministic cinematic quaternion tracks."""

from __future__ import annotations

import math
import random
import unittest

from orientation_reference import (
    OrientationCompileError, compile_orientation_track, evaluate_orientation,
    logarithmic_delta, normalize,
)


IDENTITY = (0.0, 0.0, 0.0, 1.0)


def axis_angle(axis, degrees):
    magnitude = math.sqrt(sum(value*value for value in axis))
    half = math.radians(degrees)*0.5
    scale = math.sin(half)/magnitude
    return normalize((axis[0]*scale, axis[1]*scale, axis[2]*scale, math.cos(half)))


def magnitude(vector):
    return math.sqrt(sum(value*value for value in vector))


class OrientationCompileContracts(unittest.TestCase):
    def test_rejects_invalid_shapes_durations_and_quaternions(self):
        with self.assertRaises(OrientationCompileError): compile_orientation_track((IDENTITY,), ())
        with self.assertRaises(OrientationCompileError): compile_orientation_track((IDENTITY,IDENTITY), ())
        for duration in (0.0, -1.0, math.nan, math.inf):
            with self.assertRaises(OrientationCompileError):
                compile_orientation_track((IDENTITY,IDENTITY), (duration,))
        for bad in ((0,0,0,0), (math.nan,0,0,1), (0,0,1), (0,0,0,1,2)):
            with self.assertRaises(OrientationCompileError):
                compile_orientation_track((IDENTITY,bad), (1.0,))

    def test_normalizes_and_sign_aligns_once_deterministically(self):
        rotations=(IDENTITY,(0,0,-2,0),(0,0,0,-4))
        first=compile_orientation_track(rotations,(1,2))
        second=compile_orientation_track(rotations,(1,2))
        self.assertEqual(first,second)
        self.assertTrue(all(abs(magnitude(value)-1.0)<1e-12 for value in first.waypoints))
        self.assertTrue(all(sum(a*b for a,b in zip(left,right))>=0
            for left,right in zip(first.waypoints,first.waypoints[1:])))

    def test_two_key_track_reduces_to_constant_speed_shortest_arc(self):
        end=axis_angle((0,0,1),120)
        track=compile_orientation_track((IDENTITY,end),(3,))
        for index in range(13):
            t=3*index/12
            result=evaluate_orientation(track,t).rotation
            expected_angle=math.radians(120)*index/12
            self.assertAlmostEqual(magnitude(logarithmic_delta(IDENTITY,result)),expected_angle,places=10)


class OrientationEvaluationContracts(unittest.TestCase):
    def setUp(self):
        self.rotations=(
            IDENTITY, axis_angle((0,0,1),70), axis_angle((0,1,1),130),
            axis_angle((1,-1,.5),175),
        )
        self.durations=(.75,3.25,1.5)
        self.track=compile_orientation_track(self.rotations,self.durations)

    def test_negative_time_and_every_authored_endpoint_are_exact(self):
        self.assertEqual(evaluate_orientation(self.track,-5).rotation,self.track.waypoints[0])
        elapsed=0.0
        for index,duration in enumerate(self.durations):
            elapsed += duration
            result=evaluate_orientation(self.track,elapsed)
            self.assertEqual(result.rotation,self.track.waypoints[index+1])
        self.assertTrue(evaluate_orientation(self.track,999).complete)

    def test_direct_scrub_is_history_and_frame_rate_independent(self):
        expected=evaluate_orientation(self.track,2.3456789)
        for step in (1/24,1/60,1/144):
            t=0.0
            while t<2.3456789:
                evaluate_orientation(self.track,t)
                t += step
            self.assertEqual(evaluate_orientation(self.track,2.3456789),expected)

    def test_unequal_duration_joins_have_continuous_angular_velocity(self):
        join=self.durations[0]
        for epsilon in (1e-3,2e-4,5e-5):
            before=evaluate_orientation(self.track,join-epsilon).rotation
            at=evaluate_orientation(self.track,join).rotation
            after=evaluate_orientation(self.track,join+epsilon).rotation
            incoming=tuple(-value/epsilon for value in logarithmic_delta(at,before))
            outgoing=tuple(value/epsilon for value in logarithmic_delta(at,after))
            error=magnitude(tuple(a-b for a,b in zip(incoming,outgoing)))
            self.assertLess(error,0.02)

    def test_outputs_remain_unit_and_adjacent_samples_never_sign_flip(self):
        previous=None
        for index in range(2001):
            result=evaluate_orientation(self.track,self.track.total_seconds*index/2000).rotation
            self.assertAlmostEqual(magnitude(result),1.0,places=11)
            if previous is not None:
                self.assertGreaterEqual(sum(a*b for a,b in zip(previous,result)),-1e-12)
            previous=result

    def test_equivalent_antipodal_authored_keys_produce_identical_track(self):
        negated=tuple(tuple(-value for value in rotation) if index%2 else rotation
            for index,rotation in enumerate(self.rotations))
        other=compile_orientation_track(negated,self.durations)
        for index in range(501):
            t=self.track.total_seconds*index/500
            left=evaluate_orientation(self.track,t).rotation
            right=evaluate_orientation(other,t).rotation
            self.assertLess(magnitude(logarithmic_delta(left,right)),1e-10)

    def test_nonfinite_runtime_query_fails_closed(self):
        for value in (math.nan,math.inf,-math.inf):
            with self.assertRaises(OrientationCompileError): evaluate_orientation(self.track,value)

    def test_seeded_adversarial_tracks_remain_finite_unit_and_deterministic(self):
        rng=random.Random(0xEDD057)
        for _case in range(100):
            rotations=[]
            durations=[]
            for index in range(rng.randint(2,10)):
                rotations.append(axis_angle(
                    tuple(rng.uniform(-1,1) for _ in range(3)),rng.uniform(-179.999,179.999)
                ))
                if index: durations.append(10**rng.uniform(-2,1.5))
            first=compile_orientation_track(tuple(rotations),tuple(durations))
            self.assertEqual(first,compile_orientation_track(tuple(rotations),tuple(durations)))
            for sample in range(101):
                value=evaluate_orientation(first,first.total_seconds*sample/100).rotation
                self.assertTrue(all(math.isfinite(component) for component in value))
                self.assertAlmostEqual(magnitude(value),1.0,places=10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
