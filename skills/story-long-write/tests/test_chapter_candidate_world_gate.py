"""Candidate integration tests: isolated books and mocked world helper execution."""

from __future__ import annotations

import argparse
import copy
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "chapter_candidate.py"
SPEC = importlib.util.spec_from_file_location("chapter_candidate_world_gate_tests", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
candidate_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(candidate_module)


class CandidateWorldGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.project = Path(self.workspace.name)
        self.run = self.project / "追踪" / "候选章" / "第005章" / "Ctest"
        self.run.mkdir(parents=True)
        self.candidate = self.run / "candidate.md"
        self.candidate.write_text("# 第五章\n她从同事那里得知了消息，决定独自离开。\n", encoding="utf-8")
        self.outline = self.project / "大纲" / "细纲_第5章.md"
        self.outline.parent.mkdir()
        self.outline.write_text("第五章计划", encoding="utf-8")
        self.policy = self.project / "设定" / "世界运行契约.json"
        self.policy.parent.mkdir()
        self.packet_dir = self.run / "世界引擎"
        self.packet_dir.mkdir()
        self.prewrite = self.packet_dir / "写前行动审查.json"
        self.postwrite = self.packet_dir / "写后行动复核.json"
        self.helper = self.project / "world_gate.py"
        self.helper.write_text("# mock helper\n", encoding="utf-8")
        self.data = {
            "chapter": 5,
            "candidate": self.candidate.relative_to(self.project).as_posix(),
            "target": "正文/第005章_决定.md",
            "outline": self.outline.relative_to(self.project).as_posix(),
            "expected_last_committed_chapter": 4,
            "expected_state_revision": 17,
        }

    def write_json(self, path: Path, data: dict) -> None:
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def enable(self) -> None:
        self.write_json(self.policy, {"schema_version": 1, "enabled": True})

    def write_packets(self) -> None:
        binding = {
            "tracking": {
                "path": "追踪/_tracking-state.json", "sha256": "checked-by-helper",
                "state_revision": 17, "last_committed_chapter": 4,
            }
        }
        self.write_json(self.prewrite, {"schema_version": 1, "mode": "continuation", "chapter": 5, "binding": binding})
        self.data["base_files"] = [{
            "path": self.prewrite.relative_to(self.project).as_posix(),
            "sha256": candidate_module.sha256_file(self.prewrite),
        }]
        self.write_json(self.postwrite, {
            "schema_version": 1, "mode": "continuation", "chapter": 5, "binding": binding,
            "postwrite": {
                "candidate": {
                    "path": self.data["candidate"],
                    "sha256": candidate_module.sha256_file(self.candidate),
                },
                "prewrite_packet": {
                    "path": self.prewrite.relative_to(self.project).as_posix(),
                    "sha256": candidate_module.sha256_file(self.prewrite),
                },
            },
        })

    def passing_helper(self, command: list[str], **kwargs) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(command, 0, '{"status":"STRUCTURAL_CHECK_PASS"}', "")

    def test_policy_absent_preserves_old_behavior_without_helper_lookup(self) -> None:
        with patch.object(candidate_module, "world_gate_tool") as lookup:
            self.assertEqual(candidate_module.run_world_gates(self.project, self.data, self.candidate), [])
        lookup.assert_not_called()

    def test_explicit_disabled_policy_preserves_old_behavior(self) -> None:
        self.write_json(self.policy, {"schema_version": 1, "enabled": False})
        with patch.object(candidate_module, "world_gate_tool") as lookup:
            self.assertEqual(candidate_module.run_world_gates(self.project, self.data, self.candidate), [])
        lookup.assert_not_called()

    def test_malformed_policy_never_silently_disables(self) -> None:
        for value in (
            {}, {"schema_version": 2, "enabled": False},
            {"schema_version": True, "enabled": True},
            {"schema_version": 1, "enabled": "true"},
        ):
            with self.subTest(value=value):
                self.write_json(self.policy, value)
                with self.assertRaises(candidate_module.CandidateError):
                    candidate_module.world_engine_enabled(self.project)
        self.policy.write_text("{broken", encoding="utf-8")
        with self.assertRaises(candidate_module.CandidateError):
            candidate_module.world_engine_enabled(self.project)

    def test_missing_packet_blocks_before_helper_execution(self) -> None:
        self.enable()
        with patch.object(candidate_module, "world_gate_tool", return_value=self.helper), \
                patch.object(candidate_module.subprocess, "run") as execute:
            with self.assertRaisesRegex(candidate_module.CandidateError, "审查包不存在"):
                candidate_module.run_world_gates(self.project, self.data, self.candidate)
        execute.assert_not_called()

    def test_missing_helper_blocks_enabled_book(self) -> None:
        self.enable()
        with patch.object(candidate_module, "world_gate_tool", side_effect=candidate_module.CandidateError("找不到工具")):
            with self.assertRaisesRegex(candidate_module.CandidateError, "找不到工具"):
                candidate_module.run_world_gates(self.project, self.data, self.candidate)

    def test_packets_must_bind_candidate_baseline(self) -> None:
        self.enable()
        self.write_packets()
        for key, value in (("state_revision", 16), ("last_committed_chapter", 3), ("state_revision", True)):
            with self.subTest(key=key, value=value):
                self.write_packets()
                packet = json.loads(self.prewrite.read_text(encoding="utf-8"))
                packet["binding"]["tracking"][key] = value
                self.write_json(self.prewrite, packet)
                self.data["base_files"][0]["sha256"] = candidate_module.sha256_file(self.prewrite)
                with patch.object(candidate_module, "world_gate_tool", return_value=self.helper), \
                        patch.object(candidate_module.subprocess, "run") as execute:
                    with self.assertRaisesRegex(candidate_module.CandidateError, "许可基线不一致"):
                        candidate_module.run_world_gates(self.project, self.data, self.candidate)
                execute.assert_not_called()

    def test_another_successful_candidate_cannot_lend_its_packet(self) -> None:
        self.enable()
        self.write_packets()
        other = self.run.parent / "Cother" / "candidate.md"
        other.parent.mkdir()
        other.write_bytes(self.candidate.read_bytes())
        packet = json.loads(self.postwrite.read_text(encoding="utf-8"))
        packet["postwrite"]["candidate"] = {
            "path": other.relative_to(self.project).as_posix(),
            "sha256": candidate_module.sha256_file(other),
        }
        self.write_json(self.postwrite, packet)
        with patch.object(candidate_module, "world_gate_tool", return_value=self.helper), \
                patch.object(candidate_module.subprocess, "run", side_effect=self.passing_helper) as execute:
            with self.assertRaisesRegex(candidate_module.CandidateError, "另一份候选正文"):
                candidate_module.run_world_gates(self.project, self.data, self.candidate)
        self.assertEqual(execute.call_count, 1)

    def test_changed_candidate_or_prewrite_packet_invalidates_postwrite(self) -> None:
        self.enable()
        for target, expected in ((self.candidate, "候选正文摘要"), (self.prewrite, "冻结写前包未绑定")):
            with self.subTest(target=target):
                self.write_packets()
                target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
                with patch.object(candidate_module, "world_gate_tool", return_value=self.helper), \
                        patch.object(candidate_module.subprocess, "run", side_effect=self.passing_helper):
                    with self.assertRaisesRegex(candidate_module.CandidateError, expected):
                        candidate_module.run_world_gates(self.project, self.data, self.candidate)

    def test_valid_packets_call_both_phases_and_local_tracking_tool(self) -> None:
        self.enable()
        self.write_packets()
        with patch.object(candidate_module, "world_gate_tool", return_value=self.helper), \
                patch.object(candidate_module.subprocess, "run", side_effect=self.passing_helper) as execute:
            results = candidate_module.run_world_gates(self.project, self.data, self.candidate)
        self.assertEqual([item["name"] for item in results], ["world_engine_prewrite", "world_engine_postwrite"])
        commands = [call.args[0] for call in execute.call_args_list]
        self.assertEqual([cmd[cmd.index("--phase") + 1] for cmd in commands], ["prewrite", "postwrite"])
        for command in commands:
            self.assertEqual(command[command.index("--tracking-tool") + 1], str(MODULE_PATH.parent / "tracking_commit.py"))

    def test_helper_failure_or_invalid_success_payload_blocks(self) -> None:
        self.enable()
        self.write_packets()
        for returncode, stdout in ((2, '{"status":"FAIL"}'), (0, '{"status":"FAIL"}'), (0, "not-json")):
            with self.subTest(returncode=returncode, stdout=stdout):
                result = subprocess.CompletedProcess([], returncode, stdout, "")
                with patch.object(candidate_module, "world_gate_tool", return_value=self.helper), \
                        patch.object(candidate_module.subprocess, "run", return_value=result):
                    with self.assertRaisesRegex(candidate_module.CandidateError, "门禁未通过"):
                        candidate_module.run_world_gates(self.project, self.data, self.candidate)

    def test_packet_mode_and_chapter_must_match_continuation_permit(self) -> None:
        self.enable()
        for key, value in (("mode", "revision"), ("mode", "planning"), ("chapter", 4), ("chapter", True)):
            with self.subTest(key=key, value=value):
                self.write_packets()
                packet = json.loads(self.prewrite.read_text(encoding="utf-8"))
                packet[key] = value
                self.write_json(self.prewrite, packet)
                self.data["base_files"][0]["sha256"] = candidate_module.sha256_file(self.prewrite)
                with patch.object(candidate_module, "world_gate_tool", return_value=self.helper), \
                        patch.object(candidate_module.subprocess, "run") as execute:
                    with self.assertRaises(candidate_module.CandidateError):
                        candidate_module.run_world_gates(self.project, self.data, self.candidate)
                execute.assert_not_called()

    def test_prewrite_must_match_frozen_base_even_when_both_packets_are_updated(self) -> None:
        self.enable()
        self.write_packets()
        packet = json.loads(self.prewrite.read_text(encoding="utf-8"))
        packet["new_plan"] = "候选创建后偷偷滚动改变的计划"
        self.write_json(self.prewrite, packet)
        post = json.loads(self.postwrite.read_text(encoding="utf-8"))
        post["postwrite"]["prewrite_packet"]["sha256"] = candidate_module.sha256_file(self.prewrite)
        self.write_json(self.postwrite, post)
        with patch.object(candidate_module, "world_gate_tool", return_value=self.helper), \
                patch.object(candidate_module.subprocess, "run") as execute:
            with self.assertRaisesRegex(candidate_module.CandidateError, "冻结写前包未绑定"):
                candidate_module.run_world_gates(self.project, self.data, self.candidate)
        execute.assert_not_called()

    def test_validate_run_preserves_prose_first_and_checks_world_even_freshness_only(self) -> None:
        order = []
        with patch.object(candidate_module, "freshness", return_value={"status": "fresh"}), \
                patch.object(candidate_module, "run_prose_gates", side_effect=lambda *args: order.append("prose") or []), \
                patch.object(candidate_module, "run_world_gates", side_effect=lambda *args: order.append("world") or []):
            candidate_module.validate_run(self.project, self.data, run_gates=True)
            self.assertEqual(order, ["prose", "world"])
            order.clear()
            candidate_module.validate_run(self.project, self.data, run_gates=False)
            self.assertEqual(order, ["world"])

    def test_approve_and_promote_cannot_bypass_missing_world_packet(self) -> None:
        self.enable()
        for operation, status, confirm in (
            (candidate_module.cmd_approve, "draft", "ACCEPT"),
            (candidate_module.cmd_promote, "approved", "PROMOTE"),
        ):
            with self.subTest(operation=operation.__name__):
                data = {**self.data, "status": status}
                args = argparse.Namespace(run=str(self.run), confirm=confirm, approval_note="用户明确接受")
                with patch.object(candidate_module, "load_run", return_value=(self.project, self.run / "manifest.json", data)), \
                        patch.object(candidate_module, "freshness", return_value={"status": "fresh"}), \
                        patch.object(candidate_module, "run_prose_gates", return_value=[]), \
                        patch.object(candidate_module, "world_gate_tool", return_value=self.helper), \
                        patch.object(candidate_module, "atomic_write_json") as write_json, \
                        patch.object(candidate_module, "atomic_write_bytes") as write_bytes:
                    with self.assertRaisesRegex(candidate_module.CandidateError, "审查包不存在"):
                        operation(args)
                write_json.assert_not_called()
                write_bytes.assert_not_called()


class CandidateWorldGateRealIntegrationTests(unittest.TestCase):
    """Use the installed helper and the unchanged original tracking CLI in a temp book."""

    write_json = CandidateWorldGateTests.write_json
    enable = CandidateWorldGateTests.enable

    def setUp(self) -> None:
        CandidateWorldGateTests.setUp(self)
        self.real_helper = candidate_module.world_gate_tool()
        self.tracking_tool = MODULE_PATH.parent / "tracking_commit.py"
        self.enable()
        self.card = self.policy.parent / "角色" / "林岚.md"
        self.card.parent.mkdir()
        self.card.write_text(
            "# 林岚\n"
            "林岚只用短句交代去向，拒绝用解释求同事同意。\n"
            "第4章前林岚已经收到家里的病人复诊提醒。\n"
            "林岚持有自己的车票和请假批准，能独自离开车站。\n",
            encoding="utf-8",
        )
        self.candidate.write_text(
            '# 第005章 决定\n林岚收起车票：“我先走。”\n她没有等同事回话，独自离开车站。\n',
            encoding="utf-8",
        )
        self.snapshot = {
            "identity": "林岚；已请假的职员", "location": "车站候车室",
            "goal": "赶回家陪母亲复诊", "state": "焦急但能独立决定自己的行程",
            "abilities_resources": ["本人车票", "已获准的假期"],
            "relationships": ["母亲需要她陪同复诊"],
            "knowledge": ["已收到母亲的复诊提醒；E001"],
            "open_threads": ["尚未到家陪母亲复诊"],
        }
        self.context = {
            "position": {"volume": "第一卷", "volume_start_chapter": 1,
                         "story_time": "出发日傍晚", "scene": "车站候车室"},
            "long_term_constraints": [], "active_character_names": ["林岚"], "continuity_risks": [],
        }
        initial = {
            "schema_version": 1, "book_title": "集成测试夹具", "last_chapter": 4,
            "context": {**self.context, "recent_chapters": [], "next_chapter_commitments": []},
            "character_snapshots": {"林岚": self.snapshot}, "foreshadow": [], "facts": [],
            "timeline_events": [{"id": "E001", "story_time": "出发日前一天",
                                 "objective_fact": "林岚收到母亲需要复诊的提醒",
                                 "reader_knowledge": "林岚已收到复诊提醒",
                                 "reveal_status": "已揭示", "reveal_chapter": 4,
                                 "characters": ["林岚"]}],
        }
        self.tracking_command("init", initial)
        self.data["expected_state_revision"] = 0
        self.run_command([
            sys.executable, str(self.real_helper), "init", "--project", str(self.project),
            "--chapter", "5", "--mode", "continuation", "--tracking-tool", str(self.tracking_tool),
            "--source", self.card.relative_to(self.project).as_posix(),
            "--packet", self.prewrite.relative_to(self.project).as_posix(),
        ])
        self.complete_real_packets()

    def run_command(self, command: list[str]) -> subprocess.CompletedProcess:
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        return completed

    def tracking_command(self, operation: str, document: dict) -> None:
        source = self.project / f"test-{operation}.json"
        self.write_json(source, document)
        self.run_command([
            sys.executable, str(self.tracking_tool), operation,
            "--project", str(self.project), "--input", str(source),
        ])

    def complete_real_packets(self) -> None:
        packet = json.loads(self.prewrite.read_text(encoding="utf-8"))
        voice = {"source_id": "SRC1", "start_line": 2, "end_line": 2,
                 "quote": "林岚只用短句交代去向，拒绝用解释求同事同意。"}
        timeline = {"source_id": "SRC1", "start_line": 3, "end_line": 3,
                    "quote": "第4章前林岚已经收到家里的病人复诊提醒。"}
        packet["actors"] = [{
            "id": "P1", "name": "林岚", "protagonist": True,
            "own_goal": "赶回家陪母亲复诊，保住自己的行程安排。",
            "without_protagonist": "撤去叙事特权仍按自己的车票离开车站。",
            "voice_refs": [voice], "timeline_refs": [timeline],
        }]
        packet["scenes"] = [{
            "id": "S1", "order": 1, "story_time": {"label": "出发日傍晚", "tick": 1},
            "actors_onstage": ["P1"], "actors_offstage": [],
            "actions": [{
                "id": "A1", "actor_id": "P1", "order": 1, "story_tick": 1, "kind": "action",
                "choice": "林岚结束闲谈，按已经购买的车票独自离开车站。",
                "gates": {
                    "knows": "她已收到母亲复诊提醒，但不知道路上会不会晚点。",
                    "wants": "按既有行程赶回家陪母亲复诊，不再为闲谈耽搁。",
                    "fears": "她怕错过与母亲约好的复诊时间而使母亲失望。",
                    "capability": "她持有车票和请假批准，可以独自决定离开车站。",
                    "no_plot": "即使撤去预定剧情，她仍因母亲的复诊提醒而离开。",
                    "costs": "她愿意中断同事闲谈，却无法保证列车准点运行。",
                    "consequences": "她与同事的谈话结束，陪同复诊仍需后续行程兑现。",
                },
                "knowledge_refs": [{
                    **timeline, "access": "memory", "available_chapter": 4,
                    "available_order": 0, "producer_action_id": None, "author_only": False,
                    "certainty": "known", "acquisition": "林岚在前一天亲自收到母亲的复诊短信。",
                    "boundary": "短信仅说明复诊安排，不能保证交通准点或者病情结果。",
                }],
                "capacity": {
                    "resources": ["本人车票", "已获准的假期"], "evidence_refs": ["SRC1"],
                    "permission": "她仅能安排自己的行程，不能替同事决定去向。",
                    "limits": "她没有调度交通的权限，列车晚点会使行程失败。",
                },
                "outcome": {
                    "intent": "结束闲谈后尽快赶回家里陪母亲复诊。", "success_guaranteed": False,
                    "failure_path": "列车晚点或道路受阻会使她无法按约定赶到。",
                    "opposition": "同事可能不愿结束谈话，交通也不会为她调整。",
                },
            }],
        }]
        packet["coverage"] = {
            "all_actors_reviewed": True, "all_scenes_reviewed": True,
            "basis": "测试逐行核对候选中的决定；同事尚未作出选择，所有行动均属于林岚。",
            "background_only": [{"name": "同事", "reason": "本场仅听到告别，正文未写出新的选择或者回应。"}],
        }
        packet["manual_review"] = {
            "status": "passed", "reviewer": "isolated-integration-fixture",
            "method": "逐行对照临时角色卡、时间线与场景计划。",
            "basis": "夹具逐项核对复诊信息来源、个人行程权限及短句告别，未赋予她交通调度能力。",
            "checks": {key: "passed" for key in packet["manual_review"]["checks"]},
        }
        self.write_json(self.prewrite, packet)
        frozen_base = self.project / "创作运行" / "审查包" / "第005章_写前.json"
        frozen_base.parent.mkdir(parents=True)
        frozen_base.write_bytes(self.prewrite.read_bytes())
        self.data["base_files"] = [{
            "path": frozen_base.relative_to(self.project).as_posix(),
            "sha256": candidate_module.sha256_file(frozen_base),
        }]
        post = copy.deepcopy(packet)
        evidence = {"start_line": 2, "end_line": 3, "quote": "她没有等同事回话，独自离开车站。"}
        post["postwrite"] = {
            "prewrite_packet": {"path": self.prewrite.relative_to(self.project).as_posix(),
                                "sha256": candidate_module.sha256_file(self.prewrite)},
            "candidate": {"path": self.data["candidate"], "sha256": candidate_module.sha256_file(self.candidate)},
            "scene_results": [{"scene_id": "S1", "actual_result": "林岚自行结束闲谈并离开车站，正文未保证她及时到家。",
                               "action_ids": ["A1"], "evidence": [evidence],
                               "world_followups": ["林岚离开车站，与同事对话结束；陪同复诊尚未兑现。"]}],
            "foreshadow_deltas": [{"id": "NO_CHANGE", "operation": "none",
                                   "description": "本场没有新埋或回收谜团，母亲复诊行程尚待继续。", "evidence": [evidence]}],
            "manual_review": {
                "status": "passed", "reviewer": "isolated-integration-fixture",
                "method": "回读临时候选正文与冻结前包逐项核对。",
                "basis": "夹具核对告别、离开和未完成复诊三个事实，所有选择均覆盖且没有保证最终成功。",
                "checks": {key: "passed" for key in packet["postwrite"]["manual_review"]["checks"]},
            },
        }
        self.write_json(self.postwrite, post)

    def test_real_helper_accepts_both_packets(self) -> None:
        results = candidate_module.run_world_gates(self.project, self.data, self.candidate)
        self.assertEqual([row["payload"]["phase"] for row in results], ["prewrite", "postwrite"])

    def test_real_helper_rejects_changed_candidate_before_acceptance(self) -> None:
        self.candidate.write_text(self.candidate.read_text(encoding="utf-8") + "她又折返车站。\n", encoding="utf-8")
        with self.assertRaisesRegex(candidate_module.CandidateError, "候选正文摘要已失效"):
            candidate_module.run_world_gates(self.project, self.data, self.candidate)

    def test_real_helper_rejects_changed_canon_before_acceptance(self) -> None:
        self.tracking_command("commit", {
            "schema_version": 1, "mode": "revision", "chapter": 4, "chapter_title": "复診提醒",
            "expected_state_revision": 0,
            "delta": {"result": "回读复诊提醒并保持已登记的人物事实不变。",
                      "character_changes": [], "foreshadow_changes": [], "timeline_events": [], "fact_changes": []},
            "context": self.context, "character_snapshots": {},
        })
        with self.assertRaisesRegex(candidate_module.CandidateError, "tracking.*SHA256"):
            candidate_module.run_world_gates(self.project, self.data, self.candidate)

    def test_real_helper_rejects_changed_frozen_prewrite_before_acceptance(self) -> None:
        self.prewrite.write_text(self.prewrite.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with self.assertRaisesRegex(candidate_module.CandidateError, "冻结写前包未绑定"):
            candidate_module.run_world_gates(self.project, self.data, self.candidate)

    def test_close_after_real_tracking_commit_does_not_reapply_old_world_baseline(self) -> None:
        target = self.project / self.data["target"]
        target.parent.mkdir()
        target.write_bytes(self.candidate.read_bytes())
        sha = candidate_module.sha256_file(target)
        manifest = {**self.data, "schema_version": 1, "project_root": str(self.project), "status": "promoted"}
        self.write_json(self.run / "manifest.json", manifest)
        receipt = candidate_module.receipt_path(self.project, 5)
        receipt.parent.mkdir()
        self.write_json(receipt, {"status": "promoted", "accepted_prose_sha256": sha})
        moved = {**self.snapshot, "location": "车站出口"}
        self.tracking_command("commit", {
            "schema_version": 1, "mode": "append", "chapter": 5, "chapter_title": "决定",
            "expected_state_revision": 0,
            "delta": {
                "result": "林岚结束闲谈并独自离开车站，尚未完成陪同母亲复诊。",
                "character_changes": [{"name": "林岚", "change": "结束闲谈并独自离开车站"}],
                "continuity_changes": [{"name": "林岚", "field": "location", "from": "车站候车室",
                                        "to": "车站出口", "reason": "本章主动结束闲谈并离开车站"}],
                "timeline_events": [{"id": "E002", "story_time": "出发日傍晚",
                                     "objective_fact": "林岚结束闲谈并离开车站",
                                     "reader_knowledge": "林岚已独自离开车站",
                                     "reveal_status": "已揭示", "reveal_chapter": 5, "characters": ["林岚"]}],
            },
            "context": {**self.context, "position": {**self.context["position"], "scene": "车站出口"}},
            "character_snapshots": {"林岚": moved},
        })
        with self.assertRaisesRegex(candidate_module.CandidateError, "tracking.*SHA256"):
            candidate_module.run_world_gates(self.project, self.data, self.candidate)
        with redirect_stdout(io.StringIO()):
            result = candidate_module.cmd_close(argparse.Namespace(run=str(self.run)))
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(receipt.read_text(encoding="utf-8"))["status"], "committed")
        self.assertEqual(json.loads((self.run / "manifest.json").read_text(encoding="utf-8"))["status"], "committed")


if __name__ == "__main__":
    unittest.main()
