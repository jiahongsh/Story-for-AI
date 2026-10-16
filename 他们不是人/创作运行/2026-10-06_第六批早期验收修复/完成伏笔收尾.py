from pathlib import Path
import hashlib, json, os, subprocess

BASE=Path(__file__).resolve().parent
BOOK=BASE.parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text(encoding="utf-8-sig"))
def run(*args):
    r=subprocess.run(list(map(str,args)),capture_output=True,text=True,encoding="utf-8",errors="replace",env={**os.environ,"PYTHONUTF8":"1"})
    if r.returncode: raise RuntimeError(r.stdout+r.stderr)
    return r.stdout

state=read(BOOK/"追踪/_tracking-state.json")
baseline=read(BASE/"伏笔记忆补录/baseline.json")
assert state["state_revision"]==175
for k in ("characters","timeline","facts","context"): assert state[k]==baseline[k],k
# 当前人物及时间线未改，复用此前逐条人工审核的判断，重绑新权威指纹。
out=BASE/"人物记忆_r175"; out.mkdir(exist_ok=True)
generator=(BASE/"人物记忆_r158/generate_actor_views.py").read_text(encoding="utf-8-sig").replace("158","175")
(out/"generate_actor_views.py").write_text(generator,encoding="utf-8")
print(run("python",out/"generate_actor_views.py"))
index=read(out/"索引.json")
assert index["authority"]["sha256"]==sha(BOOK/"追踪/_tracking-state.json")
for a in index["actors"].values():
    for field in ("role_card","timeline"):
        assert sha(BOOK/a[field]["path"])==a[field]["sha256"]
# 这是尚未生成成品的来源索引草稿；22条锚点将在freeze/build中逐条校验。
script=BASE/"早期伏笔索引/build_early_foreshadow_index.py"
text=script.read_text(encoding="utf-8-sig").replace("158","175")
text=text.replace("4. 此索引不调整 CORE 生命周期或 TRACK 状态，不补填过去的首埋/回收事务，也不把历史读者知识反推为人物当时所知。","4. 此索引本身只读；已核F01/F09/F11里程碑已由独立的17次历史修订事务提交。其余未核项不能据此认定完成，不把历史读者知识反推为人物当时所知。")
script.write_text(text,encoding="utf-8")
print(run("python",script,"--freeze"))
print(run("python",script,"--build"))
print(run("python",script,"--check"))
report=BASE/"本轮修订复验.md"
text=report.read_text(encoding="utf-8-sig")
text=text.replace("日期：2026-10-06。结论：原《001—050、096—099详细验收》报告列出的 A01—A08 与 B01—B13 已完成定点修订和复核。","日期：2026-10-07。结论：原《001—050、096—099详细验收》报告列出的正文缺口已完成定点修订；A07事件记忆已补齐，已核核心伏笔阶段已补账，其他伏笔的完整逐章验收仍为部分完成。")
text=text.replace("没有把当前伏笔状态反推为当年首埋/回收，也没有伪造旧章七关审批。","追加17次来源明确的历史修订：F001在032首埋并补033/045/046/050推进；新增F051对应011空白姓名页、042独立拒绝，新增F052对应017猫眼基础及019/038/045/050/096—098推进。009/021按当章知情留账，055—056后续证据分段恢复。未伪造旧章七关审批；其他未核伏笔不能据“无”认定未埋或已完成。")
text=text.replace("正式接纳进度仍为第099章。42章正文", "正式接纳进度仍为第099章。随后追加17次伏笔阶段修订，当前为r175，共71次历史修订事务。42章正文")
text=text.replace("正文唯一受改章数为43章。","第055章“五年工牌”另改为“五年前合影里的胸牌”，避免用旧合影证明连续任职；受改正文唯一章数为44章。")
text=text.replace("世界派生导出 r158", "世界派生导出 r175")
text=text.replace("七位关键行动者另有 r158", "七位关键行动者另有 r175")
text=text.replace("下次续写前以 r158 权威", "下次续写前以 r175 权威")
text=text.replace("`人物记忆_r158/索引.json`", "`人物记忆_r175/索引.json`、`伏笔记忆补录/final_checks.json`、`早期伏笔索引/早期伏笔索引.md`")
text += "\n## 伏笔记忆专项复验（2026-10-07）\n\n- CORE规划编号与TRACK执行编号已显式对应；二者不能按数字互认。F002/F003的当前摘要已修正为分阶段证据，未知关联继续保留。\n- 17份事务保留既有事件、人物变化与事实；当前人物、时间线、事实、上下文均与r158一致，只新增已核伏笔阶段并修正两个摘要。章级记录经试提交均不超3072字节。\n- 早期辅助索引绑定54章正文和22条限定证据，缺项明确写待核。A07的完整伏笔覆盖仍为PARTIAL，不能把本轮补账说成所有伏笔都已验收。\n- 第055章四项语言检查、追踪一致性、修改影响门、故事体检、世界导出均通过；第100—103章指纹不变。\n- 本轮收尾由主代理直接完成；已有独立审查结论按正文来源复核后采用。\n"
report.write_text(text,encoding="utf-8")
print("PASS: r175人物记忆、早期索引和验收报告已同步")
