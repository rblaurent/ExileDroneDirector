"""Execute private creation against the compiled Blueprint and real SaveGame I/O.

On success this intentionally leaves two committed test records in the standard
repository A/B slots.  ``Validate-RepositoryPrivateCreateRestart.py`` must run
in a fresh Unreal process to prove recovery and remove both slots.
"""

from __future__ import annotations

import unreal


PREFIX = "EDD_PRIVATE_CREATE_RUNTIME"
CLASS_PATH = (
    "/Game/Mods/ExileDroneDirector/Server/Repository/"
    "BP_EDD_FlypathRepository.BP_EDD_FlypathRepository_C"
)
SLOTS = ("EDD_Repository_A", "EDD_Repository_B")
DOCUMENT_FIELDS = {
    "SchemaVersion": ("SchemaVersion", "schema_version", "SchemaVersion_16_7F93B5224F25B9BFDAC842BCD5B16D37"),
    "TrajectoryEngineVersion": (
        "TrajectoryEngineVersion", "trajectory_engine_version",
        "TrajectoryEngineVersion_3_442F783F41FCAC3B8146EDA9233D191D",
    ),
    "RevisionNumber": ("RevisionNumber", "revision_number", "RevisionNumber_5_951904BF45A63EADA84E4AB0386D19B4"),
    "RegionId": ("RegionId", "region_id", "RegionId_8_BC1B1B9F4515D58E9666939AB30095B4"),
    "DurationSeconds": (
        "DurationSeconds", "duration_seconds", "DurationSeconds_11_4517680840D3F6CC541E6BBC6AB10DF9",
    ),
    "DefaultFlightProfile": (
        "DefaultFlightProfile", "default_flight_profile",
        "DefaultFlightProfile_14_E9663FDD4E006355747CD3B4CD8BD161",
    ),
    "Waypoints": ("Waypoints", "waypoints", "Waypoints_26_1F07C1B24D0D17E4610CDBBAFC5039E5"),
    "Segments": ("Segments", "segments", "Segments_27_C44AF0F54C828C6532348D8A42A4A92B"),
    "ContentHash": ("ContentHash", "content_hash", "ContentHash_28_C376573940EDD8D9F911D9800DB430BC"),
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
    raise RuntimeError(f"could not read {name}: {'; '.join(errors)}")


def set_prop(obj, name: str, value) -> None:
    errors = []
    for candidate in candidates(name):
        try:
            obj.set_editor_property(candidate, value)
            return
        except Exception as error:
            errors.append(f"{candidate}:{error}")
    raise RuntimeError(f"could not set {name}: {'; '.join(errors)}")


def document_prop(document, name: str):
    errors = []
    for candidate in DOCUMENT_FIELDS[name]:
        try:
            return document.get_editor_property(candidate)
        except Exception as error:
            errors.append(f"{candidate}:{error}")
    raise RuntimeError(f"could not read document {name}: {'; '.join(errors)}")


def set_document_prop(document, name: str, value) -> None:
    errors = []
    for candidate in DOCUMENT_FIELDS[name]:
        try:
            document.set_editor_property(candidate, value)
            return
        except Exception as error:
            errors.append(f"{candidate}:{error}")
    raise RuntimeError(f"could not set document {name}: {'; '.join(errors)}")


def delete_slots() -> None:
    for slot in SLOTS:
        if unreal.GameplayStatics.does_save_game_exist(slot, 0):
            require(unreal.GameplayStatics.delete_game_in_slot(slot, 0), f"could not delete {slot}")


def stage_document(actor, *, revision: int = 1, region: str = "ExiledLands") -> None:
    document = prop(actor, "RequestDraftDocumentV1")
    for name, value in (
        ("SchemaVersion", 1),
        ("TrajectoryEngineVersion", 1),
        ("RevisionNumber", revision),
        ("RegionId", region),
        ("DurationSeconds", 0.0),
        ("DefaultFlightProfile", "cinematic_drone"),
        ("Waypoints", []),
        ("Segments", []),
        ("ContentHash", ""),
    ):
        set_document_prop(document, name, value)
    # Raw Python assignment of [] to a user-defined-struct array does not carry
    # the same hidden native array identity as a Blueprint Make/Decode result.
    # Normalize the fixture through the shipped Blueprint codec so Create sees
    # the exact typed boundary that a real Blueprint caller supplies.
    set_prop(actor, "ScratchDocumentV1", document)
    actor.call_method("EncodeDocumentV1")
    actor.call_method("DecodeDocumentV1")
    require(prop(actor, "ScratchValidV1"), "Blueprint document fixture did not round-trip canonically")
    set_prop(actor, "RequestDraftDocumentV1", prop(actor, "ScratchDocumentV1"))


def stage_request(
    actor,
    *,
    flypath_id="create-runtime-a",
    owner="owner-a",
    title="Runtime Alpha",
    region="ExiledLands",
    now="2026-08-11T18:20:00Z",
    revision=1,
    draft_region=None,
) -> None:
    for name, value in (
        ("RequestRequesterAccountIdV1", owner),
        ("RequestRequesterDisplayNameV1", "Owner A"),
        ("RequestFlypathIdV1", flypath_id),
        ("RequestTitleV1", title),
        ("RequestDescriptionV1", "compiled creation acceptance"),
        ("RequestRegionIdV1", region),
        ("RequestNowUtcV1", now),
    ):
        set_prop(actor, name, value)
    stage_document(actor, revision=revision, region=draft_region or region)


def snapshot(actor):
    return (
        int(prop(actor, "ActiveGenerationV1")),
        str(prop(actor, "ActiveSlotV1")),
        tuple(prop(actor, "ActiveRecordEnvelopesV1")),
        tuple(prop(actor, "ActiveFlypathIdsV1")),
        tuple(prop(actor, "ActiveOwnerAccountIdsV1")),
        tuple(prop(actor, "ActiveVisibilitiesV1")),
        tuple(prop(actor, "ActiveUpdatedUtcV1")),
    )


def invoke_rejected(actor, code: str, detail: str, label: str) -> None:
    before = snapshot(actor)
    actor.call_method("CreatePrivateFlypathV1")
    require(prop(actor, "ResultCodeV1") == code, f"{label} code {prop(actor, 'ResultCodeV1')}")
    require(prop(actor, "ResultDetailV1") == detail, f"{label} detail {prop(actor, 'ResultDetailV1')}")
    require(snapshot(actor) == before, f"{label} mutated authority")
    require(not prop(actor, "ResultHasCurrentRevisionV1"), f"{label} leaked revision")
    require(prop(actor, "ResultRecordEnvelopeV1") == "", f"{label} leaked envelope")
    emit(label, "PASS")


actor = None
leave_for_restart = False
try:
    delete_slots()
    repository_class = unreal.load_class(None, CLASS_PATH)
    require(repository_class is not None, "repository generated class missing")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    require(subsystem is not None, "EditorActorSubsystem unavailable")
    actor = subsystem.spawn_actor_from_class(repository_class, unreal.Vector(0, 0, -100000), unreal.Rotator(), False)
    require(actor is not None, "could not spawn repository actor")

    # Every rejection below must leave both authority and physical slots untouched.
    stage_request(actor, owner="   ")
    invoke_rejected(actor, "ValidationFailed", "InvalidCreateRequest", "INVALID_OWNER")
    set_prop(actor, "MaxTitleCharsV1", 4)
    stage_request(actor, title="Too Long")
    invoke_rejected(actor, "LimitExceeded", "TitleLength", "TITLE_LIMIT")
    set_prop(actor, "MaxTitleCharsV1", 96)
    stage_request(actor, region="Unknown", draft_region="Unknown")
    invoke_rejected(actor, "RegionForbidden", "RegionNotAllowed", "REGION_POLICY")
    stage_request(actor, flypath_id="   ")
    invoke_rejected(actor, "ValidationFailed", "InvalidCreateRequest", "INVALID_ID")

    set_prop(actor, "ActiveFlypathIdsV1", ["duplicate"])
    set_prop(actor, "ActiveOwnerAccountIdsV1", ["someone"])
    set_prop(actor, "ActiveVisibilitiesV1", ["private"])
    set_prop(actor, "ActiveUpdatedUtcV1", ["2026-08-11T18:00:00Z"])
    stage_request(actor, flypath_id="duplicate")
    invoke_rejected(actor, "AlreadyExists", "FlypathIdCollision", "COLLISION")

    set_prop(actor, "ActiveFlypathIdsV1", ["owned-existing"])
    set_prop(actor, "ActiveOwnerAccountIdsV1", ["owner-a"])
    set_prop(actor, "MaxPathsPerOwnerV1", 1)
    stage_request(actor)
    invoke_rejected(actor, "LimitExceeded", "OwnerPathLimit", "OWNER_LIMIT")

    require(not any(unreal.GameplayStatics.does_save_game_exist(slot, 0) for slot in SLOTS), "rejection wrote SaveGame")
    set_prop(actor, "ActiveRecordEnvelopesV1", [])
    set_prop(actor, "ActiveFlypathIdsV1", [])
    set_prop(actor, "ActiveOwnerAccountIdsV1", [])
    set_prop(actor, "ActiveVisibilitiesV1", [])
    set_prop(actor, "ActiveUpdatedUtcV1", [])
    set_prop(actor, "MaxPathsPerOwnerV1", 2)

    # Exercise the encoded-record limit before any successful write.  The
    # production default is restored immediately afterward.
    set_prop(actor, "MaxSerializedBytesV1", 100)
    stage_request(actor)
    invoke_rejected(actor, "LimitExceeded", "SerializedSize", "SERIALIZED_SIZE")
    set_prop(actor, "MaxSerializedBytesV1", 2000000)

    stage_request(actor)
    actor.call_method("CreatePrivateFlypathV1")
    if prop(actor, "ResultCodeV1") != "Success":
        for diagnostic_name in (
            "ScratchValidV1",
            "ScratchRecordFlypathIdV1",
            "ScratchRecordOwnerAccountIdV1",
            "ScratchRecordTitleV1",
            "ScratchRecordVisibilityV1",
            "ScratchRecordRegionIdV1",
            "ScratchRecordCreatedUtcV1",
            "ScratchRecordUpdatedUtcV1",
            "ScratchRecordDraftRevisionNumberV1",
            "ScratchRecordHasPublishedRevisionV1",
            "ScratchRecordHasSourceAttributionV1",
        ):
            emit(f"DIAGNOSTIC_{diagnostic_name}", prop(actor, diagnostic_name))
        diagnostic_document = prop(actor, "ScratchRecordDraftDocumentV1")
        for diagnostic_name in DOCUMENT_FIELDS:
            emit(f"DIAGNOSTIC_DOCUMENT_{diagnostic_name}", document_prop(diagnostic_document, diagnostic_name))
        set_prop(actor, "ScratchDocumentV1", diagnostic_document)
        actor.call_method("ValidateDocumentV1")
        emit("DIAGNOSTIC_DOCUMENT_VALID", prop(actor, "ScratchValidV1"))
        actor.call_method("EncodeRecordV1")
        diagnostic_envelope = prop(actor, "ScratchEncodedRecordV1")
        emit("DIAGNOSTIC_ENVELOPE_LENGTH", len(diagnostic_envelope))
        actor.call_method("DecodeRecordV1")
        emit("DIAGNOSTIC_DECODE_VALID", prop(actor, "ScratchValidV1"))
        actor.call_method("ValidateRecordV1")
        emit("DIAGNOSTIC_REVALIDATE_VALID", prop(actor, "ScratchValidV1"))
    require(prop(actor, "ResultCodeV1") == "Success", f"first create failed {prop(actor, 'ResultCodeV1')}|{prop(actor, 'ResultDetailV1')}")
    require(snapshot(actor)[0:2] == (1, "EDD_Repository_A"), "first generation/slot changed")
    require(list(prop(actor, "ActiveFlypathIdsV1")) == ["create-runtime-a"], "first ID index changed")
    require(list(prop(actor, "ActiveOwnerAccountIdsV1")) == ["owner-a"], "first owner index changed")
    require(list(prop(actor, "ActiveVisibilitiesV1")) == ["private"], "creation was not private")
    require(prop(actor, "ResultHasCurrentRevisionV1"), "first create omitted revision flag")
    require(int(prop(actor, "ResultCurrentRevisionV1")) == 1, "first create revision changed")
    require(int(prop(actor, "ResultRecordIndexV1")) == 0, "first create index changed")
    first_envelope = prop(actor, "ResultRecordEnvelopeV1")
    require(first_envelope == list(prop(actor, "ActiveRecordEnvelopesV1"))[0], "first result envelope mismatch")
    emit("FIRST_CREATE", "PASS")

    set_prop(actor, "RequestRequesterAccountIdV1", "owner-a")
    set_prop(actor, "RequestFlypathIdV1", "create-runtime-a")
    actor.call_method("LoadDraftV1")
    require(prop(actor, "ResultCodeV1") == "Success", "owner load after create failed")
    require(int(prop(actor, "ResultCurrentRevisionV1")) == 1, "owner load revision changed")
    require(document_prop(prop(actor, "ResultDraftDocumentV1"), "RevisionNumber") == 1, "owner typed draft changed")
    set_prop(actor, "RequestRequesterAccountIdV1", "owner-b")
    actor.call_method("LoadDraftV1")
    require(prop(actor, "ResultCodeV1") == "Forbidden", "wrong owner loaded created draft")
    emit("OWNER_LOAD_BOUNDARY", "PASS")

    # The same deterministic ID must collide without advancing generation.
    stage_request(actor)
    invoke_rejected(actor, "AlreadyExists", "FlypathIdCollision", "REPEAT_ID_COLLISION")
    require(int(prop(actor, "ActiveGenerationV1")) == 1, "collision advanced generation")

    stage_request(
        actor,
        flypath_id="create-runtime-b",
        title="Runtime Beta",
        now="2026-08-11T18:21:00Z",
    )
    actor.call_method("CreatePrivateFlypathV1")
    require(prop(actor, "ResultCodeV1") == "Success", f"second create failed {prop(actor, 'ResultCodeV1')}|{prop(actor, 'ResultDetailV1')}")
    require(snapshot(actor)[0:2] == (2, "EDD_Repository_B"), "second generation/slot changed")
    require(list(prop(actor, "ActiveFlypathIdsV1")) == ["create-runtime-a", "create-runtime-b"], "deterministic ID order changed")
    require(list(prop(actor, "ActiveOwnerAccountIdsV1")) == ["owner-a", "owner-a"], "owner alignment changed")
    require(list(prop(actor, "ActiveVisibilitiesV1")) == ["private", "private"], "private defaults changed")
    require(len(list(prop(actor, "ActiveRecordEnvelopesV1"))) == 2, "record candidate did not retain first create")
    require(int(prop(actor, "ResultCurrentRevisionV1")) == 1, "second create revision changed")
    require(int(prop(actor, "ResultRecordIndexV1")) == 1, "second create index changed")
    emit("SECOND_CREATE", "PASS")

    stage_request(actor, flypath_id="create-runtime-c", title="Runtime Gamma")
    invoke_rejected(actor, "LimitExceeded", "OwnerPathLimit", "POST_CREATE_OWNER_LIMIT")
    require(int(prop(actor, "ActiveGenerationV1")) == 2, "owner limit advanced generation")

    require(unreal.GameplayStatics.does_save_game_exist("EDD_Repository_A", 0), "slot A missing")
    require(unreal.GameplayStatics.does_save_game_exist("EDD_Repository_B", 0), "slot B missing")
    latest = unreal.GameplayStatics.load_game_from_slot("EDD_Repository_B", 0)
    require(latest is not None, "could not load committed slot B")
    require(int(prop(latest, "Generation")) == 2, "slot B generation changed")
    require(bool(prop(latest, "Committed")), "slot B is not committed")
    require(list(prop(latest, "RecordEnvelopes")) == list(prop(actor, "ActiveRecordEnvelopesV1")), "slot B payload mismatch")
    emit("SAVEGAME_COMMITTED", "PASS")
    leave_for_restart = True
    emit("RESTART_REQUIRED", "PASS")
    emit("RESULT", "PASS")
finally:
    if actor is not None:
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        if subsystem is not None:
            subsystem.destroy_actor(actor)
    if not leave_for_restart:
        delete_slots()
