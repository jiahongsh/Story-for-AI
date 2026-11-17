#!/usr/bin/env python3
"""Read-only story checks; never writes prose or commits tracking authority."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import re
import tempfile
from pathlib import Path
from typing import Any

GATES = ("knows", "wants", "fears", "capability", "no_plot", "costs", "consequences")
PRE_CHECKS = ("seven_gates", "knowledge_bounds", "capacity_permissions", "autonomy",
              "constraints", "consequences", "voice", "actor_scene_coverage", "timeline")
POST_CHECKS = ("actual_coverage", "causality", "voice", "knowledge_bounds", "consequences", "foreshadow")
CORE_FIELDS = ("schema_version", "mode", "chapter", "binding", "sources", "actors",
               "scenes", "coverage", "manual_review")
LIMIT = "结构与引用检查通过不证明人物心理真实；语义判断由具名审查者承担，候选仍不是正史。"
MARKER = "<!-- story-world-engine: generated; rebuild instead of editing -->"
PLACEHOLDER = re.compile(r"^(?:todo|tbd|unknown|n/?a|待填|待补|待确认|未知|未审|无|不详|占位|\[.*\]|<.*>)$", re.I)
SUPPORTED_TRACKING_SCHEMAS = (4, 5)
FORBIDDEN_DOT_STORY_SUBDIRS = ("作者记忆", "排纲笔记")
DIRECT_CHAPTER_BODY_PATTERN = re.compile(r"^正文/第(\d+)章[^/]*\.md$")

class GateError(ValueError):
    pass

def need(condition: Any, message: str) -> None:
    if not condition:
        raise GateError(message)

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise GateError(f"JSON读取失败 {path}: {exc}") from exc
    need(isinstance(value, dict), f"JSON根必须是对象: {path}")
    return value

def text(value: Any, label: str, minimum: int = 1) -> str:
    need(isinstance(value, str) and len(value.strip()) >= minimum, f"{label}: 缺少具体说明")
    cleaned = value.strip()
    need(not PLACEHOLDER.fullmatch(cleaned), f"{label}: 占位/未答不能通过")
    need(not re.search(r"\b(?:TODO|TBD)\b|待填写|待补充|\[填写", cleaned, re.I), f"{label}: 含未完成占位")
    return cleaned

def integer(value: Any, label: str, minimum: int = 0) -> int:
    need(type(value) is int and value >= minimum, f"{label}: 必须为不小于{minimum}的整数")
    return value

def inside(project: Path, raw: Any, *, exists: bool = True) -> Path:
    name = text(raw, "项目内路径")
    path = (project / name).resolve() if not Path(name).is_absolute() else Path(name).resolve()
    need(path != project and path.is_relative_to(project), f"路径越出项目或指向项目根: {name}")
    if exists:
        need(path.is_file(), f"项目源文件不存在: {name}")
    return path

def relative(project: Path, path: Path) -> str:
    return path.relative_to(project).as_posix()

def is_dot_story_work_path(parts: tuple[str, ...]) -> bool:
    return parts[0] == ".story" and len(parts) >= 2 and parts[1] not in FORBIDDEN_DOT_STORY_SUBDIRS


def noncanonical_output(project: Path, raw: Any) -> Path:
    path = inside(project, raw, exists=False)
    parts = path.relative_to(project).parts
    allowed = (
        parts[0] == "创作运行"
        or (len(parts) >= 3 and parts[:2] == ("追踪", "候选章"))
        or is_dot_story_work_path(parts)
    )
    need(allowed, "输出仅允许创作运行/、.story/工作目录或追踪/候选章/；正文、大纲、设定、作者记忆、排纲笔记及追踪权威不可覆盖")
    return path


def validate_candidate_body(project: Path, raw: Any, *, chapter: int, mode: str, base_chapter: int) -> Path:
    body = inside(project, raw)
    try:
        noncanonical_output(project, raw)
        return body
    except GateError:
        rel = relative(project, body)
        match = DIRECT_CHAPTER_BODY_PATTERN.fullmatch(rel)
        is_uncommitted_draft = (
            match is not None
            and int(match.group(1)) == chapter
            and ((mode == "continuation" and chapter == base_chapter + 1) or (mode == "planning" and base_chapter == 0))
        )
        need(is_uncommitted_draft, "候选正文仅允许放在创作运行/、.story/工作目录、追踪/候选章/，或当章未入账的续写正文/第N章*.md")
        return body

def atomic_write(path: Path, content: str, *, generated: bool = False) -> None:
    if path.exists():
        need(generated and path.is_file() and path.read_text(encoding="utf-8").startswith(MARKER),
             f"拒绝覆盖既有非生成文件: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent,
                                     prefix=".world-engine-", delete=False) as temp:
        temp.write(content)
        temporary = Path(temp.name)
    try:
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()

def find_tracking_tool(project: Path, supplied: Any = None) -> Path:
    if supplied:
        tool = Path(text(supplied, "tracking_tool.path")).resolve()
        need(tool.is_file() and tool.name == "tracking_commit.py", "原追踪校验器不存在/工具名不匹配")
        return tool
    candidates = []
    for parent in (project, *project.parents):
        candidates.append(parent / "skills" / "story-long-write" / "scripts" / "tracking_commit.py")
        candidates.append(parent / ".workbuddy" / "skills" / "story-long-write" / "scripts" / "tracking_commit.py")
    candidates.extend([
        Path(__file__).resolve().parents[2] / "story-long-write" / "scripts" / "tracking_commit.py",
        Path.home() / ".agents" / "skills" / "story-long-write" / "scripts" / "tracking_commit.py",
        Path.home() / ".codex" / "skills" / "story-long-write" / "scripts" / "tracking_commit.py",
        Path.home() / ".workbuddy" / "skills" / "story-long-write" / "scripts" / "tracking_commit.py",
    ])
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise GateError("未找到原tracking_commit.py；正式续写/export需提供--tracking-tool，不另造权威")

def validate_authority(project: Path, tool_path: Path) -> dict[str, Any]:
    state_path = project / "追踪" / "_tracking-state.json"
    state = load_json(state_path)
    schema_version = state.get("schema_version")
    need(type(schema_version) is int and schema_version in SUPPORTED_TRACKING_SCHEMAS,
         f"追踪模式不支持；只读助手要求schema_version为{SUPPORTED_TRACKING_SCHEMAS}")
    integer(state.get("state_revision"), "tracking.state_revision")
    integer(state.get("last_committed_chapter"), "tracking.last_committed_chapter")
    before = digest(state_path)
    try:
        spec = importlib.util.spec_from_file_location("story_world_tracking_reader", tool_path)
        need(spec is not None and spec.loader is not None, "无法载入原追踪校验器")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        need(callable(getattr(module, "check_project", None)), "原追踪工具缺少只读check_project接口")
        normalized = module.check_project(project)
    except GateError:
        raise
    except Exception as exc:
        raise GateError(f"原追踪权威/派生视图校验失败: {exc}") from exc
    need(digest(state_path) == before, "原追踪校验器意外改变权威；立即停止")
    need(isinstance(normalized, dict), "原追踪校验器未返回合法状态")
    return normalized

def review(doc: Any, keys: tuple[str, ...], label: str) -> None:
    need(isinstance(doc, dict), f"{label}: 人工语义审查缺失")
    need(doc.get("status") == "passed", f"{label}: 人工语义审查尚未通过")
    text(doc.get("reviewer"), label + ".reviewer")
    text(doc.get("method"), label + ".method", 8)
    text(doc.get("basis"), label + ".basis", 20)
    checks = doc.get("checks")
    need(isinstance(checks, dict), f"{label}.checks: 缺失")
    for key in keys:
        need(checks.get(key) == "passed", f"{label}.{key}: 未完成人工逐项复核")

def citation(path: Path, entry: Any, label: str) -> None:
    need(isinstance(entry, dict), f"{label}: 引用必须为对象")
    start = integer(entry.get("start_line"), label + ".start_line", 1)
    end = integer(entry.get("end_line"), label + ".end_line", 1)
    need(start <= end, f"{label}: 引用行号倒置")
    quote = text(entry.get("quote"), label + ".quote")
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (UnicodeError, OSError) as exc:
        raise GateError(f"{label}: 源文件非可读UTF-8文本") from exc
    need(end <= len(lines), f"{label}: 行号超出源文件")
    need(quote in "\n".join(lines[start - 1:end]), f"{label}: 证据原句与源文件不匹配")

def inspect_packet(project: Path, packet_path: Path, phase: str, supplied_tool: Any = None,
                   _seen: set[Path] | None = None) -> dict[str, Any]:
    seen = set() if _seen is None else set(_seen)
    need(packet_path not in seen, "审查包引用形成循环")
    seen.add(packet_path)
    original_packet_sha = digest(packet_path)
    packet = load_json(packet_path)
    need(type(packet.get("schema_version")) is int and packet["schema_version"] == 1,
         "审查包schema_version不支持")
    mode = packet.get("mode")
    need(mode in ("planning", "continuation", "revision"), "mode必须为planning/continuation/revision")
    chapter = integer(packet.get("chapter"), "chapter", 1)
    binding = packet.get("binding")
    need(isinstance(binding, dict), "binding缺失")
    tracking = binding.get("tracking")
    actual_tracking = project / "追踪" / "_tracking-state.json"
    if tracking is None:
        need(mode == "planning" and not actual_tracking.exists(), "无tracking仅允许尚未初始化的新书规划")
        base_chapter = 0
    else:
        need(isinstance(tracking, dict), "binding.tracking必须为对象")
        bound_path = inside(project, tracking.get("path"))
        need(bound_path == actual_tracking, "权威路径必须为追踪/_tracking-state.json")
        need(digest(bound_path) == tracking.get("sha256"), "tracking来源SHA256已变；重建审查包")
        tool_binding = binding.get("tracking_tool")
        need(isinstance(tool_binding, dict), "tracking_tool绑定缺失")
        tool = find_tracking_tool(project, supplied_tool or tool_binding.get("path"))
        need(tool == Path(tool_binding.get("path", "")).resolve(), "tracking工具路径与冻结基线不一致")
        need(digest(tool) == tool_binding.get("sha256"), "tracking校验器改变；重建审查包")
        state = validate_authority(project, tool)
        need(state["state_revision"] == tracking.get("state_revision"), "tracking修订已变；重建审查包")
        need(state["last_committed_chapter"] == tracking.get("last_committed_chapter"), "tracking章号已变；重建审查包")
        base_chapter = state["last_committed_chapter"]
        if mode == "continuation":
            need(chapter == base_chapter + 1, "续写只能审查精确下一章")
        if mode == "revision":
            need(chapter <= base_chapter, "revision仅用于已提交章节；修订批准仍由原流程管理")
    source_rows = packet.get("sources")
    need(isinstance(source_rows, list) and source_rows, "sources必须包含实际大纲/角色/时间线证据")
    sources: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(source_rows):
        need(isinstance(row, dict), f"sources[{index}]: 必须为对象")
        sid = text(row.get("id"), f"sources[{index}].id")
        need(sid not in sources, "来源ID重复")
        path = inside(project, row.get("path"))
        need(digest(path) == row.get("sha256"), f"来源已变: {row.get('path')}")
        need(row.get("scope") in ("author", "reader", "mixed", "planned"), f"{sid}: 缺少来源可见范围")
        sources[sid] = {**row, "_path": path}
    actors: dict[str, dict[str, Any]] = {}
    actor_rows = packet.get("actors")
    need(isinstance(actor_rows, list) and actor_rows, "actors未登记；不得跳过行动者")
    for row in actor_rows:
        need(isinstance(row, dict), "actor必须为对象")
        aid = text(row.get("id"), "actor.id")
        need(aid not in actors, "行动者ID重复")
        text(row.get("name"), aid + ".name")
        need(type(row.get("protagonist")) is bool, aid + ".protagonist必须是布尔值")
        text(row.get("own_goal"), aid + ".own_goal", 8)
        text(row.get("without_protagonist"), aid + ".without_protagonist", 8)
        for key in ("voice_refs", "timeline_refs"):
            refs = row.get(key)
            need(isinstance(refs, list) and refs, f"{aid}.{key}: 角色声线/时间线来源缺失")
            for ref in refs:
                need(isinstance(ref, dict) and ref.get("source_id") in sources, f"{aid}.{key}: 来源ID不存在")
                citation(sources[ref["source_id"]]["_path"], ref, aid + "." + key)
        actors[aid] = row
    coverage = packet.get("coverage")
    need(isinstance(coverage, dict), "coverage未登记")
    need(coverage.get("all_actors_reviewed") is True and coverage.get("all_scenes_reviewed") is True,
         "行动者/场景覆盖尚未人工确认")
    text(coverage.get("basis"), "coverage.basis", 20)
    excluded = coverage.get("background_only")
    need(isinstance(excluded, list), "background_only须列明背景人物或为空数组")
    for row in excluded:
        need(isinstance(row, dict), "background_only条目必须为对象")
        text(row.get("name"), "background.name")
        text(row.get("reason"), "background.reason", 8)
    scenes = packet.get("scenes")
    need(isinstance(scenes, list) and scenes, "scenes未填写")
    scene_ids: set[str] = set()
    scene_orders: set[int] = set()
    actions: dict[str, dict[str, Any]] = {}
    action_orders: set[int] = set()
    used_actors: set[str] = set()
    for scene in scenes:
        need(isinstance(scene, dict), "scene必须是对象")
        sid = text(scene.get("id"), "scene.id")
        need(sid not in scene_ids, "场景ID重复")
        scene_ids.add(sid)
        order = integer(scene.get("order"), sid + ".order", 1)
        need(order not in scene_orders, "场景叙述顺序重复")
        scene_orders.add(order)
        story_time = scene.get("story_time")
        need(isinstance(story_time, dict), sid + ".story_time缺失")
        text(story_time.get("label"), sid + ".story_time.label")
        tick = integer(story_time.get("tick"), sid + ".story_time.tick")
        onstage, offstage = scene.get("actors_onstage"), scene.get("actors_offstage")
        need(isinstance(onstage, list) and isinstance(offstage, list), sid + ": 未区分台前/幕后行动者")
        roster = onstage + offstage
        need(roster and len(roster) == len(set(roster)), sid + ": 行动者清单为空/重复")
        need(all(item in actors for item in roster), sid + ": 清单出现未注册行动者")
        rows = scene.get("actions")
        need(isinstance(rows, list) and rows, sid + ": 未审查选择")
        covered: set[str] = set()
        for action in rows:
            need(isinstance(action, dict), sid + ": action必须为对象")
            aid = text(action.get("id"), sid + ".action.id")
            need(aid not in actions, "行动ID重复")
            actor = action.get("actor_id")
            need(actor in roster, aid + ": 行动者不在本场景清单")
            covered.add(actor)
            used_actors.add(actor)
            aorder = integer(action.get("order"), aid + ".order", 1)
            need(aorder not in action_orders, "行动因果顺序重复")
            action_orders.add(aorder)
            need(integer(action.get("story_tick"), aid + ".story_tick") == tick,
                 aid + ": 行动时间与场景时间不符")
            need(action.get("kind") in ("action", "refuse", "conceal", "inaction"), aid + ": 选择类型缺失")
            text(action.get("choice"), aid + ".choice", 8)
            gates = action.get("gates")
            need(isinstance(gates, dict), aid + ": 七关未填")
            for gate in GATES:
                text(gates.get(gate), aid + ".gates." + gate, 8)
            capacity = action.get("capacity")
            need(isinstance(capacity, dict), aid + ": 能力/权限结构缺失")
            resources = capacity.get("resources")
            need(isinstance(resources, list) and resources, aid + ": 可用资源未声明")
            for resource in resources:
                text(resource, aid + ".capacity.resources")
            text(capacity.get("permission"), aid + ".capacity.permission", 8)
            text(capacity.get("limits"), aid + ".capacity.limits", 8)
            refs = capacity.get("evidence_refs")
            need(isinstance(refs, list) and refs and all(ref in sources for ref in refs), aid + ": 能力/权限来源未绑定")
            outcome = action.get("outcome")
            need(isinstance(outcome, dict), aid + ": 意图与结果未区分")
            need(outcome.get("success_guaranteed") is False, aid + ": 禁止预保成功/他人配合")
            for key in ("intent", "failure_path", "opposition"):
                text(outcome.get(key), aid + ".outcome." + key, 8)
            refs = action.get("knowledge_refs")
            need(isinstance(refs, list) and refs, aid + ": 无角色可获取的知识来源")
            actions[aid] = {**action, "_scene_id": sid}
        need(covered == set(roster), sid + ": 有台前/幕后行动者未过七关")
    need(used_actors == set(actors), "全章行动者清单存在漏审/未出现角色")
    chronological = sorted(actions.values(), key=lambda row: row["order"])
    need([row["story_tick"] for row in chronological] == sorted(row["story_tick"] for row in chronological),
         "行动因果顺序与故事时间冲突；倒叙仅改变scene.order，不改变因果序号")
    for aid, action in actions.items():
        for ref in action["knowledge_refs"]:
            need(isinstance(ref, dict), aid + ": 知识引用必须为对象")
            source = sources.get(ref.get("source_id"))
            need(source is not None, aid + ": 知识来源ID不存在")
            need(source["scope"] != "author" and ref.get("author_only") is False,
                 aid + ": 作者未揭示秘密不能机械转为角色知识")
            citation(source["_path"], ref, aid + ".knowledge_refs")
            access = ref.get("access")
            need(access in ("observation", "testimony", "document", "memory", "planned-earlier-action"),
                 aid + ": 知识获得方式缺失")
            text(ref.get("acquisition"), aid + ".acquisition", 8)
            text(ref.get("boundary"), aid + ".boundary", 8)
            need(ref.get("certainty") in ("known", "belief", "inference", "unknown"), aid + ": 知识确信度缺失")
            available = integer(ref.get("available_chapter"), aid + ".available_chapter")
            need(available <= chapter, aid + ": 角色使用未来章节知识")
            if available == chapter:
                acquired_order = integer(ref.get("available_order"), aid + ".available_order")
                need(acquired_order < action["order"], aid + ": 角色在获取信息前动手")
                need(access == "planned-earlier-action", aid + ": 本章新增知识须绑定更早信息获得行动")
            body_chapter = re.search(r"(?:^|/)正文/第(\d+)章", relative(project, source["_path"]))
            if body_chapter:
                need(int(body_chapter.group(1)) <= available, aid + ": 正文来源晚于声明知识获得时间")
            if access == "planned-earlier-action":
                producer = actions.get(ref.get("producer_action_id"))
                need(producer is not None and producer["order"] < action["order"], aid + ": 先行动来源不存在/晚于当前选择")
                need(producer["story_tick"] <= action["story_tick"], aid + ": 先行动来自未来时间")
                need(ref.get("available_order") == producer["order"], aid + ": 获知顺序与来源行动不一致")
            else:
                need(available <= base_chapter or (mode == "planning" and available == 0),
                     aid + ": 正史知识超过冻结基线")
    review(packet.get("manual_review"), PRE_CHECKS, "manual_review")
    if phase == "postwrite":
        post = packet.get("postwrite")
        need(isinstance(post, dict), "postwrite未填")
        frozen = post.get("prewrite_packet")
        need(isinstance(frozen, dict), "postwrite.prewrite_packet缺失")
        pre_path = inside(project, frozen.get("path"))
        need(pre_path != packet_path, "写后包不能自称冻结写前包")
        need(digest(pre_path) == frozen.get("sha256"), "冻结写前包已改")
        pre = inspect_packet(project, pre_path, "prewrite", supplied_tool, seen)
        need(all(packet.get(key) == pre.get(key) for key in CORE_FIELDS),
             "写后包与冻结写前包核心计划不一致；重新审查，不覆盖冻结包")
        candidate = post.get("candidate")
        need(isinstance(candidate, dict), "postwrite.candidate缺失")
        body = validate_candidate_body(project, candidate.get("path"), chapter=chapter, mode=mode, base_chapter=base_chapter)
        need(digest(body) == candidate.get("sha256"), "候选正文SHA256已变；写后复核失效")
        rows = post.get("scene_results")
        need(isinstance(rows, list) and rows, "实际场景结果未登记")
        result_ids: set[str] = set()
        actual_actions: set[str] = set()
        for result in rows:
            need(isinstance(result, dict), "scene_results条目必须为对象")
            sid = result.get("scene_id")
            need(sid in scene_ids and sid not in result_ids, "实际场景ID未知/重复")
            result_ids.add(sid)
            text(result.get("actual_result"), str(sid) + ".actual_result", 8)
            aids = result.get("action_ids")
            need(isinstance(aids, list) and aids, str(sid) + ": 实际行动映射缺失")
            need(len(aids) == len(set(aids)), "同一实际结果重复登记行动ID")
            need(all(aid in actions and actions[aid]["_scene_id"] == sid for aid in aids),
                 "实际行动映射到其他场景/未知行动")
            need(not (set(aids) & actual_actions), "实际行动重复登记")
            actual_actions.update(aids)
            refs = result.get("evidence")
            need(isinstance(refs, list) and refs, "实际结果缺少正文证据")
            for ref in refs:
                citation(body, ref, str(sid) + ".actual_evidence")
            followups = result.get("world_followups")
            need(isinstance(followups, list) and followups, "世界/关系后果未复核；无新增也须具体说明")
            for item in followups:
                text(item, str(sid) + ".world_followups", 8)
        need(result_ids == scene_ids and actual_actions == set(actions),
             "实际场景/行动未全覆盖；新增选择须重做写前包")
        deltas = post.get("foreshadow_deltas")
        need(isinstance(deltas, list) and deltas, "伏笔增量未核对；无变化须operation=none")
        for delta in deltas:
            need(isinstance(delta, dict), "伏笔增量必须为对象")
            need(delta.get("operation") in ("plant", "advance", "resolve", "none"), "伏笔operation不合法")
            text(delta.get("id"), "foreshadow.id")
            text(delta.get("description"), "foreshadow.description", 8)
            refs = delta.get("evidence")
            need(isinstance(refs, list) and refs, "伏笔判断缺少正文证据")
            for ref in refs:
                citation(body, ref, "foreshadow.evidence")
        review(post.get("manual_review"), POST_CHECKS, "postwrite.manual_review")
    # Check again after semantic-record validation: never bless sources modified
    # while this process was reading them.
    for sid, source in sources.items():
        need(digest(source["_path"]) == source["sha256"], f"检查期间来源已变: {sid}")
    if tracking is not None:
        need(digest(actual_tracking) == tracking["sha256"], "检查期间tracking已变")
        need(digest(tool) == tool_binding["sha256"], "检查期间tracking校验器已变")
    else:
        need(not actual_tracking.exists(), "检查期间新增tracking；新书规划基线已变")
    if phase == "postwrite":
        need(digest(pre_path) == frozen["sha256"], "检查期间冻结写前包已变")
        need(digest(body) == candidate["sha256"], "检查期间候选正文已变")
    need(digest(packet_path) == original_packet_sha, "检查期间审查包已变")
    return packet

def initialize(args: argparse.Namespace, project: Path) -> dict[str, Any]:
    template = Path(__file__).resolve().parents[1] / "assets" / "chapter-packet.template.json"
    packet = load_json(template)
    packet["chapter"], packet["mode"] = args.chapter, args.mode
    packet["binding"] = {"tracking": None, "tracking_tool": None}
    actual = project / "追踪" / "_tracking-state.json"
    if actual.exists():
        tool = find_tracking_tool(project, args.tracking_tool)
        state = validate_authority(project, tool)
        packet["binding"] = {
            "tracking": {"path": relative(project, actual), "sha256": digest(actual),
                         "state_revision": state["state_revision"], "last_committed_chapter": state["last_committed_chapter"]},
            "tracking_tool": {"path": str(tool), "sha256": digest(tool)},
        }
    else:
        need(args.mode == "planning", "正式续写/修订缺追踪权威；先用原追踪工具初始化")
    packet["sources"] = []
    for index, raw in enumerate(args.source or []):
        path = inside(project, raw)
        packet["sources"].append({"id": f"SRC{index + 1}", "path": relative(project, path),
                                  "sha256": digest(path), "scope": "mixed"})
    output = noncanonical_output(project, args.packet)
    atomic_write(output, json.dumps(packet, ensure_ascii=False, indent=2) + "\n")
    return {"status": "TEMPLATE_CREATED_UNREVIEWED", "packet": relative(project, output),
            "packet_sha256": digest(output), "semantic_limit": LIMIT}

def safe_name(value: str) -> str:
    readable = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).rstrip(" .")[:60] or "角色"
    return readable + "_" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]

def markdown_value(value: Any) -> str:
    if isinstance(value, list):
        return "；".join(str(item) for item in value) or "待核：权威未记录"
    return str(value) if value not in (None, "") else "待核：权威未记录"

def record_sections(path: Path) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = "header"
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
        else:
            sections.setdefault(current, []).append(line)
    return sections

def export_views(args: argparse.Namespace, project: Path) -> dict[str, Any]:
    tool = find_tracking_tool(project, args.tracking_tool)
    state = validate_authority(project, tool)
    start, end = args.start, args.end
    need(1 <= start <= end <= state["last_committed_chapter"], "卷回看范围超出已提交正史")
    output = noncanonical_output(project, args.output)
    out_parts = output.relative_to(project).parts
    need(out_parts[0] == "创作运行" or is_dot_story_work_path(out_parts),
         "派生记忆仅允许创作运行/或.story/中的非权威工作目录")
    sources = [{"path": "追踪/_tracking-state.json", "sha256": digest(project / "追踪" / "_tracking-state.json")},
               {"path": str(tool), "sha256": digest(tool), "external_validator": True}]
    source_map: dict[str, str] = {}
    records: dict[int, tuple[Path, dict[str, list[str]]]] = {}
    missing: list[str] = []
    for chapter in range(1, end + 1):
        record = project / "追踪" / "逐章记录" / f"第{chapter:03d}章.md"
        if record.is_file():
            source_map[relative(project, record)] = digest(record)
            records[chapter] = (record, record_sections(record))
        else:
            missing.append(f"第{chapter:03d}章缺逐章增量，历史待核；不从当前状态逆造首埋/回收")
        bodies = sorted((project / "正文").glob(f"第{chapter:03d}章*.md"))
        if len(bodies) == 1:
            source_map[relative(project, bodies[0])] = digest(bodies[0])
        else:
            missing.append(f"第{chapter:03d}章正文证据{'缺失' if not bodies else '多版本待核'}")
    sources.extend({"path": path, "sha256": sha} for path, sha in sorted(source_map.items()))
    provenance = {"generator": "story-world-engine/v1", "state_revision": state["state_revision"],
                  "last_committed_chapter": state["last_committed_chapter"], "range": [start, end],
                  "source_sha": sources, "limitations": missing}
    fence = chr(96) * 3
    meta = MARKER + "\n\n" + fence + "json\n" + json.dumps(provenance, ensure_ascii=False, indent=2) + "\n" + fence + "\n\n"
    files: dict[str, str] = {}
    timeline = state.get("timeline", {})
    author_events: list[str] = []
    reader_events: list[str] = []
    for eid, event in sorted(timeline.items(), key=lambda item: (item[1].get("first_recorded_chapter", 0), item[0])):
        first = event.get("first_recorded_chapter", 0)
        updated = event.get("updated_chapter", first)
        if first <= end:
            if updated <= end:
                author_events.append(f"- {eid}｜故事时间：{event.get('story_time', '待核')}｜作者事实：{event.get('objective_fact', '待核')}｜首记录{first}，当前更新{updated}。")
            else:
                author_events.append(f"- {eid}｜待核：当前汇总在第{updated}章更新，不能充作第{end}章时的历史版本；回读原逐章增量。")
        reveal = event.get("reveal_chapter")
        if event.get("reveal_status") in ("已揭示", "部分揭示") and type(reveal) is int and reveal <= end:
            if updated <= end:
                reader_events.append(f"- {eid}｜第{reveal}章读者已知：{event.get('reader_knowledge', '待核：无读者摘要')}。")
            else:
                reader_events.append(f"- {eid}｜待核：摘要在本次范围之后更新，旧卷读者已知须回读原章，不能复制后续摘要。")
    files["作者/世界时间线.md"] = meta + "# 作者视图（含秘密，不可当角色知识）\n\n" + "\n".join(author_events)
    files["读者/已揭示时间线.md"] = meta + "# 读者已知（不复制作者事实或角色秘密）\n\n" + "\n".join(reader_events)
    for name, snapshot in state.get("characters", {}).items():
        entries = [f"- {key}：{markdown_value(value)}" for key, value in snapshot.items()]
        entries += ["", "## 固定性格、声线与历史", "", "待核：当前追踪快照不含完整人格/声线；须回读合法角色设定，禁止由目标字段编造。"]
        files[f"作者/角色当前卡/{safe_name(name)}.md"] = meta + f"# {name} 当前卡（第{state['last_committed_chapter']}章状态）\n\n" + "\n".join(entries)
        history: list[str] = []
        for chapter, (record_path, sections) in records.items():
            for line in (
                sections.get("角色变化", [])
                + sections.get("跨章连续性变更", [])
                + sections.get("连贯性约束", [])
            ):
                if line.startswith(f"- {name}｜"):
                    history.append(f"- 第{chapter:03d}章｜{line[2:]}｜来源：{relative(project, record_path)}")
        for eid, event in timeline.items():
            if name in event.get("characters", []) and event.get("first_recorded_chapter", 0) <= end:
                if event.get("updated_chapter", 0) <= end:
                    history.append(f"- 时间线引用 {eid}｜{event.get('story_time', '待核')}｜{event.get('objective_fact', '待核')}｜当前汇总，非逐章历史替代。")
                else:
                    history.append(f"- 时间线引用 {eid}｜待核：摘要在本次范围之后修订，旧版本须查原逐章增量。")
        files[f"作者/角色时间线/{safe_name(name)}.md"] = meta + f"# {name} 时间线\n\n" + ("\n".join(history) or "待核：没有可追溯逐章记录")
    volume = [f"# 第{start:03d}—{end:03d}章卷回看", "", "人物当前卡是最新正史状态，不伪装成指定end章的历史快照。", ""]
    foreshadow = ["# 伏笔历史（仅逐章原始增量）", "", "当前状态与历史变化分开；缺失章不推算。", ""]
    for chapter in range(start, end + 1):
        if chapter not in records:
            message = f"第{chapter:03d}章｜待核：缺逐章记录，不自动声称发生/首埋/回收。"
            volume.append(message)
            files[f"作者/逐章事件/第{chapter:03d}章.md"] = meta + message + "\n"
            continue
        record, sections = records[chapter]
        files[f"作者/逐章事件/第{chapter:03d}章.md"] = meta + "# 原始逐章增量引用\n\n" + record.read_text(encoding="utf-8-sig")
        headers = [line for line in sections.get("header", []) if line.startswith("- 结果：")]
        volume += [f"## 第{chapter:03d}章", "", *headers,
                   *sections.get("角色变化", []), *sections.get("伏笔变化", []), ""]
        for line in sections.get("伏笔变化", []):
            if line.startswith("- ") and line != "- 无":
                foreshadow.append(f"- 第{chapter:03d}章｜{line[2:]}｜来源：{relative(project, record)}")
    files["作者/卷回看.md"] = meta + "\n".join(volume)
    files["作者/伏笔历史.md"] = meta + "\n".join(foreshadow)
    rows = [f"- {fid}｜当前：{row.get('status', '待核')}｜{row.get('summary', '待核')}｜权威记首埋：{row.get('planted_chapter', '待核')}；此字段不代替逐章历史证据。"
            for fid, row in sorted(state.get("foreshadow", {}).items())]
    files["作者/伏笔当前引用.md"] = meta + "# 当前权威引用（不是历史还原）\n\n" + "\n".join(rows)
    for name in files:
        target = noncanonical_output(project, relative(project, output / name))
        if target.exists():
            need(target.is_file() and target.read_text(encoding="utf-8").startswith(MARKER),
                 f"拒绝覆盖非生成文件: {target}")
    for source in sources:
        source_path = Path(source["path"]) if source.get("external_validator") else inside(project, source["path"])
        need(digest(source_path) == source["sha256"], "生成期间来源改变；停止导出，请重试")
    for name, content in files.items():
        atomic_write(output / name, content.rstrip() + "\n", generated=True)
    return {"status": "DERIVED_VIEWS_EXPORTED", "output": relative(project, output), "files": len(files),
            "state_revision": state["state_revision"], "limitations": missing,
            "semantic_limit": "派生视图可重建，非第二权威；未知历史保留待核，不晋升候选。"}

def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="生成未填、未通过的审查模板")
    init.add_argument("--project", required=True)
    init.add_argument("--chapter", type=int, required=True)
    init.add_argument("--mode", choices=("planning", "continuation", "revision"), default="continuation")
    init.add_argument("--source", action="append", default=[])
    init.add_argument("--packet", required=True)
    init.add_argument("--tracking-tool")
    check = sub.add_parser("check", help="检查结构、引用、新鲜度与人工审查记录，不接纳正史")
    check.add_argument("--project", required=True)
    check.add_argument("--packet", required=True)
    check.add_argument("--phase", choices=("prewrite", "postwrite"), required=True)
    check.add_argument("--tracking-tool")
    export = sub.add_parser("export", help="只读正史，生成角色与逐章/卷派生视图")
    export.add_argument("--project", required=True)
    export.add_argument("--start", type=int, required=True)
    export.add_argument("--end", type=int, required=True)
    export.add_argument("--output", default="创作运行/派生视图")
    export.add_argument("--tracking-tool")
    return p

def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        project = Path(args.project).resolve()
        need(project.is_dir(), "project必须为现存书目录")
        if args.command == "init":
            integer(args.chapter, "chapter", 1)
            output = initialize(args, project)
        elif args.command == "check":
            packet_path = inside(project, args.packet)
            inspect_packet(project, packet_path, args.phase, args.tracking_tool)
            output = {"status": "STRUCTURAL_CHECK_PASS", "phase": args.phase,
                      "packet_sha256": digest(packet_path), "errors": [], "semantic_limit": LIMIT}
        else:
            output = export_views(args, project)
        print(json.dumps(output, ensure_ascii=True, indent=2))
        return 0
    except (ValueError, OSError, UnicodeError, TypeError, KeyError, AttributeError) as exc:
        print(json.dumps({"status": "FAIL", "errors": [str(exc)], "semantic_limit": LIMIT},
                         ensure_ascii=True, indent=2))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
