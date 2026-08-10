"""Add stable accepted/rejected diagnostics to waypoint mutations.

The production authoring functions already own validation, history capture,
typed-document synchronization, and preview refresh.  This final integration
layer makes every terminal path observable without changing mutation behavior:

* accepted capture/replace/delete paths emit one stable log message;
* invalid camera and invalid selection paths emit a distinct stable no-op log;
* rejected paths remain history-free and mutation-free;
* diagnostic Print String nodes write to the log but not the screen.

The EventGraph continues to emit the dynamic waypoint-count/selection summary
after physical K/R/Delete shortcuts.  These function-local messages distinguish
whether the attempted operation was accepted or rejected.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


MESSAGES = {
    "capture_ok": "[EDD] Waypoint captured",
    "capture_camera": "[EDD] Capture ignored: no drone camera",
    "replace_ok": "[EDD] Selected waypoint replaced",
    "replace_camera": "[EDD] Replace ignored: no drone camera",
    "replace_selection": "[EDD] Replace ignored: invalid selection",
    "delete_ok": "[EDD] Selected waypoint deleted",
    "delete_selection": "[EDD] Delete ignored: invalid selection",
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def print_template(builder, snippets: Path) -> str:
    text = builder.read_graph(snippets / "capture-current-waypoint.eddgraph")
    matches = [
        match.group(0)
        for match in builder.BLOCK_RE.finditer(text)
        if 'MemberName="PrintString"' in match.group(0)
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one PrintString template; found {len(matches)}")
    return matches[0]


def clone_print(builder, graph, template: str, message: str, x: int, y: int) -> str:
    new_name = graph.next_name()
    old_name = builder.block_name(template)
    block = template.replace(f'Name="{old_name}"', f'Name="{new_name}"', 1)
    export_class = builder.BLOCK_RE.match(block).group("class").rsplit(".", 1)[-1]
    block = re.sub(
        r'ExportPath="[^"]+"',
        f'ExportPath="/Script/BlueprintGraph.{export_class}\'{builder.ASSET}:{graph.graph_name}.{new_name}\'"',
        block,
        count=1,
    )
    block = builder.set_node_pos(block, x, y)
    block = re.sub(r"NodeGuid=[0-9A-F]{32}", f"NodeGuid={graph.new_id()}", block, count=1)
    block = re.sub(r",LinkedTo=\([^)]*\)", "", block)
    rebuilt: list[str] = []
    for line in block.splitlines():
        if builder.PIN_RE.match(line):
            line = re.sub(r"PinId=[0-9A-F]{32}", f"PinId={graph.new_id()}", line, count=1)
        if 'PinName="InString"' in line:
            line = re.sub(r'DefaultValue="[^"]*"', f'DefaultValue="{message}"', line, count=1)
        if 'PinName="bPrintToScreen"' in line:
            line = re.sub(r'DefaultValue="(?:true|false)"', 'DefaultValue="false"', line, count=1)
        if 'PinName="bPrintToLog"' in line:
            line = re.sub(r'DefaultValue="(?:true|false)"', 'DefaultValue="true"', line, count=1)
        rebuilt.append(line)
    block = "\n".join(rebuilt)
    graph.blocks[new_name] = block
    graph.order.append(new_name)
    return new_name


def attach_terminal(builder, graph, source: str, source_pin: str, template: str, message: str, y: int) -> str:
    if builder.pin_links(graph.blocks[source], source_pin):
        raise RuntimeError(f"{graph.graph_name} {source}.{source_pin} is not terminal")
    x, _ = builder.node_pos(graph.blocks[source])
    diagnostic = clone_print(builder, graph, template, message, x + 320, y)
    builder.connect(graph.blocks, source, source_pin, diagnostic, "execute")
    return diagnostic


def normalize_existing_print(builder, graph, message: str) -> None:
    prints = graph.calls("PrintString")
    if len(prints) != 1:
        raise RuntimeError(f"{graph.graph_name} expected one accepted PrintString; found {prints}")
    name = prints[0]
    block = graph.blocks[name]
    lines = []
    for line in block.splitlines():
        if 'PinName="InString"' in line:
            line = re.sub(r'DefaultValue="[^"]*"', f'DefaultValue="{message}"', line, count=1)
        if 'PinName="bPrintToScreen"' in line:
            line = re.sub(r'DefaultValue="(?:true|false)"', 'DefaultValue="false"', line, count=1)
        if 'PinName="bPrintToLog"' in line:
            line = re.sub(r'DefaultValue="(?:true|false)"', 'DefaultValue="true"', line, count=1)
        lines.append(line)
    graph.blocks[name] = "\n".join(lines)


def is_valid_call(graph) -> str:
    calls = graph.calls("IsValid")
    if len(calls) != 1:
        raise RuntimeError(f"{graph.graph_name} expected one IsValid call; found {calls}")
    return calls[0]


def branch_from_output(builder, graph, source: str, output_pin: str) -> str:
    links = builder.pin_links(graph.blocks[source], output_pin)
    if len(links) != 1:
        raise RuntimeError(f"{graph.graph_name} {source}.{output_pin} expected one branch link; found {links}")
    target = links[0][0]
    if "K2Node_IfThenElse" not in graph.blocks[target]:
        raise RuntimeError(f"{graph.graph_name} {source}.{output_pin} does not target a branch")
    return target


def build_capture(builder, history, snippets: Path, template: str, diagnostic_template: str):
    graph = history.build_graph(
        builder,
        snippets,
        template,
        file_name="capture-current-waypoint.eddgraph",
        graph_name="CaptureCurrentWaypoint",
        operation="Array_Add",
    )
    normalize_existing_print(builder, graph, MESSAGES["capture_ok"])
    camera_branch = branch_from_output(builder, graph, is_valid_call(graph), "ReturnValue")
    attach_terminal(builder, graph, camera_branch, "else", diagnostic_template, MESSAGES["capture_camera"], 928)
    return graph


def build_replace(builder, history, snippets: Path, template: str, diagnostic_template: str):
    graph = history.build_graph(
        builder,
        snippets,
        template,
        file_name="replace-selected-waypoint.eddgraph",
        graph_name="ReplaceSelectedWaypoint",
        operation="Array_Set",
    )
    normalize_existing_print(builder, graph, MESSAGES["replace_ok"])
    camera_branch = branch_from_output(builder, graph, is_valid_call(graph), "ReturnValue")
    next_links = builder.pin_links(graph.blocks[camera_branch], "then")
    if len(next_links) != 1 or "K2Node_IfThenElse" not in graph.blocks[next_links[0][0]]:
        raise RuntimeError("Replace camera guard no longer leads to the selected-index guard")
    selection_branch = next_links[0][0]
    attach_terminal(builder, graph, camera_branch, "else", diagnostic_template, MESSAGES["replace_camera"], 1056)
    attach_terminal(builder, graph, selection_branch, "else", diagnostic_template, MESSAGES["replace_selection"], 944)
    return graph


def build_delete(builder, history, snippets: Path, template: str, diagnostic_template: str):
    graph = history.build_graph(
        builder,
        snippets,
        template,
        file_name="delete-selected-waypoint.eddgraph",
        graph_name="DeleteSelectedWaypoint",
        operation="Array_Remove",
    )
    entry_links = builder.pin_links(graph.blocks[graph.entry()], "then")
    if len(entry_links) != 1 or "K2Node_IfThenElse" not in graph.blocks[entry_links[0][0]]:
        raise RuntimeError("Delete entry no longer leads to the pre-mutation selected-index guard")
    precondition = entry_links[0][0]
    attach_terminal(builder, graph, precondition, "else", diagnostic_template, MESSAGES["delete_selection"], -864)
    refreshes = graph.calls("RefreshPathPreviewV1")
    if len(refreshes) != 2:
        raise RuntimeError(f"Delete expected two accepted preview terminals; found {refreshes}")
    for index, refresh in enumerate(sorted(refreshes, key=lambda name: builder.node_pos(graph.blocks[name]))):
        _, y = builder.node_pos(graph.blocks[refresh])
        attach_terminal(builder, graph, refresh, "then", diagnostic_template, MESSAGES["delete_ok"], y + index * 32)
    return graph


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    builder = load_module(
        "edd_mutation_diagnostic_preview_builder",
        args.project_root / "tools" / "blueprint" / "Build-PathPreviewIntegrationGraphs.py",
    )
    history = load_module(
        "edd_mutation_diagnostic_history_builder",
        args.project_root / "tools" / "blueprint" / "Build-DraftHistoryIntegrationGraphs.py",
    )
    snippets = args.project_root / "tools" / "blueprint" / "snippets"
    template = builder.call_template(snippets)
    diagnostic_template = print_template(builder, snippets)
    graphs = (
        (build_capture(builder, history, snippets, template, diagnostic_template), "capture-current-waypoint-diagnostics-v1"),
        (build_replace(builder, history, snippets, template, diagnostic_template), "replace-selected-waypoint-diagnostics-v1"),
        (build_delete(builder, history, snippets, template, diagnostic_template), "delete-selected-waypoint-diagnostics-v1"),
    )
    for graph, stem in graphs:
        builder.write_graph(graph, args.output_dir, stem)


if __name__ == "__main__":
    main()
