"""Semantic contracts for client-owned path-preview lifecycle graphs."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


def load_helpers(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Test-PathPreviewContracts.py"
    spec = importlib.util.spec_from_file_location("edd_preview_lifecycle_contract_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load graph helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def assert_closed_graph(c, nodes, expected_nodes: int, entry_name: str | None) -> None:
    c.require(len(nodes) == expected_nodes, f"Unexpected node count: {len(nodes)}")
    known = set(nodes)
    unknown = sorted(
        {
            target
            for node in nodes.values()
            for pin in node.pins.values()
            for target, _ in pin.links
            if target not in known
        }
    )
    c.require(not unknown, f"Graph contains external node links: {unknown}")
    entries = [node for node in nodes.values() if "K2Node_FunctionEntry" in node.node_class]
    c.require(len(entries) == (1 if entry_name else 0), "Function entry inclusion changed")
    if entry_name:
        c.require(f'MemberName="{entry_name}"' in entries[0].text, "Wrong function entry")


def one_call(c, nodes, name: str):
    matches = [
        node
        for node in nodes.values()
        if "K2Node_CallFunction" in node.node_class
        and re.search(rf'MemberName="{re.escape(name)}"', node.text)
    ]
    c.require(len(matches) == 1, f"Expected one {name} call; found {len(matches)}")
    return matches[0]


def one_variable_get(c, nodes, name: str):
    matches = [
        node
        for node in nodes.values()
        if "K2Node_VariableGet" in node.node_class and f'MemberName="{name}"' in node.text
    ]
    c.require(len(matches) == 1, f"Expected one {name} getter; found {len(matches)}")
    return matches[0]


def assert_refresh(c, nodes, *, has_entry: bool) -> None:
    assert_closed_graph(c, nodes, 12 if has_entry else 11, "RefreshPathPreviewV1" if has_entry else None)
    ref_get = one_variable_get(c, nodes, "PathPreviewActorV1")
    valid = one_call(c, nodes, "IsValid")
    branch = c.linked_target(nodes, valid, "ReturnValue", "Condition", "K2Node_IfThenElse")
    document = c.one(nodes, 'VariableReference=(MemberName="DraftDocumentV1"')
    spawn_matches = [node for node in nodes.values() if node.node_class.endswith("K2Node_SpawnActorFromClass")]
    c.require(len(spawn_matches) == 1, f"Expected one preview spawn; found {len(spawn_matches)}")
    spawn = spawn_matches[0]
    spawn_transform = one_call(c, nodes, "MakeTransform")
    ref_sets = [
        node for node in nodes.values()
        if "K2Node_VariableSet" in node.node_class and 'MemberName="PathPreviewActorV1"' in node.text
    ]
    c.require(len(ref_sets) == 1, "Refresh must store exactly one spawned preview reference")
    ref_set = ref_sets[0]
    document_sets = [
        node for node in nodes.values()
        if "K2Node_VariableSet" in node.node_class and 'MemberName="PreviewDocumentV1"' in node.text
    ]
    rebuilds = [
        node for node in nodes.values()
        if "K2Node_CallFunction" in node.node_class and 'MemberName="RebuildPreviewV1"' in node.text
    ]
    c.require(len(document_sets) == 2, "Both reuse and spawn paths must copy the typed document")
    c.require(len(rebuilds) == 2, "Both reuse and spawn paths must rebuild the preview")
    c.require('/Trajectory/BP_EDD_PathPreview.BP_EDD_PathPreview_C' in spawn.text, "Refresh must spawn the preview class")
    c.require('DefaultValue="AlwaysSpawn"' in spawn.text, "Preview spawn must be collision-independent")

    if has_entry:
        entry = c.one(nodes, 'FunctionReference=(MemberName="RefreshPathPreviewV1")')
        c.require_link(entry, "then", branch, "execute", "Refresh entry must evaluate owned-reference validity")
    else:
        c.require(not branch.pins["execute"].links, "Paste body must expose one intentional entry pin")
    c.require_link(ref_get, "PathPreviewActorV1", valid, "Object", "Owned preview must drive validity")
    c.require_link(valid, "ReturnValue", branch, "Condition", "Validity must split reuse and spawn paths")

    existing_set = c.linked_target(nodes, branch, "then", "execute", 'MemberName="PreviewDocumentV1"')
    existing_rebuild = c.linked_target(nodes, existing_set, "then", "execute", 'MemberName="RebuildPreviewV1"')
    c.require_link(ref_get, "PathPreviewActorV1", existing_set, "self", "Reuse path must target the existing actor")
    c.require_link(ref_get, "PathPreviewActorV1", existing_rebuild, "self", "Reuse path must rebuild the existing actor")
    c.require_link(document, "DraftDocumentV1", existing_set, "PreviewDocumentV1", "Reuse path must copy the draft")

    c.require_link(branch, "else", spawn, "execute", "Invalid reference must spawn one preview")
    c.require_link(spawn_transform, "ReturnValue", spawn, "SpawnTransform", "Preview spawn must receive an explicit identity transform")
    c.require_link(spawn, "then", ref_set, "execute", "Spawn must commit the owned reference")
    c.require_link(spawn, "ReturnValue", ref_set, "PathPreviewActorV1", "Spawn return must be stored")
    spawned_set = c.linked_target(nodes, ref_set, "then", "execute", 'MemberName="PreviewDocumentV1"')
    spawned_rebuild = c.linked_target(nodes, spawned_set, "then", "execute", 'MemberName="RebuildPreviewV1"')
    c.require_link(ref_set, "Output_Get", spawned_set, "self", "Committed preview must receive the document")
    c.require_link(ref_set, "Output_Get", spawned_rebuild, "self", "Committed preview must rebuild")
    c.require_link(document, "DraftDocumentV1", spawned_set, "PreviewDocumentV1", "Spawn path must copy the draft")


def assert_destroy(c, nodes, *, has_entry: bool) -> None:
    assert_closed_graph(c, nodes, 8 if has_entry else 7, "DestroyPathPreviewV1" if has_entry else None)
    ref_get = one_variable_get(c, nodes, "PathPreviewActorV1")
    valid = one_call(c, nodes, "IsValid")
    branch = c.linked_target(nodes, valid, "ReturnValue", "Condition", "K2Node_IfThenElse")
    clear = one_call(c, nodes, "ClearPreviewV1")
    destroy = one_call(c, nodes, "K2_DestroyActor")
    resets = [
        node for node in nodes.values()
        if "K2Node_VariableSet" in node.node_class and 'MemberName="PathPreviewActorV1"' in node.text
    ]
    c.require(len(resets) == 2, "Valid and stale paths must both reset the owned reference")

    if has_entry:
        entry = c.one(nodes, 'FunctionReference=(MemberName="DestroyPathPreviewV1")')
        c.require_link(entry, "then", branch, "execute", "Destroy entry must evaluate owned-reference validity")
    else:
        c.require(not branch.pins["execute"].links, "Paste body must expose one intentional entry pin")
    c.require_link(ref_get, "PathPreviewActorV1", valid, "Object", "Owned preview must drive validity")
    c.require_link(valid, "ReturnValue", branch, "Condition", "Validity must split destroy and stale paths")
    c.require_link(branch, "then", clear, "execute", "Valid preview must clear pooled instances first")
    c.require_link(ref_get, "PathPreviewActorV1", clear, "self", "Clear must target the owned preview")
    c.require_link(clear, "then", destroy, "execute", "Clear must precede actor destruction")
    c.require_link(ref_get, "PathPreviewActorV1", destroy, "self", "Destroy must target the owned preview")
    valid_reset = c.linked_target(nodes, destroy, "then", "execute", 'MemberName="PathPreviewActorV1"')
    stale_reset = c.linked_target(nodes, branch, "else", "execute", 'MemberName="PathPreviewActorV1"')
    for reset in (valid_reset, stale_reset):
        c.require(not reset.pins["PathPreviewActorV1"].links, "Reference reset must write None")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--refresh", type=Path, required=True)
    parser.add_argument("--destroy", type=Path, required=True)
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    c = load_helpers(args.project_root)
    assert_refresh(c, c.parse(args.refresh), has_entry=not args.paste)
    assert_destroy(c, c.parse(args.destroy), has_entry=not args.paste)
    print("Path preview lifecycle graph contracts passed")


if __name__ == "__main__":
    main()
