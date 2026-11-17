# stroy — 网文写作项目

本项目按通用文件方式接入 oh-story skills。

- **通用端**:`skills/*/SKILL.md` 与 `skills/*/references/` 可被任意 Agent 直接读取执行;无 hooks 时运行时硬拦截与多 agent 自动协作不生效,按软约束或 solo/direct 降级执行。

## P0 级强制执行铁律：《他们不是人》长文写作 Skills 闭环（最高优先级）

任何涉及《他们不是人》**规划、大纲、细纲、设定修改、正文写作、续写或回炉改稿**的任务，必须在动手前将以下 `story-long-write` 与 `story-world-engine` 流程作为 **P0 级硬约束** 严格执行，严禁跳过任何一环：

1. **先读后写（P0-1）**：每次任务动笔前，必须读取 `skills/story-long-write/SKILL.md` 的「写前必读」清单及对应阶段流程文件（`workflow-outline.md` / `workflow-chapter.md` / `workflow-daily.md`），同时重读 `他们不是人/设定/都市异能正文风格卡.md` 与 `他们不是人/设定/题材正文提示卡.md`。
2. **先纲后文与契约校验（P0-2）**：写正文前，必须先有对应卷纲的剧情段卡（用 `scripts/outline_view.py --chapter {N} {卷纲}` 校验通过）与合规细纲（必须通过 `node skills/story-long-write/scripts/check-outline-contract.js` 零阻塞）；严禁无纲盲写正文。
3. **写前恢复与组装（P0-3）**：开写单章或日更前，必须先执行 `tracking_commit.py check` 校验账本与派生视图一致，通读 `他们不是人/追踪/上下文.md` 全 7 栏与涉及角色/势力设定，再运行 `build_writer_prompt.py --project 他们不是人 --chapter {N} --out` 完成核对，并完成七关行动审查。
4. **格式与质量同轮清零（P0-4）**：正文严格遵守 `skills/story-long-write/references/long-format.md`（相邻段落单换行 `\n`、无加粗/斜体/分隔线、无工程词泄漏）。正文落盘后同轮内必须运行 `python skills/story-long-write/scripts/storyctl.py chapter check --project 他们不是人 --chapter {N} --fix-punctuation --plain`，保证 AI 句式 0 blocking、退化检测 0、细纲照搬核验通过；字数越界按作者流程处置。
5. **串行提交追踪与设定补登（P0-5）**：每写完一章，必须紧接通过 `tracking_commit.py draft` 填妥事务并用 `storyctl.py chapter commit`（或修订 `mode=revision`）串行提交入账，确保 `追踪/上下文.md`、逐章记录、核心角色快照、伏笔与双时间线即时同步；正文中新出现或升级的重要人物、势力、能力、器物与规则，同轮必须按「新增物三级」补登进 `他们不是人/设定/` 与 `他们不是人/大纲/`。
6. **主笔版权威基准（P0-6）**：《他们不是人》已按主笔重写版全面重构，现行唯一权威为 `他们不是人/大纲/` 与 `他们不是人/设定/` 下的新版文档（旧版全量规则、103 章正细纲与历史记录已统一归档至 `他们不是人/_归档/`，仅供追溯，不再约束新稿写作）。

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

## story-world-engine 使用说明（所有 Agent 必读）

**安装位置**
- 唯一正本：`skills/story-world-engine/`（SKILL.md + `references/` + `assets/` + `scripts/`）。
- 如需其他宿主的自动发现镜像，运行 `pwsh -File skills/sync-story-world-engine.ps1` 生成同步；镜像与正本冲突以正本为准。

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
