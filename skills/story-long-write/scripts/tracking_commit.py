#!/usr/bin/env python3
"""Maintain one structured story state and its deterministic Markdown views.

The language model supplies compact semantic JSON.  This tool validates and
merges that input in memory, renders every derived view, then atomically writes
``_tracking-state.json`` last as the single commit point.  One book project has
one serial writer; concurrent commits are intentionally unsupported.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import stat
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any


INPUT_SCHEMA_VERSION = 1
TRACKING_SCHEMA_VERSION = 5
DELTA_TARGET_BYTES = 1536
DELTA_MAX_BYTES = 3072
CONTEXT_TARGET_BYTES = 8192
CONTEXT_MAX_BYTES = 12288
SNAPSHOT_TARGET_BYTES = 4096
SNAPSHOT_MAX_BYTES = 8192

CONTEXT_HEADINGS = (
    "## 当前位置",
    "## 长期约束",
    "## 核心角色状态",
    "## 活跃伏笔",
    "## 近三章速记",
    "## 下一章承诺",
    "## 连贯性风险",
)
# 跨章连续性守卫字段：这两项一旦被无声改写，就是「上一章住宿舍、下一章骑车从家出发」
# 「上一章娘摆针线摊、下一章变卖菜摊」这类读者一眼看穿的硬伤。改它们必须报旧值。
# 位置与持有物进热上下文时按字节截断。两者的 schema 上限分别是 240 和每项 384，
# 6 个活跃角色原样铺开最坏能给热上下文多加约 6KB，直接把 12288 的硬顶顶穿，
# 届时作者只会看到「hot context exceeds」而不知道该删哪。热上下文本来就是摘要：
# 让写作端知道「人在学校宿舍」就够了，精确原文在 角色状态/{名}.md，
# 而申报 continuity_changes 的 from 要求匹配完整值，正好逼模型去读那份文件。
CONTEXT_FIELD_BYTES = 60
GUARDED_SNAPSHOT_FIELDS = ("location", "abilities_resources")
GUARDED_FIELD_LABEL = {"location": "位置", "abilities_resources": "持有物"}

FORESHADOW_STATUSES = ("已埋", "已回收", "已过期", "放弃")
FORESHADOW_IMPORTANCE = ("高", "中", "低")
REVEAL_STATUSES = ("未揭示", "部分揭示", "已揭示")
INVALID_FILE_CHARS = re.compile(r"[<>:\"/\\|?*\x00-\x1f]")
FORESHADOW_ID = re.compile(r"^F\d{3,}$")
EVENT_ID = re.compile(r"^E\d{3,}$")
FACT_ID = re.compile(r"^[KR]\d{3,}$")
FACT_CATEGORIES = (
    "身份", "血缘", "亲属", "婚姻", "别名", "传承", "从属", "合作", "敌对",
    "所有权", "规则", "权限", "不可逆状态", "历史因果", "其他",
)
RELATION_CATEGORIES = {"血缘", "亲属", "婚姻", "传承", "从属", "合作", "敌对"}
FACT_CARDINALITIES = ("one", "many")
FACT_CANON_STATUSES = ("锁定设定", "正文已证")
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
RETIRED_TRACKING_PATHS = (
    "_tracking-meta.json",
    "阶段摘要.md",
    "角色状态.md",
    "时间线.md",
    "摘要",
    "时间线/事件库.json",
)
RETIRED_ARCHIVE_DIR = "_旧追踪存档"


class TrackingError(ValueError):
    """Expected validation or tracking-state error."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise TrackingError(message)


def as_mapping(value: object, label: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{label} must be a JSON object")
    return value


def as_list(value: object, label: str) -> list[Any]:
    require(isinstance(value, list), f"{label} must be a JSON array")
    return value


def as_int(value: object, label: str, *, minimum: int = 0) -> int:
    require(isinstance(value, int) and not isinstance(value, bool), f"{label} must be an integer")
    require(value >= minimum, f"{label} must be >= {minimum}")
    return value


def require_known_keys(mapping: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = set(mapping) - allowed
    require(not unknown, f"{label} contains unsupported fields: {', '.join(sorted(unknown))}")


def clean_text(value: object, label: str, *, allow_empty: bool = False, max_bytes: int = 768) -> str:
    require(isinstance(value, str), f"{label} must be a string")
    cleaned = " ".join(value.replace("|", "｜").split())
    require(allow_empty or bool(cleaned), f"{label} must not be empty")
    require(len(cleaned.encode("utf-8")) <= max_bytes, f"{label} exceeds {max_bytes} bytes")
    return cleaned


def clean_string_list(
    value: object,
    label: str,
    *,
    maximum: int | None = None,
    item_max_bytes: int = 384,
) -> list[str]:
    values = as_list(value, label)
    if maximum is not None:
        require(len(values) <= maximum, f"{label} may contain at most {maximum} items")
    return [clean_text(item, f"{label}[{index}]", max_bytes=item_max_bytes) for index, item in enumerate(values)]


def safe_file_component(value: object, label: str) -> str:
    name = unicodedata.normalize("NFC", clean_text(value, label, max_bytes=180))
    require(not INVALID_FILE_CHARS.search(name), f"{label} contains an invalid filename character")
    require(name not in {".", ".."} and not name.endswith((".", " ")), f"{label} is not a safe filename")
    require(name.split(".", 1)[0].upper() not in WINDOWS_RESERVED_NAMES, f"{label} is reserved on Windows")
    return name


def portable_name_key(name: str) -> str:
    return unicodedata.normalize("NFC", name).casefold()


def byte_size(text: str) -> int:
    return len(text.encode("utf-8"))


def clip_bytes(text: str, limit: int) -> str:
    if byte_size(text) <= limit:
        return text
    clipped = text
    while byte_size(clipped) > limit - 3:
        clipped = clipped[:-1]
    return clipped + "…"


def emit(text: str, *, error: bool = False) -> None:
    """Write UTF-8 bytes directly.

    Windows 的文本 stdout 是 cp1252（含中文即 UnicodeEncodeError），stderr 默认
    backslashreplace（中文被转义成反斜杠码位，作者看不懂）。两条路都要绕开。
    """
    stream = sys.stderr if error else sys.stdout
    stream.flush()
    stream.buffer.write((text + "\n").encode("utf-8"))
    stream.buffer.flush()


def read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TrackingError(f"unable to read JSON {path}: {exc}") from exc


def json_payload(document: object) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def atomic_write_text(path: Path, payload: str) -> None:
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


def write_if_changed(path: Path, payload: str) -> None:
    try:
        if path.read_text(encoding="utf-8") == payload:
            return
    except FileNotFoundError:
        pass
    atomic_write_text(path, payload)


def tracking_root(project: Path) -> Path:
    return project.resolve() / "追踪"


def state_path(project: Path) -> Path:
    return tracking_root(project) / "_tracking-state.json"


def delta_path(tracking: Path, chapter: int) -> Path:
    width = max(3, len(str(chapter)))
    return tracking / "逐章记录" / f"第{chapter:0{width}d}章.md"


def find_retired_tracking_paths(tracking: Path) -> list[str]:
    found = [relative for relative in RETIRED_TRACKING_PATHS if (tracking / relative).exists()]
    found.extend(sorted(path.name for path in tracking.glob("基线_截至第*章.md")))
    return found


def require_no_retired_tracking_paths(tracking: Path) -> None:
    found = find_retired_tracking_paths(tracking)
    require(not found, f"retired tracking files are not supported: {', '.join(found)}")


def archive_retired_tracking_paths(tracking: Path) -> list[str]:
    """Move a pre-transaction 追踪/ aside so init can build the current protocol in place.

    Nothing is parsed or converted: the old files are kept verbatim for the author to
    consult, and the new state is reconstructed from the init document alone.
    """
    retired = find_retired_tracking_paths(tracking)
    if not retired:
        return []
    archive = tracking / RETIRED_ARCHIVE_DIR
    for relative in retired:
        require(
            not (archive / relative).exists(),
            f"追踪/{RETIRED_ARCHIVE_DIR}/{relative} already exists; move it away before initializing",
        )
    # 先全量校验再搬运；中断后重跑时已搬走的条目不再出现在待搬列表里，可直接续做。
    for relative in retired:
        target = archive / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(tracking / relative, target)
    return retired


def validate_position(value: object, label: str = "context.position") -> dict[str, Any]:
    position = as_mapping(value, label)
    require_known_keys(position, {"volume", "volume_start_chapter", "story_time", "scene"}, label)
    return {
        "volume": safe_file_component(position.get("volume"), f"{label}.volume"),
        "volume_start_chapter": as_int(
            position.get("volume_start_chapter"), f"{label}.volume_start_chapter", minimum=1
        ),
        "story_time": clean_text(position.get("story_time"), f"{label}.story_time", max_bytes=240),
        "scene": clean_text(position.get("scene"), f"{label}.scene", max_bytes=240),
    }


def normalize_snapshot(value: object, label: str) -> dict[str, Any]:
    snapshot = as_mapping(value, label)
    require_known_keys(
        snapshot,
        {"identity", "location", "goal", "state", "abilities_resources", "relationships", "knowledge", "open_threads"},
        label,
    )
    return {
        "identity": clean_text(snapshot.get("identity"), f"{label}.identity", max_bytes=240),
        "location": clean_text(snapshot.get("location"), f"{label}.location", max_bytes=240),
        "goal": clean_text(snapshot.get("goal"), f"{label}.goal", max_bytes=300),
        "state": clean_text(snapshot.get("state"), f"{label}.state", max_bytes=300),
        "abilities_resources": clean_string_list(
            snapshot.get("abilities_resources", []), f"{label}.abilities_resources"
        ),
        "relationships": clean_string_list(snapshot.get("relationships", []), f"{label}.relationships"),
        "knowledge": clean_string_list(snapshot.get("knowledge", []), f"{label}.knowledge"),
        "open_threads": clean_string_list(snapshot.get("open_threads", []), f"{label}.open_threads"),
    }


def normalize_snapshots(value: object, label: str = "character_snapshots") -> dict[str, dict[str, Any]]:
    snapshots = as_mapping(value, label)
    normalized: dict[str, dict[str, Any]] = {}
    portable_names: set[str] = set()
    for raw_name, raw_snapshot in snapshots.items():
        name = safe_file_component(raw_name, f"{label} character name")
        key = portable_name_key(name)
        require(key not in portable_names, f"{label} contains a cross-platform duplicate character {name}")
        portable_names.add(key)
        normalized[name] = normalize_snapshot(raw_snapshot, f"{label}.{name}")
    return normalized


def render_snapshot(name: str, snapshot: dict[str, Any], through_chapter: int, revision: int) -> str:
    def section(title: str, values: list[str]) -> list[str]:
        return [f"## {title}", *(f"- {item}" for item in values or ["无"]), ""]

    lines = [
        f"# {name}｜当前状态",
        "",
        f"- 状态修订：{revision}",
        f"- 截至章节：第{through_chapter}章",
        f"- 身份：{snapshot['identity']}",
        f"- 位置：{snapshot['location']}",
        f"- 当前目标：{snapshot['goal']}",
        f"- 身心状态：{snapshot['state']}",
        "",
    ]
    lines.extend(section("能力与资源", snapshot["abilities_resources"]))
    lines.extend(section("关键关系", snapshot["relationships"]))
    lines.extend(section("已知信息", snapshot["knowledge"]))
    lines.extend(section("未结事项", snapshot["open_threads"]))
    payload = "\n".join(lines).rstrip() + "\n"
    require(
        byte_size(payload) <= SNAPSHOT_MAX_BYTES,
        f"character snapshot {name} exceeds hard cap of {SNAPSHOT_MAX_BYTES} bytes",
    )
    return payload


def normalize_foreshadow_change(
    value: object,
    label: str,
    *,
    allow_delete: bool,
    through_chapter: int,
) -> dict[str, Any]:
    row = as_mapping(value, label)
    require_known_keys(
        row,
        {"action", "id", "summary", "planted_chapter", "planned_resolution_chapter", "status", "importance"},
        label,
    )
    action = clean_text(row.get("action", "upsert"), f"{label}.action", max_bytes=24)
    require(action in ({"upsert", "delete"} if allow_delete else {"upsert"}), f"{label}.action is invalid")
    identifier = clean_text(row.get("id"), f"{label}.id", max_bytes=24)
    require(FORESHADOW_ID.fullmatch(identifier) is not None, f"{label}.id must look like F001")
    if action == "delete":
        return {"action": action, "id": identifier}
    planted_chapter = as_int(row.get("planted_chapter"), f"{label}.planted_chapter", minimum=1)
    require(planted_chapter <= through_chapter, f"{label}.planted_chapter cannot be in the future")
    planned_raw = row.get("planned_resolution_chapter")
    planned_chapter = (
        None if planned_raw is None else as_int(planned_raw, f"{label}.planned_resolution_chapter", minimum=1)
    )
    require(
        planned_chapter is None or planned_chapter >= planted_chapter,
        f"{label}.planned_resolution_chapter cannot precede planted_chapter",
    )
    status = clean_text(row.get("status"), f"{label}.status", max_bytes=24)
    importance = clean_text(row.get("importance"), f"{label}.importance", max_bytes=12)
    require(status in FORESHADOW_STATUSES, f"{label}.status must be one of {FORESHADOW_STATUSES}")
    require(importance in FORESHADOW_IMPORTANCE, f"{label}.importance must be one of {FORESHADOW_IMPORTANCE}")
    return {
        "action": action,
        "id": identifier,
        "summary": clean_text(row.get("summary"), f"{label}.summary", max_bytes=360),
        "planted_chapter": planted_chapter,
        "planned_resolution_chapter": planned_chapter,
        "status": status,
        "importance": importance,
    }


def normalize_foreshadow_state(value: object, last_chapter: int) -> dict[str, dict[str, Any]]:
    rows = as_mapping(value, "tracking state.foreshadow")
    normalized: dict[str, dict[str, Any]] = {}
    for raw_identifier, raw_row in rows.items():
        identifier = clean_text(raw_identifier, "tracking state.foreshadow ID", max_bytes=24)
        row = as_mapping(raw_row, f"tracking state.foreshadow.{identifier}")
        require_known_keys(
            row,
            {"id", "summary", "planted_chapter", "planned_resolution_chapter", "status", "importance", "updated_chapter"},
            f"tracking state.foreshadow.{identifier}",
        )
        require(row.get("id") == identifier, f"tracking state.foreshadow.{identifier}.id does not match its key")
        change = normalize_foreshadow_change(
            {
                "action": "upsert",
                **{key: value for key, value in row.items() if key != "updated_chapter"},
            },
            f"tracking state.foreshadow.{identifier}",
            allow_delete=False,
            through_chapter=last_chapter,
        )
        change.pop("action")
        updated = as_int(row.get("updated_chapter"), f"tracking state.foreshadow.{identifier}.updated_chapter", minimum=1)
        require(updated <= last_chapter, f"foreshadow {identifier} updates after current chapter")
        change["updated_chapter"] = updated
        normalized[identifier] = change
    return normalized


def render_foreshadow(rows: dict[str, dict[str, Any]], revision: int) -> str:
    lines = [
        "# 伏笔当前状态",
        "",
        f"> 状态修订：{revision}。每个 ID 只保留一行当前状态；历史变化见 `逐章记录/`。",
        "",
        "| ID | 内容 | 埋设章 | 计划回收章 | 状态 | 重要度 | 最近变更章 |",
        "|---|---|---:|---:|---|---|---:|",
    ]
    for identifier in sorted(rows):
        row = rows[identifier]
        planned = f"第{row['planned_resolution_chapter']}章" if row["planned_resolution_chapter"] else "—"
        lines.append(
            f"| {identifier} | {row['summary']} | 第{row['planted_chapter']}章 | {planned} | "
            f"{row['status']} | {row['importance']} | 第{row['updated_chapter']}章 |"
        )
    return "\n".join(lines) + "\n"


def normalize_timeline_change(
    value: object,
    label: str,
    *,
    allow_delete: bool,
    through_chapter: int,
) -> dict[str, Any]:
    event = as_mapping(value, label)
    require_known_keys(
        event,
        {"action", "id", "story_time", "objective_fact", "reader_knowledge", "reveal_status", "reveal_chapter", "characters"},
        label,
    )
    action = clean_text(event.get("action", "upsert"), f"{label}.action", max_bytes=24)
    require(action in ({"upsert", "delete"} if allow_delete else {"upsert"}), f"{label}.action is invalid")
    identifier = clean_text(event.get("id"), f"{label}.id", max_bytes=24)
    require(EVENT_ID.fullmatch(identifier) is not None, f"{label}.id must look like E001")
    if action == "delete":
        return {"action": action, "id": identifier}
    reveal_status = clean_text(event.get("reveal_status"), f"{label}.reveal_status", max_bytes=24)
    require(reveal_status in REVEAL_STATUSES, f"{label}.reveal_status must be one of {REVEAL_STATUSES}")
    reveal_raw = event.get("reveal_chapter")
    reveal_chapter = None if reveal_raw is None else as_int(reveal_raw, f"{label}.reveal_chapter", minimum=1)
    if reveal_status == "未揭示":
        require(reveal_chapter is None, f"{label} must not put a future reveal chapter in established timeline facts")
    else:
        require(reveal_chapter is not None, f"{label}.reveal_chapter is required once revealed")
        require(reveal_chapter <= through_chapter, f"{label}.reveal_chapter cannot be in the future")
    return {
        "action": action,
        "id": identifier,
        "story_time": clean_text(event.get("story_time"), f"{label}.story_time", max_bytes=240),
        "objective_fact": clean_text(event.get("objective_fact"), f"{label}.objective_fact", max_bytes=480),
        "reader_knowledge": clean_text(event.get("reader_knowledge"), f"{label}.reader_knowledge", max_bytes=480),
        "reveal_status": reveal_status,
        "reveal_chapter": reveal_chapter,
        "characters": clean_string_list(event.get("characters", []), f"{label}.characters", maximum=12, item_max_bytes=120),
    }


def normalize_timeline_state(value: object, last_chapter: int) -> dict[str, dict[str, Any]]:
    events = as_mapping(value, "tracking state.timeline")
    normalized: dict[str, dict[str, Any]] = {}
    for raw_identifier, raw_event in events.items():
        identifier = clean_text(raw_identifier, "tracking state.timeline ID", max_bytes=24)
        event = as_mapping(raw_event, f"tracking state.timeline.{identifier}")
        require_known_keys(
            event,
            {
                "id", "story_time", "objective_fact", "reader_knowledge", "reveal_status", "reveal_chapter",
                "characters", "first_recorded_chapter", "updated_chapter",
            },
            f"tracking state.timeline.{identifier}",
        )
        require(event.get("id") == identifier, f"tracking state.timeline.{identifier}.id does not match its key")
        change = normalize_timeline_change(
            {
                "action": "upsert",
                **{
                    key: value
                    for key, value in event.items()
                    if key not in {"first_recorded_chapter", "updated_chapter"}
                },
            },
            f"tracking state.timeline.{identifier}",
            allow_delete=False,
            through_chapter=last_chapter,
        )
        change.pop("action")
        first = as_int(event.get("first_recorded_chapter"), f"tracking state.timeline.{identifier}.first_recorded_chapter", minimum=1)
        updated = as_int(event.get("updated_chapter"), f"tracking state.timeline.{identifier}.updated_chapter", minimum=1)
        require(first <= last_chapter, f"timeline event {identifier} starts after current chapter")
        require(updated <= last_chapter, f"timeline event {identifier} updates after current chapter")
        change["first_recorded_chapter"] = first
        change["updated_chapter"] = updated
        normalized[identifier] = change
    return normalized


def render_timeline_views(events: dict[str, dict[str, Any]], revision: int) -> tuple[str, str]:
    author_lines = [
        "# 作者真相时间线",
        "",
        f"> 状态修订：{revision}。客观事实与读者认知的权威对照；未来揭示计划仍留在大纲。",
        "",
        "| ID | 首次登记章 | 故事时间 | 客观事实 | 读者当前认知 | 揭示状态 | 实际揭示章 |",
        "|---|---:|---|---|---|---|---:|",
    ]
    reader_lines = [
        "# 读者已知时间线",
        "",
        f"> 状态修订：{revision}。只呈现读者截至当前章节已经知道或相信的内容，不泄露作者侧客观真相。",
        "",
        "| ID | 读者当前认知 | 认知截至章 |",
        "|---|---|---:|",
    ]
    for identifier in sorted(events):
        event = events[identifier]
        reveal = f"第{event['reveal_chapter']}章" if event.get("reveal_chapter") else "—"
        characters = "、".join(event.get("characters", []))
        objective = event["objective_fact"] + (f"（涉及：{characters}）" if characters else "")
        author_lines.append(
            f"| {identifier} | 第{event['first_recorded_chapter']}章 | {event['story_time']} | {objective} | "
            f"{event['reader_knowledge']} | {event['reveal_status']} | {reveal} |"
        )
        reader_lines.append(f"| {identifier} | {event['reader_knowledge']} | 第{event['updated_chapter']}章 |")
    return "\n".join(author_lines) + "\n", "\n".join(reader_lines) + "\n"


def normalize_fact_change(
    value: object,
    label: str,
    *,
    allow_delete: bool,
    through_chapter: int,
) -> dict[str, Any]:
    fact = as_mapping(value, label)
    require_known_keys(
        fact,
        {
            "action", "id", "category", "subject", "predicate", "object", "cardinality",
            "canon_status", "reader_status", "reveal_chapter", "established_chapter",
            "evidence", "related_entities", "negative_constraints",
        },
        label,
    )
    action = clean_text(fact.get("action", "upsert"), f"{label}.action", max_bytes=24)
    require(action in ({"upsert", "delete"} if allow_delete else {"upsert"}), f"{label}.action is invalid")
    identifier = clean_text(fact.get("id"), f"{label}.id", max_bytes=24)
    require(FACT_ID.fullmatch(identifier) is not None, f"{label}.id must look like K001 or R001")
    if action == "delete":
        return {"action": action, "id": identifier}

    category = clean_text(fact.get("category"), f"{label}.category", max_bytes=24)
    require(category in FACT_CATEGORIES, f"{label}.category must be one of {FACT_CATEGORIES}")
    cardinality = clean_text(fact.get("cardinality"), f"{label}.cardinality", max_bytes=16)
    require(cardinality in FACT_CARDINALITIES, f"{label}.cardinality must be one of {FACT_CARDINALITIES}")
    canon_status = clean_text(fact.get("canon_status"), f"{label}.canon_status", max_bytes=24)
    require(canon_status in FACT_CANON_STATUSES, f"{label}.canon_status must be one of {FACT_CANON_STATUSES}")
    reader_status = clean_text(fact.get("reader_status"), f"{label}.reader_status", max_bytes=24)
    require(reader_status in REVEAL_STATUSES, f"{label}.reader_status must be one of {REVEAL_STATUSES}")
    reveal_raw = fact.get("reveal_chapter")
    reveal_chapter = None if reveal_raw is None else as_int(reveal_raw, f"{label}.reveal_chapter", minimum=1)
    if reader_status == "未揭示":
        require(reveal_chapter is None, f"{label} must not put a future reveal chapter in established facts")
    else:
        require(reveal_chapter is not None, f"{label}.reveal_chapter is required once revealed")
        require(reveal_chapter <= through_chapter, f"{label}.reveal_chapter cannot be in the future")
    established = as_int(fact.get("established_chapter", 0), f"{label}.established_chapter")
    require(established <= through_chapter, f"{label}.established_chapter cannot be in the future")
    evidence = clean_string_list(fact.get("evidence", []), f"{label}.evidence", maximum=12, item_max_bytes=480)
    require(evidence, f"{label}.evidence must contain at least one source reference")
    related_entities = [
        safe_file_component(item, f"{label}.related_entities[{index}]")
        for index, item in enumerate(as_list(fact.get("related_entities", []), f"{label}.related_entities"))
    ]
    require(len(related_entities) <= 12, f"{label}.related_entities may contain at most 12 items")
    require(
        len({portable_name_key(item) for item in related_entities}) == len(related_entities),
        f"{label}.related_entities contains duplicates",
    )
    if category in RELATION_CATEGORIES:
        require(related_entities, f"{label}.related_entities is required for relationship facts")
    return {
        "action": action,
        "id": identifier,
        "category": category,
        "subject": clean_text(fact.get("subject"), f"{label}.subject", max_bytes=180),
        "predicate": clean_text(fact.get("predicate"), f"{label}.predicate", max_bytes=180),
        "object": clean_text(fact.get("object"), f"{label}.object", max_bytes=360),
        "cardinality": cardinality,
        "canon_status": canon_status,
        "reader_status": reader_status,
        "reveal_chapter": reveal_chapter,
        "established_chapter": established,
        "evidence": evidence,
        "related_entities": related_entities,
        "negative_constraints": clean_string_list(
            fact.get("negative_constraints", []), f"{label}.negative_constraints", maximum=8, item_max_bytes=360
        ),
    }


def fact_slot_key(fact: dict[str, Any]) -> tuple[str, str]:
    return (portable_name_key(fact["subject"]), portable_name_key(fact["predicate"]))


def validate_fact_set(facts: dict[str, dict[str, Any]]) -> None:
    triples: dict[tuple[str, str, str], str] = {}
    slots: dict[tuple[str, str], list[tuple[str, dict[str, Any]]]] = {}
    for identifier, fact in facts.items():
        triple = (*fact_slot_key(fact), portable_name_key(fact["object"]))
        previous = triples.get(triple)
        require(previous is None or previous == identifier, f"fact {identifier} duplicates the same triple as {previous}")
        triples[triple] = identifier
        slots.setdefault(fact_slot_key(fact), []).append((identifier, fact))
    for slot, rows in slots.items():
        if not any(row["cardinality"] == "one" for _, row in rows):
            continue
        objects = {portable_name_key(row["object"]) for _, row in rows}
        require(
            len(objects) == 1,
            f"single-valued canon slot {slot[0]} / {slot[1]} has conflicting objects: "
            + ", ".join(identifier for identifier, _ in rows),
        )


def normalize_fact_state(value: object, last_chapter: int) -> dict[str, dict[str, Any]]:
    rows = as_mapping(value, "tracking state.facts")
    normalized: dict[str, dict[str, Any]] = {}
    for raw_identifier, raw_fact in rows.items():
        identifier = clean_text(raw_identifier, "tracking state.facts ID", max_bytes=24)
        fact = as_mapping(raw_fact, f"tracking state.facts.{identifier}")
        require_known_keys(
            fact,
            {
                "id", "category", "subject", "predicate", "object", "cardinality", "canon_status",
                "reader_status", "reveal_chapter", "established_chapter", "evidence", "related_entities",
                "negative_constraints", "first_recorded_chapter", "updated_chapter",
            },
            f"tracking state.facts.{identifier}",
        )
        require(fact.get("id") == identifier, f"tracking state.facts.{identifier}.id does not match its key")
        change = normalize_fact_change(
            {
                "action": "upsert",
                **{
                    key: item
                    for key, item in fact.items()
                    if key not in {"first_recorded_chapter", "updated_chapter"}
                },
            },
            f"tracking state.facts.{identifier}",
            allow_delete=False,
            through_chapter=last_chapter,
        )
        change.pop("action")
        first = as_int(fact.get("first_recorded_chapter"), f"tracking state.facts.{identifier}.first_recorded_chapter")
        updated = as_int(fact.get("updated_chapter"), f"tracking state.facts.{identifier}.updated_chapter")
        require(first <= last_chapter, f"fact {identifier} starts after current chapter")
        require(updated <= last_chapter, f"fact {identifier} updates after current chapter")
        change["first_recorded_chapter"] = first
        change["updated_chapter"] = updated
        normalized[identifier] = change
    validate_fact_set(normalized)
    return normalized


def fact_reveal_label(fact: dict[str, Any]) -> str:
    if fact["reader_status"] == "未揭示":
        return "未揭示"
    return f"{fact['reader_status']}（第{fact['reveal_chapter']}章）"


def render_fact_table(title: str, facts: dict[str, dict[str, Any]], revision: int) -> str:
    lines = [
        f"# {title}",
        "",
        f"> 状态修订：{revision}。由 `_tracking-state.json` 确定性生成，禁止手改。",
        "",
        "| ID | 类别 | 主体 | 关系/断言 | 客体/值 | 口径 | 读者状态 | 证据 | 禁止误读 | 最近变更章 |",
        "|---|---|---|---|---|---|---|---|---|---:|",
    ]
    for identifier in sorted(facts):
        fact = facts[identifier]
        evidence = "；".join(fact["evidence"])
        negatives = "；".join(fact["negative_constraints"]) or "—"
        lines.append(
            f"| {identifier} | {fact['category']} | {fact['subject']} | {fact['predicate']} | {fact['object']} | "
            f"{fact['canon_status']}/{fact['cardinality']} | {fact_reveal_label(fact)} | {evidence} | "
            f"{negatives} | 第{fact['updated_chapter']}章 |"
        )
    return "\n".join(lines) + "\n"


def render_entity_dossier(entity: str, facts: dict[str, dict[str, Any]], revision: int) -> str:
    selected = {
        identifier: fact
        for identifier, fact in facts.items()
        if portable_name_key(fact["subject"]) == portable_name_key(entity)
        or portable_name_key(entity) in {portable_name_key(item) for item in fact["related_entities"]}
    }
    return render_fact_table(f"{entity}｜长期事实档案", selected, revision)


def validate_context_input(value: object, *, include_initial_fields: bool) -> dict[str, Any]:
    context = as_mapping(value, "context")
    allowed = {"position", "long_term_constraints", "active_character_names", "continuity_risks"}
    if include_initial_fields:
        allowed.update({"recent_chapters", "next_chapter_commitments"})
    require_known_keys(context, allowed, "context")
    normalized: dict[str, Any] = {
        "position": validate_position(context.get("position")),
        "long_term_constraints": clean_string_list(
            context.get("long_term_constraints", []), "context.long_term_constraints", maximum=6
        ),
        "active_character_names": [
            safe_file_component(name, f"context.active_character_names[{index}]")
            for index, name in enumerate(as_list(context.get("active_character_names", []), "context.active_character_names"))
        ],
        "continuity_risks": clean_string_list(
            context.get("continuity_risks", []), "context.continuity_risks", maximum=5
        ),
    }
    require(len(normalized["active_character_names"]) <= 6, "context.active_character_names may contain at most 6 names")
    require(
        len({portable_name_key(name) for name in normalized["active_character_names"]})
        == len(normalized["active_character_names"]),
        "context.active_character_names contains cross-platform duplicates",
    )
    if include_initial_fields:
        recent: list[dict[str, Any]] = []
        for index, raw_item in enumerate(as_list(context.get("recent_chapters", []), "context.recent_chapters")):
            item = as_mapping(raw_item, f"context.recent_chapters[{index}]")
            require_known_keys(item, {"chapter", "summary"}, f"context.recent_chapters[{index}]")
            recent.append(
                {
                    "chapter": as_int(item.get("chapter"), f"context.recent_chapters[{index}].chapter", minimum=1),
                    "summary": clean_text(item.get("summary"), f"context.recent_chapters[{index}].summary", max_bytes=360),
                }
            )
        require(len(recent) <= 3, "context.recent_chapters may contain at most 3 items")
        normalized["recent_chapters"] = recent
        normalized["next_chapter_commitments"] = clean_string_list(
            context.get("next_chapter_commitments", []), "context.next_chapter_commitments", maximum=5
        )
    return normalized


def active_foreshadow_lines(rows: dict[str, dict[str, Any]]) -> list[str]:
    importance = {value: index for index, value in enumerate(FORESHADOW_IMPORTANCE)}
    candidates = [row for row in rows.values() if row["status"] == "已埋"]
    candidates.sort(
        key=lambda row: (importance[row["importance"]], row["planned_resolution_chapter"] or 10**12, row["id"])
    )
    result = []
    for row in candidates[:8]:
        planned = f"第{row['planned_resolution_chapter']}章" if row["planned_resolution_chapter"] else "回收章未定"
        result.append(f"{row['id']}｜{row['summary']}｜埋第{row['planted_chapter']}章｜{planned}｜{row['importance']}")
    return result


def render_context(state: dict[str, Any]) -> str:
    context = state["context"]
    position = context["position"]
    current_chapter = (
        "尚未开篇" if state["last_committed_chapter"] == 0 else f"第{state['last_committed_chapter']}章"
    )
    # 位置与持有物必须进热上下文。它们此前只存在快照文件里，而日更规则是
    # 「核心复用角色若不在本节，才去读 角色状态/{名}.md」——主角必然在本节，
    # 那条分支永不触发，于是写下一章时模型看不到人在哪、手里有什么。
    # 实测后果：上一章写住校宿舍，下一章骑车从家出发；上一章娘摆针线摊，
    # 下一章变卖菜摊。这两类是跨章连续性最高频的崩法。
    character_lines = []
    for name in context["active_character_names"]:
        snapshot = state["characters"][name]
        held = "；".join(snapshot["abilities_resources"][:2]) or "无"
        character_lines.append(
            f"{name}｜{snapshot['identity']}｜{snapshot['state']}｜"
            f"位置：{clip_bytes(snapshot['location'], CONTEXT_FIELD_BYTES)}｜"
            f"持有：{clip_bytes(held, CONTEXT_FIELD_BYTES)}｜目标：{snapshot['goal']}"
        )
    sections: list[tuple[str, list[str]]] = [
        (
            "## 当前位置",
            [
                f"当前章：{current_chapter}",
                f"卷：{position['volume']}（始于第{position['volume_start_chapter']}章）",
                f"故事时间：{position['story_time']}",
                f"场景：{position['scene']}",
            ],
        ),
        ("## 长期约束", context["long_term_constraints"]),
        ("## 核心角色状态", character_lines),
        ("## 活跃伏笔", active_foreshadow_lines(state["foreshadow"])),
        ("## 近三章速记", [f"第{item['chapter']}章｜{item['summary']}" for item in context["recent_chapters"]]),
        ("## 下一章承诺", context["next_chapter_commitments"]),
        ("## 连贯性风险", context["continuity_risks"]),
    ]
    lines = [
        f"# 写作连续性上下文 — {state['book_title']}",
        "",
        f"> 状态修订：{state['state_revision']}。截至当前章的续写状态卡，只放下一章真正需要的连续性状态。",
        "",
    ]
    for heading, values in sections:
        lines.append(heading)
        lines.extend(f"- {value}" for value in values or ["无"])
        lines.append("")
    payload = "\n".join(lines).rstrip() + "\n"
    headings = tuple(line for line in payload.splitlines() if line.startswith("## "))
    require(headings == CONTEXT_HEADINGS, "generated context headings do not match the seven-section schema")
    require(byte_size(payload) <= CONTEXT_MAX_BYTES, f"hot context exceeds {CONTEXT_MAX_BYTES} bytes")
    return payload


def normalize_delta(
    value: object,
    *,
    through_chapter: int,
    snapshots: dict[str, dict[str, Any]],
    existing_core_names: dict[str, str],
) -> dict[str, Any]:
    delta = as_mapping(value, "delta")
    require_known_keys(
        delta,
        {
            "result", "character_changes", "foreshadow_changes", "timeline_events", "fact_changes", "constraints",
            "next_chapter_commitments", "retired_context_items", "retired_characters",
            "continuity_changes",
        },
        "delta",
    )
    continuity_changes: list[dict[str, Any]] = []
    for index, raw in enumerate(as_list(delta.get("continuity_changes", []), "delta.continuity_changes")):
        item = as_mapping(raw, f"delta.continuity_changes[{index}]")
        require_known_keys(item, {"name", "field", "from", "to", "reason"}, f"delta.continuity_changes[{index}]")
        field = clean_text(item.get("field"), f"delta.continuity_changes[{index}].field", max_bytes=32)
        require(field in GUARDED_SNAPSHOT_FIELDS, f"delta.continuity_changes[{index}].field must be one of {GUARDED_SNAPSHOT_FIELDS}")
        continuity_changes.append({
            "name": safe_file_component(item.get("name"), f"delta.continuity_changes[{index}].name"),
            "field": field,
            "from": clean_text(item.get("from"), f"delta.continuity_changes[{index}].from", max_bytes=480),
            "to": clean_text(item.get("to"), f"delta.continuity_changes[{index}].to", max_bytes=480),
            "reason": clean_text(item.get("reason"), f"delta.continuity_changes[{index}].reason", max_bytes=240),
        })
    retired_characters = [
        safe_file_component(name, f"delta.retired_characters[{index}]")
        for index, name in enumerate(as_list(delta.get("retired_characters", []), "delta.retired_characters"))
    ]
    retired_keys = [portable_name_key(name) for name in retired_characters]
    require(len(retired_keys) == len(set(retired_keys)), "delta.retired_characters contains duplicate characters")
    retiring = set(retired_keys)
    character_changes: list[dict[str, Any]] = []
    for index, raw_change in enumerate(as_list(delta.get("character_changes", []), "delta.character_changes")):
        change = as_mapping(raw_change, f"delta.character_changes[{index}]")
        require_known_keys(change, {"name", "change"}, f"delta.character_changes[{index}]")
        name = safe_file_component(change.get("name"), f"delta.character_changes[{index}].name")
        existing = existing_core_names.get(portable_name_key(name))
        is_core = name in snapshots or existing is not None
        # 本章退役的角色记录最后一次变化即可，不必再交一份马上要删的快照。
        require(
            not is_core or name in snapshots or portable_name_key(name) in retiring,
            f"core character {name} changed but has no current snapshot",
        )
        character_changes.append(
            {"name": name, "change": clean_text(change.get("change"), f"delta.character_changes[{index}].change", max_bytes=360)}
        )
    character_keys = [portable_name_key(item["name"]) for item in character_changes]
    require(len(character_keys) == len(set(character_keys)), "delta.character_changes contains duplicate characters")
    foreshadow_changes = [
        normalize_foreshadow_change(
            raw, f"delta.foreshadow_changes[{index}]", allow_delete=True, through_chapter=through_chapter
        )
        for index, raw in enumerate(as_list(delta.get("foreshadow_changes", []), "delta.foreshadow_changes"))
    ]
    timeline_events = [
        normalize_timeline_change(
            raw, f"delta.timeline_events[{index}]", allow_delete=True, through_chapter=through_chapter
        )
        for index, raw in enumerate(as_list(delta.get("timeline_events", []), "delta.timeline_events"))
    ]
    fact_changes = [
        normalize_fact_change(
            raw, f"delta.fact_changes[{index}]", allow_delete=True, through_chapter=through_chapter
        )
        for index, raw in enumerate(as_list(delta.get("fact_changes", []), "delta.fact_changes"))
    ]
    require(
        len({item["id"] for item in foreshadow_changes}) == len(foreshadow_changes),
        "delta.foreshadow_changes contains duplicate IDs",
    )
    require(
        len({item["id"] for item in timeline_events}) == len(timeline_events),
        "delta.timeline_events contains duplicate IDs",
    )
    require(
        len({item["id"] for item in fact_changes}) == len(fact_changes),
        "delta.fact_changes contains duplicate IDs",
    )
    require(
        set(snapshots).issubset({item["name"] for item in character_changes}),
        "character_snapshots must contain exactly the core characters changed by this transaction",
    )
    return {
        "result": clean_text(delta.get("result"), "delta.result", max_bytes=480),
        "character_changes": character_changes,
        "foreshadow_changes": foreshadow_changes,
        "timeline_events": timeline_events,
        "fact_changes": fact_changes,
        "constraints": clean_string_list(delta.get("constraints", []), "delta.constraints", maximum=6),
        "next_chapter_commitments": clean_string_list(
            delta.get("next_chapter_commitments", []), "delta.next_chapter_commitments", maximum=5
        ),
        "retired_context_items": clean_string_list(
            delta.get("retired_context_items", []), "delta.retired_context_items", maximum=11
        ),
        "retired_characters": retired_characters,
        "continuity_changes": continuity_changes,
    }


def render_delta(chapter: int, title: str, delta: dict[str, Any], core_names: set[str]) -> str:
    lines = [
        f"# 第{chapter:03d}章 · {title}",
        f"- 结果：{delta['result']}",
        "- 下一章承诺：" + ("；".join(delta["next_chapter_commitments"]) or "无"),
        "",
        "## 角色变化",
    ]
    lines.extend(
        f"- {item['name']}｜{'核心' if item['name'] in core_names else '临时'}｜{item['change']}"
        for item in delta["character_changes"]
    )
    if not delta["character_changes"]:
        lines.append("- 无")
    lines.extend(["", "## 伏笔变化"])
    for item in delta["foreshadow_changes"]:
        if item["action"] == "delete":
            lines.append(f"- {item['id']}｜删除当前登记")
        else:
            planned = f"第{item['planned_resolution_chapter']}章" if item["planned_resolution_chapter"] else "未定"
            lines.append(f"- {item['id']}｜{item['status']}｜{item['summary']}｜回收{planned}")
    if not delta["foreshadow_changes"]:
        lines.append("- 无")
    lines.extend(["", "## 时间与揭示"])
    for item in delta["timeline_events"]:
        if item["action"] == "delete":
            lines.append(f"- {item['id']}｜删除当前登记")
        else:
            lines.append(
                f"- {item['id']}｜{item['story_time']}｜事实：{item['objective_fact']}｜"
                f"读者：{item['reader_knowledge']}｜{item['reveal_status']}"
            )
    if not delta["timeline_events"]:
        lines.append("- 无")
    lines.extend(["", "## 长期事实变化"])
    for item in delta["fact_changes"]:
        if item["action"] == "delete":
            lines.append(f"- {item['id']}｜删除当前登记")
        else:
            lines.append(
                f"- {item['id']}｜{item['category']}｜{item['subject']} {item['predicate']} {item['object']}｜"
                f"{item['canon_status']}｜{fact_reveal_label(item)}"
            )
    if not delta["fact_changes"]:
        lines.append("- 无")
    lines.extend(["", "## 连贯性约束"])
    lines.extend(f"- {item}" for item in delta["constraints"])
    if not delta["constraints"]:
        lines.append("- 无")
    if delta.get("continuity_changes"):
        # 位置/持有物的改动单列一节：这两项是跨章硬伤高发区，出问题时要能一眼
        # 翻到是哪一章、从什么改成什么、给的理由是什么。
        lines.extend(["", "## 跨章连续性变更"])
        lines.extend(
            f"- {item['name']}｜{GUARDED_FIELD_LABEL[item['field']]}｜{item['from']} → {item['to']}｜{item['reason']}"
            for item in delta["continuity_changes"]
        )
    retired = delta.get("retired_context_items", []) + [
        f"角色状态：{name}" for name in delta.get("retired_characters", [])
    ]
    if retired:
        # 退役条目在此留档，续写状态卡收缩后仍可回查当初撤下了什么。
        lines.extend(["", "## 本章退役登记"])
        lines.extend(f"- {item}" for item in retired)
    payload = "\n".join(lines) + "\n"
    size = byte_size(payload)
    require(size <= DELTA_MAX_BYTES, f"chapter delta is {size} bytes; hard cap is {DELTA_MAX_BYTES}")
    return payload


def normalize_state(document: object) -> dict[str, Any]:
    root = as_mapping(document, "tracking state")
    require_known_keys(
        root,
        {
            "schema_version", "book_title", "last_committed_chapter", "imported_through_chapter",
            "state_revision", "context", "characters", "foreshadow", "timeline", "facts",
        },
        "tracking state",
    )
    require(root.get("schema_version") == TRACKING_SCHEMA_VERSION, "tracking state schema is unsupported")
    last_chapter = as_int(root.get("last_committed_chapter"), "tracking state.last_committed_chapter")
    imported_through = as_int(root.get("imported_through_chapter"), "tracking state.imported_through_chapter")
    require(imported_through <= last_chapter, "imported chapter cutoff exceeds current chapter")
    context = validate_context_input(root.get("context"), include_initial_fields=True)
    require(
        context["position"]["volume_start_chapter"] <= max(1, last_chapter),
        "context.position.volume_start_chapter is after the current writing position",
    )
    recent_numbers = [item["chapter"] for item in context["recent_chapters"]]
    require(recent_numbers == sorted(recent_numbers), "context.recent_chapters must be ordered")
    require(len(recent_numbers) == len(set(recent_numbers)), "context.recent_chapters contains duplicates")
    require(all(chapter <= last_chapter for chapter in recent_numbers), "context.recent_chapters cannot include future chapters")
    characters = normalize_snapshots(root.get("characters", {}), "tracking state.characters")
    for name in context["active_character_names"]:
        require(name in characters, f"active core character {name} has no current snapshot")
    foreshadow = normalize_foreshadow_state(root.get("foreshadow", {}), last_chapter)
    timeline = normalize_timeline_state(root.get("timeline", {}), last_chapter)
    facts = normalize_fact_state(root.get("facts", {}), last_chapter)
    if last_chapter == 0:
        require(not foreshadow, "a chapter-0 project cannot have planted foreshadow facts")
        require(not timeline, "a chapter-0 project cannot have established timeline facts")
    return {
        "schema_version": TRACKING_SCHEMA_VERSION,
        "book_title": clean_text(root.get("book_title"), "tracking state.book_title", max_bytes=240),
        "last_committed_chapter": last_chapter,
        "imported_through_chapter": imported_through,
        "state_revision": as_int(root.get("state_revision"), "tracking state.state_revision"),
        "context": context,
        "characters": characters,
        "foreshadow": foreshadow,
        "timeline": timeline,
        "facts": facts,
    }


def load_state(project: Path) -> dict[str, Any]:
    path = state_path(project)
    require(path.exists(), "tracking state is missing; run init first")
    return normalize_state(read_json(path))


def normalize_initial_document(document: object) -> dict[str, Any]:
    root = as_mapping(document, "init input")
    require_known_keys(
        root,
        {
            "schema_version", "book_title", "last_chapter", "context", "character_snapshots",
            "foreshadow", "timeline_events", "facts",
        },
        "init input",
    )
    require(root.get("schema_version") == INPUT_SCHEMA_VERSION, "init input schema_version is unsupported")
    last_chapter = as_int(root.get("last_chapter"), "last_chapter")
    context = validate_context_input(root.get("context"), include_initial_fields=True)
    snapshots = normalize_snapshots(root.get("character_snapshots", {}))
    foreshadow: dict[str, dict[str, Any]] = {}
    for index, raw_row in enumerate(as_list(root.get("foreshadow", []), "foreshadow")):
        row = normalize_foreshadow_change(
            raw_row, f"foreshadow[{index}]", allow_delete=False, through_chapter=last_chapter
        )
        require(row["id"] not in foreshadow, f"duplicate foreshadow ID {row['id']}")
        row.pop("action")
        row["updated_chapter"] = max(1, last_chapter)
        foreshadow[row["id"]] = row
    timeline: dict[str, dict[str, Any]] = {}
    for index, raw_event in enumerate(as_list(root.get("timeline_events", []), "timeline_events")):
        event = normalize_timeline_change(
            raw_event, f"timeline_events[{index}]", allow_delete=False, through_chapter=last_chapter
        )
        require(event["id"] not in timeline, f"duplicate timeline event ID {event['id']}")
        event.pop("action")
        event["first_recorded_chapter"] = max(1, last_chapter)
        event["updated_chapter"] = max(1, last_chapter)
        timeline[event["id"]] = event
    facts: dict[str, dict[str, Any]] = {}
    for index, raw_fact in enumerate(as_list(root.get("facts", []), "facts")):
        fact = normalize_fact_change(
            raw_fact, f"facts[{index}]", allow_delete=False, through_chapter=last_chapter
        )
        require(fact["id"] not in facts, f"duplicate fact ID {fact['id']}")
        fact.pop("action")
        fact["first_recorded_chapter"] = last_chapter
        fact["updated_chapter"] = last_chapter
        facts[fact["id"]] = fact
    validate_fact_set(facts)
    return normalize_state(
        {
            "schema_version": TRACKING_SCHEMA_VERSION,
            "book_title": clean_text(root.get("book_title"), "book_title", max_bytes=240),
            "last_committed_chapter": last_chapter,
            "imported_through_chapter": last_chapter,
            "state_revision": 0,
            "context": context,
            "characters": snapshots,
            "foreshadow": foreshadow,
            "timeline": timeline,
            "facts": facts,
        }
    )


def normalize_transaction(state: dict[str, Any], document: object) -> dict[str, Any]:
    root = as_mapping(document, "transaction")
    require_known_keys(
        root,
        {
            "schema_version", "mode", "chapter", "chapter_title", "expected_state_revision",
            "delta", "context", "character_snapshots",
        },
        "transaction",
    )
    require(root.get("schema_version") == INPUT_SCHEMA_VERSION, "transaction schema_version is unsupported")
    mode = clean_text(root.get("mode"), "mode", max_bytes=24)
    require(mode in {"append", "revision"}, "mode must be append or revision")
    chapter = as_int(root.get("chapter"), "chapter", minimum=1)
    expected_revision = as_int(root.get("expected_state_revision"), "expected_state_revision")
    require(expected_revision == state["state_revision"], "tracking state changed since this transaction was prepared")
    last = state["last_committed_chapter"]
    if mode == "append":
        require(chapter == last + 1, f"append chapter must be {last + 1}, got {chapter}")
    else:
        require(chapter <= last, f"cannot revise unwritten chapter {chapter}; last committed chapter is {last}")
    context = validate_context_input(root.get("context"), include_initial_fields=False)
    snapshots = normalize_snapshots(root.get("character_snapshots", {}))
    existing_names = {portable_name_key(name): name for name in state["characters"]}
    for name in snapshots:
        existing = existing_names.get(portable_name_key(name))
        require(existing is None or existing == name, f"character {name} conflicts with existing character {existing}")
    through_chapter = chapter if mode == "append" else last
    delta = normalize_delta(
        root.get("delta"),
        through_chapter=through_chapter,
        snapshots=snapshots,
        existing_core_names=existing_names,
    )
    return {
        "mode": mode,
        "chapter": chapter,
        "title": clean_text(root.get("chapter_title"), "chapter_title", max_bytes=240),
        "delta": delta,
        "context": context,
        "snapshots": snapshots,
    }


def checkpoint_record(
    change: dict[str, Any], chapter: int, previous: dict[str, Any] | None, *, keep_first_chapter: bool = False
) -> dict[str, Any]:
    current = {key: value for key, value in change.items() if key != "action"}
    current["updated_chapter"] = max(previous["updated_chapter"] if previous else chapter, chapter)
    if keep_first_chapter:
        current["first_recorded_chapter"] = previous["first_recorded_chapter"] if previous else chapter
    return current


def guarded_field_value(snapshot: dict[str, Any], field: str) -> str:
    """人看到的形态：保持存储顺序，与 角色状态/{名}.md 渲染出来的一致。

    申报的 from 要跟这个比对，作者/模型从快照文件里照抄即可。
    """
    value = snapshot[field]
    return "；".join(value) if isinstance(value, list) else value


def guarded_field_key(snapshot: dict[str, Any], field: str) -> str:
    """判「变没变」用的形态：列表排序后再比，顺序不算变化。

    持有物列表重新生成时顺序常会抖动，按原序比会把纯重排判成改动，
    逼作者为一个没发生的变化写申报——闸口一旦开始误报就会被忽略。
    """
    value = snapshot[field]
    return "；".join(sorted(value)) if isinstance(value, list) else value


def brief(text: str, limit: int = 60) -> str:
    """错误信息里的旧值/新值要截断。

    持有物是列表拼串，正常项目就可能上千字；原样拼进报错会刷屏，作者根本
    看不到后面那句「该怎么办」。
    """
    return text if len(text) <= limit else f"{text[:limit]}…（共 {len(text)} 字）"


def enforce_continuity_guard(state: dict[str, Any], transaction: dict[str, Any]) -> None:
    """位置与持有物改变时，必须逐字报出库内旧值才放行。

    新快照是整份覆盖，工具原先不比对，于是「学校宿舍 302 室」可以被一句
    「家中（每日骑车走读）」无声顶掉，commit 和 check 全绿。这正是读者最容易
    一眼看穿的那类硬伤（上一章住校、下一章骑车从家出发；上一章娘摆针线摊、
    下一章变卖菜摊）。

    要求 from 与库内旧值逐字相同，是这条守卫的关键：模型必须先去读旧值才写得
    出来，光靠热上下文里那点信息猜不出。写对了说明它确实知道自己在改什么，
    这时候再改就是有意为之，不是漂移。
    """
    acknowledged: dict[tuple[str, str], dict[str, Any]] = {}
    for item in transaction["delta"]["continuity_changes"]:
        key = (portable_name_key(item["name"]), item["field"])
        require(key not in acknowledged, f"delta.continuity_changes 重复申报 {item['name']} 的 {item['field']}")
        acknowledged[key] = item

    for name, snapshot in transaction["snapshots"].items():
        previous = state["characters"].get(name)
        if previous is None:
            continue
        for field in GUARDED_SNAPSHOT_FIELDS:
            before = guarded_field_value(previous, field)
            after = guarded_field_value(snapshot, field)
            if guarded_field_key(previous, field) == guarded_field_key(snapshot, field):
                continue
            label = GUARDED_FIELD_LABEL[field]
            item = acknowledged.pop((portable_name_key(name), field), None)
            require(
                item is not None,
                f"{name} 的{label}从「{brief(before)}」改成了「{brief(after)}」，但 delta.continuity_changes 没有申报。"
                f"跨章连续性硬伤多数是这样无声发生的：先确认这次改动是剧情需要还是忘了上一章的设定，"
                f"确实要改就补一条 {{name, field={field}, from, to, reason}}，from 必须是库内旧值原文。",
            )
            claimed_from = brief(item["from"])
            claimed_to = brief(item["to"])
            require(
                item["from"] == before,
                f"{name} 的{label}申报的 from 与库内旧值不符：申报「{claimed_from}」，库内是「{brief(before)}」。"
                f"说明这次改动没有基于上一章的真实状态——先读 追踪/角色状态/{name}.md 再改。",
            )
            require(
                item["to"] == after,
                f"{name} 的{label}申报的 to 与新快照不符：申报「{claimed_to}」，快照是「{brief(after)}」。",
            )

    require(
        not acknowledged,
        "delta.continuity_changes 申报了并未发生的变更："
        + "、".join(f"{name}.{field}" for name, field in sorted(acknowledged)),
    )


def merge_transaction(state: dict[str, Any], transaction: dict[str, Any]) -> dict[str, Any]:
    next_state = copy.deepcopy(state)
    chapter = transaction["chapter"]
    if transaction["mode"] == "append":
        next_state["last_committed_chapter"] = chapter
    next_state["state_revision"] += 1
    next_state["characters"].update(transaction["snapshots"])

    next_context = transaction["context"]
    # 退役说的是「从此刻起离开当前状态」，只有 append 的逐章记录代表此刻；
    # 修订记录属于被改写的旧章，落在那里会谎报退役发生的章节。
    is_revision = transaction["mode"] == "revision"
    require(
        not (is_revision and transaction["delta"]["retired_characters"]),
        "retired_characters must be committed in an append transaction, not a revision",
    )
    for name in transaction["delta"]["retired_characters"]:
        require(name in next_state["characters"], f"retired character {name} has no current snapshot")
        require(
            name not in transaction["snapshots"],
            f"character {name} cannot be retired and updated in the same transaction",
        )
        require(
            name not in next_context["active_character_names"],
            f"retired character {name} is still listed in context.active_character_names",
        )
        next_state["characters"].pop(name)

    # 上下文条目是整份提交的；漏写会静默丢历史裁定，因此掉落必须显式声明。
    previous_items = set(state["context"]["long_term_constraints"]) | set(state["context"]["continuity_risks"])
    dropped = previous_items - (set(next_context["long_term_constraints"]) | set(next_context["continuity_risks"]))
    require(
        not (is_revision and dropped),
        "a revision must resubmit every current context item; retire them in an append transaction instead: "
        + "；".join(sorted(dropped)),
    )
    undeclared = sorted(dropped - set(transaction["delta"]["retired_context_items"]))
    require(
        not undeclared,
        "context items were dropped without being declared in delta.retired_context_items: "
        + "；".join(undeclared),
    )
    transaction["delta"]["retired_context_items"] = sorted(dropped)

    for change in transaction["delta"]["foreshadow_changes"]:
        if change["action"] == "delete":
            next_state["foreshadow"].pop(change["id"], None)
        else:
            next_state["foreshadow"][change["id"]] = checkpoint_record(
                change, chapter, next_state["foreshadow"].get(change["id"])
            )
    for change in transaction["delta"]["timeline_events"]:
        if change["action"] == "delete":
            next_state["timeline"].pop(change["id"], None)
        else:
            next_state["timeline"][change["id"]] = checkpoint_record(
                change, chapter, next_state["timeline"].get(change["id"]), keep_first_chapter=True
            )
    for change in transaction["delta"]["fact_changes"]:
        if change["action"] == "delete":
            next_state["facts"].pop(change["id"], None)
        else:
            next_state["facts"][change["id"]] = checkpoint_record(
                change, chapter, next_state["facts"].get(change["id"]), keep_first_chapter=True
            )
    validate_fact_set(next_state["facts"])

    recent_by_chapter = {item["chapter"]: item for item in state["context"]["recent_chapters"]}
    if chapter in recent_by_chapter or transaction["mode"] == "append":
        recent_by_chapter[chapter] = {"chapter": chapter, "summary": transaction["delta"]["result"]}
    recent = sorted(recent_by_chapter.values(), key=lambda item: item["chapter"])[-3:]
    current_last = next_state["last_committed_chapter"]
    next_commitments = (
        transaction["delta"]["next_chapter_commitments"]
        if transaction["mode"] == "append" or chapter == current_last
        else state["context"]["next_chapter_commitments"]
    )
    next_state["context"] = {
        **next_context,
        "recent_chapters": recent,
        "next_chapter_commitments": next_commitments,
    }
    return normalize_state(next_state)


def render_views(state: dict[str, Any]) -> dict[str, str]:
    revision = state["state_revision"]
    views = {
        "上下文.md": render_context(state),
        "伏笔.md": render_foreshadow(state["foreshadow"], revision),
        "长期事实.md": render_fact_table("长期事实索引", state["facts"], revision),
        "关系清单.md": render_fact_table(
            "关系清单",
            {
                identifier: fact
                for identifier, fact in state["facts"].items()
                if fact["category"] in RELATION_CATEGORIES or identifier.startswith("R")
            },
            revision,
        ),
    }
    author, reader = render_timeline_views(state["timeline"], revision)
    views["时间线/作者真相.md"] = author
    views["时间线/读者已知.md"] = reader
    for name, snapshot in state["characters"].items():
        views[f"角色状态/{name}.md"] = render_snapshot(
            name, snapshot, state["last_committed_chapter"], revision
        )
    entities = {
        entity
        for fact in state["facts"].values()
        for entity in [fact["subject"], *fact["related_entities"]]
    }
    portable_entities: dict[str, str] = {}
    for entity in entities:
        safe = safe_file_component(entity, "fact entity")
        key = portable_name_key(safe)
        require(key not in portable_entities or portable_entities[key] == safe, f"facts contain colliding entity names: {safe}")
        portable_entities[key] = safe
    for entity in sorted(portable_entities.values(), key=portable_name_key):
        views[f"事实档案/{entity}.md"] = render_entity_dossier(entity, state["facts"], revision)
    return views


def write_views(tracking: Path, views: dict[str, str]) -> None:
    # 上下文携带 next revision，先写它；任何后续失败都会让 hook/check 发现
    # 上下文 revision 与最后提交的 _tracking-state.json 不一致。
    write_if_changed(tracking / "上下文.md", views["上下文.md"])
    for relative in sorted(path for path in views if path != "上下文.md"):
        write_if_changed(tracking / relative, views[relative])
    expected_character_files = {
        Path(relative).name for relative in views if relative.startswith("角色状态/")
    }
    character_dir = tracking / "角色状态"
    character_dir.mkdir(parents=True, exist_ok=True)
    for path in character_dir.glob("*.md"):
        if path.name not in expected_character_files:
            path.unlink()
    expected_dossier_files = {
        Path(relative).name for relative in views if relative.startswith("事实档案/")
    }
    dossier_dir = tracking / "事实档案"
    dossier_dir.mkdir(parents=True, exist_ok=True)
    for path in dossier_dir.glob("*.md"):
        if path.name not in expected_dossier_files:
            path.unlink()


def warn_sizes(views: dict[str, str], delta_payload: str | None = None) -> None:
    if delta_payload is not None and byte_size(delta_payload) > DELTA_TARGET_BYTES:
        emit(
            f"WARNING: chapter delta is {byte_size(delta_payload)} bytes; target is <= {DELTA_TARGET_BYTES}",
            error=True,
        )
    context_size = byte_size(views["上下文.md"])
    if context_size > CONTEXT_TARGET_BYTES:
        emit(f"WARNING: hot context is {context_size} bytes; target is <= {CONTEXT_TARGET_BYTES}", error=True)
    for relative, payload in views.items():
        if not relative.startswith("角色状态/"):
            continue
        size = byte_size(payload)
        if size > SNAPSHOT_TARGET_BYTES:
            emit(
                f"WARNING: character snapshot {Path(relative).stem} is {size} bytes; target is <= {SNAPSHOT_TARGET_BYTES}",
                error=True,
            )


def initialize(project: Path, document: object) -> dict[str, Any]:
    tracking = tracking_root(project)
    require(not state_path(project).exists(), "tracking state already exists; init never overwrites project state")
    state = normalize_initial_document(document)
    views = render_views(state)
    state_payload = json_payload(state)

    # 输入全部校验通过后才动用户文件，失败的 init 不会挪走任何东西。
    archived = archive_retired_tracking_paths(tracking)
    for directory in (
        tracking / "逐章记录", tracking / "角色状态", tracking / "时间线", tracking / "事实档案"
    ):
        directory.mkdir(parents=True, exist_ok=True)
    write_views(tracking, views)
    atomic_write_text(state_path(project), state_payload)
    warn_sizes(views)
    if archived:
        emit(
            f"NOTE: 旧追踪结构已原样移入 追踪/{RETIRED_ARCHIVE_DIR}/：{', '.join(archived)}；"
            "当前状态以本次 init 输入为准，旧文件不参与解析。",
            error=True,
        )
    return state


def apply_transaction(project: Path, document: object) -> dict[str, Any]:
    tracking = tracking_root(project)
    require_no_retired_tracking_paths(tracking)
    state = load_state(project)
    transaction = normalize_transaction(state, document)
    next_state = merge_transaction(state, transaction)

    delta_payload = render_delta(
        transaction["chapter"],
        transaction["title"],
        transaction["delta"],
        # 本章退役的角色在 next_state 里已被删除，但本章记录里仍应标为核心。
        set(next_state["characters"]) | set(transaction["delta"]["retired_characters"]),
    )
    views = render_views(next_state)
    # 放在渲染之后：快照体积超硬上限之类的结构性错误应当先报，
    # 否则一份又超大又漂移的快照只会看到连续性告警，看不到真正的拦截原因。
    enforce_continuity_guard(state, transaction)
    next_state_payload = json_payload(next_state)
    path = delta_path(tracking, transaction["chapter"])
    if transaction["mode"] == "append" and path.exists():
        require(
            path.read_text(encoding="utf-8") == delta_payload,
            f"chapter delta {transaction['chapter']} already exists with different content",
        )

    write_if_changed(path, delta_payload)
    write_views(tracking, views)
    # 唯一权威文件最后落盘；在此之前失败可用同一事务直接重跑。
    atomic_write_text(state_path(project), next_state_payload)
    warn_sizes(views, delta_payload)
    return next_state


def check_project(project: Path) -> dict[str, Any]:
    tracking = tracking_root(project)
    require_no_retired_tracking_paths(tracking)
    state = load_state(project)
    last_chapter = state["last_committed_chapter"]
    required_delta_start = state["imported_through_chapter"] + 1
    for chapter in range(required_delta_start, last_chapter + 1):
        require(delta_path(tracking, chapter).exists(), f"chapter delta {chapter} is missing")
    for path in (tracking / "逐章记录").glob("第*章.md"):
        match = re.fullmatch(r"第(\d+)章\.md", path.name)
        require(match is not None, f"chapter delta has an invalid filename: {path.name}")
        chapter = as_int(int(match.group(1)), f"chapter delta {path.name}", minimum=1)
        require(path == delta_path(tracking, chapter), f"chapter delta {chapter} filename is not canonical")
        require(chapter <= last_chapter, f"chapter delta {chapter} exceeds last_committed_chapter")
        require(path.stat().st_size <= DELTA_MAX_BYTES, f"chapter delta {chapter} exceeds {DELTA_MAX_BYTES} bytes")

    expected_views = render_views(state)
    for relative, expected in expected_views.items():
        path = tracking / relative
        require(path.exists(), f"derived view is missing: {relative}")
        require(
            path.read_text(encoding="utf-8") == expected,
            f"derived view differs from _tracking-state.json: {relative}",
        )
    expected_character_files = {
        Path(relative).name for relative in expected_views if relative.startswith("角色状态/")
    }
    actual_character_files = {path.name for path in (tracking / "角色状态").glob("*.md")}
    require(actual_character_files == expected_character_files, "character snapshot files differ from tracking state")
    expected_dossier_files = {
        Path(relative).name for relative in expected_views if relative.startswith("事实档案/")
    }
    actual_dossier_files = {path.name for path in (tracking / "事实档案").glob("*.md")}
    require(actual_dossier_files == expected_dossier_files, "fact dossier files differ from tracking state")
    return state


def migrate_v4(project: Path, document: object) -> dict[str, Any]:
    """Upgrade a schema-4 authority in place and optionally seed durable canon facts.

    This is a state migration, not a fictional chapter event: it never creates or
    rewrites a chapter delta.  All derived views are rebuilt and authority is still
    written last, so an interrupted migration can be retried from the same input.
    """
    tracking = tracking_root(project)
    require_no_retired_tracking_paths(tracking)
    raw = as_mapping(read_json(state_path(project)), "tracking state")
    require(raw.get("schema_version") == 4, "migrate-v4 requires an existing schema_version=4 state")
    migration = as_mapping(document, "migration input")
    require_known_keys(migration, {"schema_version", "expected_state_revision", "facts"}, "migration input")
    require(migration.get("schema_version") == INPUT_SCHEMA_VERSION, "migration input schema_version is unsupported")
    expected = as_int(migration.get("expected_state_revision"), "expected_state_revision")
    current_revision = as_int(raw.get("state_revision"), "tracking state.state_revision")
    require(expected == current_revision, "tracking state changed since this migration was prepared")
    last_chapter = as_int(raw.get("last_committed_chapter"), "tracking state.last_committed_chapter")
    facts: dict[str, dict[str, Any]] = {}
    for index, raw_fact in enumerate(as_list(migration.get("facts", []), "facts")):
        fact = normalize_fact_change(
            raw_fact, f"facts[{index}]", allow_delete=False, through_chapter=last_chapter
        )
        require(fact["id"] not in facts, f"duplicate fact ID {fact['id']}")
        fact.pop("action")
        fact["first_recorded_chapter"] = last_chapter
        fact["updated_chapter"] = last_chapter
        facts[fact["id"]] = fact
    validate_fact_set(facts)
    candidate = copy.deepcopy(raw)
    candidate["schema_version"] = TRACKING_SCHEMA_VERSION
    candidate["state_revision"] = current_revision + 1
    candidate["facts"] = facts
    state = normalize_state(candidate)
    views = render_views(state)
    write_views(tracking, views)
    atomic_write_text(state_path(project), json_payload(state))
    warn_sizes(views)
    return state


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "commit", "migrate-v4"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--project", type=Path, required=True, help="book project root containing 追踪/")
        subparser.add_argument("--input", type=Path, required=True, help="UTF-8 JSON input document")
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--project", type=Path, required=True, help="book project root containing 追踪/")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "init":
            result = initialize(args.project, read_json(args.input))
        elif args.command == "commit":
            result = apply_transaction(args.project, read_json(args.input))
        elif args.command == "migrate-v4":
            result = migrate_v4(args.project, read_json(args.input))
        else:
            result = check_project(args.project)
    except (TrackingError, OSError, UnicodeError) as exc:
        emit(f"ERROR: {exc}", error=True)
        return 2
    emit(
        json.dumps(
            {
                "last_committed_chapter": result["last_committed_chapter"],
                "state_revision": result["state_revision"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
