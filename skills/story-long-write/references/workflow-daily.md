# workflow-daily.md：日更续写工作流

本文件为"日更续写"场景的完整指引。SKILL.md 路由到本文件后，按以下流程执行。

> **日更准备步骤**：每章写作前 4 步——状态筛选 + 题材正文提示卡召回 + 文风召回 + 意图确认，嵌入 Step 2 逐章循环。读者契约、主角代理权、期待债、终局储备统一参 `reader-contract-and-progression.md`。
>
> Step 2 必读 / 生成四类写前资料：
> 1. `{对标书路径}/剧情/情绪模块.md`（读者需求 / 情绪引擎 + 可复现模块；缺失按下方「模块/节奏缺失」规则停下修复）
> 2. `{对标书路径}/剧情/节奏.md`（关键信息推进 + 情绪触动点 + 爆发节奏；缺失按下方「模块/节奏缺失」规则停下修复）
> 3. `设定/题材正文提示卡.md`（题材边界 / 核心逻辑 / 读者期待 / 节奏密度；缺失时用 `设定/题材定位.md` + `references/genre-prose-cards.md` 索引匹配并读取 `references/genre-prose-cards/{题材}.md` 单卡优先生成，`references/style-genre-modules.md` 通用流派兜底）
> 4. 写作方法分支：先运行 `style_method.py resolve`。A 才读取 `{对标书路径}/文风.md`（整书级 ~4000 字，含原文锚点范例片段）；B 改读本章 `compiled_method_packet`
>
> 对标书路径查找：先 `{项目}/对标/{书名}/`，回退 `拆文库/{书名}/`。
>
> A 的文风召回在主产物齐备后，再按本章基调读取一个匹配章摘要及可用深度拆解；B 不读取匹配章原文锚点。
>
> **题材正文提示卡**：优先读 `设定/题材正文提示卡.md`；缺失时不阻塞，先从 `设定/题材定位.md` 精确匹配 `references/genre-prose-cards.md` 索引，并只读取 `references/genre-prose-cards/{题材}.md` 题材单卡（高/中/低置信照原卡标注），无命中再从 `references/style-genre-modules.md` 抽取通用流派短 `genre_prose_card`。题材卡只管题材味和正文取舍，不改细纲、不覆盖情绪/节奏权威文件，也不接管句长/标点等文风细节。题材卡只在写手心里校准取舍，卡名/题材标签/置信度/条目/合规自评一律不写进正文。
>
> **自定义文风（`设定/文风.md`，优先级最高）**：主会话每章写作前直接读 `设定/文风.md`（不经 story-explorer——它只看 `对标/文风.md`）。存在且含实质内容（去空白 ≥200 字，或含「句长 / 标点 / 对话 / 锚点 / 笔调」风格小节且小节内有可执行约束：比例 / 例句 / 禁止或偏好描述）即进入「自定义文风模式」：它是本书既定笔调的**权威**风格基，narrative-writer 的句长带 / 标点节奏 / 对话潜台词 / 情绪交替以它为准。A 的对标 / 拆文 `文风.md`或 B 的 `compiled_method_packet` 降级为「**参考**」，不再是被遵循的最终文风；B 即使降级也不回读来源原文。空 / 仅空白 / 仅标题 / 占位 stub（待办 / 待补充 / ___）视为不存在。仅接管风格，**不覆盖** `剧情/情绪模块.md` / `剧情/节奏.md` 的情绪与节奏意图（同下「冲突规则」）。随机标点堆砌、英文点号投机、Markdown 分隔线和项目/平台明确禁用项仍由格式门处理；有功能的 `……`、`——`/`—` 先按自定义文风和场景功能复核，不一刀切归一。段落结构、碎句密度仍按戏剧单元与读感判断。
>
> **文风缺失**：`A-standard` 且**未进入自定义文风模式**时，对标书缺 `文风.md` 则停止本章写作、不 inline 生成，报错：「对标书 X 缺少 文风.md。请用 `/story-long-analyze` 跑 Stage 6 生成文风，再 `/story-import` 同步。」已进入自定义文风模式则用 `设定/文风.md` 继续。`B-distilled` 不读取对标 `文风.md`，它只检查编译方法绑定和本章规则包。
>
> **模块/节奏缺失**：对标书缺 `剧情/情绪模块.md` 或 `剧情/节奏.md` 时停止本章准备，设置 `gaps.missing_primary_contract: true`，提示重跑 `/story-long-analyze` Stage 3+ 或重新 `/story-import`；不得用摘要文件拼装低置信替代品。
>
> **冲突规则**：`剧情/情绪模块.md` 与 `剧情/节奏.md` 是情绪和节奏的权威来源；`拆文报告.md`、`剧情/故事线.md` 是投影摘要；`文风.md` 只管风格。若摘要或文风与权威模块/节奏冲突，保留 `gaps.conflict`，正文意图跟随权威文件。
>
> **无对标项目**：无 `设定/文风.md` 时跳过「对标模块/节奏/文风召回」，在「意图确认」标记"无对标参考"，不读不存在的文风、不阻塞、不警告；题材卡不是对标产物，仍从 `设定/题材正文提示卡.md` 或本书题材信息生成 `genre_prose_card`。**有 `设定/文风.md`（自定义文风模式）则用它写作**——此时无对标可召回，情绪/节奏目标改从本书细纲「目标情绪」、卷纲、`设定/题材定位.md` 等内部材料取，`selected_emotion_module` / `rhythm_reference` 记「无」，不声称从对标召回。
>
> **多本对标书**：从 `设定/题材定位.md` 读 `主对标书` 字段；字段指向当前作品时按缺失处理（老项目可能把本书自身登记成了主对标）。缺失时用 `对标/` 下字典序第一本并提示用户补字段——先按当前项目目录名、`.active-book` 和 `设定/题材定位.md` 中的本书信息识别当前作品，排除同名或来源指向当前正文的 `对标/{当前书}/`；排除后为空则按无对标处理。
>
> 完整写前准备逻辑见 `SKILL.md` 的 Phase 4。
>
> **写作方法分支**：完整规则见 `style-method-branches.md`。没有 `设定/写作方法.json` 的旧项目使用隐式 `A-standard`，行为不变。显式 `B-distilled` 每章必须先通过 `style_method.py check/resolve`；B 只替换对标文风与原文锚点直载，情绪模块、节奏、题材卡和本书声音画像仍照常加载。B 产物失效时停止，不得静默回退 A。

---

## 适用条件

- 项目已有 `正文/` 和 `追踪/` 目录
- 用户明确说"日更""续写""继续写"，或明确指定"写第 N-M 章"
- 默认只生成 `last_committed_chapter + 1` 的一章候选并停在接纳边界；只有用户在本次任务明确授权“自动定稿/无需逐章确认/连续写完并自动定稿”时，才按最多 3 章微批次连续完成正式提交

> **裸调用不进日更**：如果用户只是触发 `/story-long-write` / `$story-long-write`，没有说"日更/续写/继续写/写第N章/只写1章/逐章确认"，不得进入本 workflow。回到 `SKILL.md` 的"裸调用与停靠点"，只展示当前进度与可选命令，避免重启会话后自动写 3 章。

---

## Step 1：快速上下文加载

**可选：使用 story-explorer agent 批量加载上下文**。按当前运行时检查 story-explorer（Claude `.claude/agents/story-explorer.md`、OpenCode `.opencode/agents/story-explorer.md`、TRAE Code `.trae/agents/story-explorer.md`、WorkBuddy 项目模式 `.codebuddy/agents/story-explorer.md`、Codex `.codex/agents/story-explorer.toml`）。可用时调用同名 agent 执行 `context_load`；TRAE Code 只用内置 `Agent` 按 `.trae/agents/story-explorer.md` 的名称选择同名 Subagent，不传 Claude 的 `subagent_type`；WorkBuddy 项目模式用 `Agent(subagent_type: "story-explorer", prompt: ...)`，plugin-only 仅在当前 Agent registry 真实返回 `oh-story:story-explorer` 时使用该精确值；Claude/OpenCode 可用等价 `subagent_type`，Codex 使用 `agent_type`，任务正文统一为 `项目目录：{dir}\n查询类型：context_load\n查询参数：准备写第 {N} 章\n追踪状态：last_committed_chapter={上一步 check 的值}，state_revision={上一步 check 的值}`。返回后直接使用其 results，跳过下方手动加载步骤。如果 agent 不可用或返回不完整，回退到下方手动加载。

手动加载（默认方式）：

| 序号 | 文件 | 用途 | 如果不存在 |
|------|------|------|-----------|
| 1 | `tracking_commit.py check` | 校验唯一结构化 state 与全部派生视图，并取得最后提交章和修订号；不把完整 state 加入 prompt | state 缺失且新书尚无正文时执行初始化；已有正文则停止并要求由 `story-import` 重新导入为标准项目 |
| 2 | `追踪/上下文.md` | 续写状态卡（≤12KB，固定 7 栏，每章整份读） | 不手写；由初始化/逐章事务生成 |
| 3 | `大纲/细纲_第{N}章.md` | 本章写作计划 | **必须先补建**，不允许跳过 |
| 4 | `大纲/卷纲_第X卷.md` | 卷契约、当前剧情单元、终局储备与未来揭示计划 | 缺必需字段时先补齐；锁定卷纲绝不自动修改 |
| 5 | `设定/角色/{角色名}.md` | 本章涉及角色的静态原始人设 | 只为核心复用角色按 Phase 3 规则补建 |
| 6 | `追踪/角色状态/{角色名}.md` | 久别核心角色的派生当前快照；只按细纲涉及角色加载 | 缺失即视为派生视图损坏：先运行 `tracking_commit.py check`，再重跑产生当前状态的完整事务；已有正文却无 state 时重新 `story-import` |
| 7 | `追踪/事实档案/{实体}.md` + `追踪/关系清单.md` | 细纲涉及的身世、血缘、婚姻、传承、所有权、权限和不可逆规则 | 实体无档案不代表没有历史；先查 `长期事实.md`、设定和正文，有长期价值的事实在本章事务补建稳定 ID |

`追踪/伏笔.md`、`追踪/时间线/`、`追踪/逐章记录/` 默认不整份读取。`长期事实.md` 也不每章整份加载；优先按细纲的人物/机构/物件名读实体档案或用 ID 定点查询。续写状态卡没有某个旧信息时，才按「旧信息查找步骤」定点查询。

**按需加载创作公式**：当写作中需要引用创作公式约束时（如期待感公式、爽点公式、信息差公式），加载 `references/genre-writing-formulas.md`。默认不加载，避免无条件加载 1500+ 行文件浪费 token。

### 续写状态卡与追踪事务

`追踪/上下文.md` 不是历史档案，而是当前语义检查点中的续写状态卡；顶层只能有以下 7 个栏目：`当前位置 / 长期约束 / 核心角色状态 / 活跃伏笔 / 近三章速记 / 下一章承诺 / 连贯性风险`。目标 8192 字节，硬上限 12288 字节。文风每章从 `设定/文风.md` / 对标文风读取；质量计数、普通待办、文件行数索引、参照章使用记录、去 AI 味统计都不进入续写状态卡。

所有追踪文件的 schema、事务 JSON、初始化和失败修复统一见 [tracking-transaction.md](tracking-transaction.md)。每章只向工具提交一次结构化事务，由 `scripts/tracking_commit.py` 确定性生成逐章增量、角色快照、伏笔当前视图、作者/读者时间线和续写状态卡；主会话和子 agent 都不得分别直接改这些最终文件。

**首次初始化**：

1. `_tracking-state.json` 不存在且项目尚无正文：构造 `last_chapter=0` 的初始化事务，执行 `tracking_commit.py init`。
2. `_tracking-state.json` 不存在但项目已有正文：停止日更。该目录停在旧追踪结构上，走 `/story-import` 的「旧追踪项目迁移」重建 `追踪/`——**不用重跑全书拆解**，只按最后完整章号和现有追踪文件构造初始化事务。本 workflow 自己不解析旧追踪结构、不推测状态。`init` 会把旧结构按原样整体移入 `追踪/_旧追踪存档/` 再建当前协议——旧内容不删除也不参与解析。
3. `tracking_commit.py check` 报告派生视图与 state 不一致：重新提交该章的 `mode=revision` 事务让工具整份重建（`expected_state_revision` 取 `追踪/_tracking-state.json` 的 `state_revision` 字段——`check` 失败时只往 stderr 打 ERROR，不输出 JSON）；不得手改 Markdown 或继续写下一章。手写出的逐章记录会让同章 append 永久报 `chapter delta N already exists with different content`，删掉那个手写文件后重跑原事务即可。

**长期约束溢出**：工具最多接受 6 条。出现第 7 条时，在提交事务前先合并语义重叠项或请用户裁定取舍；不得自动删除旧约束，也不得把待办塞进派生视图。

**退役必须显式声明**：`context.long_term_constraints` 和 `context.continuity_risks` 每章整份提交，因此每次都要把仍然成立的条目原样带上。凡是上一版有、本次不再提交的条目，必须逐条写进 `delta.retired_context_items`；漏写会被工具在任何写入前拒绝，不会被当成删除。不再复用的核心角色同理写进 `delta.retired_characters`；角色本章阵亡/退场时照常写 `character_changes`，不必再交一份马上要删的快照。两类退役都只能在 `mode=append` 提交——修订事务的记录属于被改写的旧章，写在那里会谎报退役章节；回炉必须原样重交当前全部上下文条目。两类退役都会留档在本章逐章记录，事后可回查。

**与项目 rules 的关系**：永久生效的设定裁定进入事务 `context.long_term_constraints`；短期强承诺进入 `delta.next_chapter_commitments`；已完成或只影响本章的过程决策不进续写状态卡。

> **确定下一章编号 N 与状态修订号**：执行 `tracking_commit.py check`，从其紧凑 JSON 输出取 `last_committed_chapter + 1` 与 `state_revision`，同时核对 `上下文.md` 的当前位置。逐章事务必须把该修订号写进 `expected_state_revision`；若提交前状态已经变化，工具会在任何写入前拒绝旧事务，此时重新读取当前状态并重构。不要把会随历史增长的完整 state 读进 prompt；章号不一致时修复，不扫描正文猜测编号。

先判定 `approval_mode`。未出现本次任务明确的自动定稿授权时固定为 `review`：T=下一章候选，K=1，质检后向用户交付候选摘要并停止；“续写/继续/日更/写三章”只表示希望生成内容，不自动等于接纳。只有用户明确说“自动定稿/无需逐章确认/连续写完并自动定稿”时才为 `auto`，把授权摘要写入每章候选 manifest，T 取用户目标、K 取剩余目标内 1-3 章。总字数目标只累计已接纳、已提交追踪且 doctor 通过的正文；任一门禁失败、用户中断或出现结构性路线分歧时自动授权立即失效。

---

## Step 2：串行批量写作

一次加载多章细纲，但**必须在主会话内串行逐章写作**：不得把多章同时交给多个子代理并发写。长篇章节依赖上一章正文和追踪文件，并发会导致上下文断裂、追踪覆盖和标题去重失效。

**候选 continuation 规则**：进入本 Step 后，“继续/续写/日更”不得被解释为跳过状态筛选或接纳门。`review` 模式只完成下一章候选并停止，等待用户明确“接受/定稿/采用这版”；修改意见只修改候选并重新跑 Gate。`auto` 模式才在每章 doctor 通过后串行进入下一章，每满 K（最多 3 章）进入 Step 3/4。自动授权不得跨任务、跨结构性分歧或跨失败恢复静默延续。

1. **读取写作计划**：写作计划按 **卷契约 → 当前剧情单元 → 章节细纲** 的顺序确定；已写内容仍以正文与 `追踪/` 文件为准。先从 `大纲/卷纲_第X卷.md` 读取卷契约、当前剧情单元（单元ID/位置）、单元情绪引擎、本卷主推线/战果与终局底牌边界；`review` 只加载下一章细纲，`auto` 才加载当前微批次 1-3 章细纲。卷纲或细纲缺少当前协议的必需字段时先补齐，未知字段写 `[待补充]`，不在内存临时推断一套替代结构；已锁定卷纲不得自动改动。细纲读取「阶段位置」「本章结构公式」「本章禁止提前释放」「内容概括（起因/发展/转折/高潮/结尾）」「情节安排（主线/辅线/事件线/感情线/逻辑线）」「人物关系和出场顺序」「情节细化」「结尾设定和钩子」及逐点字数预算。只有真正影响后续连续性的结果才进入本章事务，规划推理过程不落追踪。
   - **批次定位与阶段约束**：写本批前先从 `大纲/大纲.md`、对应 `大纲/卷纲_第X卷.md` 和本批细纲提取：当前章节区间属于哪个阶段、本批推进目标、本批可释放的信息、本批严禁提前释放的信息、章尾钩子不能越过的边界。必须按终局储备确认本批主推线与战果，别动用本阶段还不该解锁的终局底牌（多线齐涨的战果允许）；行动成本可无，不硬造代价。未来揭示计划留在大纲，不写入时间线事实；只有下一章必须消费的边界才进 `## 下一章承诺`。
   - **阶段进度自检**：每批写完或补完细纲后检查是否超前、拖慢或偏离阶段节奏；若偏离，把下一章必须执行的补偿动作放入事务 `next_chapter_commitments`，跨多章风险放入 `continuity_risks`；不得通过提前泄露后期信息强行提速。
2. **逐章执行**（以下每步在每章循环内执行）：
   - **创建精确许可**：先读 [章节候选协议](chapter-acceptance-and-doctor.md)，运行 `chapter_candidate.py init`；章号必须是 `last_committed_chapter + 1`，目标绑定本章正式文件名，卷纲/题材契约等作为 `--base`。所有写作和去味都只作用于运行目录中的候选正文文件
   - 读细纲 → 按需加载角色设定
   - **标题预检**：扫描既有章节标题；如本章标题同名或明显重复，先按本章核心事件改名，并同步细纲标题与正文文件名
   - **上一章欠账检查**：写本章正文前，确认上一章无未清 blocking 毒句式、语言泄漏、HTML 标记和文风卫生污染。写前 hook 会自动拦；hook 不可用时，先跑 `node scripts/language_gate.js 正文/第{N-1}章_*.md`，再跑 `node scripts/check-style-hygiene.js --check --fail-on=blocking 正文/第{N-1}章_*.md`、`node scripts/check-ai-patterns.js --check --fail-on=blocking 正文/第{N-1}章_*.md` 与 `node scripts/check-degeneration.js --check --language=zh --fail-on=blocking 正文/第{N-1}章_*.md`。有欠账先清完再写本章；去味跳过不得绕过语言门或文风卫生门，正文也不得写入 HTML 豁免标记。
   - **状态筛选**：每章开始前必须确认本章细纲、上一章正文（或上一章刚写入的正文）、`追踪/上下文.md` 已在本轮实际读取/更新，并已运行 `tracking_commit.py check`。不要为取状态/章号把完整 `_tracking-state.json` 加载进 prompt。角色最新状态先取续写状态卡 `## 核心角色状态`，待回收/推进伏笔取 `## 活跃伏笔`；缺失内容按下方「旧信息查找步骤」定点查询，不得用未标明来源的聊天记忆替代，也不得为了方便通读所有逐章记录。
   - **久别角色交叉检查**：本章细纲列出的核心复用角色若不在 `## 核心角色状态`，直接读取小文件 `追踪/角色状态/{名}.md`；不存在即视为当前检查点损坏，运行 `tracking_commit.py check` 并通过完整事务修复，不能临时扫描增量后手写替代。`设定/角色/{名}.md` 只有静态原始人设，不能替代动态快照。角色重新活跃后，把名字放进本章事务 `context.active_character_names`，由工具更新续写状态卡。
   - **写作方法分支解析**：从本章细纲提取 3-6 个场景标签，运行 `scripts/style_method.py resolve --project {项目目录} --scene-tag ...`。A 进入下方现有 `benchmark_style_load`；B 把 `selected_rules` 作为 `compiled_method_packet`，不读取对标 `文风.md`、匹配章锚点或来源原文，同时主会话直接读取 `剧情/情绪模块.md` 和 `剧情/节奏.md`。`chapter_candidate.py init/check` 会再次核验分支并把方法快照绑定进候选上下文。
   - **对标模块/节奏/题材卡/文风召回**：
     - **A 分支**调 story-explorer 的 `benchmark_style_load` query_type（输入：项目目录 + 本章目标情绪 + 本章爽点类型 + 本章目标字数）一次性拿到：`{style_profile_path, style_profile_summary, selected_emotion_module, rhythm_reference, module_source_path, rhythm_source_path, matched_chapter_K, matched_chapter_techniques, anchor_excerpts, gaps}`。**B 分支不调用这条组合召回**；它直接选择情绪模块和节奏条目，再使用上一步的 `compiled_method_packet`
     - 下方 `gaps.profile_*`、匹配章和锚点分支只适用于 A。B 只处理直接读取情绪模块/节奏时的 `missing_primary_contract` 与冲突，并检查 `compiled_method_packet` 非空；不得为了复用 A 的结构而读取来源文风或锚点
     - **题材正文提示卡召回**：主会话优先读 `设定/题材正文提示卡.md`；缺失则先读 `设定/题材定位.md` + `references/genre-prose-cards.md` 索引，按主题材精确匹配后只读取 `references/genre-prose-cards/{题材}.md` 单卡（如 都市脑洞 / 豪门总裁 / 年代 / 双男主；低置信卡必须在意图确认标注低置信，并要求同题材对标校准），无命中再读 `references/style-genre-modules.md` 通用流派模块。跨题材时主题材抽 3-5 条、辅题材抽 1-2 条，生成 `genre_prose_card`（题材边界、核心逻辑、读者期待、核心爽点/情绪、节奏密度、场景颗粒、禁止漂移、本章取舍、卡片置信度）。题材卡必须进入 narrative-writer prompt，但只传短摘要，并说明卡片只供内部题材校准、正文里不得出现卡片文字或合规自评
     - **自定义文风覆盖（先于下列 gaps 判定）**：主会话直接读 `设定/文风.md`（不经 explorer），含实质内容（去空白 ≥200 字，或含 句长 / 标点 / 对话 / 锚点 / 笔调 小节且小节内有可执行约束：比例 / 例句 / 禁止或偏好描述）则置 `custom_style=true`——它作权威风格基**取代** `style_profile_path` 喂给 narrative-writer（句长 / 标点 / 潜台词 / 情绪交替），对标 / 拆文 `style_profile_path` 降级为参考（原文锚点 + 句长分布数值兜底）。空 / 仅空白 / 仅标题 / 占位 stub（待办 / 待补充 / ___）视为不存在。仅接管风格，**不豁免情绪 / 节奏轴**。
     - 若 `gaps.no_benchmark: true` → `custom_style` 为真则进入「自定义文风模式」（用 `设定/文风.md` 写作；无对标可召回，情绪 / 节奏目标改从本书细纲「目标情绪」、卷纲、`设定/题材定位.md` 等内部材料取，`selected_emotion_module` / `rhythm_reference` 记为「无」，不声称从对标召回）；否则跳过文风召回，在「意图确认」标记"无对标参考"
     - 若 `gaps.missing_primary_contract: true` → 停止本章准备，按 `repair_action` 提示重跑 `/story-long-analyze` Stage 3+ 或重新 `/story-import`；不得进入 narrative-writer（情绪 / 节奏轴独立于文风轴，**自定义文风模式不豁免此停止**——补 `剧情/情绪模块.md` / `剧情/节奏.md`，而非写 `设定/文风.md`）
     - 若 `gaps.conflict` 或 `gaps.module_rhythm_conflict: true` → 意图确认必须说明冲突并按 `剧情/情绪模块.md` / `剧情/节奏.md` 的权威优先级执行；不得让 `文风.md` 覆盖情绪/节奏目标
     - 若 `gaps.profile_missing: true` → `custom_style` 为真则进入自定义文风模式继续；否则按上文 fail-fast 流程停止
     - 若 `gaps.profile_degenerate: true`（对标文风不可用） → `custom_style` 为真则用 `设定/文风.md` 写作；否则跳过文风、回到默认 Gates 写作
     - 若 `gaps.tone_match_failed: true` → 仅用整书文风写作，不喂 matched_chapter
     - A 原样传 `style_profile_path`、`style_profile_summary`、`selected_emotion_module`、`rhythm_reference`、`module_source_path`、`rhythm_source_path`、`matched_chapter_K`、`matched_chapter_techniques`、`anchor_excerpts` 和 `genre_prose_card` 给 Step 2 末尾的 narrative-writer prompt。B 只传 `selected_emotion_module`、`rhythm_reference`、`genre_prose_card`、`compiled_method_packet`，以及实质性的 `设定/文风.md` 和 fresh 声音画像；不得把整份编译方法、来源名、证据定位或语料原文塞进 prompt。两条分支中情绪、节奏、题材和声音画像的优先级不变。项目存在 `追踪/文风/accepted-voice-profile.json` 时先运行 `voice_profile.py verify`；仅在 `fresh` 时传本章相关的早期/近期范围摘要，作为本书声音 advisory，不传全量逐章统计、不覆盖自定义文风或情绪/节奏契约。A 的写前准备记录继续保留 `gaps` 原值，尤其 `gaps.module_missing`、`gaps.rhythm_missing`、`gaps.conflict`、`gaps.matched_deep_dive_missing`
     - **无 story-explorer 时直接执行**：主会话手动按对标书路径查找，先读 `剧情/情绪模块.md` 选 `selected_emotion_module`，再读 `剧情/节奏.md` 选 `rhythm_reference`，读 `设定/题材正文提示卡.md` 或按 `genre-prose-cards.md` 索引 + 单题材卡优先即时生成 `genre_prose_card`，并直接读 `设定/文风.md` 判定 `custom_style`。A 再读对标 `文风.md` + grep `章节/*_摘要.md` 的「基调」字段找匹配章，然后读对应 `第K章_摘要.md`；如 `第K章_深度拆解.md` 不存在，改读 `第1-3章_深度拆解.md` 中与本章基调最接近的一章。B 只使用已 resolve 的 `compiled_method_packet`，不读对标文风、匹配章或原文锚点。模块或节奏文件缺失时设置 `missing_primary_contract` 并停止修复
   - **意图确认**：从细纲「目标情绪」确认本章情绪目标，综合状态筛选 + `selected_emotion_module` + `rhythm_reference` + `genre_prose_card` + 文风召回，用一句话写本章意图（情绪+节奏+模块+题材取舍+文风指令）。意图写成“**情绪前状态 → 触发 → 后状态**”，不能只写情绪标签，并指明推进单元情绪引擎的哪一环；同时消费主角代理权、当前单元的主角目标/关键选择、主推线/战果与终局底牌边界。仅当新承载对象、关键转折或高潮进入时才跑 emotional-methods.md 的「合理性五问」，不要每段填表。
     - **细纲字段只定“发生什么”，不定正文形状**：阶段位置/禁止提前释放定边界，结构公式定骨架，内容概括定起承转合，情节安排定多线取舍，人物关系与出场顺序定镜头顺序，情节细化定行动成本/收益归属，本章兑现与状态变化定留存结果，结尾设定/章尾余势与钩子定承接。情节点可自由合并、穿插、重排，演成场景；不逐条各扩一段，不把“谁做了什么”的概括语原样搬进叙述（见 writing-craft.md「从细纲到正文」）。
     - **两条写进意图**：① 爽点出手前先铺可指认的危机/期待（plot-emotion-system 倒推法，不铺=空洞）；② 装逼/打脸/揭露章把视角/信息差经出场顺序放大成在场配角的差异化反应（plot-core-methods 信息差×人际×情绪）。对话声线与细纲边界属正文层，由 narrative-writer 执行，本步不重复。
     - **期待所有权**：按因果权 + 结算权与「关键节点四问」确认。配角可执行局部动作，不要求主角亲自动手，但不得无声夺走已承诺的高光/收益；被配角、机构或偶然性捕获且无可见交换时标记 `protagonist_agency_risk`，先修细纲/卷纲再进正文。
     - 例：「快节奏打脸——起因=账单暴露，逻辑线=发现→逼问→反证→公开代价；复现 M03‘信息差反杀’的读者期待，按都市世情题材卡落到账单/转账/旁人反应，关键信息先压后爆，爆发后用一段冷却承接下一钩子；标点照文风里的停顿节奏、对话潜台词用问非所答；剧情边界=不得新增账单之外的新敌人或提前解决下一章钩子。」
   - 写章节候选 → **字数验证（优先 Python 字符统计，`wc -m` 仅作 Unix 备选，< 目标90%则对照情节点字数预算定位欠账密点、一次性重写到配额，不挤牙膏反复回炉；只能扩写细纲内已有情节点，若现有细纲不足以达标则停止并输出 `outline_underfilled` 欠账点；> 章目标×1.1 则压过场/合并疏点收敛；90% 是放行下限非目标，理想落在 [章目标, 章目标×1.1]）** → 检查钩子/爽点 → **正文元信息扫描** → 禁用词扫描 → `chapter_candidate.py check`（含写作方法绑定、中文、AI 模式、退化三道硬门和本书声音 advisory）
     - **正文元信息扫描**：标题行以外不得出现 `第[一二三四五六七八九十百千万两0-9]+章|上一章|上章|前一章|本章|这一章|前文|后文|伏笔|细纲|读者|ch\d+ 等英文章号缩写`。这些词属于写作/工程元信息，必须改成角色当下能感知的事件锚点或相对时间；例如“比第一章那三秒开火更疼”改成“比那三秒开火更疼”。只有角色在故事世界内真实阅读/讨论“第X章”文本，或真实身为作者/读者并谈论读者身份时例外。
     - **中文语言锁**：正文叙述、对话、心理和场景都默认用中文，不得突然写出英文句/段、句首大写英文词或未命名的裸英文词。外国人对话默认翻成中文并在场内标明语种。缩写、型号和剧情代号不得自动豁免；URL、邮箱、文件名和代码只机械保护明确非叙事结构；其他外语只在用户单独确认后写入 `.deslop-whitelist`；HTML 标记不得进入正文。
   - **接纳边界**：`review` 模式报告候选标题、字数、关键变化、Gate 结果和运行目录后停止；不得先写正式正文或构造已发生事实。用户明确接纳后恢复此工作区。`auto` 模式使用 manifest 中的本次授权说明继续。
   - 候选获准后执行 `approve --confirm ACCEPT` 与 `promote --confirm PROMOTE`，然后**立即提交一次追踪事务**：
     1. 从刚落盘的正文、细纲和上一版续写状态卡提取 `result / character_changes / foreshadow_changes / timeline_events / fact_changes / constraints / next_chapter_commitments`。只记录会影响未来章节的变化；身世/血缘/亲属/婚姻/传承/物权/权限/不可逆规则有新证据时必须更新稳定事实 ID；过程日志、质检计数、参照章和去 AI 味统计全部排除。
     2. 需要长期复用的核心角色，把完整动态快照放进 `character_snapshots`，并在 `character_changes` 写对应变化；一次性路人只写变化、不交快照。已有动态快照的核心角色再次变化时必须提交新快照。静态人设继续以 `设定/角色/{名}.md` 为准。
     3. `context.long_term_constraints`、当前卷/故事时间/场景、活跃核心角色名、连贯性风险提交当前完整值；活跃伏笔、近三章速记和下一章承诺由工具从当前视图/本章增量派生，不重复手填。
     4. 把最近一次 `tracking_commit.py check` 返回的 `state_revision` 写入事务 `expected_state_revision`，再把 JSON 写到临时文件并执行 `tracking_commit.py commit`。成功并复检后删除临时 JSON；脚本返回新的 `state_revision` 才能进入下一章。
     5. 成功并通过 `tracking_commit.py check` 后依次运行 `chapter_candidate.py close`、`voice_profile.py update --project`（未配置画像时安全跳过）和 `story_doctor.py --project`。画像已配置而未更新时 doctor 会判 `voice-profile-stale`。任一失败时保留候选、提交凭证和临时事务，修复后从失败点恢复；不得另写下一章、不得手工补派生视图、不得忽略返回码。

     `追踪/逐章记录/第NNN章.md` 由工具按 6 类变化生成，目标 ≤1536 字节、硬上限 3072 字节。它不是正文摘要大全，更不保存写作过程。`伏笔.md` 每个 ID 只有一行当前状态；角色状态按核心角色拆文件；长期事实按稳定 ID 生成事实表、关系清单和实体档案；时间线的客观事实和读者认知只在同一事件登记中维护，再派生作者/读者两个视图。

     状态更新仍由主会话负责。narrative-writer 只写正文并回报必要的写作结果，不直接写 `追踪/`；主会话也不绕过事务工具直接修改最终追踪文件。
   - **质检提示**（可选）：本章写作完成。如需一致性检查，运行 `/story-review lean`。批量写作模式跳过此步骤，全部写完后再统一审查。
3. **不并发且不越权**：`review` 模式一章候选写完即停在接纳边界；`auto` 模式才在本章提交凭证闭环且 doctor 通过后直接写下一章。下一章必须读取上一章已接纳正文和更新后的追踪，不能读取未接纳候选冒充正史。

**资料研究（按需）**：如果写作中遇到需要查证的外部事实（历史年代、地理方位、职业细节等），暂停写作，spawn `story-researcher` agent 搜索并输出到 `参考资料/` 目录。研究完成后再继续写作。

### 旧信息查找步骤

状态摘要里没有、但本章确实需要的旧信息（20 章前埋的伏笔、久别角色的当前状态、某个时间锚点），按以下顺序查找，**每一步的读取量都有上限**。不允许因为"查着方便"退化成读历史记录文件全文。

| 级别 | 手段 | 成本 |
|------|------|------|
| 1 | 续写状态卡已有 → 直接用 | 0 |
| 2 | 伏笔 ID 查 `grep -n "F007" 追踪/伏笔.md`；硬事实 ID 查 `grep -n "R001\|K001" 追踪/长期事实.md`，身世/关系查 `追踪/事实档案/{实体}.md` 与 `关系清单.md`；角色当前态查 `追踪/角色状态/{名}.md`；读者认知查 `时间线/读者已知.md`，作者真相查 `时间线/作者真相.md` | 一个当前行或一个有界小文件 |
| 3 | 需要变化原因/历史时，调用 story-explorer 的 `foreshadow_status / character_status / timeline`；各 adapter 按自身 agent 调用方式，agent 不可用就直接 Grep/Read | 子代理/主会话只返回相关条目 |
| 4 | explorer 不可用 → `grep -R -n --include='第*.md' "F007" 追踪/逐章记录/ 2>/dev/null \| tail -5`，只取最近 5 条匹配增量 | 只读取匹配行 |
| 5 | 仍不够 → `Read` 对应增量或埋设章正文 | 1 个紧凑增量或单章正文 |
| 6 | 全量读取所有逐章增量/正文 | **日更禁止**。只在 `/story-review` 或用户明确要求全面审计时 |

**查询次数限制**：单章执行步骤 3 和步骤 4 合计超过 3 次，说明细纲没写清本章要消费哪些旧信息。这时一次性让 story-explorer 查询多项，并在批末口头提示细纲需补清回收项，不另写过程日志。

查询结果只有在本章结束后仍影响后续时才进入追踪事务；当前伏笔由 `foreshadow_changes` 更新，核心角色由快照更新，时序/认知由 `timeline_events` 更新，身世/关系/规则/物权/权限等稳定断言由 `fact_changes` 更新。不要直接改任何追踪派生视图的某一行。

---

## Step 3：质量检查

批量写作结束后，对本次所有新写章节执行 Phase 5 质量检查（至少包含）：

**第一关先行**：运行 `node scripts/language_gate.js 正文/第XXX章_*.md`。返回零后紧接着运行 `node scripts/check-style-hygiene.js --check --fail-on=blocking 正文/第XXX章_*.md`；任一 blocking 清零前不得进入下列质检，修文后从语言门重新复扫。

1. **禁用词扫描**：对照 `references/banned-words.md`，一级词命中即替换
2. **标题去重检查**：汇总本轮新写章节与既有标题；发现同名或明显重复时，回到对应细纲和正文文件统一重命名
3. **元信息与中文语言锁扫描**：检查标题行以外是否混入 `第[一二三四五六七八九十百千万两0-9]+章|上一章|上章|前一章|本章|这一章|前文|后文|伏笔|细纲|读者` 这类写作工程词，以及无明确设定根据的英文句/段和裸英文词。工程词命中即改成场景内表达；英文泄漏改成中文。URL、邮箱、文件名和代码只机械保护明确非叙事结构；其他外语只有经用户单独确认并由 `.deslop-whitelist` 精确登记时才保留；HTML 标记必须清零。故事内真实阅读/讨论“第X章”或真实读者身份语境除外。
4. **钩子检查**：每章章尾是否有往下看的理由（低压/过场章弱钩子或阶段目标即可，不强求强钩子，按细纲章节定位；见 references/outline-structure-theory.md「章节定位与张弛」）；如新版细纲有「结尾设定和钩子」，检查结尾是否落在具体动作/画面/悬念上（"收束状态"是规划口径，不是要写进正文的状态总结句）、留下未解决问题和下一章推动力。先跑 `node scripts/check-hook-strength.js --check 正文/第XXX章_*.md` 过下限：黄金三章弱钩是 blocking，必须补强再走；正文章的 `ending-no-hook` 是 advisory 待查清单（钩子是语义判断，词表识别不了「没有风了，井绳却晃了一下」这类反常现象钩），逐条人工确认真没钩再补。脚本只查下限存在性，悬念到底几级仍按 `hooks-suspense.md` 三档判
5. **契约与细纲双向核对**：先按 `reader-contract-and-progression.md` 检查读者契约、因果权 + 结算权、关键节点四问、期待所有权、期待债偿还、终局储备（透支两问）；章级推进按权威文件七类状态分档（快节奏保留可见事件/爽点下限），相对本书题材与对标判断；高潮后允许短暂低压和小而可见的收益/奖励。新地图/机构/能力/敌人/谜团须检查换书债；履约爽文/能力幻想另查主角是否反复以可避免的无能制造灾难再由他人收拾。再对照细纲核对正文有没有按细纲写到。新版细纲存在时，核对正文是否消费了内容概括五段式、情节安排多线、人物关系变化/出场顺序、行动成本（可无）/收益归属；并加三条写作要求 兑现核对（不达标→修复）：① 爽点出手前是否有可指认的危机/期待铺垫段落？指不出=空洞 → 回 Step 2 补铺垫情节点（plot-emotion-system 倒推法）；② 装逼/打脸/揭露章是否写出在场配角差异化反应（集体震惊/各异），还是只写主角动作？没有 → 补在场配角反应（plot-core-methods）；③ 详略是否按目的词（爽点/卖点点展开、过渡点带过、信息密度交替），还是均匀注水？均匀 → 删过渡、扩爽点点。旧版细纲只核对核心事件、目标情绪、章首/章尾钩子和字数目标
6. **伏笔盘点（仅本轮增量）**：确认本批新增/推进/回收的每个 ID 在 `追踪/伏笔.md` 恰好有一行当前状态，并能在对应 `逐章记录/第NNN章.md` 找到本次变化；不得追加第二行历史，也不得在日更流程扫描全部正文做全量伏笔审计
7. **错别字校验（独立语言门通过后，先于其他风格脚本）**：主会话运行 `node scripts/check-typos.js --check --fail-on=all 正文/第XXX章_*.md`。这一步跟风格/AI味是不同维度。所有命中都是 advisory，脚本从不自动改写；先判断是不是项目里有意为之的风格化用词，确认是真错字才改。
8. **情绪落地下限**：主会话运行 `node scripts/check-emotion-floor.js --check 正文/第XXX章_*.md`（高压章加 `--pressure=high`，过场章加 `--pressure=low`）。查的是「必须有却缺席的东西」——正文的体温。blocking 回到本章压力最高处补落点再复扫；advisory 按 `emotion-landing.md` 转译表补，不要堆精致反应刷密度。
9. **确定性收尾**：情绪下限过后，主会话对本批实际落盘正文重跑 `node scripts/language_gate.js 正文/第XXX章_*.md`；返回零后先运行 `node scripts/check-style-hygiene.js --check --fail-on=blocking 正文/第XXX章_*.md`，再运行 `node scripts/check-ai-patterns.js --check --fail-on=blocking 正文/第XXX章_*.md`；blocking 先改正文并复扫，advisory 只作读感提示，功能性写法标 `[需复核]`。脚本会同时输出一条 info 级别的 `dialogue-density-stat`（对话独立段占比，对标参考 40-55%），拿这个数字对照对标基线判断本批节奏，不必再手写脚本现算。
   再运行 `node scripts/normalize-punctuation.js 正文/第XXX章_*.md` 做确定性格式收尾；默认保留停顿标点与引号风格，只清理 Markdown 分隔线等格式问题。只有项目/平台明确禁用时才加 `--pause-mode normalize`。narrative-writer agent 不运行这些脚本。
   - **退化/英文泄漏防护**：再跑 `node scripts/check-degeneration.js --check --language=zh --fail-on=blocking 正文/第XXX章_*.md`。blocking（含英文句段、裸英文词、复读、截断、拒绝语和 tier1 工程词）只重写受影响句/段，最多 2 次；仍失败就报告证据让用户定夺。语言类 advisory 也必须逐条确认，只有用户单独确认并精确登记的外语才保留；去味跳过不豁免语言门。
10. **一致性检查（硬性必须，不可跳过）**：spawn consistency-checker agent（不可用则主线程按 quality-checklist.md 手动执行），检查范围至少含本批新写章节。执行完成前不得进入 Step 4。
11. **去AI味独立审查（硬性必须，不可跳过）**：spawn narrative-writer agent 执行独立于写作过程的去AI味审查（不可用则主线程直接执行，同等深度，不得省略）。这是与写作时的自检分开的一次专门通读，不能用"写的时候已经注意过了"替代。
12. **更新质检进度表**：项目已部署 `追踪/质检进度.md`（story-setup 2.5）时，把本批章节对应行的每一列（错别字校验/脚本三项/元信息扫描/一致性检查/去AI味审查/字数核实/对话密度实测）打勾更新。这张表是防止第 9、10 两步被静默跳过的唯一机械可查记录，跳过任何一步就据实标 `—`，不能靠事后回忆补勾。

> 完整检查清单见 [Phase 5：质量检查](../SKILL.md#phase-5质量检查)。第 10、11 两步是本节唯一容易被省略的部分——历史上曾因软性措辞（"如果部署了可以 spawn"）被连续多章跳过，现已改为硬性必须，此处不再留"可选"表述。
> 若本步发现必须回滚或修改已提交正文、既有总纲/卷纲/细纲/设定，立即暂停日更，不得一边写新章一边顺手回改。先调用 `revision-governor phase=plan`，转入 `workflow-revision.md` 建立 `追踪/修改影响/active.json`；完成所有关联修订和追踪事务后，再调用 `revision-governor phase=verify`，通过带审批戳的 `revision_guard.py check` 与 `tracking_commit.py check`。三关都通过后重新读取最新 `追踪/上下文.md`，才能恢复当前日更批次。其中 `delta` 要重算修订后该章仍成立的完整当前记录，不能只传本次改动；纯措辞调整不重复提交，但修改旧源文件仍须走修改计划和闭环复核。

---

## Step 4：批末收尾

**本步不再写任何追踪内容**——每章 Step 2 已完成事务。只做两项验证：

1. 对项目运行 `story_doctor.py --project`；它包含 `tracking_commit.py check` 与写作方法分支检查，并验证 state/派生视图、章节提交凭证、正文摘要、悬空候选、已配置声音画像的来源摘要和修订门禁。
2. 确认本批每章都有对应 `追踪/逐章记录/第NNN章.md`，每个文件 ≤3072 字节。缺失或超限时不手工补文件，回到该章事务修正并重跑 `commit`。

然后判断任务总目标：

- **`review` 候选已生成但未接纳**：向用户汇报候选摘要和接纳/修改入口，不把它计为已完成章节。
- **`auto` 的 T 已完成**：向用户汇报已接纳提交的章数、字数、漂移和 doctor 结果。
- **`auto` 的 T 未完成且无阻塞**：只发简短中间进度，自动回到 Step 1/2 读取最新追踪和下一微批次细纲，继续串行写作。
- **T 未完成但出现真实阻塞或用户中断**：停止新增正文，报告已完成章数/字数、剩余目标、阻塞证据和恢复入口；已通过的章节与追踪提交保留。

> **卷末门禁**：本章是卷尾或下一步将开启新卷时，读取 [顺序冷读协议](sequential-cold-read.md)，对本卷范围从前往后建立滚动账本。`cold_read_ledger.py close` 与 `story_doctor.py --require-cold-read-through` 未通过前，不进入下一卷正文。

---

> **漂移处理**：aligned = 按计划推进；adaptive = 细节适配但不改契约；structural 漂移 / 结构性漂移 = 正文已经改变卷契约、单元承诺、推进线或兑现归属，必须修正文或重规划未来章节细纲，不能只在增量里备注。下一章必须修的漂移进入 `next_chapter_commitments`，跨章风险进入 `continuity_risks`；两者都受续写状态卡上限约束，完整语义以紧凑增量和大纲为准。

## 细纲缺失补建流程

当检测到细纲不存在时，不能跳过。按以下步骤补建：

1. 加载 `大纲/卷纲_第{N}卷.md`（本章对应的事件规划），读取本章所属剧情单元卡；剧情单元卡含「对标剧情参照」时加读其指向的剧情单元文件（1 个），以其「结构分布」对应位置作本章功能参照；若本章起整个剧情单元均无细纲，按 outline-structure-theory.md「按剧情批出细纲」整批补建而非单章补。卷纲缺必需字段时先补齐，不绕过当前模板继续
2. 加载本章涉及的 `设定/角色/{角色名}.md`（角色状态）
3. 读取最新一章正文（情节衔接）
4. 按 SKILL.md Phase 3 的新版细纲模板补建本章细纲，补齐阶段位置、本章结构公式、本章禁止提前释放、内容概括、情节安排、人物关系/出场顺序、情节细化、结尾设定；无法从卷纲/正文/设定确认的字段写 `[待补充]`，不杜撰
5. 补建完成后继续 Step 2 写作

---

## 常见问题

| 问题 | 处理 |
|------|------|
| 细纲不存在 | 执行上方"细纲缺失补建流程" |
| 细纲缺当前蓝图字段 | 先按当前模板补齐，未知项写 `[待补充]`；未补齐前不写正文 |
| 追踪文件为空 | 正常继续，写作中逐步填充 |
| 用户要求改大纲 | 提醒"改大纲会影响后续细纲"，确认后修改，标记受影响的细纲 |
| 写到卷末 | 提示用户"当前卷已完成，是否开新卷？" |
| 用户中断批量写作 | 保存当前章节，已更新追踪文件，下次从断点继续 |
