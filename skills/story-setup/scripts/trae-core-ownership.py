#!/usr/bin/env python3
"""Classify an existing TRAE shared hook core before story-setup replaces it.

Current managed cores carry an explicit marker.  Older releases predate that
marker, so their exact SHA-256 digests are kept in a package-owned registry.
Anything else is user-owned and must not be overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


MARKER = b"// oh-story-managed: shared-hook-core"


class OwnershipError(ValueError):
    pass


def load_registry(path: Path, asset_key: str) -> set[str]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OwnershipError(f"unable to read legacy hash registry {path}: {exc}") from exc
    if not isinstance(document, dict) or not document:
        raise OwnershipError("legacy hash registry root must be a non-empty object")
    if any(
        not isinstance(key, str)
        or not re.fullmatch(r"[A-Za-z0-9_.-]+", key)
        or not isinstance(value, list)
        for key, value in document.items()
    ):
        raise OwnershipError("legacy hash registry must map safe asset names to SHA-256 arrays")
    if asset_key not in document:
        raise OwnershipError(f"legacy hash registry has no entry for {asset_key}")
    raw_hashes = document[asset_key]
    if not isinstance(raw_hashes, list) or not raw_hashes:
        raise OwnershipError("managedLegacyHashes must be a non-empty array")
    if any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value) for value in raw_hashes):
        raise OwnershipError("managedLegacyHashes contains a non-SHA-256 value")
    if len(raw_hashes) != len(set(raw_hashes)):
        raise OwnershipError("managedLegacyHashes contains duplicates")
    return set(raw_hashes)


def classify(candidate: Path, registry: Path, asset_key: str | None = None) -> dict[str, object]:
    try:
        payload = candidate.read_bytes()
    except OSError as exc:
        raise OwnershipError(f"unable to read candidate {candidate}: {exc}") from exc
    digest = hashlib.sha256(payload).hexdigest()
    resolved_asset_key = asset_key or candidate.name
    if MARKER in payload:
        return {
            "asset": resolved_asset_key,
            "managed": True,
            "reason": "marker",
            "sha256": digest,
        }
    if digest in load_registry(registry, resolved_asset_key):
        return {
            "asset": resolved_asset_key,
            "managed": True,
            "reason": "legacy-sha256",
            "sha256": digest,
        }
    return {
        "asset": resolved_asset_key,
        "managed": False,
        "reason": "unmanaged",
        "sha256": digest,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument(
        "--asset-key",
        help="registry key; defaults to the candidate basename",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = classify(args.candidate, args.registry, args.asset_key)
    except OwnershipError as exc:
        print(json.dumps({"managed": False, "reason": "error", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["managed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
