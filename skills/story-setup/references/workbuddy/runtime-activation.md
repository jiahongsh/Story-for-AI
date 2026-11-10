# WorkBuddy / CodeBuddy Code 原生能力激活与验证

写入 `.codebuddy/` 只能证明项目资产完整；真正生效还取决于目录信任、当前会话、Skill/Agent
registry 与 Hook 注册源。部署后按本页验收。

## 1. 先确定唯一运行模式

- 项目模式：发现 `.codebuddy/skills/`、`.codebuddy/commands/`、`.codebuddy/agents/`、
  `.codebuddy/rules/` 与 `.codebuddy/settings.json`；命令为裸 `/story-*`。
- plugin-only：由插件根的 `.codebuddy-plugin/plugin.json` 暴露 Skills、Agents、Hooks；Skill 命令为
  `/oh-story:story-*`，不登记同名项目 Commands。
- 运行 `codebuddy plugin list`。只有 `oh-story` 确实显示 enabled 才按 plugin-only 处理；仓库中仅存在
  manifest 不等于插件已启用。两种模式的 Hook 不能同时注册。

## 2. 信任与新会话

1. 只信任当前写作项目目录，不扩大到不相关父目录。
2. 升级 Skills、Commands、Agents、Rules 或 Hooks 后，新开 WorkBuddy / CodeBuddy Code 会话；旧会话
   不用于证明发现结果。
3. Hooks 需要 PATH 中可用的 `node`。Windows Hook 命令由 Git Bash 执行，不是 PowerShell；但 Agent
   的 `PowerShell` 工具调用仍会作为 Hook 输入，因此 runner 继续解析受测试的静态 PowerShell 写盘形式。

## 3. 验证发现与命名空间

1. 用 `/skills` 确认 `story`、`story-long-write`、`story-review` 等项目 Skills 可见。
2. 用 `/agents` 确认中文主包的 **10 个物理 Agent** 可见；项目模式按裸 `subagent_type` 调用，只有 registry
   真实显示 `oh-story:<name>` 时才使用插件命名空间。CodeBuddy 的 agentic registry 会把内置 + 项目
   Subagent 总数截为 20，因此 oh-story 项目物理卡必须不超过 19；这是平台容量边界。中文主包实际固定
   10 张（8 个通用 + `story-data-fetcher` + `story-data-readonly-runner`），其余四个只读数据逻辑角色由
   pooled runner 承载。设置页显示角色为 `on` 不能证明 `Agent` 工具可调用；逻辑角色卡留在 Skill 内，不应出现在 `/agents`。
3. 项目模式在 `/` 菜单确认 `/story`、`/story-long-write` 等 Commands；plugin-only 则确认
   `/oh-story:story-*`，不得把两套名称混报。
4. 实际调用一个通用 Agent、`story-data-fetcher`，再按 `logical_role + role_card` 合同通过
   `story-data-readonly-runner` 调用一个只读数据逻辑角色；三者都成功才算 Agent runtime 验证通过。

## 4. 验证 Hooks

1. 用 `/hooks` 查看当前注册。项目模式应由 `.codebuddy/settings.json` 唯一登记 oh-story runner；
   plugin-only 应由插件 `hooks/hooks.json` 唯一登记，项目 settings 中不得残留第二套 runner。
2. 当前中文主包项目应由已声明事件统一指向同一个 `story_workbuddy_hook.js`，不得重复注册项目/plugin runner。

## 5. 临时冒烟

- 在临时测试书目中对缺细纲的新正文目标发起 Write/Edit，PreToolUse 应阻断；不要对真实正文做破坏性测试。
- 对普通中文正文目标使用受测 Write/Edit/Bash/PowerShell 写盘面时，大纲、追踪和正文门应按合同执行。

任一 UI/registry 项未实际确认时，只能报告“静态与合成运行时通过，当前会话尚未激活验证”。

## 官方契约链接

- [Skills](https://www.codebuddy.ai/docs/cli/skills)
- [Sub-Agents](https://www.codebuddy.ai/docs/cli/sub-agents)
- [Hooks Reference](https://www.codebuddy.ai/docs/cli/hooks)
- [Plugins Reference](https://www.codebuddy.ai/docs/cli/plugins-reference)
- [Settings](https://www.codebuddy.ai/docs/cli/settings)
