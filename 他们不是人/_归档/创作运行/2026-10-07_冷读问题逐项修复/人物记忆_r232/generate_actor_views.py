"""Rebuild seven source-bound actor cards and personal timelines at tracking r232.

These are reading aids. The accepted prose and 追踪/_tracking-state.json remain authority.
Run from any working directory: python generate_actor_views.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


OUT = Path(__file__).resolve().parent
BOOK = OUT.parents[2]
STATE_PATH = BOOK / "追踪" / "_tracking-state.json"
STATE = json.loads(STATE_PATH.read_text(encoding="utf-8"))
if STATE.get("state_revision") != 232 or STATE.get("last_committed_chapter") != 99:
    raise SystemExit("Only rebuild for accepted tracking r232 through chapter 99; inspect newer canon first")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prose_path(chapter: int) -> Path:
    matches = sorted((BOOK / "正文").glob(f"第{chapter:03d}章_*.md"))
    if len(matches) != 1:
        raise ValueError(f"Expected one accepted chapter {chapter}: {matches}")
    return matches[0]


PROSE = {chapter: prose_path(chapter) for chapter in (42, 50, 51, 52)}
STATIC = BOOK / "设定" / "角色" / "当前存在.md"
EVENT_SOURCE_CACHE: dict[int, dict[str, str]] = {}


def event_source(chapter: int) -> dict[str, str]:
    if chapter not in EVENT_SOURCE_CACHE:
        path = prose_path(chapter)
        EVENT_SOURCE_CACHE[chapter] = {
            "path": path.relative_to(BOOK).as_posix(),
            "sha256": digest(path),
        }
    return EVENT_SOURCE_CACHE[chapter]


def source_line(chapter: int, needle: str) -> dict:
    path = PROSE[chapter]
    lines = path.read_text(encoding="utf-8").splitlines()
    matches = [(number, line) for number, line in enumerate(lines, 1) if needle in line]
    if len(matches) != 1:
        raise ValueError(f"Expected one line in chapter {chapter} containing {needle!r}: {matches}")
    number, line = matches[0]
    return {
        "chapter": chapter,
        "path": path.relative_to(BOOK).as_posix(),
        "sha256": digest(path),
        "line": number,
        "excerpt": line.strip(),
    }


# Each proposition below is an author-facing reading judgment. Evidence is checked
# against the accepted prose; it is not written into the tracking authority.
ACTORS = {
    "当前存在": {
        "id": "current_existence",
        "distinction": "仍使用芽旧身份入口、已无名离开旧市场且具体位置待核的当前存在；她与原芽不可合并，也不是第六卷白壳的证明任务。",
        "daily": "第042章时在北河，旧同学群仍在手机里；能独立决定周末是否赴约、是否借出群入口。后续位置必须另读后续事件。",
        "drive": "[文本]想保留自己决定旧关系如何继续的权利；[静态设定]逐步建立醒来后自己的生活。",
        "fear": "[文本可推]一旦借群查照片，就要在旧称呼下解释返程与聚餐；不愿把原芽关系当作调查工具。",
        "flaw": "第042章有清楚拒绝，不能据此写成从未模仿过旧人或已完全脱离旧身份；其前期模仿带来的伤害仍需依后续正文结算。",
        "ability": "持有旧群账号，可以发自己是否赴约的消息、拒绝他人借号；不能阻止镜辞从自己的来源找照片，也不能凭一次拒绝取得新证件或稳定新名。",
        "voice": "压力下短句划界：先说“我不发”，再说具体不允许借号、代她答应见面；不把身份谜题向旧同学群公开。",
        "known": "亲见镜辞电话请求及群内给旧称呼留位；镜辞只见她转来的两条消息，未取得群内其他私人对话。无来源显示她已知本地陈骁案全貌。",
        "choice": "第042章拒借号，亲自退出周末预留位；另一可行选择是只问照片并暂留座，但她没有这样做。",
        "cost": "失去一次旧友聚餐的留位；照片来源继续空缺，旧关系可能误解她，但是否发生误解未证。",
        "effect": "约饭者取消座位，镜辞删除借号草稿；不等于旧友承认她的新身份或她永久断交。",
        "uncertain": "约饭者的姓名、她日后是否再见旧同学、原芽照片谁持有，均无本章证据。",
        "evidence": [(42, "我不发。"), (42, "别借我的号，也别说我答应见谁。"), (42, "周末不去，不用留座。")],
        "milestones": [
            (42, "北河远程", "拒借旧同学群查原芽照片，并自行退出周末留位", "失去旧称呼下的座位；照片来源未补齐", "亲见邀约；未获陈骁案后台知识", "E042"),
        ],
        "extra_events": [],
        "static": STATIC,
    },
    "旧同学群约饭者": {
        "id": "old_classmate_meal_organizer",
        "distinction": "第042章群内安排周末聚餐的未具名同学；不能自动与唐宁或任何具名旧友合并。",
        "daily": "第042章当天在旧群里收报名并定聚餐人数；职业、住处、与原芽过去的亲疏均未交代。",
        "drive": "[文本]今天确定聚餐人数；[推断]避免为没有明确答应的人继续占位。",
        "fear": "空座影响人数安排可合理推断；旧写前材料提及垫订金，但正式正文没有订金证据，不能记为事实。",
        "flaw": "回复直接、没有追问原因，可能让旧友感到疏离；只有一条消息，尚不足定为稳定的不耐烦或冷漠性格。",
        "ability": "能调整自己负责的聚餐留位；不能替当前存在报名、推断她身份、向镜辞提供不存在的私人照片。",
        "voice": "短句先接收决定，再报人数截止，最后取消留位；已接纳原话“行，人数今天要定。我就不留位了。”",
        "known": "只可证明收到“周末不去，不用留座”的群内回复；没有证据知道北河异常、镜辞查照片或当前存在的身份判断。",
        "choice": "收到退出消息后取消预留座位；继续保留座位是备选，但没有作出。",
        "cost": "少一名潜在参与者、需要重新按实到人数安排；是否损失订金或交情待核。",
        "effect": "群消息使旧座位实际取消，成为当前存在拒绝继承旧社交义务的现实后果。",
        "uncertain": "姓名、职业、订金、后续是否主动联系她、对其身份的真实想法均待正文证据。",
        "evidence": [(42, "第二条来自约饭的人：行，人数今天要定。我就不留位了。")],
        "milestones": [
            (42, "周末聚餐人数截止当日；群聊", "收到“不去，不用留座”后取消预留位", "需按少一人重新定数；其他代价待核", "只见本人收到的群答复，不得授予身份内幕", "E042 正文补充索引"),
        ],
        "extra_events": [42],
        "static": None,
    },
    "宁州陈骁": {
        "id": "ningzhou_chenxiao",
        "distinction": "拥有宁州九年汽修生活的陈骁，与临江七周配送生活的本地陈骁分轨；同名同证件字段不等于同一条日子。",
        "daily": "宁州汽修厂请假到临江，末班车18:51到站；第051章夜里自己找旅馆，不住502。",
        "drive": "与父亲本人谈九年未结的关系，同时保住宁州工作记录；他不要求系统为自己代开502。",
        "fear": "被迫把本地刷门记录签成自己的行程，既损及工作申诉，也抹去真实缺席和父子旧账。",
        "flaw": "关心父亲又顶嘴，九年不回的亏欠不因他这次抵达而消失；不能以到场写成孝子证明。",
        "ability": "有车票、厂里工单、手机和申诉页；能拒签不实确认、承担缺勤损失；没有住宅开门决定权，也不能改物业账户。",
        "voice": "与父亲短句顶撞，谈门与药；对程序说具体记录和拒签，先问“门开不开”，再说“别用这个给我开门”。",
        "known": "亲历乘车抵达、手机绿灯、杜经理拦截、父亲视频拒门；宁州工单由厂里提供。他不能因同账户出现本地数据就知道本地陈骁的全部经历。",
        "choice": "第051章拒用自动绿灯进楼，第052章不勾承认临江进出的申诉项；替代做法是点绿灯、勾框省事，但会把他反对的合并记在本人名下。",
        "cost": "在外住宿自付；第052章厂里缺勤186元和续房42元有正文金额。不能把本地配送损失归他。",
        "effect": "502仍由父亲决定是否开放，物业留下19:12拦截；厂里扣款与未勾页成为宁州独立后果。",
        "uncertain": "两名陈骁的本体身份、同账户跨城冲突由谁造成、父子以后是否和解均未判。",
        "evidence": [(50, "也别替我把门打开。"), (51, "别用这个给我开门。"), (51, "我在外面找地方住"), (52, "不勾。窗口开到十一点。")],
        "milestones": [
            (50, "502门外视频", "自行决定回临江，与父亲谈门，不借父亲拒绝击败另一人", "厂里请假与回程安排受影响", "视频亲见楼道会谈；不知道镜辞私本里的接缝判断", "E050 正文补充索引"),
            (51, "18:51到站—19:12拦截；活动室", "到楼下仍拒用自动绿灯，视频与父亲争门，外宿", "楼门凭证停用；请假被退与住宿由自己承担", "亲历自动绿灯、拦截及父亲拒绝", "E051"),
            (52, "次晨07:40至11:00", "拒签本人在临江刷门的错误说明，保留两格未勾", "缺勤186元、续房42元，工资扣款实际入账", "有自己的检票及申诉记录；不能认证本地七周是谁", "E052"),
        ],
        "extra_events": [50],
        "same_name_events": ["E035", "E038", "E049", "E050"],
        "static": None,
    },
    "本地陈骁": {
        "id": "local_chenxiao",
        "distinction": "在临江生活并从事配送的陈骁；第042、050章正文称“本地陈骁”或“陈骁”，不可把宁州工单写成他的经历。",
        "daily": "配送站排班、改单与扣款持续牵引他；第051章他人在南环补班，没因宁州陈骁抵达被召回。",
        "drive": "保住临江七周已做的工作和人际后果，同时要求陈启明面对他；父亲拒门后也要回站里做班。",
        "fear": "自己当下做过的事被异常标签删掉，或者宁州九年工单反过来压进自己七周履历。",
        "flaw": "急于让熟悉的旧物和记忆获得父亲认可，也会对镜辞被观察的目光发火；不能把修车善意写成自动取得亲子关系。",
        "ability": "有配送岗位、同事与临江租住/工作记录；可提交药盒、接受或拒绝调查、拒签异地工单；不能强开502，也不能判定旧药盒来源。",
        "voice": "对父亲追问关系和旧物，对镜辞直接质疑“准备写什么”；谈工作与扣款时用具体班次、钱数，不讲身份理论。",
        "known": "亲历修车、交药盒、父亲拒门、配送扣款；第051章不在安平里现场，不自动知道宁州陈骁与父亲全部视频对话或19:12操作细节。",
        "choice": "第042章先回站里改班，第050章接受暂不进502，第052章拒认宁州工单是自己签的；若继续堵门或直接签错单更省眼前麻烦，却不合他已表明的关系与工作利益。",
        "cost": "扣款、改单、停单及第052章少43元配送费归本地时间线；不能和宁州厂里186元合并。",
        "effect": "陈启明仍拒认亲但承认他七周行为；配送站独立调整排班，康复楼药最终晚六分钟送到。",
        "uncertain": "药盒来源、原主身份、接缝原因及两地同证号的真实成因均未判。",
        "evidence": [(42, "我现在回去。"), (50, "我今天不进。"), (51, "人在南环补班，扣款没撤"), (52, "七周的排班、垫的费、扣的钱，都在临江。")],
        "milestones": [
            (42, "安平里雨后—下午", "交旧药盒暂存后回配送站，确认换班", "药盒未获认亲；改班持续影响自己与同事", "知道父亲拒收，药盒真实来源仍不获证", "E042 正文补充索引"),
            (50, "502门外—中午", "在父亲拒入户后自愿暂不进门，去物业留联系方式并回站", "绩效扣款、药品件转交他人", "知道父亲的拒绝和自己的临江七周；不获得宁州九年为己经历", "E050 正文补充索引"),
            (51, "宁州陈骁抵达当晚", "在南环补班，没有被再次召回小区", "扣款未撤，班仍在自己身上", "本章他未到活动室；不把现场全部信息授予他", "E051"),
            (52, "次晨—11:06", "拒签宁州工单，南环停单后去站里查下午排班", "至少少43元，改派药晚六分钟送达", "亲见自己的员工附页；不认证宁州那张工单的本体归属", "E052"),
        ],
        "extra_events": [42, 50],
        "same_name_events": ["E034", "E035", "E036", "E037", "E041", "E042", "E043", "E044", "E045", "E046", "E047", "E048", "E049", "E050"],
        "static": None,
    },
    "陈启明": {
        "id": "chen_qiming",
        "distinction": "502住户、两名陈骁所争关系的父亲；他能决定自己的住宅与称呼，不能用一句话判两人的本体身份。",
        "daily": "守住502住宅决定、照常买菜吃药；与宁州儿子九年旧账尚未清算。",
        "drive": "保留对家门和亲子关系的实际决定权，同时不让拒认亲抹除本地陈骁已做的事。",
        "fear": "自动家庭字段替他开门，或外部调查者迫他以身份结论代替自己的关系判断。",
        "flaw": "讲话硬、骂儿子且不轻易接药盒，保护边界的同时也延长了父子僵局；不能因此写成全知或无情。",
        "ability": "持有502机械门锁、门链和住宅保护工单副本；能拒开自家门、同意在活动室谈；不能停全楼后台，也不能证明药盒字迹。",
        "voice": "短句、顶撞和生活细节并行：“少管”“你不是我儿子”；对两人同样不让页面越过门链。",
        "known": "亲见本地陈骁言行及宁州陈骁视频/到达；知道自己的九年关系经历。未亲见的接缝与系统上游来源不得授予他。",
        "choice": "第050章拒本地陈骁入户，第051章也拒宁州陈骁用系统凭证进门，只同意活动室视频；备选是因熟悉或绿灯开门，但他没有选择。",
        "cost": "独自在502承担门禁与父子争执的不方便；宁州到楼下仍未解决九年问题。",
        "effect": "物业需依独立工单执行，父子改在活动室与视频沟通；谁是真的仍由材料继续核查。",
        "uncertain": "他是否会改变称呼或收药盒、旧药盒字迹归属及两陈本体状态均待证。",
        "evidence": [(50, "你不是我儿子。"), (50, "我没判你是什么。"), (51, "502今天谁也别进。"), (51, "页面爱怎么写怎么写。链子挂着。")],
        "milestones": [
            (42, "安平里物业雨棚", "拒拿药盒入户，只同意物业暂存；承认修车和借伞已发生", "亲子关系未改变；物品七日后需处理", "只见物品与本地行为，不认证来源", "E042"),
            (50, "502门内", "明确拒本地陈骁入户，安排活动室谈话", "门仍锁；与宁州儿子九年争执未结", "区分自己关系决定和他人身份调查", "E050"),
            (51, "502视频；宁州陈骁到楼下", "同样拒绿灯替自己开门，视频里检查煤气阀", "父子仍争，502门链仍挂着", "亲见视频中的儿子与拦截告知，不授系统幕后原因", "E051"),
        ],
        "extra_events": [],
        "static": None,
    },
    "杜经理": {
        "id": "property_manager_du",
        "distinction": "安平里物业经理，操作楼栋门禁及工单的人；岗位权限不等于住户授权或上游系统控制权。",
        "daily": "在值班窗口处理住户卡、楼栋安全、原页导出及投诉责任；第051章夜间仍在岗位。",
        "drive": "按可签字的独立住宅保护工单履责，避免被家庭字段反写成擅自替502开门。",
        "fear": "上游页面变绿、自己点确认以后责任留在当值工号；也怕许棠的实际送药问题被陈骁案吞掉。",
        "flaw": "会先让许棠等，工作上对可追责页面很敏感；此举保护程序，却令药晚约二十分钟，不能写成全无代价的好人。",
        "ability": "能拦截主机凭证、签19:12操作、导出原页及留原件；不能注销同证账号、替502同意入户或保证许棠卡立即修好。",
        "voice": "先说工单、操作人、确认按钮和责任，再给实际替代办法；对住户麻烦承认“还是刷不开”。",
        "known": "亲见绿灯与主机操作、独立工单、同账户页面；不因看见16:20冲突就知道谁在背后改了系统。",
        "choice": "第051章拦截自动凭证并保存操作记录；第052章不点自己未写的新字段。备选放行/确认更省力，但会把他无权决定的关系写成自己操作。",
        "cost": "夜间留岗、继续处理投诉与红卡；若保不住原页将承担解释风险，具体罚款未证。",
        "effect": "502的私人门决定没有被后台替代；原页、操作人和时间可供复核；许棠另线问题仍未解决。",
        "uncertain": "上游发起者、门禁系统最终修复日期、个人处分或实际罚款均无证据。",
        "evidence": [(50, "物业不得以恢复后的家庭字段替陈启明开门"), (51, "白天那张工单还在。"), (51, "操作人栏是杜经理刚输入的当值工号。"), (52, "我点一下，这行就变成我写的。")],
        "milestones": [
            (50, "安平里住宅保护工单", "另开独立工单，规定七日复核且不以父亲改口为完成条件", "需交接、留签字副本", "知道住户拒门及系统覆盖，不知道上游真实发起者", "E050 正文补充索引"),
            (51, "19:12楼栋主机与活动室", "手动拦截自动绿灯，签操作记录并导出16:20相斥原页", "需处理许棠仍红的卡与晚送药", "亲见拦截、原页与工号；不能据此判两陈身份", "E051"),
            (52, "次晨物业办公室", "保留待可见性复核新字段的原页，不点确认，签抄件", "投诉及许棠卡仍由当值窗口承接", "知道此行不是本人写的，不知道发起者", "E052"),
        ],
        "extra_events": [50],
        "static": None,
    },
    "许棠": {
        "id": "xu_tang",
        "distinction": "因自身门禁卡持续失效而受影响的安平里门禁用户/送药者；是否住在楼内未证，她不是两陈身份案的对照样本。",
        "daily": "第051章替许叔送七点半的药，持有收据、自己的门禁卡及邻居协助通路。其职业与许叔亲属关系细节未充分交代。",
        "drive": "先把药送上楼、解决自己的红卡，并阻止别人把她的生活损失塞进陈骁工单。",
        "fear": "再确认一次关系仍修不好卡，还让自己被记成自愿配合调查；药送迟、钱与责任归错。",
        "flaw": "不耐等候时说话冲、要求物业先办卡；这是一处可理解的急迫，不足定为长期刻薄性格。",
        "ability": "可反复试卡、催物业、请302邻居代送、保存药钱收据；不能改后台、强迫杜经理把卡修绿。",
        "voice": "用药、时间、收据和红卡说事；两次明确要求“别把我写进他们那份材料里”“别写我配合调查”。",
        "known": "亲见自己卡红、药晚、邻居代送及物业交接；不知同账户跨城谁真、陌生短信发起者或接缝。",
        "choice": "第051章不再等系统恢复，让邻居代送药；第052章保留收据并再次试卡。备选继续等物业，但七点半用药不能无限延后。",
        "cost": "药约晚二十分钟、卡次日仍红，自己仍需另找入楼方式；是否造成医疗伤害未证。",
        "effect": "药实际进楼，物业另记她的卡与代送，未归入陈骁账户；系统修复仍未完成。",
        "uncertain": "许叔和她确切关系、药品医学后果、红卡故障根因、后续修复日期均待核。",
        "evidence": [(51, "先把我的卡弄好，别拿我当对照。"), (51, "别把我写进他们那份材料里"), (51, "别写我配合调查。"), (52, "证明药钱是自己付的，门是别人开的。")],
        "milestones": [
            (51, "约19:15—邻居到楼下", "拒被列为两陈案对照，让302邻居代送药", "药约晚20分钟，卡仍红", "仅知自身刷卡及送药事实", "E051"),
            (52, "次晨物业办公室", "留药钱收据，再试卡，拒陈骁案分类", "卡仍失效；邻居中午要出门", "亲见新页面只限自己在场所见，不知上游来源", "E052 正文补充索引"),
        ],
        "extra_events": [52],
        "static": None,
    },
}


def numbered_source(ref: dict) -> str:
    return f"{ref['path']}:{ref['line']}（SHA256 {ref['sha256']}）"


def sentence(value: str) -> str:
    value = value.strip().rstrip("；;，, ")
    return value if not value or value[-1] in "。！？!?" else value + "。"


def render_card(name: str, actor: dict, refs: list[dict], source_sha: str) -> str:
    static = actor["static"]
    static_line = (
        f"{static.relative_to(BOOK).as_posix()}（SHA256 {digest(static)}；只作作者侧静态设定）"
        if static else "无已批准独立静态卡；此处为已接纳正文的紧凑辅助卡，未来正式建卡须走原写作流程"
    )
    gates = [
        ("1 知道什么", actor["known"]),
        ("2 想要什么", actor["drive"]),
        ("3 怕失去什么", actor["fear"]),
        ("4 能不能做", actor["ability"]),
        ("5 撤去剧情需要", actor["choice"]),
        ("6 代价与约束", actor["cost"]),
        ("7 后果与他人回应", actor["effect"]),
    ]
    lines = [
        f"# {name}｜来源绑定辅助角色卡",
        "",
        f"状态：可重建阅读视图；唯一结构化正史仍为追踪/_tracking-state.json。修订 232，截至第99章；权威 SHA256 {source_sha}。本卡不是历史写前七关通过证明。",
        "",
        f"稳定工作 ID：{actor['id']}。批准静态来源：{static_line}。",
        "",
        "## 身份、日常与独立驱动",
        "",
        f"- 区分：{actor['distinction']}",
        f"- 生活与位置：{actor['daily']}",
        f"- 可观察的目标：{actor['drive']}",
        f"- 风险与缺陷：{actor['flaw']}",
        "",
        "## 已发生选择的七关复核索引",
        "",
        "这些问题只帮助下次出场重评。文本、静态设定、推断和未知已经分开；不能把本表倒填成旧章当时的写前审批。",
        "",
    ]
    lines.extend(f"- {label}：{value}" for label, value in gates)
    lines += [
        "",
        "## 声线与知情红线",
        "",
        f"- 声线：{actor['voice']}",
        f"- 知情边界：{actor['known']}",
        f"- 未证：{actor['uncertain']}",
        "",
        "## 已接纳正文锚点",
        "",
    ]
    lines.extend(f"- 第{ref['chapter']:03d}章：{ref['excerpt']}｜{numbered_source(ref)}" for ref in refs)
    lines += ["", f"个人时间线：[ {name} ](../人物时间线/{name}.md)。", ""]
    return "\n".join(lines)


def render_timeline(name: str, actor: dict, refs: list[dict], source_sha: str) -> str:
    static = actor["static"]
    static_line = static.relative_to(BOOK).as_posix() if static else "无独立已批准静态卡，参见本批辅助角色卡"
    lines = [
        f"# {name}｜来源绑定个人时间线",
        "",
        "派生阅读视图，不是正史权威。生成器：本目录 generate_actor_views.py。来源修订：232；正式接纳截至99章。",
        f"权威：追踪/_tracking-state.json；SHA256 {source_sha}。静态角色卡：{static_line}。",
        "",
        "## 本批已核实的个人事件",
        "",
        "下表仅按本人可合理知道的范围记行为。E 编号是检索入口；“正文补充索引”表示结构化 E 的 characters 未单列此人，不能伪称已入其参与字段。",
        "",
        "| 时间与地点 | 本人行为 | 实际代价及后果 | 本人知情边界 | 来源 |",
        "|---|---|---|---|---|",
    ]
    for chapter, when, action, cost, known, event_id in actor["milestones"]:
        p = PROSE[chapter]
        src = f"{event_id}；{p.relative_to(BOOK).as_posix()}；SHA256 {digest(p)}"
        lines.append(f"| 第{chapter:03d}章，{when} | {action} | {cost} | {known} | {src} |")
    lines += ["", "## 全部结构化参与事件索引", ""]
    matches = []
    for eid, event in STATE["timeline"].items():
        if name in event.get("characters", []):
            matches.append((event["first_recorded_chapter"], eid, event))
    matches.sort()
    if matches:
        lines += ["以下为作者侧章事件摘要。这些 E 的 characters 字段确有本角色，但一条 E 可能记多人行动，不等于本人亲见或知道全段事实。", ""]
        for chapter, eid, event in matches:
            source = event_source(chapter)
            lines.append(
                f"- {eid}｜第{chapter:03d}章｜{sentence(event.get('story_time', '时间待核'))}"
                f"章事件：{sentence(event.get('objective_fact', ''))}"
                f"来源：{source['path']}（SHA256 {source['sha256']}）。"
            )
            if name == "当前存在" and eid == "E003":
                lines.append("  - 参与字段确实列有当前存在；该事件的错位观察属于镜辞，不能据此写成她本人知道镜辞看见了什么。")
    else:
        lines.append("- 当前结构化 E 尚未把此角色单列；见上表已接纳正文补充索引。")
    same_name_events = actor.get("same_name_events", [])
    if same_name_events:
        lines += [
            "",
            "## 同名字段的历史检索入口",
            "",
            "以下 E 的 characters 只写“陈骁”，无法据字段自动分配给宁州或本地。"
            "按事件摘要和已接纳正文建立检索入口；第042/050章个人行动已在上表逐场核实，"
            "其余章节下次引用前必须回读对应正文，不能将共享事件总述当作此人全部亲历或知情。",
            "",
        ]
        for eid in same_name_events:
            event = STATE["timeline"][eid]
            if "陈骁" not in event.get("characters", []):
                raise ValueError(f"{eid} no longer uses generic 陈骁 participant")
            chapter = event["first_recorded_chapter"]
            source = event_source(chapter)
            lines.append(
                f"- {eid}｜第{chapter:03d}章｜{sentence(event.get('objective_fact', ''))}"
                f"正文：{source['path']}（SHA256 {source['sha256']}）。"
            )
    lines += [
        "",
        "## 读者视图",
        "",
    ]
    if matches:
        lines.extend(f"- {eid}｜第{chapter:03d}章：{event.get('reader_knowledge', '')}" for chapter, eid, event in matches)
    else:
        lines.append("- 读者只在上表所引正文见到本角色的行动；不能从作者侧设定授予其额外知识。")
    lines += [
        "",
        "## 下次出场边界",
        "",
        f"- 未证：{actor['uncertain']}",
        "- 下次出场前重新读最新追踪、角色卡与相邻正文，确认经过时间、位置、收入/损失、信息取得及未履行承诺。",
        "- 第042/050—052章以外的结构化 E 只作定位线索；不得从事件总述反推角色内心或自动认定伏笔首埋、回收。",
        "",
    ]
    return "\n".join(lines)


cards_dir = OUT / "行动者卡"
timeline_dir = OUT / "人物时间线"
cards_dir.mkdir(exist_ok=True)
timeline_dir.mkdir(exist_ok=True)
authority_sha = digest(STATE_PATH)
index = {
    "kind": "source_bound_auxiliary_actor_memory",
    "state_revision": 232,
    "last_committed_chapter": 99,
    "authority": {"path": "追踪/_tracking-state.json", "sha256": authority_sha},
    "prose_sources": {str(ch): {"path": PROSE[ch].relative_to(BOOK).as_posix(), "sha256": digest(PROSE[ch])} for ch in PROSE},
    "actors": {},
}

for name, actor in ACTORS.items():
    refs = [source_line(chapter, needle) for chapter, needle in actor["evidence"]]
    card = cards_dir / f"{name}.md"
    timeline = timeline_dir / f"{name}.md"
    card.write_text(render_card(name, actor, refs, authority_sha), encoding="utf-8")
    timeline.write_text(render_timeline(name, actor, refs, authority_sha), encoding="utf-8")
    structured_events = [
        eid for eid, event in STATE["timeline"].items() if name in event.get("characters", [])
    ]
    index["actors"][name] = {
        "stable_id": actor["id"],
        "role_card": {"path": card.relative_to(BOOK).as_posix(), "sha256": digest(card)},
        "timeline": {"path": timeline.relative_to(BOOK).as_posix(), "sha256": digest(timeline)},
        "approved_static_source": (
            {"path": actor["static"].relative_to(BOOK).as_posix(), "sha256": digest(actor["static"])}
            if actor["static"] else None
        ),
        "formal_prose_anchors": refs,
        "structured_participant_events": structured_events,
        "structured_event_prose_sources": [
            {"event_id": eid, "chapter": STATE["timeline"][eid]["first_recorded_chapter"],
             **event_source(STATE["timeline"][eid]["first_recorded_chapter"])}
            for eid in structured_events
        ],
        "same_name_event_indexes": [
            {"event_id": eid, "chapter": STATE["timeline"][eid]["first_recorded_chapter"],
             **event_source(STATE["timeline"][eid]["first_recorded_chapter"])}
            for eid in actor.get("same_name_events", [])
        ],
        "prose_supplement_chapters": actor["extra_events"],
    }

(OUT / "索引.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(OUT / "使用说明.md").write_text(
    "# 人物记忆 r232 使用说明\n\n"
    "本目录七张紧凑卡与七张个人时间线，仅是正文及追踪 r232 的来源绑定阅读视图，不改写正史。"
    "每张卡的七关栏是下次出场的核对入口，不能伪称旧章曾有写前审批。\n\n"
    "重建命令：在本目录运行 python generate_actor_views.py。脚本要求追踪 r232、已接纳至第99章；版本变化时应先复核事件与卡片判断，再更新脚本，不能直接改修订号复用。"
    "索引.json 列出每份正文、卡片、时间线的 SHA256。\n\n"
    "第042章约饭者有正式正文和逐章结果，但 E042.characters 未单列；这里的 E042 是正文补充索引，不冒充结构化参与。"
    "正式正文没有说明订金，故未把旧写前候选里的垫款说法记为事实。"
    "第050章宁州/本地陈骁及杜经理的部分行动也比 E050.characters 细，时间线同样标为正文补充索引。"
    "两名陈骁还各有同名字段的历史 E 检索栏；这只是带正文 SHA 的回读入口，不能把泛称“陈骁”的整段事实直接授给其中一人。"
    "第052章许棠未在 E052.characters 单列，她继续红卡、保存收据的行为由正式正文证明。\n",
    encoding="utf-8",
)
print(json.dumps({"revision": 232, "cards": len(ACTORS), "timelines": len(ACTORS), "authority_sha256": authority_sha}, ensure_ascii=False))
