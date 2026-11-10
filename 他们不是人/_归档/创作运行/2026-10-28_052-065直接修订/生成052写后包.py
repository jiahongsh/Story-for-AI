import hashlib
import json
from pathlib import Path

project = Path(__file__).resolve().parents[2]
run = project / '追踪/候选章/第052章/直接修订_20261028_修订二'
before = run / '世界引擎/写前行动审查.json'
candidate = run / 'candidate.md'
packet = json.loads(before.read_text(encoding='utf-8'))
lines = candidate.read_text(encoding='utf-8').splitlines()

def evidence(text):
    for index, line in enumerate(lines, 1):
        if text in line:
            return {'start_line': index, 'end_line': index, 'quote': line}
    raise ValueError(text)

def relative(path):
    return path.relative_to(project).as_posix()

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

packet['postwrite'] = {
    'prewrite_packet': {'path': relative(before), 'sha256': digest(before)},
    'candidate': {'path': relative(candidate), 'sha256': digest(candidate)},
    'scene_results': [
        {'scene_id': 'S1', 'actual_result': '宁州陈骁陈述当时在宁州并拒签，工资扣款风险由其承担；姜霁分存材料，不认证身份。', 'action_ids': ['A1', 'A2'], 'evidence': [evidence('六点四十一我还在宁州'), evidence('这一张归宁州那夹')], 'world_followups': ['工厂未接受备注，陈骁继续承担工资损失，双方履历未合并。']},
        {'scene_id': 'S2', 'actual_result': '姜霁要求保留页面与时间；杜经理交接昨晚代送药与今早卡仍红，拒点非本人写的字段。', 'action_ids': ['A3', 'A4'], 'evidence': [evidence('药昨晚已经由邻居送进去了')], 'world_followups': ['物业字段与短信的关系仍是待核假设，许棠的问题独立于陈骁账户。']}
    ],
    'foreshadow_deltas': [{'id': 'NO_CHANGE', 'operation': 'none', 'description': '本次更正两个时间表述，没有新增或回收伏笔；新字段来源仍待核。', 'evidence': [evidence('待可见性复核')]}],
    'manual_review': {'status': 'passed', 'reviewer': 'Codex主线程', 'method': '回读052候选、冻结行动包及051相邻事实，检查具体措辞和证据边界。', 'basis': '陈骁仅陈述自身所在地，杜经理说前夜代送，未将短信先后写成后台因果或身份结论。', 'checks': {k: 'passed' for k in ['actual_coverage', 'causality', 'voice', 'knowledge_bounds', 'consequences', 'foreshadow']}}
}
out = run / '世界引擎/写后行动复核.json'
out.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(out)
