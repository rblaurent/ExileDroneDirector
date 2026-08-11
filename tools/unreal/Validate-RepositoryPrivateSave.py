"""Execute SaveDraftV1 through the compiled repository and real SaveGame I/O.

The test creates its fixture through CreatePrivateFlypathV1, exercises rejected
saves without authority mutation, performs two optimistic saves, and leaves the
committed A/B slots for Validate-RepositoryPrivateSaveRestart.py.
"""

from __future__ import annotations

import unreal


PREFIX = "EDD_PRIVATE_SAVE_RUNTIME"
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


def stage_document(actor, *, revision: int, region: str, duration: float) -> None:
    document = prop(actor, "RequestDraftDocumentV1")
    for name, value in (
        ("SchemaVersion", 1),
        ("TrajectoryEngineVersion", 1),
        ("RevisionNumber", revision),
        ("RegionId", region),
        ("DurationSeconds", duration),
        ("DefaultFlightProfile", "cinematic_drone"),
        ("Waypoints", []),
        ("Segments", []),
        ("ContentHash", "caller-controlled-hash-must-be-ignored"),
    ):
        set_document_prop(document, name, value)
    # Give the arrays native Blueprint identity; raw Python UDS arrays are not
    # a trustworthy request fixture in this DevKit.
    set_prop(actor, "ScratchDocumentV1", document)
    actor.call_method("EncodeDocumentV1")
    actor.call_method("DecodeDocumentV1")
    require(bool(prop(actor, "ScratchValidV1")), "document fixture did not round-trip")
    set_prop(actor, "RequestDraftDocumentV1", prop(actor, "ScratchDocumentV1"))


def stage_create(actor) -> None:
    for name, value in (
        ("RequestRequesterAccountIdV1", "save-owner"),
        ("RequestRequesterDisplayNameV1", "Save Owner"),
        ("RequestFlypathIdV1", "save-runtime-a"),
        ("RequestTitleV1", "Persistent Save Fixture"),
        ("RequestDescriptionV1", "SaveDraftV1 executable acceptance"),
        ("RequestRegionIdV1", "ExiledLands"),
        ("RequestNowUtcV1", "2026-08-11T19:00:00Z"),
    ):
        set_prop(actor, name, value)
    stage_document(actor, revision=77, region="ExiledLands", duration=0.0)


def stage_save(
    actor,
    *,
    owner: str = "save-owner",
    flypath_id: str = "save-runtime-a",
    expected: int = 1,
    now: str = "2026-08-11T19:01:00Z",
    region: str = "ExiledLands",
    duration: float = 12.5,
    caller_revision: int = 999,
) -> None:
    set_prop(actor, "RequestRequesterAccountIdV1", owner)
    set_prop(actor, "RequestFlypathIdV1", flypath_id)
    set_prop(actor, "RequestExpectedRevisionV1", expected)
    set_prop(actor, "RequestNowUtcV1", now)
    stage_document(actor, revision=caller_revision, region=region, duration=duration)


def snapshot(actor):
    return (
        int(prop(actor, "ActiveGenerationV1")),
        str(prop(actor, "ActiveSlotV1")),
        tuple(prop(actor, "ActiveRecordEnvelopesV1")),
        tuple(prop(actor, "ActiveTombstoneFlypathIdsV1")),
        tuple(prop(actor, "ActiveFlypathIdsV1")),
        tuple(prop(actor, "ActiveOwnerAccountIdsV1")),
        tuple(prop(actor, "ActiveVisibilitiesV1")),
        tuple(prop(actor, "ActiveUpdatedUtcV1")),
    )


def invoke_rejected(actor, code: str, detail: str, label: str, *, current_revision=None) -> None:
    before = snapshot(actor)
    actor.call_method("SaveDraftV1")
    require(prop(actor, "ResultCodeV1") == code, f"{label} code {prop(actor, 'ResultCodeV1')}")
    require(prop(actor, "ResultDetailV1") == detail, f"{label} detail {prop(actor, 'ResultDetailV1')}")
    require(snapshot(actor) == before, f"{label} mutated authority")
    if current_revision is None:
        require(not bool(prop(actor, "ResultHasCurrentRevisionV1")), f"{label} leaked revision")
        require(int(prop(actor, "ResultCurrentRevisionV1")) == 0, f"{label} leaked revision value")
    else:
        require(bool(prop(actor, "ResultHasCurrentRevisionV1")), f"{label} omitted conflict revision")
        require(int(prop(actor, "ResultCurrentRevisionV1")) == current_revision, f"{label} conflict revision changed")
    require(prop(actor, "ResultRecordEnvelopeV1") == "", f"{label} leaked envelope")
    emit(label, "PASS")


def require_saved_document(actor, revision: int, duration: float, label: str) -> None:
    set_prop(actor, "RequestRequesterAccountIdV1", "save-owner")
    set_prop(actor, "RequestFlypathIdV1", "save-runtime-a")
    actor.call_method("LoadDraftV1")
    require(prop(actor, "ResultCodeV1") == "Success", f"{label} owner load failed")
    require(int(prop(actor, "ResultCurrentRevisionV1")) == revision, f"{label} load revision changed")
    document = prop(actor, "ResultDraftDocumentV1")
    require(int(document_prop(document, "RevisionNumber")) == revision, f"{label} typed revision changed")
    require(abs(float(document_prop(document, "DurationSeconds")) - duration) < 0.001, f"{label} duration changed")
    require(document_prop(document, "ContentHash") != "caller-controlled-hash-must-be-ignored", f"{label} caller hash trusted")


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

    stage_create(actor)
    actor.call_method("CreatePrivateFlypathV1")
    require(prop(actor, "ResultCodeV1") == "Success", f"fixture create failed: {prop(actor, 'ResultCodeV1')}|{prop(actor, 'ResultDetailV1')}")
    require(snapshot(actor)[0:2] == (1, "EDD_Repository_A"), "fixture generation/slot changed")
    require(list(prop(actor, "ActiveVisibilitiesV1")) == ["private"], "fixture is not private")
    require(int(prop(actor, "ResultCurrentRevisionV1")) == 1, "create did not server-force revision 1")
    original_envelope = list(prop(actor, "ActiveRecordEnvelopesV1"))[0]
    emit("PRIVATE_FIXTURE", "PASS")

    stage_save(actor, flypath_id="missing")
    invoke_rejected(actor, "NotFound", "FlypathNotFound", "NOT_FOUND")
    stage_save(actor, owner="wrong-owner")
    invoke_rejected(actor, "Forbidden", "OwnerRequired", "OWNER_ISOLATION")
    stage_save(actor, expected=0)
    invoke_rejected(actor, "RevisionConflict", "ExpectedRevisionMismatch", "REVISION_CONFLICT", current_revision=1)
    stage_save(actor, now="   ")
    invoke_rejected(actor, "ValidationFailed", "InvalidSaveRequest", "INVALID_TIMESTAMP")

    set_prop(actor, "MaxWaypointsPerPathV1", -1)
    stage_save(actor)
    invoke_rejected(actor, "LimitExceeded", "WaypointLimit", "WAYPOINT_LIMIT")
    set_prop(actor, "MaxWaypointsPerPathV1", 512)

    stage_save(actor, region="Siptah")
    invoke_rejected(actor, "RegionForbidden", "DraftRegionMismatch", "REGION_MISMATCH")

    set_prop(actor, "MaxSerializedBytesV1", 100)
    stage_save(actor)
    invoke_rejected(actor, "LimitExceeded", "SerializedSize", "SERIALIZED_SIZE")
    set_prop(actor, "MaxSerializedBytesV1", 2000000)

    stage_save(actor, expected=1, now="2026-08-11T19:01:00Z", duration=12.5, caller_revision=999)
    actor.call_method("SaveDraftV1")
    require(prop(actor, "ResultCodeV1") == "Success", f"first save failed: {prop(actor, 'ResultCodeV1')}|{prop(actor, 'ResultDetailV1')}")
    require(snapshot(actor)[0:2] == (2, "EDD_Repository_B"), "first save generation/slot changed")
    require(list(prop(actor, "ActiveFlypathIdsV1")) == ["save-runtime-a"], "first save changed ID index")
    require(list(prop(actor, "ActiveOwnerAccountIdsV1")) == ["save-owner"], "first save changed owner index")
    require(list(prop(actor, "ActiveVisibilitiesV1")) == ["private"], "first save changed visibility")
    require(list(prop(actor, "ActiveUpdatedUtcV1")) == ["2026-08-11T19:01:00Z"], "first save timestamp index changed")
    require(int(prop(actor, "ResultCurrentRevisionV1")) == 2, "first save revision was not current+1")
    require(int(prop(actor, "ResultRecordIndexV1")) == 0, "first save result index changed")
    require(int(document_prop(prop(actor, "ResultDraftDocumentV1"), "RevisionNumber")) == 2, "first result typed revision changed")
    first_saved_envelope = list(prop(actor, "ActiveRecordEnvelopesV1"))[0]
    require(first_saved_envelope != original_envelope, "first save did not replace the record envelope")
    require_saved_document(actor, 2, 12.5, "first save")
    emit("FIRST_SAVE", "PASS")

    # Decode the committed envelope and prove immutable metadata survived the edit.
    set_prop(actor, "ScratchEncodedRecordV1", first_saved_envelope)
    actor.call_method("DecodeRecordV1")
    require(bool(prop(actor, "ScratchValidV1")), "first saved envelope did not decode")
    require(prop(actor, "ScratchRecordFlypathIdV1") == "save-runtime-a", "save changed record ID")
    require(prop(actor, "ScratchRecordOwnerAccountIdV1") == "save-owner", "save changed record owner")
    require(prop(actor, "ScratchRecordTitleV1") == "Persistent Save Fixture", "save changed title")
    require(prop(actor, "ScratchRecordVisibilityV1") == "private", "save changed visibility")
    require(prop(actor, "ScratchRecordCreatedUtcV1") == "2026-08-11T19:00:00Z", "save changed creation time")
    require(not bool(prop(actor, "ScratchRecordHasPublishedRevisionV1")), "save invented published state")
    require(not bool(prop(actor, "ScratchRecordHasSourceAttributionV1")), "save invented attribution")
    emit("IMMUTABLE_METADATA", "PASS")

    stage_save(actor, expected=2, now="2026-08-11T19:02:00Z", duration=25.0, caller_revision=123)
    actor.call_method("SaveDraftV1")
    require(prop(actor, "ResultCodeV1") == "Success", f"second save failed: {prop(actor, 'ResultCodeV1')}|{prop(actor, 'ResultDetailV1')}")
    require(snapshot(actor)[0:2] == (3, "EDD_Repository_A"), "second save generation/slot changed")
    require(int(prop(actor, "ResultCurrentRevisionV1")) == 3, "second save revision was not current+1")
    require(int(prop(actor, "ResultRecordIndexV1")) == 0, "second save result index changed")
    require(list(prop(actor, "ActiveUpdatedUtcV1")) == ["2026-08-11T19:02:00Z"], "second save timestamp index changed")
    second_saved_envelope = list(prop(actor, "ActiveRecordEnvelopesV1"))[0]
    require(second_saved_envelope != first_saved_envelope, "second save did not replace the record envelope")
    require_saved_document(actor, 3, 25.0, "second save")
    emit("SECOND_SAVE", "PASS")

    stage_save(actor, expected=2)
    invoke_rejected(actor, "RevisionConflict", "ExpectedRevisionMismatch", "POST_SAVE_STALE_WRITE", current_revision=3)
    require(int(prop(actor, "ActiveGenerationV1")) == 3, "stale write advanced generation")

    set_prop(actor, "RequestRequesterAccountIdV1", "wrong-owner")
    set_prop(actor, "RequestFlypathIdV1", "save-runtime-a")
    actor.call_method("LoadDraftV1")
    require(prop(actor, "ResultCodeV1") == "Forbidden", "wrong owner loaded saved draft")
    require(not bool(prop(actor, "ResultHasCurrentRevisionV1")), "wrong owner received revision")
    require(prop(actor, "ResultRecordEnvelopeV1") == "", "wrong owner received envelope")
    emit("OWNER_LOAD_BOUNDARY", "PASS")

    require(all(unreal.GameplayStatics.does_save_game_exist(slot, 0) for slot in SLOTS), "A/B SaveGame slots missing")
    latest = unreal.GameplayStatics.load_game_from_slot("EDD_Repository_A", 0)
    require(latest is not None, "could not load latest slot A")
    require(int(prop(latest, "Generation")) == 3, "latest physical generation changed")
    require(bool(prop(latest, "Committed")), "latest physical slot is uncommitted")
    require(list(prop(latest, "RecordEnvelopes")) == list(prop(actor, "ActiveRecordEnvelopesV1")), "physical payload differs from authority")
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
