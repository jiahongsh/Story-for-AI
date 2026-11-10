#!/usr/bin/env python3
"""Qualify, compile, bind, and resolve Chinese prose method branches."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
STANDARD_BRANCH = "A-standard"
DISTILLED_BRANCH = "B-distilled"
CORPUS_TYPES = {"shelf-corpus", "author-corpus", "single-work-pilot"}
AUTHOR_MODES = {"author-mechanics", "authorized-fidelity"}
SPLITS = {"train", "calibration", "holdout"}
REQUIRED_SCENE_FUNCTIONS = {"opening", "escalation", "turning-point", "aftermath"}
RULE_DIMENSIONS = {
    "sentence-rhythm",
    "paragraph-breathing",
    "dialogue",
    "narrative-distance",
    "sensory-selection",
    "emotion-landing",
    "figurative-language",
    "information-release",
    "transition",
    "scene-engine",
    "chapter-ending",
}
AUTHOR_FEATURE_FAMILIES = {
    "sentence-rhythm",
    "paragraph-breathing",
    "dialogue-ratio",
    "dialogue-tags",
    "narrative-distance",
    "sensory-selection",
    "emotion-landing",
    "figurative-density",
    "information-release",
    "transition",
    "chapter-ending",
}
COMMON_EVALUATIONS = {
    "holdout-style-separation",
    "content-preservation",
    "chinese-naturalness",
    "phrase-overlap",
    "plot-independence",
}
RIGHTS_BASES = {"self-authored", "express-license", "public-domain"}
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
SHA_PATTERN = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_RAW_KEYS = {
    "source_text",
    "source_prose",
    "raw_text",
    "original_text",
    "quote",
    "quotes",
    "excerpt",
    "excerpts",
    "anchor_excerpt",
    "sample_text",
    "原文",
    "原文片段",
    "引文",
    "摘录",
    "锚点片段",
}


class MethodError(RuntimeError):
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


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(encoded)


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    shutil.copyfile(source, temporary)
    temporary.replace(target)


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MethodError(f"{label}不存在: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MethodError(f"{label}不是有效 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise MethodError(f"{label}顶层必须是 JSON object")
    return value


def ensure_directory(path: str, label: str) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_dir():
        raise MethodError(f"{label}不存在: {resolved}")
    return resolved


def ensure_identifier(value: Any, label: str, errors: list[str]) -> str:
    if not isinstance(value, str) or ID_PATTERN.fullmatch(value) is None:
        errors.append(f"{label}必须是 1-96 位字母、数字、点、下划线或连字符")
        return ""
    return value


def check_exact_keys(value: dict[str, Any], allowed: set[str], label: str, errors: list[str]) -> None:
    extra = sorted(set(value) - allowed)
    if extra:
        errors.append(f"{label}含未声明字段: {', '.join(extra)}")


def scan_raw_fields(value: Any, label: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in FORBIDDEN_RAW_KEYS or str(key).strip() in FORBIDDEN_RAW_KEYS:
                errors.append(f"{label}不得保存原文/引文类字段: {key}")
            scan_raw_fields(child, f"{label}.{key}", errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            scan_raw_fields(child, f"{label}[{index}]", errors)


def validate_sha(value: Any, label: str, errors: list[str]) -> str:
    if not isinstance(value, str) or SHA_PATTERN.fullmatch(value) is None:
        errors.append(f"{label}必须是 64 位小写 sha256")
        return ""
    return value


def validate_string_list(
    value: Any,
    label: str,
    errors: list[str],
    *,
    minimum: int = 1,
    maximum: int = 20,
    item_max: int = 40,
) -> list[str]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        errors.append(f"{label}必须包含 {minimum}-{maximum} 项")
        return []
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip() or len(item.strip()) > item_max:
            errors.append(f"{label}[{index}]必须是 1-{item_max} 字的非空字符串")
            continue
        result.append(item.strip())
    if len(result) != len(set(result)):
        errors.append(f"{label}不得重复")
    return result


def validate_rule(
    rule: Any,
    label: str,
    errors: list[str],
    *,
    author_overlay: bool = False,
) -> dict[str, Any] | None:
    if not isinstance(rule, dict):
        errors.append(f"{label}必须是 object")
        return None
    allowed = {"rule_key", "dimension", "instruction", "applies_to", "avoid", "priority"}
    allowed |= {"support_work_ids", "control_author_ids"} if author_overlay else {"evidence_locators"}
    check_exact_keys(rule, allowed, label, errors)
    scan_raw_fields(rule, label, errors)
    key = ensure_identifier(rule.get("rule_key"), f"{label}.rule_key", errors)
    dimension = rule.get("dimension")
    if dimension not in RULE_DIMENSIONS:
        errors.append(f"{label}.dimension 不在允许集合")
    instruction = rule.get("instruction")
    if not isinstance(instruction, str) or not 4 <= len(instruction.strip()) <= 240 or "\n" in instruction:
        errors.append(f"{label}.instruction 必须是 4-240 字单行抽象规则")
        instruction = ""
    avoid = rule.get("avoid", "")
    if not isinstance(avoid, str) or len(avoid.strip()) > 160 or "\n" in avoid:
        errors.append(f"{label}.avoid 必须是不超过 160 字的单行说明")
        avoid = ""
    applies_to = validate_string_list(rule.get("applies_to"), f"{label}.applies_to", errors, maximum=8, item_max=24)
    priority = rule.get("priority", 50)
    if not isinstance(priority, int) or isinstance(priority, bool) or not 1 <= priority <= 100:
        errors.append(f"{label}.priority 必须是 1-100 的整数")
        priority = 50
    normalized: dict[str, Any] = {
        "rule_key": key,
        "dimension": dimension,
        "instruction": instruction.strip() if isinstance(instruction, str) else "",
        "applies_to": applies_to,
        "avoid": avoid.strip() if isinstance(avoid, str) else "",
        "priority": priority,
    }
    if author_overlay:
        normalized["support_work_ids"] = validate_string_list(
            rule.get("support_work_ids"), f"{label}.support_work_ids", errors, minimum=3, maximum=50, item_max=96
        )
        normalized["control_author_ids"] = validate_string_list(
            rule.get("control_author_ids"), f"{label}.control_author_ids", errors, minimum=2, maximum=20, item_max=96
        )
    else:
        locators = rule.get("evidence_locators")
        if not isinstance(locators, list) or not 1 <= len(locators) <= 12:
            errors.append(f"{label}.evidence_locators 必须包含 1-12 个定位器")
            locators = []
        normalized_locators: list[dict[str, Any]] = []
        for index, locator in enumerate(locators):
            locator_label = f"{label}.evidence_locators[{index}]"
            if not isinstance(locator, dict):
                errors.append(f"{locator_label}必须是 object")
                continue
            check_exact_keys(locator, {"chapter", "scene", "paragraph"}, locator_label, errors)
            chapter = locator.get("chapter")
            if not isinstance(chapter, int) or isinstance(chapter, bool) or chapter < 1:
                errors.append(f"{locator_label}.chapter 必须是正整数")
            scene = locator.get("scene")
            paragraph = locator.get("paragraph")
            if scene is not None and (not isinstance(scene, str) or not scene.strip() or len(scene) > 40):
                errors.append(f"{locator_label}.scene 必须是不超过 40 字的定位名")
            if paragraph is not None and (not isinstance(paragraph, str) or not paragraph.strip() or len(paragraph) > 20):
                errors.append(f"{locator_label}.paragraph 必须是不超过 20 字的定位符")
            if scene is None and paragraph is None:
                errors.append(f"{locator_label}至少提供 scene 或 paragraph")
            normalized_locators.append({"chapter": chapter, "scene": scene, "paragraph": paragraph})
        normalized["evidence_locators"] = normalized_locators
    return normalized


def validate_work_pack(path: Path, expected: dict[str, Any], errors: list[str]) -> dict[str, Any] | None:
    label = f"作品机制包 {path.name}"
    pack = load_json(path, label)
    scan_raw_fields(pack, label, errors)
    check_exact_keys(
        pack,
        {
            "schema_version",
            "work_id",
            "source_sha256",
            "split",
            "sampled_chapter_count",
            "sampled_scene_count",
            "scene_functions",
            "rules",
        },
        label,
        errors,
    )
    if pack.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{label}.schema_version 必须为 {SCHEMA_VERSION}")
    if pack.get("work_id") != expected.get("work_id"):
        errors.append(f"{label}.work_id 与语料清单不一致")
    if pack.get("source_sha256") != expected.get("source_sha256"):
        errors.append(f"{label}.source_sha256 与语料清单不一致")
    if pack.get("split") != expected.get("split"):
        errors.append(f"{label}.split 与语料清单不一致")
    chapters = pack.get("sampled_chapter_count")
    scenes = pack.get("sampled_scene_count")
    if not isinstance(chapters, int) or isinstance(chapters, bool) or chapters < 3:
        errors.append(f"{label}.sampled_chapter_count 至少为 3")
    if not isinstance(scenes, int) or isinstance(scenes, bool) or scenes < 6:
        errors.append(f"{label}.sampled_scene_count 至少为 6")
    functions = set(validate_string_list(pack.get("scene_functions"), f"{label}.scene_functions", errors, maximum=20))
    unknown_functions = functions - REQUIRED_SCENE_FUNCTIONS
    if unknown_functions:
        errors.append(f"{label}.scene_functions 含未知值: {', '.join(sorted(unknown_functions))}")
    raw_rules = pack.get("rules")
    if not isinstance(raw_rules, list) or not 2 <= len(raw_rules) <= 80:
        errors.append(f"{label}.rules 必须包含 2-80 条")
        raw_rules = []
    rules: list[dict[str, Any]] = []
    for index, raw_rule in enumerate(raw_rules):
        normalized = validate_rule(raw_rule, f"{label}.rules[{index}]", errors)
        if normalized is not None:
            rules.append(normalized)
    keys = [rule.get("rule_key") for rule in rules]
    if len(keys) != len(set(keys)):
        errors.append(f"{label}.rules 的 rule_key 不得重复")
    return {**pack, "scene_functions": sorted(functions), "rules": rules, "_path": path}


def validate_author_pack(
    path: Path,
    manifest: dict[str, Any],
    works: list[dict[str, Any]],
    errors: list[str],
) -> dict[str, Any] | None:
    label = "作者文风包"
    pack = load_json(path, label)
    scan_raw_fields(pack, label, errors)
    check_exact_keys(
        pack,
        {
            "schema_version",
            "target_author_id",
            "mode",
            "feature_families",
            "rules",
            "evaluations",
            "source_names_visible_to_writer",
            "distinctive_expression_allowed",
        },
        label,
        errors,
    )
    if pack.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{label}.schema_version 必须为 {SCHEMA_VERSION}")
    target_authors = {item.get("author_id") for item in works}
    target_author = next(iter(target_authors)) if len(target_authors) == 1 else None
    if pack.get("target_author_id") != target_author:
        errors.append(f"{label}.target_author_id 与语料作者不一致")
    mode = manifest.get("author_style_mode")
    if pack.get("mode") != mode:
        errors.append(f"{label}.mode 与语料清单不一致")
    families = set(
        validate_string_list(pack.get("feature_families"), f"{label}.feature_families", errors, minimum=11, maximum=20)
    )
    missing_families = AUTHOR_FEATURE_FAMILIES - families
    if missing_families:
        errors.append(f"{label}缺少特征族: {', '.join(sorted(missing_families))}")
    evaluations = pack.get("evaluations")
    if not isinstance(evaluations, dict):
        errors.append(f"{label}.evaluations 必须是 object")
        evaluations = {}
    required_evaluations = set(COMMON_EVALUATIONS)
    required_evaluations.add("source-obscurity" if mode == "author-mechanics" else "blind-attribution")
    for key in sorted(required_evaluations):
        if evaluations.get(key) != "passed":
            errors.append(f"{label}.evaluations.{key} 必须为 passed")
    if mode == "author-mechanics" and pack.get("source_names_visible_to_writer") is not False:
        errors.append(f"{label}在 author-mechanics 模式必须隐藏来源名称")
    if pack.get("distinctive_expression_allowed") is not False:
        errors.append(f"{label}不得允许标志性表达进入运行时")
    raw_rules = pack.get("rules")
    if not isinstance(raw_rules, list) or not 2 <= len(raw_rules) <= 60:
        errors.append(f"{label}.rules 必须包含 2-60 条")
        raw_rules = []
    rules: list[dict[str, Any]] = []
    known_work_ids = {str(item.get("work_id")) for item in works}
    controls = {str(item.get("author_id")) for item in manifest.get("control_authors", []) if isinstance(item, dict)}
    split_by_work = {str(item.get("work_id")): item.get("split") for item in works}
    for index, raw_rule in enumerate(raw_rules):
        rule = validate_rule(raw_rule, f"{label}.rules[{index}]", errors, author_overlay=True)
        if rule is None:
            continue
        support = set(rule.get("support_work_ids", []))
        if not support <= known_work_ids:
            errors.append(f"{label}.rules[{index}] 引用了未知作品")
        if {split_by_work.get(work_id) for work_id in support} != SPLITS:
            errors.append(f"{label}.rules[{index}] 必须同时经过 train/calibration/holdout 支撑")
        control_ids = set(rule.get("control_author_ids", []))
        if not control_ids <= controls or len(control_ids) < 2:
            errors.append(f"{label}.rules[{index}] 必须由至少两个登记控制作者完成区分")
        rules.append(rule)
    return {**pack, "rules": rules, "evaluations": evaluations, "_path": path}


def load_corpus(corpus: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any] | None, list[str], list[str]]:
    manifest_path = corpus / "corpus-manifest.json"
    manifest = load_json(manifest_path, "语料清单")
    errors: list[str] = []
    warnings: list[str] = []
    scan_raw_fields(manifest, "语料清单", errors)
    check_exact_keys(
        manifest,
        {
            "schema_version",
            "corpus_id",
            "corpus_type",
            "author_style_mode",
            "authorization",
            "works",
            "control_authors",
            "scene_function_coverage",
            "anti_copy",
            "control_separation_confirmed",
            "forward_test_plan",
        },
        "语料清单",
        errors,
    )
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"语料清单.schema_version 必须为 {SCHEMA_VERSION}")
    ensure_identifier(manifest.get("corpus_id"), "语料清单.corpus_id", errors)
    corpus_type = manifest.get("corpus_type")
    if corpus_type not in CORPUS_TYPES:
        errors.append("语料清单.corpus_type 无效")
    mode = manifest.get("author_style_mode")
    if corpus_type == "author-corpus" and mode not in AUTHOR_MODES:
        errors.append("author-corpus 必须声明 author_style_mode")
    if corpus_type != "author-corpus" and mode is not None:
        errors.append("只有 author-corpus 可以声明 author_style_mode")
    authorization = manifest.get("authorization")
    if not isinstance(authorization, dict):
        errors.append("语料清单.authorization 必须是 object")
        authorization = {}
    if authorization.get("lawful_access_confirmed") is not True:
        errors.append("必须确认语料合法持有或有权使用")
    rights_basis = authorization.get("rights_basis")
    if not isinstance(rights_basis, str) or not rights_basis.strip():
        errors.append("语料清单.authorization.rights_basis 不能为空")
    if mode == "authorized-fidelity":
        if rights_basis not in RIGHTS_BASES:
            errors.append("authorized-fidelity 只接受本人作品、明确授权或公版作品")
        if authorization.get("authorized_fidelity_confirmed") is not True:
            errors.append("authorized-fidelity 必须有明确高保真授权确认")
    works_raw = manifest.get("works")
    if not isinstance(works_raw, list) or not works_raw:
        errors.append("语料清单.works 不能为空")
        works_raw = []
    works: list[dict[str, Any]] = []
    for index, raw_work in enumerate(works_raw):
        label = f"语料清单.works[{index}]"
        if not isinstance(raw_work, dict):
            errors.append(f"{label}必须是 object")
            continue
        check_exact_keys(
            raw_work,
            {"work_id", "title", "author_id", "series_id", "char_count", "chapter_count", "split", "source_sha256"},
            label,
            errors,
        )
        work_id = ensure_identifier(raw_work.get("work_id"), f"{label}.work_id", errors)
        author_id = ensure_identifier(raw_work.get("author_id"), f"{label}.author_id", errors)
        if "series_id" not in raw_work:
            errors.append(f"{label}.series_id 必须显式填写；独立作品用 null")
        series_id = raw_work.get("series_id")
        if series_id is not None:
            series_id = ensure_identifier(series_id, f"{label}.series_id", errors)
        title = raw_work.get("title")
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 120:
            errors.append(f"{label}.title 必须是 1-120 字")
        char_count = raw_work.get("char_count")
        chapter_count = raw_work.get("chapter_count")
        if not isinstance(char_count, int) or isinstance(char_count, bool) or char_count < 10000:
            errors.append(f"{label}.char_count 至少为 10000")
        if not isinstance(chapter_count, int) or isinstance(chapter_count, bool) or chapter_count < 3:
            errors.append(f"{label}.chapter_count 至少为 3")
        split = raw_work.get("split")
        if split not in SPLITS:
            errors.append(f"{label}.split 必须是 train/calibration/holdout")
        source_sha = validate_sha(raw_work.get("source_sha256"), f"{label}.source_sha256", errors)
        works.append(
            {
                "work_id": work_id,
                "title": title.strip() if isinstance(title, str) else "",
                "author_id": author_id,
                "series_id": series_id,
                "char_count": char_count,
                "chapter_count": chapter_count,
                "split": split,
                "source_sha256": source_sha,
            }
        )
    work_ids = [item["work_id"] for item in works]
    if len(work_ids) != len(set(work_ids)):
        errors.append("语料清单.work_id 不得重复")
    if corpus_type == "single-work-pilot":
        warnings.append("single-work-pilot 只能探索，不能激活可复用写作方法")
    elif len(works) < 3:
        errors.append("可复用蒸馏语料至少需要 3 部作品")
    if corpus_type != "single-work-pilot" and {item["split"] for item in works} != SPLITS:
        errors.append("语料必须同时保留 train/calibration/holdout 三个集合")
    total_chars = sum(item["char_count"] for item in works if isinstance(item.get("char_count"), int))
    if corpus_type != "single-work-pilot" and total_chars < 50000:
        errors.append("可复用蒸馏语料总量至少为 50000 个中文字符")
    authors = {item["author_id"] for item in works}
    if corpus_type == "shelf-corpus" and len(authors) < 3:
        errors.append("shelf-corpus 至少覆盖 3 位作者")
    if corpus_type == "author-corpus" and len(authors) != 1:
        errors.append("author-corpus 的作品必须来自同一目标作者")
    if corpus_type == "author-corpus":
        series_buckets = {
            item["series_id"] if item.get("series_id") is not None else f"standalone:{item['work_id']}"
            for item in works
        }
        if len(series_buckets) < 2:
            errors.append("author-corpus 不能只由同一系列作品构成；至少覆盖两个系列或独立作品桶")
    controls_raw = manifest.get("control_authors", [])
    if not isinstance(controls_raw, list):
        errors.append("语料清单.control_authors 必须是数组")
        controls_raw = []
    controls: list[dict[str, Any]] = []
    for index, raw_control in enumerate(controls_raw):
        label = f"语料清单.control_authors[{index}]"
        if not isinstance(raw_control, dict):
            errors.append(f"{label}必须是 object")
            continue
        check_exact_keys(raw_control, {"author_id", "work_count", "char_count"}, label, errors)
        author_id = ensure_identifier(raw_control.get("author_id"), f"{label}.author_id", errors)
        work_count = raw_control.get("work_count")
        char_count = raw_control.get("char_count")
        if not isinstance(work_count, int) or isinstance(work_count, bool) or work_count < 1:
            errors.append(f"{label}.work_count 至少为 1")
        if not isinstance(char_count, int) or isinstance(char_count, bool) or char_count < 10000:
            errors.append(f"{label}.char_count 至少为 10000")
        controls.append({"author_id": author_id, "work_count": work_count, "char_count": char_count})
    if corpus_type == "author-corpus":
        if len({item["author_id"] for item in controls}) < 2:
            errors.append("author-corpus 至少需要 2 位邻近控制作者")
        if manifest.get("control_separation_confirmed") is not True:
            errors.append("author-corpus 必须完成目标作者与控制作者的区分检查")
    coverage = set(
        validate_string_list(
            manifest.get("scene_function_coverage"),
            "语料清单.scene_function_coverage",
            errors,
            minimum=4,
            maximum=20,
        )
    )
    if not REQUIRED_SCENE_FUNCTIONS <= coverage:
        errors.append("语料清单缺少 opening/escalation/turning-point/aftermath 场景覆盖")
    anti_copy = manifest.get("anti_copy")
    if not isinstance(anti_copy, dict):
        errors.append("语料清单.anti_copy 必须是 object")
        anti_copy = {}
    required_false = {"store_source_text", "compile_distinctive_expressions"}
    required_true = {"phrase_overlap_gate", "plot_independence_gate"}
    for key in required_false:
        if anti_copy.get(key) is not False:
            errors.append(f"语料清单.anti_copy.{key} 必须为 false")
    for key in required_true:
        if anti_copy.get(key) is not True:
            errors.append(f"语料清单.anti_copy.{key} 必须为 true")
    plan = manifest.get("forward_test_plan")
    if not isinstance(plan, dict):
        errors.append("语料清单.forward_test_plan 必须是 object")
    else:
        if plan.get("compare_against") != STANDARD_BRANCH:
            errors.append(f"前向测试必须与 {STANDARD_BRANCH} 基线比较")
        if not isinstance(plan.get("minimum_samples"), int) or plan.get("minimum_samples", 0) < 6:
            errors.append("前向测试至少需要 6 个隔离样本")
        if not isinstance(plan.get("blind_reviewers"), int) or plan.get("blind_reviewers", 0) < 2:
            errors.append("前向测试至少需要 2 位独立盲审者")
    pack_dir = corpus / "work-mechanics-packs"
    if not pack_dir.is_dir():
        errors.append(f"缺少作品机制包目录: {pack_dir}")
    pack_paths = sorted(path for path in pack_dir.glob("*.json") if path.is_file()) if pack_dir.is_dir() else []
    pack_by_work: dict[str, Path] = {}
    for path in pack_paths:
        try:
            raw = load_json(path, f"作品机制包 {path.name}")
        except MethodError as exc:
            errors.append(str(exc))
            continue
        work_id = raw.get("work_id")
        if isinstance(work_id, str):
            if work_id in pack_by_work:
                errors.append(f"作品 {work_id} 存在多个机制包")
            pack_by_work[work_id] = path
    packs: list[dict[str, Any]] = []
    for work in works:
        path = pack_by_work.get(work["work_id"])
        if path is None:
            errors.append(f"作品 {work['work_id']} 缺少机制包")
            continue
        pack = validate_work_pack(path, work, errors)
        if pack is not None:
            packs.append(pack)
    unknown_packs = sorted(set(pack_by_work) - set(work_ids))
    if unknown_packs:
        errors.append(f"机制包引用了未登记作品: {', '.join(unknown_packs)}")
    pack_coverage = {item for pack in packs for item in pack.get("scene_functions", [])}
    if corpus_type != "single-work-pilot" and not REQUIRED_SCENE_FUNCTIONS <= pack_coverage:
        errors.append("作品机制包合计未覆盖四类关键场景功能")
    author_pack: dict[str, Any] | None = None
    if corpus_type == "author-corpus":
        author_path = corpus / "author-style-pack.json"
        if not author_path.is_file():
            errors.append(f"author-corpus 缺少作者文风包: {author_path}")
        else:
            author_pack = validate_author_pack(author_path, manifest, works, errors)
    return manifest, packs, author_pack, errors, warnings


def input_inventory(corpus: Path, manifest: dict[str, Any], packs: list[dict[str, Any]], author_pack: dict[str, Any] | None) -> list[dict[str, str]]:
    paths = [corpus / "corpus-manifest.json"]
    paths.extend(pack["_path"] for pack in packs)
    if author_pack is not None:
        paths.append(author_pack["_path"])
    return [
        {"name": path.relative_to(corpus).as_posix(), "sha256": sha256_file(path)}
        for path in sorted(paths, key=lambda item: item.as_posix())
    ]


def qualification_report(corpus: Path) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any] | None]:
    manifest, packs, author_pack, errors, warnings = load_corpus(corpus)
    corpus_type = manifest.get("corpus_type")
    if corpus_type == "single-work-pilot":
        errors.append("single-work-pilot 不得编译或绑定为可复用写作方法")
    inventory = input_inventory(corpus, manifest, packs, author_pack)
    fingerprint = canonical_hash(inventory)
    report = {
        "schema_version": SCHEMA_VERSION,
        "corpus_id": manifest.get("corpus_id"),
        "corpus_type": corpus_type,
        "author_style_mode": manifest.get("author_style_mode"),
        "status": "qualified" if not errors else "unqualified",
        "checked_at": utc_now(),
        "corpus_fingerprint": fingerprint,
        "inputs": inventory,
        "errors": errors,
        "warnings": warnings,
        "gate_summary": {
            "works": len(manifest.get("works", [])) if isinstance(manifest.get("works"), list) else 0,
            "mechanics_packs": len(packs),
            "splits": sorted({item.get("split") for item in manifest.get("works", []) if isinstance(item, dict)}),
            "scene_functions": sorted({item for pack in packs for item in pack.get("scene_functions", [])}),
            "author_pack": author_pack is not None,
        },
    }
    return report, manifest, packs, author_pack


def validate_fresh_decision(corpus: Path) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any] | None]:
    decision = load_json(corpus / "distillability-decision.json", "可蒸馏性判定")
    current, manifest, packs, author_pack = qualification_report(corpus)
    if decision.get("status") != "qualified":
        raise MethodError("语料尚未通过可蒸馏性判定")
    if current.get("status") != "qualified":
        raise MethodError("语料当前已不再满足可蒸馏条件: " + "; ".join(current.get("errors", [])))
    if decision.get("corpus_fingerprint") != current.get("corpus_fingerprint"):
        raise MethodError("可蒸馏性判定已过期；语料或机制包发生变化，请重新 qualify")
    return current, manifest, packs, author_pack


def compile_rules(
    manifest: dict[str, Any],
    packs: list[dict[str, Any]],
    author_pack: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    works = {str(item.get("work_id")): item for item in manifest.get("works", []) if isinstance(item, dict)}
    grouped: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for pack in packs:
        work = works.get(str(pack.get("work_id")), {})
        for rule in pack.get("rules", []):
            grouped.setdefault(str(rule.get("rule_key")), []).append((rule, work))
    compiled: list[dict[str, Any]] = []
    for key, occurrences in sorted(grouped.items()):
        signatures = {
            (
                item[0].get("dimension"),
                item[0].get("instruction"),
                tuple(item[0].get("applies_to", [])),
                item[0].get("avoid", ""),
            )
            for item in occurrences
        }
        if len(signatures) != 1:
            continue
        support_works = {str(item[1].get("work_id")) for item in occurrences}
        support_splits = {item[1].get("split") for item in occurrences}
        support_authors = {str(item[1].get("author_id")) for item in occurrences}
        if support_splits != SPLITS or len(support_works) < 3:
            continue
        if manifest.get("corpus_type") == "shelf-corpus" and len(support_authors) < 3:
            continue
        rule = occurrences[0][0]
        compiled.append(
            {
                "rule_key": key,
                "layer": "corpus-core",
                "dimension": rule["dimension"],
                "instruction": rule["instruction"],
                "applies_to": rule["applies_to"],
                "avoid": rule.get("avoid", ""),
                "priority": rule.get("priority", 50),
                "support_work_count": len(support_works),
                "support_splits": sorted(support_splits),
            }
        )
    if author_pack is not None:
        for rule in author_pack.get("rules", []):
            compiled.append(
                {
                    "rule_key": rule["rule_key"],
                    "layer": "author-overlay",
                    "dimension": rule["dimension"],
                    "instruction": rule["instruction"],
                    "applies_to": rule["applies_to"],
                    "avoid": rule.get("avoid", ""),
                    "priority": rule.get("priority", 50),
                    "support_work_count": len(set(rule.get("support_work_ids", []))),
                    "support_splits": sorted(SPLITS),
                }
            )
    unique: dict[str, dict[str, Any]] = {}
    for rule in compiled:
        if rule["rule_key"] in unique:
            raise MethodError(f"编译规则 key 冲突: {rule['rule_key']}")
        unique[rule["rule_key"]] = rule
    output = sorted(unique.values(), key=lambda item: (-int(item.get("priority", 50)), item["rule_key"]))
    if len(output) < 4:
        raise MethodError("跨 train/calibration/holdout 稳定成立的抽象规则不足 4 条，不能编译")
    return output


def compiled_paths(directory: Path) -> tuple[Path, Path, Path]:
    return directory / "compiled-method.json", directory / "compiled-manifest.json", directory / "forward-test.json"


def validate_compiled(directory: Path, *, require_forward: bool) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    method_path, manifest_path, forward_path = compiled_paths(directory)
    method = load_json(method_path, "编译方法")
    compiled_manifest = load_json(manifest_path, "编译清单")
    if method.get("schema_version") != SCHEMA_VERSION or compiled_manifest.get("schema_version") != SCHEMA_VERSION:
        raise MethodError("不支持的编译方法版本")
    if method.get("method_branch") != DISTILLED_BRANCH:
        raise MethodError("编译方法不是 B-distilled 分支")
    if compiled_manifest.get("method_sha256") != sha256_file(method_path):
        raise MethodError("编译方法与清单哈希不一致")
    if compiled_manifest.get("method_id") != method.get("method_id"):
        raise MethodError("编译方法与清单 method_id 不一致")
    scan_errors: list[str] = []
    scan_raw_fields(method, "编译方法", scan_errors)
    if scan_errors:
        raise MethodError("; ".join(scan_errors))
    rules = method.get("rules")
    if not isinstance(rules, list) or len(rules) < 4:
        raise MethodError("编译方法有效规则不足 4 条")
    forward: dict[str, Any] | None = None
    if require_forward:
        forward = load_json(forward_path, "前向盲测结果")
        errors: list[str] = []
        check_exact_keys(
            forward,
            {
                "schema_version",
                "method_sha256",
                "test_id",
                "sample_count",
                "blind_reviewer_count",
                "baseline",
                "candidate",
                "metrics",
                "status",
                "review_completed",
            },
            "前向盲测结果",
            errors,
        )
        if forward.get("schema_version") != SCHEMA_VERSION:
            errors.append("前向盲测结果.schema_version 无效")
        if forward.get("method_sha256") != sha256_file(method_path):
            errors.append("前向盲测结果未绑定当前编译方法")
        if forward.get("baseline") != STANDARD_BRANCH or forward.get("candidate") != DISTILLED_BRANCH:
            errors.append("前向盲测必须比较 A-standard 与 B-distilled")
        if not isinstance(forward.get("sample_count"), int) or forward.get("sample_count", 0) < 6:
            errors.append("前向盲测至少需要 6 个样本")
        if not isinstance(forward.get("blind_reviewer_count"), int) or forward.get("blind_reviewer_count", 0) < 2:
            errors.append("前向盲测至少需要 2 位独立盲审者")
        metrics = forward.get("metrics")
        if not isinstance(metrics, dict):
            errors.append("前向盲测 metrics 必须是 object")
            metrics = {}
        else:
            check_exact_keys(
                metrics,
                {
                    "content_preservation_pass",
                    "chinese_naturalness_pass",
                    "phrase_overlap_pass",
                    "plot_independence_pass",
                    "b_preference_rate",
                },
                "前向盲测结果.metrics",
                errors,
            )
        for key in ("content_preservation_pass", "chinese_naturalness_pass", "phrase_overlap_pass", "plot_independence_pass"):
            if metrics.get(key) is not True:
                errors.append(f"前向盲测 metrics.{key} 必须通过")
        preference = metrics.get("b_preference_rate")
        if not isinstance(preference, (int, float)) or isinstance(preference, bool) or preference < 0.55 or preference > 1:
            errors.append("B 分支盲审偏好率必须在 0.55-1.0")
        if forward.get("review_completed") is not True or forward.get("status") != "passed":
            errors.append("前向盲测尚未完成或未通过")
        if errors:
            raise MethodError("; ".join(errors))
    return method, compiled_manifest, forward


def project_config_path(project: Path) -> Path:
    return project / "设定" / "写作方法.json"


def load_project_config(project: Path) -> tuple[dict[str, Any], bool]:
    path = project_config_path(project)
    if not path.is_file():
        return {"schema_version": SCHEMA_VERSION, "method_branch": STANDARD_BRANCH, "implicit_default": True}, True
    config = load_json(path, "写作方法配置")
    if config.get("schema_version") != SCHEMA_VERSION:
        raise MethodError("写作方法配置版本不受支持")
    branch = config.get("method_branch")
    if branch not in {STANDARD_BRANCH, DISTILLED_BRANCH}:
        raise MethodError("写作方法配置 method_branch 必须是 A-standard 或 B-distilled")
    return config, False


def check_project(project: Path) -> dict[str, Any]:
    config, implicit = load_project_config(project)
    branch = config["method_branch"]
    if branch == STANDARD_BRANCH:
        return {
            "status": "ready",
            "method_branch": STANDARD_BRANCH,
            "implicit_default": implicit,
            "runtime_strategy": "existing-style-recall",
            "read_benchmark_style": True,
            "read_raw_anchor_excerpts": True,
        }
    method_relative = config.get("compiled_method_path")
    manifest_relative = config.get("compiled_manifest_path")
    forward_relative = config.get("forward_test_path")
    expected = {
        "compiled_method_path": method_relative,
        "compiled_manifest_path": manifest_relative,
        "forward_test_path": forward_relative,
    }
    for label, relative in expected.items():
        if not isinstance(relative, str) or not relative.strip():
            raise MethodError(f"B 分支配置缺少 {label}")
        path = (project / relative).resolve()
        try:
            path.relative_to(project)
        except ValueError as exc:
            raise MethodError(f"B 分支产物必须位于项目目录内: {relative}") from exc
        if not path.is_file():
            raise MethodError(f"B 分支产物不存在: {relative}")
    method_path = project / str(method_relative)
    manifest_path = project / str(manifest_relative)
    forward_path = project / str(forward_relative)
    if config.get("compiled_method_sha256") != sha256_file(method_path):
        raise MethodError("B 分支编译方法已变化，必须重新绑定")
    if config.get("compiled_manifest_sha256") != sha256_file(manifest_path):
        raise MethodError("B 分支编译清单已变化，必须重新绑定")
    if config.get("forward_test_sha256") != sha256_file(forward_path):
        raise MethodError("B 分支前向盲测结果已变化，必须重新绑定")
    method, compiled_manifest, _ = validate_compiled(method_path.parent, require_forward=True)
    if config.get("method_id") != method.get("method_id"):
        raise MethodError("B 分支配置与编译方法 method_id 不一致")
    if config.get("corpus_fingerprint") != compiled_manifest.get("corpus_fingerprint"):
        raise MethodError("B 分支配置与编译清单语料指纹不一致")
    return {
        "status": "ready",
        "method_branch": DISTILLED_BRANCH,
        "implicit_default": False,
        "method_id": method.get("method_id"),
        "corpus_type": method.get("corpus_type"),
        "author_style_mode": method.get("author_style_mode"),
        "rule_count": len(method.get("rules", [])),
        "runtime_strategy": "compiled-scene-rules",
        "read_benchmark_style": False,
        "read_raw_anchor_excerpts": False,
        "still_load": ["情绪模块", "节奏", "题材正文提示卡", "已接纳与黄金声音画像"],
    }


def cmd_qualify(args: argparse.Namespace) -> int:
    if args.confirm != "QUALIFY":
        raise MethodError("生成可蒸馏性判定必须显式传入 --confirm QUALIFY")
    corpus = ensure_directory(args.corpus, "语料目录")
    report, _, _, _ = qualification_report(corpus)
    output = corpus / "distillability-decision.json"
    atomic_write_json(output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "qualified" else 2


def cmd_compile(args: argparse.Namespace) -> int:
    if args.confirm != "COMPILE":
        raise MethodError("编译写作方法必须显式传入 --confirm COMPILE")
    corpus = ensure_directory(args.corpus, "语料目录")
    decision, manifest, packs, author_pack = validate_fresh_decision(corpus)
    output = (corpus / (args.output or "compiled")).resolve()
    try:
        output.relative_to(corpus)
    except ValueError as exc:
        raise MethodError("编译输出目录必须位于语料目录内") from exc
    rules = compile_rules(manifest, packs, author_pack)
    method_id = f"{manifest['corpus_id']}.v1"
    method = {
        "schema_version": SCHEMA_VERSION,
        "method_id": method_id,
        "method_branch": DISTILLED_BRANCH,
        "corpus_type": manifest.get("corpus_type"),
        "author_style_mode": manifest.get("author_style_mode"),
        "source_text_visible_to_writer": False,
        "source_names_visible_to_writer": bool(manifest.get("author_style_mode") == "authorized-fidelity"),
        "distinctive_expression_allowed": False,
        "runtime_rule_budget": 8,
        "precedence": [
            "连续性/细纲/题材契约",
            "本章情绪与节奏",
            "本书自定义文风",
            "已接纳与黄金声音画像",
            "当前编译方法",
            "通用写作建议",
        ],
        "rules": rules,
    }
    output.mkdir(parents=True, exist_ok=True)
    method_path, manifest_path, _ = compiled_paths(output)
    atomic_write_json(method_path, method)
    compiled_manifest = {
        "schema_version": SCHEMA_VERSION,
        "method_id": method_id,
        "method_branch": DISTILLED_BRANCH,
        "corpus_id": manifest.get("corpus_id"),
        "corpus_type": manifest.get("corpus_type"),
        "author_style_mode": manifest.get("author_style_mode"),
        "corpus_fingerprint": decision.get("corpus_fingerprint"),
        "decision_sha256": sha256_file(corpus / "distillability-decision.json"),
        "input_hashes": decision.get("inputs", []),
        "method_sha256": sha256_file(method_path),
        "compiled_at": utc_now(),
        "activation_status": "candidate-awaiting-forward-test",
    }
    atomic_write_json(manifest_path, compiled_manifest)
    print(json.dumps({"status": "compiled", "output": str(output), "method_id": method_id, "rule_count": len(rules)}, ensure_ascii=False, indent=2))
    return 0


def cmd_bind(args: argparse.Namespace) -> int:
    if args.confirm != "BIND":
        raise MethodError("启用 B 分支必须显式传入 --confirm BIND")
    project = ensure_directory(args.project, "项目目录")
    compiled = ensure_directory(args.compiled, "编译结果目录")
    method, manifest, _ = validate_compiled(compiled, require_forward=True)
    destination = project / "设定" / "写作方法"
    source_method, source_manifest, source_forward = compiled_paths(compiled)
    target_method, target_manifest, target_forward = compiled_paths(destination)
    atomic_copy(source_method, target_method)
    atomic_copy(source_manifest, target_manifest)
    atomic_copy(source_forward, target_forward)
    config = {
        "schema_version": SCHEMA_VERSION,
        "method_branch": DISTILLED_BRANCH,
        "method_id": method.get("method_id"),
        "compiled_method_path": target_method.relative_to(project).as_posix(),
        "compiled_manifest_path": target_manifest.relative_to(project).as_posix(),
        "forward_test_path": target_forward.relative_to(project).as_posix(),
        "compiled_method_sha256": sha256_file(target_method),
        "compiled_manifest_sha256": sha256_file(target_manifest),
        "forward_test_sha256": sha256_file(target_forward),
        "corpus_fingerprint": manifest.get("corpus_fingerprint"),
        "bound_at": utc_now(),
        "binding_note": (args.note or "").strip(),
    }
    atomic_write_json(project_config_path(project), config)
    print(json.dumps(check_project(project), ensure_ascii=False, indent=2))
    return 0


def cmd_standard(args: argparse.Namespace) -> int:
    if args.confirm != "STANDARD":
        raise MethodError("切换到 A 分支必须显式传入 --confirm STANDARD")
    project = ensure_directory(args.project, "项目目录")
    config = {
        "schema_version": SCHEMA_VERSION,
        "method_branch": STANDARD_BRANCH,
        "updated_at": utc_now(),
        "note": (args.note or "").strip(),
    }
    atomic_write_json(project_config_path(project), config)
    print(json.dumps(check_project(project), ensure_ascii=False, indent=2))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    project = ensure_directory(args.project, "项目目录")
    print(json.dumps(check_project(project), ensure_ascii=False, indent=2))
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    project = ensure_directory(args.project, "项目目录")
    status = check_project(project)
    if status["method_branch"] == STANDARD_BRANCH:
        print(json.dumps({**status, "selected_rules": []}, ensure_ascii=False, indent=2))
        return 0
    config, _ = load_project_config(project)
    method = load_json(project / str(config["compiled_method_path"]), "编译方法")
    tags = {item.strip() for item in (args.scene_tag or []) if item.strip()}
    budget = args.max_rules or int(method.get("runtime_rule_budget", 8))
    if not 1 <= budget <= 12:
        raise MethodError("--max-rules 必须在 1-12")
    ranked: list[tuple[int, int, str, dict[str, Any]]] = []
    for rule in method.get("rules", []):
        applies = set(rule.get("applies_to", []))
        exact = len(tags & applies)
        global_match = 1 if "*" in applies else 0
        ranked.append((exact * 10 + global_match, int(rule.get("priority", 50)), str(rule.get("rule_key")), rule))
    matching = [item for item in ranked if item[0] > 0]
    pool = matching if matching else ranked
    pool.sort(key=lambda item: (-item[0], -item[1], item[2]))
    selected = [item[3] for item in pool[:budget]]
    runtime_rules = [
        {
            "rule_key": item["rule_key"],
            "layer": item["layer"],
            "dimension": item["dimension"],
            "instruction": item["instruction"],
            "applies_to": item["applies_to"],
            "avoid": item.get("avoid", ""),
        }
        for item in selected
    ]
    payload = {
        **status,
        "scene_tags": sorted(tags),
        "rule_budget": budget,
        "selected_rules": runtime_rules,
        "runtime_note": "只把本章命中的抽象规则交给写作者；不读取语料原文、来源锚点或标志性表达。",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    qualify = subparsers.add_parser("qualify", help="校验语料并生成可蒸馏性判定")
    qualify.add_argument("--corpus", required=True)
    qualify.add_argument("--confirm")
    qualify.set_defaults(func=cmd_qualify)

    compile_parser = subparsers.add_parser("compile", help="从通过判定的语料编译候选写作方法")
    compile_parser.add_argument("--corpus", required=True)
    compile_parser.add_argument("--output", help="语料目录内的相对输出目录，默认 compiled")
    compile_parser.add_argument("--confirm")
    compile_parser.set_defaults(func=cmd_compile)

    bind = subparsers.add_parser("bind", help="前向盲测通过后把 B 分支绑定到项目")
    bind.add_argument("--project", required=True)
    bind.add_argument("--compiled", required=True)
    bind.add_argument("--note")
    bind.add_argument("--confirm")
    bind.set_defaults(func=cmd_bind)

    standard = subparsers.add_parser("standard", help="显式切换到 A 标准直载分支")
    standard.add_argument("--project", required=True)
    standard.add_argument("--note")
    standard.add_argument("--confirm")
    standard.set_defaults(func=cmd_standard)

    check = subparsers.add_parser("check", help="检查项目写作方法分支与绑定完整性")
    check.add_argument("--project", required=True)
    check.set_defaults(func=cmd_check)

    resolve = subparsers.add_parser("resolve", help="为本章解析 A/B 分支及场景规则")
    resolve.add_argument("--project", required=True)
    resolve.add_argument("--scene-tag", action="append")
    resolve.add_argument("--max-rules", type=int)
    resolve.set_defaults(func=cmd_resolve)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except MethodError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
