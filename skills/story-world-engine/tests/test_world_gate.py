"""Invariant tests in isolated books; no live novel files are changed."""
from __future__ import annotations
import argparse
import copy
import importlib.util
import json
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("world_gate_tested", ROOT / "scripts" / "world_gate.py")
world = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(world)

def find_original_tool() -> Path:
    candidates = [
        Path.cwd() / "skills" / "story-long-write" / "scripts" / "tracking_commit.py",
        ROOT.parent / "story-long-write" / "scripts" / "tracking_commit.py",
    ]
    for path in candidates:
        if path.exists():
            return path.resolve()
    raise RuntimeError("Tests need the existing tracking_commit.py, run from the story workspace.")

TOOL = find_original_tool()
TRACK_SPEC = importlib.util.spec_from_file_location("original_tracking_for_fixture", TOOL)
tracking = importlib.util.module_from_spec(TRACK_SPEC)
TRACK_SPEC.loader.exec_module(tracking)

class WorldGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="story-world-test-")
        self.project = Path(self.temp.name) / "book"
        self.project.mkdir()
        self.source = self.project / "设定" / "角色.md"
        self.source.parent.mkdir()
        self.source.write_text(
            "阿禾从小帮父亲修锁，急时少说话。\n"
            "阿禾昨夜亲眼见到自己仓库的柜门已被打开。\n"
            "他只有自己库房的钥匙，无权搜别人房间。\n"
            "他早于故事开场就知道自己家的地址。\n", encoding="utf-8")
        self.pre_path = self.project / "创作运行" / "审查包" / "pre.json"

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    def semantic_review(self, keys):
        return {"status": "passed", "reviewer": "fixture-reviewer",
                "method": "实际逐项回读来源及场景选择",
                "basis": "核对阿禾的既有知识、钥匙权限和自身财产目标，场景没有突然获知秘密或预保他人配合。",
                "checks": {key: "passed" for key in keys}}

    def packet(self):
        ref = {"source_id": "SRC1", "start_line": 1, "end_line": 1, "quote": "阿禾从小帮父亲修锁"}
        knowledge = {
            "source_id": "SRC1", "start_line": 2, "end_line": 2,
            "quote": "阿禾昨夜亲眼见到自己仓库的柜门已被打开",
            "access": "memory", "available_chapter": 0, "available_order": 0,
            "producer_action_id": None, "author_only": False, "certainty": "known",
            "acquisition": "故事开始之前本人亲眼检查过自己库房",
            "boundary": "只知道柜门开过，并不知道谁来过和是否偷了东西",
        }
        action = {
            "id": "A1", "actor_id": "C1", "order": 1, "story_tick": 1, "kind": "action",
            "choice": "先检查自己仓库，不去搜陌生人的房间",
            "gates": {
                "knows": "只知自己柜门被开，不知来者是谁",
                "wants": "确认自己的工具是否丢失以便开店",
                "fears": "害怕丢失父亲留下的工具和当天收入",
                "capability": "可打开自己库房，无权搜索外人住宅",
                "no_plot": "即使没人调查大案他也需要保住自家工具",
                "costs": "肯推迟开店半小时，不肯冒闯别人房间的风险",
                "consequences": "晚开店影响熟客取锁，须另行通知熟客",
            },
            "knowledge_refs": [knowledge],
            "capacity": {"resources": ["自己库房的钥匙"], "permission": "仅可进入自己的库房检查财产",
                         "limits": "不能知道来者身份也没有别人房门钥匙", "evidence_refs": ["SRC1"]},
            "outcome": {"intent": "确认工具状态但不保证查到来者",
                        "success_guaranteed": False, "failure_path": "工具清点不完或现场证据不足就不能判断",
                        "opposition": "库房灯坏和营业时间压力限制本次检查"}
        }
        return {
            "schema_version": 1, "mode": "planning", "chapter": 1,
            "binding": {"tracking": None, "tracking_tool": None},
            "sources": [{"id": "SRC1", "path": "设定/角色.md",
                         "sha256": world.digest(self.source), "scope": "mixed"}],
            "actors": [{"id": "C1", "name": "阿禾", "protagonist": False,
                        "own_goal": "养活自己的店，保住父亲留下的工具",
                        "without_protagonist": "没有主角他仍照常查库并给熟客交货",
                        "voice_refs": [ref], "timeline_refs": [ref]}],
            "scenes": [{"id": "S1", "order": 1, "story_time": {"label": "第一天开店前", "tick": 1},
                        "actors_onstage": ["C1"], "actors_offstage": [], "actions": [action]}],
            "coverage": {"all_actors_reviewed": True, "all_scenes_reviewed": True,
                         "basis": "核对本场台前阿禾和全部幕后决定，此场没有另一个影响选择的人物。", "background_only": []},
            "manual_review": self.semantic_review(world.PRE_CHECKS), "postwrite": {}
        }

    def init_authority(self):
        doc = {
            "schema_version": 1, "book_title": "隔离测试", "last_chapter": 2,
            "context": {
                "position": {"volume": "第一卷", "volume_start_chapter": 1,
                             "story_time": "第二天", "scene": "库房"},
                "long_term_constraints": [], "active_character_names": ["阿禾"],
                "continuity_risks": [], "recent_chapters": [{"chapter": 2, "summary": "清点工具"}],
                "next_chapter_commitments": ["继续经营"]
            },
            "character_snapshots": {
                "阿禾": {"identity": "修锁人", "location": "自己库房", "goal": "保住店铺",
                         "state": "工具清点中", "abilities_resources": ["自家钥匙"],
                         "relationships": ["父亲已故"], "knowledge": ["作者秘密：盗窃者真实身份代号SECRET_A"],
                         "open_threads": ["谁开柜门"]}
            },
            "foreshadow": [{"id": "F001", "summary": "柜门异常", "planted_chapter": 1,
                           "planned_resolution_chapter": 2, "status": "已回收", "importance": "高"}],
            "timeline_events": [
                {"id": "E001", "story_time": "前夜", "objective_fact": "SECRET_A偷开柜门",
                 "reader_knowledge": "暂不揭示", "reveal_status": "未揭示", "reveal_chapter": None,
                 "characters": ["阿禾"]},
                {"id": "E002", "story_time": "第二天", "objective_fact": "SECRET_A借清点掩饰盗窃",
                 "reader_knowledge": "阿禾在库房清点工具", "reveal_status": "已揭示", "reveal_chapter": 2,
                 "characters": ["阿禾"]}
            ],
        }
        tracking.initialize(self.project, doc)
        record = self.project / "追踪" / "逐章记录" / "第002章.md"
        record.write_text("# 第002章\n- 结果：清点工具。\n\n## 角色变化\n- 阿禾｜核心｜清点自家工具\n\n## 伏笔变化\n- 无\n\n## 连贯性约束\n- 无\n", encoding="utf-8")
        prose = self.project / "正文" / "第002章_清点.md"
        prose.parent.mkdir()
        prose.write_text("阿禾在库房清点工具。\n", encoding="utf-8")

    def continuation_packet(self):
        self.init_authority()
        packet = self.packet()
        packet["mode"], packet["chapter"] = "continuation", 3
        authority = self.project / "追踪" / "_tracking-state.json"
        state = json.loads(authority.read_text(encoding="utf-8"))
        packet["binding"] = {
            "tracking": {"path": "追踪/_tracking-state.json", "sha256": world.digest(authority),
                         "state_revision": state["state_revision"], "last_committed_chapter": 2},
            "tracking_tool": {"path": str(TOOL), "sha256": world.digest(TOOL)}
        }
        return packet

    def check(self, packet, phase="prewrite"):
        self.write(self.pre_path, packet)
        return world.inspect_packet(self.project, self.pre_path, phase)

    def test_unfilled_init_is_not_pass(self):
        args = argparse.Namespace(chapter=1, mode="planning", source=["设定/角色.md"],
                                  packet="创作运行/审查包/empty.json", tracking_tool=None)
        result = world.initialize(args, self.project)
        self.assertEqual(result["status"], "TEMPLATE_CREATED_UNREVIEWED")
        with self.assertRaises(world.GateError):
            world.inspect_packet(self.project, self.project / args.packet, "prewrite")

    def test_fully_filled_planning_passes_without_becoming_authority(self):
        self.check(self.packet())
        self.assertFalse((self.project / "追踪" / "_tracking-state.json").exists())

    def test_seven_gates_each_unanswered_blocks(self):
        for gate in world.GATES:
            packet = self.packet()
            packet["scenes"][0]["actions"][0]["gates"][gate] = "unknown"
            with self.subTest(gate=gate), self.assertRaises(world.GateError):
                self.check(packet)

    def test_future_knowledge_blocks_even_with_manual_pass(self):
        packet = self.packet()
        packet["scenes"][0]["actions"][0]["knowledge_refs"][0]["available_chapter"] = 2
        with self.assertRaisesRegex(world.GateError, "未来章节"):
            self.check(packet)

    def test_author_secret_cannot_be_role_knowledge(self):
        packet = self.packet()
        packet["sources"][0]["scope"] = "author"
        with self.assertRaisesRegex(world.GateError, "作者未揭示秘密"):
            self.check(packet)

    def test_reasonable_unknown_with_boundary_is_allowed(self):
        packet = self.packet()
        ref = packet["scenes"][0]["actions"][0]["knowledge_refs"][0]
        ref["certainty"] = "unknown"
        self.check(packet)

    def test_omitted_actor_blocks(self):
        packet = self.packet()
        packet["actors"].append({**copy.deepcopy(packet["actors"][0]), "id": "C2", "name": "屋主"})
        packet["scenes"][0]["actors_offstage"].append("C2")
        with self.assertRaisesRegex(world.GateError, "未过七关"):
            self.check(packet)

    def test_stale_source_blocks(self):
        packet = self.packet()
        self.source.write_text("角色资料已改。\n", encoding="utf-8")
        with self.assertRaisesRegex(world.GateError, "来源已变"):
            self.check(packet)

    def test_source_change_during_check_blocks(self):
        packet = self.packet()
        original = world.citation
        changed = False
        def change_after_valid_quote(path, entry, label):
            nonlocal changed
            original(path, entry, label)
            if not changed:
                with self.source.open("a", encoding="utf-8") as stream:
                    stream.write("角色卡在检查过程中被补改。\n")
                changed = True
        with patch.object(world, "citation", side_effect=change_after_valid_quote):
            with self.assertRaisesRegex(world.GateError, "检查期间来源已变"):
                self.check(packet)

    def test_quote_must_exist(self):
        packet = self.packet()
        packet["scenes"][0]["actions"][0]["knowledge_refs"][0]["quote"] = "正文中没有的伪造原句"
        with self.assertRaisesRegex(world.GateError, "原句"):
            self.check(packet)

    def test_future_planned_action_blocks(self):
        packet = self.packet()
        action = packet["scenes"][0]["actions"][0]
        second = copy.deepcopy(action)
        second["id"], second["order"] = "A2", 2
        action["knowledge_refs"][0].update(access="planned-earlier-action", available_chapter=1,
                                            available_order=2, producer_action_id="A2")
        packet["scenes"][0]["actions"].append(second)
        with self.assertRaisesRegex(world.GateError, "获取信息前"):
            self.check(packet)

    def test_success_must_not_be_pre_guaranteed(self):
        packet = self.packet()
        packet["scenes"][0]["actions"][0]["outcome"]["success_guaranteed"] = True
        with self.assertRaisesRegex(world.GateError, "预保成功"):
            self.check(packet)

    def test_manual_review_is_required(self):
        packet = self.packet()
        packet["manual_review"]["checks"]["voice"] = "unreviewed"
        with self.assertRaisesRegex(world.GateError, "voice"):
            self.check(packet)

    def test_continuation_validates_real_tracking_read_only(self):
        packet = self.continuation_packet()
        authority = self.project / "追踪" / "_tracking-state.json"
        before = authority.read_bytes()
        self.check(packet)
        self.assertEqual(before, authority.read_bytes())

    def test_stale_tracking_blocks(self):
        packet = self.continuation_packet()
        authority = self.project / "追踪" / "_tracking-state.json"
        changed = json.loads(authority.read_text(encoding="utf-8"))
        changed["state_revision"] += 1
        self.write(authority, changed)
        with self.assertRaisesRegex(world.GateError, "tracking来源"):
            self.check(packet)

    def post_packet(self):
        packet = self.packet()
        self.write(self.pre_path, packet)
        candidate = self.project / "追踪" / "候选章" / "run-1" / "candidate.md"
        candidate.parent.mkdir(parents=True)
        candidate.write_text("阿禾打开自己库房，工具尚在。他给熟客打电话说晚半小时开店。\n", encoding="utf-8")
        post = copy.deepcopy(packet)
        evidence = {"start_line": 1, "end_line": 1, "quote": "阿禾打开自己库房，工具尚在"}
        post["postwrite"] = {
            "prewrite_packet": {"path": world.relative(self.project, self.pre_path),
                                "sha256": world.digest(self.pre_path)},
            "candidate": {"path": world.relative(self.project, candidate), "sha256": world.digest(candidate)},
            "scene_results": [{"scene_id": "S1", "actual_result": "工具还在，阿禾仅通知熟客延迟营业",
                               "action_ids": ["A1"], "evidence": [evidence],
                               "world_followups": ["熟客获知取货延迟，但开柜来者仍未获确认"]}],
            "foreshadow_deltas": [{"id": "NO_CHANGE", "operation": "none",
                                  "description": "柜门来者仍未得到答案，此章不声称回收伏笔",
                                  "evidence": [evidence]}],
            "manual_review": self.semantic_review(world.POST_CHECKS)
        }
        post_path = self.project / "创作运行" / "审查包" / "post.json"
        self.write(post_path, post)
        return post_path, post, candidate

    def test_postwrite_candidate_does_not_commit_canon(self):
        path, packet, candidate = self.post_packet()
        world.inspect_packet(self.project, path, "postwrite")
        self.assertFalse((self.project / "追踪" / "_tracking-state.json").exists())
        self.assertTrue(candidate.exists())

    def test_stale_candidate_blocks(self):
        path, packet, candidate = self.post_packet()
        candidate.write_text("改掉正文。\n", encoding="utf-8")
        with self.assertRaisesRegex(world.GateError, "候选正文SHA256"):
            world.inspect_packet(self.project, path, "postwrite")

    def test_candidate_change_during_check_blocks(self):
        path, packet, candidate = self.post_packet()
        original = world.review
        def change_after_review(doc, keys, label):
            original(doc, keys, label)
            if label == "postwrite.manual_review":
                with candidate.open("a", encoding="utf-8") as stream:
                    stream.write("另一人刚刚修改候选。\n")
        with patch.object(world, "review", side_effect=change_after_review):
            with self.assertRaisesRegex(world.GateError, "检查期间候选正文已变"):
                world.inspect_packet(self.project, path, "postwrite")

    def test_duplicate_actual_action_blocks(self):
        path, packet, candidate = self.post_packet()
        packet["postwrite"]["scene_results"][0]["action_ids"] = ["A1", "A1"]
        self.write(path, packet)
        with self.assertRaisesRegex(world.GateError, "重复登记"):
            world.inspect_packet(self.project, path, "postwrite")

    def test_malformed_json_shapes_emit_fail_not_crash(self):
        mutations = [
            lambda p: p.update(schema_version=True),
            lambda p: p.update(actors=[None]),
            lambda p: p["scenes"][0].update(actors_onstage=[{"bad": "type"}]),
            lambda p: p["actors"][0].update(voice_refs=["not an object"]),
            lambda p: p["scenes"][0]["actions"][0]["knowledge_refs"][0].update(source_id=[]),
        ]
        for mutation in mutations:
            packet = self.packet()
            mutation(packet)
            self.write(self.pre_path, packet)
            captured = io.StringIO()
            with self.subTest(mutation=mutation), redirect_stdout(captured):
                code = world.main(["check", "--project", str(self.project),
                                   "--packet", str(self.pre_path), "--phase", "prewrite"])
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(captured.getvalue())["status"], "FAIL")

    def test_same_scene_earlier_knowledge_can_pass(self):
        packet = self.packet()
        first = packet["scenes"][0]["actions"][0]
        second = copy.deepcopy(first)
        second["id"], second["order"] = "A2", 2
        ref = second["knowledge_refs"][0]
        ref.update(access="planned-earlier-action", available_chapter=1,
                   available_order=1, producer_action_id="A1")
        packet["scenes"][0]["actions"].append(second)
        self.check(packet)

    def test_same_scene_tick_must_match(self):
        packet = self.packet()
        packet["scenes"][0]["actions"][0]["story_tick"] = 2
        with self.assertRaisesRegex(world.GateError, "时间不符"):
            self.check(packet)

    def test_changed_postwrite_plan_blocks(self):
        path, packet, candidate = self.post_packet()
        packet["scenes"][0]["actions"][0]["gates"]["wants"] = "临时决定搜索所有陌生人的房间"
        self.write(path, packet)
        with self.assertRaisesRegex(world.GateError, "核心计划不一致"):
            world.inspect_packet(self.project, path, "postwrite")

    def test_paths_cannot_escape_or_overwrite_canon(self):
        for raw in (
            "../escape.json",
            "正文/章节.md",
            "设定/角色.md",
            "追踪/_tracking-state.json",
            ".story/作者记忆/state.json",
            ".story/排纲笔记/L1.md",
        ):
            with self.subTest(path=raw), self.assertRaises(world.GateError):
                world.noncanonical_output(self.project, raw)

    def test_dot_story_paths_and_direct_chapter_postwrite_work_for_v4(self):
        packet = self.continuation_packet()
        pre_path = self.project / ".story" / "世界引擎" / "第003章" / "写前行动审查.json"
        self.write(pre_path, packet)
        world.inspect_packet(self.project, pre_path, "prewrite")
        draft = self.project / "正文" / "第003章_清点后.md"
        draft.write_text("阿禾打开自己库房，工具尚在。他给熟客打电话说晚半小时开店。\n", encoding="utf-8")
        evidence = {"start_line": 1, "end_line": 1, "quote": "阿禾打开自己库房，工具尚在"}
        post = copy.deepcopy(packet)
        post["postwrite"] = {
            "prewrite_packet": {"path": world.relative(self.project, pre_path), "sha256": world.digest(pre_path)},
            "candidate": {"path": world.relative(self.project, draft), "sha256": world.digest(draft)},
            "scene_results": [{
                "scene_id": "S1", "actual_result": "工具还在，阿禾仅通知熟客延迟营业",
                "action_ids": ["A1"], "evidence": [evidence],
                "world_followups": ["熟客获知取货延迟，但开柜来者仍未获确认"]
            }],
            "foreshadow_deltas": [{
                "id": "NO_CHANGE", "operation": "none",
                "description": "柜门来者仍未得到答案，此章不声称回收伏笔", "evidence": [evidence]
            }],
            "manual_review": self.semantic_review(world.POST_CHECKS)
        }
        post_path = self.project / ".story" / "世界引擎" / "第003章" / "写后行动复核.json"
        self.write(post_path, post)
        world.inspect_packet(self.project, post_path, "postwrite")
        # Already-committed chapter file cannot be used as an uncommitted postwrite candidate
        committed = self.project / "正文" / "第002章_清点.md"
        post["postwrite"]["candidate"] = {"path": world.relative(self.project, committed), "sha256": world.digest(committed)}
        self.write(post_path, post)
        with self.assertRaises(world.GateError):
            world.inspect_packet(self.project, post_path, "postwrite")

    def test_export_supports_dot_story_output_directory(self):
        self.init_authority()
        result = world.export_views(
            argparse.Namespace(start=1, end=2, output=".story/派生视图", tracking_tool=str(TOOL)),
            self.project,
        )
        self.assertEqual(result["status"], "DERIVED_VIEWS_EXPORTED")
        self.assertTrue((self.project / ".story" / "派生视图" / "作者" / "世界时间线.md").is_file())

    def test_export_preserves_authority_and_historical_ignorance(self):
        self.init_authority()
        authority = self.project / "追踪" / "_tracking-state.json"
        before = authority.read_bytes()
        result = world.export_views(argparse.Namespace(start=1, end=2, output="创作运行/派生视图",
                                                       tracking_tool=str(TOOL)), self.project)
        self.assertEqual(result["status"], "DERIVED_VIEWS_EXPORTED")
        self.assertEqual(before, authority.read_bytes())
        output = self.project / "创作运行" / "派生视图"
        reader_text = (output / "读者" / "已揭示时间线.md").read_text(encoding="utf-8")
        self.assertIn("阿禾在库房清点工具", reader_text)
        self.assertNotIn("SECRET_A", reader_text)
        self.assertNotIn("SECRET_A", "".join(path.read_text(encoding="utf-8") for path in (output / "读者").rglob("*.md")))
        history = (output / "作者" / "伏笔历史.md").read_text(encoding="utf-8")
        self.assertNotIn("F001", history)
        current = (output / "作者" / "伏笔当前引用.md").read_text(encoding="utf-8")
        self.assertIn("F001", current)
        self.assertIn("缺逐章增量", history)

    def test_export_cannot_overwrite_user_file(self):
        self.init_authority()
        target = self.project / "创作运行" / "派生视图" / "作者" / "卷回看.md"
        target.parent.mkdir(parents=True)
        target.write_text("作者自己写的非生成文件", encoding="utf-8")
        with self.assertRaisesRegex(world.GateError, "非生成文件"):
            world.export_views(argparse.Namespace(start=1, end=2, output="创作运行/派生视图",
                                                   tracking_tool=str(TOOL)), self.project)
        self.assertEqual(target.read_text(encoding="utf-8"), "作者自己写的非生成文件")

    def test_old_volume_never_uses_future_updated_summary(self):
        self.init_authority()
        authority = self.project / "追踪" / "_tracking-state.json"
        state = json.loads(authority.read_text(encoding="utf-8"))
        state["timeline"]["E002"]["reveal_chapter"] = 1
        state["timeline"]["E002"]["reader_knowledge"] = "FUTURE_READER_DETAIL只在第二章新揭示"
        state["timeline"]["E002"]["first_recorded_chapter"] = 1
        self.write(authority, state)
        tracking.write_views(self.project / "追踪", tracking.render_views(state))
        world.export_views(argparse.Namespace(start=1, end=1, output="创作运行/旧卷视图",
                                              tracking_tool=str(TOOL)), self.project)
        reader = (self.project / "创作运行" / "旧卷视图" / "读者" / "已揭示时间线.md").read_text(encoding="utf-8")
        self.assertNotIn("FUTURE_READER_DETAIL", reader)
        self.assertIn("本次范围之后更新", reader)

    def test_export_without_authority_fails(self):
        with self.assertRaises(world.GateError):
            world.export_views(argparse.Namespace(start=1, end=1, output="创作运行/派生视图",
                                                   tracking_tool=str(TOOL)), self.project)

if __name__ == "__main__":
    unittest.main()
