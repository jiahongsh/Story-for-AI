#!/usr/bin/env python3
"""Validate chapter-extractor JSON and atomically render canonical Markdown.

The model-facing contract intentionally stays small and deterministic.  This
script rejects malformed or semantically ambiguous payloads before touching the
destination, then publishes the complete Markdown file with one ``os.replace``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


PLOT_TYPES = {
    "转折点",
    "信息揭示",
    "冲突",
    "解决",
    "铺垫",
    "行动",
    "对话",
    "状态变化",
}
THEMES = {
    "爱情",
    "亲情",
    "友情",
    "权力",
    "金钱",
    "成长",
    "复仇",
    "悬念",
    "搞笑",
    "热血",
    "日常",
    "其他",
}
TONES = {
    "紧张",
    "轻松",
    "悲伤",
    "热血",
    "爽",
    "甜",
    "温馨",
    "恐怖",
    "压抑",
    "其他",
}
TECHNIQUES = {
    "铺垫后置",
    "反应层放大",
    "信息差",
    "对比锚点",
    "延迟揭示",
    "身体反应",
    "小目标嵌套",
    "其他",
}
READER_EFFECTS = {
    "好奇",
    "期待",
    "压抑",
    "爽",
    "心疼",
    "紧张",
    "甜",
    "热血",
    "其他",
}
IMPORTANCE_LEVELS = {"major", "supporting", "minor"}

TOP_LEVEL_KEYS = {
    "chapter_number",
    "title",
    "summary",
    "key_events",
    "key_information_expansion",
    "chapter_formula",
    "characters",
    "plot_points",
}


class ContractError(ValueError):
    """A chapter-extractor payload violated the deterministic contract."""


class DuplicateKeyError(ValueError):
    """JSON contained a duplicate object key."""


def _object_without_duplicate_keys(pairs: Iterable[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError("duplicate JSON key: {!r}".format(key))
        result[key] = value
    return result


def _reject_non_finite_json(value: str) -> None:
    raise ValueError("non-finite JSON number is not allowed: {}".format(value))


def parse_json_text(text: str) -> Any:
    """Parse exactly one strict JSON value, rejecting duplicate keys and NaN."""

    try:
        return json.loads(
            text,
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_non_finite_json,
        )
    except (DuplicateKeyError, ValueError, json.JSONDecodeError) as exc:
        raise ContractError("invalid JSON: {}".format(exc)) from exc


def _require_object(value: Any, path: str, keys: Iterable[str]) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ContractError("{} must be an object".format(path))
    expected = set(keys)
    actual = set(value)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        details: List[str] = []
        if missing:
            details.append("missing keys: {}".format(", ".join(missing)))
        if extra:
            details.append("unexpected keys: {}".format(", ".join(extra)))
        raise ContractError("{} has wrong schema ({})".format(path, "; ".join(details)))
    return value


def _require_list(
    value: Any,
    path: str,
    *,
    minimum: int = 0,
    maximum: Optional[int] = None,
) -> List[Any]:
    if not isinstance(value, list):
        raise ContractError("{} must be an array".format(path))
    if len(value) < minimum:
        raise ContractError("{} must contain at least {} item(s)".format(path, minimum))
    if maximum is not None and len(value) > maximum:
        raise ContractError("{} must contain at most {} item(s)".format(path, maximum))
    return value


def _contains_forbidden_control(value: str, allow_newlines: bool) -> bool:
    for character in value:
        if unicodedata.category(character) == "Cs":
            return True
        if character in "\r\u2028\u2029":
            return True
        if character == "\n" and allow_newlines:
            continue
        if character == "\n" or (ord(character) < 32 and character != "\t"):
            return True
    return False


def _require_text(
    value: Any,
    path: str,
    *,
    minimum: int = 1,
    maximum: Optional[int] = None,
    allow_newlines: bool = False,
    require_trimmed: bool = True,
) -> str:
    if not isinstance(value, str):
        raise ContractError("{} must be a string".format(path))
    if not value.strip():
        raise ContractError("{} must not be empty".format(path))
    if require_trimmed and value != value.strip():
        raise ContractError("{} must not have leading or trailing whitespace".format(path))
    if _contains_forbidden_control(value, allow_newlines):
        raise ContractError("{} contains a forbidden control or line-separator character".format(path))
    length = len(value)
    if length < minimum:
        raise ContractError(
            "{} must contain at least {} Unicode code point(s); got {}".format(
                path, minimum, length
            )
        )
    if maximum is not None and length > maximum:
        raise ContractError(
            "{} must contain at most {} Unicode code point(s); got {}".format(
                path, maximum, length
            )
        )
    return value


def _require_nullable_text(
    value: Any,
    path: str,
    *,
    minimum: int = 1,
    maximum: Optional[int] = None,
    allow_newlines: bool = False,
) -> Optional[str]:
    if value is None:
        return None
    return _require_text(
        value,
        path,
        minimum=minimum,
        maximum=maximum,
        allow_newlines=allow_newlines,
        require_trimmed=not allow_newlines,
    )


def _require_integer(value: Any, path: str, *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError("{} must be an integer".format(path))
    if value < minimum:
        raise ContractError("{} must be >= {}".format(path, minimum))
    return value


def _require_enum(value: Any, path: str, allowed: Iterable[str]) -> str:
    text = _require_text(value, path)
    allowed_set = set(allowed)
    if text not in allowed_set:
        raise ContractError(
            "{} must be one of {}; got {!r}".format(path, sorted(allowed_set), text)
        )
    return text


def _require_text_array(
    value: Any,
    path: str,
    *,
    minimum: int = 0,
    maximum: Optional[int] = None,
) -> List[str]:
    items = _require_list(value, path, minimum=minimum, maximum=maximum)
    texts = [_require_text(item, "{}[{}]".format(path, index)) for index, item in enumerate(items)]
    return texts


PERCENT_RE = re.compile(r"^(?:100|[0-9]{1,2})%$")


def _require_percentage(value: Any, path: str) -> int:
    text = _require_text(value, path)
    if not PERCENT_RE.fullmatch(text):
        raise ContractError("{} must be a percentage string from 0% to 100%".format(path))
    return int(text[:-1])


def validate_document(
    document: Any,
    *,
    expected_chapter_number: Optional[int] = None,
    expected_title: Optional[str] = None,
) -> Mapping[str, Any]:
    """Validate the exact Stage 2 JSON schema and cross-field invariants."""

    if isinstance(document, dict) and set(document) == {"error"}:
        reason = _require_text(document["error"], "$.error")
        raise ContractError("chapter-extractor returned an error: {}".format(reason))

    root = _require_object(document, "$", TOP_LEVEL_KEYS)
    chapter_number = _require_integer(root["chapter_number"], "$.chapter_number")
    if expected_chapter_number is not None and chapter_number != expected_chapter_number:
        raise ContractError(
            "$.chapter_number must equal expected chapter {}; got {}".format(
                expected_chapter_number, chapter_number
            )
        )

    title = _require_text(root["title"], "$.title")
    if expected_title is not None and title != expected_title:
        raise ContractError("$.title does not match the expected chapter title")

    # Python len(str) counts Unicode code points rather than UTF-8 bytes.  This
    # is the documented, portable interpretation of the 100-300 character gate.
    _require_text(root["summary"], "$.summary", minimum=100, maximum=300)
    _require_text_array(root["key_events"], "$.key_events", minimum=1)

    expansions = _require_list(
        root["key_information_expansion"],
        "$.key_information_expansion",
        minimum=1,
    )
    expansion_keys = {
        "key_information",
        "expansion",
        "technique",
        "reader_effect",
        "reuse_note",
    }
    for index, raw_expansion in enumerate(expansions):
        path = "$.key_information_expansion[{}]".format(index)
        expansion = _require_object(raw_expansion, path, expansion_keys)
        _require_text(expansion["key_information"], path + ".key_information")
        _require_text(expansion["expansion"], path + ".expansion")
        _require_enum(expansion["technique"], path + ".technique", TECHNIQUES)
        _require_enum(expansion["reader_effect"], path + ".reader_effect", READER_EFFECTS)
        _require_text(expansion["reuse_note"], path + ".reuse_note")

    formula = _require_object(
        root["chapter_formula"],
        "$.chapter_formula",
        {
            "emotion_flow",
            "rhythm_ratio",
            "structure_formula",
            "core_technique",
            "hook_and_foreshadowing",
        },
    )
    emotion_flow = _require_object(
        formula["emotion_flow"],
        "$.chapter_formula.emotion_flow",
        {"start", "build", "turn", "close"},
    )
    for key in ("start", "build", "turn", "close"):
        _require_text(emotion_flow[key], "$.chapter_formula.emotion_flow." + key)

    rhythm_ratio = _require_object(
        formula["rhythm_ratio"],
        "$.chapter_formula.rhythm_ratio",
        {"slow_setup", "fast_conflict", "payoff", "hook_space"},
    )
    ratio_total = sum(
        _require_percentage(
            rhythm_ratio[key], "$.chapter_formula.rhythm_ratio." + key
        )
        for key in ("slow_setup", "fast_conflict", "payoff", "hook_space")
    )
    if ratio_total != 100:
        raise ContractError("$.chapter_formula.rhythm_ratio values must sum to 100%")
    _require_text_array(
        formula["structure_formula"],
        "$.chapter_formula.structure_formula",
        minimum=1,
    )
    _require_text(formula["core_technique"], "$.chapter_formula.core_technique")
    _require_text(
        formula["hook_and_foreshadowing"],
        "$.chapter_formula.hook_and_foreshadowing",
    )

    characters = _require_list(root["characters"], "$.characters")
    character_keys = {"name", "importance", "aliases", "performance"}
    for index, raw_character in enumerate(characters):
        path = "$.characters[{}]".format(index)
        character = _require_object(raw_character, path, character_keys)
        _require_text(character["name"], path + ".name")
        _require_enum(character["importance"], path + ".importance", IMPORTANCE_LEVELS)
        _require_text_array(character["aliases"], path + ".aliases")
        _require_text(character["performance"], path + ".performance")

    plot_points = _require_list(root["plot_points"], "$.plot_points", minimum=10, maximum=40)
    plot_keys = {
        "id",
        "title",
        "event",
        "type",
        "characters",
        "location",
        "item",
        "time",
        "quote",
        "quote_locator",
        "themes",
        "tone",
    }
    cited_points = 0
    for index, raw_point in enumerate(plot_points):
        path = "$.plot_points[{}]".format(index)
        point = _require_object(raw_point, path, plot_keys)
        expected_id = "P{}".format(index + 1)
        point_id = _require_text(point["id"], path + ".id")
        if point_id != expected_id:
            raise ContractError(
                "{}.id must be {!r}; got {!r} (plot IDs must be continuous)".format(
                    path, expected_id, point_id
                )
            )
        point_title = _require_text(point["title"], path + ".title", maximum=15)
        event = _require_text(point["event"], path + ".event")
        if point_title == event:
            raise ContractError("{}.title must not duplicate event".format(path))
        _require_enum(point["type"], path + ".type", PLOT_TYPES)
        _require_text_array(point["characters"], path + ".characters")
        _require_nullable_text(point["location"], path + ".location")
        _require_nullable_text(point["item"], path + ".item")
        _require_nullable_text(point["time"], path + ".time")
        quote = _require_nullable_text(
            point["quote"],
            path + ".quote",
            maximum=400,
            allow_newlines=True,
        )
        locator = _require_nullable_text(
            point["quote_locator"],
            path + ".quote_locator",
            minimum=5,
            maximum=15,
        )
        if quote is not None and locator is not None:
            raise ContractError("{} may set quote or quote_locator, not both".format(path))
        if quote is not None or locator is not None:
            cited_points += 1

        themes = _require_list(point["themes"], path + ".themes", minimum=1, maximum=1)
        _require_enum(themes[0], path + ".themes[0]", THEMES)
        _require_enum(point["tone"], path + ".tone", TONES)

    if cited_points > 8:
        raise ContractError(
            "$.plot_points may contain quote/quote_locator on at most 8 points; got {}".format(
                cited_points
            )
        )

    return root


MARKDOWN_ESCAPES = set("\\`*_{}[]<>#|")


def _escape_markdown_piece(value: str) -> str:
    return "".join("\\" + character if character in MARKDOWN_ESCAPES else character for character in value)


def _markdown_inline(value: str) -> str:
    return "<br>".join(_escape_markdown_piece(line) for line in value.split("\n"))


def _nullable_display(value: Optional[str]) -> str:
    return "无" if value is None else _markdown_inline(value)


def _array_display(values: Sequence[str], separator: str = ",") -> str:
    if not values:
        return "无"
    return separator.join(_markdown_inline(value) for value in values)


def render_markdown(document: Mapping[str, Any]) -> str:
    """Render a validated document into the canonical Stage 2 Markdown."""

    formula = document["chapter_formula"]
    emotion_flow = formula["emotion_flow"]
    rhythm = formula["rhythm_ratio"]
    lines: List[str] = [
        "## 第{}章 {}".format(document["chapter_number"], _markdown_inline(document["title"])),
        "",
        "**概要**：{}".format(_markdown_inline(document["summary"])),
        "",
        "**关键事件**：",
    ]
    for index, event in enumerate(document["key_events"], start=1):
        lines.append("{}. {}".format(index, _markdown_inline(event)))

    lines.extend(
        [
            "",
            "**关键信息与扩写技法**：",
            "",
            "| 关键信息/剧情走向 | 原文如何扩写 | 扩写技法 | 对读者情绪的作用 | 可复用提醒 |",
            "|---|---|---|---|---|",
        ]
    )
    for item in document["key_information_expansion"]:
        lines.append(
            "| {} | {} | {} | {} | {} |".format(
                _markdown_inline(item["key_information"]),
                _markdown_inline(item["expansion"]),
                _markdown_inline(item["technique"]),
                _markdown_inline(item["reader_effect"]),
                _markdown_inline(item["reuse_note"]),
            )
        )

    structure = " + ".join(
        _markdown_inline(value) for value in formula["structure_formula"]
    )
    lines.extend(
        [
            "",
            "**逐章写法公式**：",
            "",
            "- **情绪流向**：起：{} → 承：{} → 转：{} → 合：{}".format(
                _markdown_inline(emotion_flow["start"]),
                _markdown_inline(emotion_flow["build"]),
                _markdown_inline(emotion_flow["turn"]),
                _markdown_inline(emotion_flow["close"]),
            ),
            "- **节奏配比**：慢铺垫 {} / 快冲突 {} / 爽点爆发 {} / 悬念留白 {}".format(
                rhythm["slow_setup"],
                rhythm["fast_conflict"],
                rhythm["payoff"],
                rhythm["hook_space"],
            ),
            "- **本章结构公式**：{}".format(structure),
            "- **本章核心技巧**：{}".format(
                _markdown_inline(formula["core_technique"])
            ),
            "- **卡点与伏笔**：{}".format(
                _markdown_inline(formula["hook_and_foreshadowing"])
            ),
            "",
            "**出场人物**：",
            "",
            "| 角色 | 本章重要性 | 别名 | 本章表现 |",
            "|------|-----------|------|----------|",
        ]
    )
    for character in document["characters"]:
        lines.append(
            "| {} | {} | {} | {} |".format(
                _markdown_inline(character["name"]),
                character["importance"],
                _array_display(character["aliases"], "，"),
                _markdown_inline(character["performance"]),
            )
        )

    lines.extend(["", "**情节点**：", ""])
    for point in document["plot_points"]:
        lines.append(
            "{} **{}**：类型{} | {} | 涉及{} | 地点{} | 物品{} | 时间{}".format(
                point["id"],
                _markdown_inline(point["title"]),
                point["type"],
                _markdown_inline(point["event"]),
                _array_display(point["characters"]),
                _nullable_display(point["location"]),
                _nullable_display(point["item"]),
                _nullable_display(point["time"]),
            )
        )
        if point["quote"] is not None:
            lines.extend(point["quote"].split("\n"))
        elif point["quote_locator"] is not None:
            lines.append("原文定位：{}".format(_markdown_inline(point["quote_locator"])))
        lines.append("主题标签{} | 基调：{}".format(point["themes"][0], point["tone"]))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def atomic_write_text(path: Path, text: str) -> None:
    """Publish ``text`` atomically without exposing a partial Markdown file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    target_mode = 0o644
    if path.exists() and path.is_file():
        target_mode = stat.S_IMODE(path.stat().st_mode)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=".{}.".format(path.name),
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        fchmod = getattr(os, "fchmod", None)
        if fchmod is not None:
            fchmod(descriptor, target_mode)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(path))
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def _read_input(argument: str) -> str:
    if argument == "-":
        return sys.stdin.read()
    return Path(argument).read_text(encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="chapter-extractor JSON path, or - for stdin")
    parser.add_argument("--output", type=Path, help="canonical chapter Markdown destination")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="validate without rendering or touching --output",
    )
    parser.add_argument(
        "--expect-chapter-number",
        type=int,
        help="reject a valid payload for a different chapter",
    )
    parser.add_argument(
        "--expect-title",
        help="reject a valid payload whose title differs from the requested chapter",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.check_only and args.output is None:
        parser.error("--output is required unless --check-only is used")
    if args.expect_chapter_number is not None and args.expect_chapter_number < 1:
        parser.error("--expect-chapter-number must be >= 1")
    if (
        not args.check_only
        and args.input != "-"
        and Path(args.input).resolve() == args.output.resolve()
    ):
        parser.error("--input and --output must be different files")

    try:
        raw_text = _read_input(args.input)
        document = validate_document(
            parse_json_text(raw_text),
            expected_chapter_number=args.expect_chapter_number,
            expected_title=args.expect_title,
        )
        if args.check_only:
            print("OK: chapter {} JSON contract valid".format(document["chapter_number"]))
            return 0
        markdown = render_markdown(document)
        atomic_write_text(args.output, markdown)
        print("OK: wrote {}".format(args.output))
        return 0
    except (ContractError, OSError, UnicodeError) as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
