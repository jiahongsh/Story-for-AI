# 可执行审查包契约

工具：scripts/world_gate.py，Python 3.10+，仅标准库。它只做结构、来源、新鲜度和人工审查记录检查，不能由非空文本证明人物有真实思想，不能证明已列清全部人物，也不替代逐句因果/声线审查。STRUCTURAL_CHECK_PASS 是这些有限检查的结论，不是文学质量保证或正史接纳许可。

## 命令与退出码

--project 为书目录，不是整个工具仓库。来源、包、正文使用书目录内相对路径；原追踪校验器允许在项目外。

~~~powershell
python scripts/world_gate.py init --project D:/code/stroy/他们不是人 --chapter 16 --mode continuation --tracking-tool D:/code/stroy/skills/story-long-write/scripts/tracking_commit.py --source 大纲/细纲_第016章.md --source 设定/角色/镜辞.md --packet .story/世界引擎/第016章/写前行动审查.json
python scripts/world_gate.py check --project D:/code/stroy/他们不是人 --packet .story/世界引擎/第016章/写前行动审查.json --phase prewrite --tracking-tool D:/code/stroy/skills/story-long-write/scripts/tracking_commit.py
python scripts/world_gate.py check --project D:/code/stroy/他们不是人 --packet .story/世界引擎/第016章/写后行动复核.json --phase postwrite --tracking-tool D:/code/stroy/skills/story-long-write/scripts/tracking_commit.py
python scripts/world_gate.py export --project D:/code/stroy/他们不是人 --start 1 --end 15 --output .story/派生视图 --tracking-tool D:/code/stroy/skills/story-long-write/scripts/tracking_commit.py
~~~

示例角色/细纲路径须替换为实际存在文件。init 可直接写 `.story/世界引擎/`、`.story/work/`、`创作运行/` 或 `追踪/候选章/` 内的附属 JSON（禁止写入 `.story/作者记忆/`、`.story/排纲笔记/`、正文、大纲、设定或追踪权威）；不覆盖已有包。改变计划创建新包、重新审查，不能覆盖已经冻结的写前包。

- init 成功：退出 0，TEMPLATE_CREATED_UNREVIEWED；字段空、审查未通过，**不是写作通行证**。
- check 成功：退出 0，JSON status=STRUCTURAL_CHECK_PASS、phase、packet_sha256、errors=[]、semantic_limit。
- export 成功：退出 0，DERIVED_VIEWS_EXPORTED，列输出位置、文件数、修订号和资料不足限度。
- 校验或路径错误：退出 2，status=FAIL，errors 给原因；命令行用法错误由 argparse 返回 2。
- mode=planning 允许未初始化追踪的新书规划，不冒充正史；存在 tracking 则必须校验。continuation 仅精确下一章；revision 仅已提交章，仍服从原修订批准流程。

正式续写/修订/export 只读调用原 tracking_commit.py.check_project，支持 schema 4（当前 story-long-write 权威）与 schema 5 权威及派生视图同步。坏 JSON、缺合法 authority、原工具不可用均失败。工具不迁移、不补写 tracking，不另设 world-state。

工具发现优先显式 --tracking-tool，其次书目录/祖先工具仓库中的 `skills/story-long-write/scripts/tracking_commit.py` 或 `.workbuddy/skills/story-long-write/...`，然后已安装技能（同级、用户 .agents/skills、.codex/skills 与 .workbuddy/skills）。前包 init 和后续流程必须选同一个原工具路径，不能通过换校验器偷偷更换冻结基线。

## 冻结基线与来源

根字段：

~~~json
{
  "schema_version": 1,
  "mode": "continuation",
  "chapter": 100,
  "binding": {
    "tracking": {"path": "追踪/_tracking-state.json", "sha256": "原文件SHA256", "state_revision": 43, "last_committed_chapter": 99},
    "tracking_tool": {"path": "原工具绝对路径", "sha256": "原工具SHA256"}
  },
  "sources": [{"id": "SRC1", "path": "实际项目内文件.md", "sha256": "文件SHA256", "scope": "mixed"}]
}
~~~

init 自动填基线和 --source 文件 hash。新书无追踪时 tracking/tracking_tool 均 null。来源、追踪、原校验器改变后旧包失效，不能只改 hash 冒充重新审查。

scope 为 author（作者秘密）、reader（读者已知材料）、mixed（含多种信息，逐引用识别）、planned（本章先行行动规划）。init 默认 mixed 不意味着人物自动知道。人物为何能够获取仍须 acquisition 和人工复核。author 来源不能作人物知识证据，禁止重标 mixed 绕过。

## 行动者与场景

actors 每项：

- id 唯一、name 实际人物名、protagonist 布尔值。
- own_goal 为当前自己的目标；without_protagonist 为主角不在场仍会做什么，均至少 8 字符。主角本人写撤去叙事特权后的生活/事务。
- voice_refs、timeline_refs 非空数组，每项为 {source_id,start_line,end_line,quote}，原句须在绑定文件行范围；仅填名字不算有效语义证明。

scenes 每项有 id、order（唯一正整数叙述顺序）、story_time:{label,tick}。tick 是本章统一因果时钟，不冒充历史日历。先给真实故事时间标签，再按先后分配 tick。倒叙可改变场景 order，但行动因果 order 必须与 tick 一致。

**同一场景中每项 action.story_tick 必须严格等于该场 scene.story_time.tick；场内先后使用 action.order。** 全章行动 order 唯一递增，按 order 排序后的 story_tick 不得倒退。例如 S1.tick=10 时，A1={order:1,story_tick:10}、A2={order:2,story_tick:10}；A2 可引用 A1 获得的新消息，available_order=1、producer_action_id=A1。本章另场 S2.tick=20 的 A3={order:3,story_tick:20}。若动手时真实时间已明显改变，拆为另场，不擅给同场动作独立 tick。

actors_onstage 与 actors_offstage 合起来列全部作选择者，包括幕后命令、拒绝、隐瞒、选择不动者；每个列入者均要本场行动包。无选择路人可放 coverage.background_only:[{name,reason}]。不能把影响事件的拒绝者、传令者、办事人降成背景。

coverage 为 {all_actors_reviewed,all_scenes_reviewed,basis,background_only}，两标志人工核为 true，basis 至少 20 字符，写如何由大纲、台前/幕后与关系后果查漏。机器只核声明和清单一致，具名审查者必须查被藏掉的角色。

## 每次关键选择的七关

场景 actions 每项：

~~~json
{
  "id": "A1",
  "actor_id": "人物ID",
  "order": 1,
  "story_tick": 1,
  "kind": "refuse",
  "choice": "具体决定，不是准备服务剧情",
  "gates": {
    "knows": "他实际知道的消息，以及仍不知道什么",
    "wants": "此次动作想取得的具体东西",
    "fears": "他怕因此失去什么，既有经历和关系来源",
    "capability": "当前能力、权限、信息、工具与渠道到哪",
    "no_plot": "撤去作者预定结果仍选择它的自身理由",
    "costs": "愿付什么代价，不能越过哪些现实约束",
    "consequences": "怎样改变他人、关系、资源和后续局面"
  },
  "capacity": {
    "resources": ["实际可用资源"],
    "permission": "本人可做范围，缺权时怎么绕不过去",
    "limits": "具体能力和渠道限制，不突然扩权",
    "evidence_refs": ["SRC1"]
  },
  "outcome": {
    "intent": "企图取得的结果",
    "success_guaranteed": false,
    "failure_path": "遭拒绝、误判或障碍时的可能失败分支",
    "opposition": "对方自身目标或客观阻力，不保证配合"
  },
  "knowledge_refs": []
}
~~~

kind 可为 action/refuse/conceal/inaction。七关及关键说明至少 8 字符；空值、TODO、TBD、整项 unknown/未知/待填失败。这只是最低结构要求：凑字数、七次复制同句、写“剧情需要”必须人工否决。

不是拿杯子等每个微动作都复制七项。关键选择指改变事实/信息/风险/关系/资源的动作；同场同动机连续动作可合一包，知识、欲望、风险或权限改变要另审。分组合理性由人工覆盖复核负责。

### 人物知识引用

每项 knowledge_refs：

~~~json
{
  "source_id": "SRC1",
  "start_line": 12,
  "end_line": 15,
  "quote": "真实原句",
  "access": "testimony",
  "available_chapter": 99,
  "available_order": 0,
  "producer_action_id": null,
  "author_only": false,
  "certainty": "belief",
  "acquisition": "谁何时通过什么渠道告诉他，为何可以接触",
  "boundary": "只支持哪一部分，哪些事尚未获得证据"
}
~~~

access 为 observation/testimony/document/memory/planned-earlier-action；certainty 为 known/belief/inference/unknown。合理“不知道”允许：只知人失联、不知生死，以有限线索决定试探；须具体说明边界，不能整项“未知”却标 passed。

- 正史 available_chapter 不大于冻结 last_committed_chapter；正文第N章来源不能伪称N之前就获知。
- 本章新消息必须 planned-earlier-action，绑定更早 producer_action_id；available_chapter 为本章，available_order 等于来源动作 order 且早于当前动作。来源动作也过七关。
- 作者视图中的反派计划和世界真相不能由检查通过转给没渠道的角色。
- capacity.evidence_refs 只绑定来源；来源是否支持权限仍要逐条人工检验。

## 人工语义复核

根 manual_review：

~~~json
{
  "status": "passed",
  "reviewer": "实际审查者或Agent标识",
  "method": "实际复核方法和读过的材料",
  "basis": "至少20字符，指出具体选择、知识渠道、能力限度与声线风险的复核依据",
  "checks": {
    "seven_gates": "passed",
    "knowledge_bounds": "passed",
    "capacity_permissions": "passed",
    "autonomy": "passed",
    "constraints": "passed",
    "consequences": "passed",
    "voice": "passed",
    "actor_scene_coverage": "passed",
    "timeline": "passed"
  }
}
~~~

当前写作 Agent 可实际回读后 solo 复核，不必等用户勾选。禁止先标 passed 再补过程、使用不存在的 reviewer；计划变动应建立新前包，不能让冻结包随正文滚动。

## 写后包

复制通过的前包为独立后包。根 CORE_FIELDS（schema/mode/chapter/binding/sources/actors/scenes/coverage/manual_review）与冻结前包完全一致。新增场景/选择须新前包重新复核，不事后包装成旧计划。

填 postwrite：

~~~json
{
  "prewrite_packet": {"path": "追踪/候选章/第100章/run-id/世界引擎/写前行动审查.json", "sha256": "冻结前包SHA256"},
  "candidate": {"path": "追踪/候选章/第100章/run-id/candidate.md", "sha256": "最终候选正文SHA256"},
  "scene_results": [
    {
      "scene_id": "S1",
      "actual_result": "实际发生的事情，区分动机与结果",
      "action_ids": ["A1"],
      "evidence": [{"start_line": 10, "end_line": 13, "quote": "正文实际原句"}],
      "world_followups": ["哪个人物、资源、关系或势力有什么变化；无新增也具体说明"]
    }
  ],
  "foreshadow_deltas": [
    {"id": "F001", "operation": "advance", "description": "读者新得什么证据，不把目标回收章当回收事实",
     "evidence": [{"start_line": 12, "end_line": 13, "quote": "正文原句"}]}
  ],
  "manual_review": {
    "status": "passed",
    "reviewer": "实际审查者",
    "method": "回读最终正文和冻结前包并核角色卡",
    "basis": "具体场景因果、声线、后果和伏笔判断依据，至少20字符",
    "checks": {"actual_coverage": "passed", "causality": "passed", "voice": "passed",
               "knowledge_bounds": "passed", "consequences": "passed", "foreshadow": "passed"}
  }
}
~~~

实际结果须覆盖全场景/行动，每行动在其场景恰登记一次。引用核最终候选原句，正文变更令 hash 失效。伏笔无变化也登记 id=NO_CHANGE、operation=none，并给对照结论和正文证据。机器不证明真正回收，人工须比对承诺与实际答案。

后包递归复验冻结前包。工具不写正文/追踪、不审批候选、不调用候选接纳器；原接纳门另外绑定本 run 的包和 candidate，避免循环依赖。

## 正史派生导出

export 读取原合法权威、原逐章增量和唯一章正文的SHA256：

- 作者/角色当前卡：当前 tracking 字段；不编造人格/声线，缺字段“待核”，配合真实角色设定回读。
- 作者/角色时间线：逐章角色/连续性变化和原 timeline 引用。
- 作者/逐章事件：原增量引用；缺原记录不从当前快照反造。
- 作者/伏笔历史：仅逐章伏笔变化；当前状态另页引用，不伪造首埋/回收过程。
- 作者/卷回看：start/end 真实逐章结果、人物、伏笔变化。
- 作者/世界时间线与读者/已揭示时间线分离 objective_fact/reader_knowledge；读者页仅已揭示或部分揭示且 reveal_chapter<=end 的 reader_knowledge。

每文件带生成标记、修订、范围和来源hash，可删除重建，不是第二 authority。人物当前卡始终最新正史，不伪装指定旧卷尾状态。迁移书缺早期逐章增量明确留空；正文hash可定位证据，但不代表自动可靠推断缺失结构事实。

若时间线条目的 updated_chapter 大于指定 end，当前摘要可能含后续认识，作者/读者历史页均标待核而不复制这段摘要；原逐章增量仍可引用。检查也在完成前复核所有 hash，来源、前包、正文或权威在检查期间改变会使结果失败。

仅导出到 `创作运行/` 或 `.story/` 非权威工作目录（默认 `创作运行/派生视图`，推荐 `.story/派生视图`），不覆盖既有非生成文件；`postwrite.candidate` 除候选工作区文件外，也兼容续写流程中尚未入账的当章 `正文/第NNN章*.md`。不同版本用不同目录，避免历史混用。短篇无原合法 authority 时 export 失败；可规划角色/时间卡，但正式记忆必须由原写作追踪初始化或合法迁移，不冒充长篇已提交历史。
