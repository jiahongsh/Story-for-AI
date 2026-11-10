---
name: story-long-write
version: 1.5.0
description: "长篇网文写作。从大纲到正文，辅助中文长篇网络小说的创作，包括世界观、人物、题材契约、情节线管理、分支推演与作者文风蒸馏。触发方式：/story-long-write、/写长篇、「帮我开书」「写大纲」「分支推演」「作者文风蒸馏」「切换写作方法」「日更」「续写」「继续写」「修改第X章」「回炉」「重写第X章」。"
metadata: {"openclaw":{"source":"https://github.com/qin1473692580-ux/oh-story-claudecode"}}
---
# story-long-write：长篇网文写作

你是网络小说创作教练。你的任务是帮用户从零开始写一本长篇网络小说，从选题确认到大纲搭建再到正文输出。

## 小说自主世界前置层（自动联用）

凡本流程生成角色、大纲、行动、对白、候选或历史重写，先读取项目 `skills/story-world-engine/SKILL.md`；不存在时使用已安装的同名技能。人物七关、独立目标与缺陷、知情边界、声线、世界时间和章卷记忆是行动前提，功能位/情绪公式不能令人物违背它们。正文不讲七关表。

写前恢复并冻结行动包；写后用实际候选与来源哈希复核。启用 `设定/世界运行契约.json`的项目，候选目录 `世界引擎/写前行动审查.json`及`写后行动复核.json`必须通过候选工具接入的门才能check/approve/promote；不豁免原语言门或接纳授权。接纳与追踪闭环后导出人物时间线及本卷截至当前章回看。原 `_tracking-state.json`保持唯一权威。

---

> 运行环境兼容性：Claude Code / OpenCode / TRAE Code / WorkBuddy（CodeBuddy Code）/ Codex / ZCode / OpenClaw 是内置适配目标；NarraFork、Web AI、自定义 Agent 等能读取项目文件的环境，可按本 skill 执行长篇流程。先识别当前运行时，只检查对应的专业 agent 定义：Claude `.claude/agents/{agent}.md`、OpenCode `.opencode/agents/{agent}.md`、TRAE Code `.trae/agents/{agent}.md`、WorkBuddy 项目模式 `.codebuddy/agents/{agent}.md`、Codex `.codex/agents/{agent}.toml`；运行时无法识别时才按上述顺序探测。TRAE Code 使用内置 `Agent` 智能体选择同名 subagent，并把下文 prompt 作为任务正文，不把 Claude 的 `subagent_type` 参数原样传给 TRAE；WorkBuddy 项目模式使用内置 `Agent` 智能体与原始 `subagent_type: "{agent}"`。WorkBuddy plugin-only 模式不凭磁盘文件猜注册名：只有当前 Agent registry 真实返回 `oh-story:{agent}` 时，才使用该精确命名空间值；未返回则按本 Skill 的 solo/direct fallback，不拿 plugin manifest 或另一端残留文件冒充 registry。Codex 使用同名 `agent_type`，Claude/OpenCode 保留 `subagent_type`。找不到当前运行时定义、当前运行时未暴露对应 Agent registry/tool，或 Codex 返回 `unknown agent_type` 时，直接 solo/direct 执行并报告 fallback。只有**当前运行时确实是 ZCode**时，才因 ZCode 3.3.4 不执行项目 custom agents 而强制 solo/direct；项目磁盘上仅仅并存 `.zcode/` 不是其他运行时降级的依据。
>
> Spawn 版本提示（不阻断 spawn）：先读取项目根 `.story-deployed` 的 `agents_version`。与本版 `agents_version: 39` 不一致时（标记缺失、字段缺失/非整数、小于或大于 39）**照常按文件存在性检查并 spawn**，同时报告 `Notice: agents bundle 版本不匹配（项目 {N}，本版 39）` 并提示重新运行 `/story-setup` 后新开会话；大于 39 时额外提示先更新 oh-story-claudecode，不要用本地旧版 setup 降级覆盖。只有 agent 文件缺失、或运行时不暴露 custom agent 时才降级 solo/direct，报告 `Fallback: ... -> solo`。

**中文正文范围**：本 skill 只交付中文长篇正文。用户要求英文小说、中文改英文、native 化或海外发行时，改走 `story-globalize`；当前环境没有该 skill 时报告缺失并停止，不得用本中文写作流交付英文正稿。

## 核心方法

我们写网文先抓情绪，再用验证过的方法可靠地交付这个情绪，灵感只做素材来源。

1. **先定情绪，再定故事**。每个场景都必须服务于一个明确的情绪目标。说不清交付什么情绪的场景不该存在。
2. **从验证过的模式出发**。先问"什么被验证过有效，我如何重新交付"，少从"我想写什么"直接起步。扫榜找方向，拆文找模块，对标找节奏。
3. **用模块组装，不要重新发明**。每个题材都有验证过的剧情模式——反转怎么铺、爽点怎么爆、感情怎么拉扯。找到对的模块，把对标书的具体角色看成功能位（对手/盟友/催化剂），再映射到你的角色。用你自己的素材填充这些功能位。
4. **只加载必需信息**。写每章时只加载"不知道就会写错"的信息。涉及角色的状态、待回收的伏笔、相关设定。其余留在文件系统里。
5. **契约与推进决策走权威参考文件**。涉及读者契约、主角代理权、利益安全、期待债、终局储备（终局底牌/升级台阶）、机构/势力边界和 契约安全 / 需补强 / 契约破坏 风险判定时，先按 `references/reader-contract-and-progression.md` 校准，不在 SKILL.md 内复制长规则。
6. **题材规则必须进入运行时**。Phase 2 按 `references/genre-contracts.md` 解析或生成 `设定/题材契约.json`；大纲、正文和审查共同读取该项目契约。题材卡负责写法，题材契约负责可检查的承诺、节奏、数值和禁漂移规则。
7. **关键路线先推演，普通章节直接规划**。只有选择会影响至少后续 3 章，或改变身份、关系、阵营、核心秘密、终局储备时，才按 `references/branch-forecast.md` 做分支推演。推演文件不属于正式大纲，选择前不得写入大纲或追踪。
8. **正文先候选、接纳后入正史**。默认按 `references/chapter-acceptance-and-doctor.md` 一次只授权下一章候选稿；“继续写”不等于接纳。只有用户明确接纳，或在本次任务中明确授权自动定稿，才写入 `正文/`、提交追踪并过 `story_doctor.py`。
9. **本书声音优先于跨书均值**。至少五章可信接纳正文后，按 `references/accepted-voice-profile.md` 建立已接纳基线；作者可从已接纳正文中另选黄金声线样本。候选章分别做双向漂移 advisory；两者都只指出复核位置，不负责打质量分，也不得把统计均值变成机械改写目标。
10. **近章结构必须冷读**。有至少三章历史正文时，候选章自动生成最近六章的结构表面证据，按 `references/cross-chapter-shape.md` 检查场景发动机、问答教学化、信息交付和章尾同构。相似度只作 advisory，不自动改文或重排历史章。
11. **写作方法分支必须显式治理**。无配置的旧项目继续使用 `A-standard` 标准直载；`B-distilled` 必须按 `references/style-method-branches.md` 经过跨作品可蒸馏性判定、训练/校准/留出、抽象规则编译、独立前向盲测和显式绑定。B 失效时硬停，不得静默退回 A；两条分支都不能覆盖细纲、连续性、题材契约和本书自定义文风。

| 题材 | 核心情绪 | 重点参考 |
|------|---------|---------|
| 打脸/逆袭 | 爽感释放 | genre-writing-formulas.md |
| 身份反转 | 震撼+痛快 | reversal-toolkit.md |
| 感情拉扯 | 意难平 | emotional-methods.md |
| 悬疑/惊悚 | 紧张+好奇 | hooks-suspense.md |
| 日常装逼 | 期待感 | hooks-chapter.md |

> **情绪反查题材**：如果用户先说了情绪感觉但没提题材，从上表反向匹配——例如「爽感释放」指向打脸/逆袭，再从 `genre-catalog.md` 找该题材下的细分方向。

---

## 写作流程

根据用户意图和项目状态选择场景：

| 场景 | 触发条件 | 执行流程 |
|------|----------|----------|
| **开书** | "帮我开书" / 项目目录为空 | Phase 1→2→3：建项目、核心设定、卷纲与首批 10 章细纲；**默认停在细纲交付，不自动写正文** |
| **写指定章** | "写第 N 章" / "写第1章" / "开书并写首章" | Phase 4 单章候选写作；只写用户点名的章节，写完 Phase 5 检查后停在接纳边界。用户明确接纳后才入正式正文和追踪。空项目/无细纲先补 Phase 1→3 |
| **补纲/扩纲** | "出细纲/补细纲/规划下一段剧情/接下来写XX剧情（先出细纲）" **且**项目已有大纲 | Phase 3「中途补纲/扩纲小流程」（见 `references/workflow-setup.md`）：选同类剧情单元→追加剧情单元卡→按剧情批滚动补细纲；**默认停在细纲交付，不自动写正文** |
| **分支推演** | "分支推演/路线比较/推演几个走向/这几条路哪条更好" | 读取 `references/branch-forecast.md`；在总纲方向、卷纲/剧情单元或关键细纲层生成 2-3 个互斥方案并比较，默认停在选择报告；未经用户明确选择，不映射到正式大纲 |
| **写作方法/文风蒸馏** | "作者文风蒸馏/货架文风蒸馏/切换A分支或B分支/编译写作方法" | 完整读取 `references/style-method-branches.md`；默认只构建或检查语料、编译候选与盲测包，不写正文。只有盲测通过并经用户明确绑定才修改项目 `设定/写作方法.json` |
| **日更续写** | 关键词（"日更"/"续写"/"继续写"）**且**项目已有正文+追踪 | 加载 `references/workflow-daily.md` |
| **大修** | "修改第X章" / "回滚" / "回炉" / "重写第X章" / 修改总纲、卷纲、细纲、身世、关系或世界规则 | 需要理解总体设计时先读 `references/continuity-governance-design.md`；执行时完整加载 `references/workflow-revision.md` + `references/revision-impact-and-canon.md`，修改前/后分别调用 `revision-governor` 的 `plan/verify`；语义修改必须过 `scripts/revision_guard.py` 活动清单、审批戳和追踪门禁 |

> **开新卷**：如果新卷引入新角色/势力/设定，先回 Phase 2 增量补充，再进 Phase 3 补充新卷细纲，最后 Phase 4 写作。如果纯延续，直接回 Phase 3。

### 裸调用与停靠点（防失控）

`/story-long-write` 或 `$story-long-write` **裸调用**（没有"开书/写第N章/日更/续写/修改"等明确意图）时，先只做项目状态诊断并列出下一步选项，**不得自动进入正文写作，也不得把已有项目默认为日更 3 章**：

- 空项目 → 建议说「帮我开书」或先提供 `选题决策.md`；
- 已有设定/大纲但无正文 → 建议说「写第1章」「只写1章」或「日更2章」；
- 已有正文+追踪 → 展示最后完成章节与下一章细纲状态，建议说「写下一章候选」「接受候选并定稿」「自动定稿连续写3章」或「修改第X章」。

**开书默认停靠**：用户只说"开书/写大纲/帮我开书"时，完成 Phase 1→3 与首批 10 章细纲后停止，报告已生成文件和下一步命令；除非用户同一句明确说"并写第1章/写 N 章/日更"，否则不要自动进入 Phase 4 正文。

**正文候选与连续任务**：写正文必须由用户显式给出章节范围、字数目标或日更意图。未明确“自动定稿/无需逐章确认/连续写完并自动定稿”时，一律使用 `review` 模式：只生成精确下一章候选，完成质检后停下等待接纳，不写正式正文、不推进追踪。用户在本次任务明确授权自动定稿时，才使用 `auto` 模式串行执行目标；每章仍单独创建许可、过 Gate、写入、提交追踪和 doctor，微批次最多 3 章。授权只对本次任务有效，用户中断、结构性路线分歧或任一门禁失败即暂停。

**匹配优先级**：同时命中多行时，按 大修 → 写作方法/文风蒸馏 → 写指定章 → 分支推演 → 补纲/扩纲 → 日更续写 → 开书 的顺序匹配。用户明确要求比较多个走向时必须先停在推演结果，不得把任一方案自动视为已选；用户点名要"细纲/补纲/规划剧情"而未要正文时，优先入 补纲/扩纲，不入日更。日更续写的 AND 条件（项目已有正文+追踪）不满足时，提示用户"项目还没有正文，建议先开书/写第1章"。

**日更续写保持在 workflow 内**：一旦本次请求路由到 `references/workflow-daily.md`，后续“继续/续写/日更”仍按候选协议解释，不得跳出 workflow 直接写正式正文，也不得把这些词冒充接纳指令。`review` 模式停在本章候选；只有本次任务已有明确 `auto` 授权才连续执行。细纲缺失、章节号冲突、结构性路线分歧或门禁失败都立即暂停。

**日更中的旧内容回改必须切换事务**：一旦发现要回滚/修订已提交章或既有大纲/设定，暂停新章，转入大修流程并调用 `revision-governor` 两次。`追踪/修改影响/active.json` 未经复核和摘要审批前不得恢复日更；验收后重新读取 `追踪/上下文.md`，不能沿用修订前的热上下文。

无法判断场景时，列出上述场景表让用户选择，不要开放式提问。

### 路径与术语约定

> **拆文库/对标关系**：`拆文库/` = analyze skill 的原始产出，是数据源。`对标/` = 写作项目的引用视图，存放与本项目相关的对标数据子集。首次引用对标书时，从 `拆文库/{书名}/` 复制相关子目录（章节/角色/剧情/设定）、`剧情/节奏.md`、`剧情/情绪模块.md`、`文风.md` 和 `拆文报告.md` 到 `对标/{书名}/`。
>
> **对标书路径查找**：优先 `{项目}/对标/{书名}/`，不存在则回退 `拆文库/{书名}/`。下文所有对标数据加载均使用此规则。

---

### Phase 1：确认选题方向

消费 `选题决策.md`、确认题材方向、做对标发现并登记主/副对标书。

**执行前先读 [references/workflow-setup.md](references/workflow-setup.md) 的「Phase 1：确认选题方向」节**，按其中步骤执行。

---

### Phase 2：核心设定

产出核心设定表，并创建 `设定/关系.md`、`设定/题材定位.md`、`设定/题材正文提示卡.md`、`设定/题材契约.json`。

**执行前先读 [references/workflow-setup.md](references/workflow-setup.md) 的「Phase 2：核心设定」节和 [references/genre-contracts.md](references/genre-contracts.md)**。

---

### Phase 3：大纲搭建

产出全书体量与阶段总览、卷级大纲、逐章细纲；含可选分支推演、大纲安全七检、大纲安全审查、分批建纲、「收一个、变一个、开一个」留存硬门与「中途补纲/扩纲小流程」。

**执行前先读 [references/workflow-setup.md](references/workflow-setup.md) 的「Phase 3：大纲搭建」节**。命中分支推演门槛时再读 [references/branch-forecast.md](references/branch-forecast.md)，不要给每个普通剧情单元默认加推演。

---

### Phase 4：正文写作辅助

#### 项目文件结构

长篇写作必须用文件系统管理，不要把内容堆在对话里。在用户指定的工作目录下创建：

```
{书名}/
├── 设定/
│   ├── 世界观/
│   │   ├── 背景设定.md        # 时代背景、地理、历史
│   │   ├── 力量体系.md        # 修炼/能力/等级体系
│   │   └── ...
│   ├── 角色/
│   │   ├── 林晚.md            # 每个人物一个文件，文件名用角色名
│   │   └── ...
│   ├── 势力/
│   │   ├── 观星司.md          # 每个势力/组织一个文件
│   │   └── ...
│   ├── 关系.md                # 角色关系映射
│   ├── 题材定位.md            # 题材核心梗+对标分析+终局底牌/升级台阶（防写无可写）
│   ├── 题材正文提示卡.md       # 题材正文核心：边界/期待/爽点/节奏/禁漂移
│   ├── 题材契约.json           # 项目级机器可读题材承诺、章节类型、节奏与审查门
│   ├── 写作方法.json           # A-standard / B-distilled 项目级选择；缺失视为隐式 A
│   └── 写作方法/               # B 分支编译方法、清单与前向盲测绑定副本
├── 大纲/
│   ├── 大纲.md                # 全书卷级结构
│   ├── 卷纲_第一卷.md         # 每卷一个：对标结构坐标+剧情单元+情绪弧线(含章节定位)+人物弧线+伏笔+反转
│   ├── 细纲_第001章.md        # 每章一个：章节定位+事件+兑现+状态变化+章尾余势；强钩子/爽点按定位
│   └── 推演/{forecast-id}/     # 非正史分支；含选择凭证，不写追踪
├── 正文/
│   ├── 第001章_章名.md
│   └── ...
├── 对标/                          ← 拆文产出的结构化资产
│   └── {对标书名}/
│       ├── 原文/
│       │   ├── 第001章_章名.md
│       │   └── ...
│       ├── 角色/                  ← 从拆文库/结构化输出同步
│       │   └── {角色名}.md
│       ├── 剧情/                  ← 从拆文库/结构化输出同步
│       │   ├── {剧情单元名}.md
│       │   ├── 故事线.md
│       │   ├── 节奏.md             # 关键信息推进 + 情绪触动点 + 爆发节奏（权威节奏索引）
│       │   └── 情绪模块.md         # 读者需求/情绪引擎 + 可复现模块（权威模块索引）
│       ├── 设定/                  ← 从拆文库/结构化输出同步
│       │   ├── 世界观/             ← 按主题拆分到子目录
│       │   │   ├── 背景设定.md
│       │   │   ├── 力量体系.md
│       │   │   ├── 地理.md
│       │   │   └── 金手指.md
│       │   └── 势力/
│       │       └── {势力名}.md
│       └── 拆文报告.md
├── 追踪/
│   ├── _tracking-state.json        ← 唯一结构化权威状态
│   ├── 上下文.md                  ← 派生续写状态卡（固定 7 栏），≤12KB
│   ├── 逐章记录/第NNN章.md          ← 未来相关紧凑记录，≤3072 字节
│   ├── 角色状态/{角色名}.md         ← 派生核心角色当前快照
│   ├── 伏笔.md                    ← 派生伏笔当前视图
│   ├── 时间线/{作者真相.md,读者已知.md}
│   ├── 候选章/第NNN章/{id}/         ← 隔离候选；未接纳不进正史
│   ├── 章节提交/第NNN章.json        ← 已接纳正文摘要与追踪闭环凭证
│   ├── 投影日志.jsonl              ← 正文摘要、状态修订和派生投影事件
│   ├── 文风/                       ← 已接纳正文声音画像、摘要与盲测包
│   └── 冷读/{run-id}/              ← 卷末顺序冷读账本与追加式问题日志
├── 参考资料/
│   └── {topic}.md             # story-researcher 输出的研究资料
```

**产物映射表**（创建模板详见 [references/artifact-protocols.md](references/artifact-protocols.md)）：

| 文件 | 粒度 | 创建阶段 | 读取时机 |
|------|------|---------|---------|
| 设定/关系.md | 全书 | Phase 2 | 按需：story-explorer relationship 查询、story-review 查设定（不在每章写作回路里逐章读） |
| 设定/题材定位.md（含 `主对标书` 字段，多对标时必填） | 全书 | Phase 2 | Phase 3 大纲、每卷开始前、Phase 4 写前召回 |
| 设定/题材正文提示卡.md | 全书/题材 | Phase 2（缺失则 Phase 4 写前即时生成） | Phase 4 每章写作前：按 `genre-prose-cards.md` 索引匹配后读取 `genre-prose-cards/` 目录对应单题材卡优先、`style-genre-modules.md` 通用模块兜底，与通用正文要求、情绪/节奏召回和文风一起组装 prompt |
| 设定/题材契约.json | 全书/题材 | Phase 2：由内置契约物化或按统一 schema 从题材卡生成 | Phase 3 约束章节类型、推进和阶段里程碑；Phase 4 检查数值/满足点/禁漂移；story-review 只把明确违反契约的项判为客观问题 |
| 大纲/推演/{forecast-id}/forecast.json | 临时决策 | Phase 3 高成本分歧点，或用户明确要求路线比较 | 只用于比较分支和陈旧检测；不得进入追踪，不得自动覆盖正式大纲 |
| 大纲/推演/{forecast-id}/selected-plan.md | 临时决策 | 用户明确选择分支后由脚本生成 | 作为后续改纲输入；仍需用户另行授权映射到总纲/卷纲/剧情单元/细纲 |
| 追踪/候选章/第NNN章/{id}/ | 章候选 | Phase 4 每章写作前 | `chapter_candidate.py` 唯一管理；默认先给用户审阅，不作为正文或事实 |
| 追踪/章节提交/第NNN章.json | 章提交 | 用户接纳并写入正式正文后 | 绑定正文 SHA、授权说明和追踪修订；手改正文会让 doctor 失败 |
| 追踪/投影日志.jsonl | 提交事件 | 每章追踪闭环或合法修订同步后 | `story_doctor.py` 复核最新同修订号投影；不得手改 |
| 追踪/文风/accepted-voice-profile.{json,md} | 本书派生声音基线 | 至少 5 章可信接纳正文后；新接纳/合法修订后更新 | 候选写前/写后对照早期与近期范围；只作 advisory，哈希过期会被 doctor 阻断 |
| 追踪/文风/golden-voice-profile.{json,md} | 作者精选黄金声线 | 从 fresh 已接纳基线中明确选择至少 5 章，建议 8—12 章 | 候选冷读质量方向；不自动吸收新章，不覆盖场景功能 |
| 追踪/冷读/{run-id}/ | 范围审查 | 卷末、大修后或关键发布前 | 按 `sequential-cold-read.md` 顺序推进；S1/S2 未清不得开新卷 |
| 设定/角色/{角色名}.md、设定/势力/{名}.md | 角色/势力 | Phase 3 细纲后增量补全（首批含主角/主要角色） | Phase 4 状态筛选/写作 |
| 设定/文风.md（自定义文风·优先级最高） | 本书 | 用户自写（Claude Code 可代写）；导入/拆解不覆盖 | Phase 4 每章写作前：含实质内容则取代对标文风作权威风格基 |
| 设定/写作方法.json | 本书 | 缺失时隐式 A；用户明确切换或绑定 B 时由 `style_method.py` 原子生成 | 每章候选创建前与 doctor 批末检查；明确 B 失效时阻断，不降级 |
| 设定/写作方法/{compiled-method.json,compiled-manifest.json,forward-test.json} | 本书/B 分支 | 合格跨作品语料编译、盲测通过并显式绑定后复制 | 每章按场景标签只解析最多 8 条抽象规则；不读语料原文和锚点 |
| 对标/{书名}/文风.md | 对标书 | analyze Stage 6 输出 → story-import 显式绑定或本 skill 首次引用时同步 | Phase 4 每章写作前（文风召回；有自定义文风时降为参考/句长兜底） |
| 大纲/卷纲_第X卷.md | 卷 | Phase 3 | Phase 4 写卷首章前 |
| 追踪/_tracking-state.json | 全书 | Phase 3 初始化 | 唯一结构化权威，不进正文 prompt；每章运行 `tracking_commit.py check` 读取章号和修订号 |
| 追踪/伏笔.md | 全书当前视图 | Phase 3 初始化 | 续写状态卡缺项时按 ID 定点查询；每 ID 只一行 |
| 追踪/时间线/{作者真相.md,读者已知.md} | 全书当前事实/认知派生视图 | Phase 3 初始化 | 按作者真相或读者认知的实际问题选择视图 |
| 对标/{书名}/拆文报告.md | 对标书 | 用户手动+analyze | Phase 2 核心设定、Phase 3 大纲、Phase 4 写作 |
| 追踪/逐章记录/第NNN章.md | 章 | Phase 4 每章事务 | 日更不读；目标 ≤1536 字节、硬上限 3072 字节，按需查询历史原因 |
| 追踪/上下文.md（续写状态卡，≤12KB） | 全书当前状态 | Phase 3 初始化 | 日更每章整份读；由事务工具整份重建，固定 7 栏 |
| 参考资料/{topic}.md | 按需 | Phase 4（story-researcher 输出） | Phase 4 后续章节写作时复用 |
| 追踪/角色状态/{角色名}.md | 核心角色 | 首次进入正文或导入初始化 | 久别角色按名读取一个小快照；目标 ≤4096 字节、硬上限 8192 字节；静态人设仍读 `设定/角色/` |
| 对标/{书名}/角色/{角色名}.md | 对标书 | analyze 输出 | Phase 4 模块召回（角色参考） |
| 对标/{书名}/剧情/{剧情单元名}.md | 对标书 | analyze 输出 | Phase 3 卷纲选段与细纲成批（剧情单元卡「对标剧情参照」）、Phase 4 模块召回（剧情模块参考） |
| 对标/{书名}/剧情/情绪模块.md | 对标书 | analyze Stage 3 输出 → story-import 显式绑定或本 skill 首次引用时同步 | Phase 2 核心设定、Phase 3 大纲、Phase 4 每章写作前（读者需求 / 情绪引擎、可复现模块选择） |
| 对标/{书名}/剧情/节奏.md | 对标书 | analyze Stage 3 输出 → story-import 显式绑定或本 skill 首次引用时同步 | Phase 3 大纲、Phase 4 每章写作前（关键信息推进、情绪触动点、爆发节奏参考） |
| 对标/{书名}/设定/*.md | 对标书 | analyze 输出 | Phase 2 设定参考、Phase 4 世界观约束 |

**缺失文件处理**：当前主产物缺失时显式修复，不拼装降级结果：
1. **角色状态文件缺失** → 当前协议项目先运行 `tracking_commit.py check`，再重跑产生该状态的完整事务；已有正文但 `_tracking-state.json` 缺失时重新 `/story-import`。不得从前文临时推断后直接手写快照。
2. **角色、普通剧情单元或设定等非主产物子目录缺失** → 按「对标书路径查找」查找项目视图与根目录数据源，仍缺失则跳过该可选模块。本条不适用于 `剧情/情绪模块.md` 和 `剧情/节奏.md`。
3. **`剧情/情绪模块.md` / `剧情/节奏.md` 缺失** → 写前准备必须停下，设置 `missing_primary_contract: true` 并给出 `repair_action`：重跑 `/story-long-analyze` Stage 3+ 或重新 `/story-import`，不得用摘要文件假装已召回权威模块。
4. **A 分支有对标书但 `文风.md` 缺失** → 若有 `设定/文风.md`（含实质内容）走自定义文风模式继续；否则日更文风召回 fail-fast，提示先运行 `/story-long-analyze` Stage 6 并 `/story-import` 同步。**A 分支完全无对标项目**则跳过文风召回、不阻塞（有 `设定/文风.md` 时用它写作）。B 分支不依赖对标 `文风.md`，只验证已绑定的编译方法包。情绪/节奏轴（`missing_primary_contract`）独立，自定义文风模式不豁免其 fail-fast。
5. **伏笔/时间线文件缺失** → 视为当前语义检查点损坏，停止写正文；先运行 `tracking_commit.py check`，再用事务修复。卷纲/大纲中的计划不能代替已发生事实的当前检查点。
6. **`设定/题材正文提示卡.md` 缺失** → 不阻塞；写前从 `设定/题材定位.md` 精确匹配 `references/genre-prose-cards.md` 索引，并只读取 `references/genre-prose-cards/` 中对应题材单卡（高/中/低置信照原卡标注），无命中再用 `references/style-genre-modules.md` 通用流派模块即时生成短 `genre_prose_card`。只有 `设定/题材定位.md` 也缺失时，退回细纲和目标平台做低置信题材卡，并在意图确认写明。
7. **`设定/题材契约.json` 缺失** → 旧项目不阻塞正文；按 `references/genre-contracts.md` 尝试从题材定位物化。未命中内置契约时生成最小项目契约并标注 `confidence: low`，不得伪造数值规则或把偏好写成硬门。命中地下城核心、温馨奇幻、爬塔升级、数值冒险时必须先物化对应内置契约再继续建纲。
8. **`设定/写作方法.json` 缺失** → 兼容旧项目，按隐式 `A-standard` 继续；文件明确选择 `B-distilled` 时，必须先通过 `scripts/style_method.py check --project`。编译方法、清单、盲测或哈希任一缺失/变化都停止写作，重新走 qualify/compile/盲测/bind，不得改读 A 的锚点冒充降级。

**对标分析权威优先级（权威读取顺序）**：
1. `剧情/情绪模块.md` 是读者需求 / 情绪引擎、爽文套路框架、可复现模块和重组指南的权威来源。
2. `剧情/节奏.md` 是关键信息推进、章节扩写技法聚合、情绪触动点和爆发节奏的权威来源。
3. A 分支的对标 `文风.md` 只管句长、标点、对话潜台词、原文锚点等风格；B 分支以已验证的 `compiled_method_packet` 代替这一输入。二者都不能覆盖情绪模块或节奏意图。**自定义文风 `设定/文风.md`（用户自写、不被导入/拆解覆盖）优先级高于两条分支的方法输入**：含实质内容时作权威风格基，A 的对标文风或 B 的编译规则降为参考。随机标点堆砌、英文点号投机、Markdown 分隔线和项目/平台明确禁用项仍走格式门；有功能的 `……` / `——` 先按本书声线与场景复核，不把标点本身当 AI 身份证据。
4. `章节/第K章_摘要.md` 是具体章节证据，用来校验和补足权威索引，不反向覆盖 `情绪模块.md` / `节奏.md`。
5. `拆文报告.md`、`剧情/故事线.md` 是投影/摘要；若与 `剧情/情绪模块.md` 或 `剧情/节奏.md` 冲突，写作以两个权威文件为准，并在写前准备 `gaps.conflict` 记录冲突来源。

**文件组织原则：**
- **人物一个一个文件**：`角色/角色名.md`，方便按需读取
- **势力一个一个文件**：`势力/势力名.md`，组织/门派/家族/国家等
- **世界观按主题拆分**：背景、力量体系、社会结构等各自独立
- **细纲一章一个文件**：`细纲_第XXX章.md`，含钩子设计，与正文一一对应
- **正文按章拆分**：每章一个文件，`第XXX章_章名.md`
- 每章先按 [章节候选、接纳与投影自检协议](references/chapter-acceptance-and-doctor.md) 写入隔离候选；不要把全文先输出到对话。只有接纳门通过后才原子写入 `正文/`

#### 单章写作流程

当用户准备写某一章时：

**先建精确一章候选工作区**：执行 `scripts/chapter_candidate.py init`，把本章细纲、卷纲和其他决定有效性的文件绑定为基础指纹。narrative-writer 和主线程都只写该工作区里的候选正文文件。默认 `approval_mode=review`；没有用户本次明确的自动定稿授权，不得设为 `auto`。

**上一章中文正稿旧债门**：写第 N 章正文前，先确认第 N-1 章没有未清的 blocking 毒句式、语言泄漏、HTML 标记或文风卫生污染。写前 hook 不可用时，对上一章先运行 `node scripts/language_gate.js 正文/第{N-1}章_*.md`，该独立语言门返回零后，再依次运行 `node scripts/check-style-hygiene.js --check --fail-on=blocking 正文/第{N-1}章_*.md`、`node scripts/check-ai-patterns.js --check --fail-on=blocking 正文/第{N-1}章_*.md` 与 `node scripts/check-degeneration.js --check --language=zh --fail-on=blocking 正文/第{N-1}章_*.md`；有欠账先清零，再进入本章生成。去味跳过不得豁免语言门或文风卫生门，也不得在正文内写 HTML 豁免标记。

1. **检查细纲**：读取 `大纲/细纲_第{N}章.md`，并从对应 `大纲/卷纲_第X卷.md` 读取当前剧情单元（单元ID/位置、卷契约、本卷主推线/战果、终局底牌边界、风险等级）。如果不存在或缺少当前章节蓝图的必需字段，**必须先补建细纲再写正文**，不允许跳过细纲直接写作。补建时参考卷纲中本章对应的事件规划和上下文，补齐阶段位置、结构公式、禁止提前释放、内容概括、情节安排、人物关系/出场顺序、情节细化、结尾设定；无法从已有证据判断的字段写 `[待补充]`，不杜撰副线或关系。
2. **读取上下文**（按需选择；缺失时遵循各项及上方「缺失文件处理」，仅明确标为可选的非主产物跳过。可选快捷路径：如果当前运行时对应目录已部署 story-explorer agent（Claude `.claude/agents/story-explorer.md`、OpenCode `.opencode/agents/story-explorer.md`、TRAE Code `.trae/agents/story-explorer.md`、WorkBuddy 项目模式 `.codebuddy/agents/story-explorer.md`、Codex `.codex/agents/story-explorer.toml`），可调用同名 agent 一次获取上下文；TRAE Code 只用内置 `Agent` 按 `.trae/agents/story-explorer.md` 的名称选择同名 Subagent，不传 Claude 的 `subagent_type`；WorkBuddy 项目模式用 `Agent(subagent_type: "story-explorer", prompt: ...)`，plugin-only 模式仅在当前 Agent registry 真实返回 `oh-story:story-explorer` 时使用该精确值；Claude/OpenCode 可用等价 `subagent_type`，Codex 使用 `agent_type`，任务正文统一为 `项目目录：{dir}\n查询类型：context_load\n查询参数：准备写第 {N} 章\n追踪状态：last_committed_chapter={check 的值}，state_revision={check 的值}`）：
   - (1) `正文/第{N-1}章_*.md` — 上一章正文
   - (2) `大纲/细纲_第{N}章.md` — 本章细纲（含钩子设计）
   - (2a) `大纲/卷纲_第X卷.md` — 当前剧情单元、卷契约与终局储备（主推线/战果、终局底牌边界）
   - (3) `tracking_commit.py check` + `追踪/上下文.md` — `check` 无 ERROR 输出即通过，从它的紧凑 JSON 取 `last_committed_chapter` / `state_revision`，不把完整 state 加入 prompt；待回收伏笔取 `## 活跃伏笔`，角色当前状态取 `## 核心角色状态`，下一章硬承诺取 `## 下一章承诺`
   - (4) `设定/角色/{相关角色}.md`、`设定/势力/{相关势力}.md`（如存在）— 本章涉及的角色与势力（按细纲出场筛选）
   - (5) 对标书路径下 `拆文报告.md`（按对标书路径查找）— 对标参考
   - (6) `对标/{对标书名}/原文/第{N}章_*.md`（如存在）— 同位置章节参考
   - (7) `参考资料/{topic}.md`（如存在）— 历史研究资料（由 story-researcher 产出）
   - (8) 对标书路径下 `剧情/故事线.md`（按对标书路径查找）— 剧情单元索引，用于确定本章涉及哪些剧情单元
   - (9) 对标书路径下 `剧情/{相关剧情单元}.md`（按对标书路径查找）— 从索引中选择与本章相关的剧情单元文件
   - (10) 对标书路径下 `设定/世界观/*.md`（glob，按对标书路径查找）— 从当前拆文产出的主题化设定中获取参考；目录缺失则记录缺口并跳过本项，不读取扁平历史路径
   - (11) 对标书路径下 `剧情/情绪模块.md`（按对标书路径查找）— 读者需求 / 情绪引擎、爽文套路框架、可复现模块；缺失按上方「缺失文件处理」设置 `missing_primary_contract` 并停止准备
   - (12) 对标书路径下 `剧情/节奏.md`（按对标书路径查找）— 关键信息推进、情绪触动点、爆发节奏；缺失按上方「缺失文件处理」设置 `missing_primary_contract` 并停止准备
   - (13) `设定/题材正文提示卡.md`（如存在）— 本书正文层题材卡；缺失时从 `设定/题材定位.md` + `references/genre-prose-cards.md` 索引 + `references/genre-prose-cards/` 单题材卡目录（按题材分类优先）+ `references/style-genre-modules.md`（兜底）即时生成 `genre_prose_card`，不阻塞写作
3. **写前准备**（下面的 3 步是核心方法在单章写作中的落地：筛选状态 → 召回模块 → 确认意图）：
   - **状态筛选**：从 `追踪/上下文.md` 的 `## 核心角色状态` 取当前角色，从 `## 活跃伏笔` 取需回收/推进项，从 `## 下一章承诺` 取本章必须履行项，输出本节速记（参考 state-tracking.md）。久别角色按名读取 `追踪/角色状态/{名}.md`；只有追查变化原因时才定点查逐章增量。续写状态卡或 meta 不存在时按 workflow-daily 的当前协议处理，不手写替代文件
   - **模块召回、题材卡与文风召回**：
     - ① 本章目标情绪词？② 借鉴哪个参考文件的哪个技法？③ 用在哪些段落？答不出 → 先回读参考再动笔
     - (a) **情绪模块召回**：按「对标书路径查找」规则读 `{对标书路径}/剧情/情绪模块.md`，选出 1 个与本章目标情绪最贴近的 `selected_emotion_module`（读者需求、触发器、戏剧单元、可替换要素、反抄袭提醒）。缺失时设置 `missing_primary_contract: true`，返回明确 `repair_action` 后停止准备
     - (b) **节奏召回**：读 `{对标书路径}/剧情/节奏.md`，选出 1 条 `rhythm_reference`（关键信息 → 扩写技法 → 情绪触动点 → 爆发/冷却）。缺失时设置 `missing_primary_contract: true`，返回明确 `repair_action` 后停止准备
     - (c) **题材正文提示卡召回**：优先读 `设定/题材正文提示卡.md`；缺失则先读 `设定/题材定位.md` + `references/genre-prose-cards.md` 索引，按主题材精确匹配后只读取 `references/genre-prose-cards/` 中对应单题材卡（如 都市脑洞 / 豪门总裁 / 年代 / 双男主；低置信卡必须在意图确认标注低置信，并要求同题材对标校准），无命中再读 `references/style-genre-modules.md` 通用流派模块。跨题材时主题材抽 3-5 条、辅题材抽 1-2 条，生成短 `genre_prose_card`（题材边界、核心逻辑、读者期待、核心爽点/情绪、正文落点、前中后期打法、节奏密度、场景颗粒、禁止漂移、本章取舍、卡片置信度）。题材卡只约束正文层题材味，不改细纲剧情、不覆盖 `selected_emotion_module` / `rhythm_reference` / `设定/文风.md`；只在内部校准取舍，正文里不得出现卡名/标签/置信度/条目/合规自评
     - (c1) **写作方法分支解析**：从细纲提取 3-6 个场景标签，运行 `scripts/style_method.py resolve --project {项目目录} --scene-tag ...`。返回 A 时执行下方原有文风召回；返回 B 时把最多 8 条 `selected_rules` 作为 `compiled_method_packet`，跳过对标 `文风.md`、匹配章原文锚点和 `benchmark_style_load` 的文风部分，但仍单独加载 `剧情/情绪模块.md`、`剧情/节奏.md`、题材卡和 fresh 声音画像。显式 B 的 resolve/check 失败立即停止。
     - (d) **文风召回**：先直接读 `设定/文风.md`（不经 explorer）：含实质内容（去空白 ≥200 字，或含 句长 / 标点 / 对话 / 锚点 / 笔调 小节且小节内有可执行约束：比例 / 例句 / 禁止或偏好描述）则置 `custom_style=true`、进入「自定义文风模式」，它作权威风格基（句长 / 软标点 / 潜台词 / 情绪交替）。A 分支把对标 / 拆文 `文风.md` 降为参考（锚点 + 句长兜底）；B 分支把 `compiled_method_packet` 降为参考，且始终不读取来源锚点。空 / 仅空白 / 仅标题 / 占位 stub（待办 / 待补充 / ___）视为不存在。没有自定义文风时，A 按「对标书路径查找」规则读 `{对标书路径}/文风.md`（路径优先 `{项目}/对标/{书名}/`，回退 `拆文库/{书名}/`），多本对标书时从 `设定/题材定位.md` 读 `主对标书` 字段；A 未进入自定义文风模式且文风文件不存在则 fail-fast。B 直接使用已验证的 `compiled_method_packet`，不要求对标 `文风.md`，但情绪 / 节奏轴 `missing_primary_contract` 仍独立阻塞
     - (e) **A 分支匹配章节挑选**：仅 A 从 `{对标书路径}/章节/*_摘要.md` grep `基调：(紧张|轻松|悲伤|热血|爽|甜|温馨|恐怖|压抑|其他)`（全角冒号），按本章目标情绪挑章 K——多章同基调时选择规则：先看爽点类型是否接近，再看情节点数量/原文章节估算字数是否接近本章目标字数，最后取章节号最小者；必读 `{对标书路径}/章节/第K章_摘要.md`，若同章存在 `第K章_深度拆解.md` 则加读，否则回退黄金三章深度拆解/文风文件里的可借鉴技巧，不因非黄金三章缺少深度拆解而失败。B 跳过本步
     - (f) **结构化模块召回**：从对标的结构化子目录（角色/剧情/设定）中按本章情节检索相关模块；若与 `剧情/情绪模块.md` / `剧情/节奏.md` 冲突，权威文件优先，记录 `conflict`
     - (g) **分支化输出**：A 输出"主对标召回摘要 + 副对标召回摘要 + selected_emotion_module + rhythm_reference + genre_prose_card + 文风召回指令 + 原文锚点片段引用"；B 输出"selected_emotion_module + rhythm_reference + genre_prose_card + compiled_method_packet"，不带匹配章、原文锚点、来源名或证据定位。**A 的多对标书召回**参 `references/cross-book-recall.md`：主对标提供文风、原文锚点与 selected_emotion_module / rhythm_reference；副对标/参考对标按阶段预算提供结构化摘要，不限制登记书目，不读取副书 `文风.md` / 原文，超过预算时裁条目不裁书目记录。
     - **快捷路径**：项目已部署 story-explorer agent 时，可一次性召回文风/模块材料。
       - 按当前运行时检查：Claude `.claude/agents/story-explorer.md`、OpenCode `.opencode/agents/story-explorer.md`、TRAE Code `.trae/agents/story-explorer.md`、WorkBuddy 项目模式 `.codebuddy/agents/story-explorer.md`、Codex `.codex/agents/story-explorer.toml`。TRAE Code 用内置 `Agent` 按该 `.trae` 定义的名称选择同名 Subagent，不传 `subagent_type`；WorkBuddy 项目模式用 `Agent(subagent_type: "story-explorer", prompt: ...)`，plugin-only 仅在 registry 返回 `oh-story:story-explorer` 时用该精确值。
       - 查询类型：`benchmark_style_load`；传入项目目录、章节号、目标基调/字数和爽点类型。
       - 需要返回：`style_profile_path`、`style_profile_summary`、`selected_emotion_module`、`rhythm_reference`、来源路径、匹配章节、锚点片段、`gaps`。
       - `gaps.missing_primary_contract` 为 true 时先按 `repair_action` 修复，不进入正文生成。
       - 主会话另行直接读 `设定/文风.md`：含实质内容时作为本书风格基准；但不豁免情绪/节奏缺失。
   - **指令确认**：综合细纲、本节速记和模块召回结果，用一句话写清本章意图。
	     - 新版细纲必须消费：阶段位置、单元ID/位置、主角目标/关键选择、结构公式、禁止提前释放、内容概括、情节安排、人物关系/出场顺序、情节细化、结尾钩子，并对照当前剧情单元的卷契约、本卷主推线/战果、终局底牌边界。
	     - **细纲优先边界**：正文只能展开本章细纲已有事件、人物、冲突、伏笔和结尾钩子；不得为了凑字或"更精彩"自造新主线、新角色、新反转、提前写后续章剧情，必要的过渡动作只能服务于细纲已列情节点。后续阶段真相、底牌、关系结论和终局矛盾不得因为章尾钩子提前泄露。反过来，细纲是"要发生什么"的契约、不是正文的形状：正文可自由编排叙述顺序、合并/穿插情节点，不必一个情节点一段、也不必按五段式顺写，把每个点演成场景而不是照抄概括语（见 writing-craft.md「从细纲到正文」）。
	     - **细纲语义去重**：同一要求在核心事件、五段式、情节安排和情节点中重复，只算一个语义点；生成前合并，不把重复次数当强调，不沿用提纲原句逐项复述。比如多处都写“不带摄像机、先听完再决定拍不拍”，正文只通过一个自然动作或一句人物判断兑现，不能拆成「至于拍不拍，怎么拍…」「不带摄像机，不带采访灯」两轮说明。
	     - 爽点出手前要有可指认的危机/期待铺垫；装逼/打脸/揭露章要写在场配角的差异反应。
	     - 高压/生死/悲痛节拍 要收紧对话声线：搞笑担当让位，信息型角色不当科普嘴，对话逐句承接对方情绪。
	     - 检查任务卡点：本章如果有“办事被卡住”，它必须卡出信息、关系、代价、选择或伏笔变化；没有就不强补。
	     - 契约风险检查：按 `references/reader-contract-and-progression.md` 判定 契约安全 / 需补强 / 契约破坏；若高光/收益被配角、机构或偶然性拿走且没有可见交换，先修纲再写。
     - 例：「快节奏打脸——账单暴露→逼问→反证→公开代价；读者等了三章，这章必须一拳到位。」
4. **资料研究**（按需）：如果写作中遇到需要查证的外部事实（历史年代、地理方位、职业细节等），按当前运行时检查 story-researcher（Claude `.claude/agents/story-researcher.md`、OpenCode `.opencode/agents/story-researcher.md`、TRAE Code `.trae/agents/story-researcher.md`、WorkBuddy 项目模式 `.codebuddy/agents/story-researcher.md`、Codex `.codex/agents/story-researcher.toml`）。可用时调用同名 agent 搜索并输出到 `参考资料/`；TRAE Code 只用内置 `Agent` 按 `.trae/agents/story-researcher.md` 的名称选择同名 Subagent，不传 `subagent_type`；WorkBuddy 项目模式用 `Agent(subagent_type: "story-researcher", prompt: ...)`，plugin-only 仅在 registry 返回 `oh-story:story-researcher` 时用该精确值。TRAE Code 使用当前平台的联网能力或只读 `browser-cdp` 路由，不调用不存在的 `WebFetch`。如 agent 或联网能力不可用，由主线程在可用能力范围内执行并明确证据缺口。研究完成后再继续写作。
5. **标题预检**：写正文前从细纲读取章名；如与既有章节同名或明显重复，先按本章核心事件改名，并同步细纲标题与正文文件名。
	6. **写作**：第 1 章如果以内心戏、设定认知或独处开场，必须先把内心变化外化为可见事件（决定、误判、对话、物件变化、外部压力），再按字数目标展开；不得用大段心理独白凑字。若第 1 章低于目标，或正文代入感/推进感偏薄，优先回到细纲补有用子事件、对话交锋或选择代价，不要补解释性内心戏；任务卡点只在角色本来有要办的事、且能卡出信息/关系/代价/选择/伏笔变化时使用，没有就不强补。
	   - **正文元信息隔离**：`章节：第{N}章`、`上一章：正文/第{N-1}章_*.md`、`匹配第K章`、`细纲文件` 等只用于定位材料。标题行以外的正文不得出现 `第[一二三四五六七八九十百千万两0-9]+章|上一章|上章|前一章|本章|这一章|前文|后文|伏笔|细纲|读者|ch\d+ 等英文章号缩写` 这类写作工程词。需要承接前文时，改成角色能感知的事件锚点或相对时间，例如“比第一章那三秒开火更疼”必须写成“比那三秒开火更疼”。例外：角色在故事世界内真实阅读/讨论“第X章”文本，或真实身为作者/读者并谈论读者身份时，可保留相应词。
	   - **生成前中文锁**：正文叙述、对话、心理和场景一律使用中文；外国人对话也先译成中文并在场内注明语种。英文、缩写、型号和剧情代号不得由模型自行豁免；URL、邮箱、代码、路径和文件名只有在明确属于非叙事结构时才由检测器机械保护。用户明确要求逐字保留的其他外语，必须单独确认后在 `.deslop-whitelist` 精确登记；HTML 标签、注释和实体不得进入交付正文。
7. **正文执行**：
    - 按当前运行时检查 narrative-writer agent：Claude `.claude/agents/narrative-writer.md`、OpenCode `.opencode/agents/narrative-writer.md`、TRAE Code `.trae/agents/narrative-writer.md`、WorkBuddy 项目模式 `.codebuddy/agents/narrative-writer.md`、Codex `.codex/agents/narrative-writer.toml`。
    - 如可用，TRAE Code 只用内置 `Agent` 按 `.trae/agents/narrative-writer.md` 的名称选择同名 Subagent，把下列 prompt 作为任务正文，不传 Claude 的 `subagent_type`；WorkBuddy 项目模式 spawn `Agent(subagent_type: "narrative-writer", prompt: ...)`，plugin-only 仅在 Agent registry 真实返回 `oh-story:narrative-writer` 时用该精确值；Claude/OpenCode 可用等价 `subagent_type`，Codex 用 `agent_type`。prompt 只传本章必需材料：
     - 项目目录、章节、细纲文件、上一章、输出路径。
     - 写前准备输出：本节速记、情绪目标、涉及角色、参考技法。
     - 主对标/拆文路径、主/副对标召回摘要。
     - `selected_emotion_module`、`rhythm_reference` 及来源路径。
     - `genre_prose_card`（题材正文提示卡摘要，只含本章相关条目）。
	     - A 的文风路径、文风召回指令、原文锚点片段；B 不传这三项。
	     - 写作方法分支与 `compiled_method_packet`：A 不传；B 只传本章命中的抽象规则，不传整包、来源名、证据定位或语料原文。
	     - 已接纳正文声音画像摘要（若存在且验证为 fresh）：只传本章相关漂移项和早期/近期范围，不传全量逐章统计；画像缺失或样本不足不阻断写作。
	     - 阶段位置、本章结构公式、本章可释放信息、本章禁止提前释放信息。
	     - 字数目标、情节点预算、格式硬约束。
	     - 语言契约：`language=zh`；正文叙述、对话、心理和场景均用中文，只保留机械识别的非叙事结构或用户单独确认后在 `.deslop-whitelist` 精确登记的外语，HTML 标记必须为零。
	     - 细纲优先边界：只展开本章细纲，不自造新剧情；细纲约束“发生什么”而非正文形状，允许合并、穿插或局部重排情节点，不得一个字段/情节点机械对应一个段落；只允许逐字使用 `复沓锚句` 登记内容。若字数目标靠现有情节点无法达标，返回 `outline_underfilled` 欠账点，由主会话补纲/确认后再写。
   - 不把本文件整套规则复制进 prompt；细节以已加载 references 和 narrative-writer 模板为准。
   - agent 输出写入本次候选运行目录中的候选正文文件。如 agent 未部署，由主线程直接写候选稿；不得直接写 `正文/`。
8. **字数验证**（写作完成后的第一件事）：用跨平台 Python 字符统计本章实际字数，探测顺序 `python3/python/py`；不要用 `wc -c` 或模型估算，Windows 不直接假定 `python3` 命令可用。macOS/Linux 可用 `wc -m` 备选。
	- 同轮运行 `"$PYBIN" scripts/prose_metrics.py <候选正文>`，把短/中/长句占比、平均/中位句长、段落均长与句段比作为**唯一实测值**写入候选 Gate 报告；这些统计只用于定位读感复核，不设跨题材配额。narrative-writer 的口头估算不得替代脚本结果。
   - 字数 < 细纲目标 90%：对照情节点预算找欠账点。密点（爽点/打脸/反转）被写薄时，重写到对应预算；低压/关系/信息整理章则补细纲内已有铺垫、互动或表演节拍，不硬塞爽点。若现有细纲没有足够可展开内容，停止并输出 `outline_underfilled` 欠账点，先补纲/确认，不能让正文自造新剧情。
   - 字数 > 章目标×1.1：压过场、合并疏点、删多余过渡，不删主线爽点凑数。
	- 90% 只是放行下限，目标仍是 `[章目标, 章目标×1.1]`；重写后重新统计，落进区间再进入步骤 9。
   - **细纲照搬 Gate**：运行 `node scripts/check-outline-copy.js --outline <本章细纲> --fail-on=blocking <候选正文>`。归一化后连续 16 字及以上重合而未被细纲 `复沓锚句` 精确登记时，回到命中场景改成动作、对话、物件和角色感知，再复扫；脚本只提供证据，不自动改写。锚句只登记确需逐字回环的誓言、系统提示、案卷引文等，不得用整段概括语扩大豁免。
9. **检查**：先做“收一个、变一个、开一个”三问：本章兑现了哪笔期待或付了什么利息？七类状态哪项发生可见变化？章尾留下了什么可真实承接的下一步？低压/过场章可用决定、行动、关系变化、阶段目标或情绪余势，不强求硬悬念/爽点。再查爽点是否到位（按章节定位，高压/推进章必查）及钩子诚信（下一章不得撤回、误会化或切线逃债）。两条可证伪核对（不达标→修复）：① 爽点出手前是否有可指认的危机/期待段落（指到具体情节点）？指不出=空洞 → 回步骤 8 补铺垫情节点（plot-emotion-system 倒推法）；② 装逼/打脸/揭露章，在场配角是否写出差异化反应（集体震惊/各异），还是只写主角动作？没有 → 补在场配角反应（plot-core-methods）
10. **元信息扫描**：检查标题行以外的正文，命中 `第[一二三四五六七八九十百千万两0-9]+章|上一章|上章|前一章|本章|这一章|前文|后文|伏笔|细纲|读者` 时必须改写为场景内表达；只有角色在故事世界内真实阅读/讨论“第X章”文本，或真实身为作者/读者并谈论读者身份时例外。
	11. **禁用词扫描**：先过**最毒句式速查**（实测最易漏，命中即改）：①「不是A，(而)是B」全家族——含「没有X，没有Y(，只是Z)」排比否定、「是B，不是A」反序、「他没X，也没有Y。他只是Z」先抑后扬，；②声线反差「声音不大/不高…却…」；③「，带着……」万能状语；④预告/总结收尾「没人知道…」「(这)才刚刚开始/开头」「正朝着…压过去」「即将拉开序幕」「这一刻…」；⑤叙述里短词加引号强调（他是被请来"把关"的）。再复核 detector 的 `formulaic-parallelism` advisory：跨段「不是A。/也不是B。/只是C。」、`至于X不X，怎么X`、同动词 `不V A，不V B` 即使写在台词里也不能跳过，确属人物当场的功能性表达才保留。然后对照 `references/banned-words.md` 全表：一级词（高频AI腔）命中即替换；二级词（低频/语境相关）高频出现时替换，偶发可参考 `references/anti-ai-writing.md` 定性裁定
12. **候选 Gate、接纳与追踪**：先运行 `scripts/chapter_candidate.py check`；该命令会自动实测句段分布、核对本章细纲连续照搬，在画像可用时加入已接纳/黄金声线双向漂移 advisory，并生成近六章结构指纹冷读卡。主 Agent 必须回答结构五问并把具体证据纳入候选报告；相似度本身不阻断接纳，也不授权自动改文。`review` 模式向用户报告候选标题、字数、关键变化、Gate 结果和路径后停止；用户明确接纳后，或本次任务已有有效 `auto` 授权时，才依次执行 `approve --confirm ACCEPT` 与 `promote --confirm PROMOTE`。正式正文写入后，按 workflow-daily 构造本章唯一追踪事务并执行 `scripts/tracking_commit.py commit`；成功复检后依次运行 `chapter_candidate.py close`、`voice_profile.py update --project`（未配置画像时安全跳过）和 `story_doctor.py --project`。任一步失败都保留候选/事务现场，不手改派生文件、不写下一章。不能先把候选吸收进画像再检查自己；黄金集合也不得自动吸收新章。本章首次引入会复用的具名角色/势力时，仍按 `references/workflow-setup.md` Phase 3 规则补建静态 `设定/` 档案。
13. **中途快照**（长篇写作安全网）：每连续写完 3 章，在继续前执行以下快照操作：
   - 执行 `scripts/tracking_commit.py check`，确认 `_tracking-state.json` 有效、逐章记录连续且未超限、所有派生视图一致、续写状态卡恰好 7 栏且 ≤12288 字节
   - 用 `ls -la 正文/` 确认最近 3 个章节文件已成功写入磁盘且大小正常（>100 bytes）
   - 如果发现文件缺失或大小异常，立即重新写入
   - 快照完成后可继续写作

> **日更模式**：此步骤自动跳过——workflow-daily Step 2 已按章更新上下文.md。

#### 写作技巧提醒

| 场景 | 技巧 |
|------|------|
| 开篇 500 字 | 必须有钩子，不能从天气/风景开始（除非反差极大） |
| 对话 | 推进剧情或揭示性格，不能只为了凑字数 |
| 打斗 | 不要流水账，写策略和反转，不写「你一拳我一脚」 |
| 日常 | 日常要有人物互动和伏笔，不能只是「吃饭睡觉」 |
| 任务卡点 | 角色办事被卡住，必须卡出信息/关系/代价/选择/伏笔变化；删掉无损就压缩或删除 |
| 爽点释放 | 铺垫要充分、释放要干脆，读者等得越久释放越要爽 |
| 爽点密度 | 高压/推进章每 3000-5000 字一个「爽」的情绪节点；低压/关系/修炼/信息整理章不强求，但每章仍要有往下看的理由（见 references/outline-structure-theory.md「章节定位与张弛」） |
| 公式约束 | 参考 genre-writing-formulas.md 中的创作公式 |
| 章尾 | 每章结尾都要有让读者想翻下一页的东西 |
| 情绪验证 | 写完每章回头检查：读者到这里应该感受到什么？感受到了吗？没感受到 → 按章节定位补：高压/推进章补冲突或钩子，低压/关系章补关系或情绪质感，别一律加爽点 |

#### 字数验收权威

长篇每章只按本章细纲的 `字数目标` 与步骤 8 的统一 90% 放行下限验收。节奏类型只决定情节点疏密和展开方式，不再叠加另一套静态最低字数。

**细纲缺 `字数目标` 时**：按 3000 字/章代入，走同一条 90% 放行下限，并提示补纲。这是唯一兜底值，不按节奏类型分档——分档正是本次要消除的第二套标准。


#### 追踪文件体积

`追踪/_tracking-state.json` 是唯一结构化权威；`上下文.md`、核心角色快照、`伏笔.md`、作者真相与读者已知时间线都由它确定性派生，程序不反向解析 Markdown。`上下文.md` 固定 7 栏且 ≤12KB。`逐章记录/第NNN章.md` 每章只记录会影响后续连续性的紧凑变化，目标 ≤1536 字节、硬上限 3072 字节，不承诺单独重放出全部当前状态。阶段/卷级回看按需查询逐章记录或正文，不维护另一套长期摘要。所有追踪写入都通过 `scripts/tracking_commit.py`，禁止手改派生文件。

---

### Phase 5：质量检查

检查三个维度：(1) **情绪交付**——每章是否交付了细纲中规划的目标情绪？(2) **契约风险**——按 `references/reader-contract-and-progression.md` 检查因果权 + 结算权、关键节点四问、期待所有权、期待债、终局储备（透支两问）与换书债；章级推进按权威文件的七类状态分档（快节奏保留可见事件/爽点下限），强弱相对本书题材与对标判断，标记 契约安全 / 需补强 / 契约破坏；契约破坏 先修正文或修后续纲。(3) **技术质量**——一致性、格式、禁用词。参考 [references/quality-checklist.md](references/quality-checklist.md) 中的通用检查和长篇专项清单。

**正文元信息扫描**：质量检查必须覆盖标题行以外的正文，发现 `第[一二三四五六七八九十百千万两0-9]+章|上一章|上章|前一章|本章|这一章|前文|后文|伏笔|细纲|读者` 这类写作工程词时，先改成角色当下可感知的事件、物件、动作或相对时间，再进入其他检查；故事内真实阅读/讨论“第X章”或真实读者身份语境除外。

**写后同轮清零**：正文落盘不是汇报时机——每章落盘后必须在**同一轮**内跑完 Phase 4 步骤 10-11 扫描、下方确定性收尾脚本与 narrative-writer 审查，blocking 清零才算本章完成；不得先汇报"已写完"再等指示。写后 hook 会对落盘正文自动扫描确定性毒句式并把命中推回——那是兜底网不是替代，hook 报出的命中当轮清零。**正文内不设去味豁免标记**：不得添加 HTML 注释绕过检查；blocking 必须结合剧情功能改写并复扫清零。

**错别字校验（独立语言门通过后，先于其他风格检查）**：主会话对实际落盘文件运行 `node scripts/check-typos.js --check --fail-on=all 正文/第XXX章_*.md`。这一步专查错别字/形近字/音近字误用，跟风格/AI味/一致性是完全不同维度的问题。词典只收高置信度的固定搭配误写，找到的每一条都是 advisory，脚本从不自动改写；命中后先判断是不是项目里有意为之的风格化用词（例如呼应某条设定的专属措辞），确认是真错字才改，不是无脑替换。

**情绪落地下限（错别字校验之后、AI 味检查之前）**：主会话运行 `node scripts/check-emotion-floor.js --check 正文/第XXX章_*.md`；对峙/摊牌/生死/揭穿等高压章加 `--pressure=high`，过场/信息整理章加 `--pressure=low`。这一步和 check-ai-patterns.js 是相反方向的闸口——那个查「不该有的东西」，这个查「必须有却缺席的东西」。禁止情绪标签的规则只有上限没有下限，最省力的通关解会变成干脆不写情绪，正文因此没有体温、读者判为平淡；本步给「转译」补下限，让删除不能冒充转译。blocking 必须回到本章压力最高的 2-3 个节点补落点再复扫，advisory 按 [references/emotion-landing.md](references/emotion-landing.md) 的转译表处理，不要靠堆「心口一沉」刷密度。

**确定性收尾**：错别字校验通过后，主会话对实际落盘文件运行 `node scripts/check-ai-patterns.js --check --fail-on=blocking 正文/第XXX章_*.md`。blocking 命中先回正文改写并复扫；advisory 只作读感提示，确属问题才改，功能性写法标 `[需复核]`。
**确定性收尾**：本批正文写完后，主会话对实际落盘文件运行 `node scripts/check-ai-patterns.js --check --fail-on=blocking 正文/第XXX章_*.md`。blocking 命中先回正文改写并复扫；advisory 逐条读原文判断，确属问题才改，功能性写法标 `[需复核]`。其中 `formulaic-parallelism` 必须连同对话一起复核，不能因为 hook 不阻断台词就略过。
随后运行 `node scripts/normalize-punctuation.js 正文/第XXX章_*.md` 做确定性格式收尾；默认保留停顿标点与引号风格，只清理 Markdown 分隔线等格式问题。仅当本书文风或发布平台明确禁用停顿标点时，才加 `--pause-mode normalize` 清理 `……`、破折号和双连字符；盐言「」不受影响。narrative-writer agent 不运行这些脚本。

**退化/语言泄漏防护**：正文落盘后先运行 `node scripts/language_gate.js 正文/第XXX章_*.md`；独立语言门返回零后，运行 `node scripts/check-style-hygiene.js --check --fail-on=blocking 正文/第XXX章_*.md`，再运行 `node scripts/check-degeneration.js --check --language=zh --fail-on=blocking 正文/第XXX章_*.md`。文风卫生 blocking 按 `设定/文风.md` 的项目策略处理；退化 blocking（未授权外语、HTML 标记、复读、截断、拒绝语、tier1 工程词泄漏）只重写受影响句/段或章节，最多 2 次；修复后复扫，仍失败就报告证据让用户定夺。URL、邮箱、代码、路径和文件名只机械保护明确非叙事结构；其他外语只有在用户单独确认并精确登记时才可保留。
非语言 advisory 只提示可疑处，先看脚本给出的例外；故事内系统/界面用语、弹幕刷屏、重复台词等有功能则优先用中文表达。语言与标记门的 blocking 不得因去味跳过而降级。

#### Agent 调用：consistency-checker（硬性必须，非可选）

> 历史教训：本节曾写作"如果项目已部署...可以 spawn"，软性措辞导致执行者在写完多章后反复自行判断"要不要跑"，实际结果是连续数章漏跑却无人发现，直到用户主动追问"是否严格按工具流程"才暴露。现改为无条件必须执行，唯一的分支是"谁来执行"，不是"要不要执行"。

质量检查阶段**必须**执行一致性检查，检测事实冲突、伏笔断线、角色属性不一致，覆盖范围至少含本次新写的章节。执行方式二选一，不存在"跳过"选项：
- 当前运行时已部署 consistency-checker（Claude `.claude/agents/consistency-checker.md`、OpenCode `.opencode/agents/consistency-checker.md`、TRAE Code `.trae/agents/consistency-checker.md`、WorkBuddy 项目模式 `.codebuddy/agents/consistency-checker.md`、Codex `.codex/agents/consistency-checker.toml`）：调用同名 agent 获取 S1-S4 分级报告。TRAE Code 只用内置 `Agent` 按 `.trae/agents/consistency-checker.md` 的名称选择同名 Subagent，不传 `subagent_type`；WorkBuddy 项目模式用 `Agent(subagent_type: "consistency-checker", prompt: ...)`，plugin-only 仅在 registry 真实返回 `oh-story:consistency-checker` 时用该精确值；Claude/OpenCode 可用等价 `subagent_type`，Codex 使用 `agent_type`；任务正文为 `项目目录：{dir}\n检查范围：{本次写作的章节}\n检查类型：事实冲突+伏笔断线+角色属性不一致`。
- agent 不可用：由主线程参照 quality-checklist.md 手动执行同等深度的检查，不得以"agent 未部署"为由整项跳过。

执行完成后，在 `追踪/质检进度.md`（若项目已部署此文件，见 story-setup 2.5）对应章节行的「consistency-checker」列打 `✓`（无未解决问题）或 `○`（有 advisory/S3 待复核）；文件不存在不阻塞写作，但下次有 story-setup 部署机会时应补建。

#### Agent 调用：narrative-writer（去AI味独立审查，硬性必须，非可选）

> 历史教训：与 consistency-checker 同源问题——"可 spawn"的软性措辞导致这一步被反复跳过，且这是一次**独立于写作时脚本检测**的语义级复审（脚本抓不住的解释腔/上帝视角/精致戏剧反应堆叠，只有通读才能判断），不能用写作时顺带的自检替代。

质量检查阶段**必须**对本次新写的章节执行一次独立于写作过程的去AI味审查，不是写作 agent 顺手做的自检，是另开一次专门审查：
- 当前运行时已部署 narrative-writer（Claude `.claude/agents/narrative-writer.md`、OpenCode `.opencode/agents/narrative-writer.md`、TRAE Code `.trae/agents/narrative-writer.md`、WorkBuddy 项目模式 `.codebuddy/agents/narrative-writer.md`、Codex `.codex/agents/narrative-writer.toml`）：调用同名 agent 执行文字质量审查和去AI味检查。TRAE Code 只用内置 `Agent` 按 `.trae/agents/narrative-writer.md` 的名称选择同名 Subagent，不传 `subagent_type`；WorkBuddy 项目模式用 `Agent(subagent_type: "narrative-writer", prompt: ...)`，plugin-only 仅在 registry 真实返回 `oh-story:narrative-writer` 时用该精确值；Claude/OpenCode 可用等价 `subagent_type`，Codex 使用 `agent_type`；任务正文为 `项目目录：{dir}\n任务描述：审查+去AI味\n检查范围：{本次写作的章节}\n删除优先：每条 AI 味项先判能否删除——删后不丢伏笔/钩子/角色/情节/必要信息的直接删，会丢才润色（删除受比例上限与字数下限约束，跌破下限改降AI重写）\n必须检查：先否定再肯定的翻转句式，发现后直接改成后项或动作细节；检查作者解释总结/意义尾巴（他意识到/这意味着/真正重要的是/这次成长），优先删掉或落回场内动作、对话、物件状态；检查像/好像/仿佛/如同等比喻是否成片堆叠，确属堆叠时只留最有功能的少数比喻，其余回到具体画面；检查是否连续使用头皮发紧/眼皮一跳/心口一沉/胃里翻涌等精致戏剧反应，能写普通动作/普通感觉就写普通动作/普通感觉，且同一生理反应词跨多章重复出现时视为模板化指纹，收窄到专属语境或替换为其他生理反应；已有手机/屏幕/公告/门牌/表单/账单/物证/规则行信息，保留为角色看到或处理的场内载体，不改成叙述者解释；任务卡点只在角色本来有要办的事且能卡出信息/关系/代价/选择/伏笔变化时使用，不为自然感或字数补流程`。
- agent 不可用：由主线程直接执行，同样按上述检查项逐条通读，不得省略。

执行完成后，在 `追踪/质检进度.md` 对应章节行的「去AI味独立审查」列打 `✓`/`○`。

检查后更新 `追踪/质检进度.md`（若已部署）对应章节行：三个脚本、元信息扫描、consistency-checker、去AI味独立审查、字数核实、对话密度实测（读 check-ai-patterns.js 的 `dialogue-density-stat` info 输出，不必手写脚本现算）逐列打勾。伏笔与时间线不再手改派生文件，统一走下面的追踪事务。
质量检查阶段，如果当前运行时对应目录已部署 narrative-writer（Claude `.claude/agents/narrative-writer.md`、OpenCode `.opencode/agents/narrative-writer.md`、TRAE Code `.trae/agents/narrative-writer.md`、WorkBuddy 项目模式 `.codebuddy/agents/narrative-writer.md`、Codex `.codex/agents/narrative-writer.toml`），可调用同名 agent；TRAE Code 只用内置 `Agent` 按 `.trae/agents/narrative-writer.md` 的名称选择同名 Subagent，不传 `subagent_type`；WorkBuddy 项目模式用 `Agent(subagent_type: "narrative-writer", prompt: ...)`，plugin-only 仅在 registry 真实返回 `oh-story:narrative-writer` 时用该精确值；Claude/OpenCode 可用等价 `subagent_type`，Codex 使用 `agent_type`。任务正文为 `项目目录：{dir}\n任务描述：审查+去AI味\n检查范围：{本次写作的章节}\n删除优先：每条 AI 味项先判能否删除——删后不丢伏笔/钩子/角色/情节/必要信息的直接删，会丢才润色（删除受比例上限与字数下限约束，跌破下限改降AI重写）\n必须检查：先否定再肯定的翻转句式，含跨段‘不是A/也不是B/只是C’；对话也检查‘至于X不X，怎么X’和同动词‘不V A，不V B’工整清单，不能因脚本豁免台词而跳过；检查正文是否把细纲多个字段里重复的同一要求逐项复述，重复字段只算一个语义点；检查作者解释总结/意义尾巴（他意识到/这意味着/真正重要的是/这次成长），优先删掉或落回场内动作、对话、物件状态；检查像/好像/仿佛/如同等比喻是否成片堆叠，确属堆叠时只留最有功能的少数比喻，其余回到具体画面；检查是否连续使用头皮发紧/眼皮一跳/心口一沉/胃里翻涌等精致戏剧反应，能写普通动作/普通感觉就写普通动作/普通感觉；已有手机/屏幕/公告/门牌/表单/账单/物证/规则行信息，保留为角色看到或处理的场内载体，不改成叙述者解释；任务卡点只在角色本来有要办的事且能卡出信息/关系/代价/选择/伏笔变化时使用，不为自然感或字数补流程`。如 agent 不可用，由主线程直接执行。

检查后若正文修订改变了连续性事实，必须构造 `mode=revision` 的同章追踪事务并执行 `scripts/tracking_commit.py commit`：
- 伏笔变化用 `foreshadow_changes` 更新同一 ID 的当前行，不追加重复历史；
- 时间线变化写入 `timeline_events`，由 `_tracking-state.json` 统一派生 `作者真相.md` 与 `读者已知.md`，不得把作者秘密泄露到读者视图；
- 核心角色状态变化同时提交该角色截至当前章的完整快照；
- 身世、血缘、亲属、婚姻、传承、所有权、权限、世界规则或不可逆状态用 `fact_changes` 更新稳定 ID，由工具派生 `长期事实.md`、`关系清单.md` 和 `事实档案/{实体}.md`；
- 事务失败后保留原事务 JSON，修正写入环境并重跑同一 `commit`；成功后执行 `check`，确认 state 与全部派生视图一致再继续写作。

---

## 流程衔接

**流水线：** 长篇
**位置：** 写作（第 3/3 步）

| 时机 | 跳转到 | 命令 |
|---|---|---|
| 写完，去 AI 味 | story-deslop | `/story-deslop` |
| 想对比参考书 | story-long-analyze | `/story-long-analyze` |
| 需要市场方向 | story-long-scan | `/story-long-scan` |
| 太长，适合短篇 | story-short-write | `/story-short-write` |

---

## 参考资料索引

按场景加载，不一次全部加载。

### Phase 1：选题方向

| 场景 | 加载文件 |
|------|---------|
| 确定题材类型 | `references/genre-catalog.md` |
| 判断市场方向 | `references/genre-readers.md` |
| 特殊题材考量 | `references/plot-special-topics.md` |
| 女频长篇（题材/文案/平台/感情线） | `references/female-audience-writing.md` |

### Phase 2：核心设定

| 场景 | 加载文件 |
|------|---------|
| 设定人物 | `references/character-basics.md` |
| 设计关系 | `references/character-relations.md` |
| 题材框架与定位 | `references/genre-catalog.md` + `references/genre-core-mechanics.md` |
| 创建 artifact | `references/artifact-protocols.md` |
| 读者契约与主角高光 | `references/reader-contract-and-progression.md` |

### Phase 3：大纲搭建

| 场景 | 加载文件 |
|------|---------|
| 搭建大纲 | `references/outline-methods.md` |
| 设计矛盾与结构 | `references/outline-conflict.md` |
| 深度结构设计 | `references/outline-structure-theory.md` |
| 节奏与升级感 | `references/outline-rhythm.md` |
| 小纲与卡文 | `references/plot-core-methods.md` |
| 选择叙事框架 | `references/plot-frameworks.md` |
| 题材写作公式 | `references/genre-writing-formulas.md` |
| 黄金三章 | `references/opening-design.md` |
| 情绪弧线 | `references/emotional-arc-design.md` |
| 情绪落地转译 | `references/emotion-landing.md` |
| 契约/终局储备/剧情单元安全审查 | `references/reader-contract-and-progression.md` |
| 反转设计 | `references/reversal-toolkit.md` |

### Phase 4：正文写作

| 场景 | 加载文件 |
|------|---------|
| 章节钩子 | `references/hooks-chapter.md` |
| 悬念设计 | `references/hooks-suspense.md` |
| 段落级钩子 | `references/hooks-paragraph.md` |
| 题材正文提示卡 / 题材分类卡 | `references/genre-prose-cards.md` 索引 + `references/genre-prose-cards/` 单题材卡目录（按题材分类优先） + `references/style-genre-modules.md`（通用流派补充） |
| 打斗/装逼 | `references/style-combat-face.md` |
| 写作技法 | `references/style-craft.md` |
| 商业创作核心方法 | `references/commercial-core-methods.md` |
| 对话 | `references/dialogue-mastery.md` |
| 人物深化 | `references/character-design-methods.md` |
| 情绪技法 + 叙事单元 | `references/plot-emotion-system.md` + `references/emotional-methods.md` |
| 写作技法全程参考 | `references/writing-craft.md` |
| 格式与结构规范 | `references/format-and-structure.md`（仅对话/段落格式适用长篇） |
| 状态追踪协议 | `references/state-tracking.md` |
| 一致性与修改治理的完整设计 | `references/continuity-governance-design.md` |
| 长期事实/关系召回与跨产物修订门禁 | `references/revision-impact-and-canon.md` + `scripts/revision_guard.py` |
| 章节候选、接纳凭证与投影自检 | `references/chapter-acceptance-and-doctor.md` + `scripts/chapter_candidate.py` + `scripts/story_doctor.py` |
| 已接纳/黄金声音画像、双向漂移与盲测 | `references/accepted-voice-profile.md` + `scripts/voice_profile.py` |
| 近章结构指纹与语义五问 | `references/cross-chapter-shape.md` + `scripts/chapter_shape_gate.py` |
| 卷末/大修后顺序冷读 | `references/sequential-cold-read.md` + `scripts/cold_read_ledger.py` |
| 当前剧情单元与契约校准 | `references/reader-contract-and-progression.md` |
| A 标准直载 / B 蒸馏编译、跨作品语料与运行时规则 | `references/style-method-branches.md` + `scripts/style_method.py` |

### Phase 5：质量检查

| 场景 | 加载文件 |
|------|---------|
| 质量检查 | `references/quality-checklist.md` + `references/reader-contract-and-progression.md` |
| 错别字校验（语言门后第二步） | `scripts/check-typos.js` |
| 情绪落地下限（错别字之后） | `scripts/check-emotion-floor.js` |
| 钩子强度下限（钩子检查时） | `scripts/check-hook-strength.js` |
| 禁用词扫描 | `references/banned-words.md` |
| AI句式脚本复扫 | `scripts/check-ai-patterns.js` |
| 中文文风卫生门 | `references/style-hygiene.md` + `scripts/check-style-hygiene.js --check --fail-on=blocking`；默认拦表情、颜文字、火星文、标点堆砌，允许本书精确配置 |
| 句段分布实测 | `scripts/prose_metrics.py`；只报告确定性统计，不让写作 agent 自报比例 |
| 细纲连续照搬 | `scripts/check-outline-copy.js --outline <本章细纲>`；16 字起报，`复沓锚句` 精确豁免 |
| 独立中文正稿门 + 退化复扫 | 先 `scripts/language_gate.js`，后 `scripts/check-degeneration.js --check --language=zh --fail-on=blocking`；只机械保护明确非叙事结构，其他外语需用户单独确认并精确登记，HTML 标记阻断 |
| 去AI味 | `references/anti-ai-writing.md` |
| 本书声音漂移 | `references/accepted-voice-profile.md` + `scripts/voice_profile.py check`；只作 advisory，画像过期时先更新 |
| 近章场景发动机/问答/章尾同构 | `references/cross-chapter-shape.md` + `scripts/chapter_shape_gate.py`；只给证据，必须语义冷读 |
| 发布前导出为纯文本 | `scripts/export-for-platform.js`（只做格式转换，不做登录/发布，发布仍需作者本人在平台后台手动操作） |

### 按主题快速定位（横切主题）

有些主题横跨多个阶段、散在多个文件里。下表给每个主题一个**权威文件**（先读它，通常够用），配套文件只在需要那个角度时再加载。括号是该文件里对应的小节。

| 主题 | 权威文件（先读） | 配套文件（按角度补充） |
|------|-----------------|----------------------|
| 爽点（按意图分流） | **`references/plot-emotion-system.md`**（爽点设计体系：本质/六种类型/倒推法——"怎么设计爽点"先读这个） | 翻盘/高潮式爽点→`references/plot-core-methods.md`（假胜→崩解）· 打脸/装逼释放→`references/style-combat-face.md`· 题材打脸逆袭公式→`references/genre-writing-formulas.md`· 爽文循环/多层→`references/outline-methods.md`·`references/outline-conflict.md` |
| 情绪模块 | **`对标/{书名}/剧情/情绪模块.md`（项目/书级权威）**；无对标或设计新模块时再读 `references/plot-emotion-system.md` | `references/outline-rhythm.md` 只作理论参考；不得覆盖对标书权威模块 |
| 节奏 | **`对标/{书名}/剧情/节奏.md`（项目/书级权威）**；无对标或设计新节奏时再读 `references/outline-rhythm.md` | `references/plot-core-methods.md` 只作理论参考；不得覆盖对标书权威节奏 |
| 高潮 | **`references/plot-core-methods.md`**（高潮构建公式：蓄能→假胜→崩解） | `references/outline-rhythm.md`（高潮分类与反推）· `references/outline-methods.md`（八节点故事结构：结构定位） |
| 金手指 | **`references/plot-special-topics.md`**（金手指拆分理解与战力防崩 + 进阶设计） | `references/outline-conflict.md`（金手指与身份：四点统一） |
| 感情线 | **`references/character-relations.md`**（好感度体系/四阶段 + 男女频差异） | `references/outline-conflict.md`（感情线设计）· `references/style-combat-face.md`（后宫文女主 / 男频极简爱情线构型）· `references/plot-special-topics.md`（爱情线提纯策略） |
| 反转 | **`references/reversal-toolkit.md`**（反转类型/铺垫/有效性自检） | `references/plot-core-methods.md`（假胜：先给希望再击碎） |
| 人物 | **`references/character-basics.md`**（主角/配角/反派/动机模板速填） | `references/character-design-methods.md`（三层标签反差/九维深化）· `references/character-relations.md`（关系类型/感情线） |
| 女频写作 | **`references/female-audience-writing.md`**（女频长篇：核心原则/文案/题材/感情线长线/平台） | `references/genre-readers.md`（读者心理/平台差异）· `references/character-relations.md`（感情线总框架） |
| 去AI味 | **`references/anti-ai-writing.md`**（AI指纹/核心规则/Show Don't Tell） | `references/banned-words.md`（禁用词扫描）· `references/quality-checklist.md`（成稿检查） |

---

## 语言

- 跟随用户的语言回复，用户用什么语言就用什么语言回复
- 中文回复遵循《中文文案排版指北》

---

## 去味保护协议 v1.1

本轮新写章节进入去AI味独立审查前，先读 [小说保护账本](references/fiction-protection-ledger.md)、[模式治理](references/pattern-governance.md) 和 [结构审计](references/structural-audit.md)，再对章节工作区里的候选正文使用 [本 Skill 自带的保真脚本](scripts/deslop_guard.py) 创建 `standard + bounded` 去味候选并补全小说保护账本。narrative-writer 只编辑候选稿，完成现有 Gate 后先做保真审计，再只对改动区做残留味审计；保护检查通过后写回的仍是章节候选，不得绕过用户接纳门直接写正式正文。不得修改追踪派生文件，也不得因脚本命中自动扩大到整章结构重写。

## 中文正文英文零容忍门

中文正文和台词中的外文、缩写、型号和剧情代号一律视为 `language-leak blocking`，不得由模型自行豁免。URL、邮箱、代码、路径和文件名只有在明确属于非叙事结构时才机械保护；用户明确要求逐字保留的其他外语，必须单独确认并在 `.deslop-whitelist` 精确登记。HTML 标签、注释和实体一律视为 `forbidden-markup blocking`。题材卡、契约和提示词中的外文标签只是内部元数据，正文必须使用中文表达；独立 `language_gate.js` 未通过时不得提交章节。

## 本章语言验收 Gate（强制）

每章候选初稿完成后立即首先运行 `node scripts/language_gate.js "{候选稿文件}"`。返回非零时，把报告中的行号、原片段和所在行退回本章正文写作者修改，并重复检查；在返回码为零前，禁止运行后续检测、候选接纳、正式写入、追踪提交和下一章写作。不得用自动翻译、简单删除或未经用户单独确认的白名单代替正文修改。

## 本章文风卫生 Gate（强制）

语言门返回零后立即运行 `node scripts/check-style-hygiene.js --check --fail-on=blocking "{候选稿文件}"`。默认出版级策略清除表情符号、颜文字、火星文、标点堆砌和不可见字符；本书若确需聊天体，只能按 [正文文风卫生门](references/style-hygiene.md) 在 `设定/文风.md` 选择对白弹性或逐类配置。此 Gate 只改命中表达，不得借机改剧情、人物声线或扩大白名单。

## 适度对白技巧与漂移 Gate（强制）

重要对白场景先按 [适度对白技巧](references/dialogue-craft-moderate.md) 建立轻量对白卡，并以 [对白卡 schema](references/dialogue-scene-card.schema.json) 约束字段；长程退化边界见 [对白归属标记漂移](references/dialogue-attribution-drift.md)。中文语言 Gate 通过后运行 `node scripts/dialogue_drift_gate.js --current "{正文文件}" --history-dir "{正文目录}"`；明确的连续逐句报幕必须退回，密度和动词集中预警只进入语义审查，不机械判坏。

## 已接纳正文声音画像（足量样本后强制接入）

按 [已接纳正文声音画像协议](references/accepted-voice-profile.md) 执行。新书只从 `committed` 接纳回执取样；旧书无回执章节必须由作者显式批准连续范围。`chapter_candidate.py check` 自动对候选输出已接纳基线与黄金样本的双向 advisory；接纳闭环后 `voice_profile.py update` 只更新已接纳基线，黄金集合必须由作者再次精选。`story_doctor.py` 验证已配置画像摘要没有落后于正式正文。统计命中不自动改文；画像过期只阻断继续使用旧数据。

## 近章结构指纹 Gate

有至少三章历史正文时，按 [近章结构指纹与语义冷读](references/cross-chapter-shape.md) 执行。`chapter_candidate.py check` 自动调用 `chapter_shape_gate.py` 读取最近六章，主 Agent 必须在候选报告中回答五问并引用具体段落。脚本相似度、程序词和问答对都只作 advisory；需要重排已接纳正文时转入 revision-governor，不得从候选 Gate 直接回改旧章。
