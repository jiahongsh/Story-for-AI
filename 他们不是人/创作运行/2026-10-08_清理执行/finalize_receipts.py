"""关闭影响清单后串行同步既有接纳回执，不创建旧章新接纳。"""
from pathlib import Path
import json,hashlib,subprocess,sys,os
HERE=Path(__file__).resolve().parent;BOOK=HERE.parents[1];REPO=BOOK.parent
S=REPO/'skills/story-long-write/scripts'
manifest=BOOK/'追踪/修改影响/active.json';stamp=BOOK/'追踪/修改影响/active.approved.json'
m=json.loads(manifest.read_text(encoding='utf-8-sig'))
checks=[]
for rel in m['required_checks']:
    p=BOOK/rel;text=p.read_text(encoding='utf-8-sig')
    checks.append({'path':rel,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'read_chars':len(text),
        'scope':'核已删支段的依赖、仍在的金额/时序/来源和未来规划边界；语义结论见清理完成与验收报告，非再次逐句全卷冷读'})
(HERE/'写后影响核对.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
m['checked_files']=m['required_checks']
rows=[('C01','053配送多次报到','正文/第053章_验收题.md','删多次报到和货物岔出，保留半趟二十二、工号与拒并工单'),
 ('C02','054重复熟客取钟','正文/第054章_假通过.md','删第二轮取钟；首次普通生意和未发短信保留'),
 ('C03','市场买菜通道岔出','正文/第062章_推荐店.md','删菜筐五毛及063回声；回店时间及蓝拖鞋后果保留'),
 ('C04','无故障路人再问推荐','正文/第063章_别拿她试.md','删路人支段及历史摘要依赖，蓝拖鞋真实维修仍在'),
 ('R05','纸屏复核重做','正文/第073章_又到两点十七.md','071实际同步保留；073只核持续页面并展示新公示和实际后果'),
 ('R06','公司不等同的反复声明','正文/第083章_合作条件.md','删无新证据声明及悬空两边指代；首次边界、文件来源和K002不变'),
 ('R07','重复演算核账','正文/第061章_来修表的人.md','删事后核账；裴亮十一、孙立四十五、075现金余额及孙立六块退费保留'),
 ('R08','多人解释同一选择','正文/第061章_来修表的人.md','保陈屿14:18问话、来源未核、不回及一次边界；不再轮流确认'),
 ('R09','动作情绪解释接龙','正文/第096章_没有缝的人.md','五处只剪解释尾句，保留动作、停止观察及私人本记录'),
 ('R10','章尾重复事项清单','正文/第098章_后五年.md','删事后总结；063划自辩起笔、066复核约定、075工期及找活、098普通生意指令保留')]
m['conflicts']=[{'severity':'S2' if code=='R05' else 'S3','source':'创作运行/2026-10-08_清理候选清单/清理清单_待确认.md','target':target,'issue':code+'｜'+issue,'resolution':res,'status':'resolved'} for code,issue,target,res in rows]
m['tracking_action']={'kind':'commit','state_revision_before':232,'state_revision_after':249,'reason':'作者确认C01—R10；17章分别串行revision提交，逐章摘要删除失效动作，当前人物/事实/伏笔/事件语义保留'}
manifest.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
log=[]
def run(label,args):
    p=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',env={**os.environ,'PYTHONIOENCODING':'utf-8','PYTHONUTF8':'1'})
    log.append({'check':label,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
    (HERE/'回执与总验收.json').write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if p.returncode:raise RuntimeError(label+'\n'+p.stdout+'\n'+p.stderr)
run('revision_guard',[sys.executable,str(S/'revision_guard.py'),'check','--project',str(BOOK),'--input',str(manifest),'--stamp',str(stamp)])
synced=[];no_receipt=[]
for n in m['affected_chapters']:
    if not (BOOK/f'追踪/章节提交/第{n:03d}章.json').exists():no_receipt.append(n);continue
    run('sync '+str(n),[sys.executable,str(S/'chapter_candidate.py'),'sync','--project',str(BOOK),'--chapter',str(n),'--revision-manifest',str(manifest),'--revision-stamp',str(stamp),'--reason','用户确认C01—R10删减；无新增剧情；已完成串行修订和来源复核','--confirm','SYNC'])
    synced.append(n)
run('voice_profile',[sys.executable,str(S/'voice_profile.py'),'update','--project',str(BOOK)])
run('tracking_check',[sys.executable,str(S/'tracking_commit.py'),'check','--project',str(BOOK)])
run('story_doctor',[sys.executable,str(S/'story_doctor.py'),'--project',str(BOOK)])
print(json.dumps({'status':'PASS','synced':synced,'no_existing_receipt':no_receipt,'required_checks':len(checks)},ensure_ascii=False))
