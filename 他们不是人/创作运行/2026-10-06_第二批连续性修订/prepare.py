from pathlib import Path
import json, hashlib, shutil, difflib, re

BOOK=Path(__file__).resolve().parents[2]
WORK=Path(__file__).resolve().parent
NUMBERS=[52,70,72,73,74,75,76,77,78,79,82,83,96]
BACK=BOOK/'备份/2026-10-06_第二批连续性修订'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,data):p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def prose(n):return next((BOOK/'正文').glob(f'第{n:03d}章_*.md'))
def replace(text,old,new):
    assert text.count(old)==1,(old,text.count(old))
    return text.replace(old,new)

def revise(n,text):
    if n==52:
        text=replace(text,'她在胶纸上签了时间：八点五十六。','她在胶纸上签了时间：九点十六。')
        text=replace(text,'药已经由邻居送进去了，这件事别写进陈骁的账户。','药早上已经由邻居送进去了，这件事别写进陈骁的账户。')
        text=replace(text,'对方在群里问了两次门禁，箱子十点五十五还停在院门口。','对方在群里问了两次门禁。')
        text=replace(text,'家属后来在群里骂了一句晚了，点名骂的是站里改派。','')
        para=next(p for p in text.split('\n\n') if p.startswith('康复楼那箱药最后是新手送到的。'))
        text=replace(text,para+'\n\n','')
        marker='回到钟表行，墙上的钟走到十点五十七。'
        text=replace(text,marker,marker+'配送群里留着新手两分钟前发的消息：箱子还在院门口，正在找三号床的家属。')
        marker='两条日子都在往前长，账户只肯给它们一个名字。'
        para=para.replace('家属在群里发了一张','十一点零六，家属在群里发了一张')
        para=para.replace('马负责人只回了句','家属骂了一句晚了，点名骂的是站里改派。马负责人只回了句')
        text=replace(text,marker,para+'\n\n'+marker)
    elif n==70:
        text=replace(text,'他在私人本上只写了四个字的位置，写到一半划掉。划掉的是先喝汤。','他在私人本上写下先喝汤，随即划掉。')
        text=replace(text,'她打了六个字，打完又删掉。删掉的是：我知道。','她打出一句，又删掉：我知道。')
        text=replace(text,'半碗汤凉了一点，她又喝了一口，这一口仍是因为胃，喝完把勺横在碗上。','半碗汤凉了一点。她捧了一会儿，没再喝，把勺横在碗上。')
    elif n==72:
        text=replace(text,'笔是老秦的。纸两分，他说明天从六十里扣，今天先欠着。两分还没扣。','笔是老秦的。标签纸也在箱盖下，他抽出一张递给她，让她把掉下来的旧标签一起收好。')
        text=replace(text,'老秦数钱。六十，全是十块的纸币，六张。他付的时候笔悬在账本上。','老秦在六十下面划掉午饭预支的两块，数出五十八。他付的时候笔悬在账本上。')
        text=replace(text,'写完把六十推过来。','写完把五十八推过来。')
        text=replace(text,'她把六张纸币点完，抽出一张十块，','她把纸币和零钱点完，抽出一张十块，')
        text=text.replace('五十','四十八')
        # 上面的通用余额替换不应改实领五十八。
        text=text.replace('四十八八','五十八')
        text=replace(text,'姜霁只记：六十已付。','姜霁只记：工钱六十结清，午饭预支两块，实领五十八。')
    elif n==73:
        text=re.sub(r'(?<!点)五十','四十八',text)
    elif n==74:
        text=text.replace('五十','四十八').replace('四十二','四十')
    elif n==75:
        old='点完她把六十和前两天的钱仍分口袋。今天这六十单独一沓。前两天的五十加六十，她还没并成一捆。并成一捆是以后的事。今天下午她没问陈工是谁。'
        new='点完她去隔壁买了一副手套，八块。指甲缝里的油泥还没洗净，她试了试，指尖能弯，才付钱。今天的六十剩五十二。前两天剩下的四十和六十还在另一个口袋，她没并成一捆。手套装进包里，明天换一处干活也能用。'
        text=replace(text,old,new)
        text=replace(text,'应完她把今天的六十按进单独的口袋。','应完她把今天剩下的五十二按进单独的口袋。')
    elif n==76:
        paras=text.split('\n\n')
        text=replace(text,paras[1], '晚上七点，她把三天剩下的钱摊在柜台上。第一天的工钱扣了午饭预支，还了夜车垫款，又出了城北往返的票钱，剩四十。第二天六十。第三天买过手套，剩五十二。合起来一百五十二。')
        text=replace(text,paras[2], '她把零钱也拨进去，点了一遍。车票和手套收据放在旁边，那些钱已经花出去了，不能再数一次。镜辞在修一只表，换电池十二块，客人等着；那笔钱仍进修理抽屉。她把自己的钱拢好，留在手边。')
        text=text.replace('一百七十','一百五十二').replace('一百六十二','一百四十四')
        text=replace(text,'“工钱在我这两天的手上。','“工钱在我这三天的手上。')
        last=next(p for p in text.split('\n\n') if p.startswith('一百四十四她最后又默数了一遍。'))
        text=replace(text,last,'她按住信封口，没再数。背面那两行还在本子里，跟钱一起由她带着。镜辞没有替她划掉，也没有说算了。')
    elif n==77:
        text=text.replace('一百六十二','一百四十四').replace('一百六十','一百四十二')
        text=replace(text,'一百四十四减二等于一百四十二','一百四十四减二等于一百四十二')
    elif n==78:
        text=text.replace('一百六十','一百四十二').replace('一百四十二。证件','一百二十四。证件')
        text=replace(text,'姜霁核对十八和一百四十二。','姜霁核对十八和一百二十四。')
        text=text.replace('一百四十','一百二十二')
        # 初始一百四十二被前缀替换误吞，必须还原为142；124不受影响。
        text=text.replace('一百二十二二','一百四十二')
    elif n==79:
        text=text.replace('一百四十','一百二十二')
    elif n==82:
        text=replace(text,'一百四十在她那边。','她的信封由她自己带着。')
        text=replace(text,'不从她的一百四十里出。一百四十仍在北河方向。','不从她的信封里出。她往北河去了，信封也跟着走。')
        text=replace(text,'章没完的是条件。','没谈完的是合作条件。')
    elif n==83:
        text=replace(text,'一百四十还在北河方向，方向上仍只有一个在。','她带着自己的信封往北河去了，对话框里仍只有一个在。')
    elif n==96:
        text=replace(text,'本子上只落四个字：未见基础接缝。','本子上只落一句：未见基础接缝。')
        text=replace(text,'挂断以后，姜霁在听筒外落笔。','听筒里传来姜霁落笔的声音。')
    return text

NOTES={
52:'九点到店后九点十六封口。回店十点五十七时只知十点五十五滞留；十一点扣款与十一点零六送到依次发生。送药明确为早上已经完成。',
70:'不机械报我知道/先喝汤字数。实际喝两口，之后捧碗未喝再换白开；不可又出现第三口。',
72:'午饭两元为工资预支，结清六十工资时实领五十八，还夜车十后余四十八。标签纸为摊上耗材，不另设两分钱待扣。',
73:'本章当前存在持有首日净余四十八，不是五十；现场各人的其他损失不变。',
74:'初始四十八，往返各四元后首日余四十；第二天六十工钱另存，不算原芽的功劳。',
75:'第三天实付六十，随后本人花八元买手套，第三日现金余五十二；前两日余四十及六十，三天合计净现金152。工作结束不延长。',
76:'三天毛工资180，扣已付午饭2、还款10、往返8、手套8后现金152；晚饭8后144。承认模仿的责任，不拿钱换原谅。',
77:'继承144现金，晚饼2后142。高二的十三及四十属于旧事，不加入当前余额；前批普通客人送表修订保留。',
78:'初始142，车票18后124，回店公交2后122；买票仍本人决定，不新增批准或身份解决。',
79:'继承122现金。手套八元已在075买过，不重复扣；122只记此刻，不预断离开后的余额。',
82:'镜辞只知她携自己信封离开，不能隔空知道北河途中余额；自己的饭钱仍自己出。正文以合作条件未谈完表述，不写章没完。',
83:'只回指她已带信封离开，不断言离开后的精确余额；合作仍由镜辞本人签，不拉她回来代担条款。',
96:'正文不报告未见基础接缝字数；姜霁在电话未挂断时记结果，再结束通话。未见与100首缝保持相容。'}

state=BOOK/'追踪/_tracking-state.json'
assert read(state)['state_revision']==50
shutil.copy2(state,WORK/'修订前追踪快照.json')
for name in ['active.json','active.approved.json']:
    shutil.copy2(BOOK/'追踪/修改影响'/name,WORK/('前批_'+name))
changed=[];hashes={};diff=[]
for n in NUMBERS:
    folder=WORK/f'第{n:03d}章';folder.mkdir(parents=True,exist_ok=True)
    p=prose(n);outline=BOOK/f'大纲/细纲_第{n:03d}章.md'
    for src in [p,outline]:
        rel=src.relative_to(BOOK).as_posix();dest=BACK/rel
        assert not dest.exists(),dest
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
        changed.append(rel);hashes[rel]=hashlib.sha256(src.read_bytes()).hexdigest()
    text=p.read_text(encoding='utf-8-sig');new=revise(n,text)
    assert text!=new,n
    (folder/'candidate.md').write_text(new,encoding='utf-8')
    (folder/'outline.md').write_text(outline.read_text(encoding='utf-8-sig').rstrip()+'\n\n## 2026-10-06 第二批连续性校正\n\n'+NOTES[n]+'\n',encoding='utf-8')
    diff+=list(difflib.unified_diff(text.splitlines(),new.splitlines(),fromfile=p.name,tofile=f'修订/{p.name}',n=2))
for n in range(100,104):
    p=prose(n);hashes[p.relative_to(BOOK).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
write(WORK/'基线哈希.json',hashes)
write(WORK/'修订计划.json',{'schema_version':1,'change_id':'continuity-second-batch-20261006',
      'summary':'修052时间、072—079净现金链、070两口汤及计数、096计数与通话顺序；保留前批修复及锁定100—103',
      'semantic_change':True,'changed_files':changed,'affected_chapters':NUMBERS,
      'affected_entities':['镜辞','姜霁','当前存在','老秦','猫眼','陈骁','手套'],
      'affected_fact_ids':['K007','K010']})
(WORK/'候选差异.diff').write_text('\n'.join(diff),encoding='utf-8')
print(json.dumps({'prepared_chapters':NUMBERS,'source_files':len(changed),'formal_prose_changed':False},ensure_ascii=False))
