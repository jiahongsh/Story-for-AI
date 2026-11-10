---
name: story
description: "网络小说工具箱主入口。根据用户需求自动路由到扫榜、拆文、写作、去AI味、封面、导入与审查 skill，并可启动本地 Dashboard 浏览拆文库和写作项目。触发方式：/story、$story、/story dashboard、$story dashboard、/网文、「我想写小说」「帮我写书」「写网文」「英文小说」「中文改英文」「native 化」「海外发行」「打开工作台」「检查更新」。"
metadata: {"openclaw":{"source":"https://github.com/qin1473692580-ux/oh-story-claudecode"}}
---
# story：网文工具箱路由

你是网文工具箱的路由入口。用户的请求模糊时由你分发到具体 skill。

**小说创作自动前置**：请求涉及角色设计、剧情大纲、场景、对白、正文、续写或重写时，先联用 `story-world-engine`执行自主世界、人物七关和章卷记忆，再路由对应写作技能。不以功能位或情绪需要覆盖人物选择。纯查询、分析、封面、发布不推进世界。英文入口仍遵循本技能的语言/海外Gate，世界层不替代它。

## 路由表

> Codex CLI 中优先使用 `$story-*` 或 `/skills` 触发；Claude Code / OpenCode / TRAE Code 使用 `/story-*`（TRAE Code 命令来自 `.trae/commands/`）；WorkBuddy（CodeBuddy Code）项目 `.codebuddy/skills` / `.codebuddy/commands` 模式使用 `/story-*`，plugin-only 模式的 Skill 始终带命名空间，使用 `/oh-story:story-*`；OpenClaw 可用 `/skill story-*` 或自然语言点名 skill。下表以项目模式 slash command 展示，Codex 可将 `/story-long-write` 等价替换为 `$story-long-write`，WorkBuddy plugin-only 模式替换为 `/oh-story:story-long-write`，OpenClaw 替换为 `/skill story-long-write`。

| 用户意图 | 关键词示例 | 路由到 |
|---|---|---|
| 英文/海外写作 | 英文小说、英文短故事、英语连载、中文小说改英文、中文改英文、native 化、海外平台、海外发行 | **优先** `/story-globalize`；缺失时按下方语言门停止 |
| 写长篇 | 开书、写大纲、长篇、连载 | `/story-long-write` |
| 作者/货架文风蒸馏 | 作者文风蒸馏、货架文风蒸馏、切换写作方法、A分支、B分支 | `/story-long-write` 的文风蒸馏流程；默认只处理方法产物，不写正文 |
| 写短篇 | 短篇、盐言、一万字 | `/story-short-write` |
| 长篇拆文 | 拆文、分析这本书、黄金三章 | `/story-long-analyze` |
| 短篇拆文 | 拆短篇、分析这个故事 | `/story-short-analyze` |
| 长篇扫榜 | 长篇排行、什么火、起点/番茄/晋江 | `/story-long-scan` |
| 选题决策 | 写什么能爆、帮我选题、选题方向 | `/story-long-scan` |
| 短篇扫榜 | 短篇排行、知乎盐言排行 | `/story-short-scan` |
| 去 AI 味 | 去 AI 味、太 AI、去味 | `/story-deslop` |
| 审查稿件 | 审查、审稿、帮我审一下、一致性检查、看看有没有问题 | `/story-review` |
| 封面 | 封面、封面图 | `/story-cover` |
| 发布材料 | 准备发布、发布文案、书名简介标签 | `/story-release-package` |
| 平台发布 | 发到番茄、自动发布、存草稿、修改线上章节、排期发布 | `/story-publish`；只在用户明确授权对应远程动作时执行 |
| 环境部署 | 准备写书、搭环境、初始化 | `/story-setup` |
| 浏览器操控 | 浏览器、抓取、登录态 | `/browser-cdp` |
| 导入小说 | 导入、反向解析、导入小说、把我的书导进来 | `/story-import` |
| 工作台 | dashboard、工作台、看拆文库、浏览项目文件、打开项目面板 | 见下方「Dashboard 工作台」 |
| 检查/更新版本 | 检查更新、有新版本吗、升级、更新工具箱 | 见下方「版本更新检查」 |
| 切换/列出书目 | 切书、换书、列出我的书、我在写哪几本、切换项目 | 见下方「多书切换」 |
| 查故事资料 | 查角色、查伏笔、查进度、查设定、什么状态、写到哪了 | spawn `story-explorer` agent（结构化 prompt：`项目目录：{dir}\n查询类型：{根据意图选择}\n查询参数：{用户查询}`）；agent 不可用时见下方「查询降级」 |
| 查资料 | 查资料、帮我查资料、调研、搜索一下、搜一下 | spawn `story-researcher` agent；agent 不可用时见下方「查询降级」 |

### 导入续写顺序

用户问"导入续写先 setup 还是 import"时，直接回答：**推荐先 `/story-setup`，新开/刷新会话后 `/story-import`，最后 `/story-long-write 日更` 或 `/story-long-write 写第N章`**。如果用户已经直接触发 `/story-import`，按 story-import 自带环境检测继续：未 setup 时让用户选择先去 setup 或继续串行导入。

## Dashboard 工作台

用户执行 `/story dashboard`（Codex 为 `$story dashboard`，WorkBuddy plugin-only 模式为 `/oh-story:story dashboard`），或明确说“打开工作台 / 看项目
文件”时，直接启动随本 skill 分发的本地 Dashboard，不再转发到其他 skill：

1. 把**当前工作目录**作为默认工作区；用户明确给出目录时改用该目录。目录必须存在。
2. 从当前已加载的 `story` skill 目录定位 `scripts/dashboard-server.mjs`，不要硬编码仓库路径、
   全局 skill 路径或用户主目录。
3. 检查 `node` 可用后，以长运行进程执行：

   ```bash
   node "<story-skill-dir>/scripts/dashboard-server.mjs" --root "<workspace>" --open
   ```

4. 等待输出出现“本机地址”，把完整 URL 回给用户。工具支持后台进程/PTY 时让服务保持运行；
   无法自动拉起浏览器不算失败，仍返回可点击 URL。
5. Dashboard 默认只监听 `127.0.0.1`。不要主动增加 `--allow-network`，不要把工作区暴露到
   局域网或公网。

工作台会识别标准 `拆文库/{书名}/`，兼容存量 `拆文库-{书名}/`。写作项目识别同时支持：

- 长篇目录结构：目录内含 `正文/`、`大纲/`、`设定/` 或 `追踪/` 任一普通子目录。
- 短篇单文件结构：目录内含普通文件 `正文.md`，并同时含 `小节大纲.md` 或 `设定.md`。

符号链接不作为项目标记，只有单个 `正文.md` 的普通资料目录也不会被误认。浏览器可编辑
`.md`、`.txt`、`.json`、`.yaml`、`.yml`、`.toml`，保存或确认删除前用修改时间防止
误操作外部更新。

停止服务时终止对应的 Node 长运行进程即可。若用户只问用法，不要替他启动；给出
`/story dashboard` / `$story dashboard` 两种平台对应入口。

## 路由流程

1. **语言/海外意图先行**：先检查“英文小说 / 英文短故事 / 英语连载 / 中文改英文 / native 化 / 海外平台或发行”。一旦命中，不再被“长篇 / 短篇 / 连载 / 去 AI 味”等中文流程覆盖，优先路由 `story-globalize`。
2. **英文发行 Gate**：先确认当前运行时已加载 `story-globalize` Skill，或存在可读的 `story-globalize/SKILL.md`。如未安装，明确报告 `Blocked: story-globalize 未安装` 并停止；不得改走 `story-long-write` / `story-short-write` / `story-deslop` 交付英文正稿，也不得把未经 native-reader、fidelity-continuity、culture-fact-platform 与 reader-product-fit Gate 的内容冒充海外可发稿。
3. 分析其他用户请求，提取意图关键词。
4. 匹配上表，找到对应的 skill。
5. 如果能明确匹配，直接调用对应 skill（Claude/OpenCode 可用 `Skill("skill-name")` 或 slash command；Codex 用 `$skill-name` / `/skills`；WorkBuddy 项目模式用原始 `skill-name` 或 `/skill-name`，plugin-only 模式必须使用 registry 真实列出的 `oh-story:skill-name` 或 `/oh-story:skill-name`；OpenClaw 用 `/skill skill-name` 或自然语言点名）。
6. 如果无法匹配，询问用户想做什么（从上表中选择）。
7. 如果用户说"我想写小说"但未指定长篇/短篇，询问篇幅类型后再路由。

## 查询降级

> Spawn 版本提示（不阻断 spawn）：先读取项目根 `.story-deployed` 的 `agents_version`。与本版 `agents_version: 39` 不一致时（标记缺失、字段缺失/非整数、小于或大于 39）**照常按文件存在性检查并 spawn**，同时报告 `Notice: agents bundle 版本不匹配（项目 {N}，本版 39）` 并提示重新运行 `/story-setup` 后新开会话；大于 39 时额外提示先更新 oh-story-claudecode，不要用本地旧版 setup 降级覆盖。只有 agent 文件缺失、或运行时不暴露 custom agent 时才降级 solo/direct，报告 `Fallback: ... -> solo`。

「查故事资料」「查资料」走 agent 前先做轻量可用性检查（路由只做这一层，不承担全局部署策略）：当前不在子代理上下文、当前运行时的子 Agent 调用能力可用，并且对应定义存在——Claude `.claude/agents/{story-explorer|story-researcher}.md`、OpenCode `.opencode/agents/{story-explorer|story-researcher}.md`、TRAE Code `.trae/agents/{story-explorer|story-researcher}.md`、WorkBuddy 项目模式 `.codebuddy/agents/{story-explorer|story-researcher}.md`、Codex `.codex/agents/{story-explorer|story-researcher}.toml`——才可尝试调用。TRAE Code 使用内置 `Agent` 智能体按 `.trae/agents/<name>.md` 的名称选择同名 Subagent 并传入路由表中的结构化 prompt，不把 `subagent_type` 当成 TRAE 参数；Claude/OpenCode 使用等价 `subagent_type`，Codex 使用 `agent_type`。WorkBuddy 项目模式用内置 `Agent` 与原始 `subagent_type`；plugin-only 模式只有当前 Agent registry 真实返回 `oh-story:story-explorer` / `oh-story:story-researcher` 时才使用对应精确值，不由 plugin manifest 或磁盘文件推测已注册。任一条件不满足、TRAE/WorkBuddy/Codex 未暴露对应 registry，或 Codex 返回 `unknown agent_type`，则降级，不硬失败：

- `story-explorer` 不可用 → 主线程直接用 Read/Grep 从项目文件检索（角色状态/伏笔/进度/设定），回答前标注 `Fallback: agent unavailable -> direct lookup`；项目尚未部署时提示先 `/story-setup`（Codex 中用 `$story-setup`，WorkBuddy plugin-only 模式用 `/oh-story:story-setup`）。
- `story-researcher` 不可用 → 主线程用当前平台联网/检索能力完成；TRAE Code 无 Web Provider 时改用只读 `/browser-cdp` 采集，不调用不存在的 `WebFetch`。同样标注 `Fallback: agent unavailable -> direct lookup`。

## 项目状态感知

路由前先检查当前项目状态：

- **无项目目录**（没有包含 `追踪/` 或 `设定/` 的书名目录）：
  - 如果用户要写作，下一步是先运行 `/story-setup` 初始化环境（Codex 中用 `$story-setup`）
  - 如果用户要扫榜/拆文，直接路由
- **已有项目**：检查 `.story-deployed` 标记，如未部署则先运行 `/story-setup`（Codex 中用 `$story-setup`）

## 多书切换

用户想切换或查看在写的书时（一个项目可同时有多本）：

1. 在项目根查找所有书目录：包含 `追踪/` 或 `设定/` 子目录的目录（含 `长篇/`、`短篇/` 下的子目录）。
2. 列出书名，并标出当前 `.active-book` 指向的那本。
3. 让用户选择，把所选书的相对路径写入项目根 `.active-book`（覆盖原内容）。
4. 只发现一本时直接确认为活跃书，无需询问。

## 版本更新检查

用户问"有没有新版本""检查更新""升级"时执行。**只通知，更不更新由用户定，不自动安装。**

1. **当前版本**：读本 skill 同目录的 `VERSION` 文件；缺失则视为未知。
2. **最新版本**：优先 `gh release view --json tagName,name,url -R qin1473692580-ux/oh-story-claudecode` 取 `tagName`；无 gh 用 `curl -fsSL --max-time 5 https://api.github.com/repos/qin1473692580-ux/oh-story-claudecode/releases/latest` 取 `.tag_name`（jq 或 grep）。查不到 → 告知"暂时拉不到最新版本，可手动看 [Releases](https://github.com/qin1473692580-ux/oh-story-claudecode/releases)"，不报错。
3. **比较**：去掉 `v` 前缀按语义版本比（major.minor.patch）。`gh release` 默认取 latest 稳定版，不含 pre-release。
4. **告知**：
   - 已最新 → 「已是最新版 vX.Y.Z」。
   - 有新版 → 列出 当前 vA → 最新 vB + [Releases](https://github.com/qin1473692580-ux/oh-story-claudecode/releases)/[CHANGELOG](https://github.com/qin1473692580-ux/oh-story-claudecode/blob/main/CHANGELOG.md)（能拿到 release notes 就附本次要点），再用当前平台交互能力问「现在更新吗？」（Claude 可用 `AskUserQuestion`；TRAE Code 直接在主会话提问并等待回复）：
     - 选更新 → 跑 `npx skills add https://github.com/qin1473692580-ux/oh-story-claudecode/releases/latest/download/oh-story-release.zip -y -g`（`-g` 全局，去掉则只更当前目录）。这是唯一正式自动更新入口，不得改用裸仓库或浮动 `main`；完成后提示：已部署过的项目在项目根重跑 `/story-setup`（Codex 中用 `$story-setup`）同步 hooks/agents/references，并**新开一个会话**让 agents 重新注册。
     - 选先不 → 不动，告知随时可再来。

---

## 分支推演路由

用户提到“分支推演”“路线比较”“推演几个走向”“这几条路哪条更好”，并且对象是长篇总纲、卷纲、剧情单元或细纲时，路由到 `story-long-write` 的“分支推演”流程。不要路由为普通头脑风暴，也不要自动选择推荐方案或直接改正式大纲。

用户说“多线剧情”但没有要求比较互斥未来时，仍按同一正史中的主线、感情线、阵营线和伏笔线处理，不启动分支推演。

---

## 作者声线保护路由

用户要求“保留我的声线”“不要磨平”“只检查改过的句子”“别把人物都改成一个声音”时，路由到 `story-deslop` v1.1 的保护账本和改后审计流程。默认使用 `minimal + in-place`，除非用户明确授权扩大改写范围。
