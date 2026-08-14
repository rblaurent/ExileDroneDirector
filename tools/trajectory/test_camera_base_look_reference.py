from __future__ import annotations

import math
import random
import unittest

from camera_base_look_reference import *


class CameraBaseLookReferenceContracts(unittest.TestCase):
    def test_catalog_is_complete_explicit_and_stable(self):
        self.assertEqual(
            CAMERA_BASE_LOOK_IDS_V1,
            (
                "raw", "clean_cinematic", "epic_landscape", "dreamy_shallow_focus",
                "dark_sorcery", "high_speed_fpv", "vintage_lens", "documentary",
            ),
        )
        self.assertEqual(len(CHANNEL_IDS_V1), 13)
        for preset in CAMERA_BASE_LOOK_PRESETS_V1:
            self.assertEqual(len(preset.values), len(CHANNEL_IDS_V1))
            self.assertEqual(resolve_camera_base_look_v1(preset.preset_id), preset)

    def test_raw_is_exact_channel_default_frame(self):
        self.assertEqual(resolve_camera_base_look_v1("raw").values, CHANNEL_DEFAULTS_V1)

    def test_currently_unavailable_direct_channels_remain_neutral(self):
        defaults = dict(zip(CHANNEL_IDS_V1, CHANNEL_DEFAULTS_V1))
        for preset in CAMERA_BASE_LOOK_PRESETS_V1:
            values = dict(zip(CHANNEL_IDS_V1, preset.values))
            for channel_id in DIRECTLY_UNAVAILABLE_CHANNELS_V1:
                self.assertEqual(values[channel_id], defaults[channel_id])

    def test_sparse_authorship_wins_without_hiding_base_values(self):
        result = compose_camera_base_look_v1(
            "dreamy_shallow_focus",
            ("focal_length_mm", "bloom_weight", "chromatic_aberration_weight"),
            (42.0, 0.2, 0.0),
        )
        index = {channel_id: offset for offset, channel_id in enumerate(CHANNEL_IDS_V1)}
        self.assertEqual(result.base_values[index["focal_length_mm"]], 85.0)
        self.assertEqual(result.values[index["focal_length_mm"]], 42.0)
        self.assertEqual(result.values[index["bloom_weight"]], 0.2)
        self.assertEqual(result.values[index["vignette_weight"]], 0.2)
        self.assertEqual(result.authored_override_mask.count(True), 3)

    def test_override_order_does_not_change_canonical_output(self):
        forward = compose_camera_base_look_v1(
            "clean_cinematic", ("exposure_ev", "aperture_fstop", "vignette_weight"), (1.0, 4.0, 0.4)
        )
        reverse = compose_camera_base_look_v1(
            "clean_cinematic", ("vignette_weight", "aperture_fstop", "exposure_ev"), (0.4, 4.0, 1.0)
        )
        self.assertEqual(forward, reverse)

    def test_inputs_are_not_mutated_or_aliased(self):
        ids = ["bloom_weight"]
        values = [0.75]
        before = (tuple(ids), tuple(values))
        result = compose_camera_base_look_v1("raw", ids, values)
        self.assertEqual((tuple(ids), tuple(values)), before)
        ids[0] = "vignette_weight"
        values[0] = 0.25
        self.assertEqual(result.values[CHANNEL_IDS_V1.index("bloom_weight")], 0.75)
        self.assertTrue(result.authored_override_mask[CHANNEL_IDS_V1.index("bloom_weight")])

    def test_invalid_requests_fail_before_publication(self):
        failures = (
            ("missing", (), ()),
            ("raw", ("bloom_weight",), ()),
            ("raw", tuple(CHANNEL_IDS_V1) + ("bloom_weight",), (0.0,) * 14),
            ("raw", ("unknown",), (0.0,)),
            ("raw", ("bloom_weight", "bloom_weight"), (0.1, 0.2)),
            ("raw", ("bloom_weight",), (math.nan,)),
            ("raw", ("bloom_weight",), (math.inf,)),
            ("raw", ("bloom_weight",), (-0.01,)),
            ("raw", ("bloom_weight",), (1.01,)),
            ("raw", ("focal_length_mm",), (0.99,)),
            ("raw", ("exposure_ev",), (20.01,)),
        )
        for arguments in failures:
            with self.subTest(arguments=arguments), self.assertRaises(CameraBaseLookError):
                compose_camera_base_look_v1(*arguments)

    def test_seeded_sparse_composition_is_query_order_independent(self):
        randomizer = random.Random(0xEDD100C)
        cases = []
        for _ in range(80):
            preset_id = randomizer.choice(CAMERA_BASE_LOOK_IDS_V1)
            chosen = randomizer.sample(list(CHANNEL_POLICIES_V1), randomizer.randint(0, 13))
            ids = tuple(policy.channel_id for policy in chosen)
            values = tuple(
                randomizer.uniform(
                    policy.minimum if policy.minimum is not None else -10.0,
                    policy.maximum if policy.maximum is not None else 10.0,
                )
                for policy in chosen
            )
            cases.append((preset_id, ids, values))
        forward = tuple(compose_camera_base_look_v1(*case) for case in cases)
        reverse = tuple(reversed(tuple(compose_camera_base_look_v1(*case) for case in reversed(cases))))
        self.assertEqual(forward, reverse)


if __name__ == "__main__":
    unittest.main(verbosity=2)
