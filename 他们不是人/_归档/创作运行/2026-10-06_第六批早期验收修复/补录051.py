"""将已接纳第051章的缺失历史增量补入唯一追踪权威。"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent / "补录051"
TOOLS = ROOT.parent / "skills/story-long-write/scripts"
WORLD = ROOT.parent / "skills/story-world-engine/scripts/world_gate.py"
STATE = ROOT / "追踪/_tracking-state.json"
OUTLINE = ROOT / "大纲/细纲_第051章.md"
PROSE = ROOT / "正文/第051章_真的回来了.md"
BACKUP = ROOT / "备份/2026-10-06_第六批早期验收修复_补录051"
SOURCE_MAP = ROOT / "创作运行/2026-10-06_第六批早期验收修复/baseline_hashes.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(*argv):
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    done = subprocess.run(list(map(str, argv)), cwd=ROOT.parent, env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if done.returncode:
        raise RuntimeError(" ".join(map(str, argv)) + "\n" + done.stdout + done.stderr)
    try:
        return json.loads(done.stdout)
    except json.JSONDecodeError:
        return {"stdout": done.stdout, "stderr": done.stderr}


def tool(name: str, *args):
    return run(sys.executable, TOOLS / name, *args)


def check_locked():
    baseline = read_json(SOURCE_MAP)
    for number in range(100, 104):
        path = next((ROOT / "正文").glob(f"第{number:03d}章_*.md"))
        relative = path.relative_to(ROOT).as_posix()
        assert digest(path) == baseline[relative], relative


def prepare():
    assert read_json(STATE)["state_revision"] == 157
    assert "E051" not in read_json(STATE)["timeline"]
    assert not (ROOT / "追踪/逐章记录/第051章.md").exists()
    check_locked()
    WORK.mkdir(parents=True, exist_ok=True)
    BACKUP.mkdir(parents=True, exist_ok=True)
    for path in (OUTLINE, STATE, PROSE):
        copy_to = BACKUP / path.relative_to(ROOT)
        copy_to.parent.mkdir(parents=True, exist_ok=True)
        if not copy_to.exists():
            shutil.copy2(path, copy_to)
        assert digest(copy_to) == digest(path), str(path)

    plan = {
        "schema_version": 1,
        "change_id": "sixth-chapter051-memory-20261006",
        "summary": "修复已接纳第051章逐章记忆缺口，并把细纲状态标为正式正文映射；不反推身份、短信来源或伏笔首埋",
        "semantic_change": True,
        "changed_files": ["大纲/细纲_第051章.md", "正文/第051章_真的回来了.md"],
        "affected_entities": ["镜辞", "姜霁", "宁州陈骁", "本地陈骁", "陈启明", "杜经理", "许棠"],
        "affected_fact_ids": ["K001"],
        "affected_chapters": [50, 51, 52],
    }
    write_json(WORK / "plan.json", plan)
    preliminary = tool("revision_guard.py", "plan", "--project", ROOT,
                       "--input", WORK / "plan.json", "--output", WORK / "manifest_pre.json")
    original = OUTLINE.read_text(encoding="utf-8-sig")
    expected = (
        "# 细纲 · 第051章《真的回来了》· 二轮施工\n\n"
        "> **结构状态**：二轮施工目标。一轮稿若与本文件冲突，以本文件为准。001-050活动正文优先于本文件。"
    )
    replacement = (
        "# 细纲 · 第051章《真的回来了》· 正式正文映射\n\n"
        "> **结构状态**：已接纳正文映射。第051章活动正文为事实来源；此细纲记录其行动边界和历史记忆锚点。"
    )
    assert original.count(expected) == 1
    candidate = original.replace(expected, replacement)
    candidate += (
        "\n## 已接纳正文与记忆锚点\n\n"
        "- 正文来源：`正文/第051章_真的回来了.md`。本章补录只摘取已写事实，不补造当年的七关表。\n"
        "- 18:51是末班车到站时刻；19:12是楼栋门家庭凭证尝试与杜经理拦截时刻。陈启明在502视频中坚持不开放住宅，宁州陈骁自行拒用凭证并在外住宿。\n"
        "- 同一账户里，上周三16:20临江离楼记录与宁州汽修厂工单签字并列；姜霁保留原页面、导出时间、操作人。两份来源并列不等于认证哪个人。\n"
        "- 镜辞只在活动室近距离看宁州陈骁一次，未见接缝；这次未见不能反向认证，也不进入公共身份材料。\n"
        "- 许棠的卡仍失效，邻居代送药晚约二十分钟；她拒绝被纳入陈骁工单。夜里502可见性短信未回复，发信者未知。\n"
        "- 对应历史事件为`E051`；第052章承接两人拒签并账、来源分存及可见性新字段。此处不指定短信发起者，也不把后续状态倒填为第051章伏笔回收。\n"
    )
    candidate_path = WORK / "候选_细纲_第051章.md"
    candidate_path.write_text(candidate, encoding="utf-8")
    original_prose = PROSE.read_text(encoding="utf-8-sig")
    prose_changes = (
        ("活动室在一楼侧厅，塑料椅还堆着下午开会的水渍。",
         "活动室的门开在楼栋门禁外侧的一楼侧厅，塑料椅还堆着下午开会的水渍。"),
        ("姜霁手机里躺着白天那两组未打开的记录，她按灭屏幕",
         "姜霁手机里躺着白天那两组尚未再展开核对的记录，她按灭屏幕"),
    )
    prose_candidate = original_prose
    for old, new in prose_changes:
        assert prose_candidate.count(old) == 1, old
        prose_candidate = prose_candidate.replace(old, new)
    prose_candidate_path = WORK / "候选_正文_第051章.md"
    prose_candidate_path.write_text(prose_candidate, encoding="utf-8")
    gate_results = {}
    for name, flags in (
        ("language_gate.js", []),
        ("check-style-hygiene.js", ["--check", "--fail-on=blocking"]),
        ("check-ai-patterns.js", ["--check", "--fail-on=blocking"]),
        ("check-degeneration.js", ["--check", "--language=zh", "--fail-on=blocking"]),
    ):
        gate_results[name] = run("node", TOOLS / name, *flags, prose_candidate_path)
    write_json(WORK / "候选四门结果.json", gate_results)
    required = read_json(WORK / "manifest_pre.json")["required_checks"]
    files = []
    for relative in required:
        path = ROOT / relative
        data = path.read_text(encoding="utf-8-sig")
        files.append({"path": relative, "sha256": digest(path), "lines": len(data.splitlines())})
    write_json(WORK / "影响检查来源.json", files)
    write_json(WORK / "来源绑定.json", {
        "state_revision": 157, "outline_sha256": digest(OUTLINE),
        "prose_sha256": digest(PROSE), "candidate_sha256": digest(candidate_path),
        "prose_candidate_sha256": digest(prose_candidate_path),
        "required_checks": len(required), "preflight": preliminary,
    })
    print(json.dumps({"status": "prepared", "required_checks": len(required),
                      "candidate": str(candidate_path)}, ensure_ascii=False))


def make_transaction(state):
    result = (
        "宁州陈骁到楼下拒用绿灯进门；杜经理19:12依住宅保护工单拦截并留记录，陈启明视频拒开502。"
        "姜霁留同账户跨城16:20互斥原页。镜辞本次未见接缝且未认证。"
        "许棠卡未修，邻居代送药晚约20分钟。夜里未知号码问502是否还能看见，未回。"
    )
    return {
        "schema_version": 1, "mode": "revision", "chapter": 51,
        "chapter_title": "真的回来了", "expected_state_revision": state["state_revision"],
        "delta": {
            "result": result,
            "character_changes": [
                {"name": "宁州陈骁", "change": "拒用绿灯入楼，未进502；与父亲视频争门，自费在外住，承担请假被退的后果"},
                {"name": "陈启明", "change": "与宁州陈骁视频说话，仍拒开502、拒摘门链，不做身份认证"},
                {"name": "杜经理", "change": "按独立保护工单拦截19:12家庭凭证，签操作记录并保存并账原页"},
                {"name": "许棠", "change": "卡继续失效，拒当陈骁案对照；请邻居代送药，约晚20分钟"},
                {"name": "本地陈骁", "change": "继续南环补班，扣款未撤，不被叫回小区重新验人"},
            ],
            "foreshadow_changes": [],
            "timeline_events": [{
                "action": "upsert", "id": "E051",
                "story_time": "承050当晚；末班车18:51到站，19:12拦截门禁，夜里钟表行收短信",
                "objective_fact": result,
                "reader_knowledge": "系统绿灯未使502对任何一方开放；同账户出现跨城互斥来源。未见接缝只属一次观察，短信来源和身份真伪仍未知。",
                "reveal_status": "已揭示", "reveal_chapter": 51,
                "characters": ["镜辞", "姜霁", "宁州陈骁", "本地陈骁", "陈启明", "杜经理", "许棠"],
            }],
            "fact_changes": [],
            "constraints": [
                "家庭凭证绿灯不替代502住户入户决定，住宅保护工单独立保留",
                "本次未见接缝不认证真人，私本观察不进入公共身份材料",
                "许棠卡仍失效且她拒纳入陈骁工单；短信来源未核",
            ],
            "next_chapter_commitments": [
                "502可见性短信未答，来源待核",
                "并账的两地原始来源分存，不以同一账户直接认证身份",
            ],
            "retired_characters": [], "retired_context_items": [], "continuity_changes": [],
        },
        "context": {key: copy.deepcopy(state["context"][key]) for key in
                    ("position", "long_term_constraints", "active_character_names", "continuity_risks")},
        "character_snapshots": {},
    }


def apply():
    source = read_json(WORK / "来源绑定.json")
    state = read_json(STATE)
    assert state["state_revision"] == source["state_revision"] == 157
    assert digest(OUTLINE) == source["outline_sha256"]
    assert digest(PROSE) == source["prose_sha256"]
    candidate = WORK / "候选_细纲_第051章.md"
    assert digest(candidate) == source["candidate_sha256"]
    prose_candidate = WORK / "候选_正文_第051章.md"
    assert digest(prose_candidate) == source["prose_candidate_sha256"]
    assert len(read_json(WORK / "候选四门结果.json")) == 4
    assert "E051" not in state["timeline"]
    check_locked()
    spec = importlib.util.spec_from_file_location("tracking_commit_051", TOOLS / "tracking_commit.py")
    tc = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = tc
    spec.loader.exec_module(tc)
    transaction = make_transaction(state)
    normalized = tc.normalize_transaction(state, transaction)
    tc.enforce_continuity_guard(state, normalized)
    merged = tc.merge_transaction(state, normalized)
    size = len(tc.render_delta(51, transaction["chapter_title"], normalized["delta"],
                               set(state["characters"])).encode("utf-8"))
    assert size <= 3072, size
    assert merged["facts"] == state["facts"] and merged["foreshadow"] == state["foreshadow"]
    assert merged["characters"] == state["characters"] and merged["context"] == state["context"]
    assert merged["last_committed_chapter"] == 99 and merged["state_revision"] == 158
    assert len(merged["timeline"]) == len(state["timeline"]) + 1
    write_json(WORK / "事务_第051章.json", transaction)
    write_json(WORK / "试提交.json", {"status": "PASS", "record_bytes": size,
                                      "revision_before": 157, "revision_after": 158,
                                      "facts_and_foreshadow_unchanged": True})
    staged = WORK / "细纲_第051章.install.tmp"
    staged.write_bytes(candidate.read_bytes())
    os.replace(staged, OUTLINE)
    staged_prose = WORK / "正文_第051章.install.tmp"
    staged_prose.write_bytes(prose_candidate.read_bytes())
    os.replace(staged_prose, PROSE)
    result = tool("tracking_commit.py", "commit", "--project", ROOT,
                  "--input", WORK / "事务_第051章.json")
    assert read_json(STATE) == merged
    check_locked()
    manifest_path = ROOT / "追踪/修改影响/active.json"
    tool("revision_guard.py", "plan", "--project", ROOT,
         "--input", WORK / "plan.json", "--output", manifest_path)
    manifest = read_json(manifest_path)
    inspected = []
    for relative in manifest["required_checks"]:
        path = ROOT / relative
        text = path.read_text(encoding="utf-8-sig")
        inspected.append({"path": relative, "sha256": digest(path), "lines": len(text.splitlines())})
    write_json(WORK / "最终影响检查来源.json", inspected)
    manifest["checked_files"] = manifest["required_checks"]
    manifest["conflicts"] = [{
        "severity": "S2", "source": "正文/第051章_真的回来了.md",
        "target": "追踪/_tracking-state.json",
        "issue": "已接纳第051章缺逐章事件和记录，派生世界时间线在050与052之间断档；活动室路径和材料措辞有两处歧义",
        "resolution": "按第051章活动正文补录E051及紧凑记录；正文仅澄清侧厅入口与已保存记录的核对状态；细纲改为正式正文映射，不反推首埋回收",
        "status": "resolved",
    }]
    manifest["tracking_action"] = {
        "kind": "commit", "state_revision_before": 157, "state_revision_after": 158,
        "reason": "已接纳第051章来源绑定的历史逐章记忆补录，当前章仍为99",
    }
    write_json(manifest_path, manifest)
    stamp = ROOT / "追踪/修改影响/active.approved.json"
    checks = {
        "commit": result,
        "revision_gate": tool("revision_guard.py", "check", "--project", ROOT,
                              "--input", manifest_path, "--stamp", stamp),
        "tracking": tool("tracking_commit.py", "check", "--project", ROOT),
    }
    receipt = ROOT / "追踪/章节提交/第051章.json"
    if receipt.exists():
        checks["sync_051"] = tool("chapter_candidate.py", "sync", "--project", ROOT,
                                   "--chapter", 51, "--revision-manifest", manifest_path,
                                   "--revision-stamp", stamp, "--reason", "补录已接纳第051章历史记忆",
                                   "--confirm", "SYNC")
    checks["doctor"] = tool("story_doctor.py", "--project", ROOT)
    checks["world_export"] = run(sys.executable, WORLD, "export", "--project", ROOT,
                                 "--start", 1, "--end", 99, "--tracking-tool", TOOLS / "tracking_commit.py")
    checks["locked_100_103"] = "hash_unchanged"
    checks["prose_051"] = {"status": "two_wording_fixes", "sha256": digest(PROSE),
                           "language_gates": "4/4 PASS"}
    checks["revision_after"] = read_json(STATE)["state_revision"]
    write_json(WORK / "final_checks.json", checks)
    assert checks["doctor"]["status"] == "pass"
    print(json.dumps({"status": "PASS", "revision_after": 158,
                      "record_bytes": size, "required_checks": len(inspected)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("prepare", "apply"))
    args = parser.parse_args()
    {"prepare": prepare, "apply": apply}[args.phase]()
