#!/usr/bin/env bash
# 《他们不是人》封面生成脚本（番茄小说 600×800）
# 用法：
#   export GPT_IMAGE_API_KEY=你的key
#   export AUTHOR_NAME=你的笔名          # 必填
#   export GPT_IMAGE_BASE_URL=...        # 中转代理时设置
#   bash 生成封面.sh
set -euo pipefail
: "${GPT_IMAGE_API_KEY:?请设置 export GPT_IMAGE_API_KEY=你的key}"
AUTHOR_NAME="${AUTHOR_NAME:-小雨心啊}"
BASE_URL="${GPT_IMAGE_BASE_URL:-https://api.openai.com/v1}"
MODEL="${GPT_IMAGE_MODEL:-gpt-image-2}"
SIZE="${GPT_IMAGE_SIZE:-768x1024}"
BOOK_DIR="$(cd "$(dirname "$0")/.." && pwd)"

PROMPT=$(cat <<'EOF'
Chinese web novel cover design, Fanqie platform style, dark suspense urban horror aesthetic.
Title text '他们不是人' at top center in distorted bold cracked letters in blood red with subtle metallic sheen, characters slightly fractured as if splitting apart.
Author name 'AUTHOR_PLACEHOLDER' at bottom center in small pale grey text with slight blur effect, almost hidden in the shadows, a thin cracked line underneath.
A lone teenage boy stands in a rain-soaked city street at night, seen from behind, holding up a cracked hand mirror that reflects a crowd of faceless pale figures with hairline seams across their faces. Foreground: the boy and mirror glow with cold silver light. Midground: blurred silhouettes of ordinary pedestrians whose edges reveal thin split seams. Background: towering dark apartment blocks with dim yellow windows, heavy fog, one window glowing unnaturally green.
Dominant color palette of deep midnight blue, ash grey and desaturated city neon, with a single stroke of blood red echoing the title. Cold moonlight from above, eerie green ambient glow from the left, high contrast cinematic lighting on the mirror.
Professional book cover, high detail digital painting, portrait 3:4 ratio, keep title and author name inside the central safe area away from edges (inner ~85%), no watermark
EOF
)
PROMPT="${PROMPT//AUTHOR_PLACEHOLDER/$AUTHOR_NAME}"

mkdir -p "$BOOK_DIR/封面"
i=1
while [ -f "$BOOK_DIR/封面/封面_v${i}.png" ]; do i=$((i+1)); done
OUT="$BOOK_DIR/封面/封面_v${i}.png"
RESP=$(mktemp)
trap 'rm -f "$RESP"' EXIT

BODY=$(jq -n --arg m "$MODEL" --arg p "$PROMPT" --arg s "$SIZE" \
  '{model:$m, prompt:$p, size:$s}')

curl -fsS --max-time 180 --retry 2 --retry-delay 5 \
  "$BASE_URL/images/generations" \
  -H "Authorization: Bearer $GPT_IMAGE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$BODY" > "$RESP"

if jq -e '.error' "$RESP" >/dev/null 2>&1; then
  echo "API error:" >&2; jq '.error' "$RESP" >&2; exit 1
fi
jq -er '.data[0].b64_json // empty' "$RESP" | base64 --decode > "$OUT"
[ -s "$OUT" ] || { echo "empty or malformed output" >&2; head -c 300 "$RESP" >&2; exit 1; }

printf '%s\n' "$PROMPT" > "${OUT%.png}.prompt.txt"

# 导出番茄 600×800 上传版（居中裁剪+缩放，不变形）
UP="${OUT%.png}_上传.png"
if command -v magick >/dev/null 2>&1; then M=magick
elif command -v convert >/dev/null 2>&1; then M=convert; else M=""; fi
if [ -n "$M" ]; then
  "$M" "$OUT" -resize "600x800^" -gravity center -extent "600x800" "$UP"
else
  echo "无 ImageMagick，请手动把 $OUT 居中裁剪缩放到 600x800" >&2
fi

file "$OUT"; [ -f "$UP" ] && file "$UP"
ls -lt "$BOOK_DIR/封面/"
