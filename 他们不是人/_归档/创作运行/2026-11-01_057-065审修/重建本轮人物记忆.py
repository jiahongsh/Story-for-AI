import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / '追踪/_tracking-state.json'
STATE = json.loads(STATE_PATH.read_text(encoding='utf-8'))
assert STATE['state_revision'] == 261
OUT = ROOT / '创作运行/派生视图/2026-11-01_r261/本轮行动者'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

DETAILS = {
    '水果摊老板': ('卖菜、保住摊位和熟客；七块五只属未成交估计', '失客、蔬菜晒蔫和占位造成的生计损失', '能说明本人价目及经验，不能证明顾客必买；有放大机会损失的倾向，不能把估计作流水', 57, '她以前常买三把'),
    '裴亮': ('完成现场工作并弄清自己的扣款，寻实际负责人', '白跑后又被算作没到场、工钱无法说清', '可查本人工号群、扣款与付费页，可拨电话找人；不能改考勤，也不知道接缝及停供', 59, '三点五十以后我还在找陈工'),
    '郭老板': ('正常出餐、维护通道和生意', '食物落地、客人催闹及赔钱', '可以要求让路、承担本店损耗；沿用旧称呼而不懂接缝，忙时口气直接', 64, '挡着我上菜了'),
    '窗边老头': ('满足熟客社交与好奇，插话问两人为何生分', '被嫌多事、当众丢脸', '只见同桌关系和听惯的旧称呼；爱多嘴、越过私人边界，不具备身份异常知识', 64, '怎么还这么生分'),
    '孙立': ('保住父亲遗表、正常维修与独立原票，按本人利益办理号费', '零件被不明更换、售后说不清和额外支出', '只为本人表和票据争取，不是镜辞安排的调查者；075的六元退费已兑现，不能回退为仍未办成', 61, '我就怕零件换了'),
    '陈屿': ('可见行动是签现场单、索问观察结果及继续收尾；完整幕后欲望未知', '正文未充分披露其私人恐惧，不能由组织功能反造', '有公开项目负责人及恒准外包材料，但两家公司不合并；后台权限、真实主体与全目标图未知，后续新行动须另评七关', 65, '你不填，就有人填'),
    '当前存在': ('自己决定行程、称呼及新行动的归属，处理旧证件的现实限制', '被持续当成原芽的真假题、新行动又被抄回旧身份', '早期确曾模仿和撒谎；能拒绝、付款、买票和离开，不因本轮谈话获得正式新名或完整独立认证', 63, '人是我自己'),
    '猫眼': ('保全公开来源和版本，只交自己实际取得的材料', '被要求将未获准后台或添加人姓名写成已查明', '公开翻拍与旧快照有渠道限制，不能写成黑进上游；062的新版时间是08:20，旧11:20作废', 55, '我没进内部系统'),
    '唐宁': ('以本人旧识经历提供局部记忆，不替所有时期的芽或当前存在作证', '私人生活被变成通用身份题库；具体恐惧不从功能反造', '个体记忆不等于全知，对习惯起源的核验仍应回读069—070；不因本轮旁线获得额外知情', 69, None)
}

def body(n):
    found = list((ROOT / '正文').glob(f'第{n:03}章_*.md'))
    assert len(found) == 1
    return found[0]

def store(path, text, sources):
    path.parent.mkdir(parents=True, exist_ok=True)
    header = '# 来源绑定的辅助人物视图\n\n> r261，截至权威第099章；可重建，非第二正史。场景目标不是擅自推定人物在第099章时的内心。\n\n'
    tail = '\n\n## 来源指纹\n\n' + '\n'.join(f'- {p.relative_to(ROOT).as_posix()}｜{digest(p)}' for p in dict.fromkeys([STATE_PATH, *sources])) + '\n'
    path.write_text(header + text + tail, encoding='utf-8')

for name, (goal, fear, bounds, n, marker) in DETAILS.items():
    sources = []
    events = []
    for k in range(1, 100):
        record = ROOT / f'追踪/逐章记录/第{k:03}章.md'
        if not record.exists():
            continue
        text = record.read_text(encoding='utf-8')
        matches = [line for line in text.splitlines() if line.startswith(f'- {name}｜')]
        if matches:
            sources.append(record)
            events += [f'- 第{k:03}章｜{line[2:]}｜来源：{record.relative_to(ROOT).as_posix()}' for line in matches]
    formal = body(n)
    sources.append(formal)
    quote = None
    if marker:
        for i, line in enumerate(formal.read_text(encoding='utf-8').splitlines(), 1):
            if marker in line:
                quote = f'- {formal.relative_to(ROOT).as_posix()}:{i}｜{line}'
                events.append(f'- 第{n:03}章正文锚点（不推断缺失旧增量）｜{quote[2:]}')
                break
        assert quote, (name, marker)
    static = ROOT / f'设定/角色/{name}.md'
    static_line = '固定人格未建立独立静态卡；下列只记本轮有来源的目标、顾虑与边界，不补造未披露身世。'
    if static.exists():
        sources.append(static)
        static_line = f'固定设定见：{static.relative_to(ROOT).as_posix()}。其中作者秘密不自动授予角色。'
    card = f'# {name}｜本轮角色卡\n\n{static_line}\n\n- 独立生活目标/欲望：{goal}\n- 顾虑或未知：{fear}\n- 能力、权限与缺陷边界：{bounds}\n- 声线策略：优先依照实际话语锚点，不能把角色统一改成审核口吻；无锚点时回读静态卡和正文。\n- 个人时间线：时间线/{name}.md；只摘已提交记录与正文，不倒填旧章七关。\n\n## 实际话语/动作锚点\n\n' + (quote or '本轮未选定单句声线，不编造口头禅。')
    store(OUT / '角色卡' / f'{name}.md', card, sources)
    store(OUT / '时间线' / f'{name}.md', f'# {name}｜个人时间线\n\n' + ('\n'.join(events) if events else '缺少逐章人物增量，按正文锚点查证，不反造。'), sources)

index = '# r261人物记忆恢复入口\n\n先运行原追踪check，再读上下文。这个索引和人物视图不是正史；过期来源必须重建。\n\n'
index += '核心六人的当前卡和时间线见本版本目录的`作者/角色当前卡`及`作者/角色时间线`。\n\n'
index += '| 本轮行动者 | 角色卡 | 个人时间线 |\n|---|---|---|\n'
for name in DETAILS:
    index += f'| {name} | [角色卡](角色卡/{name}.md) | [时间线](时间线/{name}.md) |\n'
(OUT / '索引.md').write_text(index, encoding='utf-8')
print('19 actor-view files created; all bound to r261 and actual source hashes')
