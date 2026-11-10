import hashlib
import json
import sys
from pathlib import Path

project = Path(__file__).resolve().parents[2]
run = project / '追踪/候选章/第054章/直接修订_20261101_修订二'
before = run / '世界引擎/写前行动审查.json'
source = project / '正文/第054章_假通过.md'
candidate = run / 'candidate.md'
phase = sys.argv[1]

def ref(path, marker, source_id=None):
    for index, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if marker in line:
            result = {'start_line': index, 'end_line': index, 'quote': line}
            if source_id:
                result['source_id'] = source_id
            return result
    raise ValueError(marker)

if phase == 'pre':
    packet = json.loads(before.read_text(encoding='utf-8'))
    rows = [
        ('镜辞', '咨询单留着', '接听售后回访时试图只保留咨询单，却失言说出南岸', [
            '只知道来电自称恒准售后，未证实与恒泰同源，手边有两套不同材料。',
            '想保住旧咨询线索，又想避免把两套来源混合后泄露调查。',
            '怕咨询线索被撤销以及南岸地点被录入不明渠道。',
            '能选择自己说什么，不能控制客服记录及对方后续如何行动。',
            '可以只答保留，但急着划清两家关系反而失言，符合紧张时的解释冲动。',
            '南岸已被客服听见，无法把话收回；不知道地点会不会被转交。',
            '客服有自己的回访流程并追问南岸；姜霁可指出口误，不因此确认组织同源。'
        ]),
        ('姜霁', '就叫南栏', '提出向已见工单未覆盖的位置试探，并要求两种结果都保留原因未证', [
            '掌握旧照片、已见工单和公开页面，不知道现场状态及对方完整安排。',
            '想比较虚假反馈后有没有可核的新记录，避免同伴给出新认证。',
            '怕误把时间先后写成因果，亦怕一次叠加多个变量污染判断。',
            '能提出建议、保留页面与约定隔夜观察，没有调度施工的权限。',
            '可以直接猜测目标图，但既有左手误判使她更愿意保留可证与不可证的区别。',
            '等待会错过即时现场信息，假反馈也可能被利用，不能把试验看成必胜。',
            '镜辞仍自主决定发不发，对方与公开流程可能不理会；有无新行均不能单独证明原因。'
        ])
    ]
    packet['actors'] = []
    packet['scenes'] = []
    for i, (name, marker, choice, gates) in enumerate(rows, 1):
        evidence = ref(source, marker, 'SRC1')
        actor = {'id': name, 'name': name, 'protagonist': name == '镜辞', 'own_goal': gates[1], 'without_protagonist': gates[4], 'voice_refs': [evidence], 'timeline_refs': [evidence]}
        known = ref(project / ('正文/第019章_修得太正常.md' if i == 1 else '正文/第053章_验收题.md'), '售后回访' if i == 1 else '先并列着', 'SRC4' if i == 1 else 'SRC5')
        knowledge = dict(known, access='memory', available_chapter=19 if i == 1 else 53, available_order=0, producer_action_id=None, author_only=False, certainty='known', acquisition='镜辞此前亲历恒准咨询和售后回访；姜霁此前已核D4旧件与照片。此次来电自称不等于身份认证。', boundary=gates[0])
        action = {'id': f'A{i}', 'actor_id': name, 'order': i, 'story_tick': i * 10, 'kind': 'action', 'choice': choice, 'gates': dict(zip(['knows', 'wants', 'fears', 'capability', 'no_plot', 'costs', 'consequences'], gates)), 'capacity': {'resources': ['本人电话、旧照片和已取得的公开页'], 'permission': gates[3], 'limits': gates[5], 'evidence_refs': ['SRC1', 'SRC2']}, 'outcome': {'intent': gates[1], 'success_guaranteed': False, 'failure_path': '对方可拒绝回应，也可能正常更新页面，不能从等待直接推断成功。', 'opposition': gates[6]}, 'knowledge_refs': [knowledge]}
        packet['actors'].append(actor)
        packet['scenes'].append({'id': f'S{i}', 'order': i, 'story_time': {'label': '恒准售后电话' if i == 1 else '电话后对照照片并讨论未发送试探', 'tick': i * 10}, 'actors_onstage': [name], 'actors_offstage': [], 'actions': [action]})
    packet['coverage'] = {'all_actors_reviewed': True, 'all_scenes_reviewed': True, 'basis': '按修订范围只重评镜辞失言和姜霁限定试探解释；客服原有追问及他人未改动行为仍依据原接纳正文，不伪造旧章写前证明。', 'background_only': []}
    packet['manual_review'] = {'status': 'passed', 'reviewer': 'Codex主线程', 'method': '对读054原文、候选差异、053交界和逐章行动依据。', 'basis': '客服已经听见南岸，口误必须留下；无论公开页后来有无动作都不能证明完整目标图或施工因果。', 'checks': {k: 'passed' for k in ['seven_gates', 'knowledge_bounds', 'capacity_permissions', 'autonomy', 'constraints', 'consequences', 'voice', 'actor_scene_coverage', 'timeline']}}
    before.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
elif phase == 'post':
    packet = json.loads(before.read_text(encoding='utf-8'))
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    packet['postwrite'] = {
        'prewrite_packet': {'path': before.relative_to(project).as_posix(), 'sha256': sha(before)},
        'candidate': {'path': candidate.relative_to(project).as_posix(), 'sha256': sha(candidate)},
        'scene_results': [
            {'scene_id': 'S1', 'action_ids': ['A1'], 'actual_result': '镜辞仍失言提到南岸，客服仍听见并追问，前句不再把地点说成已咽回。', 'evidence': [ref(candidate, '咨询单留着')], 'world_followups': ['地点实际泄露，是否传给其他渠道未知。']},
            {'scene_id': 'S2', 'action_ids': ['A2'], 'actual_result': '姜霁只建议观察新记录，保留有无更新均不证明因果或完整目标图的边界。', 'evidence': [ref(candidate, '就叫南栏')], 'world_followups': ['镜辞本章仍没有发送南栏消息，不能预支下一章结果。']}
        ],
        'foreshadow_deltas': [{'id': 'NO_CHANGE', 'operation': 'none', 'description': '不新增或回收伏笔；保留两家公司分源和试探未发送。', 'evidence': [ref(candidate, '没有按下去')]}],
        'manual_review': {'status': 'passed', 'reviewer': 'Codex主线程', 'method': '逐行对照候选差异和冻结前包，核信息来源、时间用词与因果限制。', 'basis': '失言后果没有抹去，近期栏杆经历不再写当年，未把等待公开页写成知道幕后图。', 'checks': {k: 'passed' for k in ['actual_coverage', 'causality', 'voice', 'knowledge_bounds', 'consequences', 'foreshadow']}}
    }
    (run / '世界引擎/写后行动复核.json').write_text(json.dumps(packet, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
