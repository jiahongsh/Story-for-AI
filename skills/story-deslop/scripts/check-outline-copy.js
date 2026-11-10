#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');

const DEFAULT_THRESHOLD = 16;
const USAGE = `Usage: node check-outline-copy.js --outline <细纲文件> [--threshold=16] [--json] [--fail-on=blocking|never] <正文文件...>

检测正文与对应细纲之间未授权的连续照搬。默认把归一化后连续 16 个及以上汉字/数字重合判为 blocking。
细纲中的“复沓锚句”可以登记必须逐字回环的誓言、系统提示或案卷引文；只豁免登记短句本身，不能豁免相邻概括语。
脚本只给证据和行号，不自动改写正文。
`;

function normalizeWithMap(text) {
  const chars = [];
  const offsets = [];
  for (let offset = 0; offset < text.length;) {
    const char = String.fromCodePoint(text.codePointAt(offset));
    if (/^[\p{Script=Han}\p{N}]$/u.test(char)) {
      chars.push(char);
      offsets.push(offset);
    }
    offset += char.length;
  }
  return { chars, offsets };
}

function normalizePhrase(text) {
  return normalizeWithMap(text).chars.join('');
}

function cleanAnchor(raw) {
  let value = raw.trim()
    .replace(/^[-*+]\s*/, '')
    .replace(/^(?:锚句|第?\s*\d+\s*句)\s*[：:]\s*/, '')
    .replace(/^[`“”‘’「」『』\s]+|[`“”‘’「」『』\s]+$/g, '')
    .trim();
  if (!value || /^(?:无|没有|不适用|none|null|待补充|todo|tbd)$/i.test(value)) return '';
  if (/[{}]/.test(value) || /待补充|todo|tbd/i.test(value)) return '';
  return value;
}

function anchorPieces(raw) {
  const quoted = [];
  for (const match of raw.matchAll(/[“「『](.*?)[”」』]/g)) quoted.push(match[1]);
  const pieces = quoted.length > 0 ? quoted : raw.split(/[；;|]/);
  return pieces.map(cleanAnchor).filter(Boolean);
}

function extractAnchors(outlineText) {
  const lines = outlineText.replace(/\r\n?/g, '\n').split('\n');
  const anchors = [];
  let collecting = false;
  let headingMode = false;

  for (const line of lines) {
    const heading = line.match(/^\s*#{1,6}\s*复沓锚句\s*$/);
    const field = line.match(/^\s*(?:[-*+]\s*)?复沓锚句\s*[：:]\s*(.*)$/);
    if (heading) {
      collecting = true;
      headingMode = true;
      continue;
    }
    if (field) {
      collecting = true;
      headingMode = false;
      anchors.push(...anchorPieces(field[1]));
      continue;
    }
    if (!collecting) continue;
    if (/^\s*#{1,6}\s+/.test(line)) {
      collecting = false;
      headingMode = false;
      continue;
    }
    if (!headingMode && /^\s*[-*+]\s*[^：:\n]{1,30}[：:]/.test(line)) {
      collecting = false;
      continue;
    }
    if (/^\s*[-*+]\s+/.test(line)) anchors.push(...anchorPieces(line));
    else if (headingMode && line.trim()) anchors.push(...anchorPieces(line));
  }

  const unique = new Map();
  for (const raw of anchors) {
    const normalized = normalizePhrase(raw);
    if (normalized) unique.set(normalized, raw);
  }
  return [...unique.entries()].map(([normalized, raw]) => ({ raw, normalized }));
}

function lineNumberAt(text, offset) {
  let line = 1;
  for (let i = 0; i < offset; i++) if (text.charCodeAt(i) === 10) line += 1;
  return line;
}

function lineTextAt(text, offset) {
  const start = text.lastIndexOf('\n', Math.max(0, offset - 1)) + 1;
  const foundEnd = text.indexOf('\n', offset);
  const end = foundEnd === -1 ? text.length : foundEnd;
  return text.slice(start, end).trim().slice(0, 240);
}

function rawMatches(prose, outline, threshold) {
  const proseNorm = normalizeWithMap(prose);
  const outlineNorm = normalizeWithMap(outline);
  const outlineSeeds = new Map();
  for (let index = 0; index + threshold <= outlineNorm.chars.length; index++) {
    const seed = outlineNorm.chars.slice(index, index + threshold).join('');
    const positions = outlineSeeds.get(seed) || [];
    if (positions.length < 64) positions.push(index);
    outlineSeeds.set(seed, positions);
  }

  const unique = new Map();
  for (let proseIndex = 0; proseIndex + threshold <= proseNorm.chars.length; proseIndex++) {
    const seed = proseNorm.chars.slice(proseIndex, proseIndex + threshold).join('');
    const outlinePositions = outlineSeeds.get(seed);
    if (!outlinePositions) continue;
    for (const outlineIndex of outlinePositions) {
      let pStart = proseIndex;
      let oStart = outlineIndex;
      while (pStart > 0 && oStart > 0 && proseNorm.chars[pStart - 1] === outlineNorm.chars[oStart - 1]) {
        pStart -= 1;
        oStart -= 1;
      }
      let pEnd = proseIndex + threshold;
      let oEnd = outlineIndex + threshold;
      while (
        pEnd < proseNorm.chars.length &&
        oEnd < outlineNorm.chars.length &&
        proseNorm.chars[pEnd] === outlineNorm.chars[oEnd]
      ) {
        pEnd += 1;
        oEnd += 1;
      }
      const key = `${pStart}:${pEnd}:${oStart}:${oEnd}`;
      unique.set(key, { pStart, pEnd, oStart, oEnd, proseNorm, outlineNorm });
    }
  }
  return [...unique.values()];
}

function isContained(candidate, accepted) {
  return (
    candidate.pStart >= accepted.pStart && candidate.pEnd <= accepted.pEnd &&
    candidate.oStart >= accepted.oStart && candidate.oEnd <= accepted.oEnd
  );
}

function findMatches(prose, outline, threshold, anchors) {
  const sorted = rawMatches(prose, outline, threshold)
    .sort((left, right) => (right.pEnd - right.pStart) - (left.pEnd - left.pStart));
  const maximal = [];
  for (const candidate of sorted) {
    if (!maximal.some((accepted) => isContained(candidate, accepted))) maximal.push(candidate);
  }

  const findings = [];
  for (const match of maximal) {
    const normalized = match.proseNorm.chars.slice(match.pStart, match.pEnd).join('');
    if (anchors.some((anchor) => anchor.normalized === normalized)) continue;
    const proseOffset = match.proseNorm.offsets[match.pStart];
    const outlineOffset = match.outlineNorm.offsets[match.oStart];
    findings.push({
      severity: 'blocking',
      kind: 'outline-verbatim-overlap',
      normalized_length: match.pEnd - match.pStart,
      prose_line: lineNumberAt(prose, proseOffset),
      outline_line: lineNumberAt(outline, outlineOffset),
      match: normalized.slice(0, 160),
      prose_excerpt: lineTextAt(prose, proseOffset),
      outline_excerpt: lineTextAt(outline, outlineOffset),
    });
    if (findings.length >= 20) break;
  }
  return findings;
}

function parseArgs(argv) {
  const options = { outline: null, threshold: DEFAULT_THRESHOLD, json: false, failOn: 'blocking', files: [] };
  for (let index = 2; index < argv.length; index++) {
    const arg = argv[index];
    if (arg === '--outline') {
      options.outline = argv[++index];
    } else if (arg.startsWith('--outline=')) {
      options.outline = arg.slice('--outline='.length);
    } else if (arg.startsWith('--threshold=')) {
      options.threshold = Number(arg.slice('--threshold='.length));
    } else if (arg === '--json') {
      options.json = true;
    } else if (arg.startsWith('--fail-on=')) {
      options.failOn = arg.slice('--fail-on='.length);
    } else if (arg === '-h' || arg === '--help') {
      options.help = true;
    } else {
      options.files.push(arg);
    }
  }
  return options;
}

function main(argv) {
  const options = parseArgs(argv);
  if (options.help) {
    process.stdout.write(USAGE);
    return 0;
  }
  if (!options.outline || options.files.length === 0 || !Number.isInteger(options.threshold) || options.threshold < 8) {
    process.stderr.write(USAGE);
    return 2;
  }
  if (!['blocking', 'never'].includes(options.failOn)) {
    process.stderr.write(`未知 --fail-on 值: ${options.failOn}\n`);
    return 2;
  }

  let outlineText;
  try {
    outlineText = fs.readFileSync(options.outline, 'utf8');
  } catch (error) {
    process.stderr.write(`无法读取细纲: ${error.message}\n`);
    return 2;
  }
  const anchors = extractAnchors(outlineText);
  const results = [];
  let readError = false;
  for (const file of options.files) {
    try {
      const prose = fs.readFileSync(file, 'utf8');
      results.push({
        file,
        outline: options.outline,
        threshold: options.threshold,
        anchors: anchors.map((anchor) => anchor.raw),
        findings: findMatches(prose, outlineText, options.threshold, anchors),
      });
    } catch (error) {
      readError = true;
      results.push({ file, outline: options.outline, error: error.message, findings: [] });
    }
  }

  const totalFindings = results.reduce((total, result) => total + result.findings.length, 0);
  const payload = { status: totalFindings > 0 ? 'blocking' : 'pass', totalFindings, results };
  if (options.json) {
    process.stdout.write(JSON.stringify(payload, null, 2) + '\n');
  } else {
    for (const result of results) {
      const name = path.basename(result.file);
      if (result.error) {
        process.stderr.write(`[ERROR] ${name}: ${result.error}\n`);
      } else if (result.findings.length === 0) {
        process.stdout.write(`[PASS] ${name}: 未发现未登记的细纲连续照搬\n`);
      } else {
        for (const finding of result.findings) {
          process.stdout.write(
            `[BLOCK] ${name}:${finding.prose_line} 与细纲:${finding.outline_line} 连续重合 ${finding.normalized_length} 字：${finding.match}\n`
          );
        }
      }
    }
  }
  if (readError) return 2;
  return options.failOn === 'blocking' && totalFindings > 0 ? 1 : 0;
}

process.exit(main(process.argv));
