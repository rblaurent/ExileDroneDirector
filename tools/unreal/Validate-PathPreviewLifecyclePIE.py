r"""Single-session PIE acceptance for client-owned path-preview lifecycle.

Arm from the editor console, then start PIE once::

    py exec(open(r'T:\Projects\ExileDroneDirector\tools\unreal\Validate-PathPreviewLifecyclePIE.py').read())

The automatic driver validates create/reuse, production waypoint mutation,
playback coexistence, idempotent cleanup, a fresh re-entry instance, and remote
client isolation when the current PIE configuration has a second client.  It
ends PIE itself and never changes class defaults.
"""

from __future__ import annotations

import time
import traceback


SUPPORT_PATH = r"T:\Projects\ExileDroneDirector\tools\unreal\Validate-PathPreviewMarkersPIE.py"
with open(SUPPORT_PATH, encoding="utf-8") as support_file:
    support_source = support_file.read().split("\ndef validate_projection", 1)[0]
exec(compile(support_source, SUPPORT_PATH, "exec"), globals())

PREFIX = "EDD_PATH_PREVIEW_LIFECYCLE_PIE"
REMOTE_WORLD_PATH = "/Game/Dev/UEDPIE_1_AlmostEmpty.AlmostEmpty"


def preview_actors(world_object):
    cls = exact_class(PREVIEW_CLASS_PATH)
    return [
        actor
        for actor in unreal.GameplayStatics.get_all_actors_of_class(world_object, cls)
        if actor.get_class() == cls
    ]


def preview_ref(component_value):
    return component_value.get_editor_property("PathPreviewActorV1")


def same_object(left, right) -> bool:
    return left is not None and right is not None and left == right


def assert_single_owned_preview(world_object, component_value, expected=None):
    values = preview_actors(world_object)
    require(len(values) == 1, f"expected one path preview actor, found {len(values)}")
    owned = preview_ref(component_value)
    require(owned is not None, "owned preview reference is None")
    require(same_object(values[0], owned), "owned preview reference does not match the live actor")
    if expected is not None:
        require(same_object(owned, expected), "refresh replaced the owned preview actor")
    return owned


def assert_projection(component_value, actor, expected_markers: int, expected_segments: int) -> None:
    draft = component_value.get_editor_property("DraftDocumentV1")
    projected = actor.get_editor_property("PreviewDocumentV1")
    require(projected.export_text() == draft.export_text(), "preview document does not match the draft document")
    markers = component(actor, "WaypointMarkersV1")
    segments = component(actor, "SegmentLinesV1")
    require(markers.get_instance_count() == expected_markers, (
        f"marker count expected {expected_markers}, got {markers.get_instance_count()}"
    ))
    require(segments.get_instance_count() == expected_segments, (
        f"segment count expected {expected_segments}, got {segments.get_instance_count()}"
    ))


def remote_isolation(*, wait_for_ready: bool = False) -> bool:
    remote_world = unreal.find_object(None, REMOTE_WORLD_PATH)
    if remote_world is None:
        if wait_for_ready:
            return False
        emit("REMOTE_ISOLATION", "SKIP_ONE_PLAYER_PIE")
        return True
    controller = unreal.GameplayStatics.get_player_controller(remote_world, 0)
    if controller is None:
        if wait_for_ready:
            return False
        require(False, "remote PlayerController did not become ready")
    values = controller.get_components_by_class(exact_class(CLIENT_CLASS_PATH))
    if len(values) != 1:
        if wait_for_ready:
            return False
        require(False, f"expected one remote client director, found {len(values)}")
    remote_component = values[0]
    require(preview_ref(remote_component) is None, "host preview reference leaked to remote client")
    require(len(preview_actors(remote_world)) == 0, "host preview actor leaked to remote client world")
    emit("REMOTE_ISOLATION", "PASS")
    return True


def cleanup_host() -> None:
    try:
        world_object = pie_world()
        component_value = director(world_object)
        component_value.call_method("StopLinearPlayback")
        if bool(component_value.get_editor_property("DroneModeActive")):
            component_value.call_method("ExitDroneMode")
        component_value.call_method("DestroyPathPreviewV1")
    except Exception as error:
        unreal.log_error(f"{PREFIX}:CLEANUP_EXCEPTION:{error}")


def finish(success: bool) -> None:
    state = globals().get("_EDD_PATH_PREVIEW_LIFECYCLE_STATE")
    if state and state.get("callback") is not None:
        unreal.unregister_slate_post_tick_callback(state["callback"])
        state["callback"] = None
    emit("AUTOMATIC_RESULT", "PASS" if success else "FAIL")
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()


def run_primary_checks() -> None:
    state = globals()["_EDD_PATH_PREVIEW_LIFECYCLE_STATE"]
    world_object = pie_world()
    component_value = director(world_object)
    require(len(component_value.get_editor_property("DraftWaypointsV1")) == 0, "draft fixture did not start empty")
    if bool(component_value.get_editor_property("DroneModeActive")):
        component_value.call_method("ExitDroneMode")
    component_value.call_method("DestroyPathPreviewV1")
    require(preview_ref(component_value) is None, "baseline destroy left an owned preview reference")
    require(len(preview_actors(world_object)) == 0, "baseline contains a preview actor")

    component_value.call_method("EnterDroneMode")
    emit(
        "ENTER_DIAGNOSTIC",
        f"active={bool(component_value.get_editor_property('DroneModeActive'))}|"
        f"owned={preview_ref(component_value)}|actors={len(preview_actors(world_object))}",
    )
    first = assert_single_owned_preview(world_object, component_value)
    assert_projection(component_value, first, 0, 0)
    emit("ENTER_CREATED_ONE", first.get_path_name())

    component_value.call_method("RefreshPathPreviewV1")
    component_value.call_method("RefreshPathPreviewV1")
    assert_single_owned_preview(world_object, component_value, first)
    emit("REPEATED_REFRESH_REUSED_ONE", True)

    component_value.call_method("EnterDroneMode")
    assert_single_owned_preview(world_object, component_value, first)
    emit("REPEATED_ENTER_REUSED_ONE", True)

    drone = exact_drone(world_object)
    for location, rotation in PLACEMENTS:
        require(drone.set_actor_location(location, False, False), f"failed to place drone:{location}")
        require(drone.set_actor_rotation(rotation, False), f"failed to rotate drone:{rotation}")
        component_value.call_method("CaptureCurrentWaypoint")
        assert_single_owned_preview(world_object, component_value, first)
    assert_projection(component_value, first, 2, 1)
    emit("PRODUCTION_CAPTURE_REFRESHED_TWO_ONE", True)

    component_value.call_method("StartLinearPlayback")
    require(bool(component_value.get_editor_property("PlaybackActive")), "two-waypoint playback did not start")
    component_value.call_method("UpdateLinearPlayback")
    assert_single_owned_preview(world_object, component_value, first)
    component_value.call_method("StopLinearPlayback")
    require(not bool(component_value.get_editor_property("PlaybackActive")), "playback did not stop")
    assert_single_owned_preview(world_object, component_value, first)
    emit("PLAYBACK_PRESERVED_PREVIEW", True)

    state["first_actor"] = first
    state["first_path"] = first.get_path_name()
    component_value.call_method("ExitDroneMode")
    require(preview_ref(component_value) is None, "exit did not clear the owned preview reference")
    component_value.call_method("DestroyPathPreviewV1")
    component_value.call_method("DestroyPathPreviewV1")
    require(preview_ref(component_value) is None, "repeated destroy restored a stale reference")
    state["stage"] = "verify_destroyed"
    state["stage_at"] = time.monotonic()
    emit("EXIT_AND_REPEATED_DESTROY_DISPATCHED", True)


def verify_destroyed_and_reenter() -> None:
    state = globals()["_EDD_PATH_PREVIEW_LIFECYCLE_STATE"]
    world_object = pie_world()
    component_value = director(world_object)
    require(len(preview_actors(world_object)) == 0, "destroyed preview still exists in the world")
    component_value.call_method("EnterDroneMode")
    second = assert_single_owned_preview(world_object, component_value)
    require(second.get_path_name() != state["first_path"], "re-entry did not create a fresh preview instance")
    assert_projection(component_value, second, 2, 1)
    emit("REENTER_CREATED_FRESH_ONE", second.get_path_name())
    component_value.call_method("ExitDroneMode")
    require(preview_ref(component_value) is None, "final exit did not clear the owned preview reference")
    state["stage"] = "verify_final_cleanup"
    state["stage_at"] = time.monotonic()


def tick(_delta_seconds: float) -> None:
    state = globals()["_EDD_PATH_PREVIEW_LIFECYCLE_STATE"]
    try:
        if state["stage"] == "wait_for_pie":
            try:
                world_object = pie_world()
                controller = unreal.GameplayStatics.get_player_controller(world_object, 0)
                require(controller is not None, "host PlayerController is not ready")
                component_value = director(world_object)
                require(component_value.get_owner() == controller, "client director owner is not the host controller")
                require(controller.has_actor_begun_play(), "host controller BeginPlay has not run")
                require(controller.get_controlled_pawn() is not None, "host controlled pawn is not ready")
                require(controller.get_view_target() is not None, "host view target is not ready")
            except Exception:
                if time.monotonic() - state["armed_at"] > 45.0:
                    raise RuntimeError(f"{PREFIX}:PIE did not become ready within 45 seconds")
                return
            state["stage"] = "wait_for_ready"
            state["stage_at"] = time.monotonic()
            emit("HOST_RUNTIME_READY", True)
            return
        if state["stage"] == "wait_for_ready":
            if time.monotonic() - state["stage_at"] < 1.0:
                return
            run_primary_checks()
            return
        if time.monotonic() - state["stage_at"] < 0.25:
            return
        if state["stage"] == "verify_destroyed":
            verify_destroyed_and_reenter()
            return
        if state["stage"] == "verify_final_cleanup":
            world_object = pie_world()
            component_value = director(world_object)
            require(preview_ref(component_value) is None, "final cleanup restored an owned reference")
            require(len(preview_actors(world_object)) == 0, "final cleanup left a preview actor")
            remote_elapsed = time.monotonic() - state["stage_at"]
            if remote_elapsed < 2.0:
                return
            if not remote_isolation(wait_for_ready=True):
                if remote_elapsed < 8.0:
                    return
                remote_isolation()
            emit("FINAL_CLEANUP", "PASS")
            state["stage"] = "complete"
            finish(True)
    except Exception as error:
        unreal.log_error(f"{PREFIX}:AUTOMATIC_EXCEPTION:{error}\n{traceback.format_exc()}")
        cleanup_host()
        state["stage"] = "failed"
        finish(False)


existing = globals().get("_EDD_PATH_PREVIEW_LIFECYCLE_STATE")
if existing and existing.get("callback") is not None:
    unreal.unregister_slate_post_tick_callback(existing["callback"])
state = {
    "armed_at": time.monotonic(),
    "callback": None,
    "stage": "wait_for_pie",
    "stage_at": 0.0,
}
globals()["_EDD_PATH_PREVIEW_LIFECYCLE_STATE"] = state
state["callback"] = unreal.register_slate_post_tick_callback(tick)
emit("AUTOMATIC_ARMED", True)
emit("NEXT", "START_PIE_ONCE")
