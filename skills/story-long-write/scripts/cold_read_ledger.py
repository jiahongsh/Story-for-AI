#!/usr/bin/env python3
"""Maintain a sequential cold-read ledger and append-only continuity issue log."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SEVERITIES = {"S1", "S2", "S3", "S4"}


class LedgerError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_bytes(content)
    temp.replace(path)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write(path, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def append_event(path: Path, payload: dict[str, Any]) -> None:
    existing = path.read_bytes() if path.is_file() else b""
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n"
    atomic_write(path, existing + line)


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LedgerError(f"{label}不存在: {path}") from exc
    except json.JSONDecodeError as exc:
        raise LedgerError(f"{label}不是有效 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise LedgerError(f"{label}必须是 JSON object")
    return value


def load_run(raw: str) -> tuple[Path, Path, dict[str, Any]]:
    run = Path(raw).expanduser().resolve()
    ledger_path = run / "ledger.json"
    data = load_json(ledger_path, "冷读账本")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise LedgerError("不支持的冷读账本版本")
    project = Path(str(data.get("project_root", ""))).resolve()
    if not project.is_dir():
        raise LedgerError("账本中的项目目录不存在")
    try:
        run.relative_to(project / "追踪" / "冷读")
    except ValueError as exc:
        raise LedgerError("冷读运行目录不在项目 追踪/冷读 下") from exc
    return project, ledger_path, data


def validate_issue(raw: Any, chapter: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise LedgerError("issues 每项必须是 object")
    identifier = raw.get("id")
    if not isinstance(identifier, str) or not ID_PATTERN.fullmatch(identifier):
        raise LedgerError("issue id 只能包含字母、数字、点、下划线和连字符")
    severity = raw.get("severity")
    if severity not in SEVERITIES:
        raise LedgerError(f"issue {identifier} severity 必须是 S1-S4")
    kind = raw.get("type")
    location = raw.get("location")
    description = raw.get("description")
    if not all(isinstance(value, str) and value.strip() for value in (kind, location, description)):
        raise LedgerError(f"issue {identifier} 缺少 type/location/description")
    return {
        "id": identifier,
        "severity": severity,
        "type": kind.strip(),
        "chapter": chapter,
        "location": location.strip(),
        "description": description.strip(),
        "status": "open",
        "opened_at": utc_now(),
        "resolution": "",
    }


def validate_record(raw: dict[str, Any], expected_chapter: int) -> dict[str, Any]:
    chapter = raw.get("chapter")
    if chapter != expected_chapter:
        raise LedgerError(f"顺序冷读只允许第 {expected_chapter} 章，收到 {chapter}")
    note = raw.get("reader_note", "")
    if not isinstance(note, str):
        raise LedgerError("reader_note 必须是字符串")
    output: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "chapter": chapter, "read_at": utc_now(), "reader_note": note.strip()}
    for field in ("clock", "promises", "knowledge", "props"):
        value = raw.get(field)
        if not isinstance(value, list):
            raise LedgerError(f"{field} 必须是 list；没有变化也要传空列表")
        output[field] = value
    issues = raw.get("issues")
    if not isinstance(issues, list):
        raise LedgerError("issues 必须是 list")
    output["issues"] = [validate_issue(item, chapter) for item in issues]
    return output


def cmd_init(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    if not project.is_dir():
        raise LedgerError(f"项目目录不存在: {project}")
    if args.from_chapter <= 0 or args.to_chapter < args.from_chapter:
        raise LedgerError("冷读章节范围无效")
    run_id = args.id or datetime.now().strftime("R%Y%m%d-%H%M%S")
    if not ID_PATTERN.fullmatch(run_id):
        raise LedgerError("run id 只能包含字母、数字、点、下划线和连字符")
    run = project / "追踪" / "冷读" / run_id
    if run.exists():
        raise LedgerError(f"冷读运行目录已存在: {run}")
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "status": "open",
        "created_at": utc_now(),
        "project_root": str(project),
        "from_chapter": args.from_chapter,
        "to_chapter": args.to_chapter,
        "cursor": args.from_chapter - 1,
        "reader_charter": (args.reader_charter or "像第一次读这本书一样从前往后读；扫描器只作回归围栏，不替代发现。").strip(),
        "records": [],
        "issues": {},
        "closed_at": None,
    }
    atomic_write_json(run / "ledger.json", payload)
    atomic_write(run / "issues.jsonl", b"")
    print(run)
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    _, ledger_path, ledger = load_run(args.run)
    if ledger.get("status") != "open":
        raise LedgerError("已闭环冷读账本不能继续记录")
    expected = int(ledger["cursor"]) + 1
    if expected > int(ledger["to_chapter"]):
        raise LedgerError("目标章节已经全部读完，请执行 close")
    raw = load_json(Path(args.input).expanduser().resolve(), "冷读章节输入")
    record = validate_record(raw, expected)
    current_issues = ledger.get("issues")
    if not isinstance(current_issues, dict):
        raise LedgerError("ledger.issues 无效")
    for issue in record["issues"]:
        if issue["id"] in current_issues:
            raise LedgerError(f"issue id 重复: {issue['id']}")
    run = ledger_path.parent
    record_path = run / "records" / f"第{expected:03d}章.json"
    atomic_write_json(record_path, record)
    for issue in record["issues"]:
        current_issues[issue["id"]] = issue
        append_event(run / "issues.jsonl", {"event": "opened", **issue})
    ledger["cursor"] = expected
    ledger["issues"] = current_issues
    records = ledger.get("records")
    if not isinstance(records, list):
        records = []
    records.append({"chapter": expected, "path": record_path.relative_to(run).as_posix(), "sha256": sha256_file(record_path)})
    ledger["records"] = records
    atomic_write_json(ledger_path, ledger)
    print(record_path)
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    _, ledger_path, ledger = load_run(args.run)
    if ledger.get("status") != "open":
        raise LedgerError("已闭环冷读账本不能修改问题状态")
    issues = ledger.get("issues")
    if not isinstance(issues, dict) or args.issue_id not in issues:
        raise LedgerError(f"issue 不存在: {args.issue_id}")
    issue = issues[args.issue_id]
    if issue.get("status") != "open":
        raise LedgerError(f"issue 已处理: {args.issue_id}")
    resolution = (args.resolution or "").strip()
    if not resolution:
        raise LedgerError("resolve 必须提供 resolution")
    issue["status"] = "resolved"
    issue["resolution"] = resolution
    issue["resolved_at"] = utc_now()
    issues[args.issue_id] = issue
    ledger["issues"] = issues
    append_event(
        ledger_path.parent / "issues.jsonl",
        {"event": "resolved", "id": args.issue_id, "resolved_at": issue["resolved_at"], "resolution": resolution},
    )
    atomic_write_json(ledger_path, ledger)
    print(ledger_path)
    return 0


def validate_ledger(run: Path, ledger: dict[str, Any]) -> dict[str, Any]:
    start = int(ledger["from_chapter"])
    cursor = int(ledger["cursor"])
    records = ledger.get("records")
    if not isinstance(records, list):
        raise LedgerError("ledger.records 无效")
    expected_chapters = list(range(start, cursor + 1))
    actual_chapters = [row.get("chapter") for row in records if isinstance(row, dict)]
    if actual_chapters != expected_chapters:
        raise LedgerError(f"冷读记录不连续: expected={expected_chapters}, actual={actual_chapters}")
    for row in records:
        path = run / str(row.get("path", ""))
        if not path.is_file() or sha256_file(path) != row.get("sha256"):
            raise LedgerError(f"冷读章节记录缺失或被修改: {path}")
    issues = ledger.get("issues")
    if not isinstance(issues, dict):
        raise LedgerError("ledger.issues 无效")
    blocking = sorted(
        identifier
        for identifier, issue in issues.items()
        if isinstance(issue, dict) and issue.get("status") == "open" and issue.get("severity") in {"S1", "S2"}
    )
    return {"status": "valid", "cursor": cursor, "through": ledger["to_chapter"], "blocking_issues": blocking, "open_issue_count": sum(1 for issue in issues.values() if isinstance(issue, dict) and issue.get("status") == "open")}


def cmd_check(args: argparse.Namespace) -> int:
    _, ledger_path, ledger = load_run(args.run)
    result = validate_ledger(ledger_path.parent, ledger)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result["blocking_issues"] else 0


def render_report(ledger: dict[str, Any]) -> str:
    issues = ledger.get("issues", {})
    open_issues = [issue for issue in issues.values() if isinstance(issue, dict) and issue.get("status") == "open"]
    by_severity = {severity: sum(1 for issue in open_issues if issue.get("severity") == severity) for severity in sorted(SEVERITIES)}
    lines = [
        f"# 顺序冷读报告：{ledger['run_id']}",
        "",
        f"- 范围：第 {ledger['from_chapter']}-{ledger['to_chapter']} 章",
        f"- 完成时间：{ledger['closed_at']}",
        f"- 读者约定：{ledger['reader_charter']}",
        f"- 未解决问题：S1={by_severity['S1']}，S2={by_severity['S2']}，S3={by_severity['S3']}，S4={by_severity['S4']}",
        "",
        "## 未解决问题",
        "",
    ]
    if not open_issues:
        lines.append("无。")
    else:
        for issue in sorted(open_issues, key=lambda item: (item.get("severity", ""), item.get("id", ""))):
            lines.append(f"- [{issue['severity']}] {issue['id']}（第{issue['chapter']}章，{issue['location']}）：{issue['description']}")
    lines.extend(["", "## 账本说明", "", "时钟、承诺、知识边界和物件去向保存在逐章 records 中；issues.jsonl 为追加式问题事件日志。", ""])
    return "\n".join(lines)


def cmd_close(args: argparse.Namespace) -> int:
    if args.confirm != "CLOSE":
        raise LedgerError("闭环顺序冷读必须显式传入 --confirm CLOSE")
    _, ledger_path, ledger = load_run(args.run)
    if ledger.get("status") != "open":
        raise LedgerError("冷读账本已经闭环")
    result = validate_ledger(ledger_path.parent, ledger)
    if result["cursor"] != int(ledger["to_chapter"]):
        raise LedgerError(f"尚未顺序读完，当前只到第 {result['cursor']} 章")
    if result["blocking_issues"]:
        raise LedgerError(f"仍有未解决 S1/S2: {', '.join(result['blocking_issues'])}")
    ledger["status"] = "closed"
    ledger["closed_at"] = utc_now()
    atomic_write_json(ledger_path, ledger)
    report = ledger_path.parent / "report.md"
    atomic_write(report, render_report(ledger).encode("utf-8"))
    print(report)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="初始化顺序冷读账本")
    init.add_argument("--project", required=True)
    init.add_argument("--from-chapter", type=int, required=True)
    init.add_argument("--to-chapter", type=int, required=True)
    init.add_argument("--reader-charter")
    init.add_argument("--id")
    init.set_defaults(func=cmd_init)

    record = sub.add_parser("record", help="只记录游标的下一章")
    record.add_argument("--run", required=True)
    record.add_argument("--input", required=True)
    record.set_defaults(func=cmd_record)

    resolve = sub.add_parser("resolve", help="追加问题解决事件")
    resolve.add_argument("--run", required=True)
    resolve.add_argument("--issue-id", required=True)
    resolve.add_argument("--resolution", required=True)
    resolve.set_defaults(func=cmd_resolve)

    check = sub.add_parser("check", help="检查连续读取与阻断问题")
    check.add_argument("--run", required=True)
    check.set_defaults(func=cmd_check)

    close = sub.add_parser("close", help="读完且 S1/S2 清零后闭环")
    close.add_argument("--run", required=True)
    close.add_argument("--confirm", required=True)
    close.set_defaults(func=cmd_close)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except LedgerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
