# 顺序冷读与滚动账本协议

顺序冷读用于发现扫描器和按点查询看不到的跨章阅读问题。它按第一次读书的方式从前往后读，不能跳章、倒序补读，也不能先看问题清单后只找证据。自动检测器只作回归围栏，不替代发现。

## 触发门槛

- 一卷结束、开始下一卷前：必做本卷范围顺序冷读。
- 大规模回修、身份/血缘/规则重构后：对受影响最早章到当前章做顺序冷读。
- 发布关键批次前，或数据分析指向“找不到单章断点但整体回访下降”时：按问题范围执行。
- 普通单章日更不全书冷读；继续使用续写状态卡和定点事实索引。

## 四本滚动账

每读完一章，同时登记本章造成的变化；没有变化也传空列表：

- `clock`：故事时间、等待时长、路程、昼夜和同场顺序。
- `promises`：正文向读者承诺、兑现、延迟或违约的期待与伏笔。
- `knowledge`：角色知道什么、读者知道什么、作者真相是什么，防止提前知道或重复震惊。
- `props`：关键物件、证据、伤势、权限和唯一所有权的持有/去向。

发现的问题写入 `issues`，使用稳定 ID、`S1-S4`、精确位置和可验证描述。`issues.jsonl` 只追加 opened/resolved 事件；不删除旧问题来制造“没有发现过”。

## 命令

初始化：

下列命令中的 `{PYTHON}` 先按平台探测可用的 Python 3 解释器，再用实际命令替换。

```bash
{PYTHON} skills/story-long-write/scripts/cold_read_ledger.py init \
  --project "{项目根}" --from-chapter {A} --to-chapter {B}
```

每读完游标的下一章，构造 JSON：

```json
{
  "chapter": 1,
  "reader_note": "只写这一章给首次阅读造成的实际感受和疑问",
  "clock": [],
  "promises": [],
  "knowledge": [],
  "props": [],
  "issues": [
    {
      "id": "CR001",
      "severity": "S2",
      "type": "knowledge-leak",
      "location": "第1章末段",
      "description": "角色引用了尚未获得的信息"
    }
  ]
}
```

```bash
{PYTHON} skills/story-long-write/scripts/cold_read_ledger.py record \
  --run "{冷读运行目录}" --input "{本章记录.json}"
```

脚本只接受 `cursor + 1`，并对每章记录做摘要绑定。问题修复并经修订门禁闭环后追加解决事件：

```bash
{PYTHON} skills/story-long-write/scripts/cold_read_ledger.py resolve \
  --run "{冷读运行目录}" --issue-id CR001 --resolution "{修复证据}"
```

全部读完后：

```bash
{PYTHON} skills/story-long-write/scripts/cold_read_ledger.py check --run "{冷读运行目录}"
{PYTHON} skills/story-long-write/scripts/cold_read_ledger.py close --run "{冷读运行目录}" --confirm CLOSE
{PYTHON} skills/story-long-write/scripts/story_doctor.py \
  --project "{项目根}" --cold-read-from {A} --require-cold-read-through {B}
```

未读完、章节记录被改、或仍有未解决 S1/S2 时 `close` 失败。S3/S4 可以带入报告，但必须成为下一卷规划或修订清单的明确输入，不能在报告中消失。
