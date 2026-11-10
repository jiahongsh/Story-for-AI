#!/usr/bin/env python3
"""Build and enforce a cross-artifact revision impact checklist for a novel project."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
CHAPTER_RE = re.compile(r"第0*(\d+)章")
CHANGE_ID_RE = re.compile(r"^[A-Za-z0-9._-]{3,80}$")
SOURCE_ROOTS = ("正文", "大纲", "设定")
DERIVED_TRACKING_PREFIXES = (
    "追踪/上下文.md", "追踪/伏笔.md", "追踪/长期事实.md", "追踪/关系清单.md",
    "追踪/角色状态/", "追踪/事实档案/", "追踪/时间线/", "追踪/逐章记录/",
)
IGNORED_SOURCE_DIR_NAMES = {"归档", "archive", "archives"}


class GuardError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GuardError(message)


def as_mapping(value: object, label: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{label} must be a JSON object")
    return value


def as_list(value: object, label: str) -> list[Any]:
    require(isinstance(value, list), f"{label} must be a JSON array")
    return value


def clean_text(value: object, label: str, *, allow_empty: bool = False) -> str:
    require(isinstance(value, str), f"{label} must be a string")
    text = " ".join(value.split())
    require(allow_empty or text, f"{label} must not be empty")
    return text


def normalize_relative(project: Path, value: object, label: str, *, must_exist: bool = True) -> str:
    raw = clean_text(value, label)
    path = Path(raw)
    require(not path.is_absolute(), f"{label} must be project-relative")
    resolved = (project / path).resolve()
    try:
        relative = resolved.relative_to(project.resolve())
    except ValueError as exc:
        raise GuardError(f"{label} escapes project root") from exc
    require(not any(part in {"", ".", ".."} for part in relative.parts), f"{label} is invalid")
    if must_exist:
        require(resolved.is_file(), f"{label} does not exist: {relative.as_posix()}")
    return relative.as_posix()


def atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def is_active_source_relative(relative: str) -> bool:
    """Ignore historical copies; only active canon artifacts participate in the gate."""
    parent_parts = Path(relative).parts[:-1]
    return not any(
        "备份" in part or part in IGNORED_SOURCE_DIR_NAMES or part.startswith(".")
        for part in parent_parts
    )


def semantic_files(project: Path) -> list[Path]:
    paths: list[Path] = []
    for root_name in SOURCE_ROOTS:
        root = project / root_name
        if root.is_dir():
            paths.extend(
                path for path in root.rglob("*.md")
                if path.is_file() and is_active_source_relative(path.relative_to(project).as_posix())
            )
    return sorted(paths)


def chapter_paths(project: Path, chapter: int) -> list[Path]:
    result: list[Path] = []
    for root_name in ("正文", "大纲"):
        root = project / root_name
        if not root.is_dir():
            continue
        for path in root.rglob("*.md"):
            if not is_active_source_relative(path.relative_to(project).as_posix()):
                continue
            match = CHAPTER_RE.search(path.name)
            if match and int(match.group(1)) == chapter:
                result.append(path)
    return result


def is_broad_source(relative: str) -> bool:
    name = Path(relative).name
    return relative.startswith("设定/") or "总纲" in name or "卷纲" in name or name == "大纲.md"


def expands_all_outlines(relative: str) -> bool:
    name = Path(relative).name
    return relative.startswith("大纲/") and ("总纲" in name or "卷纲" in name or name == "大纲.md")


def required_checks(
    project: Path,
    changed_files: list[str],
    entities: list[str],
    chapters: list[int],
) -> list[str]:
    required = set(changed_files)
    broad = any(expands_all_outlines(path) for path in changed_files)

    for relative in changed_files:
        match = CHAPTER_RE.search(Path(relative).name)
        if match:
            chapters.append(int(match.group(1)))
    chapter_numbers = sorted(set(chapters))
    for chapter in chapter_numbers:
        for candidate in (chapter - 1, chapter, chapter + 1):
            if candidate < 1:
                continue
            required.update(path.relative_to(project).as_posix() for path in chapter_paths(project, candidate))

    outlines = project / "大纲"
    if outlines.is_dir():
        for path in outlines.rglob("*.md"):
            if broad or path.name == "大纲.md" or "总纲" in path.name or "卷纲" in path.name:
                required.add(path.relative_to(project).as_posix())

    if entities:
        for path in semantic_files(project):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            if any(entity in text for entity in entities):
                required.add(path.relative_to(project).as_posix())

    for fixed in ("追踪/长期事实.md", "追踪/关系清单.md", "追踪/上下文.md"):
        if (project / fixed).is_file():
            required.add(fixed)
    for entity in entities:
        for relative in (f"追踪/事实档案/{entity}.md", f"追踪/角色状态/{entity}.md"):
            if (project / relative).is_file():
                required.add(relative)
    return sorted(required)


def normalize_plan_request(project: Path, document: object) -> dict[str, Any]:
    root = as_mapping(document, "revision plan")
    allowed = {
        "schema_version", "change_id", "summary", "semantic_change", "changed_files",
        "affected_entities", "affected_fact_ids", "affected_chapters",
    }
    require(not (set(root) - allowed), f"revision plan contains unsupported fields: {sorted(set(root) - allowed)}")
    require(root.get("schema_version") == SCHEMA_VERSION, "revision plan schema_version is unsupported")
    change_id = clean_text(root.get("change_id"), "change_id")
    require(CHANGE_ID_RE.fullmatch(change_id) is not None, "change_id must use 3-80 ASCII letters, digits, dot, dash or underscore")
    semantic = root.get("semantic_change")
    require(isinstance(semantic, bool), "semantic_change must be a boolean")
    changed = [
        normalize_relative(project, item, f"changed_files[{index}]")
        for index, item in enumerate(as_list(root.get("changed_files", []), "changed_files"))
    ]
    require(changed, "changed_files must not be empty")
    require(len(changed) == len(set(changed)), "changed_files contains duplicates")
    for relative in changed:
        require(relative.startswith(tuple(f"{root_name}/" for root_name in SOURCE_ROOTS)), f"unsupported source artifact: {relative}")
        require(is_active_source_relative(relative), f"backup/archive artifacts are not active canon sources: {relative}")
        require(not relative.startswith(DERIVED_TRACKING_PREFIXES), f"derived tracking views must not be edited: {relative}")
    entities = [clean_text(item, f"affected_entities[{index}]") for index, item in enumerate(as_list(root.get("affected_entities", []), "affected_entities"))]
    fact_ids = [clean_text(item, f"affected_fact_ids[{index}]") for index, item in enumerate(as_list(root.get("affected_fact_ids", []), "affected_fact_ids"))]
    require(all(re.fullmatch(r"[KR]\d{3,}", item) for item in fact_ids), "affected_fact_ids must look like K001 or R001")
    chapters = as_list(root.get("affected_chapters", []), "affected_chapters")
    require(all(isinstance(item, int) and not isinstance(item, bool) and item >= 1 for item in chapters), "affected_chapters must contain positive integers")
    if any(is_broad_source(path) for path in changed):
        require(entities or chapters, "settings/master/volume outline changes must declare affected_entities or affected_chapters")
    return {
        "schema_version": SCHEMA_VERSION,
        "change_id": change_id,
        "summary": clean_text(root.get("summary"), "summary"),
        "semantic_change": semantic,
        "changed_files": sorted(changed),
        "affected_entities": sorted(set(entities)),
        "affected_fact_ids": sorted(set(fact_ids)),
        "affected_chapters": sorted(set(chapters)),
    }


def make_manifest(project: Path, document: object) -> dict[str, Any]:
    plan = normalize_plan_request(project, document)
    required = required_checks(
        project,
        plan["changed_files"],
        plan["affected_entities"],
        list(plan["affected_chapters"]),
    )
    return {
        **plan,
        "required_checks": required,
        "checked_files": [],
        "conflicts": [],
        "tracking_action": {
            "kind": "pending" if plan["semantic_change"] else "not_required",
            "state_revision_before": None,
            "state_revision_after": None,
            "reason": "" if plan["semantic_change"] else "仅格式/措辞修正，不改变剧情事实与未来约束",
        },
    }


def check_manifest(project: Path, document: object) -> dict[str, Any]:
    root = as_mapping(document, "revision manifest")
    plan_fields = {
        key: root.get(key)
        for key in (
            "schema_version", "change_id", "summary", "semantic_change", "changed_files",
            "affected_entities", "affected_fact_ids", "affected_chapters",
        )
    }
    plan = normalize_plan_request(project, plan_fields)
    expected = required_checks(project, plan["changed_files"], plan["affected_entities"], list(plan["affected_chapters"]))
    declared_required = [normalize_relative(project, item, f"required_checks[{index}]") for index, item in enumerate(as_list(root.get("required_checks"), "required_checks"))]
    require(declared_required == expected, "required_checks is stale or was edited; regenerate the plan")
    checked = {
        normalize_relative(project, item, f"checked_files[{index}]")
        for index, item in enumerate(as_list(root.get("checked_files"), "checked_files"))
    }
    missing = sorted(set(expected) - checked)
    require(not missing, "revision impact review is incomplete; unchecked files: " + ", ".join(missing))

    conflicts = as_list(root.get("conflicts", []), "conflicts")
    normalized_conflicts = []
    for index, raw in enumerate(conflicts):
        conflict = as_mapping(raw, f"conflicts[{index}]")
        allowed = {"severity", "source", "target", "issue", "resolution", "status"}
        require(not (set(conflict) - allowed), f"conflicts[{index}] contains unsupported fields")
        severity = clean_text(conflict.get("severity"), f"conflicts[{index}].severity")
        require(severity in {"S1", "S2", "S3", "S4"}, f"conflicts[{index}].severity is invalid")
        status = clean_text(conflict.get("status"), f"conflicts[{index}].status")
        require(status in {"resolved", "accepted", "unresolved"}, f"conflicts[{index}].status is invalid")
        require(status != "unresolved", f"conflicts[{index}] is unresolved")
        require(not (status == "accepted" and severity in {"S1", "S2"}), f"conflicts[{index}] {severity} cannot be accepted without repair")
        resolution = clean_text(conflict.get("resolution"), f"conflicts[{index}].resolution")
        normalized_conflicts.append({**conflict, "severity": severity, "status": status, "resolution": resolution})

    action = as_mapping(root.get("tracking_action"), "tracking_action")
    allowed_action = {"kind", "state_revision_before", "state_revision_after", "reason"}
    require(not (set(action) - allowed_action), "tracking_action contains unsupported fields")
    kind = clean_text(action.get("kind"), "tracking_action.kind")
    require(kind in {"commit", "migrate-v4", "not_required"}, "tracking_action.kind must close the tracking decision")
    if plan["semantic_change"]:
        require(kind in {"commit", "migrate-v4"}, "semantic revisions must update the structured tracking authority")
        before = action.get("state_revision_before")
        after = action.get("state_revision_after")
        require(isinstance(before, int) and not isinstance(before, bool), "tracking_action.state_revision_before must be an integer")
        require(isinstance(after, int) and not isinstance(after, bool) and after > before, "tracking_action.state_revision_after must be greater than before")
    else:
        require(clean_text(action.get("reason"), "tracking_action.reason"), "non-semantic revisions must explain why tracking is unchanged")
    return {
        "change_id": plan["change_id"],
        "required_check_count": len(expected),
        "checked_file_count": len(checked),
        "conflict_count": len(normalized_conflicts),
        "tracking_action": kind,
        "status": "PASS",
    }


def read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GuardError(f"unable to read JSON {path}: {exc}") from exc


def approval_stamp(manifest_path: Path, result: dict[str, Any]) -> dict[str, Any]:
    """Bind a successful review to the exact manifest bytes.

    Hooks treat this stamp as the closure boundary. Any later edit to active.json
    changes the digest and reopens the transaction instead of silently reusing an
    old approval.
    """
    try:
        payload = manifest_path.read_bytes()
    except OSError as exc:
        raise GuardError(f"unable to hash revision manifest {manifest_path}: {exc}") from exc
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS",
        "change_id": result["change_id"],
        "manifest_sha256": hashlib.sha256(payload).hexdigest(),
        "approved_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "tracking_action": result["tracking_action"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--project", type=Path, required=True)
    plan_parser.add_argument("--input", type=Path, required=True)
    plan_parser.add_argument("--output", type=Path, required=True)
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--project", type=Path, required=True)
    check_parser.add_argument("--input", type=Path, required=True)
    check_parser.add_argument(
        "--stamp",
        type=Path,
        help="write an approval stamp bound to the exact checked manifest bytes",
    )
    args = parser.parse_args()
    try:
        project = args.project.resolve()
        require(project.is_dir(), "project root does not exist")
        if args.command == "plan":
            result = make_manifest(project, read_json(args.input))
            atomic_write(args.output.resolve(), json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        else:
            manifest_path = args.input.resolve()
            result = check_manifest(project, read_json(manifest_path))
            if args.stamp:
                stamp_path = args.stamp.resolve()
                stamp = approval_stamp(manifest_path, result)
                atomic_write(stamp_path, json.dumps(stamp, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
                result = {**result, "approval_stamp": str(stamp_path)}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (GuardError, OSError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
