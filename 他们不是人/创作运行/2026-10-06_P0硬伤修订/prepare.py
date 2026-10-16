from pathlib import Path
import json, hashlib, shutil

BOOK = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
BACKUP = BOOK / '备份/2026-10-06_P0硬伤修订'
CHAPTERS = [11, 56, 58, 65, 77, 94, 95]

REPAIRS = {
11: [('几天，半个月，最长一次撑了两个月，然后又停。', '有时一天，有时几天，最长一次撑了十一天，然后又停。')],
56: [
('格子左边那张旧照片还在，金属箱的焊疤、废料筐的位置都没被新页面吃掉。', '格子左边是北河老树的旧照片，外露金属旁的泥痕和基座上的油漆记号都还清楚。'),
('“旧照片还在。页面换了设备，换不掉你包里的底片。要是有人想把现场清干净，这一步还没做完。”', '“你包里的底片还在。设备换成什么样，得另找现在的记录。旧照片只记当时。”'),
('十七号的废料筐照片也在。新页面说设备已经换完，照片里的筐还占着原来的角落。姜霁把这张照片单独夹进“未清”那一叠，跟已经换完的页面错开。“清轨迹如果是他们的目标，旧照片还没被收走。我们手里这些，今天不动。”', '零三金属箱旁的废料筐照片也在，是此前复测时拍下的。镜辞把它摆在老码头那一格。姜霁在照片背面核过拍摄日期，夹进“旧存档”那一叠。“这张不能拿来证明筐今天还在那里。我们手里这一份，留着。”'),
('旧照片仍在，现场没有被清完。', '旧照片独立保存，当前现场状态未复查。')],
58: [
('镜辞把宁州那张工单照片在文件夹里按住，没有抽出来。照片角他认得，汽修厂，同事签名，地点不在临江。他的指节发紧，还是只把文件夹留在姜霁那侧。这张桌子给路过的人看杯，不给他们看别人的工号。', '镜辞按住文件夹里的取表监控截图，没有抽出来。那时柜台前的男人还穿着灰衬衫，取件单上写的是周远；合影胸牌上的陈屿是后来才对上的。他只把文件夹留在姜霁那侧，没让旁边桌的人看见截图。'),
('你问谁配叫周远，你自己店里有两个，结论栏到现在是空的。', '你不是已经见过两个周远了吗？结论栏到现在是空的。'),
('“宁州那个有厂里的工单，有同事，人在另一座城市。”镜辞说。他没有把宁州的工单照片掏出来，只用指节点了点文件夹的边。“临江这个也有自己的日子。两个都在过。结论那一栏，我到现在没填谁是原来的。”', '“你来取表那一分钟，宁州那个在公司开会，同事也在。”镜辞用指节点了点文件夹的边。“你这边的付款、签名、监控都留着。取件单写周远，五年前的工牌又写陈屿。你要我把哪一份当错的？”')],
65: [('南栏那句没发出去。', '南栏发过‘残余明显’，没给过‘通过’。')],
77: [
('你那天答应沈竹把表送去', '你那天答应客人把修好的表送去'),
('一行：沈竹，取表，已交。', '一行：送表，已交。'),
('守钟人在后间听见沈竹两个字，没出来。', '守钟人在后间听着，没出来。')],
94: [('那是071和075留下的尾巴。尾巴还在收口。', '那是安平里复核和南岸撤场以后留下的事，还没办完。')],
95: [('写完把照片扣回去。扣回去是怕自己为了卷势硬看出一条线。', '写完，他还想把照片放大，指尖落到耳后那块，又收了回来。图里那一小片皮肤已经糊了。他把照片扣回去。')]
}

OUTLINE_REPAIRS = {
77: [('镜辞那天已经答应沈竹送表', '沈竹早在镜辞十四岁时失踪；高二那天镜辞已答应客人送一只修好的表')],
94: [('这是071和075留下的尾巴，不是新谜底。', '这承接安平里复核和南岸撤场的未结事项，不是新谜底。正文只用事件回指，不写章节编号。')]
}
NOTES = {
11: '怀表取信前历次维修的最长连续走时统一为十一天，与第001章一致；不增加特殊例外，不提前揭开第012章止动结构。',
56: '北河十七号旧照片对应老树、外露金属、泥痕及基座油漆；金属箱焊疤和废料筐属于临江老码头零三。旧存档不能证明当前现场仍未清理。',
58: '公开谈话只追问双周远：临江取表的付款、签名、监控，对照宁州公司会议及同事来源；陈屿工牌另列。宁州汽修工单和两个各自生活的陈骁不混入这场问话。',
65: '镜辞在055发出“03南栏，残余明显。”，对方次晨回复“南栏没处理过。”。发送者和回复者分清；本章保存的是已发异常描述与未给认证的区别，不能写成短信未发送。',
77: '高二旧事保留。镜辞承担普通顾客的送表委托及婚礼怀表交付；沈竹十四岁时失踪的年份不改，守钟人不能听见本场没人说出的沈竹名字。',
94: '安平里复核与南岸撤场仅作故事内事件回指，不在正文引用071/075；十一份名单筛选与周衡弱时空相关保持不变。',
95: '照片未见接缝与低参考价值保持不变；镜辞忍住扩大图像硬找异常的冲动，通过动作表现，不引用“卷势”。'
}

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write_json(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

changed = []
baseline = {}
for n in CHAPTERS:
    prose = next((BOOK/'正文').glob(f'第{n:03d}章_*.md'))
    outline = BOOK/'大纲'/f'细纲_第{n:03d}章.md'
    for path in (prose, outline):
        rel = path.relative_to(BOOK).as_posix()
        dest = BACKUP/rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            raise RuntimeError(f'备份已存在，不重用旧运行: {dest}')
        shutil.copy2(path, dest)
        baseline[rel] = sha(path)
        changed.append(rel)
    content = prose.read_text(encoding='utf-8-sig')
    for old,new in REPAIRS[n]:
        if content.count(old) != 1:
            raise RuntimeError(f'{n}: 替换目标非唯一 {old}')
        content = content.replace(old,new)
    folder = WORK/f'第{n:03d}章'
    folder.mkdir(parents=True, exist_ok=True)
    (folder/'candidate.md').write_text(content, encoding='utf-8')
    text = outline.read_text(encoding='utf-8-sig')
    for old,new in OUTLINE_REPAIRS.get(n, []):
        if text.count(old)!=1: raise RuntimeError(f'细纲{n}: 替换目标非唯一')
        text=text.replace(old,new)
    text=text.rstrip()+'\n\n## 2026-10-06 P0连续性校正\n\n'+NOTES[n]+'\n'
    (folder/'outline.md').write_text(text, encoding='utf-8')

state = BOOK/'追踪/_tracking-state.json'
shutil.copy2(state, WORK/'修订前追踪快照.json')
baseline['追踪/_tracking-state.json'] = sha(state)
for n in range(100,104):
    p=next((BOOK/'正文').glob(f'第{n:03d}章_*.md'))
    baseline[p.relative_to(BOOK).as_posix()]=sha(p)
write_json(WORK/'基线哈希.json',baseline)
write_json(WORK/'修订计划.json',{
    'schema_version':1,'change_id':'p0-first-batch-20261006','summary':'按综合方案修复六组P0硬伤；仅七章正文及对应细纲，不扩写反制与能力，不改100—103',
    'semantic_change':True,'changed_files':changed,
    'affected_entities':['周远','陈骁','陈屿','沈竹','怀表','南栏','十七号','零三','周衡'],
    'affected_fact_ids':['K001','R001','K006','K007','K008','K009'],
    'affected_chapters':CHAPTERS})
print(json.dumps({'prepared':CHAPTERS,'source_files':len(changed),'formal_prose_changed':False},ensure_ascii=False))
