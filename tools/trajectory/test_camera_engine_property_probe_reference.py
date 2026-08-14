"""Contracts for deterministic camera-engine property discovery."""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
import ast
import json
from pathlib import Path
import unittest

from camera_engine_application_reference import REQUIRED_TARGET_IDS_V1, TARGET_IDS_V1
from camera_engine_property_probe_reference import (
    CameraEnginePropertyObservationV1,
    CameraEnginePropertyProbeError,
    load_camera_engine_property_candidates_v1,
    resolve_camera_engine_property_manifest_v1,
)


def usable(value_type: str = "float") -> CameraEnginePropertyObservationV1:
    return CameraEnginePropertyObservationV1(True, True, value_type)


def complete_observations(schema: dict) -> dict[str, CameraEnginePropertyObservationV1]:
    result = {}
    for target in schema["targets"]:
        for candidate in target["candidates"]:
            result[candidate["valuePath"]] = usable()
            if candidate.get("overridePath"):
                result[candidate["overridePath"]] = usable("bool")
    return result


class CameraEnginePropertyProbeContracts(unittest.TestCase):
    def setUp(self):
        self.schema = load_camera_engine_property_candidates_v1()
        self.observations = complete_observations(self.schema)

    def test_candidate_order_and_deliberate_unsupported_targets_are_exact(self):
        self.assertEqual(tuple(item["id"] for item in self.schema["targets"]), TARGET_IDS_V1)
        self.assertEqual(
            tuple(item["id"] for item in self.schema["targets"] if item["required"]),
            REQUIRED_TARGET_IDS_V1,
        )
        unsupported = tuple(
            item["id"] for item in self.schema["targets"] if not item["candidates"]
        )
        self.assertEqual(
            unsupported,
            (
                "focus_influence",
                "color_grading_weight",
                "tint_weight",
                "sharpening_weight",
                "matte_weight",
            ),
        )

    def test_complete_reflection_selects_only_declared_one_to_one_paths(self):
        manifest = resolve_camera_engine_property_manifest_v1(
            "5.6.1-0+++UE5+Release-5.6", self.observations, self.schema
        )
        self.assertFalse(manifest.missing_required_target_ids)
        for target, available, value_path in zip(
            self.schema["targets"],
            manifest.capabilities.available,
            manifest.selected_value_paths,
        ):
            self.assertEqual(available, bool(target["candidates"]))
            self.assertEqual(value_path, target["candidates"][0]["valuePath"] if target["candidates"] else "")
        self.assertEqual(len(set(path for path in manifest.selected_value_paths if path)), 10)

    def test_override_partner_is_required_for_post_process_ownership(self):
        broken = dict(self.observations)
        broken["post_process_settings.override_bloom_intensity"] = CameraEnginePropertyObservationV1(True, False, "bool")
        manifest = resolve_camera_engine_property_manifest_v1("5.6.1", broken, self.schema)
        bloom = TARGET_IDS_V1.index("bloom_weight")
        self.assertFalse(manifest.capabilities.available[bloom])
        self.assertEqual(manifest.selected_value_paths[bloom], "")
        self.assertFalse(manifest.missing_required_target_ids)

    def test_missing_or_wrong_required_property_is_reported_in_canonical_order(self):
        broken = dict(self.observations)
        broken["filmback.sensor_height"] = usable("int")
        broken["current_focal_length"] = CameraEnginePropertyObservationV1(False, True, "float")
        manifest = resolve_camera_engine_property_manifest_v1("5.6.1", broken, self.schema)
        self.assertEqual(
            manifest.missing_required_target_ids,
            ("filmback_sensor_height_mm", "focal_length_mm"),
        )

    def test_manifest_identity_is_canonical_and_observation_order_independent(self):
        forward = resolve_camera_engine_property_manifest_v1("5.6.1", self.observations, self.schema)
        reverse = resolve_camera_engine_property_manifest_v1(
            "5.6.1", OrderedDict(reversed(tuple(self.observations.items()))), self.schema
        )
        self.assertEqual(forward, reverse)
        payload = json.loads(forward.canonical_json)
        self.assertEqual(payload["manifestId"], forward.capabilities.manifest_id)
        self.assertEqual(len(payload["manifestId"]), 64)
        self.assertEqual(forward.canonical_json, json.dumps(payload, sort_keys=True, separators=(",", ":")))

    def test_checked_in_enhanced_manifest_replays_the_probe_exactly(self):
        resolved = resolve_camera_engine_property_manifest_v1(
            "5.6.1-370197+++exiles+release", self.observations, self.schema
        )
        manifest_path = Path(__file__).with_name(
            "camera_engine_property_manifest_enhanced_5_6_1.json"
        )
        checked_in = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(
            json.dumps(checked_in, sort_keys=True, separators=(",", ":")),
            resolved.canonical_json,
        )

    def test_malformed_candidate_schemas_fail_instead_of_guessing(self):
        cases = []
        wrong_order = deepcopy(self.schema)
        wrong_order["targets"][0], wrong_order["targets"][1] = wrong_order["targets"][1], wrong_order["targets"][0]
        cases.append(wrong_order)
        alias = deepcopy(self.schema)
        alias["targets"][1]["candidates"][0]["valuePath"] = alias["targets"][0]["candidates"][0]["valuePath"]
        cases.append(alias)
        bad_type = deepcopy(self.schema)
        bad_type["targets"][0]["expectedType"] = "double"
        cases.append(bad_type)
        for schema in cases:
            with self.subTest(schema=schema), self.assertRaises(CameraEnginePropertyProbeError):
                resolve_camera_engine_property_manifest_v1("5.6.1", self.observations, schema)

    def test_unreal_probe_is_non_persistent_and_always_destroys_transient_actor(self):
        probe_path = Path(__file__).parents[1] / "unreal/Probe-CameraEngineProperties.py"
        text = probe_path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertTrue({"spawn_actor_from_class", "destroy_actor"}.issubset(calls))
        self.assertTrue(any(isinstance(node, ast.Try) and node.finalbody for node in ast.walk(tree)))
        self.assertFalse(
            {"save_asset", "save_loaded_asset", "save_directory", "save_current_level"} & calls
        )
        self.assertNotIn("EditorAssetLibrary.save", text)
        self.assertIn("load_camera_engine_property_candidates_v1", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
