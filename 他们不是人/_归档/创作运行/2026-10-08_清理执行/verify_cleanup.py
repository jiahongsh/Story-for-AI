from pathlib import Path
import json,subprocess,sys,os
HERE=Path(__file__).resolve().parent
BOOK=HERE.parents[1];REPO=BOOK.parent;S=REPO/'skills/story-long-write/scripts'
items=json.loads((HERE/'剪裁明细.json').read_text(encoding='utf-8'))
files=[str(BOOK/i['file']) for i in items]
checks=[]
def run(label,args):
    p=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',env={**os.environ,'PYTHONIOENCODING':'utf-8'})
    checks.append({'check':label,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
    (HERE/'机械验收.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if p.returncode:raise RuntimeError(label+'\n'+p.stdout+'\n'+p.stderr)
for file in files:run('language '+Path(file).name,['node',str(S/'language_gate.js'),file])
for name in ['check-style-hygiene.js','check-ai-patterns.js','check-degeneration.js']:
    run(name,['node',str(S/name),'--check','--fail-on=blocking']+(['--language=zh'] if name=='check-degeneration.js' else [])+files)
run('punctuation',['node',str(S/'normalize-punctuation.js'),'--check']+files)
run('tracking',[sys.executable,str(S/'tracking_commit.py'),'check','--project',str(BOOK)])
print(json.dumps({'status':'PASS','checks':len(checks),'chapters':len(files)},ensure_ascii=False))
