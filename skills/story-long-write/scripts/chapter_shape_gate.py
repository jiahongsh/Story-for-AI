#!/usr/bin/env python3
"""Prepare deterministic evidence for semantic cross-chapter shape review.

This tool does not decide whether prose is AI-written and never rewrites text. It
compares coarse surface signals across the candidate and recent formal chapters,
then asks a semantic reviewer to judge scene-engine, delivery-mode, and hook reuse.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any


CHAPTER_PATTERN = re.compile(r"^第0*(\d+)章(?:_|\.|\s|$)")
TITLE_PATTERN = re.compile(r"^\s*#{1,6}\s*")
CHINESE_PATTERN = re.compile(r"[\u3400-\u9fff]")
RULE_PATTERN = re.compile(r"先[^。！？]{0,18}再|不能|不得|只(?:能|准|许)|谁[^。！？]{0,16}谁|逐(?:一|项|条|个|家)|分别|分成|归到")
PROCEDURE_PATTERN = re.compile(r"表单|名单|章程|流程|手续|记录|签名|签字|盖印|核验|复核|凭据|证据|规则|簿|栏")
EXPLANATION_PATTERN = re.compile(r"这意味着|也就是说|换句话说|之所以|原因是|因此|所以|必须|需要")
SUMMARY_END_PATTERN = re.compile(r"终于明白|这意味着|才刚刚开始|注定|命运|新的人生|一切都变了")
DEADLINE_END_PATTERN = re.compile(r"明日|今晚|天亮前|午时|子时|倒计时|只剩|之前|以后|时辰")
ACTION_PATTERN = re.compile(r"拿|放|推|拉|转|抬|低|走|跑|站|坐|关|开|写|看|听|按|握|松|收|掀|递|退")
VECTOR_KEYS = (
    "dialogue_rate_pct",
    "question_rate_pct",
    "qa_pair_candidates_per_100p",
    "rule_marker_per_1k",
    "procedure_marker_per_1k",
    "explanation_marker_per_1k",
)


class ShapeError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_root(raw: str) -> Path:
    project = Path(raw).expanduser().resolve()
    if not project.is_dir():
        raise ShapeError(f"项目目录不存在: {project}")
    return project


def resolve_inside(project: Path, raw: str, label: str) -> tuple[Path, str]:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = project / path
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(project).as_posix()
    except ValueError as exc:
        raise ShapeError(f"{label}必须位于项目目录内: {raw}") from exc
    if not resolved.is_file():
        raise ShapeError(f"{label}不存在: {resolved}")
    return resolved, relative


def chapter_number(path: Path) -> int | None:
    match = CHAPTER_PATTERN.match(path.name)
    return int(match.group(1)) if match else None


def prose_paragraphs(path: Path) -> list[str]:
    paragraphs: list[str] = []
    title_skipped = False
    for raw in path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()
        if not line:
            continue
        if not title_skipped and (TITLE_PATTERN.match(line) or CHAPTER_PATTERN.match(TITLE_PATTERN.sub("", line))):
            title_skipped = True
            continue
        if line.startswith("<!--") and line.endswith("-->"):
            continue
        paragraphs.append(line)
    return paragraphs


def chinese_count(text: str) -> int:
    return len(CHINESE_PATTERN.findall(text))


def dialogue_paragraph(text: str) -> bool:
    return text.lstrip().startswith(("“", "「", "『", '"'))


def qa_pair_candidates(paragraphs: list[str]) -> int:
    count = 0
    for index, paragraph in enumerate(paragraphs):
        if "？" not in paragraph and "?" not in paragraph:
            continue
        following = paragraphs[index + 1 : index + 3]
        if any(dialogue_paragraph(item) and chinese_count(item) >= 16 for item in following):
            count += 1
    return count


def opening_mode(paragraphs: list[str]) -> str:
    if not paragraphs:
        return "empty"
    first = paragraphs[0]
    if dialogue_paragraph(first):
        return "dialogue"
    if "？" in first or "?" in first:
        return "question"
    if ACTION_PATTERN.search(first[:24]):
        return "action"
    return "exposition"


def ending_mode(paragraphs: list[str]) -> str:
    if not paragraphs:
        return "empty"
    last = paragraphs[-1]
    window = "".join(paragraphs[-3:])
    if SUMMARY_END_PATTERN.search(window):
        return "summary"
    if dialogue_paragraph(last):
        return "dialogue"
    if DEADLINE_END_PATTERN.search(window):
        return "deadline"
    if ACTION_PATTERN.search(last):
        return "action"
    return "object_or_state"


def excerpt(paragraphs: list[str], *, tail: bool) -> str:
    selected = paragraphs[-3:] if tail else paragraphs[:3]
    text = " / ".join(selected)
    return text[:140]


def analyze_file(project: Path, path: Path, chapter: int | None) -> dict[str, Any]:
    paragraphs = prose_paragraphs(path)
    compact = "".join(paragraphs)
    chars = max(1, chinese_count(compact))
    paragraph_total = max(1, len(paragraphs))
    dialogue_count = sum(1 for item in paragraphs if dialogue_paragraph(item))
    question_count = sum(1 for item in paragraphs if "？" in item or "?" in item)
    pairs = qa_pair_candidates(paragraphs)
    return {
        "chapter": chapter,
        "path": path.relative_to(project).as_posix(),
        "sha256": sha256_file(path),
        "opening_mode": opening_mode(paragraphs),
        "ending_mode": ending_mode(paragraphs),
        "metrics": {
            "dialogue_rate_pct": round(dialogue_count * 100 / paragraph_total, 4),
            "question_rate_pct": round(question_count * 100 / paragraph_total, 4),
            "qa_pair_candidates_per_100p": round(pairs * 100 / paragraph_total, 4),
            "rule_marker_per_1k": round(len(RULE_PATTERN.findall(compact)) * 1000 / chars, 4),
            "procedure_marker_per_1k": round(len(PROCEDURE_PATTERN.findall(compact)) * 1000 / chars, 4),
            "explanation_marker_per_1k": round(len(EXPLANATION_PATTERN.findall(compact)) * 1000 / chars, 4),
        },
        "opening_excerpt": excerpt(paragraphs, tail=False),
        "ending_excerpt": excerpt(paragraphs, tail=True),
    }


def vector_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    values: list[float] = []
    for key in VECTOR_KEYS:
        a = float(left.get(key, 0.0))
        b = float(right.get(key, 0.0))
        scale = max(abs(a), abs(b), 1.0)
        values.append(abs(a - b) / scale)
    distance = statistics.fmean(values) if values else 0.0
    return round(max(0.0, 1.0 - distance), 4)


def collect_history(project: Path, chapter: int, window: int) -> list[tuple[int, Path]]:
    prose_dir = project / "正文"
    rows: list[tuple[int, Path]] = []
    if prose_dir.is_dir():
        for path in prose_dir.glob("第*章*.md"):
            number = chapter_number(path)
            if number is not None and number < chapter:
                rows.append((number, path))
    duplicates: dict[int, int] = {}
    for number, _ in rows:
        duplicates[number] = duplicates.get(number, 0) + 1
    repeated = [number for number, count in duplicates.items() if count > 1]
    if repeated:
        raise ShapeError(f"正式正文存在重复章号，无法建立近章窗口: {sorted(repeated)}")
    return sorted(rows, key=lambda item: item[0])[-window:]


def build_payload(project: Path, candidate: Path, candidate_relative: str, chapter: int, window: int) -> dict[str, Any]:
    if chapter <= 0:
        raise ShapeError("chapter 必须大于 0")
    if window < 3 or window > 12:
        raise ShapeError("window 必须在 3—12 之间")
    current = analyze_file(project, candidate, chapter)
    current["path"] = candidate_relative
    history_rows = collect_history(project, chapter, window)
    history = [analyze_file(project, path, number) for number, path in history_rows]
    if len(history) < 3:
        return {
            "status": "insufficient_history",
            "severity": "advisory",
            "chapter": chapter,
            "history_count": len(history),
            "minimum_history": 3,
            "candidate": current,
            "instruction": "历史不足时不制造伪精确结构结论；继续人工通读。",
        }
    comparisons = [
        {
            "chapter": item["chapter"],
            "similarity": vector_similarity(current["metrics"], item["metrics"]),
            "same_opening_mode": current["opening_mode"] == item["opening_mode"],
            "same_ending_mode": current["ending_mode"] == item["ending_mode"],
        }
        for item in history
    ]
    signals: list[dict[str, Any]] = []
    high_similarity = [item for item in comparisons if item["similarity"] >= 0.82]
    if len(high_similarity) >= 3:
        signals.append(
            {
                "code": "surface-shape-cluster",
                "chapters": [item["chapter"] for item in high_similarity],
                "message": "候选与至少三章的对白/问答/规则说明表面向量接近；必须语义判断是否复用了同一场景发动机。",
            }
        )
    ending_run = [item for item in history[-3:] if item["ending_mode"] == current["ending_mode"]]
    if len(ending_run) == 3:
        signals.append(
            {
                "code": "ending-mode-run",
                "mode": current["ending_mode"],
                "chapters": [item["chapter"] for item in history[-3:]] + [chapter],
                "message": "连续四章使用同一粗粒度收尾方式；检查钩子功能是否也同构。",
            }
        )
    return {
        "status": "semantic_review_required",
        "severity": "advisory",
        "chapter": chapter,
        "window": window,
        "candidate": current,
        "history": history,
        "comparisons": comparisons,
        "signals": signals,
        "review_questions": [
            "近章是否反复用同一种冲突发动机，而不只是共享题材物件？",
            "配角是否只负责提出下一个规则问题，主角随后给出完整标准答案？",
            "信息是否总通过分栏、列举、公开验证或总结性对白交付？",
            "章尾钩子的事件功能是否连续同构，而不只是标点或句长相似？",
            "候选是否保留人物特有的误解、回避、私心或未解决代价？",
        ],
        "instruction": "结构信号只提供证据，不判 AI、不自动改文；功能性仪式、审讯、倒计时和连续案件结构可保留。",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--chapter", type=int, required=True)
    parser.add_argument("--window", type=int, default=6)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        project = project_root(args.project)
        candidate, relative = resolve_inside(project, args.candidate, "候选正文")
        payload = build_payload(project, candidate, relative, args.chapter, args.window)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except ShapeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
