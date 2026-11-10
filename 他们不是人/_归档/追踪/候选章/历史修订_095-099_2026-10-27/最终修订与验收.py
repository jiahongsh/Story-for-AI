import copy
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('audit',ROOT/'审查工具.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
scripts=m.REPO/'skills/story-long-write/scripts'
FACTS={95:'094候选同夜收托盘、095夜间交资料、次晨装好客表并见周衡入市场；七天为已有观察而非再过七天。',96:'同一早晨自然观察结束，午后旧纸本入店；未见不认证，不追加试探。',97:'当夜坐实最早三年至少两处版本冲突；实施者未知，近五年材料先待核。',98:'次日有限访问与自愿展示，傍晚旧芯入盒隔层、管钳约翌日归还；镜辞不预知送表。',99:'再翌日午前初检、授权在动件之前；清灰校时与小齿轮六十以内，超额大件另问，留旧件，明日取。'}
STARTS={95:['镜辞把明早要装的表收进托盘','电话断了以后','次日清晨'],96:['修鞋摊老板把箱子挪开','上午过半','午后猫眼进店时'],97:['镜辞把两处不同的名字圈到一起','姜霁的电话在这时接进来','猫眼收住最早那段'],98:['“看摊三天','回到钟表行','傍晚徐师傅进门'],99:['周衡先把管钳放','“先清灰校时。”','这次接单用了十几分钟']}
RESULTS={95:['有限七天记录交接，区分亲见与转述，无依据的怀疑没有入档。','猫眼只交初步差异与出处；已有照片经转交只核位置，不凭照片判接缝。','次晨先做正常客修，周衡因市场熟人漏水事入场；没有主动揽他进店。'],96:['周衡做有限顺手维修、回应熟人及捡球；镜辞不为观察喊人，未见可靠接缝。','姜霁接受首次自然观察为空，不追加等待复看；不确定光斑不计入。','猫眼将八年纸本带入，早期过整仅是核验方向；店务物件与纸本分开。'],97:['核地址和字段并排除部分误读，至少两处旧版本差异成立，不证明当年全部未发生。','迁移批次账号审批正常；最早三年有版本级改写，实施者和具体事件仍未知。','最近五年分散关系材料露出但还需核；姜霁入档前段结论，安排关系核验。'],98:['三名市场关系人有限陈述或自愿出示；送医、看摊、借还与争吵部分核实，各自隐私边界保留。','同事许可相关电话外放且仍有怨气；互助、返工与赔付材料分来源核对，条目改为关系后果。','徐师傅交旧芯只证旧业务，管钳另待还；周衡路过看牌，明日送表仍未预定。'],99:['普通归还工具，客人自愿送走慢旧表并准初检，真实故障成立。','预算工期及换件范围由周衡确认，接触十余分钟仍未确认接缝；不追问履历延长接触。','姜霁接纳空结果，镜辞按授权拆出变形齿轮留袋继续修表；100次日接口不改。']}

def polish(n):
 f=ROOT/f'第{n:03d}章'; p=next(f.glob('第*.md')); runid=f'ch{n:03d}_final'
 m.run([sys.executable,str(scripts/'deslop_guard.py'),'init',str(p),'--project-root',str(ROOT),'--scope','bounded','--intensity','standard','--run-id',runid],f/'保真工作区初始化.json')
 stage=ROOT/'.story-deslop/runs'/runid
 ledger=json.loads((stage/'protection-ledger.json').read_text(encoding='utf-8'))
 ledger['manual'].update(entities=list(dict.fromkeys(a['name'] for a in json.loads((f/'最终修订写前行动审查.json').read_text(encoding='utf-8'))['actors'])),timeline_facts=[FACTS[n]],knowledge_boundaries=['没有照片超凡扫描；接缝未见不能认证，首次确认留给100；回填实施者、原人、势力等级未知。'],clues=['版本回填与近五年关系后果并立，不把其中一条吞掉；工具、旧芯、维修表各有用途。'],voice_markers=['周衡问预算并嫌帮工无限；姜霁问范围；猫眼能纠正镜辞；普通当事人可拒绝、保留怨气；守钟人管实际店务。'],intentional_roughness=['保留对话中的省略与生意口气、必要记录词；不按统计百分比填对话或修成人人讲道理。'])
 m.save(stage/'protection-ledger.json',ledger)
 q=stage/'candidate.md'; s=q.read_text(encoding='utf-8')
 if n==95:
  s=s.replace('镜辞刚给客人的表扣好后盖，手机便接连震了两下。','镜辞把明早要装的表收进托盘，手机便接连震了两下。')
  s=s.replace('电话断了以后，镜辞把修好的客表装袋。袋口还没封，猫眼就从半落的卷帘门下弯腰进来，怀里夹着纸袋。她看了眼台面，等他把客表收进格子，才将几页纸放下。','电话断了以后，镜辞把两页记录移到托盘外侧。刚腾出地方，猫眼就从半落的卷帘门下弯腰进来，怀里夹着纸袋。她看了眼台面，等他把托盘推稳，才将几页纸放下。')
  old='镜辞回了收到。守钟人出来催他收茶，见他又把工具盒挪到纸上，伸手拎开了。\n\n“客人的袋子封好。少个零件，纸替你赔？”\n\n他赶紧封袋，在袋口写上取件时点，放进柜台格子。守钟人将茶端走，没再问周衡。\n\n次日清晨，镜辞先把那只表取出来，核过走时才摆上台面。手机在柜台下面震了一声，还是姜霁：保持联络。'
  new='镜辞回了收到，将两页记录收在一侧，给明早的托盘盖好防尘罩。\n\n次日清晨，镜辞把那只表取出来。守钟人出来摆工具，见他又把记录纸挪到零件旁，伸手拿开了。\n\n“客人的零件收好。少个小东西，纸替你赔？”\n\n镜辞将纸压到柜台下面，先装好那只表，核过走时才摆上台面。手机震了一声，还是姜霁：保持联络。'
  assert old in s; s=s.replace(old,new)
 if n==97:
  old='他本来想只留一袋，桌面也宽敞些，最后还是把台灯挪到了中间。'
  assert old in s; s=s.replace(old,'他将两只袋子并排放稳，把台灯挪到了中间。')
 if n==99:
  old='早晨那一页没有被他改动。'; assert old in s
  s=s.replace(old,'先前那页自然观察记录没有被他改动。')
 q.write_text(s,encoding='utf-8')
 m.run([sys.executable,str(scripts/'deslop_guard.py'),'check',str(stage)],f/'保真检查.json')
 m.run([sys.executable,str(scripts/'deslop_guard.py'),'apply',str(stage),'--confirm','APPLY'],f/'最终润色应用.json')
 m.checks(n)

def verify(n):
 f=ROOT/f'第{n:03d}章'; p=next(f.glob('第*.md')); txt=p.read_text(encoding='utf-8'); lines=txt.splitlines()
 # 应用后原目标已改变，原run不能再作覆盖许可。最终复验证据以
 # 不变的初稿source快照对照最终正文，避免把预期的stale-source忽略为通过。
 initial=ROOT/'.story-deslop/runs'/f'ch{n:03d}_final'
 evidence=ROOT/'.story-deslop/runs'/f'ch{n:03d}_evidence'
 if not evidence.exists():
  m.run([sys.executable,str(scripts/'deslop_guard.py'),'init',str(initial/'source.md'),'--project-root',str(ROOT),'--scope','bounded','--intensity','standard','--run-id',f'ch{n:03d}_evidence'],f/'保真复验证据初始化.json')
  led=json.loads((evidence/'protection-ledger.json').read_text(encoding='utf-8'))
  led['manual']=json.loads((initial/'protection-ledger.json').read_text(encoding='utf-8'))['manual']
  m.save(evidence/'protection-ledger.json',led)
  (evidence/'candidate.md').write_text(txt,encoding='utf-8')
 m.run([sys.executable,str(scripts/'deslop_guard.py'),'check',str(evidence)],f/'保真检查.json')
 m.run(['node',str(scripts/'dialogue_drift_gate.js'),'--current',str(p),'--history-dir',str(m.BOOK/'正文'),'--json'],f/'对白归属检查.json')
 m.run([sys.executable,str(scripts/'chapter_shape_gate.py'),'--project',str(m.BOOK),'--candidate',str(p),'--chapter',str(n),'--window','6'],f/'近章结构证据.json')
 m.run(['node',str(scripts/'check-typos.js'),str(p)],f/'错字检查.log')
 pre=f/'交付复验行动包.json'; d=json.loads(pre.read_text(encoding='utf-8'))
 starts=[next(i for i,l in enumerate(lines) if x in l) for x in STARTS[n]]; res=[]
 for i,scene in enumerate(d['scenes']):
  start=starts[i]; end=starts[i+1]-1 if i+1<len(starts) else len(lines)-1
  res.append(dict(scene_id=scene['id'],actual_result=RESULTS[n][i],action_ids=[a['id'] for a in scene['actions']],evidence=[dict(start_line=start+1,end_line=end+1,quote='\n'.join(lines[start:end+1]))],world_followups=[RESULTS[n][i]+' 本候选结果不提交正史；各主体的未知与未结事项继续保留。']))
 d['postwrite']=dict(prewrite_packet=dict(path=str(pre.relative_to(m.BOOK)).replace('\\','/'),sha256=m.sha(pre)),candidate=dict(path=str(p.relative_to(m.BOOK)).replace('\\','/'),sha256=m.sha(p)),scene_results=res,foreshadow_deltas=[dict(id='NO_CHANGE',operation='none',description='只展开既有调查和客修事实，不新增回收；099次日取表承诺仍交锁定100首次确认接缝，作者起源及实施者仍未揭示。',evidence=[res[-1]['evidence'][0]])],manual_review=dict(status='passed',reviewer='Codex同一Agent分阶段自审',method='四门和对白、结构、错字检查后，顺读094候选至099候选并对照100接口，再对照冻结场景和来源；没有独立代理审查。',basis=FACTS[n]+' 对照整批保留来源边界、普通人拒绝和维修先授权；不把候选结果写入正史。',checks={k:'passed' for k in ['actual_coverage','causality','voice','knowledge_bounds','consequences','foreshadow']}))
 post=f/'交付正文复验包.json'; m.save(post,d)
 m.run([sys.executable,str(m.GATE),'check','--project',str(m.BOOK),'--packet',str(post.relative_to(m.BOOK)),'--phase','postwrite','--tracking-tool',str(m.TRACK)],f/'交付正文检查.json')
 old=next((m.BOOK/'正文').glob(f'第{n:03d}章_*.md')); count=lambda s:len(re.findall(r'[\u4e00-\u9fff]',s.split('\n',1)[-1]))
 return dict(chapter=n,source=str(old.relative_to(m.BOOK)),source_sha256=m.sha(old),candidate=str(p.relative_to(m.BOOK)),candidate_sha256=m.sha(p),source_hanzi=count(old.read_text(encoding='utf-8')),candidate_hanzi=count(txt))

if __name__=='__main__':
 if sys.argv[1]=='polish':
  for n in range(int(sys.argv[2]) if len(sys.argv)>2 else 95,100): polish(n)
 elif sys.argv[1]=='verify':
  stats=[verify(n) for n in range(95,100)]
  for n in range(95,100):
   d=json.loads((ROOT/f'第{n:03d}章/交付复验行动包.json').read_text(encoding='utf-8'))
   for src in d['sources']: assert m.sha(m.BOOK/src['path'])==src['sha256'],src['path']
   assert m.sha(m.BOOK/'追踪/_tracking-state.json')==d['binding']['tracking']['sha256']
  m.save(ROOT/'候选统计与来源.json',stats)
  print(json.dumps(stats,ensure_ascii=False,indent=2))
