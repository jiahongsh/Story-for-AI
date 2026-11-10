#!/usr/bin/env python3
"""Connect oh-story to a project-local publishing adapter without shell use."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


CONFIG_NAME = ".story-publish.json"
SCHEMA_VERSION = 1
SUPPORTED_PLATFORMS = {"fanqie"}
READ_ONLY_ACTIONS = {"preview", "books", "preflight"}
SESSION_ACTIONS = {"login"}
REMOTE_WRITE_ACTIONS = {"draft", "edit", "publish", "schedule"}
ALLOWED_ACTIONS = READ_ONLY_ACTIONS | SESSION_ACTIONS | REMOTE_WRITE_ACTIONS


class BridgeError(RuntimeError):
    pass


def atomic_write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    fd, raw_temp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    temp = Path(raw_temp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(temp, 0o600)
        except OSError:
            pass
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def config_path(project_root: Path) -> Path:
    return project_root.resolve() / CONFIG_NAME


def load_config(project_root: Path, *, required: bool = True) -> dict:
    path = config_path(project_root)
    if not path.is_file():
        if required:
            raise BridgeError(
                f"未关联发布器：{path} 不存在。先运行 configure fanqie。"
            )
        return {"schema_version": SCHEMA_VERSION, "platforms": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BridgeError(f"发布关联配置不可读：{exc}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise BridgeError("发布关联配置 schema_version 不受支持")
    if not isinstance(value.get("platforms"), dict):
        raise BridgeError("发布关联配置缺少 platforms 对象")
    return value


def existing_file(
    raw: str, *, label: str, preserve_symlink: bool = False
) -> Path:
    expanded = Path(raw).expanduser()
    path = (
        Path(os.path.abspath(expanded))
        if preserve_symlink
        else expanded.resolve()
    )
    if not path.is_file():
        raise BridgeError(f"{label} 不存在或不是文件：{path}")
    return path


def existing_dir(raw: str, *, label: str) -> Path:
    path = Path(raw).expanduser().resolve()
    if not path.is_dir():
        raise BridgeError(f"{label} 不存在或不是目录：{path}")
    return path


def platform_entry(config: dict, platform: str) -> dict:
    if platform not in SUPPORTED_PLATFORMS:
        raise BridgeError(f"不支持的平台：{platform}")
    raw = config["platforms"].get(platform)
    if not isinstance(raw, dict):
        raise BridgeError(f"平台 {platform} 尚未关联适配器")
    adapter = existing_file(str(raw.get("adapter", "")), label="adapter")
    # venv/bin/python 常是 symlink；resolve() 会丢掉旁边的 pyvenv.cfg，进而
    # 把它变成缺少项目依赖的系统解释器。
    python = existing_file(
        str(raw.get("python", "")), label="python", preserve_symlink=True
    )
    cwd = existing_dir(str(raw.get("cwd", "")), label="cwd")
    if adapter.parent != cwd:
        raise BridgeError("adapter 必须位于登记的 cwd 内，避免跨目录误调用")
    return {"adapter": adapter, "python": python, "cwd": cwd}


def configure(args: argparse.Namespace) -> int:
    project_root = args.project_root.resolve()
    if not project_root.is_dir():
        raise BridgeError(f"项目根不存在：{project_root}")
    adapter = existing_file(args.adapter, label="adapter")
    python = existing_file(args.python, label="python", preserve_symlink=True)
    cwd = existing_dir(args.cwd or str(adapter.parent), label="cwd")
    if adapter.parent != cwd:
        raise BridgeError("adapter 必须直接位于 cwd 中")
    probe = subprocess.run(
        [str(python), str(adapter), "--help"],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=30,
    )
    if probe.returncode != 0:
        raise BridgeError(
            f"适配器自检失败（exit {probe.returncode}）：{probe.stdout.strip()}"
        )
    required_words = {"preview", "preflight", "draft", "publish", "schedule"}
    missing = sorted(word for word in required_words if word not in probe.stdout)
    if missing:
        raise BridgeError("适配器缺少安全动作：" + ", ".join(missing))
    config = load_config(project_root, required=False)
    config["platforms"][args.platform] = {
        "adapter": str(adapter),
        "python": str(python),
        "cwd": str(cwd),
    }
    atomic_write_json(config_path(project_root), config)
    print(f"已关联 {args.platform} 发布适配器：{adapter}")
    print("配置未保存 Book ID、Cookie、密码或 token。")
    return 0


def status(args: argparse.Namespace) -> int:
    config = load_config(args.project_root)
    print(f"配置：{config_path(args.project_root)}")
    for platform in sorted(config["platforms"]):
        entry = platform_entry(config, platform)
        print(f"{platform}: ready")
        print(f"  adapter: {entry['adapter']}")
        print(f"  python: {entry['python']}")
        print(f"  cwd: {entry['cwd']}")
    return 0


def remove_bridge_confirmation(arguments: list[str]) -> tuple[list[str], bool]:
    forwarded: list[str] = []
    confirmed = False
    for argument in arguments:
        if argument == "--confirm-remote-draft":
            confirmed = True
        elif argument != "--":
            forwarded.append(argument)
    return forwarded, confirmed


def run_adapter(args: argparse.Namespace) -> int:
    if args.action not in ALLOWED_ACTIONS:
        raise BridgeError(f"不允许的发布动作：{args.action}")
    config = load_config(args.project_root)
    entry = platform_entry(config, args.platform)
    forwarded, draft_confirmed = remove_bridge_confirmation(args.arguments)
    if args.action == "draft" and not draft_confirmed:
        raise BridgeError(
            "远程草稿写入已拦截：复核作品和章节后添加 --confirm-remote-draft"
        )
    if args.action in {"edit", "publish", "schedule"}:
        if "--confirm-live" not in forwarded:
            raise BridgeError("正式平台写入已拦截：缺少下游 --confirm-live")
        if "--ai-declaration" not in forwarded:
            raise BridgeError(
                "正式平台写入已拦截：缺少 --ai-declaration yes|no"
            )
    command = [
        str(entry["python"]),
        str(entry["adapter"]),
        args.action,
        *forwarded,
    ]
    print(f"平台：{args.platform}；动作：{args.action}")
    completed = subprocess.run(command, cwd=entry["cwd"], check=False)
    if args.action in REMOTE_WRITE_ACTIONS and completed.returncode != 0:
        print(
            "远程写入未得到成功回执；禁止自动重放。请先运行 preflight 核对远端状态。",
            file=sys.stderr,
        )
    return completed.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root", type=Path, default=Path.cwd(), help="项目根目录"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    configure_parser = sub.add_parser("configure", help="关联平台发布适配器")
    configure_parser.add_argument("platform", choices=sorted(SUPPORTED_PLATFORMS))
    configure_parser.add_argument("--adapter", required=True)
    configure_parser.add_argument("--python", required=True)
    configure_parser.add_argument("--cwd")
    configure_parser.set_defaults(handler=configure)

    status_parser = sub.add_parser("status", help="检查已登记适配器")
    status_parser.set_defaults(handler=status)

    run_parser = sub.add_parser("run", help="运行白名单内的平台动作")
    run_parser.add_argument("platform", choices=sorted(SUPPORTED_PLATFORMS))
    run_parser.add_argument("action")
    run_parser.add_argument("arguments", nargs=argparse.REMAINDER)
    run_parser.set_defaults(handler=run_adapter)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (BridgeError, OSError, subprocess.SubprocessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
