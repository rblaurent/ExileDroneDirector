"""Close asset editors before quitting the interactive Enhanced DevKit.

Closing the process while a Blueprint preview scene is still alive can assert
in ``BlueprintEditor.cpp`` during shutdown.  Invoke this through the official
remote-execution seam; it closes every asset editor, waits for Slate to flush
the close operation, and only then requests process exit.
"""

from __future__ import annotations

import unreal


PREFIX = "EDD_SAFE_QUIT"
STATE_KEY = "_EDD_SAFE_QUIT_STATE"
MINIMUM_TICKS = 3
MAXIMUM_TICKS = 120


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}|{label}|{value}")


old_state = globals().get(STATE_KEY)
if old_state and old_state.get("callback") is not None:
    unreal.unregister_slate_post_tick_callback(old_state["callback"])

subsystem = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
if subsystem is None:
    raise RuntimeError("AssetEditorSubsystem is unavailable")

edited_assets = list(subsystem.get_all_edited_assets())
emit("EDITORS_BEFORE_CLOSE", len(edited_assets))
if hasattr(subsystem, "close_all_asset_editors"):
    subsystem.close_all_asset_editors()
else:
    for asset in edited_assets:
        subsystem.close_all_editors_for_asset(asset)

state = {"callback": None, "ticks": 0}
globals()[STATE_KEY] = state


def finish_shutdown(_delta_seconds: float) -> None:
    state["ticks"] += 1
    remaining = len(subsystem.get_all_edited_assets())
    if state["ticks"] < MINIMUM_TICKS:
        return
    if remaining and state["ticks"] < MAXIMUM_TICKS:
        return
    if state["callback"] is not None:
        unreal.unregister_slate_post_tick_callback(state["callback"])
        state["callback"] = None
    if remaining:
        emit("EDITOR_CLOSE_TIMEOUT", remaining)
    else:
        emit("EDITORS_CLOSED", 0)
    emit("QUIT_REQUESTED", state["ticks"])
    unreal.SystemLibrary.quit_editor()


state["callback"] = unreal.register_slate_post_tick_callback(finish_shutdown)
emit("ARMED", True)
