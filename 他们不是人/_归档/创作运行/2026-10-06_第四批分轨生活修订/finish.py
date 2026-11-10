from pathlib import Path
import json,os,sys,subprocess,hashlib,shutil,copy,importlib.util,re,difflib
BOOK=Path(__file__).resolve().parents[2];WORK=Path(__file__).resolve().parent
SCRIPTS=BOOK.parent/'skills/story-long-write/scripts';CHAPTERS=[68,69,72,74,77]
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
def tx(n,state):
    source=BOOK/f'追踪/事务-第{n:03d}章.json'
    if n in [72,74,77]:source=BOOK/f'创作运行/2026-10-06_第二批连续性修订/第{n:03d}章/修订事务.json'
    t=read(source);d=t['delta']
    d['retired_characters']=[];d['retired_context_items']=[];d['continuity_changes']=[]
    d['foreshadow_changes']=[{'action':'upsert',**clean(BASE['foreshadow'][f['id']])} for f in d['foreshadow_changes']]
    d['timeline_events']=[{'action':'upsert',**clean(BASE['timeline']['E'+f'{n:03d}'])}]
    event=d['timeline_events'][0]
    if n==68:
        d['result']='老板娘认出修锁者、书面仍芽。她自留现用号码供先联系，不承诺到场或免费；唐宁电话未拨。'
        d['character_changes']=[{'name':'镜辞','change':'只记亲手修锁，不接管客栈售后联系与唐宁号码'},
             {'name':'姜霁','change':'核收据而不拍新留号码；私人联系不全部归档'},
             {'name':'当前存在','change':'回应修锁售后请求，只留先联系机会，不保证免费到场'},
             {'name':'北河客栈老板娘','change':'为免锁坏耽误营业索电话，接受需先联系，等不了可找街上锁匠'}]
        event['objective_fact']='老板娘先认出修锁者，门锁好用、房费40少收20、书面仍芽。她自愿给客栈现用号码，只答应先联系，未承诺到场免费；姜霁不拍号。唐宁便条原件仍在客栈，她抄号未拨。路费44，复核十八点仍未到场。'
        event['reader_knowledge']='修锁产生具体售后请求，她可有限答应；旧证件与书面芽仍在，不证明已脱离身份脚手架。唐宁尚未见。'
        event['characters']=list(dict.fromkeys(event['characters']+['北河客栈老板娘']))
        d['constraints'].append('客栈售后只先电话，没有保证到場、免费或时限；联系人她本人，调查方未留号，不能替她承诺。')
        d['next_chapter_commitments'][-1]+='客栈只先联系，无赴约日期，届时重评。'
    elif n==69:
        d['result']='她自行约唐宁，说明旧事记得但未亲历。唐宁拒代擦袖口和再约、代劝；照片仍存，镜辞仅听回店转述。'
        d['character_changes']=[{'name':'当前存在','change':'承认失联应早打电话，未以讲清身份自动免责；承受唐宁拒接触与暂不再约'},
             {'name':'唐宁','change':'追问失联，拒当前亲近、暂不再约及镜辞代劝；仍保有之后主动发消息和限定说旧事的选择'},
             {'name':'镜辞','change':'只远见抽手，回店才听她转述边界，不获场外全部对白'},
             {'name':'姜霁','change':'记录本人拨约及本人转述，不追问奶茶店全段谈话'}]
        event['objective_fact']='08:10自行拨约，08:40换电池12、09:20表带15；午后奶茶店见唐宁。她未领旧友位置，唐宁拒代擦袖口及再约、代劝。镜辞只远见抽手，回店听本人转述。旧照未删、移出置顶；18点到家消息未回复，先喝汤留次晨。'
        event['reader_knowledge']='拒承旧位置会失去当下亲近，讲清不自动免责。暂停接触不等于永远绝交；镜辞并未听到场外对白。'
        event['characters']=list(dict.fromkeys(event['characters']+['唐宁']))
        d['constraints'].append('070凌晨唐宁可主动补旧习惯，077可限定说亲历；当前私交没有和解，不把暂不再约写成永久绝交。')
        for f in d['foreshadow_changes']:
            if f['id']=='F018':f['summary']='唐宁已追问失联；她未继承旧友位置，唐宁拒当前亲近和再约，后可限定说旧事，关系仍未和解'
    elif n==72:
        d['result']='她为工钱接分类活，喜欢理顺但会求齐整拖慢；限定额外表把20分钟，不带回加班。实领58，还10余48。'
        d['character_changes']=[{'name':'当前存在','change':'喜欢分件、讨厌弄乱与催快；限定新来表把范围，明日继续三天内工作'},
             {'name':'老秦','change':'原价索额外表把，接受当日20分钟无追加；按约付工资并说明明日八点半'},
             {'name':'镜辞','change':'借工具收回垫款，不授予手艺来源或人格结论'},
             {'name':'姜霁','change':'只记既有工钱，不把调查材料送给零件摊'},
             {'name':'守钟人','change':'要她先洗手，保护修表台面'}]
        event['objective_fact']='三天分类每日60、错箱扣10。她确认当天付款接活，爱齐整也被催快。新增报废表把只分当日20分钟、不带回加班，老秦同意无追加。当日扣午饭2实领58，还夜车10余48，未扣错箱。明日8:30来，迟到扣5；临时账名不变。'
        event['reader_knowledge']='工作能带来喜好、高兴和议价，不必每件当身份验证。熟练来源未判；工资与三天约定均未增加。'
        event['characters']=list(dict.fromkeys(event['characters']+['老秦','隔壁借镊子的摊主']))
        d['constraints'].append('额外表把范围协商没有新增收入支出；075三天到期停工仍成立，不自动续成长期雇佣。')
    elif n==74:
        d['result']='方远讲旧事、边修边带学徒。她不领旧功仍问眼前工序；学徒留岗由当场看见，回店问题未答，40与60另存。'
        d['character_changes']=[{'name':'镜辞','change':'记原芽、多人接住、方远带徒三截；学徒留岗亲见，无来源短信删除'},
             {'name':'姜霁','change':'旧事抬头归原芽，旁听不授予人格资格'},
             {'name':'当前存在','change':'不领旧功仍问调轮工序；接受方远尚未懂身份，末问保留'},
             {'name':'方远','change':'讲亲历不为调查停工，有限解释调轮，继续带学徒，不理解异常'},
             {'name':'方远学徒','change':'决定再试，修后接另一辆车，下午仍留岗'},
             {'name':'老秦','change':'短信通知原约工钱结算、仍约次晨八点半'}]
        event['objective_fact']='原芽交申请后老师、同学和母亲接住方远，影响其带徒先问想走还是撑不住。她不领功仍问现场调轮工序，方远边做边答未懂身份。学徒现场继续干，未事后发短信。往返8后首日余40、次日工资60另存。回店问醒后事是否进别人生活，未答。'
        event['reader_knowledge']='旧关系影响不因记忆转移；不领功不意味着不能旁听和学手艺。学徒留岗为亲见，未新增超常能力。末问尚未回答。'
        event['characters']=list(dict.fromkeys(event['characters']+['方远','方远学徒','老秦']))
        d['constraints'].append('亲见学徒留岗不需新增联系方式；只是问工序，不能写成已会修车。075回指末问保持。')
    else:
        event['objective_fact']+='唐宁回指上次见面非昨日；她仅074到场后才听学徒想走，回述当时没说想多听一会儿。'
        event['reader_knowledge']+='她出发前未知学徒状况，怕镜辞揽事是本人判断，不证明他现场实际接管修车。'
        d['constraints'].append('069至077隔多日；不把074到场亲听的事提前到出发前，不把担忧当已发生接管。')
    t['mode']='revision';t['expected_state_revision']=state['state_revision']
    t['context']={k:copy.deepcopy(state['context'][k]) for k in ['position','long_term_constraints','active_character_names','continuity_risks']}
    t['character_snapshots']={c['name']:copy.deepcopy(state['characters'][c['name']]) for c in d['character_changes'] if c['name'] in state['characters']}
    return t
spec=importlib.util.spec_from_file_location('fourth_tracking',SCRIPTS/'tracking_commit.py')
tc=importlib.util.module_from_spec(spec);sys.modules[spec.name]=tc;spec.loader.exec_module(tc)
dry=copy.deepcopy(BASE);checks={};diffs=[];sizes={};prefix=[copy.deepcopy(BASE)]
for n in CHAPTERS:
    t=tx(n,dry);v=tc.normalize_transaction(dry,t);tc.enforce_continuity_guard(dry,v);dry=tc.merge_transaction(dry,v)
    prefix.append(copy.deepcopy(dry));size=len(tc.render_delta(n,t['chapter_title'],v['delta'],set(dry['characters'])).encode('utf-8'));assert size<=3072,(n,size)
    p=WORK/f'第{n:03d}章/candidate.md';checks[str(n)]={}
    for script,flags in [('language_gate.js',[]),('check-style-hygiene.js',['--check','--fail-on=blocking']),('check-ai-patterns.js',['--check','--fail-on=blocking']),('check-degeneration.js',['--check','--language=zh','--fail-on=blocking'])]:
        checks[str(n)][script]=run(['node',SCRIPTS/script,*flags,p])
    write(p.parent/'修订事务.json',t)
    backup=BOOK/'备份/2026-10-06_第四批分轨生活修订'/prose(n).relative_to(BOOK)
    old=backup.read_text(encoding='utf-8-sig');new=p.read_text(encoding='utf-8')
    diffs+=list(difflib.unified_diff(old.splitlines(),new.splitlines(),fromfile=prose(n).name,tofile='修订/'+prose(n).name,n=2))
    sizes[str(n)]={'before':len(old),'after':len(new),'change':len(new)-len(old),'tracking_bytes':size}
write(WORK/'语言检查.json',checks);write(WORK/'字数变化.json',sizes)
(WORK/'最终差异.diff').write_text('\n'.join(diffs),encoding='utf-8')
print(json.dumps({'dry_runs':'PASS','language_checks':20,'sizes':sizes},ensure_ascii=False))
if '--apply' not in sys.argv:sys.exit(0)
assert (WORK/'候选人工复核.json').exists(),'须先冷读候选与直接依赖'
review=read(WORK/'候选人工复核.json')
assert review['status']=='manual_pass'
for n in CHAPTERS:assert review['hashes'][str(n)]==sha(WORK/f'第{n:03d}章/candidate.md')
current=read(BOOK/'追踪/_tracking-state.json');progress=current['state_revision']-BASE['state_revision']
assert 0<=progress<=len(CHAPTERS) and current==prefix[progress],'不能套用外部变化后的旧事务'
done=set(CHAPTERS[:progress])
for rel,h in read(WORK/'基线哈希.json').items():
    found=re.search(r'第(\d+)章',rel)
    if found and int(found.group(1)) in done:
        n=int(found.group(1));a='candidate.md' if rel.startswith('正文/') else 'outline.md'
        assert sha(BOOK/rel)==sha(WORK/f'第{n:03d}章'/a),rel
    else:assert sha(BOOK/rel)==h,rel
backup=BOOK/'备份/2026-10-06_第四批分轨生活修订/追踪'
if not backup.exists():shutil.copytree(BOOK/'追踪',backup)
def install(target,source):
    temp=WORK/(target.name+'.install.tmp');temp.write_bytes(source.read_bytes());os.replace(temp,target)
for n in CHAPTERS[progress:]:
    folder=WORK/f'第{n:03d}章';install(prose(n),folder/'candidate.md');install(BOOK/f'大纲/细纲_第{n:03d}章.md',folder/'outline.md')
    p=folder/'修订事务.json';write(p,tx(n,read(BOOK/'追踪/_tracking-state.json')))
    checks[str(n)]['commit']=tool('tracking_commit.py','commit','--project',BOOK,'--input',p)
    checks[str(n)]['check']=tool('tracking_commit.py','check','--project',BOOK);write(WORK/'落盘检查.json',checks)
    print(f'{n:03d}: revised and checked')
after=read(BOOK/'追踪/_tracking-state.json')
assert after['context']==BASE['context'] and after['characters']==BASE['characters'] and after['last_committed_chapter']==99
assert after['facts']==BASE['facts'],'现金及长期事实不得静默改变'
manifest=BOOK/'追踪/修改影响/active.json'
tool('revision_guard.py','plan','--project',BOOK,'--input',WORK/'修订计划.json','--output',manifest)
m=read(manifest);index=[];pattern=re.compile('唐宁|方远|老秦|老板娘|修锁|四十八|四十|六十|学徒|新主体|锚点|陌生')
for rel in m['required_checks']:
    p=BOOK/rel;rows=p.read_text(encoding='utf-8-sig').splitlines()
    index.append({'path':rel,'sha256':sha(p),'scope':'人物关系、维修联系、工作与现金、学徒信息来源定点审查，非全卷文学冷读',
                  'hits':[{'line':i+1,'text':s} for i,s in enumerate(rows) if pattern.search(s)]})
write(WORK/'最终依赖索引.json',index);m['checked_files']=[x['path'] for x in index]
m['conflicts']=[{'source':prose(n).relative_to(BOOK).as_posix(),'target':f'大纲/细纲_第{n:03d}章.md','severity':'S2',
    'issue':{68:'修锁只作为证明，普通人后续生活需求缺失',69:'拒绝亲近只有解释，时间倒置与观察者知情范围不清',72:'普通工作反复被身份解释遮住',74:'领功解释多轮，学徒短信无联系来源',77:'隔多日错称昨日且出发前授予场外未得信息'}[n],
    'resolution':'以有限往来、拒接触、工作议价及当场行为修改，并同步细纲与历史事务','status':'resolved'} for n in CHAPTERS]
m['tracking_action']={'kind':'commit','state_revision_before':68,'state_revision_after':after['state_revision'],'reason':'五章历史修订串行提交，保存99当前状态及K010现金全链'}
write(manifest,m)
write(WORK/'写后人工复核.json',{'status':'READY_TO_CLOSE','reviewer':'Codex /root solo/direct','chapters':CHAPTERS,
    'seven_gates':'manual_pass','source_review':'四章全读、与原文逐段diff、相邻章及070/075—079直接回指冷读；其余关联产物定点索引',
    'limits':'同一主写者分阶段复核，不冒称独立代理盲审或新章world_gate候选门；不是066—079整段审结',
    'prose_hashes':{str(n):sha(prose(n)) for n in CHAPTERS}})
result={'revision_gate':tool('revision_guard.py','check','--project',BOOK,'--input',manifest,'--stamp',BOOK/'追踪/修改影响/active.approved.json'),
        'tracking':tool('tracking_commit.py','check','--project',BOOK),'receipts':{}}
for n in CHAPTERS:
    if (BOOK/f'追踪/章节提交/第{n:03d}章.json').exists():
        result['receipts'][str(n)]=tool('chapter_candidate.py','sync','--project',BOOK,'--chapter',n,'--revision-manifest',manifest,
         '--revision-stamp',BOOK/'追踪/修改影响/active.approved.json','--reason','用户授权第四批分轨生活局部修订','--confirm','SYNC')
result['voice']=tool('voice_profile.py','update','--project',BOOK);result['doctor']=tool('story_doctor.py','--project',BOOK)
result['world_export']=run([sys.executable,BOOK.parent/'skills/story-world-engine/scripts/world_gate.py','export','--project',BOOK,'--start',1,'--end',99,'--tracking-tool',SCRIPTS/'tracking_commit.py'])
for n in range(100,104):assert sha(prose(n))==read(WORK/'基线哈希.json')[prose(n).relative_to(BOOK).as_posix()]
write(WORK/'最终验收.json',result)
print(json.dumps({'revision':after['state_revision'],'doctor':result['doctor']['status'],'receipts':len(result['receipts']),'locked_100_103':True},ensure_ascii=False))
