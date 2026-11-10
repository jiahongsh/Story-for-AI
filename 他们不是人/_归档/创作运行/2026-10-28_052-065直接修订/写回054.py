import hashlib
import json
from pathlib import Path

project = Path(__file__).resolve().parents[2]
work = Path(__file__).parent
run = project / '追踪/候选章/第054章/直接修订_20261101_修订二'
packet = json.loads((run / '世界引擎/写前行动审查.json').read_text(encoding='utf-8'))
for item in packet['sources']:
    assert hashlib.sha256((project / item['path']).read_bytes()).hexdigest() == item['sha256'], item['path']
state = json.loads((project / '追踪/_tracking-state.json').read_text(encoding='utf-8'))
assert state['state_revision'] == 252
manifest_path = project / '追踪/修改影响/active.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
assert manifest['change_id'] == 'revision-054-20261101'
backup = project / '备份/2026-11-01_054修订'
for relative in manifest['changed_files']:
    path = project / relative
    target = backup / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(path.read_bytes())
manifest['checked_files'] = list(manifest['required_checks'])
manifest['conflicts'] = [
    {'source': '正文/第054章_假通过.md', 'target': '正文/第054章_假通过.md', 'severity': 'S2', 'issue': '前句说地点咽回，后句客服确实听到南岸；近期经历写成当年。', 'resolution': '保留实际失言和客服反应；改为想收口却没收住、此前。', 'status': 'resolved'},
    {'source': '正文/第053章_验收题.md', 'target': '大纲/细纲_第053章.md', 'severity': 'S2', 'issue': '细纲职责说已确认短信验收目的，强于正文。', 'resolution': '职责改为提出并试探该假设，目的和作用未证。', 'status': 'resolved'},
    {'source': '正文/第054章_假通过.md', 'target': '大纲/细纲_第054章.md', 'severity': 'S2', 'issue': '试探的因果、地图及现场被描述得过满。', 'resolution': '结果限定公开状态和时间先后，来源、现场及目标图未知。', 'status': 'resolved'}
]
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(project / '正文/第054章_假通过.md').write_bytes((run / 'candidate.md').read_bytes())
p = project / '大纲/细纲_第053章.md'
text = p.read_text(encoding='utf-8').replace('让镜辞确认，那条短信是在用他的眼睛验收处理干不干净。', '让镜辞提出并试探短信可能在借他的观察验收处理结果的假设；发信者、用途及试探作用尚未证实。')
p.write_text(text, encoding='utf-8')
p = project / '大纲/细纲_第054章.md'
text = p.read_text(encoding='utf-8').replace('验证镜辞的反馈是否会影响幕后维护链的现实动作，答案通过项目状态、设备撤出和资源调度体现。', '比较镜辞反馈后公开项目状态、设备撤出与资源调度的时间关系；本章不能证明反馈是其原因。').replace('给一个对方从未处理过的位置报假异常。', '给已见工单未覆盖、尚未复查现场的位置报假异常；后续有无新记录都不能单独证明原因。').replace('“镜辞的反馈可能参与项目收尾”从推测升级为高概率现实闭环，但幕后仍有自己的判断与目标地图。', '公开项目状态与镜辞的反馈相继发生，保留其可能相关的假设；没有证明反馈驱动收尾，也没有证实完整目标图。')
text += '\n## 本轮五问核对\n\n1. 本章是053试探后的过渡，恐怖证据不靠普通公示独立充数，与055—057的身份线索合看。\n2. 撤场也可能来自原定流程或正常售后，公开页不能替代当前现场复查。\n3. 未出现读者独知的幕后确定事实，不将共同收到的页面算认知差。\n4. 旧件被拒、手续费及地点失言均已发生；不把公开更新写成调查获胜。\n5. 保留旧基线、分开两家公司来源并隔夜观察；代价是等待和无法确认现场。\n'
p.write_text(text, encoding='utf-8')
event = {k: v for k, v in state['timeline']['E054'].items() if k not in ['first_recorded_chapter', 'updated_chapter']}
event['action'] = 'upsert'
event['reader_knowledge'] += ' 镜辞实际向恒准售后提到南岸；后续有无公开新行都不能单独证明反馈作用或幕后目标图。'
transaction = {'schema_version': 1, 'mode': 'revision', 'chapter': 54, 'chapter_title': '假通过', 'expected_state_revision': state['state_revision'], 'delta': {'result': '南岸公示改为待收尾，四十七号旧件被拒；恒准售后听到镜辞失言说出南岸，两家公司仍分存。南栏试探本章未发送，公开更新与反馈因果未证。', 'character_changes': [], 'foreshadow_changes': [], 'timeline_events': [event], 'fact_changes': [], 'constraints': ['D4能力来源是024司机身上的线，当前未核；拆件与公开复核不得当空间能力观察。', '南岸地点已在售后电话说出，不能再写成成功咽回；有无新记录均不足证明后台目标图。'], 'next_chapter_commitments': []}, 'context': {k: state['context'][k] for k in ['position', 'long_term_constraints', 'active_character_names', 'continuity_risks']}, 'character_snapshots': {}}
(work / '054修订事务.json').write_text(json.dumps(transaction, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('054 formal and 053-054 outline mappings written; transaction prepared')
