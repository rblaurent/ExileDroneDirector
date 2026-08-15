"""Offline ownership and lifecycle checks for bounded-event configuration tools."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads(
    (ROOT / "tools/events/bounded_event_adapter_blueprint_schema.json").read_text(encoding="utf-8")
)
CONFIG = (ROOT / "tools/unreal/Configure-BoundedEventAdapter.py").read_text(encoding="utf-8")
RESTORE = (ROOT / "tools/unreal/Restore-BoundedEventAdapterSchemaDefaults.py").read_text(encoding="utf-8")
for label, source in (("config", CONFIG), ("restore", RESTORE)):
    compile(source, label, "exec")
    assert "bounded_event_adapter_blueprint_schema.json" in source
    for forbidden in (
        "CameraTransform", "BodyQuat", "GimbalQuat", "K2_SetActor",
        "Repository", "HUD", "UI",
    ):
        assert forbidden not in source
assert len(SCHEMA["variables"]) == 60
assert len(SCHEMA["functions"]) == 8
for token in (
    "VARIABLE_COUNT", "FUNCTION_COUNT", "String", "Real", "Integer",
    "Boolean", "EXISTING_DEFAULT_PRESERVED", "ARRAY_DEFAULT_VERIFIED",
    "FUNCTION_VERIFIED",
):
    assert token in CONFIG
assert "get_array_type" in CONFIG
assert "add_member_variable" in CONFIG
assert "add_function_graph" in CONFIG
assert "only_if_is_dirty=False" in CONFIG
assert "only_if_is_dirty=False" in RESTORE
assert RESTORE.index("compile_blueprint(blueprint)") < RESTORE.index("load_blueprint_class(CLIENT)")
assert 'spec["container"] == "Array"' in RESTORE
assert "return []" in RESTORE
assert "VARIABLE_COUNT" in RESTORE and "COMPLETE" in RESTORE
print("bounded event-adapter configuration contracts passed")
