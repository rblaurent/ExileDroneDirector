"""Executable contracts for independent twist-minimizing carrier frames."""

from __future__ import annotations

from dataclasses import replace
from math import cos, isfinite, pi, sin, sqrt
import random
import unittest

from carrier_frame_transport_reference import (
    CarrierFrameTransportError,
    CompiledCarrierFrameTransportV1,
    compile_carrier_frame_transport_v1,
    evaluate_carrier_frame_transport_v1,
)


def dot(left, right): return sum(a * b for a, b in zip(left, right))
def length(value): return sqrt(dot(value, value))
def rotate(q, v):
    x, y, z, w = q
    qv = (v[0], v[1], v[2], 0.0)
    def mul(a, b):
        ax, ay, az, aw = a; bx, by, bz, bw = b
        return (aw*bx+ax*bw+ay*bz-az*by, aw*by-ax*bz+ay*bw+az*bx,
                aw*bz+ax*by-ay*bx+az*bw, aw*bw-ax*bx-ay*by-az*bz)
    result = mul(mul(q, qv), (-x, -y, -z, w))
    return result[:3]


class CarrierFrameTransportContracts(unittest.TestCase):
    def test_straight_world_x_is_identity_without_body_or_gimbal(self):
        positions = ((0.0,0.0,0.0),(1.0,0.0,0.0),(2.0,0.0,0.0))
        track = compile_carrier_frame_transport_v1(positions, 1.0, 0.5)
        self.assertEqual(track.rotations, ((0.0,0.0,0.0,1.0),)*3)
        self.assertNotIn("body", compile_carrier_frame_transport_v1.__code__.co_varnames)
        self.assertNotIn("gimbal", compile_carrier_frame_transport_v1.__code__.co_varnames)

    def test_planar_curve_keeps_world_up_without_frenet_roll(self):
        positions = tuple((cos(i*pi/8.0), sin(i*pi/8.0), 0.0) for i in range(5))
        track = compile_carrier_frame_transport_v1(positions, 1.0, 0.25)
        for rotation in track.rotations:
            up = rotate(rotation, (0.0,0.0,1.0))
            self.assertAlmostEqual(up[0], 0.0, places=7)
            self.assertAlmostEqual(up[1], 0.0, places=7)
            self.assertGreater(up[2], 0.999999)

    def test_vertical_motion_uses_deterministic_nonparallel_up(self):
        track = compile_carrier_frame_transport_v1(((0,0,0),(0,0,1),(0,0,2)), 1.0, 0.5)
        self.assertTrue(all(all(isfinite(value) for value in quat) for quat in track.rotations))
        self.assertEqual(track.rotations, compile_carrier_frame_transport_v1(track.positions,1.0,0.5).rotations)
        for tangent, rotation in zip(track.tangents, track.rotations):
            self.assertLess(length(tuple(a-b for a,b in zip(rotate(rotation,(1,0,0)),tangent))),1e-6)

    def test_holds_and_reversal_have_stable_hemisphere(self):
        positions=((0,0,0),(1,0,0),(1,0,0),(1,0,0),(0,0,0))
        track=compile_carrier_frame_transport_v1(positions,1.0,0.25)
        self.assertEqual(len(track.rotations),5)
        self.assertTrue(all(dot(a,b)>=-1e-9 for a,b in zip(track.rotations,track.rotations[1:])))
        self.assertAlmostEqual(dot(track.tangents[-1],(-1,0,0)),1.0,places=7)

    def test_partial_terminal_interval_and_absolute_evaluation(self):
        positions=((0,0,0),(1,0,0),(2,1,0),(3,2,0))
        track=compile_carrier_frame_transport_v1(positions,1.0,0.4)
        terminal=evaluate_carrier_frame_transport_v1(track,9.0)
        self.assertTrue(terminal.valid and terminal.complete)
        self.assertEqual((terminal.segment_index,terminal.alpha),(2,1.0))
        queries=[0.0,0.2,0.4,0.8,0.999]
        forward={t:evaluate_carrier_frame_transport_v1(track,t) for t in queries}
        reverse={t:evaluate_carrier_frame_transport_v1(track,t) for t in reversed(queries)}
        self.assertEqual(forward,reverse)

    def test_seeded_transport_is_deterministic_and_orthonormal(self):
        rng=random.Random(0xEDDCA221)
        positions=[(0.0,0.0,0.0)]
        for index in range(1,101):
            if index%17==0: positions.append(positions[-1]); continue
            step=(rng.uniform(-2,2),rng.uniform(-2,2),rng.uniform(-1,1))
            positions.append(tuple(a+b for a,b in zip(positions[-1],step)))
        track=compile_carrier_frame_transport_v1(positions,10.0,0.1)
        repeated=compile_carrier_frame_transport_v1(tuple(positions),10.0,0.1)
        self.assertEqual(track,repeated)
        for tangent,rotation in zip(track.tangents,track.rotations):
            forward=rotate(rotation,(1,0,0));right=rotate(rotation,(0,1,0));up=rotate(rotation,(0,0,1))
            self.assertLess(length(tuple(a-b for a,b in zip(forward,tangent))),1e-6)
            self.assertAlmostEqual(length(right),1.0,places=6);self.assertAlmostEqual(length(up),1.0,places=6)
            self.assertAlmostEqual(dot(forward,right),0.0,places=6);self.assertAlmostEqual(dot(forward,up),0.0,places=6);self.assertAlmostEqual(dot(right,up),0.0,places=6)

    def test_invalid_inputs_fail_closed(self):
        valid=((0,0,0),(1,0,0),(2,0,0))
        invalid=(
            (valid,0.0,1.0),(valid,2.0,0.0),(valid[:2],2.0,1.0),
            (((0,0,0),(0,0,0),(0,0,0)),2.0,1.0),
            (((0,0,0),(float("nan"),0,0),(2,0,0)),2.0,1.0),
            (valid,True,1.0),(valid,2.0,False),
        )
        for values in invalid:
            with self.subTest(values=values):
                with self.assertRaises(CarrierFrameTransportError):compile_carrier_frame_transport_v1(*values)

    def test_tampered_compiled_tracks_are_rejected_by_evaluator(self):
        track=compile_carrier_frame_transport_v1(((0,0,0),(1,0,0),(2,0,0)),1.0,0.5)
        poisoned=(
            replace(track,rotations=track.rotations[:-1]),
            replace(track,tangents=((2.0,0.0,0.0),)+track.tangents[1:]),
            replace(track,rotations=((0.0,0.0,0.0,2.0),)+track.rotations[1:]),
            replace(track,rotations=((0.0,0.0,0.0,1.0),(0.0,0.0,1.0,0.0),track.rotations[2])),
        )
        for value in poisoned:
            result=evaluate_carrier_frame_transport_v1(value,0.5)
            self.assertFalse(result.valid);self.assertIsNone(result.rotation)


if __name__=="__main__":unittest.main(verbosity=2)
