from pathlib import Path
import json,os,sys,subprocess,hashlib,shutil,copy,importlib.util,re,difflib
BOOK=Path(__file__).resolve().parents[2];WORK=Path(__file__).resolve().parent
SCRIPTS=BOOK.parent/'skills/story-long-write/scripts';CHAPTERS=[55,61,62,65,75]
ENV={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'}
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def prose(n):return next((BOOK/'正文').glob(f'第{n:03d}章_*.md'))
def run(args):
    r=subprocess.run(list(map(str,args)),env=ENV,capture_output=True,text=True,encoding='utf-8')
    if r.returncode:raise RuntimeError(r.stdout+r.stderr)
    try:return json.loads(r.stdout)
    except json.JSONDecodeError:return {'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
def tool(n,*args):return run([sys.executable,SCRIPTS/n,*args])
def clean(x):return {k:copy.deepcopy(v) for k,v in x.items() if k not in ['first_recorded_chapter','updated_chapter']}
BASE=read(WORK/'修订前追踪快照.json')
HOOK={'action':'upsert','id':'F050','summary':'075客户原维修票经窗口核验退号费6，客户留原票、窗口留副本；只兑现保票与办理，不证身份或幕后',
      'planted_chapter':61,'planned_resolution_chapter':75,'status':'已回收','importance':'中'}
def tx(n,state):
    if n==55:
        d={'result':'南栏不被接纳；公开合影对脸。打印店完成旧单后拒定时拉页，今后只打印传来文件。',
           'character_changes':[{'name':'镜辞','change':'承认南栏未处理对照，接受打印店停止定时盯页；对陈屿脸不并两家公司'},
             {'name':'姜霁','change':'按短信与公开页分存，外貌可核对但不认证'},
             {'name':'打印店老板','change':'完成当天交付后停止定时拉页，自己跟进纸车，仍接受有偿文件打印'},
             {'name':'猫眼','change':'只交公开图层与合影出处，恒泰未被写成制造方'}],
           'foreshadow_changes':[],'timeline_events':[{'action':'upsert',**clean(BASE['timeline']['E055'])}],
           'fact_changes':[],'constraints':['打印店只停定时盯页，不是拒绝065付费印文件；南栏不受短信遥控。'],
           'next_chapter_commitments':['保留照片原件，先看公开页面后决定是否回现场，不把两家公司合并。']}
        t={'schema_version':1,'chapter':55,'chapter_title':'没处理过','delta':d}
        d['timeline_events'][0]['objective_fact']+='打印店因错过进纸车，完成旧单后停止定时拉页，仍打印传来的文件。'
        d['timeline_events'][0]['characters'].append('打印店老板')
    else:
        p=BOOK/f'追踪/事务-第{n:03d}章.json'
        if n==65:p=BOOK/'创作运行/2026-10-06_P0硬伤修订/第065章/修订事务.json'
        if n==75:p=BOOK/'创作运行/2026-10-06_第二批连续性修订/第075章/修订事务.json'
        t=read(p);d=t['delta'];d['retired_characters']=[];d['retired_context_items']=[];d['continuity_changes']=[]
        d['foreshadow_changes']=[{'action':'upsert',**clean(BASE['foreshadow'][f['id']])} for f in d['foreshadow_changes']]
    if n==61:
        d['result']='孙立取修好的表及签名原维修票，店留底联；陈屿随后问话，信息来源未知。公开证件核对仅对上服务采购。'
        for c in d['character_changes']:
            if c['name']=='陈屿':c['change']='工号发来没看出来；没有证据说明他从何处取得孙立到店或观察的信息'
        d['character_changes'].append({'name':'孙立','change':'付共45取回父亲的表，收签名维修原票以备售后，自己赶班车'})
        d['timeline_events'][0]['objective_fact']='孙立油干慢表修好，补25、共45；签名原票孙立留、底联店留。脸侧再闪仍未判。14:18陈屿问没看出来，消息来源未核。公开页显示孙立三天前在东口服务部核证件，该部见于恒泰下游采购，恒准页分存。'
        d['timeline_events'][0]['reader_knowledge']='修表与付款真实；陈屿随后问话只使镜辞怀疑消息泄露，取得路径未知。证件核对不证明谁派孙立来。'
        for f in d['foreshadow_changes']:
            if f['id']=='F010':f['summary']='孙立取回修好的表，陈屿随后发来没看出来；信息路径未核，镜辞不作身份通过结论'
        d['foreshadow_changes'].append(copy.deepcopy(HOOK))
        d['constraints'].append('F050本章埋：客户原票独立保管；截至99当前值为75局部兑现，不反写为61已退费。')
    if n==62:
        d['timeline_events'][0]['objective_fact']='孙立带推荐名单争号费6；镜辞只盖维修票。两版公开页显示本店11:20被新增。推荐异议工本2、明日9点撤下。蓝拖鞋依名单到店，店付公交2、未看脸。17:12陈屿发北河老树与17金属空景，镜辞对旧图、不打电话。'
        d['constraints'].append('普通推荐路径有证据不等于排除其他原因；盖维修单不盖推荐名单，更不认证孙立身份。')
    if n==65:
        d['result']='三行当場拒填，链仍走。孙立本人自留原票，店留底联，只证修表。薄笔记无新名，后日工单保留。'
        d['timeline_events'][0]['objective_fact']='陈屿栏外问502、北河、孙立哪个通过，镜辞不填；马甲工空签到、口扣15，复核仍走。孙立回信自留维修原票，只交副本、不加签，退费自己争。薄本无新名，住宅工单改期后日18点，镜辞留店。'
        d['timeline_events'][0]['characters'].append('孙立')
        d['character_changes'].append({'name':'孙立','change':'保留原维修票，不交原件换联，也不请镜辞替自己跑退费'})
        d['constraints'].append('独立票据只支持表维修；F050此时仍等实际受理，75兑现，不证明主体。')
    if n==75:
        d['result']='东口柜仍撤、侯强亏46。孙立退费6，原票自留、窗口收副本；镜辞仅维修签字获得一次可查局部结果。'
        d['timeline_events'][0]['objective_fact']='东口7:40断电、8:05撤柜，恒泰工单；镜辞未过街，侯强亏46。她第三日工钱60买手套8后余52，前两日余40和60。孙立回述窗口核维修项目与店章退号费6、留副本；原票自留、未加签其他资料。'
        d['timeline_events'][0]['characters'].append('孙立')
        d['character_changes'].append({'name':'孙立','change':'依真实维修票拿回号费6，保留原件，不加签无关资料，未被转为调查者'})
        d['foreshadow_changes'].append(copy.deepcopy(HOOK))
        d['constraints'].append('F050保票与受理局部兑现；不证明身份或幕后、不停止维护链、六元不抵侯强46损失。')
        d['fact_changes'].append({'action':'upsert','id':'K011','category':'所有权','subject':'孙立维修票','predicate':'持有与签字证明范围',
          'object':'孙立自留原票，钟表行留底联，退费窗口留副本；店章及镜辞签名只证油干处理、走时正常、工钱45，不作身份或其他项目通过',
          'cardinality':'one','canon_status':'正文已证','reader_status':'已揭示','established_chapter':61,'reveal_chapter':75,
          'evidence':[prose(k).relative_to(BOOK).as_posix()+'｜限定维修票、本人留原件及退费' for k in [61,62,65,75]],
          'related_entities':['孙立','镜辞','姜霁'],
          'negative_constraints':['六元退费只证明该次按票受理，不能证明窗口全局承认边界或孙立是真人','原票可作独立反驳来源，不写成不会被篡改的魔法物件','不得把孙立写成镜辞安排的调查员或已知幕后执行者']})
    t['mode']='revision';t['expected_state_revision']=state['state_revision']
    t['context']={k:copy.deepcopy(state['context'][k]) for k in ['position','long_term_constraints','active_character_names','continuity_risks']}
    t['character_snapshots']={c['name']:copy.deepcopy(state['characters'][c['name']]) for c in d['character_changes'] if c['name'] in state['characters']}
    return t
spec=importlib.util.spec_from_file_location('third_tracking',SCRIPTS/'tracking_commit.py')
tc=importlib.util.module_from_spec(spec);sys.modules[spec.name]=tc;spec.loader.exec_module(tc)
dry=copy.deepcopy(BASE);checks={};diffs=[];prefix=[copy.deepcopy(BASE)]
for n in CHAPTERS:
    t=tx(n,dry);v=tc.normalize_transaction(dry,t);tc.enforce_continuity_guard(dry,v);dry=tc.merge_transaction(dry,v)
    prefix.append(copy.deepcopy(dry))
    size=len(tc.render_delta(n,t['chapter_title'],v['delta'],set(dry['characters'])).encode('utf-8'));assert size<=3072,(n,size)
    p=WORK/f'第{n:03d}章/candidate.md';checks[str(n)]={}
    for script,flags in [('language_gate.js',[]),('check-style-hygiene.js',['--check','--fail-on=blocking']),('check-ai-patterns.js',['--check','--fail-on=blocking']),('check-degeneration.js',['--check','--language=zh','--fail-on=blocking'])]:
        checks[str(n)][script]=run(['node',SCRIPTS/script,*flags,p])
    write(p.parent/'修订事务.json',t)
    diffs+=list(difflib.unified_diff(prose(n).read_text(encoding='utf-8-sig').splitlines(),p.read_text(encoding='utf-8').splitlines(),fromfile=prose(n).name,tofile='修订/'+prose(n).name,n=1))
write(WORK/'语言检查.json',checks);(WORK/'最终差异.diff').write_text('\n'.join(diffs),encoding='utf-8')
print('Five dry runs and 20 language gates PASS')
if '--apply' not in sys.argv:sys.exit(0)
current=read(BOOK/'追踪/_tracking-state.json');progress=current['state_revision']-BASE['state_revision']
assert 0<=progress<=len(CHAPTERS) and current==prefix[progress],'不能基于外部变动重用旧事务'
done=set(CHAPTERS[:progress])
for p,h in read(WORK/'基线哈希.json').items():
    found=re.search(r'第(\d+)章',p)
    if found and int(found.group(1)) in done:
        n=int(found.group(1));artifact='candidate.md' if p.startswith('正文/') else 'outline.md'
        assert sha(BOOK/p)==sha(WORK/f'第{n:03d}章'/artifact),p
    else:assert sha(BOOK/p)==h,p
backup=BOOK/'备份/2026-10-06_第三批反调查闭环/追踪'
if not backup.exists():shutil.copytree(BOOK/'追踪',backup)
def install(target,source):
    temp=WORK/(target.name+'.install.tmp');temp.write_bytes(source.read_bytes());os.replace(temp,target)
for n in CHAPTERS[progress:]:
    folder=WORK/f'第{n:03d}章';install(prose(n),folder/'candidate.md')
    install(BOOK/f'大纲/细纲_第{n:03d}章.md',folder/'outline.md')
    p=folder/'修订事务.json';write(p,tx(n,read(BOOK/'追踪/_tracking-state.json')))
    checks[str(n)]['commit']=tool('tracking_commit.py','commit','--project',BOOK,'--input',p)
    checks[str(n)]['check']=tool('tracking_commit.py','check','--project',BOOK);write(WORK/'落盘检查.json',checks)
    print(f'{n:03d}: revised and checked')
after=read(BOOK/'追踪/_tracking-state.json')
for k in ['context','characters']:assert after[k]==BASE[k],k
assert after['last_committed_chapter']==99
manifest=BOOK/'追踪/修改影响/active.json'
tool('revision_guard.py','plan','--project',BOOK,'--input',WORK/'修订计划.json','--output',manifest)
m=read(manifest);index=[];pat=re.compile('孙立|维修单|维修票|原件|小票|号费|打印店|陈屿知道|被读到')
for rel in m['required_checks']:
    p=BOOK/rel;rows=p.read_text(encoding='utf-8-sig').splitlines();index.append({'path':rel,'sha256':sha(p),
       'scope':'本批票据、孙立与观察泄露认知字段及直接回指，非全卷文学冷读',
       'hits':[{'line':i+1,'text':x} for i,x in enumerate(rows) if pat.search(x)]})
write(WORK/'最终依赖索引.json',index);m['checked_files']=[x['path'] for x in index]
m['conflicts']=[{'source':prose(n).relative_to(BOOK).as_posix(),'target':f'大纲/细纲_第{n:03d}章.md','severity':'S2',
    'issue':'反调查只有拒绝陈述、票据范围及观察信息取得路径过度断言','resolution':'实际维修原票、持有人拒交原件和退费反馈闭环，关联细纲与追踪同步','status':'resolved'} for n in CHAPTERS]
m['tracking_action']={'kind':'commit','state_revision_before':63,'state_revision_after':after['state_revision'],
    'reason':'五份历史修订事务、新增K011与TRACK:F050局部兑现；保留99当前人物位置和此前现金修复'};write(manifest,m)
write(WORK/'写后人工复核.json',{'status':'READY_TO_CLOSE','reviewer':'Codex /root solo/direct',
    'basis':'候选逐段diff与直接回指复核，普通客户争退款、打印店停止盯页、窗口按原有规则核票；既有撤柜不取消',
    'seven_gates':'manual_pass','scope':CHAPTERS,'prose_hashes':{str(n):sha(prose(n)) for n in CHAPTERS},
    'limit':'历史局部人工审查，不冒称通过新章world_gate机器接纳门；不是整卷反调查已完成'})
result={'revision_gate':tool('revision_guard.py','check','--project',BOOK,'--input',manifest,'--stamp',BOOK/'追踪/修改影响/active.approved.json'),
        'tracking':tool('tracking_commit.py','check','--project',BOOK),'receipts':{}}
for n in CHAPTERS:
    if (BOOK/f'追踪/章节提交/第{n:03d}章.json').exists():
        result['receipts'][str(n)]=tool('chapter_candidate.py','sync','--project',BOOK,'--chapter',n,'--revision-manifest',manifest,
        '--revision-stamp',BOOK/'追踪/修改影响/active.approved.json','--reason','用户授权第三批反调查局部闭环修订','--confirm','SYNC')
result['voice']=tool('voice_profile.py','update','--project',BOOK);result['doctor']=tool('story_doctor.py','--project',BOOK)
result['world_export']=run([sys.executable,BOOK.parent/'skills/story-world-engine/scripts/world_gate.py','export','--project',BOOK,'--start',1,'--end',99,'--tracking-tool',SCRIPTS/'tracking_commit.py'])
write(WORK/'最终验收.json',result)
print(json.dumps({'revision':after['state_revision'],'doctor':result['doctor']['status'],'receipts':len(result['receipts']),'dependencies':len(index)},ensure_ascii=False))
