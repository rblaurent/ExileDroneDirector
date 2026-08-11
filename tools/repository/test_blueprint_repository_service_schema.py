"""Contracts for the staged-input Blueprint repository service seam."""

from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent
SCHEMA = json.loads((ROOT / "blueprint_repository_service_schema.json").read_text(encoding="utf-8"))


class BlueprintRepositoryServiceSchemaContracts(unittest.TestCase):
    def test_asset_and_runtime_dependencies_are_fixed(self) -> None:
        self.assertEqual(SCHEMA["schemaVersion"], 1)
        self.assertEqual(SCHEMA["runtimeIntegrityMode"], "structural-v1")
        self.assertEqual(SCHEMA["parentClass"], "Actor")
        self.assertEqual(SCHEMA["jsonObjectClass"], "PlayFabJsonObject")
        self.assertEqual(
            SCHEMA["virtualPath"],
            "/Game/Mods/ExileDroneDirector/Server/Repository/BP_EDD_FlypathRepository",
        )
        self.assertIn("ST_EDD_FlypathDocument", " ".join(SCHEMA["dependencies"]))
        self.assertIn("ST_EDD_Waypoint", " ".join(SCHEMA["dependencies"]))
        self.assertIn("ST_EDD_Segment", " ".join(SCHEMA["dependencies"]))
        self.assertIn("SG_EDD_RepositoryStorage", " ".join(SCHEMA["dependencies"]))

    def test_state_request_result_scratch_and_policy_names_do_not_overlap(self) -> None:
        names = [field["name"] for field in SCHEMA["variables"]]
        self.assertEqual(len(names), len(set(names)))
        for prefix in ("Request", "Result", "Scratch"):
            self.assertTrue(any(name.startswith(prefix) for name in names))
        self.assertIn("ActiveRecordEnvelopesV1", names)
        self.assertIn("ActiveTombstoneFlypathIdsV1", names)
        self.assertIn("ActiveFlypathIdsV1", names)
        self.assertIn("CandidateRecordEnvelopesV1", names)
        self.assertIn("CandidateTombstoneFlypathIdsV1", names)
        self.assertIn("RequestDraftDocumentV1", names)
        self.assertIn("ResultDraftDocumentV1", names)

    def test_codec_staging_is_explicit_and_not_aliased_to_request_results(self) -> None:
        by_name = {field["name"]: field for field in SCHEMA["variables"]}
        expected = {
            "ScratchDocumentV1": "ST_EDD_FlypathDocument",
            "ScratchEnvelopeJsonV1": "PlayFabJsonObject",
            "ScratchRecordJsonV1": "PlayFabJsonObject",
            "ScratchDocumentJsonV1": "PlayFabJsonObject",
            "ScratchAttributionJsonV1": "PlayFabJsonObject",
            "ScratchSourceJsonV1": "String",
            "ScratchSourceDocumentJsonV1": "String",
            "ScratchSourceRecordJsonV1": "String",
            "ScratchEncodedDocumentV1": "String",
            "ScratchEncodedRecordV1": "String",
            "ScratchRecordFlypathIdV1": "String",
            "ScratchRecordOwnerAccountIdV1": "String",
            "ScratchRecordVisibilityV1": "String",
            "ScratchRecordDraftRevisionNumberV1": "Integer",
            "ScratchRecordDraftDocumentV1": "ST_EDD_FlypathDocument",
            "ScratchRecordHasPublishedRevisionV1": "Boolean",
            "ScratchRecordPublishedRevisionNumberV1": "Integer",
            "ScratchRecordPublishedDocumentV1": "ST_EDD_FlypathDocument",
            "ScratchRecordHasSourceAttributionV1": "Boolean",
            "ScratchRecordSourceFlypathIdV1": "String",
            "ScratchRecordSourceRevisionNumberV1": "Integer",
        }
        for name, field_type in expected.items():
            self.assertIn(name, by_name)
            self.assertEqual(by_name[name]["type"], field_type)
            self.assertEqual(by_name[name]["container"], "None")
        self.assertEqual(by_name["ScratchRecordVisibilityV1"]["default"], "private")
        self.assertFalse(by_name["ScratchRecordHasPublishedRevisionV1"]["default"])
        self.assertFalse(by_name["ScratchRecordHasSourceAttributionV1"]["default"])
        for name, field_type in (
            ("ScratchWaypointsV1", "ST_EDD_Waypoint"),
            ("ScratchSegmentsV1", "ST_EDD_Segment"),
        ):
            self.assertEqual(by_name[name]["type"], field_type)
            self.assertEqual(by_name[name]["container"], "Array")
        self.assertEqual(by_name["ScratchWaypointV1"]["type"], "ST_EDD_Waypoint")
        self.assertEqual(by_name["ScratchSegmentV1"]["type"], "ST_EDD_Segment")

    def test_decoder_source_staging_is_not_overwritten_by_nested_encoders(self) -> None:
        by_name = {field["name"]: field for field in SCHEMA["variables"]}
        for name in ("ScratchSourceJsonV1", "ScratchSourceDocumentJsonV1"):
            self.assertEqual(by_name[name]["type"], "String")
            self.assertEqual(by_name[name]["container"], "None")
            self.assertEqual(by_name[name]["default"], "")
        self.assertNotEqual("ScratchSourceJsonV1", "ScratchEncodedDocumentV1")
        self.assertNotEqual("ScratchSourceDocumentJsonV1", "ScratchEncodedDocumentV1")

    def test_tombstone_recovery_state_is_explicit_and_aligned(self) -> None:
        by_name = {field["name"]: field for field in SCHEMA["variables"]}
        expected = {
            "ScratchRecoveryTombstoneIdsV1": ("String", "Array"),
            "ScratchRecoveryTombstoneGenerationsV1": ("Integer", "Array"),
            "ScratchRecoveryChannelTombstonesV1": ("String", "Array"),
            "ScratchRecoveryChannelGenerationV1": ("Integer", "None"),
            "ScratchRecoveryChannelSeenIdsV1": ("String", "Array"),
            "ScratchRecoverySearchStringsV1": ("String", "Array"),
            "ScratchRecoverySearchValueV1": ("String", "None"),
            "ScratchRecoverySearchIndexV1": ("Integer", "None"),
            "ScratchRecoveryCurrentTombstoneV1": ("String", "None"),
            "ScratchRecoveryTrimmedTombstoneV1": ("String", "None"),
        }
        for name, (field_type, container) in expected.items():
            self.assertIn(name, by_name)
            self.assertEqual(by_name[name]["type"], field_type)
            self.assertEqual(by_name[name]["container"], container)
        self.assertEqual(by_name["ScratchRecoverySearchIndexV1"]["default"], -1)
        self.assertEqual(by_name["ScratchRecoveryChannelGenerationV1"]["default"], 0)

    def test_record_recovery_state_is_explicit_and_metadata_aligned(self) -> None:
        by_name = {field["name"]: field for field in SCHEMA["variables"]}
        arrays = (
            "ScratchRecoveryRecordEnvelopesV1",
            "ScratchRecoveryRecordFlypathIdsV1",
            "ScratchRecoveryRecordOwnerAccountIdsV1",
            "ScratchRecoveryRecordVisibilitiesV1",
            "ScratchRecoveryRecordUpdatedUtcV1",
            "ScratchRecoveryChannelRecordEnvelopesV1",
            "ScratchRecoveryChannelSeenRecordIdsV1",
            "ScratchRecoveryChannelAmbiguousRecordIdsV1",
        )
        for name in arrays:
            self.assertEqual(by_name[name]["type"], "String")
            self.assertEqual(by_name[name]["container"], "Array")
        self.assertEqual(by_name["ScratchRecoveryChannelRecordGenerationV1"]["type"], "Integer")
        self.assertEqual(by_name["ScratchRecoveryChannelRecordGenerationV1"]["default"], 0)
        self.assertEqual(by_name["ScratchRecoveryCurrentRecordEnvelopeV1"]["type"], "String")
        self.assertEqual(by_name["ScratchRecoveryCurrentRecordEnvelopeV1"]["default"], "")

    def test_only_automatable_variable_types_are_used(self) -> None:
        supported = {
            "Boolean",
            "Integer",
            "Real",
            "String",
            "ST_EDD_FlypathDocument",
            "ST_EDD_Waypoint",
            "ST_EDD_Segment",
            "PlayFabJsonObject",
            "SG_EDD_RepositoryStorage",
        }
        for field in SCHEMA["variables"]:
            self.assertIn(field["type"], supported)
            self.assertIn(field["container"], {"None", "Array"})
            if field["container"] == "Array":
                self.assertNotIn("default", field)

    def test_real_type_uses_the_devkit_supported_basic_type_key(self) -> None:
        configurator = (
            ROOT.parent / "unreal" / "Configure-RepositoryService.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            '"Real": unreal.BlueprintEditorLibrary.get_basic_type_by_name("real")',
            configurator,
        )
        self.assertNotIn(
            '"Real": unreal.BlueprintEditorLibrary.get_basic_type_by_name("double")',
            configurator,
        )
        self.assertIn("expected_basic_pin_fragments", configurator)

    def test_crud_and_codec_function_boundaries_are_explicit(self) -> None:
        functions = SCHEMA["functions"]
        self.assertEqual(len(functions), len(set(functions)))
        for required in (
            "ResetRepositoryStateV1",
            "ValidateStorageHeadersV1",
            "PreparePersistenceCandidateV1",
            "CommitPersistenceCandidateV1",
            "LoadRepositoryV1",
            "PersistRepositoryV1",
            "RebuildMetadataIndexV1",
            "EncodeWaypointV1",
            "DecodeWaypointV1",
            "EncodeSegmentV1",
            "DecodeSegmentV1",
            "EncodeDocumentV1",
            "DecodeDocumentV1",
            "EncodeRecordPublishedFieldsV1",
            "EncodeRecordSourceAttributionV1",
            "EncodeRecordV1",
            "DecodeRecordPublishedFieldsV1",
            "DecodeRecordSourceAttributionV1",
            "DecodeRecordV1",
            "ValidateWaypointV1",
            "ValidateSegmentV1",
            "ValidateDocumentV1",
            "ValidateRecordPublishedV1",
            "ValidateRecordSourceAttributionV1",
            "ValidateRecordV1",
            "ResetRecoveryTombstonesV1",
            "FindRecoveryStringIndexV1",
            "ValidateRecoveryTombstoneChannelV1",
            "MergeRecoveryTombstonesV1",
            "ResetRecoveryRecordsV1",
            "DecodeValidateRecoveryEnvelopeV1",
            "ScanRecoveryRecordIdentityV1",
            "AppendRecoveryRecordIfNewV1",
            "TryMergeRecoveryRecordV1",
            "RecoverRecordChannelV1",
            "RecoverRepositoryRecordsV1",
            "CommitRecoveredRepositoryV1",
            "CreatePrivateFlypathV1",
            "SaveDraftV1",
            "LoadDraftV1",
            "ListMineV1",
            "DeleteFlypathV1",
        ):
            self.assertIn(required, functions)

    def test_server_policy_defaults_are_bounded(self) -> None:
        by_name = {field["name"]: field for field in SCHEMA["variables"]}
        self.assertEqual(by_name["MaxPathsPerOwnerV1"]["default"], 64)
        self.assertEqual(by_name["MaxWaypointsPerPathV1"]["default"], 512)
        self.assertEqual(by_name["MaxSerializedBytesV1"]["default"], 2_000_000)
        self.assertEqual(by_name["MaxTitleCharsV1"]["default"], 96)
        self.assertEqual(SCHEMA["arrayDefaults"]["AllowedRegionsV1"], ["ExiledLands", "Siptah"])

    def test_hash_scratch_is_reserved_in_structural_mode(self) -> None:
        by_name = {field["name"]: field for field in SCHEMA["variables"]}
        self.assertTrue(by_name["CandidateSnapshotHashV1"]["reserved"])
        self.assertEqual(by_name["CandidateSnapshotHashV1"]["default"], "")

    def test_result_codes_match_the_repository_oracle(self) -> None:
        self.assertEqual(
            SCHEMA["resultCodes"],
            [
                "Success",
                "NotFound",
                "Forbidden",
                "RevisionConflict",
                "ValidationFailed",
                "LimitExceeded",
                "RegionForbidden",
                "PersistenceUnavailable",
                "AlreadyExists",
            ],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
