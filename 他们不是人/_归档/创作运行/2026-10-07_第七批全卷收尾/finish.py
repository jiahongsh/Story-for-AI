from pathlib import Path
import hashlib, json, os, shutil, subprocess, sys

WORK=Path(__file__).resolve().parent;BOOK=WORK.parents[1];TOOLS=BOOK.parent/'skills/story-long-write/scripts'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(*args):
    r=subprocess.run(list(map(str,args)),capture_output=True,text=True,encoding='utf-8',errors='replace',env={**os.environ,'PYTHONUTF8':'1'})
    if r.returncode:raise RuntimeError(r.stdout+r.stderr)
    try:return json.loads(r.stdout)
    except json.JSONDecodeError:return {'output':r.stdout}

state=read(BOOK/'追踪/_tracking-state.json');assert state['state_revision']==219
volume=BOOK/'大纲/卷纲_第一卷.md';master=BOOK/'大纲/伏笔总表.md'
plan={'schema_version':1,'change_id':'seventh-document-status-20261007','summary':'将施工页眉改成本轮已修复复验状态，区分后续卷未埋规划与待修缺口','semantic_change':False,'changed_files':['大纲/卷纲_第一卷.md','大纲/伏笔总表.md'],'affected_entities':[],'affected_fact_ids':[],'affected_chapters':list(range(1,104))}
write(WORK/'文档状态计划.json',plan)
active=BOOK/'追踪/修改影响/active.json'
run(sys.executable,TOOLS/'revision_guard.py','plan','--project',BOOK,'--input',WORK/'文档状态计划.json','--output',active)
for p in (volume,master):
    b=BOOK/'备份/2026-10-07_第七批文档状态收尾'/p.relative_to(BOOK);b.parent.mkdir(parents=True,exist_ok=True);assert not b.exists();shutil.copy2(p,b);assert sha(p)==sha(b)
text=volume.read_text(encoding='utf-8-sig')
text=text.replace('001—050及096—099已完成本轮详细验收缺口修订；整卷尚待独立复验。','001—099的本轮修订清单已闭合，051—095及100—103接口已顺序复核；102—103仅按用户授权修正限定文字。主代理分阶段自审，不冒称独立审查。')
text=text.replace('001—050、096—099验收项修订已写入活动正文，早期逐章事件已补至051；第104章继续冻结。下一步独立复验，不重复施工。','本轮事实、材料、私人线、现场协作与已核伏笔账完成定点修复，追踪r219、正式接纳截至099。详见2026-10-07第七批全卷收尾总报告；第104章不在本次修订范围。')
volume.write_text(text,encoding='utf-8')
text=master.read_text(encoding='utf-8-sig').replace('后续计划：第一卷后续重写时重新决定是否保留南街首埋；若不保留，则第二卷用具体工作现场建立这套分工。','后续计划：当前第一卷不以锁匠前兆作四分工首埋。后续卷如采用，须用具体工作现场正式呈现；这一规划尚未发生。')
master.write_text(text,encoding='utf-8')
m=read(active);m['checked_files']=m['required_checks'];m['conflicts']=[{'source':'大纲/卷纲_第一卷.md','target':'大纲/伏笔总表.md','severity':'S3','issue':'施工页眉尚写待复验，F04段仍指向不确定第一卷回填','resolution':'更新本轮状态；后续卷如采用仍须正式呈现，不将前兆或规划写成已埋','status':'resolved'}]
m['tracking_action']={'kind':'not_required','state_revision_before':219,'state_revision_after':219,'reason':'仅修订工作状态/已明确未埋的表述，不改变剧情、正文、正史事实或未来卷路线'};write(active,m)
checks={'revision_gate':run(sys.executable,TOOLS/'revision_guard.py','check','--project',BOOK,'--input',active,'--stamp',BOOK/'追踪/修改影响/active.approved.json')}
checks['world_export']=run(sys.executable,BOOK.parent/'skills/story-world-engine/scripts/world_gate.py','export','--project',BOOK,'--start',1,'--end',99,'--tracking-tool',TOOLS/'tracking_commit.py')
assert checks['world_export']['limitations']==[]

# 7张既有人物视图：当前人物快照未变；E062/K005只修推荐时间。
previous=BOOK/'创作运行/2026-10-06_第六批早期验收修复/人物记忆_r175'
out=WORK/'人物记忆_r219';out.mkdir(exist_ok=True)
generator=(previous/'generate_actor_views.py').read_text(encoding='utf-8-sig').replace('175','219')
(out/'generate_actor_views.py').write_text(generator,encoding='utf-8')
checks['actor_views']=run(sys.executable,out/'generate_actor_views.py')
idx=read(out/'索引.json');assert idx['authority']['sha256']==sha(BOOK/'追踪/_tracking-state.json')
for actor in idx['actors'].values():
    for field in ('role_card','timeline'):assert sha(BOOK/actor[field]['path'])==actor[field]['sha256']

# 定点补充本次行动表达涉及的小人物，所有判断仅从正文摘取，未知能力不补造。
actors={
'孙立':([60,61,62,65,75],'修好父亲留下的表，退号费；保原票继续保修，不加签其他资料。','反复确认零件和票据，担心白跑和出勤；没有已证幕后动机。','短问价格、期限，反复强调“票留好”和“我这只就这一只”；不使用身份术语。'),
'蓝拖鞋客':([62,63],'把慢表修好，按时去上班；不报姓名，不接受调查。','急于赶班；昨日未扣迟到费会主动要求删去“可能”账。','只说故障、上班时间和费用，直接说“名字今天也不留”。'),
'裴亮':([57,58,59],'按工号派工，争销扣款、问陈工在哪，避免再增车费。','迟到和空跑自己负担，仍期待陈工能处理；不知接缝和停供。','叫“陈工”，摊开金额和时间，带怨气要具体答复，不替镜辞解释原理。'),
'侯强':([75],'争补签和当天工钱，随后自行解决吃饭回家。','通知迟看、空跑损失；不认识镜辞。私下买包子/水未告知，不能进入镜辞账。','问“卡怎么不开”“还能不能补签”，给家人解释收入损失；无身份术语。'),
'郭老板':([64,69,70],'经营早餐铺，催客用餐、收碗、腾座，制止盘问妨碍生意。','急躁、沿用旧称呼；没有能力判身份，也不因主角需要变成知情者。','喊单、催汤、说炭钱，短促带火气；叫旧名字不等于为主体认证。'),
'打印店老板':([54,55],'按公开页面出纸并收费，按自己的进货时间安排工作。','不愿持续刷空页误进纸，明确拒绝再按两小时刷新；不查内部现场。','只负责打印，直接谈加急、钱、进纸车和文件；不替调查给结论。')}
supplement={}
for name,(chapters,desire,limits,voice) in actors.items():
    refs=[]
    for ch in chapters:
        p=next((BOOK/'正文').glob(f'第{ch:03d}章_*.md'));refs.append({'chapter':ch,'path':p.relative_to(BOOK).as_posix(),'sha256':sha(p)})
    content=f'# {name}来源绑定辅助角色卡\n\n追踪r219；只读阅读视图，非新设定或旧章审批。\n\n- 独立目标：{desire}\n- 缺陷/代价与知情、能力限制：{limits}\n- 声线：{voice}\n- 本次未补外貌、家庭、能力、隐秘组织归属；新出场先读下列章。\n\n## 个人时间线引用\n\n'+''.join(f"- 第{r['chapter']:03d}章：{r['path']}；SHA256 {r['sha256']}。只引用该章亲见/自述，未告知内容不可授予别人。\n" for r in refs)
    p=out/'补充行动者'/f'{name}.md';p.parent.mkdir(exist_ok=True);p.write_text(content,encoding='utf-8');supplement[name]={'card_and_timeline':p.relative_to(BOOK).as_posix(),'sha256':sha(p),'sources':refs}
write(out/'补充索引.json',{'state_revision':219,'authority_sha256':sha(BOOK/'追踪/_tracking-state.json'),'actors':supplement})

old=BOOK/'创作运行/2026-10-06_第六批早期验收修复/早期伏笔索引/build_early_foreshadow_index.py'
early=WORK/'早期伏笔索引';early.mkdir(exist_ok=True)
script=early/'build_early_foreshadow_index.py';script.write_text(old.read_text(encoding='utf-8-sig').replace('175','219'),encoding='utf-8')
checks['early_freeze']=run(sys.executable,script,'--freeze');checks['early_build']=run(sys.executable,script,'--build');checks['early_check']=run(sys.executable,script,'--check')
sources={}
for p in sorted((BOOK/'正文').glob('*.md')):
    ch=int(p.name[1:4]);
    if ch<=103:sources[ch]={'path':p.relative_to(BOOK).as_posix(),'sha256':sha(p),'tracking_status':'已接纳' if ch<=99 else '锁定活动正文，未在099追踪中接纳'}
write(WORK/'最终正文来源.json',{'state_revision':219,'last_committed_chapter':99,'sources':sources})
checks['tracking']=run(sys.executable,TOOLS/'tracking_commit.py','check','--project',BOOK)
checks['doctor']=run(sys.executable,TOOLS/'story_doctor.py','--project',BOOK)
assert checks['doctor']['status']=='pass'
write(WORK/'最终闭合检查.json',checks)
print(json.dumps({'status':'PASS','revision':219,'actors':13,'prose_sources':len(sources)}))
