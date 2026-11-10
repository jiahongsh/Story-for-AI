# 网文写作工具集 — OpenCode + 通用 Agent / Web AI

本项目同时按 OpenCode(命令式)与通用文件方式接入 oh-story skills。

- **OpenCode 端**:`.opencode/agents/`、`.opencode/commands/`、`.opencode/plugins/story-hooks.ts` 已部署,`/命令` 可直接调用。
- **通用端**:`skills/*/SKILL.md` 与 `skills/*/references/` 可被任意 Agent 直接读取执行;无 hooks 时运行时硬拦截与多 agent 自动协作不生效,按软约束或 solo/direct 降级执行。

## Skill 路由表

| 命令 / 意图 | Skill | 说明 |
|------|-------|------|
| 任意小说创作、开书、大纲、角色、场景、对白、续写、重写 | story-world-engine + 对应写作 skill | 自动先执行人物七关、独立世界与章卷记忆；安装与用法见《story-world-engine 使用说明》 |
| `/story-long-write`、`/写长篇`、写长篇/开书/续写 | story-long-write | 长篇网文写作(逐章推进) |
| `/story-short-write`、`/写短篇`、写短篇 | story-short-write | 短篇网文写作(情绪驱动) |
| `/story-long-analyze`、`/长篇拆文`、长篇拆文 | story-long-analyze | 长篇小说深度拆解 |
| `/story-short-analyze`、`/短篇拆文`、短篇拆文 | story-short-analyze | 短篇小说拆文分析 |
| `/story-long-scan`、`/长篇扫描`、长篇扫榜 | story-long-scan | 长篇小说榜单与市场趋势 |
| `/story-short-scan`、`/短篇扫描`、短篇扫榜 | story-short-scan | 短篇小说榜单与情绪风口 |
| 数据分析、后台数据 | story-data-analyze | 后台数据归因，定位读者流失 |
| `/story-deslop`、`/去AI味`、去 AI 味 | story-deslop | 去除 AI 写作痕迹 |
| `/story-cover`、`/封面`、封面 | story-cover | 生成封面图 |
| `/story-review`、`/审查`、审查 | story-review | 多视角审查;无 custom agents 时降级单线程审查 |
| `/story-import`、`/导入`、导入 | story-import | 逆向导入已有小说到项目结构 |
| 作品查询 | story-explore | 只读查询进度、角色、伏笔与设定 |
| 资料研究 | story-research | 带来源的创作事实查证 |
| 发布材料 | story-release-package | 整理已审批作品的发布文案与清单 |
| 平台发布 | story-publish | 通过项目适配器预检、存草稿或正式发布 |
| `/story`、`/网文`、网文工具箱 | story | 工具箱路由 · 模糊意图自动分发 |
| `/story-setup`、`/准备写书`、部署 | story-setup | 环境部署 · hooks/rules/agents 一键部署 |
| `/browser-cdp`、浏览器登录态/抓取 | browser-cdp | 浏览器 CDP 工具;需平台允许本地脚本/浏览器控制 |

## 文件结构

- `skills/` — 项目本地 skills;Agent 应先读对应 `SKILL.md`,再按需读取 `references/`
- `拆文库/` — 拆文分析结果存放目录
- `{书名}/正文/` — 长篇小说正文章节
- `{书名}/正文.md` — 短篇小说正文
- `{书名}/设定/` — 角色设定、世界设定
- `{书名}/大纲/` — 卷纲、细纲
- `{书名}/追踪/` — `_tracking-state.json` 唯一结构化权威、固定 7 栏 `上下文.md` 续写状态卡、逐章紧凑记录、核心角色独立派生快照、伏笔当前视图、作者与读者双时间线;全部通过追踪工具生成
- `{书名}/对标/` — 对标作品分析

## 协作规则

Agent 间的协调关系由各 Agent 定义文件的职责边界描述,不需要独立协调规则文件。

## 通用使用约定

- **自主世界底层逻辑**：凡创作或改变小说人物行动、台词、情节，必须先读 `skills/story-world-engine/SKILL.md` 并与当前写作 skill 联用。每位行动者依次回答：知道什么、想要什么、怕失去什么、能力与权限是否允许、没有剧情需要仍会否这样选、愿付代价及现实约束、后果与他人的独立回应。任一未决不写该行动；未知/误信/失败可合理存在，作者全知不能授予角色。人物功能位与情绪公式不能覆盖这些要求。
- 所有有选择、有效台词或复现价值的人物各有角色卡与个人时间线引用；记录独立目标、欲望/缺陷、声线、知情来源与能力限制。幕后按故事时间和条件推进，不按章节配额制造事件；七关表不进正文。
- 每章/小节接受后记录实际事件、人物变化、埋/推进/回收伏笔与未结承诺；每卷/短篇完篇核对继承账。既有 `_tracking-state.json`仍是唯一正史追踪权威，新世界包及 `创作运行/派生视图/`只是来源绑定、可重建的辅助产物，不手改原追踪派生文件。
- 有 `设定/世界运行契约.json`且enabled为true的长篇候选，必须通过 `chapter_candidate.py`接入的写前/写后世界门；缺包、旧版本或换稿套包不得接纳。短篇按该技能适配，不冒用长篇候选工具。此逻辑适用于今后写作，不追溯伪造旧章七关证明。
- 写正文前先有大纲:长篇需要 `大纲/细纲_第N章*.md`,短篇需要 `小节大纲.md`。
- 无 hooks 的平台不会自动拦截越权写正文,Agent 必须在执行写作 skill 时自行检查大纲、上下文和追踪文件。
- 无 custom agents 的平台按 solo/direct 执行;遇到 skill 要求调用 story-architect、narrative-writer 等 agent 时,改由当前 Agent 直接完成,并在结果里说明降级。
- **去AI味自锁**(无 hook 平台此条是唯一防线):每章正文落盘后,同一轮内按当前写作 skill 自带脚本清零。能运行 node 时依次跑该 skill 目录下的 `language_gate.js`、`check-style-hygiene.js --check --fail-on=blocking`、`check-ai-patterns.js --check --fail-on=blocking`、`check-degeneration.js --check --language=zh --fail-on=blocking`。写下一章前先复查上一章无欠账。正文不写 HTML 豁免标记。
- 长篇「续写 / 继续写 / 日更」默认只写精确下一章的候选稿到 `{书名}/追踪/候选章/`。这些词不等于定稿。只有用户明确说接受或定稿,或本次任务事先说了自动定稿,才写入 `正文/`。
- **恐怖节拍与证据升级**：《他们不是人》的细纲与正文按 `他们不是人/大纲/恐怖节拍与证据升级硬约束.md` 执行——每 3-5 章至少一个可指认的恐怖 beat（L1 习惯→L2 证词→L3 监控/时间线→L4 制度权限），每个 beat 必须有“诡异细节+日常解释”，中段保留读者认知差，每个案件收尾必须落一个不可撤销的现实后果（门禁/医疗/居住/关系字段）。细纲五问未填不得开写。
- Compact / 新会话后优先读取 `{书名}/追踪/上下文.md` 恢复当前写作状态。

## story-world-engine 使用说明（所有 Agent 必读）

**安装位置**
- 唯一正本：`skills/story-world-engine/`（SKILL.md + `references/` + `assets/` + `scripts/`）。
- 运行时镜像（同一内容，供自动发现）：`.opencode/skills/story-world-engine/`、`.claude/skills/story-world-engine/`、`.codex/skills/story-world-engine/`、`.agents/skills/story-world-engine/`。
- 改动正本后，在仓库根运行 `pwsh -File skills/sync-story-world-engine.ps1` 同步镜像；镜像与正本冲突以正本为准。

**何时必须用**
任何涉及小说新行动、新台词、新事件或修改它们的任务（续写/开书/大纲/角色/场景/对白/重写/日更），先过本技能再写。纯查询、扫榜、封面、发布不触发。

**每章最小流程**
1. **恢复**：读 `{书名}/追踪/上下文.md` + 上一已接纳章 + 本章细纲；用原追踪工具校验 `_tracking-state.json` 与派生视图同步，不同步先重建。
2. **七关**：列出全部行动者，逐项填写 packet 字段 `knows/wants/fears/capability/no_plot/costs/consequences`。阻断条件只有一条：作者答不上原因；合理未知/待核写清边界后可过。
3. **写前包**：`python skills/story-world-engine/scripts/world_gate.py init ... --tracking-tool <原tracking_commit.py路径> --packet 追踪/候选章/第N章/{run-id}/世界引擎/写前行动审查.json`，填完跑 `check --phase prewrite`。
4. **写正文**：与 story-long-write 联用；七关表不进正文或台词。
5. **写后包**：复制冻结前包填 postwrite，跑 `check --phase postwrite`；先过原写作语言门，再按 `seven-gates.md §6` 七问复读。
6. **记忆闭环**：`python skills/story-long-write/scripts/tracking_commit.py` 串行提交；复检派生视图。
7. **卷末**：核对事件、得失、人物、计划、伏笔账、未履约承诺、下卷继承。

**关键边界**
- `world_gate.py` 只做检查/导出，不写正文、不写追踪、不接纳正史；追踪只走 `tracking_commit.py`。
- `init/check/export` 必须传同一个 `--tracking-tool`。
- 写前包/写后包必须放在候选 run 目录内，不能放 `创作运行/审查包/`。
- 无 python 或脚本缺失时降级人工并声明 `Fallback: story-world-engine tool unavailable -> manual`。
- 无 hooks 平台不会自动拦截，写作者必须自查（见上）。

## Compact 后恢复上下文

此部分在 compact 后自动生效。AGENTS.md 在每次 compact 后会被重新加载。
写作中的关键上下文:
1. 当前写作项目名称和进度
2. 最近讨论的角色设定变更
3. 未完成的伏笔列表
4. 当前章节的情绪/节奏目标

如果存在 {书名}/追踪/上下文.md,compact 后首先读取恢复上下文。

随后按story-world-engine恢复顺序校验权威版本，定点召回当前行动者卡、个人知情/时间线、未结承诺与本卷伏笔；卡片缺失或来源过期先修复，不凭聊天记忆补旧事实。
