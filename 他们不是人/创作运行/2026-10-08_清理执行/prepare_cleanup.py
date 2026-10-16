"""从只读备份按已确认C01—R10剪裁，先写候选，正文应用另行串行提交。
每个新段落是原段落的字符子序列，禁止增写故事词句。
"""
from pathlib import Path
import hashlib,json,re,difflib

HERE=Path(__file__).resolve().parent
BOOK=HERE.parents[1]
BACKUP=BOOK/'备份/2026-10-08_清理C01-R10'
EDITS={}

def cut(ch,line):
    EDITS.setdefault(ch,{})[line]=None

def trim(ch,line,*parts):
    EDITS.setdefault(ch,{})[line]=('remove',parts)

def keep(ch,line,text):
    EDITS.setdefault(ch,{})[line]=('keep',text)

# R05：保第一次真实同步、次日持续结果与新损失，不再三次点验同四项。
cut(71,47)
trim(71,57,'三笔不并。','她把白天的四样又读了一遍，读完把纸扣上。')
trim(71,59,'纸上四项还在，')
keep(73,19,'杜经理把复核那夜的副本和现在的屏幕并排。屏幕上写着正常。待可见性复核那一行找不着了。')
for line in [23,25,49,51]:cut(73,line)

# C02/C04：删除已经没有新选择的重复插曲。
for line in [89,91,93,95]:cut(54,line)
cut(63,83)

# C01：独立工作、工号拒绝与签注仍在；不逐步报仓内货物。
cut(53,51)
keep(53,55,'正午过后，配送站开始装车。马负责人多问了一句，档案里那个宁州工号还在不在。陈骁把工牌翻过来，只给看临江站的编号。')
cut(53,77)

# C03：无后续决策的菜筐/五毛岔出及次章回声。
cut(62,75);cut(62,77)
keep(63,121,'九点五十，镜辞的手机扣在柜台上，屏幕朝下。')

# R06：初次两家公司分别核证、新公示与来源保留。
cut(71,69);cut(73,31);cut(75,47)
trim(83,55,'，夹子仍用硬纸隔开恒准和恒泰','剥壳人三个字不写进任何一边。')

# R07：保费用构成、支付、票据和人的损失，不再演算已结账。
keep(59,51,'裴亮说这十一块晚饭够一碗面，面他不吃了，先把车还了。还车点在东口，晚还再加一块。他看了眼时间，四点五十五，还车截止写到五点。')
keep(59,59,'镜辞把这一笔写在十五点零二分那行的后面，字迹比刚才重。裴亮不知道接缝，也不知道谁停了供给。再另起一行：停止供给是我在十五点零二分写下的。页面十五点三十六改为待复核。裴亮十五点四十四看到群消息时人已经在西口。三件事挨着。挨着，不写成那行字扣了他的钱。')
keep(61,69,'抄完他洗手。洗油的味道还在指节上，蓝印的边角也还在。水凉得他指尖一缩。他洗到蓝印淡了，才回到柜台。')
cut(61,75);cut(61,77)
keep(61,79,'守钟人回后间，门掩上，镊子又响起来。没人跟进去。')
keep(75,79,'她把镊子放回原处，说三天的箱子完了。老秦在门外叠好空箱，隔着玻璃确认六十已付清，明天不用来。她应下来。')

# R08：保不回、一次边界表述、新名单来源，去轮流复述。
for line in [51,57,61,85,87,89]:cut(61,line)

# R09：去动作之后的说明接龙，不换一套身体动作填空。
trim(72,15,'，发紧是怕再滚进地缝')
trim(74,69,'擦掉是因为圈起来就像证物已经归她。','放下以后她没再比划第二遍。第二遍就会像在表演记得。')
keep(91,17,'她没有逼他再盯一轮，直到盯出点异常才交差。不逼的时候，镜辞胸口反而沉下去。')
keep(94,25,'他把那张薄卡按回桌上。按回时手心发热。')
keep(96,25,'镜辞点头。点头时把早年过整四个字写进私人本。写完他看向市场空出来的那条路。')

# R10：保存已有约定/新回复，删尾部事项复盘。
cut(59,77);cut(59,85)
keep(63,117,'他把私人本翻到新的一页。写：她指出先喝汤、缺口碗、耳后。')
for line in [123,125,127]:cut(63,line)
keep(66,73,'九点四十，镜辞把自己的副本夹好，腾出柜台；明日十八点的两项复核还在本子上。')
keep(75,69,'镜辞把侯强的四十六写在边栏。')
keep(75,75,'她应了一声。应的是自己的活做完了。')
cut(75,77)
keep(98,19,'夜里姜霁短讯：后五年关系后果单已建。两条并立，不许互删。明日若他来还管钳或别的，照常做生意。镜辞回：收。那只走慢的旧机械表还在周衡手里，第二天会不会送来，他不知道。')

def subsequence(old,new):
    it=iter(old)
    return all(any(c==x for c in it) for x in new)

manifest=[]
for n,ops in EDITS.items():
    p=next((BACKUP/'正文').glob(f'第{n:03d}章*.md'))
    original=p.read_text(encoding='utf-8-sig');lines=original.splitlines()
    details=[]
    for num,op in sorted(ops.items()):
        old=lines[num-1]
        assert old,(n,num)
        if op is None:new=''
        elif op[0]=='keep':new=op[1]
        else:
            new=old
            for part in op[1]:
                assert new.count(part)==1,(n,num,part)
                new=new.replace(part,'')
        assert subsequence(old,new),(n,num,'不是纯剪裁',old,new)
        lines[num-1]=new
        details.append({'original_line':num,'before':old,'after':new})
    # 单段消失后归并空行，不改剩余正文的句词。
    candidate=re.sub(r'\n{3,}','\n\n','\n'.join(lines)).rstrip()+'\n'
    target=HERE/'候选'/p.name;target.parent.mkdir(exist_ok=True);target.write_text(candidate,encoding='utf-8')
    diff=''.join(difflib.unified_diff(original.splitlines(keepends=True),candidate.splitlines(keepends=True),fromfile='修复前/'+p.name,tofile='清理后/'+p.name))
    (HERE/'候选'/f'{n:03d}.diff').write_text(diff,encoding='utf-8')
    manifest.append({'chapter':n,'file':f'正文/{p.name}','before_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'after_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'before_chars':len(original),'after_chars':len(candidate),'removed_chars':len(original)-len(candidate),'details':details})
(HERE/'剪裁明细.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'chapters':len(manifest),'removed_chars':sum(x['removed_chars'] for x in manifest),'all_edits':'deletion/subsequence only','candidates':[{'chapter':x['chapter'],'removed_chars':x['removed_chars']} for x in manifest]},ensure_ascii=False))
