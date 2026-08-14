import random
import unittest

from camera_focus_helper_reference import *


class CameraFocusHelperContracts(unittest.TestCase):
 def schedule(self,total=2.0,step=.5):return tuple(min(i*step,total) for i in range(int(__import__('math').ceil(total/step))+1))
 def cameras(self,times):return tuple((value*10.0,0.0,0.0) for value in times)
 def test_trace_hit_commits_and_miss_is_zero_mutation(self):
  state=FocusMarkerStateV1();hit,changed=set_focus_here_v1(state,True,(10,20,30));self.assertTrue(changed);self.assertEqual(hit,FocusMarkerStateV1(True,(10.0,20.0,30.0),1));miss,changed=set_focus_here_v1(hit,False,(float('nan'),0,0));self.assertFalse(changed);self.assertIs(miss,hit)
 def test_manual_and_fixed_world_compile_on_exact_schedule(self):
  times=self.schedule();cameras=self.cameras(times);manual=compile_focus_distance_samples_v1("manual_distance","linear",times,.5,cameras,manual_distances_cm=[100+i for i in range(len(times))]);self.assertEqual(manual.distances_cm,(100.0,101.0,102.0,103.0,104.0));fixed=compile_focus_distance_samples_v1("fixed_world","linear",times,.5,cameras,target_positions=[(200,0,0)]);self.assertEqual(fixed.distances_cm,(200.0,195.0,190.0,185.0,180.0))
 def test_reciprocal_rack_has_optical_midpoint(self):
  times=(0.0,1.0);cameras=((0,0,0),(0,0,0));rack=compile_focus_distance_samples_v1("rack_fixed","reciprocal",times,1.0,cameras,rack_target_a=(100,0,0),rack_target_b=(400,0,0),rack_blend_weights=(0.0,.5));self.assertAlmostEqual(rack.distances_cm[0],100);self.assertAlmostEqual(rack.distances_cm[1],160)
 def test_tracking_is_prebaked_and_history_free(self):
  times=self.schedule();cameras=self.cameras(times);targets=tuple((100+index*7,0,0) for index in range(len(times)));result=compile_focus_distance_samples_v1("track_prebaked","linear",times,.5,cameras,target_positions=targets);self.assertEqual(result.distances_cm,tuple(100+index*2 for index in range(len(times))));self.assertEqual(tuple(reversed(result.distances_cm)),tuple(reversed(result.distances_cm)))
 def test_smoothed_autofocus_is_compiled_not_query_state(self):
  times=(0.0,.5,1.0,1.5);cameras=((0,0,0),)*4;targets=((100,0,0),(400,0,0),(400,0,0),(400,0,0));result=compile_focus_distance_samples_v1("smoothed_autofocus","linear",times,.5,cameras,target_positions=targets,smoothing_response_seconds=.5);self.assertEqual(result.distances_cm[0],100);self.assertTrue(100<result.distances_cm[1]<400);self.assertTrue(all(a<b for a,b in zip(result.distances_cm,result.distances_cm[1:])))
 def test_commit_publishes_only_focus_distance_channel(self):
  samples=FocusDistanceSamplesV1("manual_distance","reciprocal",(0.0,1.0),(100.0,400.0));published=commit_focus_distance_channel_v1(samples);self.assertEqual(published.channel_id,"focus_distance_cm");self.assertEqual(published.interpolation_modes,("linear",));self.assertNotIn("focus_influence",repr(published))
 def test_seeded_modes_and_inputs_are_immutable(self):
  rng=random.Random(0xEDD6F0);times=self.schedule(2.25,.5);cameras=self.cameras(times)
  for _ in range(40):
   target=tuple(rng.uniform(200,800) for _ in times);manual=list(target);before=(tuple(times),tuple(cameras),tuple(manual));result=compile_focus_distance_samples_v1("manual_distance",rng.choice(DOMAINS_V1),times,.5,cameras,manual_distances_cm=manual);self.assertEqual(before,(tuple(times),tuple(cameras),tuple(manual)));self.assertEqual(len(result.distances_cm),len(times))
 def test_invalid_families_fail_closed(self):
  times=(0.0,1.0);cameras=((0,0,0),(0,0,0));cases=(lambda:compile_focus_distance_samples_v1("bad","linear",times,1,cameras),lambda:compile_focus_distance_samples_v1("manual_distance","bad",times,1,cameras,manual_distances_cm=(1,2)),lambda:compile_focus_distance_samples_v1("manual_distance","linear",(0,2),1,cameras,manual_distances_cm=(1,2)),lambda:compile_focus_distance_samples_v1("manual_distance","linear",times,1,cameras,manual_distances_cm=(1,2),target_positions=((100,0,0),)),lambda:compile_focus_distance_samples_v1("fixed_world","linear",times,1,cameras,target_positions=()),lambda:compile_focus_distance_samples_v1("rack_fixed","linear",times,1,cameras,rack_target_a=(100,0,0),rack_target_b=(200,0,0),rack_blend_weights=(0,2)),lambda:compile_focus_distance_samples_v1("smoothed_autofocus","linear",times,1,cameras,target_positions=((100,0,0),)*2,smoothing_response_seconds=0),lambda:commit_focus_distance_channel_v1(FocusDistanceSamplesV1("manual_distance","linear",(0,0),(100,200))))
  for case in cases:
   with self.assertRaises(CameraFocusHelperError):case()


if __name__=="__main__":unittest.main(verbosity=2)
