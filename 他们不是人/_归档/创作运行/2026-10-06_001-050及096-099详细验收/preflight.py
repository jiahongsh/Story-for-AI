"""Read-only acceptance checks. Only review artifacts are written."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,hashlib,subprocess,sys
ROOT=Path(__file__).resolve().parents[3];BOOK=ROOT/'他们不是人';WORK=Path(__file__).resolve().parent
SCRIPT=ROOT/'skills/story-review/scripts'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,obj):
 (WORK/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
scope=list(range(1,51))+list(range(96,100))
files=[next((BOOK/'正文').glob(f'第{n:03d}章_*.md')) for n in scope]
baseline={p.relative_to(ROOT).as_posix():digest(p) for folder in ['正文','设定','大纲','追踪'] for p in (BOOK/folder).rglob('*') if p.is_file()}
if '--repair-punctuation' not in sys.argv:write('只读基线.json',{'state_revision':104,'last_committed_chapter':99,'scope':scope,'files':baseline})
commands=[]
for p in files:commands.append(('language',p,['node',str(SCRIPT/'language_gate.js'),'--json',str(p)]))
for key,script,args in [('style','check-style-hygiene.js',['--check','--fail-on=blocking']),('punctuation','normalize-punctuation.js',['--check']),('ai','check-ai-patterns.js',['--check','--fail-on=blocking']),('degeneration','check-degeneration.js',['--check','--language=zh','--fail-on=blocking'])]:
 for p in files:commands.append((key,p,['node',str(SCRIPT/script),*args,*(['--json'] if key!='punctuation' else []),str(p)]))
if '--repair-punctuation' in sys.argv:commands=[c for c in commands if c[0]=='punctuation']
def check(cmd):
 key,p,args=cmd;r=subprocess.run(args,cwd=ROOT,capture_output=True,encoding='utf-8',errors='replace')
 try:body=json.loads(r.stdout)
 except ValueError:body={'stdout':r.stdout,'stderr':r.stderr}
 return {'check':key,'file':p.relative_to(BOOK).as_posix(),'returncode':r.returncode,'report':body}
with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(check,commands))
if '--repair-punctuation' in sys.argv:
 old=json.loads((WORK/'机械预检明细.json').read_text(encoding='utf-8'))
 results=[r for r in old if r['check']!='punctuation']+results
write('机械预检明细.json',results)
summary={key:{'checks':len([r for r in results if r['check']==key]),'nonzero':[r['file'] for r in results if r['check']==key and r['returncode']]} for key in ['language','style','punctuation','ai','degeneration']}
write('机械预检汇总.json',summary)
print(json.dumps(summary,ensure_ascii=False))
