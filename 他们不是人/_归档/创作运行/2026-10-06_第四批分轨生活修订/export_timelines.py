"""Rebuild this batch's auxiliary actor timelines from canonical events, never write canon."""
from pathlib import Path
import json,hashlib
BOOK=Path(__file__).resolve().parents[2];WORK=Path(__file__).resolve().parent
authority=BOOK/'追踪/_tracking-state.json';state=json.loads(authority.read_text(encoding='utf-8-sig'))
source_hash=hashlib.sha256(authority.read_bytes()).hexdigest()
target=WORK/'人物时间线';target.mkdir(exist_ok=True)
index={}
extra_sources={}
source77=next((BOOK/'正文').glob('第077章_*.md'))
text77=source77.read_text(encoding='utf-8-sig')
assert '唐宁九点到。' in text77 and '我讲的是我陪过的那次。' in text77
# Legacy E077 omits her from participants; cite the accepted prose explicitly rather
# than silently rewriting the canonical event or claiming this was in its actor field.
extra_sources['唐宁']={'E077':{'path':source77.relative_to(BOOK).as_posix(),
    'sha256':hashlib.sha256(source77.read_bytes()).hexdigest(),
    'basis':'已接纳正文077唐宁九点到、限定说高二亲历；原权威E077的参与者字段未列唐宁，此处为有原文证据的辅助召回'}}
for card in (WORK/'行动者卡').glob('*.md'):
    name=card.stem;rows=[]
    for key,event in state['timeline'].items():
        if name in event.get('characters',[]):
            rows.append((event.get('first_recorded_chapter',event.get('reveal_chapter',0)),key,event))
        elif key in extra_sources.get(name,{}):
            rows.append((event.get('first_recorded_chapter',event.get('reveal_chapter',0)),key,event))
    rows.sort(key=lambda row:(row[0],row[1]))
    text=f'# {name}｜作者视图个人时间线\n\n辅助派生，不是第二正史；可用本目录export_timelines.py重建。\n\n来源：追踪/_tracking-state.json；修订{state["state_revision"]}；SHA256：{source_hash}；截至第{state["last_committed_chapter"]}章。事件参与只说明参与该事件，不代表知道事件中的全部信息。\n\n'
    for chapter,key,e in rows:
        text+=f'## {key}｜第{chapter}章｜{e["story_time"]}\n\n{e["objective_fact"]}\n\n读者所知：{e["reader_knowledge"]}\n\n'
        if key in extra_sources.get(name,{}):
            src=extra_sources[name][key]
            text+=f'参与来源补充：{src["basis"]}。来源：{src["path"]}；SHA256：{src["sha256"]}。不修改权威参与者字段。\n\n'
    if not rows:text+='待核：权威中尚无独立参与者事件；召回该角色卡中的正文锚点，不从现状编造历史。\n'
    path=target/(name+'.md');path.write_text(text,encoding='utf-8')
    index[name]={'path':path.relative_to(BOOK).as_posix(),'events':[x[1] for x in rows],'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'accepted_prose_supplement':extra_sources.get(name,{})}
    content=card.read_text(encoding='utf-8')
    marker='\n## 本批完成后的个人时间线入口\n'
    if marker in content:content=content.split(marker)[0]
    card.write_text(content.rstrip()+marker+'\n[个人时间线](../人物时间线/'+name+'.md)；修订'+str(state['state_revision'])+'。卡片上部保留写前修订68的分析，续写时须重新恢复并校验来源，不直接套用旧许可。\n',encoding='utf-8')
(WORK/'辅助时间线索引.json').write_text(json.dumps({'state_revision':state['state_revision'],'authority_hash':source_hash,'actors':index},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'revision':state['state_revision'],'timelines':len(index),'events':{k:len(v['events']) for k,v in index.items()}},ensure_ascii=False))
