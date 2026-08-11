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

ordered_a = unreal.PlayFabJsonObject.construct_json_object(None)
ordered_b = unreal.PlayFabJsonObject.construct_json_object(None)
if ordered_a is None or ordered_b is None:
    raise RuntimeError("Could not construct canonical-order fixtures")
ordered_a.set_string_field("zeta", "last")
ordered_a.set_string_field("alpha", "first")
ordered_b.set_string_field("alpha", "first")
ordered_b.set_string_field("zeta", "last")
order_a = ordered_a.encode_json()
order_b = ordered_b.encode_json()
if order_a != '{"zeta":"last","alpha":"first"}':
    raise RuntimeError(f"Unexpected first insertion order: {order_a!r}")
if order_b != '{"alpha":"first","zeta":"last"}':
    raise RuntimeError(f"Unexpected second insertion order: {order_b!r}")
if order_a == order_b:
    raise RuntimeError("PlayFab field-order probe no longer distinguishes insertion order")

emit("ROUND_TRIP_VERIFIED", actual)
emit("INSERTION_ORDER_VERIFIED", f"{order_a}|{order_b}")
emit("COMPLETE", True)
