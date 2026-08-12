"""Build bounded metadata-only public discovery from the accepted list query.

This deliberately transforms the already-contracted ListMineV1 graph instead
of maintaining a second 150-node sorting/paging implementation. The transform
removes requester validation, changes the derived-index filter from owner to
public visibility, and changes the selected-record authorization check from
owner equality to public visibility. All sorting, paging, decoding, validation,
metadata encoding, and atomic failure behavior remains shared.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import re
import sys


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def unlink(left, left_pin: str, right, right_pin: str) -> None:
    def remove(node, pin_name: str, other, other_pin_name: str) -> None:
        token = f"{other.name} {other.pins[other_pin_name]},"

        def mutate(line: str) -> str:
            updated = line.replace(token, "")
            return re.sub(r",LinkedTo=\(\)", "", updated)

        node.mutate_pin(pin_name, mutate)

    remove(left, left_pin, right, right_pin)
    remove(right, right_pin, left, left_pin)


def build_public(private, bp, enc, validation, create, templates):
    nodes = private.build_list(bp, enc, validation, create, templates)
    by_key = {node.key: node for node in nodes}

    enc.set_function_entry(by_key["entry"], "ListPublicV1")

    reset = by_key["call_ResetRepositoryResultV1_1"]
    request_branch = by_key["branch_5"]
    aligned_branch = by_key["branch_23"]
    invalid_code = by_key["set_ResultCodeV1_148"]
    invalid_detail = by_key["set_ResultDetailV1_149"]
    unlink(reset, "then", request_branch, "execute")
    unlink(request_branch, "then", aligned_branch, "execute")
    unlink(request_branch, "else", invalid_code, "execute")
    unlink(invalid_code, "then", invalid_detail, "execute")
    bp.connect(reset, "then", aligned_branch, "execute")

    owners = by_key["get_ActiveOwnerAccountIdsV1_7"]
    visibilities = by_key["get_ActiveVisibilitiesV1_8"]
    filter_loop = by_key["foreach_29"]
    requester = by_key["get_RequestRequesterAccountIdV1_30"]
    filter_equal = by_key["EqualEqual_StrStr_31"]
    unlink(owners, "ActiveOwnerAccountIdsV1", filter_loop, "Array")
    bp.connect(visibilities, "ActiveVisibilitiesV1", filter_loop, "Array")
    unlink(requester, "RequestRequesterAccountIdV1", filter_equal, "B")
    enc.set_default(filter_equal, "B", "public")

    access_equal = by_key["EqualEqual_StrStr_119"]
    access_value = by_key["get_ScratchRecordOwnerAccountIdV1_120"]
    unlink(requester, "RequestRequesterAccountIdV1", access_equal, "B")
    enc.retarget_variable(access_value, "ScratchRecordVisibilityV1", "string")
    enc.set_default(access_equal, "B", "public")

    removed = {
        "get_RequestRequesterAccountIdV1_2",
        "trim_RequestRequesterAccountIdV1",
        "NotEqual_StrStr_4",
        "branch_5",
        "get_RequestRequesterAccountIdV1_30",
        "set_ResultCodeV1_148",
        "set_ResultDetailV1_149",
    }
    result = [node for node in nodes if node.key not in removed]
    if len(result) != 145:
        raise RuntimeError(f"Public-list transform produced {len(result)} nodes, expected 145")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--paste-dir", type=Path)
    args = parser.parse_args()

    private = load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryPrivateListGraph.py",
        "edd_public_list_base",
    )
    enc = private.load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryDocumentEncoderGraphs.py",
        "edd_public_list_encoder_base",
    )
    record_encoder = private.load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryRecordEncoderGraphs.py",
        "edd_public_list_record_encoder_base",
    )
    validation = private.load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryValidationGraphs.py",
        "edd_public_list_validation_base",
    )
    create = private.load_module(
        args.project_root / "tools" / "blueprint" / "Build-RepositoryPrivateCreateGraph.py",
        "edd_public_list_create_base",
    )
    bp = enc.load_helpers(args.project_root)
    templates = validation.load_templates(args.project_root, bp, enc)
    templates.update(record_encoder.load_templates(args.project_root, bp, enc))
    json_forms = bp.read_blocks(
        args.project_root / "tools" / "blueprint" / "templates" / "repository-json-node-forms.eddgraph"
    )
    string_forms = bp.read_blocks(
        args.project_root / "tools" / "blueprint" / "templates" / "repository-string-trim-node-form.eddgraph"
    )
    templates["json_SetBoolField"] = bp.find_block(json_forms, r'MemberName="SetBoolField"')
    templates["trim_string"] = bp.find_block(string_forms, r'MemberName="Trim"')
    clean_forms = bp.read_blocks(
        args.project_root / "tools" / "blueprint" / "templates" / "conan-clean-frame-node-forms.eddgraph"
    )
    templates["select"] = bp.find_block(
        clean_forms, r"^Begin Object Class=/Script/BlueprintGraph\.K2Node_Select "
    )

    nodes = build_public(private, bp, enc, validation, create, templates)
    filename = "list-public-v1.eddgraph"
    enc.write(nodes, args.output_dir / filename, paste=False)
    if args.paste_dir:
        enc.write(
            validation.fold_paste_layout(nodes),
            args.paste_dir / filename.replace(".eddgraph", "-paste.eddgraph"),
            paste=True,
        )


if __name__ == "__main__":
    main()
