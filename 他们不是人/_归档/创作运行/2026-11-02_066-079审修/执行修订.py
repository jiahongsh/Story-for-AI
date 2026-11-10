import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from 修订配置 import CASES

WORK = Path(__file__).resolve().parent
PROJECT = WORK.parents[1]
REPO = PROJECT.parent
TRACKING = REPO / 'skills/story-long-write/scripts/tracking_commit.py'
WORLD = REPO / 'skills/story-world-engine/scripts/world_gate.py'
GUARD = REPO / 'skills/story-long-write/scripts/revision_guard.py'

def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def rel(path):
    return path.relative_to(PROJECT).as_posix()

def run(args):
    result = subprocess.run([str(x) for x in args], cwd=REPO, capture_output=True, text=True, encoding='utf-8', errors='replace', env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'})
    print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    if result.returncode:
        raise RuntimeError(f'command failed ({result.returncode})')
    return result.stdout

def chapter_path(n):
    paths = list((PROJECT / '正文').glob(f'第{n:03}章_*.md'))
    assert len(paths) == 1, paths
    return paths[0]

def cite(path, marker, source_id=None):
    lines = path.read_text(encoding='utf-8').splitlines()
    for i, line in enumerate(lines, 1):
        if marker in line:
            value = {'start_line': i, 'end_line': i, 'quote': line}
            if source_id:
                value['source_id'] = source_id
            return value
    raise ValueError(f'marker not found in {path}: {marker}')

def source_for_prior(n, marker):
    for k in range(n - 1, 0, -1):
        path = chapter_path(k)
        if marker in path.read_text(encoding='utf-8'):
            return path, k
    raise ValueError(marker)

LABELS = {66: ['065次晨整理薄本'],67: ['候车时接水并收整票据'],
    68: ['客栈归程下午，先小巴后实名客运'],
    69: ['傍晚收到唐宁到家消息之后'],
    70: ['早餐七点四十后收到初一习惯补充'],
    71: ['八点四十六后视频接通时'],
    73: ['第二工日八点十分杜经理通知', '八点四十后送药人上五楼', '其后返回活动室报告无人应门'],
    75: ['早晨公示传来后至晚间保存各自结果'],
    77: ['唐宁限定作证并核旧账后的中午'],
    57: ['西口清晨客人离开后', '同场听完摊主估计后'],
    58: ['东口下午两点的公开谈话'],
    59: ['十五点四十四读取群消息', '十五点五十至十六点四十一寻人并到店陈述'],
    60: ['九点四十接收孙立的维修表', '孙立离店后、约九点五十五前'],
    61: ['十四点十八分读到问话', '其后记下时刻和疑问'],
    64: ['早餐铺七点四十八以后邻桌挪凳', '同场端油条上菜', '八点二十前回店记录'],
    65: ['下午两点十分后的栏外问询至离场', '四点二十回店后到市场口打印']
}
RESOURCES = {'当前存在': ['本人票证、包和水瓶'],'水果摊老板': ['本人菜摊、价目牌、熟客经营记忆'], '姜霁': ['本人文件夹、已获准材料、现金和手机'], '裴亮': ['本人工号群、手机、单车付费页'], '镜辞': ['本人手机及私人本、维修工具、店内账款'], '窗边老头': ['本人凳子和豆浆、熟客经历'], '郭老板': ['竹匾、油条、漏勺、店内服务权']}

RESOURCES.update({'宁州陈骁': ['本人工厂位置、手机视频、既有家庭争议经历'], '杜经理': ['本人工单、副本、页面与电话，住宅门无代开权限'], '送药人': ['待送药物、本人脚程和敲门结果']})

def setup(n):
    cfg = CASES[n]
    folder = WORK / f'第{n:03}章'
    folder.mkdir(parents=True, exist_ok=True)
    formal = chapter_path(n)
    outline = PROJECT / f'大纲/细纲_第{n:03}章.md'
    basis = folder / '写前依据.md'
    backgrounds = {
        '水果摊老板': '本轮拟增的普通经营背景：摊主记得熟客往常买三把、按现价七块五；此记忆先于当天客人离开，不冒称旧章已写过。',
        '窗边老头': '本轮明确的熟客背景：长期在这间铺子占座，听惯郭老板叫她芽，爱插话；不知身份接缝或调查。'
    }
    text = f'# 第{n:03}章本轮写前依据\n\n只重评本次局部修订的受影响选择，不追溯伪造旧稿写前证明。\n\n'
    for i, actor in enumerate(cfg['actors'], 1):
        text += f'拟行动A{i}｜{actor["name"]}｜{actor["choice"]}\n\n'
        if actor['name'] in backgrounds and not actor.get('producer'):
            text += '既往背景｜' + backgrounds[actor['name']] + '\n\n'
        if actor.get('background'):
            text += '既往背景｜' + actor['background'] + '\n\n'
        for label, value in zip(['知情', '欲望', '顾虑', '能力权限', '脱离剧情仍会选择的理由', '代价约束', '他人独立回应'], actor['gates']):
            text += f'- {label}：{value}\n'
        text += '\n'
    text += '## 恐怖节拍五问\n\n' + '\n'.join(f'{i}. {v}' for i, v in enumerate(cfg['five'], 1)) + '\n'
    text += '\n来源限制：本轮新增的生活过渡是作者此次修订，不冒称旧正文已有证据；当场观察或对话只在发生后使用。原有动作、钱款和未揭结论见绑定的活动正文与相邻章。\n'
    basis.write_text(text, encoding='utf-8')
    plan = {'schema_version': 1, 'change_id': f'revision-{n:03}-20261102', 'summary': cfg['summary'], 'semantic_change': True, 'changed_files': [rel(formal), rel(outline)], 'affected_entities': cfg['entities'], 'affected_fact_ids': ['K004'] if n == 61 else ['K009'] if n == 65 else [], 'affected_chapters': [n]}
    write_json(folder / '修订计划.json', plan)
    run([sys.executable, GUARD, 'plan', '--project', PROJECT, '--input', folder / '修订计划.json', '--output', folder / '影响清单.json'])
    print('PREPARED', n)

def prewrite(n):
    cfg = CASES[n]
    folder = WORK / f'第{n:03}章'
    formal, outline = chapter_path(n), PROJECT / f'大纲/细纲_第{n:03}章.md'
    basis = folder / '写前依据.md'
    run_dir = PROJECT / f'追踪/候选章/第{n:03}章/直接修订_20261102'
    packet_path = run_dir / '世界引擎/写前行动审查.json'
    sources = [formal, chapter_path(n - 1), outline, basis]
    previous = {}
    for i, actor in enumerate(cfg['actors'], 1):
        if actor.get('prior_marker'):
            path, chapter = source_for_prior(n, actor['prior_marker'])
            previous[i] = (path, chapter)
            if path not in sources:
                sources.append(path)
    args = [sys.executable, WORLD, 'init', '--project', PROJECT, '--chapter', n, '--mode', 'revision', '--tracking-tool', TRACKING]
    for source in sources:
        args += ['--source', rel(source)]
    run(args + ['--packet', rel(packet_path)])
    p = read_json(packet_path)
    sid = {x['path']: x['id'] for x in p['sources']}
    for item in p['sources']:
        if item['path'] == rel(basis):
            item['scope'] = 'planned'
    p['actors'], p['scenes'] = [], []
    names = []
    for i, a in enumerate(cfg['actors'], 1):
        name, gates = a['name'], a['gates']
        if name not in names:
            names.append(name)
            voice_marker = a.get('voice_marker') or cfg.get('voice_marker') or ('这行只记用途' if name == '当前存在' else name)
            anchor = cite(formal, voice_marker, sid[rel(formal)])
            p['actors'].append({'id': name, 'name': name, 'protagonist': name == '镜辞', 'own_goal': gates[1], 'without_protagonist': gates[4], 'voice_refs': [anchor], 'timeline_refs': [anchor]})
        producer = a.get('producer')
        if producer:
            anchor = cite(basis, f'拟行动A{producer}｜', sid[rel(basis)])
            k = dict(anchor, access='planned-earlier-action', available_chapter=n, available_order=producer, producer_action_id=f'A{producer}')
        elif i in previous:
            path, chapter = previous[i]
            k = dict(cite(path, a['prior_marker'], sid[rel(path)]), access='memory', available_chapter=chapter, available_order=0, producer_action_id=None)
        else:
            k = dict(cite(basis, '既往背景｜', sid[rel(basis)]), access='memory', available_chapter=n - 1, available_order=0, producer_action_id=None)
        k.update(author_only=False, certainty='belief' if not producer and i not in previous else 'known', acquisition='既有材料或自身经营、生活经历在选择前已具备；本章对方新说的话只在其先行动发生后使用。新增背景明确为本轮规划，不冒充旧章记录。', boundary=gates[0])
        action = {'id': f'A{i}', 'actor_id': name, 'order': i, 'story_tick': i * 10, 'kind': 'action', 'choice': a['choice'], 'gates': dict(zip(['knows', 'wants', 'fears', 'capability', 'no_plot', 'costs', 'consequences'], gates)), 'capacity': {'resources': RESOURCES[name], 'permission': gates[3], 'limits': gates[5], 'evidence_refs': [sid[rel(formal)], sid[rel(basis)]]}, 'outcome': {'intent': gates[1], 'success_guaranteed': False, 'failure_path': gates[5], 'opposition': gates[6]}, 'knowledge_refs': [k]}
        p['scenes'].append({'id': f'S{i}', 'order': i, 'story_time': {'label': LABELS[n][i-1], 'tick': i * 10}, 'actors_onstage': [name], 'actors_offstage': [], 'actions': [action]})
    p['coverage'] = {'all_actors_reviewed': True, 'all_scenes_reviewed': True, 'basis': '仅重评本轮明确修订的受影响选择，按正文、准备稿差异与相邻接口核查；未改动的旧章行动不另造当年的七关，未增加幕后角色决定。', 'background_only': []}
    p['manual_review'] = {'status': 'passed', 'reviewer': 'Codex主线程', 'method': '对读现行章、相邻章节和隔离候选差异，逐项校验七关、资金及物件归属、有限知识和声线。', 'basis': cfg['summary'] + '；新生活细节和当场信息均写明来路，不以未见认证身份，不将时序作为因果。', 'checks': {k: 'passed' for k in ['seven_gates', 'knowledge_bounds', 'capacity_permissions', 'autonomy', 'constraints', 'consequences', 'voice', 'actor_scene_coverage', 'timeline']}}
    write_json(packet_path, p)
    run([sys.executable, WORLD, 'check', '--project', PROJECT, '--packet', rel(packet_path), '--phase', 'prewrite', '--tracking-tool', TRACKING])

def make_candidate(n):
    cfg = CASES[n]
    folder = PROJECT / f'追踪/候选章/第{n:03}章/直接修订_20261102'
    text = (PROJECT / cfg['prepared']).read_text(encoding='utf-8') if cfg.get('prepared') else chapter_path(n).read_text(encoding='utf-8')
    if n == 59:
        old = '他让我来的。”'
        assert text.count(old) == 1
        text = text.replace(old, old + '\n\n“三点五十以后我还在找陈工。西口外面几个摊位问了一圈，电话打了三遍，没接通。四点半还没找到，我才推车来问你们。”裴亮抹了一把额角，“这段不是那四十分钟，别给我一起报进去。”')
        text = text.replace('骑车赶路的汗还没干。', '额角还挂着汗。')
        text = text.replace('他把单车停稳，车锁扣了两次才扣上。', '他把单车支稳，支架撑了两次才立住。')
        text = text.replace('裴亮骂了一句，把车锁上，没有再进门。', '裴亮骂了一句，把车扶稳，没有再进门。')
        old = '单车订单另开一张，三块，起点仓库，终点旧市场西口。订单完成时间十五点三十九，比群里那句待复核只早几分钟。'
        assert old in text
        text = text.replace(old, '单车的预付页另开一张，三块，开锁点是仓库。裴亮又翻到十五点三十九存的截屏，定位在旧市场西口，离群里那句待复核只早几分钟。')
        text = text.replace('事由空跑。单车的预付页', '事由空跑。\n\n单车的预付页')
    if n == 60:
        old = '用自己的慢表对了一下，对不准，就放弃了。'
        assert old in text
        text = text.replace(old, '朝待修盘那边看了一眼，没有再去碰表。')
    for old, new in cfg.get('text_replacements', []):
        assert old in text, old
        text = text.replace(old, new)
    (folder / 'candidate.md').write_text(text, encoding='utf-8')
    for script, options in [('language_gate.js', []), ('check-style-hygiene.js', ['--check', '--fail-on=blocking']), ('check-ai-patterns.js', ['--check', '--fail-on=blocking']), ('check-degeneration.js', ['--check', '--language=zh', '--fail-on=blocking'])]:
        run(['node', REPO / 'skills/story-long-write/scripts' / script, *options, folder / 'candidate.md'])
    p = read_json(folder / '世界引擎/写前行动审查.json')
    results = []
    for i, a in enumerate(cfg['actors'], 1):
        evidence = cite(folder / 'candidate.md', a['post'])
        results.append({'scene_id': f'S{i}', 'action_ids': [f'A{i}'], 'actual_result': a['name'] + '实际完成的选择由下列正文原句限定：' + evidence['quote'], 'evidence': [evidence], 'world_followups': [a['gates'][6]]})
    p['postwrite'] = {'prewrite_packet': {'path': rel(folder / '世界引擎/写前行动审查.json'), 'sha256': sha(folder / '世界引擎/写前行动审查.json')}, 'candidate': {'path': rel(folder / 'candidate.md'), 'sha256': sha(folder / 'candidate.md')}, 'scene_results': results, 'foreshadow_deltas': [{'id': 'NO_CHANGE', 'operation': 'none', 'description': '本轮不新埋或回收伏笔，原ID当前状态保持；时序、个人选择及账目修正写入同章事件。', 'evidence': results[0]['evidence']}], 'manual_review': {'status': 'passed', 'reviewer': 'Codex主线程', 'method': '以候选实际句逐项对照冻结前包、原文及相邻章；四语言门均运行通过后登记。', 'basis': cfg['summary'] + '。保护故障、报价、来源限制和未决身份，不将新增的普通过渡冒充历史证据。', 'checks': {k: 'passed' for k in ['actual_coverage', 'causality', 'voice', 'knowledge_bounds', 'consequences', 'foreshadow']}}}
    write_json(folder / '世界引擎/写后行动复核.json', p)
    run([sys.executable, WORLD, 'check', '--project', PROJECT, '--packet', rel(folder / '世界引擎/写后行动复核.json'), '--phase', 'postwrite', '--tracking-tool', TRACKING])
    print('CANDIDATE_CHECKED', n)

def transaction(n, before_revision):
    cfg = CASES[n]
    state = read_json(PROJECT / '追踪/_tracking-state.json')
    assert state['state_revision'] == before_revision
    record = (PROJECT / f'追踪/逐章记录/第{n:03}章.md').read_text(encoding='utf-8')
    sections = {name: body for name, body in re.findall(r'^## ([^\n]+)\n(.*?)(?=^## |\Z)', record, re.M | re.S)}
    result = re.search(r'^- 结果：(.*)$', record, re.M).group(1)
    commitment = re.search(r'^- 下一章承诺：(.*)$', record, re.M).group(1)
    commitments = [x for x in commitment.split('；') if x and x != '无']
    roles = [{'name': name, 'change': change} for name, change in re.findall(r'^- (.*?)｜(?:核心|临时)｜(.*)$', sections['角色变化'], re.M)]
    for name, change in cfg.get('role_updates', {}).items():
        existing = next((r for r in roles if r['name'] == name), None)
        if existing:
            existing['change'] = change
        else:
            roles.append({'name': name, 'change': change})
    if n == 60:
        commitments = [x.replace('确认他知道孙立会来', '使镜辞怀疑信息泄露，但来源及是否知道孙立来过未证') for x in commitments]
    fore = []
    for fid in dict.fromkeys(re.findall(r'^- (F\d+)｜', sections['伏笔变化'], re.M)):
        current = state['foreshadow'][fid]
        fore.append({'action': 'upsert', **{k: current[k] for k in ['id', 'importance', 'planned_resolution_chapter', 'planted_chapter', 'status', 'summary'] if k in current}})
    events = []
    for eid in dict.fromkeys(re.findall(r'^- (E\d+)｜', sections['时间与揭示'], re.M)):
        event = {k: v for k, v in state['timeline'][eid].items() if k not in ['first_recorded_chapter', 'updated_chapter']}
        event['action'] = 'upsert'
        for old, new in cfg.get('event_replacements', []):
            assert old in event['objective_fact']
            event['objective_fact'] = event['objective_fact'].replace(old, new)
        if n == 59:
            event['objective_fact'] = event['objective_fact'].replace('订单15:39止', '预付页截屏15:39定位西口')
        if n == 65:
            event['objective_fact'] = event['objective_fact'].replace('马甲工空签到、口扣15', '马甲工空签到、自述十五元待队上认定')
        event['objective_fact'] += cfg.get('objective_add', '')
        if n == 65:
            event['objective_fact'] = '陈屿栏外列502、北河、孙立，镜辞拒填。马甲工空签到，晨间到场仅自述、15元待队上认；镜辞只见下午。孙立自留维修原票、自己争退费。薄本姓名空，住宅工单改期后日18点，镜辞留店。两人往返车费8从修表格出；姜霁自付打印1.5、取回找零0.5。'
        if n in [57, 59, 61, 65]:
            event['reader_knowledge'] += ' ' + cfg['result']
        events.append(event)
    facts = []
    for fid in dict.fromkeys(re.findall(r'^- ([KR]\d+)｜', sections['长期事实变化'], re.M)):
        current = {k: v for k, v in state['facts'][fid].items() if k not in ['first_recorded_chapter', 'updated_chapter']}
        facts.append({'action': 'upsert', **current})
    constraints = re.findall(r'^- (.*)$', sections['连贯性约束'], re.M)
    if n == 60:
        constraints.append('下午取表只完成正常维修，不重新决定是否给顾客出具身份验收。')
    if n == 59:
        constraints.append('15:50后寻人和16:30后推车到店为本轮新增过渡，由裴亮自述，非旧材料查得；不计入派工40分钟。')
    return {'schema_version': 1, 'mode': 'revision', 'chapter': n, 'chapter_title': chapter_path(n).stem.split('_', 1)[1], 'expected_state_revision': before_revision, 'delta': {'result': result + ' ' + cfg['result'], 'character_changes': roles, 'foreshadow_changes': fore, 'timeline_events': events, 'fact_changes': facts, 'constraints': constraints, 'next_chapter_commitments': commitments}, 'context': {k: state['context'][k] for k in ['position', 'long_term_constraints', 'active_character_names', 'continuity_risks']}, 'character_snapshots': {r['name']: state['characters'][r['name']] for r in roles if r['name'] in state['characters']}}

def accept(n):
    cfg, folder = CASES[n], WORK / f'第{n:03}章'
    run_dir = PROJECT / f'追踪/候选章/第{n:03}章/直接修订_20261102'
    pre = read_json(run_dir / '世界引擎/写前行动审查.json')
    post = read_json(run_dir / '世界引擎/写后行动复核.json')
    assert sha(PROJECT / post['postwrite']['candidate']['path']) == post['postwrite']['candidate']['sha256']
    for source in pre['sources']:
        assert sha(PROJECT / source['path']) == source['sha256'], source['path']
    state = read_json(PROJECT / '追踪/_tracking-state.json')
    before_revision = state['state_revision']
    assert before_revision == pre['binding']['tracking']['state_revision']
    reviewed = read_json(folder / '实际核读.json')
    planned = read_json(folder / '影响清单.json')
    assert set(planned['required_checks']) <= set(reviewed['checked_files']), 'required checks not fully reviewed'
    active = PROJECT / '追踪/修改影响/active.json'
    if active.exists():
        previous = read_json(active)
        target = WORK / '已关闭影响清单' / previous['change_id']
        target.mkdir(parents=True, exist_ok=True)
        (target / 'active.json').write_bytes(active.read_bytes())
        stamp = PROJECT / '追踪/修改影响/active.approved.json'
        if stamp.exists():
            (target / 'active.approved.json').write_bytes(stamp.read_bytes())
    run([sys.executable, GUARD, 'plan', '--project', PROJECT, '--input', folder / '修订计划.json', '--output', active])
    manifest = read_json(active)
    manifest['checked_files'] = reviewed['checked_files']
    manifest['conflicts'] = [{'source': rel(chapter_path(n)), 'target': rel(PROJECT / f'大纲/细纲_第{n:03}章.md'), 'severity': 'S2', 'issue': cfg['summary'], 'resolution': cfg['outline_add'], 'status': 'resolved'}]
    write_json(active, manifest)
    for relative in manifest['changed_files']:
        original = PROJECT / relative
        backup = PROJECT / f'备份/2026-11-02_057-065修订/第{n:03}章' / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(original.read_bytes())
    txn = transaction(n, before_revision)
    write_json(folder / '修订事务.json', txn)
    outline_path = PROJECT / f'大纲/细纲_第{n:03}章.md'
    text = outline_path.read_text(encoding='utf-8')
    for old, new in cfg.get('outline_replacements', []):
        assert old in text, old
        text = text.replace(old, new)
    text += '\n## 2026-11-02本轮修订映射\n\n' + cfg['outline_add'] + '\n\n### 恐怖节拍与证据五问\n\n' + '\n'.join(f'{i}. {value}' for i, value in enumerate(cfg['five'], 1)) + '\n'
    chapter_path(n).write_bytes((run_dir / 'candidate.md').read_bytes())
    outline_path.write_text(text, encoding='utf-8')
    commit_written(n)

def commit_written(n):
    cfg, folder = CASES[n], WORK / f'第{n:03}章'
    active = PROJECT / '追踪/修改影响/active.json'
    manifest = read_json(active)
    assert manifest['change_id'] == f'revision-{n:03}-20261102'
    txn = read_json(folder / '修订事务.json')
    before_revision = txn['expected_state_revision']
    assert read_json(PROJECT / '追踪/_tracking-state.json')['state_revision'] == before_revision
    run([sys.executable, TRACKING, 'commit', '--project', PROJECT, '--input', folder / '修订事务.json'])
    run([sys.executable, TRACKING, 'check', '--project', PROJECT])
    after_revision = read_json(PROJECT / '追踪/_tracking-state.json')['state_revision']
    assert after_revision == before_revision + 1
    manifest['tracking_action'] = {'kind': 'commit', 'state_revision_before': before_revision, 'state_revision_after': after_revision, 'reason': cfg['summary'] + '；完整保留截至099的人物快照及伏笔当前状态。'}
    write_json(active, manifest)
    run([sys.executable, GUARD, 'check', '--project', PROJECT, '--input', active, '--stamp', PROJECT / '追踪/修改影响/active.approved.json'])
    finish(n)

def recover_written(n):
    cfg, folder = CASES[n], WORK / f'第{n:03}章'
    run_dir = PROJECT / f'追踪/候选章/第{n:03}章/直接修订_20261102'
    assert sha(chapter_path(n)) == sha(run_dir / 'candidate.md')
    pre = read_json(run_dir / '世界引擎/写前行动审查.json')
    outline = PROJECT / f'大纲/细纲_第{n:03}章.md'
    old = next(s for s in pre['sources'] if s['path'] == rel(outline))
    assert sha(outline) == old['sha256']
    text = outline.read_text(encoding='utf-8')
    for old, new in cfg.get('outline_replacements', []):
        assert old in text
        text = text.replace(old, new)
    text += '\n## 2026-11-02本轮修订映射\n\n' + cfg['outline_add'] + '\n\n### 恐怖节拍与证据五问\n\n' + '\n'.join(f'{i}. {v}' for i, v in enumerate(cfg['five'], 1)) + '\n'
    outline.write_text(text, encoding='utf-8')
    commit_written(n)

def finish(n):
    cfg, folder = CASES[n], WORK / f'第{n:03}章'
    active = PROJECT / '追踪/修改影响/active.json'
    manifest = read_json(active)
    assert manifest['change_id'] == f'revision-{n:03}-20261102'
    run([sys.executable, GUARD, 'check', '--project', PROJECT, '--input', active, '--stamp', PROJECT / '追踪/修改影响/active.approved.json'])
    receipt = PROJECT / f'追踪/章节提交/第{n:03}章.json'
    if receipt.exists():
        run([sys.executable, REPO / 'skills/story-long-write/scripts/chapter_candidate.py', 'sync', '--project', PROJECT, '--chapter', n, '--revision-manifest', active, '--revision-stamp', PROJECT / '追踪/修改影响/active.approved.json', '--reason', cfg['summary'], '--confirm', 'SYNC'])
    run([sys.executable, REPO / 'skills/story-long-write/scripts/voice_profile.py', 'update', '--project', PROJECT])
    run([sys.executable, REPO / 'skills/story-long-write/scripts/story_doctor.py', '--project', PROJECT])
    run_dir = PROJECT / f'追踪/候选章/第{n:03}章/直接修订_20261102'
    write_json(folder / '完成记录.json', {'chapter': n, 'state_revision_before': manifest['tracking_action']['state_revision_before'], 'state_revision_after': manifest['tracking_action']['state_revision_after'], 'formal_sha256': sha(chapter_path(n)), 'candidate_sha256': sha(run_dir / 'candidate.md'), 'summary': cfg['summary']})
    print('FORMAL_REVISION_COMPLETE', n, manifest['tracking_action']['state_revision_after'])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['setup', 'pre', 'candidate', 'accept', 'finish', 'recover-written', 'commit-written'])
    parser.add_argument('chapter', type=int)
    args = parser.parse_args()
    {'setup': setup, 'pre': prewrite, 'candidate': make_candidate, 'accept': accept, 'finish': finish, 'recover-written': recover_written, 'commit-written': commit_written}[args.phase](args.chapter)

if __name__ == '__main__':
    main()
