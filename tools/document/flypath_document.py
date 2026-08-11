"""Engine-independent Flypath document, persistence, and ownership contract.

The cooked mod remains Blueprint-only.  This module is the executable oracle
for the Blueprint structs and server repository that will implement the same
rules: canonical serialization, immutable publication, optimistic draft saves,
private-by-default creation/cloning, and document-scoped stable waypoint IDs.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
from math import isfinite, sqrt
from typing import Any, Iterable, Literal


SCHEMA_VERSION = 1
TRAJECTORY_ENGINE_VERSION = 1
REPOSITORY_SCHEMA_VERSION = 1
RUNTIME_INTEGRITY_MODE = "structural-v1"
Visibility = Literal["private", "public"]
Vector3 = tuple[float, float, float]
Quaternion = tuple[float, float, float, float]


class DocumentValidationError(ValueError):
    """The document is malformed, unsafe, or internally inconsistent."""


class RevisionConflictError(ValueError):
    """A save was based on a draft revision that is no longer current."""


@dataclass(frozen=True)
class LensState:
    focal_length_mm: float = 35.0
    aperture: float = 2.8
    focus_distance_cm: float = 1000.0


@dataclass(frozen=True)
class Waypoint:
    waypoint_id: int
    position: Vector3
    body_rotation: Quaternion
    gimbal_rotation: Quaternion
    lens: LensState = LensState()
    hold_seconds: float = 0.0
    corner_mode: str = "glide"
    annotation: str = ""


@dataclass(frozen=True)
class Segment:
    segment_id: int
    from_waypoint_id: int
    to_waypoint_id: int
    duration_seconds: float = 3.0
    spatial_curve_type: str = "linear"
    time_profile: str = "linear"


@dataclass(frozen=True)
class RevisionDocument:
    revision_number: int
    region_id: str
    waypoints: tuple[Waypoint, ...] = ()
    segments: tuple[Segment, ...] = ()
    duration_seconds: float = 0.0
    default_flight_profile: str = "cinematic_drone"
    schema_version: int = SCHEMA_VERSION
    trajectory_engine_version: int = TRAJECTORY_ENGINE_VERSION
    content_hash: str = ""


@dataclass(frozen=True)
class SourceAttribution:
    flypath_id: str
    revision_number: int
    title: str
    creator_display_name: str


@dataclass(frozen=True)
class FlypathRecord:
    flypath_id: str
    owner_account_id: str
    owner_display_name: str
    title: str
    description: str
    visibility: Visibility
    region_id: str
    created_utc: str
    updated_utc: str
    draft_revision_number: int
    draft: RevisionDocument
    published_revision_number: int | None = None
    published: RevisionDocument | None = None
    source_attribution: SourceAttribution | None = None


def _require_text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DocumentValidationError(f"{field} must be non-empty text")


def _require_finite(values: Iterable[float], field: str) -> None:
    if not all(isfinite(float(value)) for value in values):
        raise DocumentValidationError(f"{field} contains a non-finite value")


def _validate_quaternion(value: Quaternion, field: str) -> None:
    if len(value) != 4:
        raise DocumentValidationError(f"{field} must contain four components")
    _require_finite(value, field)
    magnitude = sqrt(sum(float(component) ** 2 for component in value))
    if abs(magnitude - 1.0) > 1.0e-4:
        raise DocumentValidationError(f"{field} must be normalized")


def _parse_utc_text(value: str, field: str) -> datetime:
    _require_text(value, field)
    if not value.endswith("Z"):
        raise DocumentValidationError(f"{field} must be canonical UTC text")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise DocumentValidationError(f"{field} must be canonical UTC text") from error
    if utc_text(parsed) != value:
        raise DocumentValidationError(f"{field} must be canonical UTC text")
    return parsed


def validate_document(document: RevisionDocument) -> None:
    if document.schema_version != SCHEMA_VERSION:
        raise DocumentValidationError(f"unsupported schema version {document.schema_version}")
    if document.trajectory_engine_version != TRAJECTORY_ENGINE_VERSION:
        raise DocumentValidationError(
            f"unsupported trajectory engine version {document.trajectory_engine_version}"
        )
    if document.revision_number < 1:
        raise DocumentValidationError("revision number must be positive")
    _require_text(document.region_id, "region_id")
    _require_text(document.default_flight_profile, "default_flight_profile")
    _require_finite((document.duration_seconds,), "duration_seconds")
    if document.duration_seconds < 0.0:
        raise DocumentValidationError("duration_seconds cannot be negative")

    waypoint_ids: set[int] = set()
    for index, waypoint in enumerate(document.waypoints):
        if waypoint.waypoint_id <= 0 or waypoint.waypoint_id in waypoint_ids:
            raise DocumentValidationError("waypoint IDs must be positive and unique")
        waypoint_ids.add(waypoint.waypoint_id)
        _require_finite(waypoint.position, f"waypoints[{index}].position")
        _validate_quaternion(waypoint.body_rotation, f"waypoints[{index}].body_rotation")
        _validate_quaternion(waypoint.gimbal_rotation, f"waypoints[{index}].gimbal_rotation")
        _require_finite(
            (
                waypoint.lens.focal_length_mm,
                waypoint.lens.aperture,
                waypoint.lens.focus_distance_cm,
                waypoint.hold_seconds,
            ),
            f"waypoints[{index}].camera",
        )
        if waypoint.lens.focal_length_mm <= 0.0 or waypoint.lens.aperture <= 0.0:
            raise DocumentValidationError("focal length and aperture must be positive")
        if waypoint.lens.focus_distance_cm < 0.0 or waypoint.hold_seconds < 0.0:
            raise DocumentValidationError("focus distance and hold cannot be negative")
        _require_text(waypoint.corner_mode, f"waypoints[{index}].corner_mode")

    expected_segments = max(0, len(document.waypoints) - 1)
    if len(document.segments) != expected_segments:
        raise DocumentValidationError(
            f"expected {expected_segments} segments for {len(document.waypoints)} waypoints"
        )
    segment_ids: set[int] = set()
    calculated_duration = sum(waypoint.hold_seconds for waypoint in document.waypoints)
    for index, segment in enumerate(document.segments):
        if segment.segment_id <= 0 or segment.segment_id in segment_ids:
            raise DocumentValidationError("segment IDs must be positive and unique")
        segment_ids.add(segment.segment_id)
        expected_from = document.waypoints[index].waypoint_id
        expected_to = document.waypoints[index + 1].waypoint_id
        if (segment.from_waypoint_id, segment.to_waypoint_id) != (expected_from, expected_to):
            raise DocumentValidationError(f"segment {segment.segment_id} does not join adjacent waypoints")
        _require_finite((segment.duration_seconds,), f"segments[{index}].duration_seconds")
        if segment.duration_seconds <= 0.0:
            raise DocumentValidationError("segment duration must be positive")
        _require_text(segment.spatial_curve_type, f"segments[{index}].spatial_curve_type")
        _require_text(segment.time_profile, f"segments[{index}].time_profile")
        calculated_duration += segment.duration_seconds

    if abs(calculated_duration - document.duration_seconds) > 1.0e-6:
        raise DocumentValidationError(
            f"cached duration {document.duration_seconds} does not match {calculated_duration}"
        )
    if document.content_hash != "":
        raise DocumentValidationError(
            "ContentHash is reserved and must be empty in structural-v1"
        )


def validate_record(record: FlypathRecord) -> None:
    for value, field in (
        (record.flypath_id, "flypath_id"),
        (record.owner_account_id, "owner_account_id"),
        (record.title, "title"),
        (record.region_id, "region_id"),
    ):
        _require_text(value, field)
    if record.visibility not in ("private", "public"):
        raise DocumentValidationError(f"unsupported visibility {record.visibility}")
    created = _parse_utc_text(record.created_utc, "created_utc")
    updated = _parse_utc_text(record.updated_utc, "updated_utc")
    if updated < created:
        raise DocumentValidationError("updated_utc cannot precede created_utc")
    if record.draft.region_id != record.region_id:
        raise DocumentValidationError("draft region does not match its Flypath record")
    if record.draft.revision_number != record.draft_revision_number:
        raise DocumentValidationError("draft revision does not match its Flypath record")
    validate_document(record.draft)

    published_pair = (record.published_revision_number is not None, record.published is not None)
    if published_pair[0] != published_pair[1]:
        raise DocumentValidationError("published revision number and payload must be present together")
    if record.visibility == "public" and record.published is None:
        raise DocumentValidationError("a public Flypath requires a published snapshot")
    if record.published is not None:
        if record.published.region_id != record.region_id:
            raise DocumentValidationError("published region does not match its Flypath record")
        if record.published.revision_number != record.published_revision_number:
            raise DocumentValidationError("published revision does not match its Flypath record")
        if record.published.revision_number > record.draft_revision_number:
            raise DocumentValidationError("published revision cannot exceed the draft revision")
        validate_document(record.published)
    if record.source_attribution is not None:
        _require_text(record.source_attribution.flypath_id, "source_attribution.flypath_id")
        _require_text(record.source_attribution.title, "source_attribution.title")
        if record.source_attribution.revision_number < 1:
            raise DocumentValidationError("source attribution revision must be positive")


def _document_payload(document: RevisionDocument, *, include_hash: bool) -> dict[str, Any]:
    payload = {
        "schemaVersion": document.schema_version,
        "trajectoryEngineVersion": document.trajectory_engine_version,
        "revisionNumber": document.revision_number,
        "regionId": document.region_id,
        "durationSeconds": document.duration_seconds,
        "defaultFlightProfile": document.default_flight_profile,
        "waypoints": [
            {
                "waypointId": waypoint.waypoint_id,
                "position": list(waypoint.position),
                "bodyRotation": list(waypoint.body_rotation),
                "gimbalRotation": list(waypoint.gimbal_rotation),
                "lens": {
                    "focalLengthMm": waypoint.lens.focal_length_mm,
                    "aperture": waypoint.lens.aperture,
                    "focusDistanceCm": waypoint.lens.focus_distance_cm,
                },
                "holdSeconds": waypoint.hold_seconds,
                "cornerMode": waypoint.corner_mode,
                "annotation": waypoint.annotation,
            }
            for waypoint in document.waypoints
        ],
        "segments": [
            {
                "segmentId": segment.segment_id,
                "fromWaypointId": segment.from_waypoint_id,
                "toWaypointId": segment.to_waypoint_id,
                "durationSeconds": segment.duration_seconds,
                "spatialCurveType": segment.spatial_curve_type,
                "timeProfile": segment.time_profile,
            }
            for segment in document.segments
        ],
    }
    if include_hash:
        payload["contentHash"] = document.content_hash
    return payload


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))


def _require_exact_keys(payload: Any, expected: set[str], field: str) -> None:
    if not isinstance(payload, dict):
        raise DocumentValidationError(f"{field} must be an object")
    actual = set(payload)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise DocumentValidationError(
            f"{field} fields do not match schema; missing={missing}, extra={extra}"
        )


def _reject_duplicate_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DocumentValidationError(f"duplicate JSON field {key}")
        result[key] = value
    return result


def seal_document(document: RevisionDocument) -> RevisionDocument:
    sealed = replace(document, content_hash="")
    validate_document(sealed)
    return sealed


def serialize_document(document: RevisionDocument) -> str:
    validate_document(document)
    return canonical_json(_document_payload(document, include_hash=True))


def _attribution_payload(attribution: SourceAttribution) -> dict[str, Any]:
    return {
        "flypathId": attribution.flypath_id,
        "revisionNumber": attribution.revision_number,
        "title": attribution.title,
        "creatorDisplayName": attribution.creator_display_name,
    }


def _record_payload(record: FlypathRecord) -> dict[str, Any]:
    return {
        "flypathId": record.flypath_id,
        "ownerAccountId": record.owner_account_id,
        "ownerDisplayName": record.owner_display_name,
        "title": record.title,
        "description": record.description,
        "visibility": record.visibility,
        "regionId": record.region_id,
        "createdUtc": record.created_utc,
        "updatedUtc": record.updated_utc,
        "draftRevisionNumber": record.draft_revision_number,
        "draft": _document_payload(record.draft, include_hash=True),
        "publishedRevisionNumber": record.published_revision_number,
        "published": (
            _document_payload(record.published, include_hash=True)
            if record.published is not None
            else None
        ),
        "sourceAttribution": (
            _attribution_payload(record.source_attribution)
            if record.source_attribution is not None
            else None
        ),
    }


def serialize_record(record: FlypathRecord) -> str:
    """Serialize one complete repository record in canonical form."""

    validate_record(record)
    payload = _record_payload(record)
    return canonical_json(
        {
            "integrityMode": RUNTIME_INTEGRITY_MODE,
            "recordContentHash": "",
            "repositorySchemaVersion": REPOSITORY_SCHEMA_VERSION,
            "record": payload,
        }
    )


def deserialize_document(text: str) -> RevisionDocument:
    try:
        payload = json.loads(text, object_pairs_hook=_reject_duplicate_object_pairs)
        _require_exact_keys(
            payload,
            {
                "schemaVersion",
                "trajectoryEngineVersion",
                "revisionNumber",
                "regionId",
                "durationSeconds",
                "defaultFlightProfile",
                "waypoints",
                "segments",
                "contentHash",
            },
            "document",
        )
        if not isinstance(payload["waypoints"], list) or not isinstance(payload["segments"], list):
            raise DocumentValidationError("document waypoints and segments must be arrays")
        for index, item in enumerate(payload["waypoints"]):
            _require_exact_keys(
                item,
                {
                    "waypointId",
                    "position",
                    "bodyRotation",
                    "gimbalRotation",
                    "lens",
                    "holdSeconds",
                    "cornerMode",
                    "annotation",
                },
                f"waypoints[{index}]",
            )
            _require_exact_keys(
                item["lens"],
                {"focalLengthMm", "aperture", "focusDistanceCm"},
                f"waypoints[{index}].lens",
            )
        for index, item in enumerate(payload["segments"]):
            _require_exact_keys(
                item,
                {
                    "segmentId",
                    "fromWaypointId",
                    "toWaypointId",
                    "durationSeconds",
                    "spatialCurveType",
                    "timeProfile",
                },
                f"segments[{index}]",
            )
        waypoints = tuple(
            Waypoint(
                waypoint_id=item["waypointId"],
                position=tuple(item["position"]),
                body_rotation=tuple(item["bodyRotation"]),
                gimbal_rotation=tuple(item["gimbalRotation"]),
                lens=LensState(
                    focal_length_mm=item["lens"]["focalLengthMm"],
                    aperture=item["lens"]["aperture"],
                    focus_distance_cm=item["lens"]["focusDistanceCm"],
                ),
                hold_seconds=item["holdSeconds"],
                corner_mode=item["cornerMode"],
                annotation=item.get("annotation", ""),
            )
            for item in payload["waypoints"]
        )
        segments = tuple(
            Segment(
                segment_id=item["segmentId"],
                from_waypoint_id=item["fromWaypointId"],
                to_waypoint_id=item["toWaypointId"],
                duration_seconds=item["durationSeconds"],
                spatial_curve_type=item["spatialCurveType"],
                time_profile=item["timeProfile"],
            )
            for item in payload["segments"]
        )
        document = RevisionDocument(
            schema_version=payload["schemaVersion"],
            trajectory_engine_version=payload["trajectoryEngineVersion"],
            revision_number=payload["revisionNumber"],
            region_id=payload["regionId"],
            duration_seconds=payload["durationSeconds"],
            default_flight_profile=payload["defaultFlightProfile"],
            waypoints=waypoints,
            segments=segments,
            content_hash=payload["contentHash"],
        )
    except DocumentValidationError:
        raise
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise DocumentValidationError(f"invalid serialized Flypath document: {error}") from error
    validate_document(document)
    if canonical_json(payload) != text:
        raise DocumentValidationError("serialized Flypath document is not canonical JSON")
    return document


def _document_from_payload(payload: dict[str, Any]) -> RevisionDocument:
    return deserialize_document(canonical_json(payload))


def deserialize_record(text: str) -> FlypathRecord:
    """Parse and validate one complete repository record."""

    try:
        envelope = json.loads(text, object_pairs_hook=_reject_duplicate_object_pairs)
        _require_exact_keys(
            envelope,
            {"integrityMode", "record", "recordContentHash", "repositorySchemaVersion"},
            "record root",
        )
        if envelope["repositorySchemaVersion"] != REPOSITORY_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported repository schema version {envelope['repositorySchemaVersion']}"
            )
        payload = envelope["record"]
        _require_exact_keys(
            payload,
            {
                "flypathId",
                "ownerAccountId",
                "ownerDisplayName",
                "title",
                "description",
                "visibility",
                "regionId",
                "createdUtc",
                "updatedUtc",
                "draftRevisionNumber",
                "draft",
                "publishedRevisionNumber",
                "published",
                "sourceAttribution",
            },
            "record",
        )
        if envelope["integrityMode"] != RUNTIME_INTEGRITY_MODE:
            raise ValueError(f"unsupported integrity mode {envelope['integrityMode']}")
        if envelope["recordContentHash"] != "":
            raise ValueError("recordContentHash is reserved and must be empty in structural-v1")
        attribution_payload = payload.get("sourceAttribution")
        if attribution_payload is not None and not isinstance(attribution_payload, dict):
            raise TypeError("sourceAttribution must be an object or null")
        if attribution_payload is not None:
            _require_exact_keys(
                attribution_payload,
                {"flypathId", "revisionNumber", "title", "creatorDisplayName"},
                "sourceAttribution",
            )
        attribution = (
            SourceAttribution(
                flypath_id=attribution_payload["flypathId"],
                revision_number=attribution_payload["revisionNumber"],
                title=attribution_payload["title"],
                creator_display_name=attribution_payload["creatorDisplayName"],
            )
            if attribution_payload is not None
            else None
        )
        published_payload = payload.get("published")
        record = FlypathRecord(
            flypath_id=payload["flypathId"],
            owner_account_id=payload["ownerAccountId"],
            owner_display_name=payload["ownerDisplayName"],
            title=payload["title"],
            description=payload["description"],
            visibility=payload["visibility"],
            region_id=payload["regionId"],
            created_utc=payload["createdUtc"],
            updated_utc=payload["updatedUtc"],
            draft_revision_number=payload["draftRevisionNumber"],
            draft=_document_from_payload(payload["draft"]),
            published_revision_number=payload.get("publishedRevisionNumber"),
            published=(
                _document_from_payload(published_payload)
                if published_payload is not None
                else None
            ),
            source_attribution=attribution,
        )
    except DocumentValidationError:
        raise
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise DocumentValidationError(f"invalid serialized Flypath record: {error}") from error
    validate_record(record)
    if serialize_record(record) != text:
        raise DocumentValidationError("serialized Flypath record is not canonical JSON")
    return record


def utc_text(value: datetime) -> str:
    if value.tzinfo is None:
        raise DocumentValidationError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def create_private_flypath(
    *,
    flypath_id: str,
    owner_account_id: str,
    owner_display_name: str,
    title: str,
    region_id: str,
    now: datetime,
) -> FlypathRecord:
    for value, field in (
        (flypath_id, "flypath_id"),
        (owner_account_id, "owner_account_id"),
        (title, "title"),
        (region_id, "region_id"),
    ):
        _require_text(value, field)
    draft = seal_document(RevisionDocument(revision_number=1, region_id=region_id))
    timestamp = utc_text(now)
    record = FlypathRecord(
        flypath_id=flypath_id,
        owner_account_id=owner_account_id,
        owner_display_name=owner_display_name,
        title=title,
        description="",
        visibility="private",
        region_id=region_id,
        created_utc=timestamp,
        updated_utc=timestamp,
        draft_revision_number=1,
        draft=draft,
    )
    validate_record(record)
    return record


def save_draft(
    record: FlypathRecord,
    candidate: RevisionDocument,
    *,
    expected_revision: int,
    now: datetime,
) -> FlypathRecord:
    if expected_revision != record.draft_revision_number:
        raise RevisionConflictError(
            f"expected revision {expected_revision}, current revision is {record.draft_revision_number}"
        )
    if candidate.region_id != record.region_id:
        raise DocumentValidationError("a draft cannot change its Flypath region")
    next_revision = record.draft_revision_number + 1
    draft = seal_document(replace(candidate, revision_number=next_revision, content_hash=""))
    saved = replace(
        record,
        draft_revision_number=next_revision,
        draft=draft,
        updated_utc=utc_text(now),
    )
    validate_record(saved)
    return saved


def publish(record: FlypathRecord, *, now: datetime) -> FlypathRecord:
    validate_record(record)
    published = replace(
        record,
        visibility="public",
        published_revision_number=record.draft_revision_number,
        published=record.draft,
        updated_utc=utc_text(now),
    )
    validate_record(published)
    return published


def clone_published(
    source: FlypathRecord,
    *,
    flypath_id: str,
    owner_account_id: str,
    owner_display_name: str,
    now: datetime,
) -> FlypathRecord:
    if source.visibility != "public" or source.published is None or source.published_revision_number is None:
        raise DocumentValidationError("only a published revision can be cloned")
    clone = create_private_flypath(
        flypath_id=flypath_id,
        owner_account_id=owner_account_id,
        owner_display_name=owner_display_name,
        title=f"{source.title} (Clone)",
        region_id=source.region_id,
        now=now,
    )
    cloned_draft = seal_document(replace(source.published, revision_number=1, content_hash=""))
    result = replace(
        clone,
        draft=cloned_draft,
        source_attribution=SourceAttribution(
            flypath_id=source.flypath_id,
            revision_number=source.published_revision_number,
            title=source.title,
            creator_display_name=source.owner_display_name,
        ),
    )
    validate_record(result)
    return result


def readable_revision(record: FlypathRecord, requester_account_id: str) -> RevisionDocument | None:
    if requester_account_id == record.owner_account_id:
        return record.draft
    if record.visibility == "public":
        return record.published
    return None


def owner_may_edit(record: FlypathRecord, requester_account_id: str) -> bool:
    return requester_account_id == record.owner_account_id
