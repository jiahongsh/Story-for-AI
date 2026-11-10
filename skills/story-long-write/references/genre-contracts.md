# 题材契约协议

题材卡回答“正文怎么写”，题材契约回答“哪些承诺必须在大纲、正文和审查中保持一致”。本模块借鉴 InkOS 和 oh-story-claudecode 的题材方法，按本仓库的中文网文流程重新设计，不复制外部代码或文案。

## 内置契约

| `genre_id` | 中文名 | 适用场景 | 契约源 | 正文卡 |
|---|---|---|---|---|
| `dungeon-core` | 地下城核心 | 固定核心、地下城建设、冒险者探索双视角 | [dungeon-core.json](genre-contracts/dungeon-core.json) | `genre-prose-cards/地下城核心.md` |
| `cozy-fantasy` | 温馨奇幻 | 低烈度风险、社区与手艺、关系和归属感推进 | [cozy-fantasy.json](genre-contracts/cozy-fantasy.json) | `genre-prose-cards/温馨奇幻.md` |
| `tower-climber` | 爬塔升级 | 每层独立规则、层级挑战、稳定中型剧情单元 | [tower-climber.json](genre-contracts/tower-climber.json) | `genre-prose-cards/爬塔升级.md` |
| `litrpg` | 数值冒险 | 属性、技能、装备与战斗结果需要可核对的数值因果 | [litrpg.json](genre-contracts/litrpg.json) | `genre-prose-cards/数值冒险.md` |

契约源文件位于 `references/genre-contracts/*.json`，结构权威为 `references/genre-contract.schema.json`。

## Phase 2 物化流程

1. 从 `设定/题材定位.md` 提取主类型、辅类型、市场和语言。
2. 用主类型、别名或 `genre_id` 解析内置契约；不要因为出现“系统”“副本”等单个词就强行命中。
3. 命中后把契约物化为项目文件 `设定/题材契约.json`，保留 `source_contract` 和 `contract_version`。
4. 只在用户设定明确时填写 `project_overrides`；覆盖项不得取消题材的核心读者承诺。
5. 未命中时，按同一 schema 从题材正文卡生成最小契约，`evidence.confidence` 设为 `low`，只写已确认规则。

可用命令：

```bash
for PYBIN in python3 python py; do "$PYBIN" -c "" 2>/dev/null && break; done
"$PYBIN" skills/story-long-write/scripts/genre_contract.py list
"$PYBIN" skills/story-long-write/scripts/genre_contract.py resolve "爬塔"
"$PYBIN" skills/story-long-write/scripts/genre_contract.py materialize "爬塔" "{项目根目录}"
"$PYBIN" skills/story-long-write/scripts/genre_contract.py validate "{项目根目录}/设定/题材契约.json"
```

`materialize` 默认拒绝覆盖已有项目契约；只有用户明确要求重建时才能使用 `--force`。

## 各阶段消费规则

### 总纲与卷纲

- 从 `chapter_types` 选择剧情单元的主要功能，不要求每章机械套类型。
- 把 `pacing_rule` 的阶段里程碑写入总纲或卷纲。
- 数值题材必须先确定 `numerical_system` 和 `power_scaling`，再安排升级。
- 把 `reader_contract` 和 `forbidden_drift` 加入大纲安全审查。

### 细纲

- 每章记录一个主章节类型，可带一个辅类型。
- 明确本章交付的 `satisfaction_types`；过渡章允许小兑现，但不能连续欠债。
- 涉及数值、资源、楼层或建设时，写出前态、动作、代价、后态。

### 正文

- 题材契约只约束因果和承诺，不替代题材正文卡的语言、场景和节奏提示。
- 不把 JSON 字段直接写成说明书式正文。
- 项目明确偏离内置规则时，先更新 `project_overrides` 并说明对读者承诺的影响。

### 审查

- `review_gates` 和明确的 `forbidden_drift` 可形成客观问题。
- 未写入契约的口味判断只能标为 `preference`，不能假装设定冲突。
- 若项目覆盖项与内置契约冲突，以项目覆盖项为当前事实，但必须提示其市场风险。

## 组合题材

只指定一个主契约。辅题材提供补充满足点和场景方法，不得同时加载两套互相冲突的节奏硬门。例如“温馨奇幻＋数值冒险”可以保留轻量成长反馈，但不能让高频数值结算破坏温馨阅读契约。
