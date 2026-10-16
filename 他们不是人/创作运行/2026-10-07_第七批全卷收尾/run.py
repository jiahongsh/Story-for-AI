from pathlib import Path
import copy, hashlib, importlib.util, json, os, shutil, subprocess, sys

WORK=Path(__file__).resolve().parent
BOOK=WORK.parents[1]
TOOLS=BOOK.parent/'skills/story-long-write/scripts'
STATE=BOOK/'追踪/_tracking-state.json'
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,x):
    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def run(*args):
    r=subprocess.run(list(map(str,args)),capture_output=True,text=True,encoding='utf-8',errors='replace',env={**os.environ,'PYTHONUTF8':'1'})
    if r.returncode: raise RuntimeError(r.stdout+r.stderr)
    try: return json.loads(r.stdout)
    except json.JSONDecodeError: return {'output':r.stdout}
def prose(ch): return next((BOOK/'正文').glob(f'第{ch:03d}章_*.md'))
def replace(text,old,new,count=1):
    assert text.count(old)==count,(old,text.count(old)); return text.replace(old,new)
def remove_prefix(text,*prefixes):
    paragraphs=text.split('\n\n')
    for prefix in prefixes:
        hits=[i for i,p in enumerate(paragraphs) if p.startswith(prefix)]
        assert len(hits)==1,(prefix,len(hits)); paragraphs.pop(hits[0])
    return '\n\n'.join(paragraphs)

EDITS={
51:[('十九点十二分，家庭成员凭证尝试开启单元门，操作人是杜经理的当值工号。','十九点十二分，家庭成员凭证尝试开启单元门；随后拦截记录的操作人，是杜经理的当值工号。')],
53:[('上午十一点，配送站排班群里','上午十一点过后，配送站排班群里')],
55:[('同一个人为什么一边有五年工牌，一边用过周远的身份，这页还空着。','同一张脸为什么出现在五年前的陈屿合影里，又用过周远的身份来取表，这页还空着。')],
56:[('因为后面还有两小时不能摆。','因为明早还有三小时不能在原处摆。')],
57:[('笔帽仍扣着，他只是先把数字落下。','他拔下笔帽，先把数字落下。'),('这种高度是一起干出来的。当场现背的人递不准。','两人的手没有相互碰撞；姜霁把这次配合记下，三年的说法仍待别的来源核对。'),('临时来背流程的人，不会让同事先按自己的旧话扣掉十五块。','去年那条群消息和今天的签到都留着。共事多久，还得另核。')],
58:[('取件单写周远，五年前的工牌又写陈屿。','取件单写周远，五年前合影里的胸牌又写陈屿。')],
60:[('表针停在九点十二，和墙上的钟差了大约四分钟','表针停在九点十四，和墙上的钟差了大约四分钟'),('上午那页还写着未见，不可反用。','前次观察那页还写着未见，不可反用。')],
62:[('十一点二十','八点二十',3)],
63:[('他把时长写在六块旁边，不写结论。','他把六块记在票价旁边，不写结论。'),('镜辞看着通话时长，四分二十秒。','镜辞看着已经结束的通话。'),('今天不赶晚班。晚班从十点才算，我来得及。','今天换早班，十点才开门，我来得及。'),('她说晚班十点开门','她说早班十点开门'),('她把表放上台面，石英的，后盖松。镜辞旋开，电池仓是干的，秒轮旁的油发黏。','她把表放上台面，是一只机械表，后盖松。镜辞旋开，机芯里没有进水，秒轮旁的油发黏。'),('她数了十五块，一张十块，一张五块。五块是硬币，滚了一颗到尺边。','她数了十五块，一张十块，五枚一块硬币。硬币滚了一枚到尺边。')],
67:[('这七个字','这行字'),('同样七个字','同样的字')],
71:[('楼道口的防盗门上，门链反着一点光，链还挂着。','工单上另记着502的门链状态：仍挂着。'),('陈启明没下来。声音从门里出来，又闷又冲。','陈启明没下来。他给杜经理的答复仍是：')],
73:[('门链从楼梯缝里还能看见一点光。链没摘。','杜经理的交接页上记着：502门链未摘。'),('陈启明没下来。门里一句：','陈启明没下来，交接页上仍留着他那句：'),('姜霁拍给它。','姜霁拍给她。')],
81:[('铝管','金属提把',3),('费力才像一场控制，不像一段表演。','警察再次核对约束，没人撤离岗位。')],
82:[('下一次的定义她没展开。展开会把条件提前谈完。','她让镜辞把号码收好，具体使用条件回店再核。'),('具体的条款她没念。念了就会把下一场的边界提前用完。','具体条款还得双方逐项确认，她没有把这张说明算成镜辞已经同意。')],
83:[('药盒铁片说明她出门还想着拿药。拿药和不敢回家叠在一起，比一句说不清的直觉更沉。','他记住那枚铁片，等她自己说为什么拿着这把钥匙。')],
86:[('两年前的家庭短视频','历年的家庭短视频'),('他们在钟表行后间支起一块小屏。','他们在钟表行柜台侧桌支起一块小屏，屏幕背向店门。'),('普通解释无法覆盖失联后集中出现','现有普通解释尚不能覆盖失联后集中出现')],
89:[('放音机','收音机')],
92:[('散会后，姜霁再核了一遍撤点交接','姜霁再核了一遍撤点交接')],
}

def make_candidates():
    candidates={}; changes=[]
    for ch,edits in EDITS.items():
        p=prose(ch); text=p.read_text(encoding='utf-8-sig')
        for edit in edits: text=replace(text,*edit)
        candidates[ch]=text; changes.append({'chapter':ch,'kind':'知情/动作/时间/来源冲突','before':sha(p)})
    for ch in (53,59,64,65,70,75,82,84,85,90):
        p=prose(ch); text=candidates.get(ch,p.read_text(encoding='utf-8-sig'))
        if ch==53:
            text=remove_prefix(text,'镜辞把手机扣上。扣款通知和停单附页仍分在两个信封里。茶凉了')
            text+='\n\n姜霁定了晚上七点的提醒：看调度。三条待查项仍空着，私人本里的旧司机观察没有涂改。镜辞倒掉凉茶，回到待修盘前。\n'
        if ch==59:
            text=remove_prefix(text,'五点四十五，又有人在卷帘外停了一下','他没有追出去问。手机仍然屏朝下。')
        if ch==64:
            text=remove_prefix(text,'十二号嫌包子皮破了','姜霁把豆浆杯子扣下','郭老板在他们走到门口时又喊了一声芽')
        if ch==65:
            text=remove_prefix(text,'灯还开着。卷帘留一条缝，缝外有人收摊')
        if ch==70:
            text=remove_prefix(text,'她又看了眼碗。两口之后','镜辞看着勺柄，没把它当成记号。','巷口的小巴还要六分钟。')
        if ch==75:
            # 保留独立人物后果，将中午/午后材料放回当天晚饭之前。
            paragraphs=text.split('\n\n'); start=next(i for i,p in enumerate(paragraphs) if p.startswith('中午镜辞没去东口。'))
            end=next(i for i,p in enumerate(paragraphs) if p.startswith('灯还开着。坑位上的新锁'))
            block=paragraphs[start:end]; del paragraphs[start:end]
            destination=next(i for i,p in enumerate(paragraphs) if p.startswith('她下午把第三箱过完。'))
            paragraphs[destination:destination]=block; text='\n\n'.join(paragraphs)
            text=remove_prefix(text,'陈工的车过市场时没停。','她把今天的八格数字写在一张纸上','侯强的未读短信她没看见。','座钟走着。人留在店里。')
            paragraphs=text.split('\n\n')
            midday=[p for p in paragraphs if p.startswith(('侯强中午在站牌边','侯强第二趟下车的站'))]
            assert len(midday)==2
            paragraphs=[p for p in paragraphs if p not in midday]
            at=next(i for i,p in enumerate(paragraphs) if p.startswith('下午两点，猫眼'))
            paragraphs[at:at]=midday; text='\n\n'.join(paragraphs)
        if ch==82:
            text=remove_prefix(text,'灯还开着。剥壳人三个字第一次落在他听见的空气里。','他把薄纸放在箱盖旁边。')
        if ch==84:
            text=remove_prefix(text,'未知两个字在纸上发干。','镜辞跟在后面。跟的时候耳后那道接缝还在记忆里发烫。')
        if ch==85:
            text=remove_prefix(text,'验证方法四个字停在屏幕上。')
        if ch==90:
            text=remove_prefix(text,'挂断以后，观察口外的灯暗了一档。')
        candidates[ch]=text; changes.append({'chapter':ch,'kind':'重复解释/尾声与时序压缩','before':sha(p)})
    for ch,text in candidates.items():
        p=WORK/'候选'/prose(ch).name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text,encoding='utf-8')
    return candidates,changes

def prepare():
    assert read(STATE)['state_revision']==175
    candidates,changes=make_candidates()
    write(WORK/'baseline.json',read(STATE)); write(WORK/'正文改动清单.json',changes)
    write(WORK/'baseline_hashes.json',{p.relative_to(BOOK).as_posix():sha(p) for p in (BOOK/'正文').glob('*.md')})
    master=BOOK/'大纲/伏笔总表.md'; text=master.read_text(encoding='utf-8-sig')
    text=text.replace('**F05、F06、F07、F08、F10、F12尚未逐条核对012—050**，在完成核对前不得直接引用它们对该区间的结论。','**F05、F06、F07、F08、F10、F12已逐条核对001—099及100—103只读接口：均未埋。**这些条目按原计划在后续卷铺设，第一卷不伪造首埋或强行补终局答案。')
    text=text.replace('F05—F08、F10、F12的首埋核对','F05—F08、F10、F12的后续卷规划执行')
    for ident in ('F05','F06','F07','F08','F10','F12'):
        start=text.index('## '+ident+'｜'); end=text.index('\n---',start)
        section=text[start:end]
        section=section.replace('- **实际状态**：未埋。','- **实际状态**：已核，未埋。\n- **第一卷核验（2026-10-07）**：001—099及100—103只读接口没有该条指定凭证/人物习惯的首次呈现。普通版本保存、有限同意或现场救援不冒充本条首埋；不新建“已埋”的TRACK行。按上述后续卷生命周期继承。')
        text=text[:start]+section+text[end:]
    text+='\n## 第一卷本次记忆闭环补充（2026-10-07）\n\nF01在071/073再次覆盖，088首次保住本案拆分后的住宅通行限制；这是局部操作结果，不解释上游，也不保证其他系统都可如此处理。F09在066—079落实证件成本、修锁/工作后果、旧友拒绝、具体道歉与离开；TRACK F051记录长线推进，F015—F028分别只回收各章局部承诺。已回收的局部钩子不能写成主体身份已解决。\n'
    (WORK/'候选_伏笔总表.md').write_text(text,encoding='utf-8')
    changed=[prose(ch).relative_to(BOOK).as_posix() for ch in candidates]+['大纲/伏笔总表.md']
    # 每章细纲同步具体修正与当前记忆边界。
    for ch in candidates:
        p=BOOK/f'大纲/细纲_第{ch:03d}章.md'; assert p.exists()
        outline=p.read_text(encoding='utf-8-sig')
        if ch==62: outline=outline.replace('11:20','08:20').replace('十一点二十','八点二十')
        outline+='\n\n## 2026-10-07收尾校正\n\n本章本轮只按已接纳正文修正时间、来源、物件动作或重复尾声，身份结论和能力上限不变。活动正文与同章历史修订记录共同作为续写来源，不将删去的重复解释重新扩为新行动。\n'
        if ch==62: outline+='推荐页新版为当天08:20，先于孙立09:40首次到店；11:20旧口径作废。退号费仍凭维修票，次日09:00撤推荐。\n'
        if ch==63: outline+='早班10:00；蓝拖鞋客的表为机械表，使用快慢针；15元为10元纸币加五枚1元硬币。\n'
        if ch in (71,73): outline+='502门链状态来自工单/交接页和住户答复，不写从一楼越过楼梯直接看到五楼门链。\n'
        dest=WORK/'候选细纲'/p.name; dest.parent.mkdir(exist_ok=True); dest.write_text(outline,encoding='utf-8'); changed.append(p.relative_to(BOOK).as_posix())
    plan={'schema_version':1,'change_id':'seventh-final-volume-20261007','summary':'依次闭合六条未来伏笔核验、051—095残留时空/来源/动作冲突及重复尾声，补长线阶段记忆','semantic_change':True,'changed_files':changed,'affected_entities':['镜辞','姜霁','当前存在','陈屿','孙立','猫眼','陈启明','杜经理','张岚','老李'],'affected_fact_ids':['K005'],'affected_chapters':sorted(set(candidates)|{66,68,69,72,74,76,77,78,79,88})}
    write(WORK/'plan.json',plan)
    run(sys.executable,TOOLS/'revision_guard.py','plan','--project',BOOK,'--input',WORK/'plan.json','--output',WORK/'manifest_pre.json')
    gates={}
    for ch in sorted(candidates):
        p=WORK/'候选'/prose(ch).name; gates[ch]={}
        for name,flags in (('language_gate.js',[]),('check-style-hygiene.js',['--check','--fail-on=blocking']),('check-ai-patterns.js',['--check','--fail-on=blocking']),('check-degeneration.js',['--check','--language=zh','--fail-on=blocking'])):
            gates[ch][name]=run('node',TOOLS/name,*flags,p)
    write(WORK/'候选四门.json',gates)
    # 两处锁定章的纯文字冲突先准备可审候选，等明确解锁再写正式文件。
    locked={102:('两套完整的十一月。','两套完整的十一个月。'),103:('妹妹托管给自己的备用钥匙','姐姐托管给自己的备用钥匙')}
    for ch,(old,new) in locked.items():
        p=WORK/'锁定章待批准'/prose(ch).name; p.parent.mkdir(exist_ok=True)
        text=replace(prose(ch).read_text(encoding='utf-8-sig'),old,new)
        if ch==102:
            text=text.replace('这些不是“结婚纪念日是哪天”那种可以提前背下来的题。','水壶、窗户、摔倒、旧车，每件都牵着日常。')
            text=text.replace('而镜辞已经开始怀疑，真正麻烦的可能根本不是哪一边全假。\n\n是两边都留下了东西。','镜辞看着两摞材料，最难解的地方还在：两边都留下了东西。')
        if ch==103:
            text=text.replace('不是因为纸天然高贵。\n\n只是因为它没和所有东西绑在同一根线上。','纸没和所有东西绑在同一根线上，这才让它留下了另一个版本。')
        p.write_text(text,encoding='utf-8')
        for name,flags in (('language_gate.js',[]),('check-style-hygiene.js',['--check','--fail-on=blocking']),('check-ai-patterns.js',['--check','--fail-on=blocking']),('check-degeneration.js',['--check','--language=zh','--fail-on=blocking'])):
            run('node',TOOLS/name,*flags,p)
    print(json.dumps({'status':'prepared','prose_chapters':len(candidates),'language_checks':len(candidates)*4,'locked_candidates':[102,103]}))

if __name__=='__main__': prepare()
