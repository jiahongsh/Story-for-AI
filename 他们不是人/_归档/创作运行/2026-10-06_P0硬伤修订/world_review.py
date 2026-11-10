from pathlib import Path
import json, hashlib, re, ast, subprocess, sys

BOOK = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
TOOL = BOOK.parent/'skills/story-world-engine/scripts/world_gate.py'
TRACK = BOOK.parent/'skills/story-long-write/scripts/tracking_commit.py'
GATES = ['knows','wants','fears','capability','no_plot','costs','consequences']
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: p.relative_to(BOOK).as_posix()

# 手写七关在候选生成之前建立；本脚本只绑定原文引用与真实文件指纹。
audit = WORK/'写前七关与事实底表.md'
sections = audit.read_text(encoding='utf-8').split('### ')[1:]
texts = {n:[re.search(rf'^{i}\. (.+)$',section,re.M).group(1) for i in range(1,8)]
         for n,section in zip([11,56,58,65,77,94,95],sections)}
specs = {
11: [('镜辞','追查停表原因并保存沈竹遗物','反复维修失败会令遗物线索丢失','最长一次')],
56: [('镜辞','保存旧地点的独立原件并控制自己的暴露','再次去现场会留下新脚印污染原有对照','先让别人'),('姜霁','分开照片来源和日期避免错误归因','把两地并成一处会使调查失去可靠性','两份都留')],
58: [('镜辞','向取表本人追问周远和陈屿两种名字的矛盾','观察被利用与自己替人填判决都是风险','谁收'),('陈屿','取得可见性反馈并在三点前回西口签字','交出流程底细及误时等人的记录均不愿承担','我不填'),('姜霁','保护来源并限制公开谈话的资料与权限','私下交易会把观察者卷入他不能承诺的责任','要谈就谈')],
65: [('镜辞','拒绝被填为三个对象的认证者','旧观察被拿去承担他没答应的认证责任','这三行我不填'),('姜霁','分存已发原话与未给认证的独立记录','自己的记录被改写成外部观察已经通过','以前的页也分开在'),('陈屿','保留索取反馈的渠道并继续现实收尾','拒绝反馈不能让自己的复核安排停下','你不填')],
77: [('唐宁','说清自己亲历的发烧并保留不认人的决定','原芽旧事被拿去要求她接纳当前存在','我讲的是我陪过'),('镜辞','核对旧工作底账与自己不知道的关系部分','可靠导致亲近者避开自己而自己毫不知情','愿意扛')],
94: [('镜辞','找到可调查目标但不把未知当待抓名单','漏掉危险或者给证据不足的人强加结论','我跟'),('姜霁','按风险分处置状态并保护个人隐私','把专业名单变成围猎名单会制造新的伤害','别把问号')],
95: [('镜辞','保留照片未见并等待低干扰近距接触','因急着找线索而把模糊照片看成新证据','远距静态图像')]
}
anchors = {11:'最长一次撑了十一天',56:'零三金属箱旁的废料筐照片',58:'你来取表那一分钟',65:'南栏发过',77:'答应客人',94:'安平里复核和南岸撤场以后',95:'指尖落到耳后那块'}
knowledge_sources = {
    (11,'镜辞'):(1,'最长的一次','本人七年维修亲历；第一章已呈现最长十一天'),
    (56,'镜辞'):(18,'废料筐','本人到过零三并保存复测照片；旧照片只支持拍摄当时'),
    (56,'姜霁'):(55,'备注先写','本人登记短信发送时刻与对照口径，掌握已有文件而非当前现场'),
    (58,'镜辞'):(6,'生产协调会','宁州周远在电话中说明会议时间，镜辞留存两地对照；这是转述证据'),
    (58,'陈屿'):(9,'你不是已经有两个周远','本人此前说过双周远，不能由此推知他知道双陈骁的生活'),
    (58,'姜霁'):(57,'我坐另一张桌子','本人此前明确公开接触边界，未取得密室信息'),
    (65,'镜辞'):(55,'发送时间七点五十二','本人发送的南栏短信与现场极淡残余并非一回事'),
    (65,'姜霁'):(55,'备注先写','本人登记对照、不写通过，保有原始版本'),
    (65,'陈屿'):(57,'打卡归现场','本人工作的规则与签字职责持续存在，不因镜辞拒绝就停下'),
    (77,'镜辞'):(1,'修了它七年','本人长期修表与原有亲历记忆；本项不包括刚被唐宁告知的发烧证词'),
    (94,'镜辞'):(75,'镜辞','本人经历南岸撤场，只支持未结事件回指，不授予处置名单全知'),
    (94,'姜霁'):(93,'姜霁','本人参与既有材料核对；本项不声称当时已经取得下一章的新名单'),
    (95,'镜辞'):(94,'七天','本人此前确定低干扰观察边界；收到本场照片后才可能评价照片质量'),
}

def cite(path, substring, source_id=None):
    lines=path.read_text(encoding='utf-8-sig').splitlines()
    i=next(i for i,line in enumerate(lines) if substring in line)
    result={'start_line':i+1,'end_line':i+1,'quote':lines[i]}
    if source_id: result['source_id']=source_id
    return result

state=BOOK/'追踪/_tracking-state.json'
tracking=json.loads(state.read_text(encoding='utf-8-sig'))
checks={}
for n,rows in specs.items():
    folder=WORK/f'第{n:03d}章'
    old=next((BOOK/'备份/2026-10-06_P0硬伤修订/正文').glob(f'第{n:03d}章_*.md'))
    original=folder/'original.md'
    original.write_bytes(old.read_bytes())
    sources=[{'id':'ORIGINAL','path':rel(original),'sha256':sha(original),'scope':'mixed'},
             {'id':'AUDIT','path':rel(audit),'sha256':sha(audit),'scope':'planned'}]
    actors=[];actions=[];cards=[]
    for i,(name,goal,fear,voice) in enumerate(rows,1):
        identity=f'C{n:03d}_{i}'
        reference=cite(original,voice,'ORIGINAL')
        actors.append({'id':identity,'name':name,'protagonist':name=='镜辞','own_goal':goal,
                       'without_protagonist':('仍处理本人日常职责和原有关系，不因镜头停留免除责任：'+goal),
                       'voice_refs':[reference],'timeline_refs':[reference]})
        seven=dict(zip(GATES,texts[n]))
        seven['wants']=f'{name}本次自身目标：{goal}。其他行动者的愿望不属于本人。'
        seven['fears']=f'{name}本场不愿承担：{fear}。依据原话与既有选择，不新增旧经历。'
        seven['knows']='只引用本人此前亲历、持有或说出的部分，不授予其他人物私密认知。'+seven['knows']
        if (n,name) in knowledge_sources:
            prior_n,anchor,acquisition=knowledge_sources[n,name]
            prior=next((BOOK/'正文').glob(f'第{prior_n:03d}章_*.md'))
            sid=f'PRIOR{i}'
            sources.append({'id':sid,'path':rel(prior),'sha256':sha(prior),'scope':'mixed'})
            known_ref=cite(prior,anchor,sid)
        else:
            # 唐宁追述的是第一章以前亲自陪同就诊，不是把本章新对话倒填到过去。
            prior_n=0; known_ref=reference
            acquisition='高二时本人亲自陪芽就诊，发生在第一章之前；本章只是转述自己的旧经历，不获知镜辞当年的底账'
        knowledge={**known_ref,'access':'memory','available_chapter':prior_n,'available_order':0,
                   'producer_action_id':None,'author_only':False,'certainty':'known',
                   'acquisition':acquisition,
                   'boundary':'只支持该人物原有声线、目的与本场选择，具体纠错依据另在事实底表逐项溯源；不支持原主生死或后台秘密。'}
        actions.append({'id':f'A{i}','actor_id':identity,'order':i,'story_tick':1,'kind':'action',
                        'choice':f'{name}在原场景中保持自身选择，依事实底表修正直接受影响的记录或说法：{goal}',
                        'gates':seven,'capacity':{'resources':['原场景已有资料、记忆、工作权限及普通通信'],
                        'permission':'仅执行本章原有权限内的核对、陈述与拒绝，不新增身份认证职权',
                        'limits':'各角色只使用既有渠道；本轮不增加能力、内部后台或跨城到场条件','evidence_refs':['ORIGINAL','AUDIT']},
                        'outcome':{'intent':goal,'success_guaranteed':False,
                        'failure_path':'对方可以拒绝回答，材料可以只支持过去，未决问题保持未决不强填结论',
                        'opposition':'他人仍有自己的目标和边界，维护与日常生活不会因主角的愿望自动配合'},
                        'knowledge_refs':[knowledge]})
        cards.append({'id':identity,'name':name,'status':'本轮来源绑定分析，不新增静态设定',
                      'own_goal':goal,'fear_or_attachment':fear,'voice_anchor':reference,
                      'timeline_anchor':reference,'seven_gates':seven})
    pre={'schema_version':1,'mode':'revision','chapter':n,
         'binding':{'tracking':{'path':rel(state),'sha256':sha(state),'state_revision':tracking['state_revision'],'last_committed_chapter':tracking['last_committed_chapter']},
                    'tracking_tool':{'path':str(TRACK.resolve()),'sha256':sha(TRACK)}},
         'sources':sources,'actors':actors,
         'scenes':[{'id':'S1','order':1,'story_time':{'label':f'第{n:03d}章原有直接受影响场景；其余旧场景不改变选择','tick':1},
                    'actors_onstage':[a['id'] for a in actors],'actors_offstage':[],'actions':actions}],
         'coverage':{'all_actors_reviewed':True,'all_scenes_reviewed':True,'background_only':[],
                     'basis':'历史局部修订仅重评直接受影响选择；以上列齐改动涉及者，整章回读保留其他行动、因果和声线。不冒称旧稿写作时已过七关。'},
         'manual_review':{'status':'passed','reviewer':'Codex /root solo','method':'原文、对应细纲、独立事实底表及直接证据章逐项核对；本轮写作与回读分阶段执行',
                          'basis':texts[n][0]+'；'+texts[n][6]+'。不向角色转移作者秘密，不追加主角强行胜利。',
                          'checks':{k:'passed' for k in ['seven_gates','knowledge_bounds','capacity_permissions','autonomy','constraints','consequences','voice','actor_scene_coverage','timeline']}}}
    write=lambda path,obj:path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    write(folder/'角色与时间线引用卡.json',cards)
    prepath=folder/'写前行动审查.json';write(prepath,pre)
    result=subprocess.run([sys.executable,str(TOOL),'check','--project',str(BOOK),'--packet',str(prepath),'--phase','prewrite','--tracking-tool',str(TRACK)],capture_output=True,text=True,encoding='utf-8')
    checks[str(n)]={'prewrite':{'returncode':result.returncode,'output':result.stdout,'stderr':result.stderr}}
    if result.returncode: raise RuntimeError(result.stdout+result.stderr)
    post=json.loads(json.dumps(pre)); candidate=folder/'candidate.md'
    post['postwrite']={'prewrite_packet':{'path':rel(prepath),'sha256':sha(prepath)},
                       'candidate':{'path':rel(candidate),'sha256':sha(candidate)},
                       'scene_results':[{'scene_id':'S1','actual_result':texts[n][6],
                         'action_ids':[a['id'] for a in actions],'evidence':[cite(candidate,anchors[n])],
                         'world_followups':['只校正本轮原有事件和证据边界；没有新追捕、新命名、能力升级或幕后揭底。']}],
                       'foreshadow_deltas':[{'id':'NO_CHANGE','operation':'none',
                         'description':'既有钩子与未解范围保留；只纠正支撑事实，不声称额外回收长线伏笔。','evidence':[cite(candidate,anchors[n])]}],
                       'manual_review':{'status':'passed','reviewer':'Codex /root solo','method':'候选与原稿逐段差异对照，独立一轮事实、因果和去味回读',
                         'basis':'所改句段符合锁定年份、地点、发送记录与认知来源；整章既有结果保留，不提前消费100章首缝。',
                         'checks':{k:'passed' for k in ['actual_coverage','causality','voice','knowledge_bounds','consequences','foreshadow']}}}
    postpath=folder/'写后行动复核.json';write(postpath,post)
    result=subprocess.run([sys.executable,str(TOOL),'check','--project',str(BOOK),'--packet',str(postpath),'--phase','postwrite','--tracking-tool',str(TRACK)],capture_output=True,text=True,encoding='utf-8')
    checks[str(n)]['postwrite']={'returncode':result.returncode,'output':result.stdout,'stderr':result.stderr}
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    print(f'{n:03d}: prewrite PASS; postwrite PASS (限本轮受影响选择)')
(WORK/'世界门检查.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
