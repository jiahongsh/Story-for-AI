#!/usr/bin/env node
// Stage 2 机械硬检查（Node 版，等价于 _validate_batch.sh，用于无 WSL 环境）
// 用法: node _validate_batch.mjs seq_start seq_end
// 2026-08-19 改版：基调/主题标签采用开放词库原则（用户确认），枚举越界降级为 WARN 提示不阻断；
// 结构硬检查（P行数>=10、基调行==P行、白描行==P行、概要==1）保留为 FAIL。
// 参考枚举（仅提示用，不代表必须）：基调 紧张/轻松/悲伤/热血/爽/甜/温馨/恐怖/压抑/其他；
// 主题标签 爱情/亲情/友情/权力/金钱/成长/复仇/悬念/搞笑/热血/日常/其他。
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const dir = path.dirname(fileURLToPath(import.meta.url));
const start = Number(process.argv[2]);
const end = Number(process.argv[3]);
if (!start || !end) { console.error('用法: node _validate_batch.mjs seq_start seq_end'); process.exit(1); }

const JD_ENUM = /^(紧张|轻松|悲伤|热血|爽|甜|温馨|恐怖|压抑|其他)$/;
const BQ_ENUM = /^(爱情|亲情|友情|权力|金钱|成长|复仇|悬念|搞笑|热血|日常|其他)$/;

let ok = 0, bad = 0;
for (let n = start; n <= end; n++) {
  const f = path.join(dir, '章节', `第${n}章_摘要.md`);
  if (!fs.existsSync(f)) { console.log(`FAIL|${n}|文件缺失`); bad++; continue; }
  const txt = fs.readFileSync(f, 'utf8');
  if (!txt.trim()) { console.log(`FAIL|${n}|文件为空`); bad++; continue; }
  const lines = txt.split('\n');
  const errs = [];
  const warns = [];
  const p = lines.filter(l => /^P\d+ /.test(l)).length;
  const jd = lines.filter(l => l.includes('基调：')).length;
  const bd = lines.filter(l => /^P\d+ [^|]+\|[^|]*\S[^|]*\|[^|]*涉及/.test(l)).length;
  const gy = lines.filter(l => l.startsWith('**概要**')).length;
  if (p < 10) errs.push(`P数${p}<10`);
  if (jd !== p) errs.push(`基调行${jd}!=P行${p}`);
  if (bd !== p) errs.push(`白描行${bd}!=P行${p}`);
  if (gy !== 1) errs.push(`概要行${gy}!=1`);
  const jdSet = new Set();
  const bqSet = new Set();
  for (const l of lines) {
    const m = l.match(/基调：([^ |]+)/);
    if (m) jdSet.add(m[1]);
    const m2 = l.match(/主题标签[：]?([^ |]+)/);
    if (m2) bqSet.add(m2[1]);
  }
  const badjd = [...jdSet].filter(v => !JD_ENUM.test(v)).length;
  const badbq = [...bqSet].filter(v => !BQ_ENUM.test(v)).length;
  // 开放词库：枚举越界仅提示，不阻断（用户 2026-08-19 确认：主题标签应多样，不强制统一）
  if (badjd > 0) warns.push(`基调非参考枚举${badjd}种:[${[...jdSet].filter(v=>!JD_ENUM.test(v)).join(',')}]`);
  if (badbq > 0) warns.push(`主题标签非参考枚举${badbq}种:[${[...bqSet].filter(v=>!BQ_ENUM.test(v)).join(',')}]`);
  if (errs.length === 0) {
    if (warns.length > 0) console.log(`WARN|${n}|P=${p}|${warns.join(';')}`);
    else console.log(`OK|${n}|P=${p}`);
    ok++;
  }
  else { console.log(`FAIL|${n}|${errs.join(';')}${warns.length?('|WARN:'+warns.join(';')):''}`); bad++; }
}
console.log(`RESULT|${start}-${end}|ok=${ok}|fail=${bad}`);
