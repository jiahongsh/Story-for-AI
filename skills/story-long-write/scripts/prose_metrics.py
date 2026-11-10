#!/usr/bin/env python3
"""Measure Chinese prose sentence and paragraph shape without model estimates."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from voice_profile import chinese_count, normalized_lines, prose_metrics, split_sentences


def rounded(value: float) -> float:
    return round(float(value), 4)


def percentage(count: int, total: int) -> float:
    return rounded(count * 100 / total) if total else 0.0


def measure(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"正文文件不存在: {path}")
    text = path.read_text(encoding="utf-8")
    paragraphs = normalized_lines(text)
    sentences = split_sentences(paragraphs)
    sentence_lengths = [chinese_count(sentence) for sentence in sentences if chinese_count(sentence) > 0]
    paragraph_lengths = [chinese_count(paragraph) for paragraph in paragraphs if chinese_count(paragraph) > 0]
    if not sentence_lengths or not paragraph_lengths:
        raise ValueError(f"正文没有可测量的中文句段: {path}")

    metrics, _, character_count = prose_metrics(path)
    short = sum(1 for length in sentence_lengths if length <= 8)
    medium = sum(1 for length in sentence_lengths if 9 <= length <= 34)
    long = sum(1 for length in sentence_lengths if length >= 35)
    sentence_count = len(sentence_lengths)
    paragraph_count = len(paragraph_lengths)
    return {
        "status": "measured",
        "file": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "character_count": character_count,
        "sentence_count": sentence_count,
        "paragraph_count": paragraph_count,
        "bucket_contract": {"short": "1-8字", "medium": "9-34字", "long": "35字及以上"},
        "sentence_distribution": {
            "short": {"count": short, "rate_pct": percentage(short, sentence_count)},
            "medium": {"count": medium, "rate_pct": percentage(medium, sentence_count)},
            "long": {"count": long, "rate_pct": percentage(long, sentence_count)},
        },
        "sentence_mean_chars": metrics["sentence_mean_chars"],
        "sentence_median_chars": metrics["sentence_median_chars"],
        "paragraph_mean_chars": metrics["paragraph_mean_chars"],
        "paragraph_median_chars": metrics["paragraph_median_chars"],
        "sentences_per_paragraph": rounded(sentence_count / paragraph_count),
        "instruction": "只报告实测值；这些统计用于定位复核，不是跨题材质量配额。",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", help="Chinese prose files")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    results: list[dict[str, Any]] = []
    try:
        for raw in args.files:
            results.append(measure(Path(raw).expanduser().resolve()))
    except (OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    payload: dict[str, Any] = results[0] if len(results) == 1 else {"status": "measured", "results": results}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
