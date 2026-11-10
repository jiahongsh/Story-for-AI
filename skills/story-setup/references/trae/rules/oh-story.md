---
description: oh-story 中文网文项目的路由、大纲、追踪与正文门禁。
globs: "**/*.md,**/*.json"
alwaysApply: false
---

<!-- oh-story-managed: rule/oh-story -->

# oh-story 项目规则

- 任务匹配 `story-*` 或 `browser-cdp` 时，先完整读取 `.trae/skills/<skill-name>/SKILL.md`，再按其路由读取必要 references。
- 写正文前必须存在对应大纲：长篇为 `大纲/细纲_第N章*.md`，短篇为 `小节大纲.md`。
- 长篇续写先读 `追踪/上下文.md`；修改已提交正文、大纲或设定时，先执行 revision-governor 计划门，闭环验证前不得恢复日更。
- “续写/继续写/日更”只授权生成精确下一章候选稿；只有用户明确接受、定稿或事先授权自动定稿时，才能晋升到 `正文/` 并提交追踪。
- 中文正文落盘后，先通过 language gate 与 style-hygiene gate，再运行其他审查；未授权外语或 HTML 命中时禁止交付。
- Hooks 只是机械守卫，不替代 Skill 流程和语义审查。
