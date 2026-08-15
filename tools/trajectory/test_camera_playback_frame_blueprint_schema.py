from __future__ import annotations

import json
import unittest
from pathlib import Path


SCHEMA = json.loads(Path(__file__).with_name("camera_playback_frame_blueprint_schema.json").read_text(encoding="utf-8"))


class CameraPlaybackFrameBlueprintSchemaTests(unittest.TestCase):
    def test_exact_owned_shape_and_order(self):
        self.assertEqual(SCHEMA["schema"], "edd.camera-playback-frame.v1")
        variables = SCHEMA["variables"]
        self.assertEqual(len(variables), 30)
        self.assertEqual(len({item["name"] for item in variables}), len(variables))
        functions = SCHEMA["functions"]
        self.assertEqual(tuple(item["stage"] for item in functions), tuple(range(7)))
        self.assertEqual(tuple(item["name"] for item in functions), (
            "ResetCameraPlaybackFrameV1", "StageCameraPlaybackEvaluationTimeV1",
            "EvaluateCameraPlaybackSourcesV1", "StageCameraOperatorFromPlaybackV1",
            "StageCameraComfortFromPlaybackV1", "CommitCameraPlaybackFrameV1",
            "ComposeCameraPlaybackFrameV1",
        ))

    def test_one_absolute_time_drives_all_accepted_evaluators(self):
        stage = SCHEMA["functions"][1]
        self.assertEqual(tuple(stage["writes"]), (
            "CinematicPoseInputElapsedSecondsV1", "AirframePrebakeInputElapsedSecondsV1",
            "CarrierFrameInputElapsedSecondsV1", "CameraChannelQueryTimeV1",
        ))
        self.assertEqual(tuple(SCHEMA["functions"][2]["uses"]), (
            "EvaluateCompiledCinematicPoseV1", "EvaluateCompiledAirframePrebakeV1",
            "EvaluateCompiledCarrierFrameTransportV1", "EvaluateCameraChannelAssemblyV1",
        ))
        self.assertIn("exact same positive total duration", SCHEMA["architecture"]["timeline"])

    def test_body_gimbal_and_carrier_are_three_distinct_sources(self):
        operator = SCHEMA["functions"][3]
        self.assertEqual(operator["usesPosition"], "CinematicPoseResultPositionV1")
        self.assertEqual(operator["usesBody"], "AirframePrebakeResultBodyQuatV1")
        self.assertEqual(operator["usesGimbal"], "AirframePrebakeResultGimbalQuatV1")
        self.assertEqual(operator["usesCarrier"], "CarrierFrameResultQuatV1")
        authorship = SCHEMA["architecture"]["authorship"]
        self.assertIn("supplies position only", authorship)
        self.assertIn("remain distinct world-space authorship", authorship)
        self.assertIn("CinematicPoseResultQuatV1", authorship)
        self.assertIn("legacy CameraTransform rotation", authorship)
        self.assertIn("feeds only CameraOperatorInputCarrierFrameQuatV1", SCHEMA["architecture"]["carrier"])

    def test_actor_and_component_rotations_reconstruct_final_world_view(self):
        model = SCHEMA["architecture"]["componentModel"]
        self.assertIn("actor world rotation", model)
        self.assertIn("camera world rotation", model)
        self.assertIn("inverse(body) * gimbal", model)
        self.assertIn("body * relative", model)
        names = {item["name"] for item in SCHEMA["variables"]}
        self.assertTrue({
            "CameraPlaybackResultBodyWorldQuatV1",
            "CameraPlaybackResultGimbalWorldQuatV1",
            "CameraPlaybackResultGimbalRelativeQuatV1",
        }.issubset(names))

    def test_final_frame_is_atomic_and_native_application_stays_downstream(self):
        self.assertIn("written last", SCHEMA["contracts"]["atomicity"])
        self.assertIn("cannot partially replace", SCHEMA["contracts"]["failure"])
        self.assertIn("performs no native actor", SCHEMA["architecture"]["nativeApplication"])
        coordinator = tuple(SCHEMA["functions"][-1]["uses"])
        self.assertEqual(coordinator, (
            "ResetCameraPlaybackFrameV1", "StageCameraPlaybackEvaluationTimeV1",
            "EvaluateCameraPlaybackSourcesV1", "StageCameraOperatorFromPlaybackV1",
            "ApplyCameraOperatorOverrideV1", "StageCameraComfortFromPlaybackV1",
            "ApplyCameraViewerComfortV1", "CommitCameraPlaybackFrameV1",
        ))

    def test_ownership_forbids_authoritative_and_unrelated_mutation(self):
        ownership = SCHEMA["contracts"]["ownership"]
        for token in (
            "compiled tracks", "authored body/gimbal", "operator policy/state directly",
            "comfort preferences", "native camera state", "Flypaths", "repositories",
            "events", "Cue ledgers", "State Clips", "server state",
        ):
            self.assertIn(token, ownership)


if __name__ == "__main__":
    unittest.main(verbosity=2)
