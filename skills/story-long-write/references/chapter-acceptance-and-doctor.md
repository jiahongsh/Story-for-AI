# 章节候选、接纳与投影自检协议

正文不是模型生成后立即成立的事实。默认链路固定为：

```text
精确一章许可 → 隔离候选稿 → 三道正文硬 Gate + 声音/近章结构 advisory → 用户接纳 → 原子写入正文
→ 逐章追踪事务 → 提交凭证闭环 → 更新声音画像 → story doctor
```

## 授权模式

- `review`（默认）：用户说“续写/继续写/写下一章”只授权生成**下一章候选稿**。Agent 展示标题、字数、关键变化、Gate 结果和候选路径后停止。只有用户随后明确说“接受/定稿/采用这版”，才能执行 `approve` 与 `promote`。
- `auto`（显式选择）：只有用户在本次任务中明确说“自动定稿/无需逐章确认/连续写完并自动定稿”才可启用。初始化时必须把这句授权的含义写入 `--authorization-note`。它不是全书永久设置；本次任务结束、用户中断或出现结构性分歧即失效。
- “继续”“续写”“再写一章”本身不等于“接受当前候选”。用户要求修改候选时，只改候选稿并重新跑 Gate，不触碰正式正文。

## 精确章节许可

每个工作区只绑定 `last_committed_chapter + 1`、一个细纲、一个正文目标和当时的 `state_revision`。同一项目同时只能有一个未闭环候选；旧候选未接纳、放弃或完成追踪闭环前，不能创建下一章。

下列命令中的 `{PYTHON}` 先按平台探测可用的 Python 3 解释器，再用实际命令替换。

```bash
{PYTHON} skills/story-long-write/scripts/chapter_candidate.py init \
  --project "{项目根}" \
  --chapter {N} \
  --outline "大纲/细纲_第{N}章.md" \
  --target "正文/第{N}章_{标题}.md" \
  --base "大纲/卷纲_第X卷.md"
```

脚本自动绑定 `追踪/上下文.md` 和上一章正文；`--base` 再加入会决定本章有效性的总纲、卷纲、题材契约或设定。Agent 只向命令返回目录中的候选正文文件写稿，不得直接新建正式正文。

候选完成后运行：

```bash
{PYTHON} skills/story-long-write/scripts/chapter_candidate.py check --run "{候选运行目录}"
```

`check` 同时验证基础文件/追踪修订未变化，并依次运行中文语言锁、AI 模式 blocking 检查、中文退化 blocking 检查、`accepted-voice-profile` 本书声音对照，以及 `chapter_shape_gate.py` 近章结构证据包。前三项任一失败或候选摘要变化都必须重新审阅；接纳基线与作者精选黄金样本的声音漂移只作双向 advisory，具体语义见 `accepted-voice-profile.md`；结构证据必须按 `cross-chapter-shape.md` 的五问做语义复核，不因数值接近自动改文。任一已配置画像本身过期属于数据来源错误，会阻断继续使用旧范围。

## 接纳、写入与追踪闭环

用户明确接纳（或本次任务有有效 `auto` 授权）后：

```bash
{PYTHON} skills/story-long-write/scripts/chapter_candidate.py approve \
  --run "{候选运行目录}" --confirm ACCEPT \
  --approval-note "{用户本次接纳或自动定稿授权摘要}"

{PYTHON} skills/story-long-write/scripts/chapter_candidate.py promote \
  --run "{候选运行目录}" --confirm PROMOTE
```

`promote` 原子写入正式正文，并生成 `追踪/章节提交/第NNN章.json`；其中保存已接纳正文的 SHA-256、上下文指纹和追踪修订前值。随后按 `tracking-transaction.md` 提交本章唯一追踪事务，再闭环：

```bash
{PYTHON} skills/story-long-write/scripts/chapter_candidate.py close --run "{候选运行目录}"
{PYTHON} skills/story-long-write/scripts/voice_profile.py update --project "{项目根}"
{PYTHON} skills/story-long-write/scripts/story_doctor.py --project "{项目根}"
```

`close` 要求 `last_committed_chapter` 精确等于本章且 `state_revision` 已推进，并把正文摘要、状态修订和派生视图摘要追加到 `追踪/投影日志.jsonl`。声音画像尚未配置时 `update` 安全返回 `not_configured`；已经配置时必须把新回执纳入。`doctor` 复核：

- `_tracking-state.json` 与全部派生视图一致；
- 没有 draft / approved / promoted 的悬空候选；
- 已接纳正文未被静默手改；
- 已配置的接纳声音画像，以及作者精选的黄金声音样本，仍绑定当前已接纳正文；
- 修订事务已闭环；
- 最新同修订号投影未漂移；卷末要求时还要有闭环冷读账本。

任何 error 都阻止下一章。旧项目没有历史提交凭证时只从下一章起建立，不伪造旧章凭证；如要让既有旧章成为声音样本，必须按 `accepted-voice-profile.md` 由作者显式批准连续范围。

## 候选退回与合法修订

未写入正式正文的候选可显式放弃：

```bash
{PYTHON} skills/story-long-write/scripts/chapter_candidate.py abandon \
  --run "{候选运行目录}" --confirm ABANDON --reason "{原因}"
```

正式正文一旦写入，不得用候选命令覆盖。任何手工回改先走 `revision-governor` + `revision_guard.py` + 追踪修订事务；全部闭环后，用 `sync` 更新已接纳正文摘要：

```bash
{PYTHON} skills/story-long-write/scripts/chapter_candidate.py sync \
  --project "{项目根}" --chapter {N} \
  --revision-manifest "追踪/修改影响/active.json" \
  --revision-stamp "追踪/修改影响/active.approved.json" \
  --reason "{修订原因}" --confirm SYNC
```

`sync` 会再次运行修订门禁；它不是绕过摘要失效检查的快捷开关。

合法修订导致接纳正文摘要变化后，声音画像会刻意进入 `stale`。修订事务和 `sync` 全部通过后再运行 `voice_profile.py update`；由旧章显式批准、但没有回执的样本发生变化时，不得静默更新，必须重新审阅并再次确认旧章范围。
