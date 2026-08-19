#!/bin/bash
# Stage 2 机械硬检查：对 seq_start~seq_end 的章节摘要跑 4 条硬检查 + 完整性检查
# 用法: bash _validate_batch.sh seq_start seq_end
cd "$(dirname "$0")" || exit 1
start=${1:?用法: _validate_batch.sh seq_start seq_end}
end=${2:?}
JD_ENUM='^(紧张|轻松|悲伤|热血|爽|甜|温馨|恐怖|压抑|其他)$'
BQ_ENUM='^(爱情|亲情|友情|权力|金钱|成长|复仇|悬念|搞笑|热血|日常|其他)$'
ok=0; bad=0
for n in $(seq "$start" "$end"); do
  f="章节/第${n}章_摘要.md"
  if [ ! -s "$f" ]; then echo "FAIL|$n|文件缺失或为空"; bad=$((bad+1)); continue; fi
  errs=""
  p=$(grep -cE '^P[0-9]+ ' "$f")
  jd=$(grep -c '基调：' "$f")
  bd=$(grep -cE '^P[0-9]+ [^|]+\|[^|]*[^|[:space:]][^|]*\|[^|]*涉及' "$f")
  gy=$(grep -c '^\*\*概要\*\*' "$f")
  [ "$p" -lt 10 ] && errs="$errs;P数${p}<10"
  [ "$jd" -ne "$p" ] && errs="$errs;基调行${jd}!=P行${p}"
  [ "$bd" -ne "$p" ] && errs="$errs;白描行${bd}!=P行${p}"
  [ "$gy" -ne 1 ] && errs="$errs;概要行${gy}!=1"
  badjd=$(grep -hoE '基调：[^ |]+' "$f" | sed 's/^基调：//' | sort -u | grep -vcE "$JD_ENUM")
  [ "$badjd" -gt 0 ] && errs="$errs;基调枚举越界${badjd}种"
  badbq=$(grep -hoE '主题标签[：]?[^ |]+' "$f" | sed 's/^主题标签[：]\?//' | sort -u | grep -vcE "$BQ_ENUM")
  [ "$badbq" -gt 0 ] && errs="$errs;主题标签枚举越界${badbq}种"
  if [ -z "$errs" ]; then echo "OK|$n|P=${p}"; ok=$((ok+1)); else echo "FAIL|$n|${errs#;}"; bad=$((bad+1)); fi
done
echo "RESULT|${start}-${end}|ok=${ok}|fail=${bad}"
