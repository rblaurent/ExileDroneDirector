"""Validate native Blueprint forms used by SyncDraftDocumentV1 generation.

These nodes were exported from the Conan Exiles Enhanced UE 5.6 DevKit. The
generated member suffixes are part of Unreal's serialized contract: inventing
or shortening them creates orphaned pins when a graph is pasted.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


BLOCK_RE = re.compile(
    r'^Begin Object Class=(?P<class>\S+) Name="(?P<name>[^"]+)".*?^End Object\r?$',
    re.MULTILINE | re.DOTALL,
)
PIN_RE = re.compile(r'^\s*CustomProperties Pin \((?P<body>.*)\)$')

SEGMENT_STRUCT = "ST_EDD_Segment.ST_EDD_Segment'"
DOCUMENT_STRUCT = "ST_EDD_FlypathDocument.ST_EDD_FlypathDocument'"
WAYPOINT_STRUCT = "ST_EDD_Waypoint.ST_EDD_Waypoint'"

SEGMENT_FIELDS = {
    "SegmentId_3_57086B304FBCBD600FA6E398ECE727A0": ("int", None),
    "FromWaypointId_5_E660EAD84DEB59C3D0810980CF95CC91": ("int", None),
    "ToWaypointId_7_4F6D070B43FD0BB9AE3B8080C8D2001B": ("int", None),
    "DurationSeconds_14_2404E10F4AC3DE700F1974A7BD6B466A": ("real", "3.000000"),
    "SpatialCurveType_15_39D20A5A4CD2FB464BAA64839CE4012E": ("string", "linear"),
    "TimeProfile_16_3195F0C3470E1AECB34316A7BFBD2FBA": ("string", "linear"),
}

DOCUMENT_FIELDS = {
    "SchemaVersion_16_7F93B5224F25B9BFDAC842BCD5B16D37": ("int", "1"),
    "TrajectoryEngineVersion_3_442F783F41FCAC3B8146EDA9233D191D": ("int", "1"),
    "RevisionNumber_5_951904BF45A63EADA84E4AB0386D19B4": ("int", "0"),
    "RegionId_8_BC1B1B9F4515D58E9666939AB30095B4": ("string", ""),
    "DurationSeconds_11_4517680840D3F6CC541E6BBC6AB10DF9": ("real", "0.000000"),
    "DefaultFlightProfile_14_E9663FDD4E006355747CD3B4CD8BD161": (
        "string",
        "cinematic_drone",
    ),
    "Waypoints_26_1F07C1B24D0D17E4610CDBBAFC5039E5": ("struct", None),
    "Segments_27_C44AF0F54C828C6532348D8A42A4A92B": ("struct", None),
    "ContentHash_28_C376573940EDD8D9F911D9800DB430BC": ("string", ""),
}


@dataclass(frozen=True)
class Pin:
    body: str

    @property
    def direction(self) -> str:
        match = re.search(r'Direction="([^"]+)"', self.body)
        return match.group(1) if match else "EGPD_Input"

    @property
    def category(self) -> str:
        match = re.search(r'PinType.PinCategory="([^"]+)"', self.body)
        if match is None:
            raise RuntimeError("Serialized pin has no category")
        return match.group(1)

    @property
    def default(self) -> str | None:
        match = re.search(r'DefaultValue="([^"]*)"', self.body)
        return match.group(1) if match else None


@dataclass(frozen=True)
class Node:
    node_class: str
    text: str
    pins: dict[str, Pin]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def parse(path: Path) -> list[Node]:
    nodes = []
    for block in BLOCK_RE.finditer(path.read_text(encoding="utf-8")):
        pins = {}
        for line in block.group(0).splitlines():
            match = PIN_RE.match(line)
            if match is None:
                continue
            body = match.group("body")
            name = re.search(r'PinName="([^"]+)"', body)
            require(name is not None, "Serialized pin has no name")
            pins[name.group(1)] = Pin(body)
        nodes.append(Node(block.group("class"), block.group(0), pins))
    return nodes


def select(nodes: list[Node], node_class: str, struct_marker: str) -> Node:
    matches = [
        node
        for node in nodes
        if node.node_class.endswith(node_class)
        and re.search(
            rf'^\s*StructType="[^"]*{re.escape(struct_marker)}"$',
            node.text,
            re.MULTILINE,
        )
    ]
    require(
        len(matches) == 1,
        f"Expected one {node_class} for {struct_marker}; found {len(matches)}",
    )
    return matches[0]


def assert_fields(
    node: Node,
    fields: dict[str, tuple[str, str | None]],
    member_direction: str,
) -> None:
    for name, (category, expected_default) in fields.items():
        require(name in node.pins, f"{node.node_class} is missing generated pin {name}")
        pin = node.pins[name]
        require(pin.category == category, f"{name} category changed to {pin.category}")
        require(pin.direction == member_direction, f"{name} direction changed")
        if expected_default is not None and member_direction == "EGPD_Input":
            if expected_default == "":
                require(pin.default in (None, ""), f"{name} empty default changed to {pin.default!r}")
            else:
                require(pin.default == expected_default, f"{name} default changed to {pin.default!r}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--forms", type=Path, required=True)
    args = parser.parse_args()

    nodes = parse(args.forms)
    require(len(nodes) == 4, f"Expected four native struct forms; found {len(nodes)}")
    require("K2Node_FunctionEntry" not in args.forms.read_text(encoding="utf-8"), "Template must not own an entry node")
    require("LinkedTo=(" not in args.forms.read_text(encoding="utf-8"), "Native forms must remain unlinked")

    make_segment = select(nodes, "K2Node_MakeStruct", SEGMENT_STRUCT)
    break_segment = select(nodes, "K2Node_BreakStruct", SEGMENT_STRUCT)
    make_document = select(nodes, "K2Node_MakeStruct", DOCUMENT_STRUCT)
    break_document = select(nodes, "K2Node_BreakStruct", DOCUMENT_STRUCT)

    assert_fields(make_segment, SEGMENT_FIELDS, "EGPD_Input")
    assert_fields(break_segment, SEGMENT_FIELDS, "EGPD_Output")
    assert_fields(make_document, DOCUMENT_FIELDS, "EGPD_Input")
    assert_fields(break_document, DOCUMENT_FIELDS, "EGPD_Output")

    require(make_segment.pins["ST_EDD_Segment"].direction == "EGPD_Output", "Make Segment value direction changed")
    require(break_segment.pins["ST_EDD_Segment"].direction == "EGPD_Input", "Break Segment value direction changed")
    require(make_document.pins["ST_EDD_FlypathDocument"].direction == "EGPD_Output", "Make Document value direction changed")
    require(break_document.pins["ST_EDD_FlypathDocument"].direction == "EGPD_Input", "Break Document value direction changed")

    for node in (make_document, break_document):
        waypoint_pin = node.pins["Waypoints_26_1F07C1B24D0D17E4610CDBBAFC5039E5"].body
        segment_pin = node.pins["Segments_27_C44AF0F54C828C6532348D8A42A4A92B"].body
        require("PinType.ContainerType=Array" in waypoint_pin, "Waypoints must remain an array")
        require(WAYPOINT_STRUCT in waypoint_pin, "Waypoints lost ST_EDD_Waypoint element type")
        require("PinType.ContainerType=Array" in segment_pin, "Segments must remain an array")
        require(SEGMENT_STRUCT in segment_pin, "Segments lost ST_EDD_Segment element type")

    print("Document sync native struct-form contracts passed.")


if __name__ == "__main__":
    main()
