import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BOOK = ROOT.parents[2]
REPO = BOOK.parent
GATE = REPO / 'skills/story-world-engine/scripts/world_gate.py'
TRACK = REPO / 'skills/story-long-write/scripts/tracking_commit.py'
PLAN = ROOT / '规划与行动依据.md'
SCENES = {
95: [
 ('094同夜柜台核七天记录', [('姜霁','交付有限行为记录并接受投入七天仍无结论'),('镜辞','核对观察与转述的区别，不把未发现记成藏得好')]),
 ('同夜猫眼交初步差异及既有照片', [('猫眼','交付版本差异嫌疑，拒交后台与实施者答案'),('镜辞','核照片布局，不凭静态照片填写接缝栏'),('观察员','按原观察范围转交既有入口照片'),('姜霁','维持次晨自然观察边界')]),
 ('次晨市场进入', [('镜辞','先做此前客表，不借开摊把周衡叫近'),('守钟人','催清台面正常开工'),('周衡','依既有市场往来入场'),('修鞋摊老板','在自己漏水摊位叫熟人帮忙')])],
96: [
 ('095末同一早晨市场自然观察', [('修鞋摊老板','要求顺手止住漏水而不立即承担整段重做费用'),('周衡','限定临时处理范围，随后回应熟人和捡回滚球'),('赵奶奶','就本人送医旧事和就医安排抱怨'),('五金摊老板','按已有工具借还往来招呼周衡'),('镜辞','正常接活，仅自然视线观察，放弃借口叫近')]),
 ('午前离场后的电话', [('姜霁','只收首次自然观察结果，不追加反复盯看'),('镜辞','保留不确定光斑不计入，如实交空结果')]),
 ('当日午后纸本进店', [('猫眼','展示八年纸本的范围与缺口，只提整齐需核'),('镜辞','暂停凭完整度判假，先核旧来源'),('守钟人','收茶并要求纸本别压维修物件')])],
97: [
 ('当晚对比独立旧版本', [('猫眼','逐项核相同地址及字段、排除不可靠差异'),('镜辞','核代理签收可能，仅将同字段版本改变记实')]),
 ('同夜核操作相关页', [('姜霁','询问操作与改写范围，不要求给实施者'),('猫眼','交付正常迁移账号审批的有限可核页，拒绝推为动手人'),('镜辞','拒绝把最早三年全判伪造，保留无旧版可核项')]),
 ('同夜分出近五年材料', [('猫眼','翻出照片聊天和赔付旧账，发现待核关系材料'),('镜辞','分袋保留两类材料，不把近年关系先吞成假历史'),('姜霁','入档版本级回填且实施者未知，安排关系核验')])],
98: [
 ('次日早晨市场有限访问', [('姜霁','先说明访问范围及拒绝权，询问亲历旧事'),('修鞋摊老板','边营业边说三天看摊，保留怨气与自己的损失'),('赵奶奶','只展示相关票据，拒拍无关隐私'),('五金摊老板','只亮借还工具相关聊天，不交整部手机'),('镜辞','记录听到与亲见范围，不追周衡继续观察')]),
 ('午后经同意的旧同事电话与材料复核', [('姜霁','征得本人许可才播放相关电话内容'),('旧同事','限几分钟说借车与抢功旧怨，不改成好人证明'),('猫眼','对照分散来源并提出身份旁证标题'),('镜辞','将标题改为近五年关系后果，不认证原人')]),
 ('傍晚旧锁芯与路过招牌', [('徐师傅','交回旧锁芯清抽屉并划证明边界，说明管钳待还'),('镜辞','分置旧芯及周衡材料，不据物件串案'),('守钟人','维护柜台物件保管及正常店务'),('周衡','路过只看钟表招牌，不作敌意试探'),('姜霁','交代明日仍正常营业，不预定周衡进店')])],
99: [
 ('翌日午前还工具与送表初检', [('周衡','先还徐师傅管钳，再说明走慢并准许开盖初检'),('镜辞','代收普通工具并初检真实故障，不作跟踪机关')]),
 ('同次接单价格范围与自然观察', [('镜辞','说明清灰校时及小齿轮六十以内，大件和超额另问，旧件保留'),('周衡','询问工期和换件后授权有限维修，约明日取'),('镜辞','在真实工作视线中未确认，不借履历问题延长接触'),('周衡','仅谈市场熟人和当下修理抱怨，不知案内信息')]),
 ('周衡离场后的联络与拆修', [('姜霁','接受近距仍未确认，不在外围拦人'),('镜辞','如实记录并依授权继续拆修，将变形齿轮留袋'),('守钟人','要求按普通工序修表而不越报价换大件')])]
}

# 每行按知道、想要、怕失去、能不能、备选/反事实、代价、后果七关分别填写。
G = {
'镜辞': ['只用当场获准资料、自己亲见与本人修表技能，不知周衡内幕', '要可信答案和修表工作的交付，不用案情替客户作决定', '怕又把愿望当证据，也怕赔坏客人的物件和店中信用', '只会基础接缝观察与修表，可核相关纸本，没有后台和身份判决权', '可以拒接或不观察，仍选有限观察和普通客修，因为它们各有实际目标', '接受无结果和耗费工时，不引诱、尾随、超价修理或私装装置', '空结果必须保留，客人仍有选择，修理成败由本店承担而非案情开脱'],
'姜霁': ['掌握七天本人调查与已获准相关材料，新材料须当场核对', '要查清弱相关及保留可复核记录，不能无限盯住普通生活', '怕漏案也怕自己反复调查伤害当事人及材料可信度', '能有限访问与请求相关材料，无强取手机、无限调档和原人判决权限', '可以只等镜辞看出异常，仍选有限来源复核和接纳空结果维护本人方法', '愿承担查不到及被拒绝，不以调查期限投入要求强制产出', '被访者可限范围或保留不满，观察结束不自动升级为围堵抓捕'],
'猫眼': ['只掌握渠道交付的旧版本及出处，不持有后台或制造方答案', '要交付有价且可复核的来源，避免客户把差异误叫身份证明', '怕失信和暴露来源，无限答疑还会吞掉本人交易边界', '能核旧纸本缓存与有限导出相关页，不能入侵内部数据库', '可以拒绝扩大委托，仍做原范围版本核验，因为这是本人职业', '愿花时间查错门牌和代理签收，拒交整本隐私与无来源答案', '差异可以成立而实施者仍未知，镜辞也可纠正她过强的条目标题'],
'周衡': ['只知道自己生活往来和物件故障，不知内部调查及镜辞能力', '要做完手头活、归还工具并让旧表继续使用', '怕熟人把顺手帮忙当无限义务，也怕小修被算成大修', '会普通维修，有本人时间与物件授权权，无调查者内幕知识', '可以拒绝帮忙或另找店，选择有限帮工与附近修表源于既有日常便利', '愿付六十以内及一次往返，大件或超额须重新同意', '熟人可能仍抱怨漏水，表需隔日来取，镜辞受维修范围约束'],
'守钟人': ['只知道店内物件与镜辞有限交代，不知案卷全貌', '要生意按时交活、台面可用及工具零件不丢', '怕修表铺被案卷占满、客户物件混放和返工赔钱', '可以管本店台面与提醒工序，不能判案或替客人扩大授权', '可以不问案情，仍催店务是因为这就是他自己的生意', '愿借有限柜台，不让案情代替工序，不替修理结果兜底', '镜辞要腾出维修区并对自己接下的活负责，不获额外身份答案'],
'观察员': ['只知已有七天记录和入口拍到的位置，不保证未来行程', '要准确交接记录并减少新增干扰', '怕把推断作所见或为了调查产出夸大材料', '能交已有相关照片和时间位置，不能用照片作超凡扫描', '可追拍求更清晰图，选择交已有图避免新增干扰且足够定位', '接受照片不够辨接缝，不为此把拍摄延伸到近身跟踪', '收到照片者只能核布局，不能用画质不足制造异常结论'],
'修鞋摊老板': ['只知自家水管、住院和周衡替看摊的亲历，不知身份调查', '要摊位能营业又少花重做费用，旧事别耽误当前客人', '怕漏水弄湿鞋、停工赔钱，也不愿把记忆说成全知道', '能允许自家有限修理、讲本人旧事及展示自存照片', '可花钱另找人或拒绝访问，仍找熟人临时帮忙及限时说话符合经营目标', '愿几分钟和相关照片，不交所有私人往来，也未准整段重做', '周衡可限定修理，日后接头复漏仍有争执，他不需为调查者赞美目标'],
'赵奶奶': ['只知本人摔伤送医及自己的票据安排，不知案内假设', '要办自己就医卖菜的事，并说清谁陪自己去过', '怕隐私被整页带走，也烦晚辈一直催自己', '能决定展示本人相关票据范围，只能为本人亲历说话', '可拒访，仍限范围讲是想说清送医旧事又保护自己', '愿短时间说明，拒拍不相干医疗信息或替周衡保证身份', '姜霁须缩小拍摄范围，送医事实得到支持而身份结论仍未定'],
'五金摊老板': ['只知自己工具借还与当时争吵，不知周衡八年全史', '要工具和账说清、做自己的生意，不替别人背证明责任', '怕借出不还、手机隐私被翻和调查耽搁', '能展示本人相关聊天与亲历，不可认证全部身份', '可拒聊，仍给相关片段是要把欠账说明白并保留怨气', '只亮数条相关消息，不交手机联系人，徐师傅管钳不属自己旧账', '不同来源可证明争吵修补，但不会把不满自动变成异常或无罪证词'],
'旧同事': ['只知共事抢功和自己搬家借车互助，不知内部案卷', '要说明为何不喜欢周衡，不让别人替自己改关系', '怕被强迫夸人或披露全部家庭聊天和工作材料', '能电话自愿说相关亲历，播放须本人同意', '可以挂断，仍用几分钟讲清是为维护自己的说法', '接受相关部分通话，不同意无限问询和无关隐私转交', '抱怨与互助能并存，调查者无法据其怨气判身份或抹去发生过的事'],
'徐师傅': ['只知本人旧锁维修与管钳借出，陈启明已说不用再换锁', '要清抽屉并收回工具，止住旧物被反复当铁证追问', '怕正常维修被扯成谁进过门的保证或重新收费借口', '能交自己保留的旧芯并说明那单活，不能判持钥匙者与身份', '可继续收旧芯，选择交回现有协查保管者为清物件与划责任', '愿说明来源，不承担身份签认，也不把借工具当周衡异常', '旧芯进入铁盒隔层，管钳另还，后续不能拿物件混作周衡案证明']}

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def run(cmd,log):
 r=subprocess.run(cmd,cwd=REPO,capture_output=True,text=True,encoding='utf-8')
 log.write_text(r.stdout+r.stderr,encoding='utf-8')
 if r.returncode: raise RuntimeError(str(log)+'\n'+r.stdout+r.stderr)
 return r.stdout
def ref(name):
 lines=PLAN.read_text(encoding='utf-8').splitlines(); i=next(i for i,l in enumerate(lines) if l.startswith(name+'：'))
 return dict(source_id='SRC1',start_line=i+1,end_line=i+1,quote=lines[i])

def pre(n,final=False,delivery=False):
 folder=ROOT/f'第{n:03d}章'; folder.mkdir(exist_ok=True)
 path=folder/('交付复验行动包.json' if delivery else ('最终修订写前行动审查.json' if final else '写前行动审查.json'))
 if path.exists(): raise RuntimeError('冻结包已存在，不覆盖：'+str(path))
 sources=[PLAN,next((BOOK/'正文').glob(f'第{n:03d}章_*.md')),next((BOOK/'正文').glob(f'第{n-1:03d}章_*.md')),BOOK/f'大纲/细纲_第{n:03d}章.md']
 if n==95: sources.append(BOOK/'追踪/候选章/历史修订_090-094_2026-10-16/第094章/第094章_十一份.md')
 if final: sources.append(ROOT/'复核发现与最终修订计划.md')
 if delivery: sources.append(ROOT/'交付前基线复核.md')
 cmd=[sys.executable,str(GATE),'init','--project',str(BOOK),'--chapter',str(n),'--mode','revision','--tracking-tool',str(TRACK),'--packet',str(path.relative_to(BOOK))]
 for s in sources: cmd+=['--source',str(s.relative_to(BOOK))]
 subprocess.run(cmd,check=True,capture_output=True)
 d=json.loads(path.read_text(encoding='utf-8')); d['sources'][0]['scope']='planned'
 names=list(dict.fromkeys(a for _,acts in SCENES[n] for a,_ in acts))
 d['actors']=[dict(id=name,name=name,protagonist=name=='镜辞',own_goal=G[name][1],without_protagonist=G[name][4],voice_refs=[ref(name)],timeline_refs=[ref(name)]) for name in names]
 d['scenes']=[]; order=0; first={}
 remote={95:{0:['姜霁'],1:['姜霁','观察员']},96:{1:['姜霁']},97:{1:['姜霁'],2:['姜霁']},98:{1:['旧同事'],2:['姜霁']},99:{2:['姜霁']}}.get(n,{})
 for si,(label,acts) in enumerate(SCENES[n]):
  on=list(dict.fromkeys(a for a,_ in acts)); off=remote.get(si,[])
  scene=dict(id=f'S{si+1}',order=si+1,story_time=dict(label=label,tick=(si+1)*10),actors_onstage=[a for a in on if a not in off],actors_offstage=off,actions=[])
  for name,choice in acts:
   order+=1; aid=f'A{order}'; rr=ref(name); prior=first.get(name)
   kr={**rr,'access':'memory','available_chapter':n-1,'available_order':0,'producer_action_id':None,'author_only':False,'certainty':'known','acquisition':'本段工作卡只引用本人开始前职业、亲历生活和前章有限任务；该选择新增消息必须在当场交谈或观看后取得。','boundary':G[name][0]+'；整张工作卡的未来动作不当成开始前已完成。'}
   if prior:
    kr.update(access='planned-earlier-action',available_chapter=n,available_order=prior[1],producer_action_id=prior[0],acquisition='承接本章本人已列在前的观察或交谈；新刺激仅在当前场景的报告、展示或电话中取得。')
   else: first[name]=(aid,order)
   gates=dict(zip(['knows','wants','fears','capability','no_plot','costs','consequences'],G[name])); gates['wants']+='。此步具体选择：'+choice
   scene['actions'].append(dict(id=aid,actor_id=name,order=order,story_tick=(si+1)*10,kind='action',choice=choice,gates=gates,capacity=dict(resources=['本人亲历、获准相关材料或本人工作工具'],permission=G[name][3],limits=G[name][5],evidence_refs=['SRC1','SRC2','SRC3','SRC4']),outcome=dict(intent=choice,success_guaranteed=False,failure_path='可被拒绝、证据不足或修理结果不如预期，仍保留已定权限和未知。',opposition=G[name][6]),knowledge_refs=[kr]))
  d['scenes'].append(scene)
 d['coverage']=dict(all_actors_reviewed=True,all_scenes_reviewed=True,basis='对照本批逐场细纲及原文核查台前后台：记录交接、市场帮工、纸本、访谈、旧芯及客修均有行动者；来往顾客与踢球孩子仅为不承担新因果决策的布景。',background_only=[dict(name='踢球孩子与来往顾客',reason='仅正常玩球、走动与已约客修背景，不提供新案情、权限或协作承诺。')])
 d['manual_review']=dict(status='passed',reviewer='Codex单线程分阶段复核',method='先读094修订候选、095—100正式正文和细纲及角色卡，再逐场确认知识与权限；非独立代理审查。',basis='095与094同夜相接，096不加逼近试探，097只确认版本差异，098自愿有限展示并保留怨气，099六十以内与大件另问先于动件；100首缝不提前。',checks={k:'passed' for k in ['seven_gates','knowledge_bounds','capacity_permissions','autonomy','constraints','consequences','voice','actor_scene_coverage','timeline']})
 save(path,d)
 if final:
  d['manual_review']['method'] += ' 初稿完成后发现的时间承接和照片交接顺序已重新评估；本包只许可后续最终修订，不冒充初稿写作前记录。'
  save(path,d)
 if delivery:
  d['manual_review']['method']='交付前发现外部第010章修订已推进r250，重读该事务、当前上下文及本批全文和094—100接口后重评。此为交付阶段重新核源，不冒称初稿写前记录；初稿r249包原样保留。'
  save(path,d)
 run([sys.executable,str(GATE),'check','--project',str(BOOK),'--packet',str(path.relative_to(BOOK)),'--phase','prewrite','--tracking-tool',str(TRACK)],folder/('交付前核源检查.json' if delivery else ('最终修订写前检查.json' if final else '写前检查.json')))
 print(n,'PREWRITE_PASS')

def checks(n):
 folder=ROOT/f'第{n:03d}章'; body=next(folder.glob('第*.md')); scripts=REPO/'skills/story-long-write/scripts'
 for name,args in [('语言',['language_gate.js']),('文风卫生',['check-style-hygiene.js','--check','--fail-on=blocking']),('AI句式',['check-ai-patterns.js','--check','--fail-on=blocking']),('退化',['check-degeneration.js','--check','--language=zh','--fail-on=blocking'])]:
  run(['node',str(scripts/args[0]),*args[1:],str(body)],folder/(name+'检查.log'))
 print(n,'FOUR_GATES_PASS')

if __name__=='__main__':
 if sys.argv[1]=='pre':
  for n in range(95,100): pre(n)
 elif sys.argv[1]=='pre-final':
  SCENES[95][1][1][:]=[('猫眼','交付版本差异嫌疑，拒交后台与实施者答案'),('观察员','按原观察范围转交既有入口照片'),('姜霁','转交已有照片并维持次晨自然观察边界'),('镜辞','核照片布局，不凭静态照片填写接缝栏')]
  for n in range(95,100): pre(n,final=True)
 elif sys.argv[1]=='pre-delivery':
  SCENES[95][1][1][:]=[('猫眼','交付版本差异嫌疑，拒交后台与实施者答案'),('观察员','按原观察范围转交既有入口照片'),('姜霁','转交已有照片并维持次晨自然观察边界'),('镜辞','核照片布局，不凭静态照片填写接缝栏')]
  for n in range(95,100): pre(n,final=True,delivery=True)
 elif sys.argv[1]=='check': checks(int(sys.argv[2]))
