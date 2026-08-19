# -*- coding: utf-8 -*-
"""机械硬检查：P行数==基调行数==白描行数, P>=10, 无花括号, 枚举检查
用法: python _quick_validate.py <start> <end>
"""
import os, re, sys

BASE = os.path.dirname(os.path.abspath(__file__))
start = int(sys.argv[1])
end = int(sys.argv[2])

p_re = re.compile(r'^P[0-9]+ ')
diaodu_re = re.compile(r'基调：')
baimiao_re = re.compile(r'^P[0-9]+ [^|]+\|[^|]*[^|\s][^|]*\|[^|]*涉及')
brace_re = re.compile(r'[\{\}]')

ok = bad = 0
for s in range(start, end + 1):
    f = os.path.join(BASE, f'第{s}章_摘要.md')
    if not os.path.exists(f):
        print(f'MISSING {s}')
        bad += 1
        continue
    with open(f, encoding='utf-8') as fh:
        txt = fh.read()
    lines = txt.splitlines()
    p = sum(1 for ln in lines if p_re.match(ln))
    bt = sum(1 for ln in lines if diaodu_re.search(ln))
    br = sum(1 for ln in lines if baimiao_re.match(ln))
    brace = len(brace_re.findall(txt))
    if p != bt or p != br or p < 10 or brace != 0:
        print(f'BAD {s} P={p} 基调={bt} 白描={br} 花括号={brace}')
        bad += 1
    else:
        ok += 1
print(f'SUMMARY OK={ok} BAD={bad} (range {start}-{end})')
sys.exit(0 if bad == 0 else 1)
