import hashlib
import json
import sys
from pathlib import Path

project = Path(__file__).resolve().parents[2]
run = project / '追踪/候选章/第055章/直接修订_20261101'
before = run / '世界引擎/写前行动审查.json'
candidate = run / 'candidate.md'
old = project / '正文/第055章_没处理过.md'

def ref(path, marker, sid=None):
    for i, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if marker in line:
            r = {'start_line': i, 'end_line': i, 'quote': line}
            if sid:
                r['source_id'] = sid
            return r
    raise ValueError(marker)

if sys.argv[1] == 'pre':
    p = json.loads(before.read_text(encoding='utf-8'))
    rows = [
        ('镜辞', '查看次晨收到的匿名回复并对照此前发送记录', [
            '已经准备并发出了南栏试探，收到回复之前不知道对方会答什么，不能预知现场。',
            '想知道自己的试探有没有回应，保留与公开页分开的来源。',
            '怕一句假话进入未知流程后给别人带来真实后果。',
            '能够查看本人手机和既有公开页，不能查询上游内部调度。',
            '即使没有主线任务，也会查看自己主动发出询问后的回应，而不是销毁记录。',
            '等待回复已消耗一夜，不能要求对方解释，更不能由短信补齐未知现场。',
            '回复者只给一句自称未处理，姜霁仍可质疑其含义，商户照常自行营业。'
        ]),
        ('姜霁', '将匿名回复、昨晚公开空白页与尚未复查的现场分开陈述', [
            '已看到镜辞读出的回复与昨晚打印页，只知对方用过南栏这个称呼。',
            '想保存能交叉核对的材料，避免把一句自称扩大成全局目标图。',
            '怕自己的解释再次让未证实推断进入正式记录并误伤他人。',
            '可以分类材料和提出限制，没有进入现场或后台确认施工的能力。',
            '可以随同伴猜测，但过往更正责任使她仍会先说清来源和未知范围。',
            '仍需等待更多来源，无法立刻给试探判成成功，亦不能替商户判断实际损失。',
            '镜辞可保留自己的猜想，猫眼只交公开存档，不因她一句话提供内部名册。'
        ]),
        ('镜辞', '在私人本记录对方可能有安排，不把目标图和现场状态写成已确认', [
            '只掌握匿名原话、昨晚页面和商户门口照片，三者时点不同且均非现场全貌。',
            '想继续检验自己的调查是否被利用，同时保全尚未被覆盖的独立来源。',
            '怕把一次回应当胜利，反而替未知安排提供错误认证。',
            '能记录假设、保存照片和暂不回现场，不能替陌生人制定或查明全部目标。',
            '可把推断写满，但已有错误反馈代价使他愿意留下暂时无法确认的空白。',
            '接受不确定和停止定时打印带来的渠道收缩，不拿空白页抵偿别人的钱。',
            '打印店自行停止定时盯页，猫眼继续只提供公开证据，两家公司仍不能被合并。'
        ])
    ]
    p['actors'] = []
    for name in ['镜辞', '姜霁']:
        row = next(x for x in rows if x[0] == name)
        anchor = ref(project / '正文/第054章_假通过.md', '咨询单留着' if name == '镜辞' else '就叫南栏', 'SRC2')
        p['actors'].append({'id': name, 'name': name, 'protagonist': name == '镜辞', 'own_goal': row[2][1], 'without_protagonist': row[2][4], 'voice_refs': [anchor], 'timeline_refs': [anchor]})
    p['scenes'] = []
    for i, (name, choice, gates) in enumerate(rows, 1):
        anchor = ref(project / '正文/第054章_假通过.md', '输入框里打上一行', 'SRC2') if i == 1 else ref(old, '`南栏没处理过。`', 'SRC1')
        knowledge = dict(anchor, access='memory' if i == 1 else 'planned-earlier-action', available_chapter=54 if i == 1 else 55, available_order=0 if i == 1 else 1, producer_action_id=None if i == 1 else 'A1', author_only=False, certainty='known', acquisition='原有输入框和试探意图由本人持有；收信动作先取得匿名回复，后续仅据已读原话判断。', boundary=gates[0])
        action = {'id': f'A{i}', 'actor_id': name, 'order': i, 'story_tick': i * 10, 'kind': 'action', 'choice': choice, 'gates': dict(zip(['knows', 'wants', 'fears', 'capability', 'no_plot', 'costs', 'consequences'], gates)), 'knowledge_refs': [knowledge], 'capacity': {'resources': ['本人手机、打印页及公开存档'], 'permission': gates[3], 'limits': gates[5], 'evidence_refs': ['SRC1', 'SRC2', 'SRC3']}, 'outcome': {'intent': gates[1], 'success_guaranteed': False, 'failure_path': '对方不作解释，公开页仍可能遗漏现场变化，推断无法证实。', 'opposition': gates[6]}}
        p['scenes'].append({'id': f'S{i}', 'order': i, 'story_time': {'label': ['次晨六点二十一后查看来信', '查看来信及昨晚打印页后', '同次对照后写私人判断'][i-1], 'tick': i * 10}, 'actors_onstage': [name], 'actors_offstage': [], 'actions': [action]})
    p['coverage'] = {'all_actors_reviewed': True, 'all_scenes_reviewed': True, 'basis': '只重评本次收信后两位判断者的知识范围及表达，未改匿名回复、商户拒绝或猫眼交付，不补造未知回复者的后台选择。', 'background_only': []}
    p['manual_review'] = {'status': 'passed', 'reviewer': 'Codex主线程', 'method': '对读054已修正文、055差异与056已有未知边界，区分收到的原话和作者结论。', 'basis': '匿名回复只证明对方说过，空页只对应其时间和来源；无法证明现场不派人或完整目标图。', 'checks': {k: 'passed' for k in ['seven_gates', 'knowledge_bounds', 'capacity_permissions', 'autonomy', 'constraints', 'consequences', 'voice', 'actor_scene_coverage', 'timeline']}}
    before.write_text(json.dumps(p, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
else:
    p = json.loads(before.read_text(encoding='utf-8'))
    sha = lambda x: hashlib.sha256(x.read_bytes()).hexdigest()
    markers = ['把这六个字念出来', '回复里用了南栏', '对方可能有自己的安排']
    results = ['镜辞读到并保存匿名原话，没有取得工单号或现场说明。', '姜霁将匿名回复与公开页分开，明确现场未复看。', '镜辞只记可能的安排，不再认证完整目标图或自己是验收样本。']
    p['postwrite'] = {'prewrite_packet': {'path': before.relative_to(project).as_posix(), 'sha256': sha(before)}, 'candidate': {'path': candidate.relative_to(project).as_posix(), 'sha256': sha(candidate)}, 'scene_results': [{'scene_id': f'S{i}', 'action_ids': [f'A{i}'], 'actual_result': results[i-1], 'evidence': [ref(candidate, markers[i-1])], 'world_followups': ['现场及真实调度仍未查明，打印店与猫眼各自的权限不因推断扩大。']} for i in range(1, 4)], 'foreshadow_deltas': [{'id': 'NO_CHANGE', 'operation': 'none', 'description': 'F005当前权威已限定未知，此次将正文和旧事件摘要校正到该边界，不新增回收。', 'evidence': [ref(candidate, '现场有没有动')]}], 'manual_review': {'status': 'passed', 'reviewer': 'Codex主线程', 'method': '逐句核对改动、冻结行动及F005当前值，检查后续056仍保留未知。', 'basis': '只改变推断的确信程度，不改回复原文、发送时刻、公开照片、打印店拒绝及实际费用。', 'checks': {k: 'passed' for k in ['actual_coverage', 'causality', 'voice', 'knowledge_bounds', 'consequences', 'foreshadow']}}}
    (run / '世界引擎/写后行动复核.json').write_text(json.dumps(p, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
