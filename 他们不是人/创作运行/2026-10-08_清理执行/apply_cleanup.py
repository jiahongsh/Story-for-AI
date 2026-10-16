"""应用已确认删减；每章先校验，再改正文/细纲，再串行revision提交。
追踪仅用正式工具写，不手改生成Markdown。
"""
from pathlib import Path
import copy,hashlib,json,re,subprocess,sys

HERE=Path(__file__).resolve().parent
BOOK=HERE.parents[1]
REPO=BOOK.parent
BACKUP=BOOK/'备份/2026-10-08_清理C01-R10'
ITEMS=json.loads((HERE/'剪裁明细.json').read_text(encoding='utf-8'))
BASE=json.loads((HERE/'修复前权威.json').read_text(encoding='utf-8-sig'))
TRACK=REPO/'skills/story-long-write/scripts/tracking_commit.py'

def run(args):
    p=subprocess.run(args,capture_output=True,text=True,encoding='utf-8')
    if p.returncode:raise RuntimeError(p.stdout+'\n'+p.stderr)
    return p.stdout.strip()

def records(n):
    lines=(BACKUP/f'追踪/逐章记录/第{n:03d}章.md').read_text(encoding='utf-8-sig').splitlines()
    sections={};key='header'
    for l in lines:
        if l.startswith('## '):key=l[3:]
        else:sections.setdefault(key,[]).append(l)
    result=next(l[5:] for l in lines if l.startswith('- 结果：'))
    promises=next(l[8:] for l in lines if l.startswith('- 下一章承诺：'))
    changes=[]
    for l in sections['角色变化']:
        if l.startswith('- ') and l!='- 无':
            name,_,change=l[2:].split('｜',2);changes.append({'name':name,'change':change})
    # 与被删对白/指代有关的历史摘要随正文纠正。
    fixes={61:{'守钟人':'问孙立是否离店，听镜辞确认表准后回后间，人未受伤'},
           63:{'姜霁':'拦住他替空景下结论，按住抽屉，公司夹不抄旧验证'},
           71:{'姜霁':'纸和屏分开拍。没把没看见写进公共材料'},
           73:{'姜霁':'核前次副本与持续正常页，拍新公示给猫眼存档，不提供身份结论'},
           75:{'姜霁':'记下人没给结论，柜子仍撤了；侯强46与孙立退费分存'}}
    for c in changes:
        c['change']=fixes.get(n,{}).get(c['name'],c['change'])
    def refs(section,state_key):
        ids=[l[2:].split('｜',1)[0] for l in sections.get(section,[]) if l.startswith('- ') and l!='- 无']
        return [dict(action='upsert',**{k:v for k,v in BASE[state_key][eid].items() if k not in {'updated_chapter','first_recorded_chapter'}}) for eid in ids]
    constraints=[l[2:] for l in sections['连贯性约束'] if l.startswith('- ') and l!='- 无']
    return {'result':result,'character_changes':changes,'foreshadow_changes':refs('伏笔变化','foreshadow'),
            'timeline_events':refs('时间与揭示','timeline'),'fact_changes':refs('长期事实变化','facts'),
            'constraints':constraints,'next_chapter_commitments':[] if promises=='无' else promises.split('；')}

log=[]
for item in ITEMS:
    n=item['chapter']
    state=json.loads((BOOK/'追踪/_tracking-state.json').read_text(encoding='utf-8-sig'))
    run([sys.executable,str(TRACK),'check','--project',str(BOOK)])
    target=BOOK/item['file'];candidate=HERE/'候选'/target.name
    assert hashlib.sha256(target.read_bytes()).hexdigest()==item['before_sha256'],f'来源换稿：{n}'
    assert hashlib.sha256(candidate.read_bytes()).hexdigest()==item['after_sha256']
    delta=records(n)
    core={c['name']:copy.deepcopy(state['characters'][c['name']]) for c in delta['character_changes'] if c['name'] in state['characters']}
    tx={'schema_version':1,'mode':'revision','chapter':n,'chapter_title':target.name.split('_',1)[1][:-3],
        'expected_state_revision':state['state_revision'],'delta':delta,
        'context':{k:copy.deepcopy(state['context'][k]) for k in ['position','long_term_constraints','active_character_names','continuity_risks']},
        'character_snapshots':core}
    t=HERE/f'事务/第{n:03d}章.json';t.parent.mkdir(exist_ok=True);t.write_text(json.dumps(tx,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    target.write_bytes(candidate.read_bytes())
    outline=BOOK/f'大纲/细纲_第{n:03d}章.md'
    old=outline.read_text(encoding='utf-8-sig')
    # 细纲追随正文；不是新增故事设计，也不把七关写入正文。
    note='\n\n## 2026-10-08 清理同步\n\n按作者确认的C01—R10删减重复支段和解释，保持本章事实、时序、金额、角色选择及后续承诺；以本轮正文和串行修订记录为准，不补情节。\n'
    if n==61:note+='守钟人本章只问孙立是否离店，听表准后回后间；旧的核问入账及坏账对白已删除。\n'
    if n==63:note+='撤榜后无故障路人支段及菜筐/排水沟回声已删除，不再引用；蓝拖鞋回访和本人拒旧验证保留。\n'
    if n==73:note+='只核前次同步副本与持续正常页，不再重复拍纸屏或打印核对；新公示、扣薪、拒签、药暂存仍保留。\n'
    outline.write_text(old.rstrip()+note,encoding='utf-8')
    result=run([sys.executable,str(TRACK),'commit','--project',str(BOOK),'--input',str(t)])
    check=run([sys.executable,str(TRACK),'check','--project',str(BOOK)])
    log.append({'chapter':n,'before_revision':state['state_revision'],'commit':result,'check':check,'removed_chars':item['removed_chars']})
    (HERE/'串行提交记录.json').write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'{n:03d}: committed; {check}',flush=True)
print('cleanup serial commits complete')
