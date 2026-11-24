# stroy — 网文写作项目

本项目按通用文件方式接入 oh-story skills。

- **通用端**:`skills/*/SKILL.md` 与 `skills/*/references/` 可被任意 Agent 直接读取执行;无 hooks 时运行时硬拦截与多 agent 自动协作不生效,按软约束或 solo/direct 降级执行。

## P0 级强制执行铁律：《他们不是人》长文写作 Skills 闭环（最高优先级）

任何涉及《他们不是人》**规划、大纲、细纲、设定修改、正文写作、续写或回炉改稿**的任务，必须在动手前将以下 `story-long-write` 与 `story-world-engine` 流程作为 **P0 级硬约束** 严格执行，严禁跳过任何一环：

1. **先读后写（P0-1）**：每次任务动笔前，必须读取 `skills/story-long-write/SKILL.md` 的「写前必读」清单及对应阶段流程文件（`workflow-outline.md` / `workflow-chapter.md` / `workflow-daily.md`），同时重读 `他们不是人/设定/文风.md`（唯一文风与禁忌基准）与 `他们不是人/设定/题材正文提示卡.md`。
2. **先纲后文与契约校验（P0-2）**：写正文前，必须先有对应卷纲的剧情段卡（用 `scripts/outline_view.py --chapter {N} {卷纲}` 校验通过）与合规细纲（必须通过 `node skills/story-long-write/scripts/check-outline-contract.js` 零阻塞）；严禁无纲盲写正文。
3. **写前恢复与组装（P0-3）**：开写单章或日更前，必须先执行 `tracking_commit.py check` 校验账本与派生视图一致，通读 `他们不是人/追踪/上下文.md` 全 7 栏与涉及角色/势力设定，再运行 `build_writer_prompt.py --project 他们不是人 --chapter {N} --out` 完成核对，并完成七关行动审查。
4. **格式与质量同轮清零（P0-4）**：正文严格遵守 `skills/story-long-write/references/long-format.md`（相邻段落单换行 `\n`、无加粗/斜体/分隔线、无工程词泄漏）。正文落盘后同轮内必须运行 `python skills/story-long-write/scripts/storyctl.py chapter check --project 他们不是人 --chapter {N} --fix-punctuation --plain`，保证 AI 句式 0 blocking、退化检测 0、细纲照搬核验通过；字数越界按作者流程处置。
5. **串行提交追踪与设定补登（P0-5）**：每写完一章，必须紧接通过 `tracking_commit.py draft` 填妥事务并用 `storyctl.py chapter commit`（或修订 `mode=revision`）串行提交入账，确保 `追踪/上下文.md`、逐章记录、核心角色快照、伏笔与双时间线即时同步；正文中新出现或升级的重要人物、势力、能力、器物与规则，同轮必须按「新增物三级」补登进 `他们不是人/设定/` 与 `他们不是人/大纲/`。
6. **主笔版权威基准（P0-6）**：《他们不是人》已按 16 卷标准大长篇定稿重构并完成去重精简，现行唯一权威为 `他们不是人/大纲/` 与 `他们不是人/设定/` 下的单一职责文档（旧版全量规则、103 章正细纲与历史记录已统一归档至 `他们不是人/_归档/`，仅供追溯，不再约束新稿写作）。
7. **同轮收尾提交（P0-7）**：每次完成《他们不是人》细纲编写、正文写作或相关设定/追踪更新并完成全套质量与账本校验后，必须在汇报收尾前主动执行 `git` 提交，确保本轮全部正文、细纲、设定、追踪文件与配套改动完整入库可回溯。

### 《他们不是人》设定与大纲文件维护规范（单一职责 · 防漏更 · 防重复建文件）

严禁在 `设定/` 或 `大纲/` 下新建功能重叠的平行文件（已废除原重复的 `都市异能正文风格卡.md`、`角色声线节奏卡.md`、`怀表机制.md`、`外物体系.md`、`壳的来历与规律.md`、`全书卷纲总览.md`）。各保留文件的职责、更新时机与修改方法如下：

1. **长期静态配置与基准文件（日常写章节不改，仅特定情形修改）**：
   - `他们不是人/设定/世界运行契约.json`：`story-world-engine` 七关审查的固定启用开关（`enabled: true`，底账指向 `追踪/_tracking-state.json`）。日常写书**无需修改**；仅当作者明确要求停用/变更世界引擎门禁时才改 `enabled` 字段。
   - `他们不是人/设定/文风.md`：全书唯一文风、单章结构、命名规范与硬性禁用词基准（由 `build_writer_prompt.py` 自动注入）。日常写书**无需修改**；仅当作者新增或调整行文偏好、标点/命名铁律时原地修改本文件，绝不另建第二份风格卡。
   - `他们不是人/归档索引.md` & `他们不是人/作品简介.md`：工作区目录说明与平台书封简介。仅在目录结构调整或准备平台发布资料（`story-publish`）时同步修改。
2. **按卷或重大转折节点更新的文件（换卷、改大纲时必须同步改）**：
   - `他们不是人/设定/题材定位.md` & `他们不是人/设定/全书梗概.md`：全书核心方向、「作者已定」红线与五次大转折。每逢作者拍板修改主线走向、终局底牌或跨卷规则时，必须同步更新这两份文件（「作者已定」会被脚本自动注入写手提示词）。
   - `他们不是人/设定/题材正文提示卡.md`：脚本每章必读的爽点与阶段红线提示卡（`genre_prose_card`）。**每逢进入新大阶段导致金手指消耗边界变化时（如第 2 卷锁死第 1 格改走背盘、第 7 卷开启第三重赤铜盘、第 12 卷归零入第 0 格）必须同步更新**，删掉上一阶段的过时约束，防止误导后续正文。
   - `他们不是人/设定/关系.md`：全书核心人物关系矩阵。**每卷开卷排纲时，或有重要盟友入伙、核心人物阵亡/反水掉马时**，在该表的「当前状态」与「关键变化节点」列原地更新，删改过时状态。
   - `他们不是人/大纲/大纲.md` & `他们不是人/大纲/伏笔总表.md`：`大纲.md` 为唯一全书 16 卷总表兼敌我/母钟归宿总账（绝不再另建总览副本）；跨卷长线伏笔的新增与阶段回收同步登记进 `伏笔总表.md`（单章即时伏笔状态由 `追踪/伏笔.md` 自动生成）。
3. **随排纲与正文推进增量更新的文件（一人一卡 · 一题一档 · 退场归档）**：
   - `他们不是人/设定/世界观/`（固定 4 文件，禁止拆分新文件）：
     - `力量体系.md`（九响、牌令、壳侧序列、普通人时痕、第 12 格变量）；
     - `金手指.md`（唯一器物与能力主档：五重表盘、拆核上弦、百表拓印、镜返七式、随身重器进化、三母钟部件）；
     - `临江城市生态与总倒计时.md`（壳的两大铁律、四层空间与鬼市经济、三大异俗、版本抹除边界、十二整点倒计时）；
     - `地理.md`（随每批细纲新登场的复用地图锚点在文末增量追加）。
   - `他们不是人/设定/势力/`（`钟表行.md`、`剥壳人.md`、`白塔.md`、`壳巢与恒泰设施.md`）：有新编制、新分坛或势力格局剧变时原地增量更新。
   - `他们不是人/设定/角色/`（一人一卡，内置声线，退场合并）：
     - 新建或修改角色卡时，文件顶部必须写顶格 `姓名：角色名`（兼容提交校验），且卡内必须包含 `- **声线**` 或 `- **声线与高压反应**`（不再单独建声线表）。
     - **退场归档清理规则**：阶段性反派或一次性配角在正文中彻底毙命退场、确认后文不再出场后，在该剧情段收尾时将其关键事迹与遗留物浓缩一行并入 `设定/角色/_已退场角色归档.md`，随即删除其独立单卡，防止角色目录无限膨胀堆积死档。

<!-- oh-story:generic 开始：重新部署时整块替换，自己的内容写在块外 -->
# stroy — 网文写作工具集（通用 Agent / Web AI）

本项目按通用文件方式接入 oh-story skills：读取 `skills/*/SKILL.md` 并按需读取 `skills/*/references/`。无原生 hooks 或 custom agents 时，写作检查由 skill 流程执行，分工走 solo/direct fallback。

## Skill 路由表

优先用自然语言点名 skill；如果平台支持自定义命令，也可以把下表映射成命令。

| 意图 | Skill | 说明 |
|------|-------|------|
| 写长篇 / 开书 / 续写 | story-long-write | 长篇网文写作（逐章推进） |
| 写短篇 | story-short-write | 短篇网文写作（情绪驱动） |
| 长篇拆文 | story-long-analyze | 长篇小说深度拆解 |
| 短篇拆文 | story-short-analyze | 短篇小说拆文分析 |
| 长篇扫榜 | story-long-scan | 长篇小说榜单与市场趋势 |
| 短篇扫榜 | story-short-scan | 短篇小说榜单与情绪风口 |
| 去 AI 味 | story-deslop | 去除 AI 写作痕迹 |
| 封面 | story-cover | 生成封面图 |
| 发布资料 | story-publish | 发布准备：整理并核对平台书籍资料 |
| 审查 | story-review | 多视角审查；无 custom agents 时降级为单线程审查 |
| 导入 | story-import | 逆向导入已有小说到项目结构 |
| 网文工具箱 | story | 模糊意图自动分发 |
| 准备写书 / 部署 | story-setup | 通用项目结构与 skill 使用入口 |
| 浏览器登录态 / 抓取 | browser-cdp | 浏览器 CDP 工具；需平台允许本地脚本/浏览器控制 |

## 文件结构

- `skills/` — 项目本地 skills；Agent 应先读对应 `SKILL.md`，再按需读取 `references/`
- `拆文库/` — 拆文分析结果存放目录
- `{书名}/正文/` — 长篇小说正文章节
- `{书名}/正文.md` — 短篇小说正文
- `{书名}/设定/` — 角色设定、世界设定
- `{书名}/大纲/` — 卷纲、细纲
- `{书名}/追踪/` — `_tracking-state.json` 为唯一结构化权威；追踪工具生成固定 7 栏 `上下文.md`、逐章记录、核心角色快照、伏笔视图和作者/读者双时间线
- `{书名}/对标/` — 对标作品分析

## 通用使用约定

- 写正文前先有大纲：长篇需要 `大纲/细纲_第N章*.md`，短篇需要 `小节大纲.md`。
- 无 hooks 的平台不会自动拦截越权写正文，Agent 必须在执行写作 skill 时自行检查大纲、上下文和追踪文件。
- 无 custom agents 的平台按 solo/direct 执行；遇到 skill 要求调用 story-architect、narrative-writer 等 agent 时，改由当前 Agent 直接完成，并在结果里说明降级。
- **每章写完先去 AI 味**（没有 hook 替你检查）：正文落盘后同一轮内按写作 skill 的检测器和禁用词表自检、改净；能运行 node 时跑写作 skill 的 `scripts/check-ai-patterns.js --check --fail-on=blocking {章节文件}`。写下一章前先确认上一章已改净。只有作者明确说「这章不去味」时才跳过，并在标题行下加 `<!-- 去味:跳过 -->`。

## 与作者协作

- 回复用作者说话的语言，等后台助手时的进度说明也一样；主体用写书的话说（书、章、大纲、设定），不抛脚本名、字段名或状态名；报错时附原始报错。skill 里标着 `<!-- author-report -->` 的模板块只是格式参考，回复时直接输出其中的文字，不带代码块围栏。
- 作者要求记住、改掉或忘掉一条写作习惯/偏好时（如「记住：这本书对话用直角引号」），按用户明确类型或当前书类型走 story-long-write / story-short-write 的「作者记忆管理」；无当前书的通用习惯默认交长篇入口，限定本书却无法定位时问哪本书，不要求先建书，写入相应工作区或书目录的 `.story/作者记忆/`；不要存进编程工具自带的记忆。一次性要求直接照做，不记录。
- 不修改项目里已安装的 skill 文件（`SKILL.md`、`references/`、`scripts/`；story-setup 重新部署时覆盖除外）。skill 脚本报错时停下，把报错和所执行的命令告诉作者，不自行修补绕过。

## Compact 后恢复上下文

写作中的关键上下文：
1. 当前写作项目名称和进度
2. 最近讨论的角色设定变更
3. 未完成的伏笔列表
4. 当前章节的情绪/节奏目标

长篇先读 `{书名}/追踪/上下文.md`；短篇先读 `{书名}/设定.md` 和 `{书名}/小节大纲.md`。
<!-- oh-story:generic 结束 -->

## 全项目 Skills 体系使用、正本镜像与内容维护总则（全部 15 个 Skills 必读）

> **注意**：上方 `<!-- oh-story:generic 开始 ... 结束 -->` 管理块由 `story-setup` 自动维护，请勿手工拆改该块边界；全项目 **15 个 Skills**（14 个 `oh-story` 官方技能 + 1 个项目自研 `story-world-engine`）的正本规范、内容修改方法与使用边界统一以本节为准。

### 一、正本位置、去重原则与为什么保留全套 15 个目录

1. **唯一正本目录**：仓库根 `skills/`（共 15 个技能目录 + 同步脚本 `skills/sync-story-world-engine.ps1`）。
2. **禁止多目录无意义重复拷贝**：
   - 已清理 `.workbuddy/`、`.claude/`、`.codex/`、`.opencode/` 等无意义的隐藏目录重复副本。
   - 当前仅保留 `.agents/skills/story-world-engine/` 作为 Antigravity 宿主的自动发现镜像（由 `.gitignore` 忽略，不入 Git；`sync-story-world-engine.ps1` 默认只同步 `.agents/`，仅在显式部署了其他宿主目录时才按需同步）。
   - 若未来切换编程工具或需为 Antigravity 启用原生子代理/Hooks，统一执行 `/story-setup` 自动管理受管目录，**严禁手工把 `skills/` 复制到其他隐藏文件夹**。
3. **为什么不单删某几个低频/短篇 Skill 目录**：
   - 14 个 `oh-story` 技能属于 `v0.10.3（agents_version: 42）` 原子套件，`story-setup` 在环境体检与升级校验时会逐一检查这 14 个目录及 `SKILL.md` 是否齐全（缺任何一个都会判定技能包残缺并拒绝升级），且内部存在跨技能复用（如 `story-import` 复用 `story-long-analyze` / `story-short-analyze`，扫榜技能复用 `browser-cdp`）。因此 **15 个目录全部作为「日常写章节不改动、但必须整套保留的静态工具库」**，按下方职责隔离调用。

---

### 二、Skills 文件的内容修改规范（平时不改 · 怎么定制 · 怎么升级）

所有 `skills/*` 均属于**通用写作工具与规则引擎**，日常推进《他们不是人》大纲、正文或追踪时**绝不逐章修改任何 Skill 文件**。确需调整规则或升级工具时，严格按以下三类归属处理：

1. **第 1 类：12 个纯上游 `oh-story` 官方技能（严禁手改源码，定制需求分流进书目录）**
   - **包含**：`story-long-write`、`story-setup`、`story`、`story-long-analyze`、`story-long-scan`、`story-publish`、`story-cover`、`story-import`、`story-short-write`、`story-short-analyze`、`story-short-scan`、`browser-cdp`。
   - **硬禁令**：严禁手工修改其 `SKILL.md`、`references/`、`scripts/`；遇到脚本校验拦截或报错时，必须修书稿/修细纲或停下把原始报错报给作者，**绝不允许篡改脚本绕过门禁**。
   - **定制分流（想改规则时改哪里，而不是改 Skill）**：
     - 改行文质感、对白节奏、章名规则、本书硬性禁用词 ➔ 改 `他们不是人/设定/文风.md`；
     - 改当前卷段爽点与金手指消耗边界 ➔ 改 `他们不是人/设定/题材正文提示卡.md`；
     - 豁免本书高频专名/固定意象被去味脚本误报 ➔ 写入 `他们不是人/.deslop-whitelist`（一行一词）；
     - 长期记住/修改/忘掉作者跨章个人偏好 ➔ 走 `story-long-write` 的 `scripts/author_memory_commit.py` 记入 `.story/作者记忆/`。
   - **升级方法**：仅当上游 `oh-story-claudecode` 发布新版本时，先更新全局包，再在项目根执行 `/story-setup` 按 `.story-deployed` 整包刷新覆盖。

2. **第 2 类：2 个挂载了本地「v2 审查策略」增强层的技能（`story-deslop`、`story-review`）**
   - **构成**：底层确定性检查脚本（`check-ai-patterns.js`、`check-degeneration.js`、`normalize-punctuation.js`）为上游 `oh-story v0.10.3` 原版（**严禁改脚本硬门规则**）；之上挂载了本项目专属的**正样本校准与反向 Gate H（声线差异）/ Gate I（叙述者在场）**增强层：
     - 策略主档：`skills/story-deslop/references/ai-review-strategy-v2.md`（配套 `accepted-voice-profile.md`、`pattern-governance.md`、`scripts/voice_profile.py`、`scripts/prose_metrics.py`）；
     - 挂接指针：`skills/story-deslop/SKILL.md`（Phase 1/2 必填项）、`skills/story-review/references/quality-rubric.md`、`skills/story-review/references/rubrics/fanqie.md`。
   - **修改与升级方法**：
     - 调整本书具体声线或叙述标准时，优先改 `他们不是人/设定/文风.md` 与 `设定/角色/*.md`；
     - 确需修改反向 Gate H/I 审查协议或报告字段时，原地修改 `skills/story-deslop/references/ai-review-strategy-v2.md`；
     - **防覆盖核对**：每次用 `/story-setup` 升级上游套件后，`story-deslop` 与 `story-review` 会被上游覆盖，升级后须核对 `ai-review-strategy-v2.md` 及上述 3 处挂接指针是否完整保留。

3. **第 3 类：1 个本项目独立自研技能（`story-world-engine`）**
   - **唯一正本**：`skills/story-world-engine/`（不属于 `oh-story` 上游，`/story-setup` 升级不会覆盖它）。
   - **修改方法**：仅当作者要求调整人物行动七关字段、写前/写后审查包契约（`references/packet-contract.md`）或门禁导出逻辑（`scripts/world_gate.py`）时，**只在 `skills/story-world-engine/` 正本内修改**，随后依次执行：
     1. `python -m unittest discover -s skills/story-world-engine/tests`（确保单元测试全绿）；
     2. `pwsh -File skills/sync-story-world-engine.ps1`（将正本同步至 `.agents/skills/story-world-engine/`）；
     - **严禁直接编辑 `.agents/` 下的镜像文件**（镜像与正本冲突一律以正本为准）。

---

### 三、全部 15 个 Skills 分类职责、触发时机与读写边界

#### A. 《他们不是人》日常创作核心闭环（4 个高频必用 Skill）

| Skill | 触发时机与核心职责 | 必读入口与核心脚本 | 严格读写边界 |
|---|---|---|---|
| **`story-long-write`** | 开卷排纲、补/改细纲、写单章、日更续写、回炉改稿、记录作者写作习惯 | 先读 `SKILL.md`「写前必读」表及对应 `workflow-*.md`；脚本：`outline_view.py`（切卷纲，禁整读）、`check-outline-contract.js`（细纲门禁）、`build_writer_prompt.py`（写前核对组装）、`storyctl.py`（质检与提交）、`tracking_commit.py`、`author_memory_commit.py` | **唯一允许通过 `tracking_commit.py` / `storyctl.py` 写入 `追踪/_tracking-state.json` 及派生追踪视图的入口**；未明确要求写正文前最远停在细纲交付 |
| **`story-world-engine`** | 凡涉及新人物行动、新台词、新事件或重写（排纲/人设/写章/日更/改稿）均与 `story-long-write` 联用 | 先读 `SKILL.md` 与 `references/seven-gates.md`、`packet-contract.md`；脚本：`scripts/world_gate.py`（`init` / `check --phase prewrite\|postwrite` / `export`） | `world_gate.py` **只做检查与导出 `.story/派生视图`，不写正文、不改 `追踪/` 正史**；写前/写后包只放 `.story/世界引擎/第NNN章/` 等工作目录，七关字段严禁漏进正文 |
| **`story-deslop`** | 单章落盘后去 AI 味自检，或作者点名「去 AI 味 / 这篇太 AI 了」 | 先读 `SKILL.md`、`style-resolution.md`、`ai-review-strategy-v2.md` 及 `expression.md` / `narrative-focus.md` / `story-logic.md`；脚本：`check-ai-patterns.js`、`prose_metrics.py`、`voice_profile.py` | 改前自动备份至书内 `.story/work/去味原稿/`；**只改表达、用笔与既有承接**，凡需改动事件、关系、人物所知或结果，必须转交 `story-long-write`「修改第X章」同步追踪 |
| **`story-review`** | 卷纲/大纲定稿前、阶段收官或作者要求「审查一下」 | 先读 `SKILL.md`、`quality-rubric.md`、`rubrics/fanqie.md` 与 `ai-review-strategy-v2.md`；无子代理时自动降级 `solo` 单线程对抗审查 | **纯只读找茬**：只输出白话问题清单、原文证据与拍板选项，**绝不直接修改正文、大纲、设定或追踪** |

**附：`story-world-engine` 每章联用最小 7 步标准流**
1. **恢复**：读 `{书名}/追踪/上下文.md` + 上一已接纳章 + 本章细纲；用 `tracking_commit.py check` 校验 `_tracking-state.json` 与派生视图同步。
2. **七关**：列出本章全部行动者，逐项核实 `knows/wants/fears/capability/no_plot/costs/consequences`（唯一阻断：答不出原因；合理未知写清边界可过）。
3. **写前包**：`python skills/story-world-engine/scripts/world_gate.py init ... --tracking-tool skills/story-long-write/scripts/tracking_commit.py --packet .story/世界引擎/第NNN章/写前行动审查.json`，填妥跑 `check --phase prewrite`。
4. **写正文**：按 `story-long-write` 落盘 `正文/第NNN章_{章名}.md` 并跑 `storyctl.py chapter check --fix-punctuation --plain` 清零 blocking。
5. **写后包**：复制冻结前包到 `.story/世界引擎/第NNN章/写后行动复核.json`，绑定当章未入账正文填妥 `postwrite`，跑 `check --phase postwrite` 并按七问复读。
6. **记忆闭环**：用 `tracking_commit.py draft` + `storyctl.py chapter commit` 串行提交入账；按需运行 `world_gate.py export --output .story/派生视图` 刷新视图。
7. **卷末核账**：每卷收官核对事件、得失、人物关系表、伏笔总表、未履约承诺与下卷阶段提示卡。

#### B. 对标拆文、市场扫榜与出版周边（5 个阶段按需 Skill）

| Skill | 何时调用 | 产物落盘位置与读写边界 |
|---|---|---|
| **`story-long-analyze`** | 引入新的外部参考长篇 TXT（如拆解对标书黄金三章、三维节奏、情绪模块） | 原始拆文全量落盘 `拆文库/{外部书名}/`，再将与本书相关的结构化模块同步至 `他们不是人/对标/`；**严禁把本书正文当外部对标拆解** |
| **`story-long-scan`** | 开新书立项、大换地图或研判起点/番茄/七猫男频榜单风口时 | 落盘 `扫榜数据/{日期}/`（含榜单分析与选题参考）；纯市场情报，**不自动修改本书大纲、设定或追踪** |
| **`story-cover`** | 准备上架或更换书封，需要封面设计提示词或生成封面图时 | 提示词与生成图片统一落盘 `他们不是人/封面/`；仅要求提示词时不调生图接口 |
| **`story-publish`** | 正文满约 2 万字准备番茄上架，或需整理核对平台书名、标签、多版本简介时 | 读取设定与已写正文核对并更新 `他们不是人/作品简介.md` 及建书表单资料；**只生成核对资料，不代替作者去后台点击发布** |
| **`story-import`** | 将外部已写好的旧小说 TXT 逆向解析建档，或修复极早期缺失 `_tracking-state.json` 的旧项目时 | 生成标准项目目录或归档旧追踪至 `追踪/_旧追踪存档/`；**《他们不是人》现行结构与追踪完好，日常严禁误触调用** |

#### C. 底层基建路由与短篇隔离区（6 个基建 / 隔离 Skill）

| Skill | 定位与何时调用 | 隔离与安全边界 |
|---|---|---|
| **`story`** | 网文工具箱总路由与本地工作台入口（意图不明时自动分发，或 `/story dashboard` 打开本地面板） | Dashboard 仅允许监听本机 `127.0.0.1`（对应 `启动工作台.bat`），严禁暴露局域网或公网 |
| **`story-setup`** | 环境体检（`check` 模式）、切换编程工具宿主、或更新 `oh-story` 套件后重部署受管文件 | 只更新受管 skill/hook/agent 与管理块，保留书稿、设定、大纲、追踪与管理块外的项目自定义铁律 |
| **`browser-cdp`** | 供 `story-long-scan` / `story-short-scan` 在本地 Chrome 开启调试端口并获授权时复用登录态抓取榜单 | 仅走用户已授权的公开/已登录页面读取；**严禁用于绕过验证码、反爬门禁或未授权探测** |
| **`story-short-write`**<br>**`story-short-analyze`**<br>**`story-short-scan`** | **短篇专属三件套**：分别用于番茄短故事/知乎盐言等短篇创作（单文件 `正文.md` + `小节大纲.md`）、短篇拆文与短篇扫榜 | **长短篇严格隔离铁律**：在创作长篇《他们不是人》期间**严禁调用这 3 个短篇技能**，防止污染长篇逐章目录与追踪体系；仅当作者在本工作区另开独立短篇目录时启用 |
