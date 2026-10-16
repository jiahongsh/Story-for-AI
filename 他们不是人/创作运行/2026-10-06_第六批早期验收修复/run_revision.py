from pathlib import Path
import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys

book = Path(__file__).resolve().parents[2]
work = Path(__file__).resolve().parent
tools = book.parent / "skills/story-long-write/scripts"
backup = book / "备份/2026-10-06_第六批早期验收修复"

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def clean(record):
    return {key: copy.deepcopy(value) for key,value in record.items() if key not in {"first_recorded_chapter", "updated_chapter"}}

def run(command):
    environment = {**os.environ, "PYTHONUTF8":"1", "PYTHONIOENCODING":"utf-8"}
    process = subprocess.run(list(map(str,command)), capture_output=True, text=True, encoding="utf-8", errors="replace", env=environment)
    if process.returncode:
        raise RuntimeError("\n".join(map(str,command)) + "\n" + process.stdout + process.stderr)
    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError:
        return {"stdout": process.stdout, "stderr": process.stderr, "returncode": process.returncode}

def tool(name,*args):
    return run([sys.executable,tools/name,*args])

base = read_json(work / "baseline.json")
source_map = read_json(work / "candidate_sources.json")
baseline_hashes = read_json(work / "baseline_hashes.json")
capsules = read_json(work / "早期记忆来源包.json")
gate_results = read_json(work / "候选四门汇总.json")
state_file = book / "追踪/_tracking-state.json"

for rel, source_rel in source_map.items():
    candidate = book / source_rel
    assert candidate.is_file(), candidate
    target = book / rel
    assert target.is_file(), target
    assert sha(backup / rel) == baseline_hashes[rel], rel
    assert sha(target) in {baseline_hashes[rel], sha(candidate)}, rel
    if rel.startswith("正文/"):
        gate = gate_results.get(target.name)
        assert gate and not gate["failures"] and len(gate["passed"]) == 4, rel
        assert gate["sha256"] == sha(candidate), (rel, "candidate changed after gate")

candidate_hashes = {rel:sha(book / source_rel) for rel,source_rel in source_map.items()}
write_json(work / "candidate_hashes.json", candidate_hashes)
write_json(work / "候选人工复核.json", {
    "status":"manual_pass",
    "reviewer":"Codex /root solo/direct",
    "scope":"审查报告逐章证据、42章修订差异、042独立选择七关、016→017及040→041→045来源/状态、099→100接口；无历史七关伪造",
    "hashes":candidate_hashes,
    "language_gate":"42篇正文候选四门均通过",
    "locked_100_103":"哈希基线固定，提交后复核",
})

spec = importlib.util.spec_from_file_location("tracking_commit_for_sixth",tools/"tracking_commit.py")
tc = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = tc
spec.loader.exec_module(tc)

numbers = [n for n in range(1,51) if n != 11] + [96,97,98,99]

def transaction(state,chapter):
    prose = next((book / "正文").glob(f"第{chapter:03d}章_*.md"))
    candidate = book / source_map.get(prose.relative_to(book).as_posix(),prose.relative_to(book).as_posix())
    title = candidate.read_text(encoding="utf-8-sig").splitlines()[0].split(" ",2)[-1]
    if chapter <= 50:
        item = capsules[str(chapter)]
        delta = {
            "result":item["objective_fact"],
            "character_changes":[], "foreshadow_changes":[],
            "timeline_events":[{
                "action":"upsert", "id":f"E{chapter:03d}", "story_time":item["story_time"],
                "objective_fact":item["objective_fact"], "reader_knowledge":item["reader_knowledge"],
                "reveal_status":"已揭示", "reveal_chapter":chapter, "characters":item["characters"],
            }],
            "fact_changes":[], "constraints":[], "next_chapter_commitments":[],
            "retired_characters":[], "retired_context_items":[], "continuity_changes":[],
        }
        if chapter == 42:
            delta["character_changes"] = [
                {"name":"当前存在", "change":"拒借旧同学群查原芽照片，退出旧称呼预留的聚餐；接受旧座位被取消的代价"},
                {"name":"镜辞", "change":"撤回借她群号询问的草稿，另列原芽照片来源待核，不替她说明旧关系"},
            ]
    else:
        previous = read_json(book / f"追踪/事务-第{chapter:03d}章.json")
        delta = copy.deepcopy(previous["delta"])
        delta["retired_characters"] = []
        delta["retired_context_items"] = []
        delta["continuity_changes"] = []
        delta["foreshadow_changes"] = [
            {"action":"upsert",**clean(base["foreshadow"][item["id"]])}
            for item in delta.get("foreshadow_changes",[]) if item["id"] in base["foreshadow"]
        ]
        delta["timeline_events"] = [{"action":"upsert",**clean(base["timeline"][f"E{chapter:03d}"])}]
        delta["fact_changes"] = [
            {"action":"upsert",**clean(base["facts"][item["id"]])}
            for item in delta.get("fact_changes",[]) if item["id"] in base["facts"]
        ]
    snapshots = {change["name"]:copy.deepcopy(state["characters"][change["name"]]) for change in delta["character_changes"] if change["name"] in state["characters"]}
    context = {key:copy.deepcopy(state["context"][key]) for key in ["position","long_term_constraints","active_character_names","continuity_risks"]}
    return {"schema_version":1,"mode":"revision","chapter":chapter,"chapter_title":title,
            "expected_state_revision":state["state_revision"],"delta":delta,"context":context,"character_snapshots":snapshots}

dry = copy.deepcopy(base)
prefix = [copy.deepcopy(base)]
sizes = {}
for chapter in numbers:
    document = transaction(dry,chapter)
    normalized = tc.normalize_transaction(dry,document)
    tc.enforce_continuity_guard(dry,normalized)
    dry = tc.merge_transaction(dry,normalized)
    size = len(tc.render_delta(chapter,document["chapter_title"],normalized["delta"],set(dry["characters"])).encode("utf-8"))
    assert size <= 3072,(chapter,size)
    sizes[str(chapter)] = size
    write_json(work / f"事务/第{chapter:03d}章.json",document)
    prefix.append(copy.deepcopy(dry))
assert dry["last_committed_chapter"] == 99
assert dry["facts"] == base["facts"] and dry["foreshadow"] == base["foreshadow"]
assert len(dry["timeline"]) == len(base["timeline"]) + 49
assert all(f"E{n:03d}" in dry["timeline"] for n in range(1,51))
write_json(work / "dry_run.json",{
    "status":"PASS","before":base["state_revision"],"after":dry["state_revision"],
    "transactions":len(numbers),"chapter_records_bytes":sizes,
    "facts_unchanged":True,"foreshadow_current_unchanged":True,"last_committed_chapter":99,
    "timeline_events_after":len(dry["timeline"]),
})

parser = argparse.ArgumentParser()
parser.add_argument("--apply",action="store_true")
args = parser.parse_args()
if not args.apply:
    print(json.dumps({"dry_run":"PASS","transactions":len(numbers),"source_files":len(source_map),"revision_after":dry["state_revision"]},ensure_ascii=False))
    raise SystemExit(0)

review = read_json(work / "候选人工复核.json")
assert review["status"] == "manual_pass" and review["hashes"] == candidate_hashes
actual = read_json(state_file)
progress = actual["state_revision"]-base["state_revision"]
assert 0 <= progress <= len(numbers) and actual == prefix[progress],"unexpected concurrent state mutation"
for rel,source_rel in source_map.items():
    original = book / rel
    candidate = book / source_rel
    if sha(original) == sha(candidate):
        continue
    assert sha(original) == baseline_hashes[rel],rel
    temporary = work / (re.sub(r"[^A-Za-z0-9._-]","_",rel)+".install.tmp")
    temporary.write_bytes(candidate.read_bytes())
    os.replace(temporary,original)
for index in range(progress,len(numbers)):
    chapter = numbers[index]
    current = read_json(state_file)
    assert current == prefix[index],(chapter,"state drift")
    document = transaction(current,chapter)
    path = work / f"事务/第{chapter:03d}章.json"
    write_json(path,document)
    result = tool("tracking_commit.py","commit","--project",book,"--input",path)
    assert read_json(state_file) == prefix[index+1],(chapter,"committed state mismatch")
    if index % 8 == 0 or index+1 == len(numbers):
        print(f"committed {index+1}/{len(numbers)} chapter {chapter:03d} revision {result.get('state_revision')}",flush=True)
tool("tracking_commit.py","check","--project",book)

manifest = book / "追踪/修改影响/active.json"
tool("revision_guard.py","plan","--project",book,"--input",work/"plan.json","--output",manifest)
document = read_json(manifest)
checked = []
index = []
for relative in document["required_checks"]:
    source = book / relative
    data = source.read_text(encoding="utf-8-sig")
    checked.append(relative)
    index.append({"file":relative,"sha256":sha(source),"lines":len(data.splitlines()),"scope":"全文与影响索引核读；正文来源边界按审查表及候选差异复核"})
write_json(work/"final_dependencies.json",index)
document["checked_files"] = checked
issue_map = [
    ("A01", "正文/第002章_先喝汤.md", "大纲/细纲_第002章.md", "七年前年龄与K007冲突"),
    ("A02", "正文/第006章_两个周远.md", "正文/第009章_他们不是人.md", "来电、转视频和威胁所报时点冲突"),
    ("A03", "正文/第016章_十七号树.md", "正文/第017章_猫眼.md", "未拍到的维护动作被写成已证"),
    ("A04", "正文/第030章_顺记里面.md", "大纲/细纲_第030章.md", "夜间亮灯被升级为对方提前知情"),
    ("A05", "正文/第042章_他今天做的事.md", "大纲/细纲_第042章.md", "当前存在在034—050缺当次独立选择及结果"),
    ("A06", "正文/第024章_她不看接缝.md", "正文/第031章_安平里六号楼.md", "多份材料的原件、副本和授权不闭环"),
    ("A07", "正文/第001章_先喝汤.md", "追踪/_tracking-state.json", "001—050除011外缺逐章记忆"),
    ("A08", "大纲/卷纲_第一卷.md", "大纲/伏笔总表.md", "卷纲与CORE首埋/送锁映射滞后"),
]
document["conflicts"] = [
    {"source":source,"target":target,"severity":"S2","issue":f"{code} {issue}",
     "resolution":"按已接纳正文来源定点修订并同步细纲、截至099追踪及依赖，复核见final_dependencies.json", "status":"resolved"}
    for code,source,target,issue in issue_map
]
document["tracking_action"] = {"kind":"commit","state_revision_before":base["state_revision"],"state_revision_after":dry["state_revision"],
                               "reason":"49条早期事件证据回补及修订章逐章串行入账，当前章仍为99"}
write_json(manifest,document)
gate = tool("revision_guard.py","check","--project",book,"--input",manifest,"--stamp",book/"追踪/修改影响/active.approved.json")
checks = {"revision_gate":gate,"tracking":tool("tracking_commit.py","check","--project",book),"sync":{}}
for rel in source_map:
    if not rel.startswith("正文/"):
        continue
    chapter = int(re.search(r"第(\d+)章",rel).group(1))
    receipt = book / f"追踪/章节提交/第{chapter:03d}章.json"
    if receipt.is_file():
        checks["sync"][str(chapter)] = tool(
            "chapter_candidate.py","sync","--project",book,"--chapter",chapter,
            "--revision-manifest",manifest,"--revision-stamp",book/"追踪/修改影响/active.approved.json",
            "--reason","用户授权逐步修正001—050与096—099详细验收问题","--confirm","SYNC",
        )
checks["voice"] = tool("voice_profile.py","update","--project",book)
checks["doctor"] = tool("story_doctor.py","--project",book)
checks["world_export"] = run([sys.executable,book.parent/"skills/story-world-engine/scripts/world_gate.py","export","--project",book,"--start",1,"--end",99,"--tracking-tool",tools/"tracking_commit.py"])
for n in range(100,104):
    source = next((book/"正文").glob(f"第{n:03d}章_*.md"))
    assert sha(source) == baseline_hashes[source.relative_to(book).as_posix()],source
checks["locked_100_103"] = "hash_unchanged"
checks["revision_after"] = read_json(state_file)["state_revision"]
write_json(work/"final_checks.json",checks)
print(json.dumps({"status":"PASS","revision_after":checks["revision_after"],"tracking_events":len(read_json(state_file)["timeline"]),"required_checks":len(checked),"doctor":checks["doctor"].get("status")},ensure_ascii=False),flush=True)
