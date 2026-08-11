from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = Path(__file__).with_name("invoke_unreal_remote.py")
SPEC = importlib.util.spec_from_file_location("invoke_unreal_remote", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
REMOTE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REMOTE)


class FakeExecution:
    def __init__(self, nodes):
        self.remote_nodes = nodes


class InvokeUnrealRemoteContracts(unittest.TestCase):
    def test_matching_nodes_is_case_insensitive_and_exact(self):
        nodes = [
            {"node_id": "a", "project_name": "ConanSandbox"},
            {"node_id": "b", "project_name": "conansandbox"},
            {"node_id": "c", "project_name": "ConanSandboxProbe"},
            {"node_id": "d"},
        ]
        self.assertEqual(
            ["a", "b"],
            [node["node_id"] for node in REMOTE.matching_nodes(nodes, "CONANSANDBOX")],
        )

    def test_single_matching_node_is_accepted(self):
        expected = {"node_id": "only", "project_name": "ConanSandbox"}
        actual = REMOTE.wait_for_single_node(
            FakeExecution([expected, {"node_id": "other", "project_name": "Other"}]),
            "ConanSandbox",
            timeout_seconds=0.1,
            poll_seconds=0.001,
        )
        self.assertIs(actual, expected)

    def test_script_source_receives_absolute_file_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory, "remote_script.py").resolve()
            source_path.write_text(
                "from __future__ import annotations\n"
                "FILE_IDENTITY = __file__\n"
                "ANNOTATION: list[str] = []\n",
                encoding="utf-8",
            )
            source = REMOTE.source_for_script(source_path)
            self.assertEqual(source.splitlines()[0], f"__file__ = {str(source_path)!r}")
            self.assertIn("exec(compile(", source)
            self.assertIn(", __file__, 'exec'), globals())", source)
            namespace = {}
            exec(source, namespace)
            self.assertEqual(namespace["FILE_IDENTITY"], str(source_path))
            self.assertEqual(namespace["__annotations__"]["ANNOTATION"], "list[str]")

    def test_ambiguous_matching_nodes_are_rejected(self):
        execution = FakeExecution(
            [
                {"node_id": "first", "project_name": "ConanSandbox"},
                {"node_id": "second", "project_name": "ConanSandbox"},
            ]
        )
        with self.assertRaisesRegex(REMOTE.RemoteInvocationError, "matched 2 of 2"):
            REMOTE.wait_for_single_node(
                execution,
                "ConanSandbox",
                timeout_seconds=0.1,
                poll_seconds=0.001,
            )

    def test_missing_matching_node_is_rejected(self):
        execution = FakeExecution([{"node_id": "other", "project_name": "Other"}])
        with self.assertRaisesRegex(REMOTE.RemoteInvocationError, "matched 0 of 1"):
            REMOTE.wait_for_single_node(
                execution,
                "ConanSandbox",
                timeout_seconds=0.001,
                poll_seconds=0.001,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
