#!/usr/bin/env python3
"""Merge oh-story hooks into WorkBuddy / CodeBuddy project settings.

Only hook commands invoking ``story_workbuddy_hook.js`` are story-setup
owned. Redeployment removes those registrations before appending the current
project template; user hooks and unknown top-level settings remain untouched.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any


MANAGED_COMMAND_MARKER = "story_workbuddy_hook.js"


class MergeError(ValueError):
    pass


def normalized_command(value: object) -> str:
    return value.lower().replace("\\", "/") if isinstance(value, str) else ""


def is_story_setup_hook(hook: object) -> bool:
    if not isinstance(hook, dict):
        return False
    values = [normalized_command(hook.get("command"))]
    if isinstance(hook.get("args"), list):
        values.extend(normalized_command(value) for value in hook["args"])
    return any(MANAGED_COMMAND_MARKER in value for value in values)


def require_hooks(document: object, label: str) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise MergeError(f"{label} root must be a JSON object")
    hooks = document.get("hooks", {})
    if not isinstance(hooks, dict):
        raise MergeError(f"{label}.hooks must be a JSON object")
    return hooks


def strip_managed_registrations(hooks: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for event, raw_blocks in hooks.items():
        if not isinstance(raw_blocks, list):
            cleaned[event] = copy.deepcopy(raw_blocks)
            continue
        blocks: list[Any] = []
        for raw_block in raw_blocks:
            if not isinstance(raw_block, dict):
                blocks.append(copy.deepcopy(raw_block))
                continue
            if isinstance(raw_block.get("hooks"), list):
                kept = [
                    copy.deepcopy(hook)
                    for hook in raw_block["hooks"]
                    if not is_story_setup_hook(hook)
                ]
                if kept:
                    block = copy.deepcopy(raw_block)
                    block["hooks"] = kept
                    blocks.append(block)
            elif not is_story_setup_hook(raw_block):
                blocks.append(copy.deepcopy(raw_block))
        if blocks:
            cleaned[event] = blocks
    return cleaned


def validate_template(hooks: dict[str, Any]) -> None:
    for event, blocks in hooks.items():
        if not isinstance(blocks, list):
            raise MergeError(f"template.hooks.{event} must be an array")
        for block in blocks:
            if not isinstance(block, dict) or not isinstance(block.get("hooks"), list):
                raise MergeError(f"template.hooks.{event} contains an invalid matcher block")
            for hook in block["hooks"]:
                if not isinstance(hook, dict) or hook.get("type") != "command":
                    raise MergeError(f"template.hooks.{event} contains a non-command hook")
                if not is_story_setup_hook(hook):
                    raise MergeError(f"template.hooks.{event} contains an unmanaged command")


def merge_documents(existing: object, template: object) -> dict[str, Any]:
    existing_hooks = require_hooks(existing, "existing")
    template_hooks = require_hooks(template, "template")
    assert isinstance(existing, dict)
    validate_template(template_hooks)
    result = copy.deepcopy(existing)
    merged = strip_managed_registrations(existing_hooks)
    for event, blocks in template_hooks.items():
        if event in merged and not isinstance(merged[event], list):
            raise MergeError(f"existing.hooks.{event} must be an array")
        merged.setdefault(event, []).extend(copy.deepcopy(blocks))
    result["hooks"] = merged
    return result


def read_json(path: Path, *, missing_ok: bool = False) -> object:
    if missing_ok and not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MergeError(f"unable to read {path}: {exc}") from exc


def atomic_write_json(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    previous_mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    payload = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, previous_mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--existing", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        existing = read_json(args.existing, missing_ok=True)
        template = read_json(args.template)
        atomic_write_json(args.output, merge_documents(existing, template))
    except MergeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
