from pathlib import Path
import json, os, sys, subprocess, shutil, hashlib, importlib.util, copy

BOOK=Path(__file__).resolve().parents[2]
WORK=Path(__file__).resolve().parent
SCRIPTS=BOOK.parent/'skills/story-long-write/scripts'
CHAPTERS=[11,56,58,65,77,94,95]
ENV={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'}
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,obj):
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def run(args):
    r=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',env=ENV)
    if r.returncode:raise RuntimeError(r.stdout+r.stderr)
    return {'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
def original(n):return next((BOOK/'正文').glob(f'第{n:03d}章_*.md'))
def clean(row):return {k:v for k,v in row.items() if k not in ['updated_chapter','first_recorded_chapter']}
def fact(fid,subject,predicate,obj,chapter,evidence,entities,negative):
    return {'action':'upsert','id':fid,'category':'历史因果','subject':subject,'predicate':predicate,
            'object':obj,'cardinality':'one','canon_status':'正文已证','reader_status':'已揭示',
            'established_chapter':chapter,'reveal_chapter':chapter,'evidence':evidence,
            'related_entities':entities,'negative_constraints':negative}
def citation(n,text):return original(n).relative_to(BOOK).as_posix()+'｜'+text

baseline=read(WORK/'修订前追踪快照.json')
def transaction(n,state):
    if n>=57:
        t=read(BOOK/f'追踪/事务-第{n:03d}章.json')
        t['mode']='revision'
        d=t['delta']
        d['retired_context_items']=[];d['retired_characters']=[];d['continuity_changes']=[]
        transitions='；'.join(f"{f['id']}本章{f['status']}" for f in d['foreshadow_changes'])
        d['foreshadow_changes']=[{'action':'upsert',**clean(baseline['foreshadow'][f['id']])} for f in d['foreshadow_changes']]
        d['constraints'].append(transitions+'；上栏为截至99的当前值，原埋设/回收发生章仍按回收栏和原事务留存。')
        # 原始逐章事务保留在追踪，旧时现场动作仍在本章人物变化中；当前快照绝不倒退。
    else:
        title=(WORK/f'第{n:03d}章/candidate.md').read_text(encoding='utf-8').splitlines()[0].split(' ',2)[-1]
        d={'result':'','character_changes':[],'foreshadow_changes':[],'timeline_events':[],
           'fact_changes':[],'constraints':[],'next_chapter_commitments':[]}
        t={'schema_version':1,'mode':'revision','chapter':n,'chapter_title':title,'delta':d}
    if n==11:
        d.update(result='不替芽解释北河之行。核七年怀表维修单，最长走时十一天；先留影，再开后盖，不先修。',
                 character_changes=[{'name':'镜辞','change':'将自己的判断与芽的决定分开；从反复修好转为先记录停表原因'}],
                 timeline_events=[{'action':'upsert','id':'E011','story_time':'北河之行期间，中午十二点十六',
                   'objective_fact':'镜辞核七年维修单，最长连续走时十一天；留存表壳、指针和维修单影像后开后盖。',
                   'reader_knowledge':'怀表反复停走；镜辞改变拆检方法，停表原因尚未揭开。',
                   'reveal_status':'已揭示','reveal_chapter':11,'characters':['镜辞']}],
                 constraints=['取信前最长走时十一天，不由走时推断沈竹生死。'],
                 next_chapter_commitments=['在已留影的拆检中追查停表原因，不凭空再次初识遗物。'])
        d['fact_changes']=[fact('K006','沈竹遗留怀表','取信前七年维修中的最长连续走时','十一天',1,
                              [citation(1,'七年反复维修，最长十一天'),citation(11,'旧维修单与拆检')],
                              ['怀表','沈竹','镜辞'],['不是半个月或两个月；不据此推断沈竹生死','只约束已经写出的维修历史，不新增超自然走时规律'])]
    if n==56:
        d.update(result='17与03旧照片按来源分存，不据此断言当前现场。西口公示陈屿；街对面见极浅接缝一次，未追看。',
                 character_changes=[{'name':'镜辞','change':'分存旧照片，记录当前现场未复查；留西口通知，只看一次不追看'},
                                    {'name':'姜霁','change':'按地点和拍摄日期保留底片；恒准外包与恒泰公示分存'},
                                    {'name':'陈屿','change':'站街对面点表问今天还准吗，不进钟表行'},
                                    {'name':'猫眼','change':'保存公开页并回校验值，不提供内部上级名单'}],
                 foreshadow_changes=[{'action':'upsert',**clean(baseline['foreshadow']['F006'])}],
                 timeline_events=[{'action':'upsert',**clean(baseline['timeline']['E056'])}],
                 constraints=['F006本章埋设、57回收；上栏为截至99当前值。','旧照片只证明拍摄当时；17老树与03金属箱不混。'],
                 next_chapter_commitments=['按西口公示做公开核对；新角度未见不能抹掉这一次看见。'])
        d['timeline_events'][0]['reader_knowledge']='旧照片按地点分存，只证明过去；当前现场未复查。陈屿不怕被看见，南栏没有新记录。'
        d['fact_changes']=[fact('K008','十七号与零三','独立地点及旧照片归属',
                            '北河17为老树旁外露金属、泥痕与基座油漆；临江老码头03为金属箱焊疤及废料筐',18,
                            [citation(14,'北河17全景与油漆记号'),citation(18,'老码头03金属箱与废料筐'),citation(56,'旧存档分存')],
                            ['十七号','零三','镜辞','姜霁'],['两点不得合并；旧照片不能证明今天现场仍未清理'])]
    if n==58:
        d['result']='东口窗边追问双周远异地同时出现及陈屿工牌；不混用双陈骁工单。样本仅口头，不给D4与502。'
        d['timeline_events'][0]['objective_fact']='公开窗边，镜辞用临江取表记录与宁州同分钟公司会议追问陈屿。陈屿不填周远，口头称样本、栏不止一格。镜辞拒供D4与502。'
        d['constraints'].append('双周远对应取表与会议；宁州汽修工单和两套生活属于双陈骁，不混案。')
    if n==65:
        d['constraints'].append('055发的是03南栏残余明显，对方回复南栏没处理过；已发反馈不等于给过通过。')
        d['fact_changes']=[fact('K009','南栏对照短信','发送、回复与认证边界',
                            '镜辞七点五十二发送“03南栏，残余明显。”；次晨六点二十一对方回复“南栏没处理过。”；未给通过',55,
                            [citation(54,'输入框尚未发送'),citation(55,'发送及次晨回复'),citation(65,'保存已发原话，拒给认证')],
                            ['南栏','镜辞','姜霁'],['不把54尚未发延用到55之后；不对调发送者与回复者','假异常不证明现场残余明显；未给认证不等于没发短信'])]
    if n==77:
        d['timeline_events'][0]['objective_fact']=d['timeline_events'][0]['objective_fact'].replace('给沈竹送表','给普通客人送修好的表')
        d['character_changes'][2]['change']='后间听着不出来；怀表当前的事不揭，旧底账放回、原账不改'
        d['constraints'].append('沈竹镜辞十四岁时失踪。高二送表是普通客人委托，不是沈竹取表。')
        d['fact_changes']=[fact('K007','沈竹','失踪时镜辞年龄','十四岁；第一卷现时二十一岁，失踪已七年',1,
                             [citation(1,'失踪七年'), '设定/角色/沈竹.md｜失踪时镜辞十四岁',citation(77,'高二委托改为普通客人')],
                             ['沈竹','镜辞'],['不能因高二底账写成沈竹仍在送取表；不认证生死'])]
    # 原章结果与承诺保留；只提交截至99的现有核心快照，不复活已退役角色。
    t['expected_state_revision']=state['state_revision']
    t['context']={k:copy.deepcopy(state['context'][k]) for k in ['position','long_term_constraints','active_character_names','continuity_risks']}
    t['character_snapshots']={r['name']:copy.deepcopy(state['characters'][r['name']]) for r in d['character_changes'] if r['name'] in state['characters']}
    return t

spec=importlib.util.spec_from_file_location('tracking_validation',SCRIPTS/'tracking_commit.py')
tc=importlib.util.module_from_spec(spec);sys.modules[spec.name]=tc;spec.loader.exec_module(tc)
dry=copy.deepcopy(baseline)
for n in CHAPTERS:
    t=transaction(n,dry)
    normalized=tc.normalize_transaction(dry,t)
    # 当前快照原样提交，位置与持有物无变更；最终commit仍执行工具自己的连续性守卫。
    dry=tc.merge_transaction(dry,normalized)
    record=tc.render_delta(n,t['chapter_title'],normalized['delta'],set(dry['characters']))
    if len(record.encode('utf-8'))>3072:raise RuntimeError(f'{n} record too large: {len(record.encode("utf-8"))}')
    write(WORK/f'第{n:03d}章/修订事务.json',t)
    print(f'{n:03d}: tracking dry run PASS; record {len(record.encode("utf-8"))} bytes')

if '--apply' not in sys.argv:sys.exit(0)
current=read(BOOK/'追踪/_tracking-state.json')
if current!=baseline:raise RuntimeError('追踪已变；重新构造，禁止复用旧事务')
hashes=read(WORK/'基线哈希.json')
for rel,expected in hashes.items():
    if hashlib.sha256((BOOK/rel).read_bytes()).hexdigest()!=expected:raise RuntimeError('源文件已改变：'+rel)
backup=BOOK/'备份/2026-10-06_P0硬伤修订/追踪'
if not backup.exists():shutil.copytree(BOOK/'追踪',backup)
checks={}
for n in CHAPTERS:
    candidate=WORK/f'第{n:03d}章/candidate.md'
    checks[str(n)]={}
    for script,flags in [('language_gate.js',[]),('check-style-hygiene.js',['--check','--fail-on=blocking']),('check-ai-patterns.js',['--check','--fail-on=blocking']),('check-degeneration.js',['--check','--language=zh','--fail-on=blocking'])]:
        checks[str(n)][script]=run(['node',str(SCRIPTS/script),*flags,str(candidate)])
    original(n).write_bytes(candidate.read_bytes())
    (BOOK/f'大纲/细纲_第{n:03d}章.md').write_bytes((WORK/f'第{n:03d}章/outline.md').read_bytes())
    state=read(BOOK/'追踪/_tracking-state.json')
    tx=transaction(n,state)
    path=WORK/f'第{n:03d}章/修订事务.json';write(path,tx)
    checks[str(n)]['tracking_commit']=run([sys.executable,str(SCRIPTS/'tracking_commit.py'),'commit','--project',str(BOOK),'--input',str(path)])
    checks[str(n)]['tracking_check']=run([sys.executable,str(SCRIPTS/'tracking_commit.py'),'check','--project',str(BOOK)])
    print(f'{n:03d}: written; four language gates PASS; tracking committed and checked')
    write(WORK/'落盘检查.json',checks)
print('All seven revised; last chapter remains 99.')
