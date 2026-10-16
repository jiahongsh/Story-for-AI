"""来源绑定补录早期伏笔；保留原事务全部其他增量，不改正文。"""
from pathlib import Path
import copy, hashlib, importlib.util, json, os, shutil, subprocess, sys

BASE = Path(__file__).resolve().parent
BOOK = BASE.parents[1]
WORK = BASE / "伏笔记忆补录"
TOOLS = BOOK.parent / "skills/story-long-write/scripts"
STATE = BOOK / "追踪/_tracking-state.json"
MASTER = BOOK / "大纲/伏笔总表.md"

def read(p): return json.loads(p.read_text(encoding="utf-8-sig"))
def write(p, x):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def run(*args):
    r = subprocess.run(list(map(str,args)), capture_output=True, text=True, encoding="utf-8", errors="replace", env={**os.environ,"PYTHONUTF8":"1"})
    if r.returncode: raise RuntimeError(r.stdout+r.stderr)
    try: return json.loads(r.stdout)
    except json.JSONDecodeError: return {"output":r.stdout}
def module(name, path):
    s=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(s); sys.modules[name]=m; s.loader.exec_module(m); return m

tc=module("backfill_tracking",TOOLS/"tracking_commit.py")
ledger=module("backfill_evidence",BASE/"早期伏笔索引/build_early_foreshadow_index.py")

def make():
    state=read(STATE); assert state["state_revision"]==158
    assert "F051" not in state["foreshadow"] and "F052" not in state["foreshadow"]
    baseline=copy.deepcopy(state)
    changes={}; sources=[]
    mapping={"F01":("F001",32),"F09":("F051",11),"F11":("F052",17)}
    def row(ch, ident, planted, summary):
        old=baseline["foreshadow"].get(ident,{})
        changes.setdefault(ch,[]).append({"action":"upsert","id":ident,"summary":summary,"planted_chapter":planted,"planned_resolution_chapter":old.get("planned_resolution_chapter"),"status":"已埋","importance":old.get("importance","高")})
    for ch,core,stage,claim,anchors in ledger.EVIDENCE:
        if core not in mapping or stage.startswith("方法前置"): continue
        path=ledger.chapter_path(ch); lines=path.read_text(encoding="utf-8-sig").splitlines()
        for line,excerpt in anchors: assert excerpt in lines[line-1], (ch,line,excerpt)
        sources.append({"chapter":ch,"core":core,"stage":stage,"path":path.relative_to(BOOK).as_posix(),"sha256":sha(path),"anchors":anchors,"claim":claim})
        ident,planted=mapping[core]
        if core=="F09": claim += "姓名暂空；命名权和旧记录归属由她保留，未认证原主。"
        if core=="F11": claim += "保存版本不等于认证来源或身份；正式强化仍待后文。"
        row(ch,ident,planted,claim)
    row(9,"F003",9,"灰衬衫沿用周远取表身份，知沈竹、铁盒及前次通话时点，耳后短现细缝；真实姓名、知情来源和目的未明。")
    row(21,"F002",21,"泵站拆件处施工贴纸的编号异于恒准、批次格式相近；D4铝牌、台账、旧照片与现场分源保存，是否同链未证。")
    row(55,"F003",9,"009灰衬衫沿用周远取表身份；055五年前公开合影中的陈屿面部特征与他对上，胸牌写恒泰设施；不能证明连续五年任职。")
    row(56,"F003",9,"009灰衬衫沿用周远取表身份；055五年前合影中的陈屿外貌与他对上，056公示再现陈屿名并见极浅接缝；主体连续性与取表身份原因未证。")
    row(56,"F002",21,"021施工贴纸编号异于恒准而格式相近；至056恒准外包记录和恒泰设施公示分别保存，关联未证。")
    old=baseline["foreshadow"]["F001"]
    row(56,"F001",old["planted_chapter"],old["summary"])
    for ch,anchors in ((9,[(17,55),(185,205),(239,245)]),(21,[(83,95),(117,143)]),(55,[(61,79)]),(56,[(31,61)])):
        p=ledger.chapter_path(ch)
        sources.append({"chapter":ch,"path":p.relative_to(BOOK).as_posix(),"sha256":sha(p),"reviewed_line_ranges":anchors})
    tx=[]; sizes=[]
    for ch in sorted(changes):
        direct=BASE/f"事务/第{ch:03d}章.json"
        if direct.exists(): original=read(direct); source=direct
        else:
            candidates=[]
            for p in (BOOK/"创作运行").rglob("*事务*.json"):
                try: value=read(p)
                except (ValueError,OSError): continue
                if isinstance(value,dict) and value.get("chapter")==ch and value.get("mode")=="revision" and "delta" in value:
                    candidates.append((value.get("expected_state_revision",-1),p,value))
            assert candidates,ch
            _,source,original=max(candidates,key=lambda a:a[0])
        t=copy.deepcopy(original); t["expected_state_revision"]=state["state_revision"]
        t["context"]={k:copy.deepcopy(state["context"][k]) for k in ("position","long_term_constraints","active_character_names","continuity_risks")}
        t["character_snapshots"]={r["name"]:copy.deepcopy(state["characters"][r["name"]]) for r in t["delta"].get("character_changes",[]) if r["name"] in state["characters"]}
        for field,section in (("fact_changes","facts"),("timeline_events","timeline")):
            t["delta"][field]=[{"action":"upsert",**{k:v for k,v in state[section][r["id"]].items() if k not in ("updated_chapter","first_chapter","first_recorded_chapter")}} for r in t["delta"].get(field,[]) if r["id"] in state[section]]
        by_id={r["id"]:r for r in t["delta"].get("foreshadow_changes",[])}
        by_id.update({r["id"]:r for r in changes[ch]}); t["delta"]["foreshadow_changes"]=list(by_id.values())
        n=tc.normalize_transaction(state,t); tc.enforce_continuity_guard(state,n)
        size=len(tc.render_delta(ch,t["chapter_title"],n["delta"],set(state["characters"])).encode("utf-8")); assert size<=3072,(ch,size)
        state=tc.merge_transaction(state,n); tx.append(t); sizes.append({"chapter":ch,"bytes":size,"original_transaction":source.relative_to(BOOK).as_posix()})
    for key in ("characters","facts","context","timeline","last_committed_chapter"):
        assert state[key]==baseline[key], key
    for ident,value in baseline["foreshadow"].items():
        if ident not in ("F002","F003"): assert state["foreshadow"][ident]==value,ident
    write(WORK/"baseline.json",baseline); write(WORK/"expected_state.json",state)
    write(WORK/"来源及试提交.json",{"status":"PASS","revision_before":158,"revision_after":state["state_revision"],"transactions":sizes,"prose_evidence":sources,"master_sha256":sha(MASTER),"authority_sha256":sha(STATE),"scope_note":"只补已核核心伏笔里程碑；其他伏笔仍待核。旧章不补造七关审批。"})
    for t in tx: write(WORK/f"事务/第{t['chapter']:03d}章.json",t)
    text=MASTER.read_text(encoding="utf-8-sig")
    text=text.replace("`追踪/伏笔.md` 是本文件的派生执行视图。","`追踪/_tracking-state.json` 是唯一结构化状态权威；`追踪/伏笔.md` 由追踪工具生成。CORE规划编号与TRACK执行编号须显式对应。")
    text += "\n## 已核CORE与TRACK对应（2026-10-07）\n\n| 规划编号 | 执行编号 | 已核范围与边界 |\n|---|---|---|\n| CORE F01 | TRACK F001 | 032首埋，033/045/046/050推进；02:17来源未知。 |\n| CORE F09 | TRACK F051 | 011空白姓名页首埋，042自主拒绝与关系代价推进；姓名和身份仍未确定。 |\n| CORE F11 | TRACK F052 | 010仅方法前置；017猫眼角色基础，019/038/045/050/096—098推进；正式强化待写。 |\n| CORE F03 | TRACK F045—F048 | 095—098八年履历逐阶段推进；100首缝属于锁定正文，未写入截至099的追踪。 |\n| CORE F02/F04 | 暂无直接对应 | 043/039仅前兆，正式指标和四分工尚未埋设。 |\n\nTRACK F002/F003是施工来源、灰衬衫线，不能按编号当作CORE F02/F03。009不提前知道陈屿，021不提前知道恒泰；055—056的后续信息分别入账。未列章节与其他CORE项仍须核对，逐章记录的“无”只表示该事务没有伏笔状态变更。\n"
    (WORK/"候选_伏笔总表.md").write_text(text,encoding="utf-8")
    prose55=ledger.chapter_path(55); content=prose55.read_text(encoding="utf-8-sig")
    assert content.count("陈屿的五年工牌")==1
    candidate55=WORK/"候选_第055章.md"
    candidate55.write_text(content.replace("陈屿的五年工牌","五年前合影里的陈屿胸牌"),encoding="utf-8")
    gates={}
    for name,flags in (("language_gate.js",[]),("check-style-hygiene.js",["--check","--fail-on=blocking"]),("check-ai-patterns.js",["--check","--fail-on=blocking"]),("check-degeneration.js",["--check","--language=zh","--fail-on=blocking"])):
        gates[name]=run("node",TOOLS/name,*flags,candidate55)
    write(WORK/"第055章候选四门.json",gates)
    plan={"schema_version":1,"change_id":"sixth-foreshadow-memory-20261007","summary":"来源绑定补录早期伏笔阶段，明确CORE/TRACK映射和历史知情边界；055工牌改为五年前合影中的胸牌","semantic_change":True,"changed_files":["大纲/伏笔总表.md",prose55.relative_to(BOOK).as_posix()],"affected_entities":["镜辞","猫眼","当前存在","陈屿"],"affected_fact_ids":[],"affected_chapters":sorted(changes)}
    write(WORK/"plan.json",plan)
    run(sys.executable,TOOLS/"revision_guard.py","plan","--project",BOOK,"--input",WORK/"plan.json","--output",WORK/"manifest_pre.json")
    print(json.dumps({"status":"prepared","transactions":len(tx),"revision_after":state["state_revision"]}))

def apply():
    proof=read(WORK/"来源及试提交.json"); assert sha(STATE)==proof["authority_sha256"] and sha(MASTER)==proof["master_sha256"]
    backup=BOOK/"备份/2026-10-07_第六批伏笔记忆补录"
    prose55=ledger.chapter_path(55)
    for p in (STATE,MASTER,prose55):
        dest=backup/p.relative_to(BOOK); dest.parent.mkdir(parents=True,exist_ok=True); assert not dest.exists(); shutil.copy2(p,dest); assert sha(dest)==sha(p)
    for evidence in proof["prose_evidence"]: assert sha(BOOK/evidence["path"])==evidence["sha256"]
    results=[]
    for p in sorted((WORK/"事务").glob("*.json")):
        results.append(run(sys.executable,TOOLS/"tracking_commit.py","commit","--project",BOOK,"--input",p))
    assert read(STATE)==read(WORK/"expected_state.json")
    MASTER.write_bytes((WORK/"候选_伏笔总表.md").read_bytes())
    prose55.write_bytes((WORK/"候选_第055章.md").read_bytes())
    active=BOOK/"追踪/修改影响/active.json"
    run(sys.executable,TOOLS/"revision_guard.py","plan","--project",BOOK,"--input",WORK/"plan.json","--output",active)
    m=read(active); m["checked_files"]=m["required_checks"]
    write(WORK/"影响来源.json",[{"path":p,"sha256":sha(BOOK/p)} for p in m["required_checks"]])
    m["conflicts"]=[{"source":"大纲/伏笔总表.md","target":"追踪/_tracking-state.json","severity":"S2","issue":"CORE与TRACK编号无显式对应、早期伏笔里程碑缺失且两条摘要混入后文知情","resolution":"串行历史事务补已核首埋/推进，保留原事件与事实，055—056恢复后续阶段；其余未核伏笔保留待核","status":"resolved"}]
    m["tracking_action"]={"kind":"commit","state_revision_before":158,"state_revision_after":proof["revision_after"],"reason":"来源绑定的历史伏笔阶段补录及055证据措辞修正；接纳进度仍为099"}; write(active,m)
    checks={"commits":results}
    checks["revision_gate"]=run(sys.executable,TOOLS/"revision_guard.py","check","--project",BOOK,"--input",active,"--stamp",BOOK/"追踪/修改影响/active.approved.json")
    checks["tracking"]=run(sys.executable,TOOLS/"tracking_commit.py","check","--project",BOOK)
    receipt=BOOK/"追踪/章节提交/第055章.json"
    if receipt.exists():
        checks["sync055"]=run(sys.executable,TOOLS/"chapter_candidate.py","sync","--project",BOOK,"--chapter",55,"--revision-manifest",active,"--revision-stamp",BOOK/"追踪/修改影响/active.approved.json","--reason","修正五年前合影胸牌的证据范围","--confirm","SYNC")
    checks["doctor"]=run(sys.executable,TOOLS/"story_doctor.py","--project",BOOK)
    checks["world_export"]=run(sys.executable,BOOK.parent/"skills/story-world-engine/scripts/world_gate.py","export","--project",BOOK,"--start",1,"--end",99,"--tracking-tool",TOOLS/"tracking_commit.py")
    hashes=read(BASE/"baseline_hashes.json")
    for ch in range(100,104):
        p=next((BOOK/"正文").glob(f"第{ch:03d}章_*.md")); assert sha(p)==hashes[p.relative_to(BOOK).as_posix()]
    assert checks["doctor"]["status"]=="pass" and checks["world_export"]["limitations"]==[]
    checks["locked_100_103"]="hash_unchanged"; write(WORK/"final_checks.json",checks)
    print(json.dumps({"status":"PASS","revision":proof["revision_after"],"transactions":len(results)}))

if __name__=="__main__": {"prepare":make,"apply":apply}[sys.argv[1]]()
