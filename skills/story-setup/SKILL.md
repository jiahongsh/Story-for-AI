---
name: story-setup
version: 1.2.22
description: "网文写作工具集基础设施部署。为 Claude Code / OpenCode / Codex / ZCode / TRAE Code / WorkBuddy / CodeBuddy Code / OpenClaw / Reasonix 提供内置适配；Web AI / 通用 Agent 可走 skills + AGENTS.md 文件模式。触发方式：/story-setup、$story-setup、「准备写书」「帮我搭一下环境」「配置写作项目」。"
metadata: {"openclaw":{"source":"https://github.com/qin1473692580-ux/oh-story-claudecode"}}
---
# story-setup：网文写作工具集基础设施部署

你是写作基础设施部署器。将网文写作工具集部署到用户项目目录：已适配的 CLI 走专用 hooks/agents/config；NarraFork、Web AI、自定义 Agent 等环境走通用文件模式。

**执行铁律：不覆盖用户已有配置，合并而非替换。**

**交互工具兼容门**：本 Skill 中的 `AskUserQuestion` 表示“必须让用户做选择”，不表示必须存在同名工具。当前运行时未暴露该工具时（包括部分 TRAE Code、WorkBuddy / CodeBuddy Code、Web AI 会话），主 Agent 必须在当前主对话中直接提出同一个简短问题并等待回答；不得因工具缺失跳过确认、伪造已选结果或让子 Agent 代替提问。

---

## Phase 1：检测项目状态

**先自检参考目录**：以正在执行的本 `SKILL.md` 所在目录为准，列出与它同级的 `references/` 下的子目录，核对下面 10 个名字是否都在**且都非空**——`agent-references`、`templates`、`opencode`、`codex`、`zcode`、`trae`、`workbuddy`、`openclaw`、`reasonix`、`generic`；同级 `scripts/merge-claude-settings.py`、`scripts/merge-codex-hooks.py`、`scripts/merge-trae-hooks.py`、`scripts/trae-core-ownership.py`、`scripts/merge-workbuddy-settings.py` 与 `scripts/copy-path-safety.py` 也必须存在（Claude/Codex/TRAE/WorkBuddy hooks 合并、shared-core 归属验证与递归复制安全预检依赖它们）。有缺即 skill 包没装全，**立即停止，不写任何部署文件**，报告里区分「缺目录」和「目录为空」，并给修复指令：「story-setup 参考资料包不完整，缺 {目录名}。按你的安装方式重装 oh-story-claudecode（命令行装的重跑 `npx skills add https://github.com/qin1473692580-ux/oh-story-claudecode/releases/latest/download/oh-story-release.zip -y -g`，marketplace / Plugin Management 装的在面板里重装），再执行 /story-setup。」

> 判据是「有没有 `SKILL.md`」：只看正在执行的 `SKILL.md` 同级的 `references/`。项目内 `.claude/skills/story-setup/`、`.codex/skills/story-setup/` 和 OpenCode 的 `skills/story-setup/` 只有 `references/agent-references/`、不含 `SKILL.md`，不会是执行目录，也不要拿它们核对。ZCode / TRAE Code / WorkBuddy / CodeBuddy Code / OpenClaw / Reasonix / generic 的项目副本是整份 skill 拷贝、自带 `SKILL.md`，10 个子目录本就齐全，照常核对即可。

1. 检查当前目录是否已部署过（存在 `.story-deployed`）
   - `agents_version` 缺失、非整数或小于 `39` → 标记为待更新，继续执行当前部署
   - `agents_version: 39` → 使用 AskUserQuestion 确认是否重新部署；提示里写明重新部署只用**当前本地 skill 包**刷新项目文件，要拿 skill 本身的新版本得先用固定 GitHub Release 资产重跑 `npx skills add https://github.com/qin1473692580-ux/oh-story-claudecode/releases/latest/download/oh-story-release.zip -y -g`，再回来重跑
   - `agents_version` 大于 `39` → 当前 story-setup 比项目部署旧；停止以避免降级覆盖，提示先更新 oh-story-claudecode，不写任何部署文件
   - 同时读 `target_cli` 字段。**已部署项目以 sentinel 里的值为准**：非空时（逗号分隔的多端组合原样保留）跳过下面第 5-14 步的环境探测与选择，直接按这些端重新部署。只有字段缺失或为空，才回落到探测。用户明确要求增删目标端时，用 AskUserQuestion 在现有值基础上改，改完的值写回 sentinel。
2. 检查是否有书名目录（包含 `追踪/` 子目录的目录，或用户自定义结构）
   - 有 → 识别为长篇项目，显示当前项目信息
   - 无 → 识别为新项目或短篇项目
3. 检查 `.claude/settings.local.json` 是否存在
   - 存在 → 读取现有配置，后续合并
   - 不存在 → 后续创建新文件
4. 检查 `.active-book` 文件是否存在
   - 存在 → 显示当前活跃书目
   - 不存在 → 跳过
5. 检查 `opencode.json` 或 `.opencode/` 是否存在
   - 存在 → 识别为 opencode 项目，`target_cli = opencode`
   - 不存在 → 跳过
6. 检查 `.codex/`、`.codex/config.toml`、`.codex/agents/`、`.codex/hooks.json`、`AGENTS.md` 中的 Codex 段
   - 存在 → 识别为 Codex 项目，`target_cli = codex`
   - 不存在 → 跳过
7. 检查 `.zcode/`、`.zcode/config.json`、`zcode.json`、`.zcode/skills/`、`.zcode/commands/`、`AGENTS.md` 中的 ZCode 段
   - 存在 → 识别为 ZCode 项目，`target_cli = zcode`
   - 不存在 → 跳过
8. 检查 `.trae/`、`.trae/hooks.json`、`.trae/skills/`、`.trae/agents/`、`.trae/commands/`、`.trae/rules/`，或 `AGENTS.md` 中的 TRAE 段（标题行含 `网文写作工具集（TRAE Code）`）
   - 存在 → 识别为 TRAE Code 项目，`target_cli = trae`
   - 不存在 → 跳过
9. 检查 `.codebuddy/`、`.codebuddy/settings.json`、`.codebuddy/skills/`、`.codebuddy/agents/`、`.codebuddy/commands/`、`.codebuddy/rules/`，或 `.codebuddy/CODEBUDDY.md` / 根 `CODEBUDDY.md` / 根 `AGENTS.md` 中的 oh-story WorkBuddy 管理段
   - 存在 → 识别为 WorkBuddy / CodeBuddy Code 项目，`target_cli = workbuddy`
   - 不存在 → 跳过
10. 检查 `openclaw.json`、`.openclaw/`，或 `AGENTS.md` 中的 OpenClaw 段（标题行含 `网文写作工具集（OpenClaw）`）
   - 存在 → 识别为 OpenClaw 项目，`target_cli = openclaw`
   - 不存在 → 跳过
11. 检查 `.reasonix/`、`reasonix-plugin.json`、`REASONIX.md`，或 `AGENTS.md` 中的 Reasonix 段（标题行含 `网文写作工具集（Reasonix）`）
   - 存在 → 识别为 Reasonix 项目，`target_cli = reasonix`
   - 不存在 → 跳过
12. 检查 `AGENTS.md` 中的通用段（标题行含 `网文写作工具集（通用 Agent / Web AI）`）
   - 存在 → 识别为通用 Web AI 项目，`target_cli = generic`
   - 不存在 → 跳过

   > 第 8-12 步只认各端**互斥**的标记。`skills/*/SKILL.md` 的 `metadata.openclaw` 不作 OpenClaw 信号：canonical 中文主包 Skill 都带这个字段，而 OpenClaw / Reasonix / generic 三条 skills-only 路径部署出的 `skills/` 长得一样，用它判定会把后两者一律误认成 OpenClaw。`.agents/skills/` 同理由 Codex 与 Reasonix 共用，也不单独作准。TRAE 只认 `.trae/` 或 TRAE 专用标题行；WorkBuddy 只认 `.codebuddy/` 或其 CODEBUDDY 管理段；skills-only 三端真正的分辨点是各自 `AGENTS.md` 模板的标题行。

13. 如 `.claude/` 或 `CLAUDE.md`、OpenCode、Codex、ZCode、TRAE Code、WorkBuddy / CodeBuddy Code、OpenClaw、Reasonix、generic 标记同时存在 → 使用 AskUserQuestion 让用户选择目标环境（选项：Claude Code / OpenCode / Codex / ZCode / TRAE Code / WorkBuddy / CodeBuddy Code / OpenClaw / Reasonix / 通用 Web AI 或其他 Agent / 任意组合）
14. 如九类标记都不存在（全新项目）→ 使用 AskUserQuestion 让用户选择目标环境
   - 用户选择 opencode → `target_cli = opencode`，部署时创建 `opencode.json` 和 `.opencode/`
   - 用户选择 claude-code → 按现有逻辑处理
   - 用户选择 codex → `target_cli = codex`，部署时创建 `.codex/`
   - 用户选择 zcode → `target_cli = zcode`，部署时创建 `.zcode/`、合并根 `AGENTS.md`，不创建项目 custom agents
   - 用户选择 TRAE Code → `target_cli = trae`，部署时创建 `.trae/`并合并根 `AGENTS.md`、`.trae/hooks.json`，部署原生 Skills / Subagents / Commands / Rules / Hooks
   - 用户选择 WorkBuddy / CodeBuddy Code → `target_cli = workbuddy`，部署时创建 `.codebuddy/`，按「WorkBuddy memory 合并策略」选择唯一 memory 文件并合并 `.codebuddy/settings.json`，部署原生 Skills / Agents / Commands / Rules / Hooks
   - 用户选择 openclaw → `target_cli = openclaw`，部署时复制 OpenClaw 兼容 skills 到项目 `skills/`
   - 用户选择 reasonix → `target_cli = reasonix`，部署时复制 skills 到项目 `skills/`、写入 Reasonix 版 `AGENTS.md`，不创建项目 custom agents/hooks
   - 用户选择通用 Web AI / 其他 Agent → `target_cli = generic`，部署通用 `AGENTS.md` 与项目本地 `skills/`；不写平台专属 hooks/agents
   - 用户选择多端 → `target_cli = claude-code,opencode,codex,zcode,trae,workbuddy,openclaw,reasonix,generic` 的子集（仅包含用户选择的端）

## Phase 2：部署基础设施

使用 AskUserQuestion 确认部署位置后，依次执行。

整个 Phase 2 幂等：目录复制、文件写入和下表各合并算法重复执行结果一致。因环境原因（工具不可用、权限被拒、网络失败）中途失败时，直接从头重跑本 Phase，不需要先清理半成品；`create only if absent` 的用户状态文件（见下表 Owner class）不会被二次覆盖。

### Step 1：部署清单（机械可检查）

**递归复制安全预检（先于任何目录 replace/copy）**：先把 Source path 解析为“正在执行的 story-setup skill 包”内的绝对路径，把 Target path 解析为用户项目内绝对路径，再用可用的 `python3/python/py` 运行 `scripts/copy-path-safety.py <source> <target>`。读取它的 JSON 结果：

- `status=safe`：路径互不包含，才允许继续该项复制。
- `status=same`：源、目标经 realpath/samefile 指向同一对象；把该项记录为幂等 no-op，**不得再递归复制**。
- `status=unsafe`：目标位于源内，或源位于目标内；立即停止整个 Phase 2，不执行删除/覆盖，报告 `reason` 与两条 realpath。
- `status=error`：源缺失或路径解析失败；按部署包不完整处理，立即停止。

不得用字符串前缀、未展开的相对路径或“看起来不是同一个目录”代替此预检；symlink/别名必须按 realpath 判定。文件级 replace 可继续按原有原子写入规则；所有递归目录复制都必须逐项过这一关。

**TRAE 归属与备份门（`target_cli` 含 `trae` 时）**：在改动任何已存在的 `.trae/` 文件前，先将本次会改动的原文件按相对路径备份到 `.trae/.oh-story-backups/<UTC时间戳>/`；目录备份本身也要先跑 `copy-path-safety.py`。只允许替换带 `oh-story-managed` 标记的 canonical 中文主包 skill / command / agent / rule / AGENTS 管理块、头注释明确为 oh-story TRAE adapter 的 `story_trae_hook.js`，以及满足下列任一归属证据的 `story_hook_core.js`：含通用标记 `oh-story-managed: shared-hook-core`；用 `scripts/trae-core-ownership.py` 校验后 sha256 命中唯一权威 `references/trae/legacy-managed-sha256.json`；或与已验证的同项目 Claude/OpenCode/ZCode oh-story shared core 字节一致。Skill 目录的归属证据是 `SKILL.md` 的 `metadata.openclaw.source` 指向本仓库，或精确标记 `<!-- oh-story-managed: skill/{name} -->`。同名但无归属证据的用户文件必须保留并报告冲突，不得覆盖。`.trae/hooks.json` 始终用 helper 按稳定 command 身份合并，绝不整文件替换。新创建的产物必须写入对应管理标记，以保证下次可安全升级。

**TRAE 与 Claude Hook 去重门**：TRAE 会兼容读取项目 `.claude/settings*.json`。Claude settings 命令保持跨平台可执行的直接 `bash ...` 形式，不内嵌 POSIX `if`；所有 Claude shell 入口在 `source lib/common.sh` 后由共用库检测 `TRAE_PROJECT_DIR` 并成功、静默退出。在 Claude 中照常执行，在 TRAE 进程中由 `.trae/hooks.json` 独占执行。部署后用两端合成输入验证同一事件只有一套 oh-story 输出，不能把“双份提示看起来一样”当作可接受。

**WorkBuddy 归属与 Hook 互斥门（`target_cli` 含 `workbuddy` 时）**：只替换带 `oh-story-managed` 标记的 canonical 中文主包 skill / command / agent / rule / CODEBUDDY（或 AGENTS）管理块，以及带适配器头注释或通用 shared-core 标记的 hook 文件；Skill 目录使用与 TRAE 相同的仓库 metadata / `<!-- oh-story-managed: skill/{name} -->` 双证据。同名用户文件保留并报告冲突。`.codebuddy/settings.json` 只通过 `merge-workbuddy-settings.py` 合并。若当前 skill 来自已启用的 oh-story CodeBuddy plugin（实际执行路径位于插件安装根，或当前会话 registry / `codebuddy plugin list` 明确显示 `oh-story` 已启用），plugin hooks 会自动加载，此时必须用空模板移除项目内旧的 oh-story-managed hook 注册，不能再合并 `project-hooks.json`；只有 project-local skills 模式才写项目 hooks，防止同一事件双触发。仓库里存在 `.codebuddy-plugin/plugin.json` 或插件曾经安装过都不算“当前已启用”的证据。

**WorkBuddy 命名空间门**：plugin 模式只由 `.codebuddy-plugin/plugin.json` 暴露 Skills、Agents 与 Hooks；不得同时在 manifest 暴露与 Skills 同名的 Commands，否则 `/oh-story:story-*` 会发生组件名竞争。plugin 模式调用 `/oh-story:story`、`/oh-story:story-long-write` 等命名空间化 Skill；运行 `story-setup` 后的项目模式才由 `.codebuddy/commands/` 暴露 `/story`、`/story-long-write` 等裸命令。两种模式必须在安装报告中分开写，不能把裸命令说成 plugin 命令。

| Source path | Target path | Owner class | Merge mode | Validation check |
|-------------|-------------|-------------|------------|------------------|
| `skills/story-setup/references/templates/CLAUDE.md.tmpl` | `CLAUDE.md` | user+managed | marker/section merge | contains story skill routing sections |
| `skills/story-setup/references/templates/hooks/` | `.claude/hooks/` | story-setup managed | recursive replace | `session-*.sh`, `detect-story-gaps.sh`, `validate-story-commit.sh`, `guard-outline-before-prose.sh`, `check-prose-after-write.sh`, `story_hook_core.js`, `story_hook_cli.js`, `lib/common.sh`, `lib/sentinel.sh` exist；`story_hook_core.js` 与 OpenCode/ZCode 副本字节一致 |
| `skills/story-setup/references/templates/rules/*.md` | `.claude/rules/*.md` | story-setup managed | replace | every rule contains `paths` frontmatter |
| `skills/story-setup/references/templates/agents/*.md` | `.claude/agents/*.md` | story-setup managed | replace | 8 agent files exist |
| `skills/story-setup/references/agent-references/*.md` | `.claude/skills/story-setup/references/agent-references/*.md` | story-setup managed | replace | every `story-setup/references/agent-references/*.md` reference resolves |
| `skills/story-setup/references/templates/settings-hooks.json` | `.claude/settings.local.json` | user+managed | replace managed registrations by stable hook identity | hook JSON valid；旧 matcher 注册已迁移、当前模板命令各一份、用户 hook 保留 |
| `skills/story-setup/scripts/merge-claude-settings.py` | 部署时执行，不复制到项目 | story-setup helper | execute | 替换已知 story hook 注册、保留用户 hooks/顶层字段，历史 matcher 迁移与重复执行幂等 |
| `skills/story-setup/references/templates/质检进度.md.tmpl` | `{书名}/追踪/质检进度.md` | user state | create only if absent | never overwrite existing progress table |
| generated sentinel | `.story-deployed` | story-setup managed | replace | contains `agents_version`, `setup_skill_version`, `target_cli`, `resolver_strategy`, `references_dir` |
| `skills/story-setup/references/opencode/AGENTS.md.tmpl` | `AGENTS.md` | user+managed | marker/section merge | contains story skill routing sections | target_cli 含 opencode |
| `skills/story-setup/references/opencode/agents/` | `.opencode/agents/` | story-setup managed | replace | 8 agent files exist（replace 前按「配置 OpenCode Agent 模型」中的「保留已有模型配置」缓存现有 `model:`，避免覆盖用户已配模型） | target_cli 含 opencode |
| `skills/story-setup/references/opencode/plugin.ts` | `.opencode/plugins/story-hooks.ts` | story-setup managed | replace | TypeScript plugin file exists | target_cli 含 opencode |
| `skills/story-setup/references/opencode/story_hook_core.js` | `.opencode/plugins/lib/story_hook_core.js` | story-setup managed | replace | Node syntax valid；与 ZCode 副本字节一致；被 story-hooks.ts import | target_cli 含 opencode |
| `skills/story-setup/references/opencode/commands/` | `.opencode/commands/` | story-setup managed | replace | command 数量与当前 OpenCode 模板清单一致 | target_cli 含 opencode |
| `skills/story-setup/references/opencode/opencode.json.patch` | merge into `opencode.json` | user+managed | merge by plugin/permission key | plugin entry registered | target_cli 含 opencode |
| `skills/story-setup/references/agent-references/` | `skills/story-setup/references/agent-references/` | story-setup managed | replace | every reference resolves | target_cli 含 opencode |
| `skills/story-setup/references/opencode/pre-commit.sh` | `.git/hooks/pre-commit` | user+managed | append or create | file exists and is executable；含 marker 块则替换块内容，不含则检测 exit 0 位置智能插入 | target_cli 含 opencode |
| `skills/story-setup/references/codex/AGENTS.md.tmpl` | `AGENTS.md` | user+managed | marker/section merge | contains Codex story skill routing sections | target_cli 含 codex |
| `skills/story-setup/references/codex/agents/` | `.codex/agents/` | story-setup managed | replace | 8 TOML agent files parse and contain `name`/`description`/`developer_instructions` | target_cli 含 codex |
| `skills/story-setup/references/codex/hooks/hooks.json` | `.codex/hooks.json` | user+managed | replace managed registrations by stable hook identity | hook JSON valid; all stale direct/launcher registrations removed, current 6 registrations present exactly once | target_cli 含 codex |
| `skills/story-setup/references/codex/hooks/{story_codex_hook.py,run-story-hook.sh,run-story-hook.cmd}` | `.codex/hooks/` 同名文件 | story-setup managed | replace | Python/shell/cmd launcher 文件齐全 | target_cli 含 codex |
| `skills/story-setup/scripts/merge-codex-hooks.py` | 部署时执行，不复制到项目 | story-setup helper | execute | 替换已知管理注册、保留用户 hooks 与未知顶层字段，结果幂等 | target_cli 含 codex |
| `skills/story-setup/scripts/copy-path-safety.py` | 每次递归目录复制前执行，不复制到项目 | story-setup helper | execute | same=no-op；祖先/后代嵌套=阻断；仅 safe 可复制 |
| `skills/story-setup/references/agent-references/` | `.codex/skills/story-setup/references/agent-references/` | story-setup managed | replace | every reference resolves | target_cli 含 codex |
| `skills/story-setup/references/zcode/AGENTS.md.tmpl` | `AGENTS.md` | user+managed | marker/section merge | contains ZCode `$story-*` routing and solo fallback | target_cli 含 zcode |
| canonical repository `skills/{browser-cdp,story*}/` | `.zcode/skills/{browser-cdp,story*}/` | story-setup managed for 18 known skill names | replace known skill dirs only | `SKILL.md` 名字集与中文主包 18 Skill 清单一致并满足 ZCode frontmatter 限制 | target_cli 含 zcode |
| `skills/story-setup/references/zcode/commands/` | `.zcode/commands/` | story-setup managed for 18 known command names | replace known command files only | commands have valid names/frontmatter and cover the canonical skill list | target_cli 含 zcode |
| `skills/story-setup/references/zcode/hooks/story_zcode_hook.js` | `.zcode/hooks/story_zcode_hook.js` | story-setup managed | replace | Node syntax valid; hook contract tests pass | target_cli 含 zcode |
| `skills/story-setup/references/zcode/hooks/story_hook_core.js` | `.zcode/hooks/story_hook_core.js` | story-setup managed | replace | Node syntax valid; hook contract tests pass | target_cli 含 zcode |
| `skills/story-setup/references/zcode/config.json.patch` | merge into `.zcode/config.json` | user+managed | merge by event+matcher+process args | JSON valid; 按「ZCode 部署算法」第 4 步 hooks 互斥分支校验——未装 oh-story 插件时 `hooks.enabled=true`、only supported events；已装插件时校验 `.zcode/config.json` 不含（或已移除）这批 oh-story hooks 注册 | target_cli 含 zcode |
| `skills/story-setup/references/trae/AGENTS.md.tmpl` | `AGENTS.md` | user+managed | marker/section merge | contains TRAE Code story routing and fallback contract | target_cli 含 trae |
| canonical repository `skills/{browser-cdp,story*}/` | `.trae/skills/{skill-name}/` | story-setup managed for the fixed 18 source names | backup + replace managed dirs only | 目标 `SKILL.md` 数量/名字与中文主包 18 Skill 清单一致；源目标同一则 no-op | target_cli 含 trae |
| `skills/story-setup/references/trae/commands/` | `.trae/commands/{skill-name}.md` | story-setup managed by `oh-story-managed` marker | backup + replace 18 managed files only | 每个 canonical skill 恰有一个同名 command，frontmatter 含 `name` / `description` | target_cli 含 trae |
| `skills/story-setup/references/trae/agents/` | `.trae/agents/` | story-setup managed by `oh-story-managed` marker | backup + replace 精确通用名册（8 张） | 名字集精确为 `chapter-extractor`, `character-designer`, `consistency-checker`, `narrative-writer`, `revision-governor`, `story-architect`, `story-explorer`, `story-researcher`；TRAE frontmatter 可解析 | target_cli 含 trae |
| repository `skills/story-data-analyze/agents/trae/` | `.trae/agents/` | story-setup managed by `oh-story-managed` marker | backup + replace 精确数据名册（5 张） | 名字集精确为 `story-data-fetcher`, `story-data-method-validator`, `story-data-metrics-analyst`, `story-data-supervisor`, `story-data-text-improvement-planner`；与通用角色无重名 | target_cli 含 trae |
| `skills/story-setup/references/trae/rules/` | `.trae/rules/` | story-setup managed by `oh-story-managed` marker | backup + replace managed files only | rules frontmatter 含 `alwaysApply` / `globs` | target_cli 含 trae |
| `skills/story-setup/references/trae/hooks/{story_trae_hook.js,story_hook_core.js}` | `.trae/hooks/` 同名文件 | runner by adapter header; core by fixed name + packaged hash | backup + replace managed files only | Node syntax valid；shared core 与其他 adapter 副本一致 | target_cli 含 trae |
| `skills/story-setup/references/trae/hooks/hooks.json` | `.trae/hooks.json` | user+managed | replace managed registrations by stable hook command identity | `version: 1`；仅含 TRAE 支持事件；用户 hook/顶层字段保留 | target_cli 含 trae |
| `skills/story-setup/scripts/merge-trae-hooks.py` | 部署时执行，不复制到项目 | story-setup helper | execute | 迁移旧 matcher/command、保留用户配置，重复执行字节幂等 | target_cli 含 trae |
| `skills/story-setup/scripts/trae-core-ownership.py` + `references/trae/legacy-managed-sha256.json` | 部署时执行，不复制到项目 | story-setup ownership helper/registry | classify before replace | marker / legacy SHA 判 managed；unknown/error 保留并报告 | target_cli 含 trae |
| `skills/story-setup/references/workbuddy/CODEBUDDY.md.tmpl` | 既有 `CODEBUDDY.md` / `.codebuddy/CODEBUDDY.md`，或无两者时的 `AGENTS.md` / `.codebuddy/CODEBUDDY.md` | user+managed | 按「WorkBuddy memory 合并策略」只合并 marker block | 无遮蔽已有 AGENTS；条件导入占位已解析；管理块唯一 | target_cli 含 workbuddy |
| canonical repository `skills/{browser-cdp,story*}/` | `.codebuddy/skills/{skill-name}/` | story-setup managed for the fixed 18 source names | replace managed dirs only | `SKILL.md` 名字集与中文主包 18 Skill 清单一致；源目标同一则 no-op | target_cli 含 workbuddy |
| `skills/story-setup/references/workbuddy/commands/` | `.codebuddy/commands/{skill-name}.md` | story-setup managed by `oh-story-managed` marker | replace 18 managed files only | commands 与 canonical skill 一一对应，frontmatter 仅用 CodeBuddy 支持字段 | target_cli 含 workbuddy |
| `skills/story-setup/references/workbuddy/agents/` | `.codebuddy/agents/` | story-setup managed by marker | replace 精确通用名册（8 张） | 名字集精确为 `chapter-extractor`, `character-designer`, `consistency-checker`, `narrative-writer`, `revision-governor`, `story-architect`, `story-explorer`, `story-researcher`；WorkBuddy frontmatter 合法，项目 Agent 名不带 plugin namespace | target_cli 含 workbuddy |
| repository `skills/story-data-analyze/agents/workbuddy/` | `.codebuddy/agents/` | story-setup managed by marker | replace 精确数据物理名册（2 张） | 名字集精确为 `story-data-fetcher`, `story-data-readonly-runner`；4 张逻辑角色卡留在 Skill references | target_cli 含 workbuddy |
| `skills/story-setup/references/workbuddy/rules/` | `.codebuddy/rules/` | story-setup managed by marker | replace managed files only | `alwaysApply` 可解析；用户 rules 保留 | target_cli 含 workbuddy |
| `skills/story-setup/references/workbuddy/hooks/{story_workbuddy_hook.js,story_hook_core.js}` | `.codebuddy/hooks/` 同名文件 | story-setup managed | replace managed files only | Node syntax valid；shared core byte-parity | target_cli 含 workbuddy 且 project-local hook 模式 |
| `skills/story-setup/references/workbuddy/hooks/project-hooks.json` | merge into `.codebuddy/settings.json` | user+managed | merge or remove by plugin mutex | 只有 project-local 模式各注册一次；plugin 模式为零；用户设置与 hooks 保留 | target_cli 含 workbuddy |
| `skills/story-setup/scripts/merge-workbuddy-settings.py` | 部署时执行，不复制到项目 | story-setup helper | execute | 稳定 runner 身份去旧、合并/移除幂等 | target_cli 含 workbuddy |
| `skills/story-setup/references/openclaw/AGENTS.md.tmpl` | `AGENTS.md` | user+managed | marker/section merge | contains OpenClaw story skill routing sections | target_cli 含 openclaw |
| `skills/story-setup/references/generic/AGENTS.md.tmpl` | `AGENTS.md` | user+managed | marker/section merge | contains generic story skill routing sections | target_cli 含 generic |
| `skills/story-setup/references/reasonix/AGENTS.md.tmpl` | `AGENTS.md` | user+managed | marker/section merge | contains Reasonix story skill routing sections and solo/direct fallback | target_cli 含 reasonix |
| canonical repository `skills/{browser-cdp,story*}/` | `skills/{browser-cdp,story*}/` | story-setup managed for 18 known skill names | replace known skill dirs only | `SKILL.md` 名字集与中文主包 18 Skill 清单一致；OpenClaw 分支校验兼容 frontmatter | target_cli 含 openclaw 或 generic 或 reasonix |
| `skills/story-setup/references/agent-references/` | `skills/story-setup/references/agent-references/` | story-setup managed | replace via full skill copy | every reference resolves | target_cli 含 openclaw 或 generic 或 reasonix |

### opencode.json 合并算法

部署 `opencode.json.patch` 时按以下规则合并：

1. 读取现有 `opencode.json`（如存在），解析 JSON
2. 合并 `plugin` 数组：将 `./.opencode/plugins/story-hooks.ts` 加入数组，去重
3. 保留用户已有的其他配置字段（`permission`、`model`、`provider` 等），不覆盖
4. 写入合并后的 `opencode.json`

### Step 2：部署 CLAUDE.md

- 读取 `skills/story-setup/references/templates/CLAUDE.md.tmpl`
- 替换占位符（见下方「模板占位符」段）
- 写入项目根目录 `CLAUDE.md`（如已存在，按「CLAUDE.md 合并策略」处理）

### Step 3：部署 Hooks

- **递归复制完整目录树**：将 `skills/story-setup/references/templates/hooks/` 复制到用户项目 `.claude/hooks/`
- 必须保留子目录 `lib/`，其中：
  - `lib/common.sh` 提供 `project_root`、`discover_active_book`、`discover_all_books`
  - `lib/sentinel.sh` 提供 `.story-deployed` 字段读取
- 只需对 `.claude/hooks/*.sh` 设置执行权限（`chmod +x`）；`lib/*.sh` 由 hook `source`，不要求可执行位

### Step 4：部署 Rules

- 读取 `skills/story-setup/references/templates/rules/` 下所有 `.md` 文件
- 复制到用户项目的 `.claude/rules/` 目录

### Step 5：部署 Agents

- 读取 `skills/story-setup/references/templates/agents/` 下所有 `.md` 文件
- 复制到用户项目的 `.claude/agents/` 目录
- Agent 文件属于 story-setup 管理文件，可安全覆盖；版本升级时按 `UPGRADING.md` 的版本检测结果重新部署
- **`target_cli` 含 opencode 时，覆盖 `.opencode/agents/` 之前先执行下面「配置 OpenCode Agent 模型」的 Step 1 缓存现有 `model:`**。那一步写在本节后面，但必须先跑——照顺序读到哪做到哪会先覆盖再缓存，用户已配的模型就没了。
- **部署后必须新开会话**：agent 只在会话启动时注册；原因与必须输出的报告文案见「验证安装」中的「输出安装报告」。

#### Agent 兼容性处理

- Agent frontmatter 以 Claude Code 为主；OpenCode 的 `.opencode/agents/*.md`、Codex 的 `.codex/agents/*.toml`、TRAE 的 `.trae/agents/*.md` 和 WorkBuddy 的 `.codebuddy/agents/*.md` 均使用对应 adapter 下的预生成产物，不得直接复制别端 frontmatter。TRAE 通用角色的唯一来源是 `references/trae/agents/`，数据分析角色的唯一来源是 `skills/story-data-analyze/agents/trae/`；WorkBuddy 对应来源为 `references/workbuddy/agents/` 与 `skills/story-data-analyze/agents/workbuddy/`。不把 Claude 模型别名或某一端的专有字段机械带入另一端。OpenCode/Codex/WorkBuddy 预生成产物由仓库维护脚本生成；这些脚本不随 story-setup 下发，部署时只复制已提交产物。
- **ZCode 3.3.4 不部署项目 agents**：其自定义子智能体只支持用户级 `~/.zcode/agents/`，plugin manifest 中的 `agents` 当前不执行。不要创建 `.zcode/agents/` 或修改用户 home；相关 Skill 必须直接 solo/direct 并报告 fallback。
- **OpenClaw Phase 1 不部署 agents**：OpenClaw 只部署 skills，agent 协作相关 skill 必须按既有 fallback 规则降级 solo/direct，不要把 Claude/OpenCode agent frontmatter 直接复制成 OpenClaw agent。
- 部署到项目后，agent 内引用的参考资料必须走 `story-setup/references/agent-references/*.md` 这一本 skill 内复制路径；不要跨 skill 引用其他 skill 的 references。各 adapter 只使用当前规范前缀：Claude Code 为 `.claude/skills/`，OpenCode / OpenClaw / Reasonix / generic 为 `skills/`，Codex 为 `.codex/skills/`，ZCode 为 `.zcode/skills/`，TRAE Code 为 `.trae/skills/`，WorkBuddy / CodeBuddy Code 为 `.codebuddy/skills/`；插件模式可用由平台内联的 `${CODEBUDDY_PLUGIN_ROOT}/skills/`。不在运行时遍历历史备选路径。

#### 部署 Agent References

- 将 `skills/story-setup/references/agent-references/` 下所有 `.md` 复制到项目内 `.claude/skills/story-setup/references/agent-references/`
- 校验：凡 agent 或 reference 中出现 `story-setup/references/agent-references/<file>.md`，源包与目标包都必须存在 `<file>.md`

#### 部署 Codex Agents（target_cli 含 codex 时）

- 读取 `skills/story-setup/references/codex/agents/` 下所有 `.toml` 文件，复制到用户项目 `.codex/agents/`
- Agent 文件属于 story-setup 管理文件，可安全覆盖；`references/codex/agents/` 里的 TOML 由仓库根的 `scripts/generate-codex-agents.py` 从 Claude agent 模板确定性生成后提交入库，部署只做复制
- 校验每个 TOML 都能解析，且包含 Codex 必需字段：`name`、`description`、`developer_instructions`
- 只读职责 agent（`chapter-extractor`、`consistency-checker`、`revision-governor`、`story-explorer`）必须保留 `sandbox_mode = "read-only"`
- **部署后必须 trust + 新开 Codex 会话**（报告文案与 fallback 规则见「验证 Codex 部署」）；若运行时返回 `unknown agent_type`，调用方必须降级 solo/direct 并报告 fallback。
- 将 `skills/story-setup/references/agent-references/` 同步复制到 `.codex/skills/story-setup/references/agent-references/`，作为 Codex agent 的项目内参考资料主路径

#### 部署 TRAE Agents（target_cli 含 trae 时）

- 先校验 `references/trae/agents/` 的名字集精确为 `chapter-extractor`, `character-designer`, `consistency-checker`, `narrative-writer`, `revision-governor`, `story-architect`, `story-explorer`, `story-researcher`（8 张通用卡），再校验 canonical `story-data-analyze/agents/trae/` 的名字集精确为 `story-data-fetcher`, `story-data-method-validator`, `story-data-metrics-analyst`, `story-data-supervisor`, `story-data-text-improvement-planner`（5 张数据卡）。两组必须无重名，合并后名册精确为 13 张；任一必需目录缺失、为空、名字集不等、重名或 frontmatter 不可解析时停止 TRAE 分支，不进行半套部署。
- 依次写入 `.trae/agents/`，只新建或替换带 `<!-- oh-story-managed: agent/<agent-name> -->` 标记的同名文件；无标记同名文件保留并报告。不删除用户其他 agents。
- TRAE frontmatter 只用其原生字段：`name`、`description`、逗号字符串形式的 `tools` / `disallowedTools` 以及可选的 TRAE 内置 `model`；禁止自动把 Claude 模型别名写入。
- 部署后提示新开 TRAE 会话并确认 Subagents Beta 功能可用。若当前 TRAE 版本/会话不支持原生 Agent，必须按各 skill 契约降级 `solo/direct`，报告 `Fallback: TRAE subagent unavailable -> solo/direct`；不得声称 full/lean 多 Agent 已生效。

#### 部署 WorkBuddy Agents（target_cli 含 workbuddy 时）

- 先校验 `references/workbuddy/agents/` 的名字集精确为 `chapter-extractor`, `character-designer`, `consistency-checker`, `narrative-writer`, `revision-governor`, `story-architect`, `story-explorer`, `story-researcher`（8 张通用卡）；再校验 `skills/story-data-analyze/agents/workbuddy/` 的物理名字集精确为 `story-data-fetcher`, `story-data-readonly-runner`（2 张数据卡），且四张只读逻辑角色卡完整留在该 Skill 的 WorkBuddy role-card references。全部物理名必须无重复，合并后中文主包物理名册精确为 10 张。
- CodeBuddy 当前会在 `agentic` registry 查询阶段把 **内置 + 项目** Subagent 总数硬截为 20。本节列出的 WorkBuddy 精确 10 张物理卡低于平台上限；部署器不向该名册注入项目扩展卡，不靠排序或截断隐藏容量问题。
- 每个 Markdown 必须有合法 YAML frontmatter，`name` 与文件名一致，`description` 非空，`tools` / `disallowedTools` 为逗号字符串且只使用当前 CodeBuddy 工具名。plugin agent 禁止 `hooks`、`mcpServers`、`permissionMode`；项目 agent 也不依赖这些字段。
- 只新建或替换带 `<!-- oh-story-managed: agent/<name> -->` 标记的 `.codebuddy/agents/<name>.md`；无标记同名文件保留并报告冲突。项目定义优先级高于 plugin/user agent，项目模式统一用裸名称和 `Agent(subagent_type: "<name>")`。
- pooled runner 的逻辑角色卡留在所属 Skill 内，不能复制进 `.codebuddy/agents/`。主协调器必须按该 Skill 的运行时映射选择 runner，并在 prompt 中传入 `logical_role`、角色卡绝对路径、项目根、输入隔离合同和任务正文；runner 必须完整读取且核对角色卡后执行。
- plugin-only 模式的 UI 名为 `oh-story:<name>`；只有当前 registry 确实暴露该名称时才用它。未运行 story-setup 时不得凭磁盘 manifest 猜测 registry 已加载；调用失败立即按 Skill 合同降级。完成项目部署后统一使用 `.codebuddy/agents/` 的裸名称，避免命名空间分歧。
- 部署后新开 WorkBuddy / CodeBuddy 会话，用 `/agents` 或当前 registry 确认本节列出的精确 10 张物理卡全部可见；再分别冒烟一个通用 Agent 和一个 pooled runner 逻辑角色。子 Agent 不得递归 spawn。

#### 配置 OpenCode Agent 模型

> 仅当 `target_cli` 含 `opencode` 时执行。OpenCode 子代理不指定模型时继承主模型，导致低成本 Agent 也消耗主模型额度。此步骤自动检测用户模型并写入 `model:` 字段。

##### Step 1：保留已有模型配置（必须在 `.opencode/agents/` 的 replace 之前执行）

OpenCode agents 部署是 `replace`，会覆盖上次写入的 `model:`。所以在执行该 replace **之前**先扫描现有 `.opencode/agents/*.md`，缓存每个 agent 的 `model:`（agent 名 → 模型 ID）。后续检测失败/超时、或用户跳过某一级时，用缓存值回填，避免把用户上次配好的低成本模型抹成主模型。若 replace 已先发生、缓存为空，则按全新部署处理，并在安装报告中提示"未能保留上次模型配置"。

##### Step 2：获取模型列表

优先执行 `opencode models --verbose`，它输出含 cost（input/output/cache 单价）、context、capabilities 的 metadata；不可用或解析失败时回退到 `opencode models` 纯文本（每行 `provider/model`）。两者都用 60000ms（60 秒）超时，因为首次运行需加载 models.dev 缓存。

- 成功 → 进入「模型分级」
- 超时 → 重试一次（缓存可能未预热）；仍然超时则按「保留已有模型配置」缓存回填已有 `model:`、跳过自动配置，在安装报告中输出手动配置指南
- 失败（命令不存在、输出为空等）→ 同上：回填「保留已有模型配置」缓存、跳过自动配置、输出手动配置指南

##### Step 3：模型分级

**优先按成本分级（有 `--verbose` 时）**：按每模型实际 cost 从低到高分档——低端取最便宜/免费档、中端取中价档、高端取最贵或上下文/能力最强档。免费模型按真实 cost=0 归低端，**不按名字里的营销词**（如 `nemotron-3-ultra-free` 名含 `ultra` 但 cost=0，应归低端）。无 cost 数据的模型也据此进入候选，不被丢弃。

**回退按关键词分级（无 `--verbose` 或无 cost 时）**：按模型 ID 中最后一个 `/` 之后的模型名按 `-`、`.`、`_` 分割为段，逐段精确匹配关键词（不区分大小写）。例如 `minimax-m3` 拆为 `[minimax, m3]`，不匹配 `mini` 也不匹配 `max`；`claude-haiku-4.5` 拆为 `[claude, haiku, 4, 5]`，匹配 `haiku`。关键词分级是启发式，安装报告中标注 `分级依据：关键词（heuristic）`。

| 等级 | 匹配关键词 | 对应 Agent |
|------|-----------|-----------|
| 低端 | `haiku`, `flash`, `mini`, `nano`, `lite` | chapter-extractor, consistency-checker, story-explorer |
| 中端 | `sonnet`, `plus` | story-researcher, narrative-writer, character-designer, revision-governor |
| 高端 | `opus`, `pro`, `ultra`, `max` | story-architect |

- 一个模型可能匹配多个等级的关键词，取最高等级
- 关键词回退下未匹配任何关键词的模型仍列入候选附加建议（按成本分级则一律纳入），并在安装报告列出，提示"可通过自定义输入使用"
- 同一等级内，如果包含多个模型供应商，优先列出知名供应商（anthropic、openai、google、deepseek）的模型

##### Step 4：逐级交互选择

按 低端 → 中端 → 高端 顺序，每级用 AskUserQuestion 让用户选择。

**低端选项结构：**

```
问题："为低成本 Agent（chapter-extractor, consistency-checker, story-explorer）选择模型："
选项：
  - provider/model-id
  - provider/model-id
  - 自定义输入（手动输入完整模型 ID，ID 拼写错误要到运行时才会暴露）
  - 跳过，使用主模型（成本可能较高）
```

**中端选项结构：**

```
问题："为写作质量关键 Agent（narrative-writer, character-designer, story-researcher, revision-governor）选择模型："
选项：
  - provider/model-id
  - provider/model-id
  - 自定义输入（请勿使用低端模型，会影响正文质量；ID 拼写错误要到运行时才会暴露）
  - 跳过，使用主模型（主模型质量通常足够）
```

**高端选项结构：**

```
问题："为总指挥 Agent（story-architect）选择模型："
选项：
  - provider/model-id
  - provider/model-id
  - 自定义输入（手动输入完整模型 ID，ID 拼写错误要到运行时才会暴露）
  - 跳过，使用主模型（成本可能较高）
```

规则：
- 候选最多显示 5 个，超过则截断并提示"更多模型请使用自定义输入"。**每一级无论候选数是否为 0 都用 AskUserQuestion 弹出**，选项至少含：候选模型（如有）、`自定义输入`、`保留现有模型`（「保留已有模型配置」缓存到该 agent 的 model，无则不显示此项）、`跳过，用主模型`。候选为 0 时仍弹窗，并在问题说明里给出对应警告 + 列出未分级/未入档模型供参考——不再静默跳过交互（否则用户够不到自定义输入）。
- `自定义输入`：用户输入 `provider/model-id` 完整 ID；写入前校验为单行、无控制字符、匹配 `^[A-Za-z0-9._-]+/[A-Za-z0-9._:+-]+$`，不符则提示重输或改选跳过。
- `保留现有模型`：写回「保留已有模型配置」缓存的该 agent model（重新部署时保住用户上次配置），不算"跳过"。
- `跳过，用主模型`：显式清除——不写该 agent 的 `model:`，agent 继承主模型。想保留上次配置请选 `保留现有模型`。
- 各级候选为 0 时在问题说明里给出提示：
  - 低端："未检测到低成本模型，这 3 个 agent 将使用主模型，成本可能较高"
  - 中端："未检测到匹配的中端模型。narrative-writer、character-designer、story-researcher 将使用主模型。如主模型质量足够此配置合理；如需降本，请用自定义输入指定不低于主模型质量的中端模型，或从下方未分级模型里选。"
  - 高端："未检测到高端模型，story-architect 将使用主模型"

##### Step 5：写入 model 字段

对应用户选择的 agent 文件（`.opencode/agents/*.md`，由部署清单中 OpenCode agents 部署步骤在此步骤之前已部署），在 frontmatter 末尾、closing `---` 之前，以**零缩进的顶层字段**插入 `model:`（不要插进 `permission:` 等多行 map 的缩进块内部）。值含 YAML 特殊字符时加引号，确保不破坏 frontmatter：

```yaml
---
description: ...
mode: subagent
permission:
  read: allow
  edit: deny
steps: 12
model: provider/model-id
---
```

- 如果 agent 文件已有 `model:` 字段（重新部署场景），替换该顶层 `model:` 的值，不新增重复键
- `保留现有模型`：写回「保留已有模型配置」缓存的该 agent model
- `跳过，用主模型`：不写入 `model:` 字段
- 检测失败/超时、没走到本步骤的等级：用「保留已有模型配置」缓存回填 `model:`，避免 replace 抹掉用户上次配置

### Step 6：部署质检进度模板

- `追踪/上下文.md` 不再由本步部署。它已改为 `_tracking-state.json` 的派生视图，由写作 skill 自带的追踪事务工具在提交时渲染，story-setup 不再创建也不再覆盖它
- 读取 `skills/story-setup/references/templates/质检进度.md.tmpl`
- 仅当已识别为长篇书目且 `{书名}/追踪/` 已存在时，创建缺失的 `{书名}/追踪/质检进度.md`
- 如果目标文件已存在，不覆盖；短篇项目不得因此创建 `追踪/` 目录。这张表是 Phase 5 硬性必须项（consistency-checker、去AI味独立审查）的可机械核对记录，不能因为项目已在写而缺失

### Step 7：合并 Hooks 注册到 settings.local.json

1. 按现有跨平台规则探测 Python：`for PYBIN in python3 python py; do "$PYBIN" -c "" 2>/dev/null && break; done`；无可用解释器时停止，不手写或简化合并。
2. 调用 `"$PYBIN" "{story-setup skill目录}/scripts/merge-claude-settings.py" --existing "{项目}/.claude/settings.local.json" --template "{story-setup skill目录}/references/templates/settings-hooks.json" --output "{项目}/.claude/settings.local.json"`。
3. helper 会移除所有已知 story-setup hook 的历史注册，再追加当前模板；因此 matcher、timeout、if 能随版本升级，同时混在旧 block 中的用户 hook 与未知顶层字段原样保留。写后解析 JSON，验证模板命令各一份、用户配置仍在，再复跑 helper 比较文件字节确认幂等。

### Codex hooks.json 合并算法（target_cli 含 codex 时）

Codex 项目 hooks 部署到 `.codex/hooks.json`；运行脚本部署到 `.codex/hooks/story_codex_hook.py`、`run-story-hook.sh`、`run-story-hook.cmd`。JSON 只负责定位项目根与传递 event，解释器探测由平台 launcher 统一处理。

1. 定位当前 story-setup skill 目录，读取 `references/codex/hooks/hooks.json` 作为唯一当前模板，读取项目 `.codex/hooks.json`（不存在时视为空对象）。
2. 按现有跨平台规则探测可用 Python：`for PYBIN in python3 python py; do "$PYBIN" -c "" 2>/dev/null && break; done`；无可用解释器时停止，不手写或简化 JSON 合并。
3. 调用 `"$PYBIN" "{story-setup skill目录}/scripts/merge-codex-hooks.py" --existing "{项目}/.codex/hooks.json" --template "{story-setup skill目录}/references/codex/hooks/hooks.json" --output "{项目}/.codex/hooks.json"`。该 helper 会识别旧直调 `story_codex_hook.py`、当前 `run-story-hook.sh` 和 `run-story-hook.cmd` 三类管理身份，先移除所有已知管理注册，再追加当前模板。
4. 保留用户已有的非 story-setup hooks、matcher 块与未知顶层字段。重复执行必须幂等；禁止再按原始 `command` 字符串追加去重，否则 v17 直调命令会与 v18 launcher 双重注册。
5. 写入后解析 JSON 验证：旧直调 `story_codex_hook.py` 命令数为 0，当前模板 6 个注册各存在且仅存在一次，用户 hook 与未知顶层字段仍在。然后提示用户：项目 `.codex/` 层需要被 Codex trust，非 managed command hooks 还需要在 `/hooks` 中 review/trust 后才会运行；Windows 下走 `commandWindows`，launcher 从当前目录向上定位项目 `.codex/hooks/`，与 POSIX 路径的嵌套目录行为一致。

### 部署源解析（防项目旧副本自复制）

1. 记下当前正在执行的 `story-setup` 目录与其上一级 skills 根，称为 `bootstrap_root`。如果它位于目标项目的 `.trae/skills/`、`.codebuddy/skills/`、`.zcode/skills/`、`.codex/skills/`、`.claude/skills/` 或根 `skills/` 下，它只是“已部署快照”，不得一概当成升级权威源。
2. 已部署项目另外枚举这些可验证候选：当前已启用 plugin 的 `${CODEBUDDY_PLUGIN_ROOT}/skills/story-setup`、`~/.agents/skills/story-setup`、`~/.claude/skills/story-setup`、`~/.codex/skills/story-setup`，以及用户本次显式给出的本地安装目录。不搜索整个磁盘，不从网页或浮动仓库直接执行未验证内容。
3. 候选只有在以下条件全部成立时才有效：`SKILL.md` frontmatter 的 `name=story-setup`、`version` 为可比较的三段数字 SemVer、`metadata.openclaw.source` 指向本 oh-story 仓库，且 Phase 1 列出的 references 与 helper 自检全部通过。无效候选只报告，不读其他内容。
4. 在有效候选与 `bootstrap_root` 中按 SemVer 选最新完整包为 `canonical_root`；版本相同时优先项目外的安装包，版本较低的外部包不得反向降级项目。安装报告必须写出 `bootstrap_root`、`canonical_root`、各自版本/用途与选择原因。
5. 后续模板、helper 与 18 个中文主包 Skill 全部从 `canonical_root` 读取；项目自定义 Skill 不进入 TRAE/WorkBuddy 本轮适配部署源，已有用户 Skill 保留不动。
6. `copy-path-safety.py` 的 `status=same` 只让当前那一个 source/target 项 no-op；不得因项目内 `story-setup` 副本指向自身，就跳过从 `canonical_root` 刷新其他 Skills、Commands、Agents、Rules 和 Hooks。

### canonical 中文主包 Skill 清单（所有 skills 复制分支共用）

1. `canonical_root/skills/` 必须精确包含这 18 个可部署 Skill：`browser-cdp`、`story`、`story-cover`、`story-data-analyze`、`story-deslop`、`story-explore`、`story-import`、`story-long-analyze`、`story-long-scan`、`story-long-write`、`story-publish`、`story-release-package`、`story-research`、`story-review`、`story-setup`、`story-short-analyze`、`story-short-scan`、`story-short-write`。
2. 按上述固定名字集读取每个 `SKILL.md` frontmatter 的 `name` / `description`；任一缺失、目录名与 `name` 不一致或重名时停止部署。不因项目根出现额外 `story*` 目录而扩张主包。
3. 对每个源 Skill 目录与对应目标目录逐项执行 `copy-path-safety.py`；`same` 记录为 no-op，`unsafe/error` 停止，仅 `safe` 可复制。不对整个用户 skills 根目录做删除或整体替换。

### TRAE / WorkBuddy 固定 Agent 名册

1. 两端共用通用名册精确为 8 张：`chapter-extractor`, `character-designer`, `consistency-checker`, `narrative-writer`, `revision-governor`, `story-architect`, `story-explorer`, `story-researcher`。
2. TRAE 数据名册精确为 5 张：`story-data-fetcher`, `story-data-method-validator`, `story-data-metrics-analyst`, `story-data-supervisor`, `story-data-text-improvement-planner`。TRAE 物理名册必须精确等于前述 8 张通用卡与这 5 张数据卡的并集，共 13 张。
3. WorkBuddy 数据物理名册精确为 2 张：`story-data-fetcher`, `story-data-readonly-runner`。WorkBuddy 物理名册必须精确等于前述 8 张通用卡与这 2 张数据卡的并集，共 10 张。四个只读逻辑角色卡随数据分析 Skill 自身部署，由其运行时映射定位，不作物理 Agent 注册。
4. 两端都只备份/替换上述精确 marker 卡，保留用户 Agent；上次受管但本次不在对应精确名字集的卡走「管理资产收敛」备份后删除。

### ZCode 部署算法（target_cli 含 zcode 时）

ZCode 首版部署 Skills、Commands、AGENTS.md 和支持事件内的 Hooks；不部署 `.zcode/agents` 或 `.zcode/rules`。

1. 按「canonical 中文主包 Skill 清单」复制到 `.zcode/skills/{skill-name}/`；仅替换这 18 个已知目录，保留用户其他 Skills。
2. 复制 `references/zcode/commands/*.md` 到 `.zcode/commands/`；仅替换与 canonical skill 同名的管理命令，保留用户其他 Commands。若主包某个 skill 缺预生成模板，视为包不完整并停止，不临时为项目扩展生成 command。
3. 复制 `references/zcode/hooks/story_zcode_hook.js` 和 `references/zcode/hooks/story_hook_core.js` 到 `.zcode/hooks/`。
4. 读取 `references/zcode/config.json.patch` 和现有 `.zcode/config.json`（如只有根 `zcode.json`，仍创建 `.zcode/config.json` 承载 oh-story 项目 Hooks，不改写根文件）：
   - 保留用户所有未知字段、MCP、plugins、skills/commands disable overrides；
   - **hooks 互斥（避免双触发）**：若本项目经已安装的 oh-story 插件运行（marketplace 安装，仓库根 `.zcode-plugin/plugin.json` 的 `hooks.json` 已全局注册 SessionStart/PreToolUse/PostToolUse），则**跳过**下面把 `config.json.patch` 的 `hooks` 块合并进 `.zcode/config.json`——插件 manifest 已注册这批 hooks，再合并会让同一事件跑两遍（PreToolUse 拦两次、PostToolUse 注入两次）。只有未装插件（直接克隆 / 手动导入 references）时才合并 hooks。不确定时以「ZCode 是否已通过本插件注册这套 hooks」为准；skills/commands/hook 文件/AGENTS 与 config 的非 hook 字段两条路径都照常部署。
   - 合并 hooks（仅未装插件时）：设置 `hooks.enabled: true`；用户已有更大的 `timeoutMs` 时保留，否则取模板值；对 `hooks.events` 的 SessionStart、PreToolUse、PostToolUse 按 `event + matcher + process command + args` 去重追加；不复制 ZCode 不支持的 PreCompact、PostCompact、SessionEnd、SubagentStop、Notification。
5. 将 `references/zcode/AGENTS.md.tmpl` 按「AGENTS.md 合并策略」写入根 `AGENTS.md`。
6. `.story-deployed` 的 `target_cli` 写入 `zcode` 或多端组合，`references_dir` 写 `.zcode/skills/story-setup/references/agent-references`。
7. 安装报告明确说明：ZCode 3.3.4 的项目/plugin custom agents 不执行，所有专业角色走 solo/direct；系统需要可用的 `node` 命令运行项目 Hook。

Plugin 安装不经过本算法：仓库根 `.zcode-plugin/plugin.json` 直接暴露同一组 Skills/Commands/Hooks。Plugin Skills 优先级低于 workspace `.zcode/skills`；两者同时存在时项目快照优先，升级项目快照需重新运行 `$story-setup`。**Hooks 只能注册一份**：插件 manifest 与 workspace `.zcode/config.json` 注册的是同一批事件，装了插件就不要再把 `config.json.patch` 的 hooks 合并进 `.zcode/config.json`（见上算法第 4 步的 hooks 互斥），否则 PreToolUse/PostToolUse 会双触发；插件在场时以插件 manifest 为 hooks 唯一注册源。

### TRAE hooks.json 合并算法（target_cli 含 trae 时）

1. 读取 `references/trae/hooks/hooks.json` 作为唯一当前模板，读取项目 `.trae/hooks.json`（不存在时视为空对象）。TRAE 合法 schema 是顶层 `{ "version": 1, "hooks": {...} }`，事件值为 matcher group 数组，group 内是 `matcher` + `hooks`，每个 hook 仅使用 `{ "type": "command", "command": "<单一 shell command 字符串>", "timeout": <秒> }`。
2. 按跨平台规则探测 `python3/python/py`；无可用解释器时停止 TRAE 分支，不手写或整体覆盖 JSON。
3. 调用 `"$PYBIN" "{story-setup skill目录}/scripts/merge-trae-hooks.py" --existing "{项目}/.trae/hooks.json" --template "{story-setup skill目录}/references/trae/hooks/hooks.json" --output "{项目}/.trae/hooks.json"`。helper 只把 command 中包含 `.trae/hooks/story_trae_hook.js` 的注册识别为 oh-story 管理项：先从历史 event/matcher 块移除它们，再追加当前模板。同一 matcher 块中的用户 hook、其他事件、未知顶层字段全部保留。
4. 写后校验 `version == 1`；事件名只能来自 TRAE 支持集 `SessionStart`、`UserPromptSubmit`、`PreToolUse`、`PostToolUse`、`Stop`、`Notification`，当前模板不得出现 `SessionEnd`、`PreCompact`、`PostCompact`、`SubagentStop`；hook 内不得出现 ZCode 的 `process/args/timeoutMs` 或 Claude 的 `if`。正文工具 matcher 覆盖 TRAE 原生 `RunCommand|Write|Edit`，commit advisory 覆盖 `RunCommand`。
5. 统计模板中每个 oh-story command 身份在结果中恰好一份，用户 hook/顶层字段仍在；再次运行 helper，必须与上次输出字节一致。

### TRAE Code 原生部署算法（target_cli 含 trae 时）

TRAE 分支部署原生 Skills / Subagents / Commands / Rules / Hooks，不走 generic skills-only 降级模式。

1. 按「canonical 中文主包 Skill 清单」确认固定 18 个 Skill。在任何写入前，按「TRAE 归属与备份门」为本次将改动的已存管理资产建立带 UTC 时间戳的备份；遇到无 `oh-story-managed` 标记的同名文件则保留、记录冲突并停止该资产写入。
2. 逐项过 `copy-path-safety.py` 后，把 18 个 canonical Skill 复制到 `.trae/skills/{skill-name}/`。目标缺失则创建；已是 oh-story skill（`SKILL.md` 的 `metadata.openclaw.source` 指向本仓库，或含精确标记 `<!-- oh-story-managed: skill/{skill-name} -->`）才可备份后替换。现有 sentinel 不能代替单个 Skill 的归属证据；无证据则保留并报告。`status=same` 的 Skill 只验证，不复制进自身。
3. 对 18 个 canonical 名字逐一部署 `references/trae/commands/{name}.md`；任一模板缺失即按部署包不完整停止，不为项目额外 Skill 生成 fallback command。只替换带相同管理标记的文件。
4. 按「部署 TRAE Agents」与「TRAE / WorkBuddy 固定 Agent 名册」把通用 8 名与 TRAE 数据 5 名的精确并集（13 张）部署到 `.trae/agents/`。仅 Agent 内置 Agent 才能调用子 Agent；skill 流程遇到子 Agent 不可用必须走已定义的 `solo/direct` fallback。
5. 将 `references/trae/rules/*.md` 写入 `.trae/rules/`，只替换带 `<!-- oh-story-managed: rule/... -->` 标记的文件；TRAE rule frontmatter 使用 `alwaysApply: false` 和 `globs`，不复制 Claude `paths` frontmatter。将 `references/trae/AGENTS.md.tmpl` 按「AGENTS.md 合并策略」写入根 `AGENTS.md`，只替换 `<!-- BEGIN oh-story-managed: trae -->` 与 `<!-- END oh-story-managed: trae -->` 之间的块，保留用户其他段落。
6. 将 `references/trae/hooks/story_trae_hook.js` 与 `story_hook_core.js` 写入 `.trae/hooks/`；runner 只替换头注释证明为 oh-story TRAE adapter 的同名文件。既有 shared core 必须先运行 `trae-core-ownership.py --candidate <文件> --registry references/trae/legacy-managed-sha256.json`，或证明与同项目受信 sibling core 字节一致；退出 3（unmanaged）/2（registry error）都保留并报告，不覆盖。替换后执行 `node --check` 与跨 adapter byte-parity 校验，再按「TRAE hooks.json 合并算法」合并 `.trae/hooks.json`；禁止用模板整体覆盖用户配置。
   Windows 的原生 `RunCommand` 由 PowerShell 提供，runner 必须同时覆盖已测试的静态 `Set-Content`、`Add-Content`、`Out-File`、`Copy-Item`、`Move-Item`、`New-Item` 写盘形式；动态表达式、splatting、`.NET` API 和未识别外部程序仍由 Skill 自检与写后门兜底，不得声称全部 PowerShell 写入都能在 PreToolUse 硬拦。
7. 校验 `.trae/skills/` 与 `.trae/commands/` 的受管名字集都精确等于 canonical 18，受管 Agent 名字集精确等于「TRAE / WorkBuddy 固定 Agent 名册」列出的 TRAE 13 名并集，rule/hooks/AGENTS 标记齐全，hooks 契约测试通过。用户其他 `.trae` 资产必须仍在。
8. `.story-deployed` 的 `target_cli` 写 `trae` 或多端组合，`references_dir` 写 `.trae/skills/story-setup/references/agent-references`。安装报告列出备份目录、冲突/no-op、18 Skill / 18 Command / 13 Agent 验证结果与 Agent 可用性，并提示新开 TRAE 会话刷新 Skills / Commands / Rules / Subagents / Hooks。

### WorkBuddy settings.json 合并算法（target_cli 含 workbuddy 时）

1. 先判定本次会话是否已实际启用 oh-story plugin：只接受当前执行 Skill 路径位于 CodeBuddy plugin 安装根、运行时 registry 明确返回 `oh-story`，或可用的 `codebuddy plugin list` 明确显示该插件 enabled。仓库里有 manifest、磁盘上有未启用副本、或用户口头说“装过”都不能代替运行时证据。
2. plugin 已启用时选择 `references/workbuddy/hooks/disabled-hooks.json`；project-local 模式选择 `references/workbuddy/hooks/project-hooks.json`。按跨平台规则探测 `python3/python/py`，调用 `merge-workbuddy-settings.py --existing {项目}/.codebuddy/settings.json --template <所选模板> --output {项目}/.codebuddy/settings.json`；无 Python 时停止 WorkBuddy 分支，不手写 JSON。
3. helper 只把命令中含 `story_workbuddy_hook.js` 的注册认作 oh-story 管理项：先从所有历史事件/matcher 中移除，再按所选模板追加。用户 hook、权限、模型、MCP 和未知顶层字段全部保留；重复执行必须字节幂等。
4. project-local 模式把 `story_workbuddy_hook.js` 与 `story_hook_core.js` 写入 `.codebuddy/hooks/`，并确认四个当前注册各恰好一次。plugin 模式不再注册第二套项目 Hook，`.codebuddy/settings.json` 中 oh-story runner 注册必须为零。不得用“双份输出内容相同”证明兼容。
5. 校验 Hook 输出只使用 CodeBuddy 支持字段：JSON 输出分支都有顶层 `continue: true`；PreToolUse 拒绝使用 `hookSpecificOutput.permissionDecision=deny`；commit 提醒使用顶层 `systemMessage`；健康 no-op stdout 为空。matcher 只声明 runner 已有目标解析 fixture 覆盖的工具。

### WorkBuddy / CodeBuddy Code 原生部署算法（target_cli 含 workbuddy 时）

WorkBuddy Desktop 内嵌 CodeBuddy Code CLI；项目模式原生发现 `.codebuddy/skills/`、`.codebuddy/commands/`、`.codebuddy/agents/`、`.codebuddy/rules/` 与 `.codebuddy/settings.json`。不得把它降级成 generic skills-only。

1. 按「canonical 中文主包 Skill 清单」复制 18 个 Skill 到 `.codebuddy/skills/{skill-name}/`；只替换能由本仓库 metadata 或精确 marker 证明归属的主包目录，保留用户其他 Skills。源目标相同时记 no-op。
2. 对 18 个 canonical Skill 逐一复制 `references/workbuddy/commands/{name}.md` 到 `.codebuddy/commands/{name}.md`；模板缺失即按包不完整停止，不为项目扩展生成 fallback command。这里是项目裸命令 `/story-*`；plugin manifest 不加载这批 Commands。
3. 按「部署 WorkBuddy Agents」与「TRAE / WorkBuddy 固定 Agent 名册」把通用 8 名与 WorkBuddy 数据物理 2 名的精确并集（10 张）部署到 `.codebuddy/agents/`；项目卡使用裸 agent 名，由 `Agent` 工具的 `subagent_type` 字段调用。数据分析的四个只读逻辑角色按映射调用 pooled runner，不把逻辑卡复制到 registry。plugin-only 名称 `oh-story:<name>` 只能在当前 registry 真实返回时使用。
4. 将 `references/workbuddy/rules/*.md` 合并到 `.codebuddy/rules/`，只替换同管理标记文件；再按「WorkBuddy memory 合并策略」处理当前唯一生效的 memory 文件，禁止用一份很短的 CODEBUDDY 文件遮住已有 `AGENTS.md`。
5. 按「WorkBuddy settings.json 合并算法」选择 project-local 或 plugin 互斥分支，并运行 Node 语法、共享 core byte-parity、中文正文写前/写后门与合并幂等 fixture。Windows 若使用 PowerShell，只有专项 fixture 已覆盖的静态写入命令属于硬门；动态表达式、splatting、.NET API 或未识别外部写盘程序仍必须依赖 Skill 自检与写后兜底，安装报告不得声称“所有 PowerShell 写入均可硬拦截”。
6. 校验 `.codebuddy/skills/` 与 `.codebuddy/commands/` 的受管名字集精确等于 canonical 18，受管 Agent 名字集精确等于「TRAE / WorkBuddy 固定 Agent 名册」列出的 WorkBuddy 10 名并集，rule/memory marker 唯一，用户其他 `.codebuddy` 资产仍在。校验 pooled runner 的四个逻辑角色映射全集、唯一且指向 Skill 内真实卡；若本机可找到 WorkBuddy 内嵌或独立 `codebuddy`，还要在仓库根运行 `codebuddy plugin validate .` 验证 plugin manifest；命令不可用时明确记为未执行，不能伪称通过。
7. `.story-deployed` 的 `target_cli` 写 `workbuddy` 或多端组合，`references_dir` 写 `.codebuddy/skills/story-setup/references/agent-references`。安装报告分别列出：project 命令 `/story-*`；plugin-only Skill `/oh-story:story-*`；Hook 当前唯一注册源；Agent registry 结果；PowerShell 硬门边界。部署后完整执行 `references/workbuddy/runtime-activation.md`，新开 WorkBuddy / CodeBuddy 会话刷新发现结果；未进 `/skills`、`/agents`、`/hooks` 实际确认时只能报告静态/合成运行时通过。

Plugin 安装不经过项目复制算法：仓库根 `.codebuddy-plugin/plugin.json` 是唯一规范 manifest，路径均以 `./` 开头，只暴露 Skills、Agents、Hooks，不暴露同名 Commands。plugin hooks 与项目 hooks 必须互斥；即使随后运行了项目 `story-setup` 部署 Skills/Commands/Agents/Rules，也仍以 plugin hooks 为唯一注册源，并用 `disabled-hooks.json` 清掉项目旧注册。

### 管理资产收敛与减端（TRAE / WorkBuddy 必做）

1. Phase 1 在修改 `target_cli` 前同时保存 `previous_targets` 与 `desired_targets`。先完成新端部署和被移除端的退役，全部验证通过后才原子写回 sentinel；不得先改 `.story-deployed` 再留下仍会被平台发现的旧资产。
2. 目标端仍保留时也要做名字集收敛：Skill / Command 以 canonical 18 为唯一名册，TRAE Agent 以「TRAE / WorkBuddy 固定 Agent 名册」列出的通用 8 名 + TRAE 数据 5 名（共 13 张）为唯一名册，WorkBuddy Agent 以同节列出的通用 8 名 + WorkBuddy 数据物理 2 名（共 10 张）为唯一名册。将已有精确管理标记/仓库 metadata、但已不在对应精确名字集中的 Skill / Command / Agent / Rule 列为 stale managed assets。先备份，再只删这些可证归属的 stale 项；无标记同名项永不删。删后只在目录真的为空时移除空目录。
3. 从 `previous_targets` 移除 `trae` 时：
   - 对即将改动的 `.trae/` 管理资产建立 `.trae/.oh-story-backups/<UTC时间戳>/` 完整相对路径备份；
   - 用 `merge-trae-hooks.py --template references/trae/hooks/disabled-hooks.json` 从 `.trae/hooks.json` 移除且仅移除 `story_trae_hook.js` 注册，保留用户 hooks/顶层字段，并复跑确认字节幂等；
   - 仅删除能由本节归属门证明的 `.trae/skills`、`commands`、`agents`、`rules` 管理项及两个管理 hook 脚本；从 `AGENTS.md` 只移除 TRAE BEGIN/END 管理块。
4. 从 `previous_targets` 移除 `workbuddy` 时：
   - 先将即将改动的项目管理资产备份到 `.codebuddy/.oh-story-backups/<UTC时间戳>/`；
   - 用 `merge-workbuddy-settings.py --template references/workbuddy/hooks/disabled-hooks.json` 从 `.codebuddy/settings.json` 移除项目 oh-story Hook 注册，用户设置和 hooks 不动，复跑确认字节幂等；
   - 仅删除有精确归属证据的 `.codebuddy/skills`、`commands`、`agents`、`rules` 管理项及项目 hook 脚本；从当前唯一 memory 文件只移除 WorkBuddy BEGIN/END 块。如果该 memory 文件是 story-setup 创建且移除后只剩空白，可在备份后删除；否则保留。
   - 项目减端不等于卸载用户级/plugin 级 oh-story；已启用 plugin 只由 CodeBuddy plugin 管理命令单独卸载。
5. 两个项目 runner 还必须在每个事件入口检查 sentinel：如果存在有效 `target_cli` 且不含当前端，立即以空 stdout 成功返回。这是中途失败的防御线，不能代替上述物理注册/发现资产清理。
6. 退役验收必须同时证明：管理 Hook 注册为 0；管理 Skill/Command/Agent/Rule/memory 块不再被目标平台发现；用户资产字节未变；备份可回滚；再跑一次为 no-op。任一项失败时不更新 sentinel，报告部分退役路径。

### OpenClaw skills-only 部署算法（target_cli 含 openclaw 时）

OpenClaw Phase 1 只部署 skills，不部署 OpenClaw agents/hooks/plugin。

1. 按「canonical 中文主包 Skill 清单」读取固定 18 个 Skill 目录。
2. 写入目标项目 `skills/{skill-name}/`，仅替换这 18 个 story-setup 管理目录；保留用户在 `skills/` 下的其他目录，且不将它们注入中文主包。
3. 每个 `SKILL.md` 必须满足 OpenClaw frontmatter 约束：`name` / `description` 是单行键值，`metadata` 是单行 JSON 对象且含 `metadata.openclaw`。
4. 复制 `skills/story-setup/references/openclaw/AGENTS.md.tmpl` 到项目 `AGENTS.md`，按「AGENTS.md 合并策略」合并。
5. `.story-deployed` 的 `target_cli` 写入 `openclaw` 或多端组合；`references_dir` 对 OpenClaw 写 `skills/story-setup/references/agent-references`。
6. 安装报告提示项见 Phase 3 第 12 步。

### Reasonix skills-only 部署算法（target_cli 含 reasonix 时）

Reasonix（DeepSeek-Reasonix CLI）当前只部署 skills 与 `AGENTS.md`，不部署 Reasonix hooks/custom agents（hook I/O 契约与子代理行为缺少可校验的真实 CLI，留待后续阶段）。

1. 按「canonical 中文主包 Skill 清单」复制固定 18 个 Skill 到目标项目 `skills/{skill-name}/`；仅替换这些 story-setup 管理的已知目录，保留用户其他目录。
2. 在项目根创建 `.agents/skills → ../skills` 相对 symlink（与 Codex 共用的 skill root），使 Reasonix 原生扫描 `.agents/skills` 时发现这些 skill；若已是指向 `skills/` 的 symlink 则保留，若被占用为普通目录则不覆盖并在安装报告提示。Windows 未启用 symlink 时跳过本步，改走根 `reasonix-plugin.json` 的 `reasonix plugin install`。
3. 复制 `skills/story-setup/references/reasonix/AGENTS.md.tmpl` 到项目 `AGENTS.md`，按「AGENTS.md 合并策略」合并。
4. 校验 `skills/story-setup/references/agent-references/` 已随完整的 `story-setup` skill 复制到位。若当前执行源就是项目内同一路径，安全预检返回 `same`，本步必须作为 no-op，禁止再把目录复制进自身。
5. `.story-deployed` 的 `target_cli` 写入 `reasonix` 或多端组合；`references_dir` 对 Reasonix 写 `skills/story-setup/references/agent-references`。
6. 安装报告提示项见 Phase 3 第 14 步。

### 通用 Web AI / 其他 Agent 部署算法（target_cli 含 generic 时）

通用路径面向 NarraFork、Web AI、自定义 Agent 等可读取项目文件的环境，只部署通用文件，不声明平台原生 hooks/agents 能力。

1. 按「canonical 中文主包 Skill 清单」复制固定 18 个 Skill 到目标项目 `skills/{skill-name}/`；仅替换这些 story-setup 管理的已知目录，保留用户其他目录。
2. 复制 `skills/story-setup/references/generic/AGENTS.md.tmpl` 到项目 `AGENTS.md`，按「AGENTS.md 合并策略」合并。
3. 校验 `skills/story-setup/references/agent-references/` 已随完整的 `story-setup` skill 复制到位。若当前执行源就是项目内同一路径，安全预检返回 `same`，本步必须作为 no-op，禁止再把目录复制进自身。
4. `.story-deployed` 的 `target_cli` 写入 `generic` 或多端组合；`references_dir` 对 generic 写 `skills/story-setup/references/agent-references`。
5. 安装报告提示项见 Phase 3 第 13 步。

### Step 8：创建部署标记

- 创建 `.story-deployed` 文件（sentinel file）
- 写入以下字段（YAML `key: value` 格式，hook 用 `references/templates/hooks/lib/sentinel.sh` 读取）：
  ```
  deployed_at: <date -u +"%Y-%m-%dT%H:%M:%SZ">
  agents_version: 39
  setup_skill_version: 1.2.22
  target_cli: claude-code（或 opencode、codex、zcode、trae、workbuddy、openclaw、reasonix、generic，或其任意组合）
  resolver_strategy: project-local-skill-reference
  references_dir: .claude/skills/story-setup/references/agent-references（Codex 写 .codex/skills/...；ZCode 写 .zcode/skills/...；TRAE 写 .trae/skills/...；WorkBuddy 写 .codebuddy/skills/...；OpenClaw / Reasonix / generic 写 skills/...；多端用逗号分隔）
  ```
- 此文件供 session-start.sh 和写作 skill 检测部署状态，避免重复提示
- target_cli 含 claude-code 时，同时创建一次性标记文件 `.claude/.agents-pending-restart`（空文件即可）。session-start.sh 在下一个会话启动时据此确认 agents 已随新会话注册，并自动删除该标记——用来向用户确认「重启已生效」。ZCode 不创建该标记，因为它不部署项目 agents。
- 如果 `.story-deployed` 已存在但 `agents_version` 缺失、非整数或小于 `39`，按本次流程更新 hooks/agents/rules/reference bundle（具体变更见 `UPGRADING.md`）；大于 `39` 时已在 Phase 1 停止，不得降级覆盖

## Phase 3：验证安装

1. 验证 hooks 注册：
   - 检查 `.claude/settings.local.json` 中的 hooks 字段是否正确
   - 检查 `.claude/hooks/` 下的脚本是否存在且有执行权限
   - 检查 `.claude/hooks/lib/common.sh` 与 `.claude/hooks/lib/sentinel.sh` 是否存在
2. 验证 rules 路径：
   - 检查 `.claude/rules/` 下的规则文件是否存在且包含 `paths` frontmatter
3. 验证 agents：
   - 检查 `.claude/agents/` 下的 8 个 agent 定义文件是否存在
4. 验证 agent reference bundle：
   - 检查 `.claude/skills/story-setup/references/agent-references/` 下 reference 文件完整
   - 检查所有 `story-setup/references/agent-references/<file>.md` 都能解析到 deployed bundle
5. 验证部署标记：
   - 检查 `.story-deployed` 是否存在且包含时间戳、`agents_version: 39`、`setup_skill_version: 1.2.22`、`target_cli`、`resolver_strategy`、`references_dir`
6. 输出安装报告：
   - 列出所有已部署的文件
   - 列出需要注意的事项（如已有配置已合并）
    - **⚠️ 重启提示（必须醒目输出）**：本次部署写入了 `.claude/agents/`，但这些 custom agent 只在「会话启动」时才会被 Claude Code 注册成 `subagent_type`。**请新开一个 Claude Code 会话再开始写作**，否则当前会话里 story-review / story-long-write 等想 spawn `story-architect`、`narrative-writer` 等时会拿到「subagent_type 不可用」并降级 solo（单视角，失去多 agent 协作）。判断是否生效：新会话里跑 `/story-review`，报告头若是 `Effective Mode: full/lean` 即注册成功；若是 `Fallback: ... -> solo` 说明还在旧会话或未注册。
    - 重启后即可使用 `/story-long-write` 或 `/story-short-write`
    - 如果执行了「配置 OpenCode Agent 模型」，输出 Agent 模型配置摘要：
      ```
      Agent 模型配置：
        story-architect          → <高端模型>（provider/model-id）
        narrative-writer         → <中端模型>（provider/model-id）
        character-designer       → <中端模型>（provider/model-id）
        story-researcher         → <中端模型>（provider/model-id）
        revision-governor        → <中端模型>（provider/model-id）
        chapter-extractor        → <低端模型>（provider/model-id）
        consistency-checker      → <低端模型>（provider/model-id）
        story-explorer           → <低端模型>（provider/model-id）
      ```
    - 如果自动检测失败（`opencode models` 不可用），输出手动配置指南：
      ```
      无法自动检测模型列表。以下 Agent 未配置模型，将使用主模型，成本可能较高：
        - chapter-extractor（建议使用低成本模型）
        - consistency-checker（建议使用低成本模型）
        - story-explorer（建议使用低成本模型）

      手动配置方法：编辑 .opencode/agents/{agent名}.md，在 frontmatter 中添加：
        model: provider/model-id

      可用模型列表与成本可通过 opencode models --verbose 查看（输出含每模型 cost/context）。
      模型库与定价见 OpenCode 官方模型源 https://models.dev/。
      ```
7. 验证 opencode 部署（仅当 target_cli 含 opencode 时）：
    - 检查 `.opencode/agents/` 下的 8 个 agent 定义文件是否存在，且 frontmatter 包含 `mode: subagent` 和 `permission` 字段
    - 检查 `.opencode/plugins/story-hooks.ts` 是否存在
    - 检查 `.opencode/plugins/lib/story_hook_core.js` 存在且 `node --check` 通过（story-hooks.ts import 之，与 `.zcode` 副本字节一致的共享写正文守卫核；置于 `lib/` 子目录以避开 OpenCode 单层 `.opencode/plugins/*.js` 插件自动发现）
    - 检查 `.opencode/commands/` 下的 command 名字集与当前 OpenCode 模板清单一致
    - 检查 `skills/story-setup/references/agent-references/` 下 reference 文件完整且数量与源目录一致
    - 检查 `opencode.json` 的 `plugin` 数组是否包含 story-hooks 条目
    - 检查 `.git/hooks/pre-commit` 是否存在且有执行权限（Windows 上跳过执行权限检查）
    - 检查 `.opencode/agents/` 下 agent 文件 frontmatter 可被 YAML 解析、`model:`（如有配置）是合法顶层标量，而非仅 grep 到 `model:` 子串
8. 验证 Codex 部署（仅当 target_cli 含 codex 时）：
    - 检查 `AGENTS.md` 含 Codex story skill routing sections
    - 检查 `.codex/agents/` 下 8 个 `.toml` agent 定义文件存在并可解析
    - 检查 `.codex/hooks.json` 存在且 JSON 有效，Unix `command` 仅通过 `run-story-hook.sh` 启动，Windows `commandWindows` 仅通过 `run-story-hook.cmd` 启动；不存在直调 `story_codex_hook.py` 的注册
   - 检查 `.codex/hooks/story_codex_hook.py`、`run-story-hook.sh`、`run-story-hook.cmd` 存在，Python 语法有效，POSIX/Windows launcher 能从嵌套 cwd 定位项目根
    - 检查 `.codex/skills/story-setup/references/agent-references/` 下 reference 文件完整且数量与源目录一致
    - 安装报告必须提示：Codex 需要 trust 项目 `.codex/` 配置层，并在 `/hooks` review/trust 非 managed hooks；部署后新开 Codex 会话让 custom agents 生效；若当前运行时仍返回 `unknown agent_type`，按各 skill 的 fallback 规则降级 solo/direct
9. 验证 ZCode 部署（仅当 target_cli 含 zcode 时）：
    - 检查根 `AGENTS.md` 含 ZCode `$story-*` 路由、大纲守卫和 solo/direct fallback
    - 按「canonical 中文主包 Skill 清单」检查 `.zcode/skills/` 与 `.zcode/commands/` 精确为 18 个名字，验证 frontmatter 和命名一致
    - 检查 `.zcode/hooks/story_zcode_hook.js`、`.zcode/hooks/story_hook_core.js` 存在且 `node --check` 通过
    - 检查 `.zcode/config.json` JSON 有效，并按「ZCode 部署算法」第 4 步的 hooks 互斥分支校验：未装 oh-story 插件时，`hooks.enabled=true`、仅注册 ZCode 支持事件、所有 `process` args 指向项目 Hook；已装 oh-story 插件（`.zcode-plugin/plugin.json` 已全局注册这批 hooks）时，改为校验 `.zcode/config.json` 不含（或已移除）这批 oh-story hooks 注册——**不得**为了让校验通过而把 `config.json.patch` 的 hooks 块合并回去，否则同一事件双触发
    - 检查 `.zcode/skills/story-setup/references/agent-references/` 完整且所有 reference 路径可解析
    - 用 fixture 调用 SessionStart、PreToolUse deny/allow、PostToolUse，确认无发现时 stdout 为空、有输出时符合 ZCode 严格 JSON
    - 安装报告必须提示：ZCode 3.3.4 不执行项目/plugin custom agents，full/lean 多 Agent 请求会稳定降级 solo/direct；Hook 依赖 PATH 中的 `node`；部署后新开 ZCode session 刷新 Skills/Commands/AGENTS.md
10. 验证 TRAE Code 部署（仅当 target_cli 含 trae 时）：
    - 检查根 `AGENTS.md` 只有一个完整 `oh-story-managed: trae` 管理块，用户其他段落仍在
    - 检查 `.trae/skills/` 与 `.trae/commands/` 的受管名字集均精确等于 canonical 18；每个 skill 有 `SKILL.md`，每个 command 有 `name` / `description` 与 `oh-story-managed` 标记
    - 检查 `.trae/agents/` 的受管名字集精确等于「TRAE / WorkBuddy 固定 Agent 名册」列出的通用 8 名 + TRAE 数据 5 名（共 13 张），frontmatter 可解析、`name` 唯一、无 Claude-only 字段，管理标记齐全
    - 检查 `.trae/rules/` 的管理文件包含 `alwaysApply` / `globs`，不含 Claude `paths` frontmatter
    - 检查 `.trae/hooks/story_trae_hook.js`、`story_hook_core.js` 存在且 `node --check` 通过；`.trae/hooks.json` 是 `version: 1`，只使用 TRAE 支持事件和 `{type,command,timeout}` hook schema，matcher 覆盖 `RunCommand|Write|Edit`，不得出现 `SubagentStop`
    - 用 fixture 调用 SessionStart、PreToolUse deny/allow、PostToolUse，确认无发现时 stdout 为空、有输出时符合 TRAE `hookSpecificOutput`；复跑 `merge-trae-hooks.py` 确认用户 hook/未知字段保留且字节幂等
    - 检查 `.claude/settings*.json` 的 oh-story 命令保持直接 `bash ...`（不得内嵌仅 POSIX 可解析的 `if`）；所有 Claude 入口都 source 含 `TRAE_PROJECT_DIR` 静默退出逻辑的 `lib/common.sh`。用同一 PreToolUse fixture 证明 Claude 导入 Hook 在 TRAE 下无输出、TRAE 原生 Hook 只执行一次
    - 安装报告必须列出 `.trae/.oh-story-backups/` 本次备份位置和任何冲突/no-op，并提示：在 TRAE Settings 的 Hooks 页面 review/enable 本项目 Hooks，确认项目 `AGENTS.md` / Rules 导入已启用，然后新开 TRAE 会话刷新原生 Skills / Commands / Rules / Subagents / Hooks；若 Subagents Beta 不可用，full/lean 多 Agent 请求必须报告 `Fallback: TRAE subagent unavailable -> solo/direct`
11. 验证 WorkBuddy / CodeBuddy Code 部署（仅当 target_cli 含 workbuddy 时）：
    - 检查 `.codebuddy/skills/` 与 `.codebuddy/commands/` 的受管名字集均精确等于 canonical 18；每个 command 有合法 frontmatter 与管理标记
    - 检查 `.codebuddy/agents/` 的受管名字集精确等于「TRAE / WorkBuddy 固定 Agent 名册」列出的通用 8 名 + WorkBuddy 数据物理 2 名（共 10 张），总数不超过 19，名称唯一，frontmatter 只使用 CodeBuddy 支持字段；pooled runner 的每个逻辑角色都必须唯一映射到 Skill 内真实卡。新会话中分别实调基础 Agent、`story-data-fetcher` 和 pooled runner 的一个逻辑角色，成功后才允许报告多 Agent 模式生效；设置页“全部开启”不能代替 Task registry 证据
    - 检查 `.codebuddy/rules/` 和唯一生效 memory 文件的管理块；项目原有 `AGENTS.md` 内容必须仍被直接读取或通过 `@AGENTS.md` / `@../AGENTS.md` 导入，模板条件占位不得残留；根与 `.codebuddy/` 两份 CODEBUDDY 同时存在时必须报告冲突而不是猜优先级
    - 检查 `.codebuddy/settings.json` 保留用户字段，且按互斥分支验证：project-local 模式当前 4 个 oh-story Hook 注册各恰好一次，事件只有 `SessionStart` / `PreToolUse` / `PostToolUse`；plugin 模式项目注册为零。运行 helper 两次必须字节幂等
    - 用 fixture 调用 SessionStart（含 agents_version 38/39/40）、PreToolUse deny/allow/commit、PostToolUse；确认 healthy no-op stdout 为空、所有输出都有 `continue: true`，拒绝与提醒字段符合 CodeBuddy schema，路径逃逸不能绕过项目根
    - 检查 plugin manifest 不含与 Skills 同名的 `commands` 字段，所有自定义路径以 `./` 开头；可用时运行真实 `codebuddy plugin validate .`。安装报告明确 project `/story-*` 与 plugin `/oh-story:story-*` 的差异、唯一 Hook 来源、PowerShell 硬门边界，并提示新开会话
12. 验证 OpenClaw 部署（仅当 target_cli 含 openclaw 时）：
    - 检查 `AGENTS.md` 含 OpenClaw story skill routing sections
    - 按「canonical 中文主包 Skill 清单」检查 `skills/` 下固定 18 个目标 Skill，且每个 `SKILL.md` 包含单行 `name`、单行 `description`、单行 JSON `metadata.openclaw`
    - 检查 `skills/story-setup/references/agent-references/` 下 reference 文件完整且数量与源目录一致
    - 安装报告必须提示：OpenClaw Phase 1 是 skills-only；未部署 OpenClaw agents/hooks，运行时硬拦截不可用，写正文前大纲守卫、commit 提醒、session/compact 自动注入只作为 skill 内软约束；OpenClaw 在 session 启动时 snapshot eligible skills，部署后如命令/skills 未出现，需新开 OpenClaw session 或等待 skills watcher 刷新
13. 验证通用 Web AI / 其他 Agent 部署（仅当 target_cli 含 generic 时）：
    - 检查 `AGENTS.md` 含通用 story skill routing sections
    - 按「canonical 中文主包 Skill 清单」检查 `skills/` 下固定 18 个目标 Skill，且每个 `SKILL.md` 可读
    - 检查 `skills/story-setup/references/agent-references/` 下 reference 文件完整且数量与源目录一致
    - 安装报告必须提示：generic 不部署平台专属 hooks/custom agents；大纲守卫、commit 提醒、session/compact 注入等硬拦截与多 agent 协作都按 skill 内软约束或 solo/direct fallback 执行
14. 验证 Reasonix 部署（仅当 target_cli 含 reasonix 时）：
    - 检查 `AGENTS.md` 含 Reasonix story skill routing sections 与 solo/direct fallback 说明
    - 按「canonical 中文主包 Skill 清单」检查 `skills/` 下固定 18 个目标 Skill，且每个 `SKILL.md` 可读
    - 检查项目 `.agents/skills` 为指向 `skills/` 的 symlink（POSIX；使 Reasonix 原生扫描发现 skill）；Windows 未建 symlink 时改为确认根 `reasonix-plugin.json` 可用于 `reasonix plugin install`
    - 检查 `skills/story-setup/references/agent-references/` 下 reference 文件完整且数量与源目录一致
    - 安装报告必须提示：Reasonix 当前是 skills-only；未部署 Reasonix hooks/custom agents，写正文前大纲守卫、commit 提醒、session/compact 自动注入只作为 skill 内软约束，涉及专业 Agent 的 Skill 走 solo/direct fallback；可用 `reasonix doctor capabilities` 校验 skill 发现，部署后如未显示新 skills，新开 Reasonix session 或走根 `reasonix-plugin.json` 原生 plugin 安装

---

## 模板占位符

| 占位符 | 替换规则 | 示例 |
|--------|----------|------|
| `{项目名}` | 用户项目名称或目录名 | 《剑来》、《暗卫》 |
| `{书名}` | 书名目录名（与目录一致） | 与 `{项目名}` 相同，或用户自定义 |
| `{目标平台}` | 目标发布平台 | 起点、番茄、晋江、知乎盐言 |
| `{作者名}` | 用户笔名或昵称 | 未指定时用「作者」 |

替换时去掉花括号。如果用户未指定项目名，用当前目录名。未指定的占位符保留原样不替换。

## CLAUDE.md 合并策略

用户已有 CLAUDE.md 时，按 marker/section 合并：
1. 优先识别 story-setup 管理块标记（如果旧项目已有标记，只替换标记内内容）
2. 无标记时，读取用户现有 CLAUDE.md，按 `##` 标题切分为 section map
3. 读取模板 CLAUDE.md.tmpl，同样切分
4. 模板中的标准 section（Skill 路由表、文件结构、协作规则、Compact 后恢复上下文）**覆盖**用户同名 section
5. 用户独有的 section（自定义内容）**保留**不动
6. 未知冲突用 AskUserQuestion 让用户选择保留哪个版本

## AGENTS.md 合并策略（OpenCode / Codex / ZCode / TRAE Code / OpenClaw / Reasonix / generic）

用户已有 AGENTS.md 时，按 marker/section 合并：
1. 优先识别 story-setup 管理块标记（如果旧项目已有标记，只替换标记内内容）
2. 无标记时，读取用户现有 AGENTS.md，按 `##` 标题切分为 section map
3. OpenCode 使用 `skills/story-setup/references/opencode/AGENTS.md.tmpl`；Codex 使用 `skills/story-setup/references/codex/AGENTS.md.tmpl`；ZCode 使用 `skills/story-setup/references/zcode/AGENTS.md.tmpl`；TRAE Code 使用 `skills/story-setup/references/trae/AGENTS.md.tmpl`（只替换 `oh-story-managed: trae` 标记块）；OpenClaw 使用 `skills/story-setup/references/openclaw/AGENTS.md.tmpl`；Reasonix 使用 `skills/story-setup/references/reasonix/AGENTS.md.tmpl`；通用 Web AI / 其他 Agent 使用 `skills/story-setup/references/generic/AGENTS.md.tmpl`
4. 模板中的标准 section（Skill 路由表、文件结构、协作规则、Compact 后恢复上下文）覆盖同名 section；用户独有 section 保留
5. 多端同时部署时，Codex/OpenCode/ZCode/TRAE/OpenClaw/Reasonix/generic 共同可用的通用段落只保留一份；工具特有说明以小节或平台管理 marker 区分，避免互相覆盖

## WorkBuddy memory 合并策略

CodeBuddy 把根 `CODEBUDDY.md` 与 `.codebuddy/CODEBUDDY.md` 作为项目 memory，并只在没有 CODEBUDDY memory 时回退读取 `AGENTS.md`。因此不能无条件新建一份短模板遮住现有通用约定。

1. 同时检查根 `CODEBUDDY.md`、`.codebuddy/CODEBUDDY.md` 和根 `AGENTS.md`。若两份 CODEBUDDY 都存在，停止 memory 写入并报告冲突，请用户选择唯一规范位置；不得猜测加载优先级，也不得删除任一份。其他 WorkBuddy 资产可继续验证，但安装报告必须标为 memory 未闭环。
2. 只有一份 CODEBUDDY 已存在时，在原位 marker-merge WorkBuddy 管理块；若同时存在 `AGENTS.md`，把模板占位 `{{OH_STORY_AGENTS_IMPORT}}` 按目标位置替换为根文件的 `@AGENTS.md` 或 `.codebuddy` 文件的 `@../AGENTS.md`，确保原通用约定仍进入上下文。无 AGENTS 时替换为空行。
3. 两份 CODEBUDDY 都不存在但 `AGENTS.md` 已存在时，直接把 WorkBuddy 管理块合并进现有 `AGENTS.md`，并把导入占位替换为空；不新建 CODEBUDDY 文件，从而继续使用 CodeBuddy 的 AGENTS fallback。
4. 三者都不存在时，创建 `.codebuddy/CODEBUDDY.md`，导入占位替换为空。所有分支都只替换 `BEGIN/END oh-story-managed: workbuddy` 内文本，用户独有内容保留。
5. 写后验证：管理块恰好一份；`{{OH_STORY_AGENTS_IMPORT}}` 不得残留；有既存 AGENTS 且最终使用 CODEBUDDY 时必须有正确相对导入；再次合并字节幂等。

## 重新部署

- `.story-deployed` 不存在 → 全新安装，Phase 2 全部执行
- `.story-deployed` 存在且 `agents_version: 39` → 提示已部署，AskUserQuestion 确认是否重新部署；提示里写明重新部署只用当前本地 skill 包刷新项目文件，skill 本身的正式更新走固定 GitHub Release 资产：`npx skills add https://github.com/qin1473692580-ux/oh-story-claudecode/releases/latest/download/oh-story-release.zip -y -g`
- `.story-deployed` 存在但 `agents_version` 缺失、非整数或小于 `39` → 提示需要更新，重新执行 Phase 2 刷新 story-setup 管理的 agents/hooks/rules/reference bundle，CLAUDE.md / AGENTS.md / CODEBUDDY.md / settings.local.json / .codex/hooks.json / .zcode/config.json / .trae/hooks.json / .codebuddy/settings.json 走合并策略，TRAE 管理资产先备份，WorkBuddy hooks 重判 plugin/project 互斥
- `.story-deployed` 存在且 `agents_version` 大于 `39` → 当前 skill 版本过旧，停止并提示先更新 oh-story-claudecode；不覆盖项目中的更新部署

---

## 参考资料

| 文件 | 用途 |
|------|------|
| references/templates/hooks/ | 8 个 hook 脚本模板 + `story_hook_core.js`（正文网/字数/大纲守卫/连续性/commit 侦测的共享实现，与 OpenCode/ZCode 同一份）+ `story_hook_cli.js`（bash hook 调核的 node 桥）+ `lib/common.sh`/`lib/sentinel.sh`（`check-prose-after-write.sh` 负责 Write/Edit 的 PostToolUse 兜底；Bash 的重定向、`tee`、`touch`、`cp`、`mv`、`install` 写正文由 PreToolUse 共享核 best-effort 识别并执行大纲/追踪门，未识别的 Bash 写入仍由 Codex Stop 回合末 git 扫描兜底） |
| references/templates/rules/ | 4 条 path-scoped 规则模板 |
| references/templates/agents/ | 8 个 agent 定义模板（story-architect, character-designer, narrative-writer, consistency-checker, revision-governor, story-researcher, story-explorer, chapter-extractor） |
| references/agent-references/ | Agent 模板自带的参考资料副本；部署到 `.claude/skills/story-setup/references/agent-references/`，避免跨 skill references |
| references/templates/settings-hooks.json | hooks 注册 JSON 片段 |
| references/templates/质检进度.md.tmpl | 逐章 Phase 5 质检子项完成状态表，机械可查 |
| references/codex/AGENTS.md.tmpl | Codex 项目根 AGENTS.md 模板 |
| references/codex/agents/ | 8 个 Codex custom agent TOML 模板 |
| references/codex/hooks/hooks.json | Codex hooks 注册 JSON 模板（部署到 `.codex/hooks.json`） |
| references/codex/hooks/story_codex_hook.py | Codex hook adapter（部署到 `.codex/hooks/story_codex_hook.py`） |
| references/openclaw/AGENTS.md.tmpl | OpenClaw 项目根 AGENTS.md 模板（skills-only） |
| references/generic/AGENTS.md.tmpl | 通用 Web AI / 其他 Agent 项目根 AGENTS.md 模板（skills + soft checks） |
| references/zcode/ | ZCode AGENTS、Commands、workspace config patch 与严格 JSON Hook runner |
| references/trae/ | TRAE Code 原生 AGENTS、Commands、Agents、Rules 与 Hooks adapter |
| scripts/merge-trae-hooks.py | 按稳定 command 身份合并 `.trae/hooks.json`，保留用户配置 |
| scripts/trae-core-ownership.py + references/trae/legacy-managed-sha256.json | 在覆盖 TRAE shared core 前以 marker / 旧版精确 SHA 分类归属；未知文件 fail closed |
| references/workbuddy/ | WorkBuddy / CodeBuddy Code 原生 memory 模板、项目 Commands、Agents、Rules 与 Hooks adapter；plugin 模式的 Skills/Agents/Hooks 也复用这些已验证产物 |
| scripts/merge-workbuddy-settings.py | 按稳定 runner 身份合并或移除 `.codebuddy/settings.json` 中的项目 Hook，保留用户配置并保证 plugin/project 互斥 |
| 仓库根 `.codebuddy-plugin/plugin.json` | CodeBuddy plugin 规范 manifest；只暴露 Skills、Agents、Hooks，避免与同名 Commands 冲突 |
| 仓库根 `scripts/generate-workbuddy-adapter.py` | 维护期从受审 TRAE 角色/命令与共享 core 确定性生成 WorkBuddy 产物；不随项目部署下发 |

---

## 流程衔接

**流水线：** 部署
**位置：** 初始化（最前置）

| 时机 | 跳转到 | 命令 |
|---|---|---|
| 部署完成，开始写作 | story-long-write / story-short-write | `/story-long-write` 或 `/story-short-write` |
| 导入已有小说做拆解 | story-import | `/story-import` |
| 需要浏览器登录态（扫榜/拆文取原文） | browser-cdp | `/browser-cdp`；generic 需平台允许本地脚本/浏览器控制 |

各端调用语法：Claude `/名`、Codex/ZCode `$名`、TRAE Code `/名`、WorkBuddy 项目模式 `/名`、WorkBuddy plugin-only 模式 `/oh-story:名`、OpenClaw `/skill 名`、Reasonix / generic 直接点名 skill。
