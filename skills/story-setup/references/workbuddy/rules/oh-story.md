---
alwaysApply: true
---

<!-- oh-story-managed: rule/oh-story -->

# oh-story 写作项目规则（WorkBuddy / CodeBuddy Code）

- 命中某个 story Skill 时，先完整读取 `.codebuddy/skills/<skill-name>/SKILL.md`，再按该 Skill 的 references 路由执行。
- 中文正文落盘前必须有对应细纲；长篇普通续写先写入 `追踪/候选章/`，用户明确接受或本轮预授权自动定稿后才能晋升 `正文/` 并提交追踪。
- `_tracking-state.json` 是结构化事实权威；长期事实、关系清单、角色状态、伏笔与时间线是派生视图，不得手改。
- 修改旧正文、既有大纲或设定前先走 revision-governor 的 plan；关联修改、追踪更新和 verify 未闭环前不得恢复日更。
- 中文正文依次通过语言门、文风卫生、AI 模式与退化检查；Hook 只做机械门禁，不能替代 Skill 流程和语义审查。
- PowerShell Hook 只对 fixture 覆盖的静态重定向及 `Set/Add/Clear-Content`、`Out-File`、`Tee-Object`、`New/Copy/Move/Rename-Item`（含已登记别名）做目标提取；变量拼接、splatting、动态调用、.NET API 或外部程序写盘不属于可靠硬拦截，仍须在 Skill 内先验大纲/追踪并在落盘后复扫。
- 子 Agent 通过 CodeBuddy `Agent` 工具和 `subagent_type` 按 `.codebuddy/agents/*.md` 的物理名称调用；中文主包固定 10 张（8 个通用 + `story-data-fetcher` + `story-data-readonly-runner`），19 张仅是 CodeBuddy 平台容量边界。数据只读 pooled runner 必须按 Skill 映射注入 `logical_role`、Skill 内角色卡路径与完整任务合同，不能把逻辑名当成 registry 名。设置页可见不代表 Task registry 可调度；新会话中必须实际调用。子 Agent 不得递归调用子 Agent；定义或 registry 不可用时按 Skill 合同降级 solo/direct 并明确报告。
