from pathlib import Path
import json, hashlib, os, subprocess, sys, re
BOOK=Path(__file__).resolve().parents[2]
WORK=Path(__file__).resolve().parent
SCRIPTS=BOOK.parent/'skills/story-long-write/scripts'
ENV={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'}
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def run(tool,*args):
    r=subprocess.run([sys.executable,str(SCRIPTS/tool),*map(str,args)],env=ENV,capture_output=True,text=True,encoding='utf-8')
    if r.returncode:raise RuntimeError(r.stdout+r.stderr)
    try:return json.loads(r.stdout)
    except json.JSONDecodeError:return {'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
before=read(WORK/'修订前追踪快照.json')
after=read(BOOK/'追踪/_tracking-state.json')
assert after['last_committed_chapter']==before['last_committed_chapter']==99
assert after['imported_through_chapter']==before['imported_through_chapter']==56
for field in ['context','characters','foreshadow']:
    assert before[field]==after[field],f'当前{field}发生意外变化'
basehash=read(WORK/'基线哈希.json')
locked={p:sha(BOOK/p)==h for p,h in basehash.items() if re.search('正文/第10[0-3]章',p)}
assert all(locked.values()) and len(locked)==4
manifest=BOOK/'追踪/修改影响/active.json'
run('revision_guard.py','plan','--project',BOOK,'--input',WORK/'修订计划.json','--output',manifest)
m=read(manifest)
pattern=re.compile('沈竹|怀表|南栏|十一天|两个月|半个月|周远|陈骁|陈屿|宁州|十七|17|零三|03|周衡|071|075|卷势')
reviews=[]
for rel in m['required_checks']:
    p=BOOK/rel
    content=p.read_text(encoding='utf-8-sig')
    rows=content.splitlines()
    hits=[{'line':i+1,'text':line} for i,line in enumerate(rows) if pattern.search(line)]
    reviews.append({'path':rel,'sha256':sha(p),'lines':len(rows),'field_hits':hits,
                    'scope':'本轮六组P0事实及其直接回指；源文件逐项读取并检索，不冒称整卷文学冷读'})
write(WORK/'最终依赖核对索引.json',reviews)
m['checked_files']=[r['path'] for r in reviews]
def source(n):return next((BOOK/'正文').glob(f'第{n:03d}章_*.md')).relative_to(BOOK).as_posix()
issues=[(1,11,'怀表最长走时十一天与两个月矛盾','统一取信前历次维修最长十一天，并收录K006'),
        (18,56,'17与03照片归属混用，旧照片被当成当前现场','归位老树和金属箱材料，旧存档只证拍摄当时，收录K008'),
        (6,58,'双周远问话借用双陈骁汽修工单和生活证据','改为取表与宁州公司会议的异地同时对照，陈屿工牌独立追问'),
        (55,65,'南栏055已发而065说未发','区分残余明显的发送、没处理过的回复和未给通过，收录K009'),
        (1,77,'沈竹失踪后仍成为高二送取表对象','委托改普通客人，底账及守钟人反应同步，收录K007'),
        (71,94,'正文直接引用071/075','改安平里复核与南岸撤场事件回指'),
        (94,95,'镜辞以卷势解释自己的行为','改为想放大照片又收手的可见动作，仍未见接缝')]
m['conflicts']=[{'source':source(a),'target':source(b),'severity':'S1' if b in [58,77] else 'S2',
                 'issue':issue,'resolution':resolution,'status':'resolved'} for a,b,issue,resolution in issues]
m['tracking_action']={'kind':'commit','state_revision_before':before['state_revision'],
                      'state_revision_after':after['state_revision'],
                      'reason':'七章独立历史修订事务；位置仍99、当前核心快照和全部伏笔状态原样保留；更新历史事实与旧章记录'}
write(manifest,m)
write(WORK/'独立收尾复核.json',{'mode':'solo/direct','status':'READY_TO_CLOSE',
                              'basis':'候选逐段diff回读、六组P0事实跨章对照、原话发送者核对；依赖索引限定本轮字段，不是全卷文学冷读',
                              'locked_chapter_hashes':locked,'current_context_unchanged':True,
                              'current_character_snapshots_unchanged':True,'foreshadow_current_values_unchanged':True,
                              'first_batch_only':True,'tracking_revision':after['state_revision']})
results={'revision_guard':run('revision_guard.py','check','--project',BOOK,'--input',manifest,'--stamp',BOOK/'追踪/修改影响/active.approved.json'),
         'tracking_check':run('tracking_commit.py','check','--project',BOOK),'sync':{}}
for n in [58,65,77,94,95]:
    results['sync'][str(n)]=run('chapter_candidate.py','sync','--project',BOOK,'--chapter',n,
       '--revision-manifest',manifest,'--revision-stamp',BOOK/'追踪/修改影响/active.approved.json',
       '--reason','用户授权按综合方案修复第一批P0；既有正文历史修订，章节位置和锁定接口保持', '--confirm','SYNC')
    print(f'{n:03d}: accepted receipt synchronized')
results['voice_profile']=run('voice_profile.py','update','--project',BOOK)
results['story_doctor']=run('story_doctor.py','--project',BOOK)
write(WORK/'最终验收.json',results)
print(json.dumps({'revision':after['state_revision'],'last_chapter':99,'impact_checks':len(reviews),
                  'revision_gate':results['revision_guard']['status'],'doctor':results['story_doctor']['status'],
                  'warnings':results['story_doctor'].get('warnings',[])},ensure_ascii=False))
