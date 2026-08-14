"""Static safety contract for the live camera application configurator."""

from pathlib import Path
import unittest


SCRIPT = Path(__file__).with_name("Configure-CameraEngineApplication.py").read_text(encoding="utf-8")


class ConfigureCameraEngineApplicationContracts(unittest.TestCase):
    def test_exact_native_struct_classes_are_explicit(self):
        for identity, unreal_class in (
            ("/Script/CinematicCamera.CameraFilmbackSettings", "unreal.CameraFilmbackSettings"),
            ("/Script/CinematicCamera.CameraFocusSettings", "unreal.CameraFocusSettings"),
            ("/Script/Engine.PostProcessSettings", "unreal.PostProcessSettings"),
        ):
            self.assertIn(identity, SCRIPT)
            self.assertIn(unreal_class, SCRIPT)
        self.assertIn("get_struct_type(struct_class.static_struct())", SCRIPT)

    def test_reviewed_manifest_is_the_only_capability_default_source(self):
        self.assertIn('MANIFEST = json.loads', SCRIPT)
        self.assertIn('MANIFEST["engineVersion"]', SCRIPT)
        self.assertIn('MANIFEST["manifestId"]', SCRIPT)
        self.assertIn('MANIFEST["available"]', SCRIPT)

    def test_configurator_is_idempotent_and_non_destructive(self):
        self.assertIn("has_property(name)", SCRIPT)
        self.assertIn("find_graph", SCRIPT)
        self.assertNotIn("remove_function_graph", SCRIPT)
        self.assertNotIn("remove_member_variable", SCRIPT)
        self.assertNotIn("delete_asset", SCRIPT)

    def test_compile_save_and_post_save_verification_are_mandatory(self):
        self.assertGreaterEqual(SCRIPT.count("compile_blueprint"), 3)
        self.assertIn("save_asset", SCRIPT)
        self.assertIn('emit("COMPLETE", True)', SCRIPT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
