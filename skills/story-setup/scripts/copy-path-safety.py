#!/usr/bin/env python3
"""Classify a planned copy before any recursive replace is attempted."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def classify(source_raw: str, target_raw: str) -> dict[str, Any]:
    source_input = Path(source_raw).expanduser()
    target_input = Path(target_raw).expanduser()
    source = source_input.resolve(strict=False)
    target = target_input.resolve(strict=False)
    payload: dict[str, Any] = {
        "source_input": str(source_input),
        "target_input": str(target_input),
        "source_realpath": str(source),
        "target_realpath": str(target),
        "status": "error",
        "copy_allowed": False,
        "reason": "unclassified",
    }

    if not source.exists():
        payload.update(status="error", reason="source_missing")
        return payload

    if source == target:
        payload.update(status="same", reason="same_realpath")
        return payload

    if target.exists():
        try:
            if os.path.samefile(source, target):
                payload.update(status="same", reason="same_filesystem_object")
                return payload
        except OSError:
            pass

    if is_relative_to(target, source):
        payload.update(status="unsafe", reason="target_inside_source")
        return payload

    if is_relative_to(source, target):
        payload.update(status="unsafe", reason="source_inside_target")
        return payload

    payload.update(status="safe", copy_allowed=True, reason="disjoint_paths")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="copy source path")
    parser.add_argument("target", help="copy target path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = classify(args.source, args.target)
    except (OSError, RuntimeError) as exc:
        payload = {
            "source_input": args.source,
            "target_input": args.target,
            "status": "error",
            "copy_allowed": False,
            "reason": "path_resolution_failed",
            "detail": str(exc),
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if payload["status"] in {"safe", "same"}:
        return 0
    return 1 if payload["status"] == "unsafe" else 2


if __name__ == "__main__":
    sys.exit(main())
