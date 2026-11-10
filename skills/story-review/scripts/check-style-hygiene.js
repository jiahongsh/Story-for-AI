#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');

const DEFAULT_PROFILE = 'publish-clean';
const PROFILE_POLICIES = {
  'publish-clean': {
    emoji: 'forbid',
    emoticon: 'forbid',
    mars: 'forbid',
    punctuation: 'forbid',
  },
  'dialogue-flex': {
    emoji: 'dialogue',
    emoticon: 'dialogue',
    mars: 'dialogue',
    punctuation: 'forbid',
  },
  permissive: {
    emoji: 'review',
    emoticon: 'review',
    mars: 'review',
    punctuation: 'review',
  },
};

const POLICY_KEY_MAP = new Map([
  ['表情符号', 'emoji'],
  ['绘文字', 'emoji'],
  ['颜文字', 'emoticon'],
  ['火星文', 'mars'],
  ['重复标点', 'punctuation'],
  ['装饰标点', 'punctuation'],
]);

const POLICY_VALUE_MAP = new Map([
  ['禁止', 'forbid'],
  ['对白内允许', 'dialogue'],
  ['引用内允许', 'dialogue'],
  ['复核', 'review'],
  ['提示', 'review'],
  ['允许', 'allow'],
]);

const MARS_PATTERNS = [
  '伱(?:好|们|是|的)',
  '莪(?:们|是|的|要|想)',
  '吥(?:要|是|会|能|懂|知道)',
  '偶滴',
  '木有',
  '有木有',
  '肿么',
  '酱紫',
  '表酱',
  '伦家',
  '灰常',
  '内牛满面',
  '么么哒',
  '萌萌哒',
  '敲可爱',
  '炒鸡(?:可爱|喜欢|厉害)',
  '桑心',
  '介个',
  '乃们',
  '神马都是浮云',
];

function usage() {
  console.error('Usage: node check-style-hygiene.js [--check] [--json] [--fail-on=blocking|all] [--profile=publish-clean|dialogue-flex|permissive] [--style <文风.md>] <正文文件...>');
}

function parseArgs(argv) {
  const options = {
    json: false,
    failOn: null,
    profile: DEFAULT_PROFILE,
    explicitStyle: null,
    files: [],
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--check') continue;
    if (arg === '--json') options.json = true;
    else if (arg === '--fail-on') options.failOn = argv[++index];
    else if (arg.startsWith('--fail-on=')) options.failOn = arg.slice('--fail-on='.length);
    else if (arg === '--profile') options.profile = argv[++index];
    else if (arg.startsWith('--profile=')) options.profile = arg.slice('--profile='.length);
    else if (arg === '--style') options.explicitStyle = argv[++index];
    else if (arg.startsWith('--style=')) options.explicitStyle = arg.slice('--style='.length);
    else if (arg === '-h' || arg === '--help') options.help = true;
    else options.files.push(arg);
  }
  if (!PROFILE_POLICIES[options.profile]) throw new Error(`unknown profile: ${options.profile}`);
  if (options.failOn && !['blocking', 'all'].includes(options.failOn)) throw new Error(`unknown --fail-on value: ${options.failOn}`);
  return options;
}

function compact(value, limit = 120) {
  const text = String(value).replace(/\s+/g, ' ').trim();
  return text.length > limit ? `${text.slice(0, limit - 1)}…` : text;
}

function locate(text, offset) {
  const before = text.slice(0, offset);
  const line = before.split('\n').length;
  const lineStart = before.lastIndexOf('\n') + 1;
  const rawEnd = text.indexOf('\n', offset);
  const lineEnd = rawEnd < 0 ? text.length : rawEnd;
  return {
    line,
    column: offset - lineStart + 1,
    context: compact(text.slice(lineStart, lineEnd)),
  };
}

function findStyleFile(inputPath, explicitStyle) {
  if (explicitStyle) {
    const resolved = path.resolve(explicitStyle);
    if (!fs.existsSync(resolved)) throw new Error(`style file not found: ${resolved}`);
    return resolved;
  }
  if (inputPath === '-') return null;
  let directory = path.dirname(path.resolve(inputPath));
  while (true) {
    const candidate = path.join(directory, '设定', '文风.md');
    if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) return candidate;
    const parent = path.dirname(directory);
    if (parent === directory) return null;
    directory = parent;
  }
}

function loadWhitelist(inputPath) {
  if (inputPath === '-') return { path: null, entries: [] };
  let directory = path.dirname(path.resolve(inputPath));
  while (true) {
    const candidate = path.join(directory, '.style-hygiene-whitelist');
    if (fs.existsSync(candidate)) {
      const entries = fs.readFileSync(candidate, 'utf8')
        .split(/\r?\n/)
        .map((line) => line.replace(/\s+#.*$/, '').trim())
        .filter((line) => line && !line.startsWith('#'));
      return { path: candidate, entries: [...new Set(entries)] };
    }
    const parent = path.dirname(directory);
    if (parent === directory) return { path: null, entries: [] };
    directory = parent;
  }
}

function parseStylePolicy(stylePath, baseProfile) {
  const policy = { ...PROFILE_POLICIES[baseProfile] };
  let profile = baseProfile;
  if (!stylePath) return { profile, policy, stylePath: null };
  const text = fs.readFileSync(stylePath, 'utf8');
  const preset = text.match(/^\s*[-*]?\s*文风卫生\s*[:：]\s*(出版级纯中文|对白弹性|宽松复核)\s*$/mu);
  if (preset) {
    profile = preset[1] === '对白弹性' ? 'dialogue-flex' : preset[1] === '宽松复核' ? 'permissive' : 'publish-clean';
    Object.assign(policy, PROFILE_POLICIES[profile]);
  }
  const optionPattern = /^\s*[-*]?\s*(表情符号|绘文字|颜文字|火星文|重复标点|装饰标点)\s*[:：]\s*(禁止|对白内允许|引用内允许|复核|提示|允许)\s*$/gmu;
  for (const match of text.matchAll(optionPattern)) {
    policy[POLICY_KEY_MAP.get(match[1])] = POLICY_VALUE_MAP.get(match[2]);
  }
  return { profile, policy, stylePath };
}

function markProtectedStructures(text, mask) {
  const patterns = [
    /```[\s\S]*?```/g,
    /`[^`\n]+`/g,
    /https?:\/\/[^\s<>()]+/gi,
    /\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b/g,
  ];
  for (const pattern of patterns) {
    pattern.lastIndex = 0;
    for (const match of text.matchAll(pattern)) mask.fill(1, match.index, match.index + match[0].length);
  }
}

function markWhitelist(text, mask, entries) {
  for (const entry of entries) {
    let offset = 0;
    while (offset <= text.length - entry.length) {
      const start = text.indexOf(entry, offset);
      if (start < 0) break;
      mask.fill(1, start, start + entry.length);
      offset = start + Math.max(entry.length, 1);
    }
  }
}

function quoteRanges(text) {
  const ranges = [];
  const pairs = new Map([['“', '”'], ['「', '」'], ['『', '』']]);
  const stack = [];
  let asciiStart = null;
  for (let index = 0; index < text.length;) {
    const char = String.fromCodePoint(text.codePointAt(index));
    if (pairs.has(char)) stack.push({ close: pairs.get(char), start: index });
    else if (stack.length && char === stack[stack.length - 1].close) {
      const item = stack.pop();
      ranges.push([item.start, index + char.length]);
    } else if (char === '"') {
      if (asciiStart === null) asciiStart = index;
      else {
        ranges.push([asciiStart, index + 1]);
        asciiStart = null;
      }
    }
    index += char.length;
  }
  return ranges.sort((a, b) => a[0] - b[0]);
}

function isQuoted(start, end, ranges) {
  return ranges.some(([left, right]) => start >= left && end <= right);
}

function isMasked(mask, start, end) {
  for (let index = start; index < end; index += 1) if (mask[index]) return true;
  return false;
}

function severityFor(mode, quoted) {
  if (mode === 'allow') return null;
  if (mode === 'dialogue' && quoted) return null;
  if (mode === 'review') return 'advisory';
  return 'blocking';
}

function pushFinding(findings, text, mask, ranges, match, type, policyKey, message, indexOffset = 0, valueOverride = null) {
  const start = match.index + indexOffset;
  const value = valueOverride || match[0].slice(indexOffset);
  const end = start + value.length;
  if (!value || isMasked(mask, start, end)) return;
  const quoted = isQuoted(start, end, ranges);
  const severity = severityFor(policyKey, quoted);
  if (!severity) return;
  findings.push({
    severity,
    type,
    text: compact(value, 60),
    ...locate(text, start),
    action: severity === 'blocking' ? 'return_to_writer_and_rerun' : 'review_in_context',
    message,
  });
  mask.fill(1, start, end);
}

function scan(text, policy, whitelistEntries = []) {
  const findings = [];
  const mask = new Uint8Array(text.length);
  markProtectedStructures(text, mask);
  markWhitelist(text, mask, whitelistEntries);
  const ranges = quoteRanges(text);

  const emojiPattern = /(?:\p{Extended_Pictographic}(?:\uFE0E|\uFE0F)?(?:\u200D\p{Extended_Pictographic}(?:\uFE0E|\uFE0F)?)*)|(?:[\u{1F1E6}-\u{1F1FF}]{2})|(?:[#*0-9]\uFE0F?\u20E3)/gu;
  for (const match of text.matchAll(emojiPattern)) {
    pushFinding(findings, text, mask, ranges, match, 'emoji-symbol', policy.emoji, '正文出现表情符号或装饰性绘文字；出版级中文正文应改成角色动作、台词或普通标点。');
  }

  const emoticonPatterns = [
    /\^[_\-oO.]{1,4}\^/gu,
    /[TQ][_.-]?[TQ]/gu,
    /[>＜][_.-]?[<＞]/gu,
    /[（(](?:￣|▽|ω|へ|ノ|益|Д|д|口|囧|Ｔ|T|Q|A|_|＾|\^|・){2,}[）)]/gu,
  ];
  for (const pattern of emoticonPatterns) {
    for (const match of text.matchAll(pattern)) {
      pushFinding(findings, text, mask, ranges, match, 'emoticon', policy.emoticon, '正文出现颜文字；应用人物动作和对白表达情绪，不用聊天装饰符号代替叙事。');
    }
  }
  const asciiEmoticon = /(^|[^\p{L}\p{N}])([:;=8xX][\-^']?[)(/\\DPpOo])(?=$|[^\p{L}\p{N}])/gmu;
  for (const match of text.matchAll(asciiEmoticon)) {
    pushFinding(findings, text, mask, ranges, match, 'emoticon', policy.emoticon, '正文出现颜文字；应用人物动作和对白表达情绪，不用聊天装饰符号代替叙事。', match[1].length, match[2]);
  }

  const punctuationPattern = /[!！?？]{3,}|[。\.]{3,}|[~～]{2,}|[❤♥♡★☆◆◇]{2,}/gu;
  for (const match of text.matchAll(punctuationPattern)) {
    pushFinding(findings, text, mask, ranges, match, 'punctuation-spam', policy.punctuation, '正文出现重复或装饰性标点堆砌；保留真实语气所需的最少标点。');
  }

  const marsPattern = new RegExp(MARS_PATTERNS.join('|'), 'gu');
  for (const match of text.matchAll(marsPattern)) {
    pushFinding(findings, text, mask, ranges, match, 'mars-text', policy.mars, '正文出现火星文或陈旧聊天体；应改回当前人物和时代能自然使用的中文。');
  }

  const invisiblePattern = /[\u200B\u200C\u2060\uFEFF]/gu;
  for (const match of text.matchAll(invisiblePattern)) {
    pushFinding(findings, text, mask, ranges, match, 'invisible-decoration', 'forbid', '正文出现零宽或不可见装饰字符；应删除并重新检查相邻文字。');
  }

  return findings.sort((a, b) => a.line - b.line || a.column - b.column);
}

function readInput(inputPath) {
  if (inputPath === '-') return fs.readFileSync(0, 'utf8');
  return fs.readFileSync(path.resolve(inputPath), 'utf8');
}

function main(argv) {
  let options;
  try {
    options = parseArgs(argv);
  } catch (error) {
    console.error(`check-style-hygiene: ${error.message}`);
    usage();
    return 3;
  }
  if (options.help) {
    usage();
    return 0;
  }
  if (!options.files.length) {
    usage();
    return 3;
  }

  const reports = [];
  try {
    for (const inputPath of options.files) {
      const text = readInput(inputPath);
      const stylePath = findStyleFile(inputPath, options.explicitStyle);
      const style = parseStylePolicy(stylePath, options.profile);
      const whitelist = loadWhitelist(inputPath);
      const findings = scan(text, style.policy, whitelist.entries);
      reports.push({
        file: inputPath === '-' ? '-' : path.resolve(inputPath),
        profile: style.profile,
        policy: style.policy,
        style_file: style.stylePath,
        whitelist_file: whitelist.path,
        findings,
      });
    }
  } catch (error) {
    console.error(`check-style-hygiene: ${error.message}`);
    return 3;
  }

  const findings = reports.flatMap((report) => report.findings.map((finding) => ({ file: report.file, ...finding })));
  const blocking = findings.filter((finding) => finding.severity === 'blocking').length;
  const advisory = findings.filter((finding) => finding.severity === 'advisory').length;
  const result = {
    status: blocking ? 'rejected' : advisory ? 'review' : 'passed',
    blocking,
    advisory,
    reports,
    next_action: blocking ? 'revise_reported_units_and_rerun' : advisory ? 'review_advisories_in_context' : 'continue_workflow',
  };

  if (options.json) console.log(JSON.stringify(result, null, 2));
  else if (!findings.length) console.log(`PASS: style hygiene clean (${reports.length} file${reports.length === 1 ? '' : 's'})`);
  else {
    console.error(`STYLE HYGIENE: ${blocking} blocking, ${advisory} advisory`);
    for (const finding of findings) {
      console.error(`  ${finding.file}:${finding.line}:${finding.column} [${finding.severity}/${finding.type}] ${finding.text}`);
      console.error(`    ${finding.message}`);
    }
  }

  if (options.failOn === 'all' && findings.length) return 2;
  if (options.failOn === 'blocking' && blocking) return 2;
  return 0;
}

process.exitCode = main(process.argv.slice(2));
