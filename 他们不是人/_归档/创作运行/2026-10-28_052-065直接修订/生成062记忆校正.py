import json
from pathlib import Path

project = Path(__file__).resolve().parents[2]
state = json.loads((project / '追踪/_tracking-state.json').read_text(encoding='utf-8'))
previous = project / '创作运行/2026-10-06_第三批反调查闭环/第062章/修订事务.json'
transaction = json.loads(previous.read_text(encoding='utf-8'))
# 旧事务仅作完整增量结构来源；时刻按当前正文、事实K005及事件E062校正。
transaction['delta'] = json.loads(json.dumps(transaction['delta'], ensure_ascii=False).replace('十一点二十', '八点二十').replace('11:20', '08:20'))
transaction['expected_state_revision'] = state['state_revision']
transaction['context'] = {k: state['context'][k] for k in ['position', 'long_term_constraints', 'active_character_names', 'continuity_risks']}
transaction['character_snapshots'] = {item['name']: state['characters'][item['name']] for item in transaction['delta']['character_changes'] if item['name'] in state['characters']}
for group, authority in [('timeline_events', 'timeline'), ('foreshadow_changes', 'foreshadow'), ('fact_changes', 'facts')]:
    for item in transaction['delta'][group]:
        current = state[authority][item['id']]
        for key in list(item):
            if key != 'action' and key in current:
                item[key] = current[key]
out = Path(__file__).parent / '062记忆校正事务.json'
out.write_text(json.dumps(transaction, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('prepared 062 memory-only correction')
