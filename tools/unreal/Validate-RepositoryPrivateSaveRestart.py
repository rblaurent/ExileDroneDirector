"""Fresh-process recovery and resumed-write acceptance for SaveDraftV1."""

from __future__ import annotations

import unreal


PREFIX = "EDD_PRIVATE_SAVE_RESTART"
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


def stage_document(actor, revision: int, duration: float) -> None:
    document = prop(actor, "RequestDraftDocumentV1")
    for name, value in (
        ("SchemaVersion", 1),
        ("TrajectoryEngineVersion", 1),
        ("RevisionNumber", revision),
        ("RegionId", "ExiledLands"),
        ("DurationSeconds", duration),
        ("DefaultFlightProfile", "cinematic_drone"),
        ("Waypoints", []),
        ("Segments", []),
        ("ContentHash", "restart-caller-hash"),
    ):
        set_document_prop(document, name, value)
    set_prop(actor, "ScratchDocumentV1", document)
    actor.call_method("EncodeDocumentV1")
    actor.call_method("DecodeDocumentV1")
    require(bool(prop(actor, "ScratchValidV1")), "restart document fixture did not round-trip")
    set_prop(actor, "RequestDraftDocumentV1", prop(actor, "ScratchDocumentV1"))


def invoke_load(actor, owner: str) -> None:
    set_prop(actor, "RequestRequesterAccountIdV1", owner)
    set_prop(actor, "RequestFlypathIdV1", "save-runtime-a")
    actor.call_method("LoadDraftV1")


def cleanup() -> None:
    for slot in SLOTS:
        if unreal.GameplayStatics.does_save_game_exist(slot, 0):
            require(unreal.GameplayStatics.delete_game_in_slot(slot, 0), f"could not delete {slot}")
        require(not unreal.GameplayStatics.does_save_game_exist(slot, 0), f"slot survived cleanup: {slot}")


actor = None
try:
    require(all(unreal.GameplayStatics.does_save_game_exist(slot, 0) for slot in SLOTS), "save fixtures missing before restart")
    repository_class = unreal.load_class(None, CLASS_PATH)
    require(repository_class is not None, "repository generated class missing")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    require(subsystem is not None, "EditorActorSubsystem unavailable")
    actor = subsystem.spawn_actor_from_class(repository_class, unreal.Vector(0, 0, -100000), unreal.Rotator(), False)
    require(actor is not None, "could not spawn repository actor")
    actor.call_method("LoadRepositoryV1")

    require(bool(prop(actor, "RepositoryLoadedV1")), "repository did not load")
    require(int(prop(actor, "ActiveGenerationV1")) == 3, "recovered generation changed")
    require(str(prop(actor, "ActiveSlotV1")) == "EDD_Repository_A", "recovered slot changed")
    require(list(prop(actor, "ActiveFlypathIdsV1")) == ["save-runtime-a"], "recovered ID index changed")
    require(list(prop(actor, "ActiveOwnerAccountIdsV1")) == ["save-owner"], "recovered owner index changed")
    require(list(prop(actor, "ActiveVisibilitiesV1")) == ["private"], "recovered visibility changed")
    require(list(prop(actor, "ActiveUpdatedUtcV1")) == ["2026-08-11T19:02:00Z"], "recovered updated index changed")
    require(len(list(prop(actor, "ActiveRecordEnvelopesV1"))) == 1, "recovered record count changed")
    emit("RECOVERY", "PASS")

    invoke_load(actor, "save-owner")
    require(prop(actor, "ResultCodeV1") == "Success", "owner reload failed")
    require(int(prop(actor, "ResultCurrentRevisionV1")) == 3, "recovered revision changed")
    document = prop(actor, "ResultDraftDocumentV1")
    require(int(document_prop(document, "RevisionNumber")) == 3, "recovered typed revision changed")
    require(abs(float(document_prop(document, "DurationSeconds")) - 25.0) < 0.001, "recovered duration changed")
    emit("OWNER_RELOAD", "PASS")

    invoke_load(actor, "wrong-owner")
    require(prop(actor, "ResultCodeV1") == "Forbidden", "wrong owner crossed restart boundary")
    require(not bool(prop(actor, "ResultHasCurrentRevisionV1")), "wrong owner received revision")
    require(prop(actor, "ResultRecordEnvelopeV1") == "", "wrong owner received envelope")
    emit("OWNER_ISOLATION", "PASS")

    # Prove optimistic concurrency is still enforced after recovery.
    set_prop(actor, "RequestRequesterAccountIdV1", "save-owner")
    set_prop(actor, "RequestFlypathIdV1", "save-runtime-a")
    set_prop(actor, "RequestExpectedRevisionV1", 2)
    set_prop(actor, "RequestNowUtcV1", "2026-08-11T19:03:00Z")
    stage_document(actor, 444, 33.0)
    before = (
        int(prop(actor, "ActiveGenerationV1")),
        str(prop(actor, "ActiveSlotV1")),
        tuple(prop(actor, "ActiveRecordEnvelopesV1")),
        tuple(prop(actor, "ActiveUpdatedUtcV1")),
    )
    actor.call_method("SaveDraftV1")
    require(prop(actor, "ResultCodeV1") == "RevisionConflict", "restart stale write was accepted")
    require(bool(prop(actor, "ResultHasCurrentRevisionV1")), "restart conflict omitted current revision")
    require(int(prop(actor, "ResultCurrentRevisionV1")) == 3, "restart conflict revision changed")
    after = (
        int(prop(actor, "ActiveGenerationV1")),
        str(prop(actor, "ActiveSlotV1")),
        tuple(prop(actor, "ActiveRecordEnvelopesV1")),
        tuple(prop(actor, "ActiveUpdatedUtcV1")),
    )
    require(after == before, "restart stale write mutated authority")
    emit("RESTART_CONFLICT", "PASS")

    # Resume writing from the recovered state: generation 4 must alternate to B.
    set_prop(actor, "RequestExpectedRevisionV1", 3)
    actor.call_method("SaveDraftV1")
    require(prop(actor, "ResultCodeV1") == "Success", f"restart save failed: {prop(actor, 'ResultCodeV1')}|{prop(actor, 'ResultDetailV1')}")
    require(int(prop(actor, "ResultCurrentRevisionV1")) == 4, "restart save revision changed")
    require(int(prop(actor, "ResultRecordIndexV1")) == 0, "restart save result index changed")
    require(int(prop(actor, "ActiveGenerationV1")) == 4, "restart save generation changed")
    require(str(prop(actor, "ActiveSlotV1")) == "EDD_Repository_B", "restart save slot changed")
    require(list(prop(actor, "ActiveUpdatedUtcV1")) == ["2026-08-11T19:03:00Z"], "restart save updated index changed")
    invoke_load(actor, "save-owner")
    require(prop(actor, "ResultCodeV1") == "Success", "post-restart owner load failed")
    require(int(prop(actor, "ResultCurrentRevisionV1")) == 4, "post-restart owner revision changed")
    document = prop(actor, "ResultDraftDocumentV1")
    require(int(document_prop(document, "RevisionNumber")) == 4, "post-restart typed revision changed")
    require(abs(float(document_prop(document, "DurationSeconds")) - 33.0) < 0.001, "post-restart duration changed")
    latest = unreal.GameplayStatics.load_game_from_slot("EDD_Repository_B", 0)
    require(latest is not None, "post-restart slot B missing")
    require(int(prop(latest, "Generation")) == 4, "post-restart physical generation changed")
    require(bool(prop(latest, "Committed")), "post-restart physical slot is uncommitted")
    require(list(prop(latest, "RecordEnvelopes")) == list(prop(actor, "ActiveRecordEnvelopesV1")), "post-restart physical payload mismatch")
    emit("RESUMED_SAVE", "PASS")
    emit("RESULT", "PASS")
finally:
    if actor is not None:
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        if subsystem is not None:
            subsystem.destroy_actor(actor)
    cleanup()
    emit("CLEANUP", "PASS")
