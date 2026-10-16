from pathlib import Path
import copy, hashlib, importlib.util, json, os, shutil, subprocess, sys

WORK=Path(__file__).resolve().parent; BOOK=WORK.parents[1]
TOOLS=BOOK.parent/'skills/story-long-write/scripts'; STATE=BOOK/'追踪/_tracking-state.json'
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,x): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def run(*args):
    r=subprocess.run(list(map(str,args)),capture_output=True,text=True,encoding='utf-8',errors='replace',env={**os.environ,'PYTHONUTF8':'1'})
    if r.returncode: raise RuntimeError(r.stdout+r.stderr)
    try: return json.loads(r.stdout)
    except json.JSONDecodeError: return {'output':r.stdout}
def loadmodule(name,p):
    s=importlib.util.spec_from_file_location(name,p); m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
tc=loadmodule('seventh_tracking',TOOLS/'tracking_commit.py')
F09={66:'旧记忆与醒后行为分轨；旧证件仍提供社会入口，空白姓名页不能代替证件。',67:'因暂不出示旧证错车，后来用旧证买票；票面用途不等于她认同旧名字。',68:'老板娘先认修锁者，留电话并约定再来须另谈工钱；登记名字仍是芽，能力来源未判。',69:'她主动联系唐宁却拒继承旧友位置；唐宁拒当前亲近和再约，两人未和解。',70:'她因当前胃疼喝汤，习惯退出验人；唐宁消息未回，不据喝汤认旧身份。',72:'三天零件活开始，老秦付清首日工钱并用工作称呼记账；她有齐整偏好，也拒无限添活。',74:'原芽救学的后果由方远亲历核对；她拒领功，却可以学习方远的修车方法。',76:'她承认模仿旧动作的具体伤害并道歉，承担不被原谅的后果；余额144，未用好行为抵销伤害。',77:'唐宁限定讲旧事；镜辞的过度负责使旧人及当前存在隐瞒，当前关系未恢复成青梅。',78:'她自主决定回北河，接受报平安与风险建议，不接受批准或尾随；票已买，旧物待分。',79:'旧物留存、外套暂借；当前物品与责任页带走。她去赶车，镜辞未尾随；命名、原主及旧物归属仍未判。'}
F01={71:'02:17覆盖本案复核页；纸质副本、日志及502机械门链仍在，未提供可见性通过。',73:'今早纸与正常屏并列；许棠卡仍红，恒泰巡检名字只作公开来源，上游发起者未知。',88:'本案将家庭关系和住宅进入分栏并换机械锁芯；02:17关系同步后，本地住宅通行未恢复。只是本案临时措施，上游及身份仍未知。'}
RESOLVED={
'F037':(88,'本案家庭关系同步回正常，但拆开的住宅进入字段及更换的机械通道未恢复；局部挡住放行，不注销婚姻或长期居住主张。'),
'F038':(89,'旧仓库独立生活痕迹已记录；临时控制由现场破坏和异常力量风险触发，不因另有住处抓人。'),
'F039':(90,'短介入降低现实危险，却未确认原主体连续存在；强记忆残留不作救出证明，现场决定停止加深。'),
'F040':(91,'周诚近距未见，仍不认证；右肩伤转述使普通解释优先，异常观察暂缓，限定申请伤情资料。'),
'F041':(92,'肩伤与家庭适应解释主要动作差异，周诚撤案、撤点；只回收本案解释任务，不建立全体异常刻度。'),
'F042':(93,'旧行动员署名更正留存；老李旧字段拆为信息残余、当前主体连续性及原主未知三栏，旧案曾救人记录保留。'),
'F043':(94,'十一份状态分类获准查阅，周衡暂不高风险；镜辞选择低干扰跟查，不开放全库或围猎。'),
'F044':(95,'七天生活记录及公开市场照片核过，首次生活场面观察开始；不逼异常，回填嫌疑另由旧版本核对。'),
'F045':(96,'八年纸档到店，回填嫌疑进入分段核验；只兑现材料引入，实施者及近距接缝仍未定。'),
'F046':(97,'前三年后期改写或回填由独立版本冲突支持；实施者及当年事实未明，不指认周衡亲手操作。'),
'F047':(98,'后五年有分散系统外关系后果，和早期回填并列保存；不据此直接认证当前主体。'),
'F048':(99,'周衡已持真的故障表到店，近距接单未确认接缝；明日取表，首缝期待移交F049。')}

def original(ch):
    choices=[]
    paths=[BOOK/f'追踪/事务-第{ch:03d}章.json']
    paths+=list((BOOK/'创作运行').rglob('*.json'))
    for p in paths:
        if not p.exists() or WORK in p.parents:continue
        try:v=read(p)
        except (ValueError,OSError):continue
        if isinstance(v,dict) and v.get('chapter')==ch and 'delta' in v and v.get('mode') in ('append','revision'):
            choices.append((v.get('expected_state_revision',-1),str(p),v))
    assert choices,ch
    _,p,v=max(choices,key=lambda x:x[0]);return Path(p),v

def prepare():
    state=read(STATE);assert state['state_revision']==175
    baseline=copy.deepcopy(state);plan=read(WORK/'plan.json')
    chapters={ch for ch in plan['affected_chapters'] if ch<=99}|{ch for ch,_ in RESOLVED.values()}
    transactions=[];proof=[]
    for ch in sorted(chapters):
        source,t=original(ch);t=copy.deepcopy(t);t['mode']='revision';t['expected_state_revision']=state['state_revision']
        t['delta']['continuity_changes']=[];t['delta']['retired_characters']=[];t['delta']['retired_context_items']=[]
        t['context']={k:copy.deepcopy(state['context'][k]) for k in ('position','long_term_constraints','active_character_names','continuity_risks')}
        t['character_snapshots']={r['name']:copy.deepcopy(state['characters'][r['name']]) for r in t['delta'].get('character_changes',[]) if r['name'] in state['characters']}
        for field,section in (('timeline_events','timeline'),('fact_changes','facts'),('foreshadow_changes','foreshadow')):
            t['delta'][field]=[{'action':'upsert',**{k:v for k,v in state[section][r['id']].items() if k not in ('updated_chapter','first_recorded_chapter')}} for r in t['delta'].get(field,[]) if r['id'] in state[section]]
        if ch==62:
            k={k:v for k,v in state['facts']['K005'].items() if k not in ('updated_chapter','first_recorded_chapter')};k['object']=k['object'].replace('十一点二十','八点二十')
            t['delta']['fact_changes']=[r for r in t['delta']['fact_changes'] if r['id']!='K005']+[{'action':'upsert',**k}]
            for e in t['delta']['timeline_events']:
                for k in ('objective_fact','reader_knowledge','story_time'):e[k]=e[k].replace('11:20','08:20').replace('十一点二十','八点二十')
            for r in t['delta']['foreshadow_changes']:r['summary']=r['summary'].replace('十一点二十','八点二十')
            t['delta']['result']=t['delta']['result'].replace('11:20','08:20').replace('十一点二十','八点二十')
        by_id={r['id']:r for r in t['delta']['foreshadow_changes']}
        for ident,summary in [('F051',F09[ch])] if ch in F09 else []:
            by_id[ident]={'action':'upsert',**{k:v for k,v in state['foreshadow'][ident].items() if k!='updated_chapter'}};by_id[ident]['summary']=summary
        if ch in F01:
            by_id['F001']={'action':'upsert',**{k:v for k,v in state['foreshadow']['F001'].items() if k!='updated_chapter'}};by_id['F001']['summary']=F01[ch]
        for ident,(at,summary) in RESOLVED.items():
            if at==ch:
                by_id[ident]={'action':'upsert',**{k:v for k,v in state['foreshadow'][ident].items() if k!='updated_chapter'}};by_id[ident]['summary']=summary
        t['delta']['foreshadow_changes']=list(by_id.values())
        n=tc.normalize_transaction(state,t);tc.enforce_continuity_guard(state,n)
        size=len(tc.render_delta(ch,t['chapter_title'],n['delta'],set(state['characters'])).encode('utf-8'));assert size<=3072,(ch,size)
        state=tc.merge_transaction(state,n);transactions.append(t);proof.append({'chapter':ch,'bytes':size,'source':source.relative_to(BOOK).as_posix()})
    for k in ('characters','context','last_committed_chapter'):assert state[k]==baseline[k],k
    for ident,r in baseline['facts'].items():
        if ident!='K005':assert state['facts'][ident]==r,ident
    write(WORK/'试提交.json',{'status':'PASS','revision_before':175,'revision_after':state['state_revision'],'transactions':proof,'current_character_snapshots_unchanged':True})
    write(WORK/'expected_state.json',state)
    for t in transactions:write(WORK/f"事务/第{t['chapter']:03d}章.json",t)
    print(json.dumps({'status':'prepared','transactions':len(transactions),'revision_after':state['state_revision']}))

def apply():
    assert read(STATE)==read(WORK/'baseline.json')
    hashes=read(WORK/'baseline_hashes.json');plan=read(WORK/'plan.json')
    # 审查采用当前正式来源，候选不反推未发生行动。
    backup=BOOK/'备份/2026-10-07_第七批全卷收尾'
    for relative in plan['changed_files']+['追踪/_tracking-state.json']:
        p=BOOK/relative;dest=backup/relative;dest.parent.mkdir(parents=True,exist_ok=True);assert not dest.exists();shutil.copy2(p,dest);assert sha(dest)==sha(p)
    for ch in range(100,104):
        p=next((BOOK/'正文').glob(f'第{ch:03d}章_*.md'));assert sha(p)==hashes[p.relative_to(BOOK).as_posix()]
    for relative in plan['changed_files']:
        p=BOOK/relative
        if relative=='大纲/伏笔总表.md':candidate=WORK/'候选_伏笔总表.md'
        elif relative.startswith('正文/'):candidate=WORK/'候选'/p.name;assert sha(p)==hashes[relative]
        elif relative.startswith('大纲/'):candidate=WORK/'候选细纲'/p.name
        else:raise ValueError(relative)
        if relative.startswith('正文/') and int(p.name[1:4]) in (102,103):candidate=WORK/'锁定章待批准'/p.name
        p.write_bytes(candidate.read_bytes())
    commits=[]
    for p in sorted((WORK/'事务').glob('*.json')):commits.append(run(sys.executable,TOOLS/'tracking_commit.py','commit','--project',BOOK,'--input',p))
    assert read(STATE)==read(WORK/'expected_state.json')
    active=BOOK/'追踪/修改影响/active.json'
    run(sys.executable,TOOLS/'revision_guard.py','plan','--project',BOOK,'--input',WORK/'plan.json','--output',active)
    m=read(active);m['checked_files']=m['required_checks']
    write(WORK/'影响来源.json',[{'path':p,'sha256':sha(BOOK/p)} for p in m['required_checks']])
    m['conflicts']=[{'source':'正文/第062章_推荐店.md','target':'追踪/_tracking-state.json','severity':'S2','issue':'推荐名单11:20新增晚于孙立09:40首次持地址纸进店；章级长线推进与局部回收摘要不完整','resolution':'新版改为08:20，正文/细纲/K005/E062/F011同章修订；补F001及F051实际阶段，校正局部回收范围','status':'resolved'}]
    m['tracking_action']={'kind':'commit','state_revision_before':175,'state_revision_after':read(STATE)['state_revision'],'reason':'已接纳历史范围的来源与阶段记忆修正'};write(active,m)
    stamp=BOOK/'追踪/修改影响/active.approved.json'
    checks={'commits':commits}
    checks['revision_gate']=run(sys.executable,TOOLS/'revision_guard.py','check','--project',BOOK,'--input',active,'--stamp',stamp)
    for p in (WORK/'候选').glob('*.md'):
        ch=int(p.name[1:4]);receipt=BOOK/f'追踪/章节提交/第{ch:03d}章.json'
        if receipt.exists():run(sys.executable,TOOLS/'chapter_candidate.py','sync','--project',BOOK,'--chapter',ch,'--revision-manifest',active,'--revision-stamp',stamp,'--reason','第七批限定修正与重复尾声收尾','--confirm','SYNC')
    checks['tracking']=run(sys.executable,TOOLS/'tracking_commit.py','check','--project',BOOK)
    checks['doctor']=run(sys.executable,TOOLS/'story_doctor.py','--project',BOOK)
    checks['world_export']=run(sys.executable,BOOK.parent/'skills/story-world-engine/scripts/world_gate.py','export','--project',BOOK,'--start',1,'--end',99,'--tracking-tool',TOOLS/'tracking_commit.py')
    assert checks['doctor']['status']=='pass' and checks['world_export']['limitations']==[]
    for ch in (100,101):
        p=next((BOOK/'正文').glob(f'第{ch:03d}章_*.md'));assert sha(p)==hashes[p.relative_to(BOOK).as_posix()]
    checks['locked_100_101']='hash_unchanged';checks['limited_102_103']='user_authorized_wording_only';write(WORK/'final_checks.json',checks)
    print(json.dumps({'status':'PASS','revision':read(STATE)['state_revision'],'commits':len(commits)}))

if __name__=='__main__':{'prepare':prepare,'apply':apply}[sys.argv[1]]()
