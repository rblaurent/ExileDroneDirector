"""Create and verify the staged orientation-control compiler seam."""

from __future__ import annotations

import unreal


PREFIX = "EDD_ORIENTATION_COMPILER_CONFIG"
CLIENT = "/Game/Mods/ExileDroneDirector/Core/Client/BPC_EDD_ClientDirector"
QUATS = (
    "OrientationInputStartQuatV1",
    "OrientationInputEndQuatV1",
    "OrientationResultAlignedEndQuatV1",
    "OrientationResultStartControlQuatV1",
    "OrientationResultEndControlQuatV1",
    "OrientationScratchStartExponentQuatV1",
    "OrientationScratchEndExponentQuatV1",
)
VECTORS = (
    "OrientationInputPreviousDeltaVectorV1",
    "OrientationInputNextDeltaVectorV1",
    "OrientationInputStartTangentRateVectorV1",
    "OrientationInputEndTangentRateVectorV1",
    "OrientationResultDeltaVectorV1",
    "OrientationResultTangentRateVectorV1",
)
REALS = (
    "OrientationInputPreviousDurationV1",
    "OrientationInputNextDurationV1",
    "OrientationInputDurationV1",
)
BOOLS = ("OrientationResultValidV1",)
FUNCTIONS = (
    "ComputeOrientationLogDeltaV1",
    "ComputeOrientationTangentRateV1",
    "BuildOrientationSegmentControlsV1",
)


def emit(label, value): unreal.log(f"{PREFIX}|{label}|{value}")
def variants(name):
    snake = "".join(("_"+c.lower()) if c.isupper() else c for c in name).lstrip("_")
    return name, unreal.Name(name), snake, unreal.Name(snake)
def cls():
    value=unreal.EditorAssetLibrary.load_blueprint_class(CLIENT)
    if value is None: raise RuntimeError(CLIENT)
    return value
def default(): return unreal.get_default_object(cls())
def get(name):
    for value in variants(name):
        try:return default().get_editor_property(value)
        except Exception:pass
    raise RuntimeError(f"missing {name}")
def present(name):
    try:get(name);return True
    except Exception:return False
def set_value(name,value):
    for candidate in variants(name):
        try:default().set_editor_property(candidate,value);return
        except Exception:pass
    raise RuntimeError(f"cannot default {name}")


bp=unreal.EditorAssetLibrary.load_asset(CLIENT)
if bp is None:raise RuntimeError(CLIENT)
quat=unreal.load_object(None,"/Script/CoreUObject.Quat")
if quat is None:raise RuntimeError("Quat")
vector=unreal.load_object(None,"/Script/CoreUObject.Vector")
if vector is None:raise RuntimeError("Vector")
groups=(
    (QUATS,unreal.BlueprintEditorLibrary.get_struct_type(quat)),
    (VECTORS,unreal.BlueprintEditorLibrary.get_struct_type(vector)),
    (REALS,unreal.BlueprintEditorLibrary.get_basic_type_by_name("real")),
    (BOOLS,unreal.BlueprintEditorLibrary.get_basic_type_by_name("bool")),
)
for names,pin_type in groups:
    for name in names:
        if present(name):emit("VARIABLE_ALREADY_PRESENT",name);continue
        if not unreal.BlueprintEditorLibrary.add_member_variable(bp,name,pin_type):
            raise RuntimeError(f"add {name}")
        unreal.BlueprintEditorLibrary.compile_blueprint(bp);emit("VARIABLE_CREATED",name)
for name in FUNCTIONS:
    if unreal.BlueprintEditorLibrary.find_graph(bp,unreal.Name(name)) is None:
        if unreal.BlueprintEditorLibrary.add_function_graph(bp,name) is None:raise RuntimeError(f"add {name}")
        emit("FUNCTION_CREATED",name)
    else:emit("FUNCTION_ALREADY_PRESENT",name)
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
identity=unreal.Quat(0,0,0,1)
for name in QUATS:set_value(name,identity)
for name in VECTORS:set_value(name,unreal.Vector(0,0,0))
for name in REALS:set_value(name,0.0)
for name in BOOLS:set_value(name,False)
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
if not unreal.EditorAssetLibrary.save_asset(CLIENT,only_if_is_dirty=False):raise RuntimeError("save failed")
for name in (*QUATS,*VECTORS,*REALS,*BOOLS):emit("DEFAULT_VERIFIED",f"{name}|{get(name)}")
for name in FUNCTIONS:
    if unreal.BlueprintEditorLibrary.find_graph(bp,unreal.Name(name)) is None:raise RuntimeError(name)
    emit("FUNCTION_VERIFIED",name)
emit("COMPLETE",True)
