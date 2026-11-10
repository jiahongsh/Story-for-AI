from pathlib import Path
import json,shutil,hashlib,subprocess,sys,os
BOOK=Path(__file__).resolve().parents[2];WORK=Path(__file__).resolve().parent
NUMBERS=[55,61,62,65,75]; BACK=BOOK/'备份/2026-10-06_第三批反调查闭环'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def prose(n):return next((BOOK/'正文').glob(f'第{n:03d}章_*.md'))
def rep(s,a,b):
    assert s.count(a)==1,(a,s.count(a));return s.replace(a,b)
changes=[];hashes={}
assert read(BOOK/'追踪/_tracking-state.json')['state_revision']==63
shutil.copy2(BOOK/'追踪/_tracking-state.json',WORK/'修订前追踪快照.json')
for f in ['active.json','active.approved.json']:shutil.copy2(BOOK/'追踪/修改影响'/f,WORK/('前批_'+f))
for n in NUMBERS:
    for p in [prose(n),BOOK/f'大纲/细纲_第{n:03d}章.md']:
        rel=p.relative_to(BOOK).as_posix();d=BACK/rel;assert not d.exists();d.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,d);changes.append(rel);hashes[rel]=hashlib.sha256(p.read_bytes()).hexdigest()
for n in range(100,104):p=prose(n);hashes[p.relative_to(BOOK).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
write(WORK/'基线哈希.json',hashes)
plan={'schema_version':1,'change_id':'counter-investigation-third-batch-20261006','summary':'055渠道代价、061限定维修原件、062拒盖推荐页而补维修盖章、065本人保票、075退费付息；不改变维护链收尾',
      'semantic_change':True,'changed_files':changes,'affected_chapters':NUMBERS,'affected_entities':['镜辞','姜霁','孙立','陈屿','打印店','维修单'],'affected_fact_ids':['K004','K005','K011']}
write(WORK/'修订计划.json',plan)
r=subprocess.run([sys.executable,'-X','utf8',str(BOOK.parent/'skills/story-long-write/scripts/revision_guard.py'),'plan','--project',str(BOOK),'--input',str(WORK/'修订计划.json'),'--output',str(BOOK/'追踪/修改影响/active.json')],capture_output=True,text=True,encoding='utf-8')
assert r.returncode==0,r.stderr
manifest=read(BOOK/'追踪/修改影响/active.json')
index=[]
for rel in manifest['required_checks']:
    p=BOOK/rel;t=p.read_text(encoding='utf-8-sig');index.append({'path':rel,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'scope':'维修单、孙立、退费、打印渠道及直接回指','lines':len(t.splitlines())})
write(WORK/'写前依赖索引.json',index)
write(WORK/'写前冻结.json',{'mode':'historical-local-revision-manual','state_revision':63,'status':'manual_pass','reviewer':'Codex /root solo/direct',
      'source_hashes':hashes,'decision_path':'写前人物七关.md','decision_sha256':hashlib.sha256((WORK/'写前人物七关.md').read_bytes()).hexdigest(),
      'limit':'仅受影响选择；不冒称新章world_gate机器接纳或旧章原写作许可'})
NOTES={55:'完成已答应的当天出纸，打印店老板其后拒绝继续定时拉页；仍可有偿印传来文件。渠道代价不算幕后认证。',
61:'孙立手持已收过定金小票到店，不重复持有待修盘里的表。实付补款25以20+2+2+1组成。维修原票签项目与45价款，底联留店；陈屿没看出来短信只引起信息泄露怀疑，不能当已证实全知。',
62:'店章盖真实维修票，不盖推荐名单；号费6退否由窗口判断。孙立为自己的退费和售后争取原票，不被主角征为调查者。名单撤下仍次日九点生效。',
65:'保留三行拒填。孙立本人确认原票在钱包，拒交原件换另联，镜辞留底联；这份独立来源只支持维修范围。当前存在薄本与后日复核不变。',
75:'维护链仍独立撤柜、侯强仍损失46。孙立回述按维修项目和店章退6，窗口留副本、本人留原票；局部成果兑现，不证明身份或幕后。第三批不更改前批工资及手套余额。'}
for n in NUMBERS:
    s=prose(n).read_text(encoding='utf-8-sig')
    if n==55:
        marker='陌生号码安静到第二天清晨。'
        s=rep(s,marker,'清晨进纸前，打印店老板又来了一条语音：“昨天答应的都出了。今天别再让我两小时刷一次。你把文件发来，我印；进纸的车我得自己跟。”镜辞把已经设好的下一轮提醒删掉，没有再拿九块运费跟他商量。\n\n'+marker)
    if n==61:
        s=rep(s,'慢表捏在手里，每隔几秒抬起来看一眼，又放下。','定金小票捏在手里，他隔着卷帘看了几次墙上的钟。')
        s=rep(s,'一张二十，一张五。五块是两张两块和一张一块。','一张二十，两张两块和一张一块。')
        marker='孙立出门，肩膀这次没有碰卷帘。'
        s=rep(s,marker,'镜辞把维修小票写完整：机械表，油干处理，走时正常，工钱四十五。末尾签了自己的名字，底联留店，原票递给孙立。\n\n“这块表的事，我认。票留好，再慢了拿来。”\n\n孙立先看了油干和四十五，才把票折进钱包。“我就怕零件换了，回头说不清。这张我留着。”\n\n'+marker)
        s=rep(s,'四个字说明两件事：陈屿知道孙立会来，也知道镜辞看过那张脸。看的动作被读走了。','镜辞先想到的是：陈屿知道孙立来过，还在等他的观察结果。他盯着那句问话，找不到是谁告诉陈屿的。也可能对方只是拿这句话试他。')
        s=rep(s,'通知已经发生，字在屏幕上。','短信已经到，谁提供过什么消息，仍没有来源。')
        s=rep(s,'不可当成没被看见。','不能据此断定消息从谁那里来。')
        s=rep(s,'陈屿知道你看了。','陈屿发了问话，消息来源还没对上。')
    if n==62:
        s=rep(s,'这枚只证明店在。退费那一栏，得窗口自己的章。','我只给店里经手的维修单盖。你这张是推荐名单，表的问题、工钱都没写，不能在它上面盖。退费那一栏，得窗口自己认。')
        s=rep(s,'“六块还在他们的规矩里。”镜辞说，“我盖上去，窗口可以不认。你白盖一次，店多一个不该有的印。”','“你带来的维修票，油干、四十五，都对得上。”镜辞说，“我给那张盖章。拿它问窗口，六块退不退，让他们当面说。名单我不盖。”\n\n孙立把钱包里那张抽出来，折痕还在。“行。票给我留着。他们要收，就复印一份。表以后慢了，我还要凭它找你。”\n\n镜辞对过底联，在维修票角上盖了店章。孙立等印泥干了才收回去，没有把推荐名单推过来。')
        s=rep(s,'六块硬币他单独装进上衣袋，拉链拉到头，怕和公交的两块混在一起。','六块的号费收据他单独装进上衣袋，拉链拉到头，怕和公交的票根混在一起。')
    if n==65:
        marker='五点差十分，南岸方向的天色暗了一点。'
        s=rep(s,marker,'打印店回来，镜辞把孙立的底联放在那两张拒填的照片旁边，给维修单上的号码发了一句：你那张原票还在吗？只记修表的四十五，别换成别的结论。\n\n孙立回得很短：“在钱包。窗口要留，我给复印件。那张票我还要找你保修。其他资料我不加签。”又来一条：“六块我自己去问，你别替我跑。”\n\n镜辞回了好，没有追问他的脸，也没有问班车去哪里。他把这两条存到维修底联的袋子里。姜霁核过号码，只在袋边写：原票由孙立自留，店内留底。这一次她没把两份原件都收进自己的夹子。\n\n'+marker)
    if n==75:
        marker='灯还开着。坑位上的新锁在照片里。照片在猫眼那儿。店里没有一句通过。'
        s=rep(s,marker,'午后孙立发来一张号费收据，六块那一栏盖着已退。他说窗口核了维修项目和店章，留下复印件，没有收走原票。“要我另签资料那页，我没签。我来退修表的号费，不是再办一遍资料。票还在我钱包。”\n\n镜辞把回复同底联核在一起。油干处理，走时正常，四十五；那张票上仍只有表的事。他把新消息存好，没向孙立要原件，也没再发一个问题。东口柜子撤走的照片留在另一页，没拿六块退费去销侯强的四十六。\n\n'+marker)
    folder=WORK/f'第{n:03d}章';folder.mkdir(exist_ok=True)
    (folder/'candidate.md').write_text(s,encoding='utf-8')
    o=BOOK/f'大纲/细纲_第{n:03d}章.md'
    (folder/'outline.md').write_text(o.read_text(encoding='utf-8-sig').rstrip()+'\n\n## 2026-10-06 第三批反调查闭环\n\n'+NOTES[n]+'\n',encoding='utf-8')
print(json.dumps({'candidates':NUMBERS,'required_checks':len(index),'formal_changed':False},ensure_ascii=False))
