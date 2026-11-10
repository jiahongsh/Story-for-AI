"""本轮封版验收；不是以后所有修订都必须保持r232的通用门。"""
import hashlib
import importlib.util
import json
import re
from pathlib import Path

HERE=Path(__file__).resolve().parent
BOOK=HERE.parents[1]
baseline=json.loads((HERE/'修复前正文追踪指纹.json').read_text(encoding='utf-8'))
changed=[rel for rel,h in baseline.items() if not (BOOK/rel).exists() or hashlib.sha256((BOOK/rel).read_bytes()).hexdigest()!=h]
assert set(changed)=={'追踪/修改影响/active.approved.json','追踪/修改影响/active.json'},changed
spec=importlib.util.spec_from_file_location('memory',HERE/'build_memory.py')
memory=importlib.util.module_from_spec(spec)
spec.loader.exec_module(memory)
state=json.loads((BOOK/'追踪/_tracking-state.json').read_text(encoding='utf-8-sig'))
coverage={}
for name,rows in memory.ACTORS.items():
    listed={int(r['chapter']) for r in rows}
    needed=[e for e in state['timeline'].values() if name in e.get('characters',[])]
    assert all(e['reveal_chapter'] in listed for e in needed)
    coverage[name]={'nodes':len(rows),'official_participation_events':len(needed),'missing':0}
original=memory.sources
memory.sources=lambda:{**original(),'模拟换稿':'bad'}
try:
    memory.render()
except ValueError:
    pass
else:
    raise AssertionError('过期来源未阻断')
memory.sources=original
memory.render()
quotes_checked={}
for name,chapters in {'唐宁':[69,77],'老李':[84,86,87,88],'张岚':[84,85,86,87],'猫眼':[17,19,56]}.items():
    text=(BOOK/'设定/角色'/f'{name}.md').read_text(encoding='utf-8-sig')
    line=next(l for l in text.splitlines() if '真实' in l and '锚点' in l)
    quotes=re.findall('“([^”]+)”',line)
    prose='\n'.join(next((BOOK/'正文').glob(f'第{n:03d}章*.md')).read_text(encoding='utf-8-sig') for n in chapters)
    assert all(q in prose for q in quotes),(name,quotes)
    quotes_checked[name]=len(quotes)
    for target in re.findall(r'\]\(([^)]+)\)',text):
        if target.startswith('../../创作运行/'):
            assert ((BOOK/'设定/角色')/target).resolve().is_file(),target
result={'status':'pass','state_revision':state['state_revision'],'last_committed_chapter':state['last_committed_chapter'],
        'changed_baseline_files':changed,'prose_and_canon_unchanged':True,'participation_coverage':coverage,
        'exact_voice_quotes':quotes_checked,'stale_source_rejection':'pass','local_card_links':'pass','mode':'solo/direct'}
(HERE/'专项验收结果.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
