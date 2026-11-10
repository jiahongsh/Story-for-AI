#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');

// 这些是明确的非叙事结构，不是正文语言例外。外层流程应尽量不把
// 技术报告/配置交给本 Gate；确实嵌在 Markdown 文件时只机械保护结构本身。
const PROTECTED_PATTERNS = [
  /```[\s\S]*?```/g,
  /`[^`\n]+`/g,
  /https?:\/\/[^\s<>()]+/gi,
  /\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b/g,
  /(?:[A-Za-z]:[\\/]|\.{1,2}[\\/]|\/)(?:[^\s/\\<>"'“”‘’「」『』【】()\uff08\uff09,，。；;\uff1a:!！?\uff1f、]+[\\/])*[^\s/\\<>"'“”‘’「」『』【】()\uff08\uff09,，。；;\uff1a:!！?\uff1f、]+/g,
  /(?:^|[\s（(《“"'])[^\s]+\.(?:md|txt|json|ya?ml|toml|js|mjs|cjs|ts|tsx|jsx|py|sh|html|css)(?=$|[\s）)》”"'，。！？；：,.!?;:])/gim,
];

function usage() {
  console.error('Usage: node language_gate.js [--json] <chapter-file>');
}

function loadWhitelist(inputPath) {
  let directory = path.dirname(inputPath);
  while (true) {
    const candidate = path.join(directory, '.deslop-whitelist');
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

function compact(value, limit = 120) {
  const text = String(value).replace(/\s+/g, ' ').trim();
  return text.length > limit ? `${text.slice(0, limit - 1)}…` : text;
}

function locate(text, offset) {
  const before = text.slice(0, offset);
  const line = before.split('\n').length;
  const lineStart = before.lastIndexOf('\n') + 1;
  const lineEndRaw = text.indexOf('\n', offset);
  const lineEnd = lineEndRaw === -1 ? text.length : lineEndRaw;
  return { line, column: offset - lineStart + 1, context: compact(text.slice(lineStart, lineEnd)) };
}

function findForbiddenMarkup(text, mask) {
  const findings = [];
  const pattern = /<!--[\s\S]*?-->|<\/?[A-Za-z][^>]*>|<![A-Za-z][^>]*>|&(?:[A-Za-z][A-Za-z0-9]+|#\d+|#x[0-9A-Fa-f]+);/g;
  for (const match of text.matchAll(pattern)) {
    let protectedStructure = true;
    for (let index = match.index; index < match.index + match[0].length; index += 1) {
      if (!mask[index]) {
        protectedStructure = false;
        break;
      }
    }
    if (protectedStructure) continue;
    mask.fill(1, match.index, match.index + match[0].length);
    findings.push({
      severity: 'blocking',
      type: 'forbidden-markup',
      text: compact(match[0]),
      ...locate(text, match.index),
      action: 'return_to_narrative_writer',
    });
  }
  return findings;
}

function isForeignLetter(char) {
  for (const unit of char.normalize('NFKC')) {
    if (/\p{L}/u.test(unit) && !/\p{Script=Han}/u.test(unit)) return true;
  }
  return false;
}

function isBridge(char) {
  return /[\p{M}\p{N}_'’.+/#-]/u.test(char);
}

function isWhitelistTokenAt(text, index) {
  if (index < 0 || index >= text.length) return false;
  const char = String.fromCodePoint(text.codePointAt(index));
  return isForeignLetter(char) || /[0-9_.+/#-]/.test(char);
}

function markWhitelistEntries(text, mask, entries) {
  for (const entry of entries) {
    let offset = 0;
    while (offset <= text.length - entry.length) {
      const start = text.indexOf(entry, offset);
      if (start < 0) break;
      const end = start + entry.length;
      const beforeForeign = isWhitelistTokenAt(text, start - 1);
      const afterForeign = isWhitelistTokenAt(text, end);
      const whitespace = (text.slice(end).match(/^\s+/) || [''])[0];
      const followedByForeignWord = whitespace.length > 0
        && isForeignLetter(String.fromCodePoint(text.codePointAt(end + whitespace.length) || 0));
      if (!beforeForeign && !afterForeign && !followedByForeignWord) mask.fill(1, start, end);
      offset = start + Math.max(entry.length, 1);
    }
  }
}

function markProtectedStructures(text, mask) {
  for (const pattern of PROTECTED_PATTERNS) {
    pattern.lastIndex = 0;
    for (const match of text.matchAll(pattern)) {
      mask.fill(1, match.index, match.index + match[0].length);
    }
  }
}

function findForeignLetters(text, mask) {
  const findings = [];
  let index = 0;
  while (index < text.length) {
    const char = String.fromCodePoint(text.codePointAt(index));
    if (mask[index] || !isForeignLetter(char)) {
      index += char.length;
      continue;
    }

    const start = index;
    let end = index + char.length;
    while (end < text.length) {
      if (mask[end]) break;
      const next = String.fromCodePoint(text.codePointAt(end));
      if (isForeignLetter(next) || isBridge(next)) {
        end += next.length;
        continue;
      }
      if (/[ \t]/.test(next)) {
        let cursor = end + next.length;
        while (cursor < text.length) {
          const whitespace = String.fromCodePoint(text.codePointAt(cursor));
          if (!/[ \t]/.test(whitespace)) break;
          cursor += whitespace.length;
        }
        if (cursor < text.length && !mask[cursor]) {
          const following = String.fromCodePoint(text.codePointAt(cursor));
          if (isForeignLetter(following)) {
            end = cursor;
            continue;
          }
        }
      }
      break;
    }

    findings.push({
      severity: 'blocking',
      type: 'mixed-language',
      text: text.slice(start, end),
      ...locate(text, start),
      action: 'return_to_narrative_writer',
    });
    index = end;
  }
  return findings;
}

function scan(text, whitelistEntries = []) {
  const mask = new Uint8Array(text.length);
  markProtectedStructures(text, mask);
  const markupFindings = findForbiddenMarkup(text, mask);
  markWhitelistEntries(text, mask, whitelistEntries);
  return [...markupFindings, ...findForeignLetters(text, mask)]
    .sort((a, b) => a.line - b.line || a.column - b.column);
}

function main(argv) {
  let json = false;
  let input = null;
  for (const arg of argv) {
    if (arg === '--json') json = true;
    else if (!input) input = arg;
    else {
      usage();
      return 3;
    }
  }
  if (!input) {
    usage();
    return 3;
  }

  const inputPath = path.resolve(input);
  let text;
  try {
    text = fs.readFileSync(inputPath, 'utf8');
  } catch (error) {
    console.error(`language_gate: cannot read ${inputPath}: ${error.message}`);
    return 3;
  }

  const whitelist = loadWhitelist(inputPath);
  const findings = scan(text, whitelist.entries);
  const report = {
    status: findings.length ? 'rejected' : 'passed',
    file: inputPath,
    findings,
    whitelist_file: whitelist.path,
    next_action: findings.length ? 'revise_reported_sentences_and_rerun_gate' : 'continue_workflow',
  };

  if (json) console.log(JSON.stringify(report, null, 2));
  else if (findings.length === 0) console.log(`PASS: no foreign letters or forbidden markup in ${inputPath}`);
  else {
    console.error(`REJECTED: ${findings.length} language/markup finding(s) in ${inputPath}`);
    for (const finding of findings) {
      console.error(`  ${finding.line}:${finding.column} [${finding.type}] ${finding.text}`);
      console.error(`    ${finding.context}`);
    }
  }
  return findings.length ? 2 : 0;
}

process.exitCode = main(process.argv.slice(2));
