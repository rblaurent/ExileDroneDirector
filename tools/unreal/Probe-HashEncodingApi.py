"""Discover Enhanced Blueprint/Python hash and text-byte conversion seams.

Read-only.  This deliberately searches every exposed Unreal Python type rather
than only the familiar Kismet libraries, because Conan plugins may contribute a
usable Blueprint-callable helper under a non-obvious class name.
"""

from __future__ import annotations

import json

import unreal


PREFIX = "EDD_HASH_ENCODING_API"
KEYWORDS = (
    "sha1",
    "sha224",
    "sha256",
    "sha384",
    "sha512",
    "secure_hash",
    "hash",
    "digest",
    "md5",
    "crc",
    "byte",
    "utf",
    "encoding",
    "base64",
    "character_as_number",
)


def emit(label: str, value) -> None:
    unreal.log(f"{PREFIX}|{label}|{json.dumps(value, default=str, sort_keys=True)}")


def relevant(name: str) -> bool:
    if name.startswith("_"):
        return False
    lowered = name.lower()
    return any(keyword in lowered for keyword in KEYWORDS)


top_level = sorted(name for name in dir(unreal) if relevant(name))
emit("top_level", top_level)

matches: dict[str, list[str]] = {}
failures: dict[str, str] = {}
for symbol_name in sorted(name for name in dir(unreal) if not name.startswith("_")):
    try:
        symbol = getattr(unreal, symbol_name)
        members = sorted(name for name in dir(symbol) if relevant(name))
    except Exception as error:  # pragma: no cover - defensive reflection boundary
        failures[symbol_name] = f"{type(error).__name__}: {error}"
        continue
    if members:
        matches[symbol_name] = members

emit("type_members", matches)
emit("reflection_failures", failures)
emit("complete", True)
