from __future__ import annotations

import json
import unittest
from pathlib import Path

from camera_operator_override_reference import (
    MAX_DELTA_SECONDS,
    MAX_TETHER_CM,
    MODES_V1,
    TRANSLATION_FRAMES_V1,
)


SCHEMA=json.loads(Path(__file__).with_name("camera_operator_override_blueprint_schema.json").read_text(encoding="utf-8"))


class CameraOperatorOverrideBlueprintSchemaContracts(unittest.TestCase):
    def test_asset_catalogs_and_hard_limits_are_frozen(self):
        self.assertEqual(SCHEMA["schemaVersion"],1)
        self.assertEqual(SCHEMA["asset"],"Local/Core/Client/BPC_EDD_ClientDirector.uasset")
        self.assertEqual(tuple(SCHEMA["limits"]["modes"]),MODES_V1)
        self.assertEqual(tuple(SCHEMA["limits"]["translationFrames"]),TRANSLATION_FRAMES_V1)
        self.assertEqual(SCHEMA["limits"]["maximumDeltaSeconds"],MAX_DELTA_SECONDS)
        self.assertEqual(SCHEMA["limits"]["maximumTetherDistanceCm"],MAX_TETHER_CM)
        self.assertIn("[-1,1]",SCHEMA["limits"]["translationInput"])
        self.assertIn("[-1,1]",SCHEMA["limits"]["lookInput"])

    def test_variables_are_typed_unique_and_exclusively_operator_owned(self):
        variables=SCHEMA["variables"]
        names=tuple(variable["name"] for variable in variables)
        self.assertEqual(len(names),51)
        self.assertEqual(len(names),len(set(names)))
        self.assertTrue(all(name.startswith("CameraOperator") for name in names))
        self.assertTrue(all(variable["container"]=="None" for variable in variables))
        self.assertTrue(all(variable["type"] in {"Boolean","String","Vector","Quat","Float"} for variable in variables))
        roles={role:{variable["name"] for variable in variables if variable["role"]==role}
               for role in {variable["role"] for variable in variables}}
        for left in roles:
            for right in roles:
                if left!=right:self.assertTrue(roles[left].isdisjoint(roles[right]))

    def test_distinct_authorship_and_carrier_frame_cannot_be_aliased(self):
        names={variable["name"] for variable in SCHEMA["variables"]}
        self.assertIn("CameraOperatorInputAuthoredBodyQuatV1",names)
        self.assertIn("CameraOperatorInputAuthoredGimbalQuatV1",names)
        self.assertIn("CameraOperatorInputCarrierFrameQuatV1",names)
        self.assertIn("CameraOperatorResultBodyQuatV1",names)
        self.assertIn("CameraOperatorResultGimbalQuatV1",names)
        architecture=SCHEMA["architecture"]
        self.assertIn("Body is copied exactly",architecture["authorship"])
        self.assertIn("Only the local final-view gimbal",architecture["authorship"])
        self.assertIn("separate twist-minimizing transport seam",architecture["carrierFrame"])
        self.assertIn("must never be manufactured by aliasing authored body or gimbal rotation",architecture["carrierFrame"])
        self.assertNotIn("CameraTransform",json.dumps(SCHEMA,sort_keys=True))

    def test_state_is_explicit_transient_and_disjoint_from_result(self):
        state={variable["name"] for variable in SCHEMA["variables"] if variable["role"]=="state"}
        self.assertEqual(state,{
            "CameraOperatorStateInitializedV1","CameraOperatorStateModeV1",
            "CameraOperatorStateRecenterActiveV1",
            "CameraOperatorStateTranslationOffsetV1","CameraOperatorStateTranslationVelocityV1",
            "CameraOperatorStateLookOffsetQuatV1","CameraOperatorStateAngularVelocityV1",
        })
        locality=SCHEMA["architecture"]["locality"]
        for token in ("Flypath documents","immutable publication","repository state","server authority",
                      "event timing","Cue ledgers","State Clip evaluation"):
            self.assertIn(token,locality)
        self.assertIn("real local delta time",SCHEMA["architecture"]["pause"])
        self.assertIn("without changing event timing",SCHEMA["architecture"]["pause"])

    def test_functions_freeze_reset_validate_translation_look_commit_order(self):
        functions=SCHEMA["functions"]
        self.assertEqual(tuple(function["name"] for function in functions),(
            "ResetCameraOperatorOverrideStepV1","ValidateCameraOperatorOverrideInputsV1",
            "BuildCameraOperatorTranslationV1","BuildCameraOperatorLookV1",
            "CommitCameraOperatorOverrideV1","ApplyCameraOperatorOverrideV1",
        ))
        self.assertEqual(tuple(function["stage"] for function in functions),tuple(range(6)))
        self.assertEqual(tuple(functions[-1]["uses"]),tuple(function["name"] for function in functions[:-1]))

    def test_mode_transition_tether_failure_and_ownership_contracts_are_visible(self):
        contracts=SCHEMA["contracts"]
        self.assertIn("publishes the authored pose exactly",contracts["initialization"])
        self.assertIn("equals authored position, body, and gimbal exactly",contracts["directed"])
        self.assertIn("decays any inherited Carrier Freecam translation smoothly",contracts["freeLook"])
        self.assertIn("Recenter is latched until settled",contracts["freeLook"])
        self.assertIn("separately supplied carrier-frame quaternion",contracts["carrierFreecam"])
        self.assertIn("removes outward radial velocity",contracts["tether"])
        self.assertIn("preserving the complete prior operator state",contracts["failure"])
        for forbidden_owner in ("Airframe/body/gimbal","CameraComfort","CameraChannel","CameraApply",
                                "playback time","Flypaths","repositories","events","Cue ledgers",
                                "State Clips","server state"):
            self.assertIn(forbidden_owner,contracts["ownership"])


if __name__=="__main__":
    unittest.main(verbosity=2)
