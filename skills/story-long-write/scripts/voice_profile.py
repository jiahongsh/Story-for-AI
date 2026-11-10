#!/usr/bin/env python3
"""Build and verify a book-local voice profile from explicitly accepted prose."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1
MIN_CHAPTERS = 5
MIN_GOLDEN_CHAPTERS = 5
PROFILE_RELATIVE = Path("追踪/文风/accepted-voice-profile.json")
PROFILE_SUMMARY_RELATIVE = Path("追踪/文风/accepted-voice-profile.md")
GOLDEN_PROFILE_RELATIVE = Path("追踪/文风/golden-voice-profile.json")
GOLDEN_SUMMARY_RELATIVE = Path("追踪/文风/golden-voice-profile.md")
CHAPTER_PATTERN = re.compile(r"^第0*(\d+)章(?:_|\.|\s|$)")
TITLE_PATTERN = re.compile(r"^\s*#{1,6}\s*")
SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?])")
CLAUSE_SPLIT = re.compile(r"[，,；;：:。！？!?]+")
CHINESE_PATTERN = re.compile(r"[\u3400-\u9fff]")
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
METRIC_LABELS = {
    "paragraph_mean_chars": "段落平均长度",
    "paragraph_median_chars": "段落长度中位数",
    "sentence_mean_chars": "句子平均长度",
    "sentence_median_chars": "句子长度中位数",
    "clause_mean_chars": "分句平均长度",
    "short_sentence_rate_pct": "短句占比",
    "long_sentence_rate_pct": "长句占比",
    "dialogue_paragraph_rate_pct": "对白段占比",
    "comma_per_1k": "逗号密度",
    "question_per_1k": "问号密度",
    "exclamation_per_1k": "叹号密度",
    "simile_marker_per_1k": "明示比喻词密度",
    "explanation_marker_per_1k": "解释性连接词密度",
    "body_reaction_marker_per_1k": "模板化生理反应密度",
    "transition_marker_per_1k": "顺序转场词密度",
    "contrast_template_per_1k": "不是…而是句式密度",
    "internal_repeat_rate_pct": "章内原句重复占比",
}
MARKERS = {
    "simile_marker_per_1k": re.compile(r"像是|像一|仿佛|好像|如同|宛如"),
    "explanation_marker_per_1k": re.compile(r"这意味着|也就是说|换句话说|他意识到|她意识到|他明白|她明白"),
    "body_reaction_marker_per_1k": re.compile(r"心口一沉|眼皮一跳|头皮发紧|胃里翻涌|瞳孔微缩|后背发凉|呼吸一滞"),
    "transition_marker_per_1k": re.compile(r"随后|然后|与此同时|片刻后|下一刻|紧接着"),
    "contrast_template_per_1k": re.compile(r"不是[^。！？!?]{0,36}而是"),
}


class VoiceProfileError(RuntimeError):
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


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise VoiceProfileError(f"{label}不存在: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise VoiceProfileError(f"{label}不是有效 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise VoiceProfileError(f"{label}顶层必须是 object")
    return value


def project_root(raw: str) -> Path:
    project = Path(raw).expanduser().resolve()
    if not project.is_dir():
        raise VoiceProfileError(f"项目目录不存在: {project}")
    return project


def resolve_inside(project: Path, raw: str, *, label: str) -> tuple[Path, str]:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = project / path
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(project).as_posix()
    except ValueError as exc:
        raise VoiceProfileError(f"{label}必须位于项目目录内: {raw}") from exc
    if not resolved.is_file():
        raise VoiceProfileError(f"{label}不存在: {resolved}")
    return resolved, relative


def chapter_number(path: Path) -> int | None:
    match = CHAPTER_PATTERN.match(path.name)
    return int(match.group(1)) if match else None


def normalized_lines(text: str) -> list[str]:
    lines: list[str] = []
    title_skipped = False
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()
        if not line:
            continue
        if not title_skipped and (TITLE_PATTERN.match(line) or CHAPTER_PATTERN.match(TITLE_PATTERN.sub("", line))):
            title_skipped = True
            continue
        if line.startswith("<!--") and line.endswith("-->"):
            continue
        lines.append(line)
    return lines


def chinese_count(text: str) -> int:
    return len(CHINESE_PATTERN.findall(text))


def split_sentences(lines: Iterable[str]) -> list[str]:
    sentences: list[str] = []
    for line in lines:
        for piece in SENTENCE_SPLIT.split(line):
            normalized = re.sub(r"\s+", "", piece).strip("“”‘’「」『』")
            if chinese_count(normalized) > 0:
                sentences.append(normalized)
    return sentences


def normalized_sentence(sentence: str) -> str:
    return re.sub(r"[^\u3400-\u9fff0-9]", "", sentence)


def percentile_median(values: list[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def rounded(value: float) -> float:
    return round(float(value), 4)


def prose_metrics(path: Path) -> tuple[dict[str, float], list[str], int]:
    text = path.read_text(encoding="utf-8")
    paragraphs = normalized_lines(text)
    sentences = split_sentences(paragraphs)
    paragraph_lengths = [chinese_count(item) for item in paragraphs if chinese_count(item) > 0]
    sentence_lengths = [chinese_count(item) for item in sentences if chinese_count(item) > 0]
    clauses = [
        piece
        for paragraph in paragraphs
        for piece in CLAUSE_SPLIT.split(paragraph)
        if chinese_count(piece) > 0
    ]
    clause_lengths = [chinese_count(item) for item in clauses]
    character_count = max(1, chinese_count("".join(paragraphs)))
    sentence_total = max(1, len(sentence_lengths))
    paragraph_total = max(1, len(paragraph_lengths))
    normalized_sentences = [normalized_sentence(item) for item in sentences]
    normalized_sentences = [item for item in normalized_sentences if len(item) >= 4]
    sentence_counts = Counter(normalized_sentences)
    repeated_occurrences = sum(count for count in sentence_counts.values() if count >= 2)
    metrics: dict[str, float] = {
        "paragraph_mean_chars": rounded(statistics.fmean(paragraph_lengths) if paragraph_lengths else 0),
        "paragraph_median_chars": rounded(percentile_median([float(item) for item in paragraph_lengths])),
        "sentence_mean_chars": rounded(statistics.fmean(sentence_lengths) if sentence_lengths else 0),
        "sentence_median_chars": rounded(percentile_median([float(item) for item in sentence_lengths])),
        "clause_mean_chars": rounded(statistics.fmean(clause_lengths) if clause_lengths else 0),
        "short_sentence_rate_pct": rounded(sum(1 for item in sentence_lengths if item <= 8) * 100 / sentence_total),
        "long_sentence_rate_pct": rounded(sum(1 for item in sentence_lengths if item >= 35) * 100 / sentence_total),
        "dialogue_paragraph_rate_pct": rounded(
            sum(1 for item in paragraphs if item.lstrip().startswith(("“", "「", "『", "\""))) * 100 / paragraph_total
        ),
        "comma_per_1k": rounded((text.count("，") + text.count(",")) * 1000 / character_count),
        "question_per_1k": rounded((text.count("？") + text.count("?")) * 1000 / character_count),
        "exclamation_per_1k": rounded((text.count("！") + text.count("!")) * 1000 / character_count),
        "internal_repeat_rate_pct": rounded(repeated_occurrences * 100 / sentence_total),
    }
    compact = "".join(paragraphs)
    for key, pattern in MARKERS.items():
        metrics[key] = rounded(len(pattern.findall(compact)) * 1000 / character_count)
    return metrics, sentences, character_count


def source_digest(sources: list[dict[str, Any]]) -> str:
    compact = [
        {
            "chapter": item["chapter"],
            "path": item["path"],
            "sha256": item["sha256"],
            "provenance": item["provenance"],
            "receipt": item.get("receipt"),
        }
        for item in sources
    ]
    encoded = json.dumps(compact, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(encoded)


def prose_by_chapter(project: Path) -> dict[int, Path]:
    root = project / "正文"
    matches: dict[int, list[Path]] = {}
    if root.is_dir():
        for path in sorted(root.glob("第*章*.md")):
            number = chapter_number(path)
            if number is not None:
                matches.setdefault(number, []).append(path)
    duplicates = {number: paths for number, paths in matches.items() if len(paths) > 1}
    if duplicates:
        number = sorted(duplicates)[0]
        raise VoiceProfileError(f"第 {number} 章存在多个正文文件，无法建立唯一声音样本")
    return {number: paths[0] for number, paths in matches.items()}


def committed_receipts(project: Path) -> dict[int, dict[str, Any]]:
    root = project / "追踪" / "章节提交"
    output: dict[int, dict[str, Any]] = {}
    if not root.is_dir():
        return output
    for receipt_path in sorted(root.glob("第*章.json")):
        receipt = load_json(receipt_path, "章节接纳回执")
        if receipt.get("status") != "committed":
            continue
        chapter = receipt.get("chapter")
        if not isinstance(chapter, int) or chapter <= 0:
            raise VoiceProfileError(f"章节接纳回执缺少有效章号: {receipt_path}")
        if chapter in output:
            raise VoiceProfileError(f"第 {chapter} 章存在重复接纳回执")
        target, relative = resolve_inside(project, str(receipt.get("target", "")), label="接纳正文")
        if not relative.startswith("正文/"):
            raise VoiceProfileError(f"接纳回执目标不在正文目录: {receipt_path}")
        expected = receipt.get("accepted_prose_sha256")
        actual = sha256_file(target)
        if not isinstance(expected, str) or actual != expected:
            raise VoiceProfileError(f"第 {chapter} 章正文与接纳回执摘要不一致")
        output[chapter] = {
            "chapter": chapter,
            "path": relative,
            "sha256": actual,
            "provenance": "committed_receipt",
            "receipt": receipt_path.relative_to(project).as_posix(),
        }
    return output


def collect_sources(project: Path, legacy_approved_through: int | None) -> list[dict[str, Any]]:
    sources = committed_receipts(project)
    if legacy_approved_through is not None:
        if legacy_approved_through <= 0:
            raise VoiceProfileError("legacy-approved-through 必须大于 0")
        prose = prose_by_chapter(project)
        for chapter in range(1, legacy_approved_through + 1):
            path = prose.get(chapter)
            if path is None:
                raise VoiceProfileError(f"旧章批准范围缺少第 {chapter} 章正文")
            if chapter in sources:
                continue
            relative = path.relative_to(project).as_posix()
            sources[chapter] = {
                "chapter": chapter,
                "path": relative,
                "sha256": sha256_file(path),
                "provenance": "explicit_legacy_approval",
                "receipt": None,
            }
    return [sources[number] for number in sorted(sources)]


def aggregate(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    output: dict[str, dict[str, float]] = {}
    for key in METRIC_LABELS:
        values = [float(row["metrics"][key]) for row in rows]
        output[key] = {
            "min": rounded(min(values)),
            "max": rounded(max(values)),
            "median": rounded(statistics.median(values)),
            "mean": rounded(statistics.fmean(values)),
        }
    return output


def source_core(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "chapter": item.get("chapter"),
        "path": item.get("path"),
        "sha256": item.get("sha256"),
        "provenance": item.get("provenance"),
        "receipt": item.get("receipt"),
    }


def parse_chapter_selection(raw: str) -> list[int]:
    values: list[int] = []
    for token in re.split(r"[,，\s]+", raw.strip()):
        if not token:
            continue
        if not token.isdigit() or int(token) <= 0:
            raise VoiceProfileError(f"黄金样本章号无效: {token}")
        values.append(int(token))
    chapters = sorted(set(values))
    if len(chapters) < MIN_GOLDEN_CHAPTERS:
        raise VoiceProfileError(
            f"黄金样本只有 {len(chapters)} 章，至少需要 {MIN_GOLDEN_CHAPTERS} 章；建议精选 8—12 章"
        )
    return chapters


def build_payload(
    project: Path,
    sources: list[dict[str, Any]],
    *,
    legacy_approved_through: int | None,
    min_chapters: int,
) -> dict[str, Any]:
    if min_chapters < MIN_CHAPTERS:
        raise VoiceProfileError(f"minimum_chapters 不得低于 {MIN_CHAPTERS}，不能用少量样本制造伪精确画像")
    if len(sources) < min_chapters:
        raise VoiceProfileError(
            f"已接纳样本只有 {len(sources)} 章，至少需要 {min_chapters} 章；不足时继续使用通用去 AI 味门，不建立伪精确画像"
        )
    rows: list[dict[str, Any]] = []
    accepted_sentence_hashes: Counter[str] = Counter()
    for source in sources:
        path = project / source["path"]
        metrics, sentences, character_count = prose_metrics(path)
        for sentence in sentences:
            normalized = normalized_sentence(sentence)
            if len(normalized) >= 12:
                accepted_sentence_hashes[sha256_bytes(normalized.encode("utf-8"))] += 1
        rows.append({**source, "character_count": character_count, "metrics": metrics})
    baseline_count = min(5, len(rows))
    recent_count = min(5, len(rows))
    digest = source_digest(sources)
    return {
        "schema_version": SCHEMA_VERSION,
        "profile_kind": "accepted_prose_voice",
        "status": "derived",
        "built_at": utc_now(),
        "project_root": str(project),
        "source_digest": digest,
        "source_count": len(rows),
        "chapter_range": [rows[0]["chapter"], rows[-1]["chapter"]],
        "policy": {
            "severity": "advisory",
            "comparison": "bidirectional_outside_both_early_and_recent_ranges",
            "minimum_chapters": min_chapters,
            "early_window": baseline_count,
            "recent_window": recent_count,
            "legacy_approved_through": legacy_approved_through,
            "not_a_quality_score": True,
        },
        "sources": rows,
        "baselines": {
            "full": aggregate(rows),
            "early": aggregate(rows[:baseline_count]),
            "recent": aggregate(rows[-recent_count:]),
        },
        "accepted_sentence_hashes": dict(sorted(accepted_sentence_hashes.items())),
    }


def markdown_summary(profile: dict[str, Any]) -> str:
    chapter_range = profile["chapter_range"]
    policy = profile["policy"]
    lines = [
        "# 已接纳正文声音画像",
        "",
        "> 本文件由 `voice_profile.py` 从正式接纳正文派生，不得手改。它只提示偏离，不是质量分，也不规定所有作品都该写成同一种比例。",
        "",
        f"- 样本：{profile['source_count']} 章（第 {chapter_range[0]}—{chapter_range[1]} 章）",
        f"- 来源摘要：`{profile['source_digest']}`",
        f"- 早期窗口：{policy['early_window']} 章",
        f"- 近期窗口：{policy['recent_window']} 章",
        f"- 旧章显式批准到：{policy.get('legacy_approved_through') or '无'}",
        "- 处置：只生成双向 advisory；偏高、偏低都可能是有意的，必须回到场景功能判断",
        "",
        "| 观察项 | 全书中位数 | 早期范围 | 近期范围 |",
        "|---|---:|---:|---:|",
    ]
    for key, label in METRIC_LABELS.items():
        full = profile["baselines"]["full"][key]
        early = profile["baselines"]["early"][key]
        recent = profile["baselines"]["recent"][key]
        lines.append(
            f"| {label} | {full['median']:.4g} | {early['min']:.4g}—{early['max']:.4g} | {recent['min']:.4g}—{recent['max']:.4g} |"
        )
    lines.extend(
        [
            "",
            "## 使用边界",
            "",
            "- 画像只能由已闭环接纳回执，或作者显式批准的旧章范围生成。",
            "- 候选章在接纳前对照画像；接纳后更新画像，不能先把候选吸收进基线再检查。",
            "- 统计漂移只用于定位复核点；不得为了回到均值机械增删短句、对白或修辞。",
            "- 角色声线、幽默感、叙述距离和故意变奏仍需人工/Agent 语义冷读。",
            "",
        ]
    )
    return "\n".join(lines)


def write_profile(project: Path, profile: dict[str, Any]) -> None:
    atomic_write_json(project / PROFILE_RELATIVE, profile)
    atomic_write_text(project / PROFILE_SUMMARY_RELATIVE, markdown_summary(profile))


def golden_markdown_summary(profile: dict[str, Any]) -> str:
    chapters = "、".join(str(item) for item in profile["chapters"])
    lines = [
        "# 黄金声线样本",
        "",
        "> 本文件由 `voice_profile.py golden-build` 从作者明确精选、且已经接纳的章节派生。它是质量方向参考，不是 AI 分数，也不能覆盖剧情、题材和场景需要。",
        "",
        f"- 精选章节：{chapters}",
        f"- 样本数：{profile['source_count']} 章",
        f"- 来源摘要：`{profile['source_digest']}`",
        "- 建议规模：8—12 章；至少 5 章，避免单章偶然性",
        "- 处置：只生成双向 advisory，不自动改文",
        "",
        "| 观察项 | 中位数 | 观察范围 |",
        "|---|---:|---:|",
    ]
    for key, label in METRIC_LABELS.items():
        values = profile["baseline"][key]
        lines.append(f"| {label} | {values['median']:.4g} | {values['min']:.4g}—{values['max']:.4g} |")
    lines.extend(
        [
            "",
            "## 使用边界",
            "",
            "- 已接纳基线回答‘像不像这本书’，黄金样本只回答‘是否远离作者精选的强样本’。两者不能互相替代。",
            "- 只有作者明确选择的已接纳章节可以进入；候选稿、对标作品、备份和未闭环章节不得进入。",
            "- 黄金样本变化、失去接纳来源或正文摘要变化时立即视为 stale，重新冷读后才能重建。",
            "- 角色声线和跨章结构仍由语义审查处理，不从统计范围自动推导。",
            "",
        ]
    )
    return "\n".join(lines)


def write_golden_profile(project: Path, profile: dict[str, Any]) -> None:
    atomic_write_json(project / GOLDEN_PROFILE_RELATIVE, profile)
    atomic_write_text(project / GOLDEN_SUMMARY_RELATIVE, golden_markdown_summary(profile))


def load_profile(project: Path) -> dict[str, Any] | None:
    path = project / PROFILE_RELATIVE
    if not path.is_file():
        return None
    profile = load_json(path, "声音画像")
    if profile.get("schema_version") != SCHEMA_VERSION or profile.get("profile_kind") != "accepted_prose_voice":
        raise VoiceProfileError("声音画像 schema 不受支持")
    policy = profile.get("policy")
    if not isinstance(policy, dict) or not isinstance(policy.get("minimum_chapters"), int):
        raise VoiceProfileError("声音画像缺少有效 minimum_chapters")
    if int(policy["minimum_chapters"]) < MIN_CHAPTERS:
        raise VoiceProfileError(f"声音画像 minimum_chapters 低于安全下限 {MIN_CHAPTERS}")
    return profile


def load_golden_profile(project: Path) -> dict[str, Any] | None:
    path = project / GOLDEN_PROFILE_RELATIVE
    if not path.is_file():
        return None
    profile = load_json(path, "黄金声音画像")
    if profile.get("schema_version") != SCHEMA_VERSION or profile.get("profile_kind") != "golden_prose_voice":
        raise VoiceProfileError("黄金声音画像 schema 不受支持")
    sources = profile.get("sources")
    if not isinstance(sources, list) or len(sources) < MIN_GOLDEN_CHAPTERS:
        raise VoiceProfileError("黄金声音画像缺少足量有效 sources")
    return profile


def current_source_status(project: Path, profile: dict[str, Any]) -> dict[str, Any]:
    policy = profile.get("policy") if isinstance(profile.get("policy"), dict) else {}
    legacy = policy.get("legacy_approved_through")
    if legacy is not None and not isinstance(legacy, int):
        raise VoiceProfileError("声音画像 legacy_approved_through 无效")
    current = collect_sources(project, legacy)
    recorded = profile.get("sources")
    if not isinstance(recorded, list):
        raise VoiceProfileError("声音画像缺少 sources")
    recorded_core = [
        {
            "chapter": item.get("chapter"),
            "path": item.get("path"),
            "sha256": item.get("sha256"),
            "provenance": item.get("provenance"),
            "receipt": item.get("receipt"),
        }
        for item in recorded
        if isinstance(item, dict)
    ]
    changes: list[dict[str, Any]] = []
    old_by_chapter = {item["chapter"]: item for item in recorded_core if isinstance(item.get("chapter"), int)}
    new_by_chapter = {item["chapter"]: item for item in current}
    for chapter in sorted(set(old_by_chapter) | set(new_by_chapter)):
        old = old_by_chapter.get(chapter)
        new = new_by_chapter.get(chapter)
        if old is None:
            changes.append({"chapter": chapter, "reason": "newly_accepted"})
        elif new is None:
            changes.append({"chapter": chapter, "reason": "accepted_source_missing"})
        elif old != new:
            changes.append({"chapter": chapter, "reason": "accepted_source_changed", "path": new.get("path")})
    digest = source_digest(current)
    if digest != profile.get("source_digest") and not changes:
        changes.append({"reason": "source_digest_changed"})
    return {
        "status": "stale" if changes else "fresh",
        "profile": str(project / PROFILE_RELATIVE),
        "source_digest": digest,
        "source_count": len(current),
        "changes": changes,
    }


def golden_source_status(accepted_profile: dict[str, Any], golden_profile: dict[str, Any]) -> dict[str, Any]:
    accepted = {
        item.get("chapter"): source_core(item)
        for item in accepted_profile.get("sources", [])
        if isinstance(item, dict) and isinstance(item.get("chapter"), int)
    }
    recorded = [source_core(item) for item in golden_profile.get("sources", []) if isinstance(item, dict)]
    current: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    for item in recorded:
        chapter = item.get("chapter")
        source = accepted.get(chapter)
        if source is None:
            changes.append({"chapter": chapter, "reason": "no_longer_accepted"})
            continue
        current.append(source)
        if source != item:
            changes.append({"chapter": chapter, "reason": "accepted_source_changed", "path": source.get("path")})
    digest = source_digest(current)
    if digest != golden_profile.get("source_digest") and not changes:
        changes.append({"reason": "source_digest_changed"})
    return {
        "status": "stale" if changes else "fresh",
        "profile": str(GOLDEN_PROFILE_RELATIVE),
        "source_digest": digest,
        "source_count": len(current),
        "changes": changes,
    }


def compare_candidate(profile: dict[str, Any], metrics: dict[str, float]) -> list[dict[str, Any]]:
    advisories: list[dict[str, Any]] = []
    for key, label in METRIC_LABELS.items():
        value = float(metrics[key])
        early = profile["baselines"]["early"][key]
        recent = profile["baselines"]["recent"][key]
        direction: str | None = None
        if value < float(early["min"]) and value < float(recent["min"]):
            direction = "below"
        elif value > float(early["max"]) and value > float(recent["max"]):
            direction = "above"
        if direction is not None:
            advisories.append(
                {
                    "code": "voice-drift",
                    "metric": key,
                    "label": label,
                    "direction": direction,
                    "candidate": rounded(value),
                    "early_range": [early["min"], early["max"]],
                    "recent_range": [recent["min"], recent["max"]],
                    "message": "候选值同时落在早期与近期样本范围之外；先判断是否为本章有意变奏，再决定是否修改。",
                }
            )
    return advisories


def compare_golden(profile: dict[str, Any], metrics: dict[str, float]) -> list[dict[str, Any]]:
    advisories: list[dict[str, Any]] = []
    for key, label in METRIC_LABELS.items():
        value = float(metrics[key])
        observed = profile["baseline"][key]
        direction: str | None = None
        if value < float(observed["min"]):
            direction = "below"
        elif value > float(observed["max"]):
            direction = "above"
        if direction is not None:
            advisories.append(
                {
                    "code": "golden-voice-drift",
                    "metric": key,
                    "label": label,
                    "direction": direction,
                    "candidate": rounded(value),
                    "golden_range": [observed["min"], observed["max"]],
                    "message": "候选值落在作者精选样本观察范围之外；只定位冷读点，不据此自动改文。",
                }
            )
    return advisories


def cmd_golden_build(args: argparse.Namespace) -> int:
    if args.confirm != "GOLDEN_APPROVED":
        raise VoiceProfileError("建立黄金样本必须由作者明确选择，并传入 --confirm GOLDEN_APPROVED")
    project = project_root(args.project)
    accepted_profile = load_profile(project)
    if accepted_profile is None:
        raise VoiceProfileError("先建立已接纳正文声音画像，再选择黄金样本")
    accepted_status = current_source_status(project, accepted_profile)
    if accepted_status["status"] != "fresh":
        raise VoiceProfileError("已接纳正文声音画像已过期，先更新后再选择黄金样本")
    chapters = parse_chapter_selection(args.chapters)
    accepted = {
        item.get("chapter"): item
        for item in accepted_profile.get("sources", [])
        if isinstance(item, dict) and isinstance(item.get("chapter"), int)
    }
    missing = [chapter for chapter in chapters if chapter not in accepted]
    if missing:
        raise VoiceProfileError(f"黄金样本必须来自已接纳正文，缺少章号: {missing}")
    sources = [source_core(accepted[chapter]) for chapter in chapters]
    rows: list[dict[str, Any]] = []
    for source in sources:
        metrics, _, character_count = prose_metrics(project / str(source["path"]))
        rows.append({**source, "character_count": character_count, "metrics": metrics})
    payload = {
        "schema_version": SCHEMA_VERSION,
        "profile_kind": "golden_prose_voice",
        "status": "derived",
        "built_at": utc_now(),
        "project_root": str(project),
        "source_digest": source_digest(sources),
        "source_count": len(rows),
        "chapters": chapters,
        "policy": {
            "severity": "advisory",
            "author_curated": True,
            "minimum_chapters": MIN_GOLDEN_CHAPTERS,
            "recommended_chapters": [8, 12],
            "not_a_quality_score": True,
        },
        "sources": rows,
        "baseline": aggregate(rows),
    }
    write_golden_profile(project, payload)
    print(
        json.dumps(
            {
                "status": "built",
                "profile": str(project / GOLDEN_PROFILE_RELATIVE),
                "source_count": len(rows),
                "chapters": chapters,
                "source_digest": payload["source_digest"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_golden_verify(args: argparse.Namespace) -> int:
    project = project_root(args.project)
    golden = load_golden_profile(project)
    if golden is None:
        print(json.dumps({"status": "not_configured", "profile": str(project / GOLDEN_PROFILE_RELATIVE)}, ensure_ascii=False, indent=2))
        return 0
    accepted = load_profile(project)
    if accepted is None:
        raise VoiceProfileError("黄金声音画像存在，但已接纳正文声音画像缺失")
    accepted_status = current_source_status(project, accepted)
    if accepted_status["status"] != "fresh":
        print(json.dumps({"status": "stale", "reason": "accepted_profile_stale", **accepted_status}, ensure_ascii=False, indent=2))
        return 2
    result = golden_source_status(accepted, golden)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result["status"] == "stale" else 0


def exact_overlap(profile: dict[str, Any], sentences: list[str]) -> list[dict[str, Any]]:
    accepted = profile.get("accepted_sentence_hashes")
    if not isinstance(accepted, dict):
        return []
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for sentence in sentences:
        normalized = normalized_sentence(sentence)
        if len(normalized) < 12:
            continue
        digest = sha256_bytes(normalized.encode("utf-8"))
        if digest in accepted and digest not in seen:
            seen.add(digest)
            output.append(
                {
                    "code": "accepted-sentence-overlap",
                    "sentence": sentence[:80],
                    "accepted_occurrences": accepted[digest],
                    "message": "候选句与已接纳正文存在原句级重合；固定口头禅可保留，非刻意复现需复核。",
                }
            )
        if len(output) >= 5:
            break
    return output


def cmd_build(args: argparse.Namespace) -> int:
    project = project_root(args.project)
    profile_path = project / PROFILE_RELATIVE
    if args.legacy_approved_through is not None and args.confirm != "LEGACY_APPROVED":
        raise VoiceProfileError("纳入无回执旧章必须显式传入 --confirm LEGACY_APPROVED")
    if profile_path.exists() and args.confirm not in {"REBUILD", "LEGACY_APPROVED"}:
        raise VoiceProfileError("声音画像已存在；重建需显式传入 --confirm REBUILD")
    sources = collect_sources(project, args.legacy_approved_through)
    profile = build_payload(
        project,
        sources,
        legacy_approved_through=args.legacy_approved_through,
        min_chapters=args.min_chapters,
    )
    write_profile(project, profile)
    print(json.dumps({"status": "built", "profile": str(profile_path), "source_count": len(sources), "source_digest": profile["source_digest"]}, ensure_ascii=False, indent=2))
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    project = project_root(args.project)
    profile = load_profile(project)
    if profile is None:
        print(json.dumps({"status": "not_configured", "message": "尚未建立本书声音画像"}, ensure_ascii=False, indent=2))
        return 0
    policy = profile.get("policy") if isinstance(profile.get("policy"), dict) else {}
    legacy = policy.get("legacy_approved_through")
    if legacy is not None:
        for source in profile.get("sources", []):
            if not isinstance(source, dict) or source.get("provenance") != "explicit_legacy_approval":
                continue
            path = project / str(source.get("path", ""))
            if not path.is_file() or sha256_file(path) != source.get("sha256"):
                raise VoiceProfileError("显式批准的旧章样本已变化；必须重新审阅后用 build --confirm LEGACY_APPROVED 重建")
    sources = collect_sources(project, legacy if isinstance(legacy, int) else None)
    rebuilt = build_payload(
        project,
        sources,
        legacy_approved_through=legacy if isinstance(legacy, int) else None,
        min_chapters=int(policy.get("minimum_chapters", MIN_CHAPTERS)),
    )
    write_profile(project, rebuilt)
    print(json.dumps({"status": "updated", "profile": str(project / PROFILE_RELATIVE), "source_count": len(sources), "source_digest": rebuilt["source_digest"]}, ensure_ascii=False, indent=2))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    project = project_root(args.project)
    profile = load_profile(project)
    if profile is None:
        print(json.dumps({"status": "not_configured", "profile": str(project / PROFILE_RELATIVE)}, ensure_ascii=False, indent=2))
        return 0
    result = current_source_status(project, profile)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result["status"] == "stale" else 0


def cmd_check(args: argparse.Namespace) -> int:
    project = project_root(args.project)
    candidate, candidate_relative = resolve_inside(project, args.candidate, label="候选正文")
    profile = load_profile(project)
    if profile is None:
        print(
            json.dumps(
                {
                    "status": "not_configured",
                    "severity": "advisory",
                    "candidate": candidate_relative,
                    "message": "尚无足量已接纳样本；本轮只执行通用语言与去 AI 味门。",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    freshness = current_source_status(project, profile)
    if freshness["status"] != "fresh":
        print(json.dumps({"status": "stale", "severity": "blocking", "candidate": candidate_relative, **freshness}, ensure_ascii=False, indent=2))
        return 2
    metrics, sentences, character_count = prose_metrics(candidate)
    advisories = compare_candidate(profile, metrics)
    overlaps = exact_overlap(profile, sentences)
    golden = load_golden_profile(project)
    golden_result: dict[str, Any] = {"status": "not_configured"}
    golden_advisories: list[dict[str, Any]] = []
    if golden is not None:
        golden_freshness = golden_source_status(profile, golden)
        if golden_freshness["status"] != "fresh":
            print(
                json.dumps(
                    {
                        "status": "stale",
                        "severity": "blocking",
                        "candidate": candidate_relative,
                        "reason": "golden_profile_stale",
                        **golden_freshness,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 2
        golden_advisories = compare_golden(golden, metrics)
        golden_result = {
            "status": "advisory" if golden_advisories else "within_observed_ranges",
            "source_digest": golden["source_digest"],
            "chapters": golden["chapters"],
            "drift_advisories": golden_advisories,
        }
    payload = {
        "status": "advisory" if advisories or overlaps or golden_advisories else "within_observed_ranges",
        "severity": "advisory",
        "candidate": candidate_relative,
        "candidate_sha256": sha256_file(candidate),
        "character_count": character_count,
        "profile_source_digest": profile["source_digest"],
        "metrics": metrics,
        "drift_advisories": advisories,
        "sentence_overlap_advisories": overlaps,
        "golden_voice": golden_result,
        "instruction": "统计结果只定位复核点；不得为了回到均值机械改写。",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def prose_chunks(path: Path) -> list[str]:
    paragraphs = normalized_lines(path.read_text(encoding="utf-8"))
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for paragraph in paragraphs:
        length = chinese_count(paragraph)
        if current and size + length > 320:
            if size >= 120:
                chunks.append("\n\n".join(current))
            current = []
            size = 0
        current.append(paragraph)
        size += length
        if size >= 180:
            chunks.append("\n\n".join(current))
            current = []
            size = 0
    if current and size >= 100:
        chunks.append("\n\n".join(current))
    return chunks


def cmd_blind(args: argparse.Namespace) -> int:
    if args.confirm != "PREPARE":
        raise VoiceProfileError("生成盲测包必须显式传入 --confirm PREPARE")
    if not ID_PATTERN.fullmatch(args.id):
        raise VoiceProfileError("盲测 id 只能包含字母、数字、点、下划线和连字符")
    project = project_root(args.project)
    candidate, candidate_relative = resolve_inside(project, args.candidate, label="候选正文")
    profile = load_profile(project)
    if profile is None:
        raise VoiceProfileError("尚未建立声音画像，不能生成绑定基线的盲测包")
    freshness = current_source_status(project, profile)
    if freshness["status"] != "fresh":
        raise VoiceProfileError("声音画像已过期，先更新后再生成盲测包")
    sources = profile["sources"]
    baseline_kind = "accepted_early_recent"
    golden = load_golden_profile(project)
    if golden is not None:
        golden_freshness = golden_source_status(profile, golden)
        if golden_freshness["status"] != "fresh":
            raise VoiceProfileError("黄金声音画像已过期，先重建后再生成盲测包")
        sources = golden["sources"]
        baseline_kind = "author_curated_golden"
    accepted_choices = [sources[0], sources[-1]] if len(sources) > 1 else [sources[0]]
    rows: list[dict[str, Any]] = []
    for index, source in enumerate(accepted_choices, start=1):
        chunks = prose_chunks(project / source["path"])
        if not chunks:
            raise VoiceProfileError(f"已接纳样本第 {source['chapter']} 章不足以抽取盲测片段")
        rows.append({"kind": "accepted", "source": source["path"], "chapter": source["chapter"], "text": chunks[(index - 1) % len(chunks)]})
    candidate_chunks = prose_chunks(candidate)
    if not candidate_chunks:
        raise VoiceProfileError("候选正文不足以抽取盲测片段")
    for index, chunk in enumerate(candidate_chunks[:2], start=1):
        rows.append({"kind": "candidate", "source": candidate_relative, "chunk": index, "text": chunk})
    seed = sha256_bytes(f"{profile['source_digest']}:{sha256_file(candidate)}:{args.id}".encode("utf-8"))
    random.Random(seed).shuffle(rows)
    output = project / "追踪" / "文风" / "盲测" / args.id
    if output.exists():
        raise VoiceProfileError(f"盲测目录已存在: {output}")
    labels = [chr(ord("A") + index) for index in range(len(rows))]
    pack_lines = [
        "# 文风盲测包",
        "",
        "> 先只看本文件，不打开同目录答案。逐段记录：是否像同一本书、哪里出戏、哪些变化是场景需要。不要猜作者或模型。",
        "",
        f"- 绑定声音画像：`{profile['source_digest']}`",
        f"- 候选摘要：`{sha256_file(candidate)}`",
        f"- 对照基线：`{baseline_kind}`",
        "",
    ]
    answers: list[dict[str, Any]] = []
    for label, row in zip(labels, rows):
        pack_lines.extend([f"## 片段 {label}", "", row["text"], ""])
        answers.append({"label": label, **{key: value for key, value in row.items() if key != "text"}})
    key = {
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now(),
        "profile_source_digest": profile["source_digest"],
        "candidate": candidate_relative,
        "candidate_sha256": sha256_file(candidate),
        "baseline_kind": baseline_kind,
        "answers": answers,
    }
    atomic_write_text(output / "review-pack.md", "\n".join(pack_lines))
    atomic_write_json(output / "answer-key.json", key)
    print(json.dumps({"status": "prepared", "pack": str(output / "review-pack.md"), "answer_key": str(output / "answer-key.json"), "passages": len(rows)}, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="从已接纳正文首次建立或显式重建画像")
    build.add_argument("--project", required=True)
    build.add_argument("--legacy-approved-through", type=int)
    build.add_argument("--min-chapters", type=int, default=MIN_CHAPTERS)
    build.add_argument("--confirm")
    build.set_defaults(func=cmd_build)

    update = subparsers.add_parser("update", help="在新接纳回执闭环后更新画像")
    update.add_argument("--project", required=True)
    update.set_defaults(func=cmd_update)

    verify = subparsers.add_parser("verify", help="检查画像是否仍绑定当前接纳正文")
    verify.add_argument("--project", required=True)
    verify.set_defaults(func=cmd_verify)

    check = subparsers.add_parser("check", help="对候选正文做双向 advisory 漂移检查")
    check.add_argument("--project", required=True)
    check.add_argument("--candidate", required=True)
    check.set_defaults(func=cmd_check)

    blind = subparsers.add_parser("blind", help="生成不暴露来源标签的 A/B 冷读包")
    blind.add_argument("--project", required=True)
    blind.add_argument("--candidate", required=True)
    blind.add_argument("--id", required=True)
    blind.add_argument("--confirm")
    blind.set_defaults(func=cmd_blind)

    golden_build = subparsers.add_parser("golden-build", help="从作者明确精选的已接纳章节建立黄金声线样本")
    golden_build.add_argument("--project", required=True)
    golden_build.add_argument("--chapters", required=True, help="逗号分隔的已接纳章号，例如 3,8,15,22,31")
    golden_build.add_argument("--confirm", required=True)
    golden_build.set_defaults(func=cmd_golden_build)

    golden_verify = subparsers.add_parser("golden-verify", help="验证黄金声线样本仍绑定已接纳正文")
    golden_verify.add_argument("--project", required=True)
    golden_verify.set_defaults(func=cmd_golden_verify)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except VoiceProfileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
