#!/usr/bin/env python3
"""Create, check, and select non-canonical outline forecasts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FORECAST_VERSION = 1
LEVEL_LIMITS = {
    "book": (0, 0, 0),
    "volume": (5, 30, 15),
    "unit": (3, 15, 8),
    "chapter": (1, 3, 3),
}
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class ForecastError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(content, encoding="utf-8")
    temp.replace(path)


def load_forecast(directory: Path) -> tuple[Path, dict[str, Any]]:
    path = directory / "forecast.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ForecastError(f"推演文件不存在: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ForecastError(f"推演 JSON 无效: {exc}") from exc
    if not isinstance(data, dict) or data.get("forecast_version") != FORECAST_VERSION:
        raise ForecastError("不支持的推演版本")
    branches = data.get("branches")
    if not isinstance(branches, list) or not 2 <= len(branches) <= 3:
        raise ForecastError("branches 必须包含 2-3 个分支")
    ids = [item.get("id") for item in branches if isinstance(item, dict)]
    if len(ids) != len(branches) or len(set(ids)) != len(ids):
        raise ForecastError("分支 id 缺失或重复")
    return path, data


def resolve_project_file(project_root: Path, raw: str) -> tuple[Path, str]:
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = project_root / candidate
    resolved = candidate.resolve()
    try:
        relative = resolved.relative_to(project_root).as_posix()
    except ValueError as exc:
        raise ForecastError(f"基础文件必须位于项目根目录内: {raw}") from exc
    if not resolved.is_file():
        raise ForecastError(f"基础文件不存在: {resolved}")
    return resolved, relative


def fingerprint_entries(project_root: Path, raw_paths: list[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_paths:
        path, relative = resolve_project_file(project_root, raw)
        if relative in seen:
            continue
        seen.add(relative)
        entries.append({"path": relative, "sha256": sha256_file(path), "size": path.stat().st_size})
    if not entries:
        raise ForecastError("至少提供一个 --base 基础文件")
    return entries


def context_fingerprint(entries: list[dict[str, Any]], state_revision: int | None) -> str:
    payload = {"base_files": entries, "base_state_revision": state_revision}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def current_state_revision(project_root: Path) -> int | None:
    path = project_root / "追踪" / "_tracking-state.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ForecastError(f"追踪权威状态 JSON 无效: {exc}") from exc
    revision = data.get("state_revision") if isinstance(data, dict) else None
    if not isinstance(revision, int) or revision < 0:
        raise ForecastError("追踪权威状态缺少有效 state_revision")
    return revision


def check_freshness(data: dict[str, Any]) -> dict[str, Any]:
    project_root = Path(data["project_root"]).resolve()
    changed: list[dict[str, str]] = []
    current_entries: list[dict[str, Any]] = []
    for entry in data.get("base_files", []):
        relative = entry.get("path", "")
        path = project_root / relative
        if not path.is_file():
            changed.append({"path": relative, "reason": "missing"})
            continue
        current = {"path": relative, "sha256": sha256_file(path), "size": path.stat().st_size}
        current_entries.append(current)
        if current["sha256"] != entry.get("sha256"):
            changed.append({"path": relative, "reason": "content_changed"})
    stored_revision = data.get("base_state_revision")
    current_revision = current_state_revision(project_root) if stored_revision is not None else None
    if stored_revision is not None and current_revision != stored_revision:
        changed.append({"path": "追踪/_tracking-state.json", "reason": "state_revision_changed"})
    current_fingerprint = context_fingerprint(current_entries, current_revision)
    return {
        "status": "stale" if changed or current_fingerprint != data.get("context_fingerprint") else "fresh",
        "changed": changed,
        "stored_fingerprint": data.get("context_fingerprint"),
        "current_fingerprint": current_fingerprint,
        "stored_state_revision": stored_revision,
        "current_state_revision": current_revision,
    }


def branch_skeleton(index: int) -> dict[str, Any]:
    return {
        "id": f"B{index}",
        "title": "",
        "premise": "",
        "key_decisions": [],
        "beats": [],
        "projected_changes": {"characters": [], "relationships": [], "world": [], "hooks": []},
        "reader_contract_effect": "",
        "protagonist_agency": "",
        "terminal_reserve_cost": [],
        "end_state": "",
        "next_opening": "",
        "risks": {"continuity": [], "causality": [], "character": [], "pacing": []},
        "uncertainties": [],
        "author_intent_alignment": {"score": 0, "rationale": ""},
    }


def cmd_init(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    if not project_root.is_dir():
        raise ForecastError(f"项目根目录不存在: {project_root}")
    minimum, maximum, default = LEVEL_LIMITS[args.level]
    horizon = default if args.horizon is None else args.horizon
    if not minimum <= horizon <= maximum:
        expected = "0（总纲只比较宏观方向）" if args.level == "book" else f"{minimum}-{maximum}"
        raise ForecastError(f"{args.level} 层 horizon 必须为 {expected}")
    forecast_id = args.id or datetime.now().strftime("F%Y%m%d-%H%M%S")
    if not ID_PATTERN.fullmatch(forecast_id):
        raise ForecastError("forecast id 只能包含字母、数字、点、下划线和连字符")
    directory = project_root / "大纲" / "推演" / forecast_id
    if directory.exists():
        raise ForecastError(f"推演目录已存在: {directory}")
    entries = fingerprint_entries(project_root, args.base)
    state_revision = args.state_revision
    if state_revision is None:
        state_revision = current_state_revision(project_root)
    payload: dict[str, Any] = {
        "forecast_version": FORECAST_VERSION,
        "forecast_id": forecast_id,
        "status": "draft",
        "created_at": utc_now(),
        "project_root": str(project_root),
        "level": args.level,
        "horizon_chapters": horizon,
        "divergence_point": args.divergence,
        "author_intent": args.author_intent or "",
        "base_state_revision": state_revision,
        "base_files": entries,
        "context_fingerprint": context_fingerprint(entries, state_revision),
        "branches": [branch_skeleton(index) for index in range(1, args.branches + 1)],
        "comparison": {"recommended_branch": "", "rationale": "", "tradeoffs": []},
        "selection": None,
        "canonical_writeback": {"allowed": False, "note": "本文件不自动写回正式大纲；另行取得用户授权。"},
    }
    atomic_write_json(directory / "forecast.json", payload)
    print(directory)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    _, data = load_forecast(Path(args.forecast_dir).expanduser().resolve())
    result = check_freshness(data)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "fresh" else 2


def validate_selectable(branch: dict[str, Any]) -> None:
    missing = [key for key in ("title", "premise", "reader_contract_effect", "protagonist_agency", "end_state") if not branch.get(key)]
    if not isinstance(branch.get("beats"), list) or not branch["beats"]:
        missing.append("beats")
    if missing:
        raise ForecastError(f"分支 {branch.get('id')} 尚未填写完整: {', '.join(missing)}")


def render_selected(data: dict[str, Any], branch: dict[str, Any]) -> str:
    lines = [
        f"# 已选分支：{branch['id']} {branch['title']}",
        "",
        f"- 推演编号：{data['forecast_id']}",
        f"- 推演层级：{data['level']}",
        f"- 分歧点：{data['divergence_point']}",
        f"- 选择时间：{data['selection']['selected_at']}",
        f"- 上下文指纹：`{data['context_fingerprint']}`",
        "",
        "> 本文件只记录用户已选路线，不是正式大纲，也不属于追踪事实。修改正式大纲前必须另行取得用户授权。",
        "",
        "## 路线前提",
        "",
        branch["premise"],
        "",
        "## 主角主动性",
        "",
        branch["protagonist_agency"],
        "",
        "## 读者契约影响",
        "",
        branch["reader_contract_effect"],
        "",
        "## 推演节拍",
        "",
    ]
    for index, beat in enumerate(branch["beats"], start=1):
        if isinstance(beat, dict):
            label = beat.get("chapter") or beat.get("stage") or index
            event = beat.get("event", "")
            choice = beat.get("choice", "")
            consequence = beat.get("consequence", "")
            hook = beat.get("hook", "")
            lines.append(f"{index}. **{label}**：{event}；选择：{choice}；后果：{consequence}；余势：{hook}")
        else:
            lines.append(f"{index}. {beat}")
    lines.extend(["", "## 分支终态", "", branch["end_state"], "", "## 下一单元开口", "", branch.get("next_opening") or "待映射正式大纲时补充。", ""])
    return "\n".join(lines)


def cmd_select(args: argparse.Namespace) -> int:
    if args.confirm != "SELECT":
        raise ForecastError("选择分支必须显式传入 --confirm SELECT")
    directory = Path(args.forecast_dir).expanduser().resolve()
    path, data = load_forecast(directory)
    if data.get("status") != "draft":
        raise ForecastError(f"只有 draft 推演可以选择，当前状态: {data.get('status')}")
    freshness = check_freshness(data)
    if freshness["status"] != "fresh":
        changed = ", ".join(item["path"] for item in freshness["changed"]) or "上下文指纹变化"
        raise ForecastError(f"推演已过期，拒绝选择: {changed}")
    branch = next((item for item in data["branches"] if item.get("id") == args.branch), None)
    if branch is None:
        raise ForecastError(f"分支不存在: {args.branch}")
    validate_selectable(branch)
    approval_note = (args.approval_note or "").strip()
    if not approval_note:
        raise ForecastError("必须记录用户明确选择该分支的说明")
    branch_digest = hashlib.sha256(
        json.dumps(branch, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    data["status"] = "selected"
    data["selection"] = {
        "branch_id": args.branch,
        "selected_at": utc_now(),
        "approval_note": approval_note,
        "branch_sha256": branch_digest,
    }
    atomic_write_json(path, data)
    selected_path = directory / "selected-plan.md"
    atomic_write_text(selected_path, render_selected(data, branch))
    atomic_write_json(
        directory / "selection-receipt.json",
        {
            "forecast_version": FORECAST_VERSION,
            "forecast_id": data["forecast_id"],
            "branch_id": args.branch,
            "selected_at": data["selection"]["selected_at"],
            "approval_note": approval_note,
            "branch_sha256": branch_digest,
            "context_fingerprint": data["context_fingerprint"],
            "canonical_writeback_allowed": False,
        },
    )
    print(selected_path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init", help="初始化非正史分支推演")
    init_parser.add_argument("project_root")
    init_parser.add_argument("--level", choices=tuple(LEVEL_LIMITS), default="unit")
    init_parser.add_argument("--horizon", type=int)
    init_parser.add_argument("--divergence", required=True)
    init_parser.add_argument("--author-intent")
    init_parser.add_argument("--base", action="append", required=True)
    init_parser.add_argument("--state-revision", type=int)
    init_parser.add_argument("--branches", type=int, choices=(2, 3), default=3)
    init_parser.add_argument("--id")
    init_parser.set_defaults(func=cmd_init)

    check_parser = sub.add_parser("check", help="检查基础文件变化和推演陈旧状态")
    check_parser.add_argument("forecast_dir")
    check_parser.set_defaults(func=cmd_check)

    select_parser = sub.add_parser("select", help="在用户明确选择后生成 selected-plan.md")
    select_parser.add_argument("forecast_dir")
    select_parser.add_argument("--branch", required=True)
    select_parser.add_argument("--confirm", required=True)
    select_parser.add_argument("--approval-note", required=True)
    select_parser.set_defaults(func=cmd_select)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except ForecastError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
