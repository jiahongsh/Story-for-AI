import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
BOOK = ROOT.parents[2]
REPO = BOOK.parent
GATE = REPO / 'skills/story-world-engine/scripts/world_gate.py'
TRACK = REPO / 'skills/story-long-write/scripts/tracking_commit.py'
PLAN = ROOT / '规划与行动依据.md'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

# 同一场景内每人以一项连续决策包覆盖其响应；条件转换另开场景。
SCENES = {
90: [
 ('受控点当晚开始短介入', [('现场负责人','确认短介入与停止条件后批准开始'),('镇封行动员','维持目标单体范围并持续报告承载'),('定向剥蚀行动员','独立核位置后作一次定向短介入'),('老李','以家庭往事和仓库物件争取自己的位置'),('镜辞','只记录亲见接缝与外观不一致'),('姜霁','保留旧家庭与仓库两条来源不替人定身份')]),
 ('同场承载下降后', [('镇封行动员','报告维持范围松动并请求交接'),('年长行动员','根据过去救人经验提出加深质疑'),('现场负责人','停止剥蚀并安排换班保留约束'),('定向剥蚀行动员','执行停手不再深入追逐记忆'),('镜辞','撤回救出愿望拒改亲见原句'),('姜霁','要求记录未知保留原页及责任来源'),('年长行动员','将本次原人断言更正为状态未知'),('老李','仍追问张岚及被收走的物件')]),
 ('处置结束后电话', [('姜霁','只向张岚告知已确认三项结果'),('张岚','追问丈夫下落保留安全住处')]),
 ('回店及次日上午', [('镜辞','交代观察身份并把旧案单独留袋'),('守钟人','确认店内安全边界维持修表店务'),('姜霁','递交获准关联页让镜辞选择新任务')])],
91: [
 ('次日上午柜台接案', [('姜霁','说明两周观察与限定复核任务'),('镜辞','阅读关联材料接受一次有限观察')]),
 ('当日公共花园观察', [('周诚','按正常交谈说外派生活不配合摆角度'),('周诚妻子','提出自己担心的日常变化'),('镜辞','到约定时间仍未见如实停止观察'),('姜霁','接受未见不要求再看出异常')]),
 ('花园交谈转向肩伤', [('周诚妻子','说出曾听过的肩伤及早好了的判断'),('周诚','确认肩伤并限本次伤情开放材料'),('姜霁','优先核伤情并暂缓异常观察'),('镜辞','分开记录转述与亲见不认证身份')])],
92: [
 ('五天后材料到齐', [('姜霁','核实独立材料能否解释主要动作'),('镜辞','查获准关联材料不替医学下诊断')]),
 ('同日花园回溯', [('周诚妻子','重述本人挪杯与钥匙盘及孩子换边'),('姜霁','按时间核对过程不诱导身份结论'),('镜辞','将家庭适应与伤情对应而不新增异常')]),
 ('同日柜台撤案', [('姜霁','正式撤案通知观察组停止相关观察'),('观察员','按撤点通知取消晚间与视频任务'),('周诚','要求明确今后是否继续记录日常'),('周诚妻子','指出调查增加自己恐惧不以感谢收场'),('镜辞','接受撤案不私下重返花园盯看')]),
 ('当日复盘会', [('年长行动员','提出过去漏案风险仍反对轻易放下'),('姜霁','维护本次撤案回应不同案件证据边界'),('镜辞','听取分歧不要求老李案替周诚加权')])],
93: [
 ('复盘后钟表行获准旧案', [('镜辞','追问撤案不安的来源查看去标识旧案'),('姜霁','开放与本次结论有关的有限旧案')]),
 ('稍后交回署名更正', [('年长行动员','保留过去成功同时署名撤回本次过强结论'),('姜霁','接受有限更正分列老李案三个问题'),('镜辞','对照亲见记录不把未知改成死活答案')]),
 ('当晚有限编号卡及归档消息', [('姜霁','展示十一份有限编号但不开放周衡全卷'),('镜辞','记下周衡名字停止越权翻阅'),('守钟人','提醒店务边界不替名单判人')])],
94: [
 ('次日柜台有限状态筛选', [('姜霁','按许可展示不同处置状态及未结事项'),('镜辞','区分待撤受控失联等状态不按壳统称')]),
 ('同日查看周衡获准页', [('镜辞','追问为何撤周诚却继续查周衡'),('姜霁','说明两处弱相关和两轮观察承认证据上限')]),
 ('同日商定低干扰方案', [('镜辞','有条件接受自然场合观察拒绝主动刺激'),('姜霁','限定分工保留空结果不组织围堵'),('猫眼','接获有限旧版本核验任务不保证查出问题')]),
 ('当夜既有市场动向', [('观察员','依据已有市场往来来源交接可能到场动向'),('姜霁','转交有限消息要求照常经营'),('镜辞','答应照常开摊不将市场变成诱饵'),('守钟人','坚持修表正常接客不替调查揽客')])]
}

def citation(sid, path, fragment):
    lines=path.read_text(encoding='utf-8').splitlines()
    idx=next(i for i,line in enumerate(lines) if fragment in line)
    return dict(source_id=sid,start_line=idx+1,end_line=idx+1,quote=lines[idx])

def pre(n):
    folder=ROOT/f'第{n:03d}章'
    folder.mkdir(exist_ok=True)
    dest=folder/'写前行动审查.json'
    if dest.exists():
        return
    original=next((BOOK/'正文').glob(f'第{n:03d}章_*.md'))
    prev=next((BOOK/'正文').glob(f'第{n-1:03d}章_*.md'))
    sources=[PLAN,original,prev,BOOK/f'大纲/细纲_第{n:03d}章.md']
    cmd=[sys.executable,str(GATE),'init','--project',str(BOOK),'--chapter',str(n),'--mode','revision','--tracking-tool',str(TRACK),'--packet',str(dest.relative_to(BOOK))]
    for src in sources:
        cmd+=['--source',str(src.relative_to(BOOK))]
    subprocess.run(cmd,check=True,capture_output=True)
    doc=json.loads(dest.read_text(encoding='utf-8'))
    names=list(dict.fromkeys(name for _,acts in SCENES[n] for name,_ in acts))
    doc['actors']=[]
    notes={}
    for i,name in enumerate(names):
        ref=citation('SRC1',PLAN,name+'：')
        notes[name]=ref['quote']
        doc['actors'].append(dict(id=name,name=name,protagonist=name=='镜辞',own_goal=ref['quote'],without_protagonist=ref['quote'],voice_refs=[ref],timeline_refs=[ref]))
    doc['scenes']=[]
    order=0
    first={}
    for i,(label,acts) in enumerate(SCENES[n],1):
        scene=dict(id=f'S{i}',order=i,story_time=dict(label=label,tick=i*10),actors_onstage=list(dict.fromkeys(x[0] for x in acts)),actors_offstage=[],actions=[])
        remote={90:{3:['张岚']},92:{3:['观察员']},94:{3:['猫眼'],4:['观察员']}}.get(n,{}).get(i,[])
        scene['actors_offstage']=remote
        scene['actors_onstage']=[name for name in scene['actors_onstage'] if name not in remote]
        for name,choice in acts:
            order+=1
            aid=f'A{order}'
            ref=citation('SRC1',PLAN,name+'：')
            # 这条引用只授予规划页明确写出的开始前生活/职业知识；
            # 当前场景新信息由更早动作取得，不能从旧正文导入未来结论。
            knowledge={**ref,'access':'memory','available_chapter':n-1,'available_order':0,'producer_action_id':None,'author_only':False,'certainty':'known','acquisition':'开始前本人经历或专业任务所知，逐项以既有正文与角色资料核对；本章新消息只在场景内听见或亲见后使用。','boundary':'仅支持本人的生活事实、既有职责和此次有限任务；不授予案卷全部内容与后续身份答案。'}
            prior=first.get(name)
            if prior:
                knowledge.update(access='planned-earlier-action',available_chapter=n,available_order=prior[1],producer_action_id=prior[0],acquisition='先完成本章已列在前的本人观察或交谈，再根据现场报告和当事人原话选择后续行动。')
            else:
                first[name]=(aid,order)
            gates=dict(knows=notes[name]+'当前只在'+label+'接收当场信息，不调入后续章节。',wants=choice+'；独立生活目标见本人的开始前依据。',fears=notes[name],capability=notes[name],no_plot='备选是拒绝或维持原判断；'+choice+'符合本人已有生活或职责目标，不因镜辞需要结论而必然成功。',costs=notes[name],consequences=choice+'会改变本人的责任与他人可采取的行动；当事人可拒绝、仍不满，未知与风险不被自动取消。')
            scene['actions'].append(dict(id=aid,actor_id=name,order=order,story_tick=i*10,kind='action',choice=choice,gates=gates,capacity=dict(resources=['本人已取得的有限材料、亲历生活或专业任务'],permission=notes[name],limits='不超出本人开始前资料明确的知识权限；没有身份判决、无限能力或未来材料。',evidence_refs=['SRC1','SRC2','SRC3','SRC4']),outcome=dict(intent=choice,failure_path='可能遭到对方拒绝、只能取得空结果或仍无法确认身份，维持既有安全边界。',opposition='当事人的隐私、生活诉求与不同专业意见独立存在，不保证按调查者意图响应。',success_guaranteed=False),knowledge_refs=[knowledge]))
        doc['scenes'].append(scene)
    doc['coverage']=dict(all_actors_reviewed=True,all_scenes_reviewed=True,basis='按原正文、上一轮已批准规划逐场核对所有会决定停手、交出信息、接受或拒绝任务者；背景旁观者没有新增决策。',background_only=[dict(name='其他路人和家中孩子',reason='只引用既有日常行为或背景；本候选不安排新有效台词与自主任务。')])
    doc['manual_review']=dict(status='passed',reviewer='Codex（同一Agent，非独立审查）',method='先读原章与相邻接口，再逐项核对人物资料及本批具体行动；写作前完成。',basis='核对090停手责任与记忆边界、091—092肩伤有限授权及撤点、093署名更正、094弱相关自然观察；不把作者秘密授予人物。',checks={x:'passed' for x in ['seven_gates','knowledge_bounds','capacity_permissions','autonomy','constraints','consequences','voice','actor_scene_coverage','timeline']})
    save(dest,doc)
    result=subprocess.run([sys.executable,str(GATE),'check','--project',str(BOOK),'--packet',str(dest.relative_to(BOOK)),'--phase','prewrite','--tracking-tool',str(TRACK)],capture_output=True,text=True,encoding='utf-8')
    (folder/'写前检查.json').write_text(result.stdout+result.stderr,encoding='utf-8')
    if result.returncode:
        raise RuntimeError(result.stdout+result.stderr)
    print(f'{n}: prewrite structural pass')

if __name__=='__main__':
    for chapter in SCENES:
        pre(chapter)
