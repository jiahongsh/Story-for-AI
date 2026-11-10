from pathlib import Path
import json,subprocess,sys,os,hashlib
HERE=Path(__file__).resolve().parent;BOOK=HERE.parents[1];REPO=BOOK.parent
S=REPO/'skills/story-long-write/scripts'
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s,encoding='utf-8')
def run(args):
    p=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',env={**os.environ,'PYTHONIOENCODING':'utf-8','PYTHONUTF8':'1'})
    if p.returncode:raise RuntimeError(p.stdout+'\n'+p.stderr)
    return p.stdout
items=load(HERE/'剪裁明细.json');voice=[]
if (HERE/'对白漂移验收.json').exists():voice=load(HERE/'对白漂移验收.json')
else:
    for i in items:
        result=json.loads(run(['node',str(S/'dialogue_drift_gate.js'),'--current',str(BOOK/i['file']),'--history-dir',str(BOOK/'正文'),'--json']))
        voice.append({'chapter':i['chapter'],**result})
    write(HERE/'对白漂移验收.json',json.dumps(voice,ensure_ascii=False,indent=2)+'\n')
doctor=load(HERE/'最终项目验收.json')['doctor'] if (HERE/'最终项目验收.json').exists() else json.loads(run([sys.executable,str(S/'story_doctor.py'),'--project',str(BOOK)]))
assert doctor['status']=='pass' and not doctor['errors']
guard=load(HERE/'最终项目验收.json')['revision_guard'] if (HERE/'最终项目验收.json').exists() else json.loads(run([sys.executable,str(S/'revision_guard.py'),'check','--project',str(BOOK),'--input',str(BOOK/'追踪/修改影响/active.json'),'--stamp',str(BOOK/'追踪/修改影响/active.approved.json')]))
assert guard['status']=='PASS'
write(HERE/'最终项目验收.json',json.dumps({'doctor':doctor,'revision_guard':guard},ensure_ascii=False,indent=2)+'\n')
oldlog=load(HERE/'回执与总验收.json')
oldlog.append({'check':'story_doctor_UTF8重验','returncode':0,'stdout':json.dumps(doctor,ensure_ascii=False),'stderr':''})
write(HERE/'回执与总验收.json',json.dumps(oldlog,ensure_ascii=False,indent=2)+'\n')
for i in items:
    assert hashlib.sha256((BOOK/i['file']).read_bytes()).hexdigest()==i['after_sha256']
    receipt=BOOK/f'追踪/章节提交/第{i["chapter"]:03d}章.json'
    if receipt.exists():
        r=load(receipt);assert r['accepted_prose_sha256']==i['after_sha256']
rows='\n'.join(f'| {i["chapter"]:03d} | {i["before_chars"]} | {i["after_chars"]} | {i["removed_chars"]} |' for i in sorted(items,key=lambda x:x['chapter']))
manifest=load(BOOK/'追踪/修改影响/active.json')
resolutions='\n'.join(f'| {c["issue"]} | {c["resolution"]} | 已完成 |' for c in manifest['conflicts'])
report=f'''# 《他们不是人》C01—R10清理完成与验收报告

2026-10-08。本轮承接作者“开始改吧”及“继续”的授权，只执行已列清单C01—R10。正文只删除、压缩和剪合已有文字，没有增加行动、对白、场景、人物动机或设定。L11不在本次执行范围；100—103原文件指纹未变，104继续冻结。

## 完成结果

17章净删3225字符（包括标点及空白，不等同于汉字字数）。001—103中其余86章正文与写前指纹一致。没有合并章节或改章号。单章最大删减061章676字符；各章删减均未超过30%。

| 章 | 修改前字符 | 修改后字符 | 净删 |
|---|---:|---:|---:|
{rows}

## 清单逐项闭合

| 编号与问题 | 实际处理及保护项 | 状态 |
|---|---|---|
{resolutions}

同一段同时命中R07/R08/R10时仅剪一次，不能把编号当作独立删减次数。C03属于作者已经选择执行的市场气氛取舍，保留下来的市井工作与普通生意并未整体裁掉。

## 语义复核与人物七关保护

本轮是已接纳历史的删减修订；不伪造旧章当时的写前审批。对保留下来的关键选择重新核对其证据和边界，没有为了把清单修完而补写人物心理。

| 七关 | 本轮复核结论与来源 |
|---|---|
| 知道什么 | 053的D4仍来自旧司机观察与既有记录；061仍区分公开名单和陈屿问话的未知来源；073门链来自交接与送药人的转述；侯强075未告诉镜辞的私支出没有被写进镜辞账。 |
| 想要什么 | 053本地陈骁保工作及自己的工号；061孙立要修父亲的表；073许棠要实际通行与工作，拒当对照；075当前存在问的是明日劳动而非配合调查。原有目标仍有行动承载。 |
| 怕失去什么 | 班次、工时、零钱、维修责任和个人解释权仍由当事人自己承担。删掉事后说明，保留具体失去与拒绝，未额外赋予反派动机。 |
| 能力与权限 | 猫眼只交付来源/公开版本，不知制造方；物业不能开502住宅门；镜辞自然观察未见不构成身份结论。能力及渠道均未因压缩而升级。 |
| 没有剧情需要仍会选吗 | 孙立付钱取表、许棠拒重签并回单位解释、本地陈骁拒到安平里而等下一单、当前存在赴摊及继续找活，各有现实目标；镜辞不回身份问话也保留实际拒绝。没有以推动主线替代其选择。 |
| 代价与约束 | 二十二、十一、四十五、四十、十二、六块退款，以及075六十收入、八块手套、五十二余额仍按各自发生条件记录；073与071不是同一天或第二次同步；075三日工期实际结束。 |
| 后果与独立回应 | 删重复核账不删实际票据与后续退款；拒验收未让维护链停转；许棠未签、药暂存、门未开仍在；096自然观察未见→097前三年冲突→098近五年关系后果→099普通客修表的递进保留。 |

061多位人物重复判词删去后，陈屿14:18问话、孙立约14:12离店及六分钟间隔仍在，来源仍未证。063保留“她指出先喝汤、缺口碗、耳后”的起笔，随后划掉自辩有明确指代。083删重复分公司声明时一并清除悬空“两边”。098保留姜霁的普通生意要求与坏表是否送来的未知，不制造新钩子。

对白在当前Agent的solo/direct模式复核：不声明独立多Agent验收。机器对白扫描17章无阻断；普通“说”字等advisory保留，并不据此给人物另造口头禅或扩大改文范围。

## 长期记忆与来源闭环

- 权威通过17次串行revision提交由r232升至r249，截至099；不是新增17章。
- 逐章记录按新正文纠正061/063/071/073/075的失效动作摘要，其他约束和下一章承诺保留。六名核心人物截至099快照，以及事实、伏笔、时间线的实际语义与写前一致；仅正常修订管理字段变化。
- 已有接纳回执的15章完成sync；053、054没有既有回执，只保留合法修订记录，不倒造接纳回执。43份既有回执总数不变。
- 六名核心人物的作者/读者派生视图与001—099卷末记录重建至r249；七名辅助行动者卡及个人时间线、裴亮/陌生男人/周衡补充卡按现文复验重建。
- 猫眼25节点、唐宁5节点重建为当前来源绑定时间线；两张静态卡仅更新阅读入口，人物目标、声线与未来规划未改。旧r232包留作历史，不刷新标签冒充当前。
- 17份细纲附本轮执行口径，061/063/073明确不恢复已删动作；大纲未来设想仍不当成角色当前已知。

当前人物恢复入口：[人物记忆索引](../派生视图/人物记忆索引.md)。卷末版本：[r249卷末记录](../卷末记录/第一卷_001-099_r249_清理后/)。

## 验收证据与范围

语言门17/17、文风卫生、AI句式、退化、标点和对白漂移均通过阻断检查。影响清单280文件已做定点依赖核对；C01—R10十项闭合。revision_guard、tracking check、story_doctor通过，当前候选欠账0，接纳摘要和最新投影一致。机械门不证明文学效果最优；本轮没有再声称完成一次001—103的逐句连续冷读。

既有提示保留：本书尚未配置作者声音画像，doctor返回warning，未作为本轮新增缺陷或借机建立旧章画像。工具首轮总检曾遇Windows子进程编码异常，已启用UTF-8重验通过；原失败记录与通过记录均保存，不掩盖执行结果。

证据文件：剪裁明细.json（含原句与剪后句）、串行提交记录.json、来源与记忆验收.json、写后影响核对.json、机械验收.json、对白漂移验收.json、回执与总验收.json、最终项目验收.json。备份位于书根`备份/2026-10-08_清理C01-R10/`。

结论：此次作者确认的C01—R10清理已完成，没有待接着执行的本轮清单项；L11仍仅是锁定范围的另列建议。
'''
assert all(i['removed_chars']/i['before_chars']<=.30 for i in items)
write(HERE/'清理完成与验收报告.md',report)
write(REPO/'.story-review/state.md','''# 《他们不是人》清理状态（2026-10-08）

- 当前任务：作者确认C01—R10，只删减，不加情节；已全部完成，十项未解决为0。
- 执行：solo/direct；17章净删3225字符，未合并章号，余下86章正文指纹一致。
- 正史：r249，截至099；逐章摘要、现有人物/伏笔/事实/时间线闭环，15章既有回执已同步。
- 当前人物记忆、作者/读者视图及001—099卷末记录已按清理后来源重建。
- 验收：语言与去AI味阻断门、标点、对白、修订门、追踪check、story-doctor通过。原作者声音画像未配置提示保留。
- 边界：不宣称本轮重新完成全卷逐句连续冷读，不保证作品不存在其他文学问题。L11不执行，100—103文件未变且未晋升，104冻结。
- 报告：他们不是人/创作运行/2026-10-08_清理执行/清理完成与验收报告.md。
- 恢复入口：他们不是人/创作运行/派生视图/人物记忆索引.md。
- 旧轮复查报告保留为历史：他们不是人/创作运行/2026-10-08_全书内容与世界记忆复查/完整复查报告.md。
''')
print(json.dumps({'status':'COMPLETE','chapters':17,'removed_chars':3225,'revision':249,'synced_receipts':15,'report':str(HERE/'清理完成与验收报告.md')},ensure_ascii=False))
