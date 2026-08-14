import json
import unittest
from pathlib import Path


SCHEMA=json.loads((Path(__file__).with_name("camera_focus_helper_blueprint_schema.json")).read_text(encoding="utf-8"))


class CameraFocusHelperSchemaContracts(unittest.TestCase):
 def test_exact_modes_and_functions(self):
  self.assertEqual(SCHEMA["modes"],["manual_distance","fixed_world","rack_fixed","track_prebaked","smoothed_autofocus"]);self.assertEqual([item["name"] for item in SCHEMA["functions"]],["SetCameraFocusHereV1","ResetCameraFocusCompileV1","ValidateCameraFocusInputsV1","BuildCameraFocusDistanceCandidatesV1","CommitCameraFocusDistanceChannelV1","CompileCameraFocusDistanceChannelV1"]);self.assertEqual(SCHEMA["functions"][0]["boundary"],"authoring");self.assertEqual(SCHEMA["functions"][-1]["uses"],["ResetCameraFocusCompileV1","ValidateCameraFocusInputsV1","BuildCameraFocusDistanceCandidatesV1","CommitCameraFocusDistanceChannelV1"])
 def test_ownership_forbids_other_camera_and_motion_state(self):
  names={item["name"] for item in SCHEMA["variables"]};self.assertTrue(all("Influence" not in name for name in names));self.assertTrue(all(not name.startswith(("CameraApply","Airframe","Document")) for name in names));self.assertIn("only the focus_distance_cm",SCHEMA["invariants"]["ownership"])
 def test_actor_tracking_is_prebaked_not_pointer_authorship(self):
  variables=SCHEMA["variables"];self.assertTrue(any(item["name"]=="CameraFocusInputTargetPositionsV1" and item["type"]=="Vector" and item["container"]=="Array" for item in variables));self.assertFalse(any(item["type"] in ("Object","Actor") for item in variables));self.assertIn("No transient actor pointer",SCHEMA["invariants"]["tracking"])
 def test_candidate_and_compiled_storage_are_distinct(self):
  roles={item["name"]:item["role"] for item in SCHEMA["variables"]};self.assertEqual(roles["CameraFocusCandidateDistancesCmV1"],"candidate");self.assertEqual(roles["CameraFocusCompiledDistancesCmV1"],"compiled");self.assertIn("prior compiled focus channel",SCHEMA["invariants"]["atomicity"])
 def test_schedule_is_absolute_and_bounded(self):
  self.assertEqual(SCHEMA["limits"],{"minimumDistanceCm":1.0,"minimumSamples":2,"maximumSamples":65536});self.assertIn("independent of query order",SCHEMA["invariants"]["schedule"])
 def test_mode_inputs_are_exclusive(self):self.assertIn("Exactly one mode-specific",SCHEMA["invariants"]["exclusivity"])


if __name__=="__main__":unittest.main(verbosity=2)
