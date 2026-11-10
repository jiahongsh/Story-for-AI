#!/bin/bash
# guard-outline-before-prose.sh — PreToolUse(Bash|Write|Edit|MultiEdit) 流程守卫
# 写「正文」前必须先有对应大纲/细纲，否则阻止（exit 2，BLOCKING）。
#
# 细纲门只拦「首次创建正文文件且缺细纲」；追踪门另按部署代际判定：
#   - 长篇 正文/第N章_*.md ：要求同书 大纲/细纲_第N章.md 存在
#   - 短篇 正文.md         ：要求同目录 小节大纲.md 存在
#   - agents_version >= 28 的普通长篇缺 _tracking-state.json 时，首建与修改都拦截
#   - 拆文库/{书名} 在场时保留受控 story-import 窗口，与共享严格核一致
#   - 旧版/无 sentinel 缺 state 仍兼容放行追踪缺失本身，但上一章中文语言/毒句欠账仍走共享核
# 非正文目标、解析不到路径一律静默放行。
# 设计原则：宁可漏拦不可误伤——任何不确定都 exit 0。
set -euo pipefail

source "$(dirname "$0")/lib/common.sh"
source "$(dirname "$0")/lib/sentinel.sh"

# 全程走字节稳定区域：本 hook 在中文路径上做 bash 通配（中间目录是中文书名时
# 细纲_第*章*.md 在 GBK 区域会 NOMATCH）、sed 提章号、case 匹配。Windows 中文系统若导出
# GBK/GB2312 区域设置，这些都会按多字节错误解码 UTF-8 而失效。强制 C 区域走字节匹配（UTF-8
# 字面量 vs UTF-8 字节相等）才稳定（issue #164）。路径抽取走 node 共享核，node 自身按 UTF-8
# 处理、与 bash 区域无关；拦截判定全在下方 bash，不受影响。
export LC_ALL=C

HOOK_INPUT="${CLAUDE_TOOL_INPUT:-}"
if [ -z "$HOOK_INPUT" ] && [ ! -t 0 ]; then
  HOOK_INPUT="$(cat)"
fi
# 故意不 export：Write/Edit/MultiEdit 负载里带整章正文（MultiEdit 还带 old_string+new_string），
# export 会把它塞进本脚本每个子进程的 envp，负载一大 execve 就 E2BIG（Linux 单个环境变量上限
# 128 KiB，macOS 整体 1 MiB），dirname/sed/node 全报「Argument list too long」——本守卫会在
# 走到 exit 2 之前死掉，退成「非阻塞错误」放过这次写入，与 BLOCKING 契约相反。改为只在需要负载
# 的 node 调用处用管道喂 stdin（story_hook_cli.js extract-target 在 HOOK_INPUT 缺省时读 stdin）；
# 下方 extract_target_bash 用的是 printf 内建，不需要 export。

# 提取直接写工具的目标文件路径：优先 node 共享核（与其它端同一份实现）；node 缺席、或 node 在但抽取失败时
# 都回落纯 bash 抽取。这是阻断守卫，不能因 node 问题而 fail-open——官方现在推荐原生二进制装
# Claude Code，只有 npm 装法才带 Node，native 运行时可能无 node；旧 node 不识 node: 前缀、或
# 部署的核损坏时 node 探测通过但抽取会抛错。只要能解析出目标路径就照常判定拦截，两条路径都抽不到
# 才放行（宁可漏拦不可误伤）。
CLI="$(dirname "$0")/story_hook_cli.js"

# 纯 bash JSON 抽取兜底：按 dig 优先级取第一处 file_path/path/filePath 字符串值。Claude(node
# 应用)的 hook 负载走 JSON.stringify——非 ASCII 路径是原始 UTF-8（不转 \uXXXX），Windows 盘符
# 路径是 \\ 转义；两者都可在 bash 里还原（下方盘符分支再把 \ 归一成 /）。node 缺席、或 node 在
# 但抽取失败时启用。
extract_target_bash() {
  local key val
  for key in file_path path filePath; do
    val="$(printf '%s' "$HOOK_INPUT" \
      | grep -oE "\"$key\"[[:space:]]*:[[:space:]]*\"([^\"\\\\]|\\\\.)*\"" \
      | head -n1 \
      | sed -E "s/^\"$key\"[[:space:]]*:[[:space:]]*\"//; s/\"\$//")"
    if [ -n "$val" ]; then
      val="${val//\\\"/\"}"   # \" -> "
      val="${val//\\\\/\\}"   # \\ -> \
      printf '%s' "$val"
      return 0
    fi
  done
  return 1
}

TARGET=""
if node -e "" >/dev/null 2>&1 && [ -f "$CLI" ]; then
  TARGET="$(printf '%s' "$HOOK_INPUT" | node "$CLI" extract-target 2>/dev/null || true)"
fi
# node 在场却抽空（旧 node 不识 node: 前缀 / 核损坏时探测通过但抽取抛错）也回落纯 bash。
# Bash 负载没有 file_path；直接目标抽不到时，再让共享核只识别重定向/tee/touch/cp/mv 的写入目标，
# 避免把 grep/cat 等只读命令里提及的正文路径误判为写入。该面依赖 node；node 缺席时 Bash 命令
# 按“宁可漏拦不可误伤”放行，Write/Edit/MultiEdit 仍走上面的纯 bash 兜底。
[ -z "$TARGET" ] && TARGET="$(extract_target_bash 2>/dev/null || true)"

ROOT=$(project_root)
if [ -z "$TARGET" ]; then
  if node -e "" >/dev/null 2>&1 && [ -f "$CLI" ]; then
    set +e
    COMMAND_BLOCK="$(printf '%s' "$HOOK_INPUT" | node "$CLI" prose-command-guard "$ROOT" 2>&1)"
    COMMAND_STATUS=$?
    set -e
    if [ "$COMMAND_STATUS" -ne 0 ]; then
      printf '%s\n' "⚠ Bash 正文写入守卫解析失败，本次按 fail-open 放行；请改用 Write/Edit 或修复 hook：${COMMAND_BLOCK:-未知错误}" >&2
      exit 0
    fi
    if [ -n "$COMMAND_BLOCK" ]; then
      printf '%s\n' "$COMMAND_BLOCK" >&2
      exit 2
    fi
  elif printf '%s' "$HOOK_INPUT" | grep -q '正文'; then
    printf '%s\n' "⚠ 当前环境缺少可用 Node/story_hook_cli.js，无法判定 Bash 是否写正文；本次按 fail-open 放行，请改用 Write/Edit 以启用大纲守卫。" >&2
  fi
  exit 0
fi

# 绝对路径直接采用，相对路径才拼项目根。
# Windows + Git Bash 下 Claude Code 可能传入盘符绝对路径（F:/work/... 或 F:\work\...）；
# 只认 /* 会把它们当相对路径拼成 $ROOT/F:/work/...，找错 大纲/ 目录、误报细纲缺失（issue #184）。
# [A-Za-z]:[/\\]* 命中盘符绝对路径，并把反斜杠统一成正斜杠（对齐 plugin.ts 的 isAbsolute + 反斜杠归一）。
case "$TARGET" in
  /*) ABS="$TARGET" ;;
  [A-Za-z]:[/\\]*) ABS="${TARGET//\\//}" ;;
  *)  ABS="$ROOT/$TARGET" ;;
esac

# 旧正文/既有大纲/设定的修改必须先有 revision-governor 影响计划。该门放在正文专用
# 细纲门之前，因此同一脚本也能覆盖总纲、卷纲、细纲和设定写入。
if node -e "" >/dev/null 2>&1 && [ -f "$CLI" ]; then
  REVISION_BLOCK="$(node "$CLI" revision-block-reason "$ROOT" "$ABS" 2>/dev/null || true)"
  if [ -n "$REVISION_BLOCK" ]; then
    printf '%s\n' "$REVISION_BLOCK" >&2
    exit 2
  fi
fi

# 核判据：OpenCode / ZCode / Codex 三端写正文前都调 core.proseBlockReason，唯独本端
# 早先只有下面的纯 bash 细纲检查，于是「首建第 N+1 章前必须先提交第 N 章追踪事务」这条
# 顺序校验在 Claude Code 上从不触发——跨章连续性守卫在这一端是开环的：模型不主动跑
# tracking_commit.py 就没人拦位置/持有物漂移。
#
# 追踪门是双轨的：agents_version >= 28 的新部署对普通缺 state 项目 fail-closed；
# 旧版/无 sentinel 项目仍保留迁移兼容，不因缺 state 单独被卡；只要 Node/共享核可用就调用
# proseBlockReason，校验 schema/revision/提交顺序并补跑上一章中文语言/毒句欠账。新部署的缺 state 判定先用
# 纯 bash 执行，确保 Claude Code 原生安装不带 Node 时也不会退化放行；核定义的
# 拆文库/{书名} story-import 窗口仍然保留。
GUARD_BOOK=""
GUARD_IS_LONG=0
case "$(basename "$(dirname "$ABS")")" in
  正文) GUARD_BOOK="$(dirname "$(dirname "$ABS")")"; GUARD_IS_LONG=1 ;;
  *)    [ "$(basename "$ABS")" = "正文.md" ] && GUARD_BOOK="$(dirname "$ABS")" ;;
esac
TRACKING_STATE="${GUARD_BOOK:+$GUARD_BOOK/追踪/_tracking-state.json}"
TRACKING_REQUIRED_AGENTS_VERSION=28
AGENTS_VERSION="$(read_sentinel_field agents_version "$ROOT/.story-deployed")"
if [ "$GUARD_IS_LONG" -eq 1 ] && [ ! -f "$TRACKING_STATE" ] \
   && [ ! -d "$ROOT/拆文库/$(basename "$GUARD_BOOK")" ] \
   && [[ "$AGENTS_VERSION" =~ ^[0-9]+$ ]] \
   && [ "$AGENTS_VERSION" -ge "$TRACKING_REQUIRED_AGENTS_VERSION" ] 2>/dev/null; then
  DISPLAY_BOOK="${GUARD_BOOK#$ROOT/}"
  printf '%s\n' "⛔ 写正文被拦截：${DISPLAY_BOOK} 的追踪/_tracking-state.json 缺失；已有正文项目走 /story-import 的「旧追踪项目迁移」重建追踪（不必重跑全书拆解），新书先用 tracking_commit.py init 初始化。" >&2
  exit 2
fi
if [ -n "$GUARD_BOOK" ] \
   && node -e "" >/dev/null 2>&1 && [ -f "$CLI" ]; then
  BLOCK_REASON="$(node "$CLI" prose-block-reason "$ROOT" "$ABS" 2>/dev/null || true)"
  if [ -n "$BLOCK_REASON" ]; then
    printf '%s\n' "$BLOCK_REASON" >&2
    exit 2
  fi
fi

BASE="$(basename "$ABS")"
PARENT="$(basename "$(dirname "$ABS")")"

case "$BASE" in
  正文.md)
    # 短篇单文件正文：已存在则放行（续写/改稿）
    [ -f "$ABS" ] && exit 0
    BOOK_DIR="$(dirname "$ABS")"
    # story-import 迁移：已有 拆文库/{书名}/ 分析源时，正文先于小节大纲迁移是正常流程（小节大纲由拆文反推），放行
    [ -d "$ROOT/拆文库/$(basename "$BOOK_DIR")" ] && exit 0
    # 仅在确为短篇工程时拦截（有 设定.md 信号——story-short-write/import 都先产 设定.md），
    # 避免误伤 docs/正文.md 等非作品文件
    [ -f "$BOOK_DIR/设定.md" ] || exit 0
    if [ ! -f "$BOOK_DIR/小节大纲.md" ]; then
      printf '%s\n' "⛔ 写正文被拦截：${TARGET} 缺少同目录 小节大纲.md。" >&2
      printf '%s\n' "   先按 story-short-write 完成「小节大纲.md」，再写正文（不允许跳过大纲直接写正文）。" >&2
      printf '%s\n' "   如确需先起草，请先补建 小节大纲.md。" >&2
      exit 2
    fi
    ;;
  *)
    # 长篇分章正文：父目录须为「正文」，文件名形如 第N章...
    [ "$PARENT" = "正文" ] || exit 0
    case "$BASE" in
      第*章*.md) ;;
      *) exit 0 ;;
    esac
    # 已存在则放行（续写/改稿）
    [ -f "$ABS" ] && exit 0
    # 章号（去前导零）
    NUM="$(printf '%s' "$BASE" | sed -n 's/^第0*\([0-9][0-9]*\)章.*/\1/p')"
    [ -z "$NUM" ] && exit 0
    BOOK_DIR="$(dirname "$(dirname "$ABS")")"
    # story-import 迁移：已有 拆文库/{书名}/ 分析源时放行（细纲由章节摘要反推、晚于正文迁移）。
    # 一旦 追踪/_tracking-state.json 存在即进入当前追踪协议，不再因为保留了 拆文库/ 分析资产
    # 而永久绕过守卫（与 story_hook_core.js 的同一判定保持一致）。
    if [ -d "$ROOT/拆文库/$(basename "$BOOK_DIR")" ] && [ ! -f "$BOOK_DIR/追踪/_tracking-state.json" ]; then
      exit 0
    fi
    OUTLINE_DIR="$BOOK_DIR/大纲"
    FOUND=""
    if [ -d "$OUTLINE_DIR" ]; then
      # 容忍补零差异与标题后缀：按整数章号匹配 大纲/细纲_第*章*.md
      for f in "$OUTLINE_DIR"/细纲_第*章*.md; do
        [ -e "$f" ] || continue
        fnum="$(basename "$f" | sed -n 's/^细纲_第0*\([0-9][0-9]*\)章.*/\1/p')"
        if [ "$fnum" = "$NUM" ]; then FOUND="$f"; break; fi
      done
    fi
    if [ -z "$FOUND" ]; then
      printf '%s\n' "⛔ 写正文被拦截：第 ${NUM} 章缺少细纲（${OUTLINE_DIR#$ROOT/}/细纲_第${NUM}章.md）。" >&2
      printf '%s\n' "   按 story-long-write 单章流程先补建细纲，再写正文（不允许跳过细纲直接写作）。" >&2
      printf '%s\n' "   如确需先起草，请先补建对应细纲文件。" >&2
      exit 2
    fi
    # 留存字段告警（非阻塞）：细纲缺「收一个/变一个/开一个」三留存字段时提醒补齐，但**不拦写**——
    # 硬拦保留在 story-long-write 细纲批末门（scripts/check-outline-retention.js）。此处只是写正文前的
    # 二道提醒网，避免误伤未迁移到新模板的旧格式细纲，也不改核心阻断契约（不进 proseBlockReason，
    # 不动 parity）。走字节匹配（LC_ALL=C 已设），用参数展开抽值、避开多字节正则。任何异常均放行。
    RET_MISSING=""
    for _label in "本章兑现（收一个）" "状态变化（变一个）" "章尾余势（开一个）"; do
      _line="$(grep -m1 -F "$_label" "$FOUND" 2>/dev/null || true)"
      if [ -z "$_line" ]; then RET_MISSING="$RET_MISSING ${_label}[缺]"; continue; fi
      _rest="${_line#*"$_label"}"; _rest="${_rest#：}"; _rest="${_rest#:}"
      _rest="${_rest#"${_rest%%[![:space:]]*}"}"
      case "$_rest" in
        "") RET_MISSING="$RET_MISSING ${_label}[空]" ;;
        \{*) RET_MISSING="$RET_MISSING ${_label}[占位]" ;;
      esac
    done
    if [ -n "$RET_MISSING" ]; then
      printf '%s\n' "⚠ 细纲留存字段未填（不拦写，建议补齐后再落正文）：第 ${NUM} 章 —$RET_MISSING" >&2
      printf '%s\n' "   跑 story-long-write 的 scripts/check-outline-retention.js 补齐「收一个/变一个/开一个」，再写正文。" >&2
    fi
    # 欠账门（无状态）：写第 N 章（首建）前，上一章有未清毒句式时先清再写。
    # 毒句式扫描走共享核 prose-toxic 子命令（与写后网同一份规则）；node/核缺失或扫描失败一律
    # 放行（宁可漏拦不可误伤）——写后网与 SKILL 同轮铁律仍兜底。判据现算自上一章文件，无状态。
    PREV=$((NUM - 1))
    if [ "$PREV" -ge 1 ] && node -e "" >/dev/null 2>&1 && [ -f "$CLI" ]; then
      PROSE_DIR="$(dirname "$ABS")"
      PREV_FILE=""
      # glob 已按字典序，但同章号的原稿备份（workflow-revision 的「备份原稿」产物）
      # 也会命中；显式跳过 _原稿_，与 JS 核 / codex py 取同一个「上一章」。
      for f in "$PROSE_DIR"/第*章*.md; do
        [ -e "$f" ] || continue
        case "$(basename "$f")" in *_原稿_*) continue ;; esac
        pnum="$(basename "$f" | sed -n 's/^第0*\([0-9][0-9]*\)章.*/\1/p')"
        if [ "$pnum" = "$PREV" ]; then PREV_FILE="$f"; break; fi
      done
      if [ -n "$PREV_FILE" ]; then
        TOXIC="$(node "$CLI" prose-toxic "$PREV_FILE" 2>/dev/null || true)"
        if [ -n "$TOXIC" ]; then
          printf '%s\n' "⛔ 写正文被拦截：上一章（$(basename "$PREV_FILE")）有未清毒句式欠账，先清零再写第 ${NUM} 章；毒句式欠账必须改写清零，正文不得添加 HTML 豁免标记。" >&2
          # 只列前 8 条。不能写 `printf … | head -n 8`：欠账多时 head 先退出，printf 吃 SIGPIPE，
          # pipefail 下整条管道返回 141，set -e 立刻终止脚本——下面的 exit 2 永远走不到，拦截
          # 退成「非阻塞错误」放过这次写入。改用 here-string 直喂 head（无管道即无 SIGPIPE），
          # 再兜一层 || true，保证无论如何都能走到 exit 2。
          head -n 8 <<< "$TOXIC" >&2 || true
          exit 2
        fi
      fi
    fi
    ;;
esac

exit 0
