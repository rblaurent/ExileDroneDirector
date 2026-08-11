"""Build deterministic core graphs for the server Flypath repository actor."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


TARGET_ASSET = (
    "/Game/Mods/ExileDroneDirector/Server/Repository/"
    "BP_EDD_FlypathRepository.BP_EDD_FlypathRepository"
)


def load_helpers(project_root: Path):
    path = project_root / "tools" / "blueprint" / "Build-WaypointCaptureGraph.py"
    spec = importlib.util.spec_from_file_location("edd_repository_graph_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load graph helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def set_function_entry(node, name: str) -> None:
    node.text = re.sub(
        r'FunctionReference=\(MemberName="[^"]+"\)',
        f'FunctionReference=(MemberName="{name}")',
        node.text,
        count=1,
    )


def pin_kind(node, pin_name: str, kind: str, *, array: bool = False) -> None:
    def mutate(line: str) -> str:
        line = re.sub(r'PinType\.PinCategory="[^"]+"', f'PinType.PinCategory="{kind}"', line, count=1)
        line = re.sub(r'PinType\.PinSubCategory="[^"]*"', 'PinType.PinSubCategory=""', line, count=1)
        line = re.sub(
            r'PinType\.PinSubCategoryObject=(?:None|"[^"]+")',
            'PinType.PinSubCategoryObject=None',
            line,
            count=1,
        )
        line = re.sub(
            r'PinType\.ContainerType=(?:None|Array)',
            f'PinType.ContainerType={"Array" if array else "None"}',
            line,
            count=1,
        )
        return line
    node.mutate_pin(pin_name, mutate)


def retarget_variable(node, old_name: str, new_name: str, kind: str, *, array: bool = False) -> None:
    node.text = re.sub(
        rf'VariableReference=\(MemberName="{re.escape(old_name)}"[^)]*\)',
        f'VariableReference=(MemberName="{new_name}",bSelfContext=True)',
        node.text,
        count=1,
    )
    node.text = node.text.replace(f'PinName="{old_name}"', f'PinName="{new_name}"')
    node.pins[new_name] = node.pins.pop(old_name)
    pin_kind(node, new_name, kind, array=array)
    if "Output_Get" in node.pins:
        pin_kind(node, "Output_Get", kind)


def retarget_array_clear(node) -> None:
    pin_kind(node, "TargetArray", "string", array=True)


def retarget_array_find(node) -> None:
    pin_kind(node, "TargetArray", "string", array=True)
    pin_kind(node, "ItemToFind", "string")
    pin_kind(node, "ReturnValue", "int")


def set_default(node, pin_name: str, value: str) -> None:
    def mutate(line: str) -> str:
        if "DefaultValue=" in line:
            return re.sub(r'DefaultValue="[^"]*"', f'DefaultValue="{value}"', line, count=1)
        return line.replace(",PersistentGuid=", f',DefaultValue="{value}",PersistentGuid=', 1)
    node.mutate_pin(pin_name, mutate)


class Builder:
    def __init__(self, bp, templates: dict[str, str], graph_name: str):
        self.bp = bp
        self.templates = templates
        self.nodes = []
        bp.TARGET_ASSET = TARGET_ASSET
        bp.TARGET_GRAPH = graph_name
        self.entry = self.add("entry", "K2Node_FunctionEntry_0", 0, 0)
        set_function_entry(self.entry, graph_name)

    def add(self, template: str, name: str, x: int, y: int):
        node = self.bp.Node.clone(template, self.templates[template], name, x, y)
        self.nodes.append(node)
        return node

    def setter(self, name: str, kind: str, x: int, y: int):
        node = self.add("setter", f"K2Node_VariableSet_{len(self.nodes)}", x, y)
        retarget_variable(node, "NextWaypointId", name, kind)
        return node

    def getter(self, old_name: str, name: str, kind: str, x: int, y: int, *, array: bool = False):
        template = "array_getter" if array else "scalar_getter"
        node = self.add(template, f"K2Node_VariableGet_{len(self.nodes)}", x, y)
        retarget_variable(node, old_name, name, kind, array=array)
        return node


def templates(project_root: Path, bp) -> dict[str, str]:
    snippets = project_root / "tools" / "blueprint" / "snippets"
    capture = bp.read_blocks(project_root / "tools" / "blueprint" / "templates" / "waypoint-capture-node-forms.eddgraph")
    sync = bp.read_blocks(snippets / "sync-draft-waypoints-v1.eddgraph")
    return {
        "entry": bp.find_block(capture, r"K2Node_FunctionEntry"),
        "setter": bp.find_block(capture, r'K2Node_VariableSet.*MemberName="NextWaypointId"'),
        "scalar_getter": bp.find_block(capture, r'K2Node_VariableGet.*MemberName="NextWaypointId"'),
        "array_getter": bp.find_block(sync, r'K2Node_VariableGet.*MemberName="DraftWaypointIds"'),
        "array_clear": bp.find_block(sync, r'MemberName="Array_Clear"'),
        "array_find": bp.find_block(sync, r'MemberName="Array_Find"'),
    }


def build_reset(bp, forms: dict[str, str]):
    b = Builder(bp, forms, "ResetRepositoryResultV1")
    specs = (
        ("ResultCodeV1", "string", "Success"),
        ("ResultDetailV1", "string", ""),
        ("ResultHasCurrentRevisionV1", "bool", "false"),
        ("ResultCurrentRevisionV1", "int", "0"),
        ("ResultRecordIndexV1", "int", "-1"),
        ("ResultRecordEnvelopeV1", "string", ""),
    )
    setters = []
    for index, (name, kind, default) in enumerate(specs):
        node = b.setter(name, kind, 256 * (index + 1), 0)
        set_default(node, name, default)
        setters.append(node)
    metadata = b.getter(
        "DraftWaypointIds",
        "ResultMetadataEnvelopesV1",
        "string",
        1280,
        224,
        array=True,
    )
    clear = b.add("array_clear", "K2Node_CallArrayFunction_8", 1792, 0)
    retarget_array_clear(clear)
    bp.connect(b.entry, "then", setters[0], "execute")
    for left, right in zip(setters, setters[1:]):
        bp.connect(left, "then", right, "execute")
    bp.connect(setters[-1], "then", clear, "execute")
    bp.connect(metadata, "ResultMetadataEnvelopesV1", clear, "TargetArray")
    return b.nodes


def build_find(bp, forms: dict[str, str]):
    b = Builder(bp, forms, "FindRecordIndexV1")
    ids = b.getter("DraftWaypointIds", "ActiveFlypathIdsV1", "string", 0, 224, array=True)
    requested = b.getter("NextWaypointId", "RequestFlypathIdV1", "string", 256, 224)
    find = b.add("array_find", "K2Node_CallArrayFunction_3", 512, 224)
    retarget_array_find(find)
    result = b.setter("ResultRecordIndexV1", "int", 768, 0)
    bp.connect(b.entry, "then", result, "execute")
    bp.connect(ids, "ActiveFlypathIdsV1", find, "TargetArray")
    bp.connect(requested, "RequestFlypathIdV1", find, "ItemToFind")
    bp.connect(find, "ReturnValue", result, "ResultRecordIndexV1")
    return b.nodes


def write(nodes, output: Path, *, paste: bool) -> None:
    blocks = []
    entry = nodes[0]
    for node in nodes:
        if paste and node is entry:
            continue
        text = node.text
        if paste:
            text = re.sub(r',LinkedTo=\(K2Node_FunctionEntry_0 [0-9A-F]{32},\)', '', text)
        blocks.append(text)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(blocks) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--paste-dir", type=Path)
    args = parser.parse_args()
    bp = load_helpers(args.project_root)
    forms = templates(args.project_root, bp)
    graphs = {
        "reset-repository-result-v1.eddgraph": build_reset(bp, forms),
        "find-record-index-v1.eddgraph": build_find(bp, forms),
    }
    for filename, nodes in graphs.items():
        write(nodes, args.output_dir / filename, paste=False)
        if args.paste_dir:
            write(nodes, args.paste_dir / filename.replace(".eddgraph", "-paste.eddgraph"), paste=True)


if __name__ == "__main__":
    main()
