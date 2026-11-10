# story-data-analyze artifact contracts

这些 JSON Schema 是 Agent 之间的结构合同，不是提示词示例。真正的运行时硬门由
`scripts/data_workflow.py` 的确定性 validator 执行：除结构外，它还会回读源文件、
重算 hash/公式、重放状态机并核验角色分离。Schema 与运行时 required 字段由测试保持
同步；不能把“JSON 外形合法”误写成“业务证据已通过”。

- `run.schema.json`：`数据追踪/analysis-runs/<run_id>/manifest.json` 的事务清单与状态机。
- `artifact-envelope.schema.json`：每个不可变 attempt 的哈希链信封。
- `raw-capture.schema.json`、`data-quality.schema.json`：抓取与质量门。
- `normalized-snapshot.schema.json`、`window-bound.schema.json`、`metrics.schema.json`：三种原始形态归一化、改动窗口绑定与指标事实。
- `analysis.schema.json`、`validation.schema.json`、`text-diagnosis.schema.json`、`supervision.schema.json`：四个推理阶段。
- `report.schema.json`：仅在观察型 supervisor PASS 后生成的最终报告。
- `authorization.schema.json`：把用户表意与 run/proposal/target/hash 绑定的程序性记录；当前宿主无不可伪造的事件签名，所以只允许 `UNATTESTED_PROCEDURAL`，不是自动改文/发布授权。
- `case.schema.json`：只有完整通过监督的 run 才能晋升为知识案例。
- `method.schema.json`：分析方法的版本化晋升合同；同一版本不可覆盖，后续版本必须声明 `supersedes`。

运行时由 `scripts/data_workflow.py` 做标准库内的关键字段和语义校验；Schema 用于跨 Agent 交接、外部工具校验和版本审计。
