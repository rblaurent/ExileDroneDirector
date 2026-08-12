"""Create and verify the staged quaternion segment-evaluator seam."""

from __future__ import annotations

import unreal


PREFIX = "EDD_TRAJECTORY_QUATERNION_CONFIG"
CLIENT_PATH = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector"
QUAT_NAMES = (
    "TrajectoryInputOrientationStartQuatV1",
    "TrajectoryInputOrientationStartControlQuatV1",
    "TrajectoryInputOrientationEndControlQuatV1",
    "TrajectoryInputOrientationEndQuatV1",
    "TrajectoryResultOrientationQuatV1",
)
BOOL_NAMES = ("TrajectoryResultOrientationValidV1",)
FUNCTION_NAME = "EvaluateSphericalBezierQuaternionV1"


def emit(label, value): unreal.log(f"{PREFIX}|{label}|{value}")
def candidates(name):
    snake="".join(("_"+c.lower()) if c.isupper() else c for c in name).lstrip("_")
    return name,unreal.Name(name),snake,unreal.Name(snake)
def generated_class():
    value=unreal.EditorAssetLibrary.load_blueprint_class(CLIENT_PATH)
    if value is None: raise RuntimeError(CLIENT_PATH)
    return value
def default_object(): return unreal.get_default_object(generated_class())
def get_property(name):
    for candidate in candidates(name):
        try:return default_object().get_editor_property(candidate)
        except Exception:pass
    raise RuntimeError(f"missing {name}")
def has_property(name):
    try:get_property(name);return True
    except Exception:return False
def set_property(name,value):
    for candidate in candidates(name):
        try:default_object().set_editor_property(candidate,value);return
        except Exception:pass
    raise RuntimeError(f"cannot default {name}")


blueprint=unreal.EditorAssetLibrary.load_asset(CLIENT_PATH)
if blueprint is None:raise RuntimeError(CLIENT_PATH)
quat_struct=unreal.load_object(None,"/Script/CoreUObject.Quat")
if quat_struct is None:raise RuntimeError("native Quat ScriptStruct unavailable")
groups=(
    (QUAT_NAMES,unreal.BlueprintEditorLibrary.get_struct_type(quat_struct)),
    (BOOL_NAMES,unreal.BlueprintEditorLibrary.get_basic_type_by_name("bool")),
)
for names,pin_type in groups:
    for name in names:
        if has_property(name):emit("VARIABLE_ALREADY_PRESENT",name);continue
        if not unreal.BlueprintEditorLibrary.add_member_variable(blueprint,name,pin_type):
            raise RuntimeError(f"failed to add {name}")
        unreal.BlueprintEditorLibrary.compile_blueprint(blueprint);emit("VARIABLE_CREATED",name)
if unreal.BlueprintEditorLibrary.find_graph(blueprint,unreal.Name(FUNCTION_NAME)) is None:
    if unreal.BlueprintEditorLibrary.add_function_graph(blueprint,FUNCTION_NAME) is None:
        raise RuntimeError(f"failed to add {FUNCTION_NAME}")
    emit("FUNCTION_CREATED",FUNCTION_NAME)
else:emit("FUNCTION_ALREADY_PRESENT",FUNCTION_NAME)
unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
identity=unreal.Quat(0.0,0.0,0.0,1.0)
for name in QUAT_NAMES:set_property(name,identity)
for name in BOOL_NAMES:set_property(name,False)
unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
if not unreal.EditorAssetLibrary.save_asset(CLIENT_PATH,only_if_is_dirty=False):raise RuntimeError("save failed")
for name in (*QUAT_NAMES,*BOOL_NAMES):emit("DEFAULT_VERIFIED",f"{name}|{get_property(name)}")
if unreal.BlueprintEditorLibrary.find_graph(blueprint,unreal.Name(FUNCTION_NAME)) is None:raise RuntimeError(FUNCTION_NAME)
unreal.BlueprintEditorLibrary.refresh_open_editors_for_blueprint(blueprint)
emit("FUNCTION_VERIFIED",FUNCTION_NAME);emit("COMPLETE",True)
