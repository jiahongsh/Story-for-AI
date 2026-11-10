"""清理后来源核对与人物辅助视图重建；不写正史。"""
from pathlib import Path
import hashlib,json,re,subprocess,sys,os

HERE=Path(__file__).resolve().parent
BOOK=HERE.parents[1]
REPO=BOOK.parent
OLD=BOOK/'创作运行/2026-10-07_冷读问题逐项修复/人物记忆_r232'
NEW=HERE/'人物记忆_r249'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return p.read_text(encoding='utf-8-sig')
def write(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s,encoding='utf-8')
def run(args):
    p=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',env={**os.environ,'PYTHONIOENCODING':'utf-8'})
    if p.returncode:raise RuntimeError(p.stdout+'\n'+p.stderr)
    return p.stdout.strip()
state=json.loads(read(BOOK/'追踪/_tracking-state.json'))
base=json.loads(read(HERE/'修复前权威.json'))
assert (state['state_revision'],state['last_committed_chapter'])==(249,99)
def semantic(v):
    if isinstance(v,dict):return {k:semantic(x) for k,x in v.items() if k not in {'updated_chapter','first_recorded_chapter'}}
    if isinstance(v,list):return [semantic(x) for x in v]
    return v
for k in ['characters','facts','foreshadow','timeline']:
    assert semantic(state[k])==semantic(base[k]),f'截至099的语义漂移：{k}'
items=json.loads(read(HERE/'剪裁明细.json'))
changed={i['file'] for i in items}
fingerprints=json.loads(read(HERE/'修复前来源指纹.json'))
unchanged=[]
for rel,h in fingerprints.items():
    if rel.startswith('正文/') and rel not in changed:
        assert sha(BOOK/rel)==h,f'未授权正文变化：{rel}'
        unchanged.append(rel)
for i in items:
    assert sha(BOOK/i['file'])==i['after_sha256']
    for d in i['details']:
        it=iter(d['before'])
        assert all(any(c==x for x in it) for c in d['after']),f'不是纯剪裁：{i["chapter"]}'
# 旧七人包判断来自042/050/051/052原文及未变语义的事件；不重授已删动作。
script=read(OLD/'generate_actor_views.py').replace('232','249')
write(NEW/'generate_actor_views.py',script)
logs={'seven_actors':run([sys.executable,str(NEW/'generate_actor_views.py')])}
# 三张补充卡逐条核读后保留独立目标/声线/未知，删除旧轮许可与变化说明。
for name in ['裴亮','陌生男人','周衡']:
    src=OLD/f'本轮行动者/{name}.md'
    content=read(src).split('## 本輪变化')[0]
    content=content.replace('追踪r232，截至099。角色驱动取自已接纳原文；本轮七关许可见../../写前七关.md，不把旧章审读伪称当时审批。',
        '追踪r249，截至099。独立目标、声线和知情边界经清理后正文复验；本卡不是旧章写前七关审批，也不承接旧轮的修改许可。')
    sources=json.loads(read(OLD/f'本轮行动者/{name}.来源.json'))
    for row in sources:
        p=BOOK/row['path'];oldhash=row['sha256'];row['sha256']=sha(p)
        content=content.replace(oldhash,row['sha256'])
    content+='## 本轮来源复核\n\n本轮仅删减重复支段、解释和收尾。裴亮本人不知道停供及接缝；陌生男人身份与组织仍未证；周衡099的六十元以内授权及未经同意不换大件保留。作者调查结果不授予本人。\n'
    write(NEW/f'本轮行动者/{name}.md',content)
    write(NEW/f'本轮行动者/{name}.来源.json',json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
# 两张静态卡只换当前阅读入口；独立欲望、声线和未来规划均不改。
for name in ['猫眼','唐宁']:
    p=BOOK/f'设定/角色/{name}.md'
    write(p,read(p).replace('r232作者','r249作者').replace('人物记忆_r232_2026-10-08','人物记忆_r249_清理后'))
personal=read(BOOK/'创作运行/2026-10-08_角色记忆逐项修复/build_memory.py')
personal=personal.replace('232','249').replace('人物记忆_r249_2026-10-08','人物记忆_r249_清理后')
personal=personal.replace('2026-10-08_角色记忆逐项修复','2026-10-08_清理执行').replace('build_memory.py','build_personal_memory.py')
write(HERE/'build_personal_memory.py',personal)
logs['personal_bind']=run([sys.executable,str(HERE/'build_personal_memory.py'),'build' if (HERE/'来源绑定.json').exists() else 'bind'])
logs['personal_check']=run([sys.executable,str(HERE/'build_personal_memory.py'),'check'])
idx=BOOK/'创作运行/派生视图/人物记忆索引.md'
index=read(idx).replace('r232','r249').replace('人物记忆_r249_2026-10-08','人物记忆_r249_清理后')
index=index.replace('../2026-10-07_冷读问题逐项修复/人物记忆_r249','../2026-10-08_清理执行/人物记忆_r249')
index=index.replace('既有r249七人包说明','清理后r249七人包说明')
write(idx,index)
logs['world_export']=run([sys.executable,str(REPO/'skills/story-world-engine/scripts/world_gate.py'),'export','--project',str(BOOK),'--start','1','--end','99'])
logs['volume_export']=run([sys.executable,str(REPO/'skills/story-world-engine/scripts/world_gate.py'),'export','--project',str(BOOK),'--start','1','--end','99','--output','创作运行/卷末记录/第一卷_001-099_r249_清理后'])
logs['source_check']={'state_revision':249,'semantic_keys_unchanged':['characters','facts','foreshadow','timeline'],'unchanged_prose_count':len(unchanged),'changed_prose_count':len(items),'removed_chars':sum(i['removed_chars'] for i in items),'locked_100_103':'unchanged'}
write(HERE/'来源与记忆验收.json',json.dumps(logs,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(logs['source_check'],ensure_ascii=False))
