#!/bin/bash
# 机械硬检查：P行数==基调行数==白描行数, P>=10, 无花括号
# 用法: bash _quick_validate.sh <start> <end>
cd "$(dirname "$0")" || exit 1
start=${1:?需要起始章号}
end=${2:?需要结束章号}
ok=0
bad=0
for ((s=start; s<=end; s++)); do
  f="第${s}章_摘要.md"
  if [ ! -f "$f" ]; then
    echo "MISSING $s"
    bad=$((bad+1))
    continue
  fi
  p=$(grep -cE '^P[0-9]+ ' "$f")
  bt=$(grep -c '基调：' "$f")
  br=$(grep -cE '^P[0-9]+ [^|]+\|[^|]*[^|[:space:]][^|]*\|[^|]*涉及' "$f")
  brace=$(grep -cE '[\{\}]' "$f")
  if [ "$p" -ne "$bt" ] || [ "$p" -ne "$br" ] || [ "$p" -lt 10 ] || [ "$brace" -ne 0 ]; then
    echo "BAD $s P=$p 基调=$bt 白描=$br 花括号=$brace"
    bad=$((bad+1))
  else
    ok=$((ok+1))
  fi
done
echo "SUMMARY OK=$ok BAD=$bad (range ${start}-${end})"
[ "$bad" -eq 0 ]
