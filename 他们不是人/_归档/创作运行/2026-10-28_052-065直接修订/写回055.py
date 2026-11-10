import hashlib
import json
from pathlib import Path

project = Path(__file__).resolve().parents[2]
work = Path(__file__).parent
run = project / '追踪/候选章/第055章/直接修订_20261101'
packet = json.loads((run / '世界引擎/写前行动审查.json').read_text(encoding='utf-8'))
for item in packet['sources']:
    assert hashlib.sha256((project / item['path']).read_bytes()).hexdigest() == item['sha256']
state = json.loads((project / '追踪/_tracking-state.json').read_text(encoding='utf-8'))
assert state['state_revision'] == 253
manifest_path = project / '追踪/修改影响/active.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
assert manifest['change_id'] == 'revision-055-20261101'
for relative in manifest['changed_files']:
    original = project / relative
    backup = project / '备份/2026-11-01_055修订' / relative
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_bytes(original.read_bytes())
manifest['checked_files'] = list(manifest['required_checks'])
manifest['conflicts'] = [
    {'source': '追踪/长期事实.md', 'target': '正文/第055章_没处理过.md', 'severity': 'S2', 'issue': '匿名原话与公开页空白被扩大为现场不派人和完整目标图。', 'resolution': '只保留匿名声称、页面范围和私人假设；当前现场及全图未知。', 'status': 'resolved'},
    {'source': '正文/第055章_没处理过.md', 'target': '大纲/细纲_第055章.md', 'severity': 'S2', 'issue': '细纲把试探成功和现场不变写成事实。', 'resolution': '改为对比来源和未知边界，维护目的未证。', 'status': 'resolved'},
    {'source': '正文/第056章_清理轨迹.md', 'target': '大纲/细纲_第056章.md', 'severity': 'S2', 'issue': '细纲上部仍说南栏保持不变，与底部冷读口径矛盾。', 'resolution': '统一为匿名声称和公开页未见新行，现场及因果未知。', 'status': 'resolved'}
]
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(project / '正文/第055章_没处理过.md').write_bytes((run / 'candidate.md').read_bytes())
p = project / '大纲/细纲_第055章.md'
text = p.read_text(encoding='utf-8').replace('证明维护链并不盲信镜辞；镜辞只能影响已处理目标的验收，不能凭空把不存在的问题骗进施工表。', '比较假异常短信、匿名回应和公开页面；不能据此确认施工是否受反馈驱动，也不能认定对方的完整目标图。').replace('一夜没有施工、工单、设备变化，陌生号码只回复：', '截至所见公开页南栏未见新增行，现场未复核；陌生号码只回复：').replace('镜辞确认对方拥有独立目标地图，自己不是目标探测器，而是难骗的外部验收样本之一。', '镜辞只记对方可能有自己的安排；匿名话语不证明完整目标图，也不能给自己定为验收样本。')
text += '\n## 本轮五问核对\n\n1. 同脸与既有取表姓名、公开合影身份并列，形成身份线索，不能直接判替换。\n2. 借名取表或履历变动仍是可能的日常解释；合影不证明连续主体。\n3. 猫眼交来的公开照片为共同新知，不冒充读者先知。\n4. 打印费六元、进纸运费九元及定时盯页服务终止已发生，各有承担者。\n5. 分存照片与公开版本，代价是渠道收缩和等待；匿名回复不替代现场核查。\n'
p.write_text(text, encoding='utf-8')
p = project / '大纲/细纲_第056章.md'
text = p.read_text(encoding='utf-8').replace('确认调查本身会污染现场', '保留调查可能影响现场的假设').replace('03南栏作为未处理对照点保持不变。', '03南栏只有匿名声称未处理和截至观察时公开页未见新行；现场状态及对方目标图未知。')
p.write_text(text, encoding='utf-8')
transaction = json.loads((project / '创作运行/2026-10-06_第三批反调查闭环/第055章/修订事务.json').read_text(encoding='utf-8'))
transaction['expected_state_revision'] = state['state_revision']
transaction['context'] = {k: state['context'][k] for k in ['position', 'long_term_constraints', 'active_character_names', 'continuity_risks']}
transaction['character_snapshots'] = {name: state['characters'][name] for name in ['镜辞', '姜霁']}
d = transaction['delta']
d['result'] = '匿名回复声称南栏没处理过；公开页未见新行，现场及目标图未知。公开合影对脸，打印店完成旧单后拒绝定时拉页，今后只打印传来文件。'
d['character_changes'][0]['change'] = '只记南栏匿名说法和页面范围；接受打印店停止定时盯页，对陈屿同脸不并两家公司'
f = state['foreshadow']['F003']
d['foreshadow_changes'] = [dict(action='upsert', **{k: f[k] for k in ['id', 'importance', 'planned_resolution_chapter', 'planted_chapter', 'status', 'summary'] if k in f})]
e = {k: v for k, v in state['timeline']['E055'].items() if k not in ['first_recorded_chapter', 'updated_chapter']}
e['action'] = 'upsert'
e['objective_fact'] = e['objective_fact'].replace('南栏假异常没有引来施工，陌生号码回复没处理过。', '陌生号码声称南栏没处理过；截至所见公开页未见新行，现场未复核。')
e['reader_knowledge'] = '匿名回复只证明对方说过，公开页只证明截至其时间未见新行；现场及完整目标图未知。名字早就有，新的只是脸与公开合影对上。'
d['timeline_events'] = [e]
d['constraints'] = ['打印店只停定时盯页，不是拒绝065付费印文件；不得从空白页及匿名回复推定现场是否受反馈驱动。', 'D4只保留旧司机接缝基线，未复看；两家公司分存，未知主体连续性。']
(work / '055修订事务.json').write_text(json.dumps(transaction, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('055 formal and 055-056 outline mappings written; transaction prepared')
