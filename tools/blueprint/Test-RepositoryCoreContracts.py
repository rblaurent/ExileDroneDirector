"""Semantic graph contracts for repository result reset and ID lookup."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys


def load_contracts(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Test-WaypointCaptureContracts.py"
    spec = importlib.util.spec_from_file_location("edd_repository_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load contract helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def one(c, nodes, marker: str):
    return c.one(nodes, marker)


def assert_closed(c, nodes, expected: int, entry_name: str | None) -> None:
    c.require(len(nodes) == expected, f"Expected {expected} nodes; found {len(nodes)}")
    known = set(nodes)
    unknown = sorted({
        target
        for node in nodes.values()
        for pin in node.pins.values()
        for target, _ in pin.links
        if target not in known
    })
    c.require(not unknown, f"External links are forbidden: {unknown}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (1 if entry_name else 0), "Function entry inclusion changed")
    if entry_name:
        c.require(f'MemberName="{entry_name}"' in entries[0].text, "Wrong function entry")


def assert_reset(c, nodes, *, paste: bool) -> None:
    assert_closed(c, nodes, 9 if not paste else 8, None if paste else "ResetRepositoryResultV1")
    order = (
        ("ResultCodeV1", "Success"),
        ("ResultDetailV1", ""),
        ("ResultHasCurrentRevisionV1", "false"),
        ("ResultCurrentRevisionV1", "0"),
        ("ResultRecordIndexV1", "-1"),
        ("ResultRecordEnvelopeV1", ""),
    )
    setters = [one(c, nodes, f'MemberName="{name}"') for name, _ in order]
    metadata = one(c, nodes, 'MemberName="ResultMetadataEnvelopesV1"')
    clear = one(c, nodes, 'MemberName="Array_Clear"')
    for node, (name, default) in zip(setters, order):
        line = next(line for line in node.text.splitlines() if f'PinName="{name}"' in line)
        c.require(f'DefaultValue="{default}"' in line, f"{name} reset default changed")
    if paste:
        c.require(not setters[0].pins["execute"].links, "Paste body must expose the first setter")
    else:
        entry = one(c, nodes, 'FunctionReference=(MemberName="ResetRepositoryResultV1")')
        c.require_link(entry, "then", setters[0], "execute", "Reset entry must reach first setter")
    for left, right in zip(setters, setters[1:]):
        c.require_link(left, "then", right, "execute", "Result fields must reset in fixed order")
    c.require_link(setters[-1], "then", clear, "execute", "Metadata clear must be terminal")
    c.require_link(metadata, "ResultMetadataEnvelopesV1", clear, "TargetArray", "Reset must clear metadata results")


def assert_find(c, nodes, *, paste: bool) -> None:
    assert_closed(c, nodes, 5 if not paste else 4, None if paste else "FindRecordIndexV1")
    ids = one(c, nodes, 'MemberName="ActiveFlypathIdsV1"')
    request = one(c, nodes, 'MemberName="RequestFlypathIdV1"')
    find = one(c, nodes, 'MemberName="Array_Find"')
    result = one(c, nodes, 'MemberName="ResultRecordIndexV1"')
    c.require_link(ids, "ActiveFlypathIdsV1", find, "TargetArray", "Lookup must use the derived ID index")
    c.require_link(request, "RequestFlypathIdV1", find, "ItemToFind", "Lookup must use the staged request ID")
    c.require_link(find, "ReturnValue", result, "ResultRecordIndexV1", "Array_Find result must be committed exactly")
    if paste:
        c.require(not result.pins["execute"].links, "Paste body must expose the result setter")
    else:
        entry = one(c, nodes, 'FunctionReference=(MemberName="FindRecordIndexV1")')
        c.require_link(entry, "then", result, "execute", "Find entry must commit the computed index")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    c = load_contracts(args.project_root)
    suffix = "-paste" if args.paste else ""
    assert_reset(c, c.parse_graph(args.input_dir / f"reset-repository-result-v1{suffix}.eddgraph"), paste=args.paste)
    assert_find(c, c.parse_graph(args.input_dir / f"find-record-index-v1{suffix}.eddgraph"), paste=args.paste)
    print("Repository core graph contracts passed")


if __name__ == "__main__":
    main()
