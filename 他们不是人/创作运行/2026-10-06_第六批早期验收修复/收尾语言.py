"""对097—099三处残留复述/错字做非事实修订。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent / "收尾语言"
TOOLS = ROOT.parent / "skills/story-long-write/scripts"
WORLD = ROOT.parent / "skills/story-world-engine/scripts/world_gate.py"
STATE = ROOT / "追踪/_tracking-state.json"
BACKUP = ROOT / "备份/2026-10-06_第六批早期验收修复_收尾语言"
PREVIOUS_HASHES = ROOT / "创作运行/2026-10-06_第六批早期验收修复/baseline_hashes.json"
EDITS = {
    "正文/第014章_十七.md": [
        ("“你知道里面有纸？”", "“你以前就知道表里有纸？”"),
    ],
    "大纲/卷纲_第一卷.md": [
        ("001—050及096—099正在按详细验收修订，整卷尚未重新验收。",
         "001—050及096—099已完成本轮详细验收缺口修订；整卷尚待独立复验。"),
        ("上述验收缺口以本轮正文和追踪实际修复为准。",
         "本轮修订已按实际正文补齐001—051逐章事件，具体状态以当前追踪和修订后复验为准。"),
        ("> **当前施工点**：001—050、096—099验收缺口与早期记忆回补。第104章继续冻结。",
         "> **当前状态**：001—050、096—099验收项修订已写入活动正文，早期逐章事件已补至051；第104章继续冻结。下一步独立复验，不重复施工。"),
    ],
    "大纲/伏笔总表.md": [
        ("当前施工焦点是001—050、096—099详细验收缺口及早期记忆，100—103锁定、104冻结。",
         "001—050及096—099本轮修订与早期逐章事件回补已完成。下一步核对尚未重算的首埋，并对第一卷做独立复验；100—103锁定、104冻结。"),
    ],
    "正文/第097章_前三年.md": [(
        "夜里姜霁把版本回填结论入档。入档页上没有周衡实施四个字。没有不等于洗白。洗白要证据。证据今晚仍空着。空着的栏位旁边，她另写：近五年系统外后果增多。增多项单独列。列完她发短讯给镜辞：暂不接触。先把近五年关系后果核完。",
        "夜里姜霁把版本回填结论入档。入档页上没有“周衡实施”四个字；实施者一栏仍空着。她另列近五年系统外的关系后果，发短讯给镜辞：暂不接触。先把近五年关系后果核完。",
    )],
    "正文/第098章_后五年.md": [
        ("差别很小。小完却关键。", ""),
    ],
    "正文/第099章_一只真的坏表.md": [
        ("半行旁边不写“伪装成功”。成功要证据。眼下没有。", "半行旁边不写“伪装成功”。"),
    ],
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args):
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    completed = subprocess.run(list(map(str, args)), cwd=ROOT.parent, env=env,
                               text=True, capture_output=True, encoding="utf-8", errors="replace")
    if completed.returncode:
        raise RuntimeError(" ".join(map(str, args)) + "\n" + completed.stdout + completed.stderr)
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"stdout": completed.stdout, "stderr": completed.stderr}


def tool(name, *args):
    return run(sys.executable, TOOLS / name, *args)


def assert_locked():
    baseline = read_json(PREVIOUS_HASHES)
    for number in range(100, 104):
        path = next((ROOT / "正文").glob(f"第{number:03d}章_*.md"))
        assert sha(path) == baseline[path.relative_to(ROOT).as_posix()]


def prepare():
    assert read_json(STATE)["state_revision"] == 158
    assert_locked()
    WORK.mkdir(parents=True, exist_ok=True)
    BACKUP.mkdir(parents=True, exist_ok=True)
    plan = {
        "schema_version": 1, "change_id": "sixth-prose-097-099-20261006",
        "summary": "澄清014旧知情问法，删除097和099两处复述，修复098错字；卷纲/伏笔总表状态更新为本轮修订已完成",
        "semantic_change": False,
        "changed_files": list(EDITS),
        "affected_entities": ["镜辞", "姜霁", "猫眼", "周衡", "守钟人"],
        "affected_fact_ids": [],
        "affected_chapters": [1, 12, 13, 14, 15, 50, 51, 96, 97, 98, 99, 100, 103, 104],
    }
    write_json(WORK / "plan.json", plan)
    tool("revision_guard.py", "plan", "--project", ROOT, "--input", WORK / "plan.json",
         "--output", WORK / "manifest_pre.json")
    bindings = {"state_revision": 158, "sources": {}, "candidates": {}}
    gates = {}
    for relative, replacements in EDITS.items():
        original = ROOT / relative
        backup = BACKUP / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            shutil.copy2(original, backup)
        assert sha(backup) == sha(original)
        text = original.read_text(encoding="utf-8-sig")
        for old, new in replacements:
            assert text.count(old) == 1, (relative, old)
            text = text.replace(old, new)
        candidate = WORK / original.name
        candidate.write_text(text, encoding="utf-8")
        bindings["sources"][relative] = sha(original)
        bindings["candidates"][relative] = sha(candidate)
        if relative.startswith("正文/"):
            gates[relative] = {}
            for name, flags in (
                ("language_gate.js", []),
                ("check-style-hygiene.js", ["--check", "--fail-on=blocking"]),
                ("check-ai-patterns.js", ["--check", "--fail-on=blocking"]),
                ("check-degeneration.js", ["--check", "--language=zh", "--fail-on=blocking"]),
            ):
                gates[relative][name] = run("node", TOOLS / name, *flags, candidate)
    write_json(WORK / "来源绑定.json", bindings)
    write_json(WORK / "候选四门结果.json", gates)
    required = read_json(WORK / "manifest_pre.json")["required_checks"]
    write_json(WORK / "预先影响检查.json", [
        {"path": relative, "sha256": sha(ROOT / relative),
         "lines": len((ROOT / relative).read_text(encoding="utf-8-sig").splitlines())}
        for relative in required
    ])
    print(json.dumps({"status": "prepared", "candidate_chapters": [14, 97, 98, 99],
                      "required_checks": len(required), "gates": "16/16 PASS"}, ensure_ascii=False))


def apply():
    assert read_json(STATE)["state_revision"] == 158
    assert_locked()
    bindings = read_json(WORK / "来源绑定.json")
    assert bindings["state_revision"] == 158
    gates = read_json(WORK / "候选四门结果.json")
    assert all(len(gates[relative]) == 4 for relative in EDITS if relative.startswith("正文/"))
    for relative in EDITS:
        target = ROOT / relative
        candidate = WORK / target.name
        assert sha(target) == bindings["sources"][relative]
        assert sha(candidate) == bindings["candidates"][relative]
    for relative in EDITS:
        target = ROOT / relative
        staged = WORK / (target.name + ".install.tmp")
        staged.write_bytes((WORK / target.name).read_bytes())
        os.replace(staged, target)
    manifest_path = ROOT / "追踪/修改影响/active.json"
    tool("revision_guard.py", "plan", "--project", ROOT, "--input", WORK / "plan.json",
         "--output", manifest_path)
    manifest = read_json(manifest_path)
    files = []
    for relative in manifest["required_checks"]:
        path = ROOT / relative
        data = path.read_text(encoding="utf-8-sig")
        files.append({"path": relative, "sha256": sha(path), "lines": len(data.splitlines())})
    write_json(WORK / "最终影响检查.json", files)
    manifest["checked_files"] = manifest["required_checks"]
    manifest["conflicts"] = [
        {"severity": "S4", "source": "正文/第012章_不该在这里的零件.md",
         "target": "正文/第014章_十七.md",
         "issue": "014追问老人知纸，易被读成忘记012已经共同看到纸边",
         "resolution": "补出‘以前’限定，明确问的是此前预知而非眼前是否看见",
         "status": "resolved"},
        {"severity": "S3", "source": "正文/第097章_前三年.md",
         "target": "正文/第099章_一只真的坏表.md",
         "issue": "097和099仍用重复解释强调不认证身份，削弱纸档与维修动作的表达",
         "resolution": "保留入档空栏、私本不写伪装成功及两地材料事实，仅删动作后复述",
         "status": "resolved"},
        {"severity": "S4", "source": "正文/第098章_后五年.md",
         "target": "大纲/细纲_第098章.md",
         "issue": "098出现“小完却关键”错字病句",
         "resolution": "删除多余评注，保留镜辞改写记录的直接动作和归属边界",
         "status": "resolved"},
        {"severity": "S3", "source": "大纲/卷纲_第一卷.md",
         "target": "大纲/伏笔总表.md",
         "issue": "旧页眉仍把已经落盘的本轮验收修订写成当前施工",
         "resolution": "改为本轮修订和逐章事件已完成，明确其他首埋重算与整卷独立复验仍待做",
         "status": "resolved"},
    ]
    manifest["tracking_action"] = {
        "kind": "not_required", "state_revision_before": 158, "state_revision_after": 158,
        "reason": "仅澄清既有问法、修错字和重复评注及文档施工状态，未改变事件、人物选择、材料来源或当前连续性",
    }
    write_json(manifest_path, manifest)
    stamp = ROOT / "追踪/修改影响/active.approved.json"
    checks = {"revision_gate": tool("revision_guard.py", "check", "--project", ROOT,
                                      "--input", manifest_path, "--stamp", stamp)}
    for chapter in (14, 97, 98, 99):
        if not (ROOT / f"追踪/章节提交/第{chapter:03d}章.json").exists():
            continue
        checks[f"sync_{chapter}"] = tool(
            "chapter_candidate.py", "sync", "--project", ROOT, "--chapter", chapter,
            "--revision-manifest", manifest_path, "--revision-stamp", stamp,
            "--reason", "逐章验收后清理重复解释及错字", "--confirm", "SYNC")
    checks["tracking"] = tool("tracking_commit.py", "check", "--project", ROOT)
    checks["doctor"] = tool("story_doctor.py", "--project", ROOT)
    checks["world_export"] = run(sys.executable, WORLD, "export", "--project", ROOT,
                                 "--start", 1, "--end", 99,
                                 "--tracking-tool", TOOLS / "tracking_commit.py")
    assert checks["tracking"]["state_revision"] == 158
    assert checks["doctor"]["status"] == "pass"
    assert checks["world_export"]["limitations"] == []
    assert_locked()
    write_json(WORK / "final_checks.json", checks)
    print(json.dumps({"status": "PASS", "state_revision": 158,
                      "required_checks": len(files), "gates": "16/16 PASS"}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("prepare", "apply"))
    args = parser.parse_args()
    {"prepare": prepare, "apply": apply}[args.phase]()
