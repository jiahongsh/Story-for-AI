#!/usr/bin/env python3
"""Merge oh-story's TRAE hooks while preserving user-owned configuration.

Only hook registrations whose command invokes ``.trae/hooks/story_trae_hook.js``
belong to story-setup.  Redeployment removes those registrations from their old
event/matcher blocks before appending the current template; unrelated hooks and
unknown top-level keys remain untouched.

TRAE's native schema is always emitted as ``{"version": 1, "hooks": {...}}``.
The helper also migrates the short-lived project format that placed supported
event arrays directly at the document root, with or without ``version: 1``.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import shlex
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any


MANAGED_COMMAND_MARKER = ".trae/hooks/story_trae_hook.js"
SCHEMA_VERSION = 1
SUPPORTED_EVENTS = (
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "Stop",
    "Notification",
)
SUPPORTED_EVENT_SET = frozenset(SUPPORTED_EVENTS)
KNOWN_NON_TRAE_EVENTS = frozenset(
    {
        "SessionEnd",
        "PreCompact",
        "PostCompact",
        "SubagentStop",
        "PermissionRequest",
        "PostToolUseFailure",
    }
)


class MergeError(ValueError):
    pass


def normalized_command(value: object) -> str:
    return value.lower().replace("\\", "/") if isinstance(value, str) else ""


def is_node_program(value: object) -> bool:
    normalized = normalized_command(value).strip().strip('"\'')
    return normalized.rsplit("/", 1)[-1] in {"node", "node.exe"}


def is_managed_runner_path(value: object) -> bool:
    normalized = normalized_command(value).strip().strip('"\'')
    return normalized == MANAGED_COMMAND_MARKER or normalized.endswith(f"/{MANAGED_COMMAND_MARKER}")


def command_invokes_managed_runner(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        tokens = shlex.split(value.replace("\\", "/"), posix=True)
    except ValueError:
        return False
    return len(tokens) >= 2 and is_node_program(tokens[0]) and is_managed_runner_path(tokens[1])


def is_story_setup_hook(hook: object) -> bool:
    if not isinstance(hook, dict):
        return False
    if any(
        command_invokes_managed_runner(hook.get(key))
        for key in ("command", "commandWindows")
    ):
        return True

    # Forward compatibility for the short-lived process/args draft.  Both the
    # executable identity and the first argv entry must match; a user hook that
    # merely mentions the runner path in a message/argument remains user-owned.
    args = hook.get("args")
    if not isinstance(args, list) or not args:
        return False
    return any(
        is_node_program(hook.get(key)) and is_managed_runner_path(args[0])
        for key in ("command", "commandWindows", "process")
    )


def require_event_map(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MergeError(f"{label} must be a JSON object")
    for event, blocks in value.items():
        if not isinstance(blocks, list):
            raise MergeError(f"{label}.{event} must be an array")
    return value


def validate_hook_schema(hook: object, label: str) -> None:
    if not isinstance(hook, dict):
        raise MergeError(f"{label} must be a JSON object")
    unknown = set(hook) - {"type", "command", "timeout"}
    if unknown:
        raise MergeError(f"{label} contains unsupported keys: {', '.join(sorted(unknown))}")
    hook_type = hook.get("type", "command")
    if hook_type != "command":
        raise MergeError(f"{label}.type must be omitted or 'command'")
    command = hook.get("command")
    if not isinstance(command, str) or not command.strip():
        raise MergeError(f"{label}.command must be a non-empty string")
    if "timeout" in hook:
        timeout = hook["timeout"]
        if (
            not isinstance(timeout, (int, float))
            or isinstance(timeout, bool)
            or not math.isfinite(timeout)
            or not 1 <= timeout <= 600
        ):
            raise MergeError(f"{label}.timeout must be a finite number from 1 through 600")


def validate_event_schema(event: str, groups: object, label: str) -> None:
    if not isinstance(groups, list):
        raise MergeError(f"{label} must be an array")
    for group_index, group in enumerate(groups):
        group_label = f"{label}[{group_index}]"
        if not isinstance(group, dict):
            raise MergeError(f"{group_label} must be a JSON object")
        unknown = set(group) - {"matcher", "loop_limit", "hooks"}
        if unknown:
            raise MergeError(f"{group_label} contains unsupported keys: {', '.join(sorted(unknown))}")
        if "matcher" in group:
            matcher = group["matcher"]
            if not isinstance(matcher, str) or not matcher.strip():
                raise MergeError(f"{group_label}.matcher must be a non-empty string")
        if "loop_limit" in group:
            loop_limit = group["loop_limit"]
            if event != "Stop":
                raise MergeError(f"{group_label}.loop_limit is only valid for Stop")
            if not isinstance(loop_limit, int) or isinstance(loop_limit, bool) or loop_limit < 1:
                raise MergeError(f"{group_label}.loop_limit must be a positive integer")
        executable_hooks = group.get("hooks")
        if not isinstance(executable_hooks, list) or not executable_hooks:
            raise MergeError(f"{group_label}.hooks must be a non-empty array")
        for hook_index, hook in enumerate(executable_hooks):
            validate_hook_schema(hook, f"{group_label}.hooks[{hook_index}]")


def validate_event_map_schema(events: dict[str, Any], label: str) -> None:
    for event, groups in events.items():
        validate_event_schema(event, groups, f"{label}.{event}")


def is_schema_version_one(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value == SCHEMA_VERSION


def reject_known_non_trae_events(events: object, label: str) -> None:
    if not isinstance(events, dict):
        return
    unsupported = set(events) & KNOWN_NON_TRAE_EVENTS
    if unsupported:
        raise MergeError(f"{label} contains non-TRAE events: {', '.join(sorted(unsupported))}")


def normalize_existing(document: object) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(document, dict):
        raise MergeError("existing root must be a JSON object")

    # Native TRAE hook envelope, version 1. Once a document declares the wrapper, both the version
    # and hooks object are mandatory; silently treating malformed v1 as a legacy
    # document could discard user registrations.
    if "hooks" in document:
        if not is_schema_version_one(document.get("version")):
            raise MergeError("existing.version must be integer 1 when existing.hooks is present")
        normalized = copy.deepcopy(document)
        hooks = require_event_map(normalized["hooks"], "existing.hooks")
        unsupported = set(hooks) - SUPPORTED_EVENT_SET
        if unsupported:
            raise MergeError(
                f"existing.hooks contains unsupported TRAE events: {', '.join(sorted(unsupported))}"
            )
        validate_event_map_schema(hooks, "existing.hooks")
        return normalized, hooks

    version = document.get("version", SCHEMA_VERSION)
    if not is_schema_version_one(version):
        raise MergeError(f"existing.version {document.get('version')!r} is incompatible with schema version 1")

    # Compatibility bridge for the previously deployed direct-map form:
    # {"version": 1, "PreToolUse": [...], ...}.  Only official TRAE events
    # are moved; unrelated top-level extension data remains user-owned.
    legacy_hooks: dict[str, Any] = {}
    normalized = copy.deepcopy(document)
    normalized.pop("version", None)
    reject_known_non_trae_events(normalized, "existing legacy root")
    # A legacy direct-map event is necessarily an array.  Unknown non-array
    # keys remain top-level metadata; unknown arrays are ambiguous and must be
    # rejected instead of being silently migrated or emitted as invalid v1.
    ambiguous = {
        key
        for key, value in normalized.items()
        if key not in SUPPORTED_EVENT_SET and isinstance(value, list)
    }
    if ambiguous:
        raise MergeError(
            "existing legacy root contains ambiguous unsupported event arrays: "
            + ", ".join(sorted(ambiguous))
        )
    for event in SUPPORTED_EVENTS:
        if event not in normalized:
            continue
        blocks = normalized.pop(event)
        if not isinstance(blocks, list):
            raise MergeError(f"existing legacy event {event} must be an array")
        legacy_hooks[event] = blocks
    validate_event_map_schema(legacy_hooks, "existing legacy root")
    normalized["version"] = SCHEMA_VERSION
    normalized["hooks"] = legacy_hooks
    return normalized, legacy_hooks


def normalize_template(document: object) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(document, dict):
        raise MergeError("template root must be a JSON object")
    if set(document) != {"version", "hooks"}:
        raise MergeError("template root must contain exactly version and hooks")
    if not is_schema_version_one(document.get("version")):
        raise MergeError("template.version must be integer 1")
    hooks = require_event_map(document.get("hooks"), "template.hooks")
    unsupported = set(hooks) - SUPPORTED_EVENT_SET
    if unsupported:
        raise MergeError(f"template contains unsupported TRAE events: {', '.join(sorted(unsupported))}")
    validate_event_map_schema(hooks, "template.hooks")
    return copy.deepcopy(document), hooks


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

            # TRAE currently nests executable hooks under a matcher block.  The
            # direct-hook branch keeps the helper forward-compatible with an
            # already deployed early template that used an executable object as
            # the array element itself.
            if isinstance(raw_block.get("hooks"), list):
                kept_hooks = [
                    copy.deepcopy(hook)
                    for hook in raw_block["hooks"]
                    if not is_story_setup_hook(hook)
                ]
                if not kept_hooks:
                    continue
                block = copy.deepcopy(raw_block)
                block["hooks"] = kept_hooks
                blocks.append(block)
            elif not is_story_setup_hook(raw_block):
                blocks.append(copy.deepcopy(raw_block))

        if blocks:
            cleaned[event] = blocks
    return cleaned


def merge_documents(existing: object, template: object) -> dict[str, Any]:
    result, existing_hooks = normalize_existing(existing)
    _, template_hooks = normalize_template(template)
    merged_hooks = strip_managed_registrations(existing_hooks)
    for event, blocks in template_hooks.items():
        merged_hooks.setdefault(event, []).extend(copy.deepcopy(blocks))
    result["hooks"] = merged_hooks
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
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--existing", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
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
