from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import sys

book = Path(__file__).resolve().parents[2]
work = Path(__file__).resolve().parent
tools = book.parent / "skills/story-long-write/scripts"
backup = book / "备份/2026-10-06_第六批早期验收修复"

def read(path):
    return path.read_text(encoding="utf-8-sig")

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(script, *args):
    cp = subprocess.run([sys.executable, str(tools / script), *map(str,args)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if cp.returncode:
        raise RuntimeError(cp.stdout + cp.stderr)
    return cp.stdout.strip()

assert not (work / "baseline.json").exists(), "revision already begun"
gate_results = json.loads(read(work / "候选四门汇总.json"))
assert all(not row["failures"] and len(row["passed"]) == 4 for row in gate_results.values())

state = json.loads(read(book / "追踪/_tracking-state.json"))
assert state["state_revision"] == 104 and state["last_committed_chapter"] == 99
run("tracking_commit.py", "check", "--project", book)

groups = [work / "候选_001-016", work / "候选_017-033/全文", work / "候选_034-050", work / "候选_096-099"]
candidate_sources = {}
for group in groups:
    for candidate in group.glob("第*.md"):
        if candidate.name.startswith("细纲_"):
            continue
        original = book / "正文" / candidate.name
        if original.is_file() and read(candidate) != read(original):
            candidate_sources[original.relative_to(book).as_posix()] = candidate
for group in [work / "候选_细纲", work / "候选_096-099"]:
    for candidate in group.glob("细纲_第*.md"):
        original = book / "大纲" / candidate.name
        if read(candidate) != read(original):
            candidate_sources[original.relative_to(book).as_posix()] = candidate
for name in ["卷纲_第一卷.md", "伏笔总表.md"]:
    candidate = work / "候选_卷纲伏笔" / name
    original = book / "大纲" / name
    assert read(candidate) != read(original)
    candidate_sources[original.relative_to(book).as_posix()] = candidate

assert len([k for k in candidate_sources if k.startswith("正文/")]) >= 40
assert not backup.exists(), backup
backup.mkdir(parents=True)
hashes = {}
candidate_hashes = {}
for rel, candidate in sorted(candidate_sources.items()):
    original = book / rel
    target = backup / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(original, target)
    hashes[rel] = digest(original)
    candidate_hashes[rel] = digest(candidate)
for n in range(100, 104):
    path = next((book / "正文").glob(f"第{n:03d}章_*.md"))
    hashes[path.relative_to(book).as_posix()] = digest(path)
shutil.copytree(book / "追踪", backup / "追踪")

plan = {
    "schema_version": 1,
    "change_id": "sixth-early-acceptance-20261006",
    "summary": "001—050与096—099详细验收修订：年龄与电话、观察证据、材料保管、当前存在自主选择、24小时状态、早期记忆与卷纲伏笔映射",
    "semantic_change": True,
    "changed_files": sorted(candidate_sources),
    "affected_entities": ["镜辞", "沈竹", "原芽", "当前存在", "周远", "陈屿", "猫眼", "姜霁", "陈骁", "陈启明", "许棠", "杜经理", "徐师傅", "周衡", "守钟人", "老韩"],
    "affected_fact_ids": ["K001", "K007", "K008", "K011"],
    "affected_chapters": list(range(1, 51)) + [96, 97, 98, 99],
}
write_json(work / "baseline.json", state)
write_json(work / "baseline_hashes.json", hashes)
write_json(work / "candidate_sources.json", {rel: candidate.relative_to(book).as_posix() for rel, candidate in sorted(candidate_sources.items())})
write_json(work / "candidate_hashes.json", candidate_hashes)
write_json(work / "plan.json", plan)
run("revision_guard.py", "plan", "--project", book, "--input", work / "plan.json", "--output", book / "追踪/修改影响/active.json")

manifest = json.loads(read(book / "追踪/修改影响/active.json"))
index = []
pattern = re.compile("镜辞|沈竹|原芽|当前存在|陈骁|周衡|十七号|02:17|交接联|出库|身份")
for rel in manifest["required_checks"]:
    path = book / rel
    lines = read(path).splitlines()
    hits = [{"line": i+1, "text": line[:200]} for i,line in enumerate(lines) if pattern.search(line)]
    index.append({"file": rel, "sha256": digest(path), "lines": len(lines), "hits": hits[:8], "hit_count": len(hits)})
write_json(work / "dependency_index.json", index)
(work / "写前七关与修订裁定.md").write_text(
    "# 早期验收修订写前裁定\n\n基线r104/99，100—103正文哈希锁定。revision-governor未注册，由主线程按同一影响规则solo/direct执行。候选四门通过；源文、细纲、审查报告、人物与长期事实定点复核，required_checks完整读取和索引见dependency_index.json。\n\n"
    "人物七关：002只改锁定年龄；006/009灰衬衫仅报亲知的通话时点，不据此披露监听来源；016/017镜辞与猫眼只能用实见和有来源的照片。024—032姜霁要保可复核材料，不能凭职业跨私店权限，原件归原持有人，照片有限外查。040—041杜经理要保护住户又怕越权，临限到期恢复；父亲仍控制屋门。042当前存在不愿被旧群关系继续借用，知道自己的邀约和镜辞请求，能拒借号、退出聚餐，代价是旧位置被取消；约饭者因人数/订金独立取消留位；镜辞失去省事的询问路径，仍可另找来源。096—099周衡仍做自己的工作和修真坏表，姜霁接纳未见，镜辞不以空观察认证。逐项详证见候选_034-050/写前行动与影响说明.md及三段审查报告。\n\n写后必须核各候选未提前认证身份、没有新增权限、100—103哈希未变、追踪99当前快照未倒退；历史修订不伪造当年写前许可。\n",
    encoding="utf-8",
)
print(json.dumps({"changed_sources": len(candidate_sources), "body": sum(k.startswith('正文/') for k in candidate_sources), "outlines": sum('细纲' in k for k in candidate_sources), "required_checks": len(index), "backup": backup.as_posix()}, ensure_ascii=False))
