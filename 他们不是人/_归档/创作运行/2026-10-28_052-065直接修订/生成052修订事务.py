import json
from pathlib import Path

project = Path(__file__).resolve().parents[2]
state = json.loads((project / '追踪/_tracking-state.json').read_text(encoding='utf-8'))
event = dict(state['timeline']['E052'])
event.pop('first_recorded_chapter', None)
event.pop('updated_chapter', None)
event['action'] = 'upsert'
event['objective_fact'] += ' 宁州陈骁陈述六点四十一本人仍在宁州；许棠的药由邻居前晚代送。'
event['reader_knowledge'] += ' 宁州陈骁的位置是本人陈述，短信和物业新字段是否有关未证实。'
names = ['镜辞', '姜霁']
record = {
    'schema_version': 1,
    'mode': 'revision',
    'chapter': 52,
    'chapter_title': '一条时间线',
    'expected_state_revision': state['state_revision'],
    'delta': {
        'result': '双陈骁分别拒签并账。宁州陈骁自述六点四十一仍在宁州；许棠的药前晚由邻居代送。猫眼九点到、九点十六封存；十点五十七回店，十一点扣186列入工资预告，十一点零六另一笔药送到。',
        'character_changes': [
            {'name': '镜辞', 'change': '见证扣款与停单，不合并两地履历；分存两地与新字段原件'},
            {'name': '姜霁', 'change': '核新字段与独立来源；可见性与短信相关仅作假设'},
            {'name': '猫眼', 'change': '分别封存两地来源，不标真伪；封口时刻晚于到店'},
            {'name': '宁州陈骁', 'change': '陈述当时在宁州，拒勾两项不符事实的说明；厂里扣186、续房42自己承担'},
            {'name': '本地陈骁', 'change': '拒把宁州工单归到七周履历；配送停单少43，不许到站验人'},
            {'name': '杜经理', 'change': '拒点非本人写的新字段，提供原页及签字抄件；说明许棠的药前晚已由邻居代送'}
        ],
        'foreshadow_changes': [], 'timeline_events': [event], 'fact_changes': [],
        'constraints': ['两地损失不混；本人位置陈述不能冒充独立证据；短信与新字段先后不证明同源；不提前获知十一点零六结果。'],
        'next_chapter_commitments': ['502可见性短信未答；D4试验不能拿陈骁当标准答案。']
    },
    'context': {k: state['context'][k] for k in ['position', 'long_term_constraints', 'active_character_names', 'continuity_risks']},
    'character_snapshots': {name: state['characters'][name] for name in names}
}
out = Path(__file__).parent / '052修订事务.json'
out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('transaction prepared')
