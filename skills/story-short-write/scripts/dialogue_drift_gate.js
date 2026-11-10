#!/usr/bin/env node

/**
 * Detect long-horizon drift toward repetitive Chinese dialogue attribution.
 *
 * This gate does not ban ordinary attribution verbs and does not rewrite prose.
 * It compares the current chapter with early accepted chapters and recent
 * chapters, then rejects only clear density, repetition, or consecutive-tag
 * degeneration.
 */

const fs = require('fs');
const path = require('path');

const VERBS = [
  '低声说道', '沉声说道', '冷声说道', '缓缓说道', '淡淡说道',
  '开口说道', '开口说', '说道', '问道', '反问道', '回答道', '答道',
  '喊道', '叫道', '嘀咕道', '回答', '反问', '嘀咕', '说', '问', '答', '喊', '叫',
];
const ATTRIBUTION_RE = new RegExp(`(${VERBS.join('|')})(?=[，。！？：；])`, 'gu');
const NON_SPEECH_PREFIX_RE = /(?:没有|没|未|未曾|不曾|不想|不愿|不肯|拒绝|避免|懒得|无意|只想|想|想要|打算|准备|正要|刚要|试图|来不及)\s*$/u;
const OPEN_QUOTE_RE = /^[，,:：\s]*[“「『"]/u;
const POST_QUOTE_TAG_RE = /^[，,\s]*[\p{Script=Han}]{1,12}$/u;

function isHighConfidenceAttribution(line, verbIndex, verb) {
  const before = line.slice(0, verbIndex);
  if (NON_SPEECH_PREFIX_RE.test(before.slice(-12))) return false;
  const afterVerb = line.slice(verbIndex + verb.length);
  if (OPEN_QUOTE_RE.test(afterVerb)) return true;
  const closeQuote = Math.max(before.lastIndexOf('”'), before.lastIndexOf('」'), before.lastIndexOf('』'), before.lastIndexOf('"'));
  if (closeQuote < 0) return false;
  return POST_QUOTE_TAG_RE.test(before.slice(closeQuote + 1));
}

const TRAILING_MODIFIER_RE = /(?:又|便|才|却|也|立刻|马上|忽然|低声|沉声|冷声|缓缓|淡淡地?)$/u;
const SUBJECT_RE = /(?:^|[“”「」。！？；，\s])([\p{Script=Han}]{1,6})$/u;

function extractSubject(line, verbIndex) {
  let before = line.slice(0, verbIndex);
  before = before.replace(TRAILING_MODIFIER_RE, '');
  const match = before.match(SUBJECT_RE);
  if (!match) return null;
  const subject = match[1];
  if (subject.length === 1 && !['我', '你', '他', '她', '它'].includes(subject)) return null;
  return subject;
}

function parseArgs(argv) {
  const options = { json: false, baselineCount: 3, recentWindow: 3 };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--json') options.json = true;
    else if (arg === '--current') options.current = argv[++index];
    else if (arg === '--history-dir') options.historyDir = argv[++index];
    else if (arg === '--baseline-count') options.baselineCount = Number(argv[++index]);
    else if (arg === '--recent-window') options.recentWindow = Number(argv[++index]);
    else if (!arg.startsWith('--') && !options.current) options.current = arg;
    else throw new Error(`unknown argument: ${arg}`);
  }
  if (!options.current) throw new Error('missing --current <chapter-file>');
  return options;
}

function chapterNumber(filePath) {
  const match = path.basename(filePath).match(/第0*(\d+)章/);
  return match ? Number(match[1]) : null;
}

function familyOf(verb) {
  if (verb.includes('问')) return '问';
  if (verb.includes('说') || verb === '嘀咕' || verb === '嘀咕道') return '说';
  if (verb.includes('答')) return '答';
  if (verb.includes('喊') || verb.includes('叫')) return '喊叫';
  return verb;
}

function countMatches(text, regex) {
  return [...text.matchAll(regex)].length;
}

function analyze(text) {
  const lines = text.split(/\r?\n/);
  const occurrences = [];
  const verbs = new Map();
  const families = new Map();
  let dialogueTurns = 0;
  let consecutive = 0;
  let maxConsecutive = 0;

  lines.forEach((line, lineIndex) => {
    const turnsOnLine = countMatches(line, /[“「]/g);
    dialogueTurns += turnsOnLine;
    ATTRIBUTION_RE.lastIndex = 0;
    const lineOccurrences = [];
    for (const match of line.matchAll(ATTRIBUTION_RE)) {
      const verb = match[1];
      if (!isHighConfidenceAttribution(line, match.index, verb)) continue;
      const subject = extractSubject(line, match.index);
      const family = familyOf(verb);
      const item = {
        line: lineIndex + 1,
        column: match.index + 1,
        text: subject ? `${subject}${verb}` : verb,
        subject,
        verb,
        family,
        context: line.trim(),
      };
      occurrences.push(item);
      lineOccurrences.push(item);
      verbs.set(verb, (verbs.get(verb) || 0) + 1);
      families.set(family, (families.get(family) || 0) + 1);
    }

    if (turnsOnLine > 0 && lineOccurrences.length > 0) {
      consecutive += 1;
      maxConsecutive = Math.max(maxConsecutive, consecutive);
    } else if (line.trim()) {
      consecutive = 0;
    }
  });

  const attributionCount = occurrences.length;
  const density = dialogueTurns > 0 ? attributionCount / dialogueTurns : 0;
  const topVerb = [...verbs.entries()].sort((left, right) => right[1] - left[1])[0] || [null, 0];
  const topFamily = [...families.entries()].sort((left, right) => right[1] - left[1])[0] || [null, 0];

  return {
    dialogueTurns,
    attributionCount,
    density,
    maxConsecutive,
    topVerb: { value: topVerb[0], count: topVerb[1], ratio: attributionCount ? topVerb[1] / attributionCount : 0 },
    topFamily: { value: topFamily[0], count: topFamily[1], ratio: attributionCount ? topFamily[1] / attributionCount : 0 },
    occurrences,
  };
}

function mean(items, selector) {
  if (!items.length) return null;
  return items.reduce((sum, item) => sum + selector(item), 0) / items.length;
}

function loadHistory(currentPath, historyDir) {
  const currentNumber = chapterNumber(currentPath);
  if (currentNumber === null) return [];
  return fs.readdirSync(historyDir)
    .filter((name) => name.endsWith('.md'))
    .map((name) => path.join(historyDir, name))
    .map((filePath) => ({ filePath, number: chapterNumber(filePath) }))
    .filter((item) => item.number !== null && item.number < currentNumber)
    .sort((left, right) => left.number - right.number)
    .map((item) => ({
      file: item.filePath,
      number: item.number,
      metrics: analyze(fs.readFileSync(item.filePath, 'utf8')),
    }));
}

function evaluate(current, baseline, recent) {
  const findings = [];
  const advisories = [];
  const block = (code, message) => findings.push({ severity: 'blocking', code, message });
  const advise = (code, message) => advisories.push({ severity: 'advisory', code, message });

  if (current.dialogueTurns >= 6 && current.attributionCount >= 6 && current.density >= 0.72) {
    advise('attribution-density', `对白归属标记密度为 ${current.density.toFixed(2)}，需要结合场景清晰度复核`);
  }
  if (current.attributionCount >= 5 && current.topFamily.ratio >= 0.60) {
    advise('verb-family-repeat', `“${current.topFamily.value}”类标记占全部归属标记的 ${(current.topFamily.ratio * 100).toFixed(0)}%`);
  }
  if (current.attributionCount >= 4 && current.topVerb.count >= 4 && current.topVerb.ratio >= 0.50) {
    advise('same-verb-repeat', `“${current.topVerb.value}”重复 ${current.topVerb.count} 次`);
  }
  if (current.maxConsecutive >= 4) {
    block('consecutive-tagged-turns', `连续 ${current.maxConsecutive} 个对白行使用显式归属标记，需退回检查是否逐句报幕`);
  }

  const baselineDensity = mean(baseline, (item) => item.metrics.density);
  if (
    baselineDensity !== null
    && current.dialogueTurns >= 6
    && current.attributionCount >= 5
    && current.density >= 0.50
    && current.density >= baselineDensity + 0.25
    && current.density >= baselineDensity * 1.5
  ) {
    advise('baseline-drift', `本章密度 ${current.density.toFixed(2)}，明显高于前期基线 ${baselineDensity.toFixed(2)}`);
  }

  const recentDensity = mean(recent, (item) => item.metrics.density);
  if (
    recentDensity !== null
    && current.dialogueTurns >= 6
    && current.attributionCount >= 5
    && current.density >= 0.60
    && current.density >= recentDensity + 0.25
  ) {
    advise('chapter-spike', `本章密度 ${current.density.toFixed(2)}，较近期均值 ${recentDensity.toFixed(2)} 突升`);
  }

  return { findings, advisories, baselineDensity, recentDensity };
}

function main() {
  let options;
  try {
    options = parseArgs(process.argv.slice(2));
  } catch (error) {
    console.error(`dialogue_drift_gate: ${error.message}`);
    console.error('Usage: node dialogue_drift_gate.js --current <file> [--history-dir <dir>] [--json]');
    process.exit(3);
  }

  const currentPath = path.resolve(options.current);
  const historyDir = path.resolve(options.historyDir || path.dirname(currentPath));
  try {
    const current = analyze(fs.readFileSync(currentPath, 'utf8'));
    const history = loadHistory(currentPath, historyDir);
    const baseline = history.slice(0, options.baselineCount);
    const recent = history.slice(-options.recentWindow);
    const evaluation = evaluate(current, baseline, recent);
    const rejected = evaluation.findings.length > 0;
    const result = {
      status: rejected ? 'rejected' : 'passed',
      file: currentPath,
      metrics: {
        dialogue_turns: current.dialogueTurns,
        attribution_count: current.attributionCount,
        attribution_density: Number(current.density.toFixed(3)),
        max_consecutive_tagged_turns: current.maxConsecutive,
        top_verb: current.topVerb,
        top_family: current.topFamily,
        baseline_density: evaluation.baselineDensity === null ? null : Number(evaluation.baselineDensity.toFixed(3)),
        recent_density: evaluation.recentDensity === null ? null : Number(evaluation.recentDensity.toFixed(3)),
      },
      findings: evaluation.findings,
      advisories: evaluation.advisories,
      examples: current.occurrences.slice(0, 12),
      next_action: rejected
        ? 'return_to_narrative_writer_for_contextual_revision'
        : evaluation.advisories.length
          ? 'continue_with_semantic_dialogue_review'
          : 'continue_workflow',
    };

    if (options.json) {
      process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    } else if (!rejected) {
      console.log(`PASS: dialogue attribution is stable in ${currentPath}`);
      evaluation.advisories.forEach((finding) => console.log(`  ADVISORY [${finding.code}] ${finding.message}`));
    } else {
      console.error(`REJECTED: dialogue attribution drift in ${currentPath}`);
      evaluation.findings.forEach((finding) => console.error(`  [${finding.code}] ${finding.message}`));
      evaluation.advisories.forEach((finding) => console.error(`  ADVISORY [${finding.code}] ${finding.message}`));
      current.occurrences.slice(0, 12).forEach((item) => console.error(`  ${item.line}:${item.column} [${item.text}] ${item.context}`));
      console.error('Return this chapter to the narrative writer, revise in context, then rerun the gate.');
    }
    process.exit(rejected ? 2 : 0);
  } catch (error) {
    console.error(`dialogue_drift_gate: ${error.message}`);
    process.exit(3);
  }
}

main();
