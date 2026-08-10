"""Insert one pre-mutation history snapshot into waypoint authoring graphs.

The source graphs are the deterministic production graphs, not prior clipboard
round-trips.  Preview/document integration is applied first, then exactly one
RecordUndoSnapshotV1 call is inserted after the final precondition guard and
before the first array mutation.  Invalid capture/replace/delete attempts remain
terminal no-ops and therefore do not consume history.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


def load_preview_builder(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Build-PathPreviewIntegrationGraphs.py"
    spec = importlib.util.spec_from_file_location("edd_preview_integration_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load preview integration builder: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def mutation_calls(builder, graph, operation: str) -> set[str]:
    return {
        name
        for name, block in graph.blocks.items()
        if "K2Node_CallArrayFunction" in block
        and re.search(rf'MemberName="{re.escape(operation)}"', block)
    }


def insert_snapshot(builder, graph, operation: str) -> None:
    mutations = mutation_calls(builder, graph, operation)
    if not mutations:
        raise RuntimeError(f"{graph.graph_name} has no {operation} mutation")
    guards = []
    for name, block in graph.blocks.items():
        if not block.startswith("Begin Object Class=/Script/BlueprintGraph.K2Node_IfThenElse "):
            continue
        targets = builder.pin_links(block, "then")
        if len(targets) == 1 and targets[0][0] in mutations:
            guards.append(name)
    if len(guards) != 1:
        raise RuntimeError(
            f"{graph.graph_name} expected one guard immediately before {operation}; found {guards}"
        )
    graph.insert_after(guards[0], "RecordUndoSnapshotV1", shift_downstream=True)


def build_graph(builder, snippets: Path, template: str, *, file_name: str, graph_name: str, operation: str):
    graph = builder.build_mutation(snippets, file_name, graph_name, template)
    insert_snapshot(builder, graph, operation)
    return graph


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    builder = load_preview_builder(args.project_root)
    snippets = args.project_root / "tools" / "blueprint" / "snippets"
    template = builder.call_template(snippets)
    graphs = (
        (
            build_graph(
                builder,
                snippets,
                template,
                file_name="capture-current-waypoint.eddgraph",
                graph_name="CaptureCurrentWaypoint",
                operation="Array_Add",
            ),
            "capture-current-waypoint-history-v1",
        ),
        (
            build_graph(
                builder,
                snippets,
                template,
                file_name="replace-selected-waypoint.eddgraph",
                graph_name="ReplaceSelectedWaypoint",
                operation="Array_Set",
            ),
            "replace-selected-waypoint-history-v1",
        ),
        (
            build_graph(
                builder,
                snippets,
                template,
                file_name="delete-selected-waypoint.eddgraph",
                graph_name="DeleteSelectedWaypoint",
                operation="Array_Remove",
            ),
            "delete-selected-waypoint-history-v1",
        ),
    )
    for graph, stem in graphs:
        builder.write_graph(graph, args.output_dir, stem)


if __name__ == "__main__":
    main()
