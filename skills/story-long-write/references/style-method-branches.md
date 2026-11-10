# 中文写作方法双分支与作者文风蒸馏

本协议管理正文写作时“方法从哪里来、怎样进入运行时”。它不管理剧情正史，不替代细纲、连续性、题材契约、情绪模块、节奏索引或本书已接纳声音画像。

## 分支总览

### A-standard：标准直载

- 没有 `设定/写作方法.json` 的旧项目自动使用本分支，现有行为不变。
- 每章直接召回对标 `剧情/情绪模块.md`、`剧情/节奏.md`、`文风.md`、匹配章技巧与少量锚点。
- 有实质内容的 `设定/文风.md` 仍是本书权威风格基；对标文风降为参考。
- 本分支不需要编译方法包，适合对标材料少、尚未建立合格跨作品语料或希望快速起步的项目。

### B-distilled：蒸馏编译

- 只在用户明确选择并完成 `qualify → compile → 前向盲测 → bind` 后启用。
- 每章只解析最多八条与场景匹配的抽象规则，不把语料原文、锚点、来源名或标志性表达交给正文写作者。
- 仍需读取本章情绪模块、节奏索引、题材正文提示卡和本书已接纳/黄金声音画像；B 只替换 A 的“对标文风与原文锚点直载”部分。
- 配置明确写着 B 时，编译包、清单、盲测或哈希任一失效都必须停止写作，不得静默回退 A。

运行时优先级：连续性/细纲/题材契约 > 本章情绪与节奏 > 本书自定义文风 > 已接纳与黄金声音画像 > 编译方法 > 通用写作建议。声音画像仍是 advisory；遇到有意的场景变奏时做语义冷读，不为贴均值机械改句。

## B 分支的三类语料

| 类型 | 用途 | 能否绑定生产项目 |
|------|------|------------------|
| `single-work-pilot` | 单书探索规则、验证拆解方法 | 否；无论样本多长都不能冒充可复用方法 |
| `shelf-corpus` | 同一货架、至少三位作者的可迁移机制 | 通过全部门禁后可以 |
| `author-corpus` | 同一作者至少三部作品的跨作品机制 | 通过全部门禁后可以 |

`author-corpus` 再分两种：

- `author-mechanics`：只保留抽象机制，写作端隐藏来源名，必须通过来源隐匿评测。
- `authorized-fidelity`：只允许本人作品、明确授权或公版作品，必须完成高保真授权确认和盲归因评测。

两种模式都禁止把标志性表达、原句、桥段顺序或专名编译进方法。

## 目录与生命周期

语料目录属于用户项目数据，不进入通用工具包：

```text
文风语料/{corpus-id}/
├── corpus-manifest.json
├── work-mechanics-packs/
│   ├── {work-id}.json
│   └── ...
├── author-style-pack.json          # 仅 author-corpus
├── distillability-decision.json    # qualify 生成，不手改
└── compiled/
    ├── compiled-method.json        # compile 生成
    ├── compiled-manifest.json      # compile 生成
    └── forward-test.json           # 独立盲测完成后填写
```

绑定后项目只复制抽象产物：

```text
{作品}/设定/
├── 写作方法.json
└── 写作方法/
    ├── compiled-method.json
    ├── compiled-manifest.json
    └── forward-test.json
```

原始语料、拆文原文和作品机制包不复制进写作项目运行时。工具代码只保存 schema、算法和门禁，不保存具体作品事实。

## 语料清单

`corpus-manifest.json` 顶层字段固定如下：

```json
{
  "schema_version": 1,
  "corpus_id": "urban-family-author-v1",
  "corpus_type": "author-corpus",
  "author_style_mode": "author-mechanics",
  "authorization": {
    "lawful_access_confirmed": true,
    "rights_basis": "lawfully-held-analysis",
    "authorized_fidelity_confirmed": false
  },
  "works": [
    {
      "work_id": "work-01",
      "title": "作品一",
      "author_id": "target-author",
      "series_id": null,
      "char_count": 60000,
      "chapter_count": 20,
      "split": "train",
      "source_sha256": "<64位小写sha256>"
    }
  ],
  "control_authors": [
    {"author_id": "control-01", "work_count": 1, "char_count": 30000},
    {"author_id": "control-02", "work_count": 1, "char_count": 30000}
  ],
  "scene_function_coverage": ["opening", "escalation", "turning-point", "aftermath"],
  "anti_copy": {
    "store_source_text": false,
    "compile_distinctive_expressions": false,
    "phrase_overlap_gate": true,
    "plot_independence_gate": true
  },
  "control_separation_confirmed": true,
  "forward_test_plan": {
    "compare_against": "A-standard",
    "minimum_samples": 6,
    "blind_reviewers": 2
  }
}
```

可复用语料的硬下限：至少三部作品、总计五万个中文字符，同时保留 `train`、`calibration`、`holdout`；每个作品机制包至少抽三章、六个场景。`shelf-corpus` 至少三位作者；`author-corpus` 的目标作品必须同一作者、至少覆盖两个系列或独立作品桶，并登记至少两位邻近控制作者。`series_id` 必须显式填写，独立作品使用 `null`。

## 作品机制包

每部作品一份 JSON，只存抽象机制和可回查位置，不存原文：

```json
{
  "schema_version": 1,
  "work_id": "work-01",
  "source_sha256": "<与语料清单一致>",
  "split": "train",
  "sampled_chapter_count": 6,
  "sampled_scene_count": 12,
  "scene_functions": ["opening", "escalation", "turning-point", "aftermath"],
  "rules": [
    {
      "rule_key": "pressure-dialogue-compression",
      "dimension": "dialogue",
      "instruction": "高压对峙时缩短问答回合，让动作承担未说出口的抵抗。",
      "applies_to": ["高压", "对峙"],
      "avoid": "不要把人物的真实意图补成解释性旁白。",
      "priority": 80,
      "evidence_locators": [
        {"chapter": 3, "scene": "第一次正面对峙", "paragraph": "中段"}
      ]
    }
  ]
}
```

允许的 `dimension`：`sentence-rhythm`、`paragraph-breathing`、`dialogue`、`narrative-distance`、`sensory-selection`、`emotion-landing`、`figurative-language`、`information-release`、`transition`、`scene-engine`、`chapter-ending`。

同一 `rule_key` 在不同作品中必须表达同一条规则。编译器只接纳同时在训练、校准、留出作品中稳定出现的规则；货架语料还要求至少三位作者共同支撑。

## 作者文风包

`author-corpus` 额外需要 `author-style-pack.json`：

```json
{
  "schema_version": 1,
  "target_author_id": "target-author",
  "mode": "author-mechanics",
  "feature_families": [
    "sentence-rhythm", "paragraph-breathing", "dialogue-ratio", "dialogue-tags",
    "narrative-distance", "sensory-selection", "emotion-landing", "figurative-density",
    "information-release", "transition", "chapter-ending"
  ],
  "rules": [
    {
      "rule_key": "author-transition-object-carry",
      "dimension": "transition",
      "instruction": "场景切换优先让上一场留下的物件或动作进入下一场，少用时间总结句。",
      "applies_to": ["转场"],
      "avoid": "不要复刻任何作品中的专名物件。",
      "priority": 70,
      "support_work_ids": ["work-01", "work-02", "work-03"],
      "control_author_ids": ["control-01", "control-02"]
    }
  ],
  "evaluations": {
    "holdout-style-separation": "passed",
    "content-preservation": "passed",
    "chinese-naturalness": "passed",
    "phrase-overlap": "passed",
    "plot-independence": "passed",
    "source-obscurity": "passed"
  },
  "source_names_visible_to_writer": false,
  "distinctive_expression_allowed": false
}
```

`authorized-fidelity` 把 `source-obscurity` 换成 `blind-attribution`，并把 `source_names_visible_to_writer` 设为 `true`；运行时仍不携带原文和标志性表达。

## 操作流程

先探测可用 Python，所有命令都从当前 `story-long-write` skill 的 `scripts/` 执行：

```bash
for PYBIN in python3 python py; do "$PYBIN" -c "" 2>/dev/null && break; done

"$PYBIN" scripts/style_method.py qualify \
  --corpus "文风语料/{corpus-id}" --confirm QUALIFY

"$PYBIN" scripts/style_method.py compile \
  --corpus "文风语料/{corpus-id}" --confirm COMPILE
```

`qualify` 每次重新读取清单和机制包，生成带输入哈希的 `distillability-decision.json`。之后任何输入变化都会使判定过期；必须重新 qualify，不能复用旧审批。

`compile` 只生成待评估候选，不自动启用。随后用同一批互不泄漏的细纲分别生成 A、B 候选，至少六组、两位独立冷读者，先盲读再揭晓。`compiled/forward-test.json` 格式：

```json
{
  "schema_version": 1,
  "method_sha256": "<compiled-method.json 的 sha256>",
  "test_id": "forward-001",
  "sample_count": 6,
  "blind_reviewer_count": 2,
  "baseline": "A-standard",
  "candidate": "B-distilled",
  "metrics": {
    "content_preservation_pass": true,
    "chinese_naturalness_pass": true,
    "phrase_overlap_pass": true,
    "plot_independence_pass": true,
    "b_preference_rate": 0.67
  },
  "status": "passed",
  "review_completed": true
}
```

只有内容保真、中文自然度、短语重合、剧情独立四项都通过，且 B 盲审偏好率不低于 55%，才能绑定：

```bash
"$PYBIN" scripts/style_method.py bind \
  --project "{作品目录}" \
  --compiled "文风语料/{corpus-id}/compiled" \
  --confirm BIND \
  --note "用户确认启用本方法"
```

显式切回 A：

```bash
"$PYBIN" scripts/style_method.py standard \
  --project "{作品目录}" --confirm STANDARD
```

## 每章运行时

写候选章之前，先根据细纲提取三到六个场景标签，再运行：

```bash
"$PYBIN" scripts/style_method.py resolve \
  --project "{作品目录}" \
  --scene-tag "高压" --scene-tag "对峙"
```

- 返回 `A-standard`：继续现有 `benchmark_style_load`，行为不变。
- 返回 `B-distilled`：不读取对标 `文风.md` 和原文锚点；把 `selected_rules` 作为 `compiled_method_packet` 交给写作者，同时单独加载情绪模块、节奏、题材卡和声音画像。
- B 每章最多十二条，默认八条；不得把整份方法包塞进 prompt。

`chapter_candidate.py check` 与 `story_doctor.py` 都会运行 `style_method.py check`。配置缺失时它们接受隐式 A；显式 B 失效时二者都会阻断。

## 负向边界

- 不从单部作品编译可复用作者方法。
- 不用同一系列三部作品替代跨作品控制；同系列可以进入探索，但不能自动证明作者独有机制。
- 不把来源原文、长摘录、专名、标志性台词和独特桥段写进任何机制包或编译方法。
- 不因 B 已通过一次盲测就永久有效；语料、规则、算法或编译包变化后重新 qualify、compile、盲测和 bind。
- 不让 B 覆盖本章细纲、连续性、题材契约和用户明确写入的 `设定/文风.md`。
- A/B 前向测试的候选编号只是盲测标签，不等于剧情分支，也不进入正史追踪。
