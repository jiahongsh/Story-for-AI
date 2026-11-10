#!/usr/bin/env python3
"""Resolve, validate, and materialize built-in oh-story genre contracts."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONTRACT_DIR = Path(__file__).resolve().parent.parent / "references" / "genre-contracts"
REQUIRED_KEYS = {
    "contract_version",
    "genre_id",
    "display_name",
    "aliases",
    "markets",
    "languages",
    "core_promise",
    "chapter_types",
    "satisfaction_types",
    "conflict_engine",
    "pacing_rule",
    "numerical_system",
    "power_scaling",
    "reader_contract",
    "forbidden_drift",
    "review_gates",
    "evidence",
}


class ContractError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContractError(f"文件不存在: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ContractError(f"JSON 无效: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ContractError(f"契约根节点必须是对象: {path}")
    return data


def validate_contract(data: dict[str, Any], source: str) -> None:
    missing = sorted(REQUIRED_KEYS - data.keys())
    if missing:
        raise ContractError(f"{source} 缺少字段: {', '.join(missing)}")
    if not isinstance(data["genre_id"], str) or not data["genre_id"]:
        raise ContractError(f"{source} genre_id 无效")
    for key in ("aliases", "markets", "languages", "chapter_types", "satisfaction_types", "reader_contract", "review_gates"):
        if not isinstance(data[key], list) or not data[key]:
            raise ContractError(f"{source} {key} 必须是非空数组")
    chapter_ids = [item.get("id") for item in data["chapter_types"] if isinstance(item, dict)]
    if len(chapter_ids) != len(data["chapter_types"]) or any(not value for value in chapter_ids):
        raise ContractError(f"{source} chapter_types 项必须包含 id")
    if len(set(chapter_ids)) != len(chapter_ids):
        raise ContractError(f"{source} chapter_types id 重复")


def iter_contracts() -> list[tuple[Path, dict[str, Any]]]:
    result: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(CONTRACT_DIR.glob("*.json")):
        data = load_json(path)
        validate_contract(data, str(path))
        result.append((path, data))
    return result


def normalize(value: str) -> str:
    return "".join(value.strip().casefold().split())


def resolve_contract(query: str) -> tuple[Path, dict[str, Any]]:
    needle = normalize(query)
    exact: list[tuple[Path, dict[str, Any]]] = []
    for path, data in iter_contracts():
        names = [data["genre_id"], data["display_name"], *data["aliases"]]
        if needle in {normalize(str(name)) for name in names}:
            exact.append((path, data))
    if not exact:
        raise ContractError(f"未命中内置题材契约: {query}")
    if len(exact) > 1:
        ids = ", ".join(item[1]["genre_id"] for item in exact)
        raise ContractError(f"题材别名冲突: {query} -> {ids}")
    return exact[0]


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def cmd_list(_: argparse.Namespace) -> int:
    for path, data in iter_contracts():
        aliases = " / ".join(data["aliases"])
        print(f"{data['genre_id']}\t{data['display_name']}\t{aliases}\t{path}")
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    path, data = resolve_contract(args.genre)
    if args.path_only:
        print(path)
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def cmd_materialize(args: argparse.Namespace) -> int:
    source_path, source = resolve_contract(args.genre)
    project_root = Path(args.project_root).expanduser().resolve()
    if not project_root.is_dir():
        raise ContractError(f"项目根目录不存在: {project_root}")
    target = project_root / "设定" / "题材契约.json"
    if target.exists() and not args.force:
        raise ContractError(f"项目契约已存在，拒绝覆盖: {target}；确认重建后使用 --force")
    payload = copy.deepcopy(source)
    payload["source_contract"] = source_path.name
    payload["project_binding"] = {
        "materialized_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(project_root),
    }
    payload["project_overrides"] = {}
    atomic_write_json(target, payload)
    print(target)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    path = Path(args.file).expanduser().resolve()
    data = load_json(path)
    validate_contract(data, str(path))
    print(f"valid\t{data['genre_id']}\t{path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list", help="列出内置契约")
    list_parser.set_defaults(func=cmd_list)

    resolve_parser = sub.add_parser("resolve", help="按 id、中文名或别名解析契约")
    resolve_parser.add_argument("genre")
    resolve_parser.add_argument("--path-only", action="store_true")
    resolve_parser.set_defaults(func=cmd_resolve)

    materialize_parser = sub.add_parser("materialize", help="把内置契约写入项目的设定目录")
    materialize_parser.add_argument("genre")
    materialize_parser.add_argument("project_root")
    materialize_parser.add_argument("--force", action="store_true")
    materialize_parser.set_defaults(func=cmd_materialize)

    validate_parser = sub.add_parser("validate", help="执行轻量结构校验")
    validate_parser.add_argument("file")
    validate_parser.set_defaults(func=cmd_validate)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except ContractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
