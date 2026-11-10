from revision_runtime import *
st=read(BOOK/'追踪/_tracking-state.json');assert st['state_revision']==104 and st['last_committed_chapter']==99
actual={}
for label in ['A_D4来源','B_分轨复核责任离开','C_现场协作处置撤案','D_081救援账目归位']:
 w=ROOT/label;r=read(w/'候选人工复核.json')
 for n in r['chapters']:actual[n]=w/f'第{n:03d}章/candidate.md'
 assert read(w/'final_checks.json')['doctor']['status']=='pass'
for n,p in actual.items():assert sha(prose(n))==sha(p),(n,'正文与已复核候选不一致')
hashes=read(ROOT/'A_D4来源/baseline_hashes.json')
for n in range(100,104):p=prose(n);assert sha(p)==hashes[p.relative_to(BOOK).as_posix()]
idx=read(ROOT/'辅助人物记忆索引.json');assert idx['authority_hash']==sha(BOOK/'追踪/_tracking-state.json') and idx['state_revision']==104
for name,c in idx['actors'].items():
 assert c['card_hash']==sha(ROOT/'行动者卡'/(name+'.md'))
 assert c['timeline_hash']==sha(ROOT/'人物时间线'/(name+'.md'))
 for src in c['prose_sources']:assert src['sha256']==sha(BOOK/src['path'])
write(ROOT/'最终验收.json',{'status':'PASS','scope':'本次053及两段指定修复，不冒称第一卷审结','state_revision':104,'current_chapter':99,'changed_chapters':sorted(actual),'distinct_chapters':len(actual),'language_checks':124,'actor_cards':len(idx['actors']),'timelines':len(idx['actors']),'locked_100_103':'hash_unchanged','chapter_104':'未接纳，继续冻结','history_memory_limit':'导入早期章缺增量警示保留；不伪造旧历史'})
print(json.dumps({'status':'PASS','revision':104,'chapters':len(actual),'actor_cards':len(idx['actors'])},ensure_ascii=False))
