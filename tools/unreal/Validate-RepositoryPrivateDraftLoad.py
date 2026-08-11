"""Execute the compiled owner-only private draft loader against real data.

The probe spawns the shipped repository actor, seeds a canonical private record,
and proves all security-sensitive outcomes.  Failure cases must not leak the
record envelope, revision, or typed document left by an earlier invocation.
"""

from __future__ import annotations

import unreal


PREFIX = "EDD_PRIVATE_DRAFT_LOAD_RUNTIME"
CLASS_PATH = (
    "/Game/Mods/ExileDroneDirector/Server/Repository/"
    "BP_EDD_FlypathRepository.BP_EDD_FlypathRepository_C"
)
DOCUMENT_FIELDS = {
    "SchemaVersion": ("SchemaVersion", "schema_version", "SchemaVersion_16_7F93B5224F25B9BFDAC842BCD5B16D37"),
    "TrajectoryEngineVersion": (
        "TrajectoryEngineVersion",
        "trajectory_engine_version",
        "TrajectoryEngineVersion_3_442F783F41FCAC3B8146EDA9233D191D",
    ),
    "RevisionNumber": ("RevisionNumber", "revision_number", "RevisionNumber_5_951904BF45A63EADA84E4AB0386D19B4"),
    "RegionId": ("RegionId", "region_id", "RegionId_8_BC1B1B9F4515D58E9666939AB30095B4"),
    "DefaultFlightProfile": (
        "DefaultFlightProfile",
        "default_flight_profile",
        "DefaultFlightProfile_14_E9663FDD4E006355747CD3B4CD8BD161",
    ),
    "Waypoints": ("Waypoints", "waypoints", "Waypoints_26_1F07C1B24D0D17E4610CDBBAFC5039E5"),
    "Segments": ("Segments", "segments", "Segments_27_C44AF0F54C828C6532348D8A42A4A92B"),
}


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}|{label}|{value}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(f"{PREFIX}|FAIL|{message}")


def candidates(name: str):
    snake = "".join(("_" + c.lower()) if c.isupper() else c for c in name).lstrip("_")
    return (name, unreal.Name(name), snake, unreal.Name(snake))


def prop(obj, name: str):
    errors = []
    for candidate in candidates(name):
        try:
            return obj.get_editor_property(candidate)
        except Exception as error:
            errors.append(f"{candidate}:{error}")
    raise RuntimeError(f"{PREFIX}|FAIL|could not read {name}: {'; '.join(errors)}")


def set_prop(obj, name: str, value) -> None:
    errors = []
    for candidate in candidates(name):
        try:
            obj.set_editor_property(candidate, value)
            return
        except Exception as error:
            errors.append(f"{candidate}:{error}")
    raise RuntimeError(f"{PREFIX}|FAIL|could not set {name}: {'; '.join(errors)}")


def document_prop(document, name: str):
    errors = []
    for candidate in DOCUMENT_FIELDS[name]:
        try:
            return document.get_editor_property(candidate)
        except Exception as error:
            errors.append(f"{candidate}:{error}")
    raise RuntimeError(f"{PREFIX}|FAIL|could not read document {name}: {'; '.join(errors)}")


def set_document_prop(document, name: str, value) -> None:
    errors = []
    for candidate in DOCUMENT_FIELDS[name]:
        try:
            document.set_editor_property(candidate, value)
            return
        except Exception as error:
            errors.append(f"{candidate}:{error}")
    raise RuntimeError(f"{PREFIX}|FAIL|could not set document {name}: {'; '.join(errors)}")


def build_blueprint_canonical_record(actor) -> str:
    document = prop(actor, "ScratchRecordDraftDocumentV1")
    set_document_prop(document, "SchemaVersion", 1)
    set_document_prop(document, "TrajectoryEngineVersion", 1)
    set_document_prop(document, "RevisionNumber", 7)
    set_document_prop(document, "RegionId", "ExiledLands")
    set_document_prop(document, "DefaultFlightProfile", "cinematic_drone")
    set_document_prop(document, "Waypoints", [])
    set_document_prop(document, "Segments", [])
    set_prop(actor, "ScratchRecordDraftDocumentV1", document)
    for name, value in (
        ("ScratchRecordFlypathIdV1", "private-a"),
        ("ScratchRecordOwnerAccountIdV1", "owner-a"),
        ("ScratchRecordOwnerDisplayNameV1", "Owner A"),
        ("ScratchRecordTitleV1", "Runtime Private Draft"),
        ("ScratchRecordDescriptionV1", "loader acceptance"),
        ("ScratchRecordVisibilityV1", "private"),
        ("ScratchRecordRegionIdV1", "ExiledLands"),
        ("ScratchRecordCreatedUtcV1", "2026-08-11T17:00:00Z"),
        ("ScratchRecordUpdatedUtcV1", "2026-08-11T17:05:00Z"),
        ("ScratchRecordDraftRevisionNumberV1", 7),
        ("ScratchRecordHasPublishedRevisionV1", False),
        ("ScratchRecordHasSourceAttributionV1", False),
    ):
        set_prop(actor, name, value)
    actor.call_method("EncodeRecordV1")
    encoded = prop(actor, "ScratchEncodedRecordV1")
    require(bool(encoded), "Blueprint encoder returned an empty record")
    return encoded


def invoke(actor, requester: str, flypath_id: str) -> None:
    set_prop(actor, "RequestRequesterAccountIdV1", requester)
    set_prop(actor, "RequestFlypathIdV1", flypath_id)
    actor.call_method("LoadDraftV1")


def require_no_payload(actor, label: str) -> None:
    require(not bool(prop(actor, "ResultHasCurrentRevisionV1")), f"{label} exposed revision flag")
    require(int(prop(actor, "ResultCurrentRevisionV1")) == 0, f"{label} exposed revision")
    require(prop(actor, "ResultRecordEnvelopeV1") == "", f"{label} exposed record envelope")
    document = prop(actor, "ResultDraftDocumentV1")
    require(int(document_prop(document, "RevisionNumber")) == 0, f"{label} exposed typed draft")


actor = None
try:
    repository_class = unreal.load_class(None, CLASS_PATH)
    require(repository_class is not None, "repository generated class missing")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    require(subsystem is not None, "EditorActorSubsystem unavailable")
    actor = subsystem.spawn_actor_from_class(
        repository_class,
        unreal.Vector(0.0, 0.0, -100000.0),
        unreal.Rotator(),
        False,
    )
    require(actor is not None, "could not spawn repository actor")

    valid_record = build_blueprint_canonical_record(actor)
    set_prop(actor, "RepositoryLoadedV1", True)
    set_prop(actor, "ActiveRecordEnvelopesV1", [valid_record])
    set_prop(actor, "ActiveFlypathIdsV1", ["private-a"])
    set_prop(actor, "ActiveOwnerAccountIdsV1", ["owner-a"])
    set_prop(actor, "ActiveVisibilitiesV1", ["private"])
    set_prop(actor, "ActiveUpdatedUtcV1", ["2026-08-11T17:05:00Z"])

    invoke(actor, "owner-a", "missing")
    require(prop(actor, "ResultCodeV1") == "NotFound", "missing record code changed")
    require(prop(actor, "ResultDetailV1") == "FlypathNotFound", "missing record detail changed")
    require_no_payload(actor, "missing record")
    emit("NOT_FOUND", "PASS")

    invoke(actor, "owner-b", "private-a")
    require(prop(actor, "ResultCodeV1") == "Forbidden", "wrong-owner code changed")
    require(prop(actor, "ResultDetailV1") == "OwnerRequired", "wrong-owner detail changed")
    require_no_payload(actor, "wrong owner")
    emit("OWNER_ISOLATION", "PASS")

    set_prop(actor, "ActiveRecordEnvelopesV1", ["not-json"])
    invoke(actor, "owner-a", "private-a")
    require(prop(actor, "ResultCodeV1") == "ValidationFailed", "corrupt record code changed")
    require(
        prop(actor, "ResultDetailV1") == "StoredRecordDecodeFailed",
        "corrupt record detail changed",
    )
    require_no_payload(actor, "corrupt record")
    emit("CORRUPT_RECORD", "PASS")

    set_prop(actor, "ActiveRecordEnvelopesV1", [valid_record])
    invoke(actor, "owner-a", "private-a")
    require(
        prop(actor, "ResultCodeV1") == "Success",
        f"owner load did not succeed: {prop(actor, 'ResultCodeV1')}|{prop(actor, 'ResultDetailV1')}",
    )
    require(prop(actor, "ResultDetailV1") == "", "owner load returned detail")
    require(bool(prop(actor, "ResultHasCurrentRevisionV1")), "owner load omitted revision flag")
    require(int(prop(actor, "ResultCurrentRevisionV1")) == 7, "owner load revision changed")
    require(prop(actor, "ResultRecordEnvelopeV1") == valid_record, "owner envelope changed")
    document = prop(actor, "ResultDraftDocumentV1")
    require(int(document_prop(document, "SchemaVersion")) == 1, "document schema changed")
    require(int(document_prop(document, "TrajectoryEngineVersion")) == 1, "trajectory schema changed")
    require(int(document_prop(document, "RevisionNumber")) == 7, "typed revision changed")
    require(document_prop(document, "RegionId") == "ExiledLands", "typed region changed")
    require(document_prop(document, "DefaultFlightProfile") == "cinematic_drone", "typed profile changed")
    require(list(document_prop(document, "Waypoints")) == [], "unexpected waypoints")
    require(list(document_prop(document, "Segments")) == [], "unexpected segments")
    emit("OWNER_LOAD", "PASS")

    # A later denial must reset the successful payload, preventing stale-data leaks.
    invoke(actor, "owner-b", "private-a")
    require(prop(actor, "ResultCodeV1") == "Forbidden", "post-success denial changed")
    require_no_payload(actor, "post-success denial")
    emit("STALE_PAYLOAD_RESET", "PASS")
    emit("RESULT", "PASS")
finally:
    if actor is not None:
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        if subsystem is not None:
            subsystem.destroy_actor(actor)
