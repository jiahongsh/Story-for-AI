from pathlib import Path
import json,copy,hashlib,subprocess,sys,os,shutil,re,importlib.util,difflib
BOOK=Path(__file__).resolve().parents[2];ROOT=Path(__file__).resolve().parent;TOOLS=BOOK.parent/'skills/story-long-write/scripts'
ENV={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'}
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,o):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def prose(n):return next((BOOK/'正文').glob(f'第{n:03d}章_*.md'))
def text(p):return p.read_text(encoding='utf-8-sig')
def rep(s,a,b):assert s.count(a)==1,(a,s.count(a));return s.replace(a,b)
def between(s,a,b,new):i=s.index(a);j=s.index(b,i);return s[:i]+new+s[j:]
def tail(s,a,new):return s[:s.index(a)]+new
def run(args):
    r=subprocess.run(list(map(str,args)),capture_output=True,text=True,encoding='utf-8',env=ENV)
    if r.returncode:raise RuntimeError(r.stdout+r.stderr)
    try:return json.loads(r.stdout)
    except json.JSONDecodeError:return {'stdout':r.stdout,'stderr':r.stderr,'returncode':r.returncode}
def tool(script,*args):return run([sys.executable,TOOLS/script,*args])
def clean(obj):return {k:copy.deepcopy(v) for k,v in obj.items() if k not in ['updated_chapter','first_recorded_chapter']}
def begin(label,numbers,entities,facts,summary,gates):
    work=ROOT/label;work.mkdir(exist_ok=True);assert not (work/'baseline.json').exists()
    base=read(BOOK/'追踪/_tracking-state.json');tool('tracking_commit.py','check','--project',BOOK)
    write(work/'baseline.json',base);changed=[];hashes={};backup=BOOK/'备份'/('2026-10-06_第五批_'+label)
    for n in numbers:
        for p in [prose(n),BOOK/f'大纲/细纲_第{n:03d}章.md']:
            rel=p.relative_to(BOOK).as_posix();d=backup/rel;d.parent.mkdir(parents=True,exist_ok=True);assert not d.exists();shutil.copy2(p,d)
            changed.append(rel);hashes[rel]=sha(p)
    for n in range(100,104):p=prose(n);hashes[p.relative_to(BOOK).as_posix()]=sha(p)
    write(work/'baseline_hashes.json',hashes)
    plan={'schema_version':1,'change_id':'fifth-'+label.split('_')[0]+'-20261006','summary':summary,'semantic_change':True,
          'changed_files':changed,'affected_chapters':numbers,'affected_entities':entities,'affected_fact_ids':facts}
    write(work/'plan.json',plan);tool('revision_guard.py','plan','--project',BOOK,'--input',work/'plan.json','--output',BOOK/'追踪/修改影响/active.json')
    index=[]
    pat=re.compile('|'.join(map(re.escape,entities))+r'|D4|极淡|第一式|未见|空间|原芽|接缝|保护|授权|撤案')
    for rel in read(BOOK/'追踪/修改影响/active.json')['required_checks']:
        p=BOOK/rel;lines=text(p).splitlines();index.append({'path':rel,'sha256':sha(p),'hits':[{'line':i+1,'text':s} for i,s in enumerate(lines) if pat.search(s)]})
    write(work/'dependency_index.json',index)
    (work/'写前七关与人物卡.md').write_text('# '+summary+'\n\n状态：READY_TO_PLAN，solo/direct人工分阶段执行；历史修订，不伪造新章候选门。\n\n基线修订'+str(base['state_revision'])+'；当前章99；来源正文、细纲、角色设定及追踪K/E/F，哈希见baseline_hashes和dependency_index。\n\n'+gates,encoding='utf-8')
    write(work/'冻结写前包.json',{'revision':base['state_revision'],'chapters':numbers,'status':'manual_pass','gate_hash':sha(work/'写前七关与人物卡.md'),'source_hashes':hashes})
    return work,base
def candidate(work,n,s,note):
    folder=work/f'第{n:03d}章';folder.mkdir(exist_ok=True)
    (folder/'candidate.md').write_text(s,encoding='utf-8')
    outline=text(BOOK/f'大纲/细纲_第{n:03d}章.md')
    (folder/'outline.md').write_text(outline.rstrip()+'\n\n## 2026-10-06 第五批修订映射\n\n'+note+'\n',encoding='utf-8')
def prior_delta(n):
    candidates=[]
    p=BOOK/f'追踪/事务-第{n:03d}章.json'
    if p.exists():candidates.append(p)
    for p in (BOOK/'创作运行').glob(f'*/第{n:03d}章/修订事务.json'):candidates.append(p)
    candidates.sort(key=lambda p:p.stat().st_mtime,reverse=True)
    if candidates:return copy.deepcopy(read(candidates[0])['delta'])
    return {'result':'','character_changes':[],'foreshadow_changes':[],'timeline_events':[],'fact_changes':[],
            'constraints':[],'next_chapter_commitments':[]}
def transaction(base,state,n,edit):
    d=prior_delta(n);d['retired_characters']=[];d['retired_context_items']=[];d['continuity_changes']=[]
    d['foreshadow_changes']=[{'action':'upsert',**clean(base['foreshadow'][f['id']])} for f in d['foreshadow_changes'] if f['id'] in base['foreshadow']]
    key=f'E{n:03d}';d['timeline_events']=[{'action':'upsert',**clean(base['timeline'][key])}] if key in base['timeline'] else []
    if not d.get('result') and d['timeline_events']:d['result']=d['timeline_events'][0]['objective_fact'][:100]
    edit(d,n,base)
    context={k:copy.deepcopy(state['context'][k]) for k in ['position','long_term_constraints','active_character_names','continuity_risks']}
    snapshots={c['name']:copy.deepcopy(state['characters'][c['name']]) for c in d['character_changes'] if c['name'] in state['characters']}
    if hasattr(edit,'context'):edit.context(context,snapshots,n)
    return {'schema_version':1,'mode':'revision','chapter':n,'chapter_title':text(prose(n)).splitlines()[0].split(' ',2)[-1],
            'expected_state_revision':state['state_revision'],'delta':d,'context':context,'character_snapshots':snapshots}
def finish(work,numbers,edit,apply=False):
    base=read(work/'baseline.json');spec=importlib.util.spec_from_file_location('batch_tracking',TOOLS/'tracking_commit.py')
    tc=importlib.util.module_from_spec(spec);sys.modules[spec.name]=tc;spec.loader.exec_module(tc)
    dry=copy.deepcopy(base);prefix=[copy.deepcopy(base)];checks={};diff=[];sizes={}
    for n in numbers:
        p=work/f'第{n:03d}章/candidate.md';t=transaction(base,dry,n,edit);v=tc.normalize_transaction(dry,t)
        tc.enforce_continuity_guard(dry,v);dry=tc.merge_transaction(dry,v);prefix.append(copy.deepcopy(dry))
        size=len(tc.render_delta(n,t['chapter_title'],v['delta'],set(dry['characters'])).encode('utf-8'));assert size<=3072,(n,size)
        checks[str(n)]={}
        for name,flags in [('language_gate.js',[]),('check-style-hygiene.js',['--check','--fail-on=blocking']),('check-ai-patterns.js',['--check','--fail-on=blocking']),('check-degeneration.js',['--check','--language=zh','--fail-on=blocking'])]:
            checks[str(n)][name]=run(['node',TOOLS/name,*flags,p])
        write(p.parent/'修订事务.json',t)
        old=text(BOOK/'备份'/('2026-10-06_第五批_'+work.name)/prose(n).relative_to(BOOK));new=text(p)
        diff+=list(difflib.unified_diff(old.splitlines(),new.splitlines(),fromfile=prose(n).name,tofile='修订/'+prose(n).name,n=2))
        sizes[str(n)]={'before':len(old),'after':len(new),'delta':len(new)-len(old),'tracking_bytes':size}
    write(work/'language_checks.json',checks);write(work/'sizes.json',sizes);(work/'修订差异.diff').write_text('\n'.join(diff),encoding='utf-8')
    print(json.dumps({'dry_run':'PASS','language_checks':len(numbers)*4,'sizes':sizes},ensure_ascii=False))
    if not apply:return
    review=read(work/'候选人工复核.json');assert review['status']=='manual_pass'
    for n in numbers:assert review['hashes'][str(n)]==sha(work/f'第{n:03d}章/candidate.md')
    state=read(BOOK/'追踪/_tracking-state.json');progress=state['state_revision']-base['state_revision']
    assert 0<=progress<=len(numbers) and state==prefix[progress],'外部修改或中断状态不一致'
    done=set(numbers[:progress])
    for rel,h in read(work/'baseline_hashes.json').items():
        m=re.search(r'第(\d+)章',rel)
        if m and int(m[1]) in done:
            name='candidate.md' if rel.startswith('正文/') else 'outline.md';assert sha(BOOK/rel)==sha(work/f'第{int(m[1]):03d}章'/name)
        else:assert sha(BOOK/rel)==h,rel
    backup=BOOK/'备份'/('2026-10-06_第五批_'+work.name)/'追踪'
    if not backup.exists():shutil.copytree(BOOK/'追踪',backup)
    for n in numbers[progress:]:
        folder=work/f'第{n:03d}章'
        for target,src in [(prose(n),folder/'candidate.md'),(BOOK/f'大纲/细纲_第{n:03d}章.md',folder/'outline.md')]:
            tmp=work/(target.name+'.install.tmp');tmp.write_bytes(src.read_bytes());os.replace(tmp,target)
        t=transaction(base,read(BOOK/'追踪/_tracking-state.json'),n,edit);p=folder/'修订事务.json';write(p,t)
        checks[str(n)]['commit']=tool('tracking_commit.py','commit','--project',BOOK,'--input',p)
        checks[str(n)]['check']=tool('tracking_commit.py','check','--project',BOOK);write(work/'commit_checks.json',checks)
        print(f'{n:03d} committed and checked')
    after=read(BOOK/'追踪/_tracking-state.json');assert after['last_committed_chapter']==99 and after['facts']==dry['facts']
    manifest=BOOK/'追踪/修改影响/active.json';tool('revision_guard.py','plan','--project',BOOK,'--input',work/'plan.json','--output',manifest)
    m=read(manifest);index=[]
    for rel in m['required_checks']:
        p=BOOK/rel;content=text(p);index.append({'path':rel,'sha256':sha(p),'scope':'本阶段人物知情、能力范围、关系责任、处置权限及直接回指定点核对'})
    write(work/'final_dependencies.json',index);m['checked_files']=[r['path'] for r in index]
    m['conflicts']=[{'source':prose(n).relative_to(BOOK).as_posix(),'target':f'大纲/细纲_第{n:03d}章.md','severity':'S2','issue':m['summary'],
                    'resolution':'正文按写前七关修订并同步细纲、实际事件与截至99当前追踪','status':'resolved'} for n in numbers]
    m['tracking_action']={'kind':'commit','state_revision_before':base['state_revision'],'state_revision_after':after['state_revision'],'reason':'历史修订逐章串行提交，保留当前章99和长期事实'};write(manifest,m)
    write(work/'写后复核.json',{'status':'READY_TO_CLOSE','reviewer':'Codex /root solo/direct','chapters':numbers,'hashes':{str(n):sha(prose(n)) for n in numbers},
            'scope':'本阶段完整候选冷读及直接依赖复核；其他影响产物定点核对，不冒称整卷审结'})
    result={'revision_gate':tool('revision_guard.py','check','--project',BOOK,'--input',manifest,'--stamp',BOOK/'追踪/修改影响/active.approved.json'),
            'tracking':tool('tracking_commit.py','check','--project',BOOK),'receipts':{}}
    for n in numbers:
        if (BOOK/f'追踪/章节提交/第{n:03d}章.json').exists():
            result['receipts'][str(n)]=tool('chapter_candidate.py','sync','--project',BOOK,'--chapter',n,'--revision-manifest',manifest,
             '--revision-stamp',BOOK/'追踪/修改影响/active.approved.json','--reason','用户授权依次完成D4与两段修订','--confirm','SYNC')
    result['voice']=tool('voice_profile.py','update','--project',BOOK);result['doctor']=tool('story_doctor.py','--project',BOOK)
    result['world_export']=run([sys.executable,BOOK.parent/'skills/story-world-engine/scripts/world_gate.py','export','--project',BOOK,'--start',1,'--end',99,'--tracking-tool',TOOLS/'tracking_commit.py'])
    for n in range(100,104):assert sha(prose(n))==read(work/'baseline_hashes.json')[prose(n).relative_to(BOOK).as_posix()]
    write(work/'final_checks.json',result);print(json.dumps({'revision':after['state_revision'],'doctor':result['doctor']['status'],'locked':True},ensure_ascii=False))
