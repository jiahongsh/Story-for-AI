#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');

const USAGE = `Usage: node check-outline-retention.js [--json] [--fail-on=blocking|all] <细纲文件...>

把"章章推进 / 收一个、变一个、开一个"的留存节奏从文档自觉变成大纲层确定性硬门。
逐个检查细纲文件是否填齐三个留存字段（只查"字段在不在、填没填"，不判断内容语义质量）：

  - 本章兑现（收一个）   本章偿还哪笔期待债 / 付了什么利息（进展·收益·关系反馈·情绪释放）
  - 状态变化（变一个）   目标/风险/信息/关系/资源/身份/情绪立场 至少一项 章前 → 章后
  - 章尾余势（开一个）   留下的下一步（问题/决定/行动/关系变化/阶段目标/情绪余势）

只处理"能确定性判定"的部分。跨章语义问题（假钩子=下一章是否撤回、刺激通胀=跨章强度曲线、
本章兑现是否真的兑现）不在这里硬做——那些留给 story-review 审查 agent，正则会误杀。

一个字段判为缺失（blocking）当且仅当：整章找不到该字段行，或该字段冒号后仍是 {…} 模板占位、
或冒号后为空。填了真实内容（哪怕简短）即视为通过——不评判好坏，只保证"没被跳过"。

退出码：0 = 全部通过；1 = 有 blocking（缺字段/占位/空）；2 = 用法或读取错误。
`;

const FIELDS = [
  { key: '本章兑现', label: '本章兑现（收一个）' },
  { key: '状态变化', label: '状态变化（变一个）' },
  { key: '章尾余势', label: '章尾余势（开一个）' },
];

// 章节分节：模板用 "### 第 N 章：" 作为单章起点；无此标记时整文件按一章处理。
const CHAPTER_HEADER = /^#{2,4}\s*第\s*[0-9一二三四五六七八九十百千两]+\s*章/;

function isPlaceholder(value) {
  const v = value.trim();
  if (v === '') return true;
  // 冒号后仍是整段 {…} 模板占位（允许前后有少量修饰），视为未填。
  if (/^\{[^}]*\}$/.test(v)) return true;
  if (/^[（(]\s*待补充\s*[)）]$/.test(v) || v === '待补充' || v === 'TODO' || v === 'TBD') return true;
  return false;
}

function fieldValue(sectionText, label) {
  // 容忍 label 中括号/冒号的全半角；核心以中文字段名锚定，冒号用 [：:]。
  const core = label.replace(/[（(].*$/, ''); // 本章兑现 / 状态变化 / 章尾余势
  const bracket = label.match(/[（(](.+?)[)）]/); // 收一个 / 变一个 / 开一个
  const tag = bracket ? bracket[1] : '';
  const re = new RegExp(
    `^\\s*[-*]?\\s*${core}\\s*[（(]\\s*${tag}\\s*[)）]\\s*[：:]\\s*(.*)$`,
    'm'
  );
  const m = sectionText.match(re);
  if (m) return { present: true, value: m[1] };
  // 退一步：只按核心字段名 + 冒号匹配（容忍作者漏写括注）。
  const re2 = new RegExp(`^\\s*[-*]?\\s*${core}\\s*[（(][^)）]*[)）]?\\s*[：:]\\s*(.*)$`, 'm');
  const m2 = sectionText.match(re2);
  if (m2) return { present: true, value: m2[1] };
  return { present: false, value: '' };
}

function splitChapters(text) {
  const lines = text.split('\n');
  const idx = [];
  lines.forEach((line, i) => {
    if (CHAPTER_HEADER.test(line)) idx.push(i);
  });
  if (idx.length <= 1) return [{ title: null, text }];
  const sections = [];
  for (let k = 0; k < idx.length; k++) {
    const start = idx[k];
    const end = k + 1 < idx.length ? idx[k + 1] : lines.length;
    sections.push({ title: lines[start].replace(/^#+\s*/, '').trim(), text: lines.slice(start, end).join('\n') });
  }
  return sections;
}

function checkFile(file) {
  let text;
  try {
    text = fs.readFileSync(file, 'utf8');
  } catch (err) {
    return { file, error: `无法读取: ${err.message}`, findings: [] };
  }
  const findings = [];
  for (const chap of splitChapters(text)) {
    for (const field of FIELDS) {
      const { present, value } = fieldValue(chap.text, field.label);
      if (!present) {
        findings.push({ chapter: chap.title, field: field.label, reason: '缺失字段' });
      } else if (isPlaceholder(value)) {
        findings.push({ chapter: chap.title, field: field.label, reason: '仍是占位符/空' });
      }
    }
  }
  return { file, error: null, findings };
}

function main(argv) {
  const args = argv.slice(2);
  let json = false;
  let failOn = 'blocking';
  const files = [];
  for (const a of args) {
    if (a === '--json') json = true;
    else if (a === '-h' || a === '--help') { process.stdout.write(USAGE); return 0; }
    else if (a.startsWith('--fail-on=')) failOn = a.slice('--fail-on='.length);
    else files.push(a);
  }
  if (files.length === 0) { process.stderr.write(USAGE); return 2; }

  const results = files.map(checkFile);
  const hadReadError = results.some((r) => r.error);
  const totalFindings = results.reduce((n, r) => n + r.findings.length, 0);

  if (json) {
    process.stdout.write(JSON.stringify({ results, totalFindings }, null, 2) + '\n');
  } else {
    for (const r of results) {
      const name = path.basename(r.file);
      if (r.error) { process.stderr.write(`[ERROR] ${name}: ${r.error}\n`); continue; }
      if (r.findings.length === 0) { process.stdout.write(`[PASS] ${name}: 三个留存字段齐备\n`); continue; }
      for (const f of r.findings) {
        const where = f.chapter ? `（${f.chapter}）` : '';
        process.stdout.write(`[缺] ${name}${where}: ${f.field} —— ${f.reason}\n`);
      }
    }
    if (totalFindings > 0) {
      process.stdout.write(`\n共 ${totalFindings} 处留存字段缺失/未填。补齐"收一个（本章兑现）/变一个（状态变化）/开一个（章尾余势）"后再落正文。\n`);
    }
  }

  if (hadReadError) return 2;
  if (failOn === 'all' || failOn === 'blocking') return totalFindings > 0 ? 1 : 0;
  return 0;
}

process.exit(main(process.argv));
