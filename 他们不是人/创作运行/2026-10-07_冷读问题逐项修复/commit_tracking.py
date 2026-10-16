from pathlib import Path
import json, re, subprocess, sys, copy
P=Path(__file__).resolve().parents[2]
W=Path(__file__).parent
TOOL=P.parent/'skills/story-long-write/scripts/tracking_commit.py'
updates={
5:('当日取件单与004约定、006取表同属次日下午；两人互相观察。','当前存在补回先喝汤，又从店与市场消息推知镜辞行程；当日准备取件单，006同日下午取表。','次日早上钟表行'),
33:('授权日志核验；12:40旧凭证仍停用，15:18:07另签新凭证。','授权调日志，02:17同步04秒、覆盖06秒、重算09秒。11:00及12:40原凭证停用；12:40门禁服务正常，15:18:07另签新凭证，来人进楼不等于认证。',None),
45:('两地来源与住户拒绝登记重大争议，暂停的是楼栋入口关联通行。','两地来源与住户拒绝进入重大争议；暂停六号楼入口关联自动通行，人工联系保留，502机械门与门链仍由住户控制。杜分存纸件、存储盘和操作编号。',None),
56:('旧照片与新公开页分存；南栏匿名答复与页面空白并列，现场未核。陈屿公示及一次极浅缝保留。','旧点未回现场。南栏公开页无新行，匿名声称没处理过，现场及对方目标图未知。西口公示陈屿次日负责恒泰巡检；街对面极浅接缝一次，未追看。',None),
59:('15:02停供与15:36待复核相邻不判因果；裴亮29分钟骑行加11分钟等候记40，损失11元。','15:02停供，公开栏15:36待复核。裴亮15:10出仓，订单15:39止；自述等到15:50，骑行29加等待11共40分钟扣8，西口单车3，共11；到店及返程另计。陈屿群里说人别来店。',None),
66:('分开记得与亲做；旧证在她手里，次日18点复核保留，她自行离店。','沿011两页分开记得与亲做并纠正北河日期；柜台丢12电池单，拒蛋3。旧证在她手里，她自行离店。承065次晨，约定为明日18点，没有再次顺延。',None),
70:('胃疼喝汤不验人；旧缺席与逾期保留，杜通知当天补核，两人出发。','唐宁说初一无先喝汤习惯。她胃疼喝两口，汤4、白开1，镜辞油条2。原约定缺席逾期保留，杜当天通知补核，带工单去活动室不进502；两人各投2，她留铺未续旧话。',None),
71:('补核四项保护，次日02:17同步仍覆盖；跨午夜33元损失与纸签保留。','当天补核四项，不要求改口；留守至次日02:17亲见页面覆正常，楼下绿、502门链状态由交接核对。杜留纸签日志；临江18+15跨夜共33，宁州车补40不发无新186；许棠红卡。03:05后出租18镜10姜8回店。', '补核当日08:46至次日凌晨03:05后'),
72:('凌晨回店后的同一早晨开始首日零工；工资60扣饭2还夜车10，余48。','凌晨回店后的同一早晨接三日分类活：每日60错箱扣10。爱齐整被催快；报废表把只分当日20分钟、不带回加班，老秦同意无追加。首日扣饭2实领58、还10余48。明日08:30，迟到扣5。', '补核次日早上09:00至晚上20:00（首个工日）'),
73:('第二工日核前次同步副本与今早持续正常；新损失12、40各留来源。','第二工日杜叫核前次02:17日志、纸副本与持续正常页，不新增同步。许棠半日扣40拒签，临江今早12改派与前次33分记，宁州车补40不发。502药暂存12门未开；她在摊，镜姜各往返4。', '首个工日后次晨08:10至09:40（第二工日）'),
79:('旧物托管与当前行李分层，携122离开；陌生男退让入口短等未追车。','旧赠物留店托管未分权，当前手套图衣本带走，外套暂借。携122和08:40票离开，镜辞不追。陌生男有限问话后退到入口让路并等待未答问题，无姓名组织；镜辞不催平安，回店修后盖。', '次日06:40至08:00出门及回店'),
80:(None,None,None),
99:('真实坏表接修，报价60以内清灰校时及小齿轮获准；近距缝未立，明日取。','周衡还管钳送慢表。积灰磨损成立；更换前授权清灰校时及小齿轮合计60以内，大件或超额先问、旧件保留。近距未见稳定缝，玻璃反光不认证；单约明日取，姜要求写没有。',None)
}

def section(text,name):
    m=re.search(r'^## '+re.escape(name)+r'\n(.*?)(?=^## |\Z)',text,re.M|re.S)
    return [l[2:] for l in m.group(1).splitlines() if l.startswith('- ') and l!='- 无'] if m else []

for n,(result,obj,time) in updates.items():
    st=json.loads((P/'追踪/_tracking-state.json').read_text(encoding='utf-8-sig'))
    rec=(P/f'追踪/逐章记录/第{n:03}章.md').read_text(encoding='utf-8-sig')
    body=next((P/'正文').glob(f'第{n:03}章*'))
    changes=[{'name':l.split('｜',2)[0],'change':l.split('｜',2)[2]} for l in section(rec,'角色变化')]
    shadows=[]
    for l in section(rec,'伏笔变化'):
        ident=l.split('｜')[0]; v=copy.deepcopy(st['foreshadow'][ident]);v.pop('updated_chapter',None);v['action']='upsert';shadows.append(v)
    if n==56:
        v=copy.deepcopy(st['foreshadow']['F005']);v.pop('updated_chapter',None);v['action']='upsert';v['summary']='匿名答复声称南栏没处理过；截至观察时公开页未见新行。现场状态、对方完整目标图及是否以镜辞回复驱动均未证。';shadows.append(v)
    events=[]
    for l in section(rec,'时间与揭示'):
        ident=l.split('｜')[0];v=copy.deepcopy(st['timeline'][ident]);v.pop('updated_chapter',None);v.pop('first_recorded_chapter',None);v['action']='upsert'
        if ident==f'E{n:03}':
            if obj:v['objective_fact']=obj
            if time:v['story_time']=time
            if n==56:v['reader_knowledge']='旧图只证明过去，当前现场未复查；南栏无公开新行与匿名说法不是现场证实。陈屿一次极浅缝不授目标图。'
            if n==80:v['objective_fact']='陌生男仍在入口等问话，现实伤人打断对话。'+v['objective_fact']
        events.append(v)
    facts=[]
    for l in section(rec,'长期事实变化'):
        ident=l.split('｜')[0];v=copy.deepcopy(st['facts'][ident]);v.pop('updated_chapter',None);v.pop('first_recorded_chapter',None);v['action']='upsert';facts.append(v)
    constraints=section(rec,'连贯性约束')
    # Correct stale calendar instructions without removing independent constraints.
    constraints=[l.replace('昨天的三十三','前次复核的三十三').replace('次晨生活后果','首日零工后复查生活后果') for l in constraints]
    if n==59:constraints.append('11元仅为派工40分钟扣8加去西口单车3；其他行程不并入。')
    if n==70:constraints.append('逾期未到场记录保留，今天另安排补核。')
    if n==73:constraints.append('前次同步不重演；今早是第二工日，33为前次而非昨天。')
    if n==99:constraints.append('授权60以内清灰校时及小齿轮；大件或超额先问。')
    commitments=re.search(r'^- 下一章承诺：(.*)$',rec,re.M).group(1)
    commitments=[] if commitments=='无' else commitments.split('；')
    d={'result':result or re.search(r'^- 结果：(.*)$',rec,re.M).group(1),'character_changes':changes,'foreshadow_changes':shadows,'timeline_events':events,'fact_changes':facts,'constraints':constraints,'next_chapter_commitments':commitments}
    context={k:copy.deepcopy(v) for k,v in st['context'].items() if k not in ['recent_chapters','next_chapter_commitments']}
    snap={c['name']:copy.deepcopy(st['characters'][c['name']]) for c in changes if c['name'] in st['characters']}
    if n==99:
        snap['镜辞']['knowledge'].append('周衡同意60以内清灰校时及小齿轮；大件或超额先问。')
    txn={'schema_version':1,'mode':'revision','chapter':n,'chapter_title':body.stem.split('_',1)[1],'expected_state_revision':st['state_revision'],'delta':d,'context':context,'character_snapshots':snap}
    f=W/f'事务/第{n:03}章.json';f.parent.mkdir(exist_ok=True);f.write_text(json.dumps(txn,ensure_ascii=False,indent=2),encoding='utf-8')
    r=subprocess.run([sys.executable,'-X','utf8',str(TOOL),'commit','--project',str(P),'--input',str(f)],capture_output=True,text=True,encoding='utf-8')
    print(n,r.returncode,r.stdout.strip(),r.stderr.strip())
    if r.returncode:sys.exit(r.returncode)
    r=subprocess.run([sys.executable,'-X','utf8',str(TOOL),'check','--project',str(P)],capture_output=True,text=True,encoding='utf-8')
    print(r.stdout.strip(),r.stderr.strip())
    if r.returncode:sys.exit(r.returncode)
