"""Prove the runtime JSON dependency needed by the Blueprint record codec."""

from __future__ import annotations

import unreal


PREFIX = "EDD_REPOSITORY_JSON_CODEC"


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}:{label}:{value}")


root = unreal.PlayFabJsonObject.construct_json_object(None)
nested = unreal.PlayFabJsonObject.construct_json_object(None)
if root is None or nested is None:
    raise RuntimeError("Could not construct PlayFab JSON objects")

nested.set_string_field("title", "Unicode flight — 北風")
nested.set_bool_field("private", True)
nested.set_string_array_field("ids", ["one", "two", "three"])
root.set_string_field("schemaVersion", "1")
root.set_string_field("revision", "17")
root.set_object_field("record", nested)
encoded = root.encode_json()
if not encoded:
    raise RuntimeError("EncodeJson returned an empty string")

decoded = unreal.PlayFabJsonObject.construct_json_object(None)
if decoded is None or not decoded.decode_json(encoded):
    raise RuntimeError("DecodeJson rejected an encoded object")
decoded_nested = decoded.get_object_field("record")
actual = (
    decoded.get_string_field("schemaVersion"),
    decoded.get_string_field("revision"),
    decoded_nested.get_string_field("title"),
    decoded_nested.get_bool_field("private"),
    list(decoded_nested.get_string_array_field("ids")),
)
expected = ("1", "17", "Unicode flight — 北風", True, ["one", "two", "three"])
if actual != expected:
    raise RuntimeError(f"JSON round trip mismatch: {actual!r}")

emit("ROUND_TRIP_VERIFIED", actual)
emit("COMPLETE", True)
