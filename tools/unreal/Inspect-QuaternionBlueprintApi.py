"""Emit Enhanced Kismet quaternion/rotator functions needed by Flypath codecs.

The Blueprint document contract stores normalized quaternions, while the proven
authoring bridge currently owns an Unreal Transform.  This read-only probe locks
the native conversion surface before codec graph generation depends on it.
"""

from __future__ import annotations

import unreal


PREFIX = "EDD_QUATERNION_BLUEPRINT_API"
TOKENS = ("quat", "rotator")
REQUIRED_METHODS = (
    "conv_rotator_to_quaternion",
    "quat_rotator",
    "quat_is_finite",
    "quat_is_normalized",
    "quat_normalized",
)


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}:{label}:{value}")


library_class = unreal.load_class(None, "/Script/Engine.KismetMathLibrary")
if library_class is None:
    raise RuntimeError("Could not load /Script/Engine.KismetMathLibrary")

emit("CLASS", library_class.get_path_name())
emit("PYTHON_TYPE", type(library_class).__name__)
for global_name in sorted(name for name in dir(unreal) if "kismet" in name.lower()):
    emit("UNREAL_GLOBAL", global_name)
for global_name in sorted(name for name in dir(unreal) if "type" in name.lower() and "class" in name.lower()):
    emit("TYPE_HOOK", global_name)

library_type = None
get_type_from_class = getattr(unreal, "get_type_from_class", None)
if callable(get_type_from_class):
    library_type = get_type_from_class(library_class)
    emit("GENERATED_TYPE", getattr(library_type, "__name__", repr(library_type)))

surface = library_type if library_type is not None else library_class
for method_name in REQUIRED_METHODS:
    if not callable(getattr(surface, method_name, None)):
        raise RuntimeError(f"Required Kismet math method is missing: {method_name}")
    emit("REQUIRED", method_name)

for method_name in sorted(dir(surface)):
    if not any(token in method_name for token in TOKENS):
        continue
    method = getattr(surface, method_name, None)
    if not callable(method):
        continue
    documentation = (method.__doc__ or "").replace("\r", " ").replace("\n", " ")
    emit(f"DOC:{method_name}", " ".join(documentation.split()))

emit("COMPLETE", True)
