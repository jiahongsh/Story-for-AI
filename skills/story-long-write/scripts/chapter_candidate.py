#!/usr/bin/env python3
"""Stage, validate, accept, promote, and reconcile one long-form chapter candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
CHAPTER_PATTERN = re.compile(r"^第0*(\d+)章(?:_|\.|$)")
OPEN_STATUSES = {"draft", "approved", "promoted"}


class CandidateError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


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


def atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_bytes(content)
    temp.replace(path)


def atomic_append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    existing = path.read_bytes() if path.is_file() else b""
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n"
    atomic_write_bytes(path, existing + line)


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CandidateError(f"{label}不存在: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CandidateError(f"{label}不是有效 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise CandidateError(f"{label}必须是 JSON object")
    return value


def resolve_inside(project: Path, raw: str, *, must_exist: bool, label: str) -> tuple[Path, str]:
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = project / candidate
    resolved = candidate.resolve()
    try:
        relative = resolved.relative_to(project).as_posix()
    except ValueError as exc:
        raise CandidateError(f"{label}必须位于项目目录内: {raw}") from exc
    if must_exist and not resolved.is_file():
        raise CandidateError(f"{label}不存在: {resolved}")
    return resolved, relative


def tracking_snapshot(project: Path) -> tuple[int, int]:
    state = load_json(project / "追踪" / "_tracking-state.json", "追踪权威状态")
    last = state.get("last_committed_chapter")
    revision = state.get("state_revision")
    if not isinstance(last, int) or last < 0 or not isinstance(revision, int) or revision < 0:
        raise CandidateError("追踪权威状态缺少有效 last_committed_chapter/state_revision")
    return last, revision


def writing_method_snapshot(project: Path) -> dict[str, Any]:
    tool = Path(__file__).resolve().parent / "style_method.py"
    completed = subprocess.run(
        [sys.executable, str(tool), "check", "--project", str(project)],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "写作方法门禁失败").strip()[-4000:]
        raise CandidateError(detail)
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise CandidateError("style_method.py check 未返回有效 JSON") from exc
    if not isinstance(result, dict) or result.get("status") != "ready":
        raise CandidateError("写作方法状态无效")
    return {
        "method_branch": result.get("method_branch"),
        "method_id": result.get("method_id"),
        "implicit_default": bool(result.get("implicit_default")),
    }


def writing_method_files(project: Path) -> list[Path]:
    config_path = project / "设定" / "写作方法.json"
    if not config_path.is_file():
        return []
    config = load_json(config_path, "写作方法配置")
    output = [config_path]
    if config.get("method_branch") == "B-distilled":
        for key in ("compiled_method_path", "compiled_manifest_path", "forward_test_path"):
            raw = config.get(key)
            if isinstance(raw, str) and raw.strip():
                path, _ = resolve_inside(project, raw, must_exist=True, label=f"写作方法 {key}")
                output.append(path)
    return output


def chapter_number(path: Path) -> int | None:
    match = CHAPTER_PATTERN.match(path.name)
    return int(match.group(1)) if match else None


def previous_chapter(project: Path, chapter: int) -> Path | None:
    if chapter <= 1:
        return None
    prose_dir = project / "正文"
    matches = sorted(
        path for path in prose_dir.glob("第*章*.md") if path.is_file() and chapter_number(path) == chapter - 1
    )
    if len(matches) > 1:
        raise CandidateError(f"第{chapter - 1}章存在多个正文文件，先解决章节号冲突")
    return matches[0] if matches else None


def fingerprint(project: Path, paths: list[Path]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in paths:
        resolved = path.resolve()
        relative = resolved.relative_to(project).as_posix()
        if relative in seen:
            continue
        seen.add(relative)
        entries.append({"path": relative, "sha256": sha256_file(resolved), "size": resolved.stat().st_size})
    return entries


def context_digest(entries: list[dict[str, Any]], last: int, revision: int, target: str) -> str:
    payload = {
        "base_files": entries,
        "expected_last_committed_chapter": last,
        "expected_state_revision": revision,
        "target": target,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(encoded)


def iter_manifests(project: Path) -> list[tuple[Path, dict[str, Any]]]:
    output: list[tuple[Path, dict[str, Any]]] = []
    root = project / "追踪" / "候选章"
    if not root.is_dir():
        return output
    for path in sorted(root.glob("第*章/*/manifest.json")):
        try:
            data = load_json(path, "候选章 manifest")
        except CandidateError:
            continue
        output.append((path, data))
    return output


def open_workspaces(project: Path, *, excluding: Path | None = None) -> list[Path]:
    result: list[Path] = []
    for path, data in iter_manifests(project):
        if excluding is not None and path.resolve() == excluding.resolve():
            continue
        if data.get("status") in OPEN_STATUSES:
            result.append(path.parent)
    return result


def load_run(raw: str) -> tuple[Path, Path, dict[str, Any]]:
    run = Path(raw).expanduser().resolve()
    manifest_path = run / "manifest.json"
    data = load_json(manifest_path, "候选章 manifest")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise CandidateError("不支持的候选章 manifest 版本")
    project = Path(str(data.get("project_root", ""))).resolve()
    if not project.is_dir():
        raise CandidateError("manifest 中的项目目录不存在")
    try:
        run.relative_to(project / "追踪" / "候选章")
    except ValueError as exc:
        raise CandidateError("候选运行目录不在项目的 追踪/候选章 内") from exc
    return project, manifest_path, data


def freshness(project: Path, data: dict[str, Any]) -> dict[str, Any]:
    changed: list[dict[str, str]] = []
    last, revision = tracking_snapshot(project)
    if last != data.get("expected_last_committed_chapter"):
        changed.append({"path": "追踪/_tracking-state.json", "reason": "last_committed_chapter_changed"})
    if revision != data.get("expected_state_revision"):
        changed.append({"path": "追踪/_tracking-state.json", "reason": "state_revision_changed"})
    stored_method = data.get("writing_method")
    if isinstance(stored_method, dict):
        current_method = writing_method_snapshot(project)
        if current_method != stored_method:
            changed.append({"path": "设定/写作方法.json", "reason": "writing_method_changed"})
    current_entries: list[dict[str, Any]] = []
    for entry in data.get("base_files", []):
        relative = str(entry.get("path", ""))
        path = project / relative
        if not path.is_file():
            changed.append({"path": relative, "reason": "missing"})
            continue
        current = {"path": relative, "sha256": sha256_file(path), "size": path.stat().st_size}
        current_entries.append(current)
        if current["sha256"] != entry.get("sha256"):
            changed.append({"path": relative, "reason": "content_changed"})
    current_digest = context_digest(current_entries, last, revision, str(data.get("target", "")))
    if current_digest != data.get("context_digest") and not changed:
        changed.append({"path": "manifest.json", "reason": "context_digest_changed"})
    target = project / str(data.get("target", ""))
    if target.exists():
        promoted = data.get("promotion") if isinstance(data.get("promotion"), dict) else {}
        expected_target_sha = promoted.get("target_sha256")
        if data.get("status") != "promoted" or not expected_target_sha or sha256_file(target) != expected_target_sha:
            changed.append({"path": str(data.get("target", "")), "reason": "target_created_or_changed"})
    return {
        "status": "stale" if changed else "fresh",
        "changed": changed,
        "current_last_committed_chapter": last,
        "current_state_revision": revision,
        "current_context_digest": current_digest,
    }


def candidate_outline(project: Path, data: dict[str, Any]) -> Path:
    raw = data.get("outline")
    if not isinstance(raw, str) or not raw.strip():
        for entry in data.get("base_files", []):
            if not isinstance(entry, dict):
                continue
            candidate = entry.get("path")
            if isinstance(candidate, str) and candidate.startswith("大纲/") and "细纲" in Path(candidate).name:
                raw = candidate
                break
    if not isinstance(raw, str) or not raw.strip():
        raise CandidateError("候选章 manifest 缺少可识别的本章细纲")
    outline, _ = resolve_inside(project, raw, must_exist=True, label="本章细纲")
    return outline


def prose_gate_commands(project: Path, candidate: Path, outline: Path, chapter: int) -> list[tuple[str, list[str]]]:
    scripts = Path(__file__).resolve().parent
    return [
        (
            "writing_method",
            [sys.executable, str(scripts / "style_method.py"), "check", "--project", str(project)],
        ),
        ("language", ["node", str(scripts / "language_gate.js"), str(candidate)]),
        ("ai_patterns", ["node", str(scripts / "check-ai-patterns.js"), "--check", "--fail-on=blocking", str(candidate)]),
        (
            "degeneration",
            [
                "node",
                str(scripts / "check-degeneration.js"),
                "--check",
                "--language=zh",
                "--fail-on=blocking",
                str(candidate),
            ],
        ),
        ("prose_metrics", [sys.executable, str(scripts / "prose_metrics.py"), str(candidate)]),
        (
            "outline_copy",
            [
                "node",
                str(scripts / "check-outline-copy.js"),
                "--outline",
                str(outline),
                "--fail-on=blocking",
                str(candidate),
            ],
        ),
        (
            "accepted_voice_profile",
            [
                sys.executable,
                str(scripts / "voice_profile.py"),
                "check",
                "--project",
                str(project),
                "--candidate",
                str(candidate),
            ],
        ),
        (
            "cross_chapter_shape",
            [
                sys.executable,
                str(scripts / "chapter_shape_gate.py"),
                "--project",
                str(project),
                "--candidate",
                str(candidate),
                "--chapter",
                str(chapter),
                "--window",
                "6",
            ],
        ),
    ]


def run_prose_gates(project: Path, candidate: Path, outline: Path, chapter: int) -> list[dict[str, Any]]:
    if not candidate.is_file() or not candidate.read_text(encoding="utf-8").strip():
        raise CandidateError("候选稿为空")
    results: list[dict[str, Any]] = []
    for name, command in prose_gate_commands(project, candidate, outline, chapter):
        try:
            completed = subprocess.run(command, text=True, capture_output=True, check=False)
        except FileNotFoundError as exc:
            raise CandidateError("运行正文门禁需要 node") from exc
        result = {
            "name": name,
            "status": "pass" if completed.returncode == 0 else "fail",
            "returncode": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        }
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, (dict, list)):
            result["payload"] = payload
        results.append(result)
        if completed.returncode != 0:
            raise CandidateError(f"正文门禁未通过: {name}\n{completed.stdout}{completed.stderr}".rstrip())
    return results


def world_engine_enabled(project: Path) -> bool:
    """An absent policy preserves old books; a malformed policy never disables a gate."""
    policy = project / "设定" / "世界运行契约.json"
    if not policy.exists():
        if policy.is_symlink():
            raise CandidateError("世界运行契约链接失效")
        return False
    try:
        data = load_json(policy, "世界运行契约")
    except (OSError, UnicodeError) as exc:
        raise CandidateError(f"世界运行契约无法读取: {exc}") from exc
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise CandidateError("世界运行契约 schema_version 必须为 1")
    if type(data.get("enabled")) is not bool:
        raise CandidateError("世界运行契约 enabled 必须为布尔值")
    return data["enabled"]


def world_gate_tool() -> Path:
    """Only discover the maintained local/global helper, never a policy-supplied script."""
    local = Path(__file__).resolve().parents[2] / "story-world-engine" / "scripts" / "world_gate.py"
    installed = Path.home() / ".codex" / "skills" / "story-world-engine" / "scripts" / "world_gate.py"
    for path in (local, installed):
        if path.is_file():
            return path
    raise CandidateError("世界引擎已启用，但找不到 story-world-engine/scripts/world_gate.py")


def validate_world_packet_binding(
    project: Path, data: dict[str, Any], packet: dict[str, Any], *, phase: str,
    candidate: Path, prewrite_path: Path,
) -> None:
    if packet.get("mode") != "continuation":
        raise CandidateError(f"世界引擎 {phase} 包必须使用 continuation 模式")
    if type(packet.get("chapter")) is not int or packet["chapter"] != data.get("chapter"):
        raise CandidateError(f"世界引擎 {phase} 包章号与候选许可不一致")
    binding = packet.get("binding")
    tracking = binding.get("tracking") if isinstance(binding, dict) else None
    if not isinstance(tracking, dict):
        raise CandidateError(f"世界引擎 {phase} 包缺少追踪基线")
    for key in ("state_revision", "last_committed_chapter"):
        value = tracking.get(key)
        expected = data.get(f"expected_{key}")
        if type(value) is not int or value != expected:
            raise CandidateError(f"世界引擎 {phase} 包的 {key} 与候选许可基线不一致")
    if phase != "postwrite":
        return
    postwrite = packet.get("postwrite")
    candidate_binding = postwrite.get("candidate") if isinstance(postwrite, dict) else None
    if not isinstance(candidate_binding, dict) or not isinstance(candidate_binding.get("path"), str):
        raise CandidateError("世界引擎写后包缺少候选正文绑定")
    bound_candidate, _ = resolve_inside(
        project, candidate_binding["path"], must_exist=True, label="世界引擎候选正文"
    )
    if bound_candidate != candidate.resolve():
        raise CandidateError("世界引擎写后包绑定的是另一份候选正文")
    if candidate_binding.get("sha256") != sha256_file(candidate):
        raise CandidateError("世界引擎写后包的候选正文摘要已失效")
    prewrite_binding = postwrite.get("prewrite_packet")
    if not isinstance(prewrite_binding, dict) or not isinstance(prewrite_binding.get("path"), str):
        raise CandidateError("世界引擎写后包缺少写前审查绑定")
    bound_prewrite, _ = resolve_inside(
        project, prewrite_binding["path"], must_exist=True, label="世界引擎写前审查"
    )
    if bound_prewrite != prewrite_path.resolve():
        raise CandidateError("世界引擎写后包绑定的是另一份写前审查")
    if prewrite_binding.get("sha256") != sha256_file(prewrite_path):
        raise CandidateError("世界引擎写后包的写前审查摘要已失效")


def run_world_gates(project: Path, data: dict[str, Any], candidate: Path) -> list[dict[str, Any]]:
    if not world_engine_enabled(project):
        return []
    helper = world_gate_tool()
    packet_dir = candidate.parent / "世界引擎"
    prewrite_path = packet_dir / "写前行动审查.json"
    if prewrite_path.is_file():
        prewrite_sha = sha256_file(prewrite_path)
        base_files = data.get("base_files")
        if not isinstance(base_files, list) or not any(
            isinstance(entry, dict) and entry.get("sha256") == prewrite_sha for entry in base_files
        ):
            raise CandidateError("世界引擎冻结写前包未绑定候选基础指纹；计划改变必须重新创建候选许可")
    results: list[dict[str, Any]] = []
    for phase, name in (("prewrite", "写前行动审查.json"), ("postwrite", "写后行动复核.json")):
        packet_path = packet_dir / name
        try:
            packet = load_json(packet_path, f"世界引擎 {phase} 审查包")
        except (OSError, UnicodeError) as exc:
            raise CandidateError(f"世界引擎 {phase} 审查包无法读取: {exc}") from exc
        validate_world_packet_binding(
            project, data, packet, phase=phase, candidate=candidate, prewrite_path=prewrite_path
        )
        command = [
            sys.executable, str(helper), "check", "--project", str(project),
            "--packet", str(packet_path), "--phase", phase,
            "--tracking-tool", str(Path(__file__).resolve().parent / "tracking_commit.py"),
        ]
        try:
            completed = subprocess.run(command, text=True, capture_output=True, check=False)
        except OSError as exc:
            raise CandidateError(f"世界引擎 {phase} 检查工具无法运行: {exc}") from exc
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = None
        if (
            completed.returncode != 0
            or not isinstance(payload, dict)
            or payload.get("status") != "STRUCTURAL_CHECK_PASS"
        ):
            detail = (completed.stderr or completed.stdout or "检查工具未返回有效通过结果").strip()[-4000:]
            raise CandidateError(f"世界引擎 {phase} 门禁未通过: {detail}")
        results.append({
            "name": f"world_engine_{phase}", "status": "pass", "returncode": 0, "payload": payload,
        })
    return results


def validate_run(project: Path, data: dict[str, Any], *, run_gates: bool) -> dict[str, Any]:
    result = freshness(project, data)
    if result["status"] != "fresh":
        details = ", ".join(f"{item['path']}:{item['reason']}" for item in result["changed"])
        raise CandidateError(f"候选稿上下文已过期: {details}")
    candidate = project / str(data.get("candidate", ""))
    if not candidate.is_file():
        raise CandidateError(f"候选稿不存在: {candidate}")
    expected_chapter = data.get("chapter")
    if not isinstance(expected_chapter, int) or expected_chapter <= 0:
        raise CandidateError("manifest 章号无效")
    target = project / str(data.get("target", ""))
    if chapter_number(target) != expected_chapter:
        raise CandidateError("目标文件名章号与许可章号不一致")
    candidate_sha = sha256_file(candidate)
    outline = candidate_outline(project, data)
    gates = run_prose_gates(project, candidate, outline, expected_chapter) if run_gates else []
    gates.extend(run_world_gates(project, data, candidate))
    return {**result, "candidate_sha256": candidate_sha, "gates": gates}


def cmd_init(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    if not project.is_dir():
        raise CandidateError(f"项目目录不存在: {project}")
    if args.chapter <= 0:
        raise CandidateError("chapter 必须大于 0")
    last, revision = tracking_snapshot(project)
    if args.chapter != last + 1:
        raise CandidateError(f"精确章节许可只允许第 {last + 1} 章，收到第 {args.chapter} 章")
    existing = open_workspaces(project)
    if existing:
        raise CandidateError(f"已有未闭环候选章: {existing[0]}")
    outline, outline_relative = resolve_inside(project, args.outline, must_exist=True, label="本章细纲")
    target, target_relative = resolve_inside(project, args.target, must_exist=False, label="正文目标")
    if not target_relative.startswith("正文/") or target.suffix.lower() != ".md":
        raise CandidateError("正文目标必须是项目 正文/ 下的 Markdown 文件")
    if target.exists():
        raise CandidateError("正文目标已存在；修改旧章必须走 revision-governor/revision_guard")
    if chapter_number(target) != args.chapter:
        raise CandidateError("正文目标文件名章号与 --chapter 不一致")
    if args.approval_mode == "auto" and not (args.authorization_note or "").strip():
        raise CandidateError("自动定稿模式必须记录用户的明确授权说明")
    method_snapshot = writing_method_snapshot(project)
    run_id = args.id or datetime.now().strftime("C%Y%m%d-%H%M%S")
    if not ID_PATTERN.fullmatch(run_id):
        raise CandidateError("candidate id 只能包含字母、数字、点、下划线和连字符")
    run = project / "追踪" / "候选章" / f"第{args.chapter:03d}章" / run_id
    if run.exists():
        raise CandidateError(f"候选运行目录已存在: {run}")
    base_paths = [outline]
    context = project / "追踪" / "上下文.md"
    if context.is_file():
        base_paths.append(context)
    previous = previous_chapter(project, args.chapter)
    if args.chapter > 1 and previous is None:
        raise CandidateError(f"第{args.chapter - 1}章正文缺失，拒绝创建下一章候选")
    if previous is not None:
        base_paths.append(previous)
    for raw in args.base or []:
        path, _ = resolve_inside(project, raw, must_exist=True, label="基础文件")
        base_paths.append(path)
    base_paths.extend(writing_method_files(project))
    entries = fingerprint(project, base_paths)
    candidate_relative = (run / "candidate.md").relative_to(project).as_posix()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": run_id,
        "status": "draft",
        "created_at": utc_now(),
        "project_root": str(project),
        "chapter": args.chapter,
        "target": target_relative,
        "candidate": candidate_relative,
        "outline": outline_relative,
        "approval_mode": args.approval_mode,
        "authorization_note": (args.authorization_note or "").strip(),
        "expected_last_committed_chapter": last,
        "expected_state_revision": revision,
        "writing_method": method_snapshot,
        "base_files": entries,
        "context_digest": context_digest(entries, last, revision, target_relative),
        "validation": None,
        "approval": None,
        "promotion": None,
    }
    run.mkdir(parents=True)
    atomic_write_json(run / "manifest.json", payload)
    atomic_write_bytes(run / "candidate.md", b"")
    print(run)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    project, _, data = load_run(args.run)
    result = validate_run(project, data, run_gates=not args.freshness_only)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    if args.confirm != "ACCEPT":
        raise CandidateError("接纳候选稿必须显式传入 --confirm ACCEPT")
    project, manifest_path, data = load_run(args.run)
    if data.get("status") != "draft":
        raise CandidateError(f"只有 draft 候选可以接纳，当前状态: {data.get('status')}")
    note = (args.approval_note or data.get("authorization_note") or "").strip()
    if not note:
        raise CandidateError("必须记录用户的明确接纳说明或预先自动定稿授权")
    validation = validate_run(project, data, run_gates=True)
    data["status"] = "approved"
    data["validation"] = {**validation, "validated_at": utc_now()}
    data["approval"] = {
        "approved_at": utc_now(),
        "mode": data.get("approval_mode"),
        "note": note,
        "candidate_sha256": validation["candidate_sha256"],
    }
    atomic_write_json(manifest_path, data)
    print(manifest_path)
    return 0


def receipt_path(project: Path, chapter: int) -> Path:
    return project / "追踪" / "章节提交" / f"第{chapter:03d}章.json"


def projection_snapshot(project: Path, chapter: int) -> list[dict[str, Any]]:
    tracking = project / "追踪"
    paths = [
        tracking / "上下文.md",
        tracking / "伏笔.md",
        tracking / "长期事实.md",
        tracking / "关系清单.md",
        tracking / "时间线" / "作者真相.md",
        tracking / "时间线" / "读者已知.md",
        tracking / "逐章记录" / f"第{chapter:03d}章.md",
    ]
    paths.extend(sorted((tracking / "角色状态").glob("*.md")) if (tracking / "角色状态").is_dir() else [])
    paths.extend(sorted((tracking / "事实档案").glob("*.md")) if (tracking / "事实档案").is_dir() else [])
    entries: list[dict[str, Any]] = []
    for path in paths:
        if path.is_file():
            entries.append(
                {
                    "path": path.relative_to(project).as_posix(),
                    "sha256": sha256_file(path),
                    "size": path.stat().st_size,
                }
            )
    return entries


def append_projection_event(
    project: Path,
    *,
    event: str,
    chapter: int,
    state_revision: int,
    prose_sha256: str,
    receipt: Path,
) -> None:
    atomic_append_jsonl(
        project / "追踪" / "投影日志.jsonl",
        {
            "schema_version": SCHEMA_VERSION,
            "event": event,
            "recorded_at": utc_now(),
            "chapter": chapter,
            "state_revision": state_revision,
            "accepted_prose_sha256": prose_sha256,
            "receipt": receipt.relative_to(project).as_posix(),
            "projections": projection_snapshot(project, chapter),
        },
    )


def cmd_promote(args: argparse.Namespace) -> int:
    if args.confirm != "PROMOTE":
        raise CandidateError("写入正式正文必须显式传入 --confirm PROMOTE")
    project, manifest_path, data = load_run(args.run)
    if data.get("status") != "approved":
        raise CandidateError(f"只有 approved 候选可以写入正式正文，当前状态: {data.get('status')}")
    validation = validate_run(project, data, run_gates=True)
    approved_sha = (data.get("approval") or {}).get("candidate_sha256")
    if validation["candidate_sha256"] != approved_sha:
        raise CandidateError("候选稿在接纳后被修改，必须回到 draft 重新审阅")
    candidate = project / data["candidate"]
    target = project / data["target"]
    receipt = receipt_path(project, int(data["chapter"]))
    if receipt.exists():
        raise CandidateError(f"章节提交凭证已存在: {receipt}")
    content = candidate.read_bytes()
    atomic_write_bytes(target, content)
    target_sha = sha256_bytes(content)
    promoted_at = utc_now()
    receipt_payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "awaiting_tracking",
        "chapter": data["chapter"],
        "target": data["target"],
        "accepted_prose_sha256": target_sha,
        "candidate_id": data["candidate_id"],
        "candidate_manifest": manifest_path.relative_to(project).as_posix(),
        "context_digest": data["context_digest"],
        "state_revision_before": data["expected_state_revision"],
        "state_revision_after": None,
        "accepted_at": promoted_at,
        "approval_mode": data["approval_mode"],
        "approval_note": data["approval"]["note"],
        "sync_history": [],
    }
    atomic_write_json(receipt, receipt_payload)
    data["status"] = "promoted"
    data["promotion"] = {"promoted_at": promoted_at, "target_sha256": target_sha, "receipt": receipt.relative_to(project).as_posix()}
    atomic_write_json(manifest_path, data)
    print(target)
    return 0


def cmd_close(args: argparse.Namespace) -> int:
    project, manifest_path, data = load_run(args.run)
    if data.get("status") != "promoted":
        raise CandidateError(f"只有 promoted 候选可以闭环，当前状态: {data.get('status')}")
    chapter = int(data["chapter"])
    receipt = receipt_path(project, chapter)
    receipt_data = load_json(receipt, "章节提交凭证")
    last, revision = tracking_snapshot(project)
    if last != chapter:
        raise CandidateError(f"追踪尚未精确提交第 {chapter} 章，当前 last_committed_chapter={last}")
    if revision <= int(data["expected_state_revision"]):
        raise CandidateError("追踪 state_revision 未推进")
    target = project / data["target"]
    target_sha = sha256_file(target)
    if target_sha != receipt_data.get("accepted_prose_sha256"):
        raise CandidateError("正式正文与接纳摘要不一致")
    closed_at = utc_now()
    receipt_data["status"] = "committed"
    receipt_data["state_revision_after"] = revision
    receipt_data["closed_at"] = closed_at
    atomic_write_json(receipt, receipt_data)
    data["status"] = "committed"
    data["closed_at"] = closed_at
    data["state_revision_after"] = revision
    atomic_write_json(manifest_path, data)
    append_projection_event(
        project,
        event="chapter_commit",
        chapter=chapter,
        state_revision=revision,
        prose_sha256=target_sha,
        receipt=receipt,
    )
    print(receipt)
    return 0


def cmd_abandon(args: argparse.Namespace) -> int:
    if args.confirm != "ABANDON":
        raise CandidateError("放弃候选稿必须显式传入 --confirm ABANDON")
    _, manifest_path, data = load_run(args.run)
    if data.get("status") not in {"draft", "approved"}:
        raise CandidateError("只有尚未写入正式正文的候选可以放弃")
    data["status"] = "abandoned"
    data["abandoned_at"] = utc_now()
    data["abandon_reason"] = (args.reason or "").strip()
    atomic_write_json(manifest_path, data)
    print(manifest_path)
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    if args.confirm != "SYNC":
        raise CandidateError("同步合法修订后的正文摘要必须显式传入 --confirm SYNC")
    project = Path(args.project).expanduser().resolve()
    if not (args.reason or "").strip():
        raise CandidateError("sync 必须记录修订原因")
    chapter = args.chapter
    receipt = receipt_path(project, chapter)
    data = load_json(receipt, "章节提交凭证")
    if data.get("status") != "committed":
        raise CandidateError("只能同步已闭环章节")
    revision_tool = Path(__file__).resolve().parent / "revision_guard.py"
    command = [
        sys.executable,
        str(revision_tool),
        "check",
        "--project",
        str(project),
        "--input",
        str(Path(args.revision_manifest).expanduser().resolve()),
        "--stamp",
        str(Path(args.revision_stamp).expanduser().resolve()),
    ]
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise CandidateError(f"修订门禁未通过，拒绝同步摘要\n{completed.stdout}{completed.stderr}".rstrip())
    target = project / str(data.get("target", ""))
    if not target.is_file() or chapter_number(target) != chapter:
        raise CandidateError("章节提交凭证指向的正文不存在或章号不匹配")
    last, revision = tracking_snapshot(project)
    if last < chapter:
        raise CandidateError("追踪状态落后于待同步章节")
    old_sha = data.get("accepted_prose_sha256")
    new_sha = sha256_file(target)
    history = data.get("sync_history")
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "synced_at": utc_now(),
            "reason": args.reason.strip(),
            "old_sha256": old_sha,
            "new_sha256": new_sha,
            "state_revision": revision,
            "revision_manifest": Path(args.revision_manifest).expanduser().resolve().relative_to(project).as_posix(),
        }
    )
    data["accepted_prose_sha256"] = new_sha
    data["state_revision_after"] = revision
    data["sync_history"] = history
    atomic_write_json(receipt, data)
    append_projection_event(
        project,
        event="revision_sync",
        chapter=chapter,
        state_revision=revision,
        prose_sha256=new_sha,
        receipt=receipt,
    )
    print(receipt)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="创建只绑定下一章的候选工作区")
    init.add_argument("--project", required=True)
    init.add_argument("--chapter", type=int, required=True)
    init.add_argument("--outline", required=True)
    init.add_argument("--target", required=True)
    init.add_argument("--base", action="append")
    init.add_argument("--approval-mode", choices=("review", "auto"), default="review")
    init.add_argument("--authorization-note")
    init.add_argument("--id")
    init.set_defaults(func=cmd_init)

    check = sub.add_parser("check", help="检查陈旧状态和中文/AI味/退化门禁")
    check.add_argument("--run", required=True)
    check.add_argument("--freshness-only", action="store_true")
    check.set_defaults(func=cmd_check)

    approve = sub.add_parser("approve", help="记录用户接纳并锁定候选摘要")
    approve.add_argument("--run", required=True)
    approve.add_argument("--confirm", required=True)
    approve.add_argument("--approval-note")
    approve.set_defaults(func=cmd_approve)

    promote = sub.add_parser("promote", help="把已接纳候选原子写入正式正文")
    promote.add_argument("--run", required=True)
    promote.add_argument("--confirm", required=True)
    promote.set_defaults(func=cmd_promote)

    close = sub.add_parser("close", help="追踪提交后闭环本章提交凭证")
    close.add_argument("--run", required=True)
    close.set_defaults(func=cmd_close)

    abandon = sub.add_parser("abandon", help="放弃尚未写入正式正文的候选")
    abandon.add_argument("--run", required=True)
    abandon.add_argument("--confirm", required=True)
    abandon.add_argument("--reason")
    abandon.set_defaults(func=cmd_abandon)

    sync = sub.add_parser("sync", help="仅在修订事务闭环后同步正文摘要")
    sync.add_argument("--project", required=True)
    sync.add_argument("--chapter", type=int, required=True)
    sync.add_argument("--revision-manifest", required=True)
    sync.add_argument("--revision-stamp", required=True)
    sync.add_argument("--reason", required=True)
    sync.add_argument("--confirm", required=True)
    sync.set_defaults(func=cmd_sync)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except CandidateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
