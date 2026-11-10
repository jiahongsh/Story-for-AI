import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('packet_builder',ROOT/'构建审查包.py')
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

SCENE_STARTS={
90:['老李的左手一直往身侧探。','“范围在松。”镇封者说。','姜霁出了观察区才给张岚打电话。','回旧市场时，店里的灯还亮着。'],
91:['周诚的文件夹在柜台上摊了一上午。','小区公共花园里，周诚穿深灰夹克','妻子看着丈夫提袋的手，忽然问'],
92:['第五天，最后一份随访材料到了。','两人再到公共花园','回店后，姜霁将原来的高风险备注','下午的复盘会开在城南'],
93:['从复盘会回到钟表行','门口进来一个人','姜霁收齐获准的旧档'],
94:['姜霁把十一份编号卡铺到柜台时','身份资料连续，工作和租住接得上','柜台里有一只还没装好的表','当天夜里，观察员传来市场动向']}

RESULTS={
90:['在受控场合短介入，家庭旧事和仓库记忆交错，外观不稳定而未出现可确认的原人。','承载下降后负责人停手、维持约束并换班；观察更正为强记忆残留且原人未知。','张岚通过电话只得到危险受控、严重错位和原人未知，追问没有得到答案。','镜辞回店交代安全边界；次日上午只收到新案关联页，没有让老李案给新案加权。'],
91:['镜辞获知限定复核范围并接受任务，两周观察已有普通项排除。','周诚正常交谈，镜辞到点未见即停，姜霁没有追加反复盯看。','妻子提伤情，周诚确认治疗并限范围授权；姜霁暂缓异常观察，材料尚待核实。'],
92:['五天后材料汇合支持右肩伤，未作身份认证。','妻子回溯本人参与的家庭适应，记不清日期保留范围。','姜霁撤案并核对撤点确认，停止孩子日常视频；夫妻可要求明确边界并表达不满。','年长者仍担忧漏案，姜霁没有因此恢复观察，镜辞不私下重返盯人。'],
93:['三类成功和其他无确认结果旧案并置，旧经验来源成立但机制不等同。','年长者署名撤回本次过强结论而保留旧成功，姜霁分列三个问题并保留仓库记录。','十一份仅有限开放；周衡只出现名字及七天无异常摘要，全卷未批；署名更正入卷。'],
94:['十一份按不同状态查看，老李和安平里未结状态继续保留。','两轮行为与两处弱相关支持有限复核而不足高风险，七天投入不作为危险加权。','镜辞有条件接受自然观察，猫眼收到有限核验任务，无新回填结论。','观察员交接已有往来来源的市场动向，镜辞照常开摊，不预定目标进店和谈话。']}

def run(cmd,path):
    r=subprocess.run(cmd,cwd=m.REPO,capture_output=True,text=True,encoding='utf-8')
    path.write_text(r.stdout+r.stderr,encoding='utf-8')
    if r.returncode:
        raise RuntimeError(f'{path}: '+r.stdout+r.stderr)
    return r.stdout

def main():
    stats=[]
    for n in range(90,95):
        folder=ROOT/f'第{n:03d}章'
        body=next(folder.glob('第*.md'))
        txt=body.read_text(encoding='utf-8')
        old=next((m.BOOK/'正文').glob(f'第{n:03d}章_*.md'))
        oldtxt=old.read_text(encoding='utf-8')
        count=lambda s:len(re.findall(r'[\u4e00-\u9fff]',s.split('\n',1)[-1]))
        stats.append(dict(chapter=n,old_hanzi=count(oldtxt),candidate_hanzi=count(txt),candidate_sha256=m.sha(body),original_sha256=m.sha(old)))
        checks=[('语言', ['node',str(m.REPO/'skills/story-long-write/scripts/language_gate.js'),str(body)]),('文风卫生',['node',str(m.REPO/'skills/story-long-write/scripts/check-style-hygiene.js'),'--check','--fail-on=blocking',str(body)]),('AI句式',['node',str(m.REPO/'skills/story-long-write/scripts/check-ai-patterns.js'),'--check','--fail-on=blocking',str(body)]),('退化',['node',str(m.REPO/'skills/story-long-write/scripts/check-degeneration.js'),'--check','--language=zh','--fail-on=blocking',str(body)]),('对白归属',['node',str(m.REPO/'skills/story-long-write/scripts/dialogue_drift_gate.js'),'--current',str(body),'--history-dir',str(m.BOOK/'正文'),'--json']),('结构证据',[sys.executable,str(m.REPO/'skills/story-long-write/scripts/chapter_shape_gate.py'),'--project',str(m.BOOK),'--candidate',str(body),'--chapter',str(n),'--window','6'])]
        for label,cmd in checks:
            run(cmd,folder/f'{label}检查.log')
        doc=json.loads((folder/'写前行动审查.json').read_text(encoding='utf-8'))
        lines=txt.splitlines()
        starts=[next(i for i,line in enumerate(lines) if marker in line) for marker in SCENE_STARTS[n]]
        results=[]
        for i,scene in enumerate(doc['scenes']):
            start=starts[i]
            end=starts[i+1]-1 if i+1<len(starts) else len(lines)-1
            quote='\n'.join(lines[start:end+1])
            results.append(dict(scene_id=scene['id'],actual_result=RESULTS[n][i],action_ids=[a['id'] for a in scene['actions']],evidence=[dict(start_line=start+1,end_line=end+1,quote=quote)],world_followups=[RESULTS[n][i]+'这些是候选拟变化，未写入正史；未解身份和权限边界仍按原正文。']))
        pre=folder/'写前行动审查.json'
        doc['postwrite']=dict(prewrite_packet=dict(path=str(pre.relative_to(m.BOOK)).replace('\\','/'),sha256=m.sha(pre)),candidate=dict(path=str(body.relative_to(m.BOOK)).replace('\\','/'),sha256=m.sha(body)),scene_results=results,foreshadow_deltas=[dict(id='NO_CHANGE',operation='none',description='保留原案未解和原有揭露安排；现场展开没有解决原人、周衡回填实施者或新接缝；不增改正式伏笔状态。',evidence=[results[-1]['evidence'][0]])],manual_review=dict(status='passed',reviewer='Codex（同一Agent，自审）',method='读完整候选并对照原文、冻结场景及前后接口，机械检查后逐场复核。',basis='090停手不越权，091未见不认证，092撤点实际完成且当事人可不满，093保留旧成功与署名责任，094不释放回填与接缝；095时间接口作为待后批采用事项明示。',checks={x:'passed' for x in ['actual_coverage','causality','voice','knowledge_bounds','consequences','foreshadow']}))
        post=folder/'写后行动复核.json'
        m.save(post,doc)
        run([sys.executable,str(m.GATE),'check','--project',str(m.BOOK),'--packet',str(post.relative_to(m.BOOK)),'--phase','postwrite','--tracking-tool',str(m.TRACK)],folder/'写后检查.json')
        print(f'{n}: {count(oldtxt)} -> {count(txt)} Hanzi; checks passed')
    m.save(ROOT/'候选统计与来源.json',stats)

if __name__=='__main__':
    main()
