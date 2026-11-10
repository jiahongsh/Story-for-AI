#!/usr/bin/env node
'use strict';

const fs = require('fs');

const USAGE = `Usage: node check-emotion-floor.js [--check] [--json] [--fail-on=blocking|all]
                                  [--pressure=low|normal|high] <file...>

情绪落地下限闸口。与 check-ai-patterns.js 互补：那个脚本查「不该有的东西」
（AI 味、套路、电报体），这个脚本查「必须有却缺席的东西」——正文的体温。

为什么需要它：写作规则里禁止情绪标签（「她感到愤怒」）并要求把情绪转译成
身体和动作，但全部闸口都是禁止型的，没有一条下限。于是最省力的通关解变成
「干脆不写情绪」——零情绪标签可以完美通过所有检查，代价是正文没有体温、
读者判为平淡。本脚本给「转译」补上下限，让删除不能冒充转译。

三通道判定（不是数生理词，那样只会催生「心口一沉」复读）：

  somatic   身体信号：心跳/喉咙/指尖/冷汗/呼吸/耳鸣……
  impulse   失控动作：攥/砸/摔/僵住/退半步/手一滑/说到一半停下……
  sense     具身感官：烫/凉/腥/涩/刺/闷/发麻……

同时要求密度与广度：只靠单一通道刷量不算达标，反复复读同一个词组反而扣分。

findings 分级：
  blocking  somatic-floor-critical / emotionless-run-critical / single-channel-spam
  advisory  somatic-floor-low / emotionless-run / channel-narrow / no-loss-of-control
  info      emotion-density-stat（确定性统计输出，不计入退出码）

--pressure=high 用于高压章（对峙/摊牌/生死/揭穿），阈值上调并强制要求失控点；
--pressure=low 用于过场/信息整理章，阈值下调但不取消下限。
--fail-on=blocking 只在 blocking finding 出现时退出 1；默认 --fail-on=all 时
blocking/advisory 任一出现即退出 1（info 不计入）。

**--pressure 作用于本次传入的全部文件，不是逐章判定。** 一批里混着高压章和过场章
时必须分组调用：用 high 会把过场章全判不达标，用 low 会把高压章全放过。

  node check-emotion-floor.js --check --pressure=high 正文/第041章_*.md 正文/第043章_*.md
  node check-emotion-floor.js --check --pressure=low  正文/第042章_*.md
  node check-emotion-floor.js --check 正文/第*.md          # 不带则全部按 normal`;

// ── 三通道词表 ────────────────────────────────────────────────────────────
// 收词原则：只收「身体自己发生、不受意志控制」的信号。不收情绪标签本身
// （愤怒/悲伤/紧张），那些正是规则要禁止的；也不收纯粹的自主动作（走/看/说），
// 那些任何叙述都有，计入会让指标失真。
// 全部使用「贴身二字及以上搭配」，不收裸单字。中文里「压/空/干/沉/尖」这类
// 单字在普通叙述中大量出现（压住付款、杯子空了、干硬的封泥），按单字统计会把
// 物理动作和物体属性算成情绪落点，指标立刻失真——实测一章可虚高一倍以上。
const CHANNELS = {
  somatic: [
    '心跳', '心口', '心脏', '心尖', '胸口', '喉咙', '喉头', '嗓子',
    '指尖', '掌心', '手心', '后背', '脊背', '后颈', '太阳穴', '耳鸣',
    '眼眶', '眼角', '鼻尖', '小腹', '腿软', '膝盖一', '胃里',
    '呼吸', '喘息', '喘了', '喘不', '气息', '冷汗', '出汗', '汗湿',
    '发抖', '发颤', '哆嗦', '战栗', '打颤', '血色', '脸色', '嘴唇', '牙关',
  ],
  impulse: [
    '攥紧', '攥住', '攥着', '握紧', '掐住', '砸', '摔', '撞', '踢开',
    '抓住', '扯住', '拽住', '咬紧', '咬住', '咬着牙',
    '僵住', '顿住', '停住', '愣住', '怔了', '怔住', '哽住', '哽了',
    '退了半步', '退后', '后退', '站不住', '坐不住', '撑住', '扶住',
    '手一滑', '手一抖', '没接住', '打翻', '碰倒', '碰翻', '踉跄',
    '话没说完', '说到一半', '没说出口', '没接话', '半天没', '说不出',
  ],
  sense: [
    '发烫', '滚烫', '发热', '发凉', '冰凉', '冰冷', '发冷', '发酸',
    '发涩', '发苦', '发麻', '发木', '发僵', '发紧', '发虚', '发飘',
    '发空', '发钝', '发哑', '发堵', '发沉', '刺痛', '酸胀', '酸涩',
    '钝痛', '闷痛', '绞痛', '火辣', '腥气', '腥味', '又酸', '又胀',
  ],
};

// 全局最长匹配、不重叠地扫一遍。逐词 indexOf 会让「攥紧」同时被「攥」和
// 「攥紧」各计一次，一章能虚高一倍；不重叠扫描保证每段文字只归一个落点。
// 必须在主执行块之前完成初始化（const 不提升，放到文件末尾会触发 TDZ）。
const LEXICON = [];
for (const [channel, words] of Object.entries(CHANNELS)) {
  for (const word of words) LEXICON.push({ word, channel });
}
LEXICON.sort((a, b) => b.word.length - a.word.length);

// 精致戏剧反应：仓库既有规则明确反对连续使用。这里不禁用，但纳入复读检测，
// 避免本脚本把「有体温」的达标线变成「心口一沉」的刷分线。
const CLICHE_PHRASES = [
  '头皮发紧', '头皮发麻', '眼皮一跳', '心口一沉', '心里一沉', '胃里翻涌',
  '心头一紧', '瞳孔一缩', '呼吸一滞', '血液凝固', '脊背发凉', '浑身一僵',
];

// ── 阈值 ─────────────────────────────────────────────────────────────────
// 阈值按已完本长篇 84 章的实测分布标定：全书中位 2.8/千字，情绪强的章落在
// 4—12，被读者判为平淡的中段（第 39—62 章）均值 0.97、其中 8 章为 0。
// 因此 normal 取 floor=3.0（约中位偏上）、critical=1.0（把接近零体温的章拦死）。
// 换项目/换题材时应先用 --json 跑一遍全书看分布，再决定要不要调。
const PRESSURE_PRESETS = {
  low:    { floor: 1.5, critical: 0.5, run: 1200, runCritical: 2000, minChannels: 1, requireImpulse: false },
  normal: { floor: 3.0, critical: 1.0, run: 800,  runCritical: 1500, minChannels: 2, requireImpulse: false },
  high:   { floor: 5.0, critical: 2.0, run: 500,  runCritical: 1000, minChannels: 2, requireImpulse: true },
};
const CLICHE_SPAM_MIN = 4;        // 同一精致反应词组出现次数达此值 → blocking
const SINGLE_CHANNEL_RATIO = 0.85; // 单通道占比超过此值且总量达标 → 视为刷分

// ── CLI ──────────────────────────────────────────────────────────────────
const options = { json: false, failOn: 'all', pressure: 'normal' };
const files = [];
for (let i = 2; i < process.argv.length; i += 1) {
  const arg = process.argv[i];
  if (arg === '--check') continue;
  else if (arg === '--json') options.json = true;
  else if (arg === '-h' || arg === '--help') { console.log(USAGE.trimEnd()); process.exit(0); }
  else if (arg.startsWith('--fail-on=')) {
    const value = arg.slice('--fail-on='.length);
    if (value !== 'blocking' && value !== 'all') die(`unknown --fail-on value: ${value}`);
    options.failOn = value;
  } else if (arg.startsWith('--pressure=')) {
    const value = arg.slice('--pressure='.length);
    if (!PRESSURE_PRESETS[value]) die(`unknown --pressure value: ${value}`);
    options.pressure = value;
  } else if (arg.startsWith('-')) die(`unknown option: ${arg}`);
  else files.push(arg);
}
if (files.length === 0) die('no input file given');

const preset = PRESSURE_PRESETS[options.pressure];
let failed = false;
const allFindings = [];

for (const file of files) {
  let input;
  try {
    input = fs.readFileSync(file, 'utf8');
  } catch (error) {
    failed = true;
    if (!options.json) console.error(`${file}: unable to read (${error.message})`);
    continue;
  }
  allFindings.push(...scanDocument(input, preset).map((finding) => ({ file, ...finding })));
}

if (options.json) {
  process.stdout.write(`${JSON.stringify({ findings: allFindings }, null, 2)}\n`);
} else if (allFindings.length === 0) {
  console.log('情绪落地下限检查通过。');
} else {
  for (const f of allFindings) {
    const where = f.line ? `:${f.line}` : '';
    console.log(`${f.file}${where}: [${f.severity}] ${f.type}: ${f.message}${f.excerpt ? ` (${f.excerpt})` : ''}`);
  }
}

if (failed) process.exit(2);
const blocking = allFindings.filter((f) => f.severity === 'blocking');
const actionable = allFindings.filter((f) => f.severity !== 'info');
if (options.failOn === 'blocking' && blocking.length > 0) process.exit(1);
if (options.failOn === 'all' && actionable.length > 0) process.exit(1);

// ── 实现 ─────────────────────────────────────────────────────────────────
function die(message) {
  console.error(message);
  console.error(USAGE.trimEnd());
  process.exit(2);
}

// 只统计正文：剥掉标题行与 Markdown 结构行，避免把章名和文件头算进分母。
function proseOf(input) {
  const lines = input.split(/\r?\n/);
  const kept = [];
  lines.forEach((line, index) => {
    const t = line.trim();
    if (!t) return;
    if (/^#{1,6}\s*/.test(t) || /^###第/.test(t)) return;
    if (/^(-{3,}|\*{3,}|={3,})$/.test(t)) return;
    kept.push({ line: index + 1, text: line });
  });
  return kept;
}

function scanHits(text) {
  const perChannel = { somatic: 0, impulse: 0, sense: 0 };
  let total = 0;
  let i = 0;
  while (i < text.length) {
    const hit = LEXICON.find((entry) => text.startsWith(entry.word, i));
    if (hit) {
      perChannel[hit.channel] += 1;
      total += 1;
      i += hit.word.length;
    } else i += 1;
  }
  return { perChannel, total };
}

function hasHit(text) {
  for (let i = 0; i < text.length; i += 1) {
    if (LEXICON.some((entry) => text.startsWith(entry.word, i))) return true;
  }
  return false;
}

// 精致反应是固定四字词组，彼此不重叠，按出现次数直接统计即可。
function countCliches(text) {
  const seen = new Map();
  for (const phrase of CLICHE_PHRASES) {
    let from = 0;
    let at;
    while ((at = text.indexOf(phrase, from)) !== -1) {
      seen.set(phrase, (seen.get(phrase) || 0) + 1);
      from = at + phrase.length;
    }
  }
  return seen;
}

function scanDocument(input, cfg) {
  const prose = proseOf(input);
  const text = prose.map((p) => p.text).join('\n');
  const chars = text.replace(/[\s\p{P}]/gu, '').length;
  const findings = [];
  if (chars < 200) return findings;

  const { perChannel: per, total: totalHits } = scanHits(text);
  const density = (totalHits * 1000) / chars;
  const activeChannels = Object.values(per).filter((n) => n > 0).length;

  findings.push({
    type: 'emotion-density-stat',
    severity: 'info',
    message: `情绪落地密度 ${density.toFixed(1)}/千字（somatic ${per.somatic} / impulse ${per.impulse} / sense ${per.sense}，正文 ${chars} 字，pressure=${options.pressure}，下限 ${cfg.floor}）`,
  });

  // 1) 密度下限
  if (density < cfg.critical) {
    findings.push({
      type: 'somatic-floor-critical',
      severity: 'blocking',
      message: `情绪落地密度 ${density.toFixed(1)}/千字，低于硬下限 ${cfg.critical}。本章几乎没有体温——读者只看到事件推进，感觉不到人物在承受什么。回到情绪最强的 2-3 个节点，把「他很愤怒/她很害怕」这类被删掉的情绪改写成身体反应或失控动作，不是补形容词。`,
    });
  } else if (density < cfg.floor) {
    findings.push({
      type: 'somatic-floor-low',
      severity: 'advisory',
      message: `情绪落地密度 ${density.toFixed(1)}/千字，低于建议下限 ${cfg.floor}。挑本章压力最高的一到两个场景补落点即可，不要全章均匀撒。`,
    });
  }

  // 2) 通道广度：只靠一个通道刷量不算达标
  if (activeChannels < cfg.minChannels && density >= cfg.critical) {
    findings.push({
      type: 'channel-narrow',
      severity: 'advisory',
      message: `情绪落点集中在 ${activeChannels} 个通道（somatic/impulse/sense 各 ${per.somatic}/${per.impulse}/${per.sense}）。只写身体感觉不写失控动作，人物会显得在旁观自己；补一个「做了本来不打算做的事」更有效。`,
    });
  }
  const top = Math.max(per.somatic, per.impulse, per.sense);
  if (totalHits >= 6 && top / totalHits > SINGLE_CHANNEL_RATIO) {
    findings.push({
      type: 'single-channel-spam',
      severity: 'blocking',
      message: `${((top / totalHits) * 100).toFixed(0)}% 的情绪落点挤在同一个通道里。这是在刷密度指标而不是写情绪，换成动作、对话中断、物件状态变化等其他落法。`,
    });
  }

  // 3) 精致戏剧反应复读：防止本闸口被套路化通关
  for (const [phrase, n] of countCliches(text)) {
    if (n >= CLICHE_SPAM_MIN) {
      findings.push({
        type: 'single-channel-spam',
        severity: 'blocking',
        message: `「${phrase}」在本章出现 ${n} 次。精致戏剧反应复读会让情绪贬值，能写普通动作/普通感觉就写普通动作/普通感觉。`,
      });
    }
  }

  // 4) 零体温段：连续多少字没有任何情绪落点
  let run = 0;
  let runStartLine = prose.length ? prose[0].line : 1;
  let worst = { len: 0, line: runStartLine };
  for (const p of prose) {
    const bare = p.text.replace(/[\s\p{P}]/gu, '').length;
    if (hasHit(p.text)) {
      if (run > worst.len) worst = { len: run, line: runStartLine };
      run = 0;
      runStartLine = p.line;
    } else {
      if (run === 0) runStartLine = p.line;
      run += bare;
    }
  }
  if (run > worst.len) worst = { len: run, line: runStartLine };

  if (worst.len >= cfg.runCritical) {
    findings.push({
      line: worst.line,
      type: 'emotionless-run-critical',
      severity: 'blocking',
      message: `连续 ${worst.len} 字没有任何情绪落点（硬上限 ${cfg.runCritical} 字）。这一段读者是零体温读完的，通常出现在纯谈判、纯文书、纯信息交接的场景——正是最容易被判平淡的地方。`,
    });
  } else if (worst.len >= cfg.run) {
    findings.push({
      line: worst.line,
      type: 'emotionless-run',
      severity: 'advisory',
      message: `连续 ${worst.len} 字没有情绪落点（建议上限 ${cfg.run} 字）。不必整段改写，在这段的转折处放一个身体反应或失控动作即可。`,
    });
  }

  // 5) 高压章必须有失控点
  if (cfg.requireImpulse && per.impulse === 0) {
    findings.push({
      type: 'no-loss-of-control',
      severity: 'advisory',
      message: '高压章全程没有失控动作。主角每一步都在计划内、每句话都答得漂亮，读者不会紧张——赢得太顺等于没有赌注。给一个非计划反应：手抖、说错话、摔东西、沉默过久、动作做到一半停下。',
    });
  }

  return findings;
}
