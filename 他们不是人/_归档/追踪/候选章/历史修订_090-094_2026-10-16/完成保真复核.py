import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('helpers',ROOT/'构建审查包.py')
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

for n in range(90,95):
    folder=ROOT/f'第{n:03d}章'
    body=next(folder.glob('第*.md'))
    runid=f'ch{n:03d}_final2'
    r=subprocess.run([sys.executable,str(m.REPO/'skills/story-long-write/scripts/deslop_guard.py'),'init',str(body),'--project-root',str(ROOT),'--scope','bounded','--intensity','standard','--run-id',runid],capture_output=True,text=True,encoding='utf-8')
    if r.returncode:
        raise RuntimeError(r.stdout+r.stderr)
    stage=ROOT/'.story-deslop/runs'/runid
    ledger=json.loads((stage/'protection-ledger.json').read_text(encoding='utf-8'))
    ledger['manual'].update(entities=['镜辞','姜霁']+({90:['老李','张岚','守钟人'],91:['周诚'],92:['周诚'],93:['年长行动员','周衡'],94:['周衡','猫眼','恒泰设施']}[n]),timeline_facts=['090处置后次日上午接案；091至092经过五天；093当晚至094次日；094夜约次日市场。'],knowledge_boundaries=['接缝只证错位，未见不认证；原老李状态未知；周衡新接缝与回填分段不能前置。'],clues=['原案身份与长期伏笔未解决，展开人物冲突不增加阵营或能力答案。'],voice_markers=['镜辞问具体人事；姜霁直接追依据；周诚不必感谢；年长者保留旧成功。'],intentional_roughness=['保留未答完的短句、正常问答和有限重复，不把专业对白机械改成隐喻。'])
    m.save(stage/'protection-ledger.json',ledger)
    r=subprocess.run([sys.executable,str(m.REPO/'skills/story-long-write/scripts/deslop_guard.py'),'check',str(stage)],capture_output=True,text=True,encoding='utf-8')
    (folder/'保真检查.json').write_text(r.stdout+r.stderr,encoding='utf-8')
    if r.returncode:
        raise RuntimeError(r.stdout+r.stderr)
    print(f'{n}: final deslop staging/protection checked; no further automatic edits')

# 此轮只修订候选，确认正式源与冻结来源一致。
for n in range(90,95):
    doc=json.loads((ROOT/f'第{n:03d}章/写前行动审查.json').read_text(encoding='utf-8'))
    for src in doc['sources']:
        assert m.sha(m.BOOK/src['path'])==src['sha256'],src['path']
    assert m.sha(m.BOOK/'追踪/_tracking-state.json')==doc['binding']['tracking']['sha256']
print('All bound canonical sources and state unchanged.')
