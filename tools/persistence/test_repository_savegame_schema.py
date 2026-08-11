"""Source contract for the Blueprint SaveGame storage adapter."""

from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = ROOT / "repository_savegame_schema.json"


class RepositorySaveGameSchemaContracts(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_asset_slots_and_field_order_are_fixed(self) -> None:
        self.assertEqual(self.schema["schemaVersion"], 1)
        self.assertEqual(self.schema["runtimeIntegrityMode"], "structural-v1")
        self.assertEqual(
            self.schema["virtualPath"],
            "/Game/Mods/ExileDroneDirector/Server/Persistence/SG_EDD_RepositoryStorage",
        )
        self.assertEqual(self.schema["slots"], ["EDD_Repository_A", "EDD_Repository_B"])
        self.assertEqual(
            [field["name"] for field in self.schema["fields"]],
            [
                "RepositorySchemaVersion",
                "Generation",
                "Committed",
                "SnapshotHash",
                "RecordEnvelopes",
                "TombstoneFlypathIds",
            ],
        )

    def test_only_automatable_blueprint_field_kinds_are_used(self) -> None:
        for field in self.schema["fields"]:
            self.assertIn(field["type"], {"Integer", "Boolean", "String"})
            self.assertIn(field["container"], {"None", "Array"})
            if field["container"] == "Array":
                self.assertNotIn("default", field)

    def test_snapshot_contains_opaque_records_and_explicit_tombstones(self) -> None:
        by_name = {field["name"]: field for field in self.schema["fields"]}
        self.assertEqual(by_name["RecordEnvelopes"]["container"], "Array")
        self.assertEqual(by_name["TombstoneFlypathIds"]["container"], "Array")
        self.assertEqual(by_name["Committed"]["default"], False)
        self.assertEqual(by_name["Generation"]["default"], 0)
        self.assertTrue(by_name["SnapshotHash"]["reserved"])
        self.assertEqual(by_name["SnapshotHash"]["default"], "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
