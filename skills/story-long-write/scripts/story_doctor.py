#!/usr/bin/env python3
"""Diagnose long-form canon, accepted prose, projections, and cold-read gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class DoctorError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DoctorError(f"无法读取 JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DoctorError(f"JSON 顶层必须是 object: {path}")
    return value


def add(items: list[dict[str, str]], code: str, message: str, path: Path | None = None) -> None:
    row = {"code": code, "message": message}
    if path is not None:
        row["path"] = str(path)
    items.append(row)


def run_tracking_check(project: Path, errors: list[dict[str, str]], checks: list[dict[str, Any]]) -> dict[str, Any] | None:
    tool = Path(__file__).resolve().parent / "tracking_commit.py"
    completed = subprocess.run(
        [sys.executable, str(tool), "check", "--project", str(project)],
        text=True,
        capture_output=True,
        check=False,
    )
    checks.append({"name": "tracking_commit", "status": "pass" if completed.returncode == 0 else "fail"})
    if completed.returncode != 0:
        add(errors, "tracking-check-failed", (completed.stderr or completed.stdout).strip()[-4000:])
        return None
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        add(errors, "tracking-check-output-invalid", "tracking_commit.py check 未返回有效 JSON")
        return None
    return result if isinstance(result, dict) else None


def check_writing_method(project: Path, errors: list[dict[str, str]], checks: list[dict[str, Any]]) -> None:
    tool = Path(__file__).resolve().parent / "style_method.py"
    completed = subprocess.run(
        [sys.executable, str(tool), "check", "--project", str(project)],
        text=True,
        capture_output=True,
        check=False,
    )
    details: dict[str, Any] | None = None
    try:
        payload = json.loads(completed.stdout)
        if isinstance(payload, dict):
            details = payload
    except json.JSONDecodeError:
        details = None
    if completed.returncode != 0:
        add(
            errors,
            "writing-method-invalid",
            (completed.stderr or completed.stdout or "写作方法门禁失败").strip()[-4000:],
            project / "设定" / "写作方法.json",
        )
    checks.append(
        {
            "name": "writing_method",
            "status": "pass" if completed.returncode == 0 else "fail",
            "details": details,
        }
    )


def check_candidate_workspaces(project: Path, errors: list[dict[str, str]], checks: list[dict[str, Any]]) -> None:
    root = project / "追踪" / "候选章"
    open_count = 0
    invalid_count = 0
    if root.is_dir():
        for path in sorted(root.glob("第*章/*/manifest.json")):
            try:
                data = load_json(path)
            except DoctorError as exc:
                invalid_count += 1
                add(errors, "candidate-manifest-invalid", str(exc), path)
                continue
            status = data.get("status")
            if status in {"draft", "approved", "promoted"}:
                open_count += 1
                add(errors, "candidate-not-closed", f"候选章仍处于 {status}，不得开始下一章", path.parent)
    checks.append({"name": "chapter_candidates", "status": "pass" if open_count == 0 and invalid_count == 0 else "fail", "open": open_count})


def check_receipts(project: Path, errors: list[dict[str, str]], checks: list[dict[str, Any]]) -> None:
    root = project / "追踪" / "章节提交"
    count = 0
    if root.is_dir():
        for path in sorted(root.glob("第*章.json")):
            count += 1
            try:
                data = load_json(path)
            except DoctorError as exc:
                add(errors, "chapter-receipt-invalid", str(exc), path)
                continue
            if data.get("status") != "committed":
                add(errors, "chapter-receipt-open", "正文已写入但追踪提交尚未闭环", path)
                continue
            target = project / str(data.get("target", ""))
            if not target.is_file():
                add(errors, "accepted-prose-missing", "提交凭证指向的正文不存在", target)
                continue
            current = sha256_file(target)
            if current != data.get("accepted_prose_sha256"):
                add(
                    errors,
                    "accepted-prose-digest-mismatch",
                    "正式正文已在接纳后变化；先走修订事务，再用 chapter_candidate.py sync 更新摘要",
                    target,
                )
    checks.append({"name": "accepted_prose_receipts", "status": "pass" if not any(item["code"].startswith(("chapter-receipt", "accepted-prose")) for item in errors) else "fail", "count": count})


def check_voice_profile(
    project: Path,
    errors: list[dict[str, str]],
    warnings: list[dict[str, str]],
    checks: list[dict[str, Any]],
) -> None:
    tool = Path(__file__).resolve().parent / "voice_profile.py"
    completed = subprocess.run(
        [sys.executable, str(tool), "verify", "--project", str(project)],
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        message = (completed.stderr or completed.stdout or "voice_profile.py verify 未返回有效 JSON").strip()[-4000:]
        add(errors, "voice-profile-invalid", message, project / "追踪" / "文风")
        checks.append({"name": "accepted_voice_profile", "status": "fail"})
        return
    status = result.get("status") if isinstance(result, dict) else None
    if completed.returncode != 0 or status == "stale":
        changes = result.get("changes", []) if isinstance(result, dict) else []
        add(
            errors,
            "voice-profile-stale",
            f"声音画像未绑定当前已接纳正文；先运行 voice_profile.py update。变化：{json.dumps(changes, ensure_ascii=False)}",
            project / "追踪" / "文风" / "accepted-voice-profile.json",
        )
        checks.append({"name": "accepted_voice_profile", "status": "fail", "details": result})
        return
    if status == "not_configured":
        add(
            warnings,
            "voice-profile-not-configured",
            "尚无本书声音画像；不足五章时正常，达到五章后可从接纳回执建立，旧章必须显式批准范围",
            project / "追踪" / "文风",
        )
        checks.append({"name": "accepted_voice_profile", "status": "not_configured"})
    elif status != "fresh":
        add(errors, "voice-profile-status-invalid", f"声音画像返回未知状态: {status}", project / "追踪" / "文风")
        checks.append({"name": "accepted_voice_profile", "status": "fail"})
        return
    else:
        checks.append({"name": "accepted_voice_profile", "status": "pass", "source_count": result.get("source_count")})

    golden_completed = subprocess.run(
        [sys.executable, str(tool), "golden-verify", "--project", str(project)],
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        golden_result = json.loads(golden_completed.stdout)
    except json.JSONDecodeError:
        message = (golden_completed.stderr or golden_completed.stdout or "voice_profile.py golden-verify 未返回有效 JSON").strip()[-4000:]
        add(errors, "golden-voice-profile-invalid", message, project / "追踪" / "文风")
        checks.append({"name": "golden_voice_profile", "status": "fail"})
        return
    golden_status = golden_result.get("status") if isinstance(golden_result, dict) else None
    if golden_completed.returncode != 0 or golden_status == "stale":
        changes = golden_result.get("changes", []) if isinstance(golden_result, dict) else []
        add(
            errors,
            "golden-voice-profile-stale",
            f"黄金声音样本不再绑定当前已接纳正文；重新冷读后再用 golden-build 重建。变化：{json.dumps(changes, ensure_ascii=False)}",
            project / "追踪" / "文风" / "golden-voice-profile.json",
        )
        checks.append({"name": "golden_voice_profile", "status": "fail", "details": golden_result})
        return
    if golden_status not in {"fresh", "not_configured"}:
        add(errors, "golden-voice-profile-status-invalid", f"黄金声音样本返回未知状态: {golden_status}", project / "追踪" / "文风")
        checks.append({"name": "golden_voice_profile", "status": "fail"})
        return
    checks.append({"name": "golden_voice_profile", "status": "pass" if golden_status == "fresh" else "not_configured"})


def read_projection_log(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not path.is_file():
        return events
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DoctorError(f"投影日志第 {number} 行无效: {exc}") from exc
        if not isinstance(row, dict):
            raise DoctorError(f"投影日志第 {number} 行不是 object")
        events.append(row)
    return events


def check_latest_projection(
    project: Path,
    tracking: dict[str, Any] | None,
    errors: list[dict[str, str]],
    warnings: list[dict[str, str]],
    checks: list[dict[str, Any]],
) -> None:
    path = project / "追踪" / "投影日志.jsonl"
    try:
        events = read_projection_log(path)
    except DoctorError as exc:
        add(errors, "projection-log-invalid", str(exc), path)
        checks.append({"name": "latest_projection", "status": "fail"})
        return
    if not events:
        add(warnings, "projection-log-missing", "旧项目尚无章节候选提交投影；从下一章开始建立", path)
        checks.append({"name": "latest_projection", "status": "legacy", "events": 0})
        return
    latest = events[-1]
    state_revision = tracking.get("state_revision") if isinstance(tracking, dict) else None
    event_revision = latest.get("state_revision")
    if isinstance(state_revision, int) and isinstance(event_revision, int) and event_revision > state_revision:
        add(errors, "projection-state-revision-future", "最新投影凭证指向不存在的未来追踪修订", path)
    elif event_revision != state_revision:
        add(warnings, "projection-log-behind", "投影日志早于当前追踪修订；追踪派生一致性仍由 tracking_commit.py check 验证", path)
    else:
        for entry in latest.get("projections", []):
            if not isinstance(entry, dict):
                add(errors, "projection-entry-invalid", "投影条目不是 object", path)
                continue
            target = project / str(entry.get("path", ""))
            if not target.is_file():
                add(errors, "projection-missing", "最新追踪投影缺失", target)
            elif sha256_file(target) != entry.get("sha256"):
                add(errors, "projection-digest-mismatch", "最新追踪投影在提交后变化", target)
    failed = any(item["code"].startswith("projection-") for item in errors)
    checks.append({"name": "latest_projection", "status": "fail" if failed else "pass", "events": len(events)})


def check_revision_gate(project: Path, errors: list[dict[str, str]], checks: list[dict[str, Any]]) -> None:
    manifest = project / "追踪" / "修改影响" / "active.json"
    if not manifest.is_file():
        checks.append({"name": "revision_gate", "status": "not_applicable"})
        return
    stamp = project / "追踪" / "修改影响" / "active.approved.json"
    if not stamp.is_file():
        add(errors, "revision-gate-open", "存在修改影响清单但没有有效审批戳", manifest)
        checks.append({"name": "revision_gate", "status": "fail"})
        return
    tool = Path(__file__).resolve().parent / "revision_guard.py"
    completed = subprocess.run(
        [sys.executable, str(tool), "check", "--project", str(project), "--input", str(manifest), "--stamp", str(stamp)],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        add(errors, "revision-gate-failed", (completed.stderr or completed.stdout).strip()[-4000:], manifest)
    checks.append({"name": "revision_gate", "status": "pass" if completed.returncode == 0 else "fail"})


def check_cold_read(
    project: Path,
    start: int | None,
    through: int | None,
    errors: list[dict[str, str]],
    checks: list[dict[str, Any]],
) -> None:
    if through is None:
        checks.append({"name": "cold_read", "status": "not_required"})
        return
    required_start = 1 if start is None else start
    root = project / "追踪" / "冷读"
    found: Path | None = None
    if root.is_dir():
        for path in sorted(root.glob("*/ledger.json"), reverse=True):
            try:
                data = load_json(path)
            except DoctorError:
                continue
            if (
                data.get("status") == "closed"
                and isinstance(data.get("from_chapter"), int)
                and isinstance(data.get("to_chapter"), int)
                and data["from_chapter"] <= required_start
                and data["to_chapter"] >= through
            ):
                found = path
                break
    if found is None:
        add(errors, "cold-read-required", f"缺少覆盖第 {required_start}-{through} 章的已闭环顺序冷读账本", root)
    checks.append({"name": "cold_read", "status": "pass" if found else "fail", "ledger": str(found) if found else None})


def cmd_check(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    if not project.is_dir():
        raise DoctorError(f"项目目录不存在: {project}")
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    checks: list[dict[str, Any]] = []
    tracking = run_tracking_check(project, errors, checks)
    check_writing_method(project, errors, checks)
    check_candidate_workspaces(project, errors, checks)
    check_receipts(project, errors, checks)
    check_voice_profile(project, errors, warnings, checks)
    check_latest_projection(project, tracking, errors, warnings, checks)
    check_revision_gate(project, errors, checks)
    check_cold_read(project, args.cold_read_from, args.require_cold_read_through, errors, checks)
    payload = {
        "status": "fail" if errors else "pass",
        "project": str(project),
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if errors else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--cold-read-from", type=int)
    parser.add_argument("--require-cold-read-through", type=int)
    parser.set_defaults(func=cmd_check)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except DoctorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
