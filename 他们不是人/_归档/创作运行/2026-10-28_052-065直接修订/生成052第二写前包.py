import json
from pathlib import Path

project = Path(__file__).resolve().parents[2]
old = project / '追踪/候选章/第052章/直接修订_20261028/世界引擎/写前行动审查.json'
new = project / '追踪/候选章/第052章/直接修订_20261028_修订二/世界引擎/写前行动审查.json'
previous = json.loads(old.read_text(encoding='utf-8'))
packet = json.loads(new.read_text(encoding='utf-8'))
for field in ['actors', 'scenes', 'coverage', 'manual_review']:
    packet[field] = previous[field]

plan_lines = (project / packet['sources'][0]['path']).read_text(encoding='utf-8').splitlines()
for actor in packet['actors']:
    for group in ['voice_refs', 'timeline_refs']:
        ref = actor[group][0]
        ref['quote'] = plan_lines[ref['start_line'] - 1]

source_lines = (project / packet['sources'][1]['path']).read_text(encoding='utf-8').splitlines()
for scene in packet['scenes']:
    for action in scene['actions']:
        ref = action['knowledge_refs'][0]
        source_line = {'姜霁': 97, '宁州陈骁': 79, '杜经理': 45}[action['actor_id']]
        ref.update({'source_id': 'SRC2', 'start_line': source_line, 'end_line': source_line, 'quote': source_lines[source_line - 1]})
        if action['id'] == 'A1':
            action['gates']['knows'] = '前夜见过门禁和两地材料，收到电话时尚未收到物业新字段'
            ref['boundary'] = '该证据只证明前夜门禁和并账材料，不能提前知道本章稍后的物业新字段。'
            ref['acquisition'] = '姜霁前夜在活动室查看并保存门禁页面及两地材料。'
        elif action['id'] == 'A3':
            action['gates']['knows'] = '前夜见过门禁和并账材料，刚接到杜经理发来的页面，不知道字段来源'
            ref['boundary'] = '前夜材料只证明已见过门禁记录；新字段通过本场刚收到的页面获知，不证明上游来源。'
            ref['acquisition'] = '姜霁前夜在活动室查看并保存门禁材料，本场先收到杜经理发来的页面。'
        elif action['id'] == 'A2':
            ref['boundary'] = '该记录只支持本人遭遇退假和曾在回程车上，不证明六点四十一的票据或具体位置。'
            ref['acquisition'] = '本人亲历申请退假与回程，在前夜活动室作出陈述。'
        else:
            ref['boundary'] = '前夜物业现场出现许棠的药；代送还须结合051稍后的邻居取药，不能由此认证身份。'
            ref['acquisition'] = '杜经理本人当晚在物业柜台参与处理拦截和邻居代送。'
packet['manual_review']['basis'] = '宁州陈骁仅陈述本人位置；姜霁先接电话，后来才收到物业字段；杜经理按前夜事件交接。'
new.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
