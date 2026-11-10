# TRAE Code 原生能力激活与验证

把 `.trae/` 文件写入项目只能证明静态部署完整，不能证明当前 TraeCode 会话已加载 Skills、Commands、Rules、Subagents 和 Hooks。部署后按下列顺序验证。

## 1. 确认环境边界

- 本适配器面向 **TraeCode IDE**，项目路径为 `.trae/skills/`、`.trae/commands/`、`.trae/agents/`、`.trae/rules/` 和 `.trae/hooks.json`。
- TraeCode CLI 的 Commands / Agents 原生路径是 `.traecli/commands/` 与 `.traecli/agents/`。未额外部署 `.traecli/` 时，不得把本 IDE 适配声称为完整 CLI 适配。
- 从项目根目录打开 TraeCode，并信任该项目。

## 2. 激活项目 Hooks

1. 打开「设置 > Hooks」。
2. review 项目的 `.trae/hooks.json`，确认顶层为 `version: 1` 与 `hooks`，且 oh-story 命令只指向 `.trae/hooks/story_trae_hook.js`，然后启用该配置。旧版把 `SessionStart` 等事件直接挂在顶层的文件不会按当前官方 schema 加载，须先重新执行 `story-setup` 迁移。
3. 如果同一项目还启用了 `.claude/settings.json` 或 `.claude/settings.local.json`，TraeCode 会合并执行两端 Hooks。oh-story 的 Claude shell 入口在真正启动并检测到 `TRAE_PROJECT_DIR` 后会静默退出，由 `.trae/hooks.json` 成为唯一执行源。Windows 的 TRAE Hook 默认由 PowerShell 执行；若系统没有可用的 `bash`，导入的 Claude 命令会在进入该去重守卫前失败，因此必须在 Hooks 面板禁用 Claude 配置，只启用 `.trae/hooks.json`。旧 Claude hooks 没有去重守卫时也同样禁用，避免同一 Write/Edit 事件执行两次。
4. Hook 运行需要 PATH 中可用的 `node`。

## 3. 确认 Skills 与 Commands

1. 打开「设置 > 技能与命令」，确认「项目」Skill 中能看到 `story`、`story-long-write`、`story-review` 等条目。
2. 确认这些 Skill 已启用；若 `.trae/skill-config.json` 将某项目 Skill 列为禁用，磁盘上存在 `SKILL.md` 也不会生效。
3. 在输入框的 `/` 面板确认同名项目 Commands 可见。Skills 和 Commands 是两条独立发现链，不得只验证其中一条。

## 4. 激活 Rules 与 AGENTS.md

1. 打开「设置 > Rules」，确认 `.trae/rules/oh-story.md` 可见。
2. 如果项目依赖根 `AGENTS.md` 的路由和写作门禁，启用「将 AGENTS.md 包含在上下文中」。
3. `.trae/rules/*.md` 是按 `globs` 匹配的项目规则；AGENTS.md 导入开关不能用“文件存在”代替。

## 5. 激活 Subagents

1. 在「设置 > Beta > Subagents」中开启「启用 Subagents 目录」。
2. 使用 TraeCode 内置 **Agent** 智能体（输入框的 `@` 菜单中选择 Agent）执行需要多角色的 story 流程。只有内置 Agent 能调用 Subagent；Chat 或普通自定义智能体不能因为磁盘上有 `.trae/agents/*.md` 就声称已执行多 Agent。
3. 在 Agent 智能体中明确指定要使用的同名 Subagent，例如“使用 story-architect 审查大纲”。这是 TraeCode 的 Subagent 调度能力，不是 Claude Code 的 `subagent_type` 调用参数。
4. 若目录开关、当前智能体或 registry 不可用，按对应 Skill 的 `solo/direct` 合同降级，不得伪造独立子 Agent 已运行。

## 6. 新会话验证

重载项目或新建 TraeCode 会话后，逐项确认：

- Skills 面板能看到 `story`、`story-long-write`、`story-review` 等项目 Skills。
- `/` 面板能看到同名 Commands，命令参数没有以字面量 `$ARGUMENTS` 泄漏到请求中。
- 内置 Agent 能看到 `story-architect`、`narrative-writer`、`consistency-checker` 等项目 Subagents。
- Hooks 面板显示 `.trae/hooks.json` 已启用，Rules 面板显示 `.trae/rules/oh-story.md` 已加载。
- 在临时测试书目中对一个缺失对应细纲的新正文文件发起 Write/Edit 前，PreToolUse 应返回明确 deny；补齐细纲与追踪前不要真正写入作品。
- Windows 再用临时路径分别验证 `Set-Content`、`Add-Content`、`Out-File`、`Copy-Item`、`Move-Item` 与 `New-Item` 的静态字面量写盘。动态表达式、splatting、`.NET` API 或未识别外部程序不属于可靠的 PreToolUse 静态解析范围，仍依赖 Skill 自检与 PostToolUse 兜底。

任一项未经实际验证时，安装报告只能写“静态兼容，运行时未验证”，不能写“已在 TraeCode 中生效”。

## 官方契约链接

- [Skill](https://docs.trae.cn/ide_skills)
- [Command](https://docs.trae.cn/ide_slash-commands)
- [Rule 与 AGENTS.md 导入](https://docs.trae.cn/ide_rules)
- [Subagent](https://docs.trae.cn/ide_subagents)
- [内置智能体 Agent](https://docs.trae.cn/ide_built-in-agent)
- [Hook 管理与安全启用](https://docs.trae.cn/ide_automate-actions-with-hooks)
- [Hook schema、事件、工具名和 I/O](https://docs.trae.cn/ide_hook-configuration-reference)
