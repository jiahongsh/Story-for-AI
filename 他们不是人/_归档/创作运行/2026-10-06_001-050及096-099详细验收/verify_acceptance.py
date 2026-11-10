"""Validate review coverage, source links, and unchanged canonical files."""
from pathlib import Path
import hashlib,json,re,os
WORK=Path(__file__).resolve().parent;ROOT=WORK.parents[2];BOOK=ROOT/'他们不是人'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=json.loads((WORK/'只读基线.json').read_text(encoding='utf-8'))
changed=[rel for rel,h in base['files'].items() if not (ROOT/rel).is_file() or sha(ROOT/rel)!=h]
assert not changed,changed
state=json.loads((BOOK/'追踪/_tracking-state.json').read_text(encoding='utf-8-sig'))
assert state['state_revision']==104 and state['last_committed_chapter']==99
reports=['分段001-016.md','分段017-033.md','分段034-050.md','分段096-099.md','详细验收总报告.md']
for f in reports:assert (WORK/f).is_file()
main=(WORK/reports[-1]).read_text(encoding='utf-8')
for name in re.findall(r'第\d{3}章_[^`：:\n/；]+?\.md',main):
 assert (BOOK/'正文'/name).is_file(),name
checks=json.loads((WORK/'机械预检明细.json').read_text(encoding='utf-8'))
assert len(checks)==270
assert not any('Unknown option' in str(r['report']) or 'Usage: node' in str(r['report']) for r in checks)
lang=[r for r in checks if r['check']=='language' and r['returncode']]
ai=[r for r in checks if r['check']=='ai' and r['returncode']]
language_count=sum(len(r['report']['findings']) for r in lang)
ai_count=sum(sum(f.get('severity')=='blocking' for f in r['report'].get('findings',[])) for r in ai)
scope=list(range(1,51))+list(range(96,100))
missing=[n for n in range(1,51) if not (BOOK/f'追踪/逐章记录/第{n:03d}章.md').exists()]
result={'task_status':'complete','acceptance_verdict':'CONCERNS','scope':scope,'complete_read_chapters':54,'state_revision':104,'current_committed_chapter':99,'canonical_files_unchanged':True,'source_hashes':base['files'],'reports':{f:sha(WORK/f) for f in reports},'mechanical_checks':270,'language_blocked_chapters':len(lang),'language_findings':language_count,'ai_blocked_chapters':len(ai),'ai_blocking_findings':ai_count,'early_chapter_records_missing':missing,'review_does_not_accept_or_revise_fiction':True}
(WORK/'验收结论.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
status=ROOT/'.story-review/state.md'
body='''# 《他们不是人》专项详细验收状态（2026-10-06）

- 完整范围：001—050、096—099，共54章；全部全文取证与综合裁决完成。
- 方法：story-world-engine专项验收；三个普通只读分段助手与主会话综合裁决，不冒充未注册的story-review四角色full。
- 权威基线：修订104，接纳099；100—103正文锁定，104章冻结。所有基线正文/设定/大纲/追踪哈希未变。
- 结果：验收工作完成，内容判定CONCERNS。认知主结构、沈竹私人线利息、家庭有限保护与096—099接口成立，仍需定点修复。
- 下一批：无，本次54章验收结束。后续修复尚未实施，不能把本状态当正文修改或接纳凭据。
- 未解决摘要：002:5年龄与K007冲突（002/004/沈竹卡）；006:73、123→009:31通话时点（006/009）；016:201—207维护动作越过所见（014—016及后续维护判断）；030:7—13夜间活动过度证明知情（030/031）；034—050当前存在仅042:95参照，需独立拒绝及后果（034—050与后066—079）；018/020/024—026/030—031材料来源、副本和带离权限；04024h临时状态过期衔接；早期49章逐章记忆缺口；卷纲和CORE映射旧值；096:17作者编号，099:21午前写今晚。
- 语言门：7章16处精确白名单未覆盖token；AI模式：17章19处blocking；风格/标点无阻断。详表为只读检查，不代文学结论。
- 总报告：他们不是人/创作运行/2026-10-06_001-050及096-099详细验收/详细验收总报告.md。
- 上轮已结束审查状态保留在history/2026-10-05_综合审查已完成.md；已修旧问题不继续当未修继承。
'''
temp=status.with_name('state.next.md');temp.write_text(body,encoding='utf-8');os.replace(temp,status)
print(json.dumps({'task':'complete','verdict':'CONCERNS','chapters':54,'canon_unchanged':True,'missing_early_records':len(missing),'language_findings':language_count,'ai_blocking':ai_count},ensure_ascii=False))
