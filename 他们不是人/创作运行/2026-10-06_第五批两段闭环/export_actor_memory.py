"""Generate source-bound auxiliary cards and personal timelines; never modify canon."""
from revision_runtime import *
import re
authority=BOOK/'追踪/_tracking-state.json';state=read(authority)
revision=state['state_revision'];assert revision>=104
cards=ROOT/'行动者卡';timelines=ROOT/'人物时间线'
cards.mkdir(exist_ok=True);timelines.mkdir(exist_ok=True)
sources={x:ROOT/y/'写前七关与人物卡.md' for x,y in [('A','A_D4来源'),('B','B_分轨复核责任离开'),('C','C_现场协作处置撤案')]}
gates={x:text(p) for x,p in sources.items()}
def section(phase,title):
 return gates[phase].split('## '+title+'\n',1)[1].split('\n## ',1)[0].strip()
def paragraph(phase,prefix):
 return next(p for p in gates[phase].splitlines() if p.startswith(prefix))
entries={
 '镜辞':('A/B/C',section('B','镜辞')+'\n\n'+section('C','镜辞卡与行动七关'),[53,80,81,83,90,95],'先问具体事，承认想冲；手艺比喻不等于有处置权。'),
 '姜霁':('A/B/C',section('B','姜霁')+'\n\n'+section('C','姜霁卡与七关'),[53,80,83,88,90,92],'短任务和限制；遭遇质问须承认责任，不用审核术语盖住别人不满。'),
 '当前存在':('B',section('B','当前存在'),[66,67,76,77,78,79],'用眼前需求、抱怨和明确拒绝；道歉承认具体伤害，不自列善行求抵账。'),
 '守钟人':('A',paragraph('A','守钟人（'),[53,83,95],'短问、修表与店规的提醒，不知道的幕后不讲答案。'),
 '陈屿':('A',paragraph('A','陈屿（'),[58],'索取反馈，允许被拒；不能引用未取得的私人笔记细节。'),
 '陈平':('C',section('C','灰外套/陈平卡'),[80,81],'坚持叫我陈平和我要走；不是专为主角宣讲道理。'),
 '陌生男人':('B/C',section('C','陌生男人卡'),[79,80,81,82],'现场老手的压迫感，先松手、留下伤者；身份与所属仍未知。'),
 '张岚':('C',paragraph('C','张岚：'),[83,84,85,86,87,88,90],'先说今晚住哪、怕什么；可重复否定共住，不被调查结论替她作选择。'),
 '老李':('C',paragraph('C','老李：'),[84,85,86,87,88,89,90],'列正确旧事、索问位置、坚持改动作和回家；压力下反复追问。'),
 '物业技术员':('C',paragraph('C','技术员：'),[88],'操作性抱怨与确认，不代法院判身份和永久居住权。'),
 '镇封行动员':('C',paragraph('C','镇封者：'),[90],'报告范围与承载，不诊断原人；直接台词尚少，不编固定口头禅。'),
 '定向剥蚀行动员':('C',paragraph('C','剥蚀者：'),[90],'动作与停手表达专业边界；未有足够直接台词定稳定口头禅。'),
 '年长行动员':('C',paragraph('C','年长者：'),[89,90,92,93],'旧成功经验撑着不甘；会问压得够不够深，也能署名承认此次未证。'),
 '周诚':('C',paragraph('C','周诚：'),[91,92],'普通抱怨、直接问还要记录哪只手买菜；不被撤案变成感恩工具。'),
 '周诚妻子':('C',paragraph('C','妻子：'),[91,92],'先回忆摆杯等日常，再承认焦虑、指出调查增加恐惧。'),
 '观察员':('C',paragraph('C','观察员：'),[88,92,94,95],'范围内短讯；撤令后没有私自盯人的隐藏授权。'),
 '猫眼':('C',paragraph('C','猫眼：').split('；周衡')[0]+'。',[95],'拿具体旧版本说话；谁动手未知，不能卖一个全知答案。'),
 '周衡':('C','本人自然买菜、送工具、帮摊主和修水管，日常来往有独立需求。本人是否知道被调查、身份真相及幕后目的未证，不由读者所知反授给他。此次只写既有生活行为；稳定缺陷与内在欲望待后文证据，不能凭薄卡预设反派心理。',[94,95],'本段主要是别人喊周师傅；其稳定直接声线尚未展开。'),
}
for name,prefix,voice,chs in [
 ('吴老板','吴：','疼中仍关心铺和米，自己报钥匙位置。',[80,81]),
 ('刘成','刘成：','此段主要以救援行动与伤腕表现，未有足够台词定型。',[80,81,82]),
 ('市场管理员','管理员：','吹哨、分路、明确让搬哪两只筐。',[80,81]),
 ('杜经理','杜：','讲工单和责任，拒替住户同意。',[71,73]),
 ('陈启明','陈启明：','维护自家门链，拒交钥匙。',[71,73]),
 ('许棠','许棠：','说白跑和扣钱，自己阻止邻居白下楼。',[73]),
 ('郭老板','郭（070）：','营业与做饭的话，普通生活不中断。',[70]),
 ('老秦','老秦（075/078）：','工钱、收摊、公物按约算，不代安排去处。',[75,78]),
 ('侯强','侯强（075）：','签收和白跑损失，不由别人的退款抹平。',[75]),
 ('孙立','孙立（075）：','据原票要六元，拒非必要资料。',[75]),
 ('唐宁','唐宁（077）：','限定我讲的是亲历旧事；不自动恢复当前友谊。',[77])]:
 phase='C' if prefix in ['吴：','刘成：','管理员：'] else 'B'
 entries[name]=(phase,paragraph(phase,prefix),chs,voice)
entries['医护']=('C','由现场出血与转运需要判断，能加压止血和送医，不能认证身份；职责要保患者生命，可接受少观察而先送走。未有稳定性格缺陷证据，不编造。',[81],'现场处置与转运指令，身份判断不在其任务内。')
entries['警察']=('C','暴力报警到场，依据危险和亲见伤损处理；普通口令拘捕，不受主角接缝报告指挥。具体程序有耗时、现场保留证物；没有一掌秒控。稳定缺陷未证。',[81],'清楚且重复的控制口令，不宣布超自然身份。')
entries['售票员']=('B',paragraph('B','售票员、收蛋者：')+'本卡只保售票窗口职责，不能免实名或替旅客改名。',[67,78],'窗口班次、票价与实名规则；未有稳定性格缺陷证据。')
entries['收蛋者']=('B',paragraph('B','售票员、收蛋者：')+'本卡只保订货营业与先付订金，不与售票员身份合并。',[66],'普通订货与先付要求；未有固定口头禅证据。')
for name,prefix in [('临江陈骁','临江'),('宁州陈骁','宁州')]:
 entries[name]=('B',paragraph('B','双陈骁：')+'\n\n本卡仅召回'+prefix+'本人所在岗位与损失；另一人的电话和工单不得当成本人已经知道。',[71,73],'本人工作与到场限制，不为调查放下班次。')
index={}
for name,(phase,analysis,chs,voice) in entries.items():
 refs=[{'path':prose(n).relative_to(BOOK).as_posix(),'sha256':sha(prose(n)),'chapter':n} for n in chs]
 rows=[]
 for eid,e in state['timeline'].items():
  chapter=e.get('first_recorded_chapter',e.get('reveal_chapter',0))
  # Prose supplements explicitly differ from canonical participant fields.
  if name in e.get('characters',[]) or chapter in chs:
   rows.append((chapter,eid,e,name not in e.get('characters',[])))
 rows.sort(key=lambda r:(r[0],r[1]))
 header=f'来源绑定的辅助视图，可用export_actor_memory.py重建；不修改唯一权威追踪。权威修订{revision}，截至99章，SHA256：{sha(authority)}。本卡只授予本人亲见、被告知或合理推断的信息；事件总述并不等于角色全知。\n\n'
 body='# '+name+'｜本批行动者卡\n\n'+header+'## 写前动机、知情与七关依据\n\n'+analysis+'\n\n## 声线与证据边界\n\n'+voice+'\n\n## 已修正文来源\n\n'+''.join(f'- {r["path"]}；SHA256：{r["sha256"]}\n' for r in refs)+'\n## 长期召回\n\n[个人时间线](../人物时间线/'+name+'.md)。上面的七关是本批行动许可，未来场景必须重评；未写出的私生活和未结未知不得擅补。分析原包：'+phase+'。\n'
 (cards/(name+'.md')).write_text(body,encoding='utf-8')
 timeline='# '+name+'｜个人时间线召回\n\n'+header
 for ch,eid,e,supp in rows:
  timeline+=f'## {eid}｜第{ch}章｜{e["story_time"]}\n\n'+e['objective_fact']+'\n\n读者当时所知：'+e['reader_knowledge']+'\n\n'
  if supp:timeline+='参与字段未单列该角色：仅作为上述已接纳正文的定点召回入口；不宣称权威参与者字段已有此人，也不从事件总述推其知情。\n\n'
 (timelines/(name+'.md')).write_text(timeline,encoding='utf-8')
 index[name]={'events':[r[1] for r in rows],'prose_sources':refs,'card_hash':sha(cards/(name+'.md')),'timeline_hash':sha(timelines/(name+'.md'))}
write(ROOT/'辅助人物记忆索引.json',{'state_revision':revision,'authority_hash':sha(authority),'gate_sources':{k:{'path':p.relative_to(BOOK).as_posix(),'sha256':sha(p)} for k,p in sources.items()},'actors':index})
print(json.dumps({'revision':revision,'cards':len(index),'timelines':len(index)},ensure_ascii=False))
