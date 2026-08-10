"""Integrate client-owned path previews into production authoring functions.

The generated graphs keep the existing camera and waypoint contracts intact while
adding the narrow lifecycle hooks required by the editor preview:

* entering drone mode refreshes the preview on both successful camera paths;
* every successful waypoint mutation rebuilds the typed document, then refreshes;
* exiting drone mode destroys the locally owned preview before view restoration.

Every inserted node receives deterministic identifiers from a namespace that is
checked against the source graph, and every execution link is serialized in both
directions.
"""

from __future__ import annotations

import argparse
import re
import uuid
from pathlib import Path


BLOCK_RE = re.compile(
    r'^Begin Object Class=(?P<class>\S+) Name="(?P<name>[^"]+)".*?^End Object\r?$',
    re.MULTILINE | re.DOTALL,
)
PIN_RE = re.compile(r'^\s*CustomProperties Pin \(.*?PinName="(?P<name>[^"]+)".*\)$')
ASSET = (
    "/Game/Mods/ExileDroneDirector/Core/Client/"
    "BPC_EDD_ClientDirector.BPC_EDD_ClientDirector"
)


def block_name(block: str) -> str:
    match = BLOCK_RE.match(block)
    if match is None:
        raise RuntimeError("Malformed Blueprint node block")
    return match.group("name")


def pin_map(block: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in block.splitlines():
        match = PIN_RE.match(line)
        if not match:
            continue
        pin_id = re.search(r"PinId=([0-9A-F]{32})", line)
        if pin_id is None:
            raise RuntimeError(f"{block_name(block)}.{match.group('name')} has no PinId")
        result[match.group("name")] = pin_id.group(1)
    return result


def pin_links(block: str, pin_name: str) -> list[tuple[str, str]]:
    pin_id = pin_map(block)[pin_name]
    for line in block.splitlines():
        if f"PinId={pin_id}" not in line:
            continue
        linked = re.search(r",LinkedTo=\((?P<links>[^)]*)\)", line)
        if linked is None:
            return []
        return re.findall(r"([A-Za-z0-9_]+) ([0-9A-F]{32}),", linked.group("links"))
    raise RuntimeError(f"Could not find {block_name(block)}.{pin_name}")


def remove_link(block: str, pin_name: str, other_name: str) -> str:
    pin_id = pin_map(block)[pin_name]
    lines = block.splitlines()
    for index, line in enumerate(lines):
        if f"PinId={pin_id}" not in line:
            continue
        linked = re.search(r",LinkedTo=\((?P<links>[^)]*)\)", line)
        if linked is None:
            raise RuntimeError(f"{block_name(block)}.{pin_name} has no links")
        links = re.findall(r"([A-Za-z0-9_]+) ([0-9A-F]{32}),", linked.group("links"))
        filtered = [(name, identifier) for name, identifier in links if name != other_name]
        if len(filtered) == len(links):
            raise RuntimeError(f"{block_name(block)}.{pin_name} is not linked to {other_name}")
        replacement = ""
        if filtered:
            replacement = ",LinkedTo=(" + "".join(
                f"{name} {identifier}," for name, identifier in filtered
            ) + ")"
        lines[index] = line[: linked.start()] + replacement + line[linked.end() :]
        return "\n".join(lines)
    raise RuntimeError(f"Could not find {block_name(block)}.{pin_name}")


def add_link(block: str, pin_name: str, other_name: str, other_pin_id: str) -> str:
    pin_id = pin_map(block)[pin_name]
    lines = block.splitlines()
    for index, line in enumerate(lines):
        if f"PinId={pin_id}" not in line:
            continue
        linked = re.search(r",LinkedTo=\((?P<links>[^)]*)\)", line)
        if linked:
            links = linked.group("links") + f"{other_name} {other_pin_id},"
            lines[index] = line[: linked.start()] + f",LinkedTo=({links})" + line[linked.end() :]
        else:
            lines[index] = line.replace(
                ",PersistentGuid=",
                f",LinkedTo=({other_name} {other_pin_id},),PersistentGuid=",
                1,
            )
        return "\n".join(lines)
    raise RuntimeError(f"Could not find {block_name(block)}.{pin_name}")


def connect(
    blocks: dict[str, str],
    left_name: str,
    left_pin: str,
    right_name: str,
    right_pin: str,
) -> None:
    left_id = pin_map(blocks[left_name])[left_pin]
    right_id = pin_map(blocks[right_name])[right_pin]
    blocks[left_name] = add_link(blocks[left_name], left_pin, right_name, right_id)
    blocks[right_name] = add_link(blocks[right_name], right_pin, left_name, left_id)


def node_pos(block: str) -> tuple[int, int]:
    x = re.search(r"NodePosX=(-?\d+)", block)
    y = re.search(r"NodePosY=(-?\d+)", block)
    return (int(x.group(1)) if x else 0, int(y.group(1)) if y else 0)


def set_node_pos(block: str, x: int, y: int) -> str:
    block = re.sub(r"NodePosX=-?\d+", f"NodePosX={x}", block, count=1)
    block = re.sub(r"NodePosY=-?\d+", f"NodePosY={y}", block, count=1)
    return block


class Graph:
    def __init__(self, graph_name: str, text: str, call_template: str):
        self.graph_name = graph_name
        source = [match.group(0) for match in BLOCK_RE.finditer(text)]
        self.order = [block_name(block) for block in source]
        self.blocks = {block_name(block): block for block in source}
        self.call_template = call_template
        self.used_ids = set(re.findall(r"(?:NodeGuid=|PinId=)([0-9A-F]{32})", text))
        self.counter = 0

    def new_id(self) -> str:
        while True:
            self.counter += 1
            value = uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"exile-drone-director:path-preview-integration:{self.graph_name}:{self.counter}",
            ).hex.upper()
            if value not in self.used_ids:
                self.used_ids.add(value)
                return value

    def next_name(self) -> str:
        indexes = [
            int(value)
            for value in re.findall(r'Name="K2Node_CallFunction_(\d+)"', "\n".join(self.blocks.values()))
        ]
        return f"K2Node_CallFunction_{max(indexes, default=-1) + 1}"

    def clone_call(self, function_name: str, x: int, y: int) -> str:
        new_name = self.next_name()
        old_name = block_name(self.call_template)
        block = self.call_template.replace(f'Name="{old_name}"', f'Name="{new_name}"', 1)
        export_class = BLOCK_RE.match(block).group("class").rsplit(".", 1)[-1]
        block = re.sub(
            r'ExportPath="[^"]+"',
            f'ExportPath="/Script/BlueprintGraph.{export_class}\'{ASSET}:{self.graph_name}.{new_name}\'"',
            block,
            count=1,
        )
        block = set_node_pos(block, x, y)
        block = re.sub(r"NodeGuid=[0-9A-F]{32}", f"NodeGuid={self.new_id()}", block, count=1)
        block = re.sub(r",LinkedTo=\([^)]*\)", "", block)
        rebuilt: list[str] = []
        for line in block.splitlines():
            if PIN_RE.match(line):
                line = re.sub(r"PinId=[0-9A-F]{32}", f"PinId={self.new_id()}", line, count=1)
            rebuilt.append(line)
        block = "\n".join(rebuilt)
        block = re.sub(
            r"FunctionReference=\([^\r\n]+\)",
            f'FunctionReference=(MemberName="{function_name}",bSelfContext=True)',
            block,
            count=1,
        )
        self.blocks[new_name] = block
        self.order.append(new_name)
        return new_name

    def calls(self, function_name: str) -> list[str]:
        return [
            name
            for name, block in self.blocks.items()
            if "K2Node_CallFunction" in block
            and re.search(rf'MemberName="{re.escape(function_name)}"', block)
        ]

    def entry(self) -> str:
        entries = [
            name
            for name, block in self.blocks.items()
            if block.startswith("Begin Object Class=/Script/BlueprintGraph.K2Node_FunctionEntry ")
        ]
        if len(entries) != 1:
            raise RuntimeError(f"{self.graph_name} expected one entry; found {len(entries)}")
        return entries[0]

    def retarget_call(self, name: str, function_name: str) -> None:
        self.blocks[name] = re.sub(
            r"FunctionReference=\([^\r\n]+\)",
            f'FunctionReference=(MemberName="{function_name}",bSelfContext=True)',
            self.blocks[name],
            count=1,
        )

    def shift_after(self, x: int, delta: int) -> None:
        for name, block in list(self.blocks.items()):
            current_x, current_y = node_pos(block)
            if current_x > x:
                self.blocks[name] = set_node_pos(block, current_x + delta, current_y)

    def insert_after(self, source_name: str, function_name: str, *, shift_downstream: bool) -> str:
        source_x, source_y = node_pos(self.blocks[source_name])
        targets = pin_links(self.blocks[source_name], "then")
        if len(targets) > 1:
            raise RuntimeError(f"{source_name}.then has ambiguous fan-out: {targets}")
        if shift_downstream and targets:
            self.shift_after(source_x, 288)
        new_name = self.clone_call(function_name, source_x + 288, source_y)
        if targets:
            target_name, _ = targets[0]
            self.blocks[source_name] = remove_link(self.blocks[source_name], "then", target_name)
            self.blocks[target_name] = remove_link(self.blocks[target_name], "execute", source_name)
        connect(self.blocks, source_name, "then", new_name, "execute")
        if targets:
            connect(self.blocks, new_name, "then", targets[0][0], "execute")
        return new_name

    def full_text(self) -> str:
        return "\n".join(self.blocks[name] for name in self.order) + "\n"

    def paste_text(self) -> str:
        entry_name = self.entry()
        body: list[str] = []
        for name in self.order:
            if name == entry_name:
                continue
            block = self.blocks[name]
            for pin_name in pin_map(block):
                if any(target == entry_name for target, _ in pin_links(block, pin_name)):
                    block = remove_link(block, pin_name, entry_name)
            body.append(block)
        return "\n".join(body) + "\n"


def read_graph(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def call_template(snippets: Path) -> str:
    text = read_graph(snippets / "capture-current-waypoint.eddgraph")
    matches = [
        match.group(0)
        for match in BLOCK_RE.finditer(text)
        if 'MemberName="SyncDraftWaypointsV1"' in match.group(0)
    ]
    if len(matches) != 1:
        raise RuntimeError("Could not resolve the neutral self-call template")
    return matches[0]


def build_enter(snippets: Path, template: str) -> Graph:
    graph = Graph("EnterDroneMode", read_graph(snippets / "enter-drone-mode.eddgraph"), template)
    terminals = graph.calls("ActivateDroneView")
    if len(terminals) != 2:
        raise RuntimeError(f"EnterDroneMode expected two ActivateDroneView terminals; found {len(terminals)}")
    for terminal in terminals:
        if pin_links(graph.blocks[terminal], "then"):
            raise RuntimeError(f"{terminal} must remain a successful terminal before preview integration")
        graph.insert_after(terminal, "RefreshPathPreviewV1", shift_downstream=False)
    return graph


def build_exit(snippets: Path, template: str) -> Graph:
    graph = Graph("ExitDroneMode", read_graph(snippets / "exit-drone-mode.eddgraph"), template)
    graph.insert_after(graph.entry(), "DestroyPathPreviewV1", shift_downstream=True)
    return graph


def build_mutation(snippets: Path, file_name: str, graph_name: str, template: str) -> Graph:
    graph = Graph(graph_name, read_graph(snippets / file_name), template)
    syncs = graph.calls("SyncDraftWaypointsV1")
    expected = 2 if graph_name == "DeleteSelectedWaypoint" else 1
    if len(syncs) != expected:
        raise RuntimeError(f"{graph_name} expected {expected} sync calls; found {len(syncs)}")
    for sync in syncs:
        graph.retarget_call(sync, "SyncDraftDocumentV1")
        graph.insert_after(sync, "RefreshPathPreviewV1", shift_downstream=True)
    return graph


def write_graph(graph: Graph, output_dir: Path, stem: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{stem}.eddgraph").write_text(graph.full_text(), encoding="utf-8")
    (output_dir / f"{stem}-paste.eddgraph").write_text(graph.paste_text(), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    snippets = args.project_root / "tools" / "blueprint" / "snippets"
    template = call_template(snippets)
    graphs = (
        (build_enter(snippets, template), "enter-drone-mode-preview"),
        (build_exit(snippets, template), "exit-drone-mode-preview"),
        (
            build_mutation(
                snippets,
                "capture-current-waypoint.eddgraph",
                "CaptureCurrentWaypoint",
                template,
            ),
            "capture-current-waypoint-preview",
        ),
        (
            build_mutation(
                snippets,
                "replace-selected-waypoint.eddgraph",
                "ReplaceSelectedWaypoint",
                template,
            ),
            "replace-selected-waypoint-preview",
        ),
        (
            build_mutation(
                snippets,
                "delete-selected-waypoint.eddgraph",
                "DeleteSelectedWaypoint",
                template,
            ),
            "delete-selected-waypoint-preview",
        ),
    )
    for graph, stem in graphs:
        write_graph(graph, args.output_dir, stem)


if __name__ == "__main__":
    main()
