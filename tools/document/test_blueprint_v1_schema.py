"""Contracts for the authored version-1 Blueprint document schema."""

from __future__ import annotations

from dataclasses import fields
import json
from pathlib import Path
import unittest

from flypath_document import FlypathRecord, RevisionDocument, Segment, SourceAttribution
from flypath_repository import FlypathMetadata, RepositoryLimits, ResultCode


ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = ROOT / "blueprint_v1_schema.json"


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


class BlueprintV1SchemaContracts(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = load_schema()
        self.structs = self.schema["structs"]

    def field_names(self, struct_name: str) -> list[str]:
        return [field["name"] for field in self.structs[struct_name]["fields"]]

    def test_schema_and_struct_order_are_fixed(self) -> None:
        self.assertEqual(self.schema["schemaVersion"], 1)
        self.assertEqual(self.schema["repositorySchemaVersion"], 1)
        self.assertEqual(
            list(self.structs),
            [
                "ST_EDD_Waypoint",
                "ST_EDD_Segment",
                "ST_EDD_FlypathDocument",
                "ST_EDD_SourceAttribution",
                "ST_EDD_FlypathRecord",
                "ST_EDD_FlypathMetadata",
                "ST_EDD_RepositoryResult",
                "ST_EDD_ServerPolicy",
                "ST_EDD_PersistedGeneration",
            ],
        )
        for name, definition in self.structs.items():
            names = [field["name"] for field in definition["fields"]]
            self.assertEqual(len(names), len(set(names)), f"{name} has duplicate fields")

    def test_waypoint_struct_preserves_the_proven_six_field_bridge(self) -> None:
        self.assertEqual(
            self.field_names("ST_EDD_Waypoint"),
            [
                "WaypointId",
                "CameraTransform",
                "FocalLength",
                "Aperture",
                "ManualFocusDistance",
                "HoldSeconds",
            ],
        )

    def test_segment_struct_maps_every_oracle_field(self) -> None:
        oracle_fields = [field.name for field in fields(Segment)]
        self.assertEqual(
            oracle_fields,
            [
                "segment_id",
                "from_waypoint_id",
                "to_waypoint_id",
                "duration_seconds",
                "spatial_curve_type",
                "time_profile",
            ],
        )
        self.assertEqual(
            self.field_names("ST_EDD_Segment"),
            [
                "SegmentId",
                "FromWaypointId",
                "ToWaypointId",
                "DurationSeconds",
                "SpatialCurveType",
                "TimeProfile",
            ],
        )

    def test_document_struct_maps_the_revision_payload(self) -> None:
        self.assertEqual(
            [field.name for field in fields(RevisionDocument)],
            [
                "revision_number",
                "region_id",
                "waypoints",
                "segments",
                "duration_seconds",
                "default_flight_profile",
                "schema_version",
                "trajectory_engine_version",
                "content_hash",
            ],
        )
        self.assertEqual(
            self.field_names("ST_EDD_FlypathDocument"),
            [
                "SchemaVersion",
                "TrajectoryEngineVersion",
                "RevisionNumber",
                "RegionId",
                "DurationSeconds",
                "DefaultFlightProfile",
                "Waypoints",
                "Segments",
                "ContentHash",
            ],
        )

    def test_nested_arrays_and_client_seams_are_exact(self) -> None:
        document_fields = {
            field["name"]: field for field in self.structs["ST_EDD_FlypathDocument"]["fields"]
        }
        self.assertEqual(document_fields["Waypoints"], {
            "name": "Waypoints",
            "type": "ST_EDD_Waypoint",
            "container": "Array",
        })
        self.assertEqual(document_fields["Segments"], {
            "name": "Segments",
            "type": "ST_EDD_Segment",
            "container": "Array",
        })
        self.assertEqual(
            self.schema["clientVariables"],
            [
                {"name": "DraftWaypointsV1", "type": "ST_EDD_Waypoint", "container": "Array"},
                {"name": "DraftSegmentsV1", "type": "ST_EDD_Segment", "container": "Array"},
                {"name": "DraftDocumentV1", "type": "ST_EDD_FlypathDocument", "container": "None"},
            ],
        )

    def test_only_supported_blueprint_field_kinds_are_used(self) -> None:
        supported = {
            "Integer",
            "Float",
            "Boolean",
            "String",
            "Transform",
            "ST_EDD_Waypoint",
            "ST_EDD_Segment",
            "ST_EDD_FlypathDocument",
            "ST_EDD_SourceAttribution",
        }
        for definition in self.structs.values():
            for field in definition["fields"]:
                self.assertIn(field["type"], supported)
                self.assertIn(field["container"], {"None", "Array"})

    def test_repository_structs_map_oracle_seams_without_nullable_fields(self) -> None:
        self.assertEqual(
            [field.name for field in fields(SourceAttribution)],
            ["flypath_id", "revision_number", "title", "creator_display_name"],
        )
        self.assertEqual(
            [field.name for field in fields(FlypathRecord)],
            [
                "flypath_id",
                "owner_account_id",
                "owner_display_name",
                "title",
                "description",
                "visibility",
                "region_id",
                "created_utc",
                "updated_utc",
                "draft_revision_number",
                "draft",
                "published_revision_number",
                "published",
                "source_attribution",
            ],
        )
        record_fields = self.field_names("ST_EDD_FlypathRecord")
        self.assertEqual(
            record_fields,
            [
                "FlypathId",
                "OwnerAccountId",
                "OwnerDisplayName",
                "Title",
                "Description",
                "Visibility",
                "RegionId",
                "CreatedUtc",
                "UpdatedUtc",
                "DraftRevisionNumber",
                "Draft",
                "HasPublishedRevision",
                "PublishedRevisionNumber",
                "Published",
                "HasSourceAttribution",
                "SourceAttribution",
            ],
        )
        self.assertLess(record_fields.index("HasPublishedRevision"), record_fields.index("Published"))
        self.assertLess(record_fields.index("HasSourceAttribution"), record_fields.index("SourceAttribution"))

    def test_metadata_policy_and_result_code_contracts_are_exact(self) -> None:
        self.assertEqual(
            [field.name for field in fields(FlypathMetadata)],
            [
                "flypath_id",
                "owner_display_name",
                "title",
                "visibility",
                "region_id",
                "updated_utc",
                "draft_revision_number",
                "published_revision_number",
            ],
        )
        self.assertEqual(
            self.schema["repositoryResultCodes"],
            [code.value for code in ResultCode],
        )
        policy = RepositoryLimits()
        policy_fields = {field["name"]: field for field in self.structs["ST_EDD_ServerPolicy"]["fields"]}
        self.assertEqual(policy_fields["MaxPathsPerOwner"]["default"], policy.max_paths_per_owner)
        self.assertEqual(policy_fields["MaxWaypointsPerPath"]["default"], policy.max_waypoints_per_path)
        self.assertEqual(policy_fields["MaxSerializedBytes"]["default"], policy.max_serialized_bytes)
        self.assertEqual(policy_fields["MaxTitleChars"]["default"], policy.max_title_chars)

    def test_metadata_struct_carries_no_revision_payload(self) -> None:
        field_types = [field["type"] for field in self.structs["ST_EDD_FlypathMetadata"]["fields"]]
        self.assertNotIn("ST_EDD_FlypathDocument", field_types)

    def test_segment_field_types_containers_and_defaults_are_exact(self) -> None:
        self.assertEqual(
            self.structs["ST_EDD_Segment"]["fields"],
            [
                {"name": "SegmentId", "type": "Integer", "container": "None", "default": 0},
                {"name": "FromWaypointId", "type": "Integer", "container": "None", "default": 0},
                {"name": "ToWaypointId", "type": "Integer", "container": "None", "default": 0},
                {"name": "DurationSeconds", "type": "Float", "container": "None", "default": 3.0},
                {"name": "SpatialCurveType", "type": "String", "container": "None", "default": "linear"},
                {"name": "TimeProfile", "type": "String", "container": "None", "default": "linear"},
            ],
        )

    def test_document_field_types_containers_and_defaults_are_exact(self) -> None:
        self.assertEqual(
            self.structs["ST_EDD_FlypathDocument"]["fields"],
            [
                {"name": "SchemaVersion", "type": "Integer", "container": "None", "default": 1},
                {"name": "TrajectoryEngineVersion", "type": "Integer", "container": "None", "default": 1},
                {"name": "RevisionNumber", "type": "Integer", "container": "None", "default": 0},
                {"name": "RegionId", "type": "String", "container": "None", "default": ""},
                {"name": "DurationSeconds", "type": "Float", "container": "None", "default": 0.0},
                {
                    "name": "DefaultFlightProfile",
                    "type": "String",
                    "container": "None",
                    "default": "cinematic_drone",
                },
                {"name": "Waypoints", "type": "ST_EDD_Waypoint", "container": "Array"},
                {"name": "Segments", "type": "ST_EDD_Segment", "container": "Array"},
                {"name": "ContentHash", "type": "String", "container": "None", "default": ""},
            ],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
