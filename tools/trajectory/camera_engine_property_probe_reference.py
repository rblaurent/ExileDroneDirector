"""Deterministic resolver for camera-property reflection observations."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Mapping

from camera_engine_application_reference import (
    TARGET_IDS_V1,
    CameraEngineCapabilitySnapshotV1,
)


CANDIDATE_PATH = Path(__file__).with_name("camera_engine_property_candidates_v1.json")


class CameraEnginePropertyProbeError(ValueError):
    pass


@dataclass(frozen=True)
class CameraEnginePropertyObservationV1:
    readable: bool
    same_value_writable: bool
    value_type: str


@dataclass(frozen=True)
class CameraEngineResolvedManifestV1:
    capabilities: CameraEngineCapabilitySnapshotV1
    selected_value_paths: tuple[str, ...]
    selected_override_paths: tuple[str, ...]
    missing_required_target_ids: tuple[str, ...]
    canonical_json: str


def load_camera_engine_property_candidates_v1(path: Path = CANDIDATE_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_candidates(schema: dict) -> tuple[dict, ...]:
    if schema.get("schema") != "edd.camera-engine-property-candidates.v1" or schema.get("version") != 1:
        raise CameraEnginePropertyProbeError("unsupported_candidate_schema")
    targets = schema.get("targets")
    if not isinstance(targets, list) or tuple(item.get("id") for item in targets) != TARGET_IDS_V1:
        raise CameraEnginePropertyProbeError("candidate_target_order")
    owned_paths: set[str] = set()
    for target in targets:
        if not isinstance(target.get("required"), bool):
            raise CameraEnginePropertyProbeError("candidate_required_type")
        if target.get("expectedType") != "float":
            raise CameraEnginePropertyProbeError("candidate_value_type")
        if not isinstance(target.get("candidates"), list):
            raise CameraEnginePropertyProbeError("candidate_list_type")
        for candidate in target["candidates"]:
            value_path = candidate.get("valuePath")
            if not isinstance(value_path, str) or not value_path:
                raise CameraEnginePropertyProbeError("candidate_value_path")
            if value_path in owned_paths:
                raise CameraEnginePropertyProbeError("candidate_value_alias")
            owned_paths.add(value_path)
            override_path = candidate.get("overridePath", "")
            if not isinstance(override_path, str):
                raise CameraEnginePropertyProbeError("candidate_override_path")
            if override_path:
                if override_path in owned_paths:
                    raise CameraEnginePropertyProbeError("candidate_override_alias")
                owned_paths.add(override_path)
    return tuple(targets)


def _usable(observation: object, expected_type: str) -> bool:
    return (
        isinstance(observation, CameraEnginePropertyObservationV1)
        and observation.readable
        and observation.same_value_writable
        and observation.value_type == expected_type
    )


def resolve_camera_engine_property_manifest_v1(
    engine_version: str,
    observations: Mapping[str, CameraEnginePropertyObservationV1],
    candidate_schema: dict | None = None,
) -> CameraEngineResolvedManifestV1:
    if not isinstance(engine_version, str) or not engine_version.strip():
        raise CameraEnginePropertyProbeError("invalid_engine_version")
    schema = load_camera_engine_property_candidates_v1() if candidate_schema is None else candidate_schema
    targets = _validate_candidates(schema)
    available: list[bool] = []
    selected_values: list[str] = []
    selected_overrides: list[str] = []
    missing_required: list[str] = []
    for target in targets:
        selected_value = ""
        selected_override = ""
        for candidate in target["candidates"]:
            value_path = candidate["valuePath"]
            override_path = candidate.get("overridePath", "")
            if not _usable(observations.get(value_path), target["expectedType"]):
                continue
            if override_path and not _usable(observations.get(override_path), "bool"):
                continue
            selected_value = value_path
            selected_override = override_path
            break
        is_available = bool(selected_value)
        available.append(is_available)
        selected_values.append(selected_value)
        selected_overrides.append(selected_override)
        if target["required"] and not is_available:
            missing_required.append(target["id"])

    payload = {
        "schema": "edd.camera-engine-property-manifest.v1",
        "candidateSchema": schema["schema"],
        "candidateVersion": schema["version"],
        "engineVersion": engine_version,
        "targetIds": list(TARGET_IDS_V1),
        "available": available,
        "selectedValuePaths": selected_values,
        "selectedOverridePaths": selected_overrides,
        "missingRequiredTargetIds": missing_required,
    }
    identity_source = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    manifest_id = hashlib.sha256(identity_source.encode("utf-8")).hexdigest().upper()
    payload["manifestId"] = manifest_id
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    capabilities = CameraEngineCapabilitySnapshotV1(
        engine_version,
        manifest_id,
        TARGET_IDS_V1,
        tuple(available),
    )
    return CameraEngineResolvedManifestV1(
        capabilities,
        tuple(selected_values),
        tuple(selected_overrides),
        tuple(missing_required),
        canonical_json,
    )
