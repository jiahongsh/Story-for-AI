#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');

const USAGE = `Usage: node check-hook-strength.js [--check] [--json] [--fail-on=blocking|all]
                                  [--chapter=N] [--position=golden|body|key|climax] <file...>

钩子强度下限闸口。把 hooks-chapter.md 的「第 1 章必须强 / 2-3 章强」和
hooks-suspense.md 的三档等级下限，从纯文档变成可机器校验的存在性检查。

为什么需要它：这两条规则此前只写在参考文件里，没有任何脚本能查。本仓库
历史上正是在无闸口的情况下，把上游的「第 1 章必须强」改成了「通常强，服从
题材契约」、把「正文章至少 2 级」改成了「通常 1-2 级」，中段因此连续二十余章
没有悬念下限。规则要能守住，得有东西替它站岗。

**本脚本查的是下限存在性，不是等级评定。** 悬念到底算几级、钩子够不够好，
仍由人或 agent 按 hooks-suspense.md 判断；脚本只保证「章尾什么都没留下」
和「黄金三章用弱钩收尾」这两种情况不会静悄悄溜过去。

章尾钩子按九类词表信号（互不重叠地取最长匹配）加两条结构判定识别：

  question    悬置的问题：到底是谁、为什么、什么人，以及问号收尾
  interrupt   未完成 / 被打断：话没说完、就在这时、下一秒、刚要、还差
  reveal      新信息突入：推开门、亮起、响起、递过来、显示、跳出、写着
  pressure    时间或数量压力：还剩、剩余、截止、期限、最后一次、天亮前
  threat      危险信号：不对劲、来不及、已经晚了、原来、竟然
  suspend     动作悬置：停在半空、原封未动、没有拆开，以及「没有动 / 还没
              松开」这类否定式（正则）
  unknown     未知悬置：看不懂、看不见、说不清、猜不透、还不知道
  appointment 时点承诺：天亮之前、开庭前，以及「九点以前」（正则）
  crosscut    视角切走：那头、另一边、同一片天色
  dialogue    结构判定：章尾最后一行是台词，话头刚起、场景没收

findings 分级：
  blocking  golden-three-weak-hook；黄金三章的 ending-no-hook
  advisory  正文章的 ending-no-hook / ending-summary-tell / opening-scenery
            / hook-type-repeat
  info      hook-signal-stat

为什么正文章的 ending-no-hook 只是 advisory：钩子有没有是语义判断，词表识别
不了「没有风了，井绳却晃了一下」这类反常现象钩。已完本长篇实测，词表迭代三轮
把误报从 51 章压到 18 章（21%），其中还包含判对的完结章。这个召回率适合当待查
清单，不适合当硬门——硬门误报多了，作者会学会忽略它，比没有闸口更糟。
黄金三章只有 3 章，人工复核成本极低，弱钩代价又最高，所以那里仍是硬门。

章号从文件名 第NNN章 解析，解析不到再读首行标题（支持中文数字）；
都拿不到时按 --chapter 指定，仍无则按正文章处理，不做黄金三章判定。
**--position 与 --chapter 作用于本次传入的全部文件，不是逐章判定。** 批量跑时不要
带这两个参数——章号能从文件名/标题自动解析，第 1-3 章会自动按黄金三章处理。只有
给单章覆盖定位（例如把完结章显式标成 climax）时才传，且此时只传那一章。

  node check-hook-strength.js --check 正文/第*.md                    # 批量，自动判定
  node check-hook-strength.js --check --position=climax 正文/第084章_*.md`;

// ── 钩子信号词表 ─────────────────────────────────────────────────────────
// 只收二字及以上、且在章尾语境里确实指向「还没完」的表达。裸单字（问/看/走）
// 在任何叙述里都高频出现，收进来会让所有章一律判为有钩子，闸口就废了。
const SIGNALS = {
  question: [
    '到底是谁', '到底是什么', '到底是', '究竟是', '是谁', '什么人', '哪里来',
    '为什么', '怎么会', '怎么可能', '会是谁', '还是谁', '凭什么',
  ],
  interrupt: [
    '话没说完', '话还没', '没说完', '没来得及', '来不及', '还没等',
    '就在这时', '就在此时', '下一秒', '下一刻', '刚要', '正要', '刚想',
    '还差', '只差', '还剩最后', '再往下', '正准备',
  ],
  reveal: [
    '推开门', '门被推开', '走进来', '闯进来', '亮起', '响起', '亮了',
    '递过来', '递上来', '伸过来', '抬头看见', '一抬头', '这才看清',
    '显示', '跳出', '弹出', '写着', '露出', '浮出', '出现在',
  ],
  pressure: [
    '还剩', '剩余', '只剩', '截止', '期限', '倒计时', '最后一次',
    '最后一天', '最后期限', '天亮前', '午夜前', '来得及吗', '还有多久',
  ],
  threat: [
    '不对劲', '不对头', '出事了', '已经晚', '晚了一步', '来不及了',
    '原来是', '原来不是', '竟然是', '居然是', '根本不是', '从来不是',
  ],
  // 下面四类是按已完本长篇实测补的。只收前五类时，84 章有 51 章判无钩子，
  // 而抽查显示那些章其实都有钩，只是钩型是「动作停在半空」「她还没看懂」
  // 「九点以前要到核验台」「那头，某人正望着同一片天色」这几种——词表漏了，
  // 不是正文漏了。闸口召回不足会让作者学会忽略它，比没有闸口更糟。
  suspend: [
    '停在半空', '悬在半空', '举在半空', '停在那里', '停住不动', '迟迟没有',
    '没有打开', '没有拆开', '没有拆', '原封未动', '没有落下', '没有说出',
    '没有接过', '没有伸手', '没有开盒', '没有回头', '没有追问',
  ],
  unknown: [
    '看不懂', '还没看懂', '看不见', '看不出', '看不清', '没看清',
    '说不清', '猜不透', '想不通', '还不知道', '不知道是谁', '不知道那',
    '一个她还没', '一个他还没', '连对家的脸', '不知道会',
  ],
  appointment: [
    '天亮之前', '天亮以前', '天亮前', '子时前', '子时以前', '开庭前',
    '明天一早', '次日一早', '后天', '三日之内', '七日之内', '当天以前',
  ],
  crosscut: [
    '那头，', '另一头', '另一边', '同一片天色', '同一时刻', '这个时候',
    '与此同一', '城的另一', '定北那头', '京城那头',
  ],
};

// 「N 点以前 / 之前」这类时点承诺是变量，词表列不全，用一条窄正则补。
const APPOINTMENT_PATTERN = /[0-9一二三四五六七八九十]+\s*(?:点|时|刻)\s*(?:以前|之前|前)/;

// 否定式悬置：「锁没有动」「手还没有松开」这类说法组合太多，逐条列会漏，
// 限定在少数几个「动作没发生」的动词上用正则收。
const NEGATED_ACTION_PATTERN =
  /(?:还)?没(?:有)?\s*(?:动|松开|松手|回头|落下|拆开|打开|接过|说话|抬头|放下|出声|应声|伸手)/;

// 章尾最后一行是台词 = 话头刚起、场景没收，属于结构可判的强收尾，
// 词表判不出来（台词内容可以是任何字）。引号风格跟随项目，两种都认。
const DIALOGUE_LINE_PATTERN = /^\s*[「“"'『][^]*$/;

// 总结体收尾：把本章讲完的道理再说一遍，等于主动关掉期待。
const SUMMARY_TAILS = [
  '这就是', '从此以后', '从那以后', '终于明白', '这才明白', '这意味着',
  '意味着', '原来如此', '一切都结束', '一切都过去', '尘埃落定',
  '真正重要的是', '她终于懂得', '他终于懂得', '算是有了交代',
];

// 章首风景 / 天气开场：hooks-chapter 明确列为反模式。
const SCENERY_OPENERS = [
  '天气', '阳光', '天空', '晨光', '暮色', '夜色', '月光', '春风', '秋风',
  '天刚亮', '天还没亮', '雨下', '下起了', '风吹', '云层', '空气里',
];

const ENDING_WINDOW = 220;   // 章尾判定窗口（去标点后的字数）
const OPENING_WINDOW = 100;  // 章首判定窗口

// 非重叠最长匹配用的统一词表
const LEXICON = [];
for (const [kind, words] of Object.entries(SIGNALS)) {
  for (const word of words) LEXICON.push({ word, kind });
}
LEXICON.sort((a, b) => b.word.length - a.word.length);

// ── CLI ──────────────────────────────────────────────────────────────────
const options = { json: false, failOn: 'all', chapter: null, position: null };
const files = [];
for (let i = 2; i < process.argv.length; i += 1) {
  const arg = process.argv[i];
  if (arg === '--check') continue;
  else if (arg === '--json') options.json = true;
  else if (arg === '-h' || arg === '--help') { console.log(USAGE.trimEnd()); process.exit(0); }
  else if (arg.startsWith('--fail-on=')) {
    const v = arg.slice('--fail-on='.length);
    if (v !== 'blocking' && v !== 'all') die(`unknown --fail-on value: ${v}`);
    options.failOn = v;
  } else if (arg.startsWith('--chapter=')) {
    const v = Number(arg.slice('--chapter='.length));
    if (!Number.isInteger(v) || v < 1) die(`--chapter must be a positive integer`);
    options.chapter = v;
  } else if (arg.startsWith('--position=')) {
    const v = arg.slice('--position='.length);
    if (!['golden', 'body', 'key', 'climax'].includes(v)) die(`unknown --position value: ${v}`);
    options.position = v;
  } else if (arg.startsWith('-')) die(`unknown option: ${arg}`);
  else files.push(arg);
}
if (files.length === 0) die('no input file given');

let failed = false;
const allFindings = [];
let previousKinds = null;
let previousFile = null;
let previousChapter = null;

for (const file of files) {
  let input;
  try {
    input = fs.readFileSync(file, 'utf8');
  } catch (error) {
    failed = true;
    if (!options.json) console.error(`${file}: unable to read (${error.message})`);
    continue;
  }
  const result = scanDocument(input, file);
  const chapterNo = result.chapterNo;
  allFindings.push(...result.findings.map((f) => ({ file, ...f })));

  // 连续两章同一类钩子 → 刺激通胀，hooks-chapter 要求主动错落。
  // 只在章号真的相邻（N-1 → N）时判：早先按「上一个非空文件」判，中间夹一个
  // 零信号章就会拿 N-2 跟 N 比，消息还写着「上一章」；文件乱序传入时更是无稽。
  // 章号解析不到就不判——宁可漏报，不报错话。
  if (
    previousKinds
    && previousChapter !== null
    && chapterNo !== null
    && chapterNo === previousChapter + 1
    && result.kinds.size === 1
    && previousKinds.size === 1
  ) {
    const [a] = [...previousKinds];
    const [b] = [...result.kinds];
    if (a === b) {
      allFindings.push({
        file,
        type: 'hook-type-repeat',
        severity: 'advisory',
        message: `本章与上一章（${path.basename(previousFile)}）都只用了 ${a} 一类钩子。连续同型钩子会造成刺激通胀，换一类收尾。`,
      });
    }
  }
  previousKinds = result.kinds;
  previousFile = file;
  previousChapter = chapterNo;
}

if (options.json) {
  process.stdout.write(`${JSON.stringify({ findings: allFindings }, null, 2)}\n`);
} else if (allFindings.length === 0) {
  console.log('钩子强度下限检查通过。');
} else {
  for (const f of allFindings) {
    console.log(`${f.file}: [${f.severity}] ${f.type}: ${f.message}${f.excerpt ? ` (${f.excerpt})` : ''}`);
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

const CN_DIGITS = { 零: 0, 〇: 0, 一: 1, 二: 2, 两: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9 };

function cnToNumber(text) {
  if (/^\d+$/.test(text)) return Number(text);
  let total = 0;
  let section = 0;
  let current = 0;
  for (const ch of text) {
    if (ch in CN_DIGITS) current = CN_DIGITS[ch];
    else if (ch === '十') { section += (current || 1) * 10; current = 0; }
    else if (ch === '百') { section += (current || 1) * 100; current = 0; }
    else if (ch === '千') { section += (current || 1) * 1000; current = 0; }
    else if (ch === '万') { total += (section + current) * 10000; section = 0; current = 0; }
    else return null;
  }
  const value = total + section + current;
  return value > 0 ? value : null;
}

function chapterNumberOf(input, file) {
  const byName = path.basename(file).match(/第\s*(\d+)\s*章/);
  if (byName) return Number(byName[1]);
  const firstLine = input.split(/\r?\n/, 1)[0] || '';
  const byTitle = firstLine.match(/第\s*([0-9一二三四五六七八九十百千万零〇两]+)\s*章/);
  if (byTitle) return cnToNumber(byTitle[1]);
  return options.chapter;
}

function positionOf(chapterNo) {
  if (options.position) return options.position;
  if (chapterNo !== null && chapterNo <= 3) return 'golden';
  return 'body';
}

function proseOf(input) {
  return input
    .split(/\r?\n/)
    .filter((line) => {
      const t = line.trim();
      if (!t) return false;
      if (/^#{1,6}\s*/.test(t) || /^###第/.test(t) || /^###\d+\.?$/.test(t)) return false;
      if (/^(-{3,}|\*{3,}|={3,})$/.test(t)) return false;
      return true;
    })
    .join('\n');
}

function scanSignals(text) {
  const kinds = new Set();
  let total = 0;
  let i = 0;
  while (i < text.length) {
    const hit = LEXICON.find((entry) => text.startsWith(entry.word, i));
    if (hit) { kinds.add(hit.kind); total += 1; i += hit.word.length; }
    else i += 1;
  }
  return { kinds, total };
}

function scanDocument(input, file) {
  const prose = proseOf(input);
  const findings = [];
  const bare = prose.replace(/[\s\p{P}]/gu, '');
  const chapterNo = chapterNumberOf(input, file);
  if (bare.length < 200) return { findings, kinds: new Set(), chapterNo };

  const position = positionOf(chapterNo);

  // 章尾窗口：按去标点后的字数回溯，避免长对话行把窗口撑空
  let tail = prose;
  if (bare.length > ENDING_WINDOW) {
    let count = 0;
    let cut = prose.length;
    for (let i = prose.length - 1; i >= 0; i -= 1) {
      if (!/[\s\p{P}]/u.test(prose[i])) count += 1;
      if (count >= ENDING_WINDOW) { cut = i; break; }
    }
    tail = prose.slice(cut);
  }
  const endsWithQuestion = /[？?]\s*$/.test(prose.trim());
  const { kinds, total } = scanSignals(tail);
  if (endsWithQuestion) kinds.add('question');
  const hasAppointment = APPOINTMENT_PATTERN.test(tail);
  if (hasAppointment) kinds.add('appointment');
  const hasNegatedAction = NEGATED_ACTION_PATTERN.test(tail);
  if (hasNegatedAction) kinds.add('suspend');
  const proseLines = prose.split(/\r?\n/).filter((l) => l.trim());
  const lastLine = proseLines[proseLines.length - 1] || '';
  const endsWithDialogue = DIALOGUE_LINE_PATTERN.test(lastLine);
  if (endsWithDialogue) kinds.add('dialogue');
  const signalCount = total
    + (endsWithQuestion ? 1 : 0)
    + (hasAppointment ? 1 : 0)
    + (hasNegatedAction ? 1 : 0)
    + (endsWithDialogue ? 1 : 0);

  findings.push({
    type: 'hook-signal-stat',
    severity: 'info',
    message: `章尾钩子信号 ${signalCount} 个，类型 [${[...kinds].join(', ') || '无'}]（第 ${chapterNo ?? '?'} 章，定位 ${position}，窗口末 ${Math.min(ENDING_WINDOW, bare.length)} 字）`,
  });

  if (signalCount === 0) {
    findings.push({
      type: 'ending-no-hook',
      severity: position === 'golden' ? 'blocking' : 'advisory',
      message: '章尾未识别出钩子信号：没有悬置的问题、被打断的动作、新信息突入、时间压力或未落下的动作。请人工确认——「有没有钩子」是语义判断，词表识别不了「没有风了，井绳却晃了一下」这类反常现象钩，本条是待查清单不是定论。确认确实没有则补，低压章可以用弱钩，但不能没有钩。',
      excerpt: compact(tail.slice(-60)),
    });
  } else if (position === 'golden' && signalCount < 2) {
    findings.push({
      type: 'golden-three-weak-hook',
      severity: 'blocking',
      message: `第 ${chapterNo} 章属于黄金三章，章尾只有 ${signalCount} 个钩子信号。前三章决定读者是否追读，强度是硬下限，不适用「服从题材契约」「慢热」「呼吸章」任何豁免（见 hooks-chapter.md）。`,
      excerpt: compact(tail.slice(-60)),
    });
  }

  for (const phrase of SUMMARY_TAILS) {
    if (tail.includes(phrase)) {
      findings.push({
        type: 'ending-summary-tell',
        severity: 'advisory',
        message: `章尾出现总结句「${phrase}」。把本章讲完的意思再说一遍等于主动关掉期待，用动作、对话或物件状态收束。`,
        excerpt: compact(tail.slice(Math.max(0, tail.indexOf(phrase) - 20), tail.indexOf(phrase) + 40)),
      });
      break;
    }
  }

  const head = prose.slice(0, OPENING_WINDOW * 2);
  const headBare = head.replace(/[\s\p{P}]/gu, '').slice(0, OPENING_WINDOW);
  const sceneryHit = SCENERY_OPENERS.find((w) => headBare.includes(w));
  if (sceneryHit && !/[「」“”？?！!]/.test(head.slice(0, 60))) {
    findings.push({
      type: 'opening-scenery',
      severity: 'advisory',
      message: `章首 ${OPENING_WINDOW} 字内以「${sceneryHit}」这类天气/风景起手，且没有对话或动作。hooks-chapter 把风景开场列为反模式，前 100 字要给钩子。`,
      excerpt: compact(head.slice(0, 50)),
    });
  }

  return { findings, kinds, chapterNo };
}

function compact(text) {
  const normalized = text.replace(/\s+/g, ' ').trim();
  return normalized.length > 70 ? `${normalized.slice(0, 67)}...` : normalized;
}
