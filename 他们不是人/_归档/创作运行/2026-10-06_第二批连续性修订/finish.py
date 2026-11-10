from pathlib import Path
import json, os, sys, subprocess, hashlib, shutil, copy, importlib.util, re, difflib
BOOK=Path(__file__).resolve().parents[2]; WORK=Path(__file__).resolve().parent
SCRIPTS=BOOK.parent/'skills/story-long-write/scripts'
ENV={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'}
CHAPTERS=[52,70,72,73,74,75,76,77,78,79,82,83,96]
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def prose(n):return next((BOOK/'正文').glob(f'第{n:03d}章_*.md'))
def run(args):
    r=subprocess.run(list(map(str,args)),env=ENV,capture_output=True,text=True,encoding='utf-8')
    if r.returncode:raise RuntimeError(r.stdout+r.stderr)
    try:return json.loads(r.stdout)
    except json.JSONDecodeError:return {'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
def tool(name,*args):return run([sys.executable,SCRIPTS/name,*args])
def clean(row):return {k:v for k,v in row.items() if k not in ['first_recorded_chapter','updated_chapter']}
BASE=read(WORK/'修订前追踪快照.json')
def transaction(n,state):
    if n==52:
        t={'schema_version':1,'chapter':52,'chapter_title':'一条时间线','delta':{
            'result':'双陈骁分别拒签并账。猫眼九点到、九点十六封存；十点五十七回店，十一点扣186列入工资预告，十一点零六药送到。',
            'character_changes':[{'name':'镜辞','change':'见证扣款与停单，不合并两地履历；分存两地与新字段原件'},
               {'name':'姜霁','change':'核新字段与独立来源；可见性与短信相关仅作假设'},
               {'name':'猫眼','change':'分别封存两地来源，不标真伪；封口时刻晚于到店'},
               {'name':'宁州陈骁','change':'拒勾两项不符事实的说明，厂里扣186、续房42自己承担'},
               {'name':'本地陈骁','change':'拒把宁州工单归到七周履历；配送停单少43，不许到站验人'},
               {'name':'杜经理','change':'拒点非本人写的新字段，提供原页及签字抄件'}],
            'foreshadow_changes':[],'timeline_events':[{'action':'upsert','id':'E052','story_time':'并账次日早上七点四十至十一点零六之后',
              'objective_fact':'双陈骁拒签。猫眼九点到店，九点十六封存两地材料。物业新字段待可见性复核。十点五十七回店，十一点厂里确认随月薪扣186；十一点零六改派药送到、晚六分钟。',
              'reader_knowledge':'两地来源各自成立但账户并账；镜辞只见证事件，不认证身份。晚送消息在发生后取得。',
              'reveal_status':'已揭示','reveal_chapter':52,'characters':['镜辞','姜霁','猫眼','宁州陈骁','本地陈骁','杜经理']}],
            'fact_changes':[],'constraints':['两地损失不混；时间相邻不证明上游来源；不提前获知十一点零六结果。'],
            'next_chapter_commitments':['502可见性短信未答；D4试验不能拿陈骁当标准答案。']}}
    else:
        path=BOOK/f'追踪/事务-第{n:03d}章.json'
        if n==77:path=BOOK/'创作运行/2026-10-06_P0硬伤修订/第077章/修订事务.json'
        t=read(path);d=t['delta']
        d['retired_characters']=[];d['retired_context_items']=[];d['continuity_changes']=[]
        historical='；'.join(f"{f['id']}本章{f['status']}" for f in d['foreshadow_changes'])
        d['foreshadow_changes']=[{'action':'upsert',**clean(BASE['foreshadow'][f['id']])} for f in d['foreshadow_changes']]
        if n!=77:d['constraints'].append(historical+'；伏笔栏为截至99当前值，后来回收不反记为本章兑现。')
    d=t['delta']
    if n==72:
        d['timeline_events'][0]['objective_fact']='老秦零件摊日薪六十，分错扣十未发生；标签纸由摊提供。她完成工作，午饭预支2，实领58，还夜车10后余48。账上写钟表行带来的人，明日还去。'
        d['constraints'].append('首日预支2已结，不再欠两分钱标签纸；还夜车后现金48。')
        next(r for r in d['character_changes'] if r['name']=='当前存在')['change']='接活不报芽名。工钱60结清、实领58；还垫款10后余48。明天还来'
    if n==73:d['constraints'].append('她继承现金48，其他人的12与40损失不归她。')
    if n==74:
        d['timeline_events'][0]['objective_fact']+='她从48付往返8后余40，第二日工资60另存。'
        d['constraints'].append('40为首日余额，60为第二日实领，不把毛收入当现有现金。')
    if n==75:
        d['timeline_events'][0]['objective_fact']+='第三日工资60到账后，她买手套8，余52；前两日余40与60。'
        next(r for r in d['character_changes'] if r['name']=='当前存在')['change']='第三天箱子做完、工资到账，买手套8后余52；没被拉去东口当样本'
    if n==76:
        d['result']='她写下不想认的两件事，不拿工钱换原谅。净现金152入当前开销，晚饭8后144。镜辞说记得，责任问题未答。'
        d['timeline_events'][0]['objective_fact']='她将三日未花现金40、60、52共152放入当前开销信封，晚饭8后144。背面两行是旧名用途与知道他找人仍模仿的动作。镜辞记得但未原谅。责任未答。'
    if n==77:d['timeline_events'][0]['objective_fact']+='当晚从144付饼2，余142。'
    if n==78:
        d['result']='她自主决定回北河并接受四条约定。从142付票18与回店公交2后余122。他不跟；旧物未分。'
        d['timeline_events'][0]['objective_fact']=d['timeline_events'][0]['objective_fact'].replace('信封余一百四十','142付车票18、回店公交2后信封余122')
    if n==79:
        d['timeline_events'][0]['objective_fact']=d['timeline_events'][0]['objective_fact'].replace('信封一百四十','信封122')
        d['constraints'].append('手套8在075已支付，079不重扣。现金122只限离店时，不预断途中消费。')
        d['fact_changes']=[{'action':'upsert','id':'K010','category':'历史因果','subject':'当前存在','predicate':'三日工钱及离店前已写支出',
          'object':'工资180；午饭2、还垫款10、往返8、手套8后余152；076晚饭后144，077饼后142，078买票及回店后122，079带走122',
          'cardinality':'one','canon_status':'正文已证','reader_status':'已揭示','established_chapter':79,'reveal_chapter':79,
          'evidence':[prose(k).relative_to(BOOK).as_posix()+'｜本人实领及实际支付' for k in [72,74,75,76,77,78,79]],
          'related_entities':['当前存在','老秦','镜辞','手套'],
          'negative_constraints':['不能把180毛工资或170漏扣余额当现金；手套不得重复扣款','122只约束079离店时，镜辞不知道她离开后实际余额','早先票证和原芽旧账不从三天工钱逆造支付来源']}]
    if n in [82,83]:d['constraints'].append('只知她已自带信封离开，不隔空断言途中精确现金余额。')
    if n==96:d['constraints'].append('电话内收观察答复并记录，之后才挂断；不按字数定义观察。')
    t['mode']='revision';t['expected_state_revision']=state['state_revision']
    t['context']={k:copy.deepcopy(state['context'][k]) for k in ['position','long_term_constraints','active_character_names','continuity_risks']}
    t['character_snapshots']={c['name']:copy.deepcopy(state['characters'][c['name']]) for c in d['character_changes'] if c['name'] in state['characters']}
    return t

module=importlib.util.spec_from_file_location('tracking_second',SCRIPTS/'tracking_commit.py')
tc=importlib.util.module_from_spec(module);sys.modules[module.name]=tc;module.loader.exec_module(tc)
dry=copy.deepcopy(BASE);checks={};diffs=[];sizes={}
for n in CHAPTERS:
    t=transaction(n,dry);normal=tc.normalize_transaction(dry,t);tc.enforce_continuity_guard(dry,normal)
    dry=tc.merge_transaction(dry,normal)
    payload=tc.render_delta(n,t['chapter_title'],normal['delta'],set(dry['characters']))
    assert len(payload.encode('utf-8'))<=3072,(n,len(payload.encode('utf-8')))
    folder=WORK/f'第{n:03d}章';candidate=folder/'candidate.md'
    old=prose(n).read_text(encoding='utf-8-sig');new=candidate.read_text(encoding='utf-8')
    diffs+=list(difflib.unified_diff(old.splitlines(),new.splitlines(),fromfile=prose(n).name,tofile='修订/'+prose(n).name,n=1))
    sizes[str(n)]={'before':len(old),'after':len(new),'delta':len(new)-len(old)}
    checks[str(n)]={}
    for script,flags in [('language_gate.js',[]),('check-style-hygiene.js',['--check','--fail-on=blocking']),('check-ai-patterns.js',['--check','--fail-on=blocking']),('check-degeneration.js',['--check','--language=zh','--fail-on=blocking'])]:
        checks[str(n)][script]=run(['node',SCRIPTS/script,*flags,candidate])
    write(folder/'修订事务.json',t)
write(WORK/'语言检查.json',checks);write(WORK/'字数变化.json',sizes)
(WORK/'最终候选差异.diff').write_text('\n'.join(diffs),encoding='utf-8')
print('13 tracking dry runs and 52 language gates PASS')
if '--apply' not in sys.argv:sys.exit(0)
assert read(BOOK/'追踪/_tracking-state.json')==BASE
for rel,h in read(WORK/'基线哈希.json').items():assert sha(BOOK/rel)==h,rel
audit=WORK/'事实与七关.md'
write(WORK/'写前冻结.json',{'kind':'historical-local-revision-manual-review','tracking_revision':50,
    'audit_path':audit.relative_to(BOOK).as_posix(),'audit_sha256':sha(audit),
    'scope':CHAPTERS,'reviewer':'Codex /root solo/direct','status':'manual_pass',
    'scope_limit':'本轮受影响选择，非旧章原写作通行证；不冒称已通过world_gate机器门',
    'source_hashes':read(WORK/'基线哈希.json')})
backup=BOOK/'备份/2026-10-06_第二批连续性修订/追踪'
assert not backup.exists();shutil.copytree(BOOK/'追踪',backup)
for n in CHAPTERS:
    folder=WORK/f'第{n:03d}章'
    prose(n).write_bytes((folder/'candidate.md').read_bytes())
    (BOOK/f'大纲/细纲_第{n:03d}章.md').write_bytes((folder/'outline.md').read_bytes())
    t=transaction(n,read(BOOK/'追踪/_tracking-state.json'));path=folder/'修订事务.json';write(path,t)
    checks[str(n)]['commit']=tool('tracking_commit.py','commit','--project',BOOK,'--input',path)
    checks[str(n)]['check']=tool('tracking_commit.py','check','--project',BOOK)
    write(WORK/'落盘检查.json',checks);print(f'{n:03d}: revised and tracking checked')
after=read(BOOK/'追踪/_tracking-state.json')
for k in ['context','characters','foreshadow']:assert BASE[k]==after[k],k
assert after['last_committed_chapter']==99
plan=read(WORK/'修订计划.json');plan['summary']+='；同步082/083不知离开后现金的回指'
write(WORK/'修订计划.json',plan)
manifest=BOOK/'追踪/修改影响/active.json'
tool('revision_guard.py','plan','--project',BOOK,'--input',WORK/'修订计划.json','--output',manifest)
m=read(manifest);indexed=[]
pattern=re.compile('五十|四十二|一百[二四五六七八]|手套|预支|两分|九点|十点|十一点|我知道|基础接缝|信封|三天')
for rel in m['required_checks']:
    p=BOOK/rel;lines=p.read_text(encoding='utf-8-sig').splitlines()
    indexed.append({'path':rel,'sha256':sha(p),'line_count':len(lines),
       'hits':[{'line':i+1,'text':x} for i,x in enumerate(lines) if pattern.search(x)],
       'scope':'本批时间、工资支出、回指及所改动作；定点字段核对，不冒称全卷文学冷读'})
write(WORK/'依赖核对索引.json',indexed);m['checked_files']=[i['path'] for i in indexed]
m['conflicts']=[{'source':prose(n).relative_to(BOOK).as_posix(),'target':f'大纲/细纲_第{n:03d}章.md',
       'severity':'S2' if n in [52,72,74,75,76,77,78,79] else 'S3','issue':'正文时间、现金或文字回指口径冲突',
       'resolution':'按写前事实与七关底表校正，细纲及追踪事务同步','status':'resolved'} for n in CHAPTERS]
m['tracking_action']={'kind':'commit','state_revision_before':50,'state_revision_after':after['state_revision'],
       'reason':'13份历史修订事务；保留99当前位置及全部核心当前快照、伏笔状态，校正历史现金与时间'}
write(manifest,m)
locked={rel:sha(BOOK/rel)==h for rel,h in read(WORK/'基线哈希.json').items() if re.search('正文/第10[0-3]章',rel)}
assert len(locked)==4 and all(locked.values())
write(WORK/'写后人工复核.json',{'status':'READY_TO_CLOSE','reviewer':'Codex /root solo/direct',
    'method':'原文与候选差异逐段回读；实际收入支出逐笔核对；直接后章余额回指及前批沈竹普通委托保真',
    'scope':CHAPTERS,'source_bound_prose':{str(n):sha(prose(n)) for n in CHAPTERS},
    'locked_hashes':locked,'current_context_unchanged':True,'seven_gates':'manual_pass',
    'limits':'不等于全卷结构问题已修；世界门机械集成只用于新长篇候选，本批为手动审查的历史局部修订'})
result={'revision_gate':tool('revision_guard.py','check','--project',BOOK,'--input',manifest,'--stamp',BOOK/'追踪/修改影响/active.approved.json'),
        'tracking':tool('tracking_commit.py','check','--project',BOOK),'receipts':{}}
for n in CHAPTERS:
    if (BOOK/f'追踪/章节提交/第{n:03d}章.json').exists():
        result['receipts'][str(n)]=tool('chapter_candidate.py','sync','--project',BOOK,'--chapter',n,
          '--revision-manifest',manifest,'--revision-stamp',BOOK/'追踪/修改影响/active.approved.json',
          '--reason','用户授权继续修综合方案下一批；时间与实际现金连续性修订','--confirm','SYNC')
result['voice']=tool('voice_profile.py','update','--project',BOOK)
result['doctor']=tool('story_doctor.py','--project',BOOK)
world=BOOK.parent/'skills/story-world-engine/scripts/world_gate.py'
result['world_export']=run([sys.executable,world,'export','--project',BOOK,'--start',1,'--end',99,'--tracking-tool',SCRIPTS/'tracking_commit.py'])
write(WORK/'最终验收.json',result)
print(json.dumps({'revision':after['state_revision'],'doctor':result['doctor']['status'],'impact_files':len(indexed),'receipts_synced':len(result['receipts'])},ensure_ascii=False))
