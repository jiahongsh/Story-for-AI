from pathlib import Path
import json

source = Path(__file__).resolve().parents[1] / '2026-11-01_057-065审修/重建本轮人物记忆.py'
project = Path(__file__).resolve().parents[2]
revision = json.loads((project / '追踪/_tracking-state.json').read_text(encoding='utf-8'))['state_revision']
code = source.read_text(encoding='utf-8').replace('2026-11-01_r261', f'2026-11-02_r{revision}').replace('261', str(revision))
exec(compile(code, str(source), 'exec'))

# 限于本批实际出现、能定位的行动；不替未披露人物填完整生平。
extra = {
    '宁州陈骁': {
        'goal': '保住工厂工作、自己处理与父亲的门和关系争议。',
        'fear': '别人代开家门扩大冲突，工作补贴继续受损。',
        'bounds': '能视频和提供本人工厂材料，不能从宁州看见502屋内。原主和主体连续性仍未裁定。',
        'voice': '短句拒绝代办，明确本人位置；可与父亲争吵，不替物业认身份。',
        'nodes': [(50, '也别替我把门打开'), (71, '先扫了一眼活动室'), (73, '宁州发来一行')]
    },
    '杜经理': {
        'goal': '处理本人经办的复核和现场交接，保住没代开门、没点确认的可核依据。',
        'fear': '页面正常后由本人独担争议和责任；压力下反复要求别人核看。',
        'bounds': '能核工单、留日志并签药到活动室；不能因家庭字段代开502，也未建立物业保管502备用钥匙的事实。',
        'voice': '催人到场，强调活动室和别进502；怕担责可直说，不赋予制度之外的裁决权。',
        'nodes': [(70, '原定十八点那一档'), (71, '我留在这儿'), (73, '前次补核你们都在')]
    },
    '送药人': {
        'goal': '送达本次药物或说明未交付结果，避免药去向不明。',
        'fear': '未交到收货人却被算成签收；其私人生平、长期恐惧和缺陷未知，不从配送功能编造。',
        'bounds': '只知待送502、本人上楼敲门未应、带回活动室。不能从门外猫眼看门链；不知接缝、同步上游及屋内是否有人。',
        'voice': '只留配送现场短报告，不说身份判断。药12先挂，杜签暂存不是住户签收。',
        'nodes': [(73, '说敲了门，屋里没人回答')]
    },
    '侯强': {
        'goal': '争取当班工钱和补签，处理白跑后的交通及午饭。',
        'fear': '半日40不发且车费无人报；未及时看短信影响本人到场，不替他洗掉这一点。',
        'bounds': '只知本人通知、工牌、管事回复和开销；不认识镜辞，不知接缝。40未领加往返6是46，包子4及水1另记。镜辞、姜霁没有获知这本私账。',
        'voice': '先问卡怎么不开，再问能否补签；给家里说当日钱没了，不讲调查道理。',
        'nodes': [(75, '侯强八点二十才到'), (75, '两张票根都是三块'), (75, '这一块侯强没告诉任何人')]
    }
}
for name, detail in extra.items():
    sources, nodes = [], []
    for n, marker in detail['nodes']:
        formal = body(n)
        sources.append(formal)
        lines = formal.read_text(encoding='utf-8').splitlines()
        found = next((i, line) for i, line in enumerate(lines, 1) if marker in line)
        nodes.append(f'- 第{n:03}章｜{formal.relative_to(ROOT).as_posix()}:{found[0]}｜{found[1]}')
    card = f'# {name}｜本批角色短卡\n\n- 独立目标：{detail["goal"]}\n- 顾虑及缺陷边界：{detail["fear"]}\n- 可知与能力上限：{detail["bounds"]}\n- 声线：{detail["voice"]}\n- 个人时间线：../时间线/{name}.md。以下只是来源恢复，不伪造旧章写前审批。\n\n## 真实锚点\n\n' + '\n'.join(nodes)
    store(OUT / '角色卡' / f'{name}.md', card, sources)
    store(OUT / '时间线' / f'{name}.md', f'# {name}｜本批个人时间线\n\n只列以上来源中本人参与的节点；其他人的场外信息不能沿作者视角自动授予。\n\n' + '\n'.join(nodes), sources)
index_path = OUT / '索引.md'
index = index_path.read_text(encoding='utf-8')
index += '\n## 本批补齐的行动者\n\n| 人物 | 角色卡 | 个人时间线 |\n|---|---|---|\n'
for name in extra:
    index += f'| {name} | [角色卡](角色卡/{name}.md) | [时间线](时间线/{name}.md) |\n'
index_path.write_text(index, encoding='utf-8')
print(f'8 additional actor-view files created at r{revision}')
