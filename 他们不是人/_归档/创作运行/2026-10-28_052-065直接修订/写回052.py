import hashlib
import json
from pathlib import Path

project = Path(__file__).resolve().parents[2]
root = Path(__file__).parent
manifest_path = project / '追踪/修改影响/active.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
assert manifest['change_id'] == 'revision-052-20261028'
state = json.loads((project / '追踪/_tracking-state.json').read_text(encoding='utf-8'))
assert state['state_revision'] == 250
run = project / '追踪/候选章/第052章/直接修订_20261028_修订二'
before = json.loads((run / '世界引擎/写前行动审查.json').read_text(encoding='utf-8'))
formal = project / '正文/第052章_一条时间线.md'
source = next(x for x in before['sources'] if x['path'] == '正文/第052章_一条时间线.md')
assert hashlib.sha256(formal.read_bytes()).hexdigest() == source['sha256']
manifest['checked_files'] = list(manifest['required_checks'])
manifest['conflicts'] = [
    {'source': '正文/第051章_真的回来了.md', 'target': '正文/第052章_一条时间线.md', 'severity': 'S2', 'issue': '052早晨检票陈述与前日宁州在厂、晚间返临不符，许棠代送药日序错误。', 'resolution': '仅保留宁州陈骁本人位置陈述，去掉检票证据；许棠药改为前晚代送。', 'status': 'resolved'},
    {'source': '正文/第052章_一条时间线.md', 'target': '大纲/细纲_第052章.md', 'severity': 'S2', 'issue': '细纲将短信与物业字段关联写得高于正文证据。', 'resolution': '限定为未核假设，区分两笔药品配送，认知等级按制度权限证据标L4。', 'status': 'resolved'}
]
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(root / '052实际核读范围.txt').write_text('限定事实清单全部核读。前次代理完整核读大纲总卷纲及正文031—053、070—073；主线程补读清单内全部18份细纲、角色生态约束、上下文与事实记录。051“我还在车上”是接到退假时本人自述，未声称六点四十一已乘车，本次不扩改051。\n', encoding='utf-8')
formal.write_bytes((run / 'candidate.md').read_bytes())
(project / '大纲/细纲_第052章.md').write_bytes((project / '追踪/候选章/第052章/直接修订_20261028/细纲候选.md').read_bytes())
print('052 formal and outline written')
