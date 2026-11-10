#!/usr/bin/env python3
"""Stage fiction deslop edits, protect literals, and apply checked candidates."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUN_VERSION = 1
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_])\d+(?:\.\d+)?(?:[%％年月日时分秒章卷万亿元岁号层级]*)")
TITLE_RE = re.compile(r"《([^》\n]{1,80})》")
CODE_RE = re.compile(r"`([^`\n]{1,120})`")


class GuardError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise GuardError(f"文件不存在: {path}") from exc
    except UnicodeDecodeError as exc:
        raise GuardError(f"文件不是 UTF-8: {path}") from exc


def atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(content, encoding="utf-8")
    temp.replace(path)


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def within(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise GuardError(f"正文文件必须位于项目根目录内: {path}") from exc


def unique_matches(pattern: re.Pattern[str], text: str) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for match in pattern.finditer(text):
        value = match.group(1) if match.lastindex else match.group(0)
        if value not in seen:
            values.append(value)
            seen.add(value)
    return values


def auto_ledger(text: str) -> dict[str, Any]:
    return {
        "version": 1,
        "auto": {
            "numbers": unique_matches(NUMBER_RE, text),
            "titled_terms": unique_matches(TITLE_RE, text),
            "inline_code": unique_matches(CODE_RE, text),
        },
        "manual": {
            "protected_literals": [], "entities": [], "timeline_facts": [],
            "knowledge_boundaries": [], "clues": [], "voice_markers": [],
            "intentional_roughness": [],
        },
        "allowed_changes": [],
    }


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise GuardError(f"JSON 无效: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GuardError(f"JSON 根节点必须是对象: {path}")
    return value


def load_run(raw: str) -> tuple[Path, dict[str, Any]]:
    run_dir = Path(raw).expanduser().resolve()
    manifest = load_json(run_dir / "manifest.json")
    if manifest.get("run_version") != RUN_VERSION:
        raise GuardError("不支持的去味运行版本")
    return run_dir, manifest


def snapshot_paths(run_dir: Path, manifest: dict[str, Any]) -> tuple[Path, Path]:
    return run_dir / manifest["snapshot_file"], run_dir / manifest["candidate_file"]


def changed_spans(source: str, candidate: str) -> list[dict[str, Any]]:
    before, after = source.splitlines(), candidate.splitlines()
    matcher = difflib.SequenceMatcher(a=before, b=after, autojunk=False)
    spans = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            spans.append({
                "kind": tag, "source_start": i1 + 1, "source_end": i2,
                "candidate_start": j1 + 1, "candidate_end": j2,
                "source_preview": before[i1:i2][:3], "candidate_preview": after[j1:j2][:3],
            })
    return spans


def allowed_map(ledger: dict[str, Any]) -> dict[str, str]:
    result = {}
    for item in ledger.get("allowed_changes", []):
        if isinstance(item, dict) and isinstance(item.get("from"), str) and isinstance(item.get("to"), str):
            result[item["from"]] = item["to"]
    return result


def hard_literals(ledger: dict[str, Any]) -> list[str]:
    values: list[str] = []
    auto, manual = ledger.get("auto", {}), ledger.get("manual", {})
    for key in ("numbers", "titled_terms", "inline_code"):
        if isinstance(auto.get(key), list):
            values.extend(str(item) for item in auto[key] if str(item))
    for key in ("protected_literals", "entities"):
        if isinstance(manual.get(key), list):
            values.extend(str(item) for item in manual[key] if str(item))
    return list(dict.fromkeys(values))


def build_report(run_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    snapshot, candidate_path = snapshot_paths(run_dir, manifest)
    source, candidate = read_text(snapshot), read_text(candidate_path)
    ledger = load_json(run_dir / "protection-ledger.json")
    source_live = Path(manifest["project_root"]) / manifest["source_path"]
    blocking, advisory = [], []

    if not source_live.is_file() or sha256(source_live) != manifest["source_sha256"]:
        blocking.append({"type": "stale-source", "message": "源正文在初始化后发生变化，拒绝覆盖。"})

    replacements = allowed_map(ledger)
    for literal in hard_literals(ledger):
        expected, actual = source.count(literal), candidate.count(literal)
        replacement = replacements.get(literal)
        if expected > actual and not (replacement and candidate.count(replacement) >= expected - actual):
            blocking.append({"type": "protected-literal-missing", "message": f"保护项减少: {literal!r}，源文 {expected} 次，候选稿 {actual} 次。"})

    retention = len(candidate) / max(len(source), 1)
    line_delta = abs(len(candidate.splitlines()) - max(len(source.splitlines()), 1)) / max(len(source.splitlines()), 1)
    if manifest["edit_scope"] == "in-place" and retention < 0.85:
        advisory.append({"type": "scope-retention", "message": f"in-place 字数保留率仅 {retention:.1%}。"})
    if manifest["edit_scope"] == "in-place" and line_delta > 0.10:
        advisory.append({"type": "scope-line-delta", "message": f"in-place 行数变化 {line_delta:.1%}。"})

    spans = changed_spans(source, candidate)
    atomic_json(run_dir / "changed-spans.json", {"version": 1, "spans": spans})
    return {
        "status": "blocked" if blocking else "pass", "run_id": manifest["run_id"],
        "edit_scope": manifest["edit_scope"], "rewrite_intensity": manifest["rewrite_intensity"],
        "retention_ratio": round(retention, 6), "changed_span_count": len(spans),
        "blocking": blocking, "advisory": advisory,
    }


def cmd_init(args: argparse.Namespace) -> int:
    source = Path(args.source).expanduser().resolve()
    project_root = Path(args.project_root).expanduser().resolve()
    if not source.is_file():
        raise GuardError(f"正文文件不存在: {source}")
    if not project_root.is_dir():
        raise GuardError(f"项目根目录不存在: {project_root}")
    source_relative = within(project_root, source)
    run_id = args.run_id or datetime.now().strftime("D%Y%m%d-%H%M%S")
    if not RUN_ID_RE.fullmatch(run_id):
        raise GuardError("run id 只能包含字母、数字、点、下划线和连字符")
    run_dir = project_root / ".story-deslop" / "runs" / run_id
    if run_dir.exists():
        raise GuardError(f"运行目录已存在: {run_dir}")
    run_dir.mkdir(parents=True)
    suffix = source.suffix or ".txt"
    snapshot_name, candidate_name = f"source{suffix}", f"candidate{suffix}"
    shutil.copyfile(source, run_dir / snapshot_name)
    shutil.copyfile(source, run_dir / candidate_name)
    manifest = {
        "run_version": RUN_VERSION, "run_id": run_id, "status": "draft", "created_at": now_iso(),
        "project_root": str(project_root), "source_path": source_relative, "source_sha256": sha256(source),
        "snapshot_file": snapshot_name, "candidate_file": candidate_name,
        "edit_scope": args.scope, "rewrite_intensity": args.intensity, "issue_density": args.issue_density,
    }
    atomic_json(run_dir / "manifest.json", manifest)
    atomic_json(run_dir / "protection-ledger.json", auto_ledger(read_text(source)))
    print(run_dir)
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    run_dir, manifest = load_run(args.run_dir)
    snapshot, candidate_path = snapshot_paths(run_dir, manifest)
    source, candidate = read_text(snapshot), read_text(candidate_path)
    payload = {"version": 1, "spans": changed_spans(source, candidate)}
    atomic_json(run_dir / "changed-spans.json", payload)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("".join(difflib.unified_diff(source.splitlines(True), candidate.splitlines(True), fromfile="source", tofile="candidate")), end="")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    run_dir, manifest = load_run(args.run_dir)
    report = build_report(run_dir, manifest)
    atomic_json(run_dir / "check-report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 2


def cmd_apply(args: argparse.Namespace) -> int:
    if args.confirm != "APPLY":
        raise GuardError("应用候选稿必须显式传入 --confirm APPLY")
    run_dir, manifest = load_run(args.run_dir)
    report = build_report(run_dir, manifest)
    atomic_json(run_dir / "check-report.json", report)
    if report["status"] != "pass":
        raise GuardError("保护检查未通过，拒绝应用候选稿")
    _, candidate_path = snapshot_paths(run_dir, manifest)
    source_live = Path(manifest["project_root"]) / manifest["source_path"]
    atomic_text(source_live, read_text(candidate_path))
    manifest.update({"status": "applied", "applied_at": now_iso(), "applied_sha256": sha256(source_live)})
    atomic_json(run_dir / "manifest.json", manifest)
    print(source_live)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init_parser = sub.add_parser("init")
    init_parser.add_argument("source")
    init_parser.add_argument("--project-root", required=True)
    init_parser.add_argument("--scope", choices=("in-place", "bounded", "structural"), default="bounded")
    init_parser.add_argument("--intensity", choices=("minimal", "standard", "aggressive"), default="standard")
    init_parser.add_argument("--issue-density", choices=("light", "concentrated", "structural"), default="light")
    init_parser.add_argument("--run-id")
    init_parser.set_defaults(func=cmd_init)
    diff_parser = sub.add_parser("diff")
    diff_parser.add_argument("run_dir")
    diff_parser.add_argument("--format", choices=("unified", "json"), default="unified")
    diff_parser.set_defaults(func=cmd_diff)
    check_parser = sub.add_parser("check")
    check_parser.add_argument("run_dir")
    check_parser.set_defaults(func=cmd_check)
    apply_parser = sub.add_parser("apply")
    apply_parser.add_argument("run_dir")
    apply_parser.add_argument("--confirm", required=True)
    apply_parser.set_defaults(func=cmd_apply)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except GuardError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
