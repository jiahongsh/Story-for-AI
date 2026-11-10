#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');

const USAGE = `Usage: node check-degeneration.js [--check] [--json] [--fail-on=blocking|all] [--language=auto|zh|en] <file...|->

Detect model-degeneration fingerprints that a degrading model cannot self-report:
  - verbatim repetition (复读/打转): a long sentence repeated, or back-to-back identical lines
  - mid-sentence truncation (截断): file ends without terminal/closing punctuation
  - placeholder / refusal / meta leakage (元信息泄漏): 作为AI / 我无法继续 / 此处省略 / 乱码
  - engineering-word leakage (工程词泄漏): 细纲 / 情节点 / 本章 / 下一章 / 任务描述 漏进正文
  - chapter-ref leakage (章号引用泄漏): ch13 / Ch.13 / chapter 13 这类英文章号缩写漏进正文
  - language leakage (语言泄漏): 中文正文混入纯英文句段、完整英文台词、连续英文短语或裸英文词

Each finding carries severity: blocking (复读/截断/占位拒绝语/tier1 工程词，以及 zh 中的英文句段/
完整英文台词/连续短语/高置信裸词) 或 advisory (tier2 章节/歧义词、疑似外文专名或短词，交人/LLM 判)。
--fail-on=blocking 只在出现 blocking finding 时退出 1；默认 --fail-on=all 有任何 finding 即退出 1。
--language=auto 根据整份正文判定中文/英文（默认）；zh 开启中文正文语言门禁；en 跳过语言门禁，
但仍执行复读、截断、占位符和工程词检测。中文正稿确需逐字保留的其他外语，必须由用户单独确认后，
在正文所在项目根目录的 .deslop-whitelist 中逐行精确登记（不做子串豁免）。

Report-only. The script never rewrites — the safe response is to regenerate the
affected unit (chapter / 摘要) with the finding fed back as a constraint, cap retries,
then surface the evidence to the user. Conservative by design: 通俗网文 deliberately
uses 排比/复沓/弹幕刷屏/重复台词 for rhythm, so short and dialogue repetition is exempt.`;

// 复读：长句（可见字数 ≥ REPEAT_MIN_LEN）出现 ≥ REPEAT_MIN_COUNT 次判为打转；
// 紧邻整行重复（可见字数 ≥ ADJACENT_MIN_LEN）判为即时循环。短句/弹幕/对话刷屏豁免。
const REPEAT_MIN_LEN = 12;
const REPEAT_MIN_COUNT = 3;
const ADJACENT_MIN_LEN = 8;

// hard = 任何行都判（正文里永不合法）；soft = 只在「非对话」叙述行判（角色台词里可能合法，
// 如「对不起，我无法答应你」是正常对话，不是模型拒绝语）。
const PLACEHOLDER_PATTERNS = [
  // 「作为AI」需在自指位置（其后是断句/我/无法… 或句末），避免误报「人工智能时代的产物」这类
  // 复合名词；并对对话行豁免（系统流/AI 伴侣题材里 AI 角色台词「作为AI，我会保护你」是合法对话）。
  // 型号后缀（AI语言模型/AI助手/人工智能语言模型/AI模型/AI大模型）必须可选吃掉：否则前视断言紧跟
  // 在「AI」后面看到的是「语」/「助」/「模」，最典型的退化开场整类漏检（与写后网 story_hook_core.js
  // SOFT_PATTERNS / story_codex_hook.py _NET_SOFT_PATTERNS 同语义）。
  { re: /作为(一个)?(AI|人工智能|大?语言模型|智能助手|聊天助手)(?:语言模型|大?模型|助手|机器人)?(?=[，,。、；;：:！!？?\s）)」』"】]|我|无法|不能|没法|$)/, label: '元信息泄漏（AI 自指）', hard: false },
  { re: /�/, label: '乱码（替换字符 �）', hard: true },
  { re: /^(Sure|Certainly|Here'?s|As an AI|I (?:cannot|can't|am unable|apologize))/, label: '元信息泄漏（英文 AI 腔）', hard: true },
  { re: /[（(](此处|以下|这里|下文|后续)?\s*(省略|略)(去|过)?[^）)]{0,10}[）)]/, label: '占位符（括号省略）', hard: true },
  { re: /(未完待续|TODO|占位符|placeholder)/, label: '占位符', hard: true },
  { re: /我(无法|不能)(继续(写|创作|生成|下去)|生成(内容|文本|正文)?|创作|续写|完成(这个|本)?(章|篇|创作|请求))/, label: '元信息泄漏（生成拒绝语）', hard: false },
];

// 工程词泄漏（正文元信息扫描的确定性版）：弱模型把写作工程词漏进正文，破坏代入感
// （DeepSeek-v4 这类会在对话里冒「该到下一章了」）。漏词的模型自己发现不了，靠脚本兜。
// tier1 = 纯写作流水线术语，正文里几乎永不合法；tier2 = 章节结构/歧义词，角色在故事内
// 真实阅读/讨论「第X章」或故事内系统/界面用语时属例外（report-only，交人/LLM 判）。
// tier1 词表按「规划文件里真的有、正文里零误报」实测扩过一轮：细纲/卷纲里
// 剧情单元 ID（V6-U3）46 次、结构字段名 599 次、压力级标记 90 次、规划文件路径 3 次，
// 在 101 个正文文件里各 0 次误报，全部收进来。
// 唯独字母+数字式的旧伏笔 ID（B8/C5/N5）不收——正文里会撞 R66-7 这类材料牌号
// （本身还是剧情物证），实测 7 处误报。
const META_TIER1_RE = /细纲|情节点|卷纲|功能标签|目标情绪|字数目标|章首钩子|章尾钩子/;
// 规划记号（剧情单元 ID / 结构字段名 / 压力级标记 / 规划文件路径）单列一条，不并进
// META_TIER1_RE：四端 parity 靠 test-prose-net-parity.sh 逐字锚定那一串，改散了就绕过锚点。
const META_PLANNING_MARKER_RE = /内容概括|情节安排|预算合计|结尾设定|阶段位置|结构公式|压力级|爽点类型|章节定位|\bV\d+-U\d+\b|\b[FE]\d{3,}\b|(?:追踪|大纲|设定|拆文库)\/[^\s，。）】」]+\.md/;
// 章号引用的英文缩写形态：ch13 / Ch.13 / CH 13 / chapter 13。实测泄漏样本
// 「她在 ch13 便学乖了」「ch13 那夜合苔三倍灵气第一次涌」——中文词表一条都不命中，
// 因为它只收「第X章/本章/前文」这些写法。中文正文里 ch+数字 不可能是故事内表达，
// 归 tier1。\b 前界保证 Bach13、Munch13 这类词不误伤。
// 中文正文语言门禁。旧规则只扫「单行 CJK 占比 ≥50% + 全小写 ≥4 位」的裸词，会漏掉
// 纯英文段、TitleCase 人名占位、go/to 等短词，以及英文占比一高就自动逃逸的整句。
// 新规则先按整份正文判语言，再用等长遮罩保护 URL/邮箱/代码/路径/文件名，最后按精确 offset
// 判断命中是否真的位于引号内；同一行其他位置出现引号不再把整行误降级。
const CJK_CHAR_RE = /[\u3400-\u9fff]/g;
const LATIN_LETTER_RE = /[A-Za-z]/g;
const LATIN_TOKEN_SOURCE = "[A-Za-z]+(?:['’][A-Za-z]+)?";
const LATIN_TOKEN_RE = new RegExp(`(?<![A-Za-z0-9])${LATIN_TOKEN_SOURCE}(?![A-Za-z0-9])`, 'g');
const LANGUAGE_MODES = new Set(['auto', 'zh', 'en']);
const LANGUAGE_PHRASE_MIN_WORDS = 3;
const LANGUAGE_PHRASE_MIN_LETTERS = 12;
const META_CHAPTER_REF_RE = /\b(?:ch|chap|chapter)\.?\s?\d{1,4}\b/i;
const META_TIER2_RE = /第[一二三四五六七八九十百千万两0-9]+章|本章|这一章|上一章|下一章|上章|下章|前一章|后一章|前文|后文|伏笔|读者|任务描述/;

const options = { json: false, files: [], failOn: 'all', language: 'auto' };

for (let i = 2; i < process.argv.length; i += 1) {
  const arg = process.argv[i];
  if (arg === '--check') {
    // Accepted for symmetry with the other detectors; detection is always check-only.
  } else if (arg === '--json') {
    options.json = true;
  } else if (arg.startsWith('--fail-on=')) {
    const v = arg.slice('--fail-on='.length);
    if (v !== 'blocking' && v !== 'all') die(`--fail-on must be 'blocking' or 'all'`);
    options.failOn = v;
  } else if (arg.startsWith('--language=')) {
    const v = arg.slice('--language='.length);
    if (!LANGUAGE_MODES.has(v)) die(`--language must be 'auto', 'zh', or 'en'`);
    options.language = v;
  } else if (arg === '-h' || arg === '--help') {
    process.stdout.write(`${USAGE}\n`);
    process.exit(0);
  } else if (arg === '-') {
    options.files.push(arg);
  } else if (arg.startsWith('-')) {
    die(`Unknown option: ${arg}`);
  } else {
    options.files.push(arg);
  }
}

if (options.files.length === 0) {
  die('No files provided');
}

let failed = false;
const allFindings = [];

for (const file of options.files) {
  // Git Bash on Windows exposes `/dev/stdin` to shell tools, but Node's Win32
  // path resolver turns it into a drive path that cannot be opened. Read fd 0
  // directly for both conventional stdin spellings while keeping the original
  // label in findings. Stdin has no trustworthy project root, so it must not
  // inherit a `.deslop-whitelist` from the caller's cwd.
  const isStdin = file === '-' || file === '/dev/stdin';
  const fullPath = isStdin ? null : path.resolve(file);
  let input;
  try {
    input = fs.readFileSync(isStdin ? 0 : fullPath, 'utf8');
  } catch (error) {
    failed = true;
    if (!options.json) console.error(`${file}: unable to read (${error.message})`);
    continue;
  }
  const whitelist = isStdin ? emptyLanguageWhitelist() : loadLanguageWhitelist(fullPath);
  const findings = scanDocument(input, { language: options.language, whitelist })
    .map((finding) => ({ file, ...finding }));
  allFindings.push(...findings);
}

if (options.json) {
  process.stdout.write(`${JSON.stringify({ findings: allFindings }, null, 2)}\n`);
} else {
  for (const f of allFindings) {
    console.log(`${f.file}:${f.line}:${f.column}: [${f.severity}] ${f.type}: ${f.message} (${f.excerpt})`);
  }
}

if (failed) process.exit(2);
// --fail-on=blocking 只在出现 blocking finding 时退出 1（advisory 仅报告）；默认 all 沿用「有任何 finding 即 1」。
const hasBlocking = allFindings.some((f) => f.severity === 'blocking');
if (options.failOn === 'blocking' ? hasBlocking : allFindings.length > 0) process.exit(1);

function die(message) {
  console.error(message);
  console.error(USAGE.trimEnd());
  process.exit(2);
}

function scanDocument(input, { language = 'auto', whitelist = emptyLanguageWhitelist() } = {}) {
  const lines = input.split(/\r?\n/);
  const content = []; // { text, trimmed, lineNo } for body lines outside front-matter/fences
  let fence = null; // { marker, length }
  let inFrontMatter = hasYamlFrontMatter(lines);

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const trimmed = line.trim();
    if (inFrontMatter) {
      if (index > 0 && trimmed === '---') inFrontMatter = false;
      continue;
    }
    const fenceMarker = /^(`{3,}|~{3,})/.exec(trimmed);
    if (fence) {
      if (
        fenceMarker
        && fenceMarker[1][0] === fence.marker
        && fenceMarker[1].length >= fence.length
        && trimmed.slice(fenceMarker[1].length).trim() === ''
      ) fence = null;
      continue;
    }
    if (fenceMarker) {
      fence = { marker: fenceMarker[1][0], length: fenceMarker[1].length };
      continue;
    }
    // Markdown reference definition is document metadata, not visible prose. The visible label in
    // `[Chinese label][docs]` is still scanned; only its reference id/definition is protected.
    if (/^\s{0,3}\[[^\]\n]+\]:\s*(?:<[^>\n]+>|\S+)/.test(line)) continue;
    content.push({ text: line, trimmed, lineNo: index + 1 });
  }

  const findings = [];
  findings.push(...findRepetition(content));
  findings.push(...findTruncation(content));
  findings.push(...findPlaceholders(content));
  findings.push(...findMetaLeak(content));
  const resolvedLanguage = resolveDocumentLanguage(content, language);
  if (resolvedLanguage === 'zh') findings.push(...findLanguageLeak(content, whitelist));
  findings.sort((a, b) => a.line - b.line || a.column - b.column);
  return findings;
}

function isContent(trimmed) {
  return trimmed && !trimmed.startsWith('#') && !/^-{3,}$/.test(trimmed);
}

// 去掉成对引号内的片段（台词/系统词/引用物件），只留引号外叙述。复读判定用：重复台词是体裁
// 手法（豁免），但「叙述 + 引号内物件/短台词」混合行里引号外叙述的复读仍是退化，不能整行豁免。
function stripQuoted(text) {
  return text
    .replace(/「[^」]*」/g, '')
    .replace(/『[^』]*』/g, '')
    .replace(/【[^】]*】/g, '')
    .replace(/“[^”]*”/g, '')
    .replace(/‘[^’]*’/g, '')
    .replace(/"[^"]*"/g, '')
    .replace(/'[^']*'/g, '');
}

function visibleLength(text) {
  const m = text.match(/[一-鿿Ａ-ｚA-Za-z0-9]/g);
  return m ? m.length : 0;
}

function findRepetition(content) {
  const findings = [];
  const body = content.filter((c) => isContent(c.trimmed));

  // (1) back-to-back identical lines (immediate loop). 纯台词/弹幕复沓（引号外叙述很短）豁免；
  // 「叙述 + 引号内物件」混合行的整行复读仍判（去引号后叙述够长）。
  for (let i = 1; i < body.length; i += 1) {
    if (
      body[i].trimmed === body[i - 1].trimmed &&
      visibleLength(stripQuoted(body[i].trimmed)) >= ADJACENT_MIN_LEN
    ) {
      findings.push({
        line: body[i].lineNo,
        column: 1,
        type: 'verbatim-repeat',
        severity: 'blocking',
        message: '逐行复读（紧邻整行重复）：疑似模型打转，重写本段、删掉重复。',
        excerpt: compact(body[i].trimmed),
      });
    }
  }

  // (2) any long sentence repeated >= REPEAT_MIN_COUNT times across the file.
  // 只豁免引号内台词（体裁手法），引号外叙述句仍参与复读计数（含「叙述+引号内物件」混合行）。
  const counts = new Map();
  for (const { trimmed } of body) {
    for (const sentence of stripQuoted(trimmed).split(/[。！？!?]/)) {
      const s = sentence.trim();
      if (visibleLength(s) < REPEAT_MIN_LEN) continue;
      const entry = counts.get(s) || { count: 0, firstLine: null };
      entry.count += 1;
      counts.set(s, entry);
    }
  }
  // record first line for repeated sentences
  const flagged = new Set();
  for (const [s, entry] of counts) {
    if (entry.count >= REPEAT_MIN_COUNT) flagged.add(s);
  }
  if (flagged.size) {
    for (const { trimmed, lineNo } of body) {
      for (const sentence of stripQuoted(trimmed).split(/[。！？!?]/)) {
        const s = sentence.trim();
        if (flagged.has(s)) {
          findings.push({
            line: lineNo,
            column: 1,
            type: 'verbatim-repeat',
            severity: 'blocking',
            message: `长句复读（同句出现 ${counts.get(s).count} 次）：疑似模型打转，重写、保留一处。`,
            excerpt: compact(s),
          });
          flagged.delete(s); // report each repeated sentence once, at its first occurrence
        }
      }
    }
  }

  return findings;
}

function findTruncation(content) {
  const body = content.filter((c) => isContent(c.trimmed));
  if (body.length === 0) return [];
  const last = body[body.length - 1];
  // a finished chapter ends on terminal/closing punctuation; otherwise it was cut off.
  if (/[。.！？!?…”"』」）)】]$/.test(last.trimmed)) return [];
  return [{
    line: last.lineNo,
    column: last.trimmed.length,
    type: 'truncated',
    severity: 'blocking',
    message: '疑似截断：正文末尾未以句末/收尾标点结束，可能被模型中途切断；补完结尾或重写收尾。',
    excerpt: compact(last.trimmed.slice(-24)),
  }];
}

function findPlaceholders(content) {
  const findings = [];
  for (const { trimmed, lineNo } of content) {
    if (!isContent(trimmed)) continue;
    const quoteRanges = quotedRanges(trimmed);
    for (const { re, label, hard } of PLACEHOLDER_PATTERNS) {
      const matches = findAllMatches(trimmed, re);
      // soft 拒绝语只有命中本身落在台词里才豁免；本行别处有引号不能让叙述层泄漏逃逸。
      const m = hard
        ? matches[0]
        : matches.find((candidate) => !isRangeQuoted(quoteRanges, candidate.index, candidate[0].length));
      if (m) {
        findings.push({
          line: lineNo,
          column: (m.index || 0) + 1,
          type: 'placeholder-leak',
          severity: 'blocking',
          message: `${label}：正文混入元信息/拒绝语/占位符，重写本段干净落地。`,
          excerpt: compact(trimmed.slice(Math.max(0, (m.index || 0) - 4), (m.index || 0) + 20)),
        });
        break; // one finding per line is enough
      }
    }
  }
  return findings;
}

function findMetaLeak(content) {
  const findings = [];
  let firstContentSeen = false;
  for (const { trimmed, lineNo } of content) {
    if (!isContent(trimmed)) continue;
    if (!firstContentSeen) {
      firstContentSeen = true;
      // 标题行（第N章 章名，无 ## 前缀时也算）属「标题行以外的正文」之外，排除
      if (/^第[一二三四五六七八九十百千万两0-9]+章/.test(trimmed)) continue;
    }
    const quoteRanges = quotedRanges(trimmed);
    let m = preferUnquotedMatch(findAllMatches(trimmed, META_CHAPTER_REF_RE), quoteRanges);
    if (m) {
      const dialogue = isRangeQuoted(quoteRanges, m.index, m[0].length);
      findings.push({
        line: lineNo,
        column: m.index + 1,
        type: 'meta-leak',
        severity: dialogue ? 'advisory' : 'blocking',
        message: `章号引用泄漏：「${m[0]}」是写作时用的章节编号，正文里不该出现；改成角色当下可感知的时间锚点（那年秋天／她还住在庄后那阵子），不要换成「第13章」——换个写法仍是同一个毛病。${dialogue ? '例外：角色在故事内真实讨论书稿章节时，台词里可能合法。' : ''}`,
        excerpt: compact(trimmed.slice(Math.max(0, m.index - 8), m.index + 20)),
      });
      continue;
    }
    m = preferUnquotedMatch([
      ...findAllMatches(trimmed, META_TIER1_RE),
      ...findAllMatches(trimmed, META_PLANNING_MARKER_RE),
    ], quoteRanges);
    if (m) {
      const dialogue = isRangeQuoted(quoteRanges, m.index, m[0].length);
      // tier1 纯工程词正文里几乎永不合法→blocking；但写手/编剧题材里角色在故事内真讨论创作，
      // 台词（对话行）里可能合法，降级为 advisory（仍报告，交人/LLM 判，不强制回炉）。
      findings.push({
        line: lineNo,
        column: m.index + 1,
        type: 'meta-leak',
        severity: dialogue ? 'advisory' : 'blocking',
        message: `工程词泄漏：「${m[0]}」是写作流水线术语，正文里不该出现；改成角色/场景内表达。${dialogue ? '例外：角色为作者/编剧、在故事内真实讨论创作时，台词里可能合法。' : ''}`,
        excerpt: compact(trimmed.slice(Math.max(0, m.index - 6), m.index + 18)),
      });
      continue; // tier1 命中即可，不再叠 tier2
    }
    m = preferUnquotedMatch(findAllMatches(trimmed, META_TIER2_RE), quoteRanges);
    if (m) {
      findings.push({
        line: lineNo,
        column: m.index + 1,
        type: 'meta-leak',
        severity: 'advisory',
        message: `元信息泄漏：「${m[0]}」疑似工程/章节结构词混入正文；改成角色当下可感知的事件锚点或相对时间。例外：角色在故事内真实阅读/讨论「第X章」、真身为作者/读者、或故事内系统/界面用语。`,
        excerpt: compact(trimmed.slice(Math.max(0, m.index - 6), m.index + 18)),
      });
    }
  }
  return findings;
}

function emptyLanguageWhitelist() {
  return { tokens: new Set(), phrases: new Set(), source: null };
}

// 从正文文件所在目录逐级向上找最近的项目白名单。绝不回退到调用者的 cwd：
// 一次扫多个项目时，cwd 属于 A 项目不能让 A 的白名单豁免 B 项目。读取失败时保持 report-only。
function loadLanguageWhitelist(filePath) {
  const candidates = [];
  let current = path.dirname(filePath);
  while (true) {
    candidates.push(path.join(current, '.deslop-whitelist'));
    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }
  const whitelistPath = candidates.find((candidate) => fs.existsSync(candidate));
  if (!whitelistPath) return emptyLanguageWhitelist();

  try {
    const tokens = new Set();
    const phrases = new Set();
    for (const rawLine of fs.readFileSync(whitelistPath, 'utf8').split(/\r?\n/)) {
      if (/^\s*#/.test(rawLine)) continue;
      const entry = rawLine.replace(/\s+#.*$/, '').trim();
      if (!entry || !/[A-Za-z]/.test(entry) || CJK_CHAR_RE.test(entry)) {
        CJK_CHAR_RE.lastIndex = 0;
        continue;
      }
      CJK_CHAR_RE.lastIndex = 0;
      if (new RegExp(`^${LATIN_TOKEN_SOURCE}$`).test(entry)) tokens.add(entry);
      else {
        const phrase = normalizeEnglishPhrase(entry);
        if (phrase) phrases.add(phrase);
      }
    }
    return { tokens, phrases, source: whitelistPath };
  } catch (_) {
    return emptyLanguageWhitelist();
  }
}

function normalizeEnglishPhrase(text) {
  let normalized = text.trim();
  const outerPairs = [['“', '”'], ['‘', '’'], ['「', '」'], ['『', '』'], ['"', '"'], ["'", "'"]];
  let changed = true;
  while (changed && normalized.length >= 2) {
    changed = false;
    for (const [open, close] of outerPairs) {
      if (normalized.startsWith(open) && normalized.endsWith(close)) {
        normalized = normalized.slice(open.length, -close.length).trim();
        changed = true;
        break;
      }
    }
  }
  return normalized.replace(/[。！？.!?]+$/, '').trim().replace(/\s+/g, ' ');
}

function isWhitelistedToken(token, whitelist) {
  return whitelist.tokens.has(token);
}

function isWhitelistedPhrase(text, whitelist) {
  const normalized = normalizeEnglishPhrase(text);
  return normalized.length > 0 && whitelist.phrases.has(normalized);
}

// 每个区间都记录真正的引号内容边界，判断命中时看 offset，而不是“本行出现过任意引号”。
// ASCII 单引号若两侧都是字母，视为 can't 一类撇号，不当成台词界线。
function quotedRanges(text) {
  const ranges = [];
  const directional = [['「', '」'], ['『', '』'], ['【', '】'], ['“', '”'], ['‘', '’']];
  for (const [open, close] of directional) {
    let cursor = 0;
    while (cursor < text.length) {
      const start = text.indexOf(open, cursor);
      if (start < 0) break;
      const closeAt = text.indexOf(close, start + open.length);
      if (closeAt < 0) break;
      ranges.push({ start, contentStart: start + open.length, contentEnd: closeAt, end: closeAt + close.length });
      cursor = closeAt + close.length;
    }
  }
  for (const quote of ['"', "'"]) {
    const points = [];
    for (let i = 0; i < text.length; i += 1) {
      if (text[i] !== quote) continue;
      if (quote === "'" && /[A-Za-z]/.test(text[i - 1] || '') && /[A-Za-z]/.test(text[i + 1] || '')) continue;
      points.push(i);
    }
    for (let i = 0; i + 1 < points.length; i += 2) {
      ranges.push({ start: points[i], contentStart: points[i] + 1, contentEnd: points[i + 1], end: points[i + 1] + 1 });
    }
  }
  return ranges.sort((a, b) => a.start - b.start || a.end - b.end);
}

function quoteRangeIndexAt(ranges, start, length = 1) {
  const end = start + Math.max(length, 1);
  return ranges.findIndex((range) => start >= range.contentStart && end <= range.contentEnd);
}

function isRangeQuoted(ranges, start, length = 1) {
  return quoteRangeIndexAt(ranges, start, length) >= 0;
}

function findAllMatches(text, pattern) {
  const flags = pattern.flags.includes('g') ? pattern.flags : `${pattern.flags}g`;
  const scanner = new RegExp(pattern.source, flags);
  const matches = [];
  let match;
  while ((match = scanner.exec(text)) !== null) {
    matches.push(match);
    if (match[0].length === 0) scanner.lastIndex += 1;
  }
  return matches;
}

function preferUnquotedMatch(matches, ranges) {
  const ordered = [...matches].sort((a, b) => a.index - b.index);
  return ordered.find((match) => !isRangeQuoted(ranges, match.index, match[0].length)) || ordered[0];
}

function maskRange(chars, start, end) {
  for (let i = Math.max(0, start); i < Math.min(chars.length, end); i += 1) chars[i] = ' ';
}

// 所有保护都做等长空格遮罩，保证后续 finding.column 与原文严格对齐。
function maskProtectedLatin(text) {
  const chars = text.split('');
  const maskMatches = (pattern, rangeForMatch = (match) => [match.index, match.index + match[0].length]) => {
    for (const match of findAllMatches(text, pattern)) {
      const [start, end] = rangeForMatch(match);
      maskRange(chars, start, end);
    }
  };

  // Markdown inline code；fenced code 已在 scanDocument 收集正文行时整块排除。
  maskMatches(/`+[^`\n]*`+/g);
  // Markdown link 的 label 仍属于可见正文，只保护目标和可选 title。
  maskMatches(/\]\(\s*(?:<[^>\n]*>|[^)\n]*)\)/g, (match) => {
    const openOffset = match[0].indexOf('(');
    return [match.index + openOffset + 1, match.index + match[0].length - 1];
  });
  // Reference-style link 的第二个 `docs` 只是不可见 id；第一个 label 仍照常扫描。
  maskMatches(/\]\s*\[([A-Za-z0-9_.-]+)\]/g, (match) => {
    const offset = match[0].lastIndexOf(match[1]);
    return [match.index + offset, match.index + offset + match[1].length];
  });
  maskMatches(/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi);
  maskMatches(/(?:https?:\/\/|ftp:\/\/|www\.)[^\s<>"'”’」』】)）]+/gi);
  // 绝对/相对文件路径、文件名与独立扩展名。路径段允许 Unicode，末级也不强制扩展名；
  // 紧跟的中英文句子标点不吃进遮罩。
  maskMatches(/(?:[A-Za-z]:[\\/]|\.{1,2}[\\/]|\/)(?:[^\s/\\<>"'“”‘’「」『』【】()（）,，。；;：:!！?？、]+[\\/])*[^\s/\\<>"'“”‘’「」『』【】()（）,，。；;：:!！?？、]+/g);
  maskMatches(/(?<![A-Za-z0-9])(?:[^\s/\\<>"'“”‘’「」『』【】()（）,，。；;：:!！?？、]+[\\/])+[^\s/\\<>"'“”‘’「」『』【】()（）,，。；;：:!！?？、]+(?![A-Za-z0-9])/g);
  maskMatches(/(?<![A-Za-z0-9])(?:[A-Za-z0-9_-]+\.)+[A-Za-z][A-Za-z0-9]{0,11}(?![A-Za-z0-9])/g);
  maskMatches(/(?<![A-Za-z0-9])\.[A-Za-z][A-Za-z0-9]{0,11}(?![A-Za-z0-9])/g);
  // 只保护纯数字。缩写、型号、科学名称、分组字母和剧情代号
  // 都属于叙事内容，不得由检测器猜测放行；只有用户单独确认逐字保留后，
  // 才能写入 .deslop-whitelist 精确登记。这与独立 language_gate.js 的边界一致。
  maskMatches(/(?<![A-Za-z0-9])\d+(?:[.,:/-]\d+)*%?(?![A-Za-z0-9])/g);
  return chars.join('');
}

function resolveDocumentLanguage(content, requested) {
  if (requested !== 'auto') return requested;
  const visible = content
    .filter(({ trimmed }) => isContent(trimmed))
    .map(({ trimmed }) => maskProtectedLatin(trimmed))
    .join('\n');
  const cjk = (visible.match(CJK_CHAR_RE) || []).length;
  const latin = (visible.match(LATIN_LETTER_RE) || []).length;
  if (cjk === 0) return 'en';
  if (latin === 0) return 'zh';
  const cjkShare = cjk / (cjk + latin);
  // auto 对中文写作保守：只要存在一个最短中文句子骨架（≥2 汉字）就开 zh 门。
  // 否则“她说：The room was quiet.”会因英文较长而被反判成英文。真英文项目用
  // `--language=en`；标题/front matter 本就不参与这个判定。
  return cjk >= 2 || cjkShare >= 0.18 ? 'zh' : 'en';
}

function latinTokens(text) {
  return findAllMatches(text, LATIN_TOKEN_RE).map((match) => ({
    value: match[0],
    index: match.index,
    end: match.index + match[0].length,
    letters: (match[0].match(LATIN_LETTER_RE) || []).length,
  }));
}

function isOrdinaryEnglishToken(token, whitelist) {
  return !isWhitelistedToken(token.value, whitelist);
}

function isEnglishOnlySegment(text) {
  if (!/[A-Za-z]/.test(text) || CJK_CHAR_RE.test(text)) {
    CJK_CHAR_RE.lastIndex = 0;
    return false;
  }
  CJK_CHAR_RE.lastIndex = 0;
  const residue = text
    .replace(new RegExp(LATIN_TOKEN_SOURCE, 'g'), '')
    .replace(/[\s.,;:!?，。；：！？、'"“”‘’「」『』【】()[\]{}<>*_~…—–\->]/g, '');
  return residue.length === 0;
}

function isCovered(covered, start, end) {
  return covered.some((range) => start >= range.start && end <= range.end);
}

function cover(covered, start, end) {
  covered.push({ start, end });
}

function lineEnglishCore(text) {
  const prefix = /^\s*(?:(?:>|[-+*])\s+|\d+[.)]\s+)/.exec(text);
  const start = prefix ? prefix[0].length : 0;
  return { start, text: text.slice(start).trimEnd() };
}

function sentenceRanges(text) {
  const ranges = [];
  let start = 0;
  for (let i = 0; i < text.length; i += 1) {
    if (!/[。！？.!?]/.test(text[i])) continue;
    ranges.push({ start, end: i + 1 });
    start = i + 1;
  }
  if (start < text.length) ranges.push({ start, end: text.length });
  return ranges;
}

function sourceColumn(sourceText, codeUnitIndex) {
  return Array.from(sourceText.slice(0, Math.max(0, codeUnitIndex))).length + 1;
}

function languageFinding(lineNo, column, severity, message, excerpt) {
  return { line: lineNo, column, type: 'language-leak', severity, message, excerpt: compact(excerpt) };
}

function findLanguageLeak(content, whitelist) {
  const findings = [];
  for (const { text, trimmed, lineNo } of content) {
    if (!isContent(trimmed)) continue;
    const leadingCodeUnits = text.indexOf(trimmed);
    const columnAt = (trimmedIndex) => sourceColumn(text, leadingCodeUnits + trimmedIndex);
    const masked = maskProtectedLatin(trimmed);
    const tokens = latinTokens(masked);
    if (tokens.length === 0) continue;
    const ranges = quotedRanges(trimmed);
    const covered = [];

    // 完整英文台词：引号内容除标点外全为英文。未精确登记的
    // TitleCase、短词与全大写缩写同样 blocking。
    for (const range of ranges) {
      const segment = masked.slice(range.contentStart, range.contentEnd);
      if (!isEnglishOnlySegment(segment)) continue;
      const segmentTokens = latinTokens(segment).map((token) => ({
        ...token,
        index: token.index + range.contentStart,
        end: token.end + range.contentStart,
      }));
      const ordinary = segmentTokens.filter((token) => isOrdinaryEnglishToken(token, whitelist));
      if (ordinary.length === 0) continue;
      const original = trimmed.slice(range.contentStart, range.contentEnd);
      if (isWhitelistedPhrase(original, whitelist) || (segmentTokens.length === 1 && isWhitelistedToken(segmentTokens[0].value, whitelist))) {
        cover(covered, range.contentStart, range.contentEnd);
        continue;
      }
      // 整个引号内只有英文时就是完整英文台词；“Go”即使没句号也不能逃逸。
      // 确属专名/引文时用精确白名单表达意图。
      findings.push(languageFinding(
        lineNo,
        columnAt(range.contentStart),
        'blocking',
        `完整英文台词泄漏：「${compact(original)}」未在 .deslop-whitelist 精确登记；中文项目应改成中文台词，只有用户单独确认逐字保留后才能登记完整短句。`,
        trimmed.slice(Math.max(0, range.start - 8), Math.min(trimmed.length, range.end + 8)),
      ));
      cover(covered, range.contentStart, range.contentEnd);
    }

    // 整行/整段英文。在明确 zh 模式下不再用“行内 CJK ≥50%”当门槛；保护区被遮罩后，
    // 只要是两个以上普通英文词组成的纯英文正文行，就按 blocking 处理。
    const core = lineEnglishCore(masked);
    const coreEnd = core.start + core.text.length;
    const coreTokens = latinTokens(core.text).map((token) => ({ ...token, index: token.index + core.start, end: token.end + core.start }));
    const uncoveredCore = coreTokens.filter((token) => !isCovered(covered, token.index, token.end));
    const ordinaryCore = uncoveredCore.filter((token) => isOrdinaryEnglishToken(token, whitelist));
    const singleWordSentence = ordinaryCore.length === 1 && /[。！？.!?]\s*$/.test(core.text);
    if (isEnglishOnlySegment(core.text) && (ordinaryCore.length >= 2 || singleWordSentence)) {
      const original = trimmed.slice(core.start, coreEnd);
      if (isWhitelistedPhrase(original, whitelist)) {
        cover(covered, core.start, coreEnd);
      } else if (ordinaryCore.length > 0) {
        findings.push(languageFinding(
          lineNo,
          columnAt(core.start),
          'blocking',
          `纯英文句段泄漏：「${compact(original)}」出现在中文正文中；应整句改成中文，只有用户单独确认逐字保留后才能在 .deslop-whitelist 精确登记。`,
          original,
        ));
        cover(covered, core.start, coreEnd);
      }
    }

    // 同一中文行里独立出现的英文句（例如“她停住。Go away. 她没回头。”）。
    for (const sentence of sentenceRanges(masked)) {
      if (isCovered(covered, sentence.start, sentence.end)) continue;
      const segment = masked.slice(sentence.start, sentence.end).trim();
      if (!isEnglishOnlySegment(segment)) continue;
      const segmentTokens = latinTokens(segment)
        .map((token) => ({ ...token, index: token.index + sentence.start, end: token.end + sentence.start }))
        .filter((token) => !isCovered(covered, token.index, token.end))
        .filter((token) => isOrdinaryEnglishToken(token, whitelist));
      if (segmentTokens.length < 2) continue;
      const original = trimmed.slice(sentence.start, sentence.end).trim();
      if (isWhitelistedPhrase(original, whitelist)) {
        cover(covered, sentence.start, sentence.end);
        continue;
      }
      const first = trimmed.slice(sentence.start, sentence.end).search(/[A-Za-z]/);
      findings.push(languageFinding(
        lineNo,
        columnAt(sentence.start + Math.max(first, 0)),
        'blocking',
        `纯英文句段泄漏：「${compact(original)}」出现在中文正文中；整句改成中文，或确认剧情需要后精确登记。`,
        original,
      ));
      cover(covered, sentence.start, sentence.end);
    }

    // 连续 3 个以上普通英文词且字母总数 ≥12：即使英文占整行比例很低，也属于高置信泄漏。
    const candidates = tokens.filter((token) => !isCovered(covered, token.index, token.end));
    let run = [];
    const flushRun = () => {
      const uppercasePhrase = run.length >= 2 && run.every((token) => /^[A-Z]+$/.test(token.value));
      if (run.length < LANGUAGE_PHRASE_MIN_WORDS && !uppercasePhrase) {
        run = [];
        return;
      }
      const letters = run.reduce((sum, token) => sum + token.letters, 0);
      if (letters < LANGUAGE_PHRASE_MIN_LETTERS && !uppercasePhrase) {
        run = [];
        return;
      }
      const start = run[0].index;
      const end = run[run.length - 1].end;
      const original = trimmed.slice(start, end);
      if (isWhitelistedPhrase(original, whitelist)) cover(covered, start, end);
      else {
        findings.push(languageFinding(
          lineNo,
          columnAt(start),
          'blocking',
          `连续英文短语泄漏：「${compact(original)}」含 ${run.length} 个普通英文词；中文正文应改成中文表达。`,
          trimmed.slice(Math.max(0, start - 10), Math.min(trimmed.length, end + 10)),
        ));
        cover(covered, start, end);
      }
      run = [];
    };
    for (const token of candidates) {
      if (!isOrdinaryEnglishToken(token, whitelist)) {
        flushRun();
        continue;
      }
      if (run.length > 0) {
        const previous = run[run.length - 1];
        const sameQuote = quoteRangeIndexAt(ranges, previous.index, previous.value.length) === quoteRangeIndexAt(ranges, token.index, token.value.length);
        const gap = masked.slice(previous.end, token.index);
        if (!sameQuote || !/^[\s,，;；:：—–-]*$/.test(gap)) flushRun();
      }
      run.push(token);
    }
    flushRun();

    // Unicode 外文字母先于 ASCII token 扫描：覆盖全角/扩展拉丁、希腊、西里尔、
    // 罗马数字、带圈字母和数学字母。ASCII-only 片段留给下方既有规则处理。
    const unicodeForeignRun = /[\p{Script=Latin}\p{Script=Greek}\p{Script=Cyrillic}\u2160-\u2188\u24B6-\u24E9\u{1D400}-\u{1D7FF}]+/gu;
    for (const match of masked.matchAll(unicodeForeignRun)) {
      const value = match[0];
      if (/^[\x00-\x7F]+$/.test(value)) continue;
      const start = match.index;
      const end = start + value.length;
      if (isCovered(covered, start, end)) continue;
      if (isWhitelistedToken(value, whitelist) || isWhitelistedPhrase(value, whitelist)) {
        cover(covered, start, end);
        continue;
      }
      findings.push(languageFinding(
        lineNo,
        columnAt(start),
        'blocking',
        `Unicode 外文字母泄漏：「${value}」出现在中文正文中；全角、扩展字母和常见混淆字符同样禁止，应改成中文；确需保留时必须先由用户单独确认并精确登记。`,
        trimmed.slice(Math.max(0, start - 10), Math.min(trimmed.length, end + 14)),
      ));
      cover(covered, start, end);
    }

    // 剩余单词：未授权 ASCII token 全部 blocking；TitleCase、
    // mixed-case 与 1-3 字母短词同样 blocking；合法专名只能通过精确白名单授权。
    for (const token of tokens) {
      if (isCovered(covered, token.index, token.end)) continue;
      if (isWhitelistedToken(token.value, whitelist)) continue;
      const inDialogue = isRangeQuoted(ranges, token.index, token.value.length);
      const lowercaseLong = /^[a-z]+(?:['’][a-z]+)?$/.test(token.value) && token.letters >= 4;
      if (lowercaseLong) {
        findings.push(languageFinding(
          lineNo,
          columnAt(token.index),
          'blocking',
          `裸英文词泄漏：「${token.value}」出现在中文正文${inDialogue ? '的中英混合台词' : '叙述层'}；中英混写属于 blocking，应改成中文称呼；确需逐字保留时必须先由用户单独确认并在 .deslop-whitelist 精确登记。`,
          trimmed.slice(Math.max(0, token.index - 10), Math.min(trimmed.length, token.end + 14)),
        ));
      } else {
        findings.push(languageFinding(
          lineNo,
          columnAt(token.index),
          'blocking',
          `英文专名/短词泄漏：「${token.value}」出现在中文正文中；不再默认豁免专名、缩写或短词，应改成中文；确需逐字保留时必须先由用户单独确认并在 .deslop-whitelist 精确登记。`,
          trimmed.slice(Math.max(0, token.index - 10), Math.min(trimmed.length, token.end + 14)),
        ));
      }
    }
  }
  return findings;
}

function hasYamlFrontMatter(lines) {
  if (!lines[0] || lines[0].trim() !== '---') return false;
  let sawYamlField = false;
  for (let i = 1; i < Math.min(lines.length, 40); i += 1) {
    const trimmed = lines[i].trim();
    if (trimmed === '---') return sawYamlField;
    if (/^[A-Za-z0-9_-]+:\s*/.test(trimmed)) sawYamlField = true;
  }
  return false;
}

function compact(text) {
  const normalized = text.replace(/\s+/g, ' ').trim();
  return normalized.length > 80 ? `${normalized.slice(0, 77)}...` : normalized;
}
