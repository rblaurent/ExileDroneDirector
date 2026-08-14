"""Offline ownership and lifecycle checks for camera scalar-track live tooling."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CONFIG=(ROOT/"tools/unreal/Configure-CameraScalarTrackAssembly.py").read_text(encoding="utf-8")
RUNTIME=(ROOT/"tools/unreal/Validate-CameraScalarTrackRuntime.py").read_text(encoding="utf-8")
PIE=(ROOT/"tools/unreal/Validate-CameraScalarTrackPIE.py").read_text(encoding="utf-8")
RESTORE=(ROOT/"tools/unreal/Restore-CameraScalarTrackSchemaDefaults.py").read_text(encoding="utf-8")
DEFAULTS=(ROOT/"tools/unreal/Validate-CameraScalarTrackSchemaDefaults.py").read_text(encoding="utf-8")
for label,source in (("config",CONFIG),("runtime",RUNTIME),("PIE",PIE),("restore",RESTORE),("defaults",DEFAULTS)):
    compile(source,label,"exec")
    assert "camera_scalar_track_blueprint_schema.json" in source
    assert "CameraTransform" not in source
for token in ("VARIABLE_COUNT","FUNCTION_COUNT","FUNCTION_ALREADY_PRESENT"):assert token in CONFIG
for token in ("FORWARD_TRACKS","REVERSE_TRACKS","QUERY_EVALUATIONS","INVALID_FAMILIES","DEFAULTS_RESTORED"):assert token in RUNTIME
for token in ("OPTICAL_MIDPOINT","GAME_WORLD_RESULT","DEFAULTS_RESTORED","editor_request_begin_play","editor_request_end_play","STATE_NAMES"):assert token in PIE
for source in (RUNTIME,PIE):
    assert 'ARRAY_NAMES=frozenset(' in source
    assert 'def clone(name,value):return list(value) if name in ARRAY_NAMES else value' in source
assert "compile_blueprint" not in PIE and 'state["originals"]={name:clone(name,get(state["defaults"],name)) for name in STATE_NAMES}' in PIE
assert "only_if_is_dirty=False" in RESTORE
assert RESTORE.index("compile_blueprint(blueprint)")<RESTORE.index("load_blueprint_class(CLIENT)")
assert 'spec["container"]=="Array"' in RESTORE and "return []" in RESTORE
for token in ("BEFORE_COMPILE","AFTER_COMPILE","COMPLETE"):assert token in DEFAULTS
assert "save_asset" not in DEFAULTS and "set_editor_property" not in DEFAULTS
print("camera scalar-track live-tool contracts passed")
