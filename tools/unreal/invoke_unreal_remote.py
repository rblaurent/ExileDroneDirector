#!/usr/bin/env python3
"""Invoke Unreal Python through Epic's official remote-execution transport.

This helper deliberately refuses ambiguous discovery. Asset-mutating automation must
target exactly one Enhanced DevKit editor, never whichever UDP responder happens to
answer first.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
import time
from typing import Any, Iterable


DEFAULT_DEVKIT_ROOT = Path(r"F:\CEUE5Devkit")
REMOTE_MODULE_RELATIVE_PATH = Path(
    r"Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python\remote_execution.py"
)


class RemoteInvocationError(RuntimeError):
    """Raised when discovery or remote execution cannot be proven safe."""


def matching_nodes(nodes: Iterable[dict[str, Any]], project_name: str) -> list[dict[str, Any]]:
    expected = project_name.casefold()
    return [
        node
        for node in nodes
        if str(node.get("project_name", "")).casefold() == expected
    ]


def wait_for_single_node(
    execution: Any,
    project_name: str,
    timeout_seconds: float,
    poll_seconds: float = 0.25,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_matches: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        last_matches = matching_nodes(execution.remote_nodes, project_name)
        if len(last_matches) == 1:
            return last_matches[0]
        if len(last_matches) > 1:
            break
        time.sleep(poll_seconds)

    discovered = list(execution.remote_nodes)
    raise RemoteInvocationError(
        "Expected exactly one remote Unreal node for "
        f"{project_name!r}; matched {len(last_matches)} of {len(discovered)} discovered: "
        f"{json.dumps(discovered, sort_keys=True, default=str)}"
    )


def load_remote_module(devkit_root: Path) -> Any:
    module_path = devkit_root / REMOTE_MODULE_RELATIVE_PATH
    if not module_path.is_file():
        raise RemoteInvocationError(f"Epic remote-execution client is missing: {module_path}")
    spec = importlib.util.spec_from_file_location("edd_epic_remote_execution", module_path)
    if spec is None or spec.loader is None:
        raise RemoteInvocationError(f"Could not load Epic remote-execution client: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_for_script(path: Path) -> str:
    """Load a remote script while preserving the file identity Python normally provides."""
    script_path = path.resolve()
    script_source = script_path.read_text(encoding="utf-8-sig")
    return (
        f"__file__ = {str(script_path)!r}\n"
        f"exec(compile({script_source!r}, __file__, 'exec'), globals())"
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--code", help="Literal Python source to execute in Unreal.")
    source.add_argument("--script", type=Path, help="UTF-8 Python file whose source is sent to Unreal.")
    parser.add_argument("--devkit-root", type=Path, default=DEFAULT_DEVKIT_ROOT)
    parser.add_argument("--project-name", default="ConanSandbox")
    parser.add_argument("--discovery-timeout", type=float, default=30.0)
    parser.add_argument(
        "--exec-mode",
        choices=("file", "statement", "evaluate"),
        default="file",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.discovery_timeout <= 0:
        raise RemoteInvocationError("--discovery-timeout must be positive")

    source = args.code
    if args.script is not None:
        if not args.script.is_file():
            raise RemoteInvocationError(f"Remote script is missing: {args.script}")
        source = source_for_script(args.script)
    assert source is not None

    remote = load_remote_module(args.devkit_root.resolve())
    mode_by_name = {
        "file": remote.MODE_EXEC_FILE,
        "statement": remote.MODE_EXEC_STATEMENT,
        "evaluate": remote.MODE_EVAL_STATEMENT,
    }
    execution = remote.RemoteExecution()
    execution.start()
    try:
        node = wait_for_single_node(
            execution,
            project_name=args.project_name,
            timeout_seconds=args.discovery_timeout,
        )
        node_id = node.get("node_id")
        if not node_id:
            raise RemoteInvocationError(f"Discovered node has no node_id: {node!r}")
        print(f"EDD_REMOTE_DISCOVERY|MATCHED|1|NODE|{node_id}")
        execution.open_command_connection(node_id)
        result = execution.run_command(
            source,
            unattended=True,
            exec_mode=mode_by_name[args.exec_mode],
            raise_on_failure=False,
        )
        print(json.dumps({"node": node, "command_result": result}, sort_keys=True, default=str))
        if not result.get("success", False):
            raise RemoteInvocationError(f"Remote command failed: {result.get('result', result)!r}")
        print("EDD_REMOTE_RESULT|SUCCESS")
        return 0
    finally:
        execution.stop()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RemoteInvocationError as error:
        print(f"EDD_REMOTE_ERROR|{error}", file=sys.stderr)
        raise SystemExit(2)
