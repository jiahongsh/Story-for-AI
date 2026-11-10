from pathlib import Path
import json,hashlib,shutil,subprocess,sys
BOOK=Path(__file__).resolve().parents[2];WORK=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert read(BOOK/'追踪/_tracking-state.json')['state_revision']==68
hashes=read(WORK/'基线哈希.json');plan=read(WORK/'修订计划.json')
prose=next((BOOK/'正文').glob('第077章_*.md'));outline=BOOK/'大纲/细纲_第077章.md'
for p in [prose,outline]:
    rel=p.relative_to(BOOK).as_posix();target=BOOK/'备份/2026-10-06_第四批分轨生活修订'/rel
    assert not target.exists();target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
    hashes[rel]=hashlib.sha256(p.read_bytes()).hexdigest();plan['changed_files'].append(rel)
plan['affected_chapters'].append(77);plan['summary']+='；077修正隔日称谓与到场前未知学徒的知情越界'
write(WORK/'基线哈希.json',hashes);write(WORK/'修订计划.json',plan)
r=subprocess.run([sys.executable,'-X','utf8',str(BOOK.parent/'skills/story-long-write/scripts/revision_guard.py'),'plan','--project',str(BOOK),'--input',str(WORK/'修订计划.json'),'--output',str(BOOK/'追踪/修改影响/active.json')],capture_output=True,text=True,encoding='utf-8');assert r.returncode==0,r.stdout+r.stderr
gate=WORK/'写前人物七关.md'
with gate.open('a',encoding='utf-8') as f:f.write('''
## 计划扩展：077两句直接依赖（先审再改）

唐宁：1亲历069见面而后经过早餐、复核、三天工期与076夜谈，绝非昨日；2限定讲高二旧事而不续现在关系；3怕又被代定义；4可独立到店、说自己亲历；5可不来，愿讲旧友确曾受益的事实不等于和解；6只讲旧事、不留谈现在；7上次没想通这次也没想通，兼容069拒再约。

当前存在：1只有074到铺子后才亲听学徒想走，出发前不知道；2承认现在也因镜辞会停手救人而隐瞒需要；3怕他再次揽事；4能回述当场听见后自己的想法，无预知；5可全说，她曾迟疑，在077承担省略信息的责任；6不把关系问题全推给镜辞或原芽；7仅修正到场后的选择，不改变高二病与工钱、077吃饼142和后续离开。

镜辞、姜霁只听本人回述与唐宁亲历，不把恐惧推断当当时真的发生援救。范围扩展已在active.json计划中先登记。
''')
frozen=read(WORK/'冻结写前包.json');frozen['chapters'].append(77);frozen['source_hashes']=hashes
frozen['gate_hash']=hashlib.sha256(gate.read_bytes()).hexdigest();write(WORK/'冻结写前包.json',frozen)
folder=WORK/'第077章';folder.mkdir()
s=prose.read_text(encoding='utf-8-sig');a='现在这个人是谁，我昨天没想通，今天也不想通。';assert s.count(a)==1
s=s.replace(a,'现在这个人是谁，上次没想通，这次也没想通。')
a='去方远那儿之前，我没把学徒要走、车主在等的风险说完。';assert s.count(a)==1
s=s.replace(a,'到了方远那儿，听见学徒说不想干，我也没告诉你我还想多听一会儿，怕你先把他们的活揽过来。')
(folder/'candidate.md').write_text(s,encoding='utf-8')
(folder/'outline.md').write_text(outline.read_text(encoding='utf-8-sig').rstrip()+'\n\n## 2026-10-06 第四批直接依赖校正\n\n唐宁说上次而非昨天，不因多日间隔退化时间。当前存在对学徒想走的知情只能在074到场后取得，077回述改为到场听到后未说自己的停留意愿；不写成出发前已知现场风险。高二陪诊、镜辞可靠性后果与142现金保持。\n',encoding='utf-8')
print('077 dependency planned and seven-gate reviewed before candidate creation')
