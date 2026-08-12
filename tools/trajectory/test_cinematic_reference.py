"""Executable contracts for deterministic cinematic position and timing."""

from __future__ import annotations

import math
import random
import unittest

from cinematic_reference import (
    AuthoredSegment, CompiledSegment, TrajectoryCompileError, compile_trajectory,
    evaluate_position, evaluate_spatial, evaluate_spatial_derivatives,
    evaluate_time_profile, invert_arc_length, invert_arc_table,
    build_arc_table_iterative, trace_arc_table_iterative,
)


def distance(a, b):
    return math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))


class TimeProfileContracts(unittest.TestCase):
    def test_every_preset_is_clamped_exact_and_monotonic(self):
        names = ("linear", "smoothstep", "smootherstep", "cinematic_s_curve",
                 "accelerate_through", "brake_into")
        for name in names:
            values = [evaluate_time_profile(name, index / 1000) for index in range(1001)]
            self.assertEqual(evaluate_time_profile(name, -2.0), 0.0)
            self.assertEqual(evaluate_time_profile(name, 2.0), 1.0)
            self.assertEqual(values[0], 0.0)
            self.assertAlmostEqual(values[-1], 1.0, places=12)
            self.assertTrue(all(a <= b + 1e-14 for a,b in zip(values, values[1:])), name)

    def test_profiles_have_the_intended_speed_bias(self):
        self.assertLess(evaluate_time_profile("accelerate_through", .5), .5)
        self.assertGreater(evaluate_time_profile("brake_into", .5), .5)
        self.assertAlmostEqual(evaluate_time_profile("cinematic_s_curve", .5), .5)

    def test_unknown_and_nonfinite_profiles_fail_closed(self):
        with self.assertRaises(TrajectoryCompileError): evaluate_time_profile("bounce", .5)
        with self.assertRaises(TrajectoryCompileError): evaluate_time_profile("linear", math.nan)


class CompileContracts(unittest.TestCase):
    def test_rejects_invalid_shape_duration_curves_and_controls(self):
        good = ((0.,0.,0.), (1.,0.,0.))
        with self.assertRaises(TrajectoryCompileError): compile_trajectory(good[:1], ())
        with self.assertRaises(TrajectoryCompileError): compile_trajectory(good, ())
        with self.assertRaises(TrajectoryCompileError): compile_trajectory(good, (AuthoredSegment(0),))
        with self.assertRaises(TrajectoryCompileError): compile_trajectory(good, (AuthoredSegment(math.inf),))
        with self.assertRaises(TrajectoryCompileError): compile_trajectory(((math.nan,0,0),good[1]), (AuthoredSegment(1),))
        with self.assertRaises(TrajectoryCompileError): compile_trajectory(good, (AuthoredSegment(1,"orbit"),))
        with self.assertRaises(TrajectoryCompileError): compile_trajectory(good, (AuthoredSegment(1,time_profile="bounce"),))
        with self.assertRaises(TrajectoryCompileError): compile_trajectory(good, (AuthoredSegment(1),),arc_tolerance=0)
        with self.assertRaises(TrajectoryCompileError): compile_trajectory(good, (AuthoredSegment(1),),max_arc_depth=21)

    def test_compilation_is_bitwise_deterministic_for_identical_input(self):
        points=((0.,0.,0.),(10.,0.,0.),(12.,8.,3.),(20.,10.,0.))
        segments=(AuthoredSegment(2),AuthoredSegment(3),AuthoredSegment(4))
        self.assertEqual(compile_trajectory(points,segments),compile_trajectory(points,segments))

    def test_linear_length_is_exact_and_auto_curve_has_ordered_bounded_table(self):
        linear=compile_trajectory(((0.,0.,0.),(3.,4.,0.)),(AuthoredSegment(2,"linear","linear"),))
        self.assertEqual(linear.segments[0].length,5.0)
        curved=compile_trajectory(((0.,0.,0.),(10.,0.,0.),(10.,10.,0.)),
            (AuthoredSegment(2),AuthoredSegment(2)))
        for segment in curved.segments:
            self.assertGreaterEqual(len(segment.arc_table),2)
            self.assertEqual(segment.arc_table[0].u,0.0)
            self.assertEqual(segment.arc_table[-1].u,1.0)
            self.assertTrue(all(a.u < b.u for a,b in zip(segment.arc_table,segment.arc_table[1:])))
            self.assertTrue(all(a.distance <= b.distance for a,b in zip(segment.arc_table,segment.arc_table[1:])))

    def test_iterative_blueprint_table_matches_recursive_oracle_exactly(self):
        rng=random.Random(0xEDD068)
        compared=0
        for _ in range(80):
            points=tuple(tuple(rng.uniform(-500,500) for _ in range(3)) for _ in range(rng.randint(2,8)))
            authored=tuple(AuthoredSegment(rng.uniform(.1,5)) for _ in range(len(points)-1))
            compiled=compile_trajectory(points,authored,arc_tolerance=.01,max_arc_depth=12)
            for segment in compiled.segments:
                self.assertEqual(
                    build_arc_table_iterative(segment,.01,12,8191),
                    segment.arc_table,
                )
                compared += 1
        self.assertGreater(compared,200)

    def test_iterative_blueprint_table_has_explicit_budget_and_input_failures(self):
        segment=compile_trajectory(
            ((0.,0.,0.),(10.,10.,5.),(30.,-10.,0.)),
            (AuthoredSegment(1),AuthoredSegment(1)),
            arc_tolerance=.001,
        ).segments[0]
        with self.assertRaises(TrajectoryCompileError): build_arc_table_iterative(segment,0,12,8191)
        with self.assertRaises(TrajectoryCompileError): build_arc_table_iterative(segment,.01,0,8191)
        with self.assertRaises(TrajectoryCompileError): build_arc_table_iterative(segment,.01,13,8191)
        with self.assertRaises(TrajectoryCompileError): build_arc_table_iterative(segment,.01,12,0)
        with self.assertRaises(TrajectoryCompileError): build_arc_table_iterative(segment,.01,12,8192)
        with self.assertRaises(TrajectoryCompileError): build_arc_table_iterative(segment,.001,12,1)
        malformed=CompiledSegment(**{
            **segment.__dict__, "start_velocity_u": (math.nan,0.,0.),
        })
        with self.assertRaises(TrajectoryCompileError): build_arc_table_iterative(malformed,.01,12,8191)

    def test_iterative_trace_reports_exact_operation_count(self):
        linear=compile_trajectory(((0.,0.,0.),(3.,4.,0.)),(AuthoredSegment(2,"linear","linear"),)).segments[0]
        table,operations=trace_arc_table_iterative(linear,.01,12,8191)
        self.assertEqual(table,linear.arc_table)
        self.assertEqual(len(table),65)
        self.assertEqual(operations,127)
        shallow=CompiledSegment(**{**linear.__dict__,"arc_table":()})
        table,operations=trace_arc_table_iterative(shallow,.01,1,3)
        self.assertEqual(len(table),3)
        self.assertEqual(operations,3)


class EvaluationContracts(unittest.TestCase):
    def setUp(self):
        self.points=((0.,0.,0.),(10.,10.,0.),(30.,10.,0.))
        self.compiled=compile_trajectory(self.points,(
            AuthoredSegment(2,"auto_cinematic","linear"),
            AuthoredSegment(4,"auto_cinematic","linear"),
        ),arc_tolerance=1e-5)

    def test_negative_time_and_every_authored_endpoint_are_exact(self):
        self.assertEqual(evaluate_position(self.compiled,-99).position,self.points[0])
        middle=evaluate_position(self.compiled,2)
        self.assertEqual(middle.position,self.points[1])
        self.assertFalse(middle.complete)
        end=evaluate_position(self.compiled,999)
        self.assertEqual(end.position,self.points[2])
        self.assertTrue(end.complete)
        self.assertEqual(end.total_seconds,6.0)

    def test_direct_scrub_is_history_and_frame_rate_independent(self):
        expected=evaluate_position(self.compiled,3.14159265)
        for step in (1/24,1/30,1/60,1/144):
            t=0.0
            while t < 3.14159265:
                evaluate_position(self.compiled,t)
                t += step
            self.assertEqual(evaluate_position(self.compiled,3.14159265),expected)

    def test_auto_cinematic_spatial_curve_is_c2_at_shared_waypoint(self):
        left,right=self.compiled.segments
        v_left,a_left=evaluate_spatial_derivatives(left,1.0)
        v_right,a_right=evaluate_spatial_derivatives(right,0.0)
        for actual,expected in zip(v_left,v_right): self.assertAlmostEqual(actual,expected,places=10)
        for actual,expected in zip(a_left,a_right): self.assertAlmostEqual(actual,expected,places=10)
        self.assertGreater(math.sqrt(sum(v*v for v in v_left)),0.0)

    def test_reverse_corner_stops_instead_of_generating_a_loop_tangent(self):
        compiled=compile_trajectory(((0.,0.,0.),(10.,0.,0.),(0.,0.,0.)),
            (AuthoredSegment(1),AuthoredSegment(1)))
        v_left,_=evaluate_spatial_derivatives(compiled.segments[0],1)
        v_right,_=evaluate_spatial_derivatives(compiled.segments[1],0)
        self.assertLess(math.sqrt(sum(v*v for v in v_left)),1e-10)
        self.assertLess(math.sqrt(sum(v*v for v in v_right)),1e-10)

    def test_auto_velocity_is_componentwise_monotone_and_time_normalized(self):
        compiled=compile_trajectory(((0.,0.,0.),(10.,-20.,5.),(30.,-30.,25.)),(
            AuthoredSegment(1,"auto_cinematic","linear"),
            AuthoredSegment(2,"auto_cinematic","linear"),
        ))
        self.assertEqual(compiled.segments[0].end_velocity_u,(10.,-5.,5.))
        self.assertEqual(compiled.segments[1].start_velocity_u,(20.,-10.,10.))
        left,_=evaluate_spatial_derivatives(compiled.segments[0],1.0)
        right,_=evaluate_spatial_derivatives(compiled.segments[1],0.0)
        self.assertEqual(left,right)
        self.assertEqual(left,(10.,-5.,5.))

    def test_flat_component_and_mixed_linear_neighbor_force_zero_velocity(self):
        flat=compile_trajectory(((0.,0.,0.),(10.,10.,10.),(20.,10.,30.)),(
            AuthoredSegment(1),AuthoredSegment(1),
        ))
        self.assertEqual(flat.segments[0].end_velocity_u,(10.,0.,10.))
        mixed=compile_trajectory(((0.,0.,0.),(10.,10.,10.),(20.,20.,20.)),(
            AuthoredSegment(1,"linear","linear"),AuthoredSegment(1,"auto_cinematic","linear"),
        ))
        self.assertEqual(mixed.segments[0].end_velocity_u,(0.,0.,0.))
        self.assertEqual(mixed.segments[1].start_velocity_u,(0.,0.,0.))

    def test_arc_inversion_approximates_equal_world_distance_on_curve(self):
        segment=self.compiled.segments[0]
        positions=[evaluate_spatial(segment,invert_arc_length(segment,i/10)) for i in range(11)]
        steps=[distance(a,b) for a,b in zip(positions,positions[1:])]
        mean=sum(steps)/len(steps)
        self.assertLess(max(abs(step-mean) for step in steps),mean*.08)

    def test_zero_length_segment_is_stable_and_time_still_advances(self):
        compiled=compile_trajectory(((1.,2.,3.),(1.,2.,3.)),
            (AuthoredSegment(2,"auto_cinematic","cinematic_s_curve"),))
        for t in (-1,0,.5,1,2,9): self.assertEqual(evaluate_position(compiled,t).position,(1.,2.,3.))

    def test_time_profile_changes_distance_not_geometry(self):
        points=((0.,0.,0.),(10.,0.,0.))
        linear=compile_trajectory(points,(AuthoredSegment(2,"linear","linear"),))
        ease=compile_trajectory(points,(AuthoredSegment(2,"linear","cinematic_s_curve"),))
        self.assertLess(evaluate_position(ease,.5).position[0],evaluate_position(linear,.5).position[0])
        self.assertEqual(evaluate_position(ease,1).position,evaluate_position(linear,1).position)

    def test_nonfinite_runtime_queries_fail_closed(self):
        with self.assertRaises(TrajectoryCompileError): evaluate_position(self.compiled,math.inf)
        with self.assertRaises(TrajectoryCompileError): invert_arc_length(self.compiled.segments[0],math.nan)

    def test_published_arc_table_boundary_rejects_every_malformed_family(self):
        valid=((0.0,.25,.75,1.0),(0.0,2.0,8.0,10.0),10.0,.5)
        self.assertAlmostEqual(invert_arc_table(*valid),.5)
        malformed=(
            ((),(),0.0,.5),
            ((0.0,1.0),(0.0,),1.0,.5),
            ((.1,1.0),(0.0,1.0),1.0,.5),
            ((0.0,1.0),(.1,1.0),1.0,.5),
            ((0.0,.5),(0.0,1.0),1.0,.5),
            ((0.0,.75,.5,1.0),(0.0,.2,.8,1.0),1.0,.5),
            ((0.0,.25,.75,1.0),(0.0,.8,.2,1.0),1.0,.5),
            ((0.0,1.0),(0.0,1.0),-1.0,.5),
            ((0.0,1.0),(0.0,1.0),math.inf,.5),
            ((0.0,math.nan),(0.0,1.0),1.0,.5),
            ((0.0,1.0),(0.0,math.inf),math.inf,.5),
            ((0.0,1.0),(0.0,1.0),1.0,math.nan),
        )
        for case in malformed:
            with self.subTest(case=case):
                with self.assertRaises(TrajectoryCompileError): invert_arc_table(*case)

    def test_arc_table_inversion_clamps_and_handles_plateaus_and_zero_length(self):
        self.assertEqual(invert_arc_table((0.0,1.0),(0.0,5.0),5.0,-2.0),0.0)
        self.assertEqual(invert_arc_table((0.0,1.0),(0.0,5.0),5.0,2.0),1.0)
        self.assertEqual(invert_arc_table((0.0,.25,.75,1.0),(0.0,2.0,2.0,4.0),4.0,.5),.25)
        for alpha in (-1.0,0.0,.125,.5,1.0,2.0):
            self.assertEqual(
                invert_arc_table((0.0,.5,1.0),(0.0,0.0,0.0),0.0,alpha),
                max(0.0,min(1.0,alpha)),
            )

    def test_bounded_auto_tangents_do_not_leave_local_chord_box_on_adversarial_paths(self):
        fixtures = (
            ((0.,0.,0.),(100.,0.,0.),(100.1,.01,0.),(200.,100.,0.)),
            ((0.,0.,0.),(.001,0.,0.),(1000.,1.,0.),(1000.,1000.,0.)),
            ((0.,0.,0.),(10.,0.,0.),(.1,.001,0.),(20.,0.,0.)),
            ((0.,0.,0.),(0.,10.,0.),(10.,10.,10.),(10.,20.,-10.)),
        )
        for points in fixtures:
            compiled=compile_trajectory(points,tuple(AuthoredSegment(1) for _ in range(len(points)-1)))
            for index,segment in enumerate(compiled.segments):
                local=points[max(0,index-1):min(len(points),index+3)]
                for axis in range(3):
                    low=min(point[axis] for point in local)-1e-8
                    high=max(point[axis] for point in local)+1e-8
                    for sample in range(101):
                        value=evaluate_spatial(segment,sample/100)[axis]
                        self.assertGreaterEqual(value,low,(points,index,axis,sample))
                        self.assertLessEqual(value,high,(points,index,axis,sample))

    def test_seeded_adversarial_compile_and_evaluation_stay_finite_and_bounded(self):
        rng=random.Random(0xEDD053)
        for _case in range(100):
            points=[]
            current=[0.0,0.0,0.0]
            for _ in range(rng.randint(2,10)):
                current=[value+rng.uniform(-1000,1000) for value in current]
                points.append(tuple(current))
            authored=tuple(AuthoredSegment(rng.uniform(.01,30)) for _ in range(len(points)-1))
            compiled=compile_trajectory(tuple(points),authored,arc_tolerance=.001)
            self.assertTrue(math.isfinite(compiled.total_distance))
            self.assertTrue(math.isfinite(compiled.total_seconds))
            for segment in compiled.segments:
                self.assertLessEqual(len(segment.arc_table),2**12+1)
                for sample in segment.arc_table:
                    self.assertTrue(math.isfinite(sample.u) and math.isfinite(sample.distance))
            for sample in range(101):
                result=evaluate_position(compiled,compiled.total_seconds*sample/100)
                self.assertTrue(all(math.isfinite(value) for value in result.position))


if __name__ == "__main__":
    unittest.main(verbosity=2)
