"""Schema and ownership contracts for the independent carrier frame track."""

from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT=Path(__file__).resolve().parents[2]
SCHEMA=json.loads((ROOT/"tools/trajectory/carrier_frame_transport_blueprint_schema.json").read_text(encoding="utf-8"))


class CarrierFrameSchemaContracts(unittest.TestCase):
    def test_identity_and_limits_are_frozen(self):
        self.assertEqual((SCHEMA["schema"],SCHEMA["version"]),("edd.carrier-frame-transport.v1",1))
        self.assertEqual(SCHEMA["limits"],{"minimumFixedStepSeconds":1/240,"maximumFixedStepSeconds":0.5,"maximumTotalSeconds":3600.0,"maximumSampleCount":65536,"unitTolerance":1e-6})

    def test_upstream_is_only_the_accepted_sampled_path(self):
        self.assertEqual(SCHEMA["upstream"],{
            "sourceValid":"AirframeDesiredStreamCompileValidV1",
            "positions":"AirframeDesiredStreamInputPositionsV1",
            "totalSeconds":"AirframeDesiredStreamInputTotalSecondsV1",
            "fixedStepSeconds":"AirframeDesiredStreamInputFixedStepSecondsV1",
        })
        text=json.dumps(SCHEMA)
        self.assertNotIn("BodyQuat",text);self.assertNotIn("GimbalQuat",text);self.assertNotIn("CameraTransform",text)

    def test_variables_have_exact_unique_names_and_roles(self):
        variables=SCHEMA["variables"];names=[item["name"] for item in variables]
        self.assertEqual(len(names),24);self.assertEqual(len(names),len(set(names)))
        self.assertTrue(all(name.startswith("CarrierFrame") for name in names))
        roles={item["role"] for item in variables}
        self.assertEqual(roles,{"input","candidate","result","evaluationInput","evaluationResult","diagnostic","scratch"})
        arrays={item["name"] for item in variables if item["container"]=="Array"}
        self.assertEqual(arrays,{"CarrierFrameInputPositionsV1","CarrierFrameCandidateTangentsV1","CarrierFrameCandidateQuatsV1","CarrierFrameCompiledTangentsV1","CarrierFrameCompiledQuatsV1"})

    def test_function_order_and_dependencies_are_exact(self):
        functions=SCHEMA["functions"]
        self.assertEqual([item["stage"] for item in functions],list(range(8)))
        self.assertEqual([item["name"] for item in functions],[
            "ResetCarrierFrameTransportV1","StageCarrierFrameTransportInputsV1",
            "ValidateCarrierFrameTransportInputsV1","BuildCarrierFrameTangentsV1",
            "BuildCarrierFrameTransportSamplesV1","CommitCompiledCarrierFrameTransportV1",
            "CompileCarrierFrameTransportV1","EvaluateCompiledCarrierFrameTransportV1",
        ])
        self.assertEqual(functions[6]["uses"],[item["name"] for item in functions[:6]])

    def test_contracts_freeze_transport_atomicity_and_non_authority(self):
        contracts=SCHEMA["contracts"]
        for name in ("authorship","transport","holds","schedule","atomicity","evaluation","failure","ownership"):
            self.assertIn(name,contracts);self.assertTrue(contracts[name])
        self.assertIn("neither read nor copied",contracts["authorship"])
        self.assertIn("never use a Frenet normal",contracts["transport"])
        self.assertIn("validity last",contracts["atomicity"])
        self.assertIn("non-authoritative",contracts["ownership"])


if __name__=="__main__":unittest.main(verbosity=2)

