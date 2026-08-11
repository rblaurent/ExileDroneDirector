"""Emit the exact Enhanced PlayFab JSON callable surface used by the repository.

This is a read-only reflection probe.  Its output is the source of truth for
the native function names and Python-visible signatures that the reviewed
Blueprint node-form fixture must represent.
"""

from __future__ import annotations

import unreal


PREFIX = "EDD_REPOSITORY_JSON_API"
METHODS = (
    "construct_json_object",
    "set_string_field",
    "get_string_field",
    "set_bool_field",
    "get_bool_field",
    "set_number_field",
    "get_number_field",
    "set_string_array_field",
    "get_string_array_field",
    "set_number_array_field",
    "get_number_array_field",
    "set_object_field",
    "get_object_field",
    "set_object_array_field",
    "get_object_array_field",
    "has_field",
    "get_field_names",
    "set_field_null",
    "get_field",
    "encode_json",
    "decode_json",
)

VALUE_METHOD_TOKENS = ("null", "type", "bool", "number", "string", "object", "array")


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}:{label}:{value}")


emit("CLASS", unreal.PlayFabJsonObject.__name__)
for method_name in METHODS:
    method = getattr(unreal.PlayFabJsonObject, method_name, None)
    emit(f"PRESENT:{method_name}", method is not None)
    if method is not None:
        documentation = (method.__doc__ or "").replace("\r", " ").replace("\n", " ")
        emit(f"DOC:{method_name}", " ".join(documentation.split()))

emit("VALUE_CLASS", unreal.PlayFabJsonValue.__name__)
for method_name in sorted(dir(unreal.PlayFabJsonValue)):
    if not any(token in method_name for token in VALUE_METHOD_TOKENS):
        continue
    method = getattr(unreal.PlayFabJsonValue, method_name, None)
    if not callable(method):
        continue
    documentation = (method.__doc__ or "").replace("\r", " ").replace("\n", " ")
    emit(f"VALUE_DOC:{method_name}", " ".join(documentation.split()))

emit("COMPLETE", True)
