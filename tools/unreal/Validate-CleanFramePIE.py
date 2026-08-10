r"""One-session PIE acceptance for reversible Clean Frame state.

Arm from the editor console, then start PIE once::

    py exec(open(r'T:\Projects\ExileDroneDirector\tools\unreal\Validate-CleanFramePIE.py').read())

The fixture validates exact Conan HUD/Popup category restoration, preview
suppression, idempotence, normal-exit restoration, and emergency restoration.
The synthetic AlmostEmpty fixture may not instantiate Conan's BaseGameHUD, so
the notification-widget visibility call remains structurally covered and is
visually accepted later in a normal cooked client.
"""

from __future__ import annotations

import time
import traceback


SUPPORT_PATH = r"T:\Projects\ExileDroneDirector\tools\unreal\Validate-PathPreviewMarkersPIE.py"
with open(SUPPORT_PATH, encoding="utf-8") as support_file:
    support_source = support_file.read().split("\ndef validate_projection", 1)[0]
exec(compile(support_source, SUPPORT_PATH, "exec"), globals())

PREFIX = "EDD_CLEAN_FRAME_PIE"


def enum_type():
    direct = getattr(unreal, "GUIModuleCategory", None)
    if direct is not None:
        return direct
    matches = [
        getattr(unreal, name)
        for name in dir(unreal)
        if name.lower().replace("_", "") in {"guimodulecategory", "eguimodulecategory"}
    ]
    require(len(matches) == 1, f"could not resolve GUIModuleCategory enum: {matches}")
    return matches[0]


def enum_value(enum, wanted: str):
    matches = [
        getattr(enum, name)
        for name in dir(enum)
        if name.lower().replace("_", "") == wanted.lower().replace("_", "")
    ]
    require(len(matches) == 1, f"could not resolve {wanted} enum value")
    return matches[0]


def gui(component_value):
    result = unreal.GUIModuleController.get_gui_module_controller(component_value)
    require(result is not None, "GUIModuleController is unavailable")
    return result


def preview(component_value):
    return component_value.get_editor_property("PathPreviewActorV1")


def hidden(actor) -> bool:
    require(actor is not None, "path preview actor is missing")
    errors = []
    for property_name in ("hidden", "b_hidden", "bHidden"):
        try:
            return bool(actor.get_editor_property(property_name))
        except Exception as error:
            errors.append(f"{property_name}:{error}")
    raise RuntimeError(f"could not read actor hidden state; symbols={sorted(name for name in dir(actor) if 'hidden' in name.lower())}; errors={errors}")


def assert_categories(controller, hud, popup, expected_hud: bool, expected_popup: bool) -> None:
    require(bool(controller.is_category_enabled(hud)) == expected_hud, "HUD category mismatch")
    require(bool(controller.is_category_enabled(popup)) == expected_popup, "Popup category mismatch")


def restore_fixture() -> None:
    state = globals().get("_EDD_CLEAN_FRAME_STATE")
    if not state:
        return
    try:
        world_object = pie_world()
        component_value = director(world_object)
        if bool(component_value.get_editor_property("CleanFrameActiveV1")):
            component_value.call_method("ExitCleanFrameV1")
        if bool(component_value.get_editor_property("DroneModeActive")):
            component_value.call_method("ExitDroneMode")
        controller = gui(component_value)
        controller.enable_category(state["hud"], state["original_hud"])
        controller.enable_category(state["popup"], state["original_popup"])
    except Exception as error:
        unreal.log_error(f"{PREFIX}:CLEANUP_EXCEPTION:{error}")


def finish(success: bool) -> None:
    state = globals().get("_EDD_CLEAN_FRAME_STATE")
    if state and state.get("callback") is not None:
        unreal.unregister_slate_post_tick_callback(state["callback"])
        state["callback"] = None
    restore_fixture()
    emit("AUTOMATIC_RESULT", "PASS" if success else "FAIL")
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()


def run_checks() -> None:
    state = globals()["_EDD_CLEAN_FRAME_STATE"]
    world_object = pie_world()
    component_value = director(world_object)
    enum = enum_type()
    hud = enum_value(enum, "HUD")
    popup = enum_value(enum, "POPUP")
    controller = gui(component_value)
    state.update(
        hud=hud,
        popup=popup,
        original_hud=bool(controller.is_category_enabled(hud)),
        original_popup=bool(controller.is_category_enabled(popup)),
    )
    if bool(component_value.get_editor_property("DroneModeActive")):
        component_value.call_method("ExitDroneMode")
    component_value.call_method("EnterDroneMode")
    actor = preview(component_value)
    require(actor is not None, "Drone Mode did not create its path preview")
    require(not hidden(actor), "preview started hidden")

    # Deliberately divergent baseline proves exact per-category restoration.
    controller.enable_category(hud, False)
    controller.enable_category(popup, True)
    assert_categories(controller, hud, popup, False, True)
    component_value.call_method("EnterCleanFrameV1")
    require(bool(component_value.get_editor_property("CleanFrameActiveV1")), "enter did not set active")
    assert_categories(controller, hud, popup, False, False)
    require(hidden(actor), "enter did not hide path preview")
    require(
        not bool(component_value.get_editor_property("CleanFrameRestoreHUDCategoryV1")),
        "HUD baseline was not captured",
    )
    require(
        bool(component_value.get_editor_property("CleanFrameRestorePopupCategoryV1")),
        "Popup baseline was not captured",
    )
    component_value.call_method("EnterCleanFrameV1")
    require(
        not bool(component_value.get_editor_property("CleanFrameRestoreHUDCategoryV1"))
        and bool(component_value.get_editor_property("CleanFrameRestorePopupCategoryV1")),
        "repeated enter overwrote the captured baseline",
    )
    component_value.call_method("ExitCleanFrameV1")
    require(not bool(component_value.get_editor_property("CleanFrameActiveV1")), "exit left active")
    assert_categories(controller, hud, popup, False, True)
    require(not hidden(actor), "exit did not restore path preview")
    component_value.call_method("ExitCleanFrameV1")
    assert_categories(controller, hud, popup, False, True)
    emit("DIRECT_TOGGLE_AND_IDEMPOTENCE", "PASS")

    controller.enable_category(hud, True)
    controller.enable_category(popup, False)
    component_value.call_method("EnterCleanFrameV1")
    assert_categories(controller, hud, popup, False, False)
    component_value.call_method("ExitDroneMode")
    require(not bool(component_value.get_editor_property("CleanFrameActiveV1")), "normal exit left active")
    assert_categories(controller, hud, popup, True, False)
    require(preview(component_value) is None, "normal exit did not destroy preview")
    emit("NORMAL_EXIT_RESTORATION", "PASS")

    component_value.call_method("EnterDroneMode")
    actor = preview(component_value)
    require(actor is not None, "re-entry did not recreate preview")
    controller.enable_category(hud, True)
    controller.enable_category(popup, True)
    component_value.call_method("EnterCleanFrameV1")
    component_value.call_method("EmergencyExitDroneMode")
    require(not bool(component_value.get_editor_property("CleanFrameActiveV1")), "emergency exit left active")
    assert_categories(controller, hud, popup, True, True)
    require(preview(component_value) is None, "emergency exit did not destroy preview")
    emit("EMERGENCY_EXIT_RESTORATION", "PASS")


def tick(_delta_seconds: float) -> None:
    state = globals()["_EDD_CLEAN_FRAME_STATE"]
    try:
        if state["stage"] == "wait_for_pie":
            try:
                world_object = pie_world()
                component_value = director(world_object)
                require(component_value.get_owner() is not None, "client director owner is not ready")
                require(component_value.get_owner().has_actor_begun_play(), "owner BeginPlay is not ready")
            except Exception:
                if time.monotonic() - state["armed_at"] > 45.0:
                    raise RuntimeError("PIE did not become ready within 45 seconds")
                return
            state["stage"] = "settle"
            state["stage_at"] = time.monotonic()
            emit("HOST_RUNTIME_READY", True)
            return
        if state["stage"] == "settle":
            if time.monotonic() - state["stage_at"] < 1.0:
                return
            run_checks()
            state["stage"] = "complete"
            finish(True)
    except Exception as error:
        unreal.log_error(f"{PREFIX}:AUTOMATIC_EXCEPTION:{error}\n{traceback.format_exc()}")
        state["stage"] = "failed"
        finish(False)


old_state = globals().get("_EDD_CLEAN_FRAME_STATE")
if old_state and old_state.get("callback") is not None:
    unreal.unregister_slate_post_tick_callback(old_state["callback"])

_EDD_CLEAN_FRAME_STATE = {
    "stage": "wait_for_pie",
    "armed_at": time.monotonic(),
    "stage_at": time.monotonic(),
    "callback": None,
}
_EDD_CLEAN_FRAME_STATE["callback"] = unreal.register_slate_post_tick_callback(tick)
emit("ARMED", True)
