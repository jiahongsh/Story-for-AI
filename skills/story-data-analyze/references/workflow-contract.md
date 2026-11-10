# 数据分析多 Agent 工作流合同

> 本文件定义运行时编排、Agent 职责、产物、门禁、回退和降级。指标定义与下钻关系以
> `../dictionary/` 为权威；分析方法与案例以 `数据追踪/knowledge/` 为知识层；任何日报都只是某次
> run 的派生视图。

## 1. 设计原则

1. **唯一编排器**：调用 `story-data-analyze` 的主 Agent 是唯一编排器和最终写入者。子 Agent 不得递归 spawn，也不得相互私下传递结论。
2. **先事实后解释**：抓取、标准化、指标计算、异动解释、文本诊断、监督验收是不同阶段；上一步未过门禁，下步产物无效。
3. **独立复算**：方法校验 Agent 必须从冻结输入重新计算，而不是润色分析 Agent 的答案。
4. **数据与文本分权**：指标分析 Agent 不读正文；文本改进 Agent 只能读取已验证断点对应的正文范围。
5. **监督不替做**：看守 Agent 只验合同、证据链和结论边界，不替分析 Agent 发明新的解释。
6. **不可变证据**：每次尝试写成新 artifact；修正用 `supersedes` 或 `attempt`，不得覆盖旧判断。
7. **修改需可验证授权**：数据分析默认只提交方案。当前运行时只能保存 `UNATTESTED_PROCEDURAL` 程序性记录，没有宿主签名，因此不得自动修改正文、书名、封面、简介、标签或远端状态；详见第 9 节。
8. **知识不混运行**：raw、日报、单次分析、实验运行不进入知识库。只有监督通过且带完整证据的通用方法或案例可以晋升。
9. **样本不可替代**：合格样本分母不可从冻结源取得时，登记“样本不可用”，不得用日阅读、在读、其他资格人群或百分比反推下界占位。
10. **恢复不造事实**：事务恢复只能隔离未提交孤儿和重建已提交 artifact 内嵌的知识文件，不能补写业务阶段、推断缺失证据或替 Agent 作决定。

## 2. 五个角色

### 2.1 `story-data-fetcher`：数据抓取

- 唯一允许执行批准的只读平台抓取命令。
- 核验登录、作品 ID、拉取时间、数据截止日、endpoint 状态和字段存在性。
- 只产出 raw、capture manifest 和 hash，不做“变好/变差”解释。
- 禁止输出登录态文件、cookie、token 或其他凭据；禁止调用后台写接口。

### 2.2 `story-data-metrics-analyst`：指标分析

- 输入必须是已冻结、已通过质量门的事实表与指标字典版本。
- 按指标树从结果节点下钻到驱动节点、诊断节点和护栏节点。
- 识别数据异动、流量异动、转化异动、滚动窗异动和互动异动。
- 输出异常节点、联查结果、首要约束、次要风险、候选机制和证据等级。
- 禁止读取正文、提出具体改文、使用“平台算法一定如何”的未经证实说法。

### 2.3 `story-data-method-validator`：方法与计算校验

- 独立读取同一冻结输入和指标字典，不继承 analyst 的隐含推理。
- 从 raw/normalized 冻结文件与每条事实的 JSON Pointer、source observation、calculation expression 重新读取并复算全部 metric fact；不能把 analyst 或 metric engine 回填的 `recalculated_value` 当证据。
- 复核分子/分母、窗口、去重、滚动窗、`null/0/missing`、版本覆盖、渠道可比性、样本量、MDE、置信区间和替代解释。
- 检查 analyst 是否沿指标树完成了必查邻接节点，是否越过证据等级。
- 输出 `PASS / REWORK / BLOCK`，并指出最早出错阶段。
- 禁止读取正文或替 analyst 给文本解释。

### 2.4 `story-data-text-improvement-planner`：文本定位与改进实验

- 只有 `ANALYSIS_VERIFIED` 后才能执行。
- 按已验证断点读取线上对应版本的具体文件、章节、段落和上下游承诺。
- 证明“数据断点 → 可观察文本问题 → 读者决策机制 → 单变量修改 → 目标指标”的闭环。
- 输出最小修改方案、反事实、主指标、护栏、MDE、验证窗口与回滚条件。
- 默认只读，绝不直接改正文；当前只交付人工修改清单。只有未来宿主能提供 `HOST_ATTESTED` 授权时，主 Agent 才可按精确 scope 路由长篇或短篇写作 Skill。

### 2.5 `story-data-supervisor`：全流程看守

- 检查所有 lane 的 `run_id`、schema、输入 hash、产物 hash、阶段状态和引用闭合。
- 验收六问是否回答、指标树是否覆盖、文本证据是否位于流失前、修改是否单变量、护栏是否完整。
- 输出 `PASS / RETURN / BLOCKED`；`RETURN` 必须指向最早错误阶段，不得只说“再分析一下”。
- 不 spawn、不抓取、不替任何 lane 重算或重写；最多允许三轮回退，随后 `BLOCKED` 并列出需要的外部信息。

## 3. 统一输入合同

调用任一角色时，主 Agent 必须提供自包含输入：

```json
{
  "schema_version": 1,
  "run_id": "fanqie-1000000000000000000-20260812T120000+0800",
  "lane": "metrics_analysis",
  "mode": "latest|snapshot|method_only",
  "project_abs_path": "/absolute/project/path",
  "platform": "fanqie",
  "work_type": "LONG_NOVEL|SHORT_STORY",
  "work_id": "1000000000000000000",
  "question": "改版后前三章是否改善",
  "data_cutoff_expected": "2026-08-11",
  "immutable_inputs": [
    {"path": "/absolute/path", "sha256": "..."}
  ],
  "change_event": {
    "what": "第1章结尾修改",
    "published_at": "2026-08-08T01:19:00+08:00",
    "target_metric_ids": ["fanqie.long.chapter.follow_rate"],
    "guard_metric_ids": [],
    "confounders": []
  },
  "allowed_outputs": [],
  "forbidden_paths": [],
  "canonical_references": [],
  "prior_artifact": {"path": "...", "sha256": "..."},
  "fallback_context": "缺字段时允许输出什么，禁止补猜什么"
}
```

不得依赖“你已经知道我们昨天改了什么”之类会话隐含上下文。

## 4. 统一输出合同

所有角色只返回一个 JSON envelope：

```json
{
  "schema_version": 1,
  "run_id": "...",
  "role": "story-data-metrics-analyst",
  "status": "success|partial|blocked|failed",
  "input_hashes": {},
  "source_files": [],
  "artifacts_written": [],
  "data_until": "2026-08-11",
  "findings": [
    {
      "id": "F-001",
      "severity": "S1|S2|S3|S4",
      "evidence_type": "OBSERVED|DERIVED|ASSOCIATION|HYPOTHESIS|CAUSAL",
      "location": "metric_id or text location",
      "evidence": [],
      "issue": "...",
      "action": "...",
      "confidence": "low|medium|high"
    }
  ],
  "gaps": [],
  "handoff": {}
}
```

角色专属字段由 `contracts/` 中的 schema 约束。格式错误、hash 不一致或缺少引用的输出一律视为 lane 失败。

## 5. 运行状态机

权威目录：`数据追踪/analysis-runs/<run_id>/`。

```text
INIT
  ↓
RAW_CAPTURED
  ↓ G1 数据存在、作品正确、hash 固定
DATA_QUALIFIED
  ↓ G2 刷新/口径/完整性/内部一致性可用
WINDOW_BOUND
  ↓ G3 改动版本与观测窗口可比较
METRICS_READY
  ↓ G4 指标树要求的事实和派生值齐备
ANALYZED
  ↓ G5 analyst 输出完整
ANALYSIS_VERIFIED
  ↓ G6 validator PASS
TEXT_DIAGNOSED
  ↓ G7 文本证据、机制、单变量实验齐备
SUPERVISED
  ↓ G8 supervisor PASS
REPORT_COMPLETE
```

`LOGIN_INVALID / PLATFORM_NOT_UPDATED / SCOPE_UNKNOWN / CORRUPT` 不能越过 G2。`PARTIAL` 只有在列出 `usable_fields` 且后续问题完全落在这些字段内时才可继续。

### 样本不可用状态

样本门使用的必须是与问题同 cohort、同口径、可从冻结源复算且全部证据为权威的分母。若不存在：

```text
sample_size_qualified     = false
sample_size               = 0
sample_size_authoritative = false
sample_aggregation        = unavailable
sample_unavailability_reasons = [至少一条明确原因]
analysis.sample_metric_id = UNAVAILABLE
```

此时 `sample_size=0` 只编码“合格样本不可得”，不表示真实读者为零；`sample_size_evidence` 必须为空，禁止引用替代计数。analysis 只能给 `样本不足/SAMPLE_INSUFFICIENT`，不得触发异常阈值、强结论或因果归因。由展示百分比反推的 `minimum_compatible_*_lower_bound` 是 `display_only/non-authoritative/not-an-estimate`，同样禁止充当样本、显著性分母、绝对人数或跨快照增量。

### 改动覆盖日期

`published_at` 必须带时区，工作流先转换为 `Asia/Shanghai` 后机械推导：

```text
first_covered_data_date = 上海本地发布日期
first_full_data_date    = 若本地时间恰为 00:00:00，则为同日；否则为次日
```

最新快照的 `data_until` 决定且只能决定以下三个有效覆盖结果：

```text
data_until < first_covered                 → NOT_COVERED
first_covered ≤ data_until < first_full    → PARTIAL_DAY_COVERED
data_until ≥ first_full                    → FULL_DAY_COVERED
```

覆盖日只说明统计窗口是否可能包含新版，不替代线上版本核验。`version_status` 与非空 `version_evidence/coverage_evidence` 仍须独立提供；`PARTIAL_DAY_COVERED` 不能冒充完整自然日。

### 回退

- validator 或 supervisor 发现错误时必须写 `RETURN` artifact，包含 `earliest_fault_state`、`root_cause_id`、`error_code`、`rejected_finding_ids` 和非空 `repair_requirements`。
- 主 Agent 从最早错误阶段新建 `attempt-NN`，后续旧 attempt 保留但不再作为有效输入。
- 整个 run 的 validator/supervisor `RETURN` **合计最多 3 次**；这是全局额度，不因角色、阶段或根因不同而重置。工作流同时保留 `return_counts_by_root_cause` 供诊断，但全局 `return_count` 达到 3 后下一次退回直接 `BLOCKED`，禁止通过改根因 ID 绕过。

### 只观察分支

用户只要日报或没有可执行文本异常时，仍需走到 supervisor；文本诊断可产出 `NOT_APPLICABLE` artifact，说明为什么无需读正文，然后完成报告。

## 6. Wave 编排

为保证独立性又不浪费并发槽：

1. **Wave A（串行）**：fetcher → 确定性标准化/质量校验。
2. **Wave B（串行）**：metrics analyst。
3. **Wave C（串行）**：method validator 独立复算并 PASS。
4. **Wave D（串行）**：text planner 只在 validator PASS 后读取指定正文；此前最多预载不含正文的方法，不能形成有效 artifact。
5. **Wave E（串行）**：supervisor。
6. **Wave F（主 Agent）**：渲染日报、追加日志、交付人工修改清单；当前不自动另开改文/发布流程。未来只有宿主提供 `HOST_ATTESTED` 授权时才可进入受信执行流程。

各角色返回统一 envelope，而事务 CLI 记录角色专属 lane payload。主 Agent 必须使用确定性 adapter 先校验 `run_id/role/status/input_hashes`，再提取合同规定的 lane 对象；禁止把整个响应原样记录。子 Agent 不得再 spawn。

## 7. 八道门禁

| Gate | 必须满足 | 失败动作 |
|---|---|---|
| G1 Capture | 作品 ID、截止日、拉取时间、raw hash、endpoint 状态存在 | 回抓取 |
| G2 Quality | `0/null/missing` 已区分；数据已刷新；公式/范围可用 | 停止或限定字段 |
| G3 Window | 改动时间、线上版本、首个覆盖窗口、基线和干扰项已登记 | 补事件/版本 |
| G4 Metrics | 指标目录版本固定；分子分母、维度、时间窗、联查指标齐备 | 回标准化/派生 |
| G5 Analysis | 异动规则、唯一事实 selector、可复算 delta、效应、历史噪声、候选解释和优先级完整 | 回 analyst |
| G6 Validation | 从冻结源独立复算全部事实且一致；证据等级没有越权；必查邻接节点无遗漏 | 回最早错误阶段 |
| G7 Text | 线上版本可确认；读到具体位置；机制在流失前；方案单变量且有护栏 | 回文本诊断 |
| G8 Supervision | hash 链闭合；所有结论有证据；报告不超出可判边界 | RETURN 或 BLOCKED |

## 8. 异动事实绑定与独立复算

每条 anomaly 必须带 `baseline_fact` 和 `current_fact` selector。selector 由 `metric_id + 完整 dimensions` 构成，并且各自在冻结的 metrics facts 中唯一命中一行。运行时强制：

```text
baseline    = baseline_fact.value
current     = current_fact.value
delta       = current - baseline
effect_size = 同一带符号、保留原单位的 delta
direction   = UP / DOWN / FLAT，由 delta 确定
```

selector 命中 0 行或多行、事实非数值、手抄值与事实不一致、delta 或 direction 不能复算时，G5 失败。`MIXED` 可以出现在 schema 词表中，但单一事实对的机械差值不能用它逃避方向校验。

G5 还强制 `analysis.change_assessments[]` 与 `window_bound.changes[]` 一一对应：不得漏评、多评或虚构 `change_id`，评估指标只能来自该改动的 `target_metric_ids`，覆盖与版本状态必须等于 G3 的机械结果。每个改动只能取受控状态之一。改善/恶化必须同时满足：完整日覆盖、线上版本 `VERIFIED`、目标指标异动已触发，并且异动方向符合指标目录的 `preferred_direction_by_metric`。未覆盖改动必须为 `CHANGE_NOT_COVERED + UNKNOWN`；不合格或小于 30 的样本不得输出改善/恶化。

validator PASS 时必须覆盖 metrics artifact 中**每一条** fact。对每条 fact，它重新打开已冻结 raw/normalized/window 源，按记录的 JSON Pointer 读取 source observations，并按同一 calculation expression 复算；`metric_id + dimensions`、source refs、observations、formula、calculation 与复算值都要一致。只复制 analyst/metric engine 输出、遗漏任一 fact 或存在 `recalculation_disagreements` 都不能 PASS。

## 9. 授权与机械 hook 边界

### 9.1 当前授权保证

authorization artifact 可绑定 `user_event_id + user_message_sha256 + run_id + chain_head + proposal/action/target/hash`，但本运行时只能写：

```text
attestation_status = UNATTESTED_PROCEDURAL
```

它是可审计的程序性记录，不是宿主签名，也不能证明事件确由用户在受信 UI 中发出。自动执行检查要求 `HOST_ATTESTED`；当前运行时不能铸造该状态。因此即使程序记录为 `APPROVED`，也禁止自动改文、改包装或发布。合法交付是方案与人工操作清单；只有未来由宿主提供不可伪造事件凭证并重新授权，才可启用自动执行。

### 9.2 hook 边界

hook 是防误操作/低成本绕过的事故防护，不是安全沙箱，也不是权限边界：

- 在 hook 实际覆盖的工具调用中，拦截对 `数据追踪/analysis-runs/` manifest 和不可变 artifacts 的直接改写。
- 在 hook 实际覆盖的工具调用中，拦截绕过晋升命令写入 `数据追踪/knowledge/` 的操作。
- 带 `--analysis-run <id>` 的改文或发布操作，即使存在完整程序性 authorization artifact 和已通过 gate，也会因为缺少 `HOST_ATTESTED` 而保持不可自动执行；命令标签本身不是授权。
- 不得因为存在未完成的数据 run 而阻断普通日更或用户独立发文。
- 对受保护路径解析失败时 fail closed；对无关操作 fail open。
- Session/Stop 只能提示未完成阶段，不能自动补状态或偷偷发布。

能绕开本地 hook 的进程、手工文件操作或被攻陷的宿主仍可能改写文件；不要把 hook 描述成抵御恶意操作者、保护凭据或提供系统级隔离。

## 10. 事务写入与 recover

阶段 artifact 先以唯一 `attempt` 文件落盘，再由 manifest revision/hash chain 提交。未被 manifest 引用的 `*.attempt-*.json` 视为崩溃孤儿，正常校验 fail closed。使用：

```bash
for PYBIN in python3 python py; do "$PYBIN" -c "" 2>/dev/null && break; done
"$PYBIN" skills/story-data-analyze/scripts/data_workflow.py recover --run-id <run_id>
```

recover 在 run lock 下执行两类且仅两类确定性修复：

1. 将未提交孤儿移动到 `analysis-runs/<run_id>/recovery/<timestamp>/` 隔离保存，不删除、不纳入有效链；
2. 若已提交的 case/method promotion artifact 存在、hash 链有效，而目标知识文件缺失，则只从 artifact 中内嵌且 hash 匹配的 `knowledge_document` 原样重建。

recover 不修改已提交 artifact、不推断缺失 Agent 输出、不增加 RETURN、不推进业务 state。链无效、目标越出规范知识目录或内嵌文档 hash 不匹配时必须停止。

## 11. 知识晋升复现门

`outcome_unverified` 与高质量无法判断案例可以在监督后沉淀，但不得标成效果已验证。`verified_improvement / verified_regression / verified_no_effect` 至少要求两个不同的完整验证 run，并且每个 run 都须：

- `REPORT_COMPLETE + supervisor PASS + validator PASS`；
- 同一 `change_id`、`FULL_DAY_COVERED`、`version_status=VERIFIED`；
- `sample_size_qualified=true`、权威样本 `≥100`；
- MDE 已评估、护栏通过、结果状态方向一致。

“不同 run ID”不等于不同复现。工作流以 `(latest_snapshot.source_sha256, latest_snapshot.data_until)` 作为冻结最新窗口键；两个 run 使用同一键只算一次，`replicated_windows` 必须等于不同窗口键数量。

## 12. 降级矩阵

| 缺失能力 | 允许交付 | 禁止声称 |
|---|---|---|
| fetcher 不可用 | 分析用户指定的冻结快照 | “这是最新数据” |
| analyst 不可用 | 主 Agent 按目录确定性计算，标 `solo` | 多 Agent 独立分析 |
| validator 不可用 | 事实和派生值、低强度方向 | `ANALYSIS_VERIFIED`、强归因 |
| text planner 不可用 | 指标断点和需阅读范围 | 具体改文已经验证合理 |
| supervisor 不可用 | 草稿报告，标 `Independent Gate: NOT_RUN` | 全流程验收通过 |

## 13. 完成标准

一次 run 只有同时满足以下条件才算完成：

- 使用了固定版本的指标目录、指标树、诊断路由和方法知识；
- raw 与全部有效产物有可复核 hash 链；
- 每个关键变化都能回答“变化的是哪个对象、事件、口径、窗口和维度”；
- 每个异常节点都完成规定的横向联查和纵向下钻；
- 需要改文时，读到了确切线上版本对应的章/段，方案能解释如何改变读者当下决策；
- 监督 Agent 给出 PASS，或报告明确写出降级能力和不可判事项；
- 没有把观察相关写成因果；当前无宿主签名条件下，没有自动修改正文、包装或远端状态。
