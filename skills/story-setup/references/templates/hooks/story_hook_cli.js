#!/usr/bin/env node
"use strict"

// story_hook_cli.js — Claude Code bash hook 的 node 桥
// Claude 侧 hook 是 bash（settings.json 挂 bash 脚本），归核逻辑走这里 require 的
// 共享核 story_hook_core.js——和 OpenCode/ZCode 用的是同一份，由 check-shared-files
// 保证字节相同。归核（单份实现在 core）的面：正文网/字数（prose-net）、路径抽取
// （extract-target）、Bash 正文写入前置门（prose-command-guard）、毒句式扫描
// （prose-toxic）、大纲/追踪阻断判定（prose-block-reason）、git commit 侦测
// （is-git-commit）、连续性（continuity）。
// 尚未归核、各端独立实现的面：
//   - Write/Edit/MultiEdit 的无 Node 兜底：Claude 仍由 guard-outline-before-prose.sh
//     保留纯 bash 细纲检查；Bash 命令必须先区分真正写入和只读提及，故经本 CLI 复用
//     共享核，node 缺失时该命令面 fail-open。codex prose_block_reason ↔ core
//     proseBlockReason 由 scripts/test-prose-net-parity.sh Part E 锁 parity。
//   - staged markdown warnings：Claude 走 validate-story-commit.sh bash grep；codex
//     staged_markdown_warnings ↔ core stagedMarkdownWarnings 同由 Part E 锁 parity。
//     匹配语义与文案以 JS core 为准。
// 各端只留读写各自 hook I/O 格式的薄壳。node 天生按 UTF-8 写 stdout，顺带免掉了
// 旧内嵌 python 那套 cp936/LC_ALL 编码体操。

const fs = require("node:fs")
const path = require("node:path")
const core = require("./story_hook_core.js")

function readStdin() {
  try {
    return fs.readFileSync(0, "utf8")
  } catch {
    return ""
  }
}

const NESTED_INPUT_KEYS = ["tool_input", "input", "parameters", "args"]

function digString(value, keys, allowEmpty = false) {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    for (const key of keys) {
      const found = value[key]
      if (typeof found === "string" && (allowEmpty || found)) return found
    }
    for (const key of NESTED_INPUT_KEYS) {
      const found = digString(value[key], keys, allowEmpty)
      if (found) return found
    }
  }
  return ""
}

const digTargetPath = (value) => digString(value, ["file_path", "path", "filePath"])
const digCommand = (value) => digString(value, ["command", "cmd", "script"], true)
const digWorkingDirectory = (value) =>
  digString(value, ["cwd", "working_directory", "workingDirectory"])

const TRACKING_REQUIRED_AGENTS_VERSION = 28
const MISSING_TRACKING_STATE = "追踪/_tracking-state.json 缺失"

function deployedAgentsVersion(root) {
  try {
    const text = fs.readFileSync(path.join(root, ".story-deployed"), "utf8")
    const line = text.split(/\r?\n/).find((item) => item.startsWith("agents_version:"))
    if (!line) return null
    let value = line.slice("agents_version:".length).trim()
    if (value.length >= 2) {
      const first = value[0]
      const last = value[value.length - 1]
      if ((first === '"' && last === '"') || (first === "'" && last === "'")) {
        value = value.slice(1, -1)
      }
    }
    if (!/^\d+$/.test(value)) return null
    const version = Number(value)
    return Number.isSafeInteger(version) ? version : null
  } catch {
    return null
  }
}

function longProseTarget(absolute) {
  const base = path.basename(absolute)
  if (path.basename(path.dirname(absolute)) !== "正文") return null
  const match = base.match(/^第0*(\d+)章.*\.md$/)
  if (!match) return null
  return {
    absolute,
    base,
    book: path.dirname(path.dirname(absolute)),
    chapter: Number(match[1]),
  }
}

// 严格核在追踪检查点后还有上一章中文语言漂移 / 毒句式欠账门。legacy 项目仅豁免“state
// 缺失”本身，不能连无状态欠账门一起吞掉；因此在严格核返回缺 state 后，用核导出的
// languageLeakRecords / toxicPhraseFindings 补跑同一判据。这只是 legacy 兼容支路；state 在场时仍原样走
// core.proseBlockReason，不在薄壳里重写追踪规则。
function legacyProseDebtReason(root, target) {
  if (fs.existsSync(target.absolute) || target.chapter <= 1) return null
  let prevFile = null
  try {
    const candidates = fs.readdirSync(path.dirname(target.absolute))
      .filter((file) => {
        const match = file.match(/^第0*(\d+)章.*\.md$/)
        return match && Number(match[1]) === target.chapter - 1 && !file.includes("_原稿_")
      })
      .sort()
    if (candidates.length) prevFile = path.join(path.dirname(target.absolute), candidates[0])
  } catch {}
  if (!prevFile) return null

  let prevText
  try {
    prevText = fs.readFileSync(prevFile, "utf8")
  } catch {
    return null
  }
  const languageHits = core.languageLeakRecords(prevText, core.readDeslopWhitelist(root, prevFile))
    .filter((record) => record.blocking)
  if (languageHits.length) {
    const shown = languageHits.slice(0, 6).map((record) => record.finding)
    const more = languageHits.length - shown.length
    let reason = `⛔ 写正文被拦截：上一章（${path.basename(prevFile)}）有 ${languageHits.length} 处未清中文语言漂移欠账，先改成中文再写第 ${target.chapter} 章；确需保留的外语逐项写入项目根 .deslop-whitelist 后重试。\n${shown.join("\n")}`
    if (more > 0) reason += `\n（另有 ${more} 处，请执行正文确定性扫描查看全部命中）`
    return reason
  }
  // 旧版正文中的 HTML 跳过标记不再生效；语言门和毒句式欠账都必须清零。
  const hits = core.toxicPhraseFindings(prevText).filter((line) => line.startsWith("第"))
  if (!hits.length) return null
  const shown = hits.slice(0, 6)
  const more = hits.length - shown.length
  let reason = `⛔ 写正文被拦截：上一章（${path.basename(prevFile)}）有 ${hits.length} 处未清毒句式欠账，先清零再写第 ${target.chapter} 章；毒句式欠账必须改写清零，正文不得添加 HTML 豁免标记。\n${shown.join("\n")}`
  if (more > 0) reason += `\n（另有 ${more} 处，完整扫描：node <skill>/scripts/check-ai-patterns.js --check 上一章文件）`
  return reason
}

function deploymentAwareProseBlockReason(root, absolute) {
  const target = longProseTarget(absolute)
  if (!target) return core.proseBlockReason(root, absolute)

  const state = path.join(target.book, "追踪", "_tracking-state.json")
  if (fs.existsSync(state)) return core.proseBlockReason(root, absolute)

  const version = deployedAgentsVersion(root)
  if (version !== null && version >= TRACKING_REQUIRED_AGENTS_VERSION) {
    // v28 起普通长篇写入缺 state 必须硬拦。整条交给严格核，同时保留核定义的
    // 受控 story-import 窗口（拆文库/{书名} 在场且 state 尚未初始化）。
    return core.proseBlockReason(root, absolute)
  }

  const reason = core.proseBlockReason(root, absolute)
  if (!reason || !reason.includes(MISSING_TRACKING_STATE)) return reason
  return legacyProseDebtReason(root, target)
}

const [command, ...args] = process.argv.slice(2)

function emitProseNet(root, absolute) {
  let text
  try {
    text = fs.readFileSync(absolute, "utf8")
  } catch {
    return
  }
  const out = core.proseNetFindings(text, core.readDeslopWhitelist(root, absolute))
  const wordcount = core.wordcountFinding(absolute, text)
  if (wordcount) out.push(wordcount)
  if (out.length) process.stdout.write(out.join("\n"))
}

if (command === "extract-target") {
  // PostToolUse 工具输入 JSON → 目标文件路径。无输入/解析失败/无路径都以非零退出，
  // 让 bash 侧静默放行（与旧 python sys.exit(1) 一致）。
  const raw = process.env.HOOK_INPUT || readStdin()
  if (!raw) process.exit(1)
  let obj
  try {
    obj = JSON.parse(raw)
  } catch {
    process.exit(1)
  }
  const target = digTargetPath(obj)
  if (!target) process.exit(1)
  process.stdout.write(target)
} else if (command === "prose-command-guard") {
  // Claude Bash PreToolUse JSON → 真正的正文写入目标 → 共享核阻断原因。只识别共享核明确
  // 支持的重定向/tee/touch/cp/mv/install 写法；grep 等只读提及不会产生 target。无目标正常
  // 放行；解析/共享核异常用独立退出码交给 bash 壳显式告警后 fail-open，不能伪装成“无目标”。
  const root = args[0]
  const raw = process.env.HOOK_INPUT || readStdin()
  try {
    if (!root || !raw) process.exit(0)
    const obj = JSON.parse(raw)
    const shellCommand = digCommand(obj)
    if (!shellCommand) process.exit(0)
    let base = root
    const requestedBase = core.existingDir(digWorkingDirectory(obj))
    if (requestedBase) {
      const relative = path.relative(path.resolve(root), requestedBase)
      if (!relative.startsWith("..") && !path.isAbsolute(relative)) base = requestedBase
    }
    const seen = new Set()
    for (const target of core.extractProseTargets(shellCommand)) {
      const absolute = core.resolveTarget(root, target, base)
      if (seen.has(absolute)) continue
      seen.add(absolute)
      const reason = core.revisionBlockReason(root, absolute) || deploymentAwareProseBlockReason(root, absolute)
      if (reason) {
        process.stdout.write(`${reason}（已从 Bash 命令识别到写入目标。）`)
        break
      }
    }
  } catch (error) {
    const detail = error && error.message ? error.message : String(error)
    process.stderr.write(`[story-guard] Bash 正文目标解析失败，已降级放行：${detail}`)
    process.exit(3)
  }
} else if (command === "prose-net") {
  // 轻量确定性网（含毒句式）+ 字数欠账，对齐旧内嵌 python 第二段的 out 列表（net 逐条 +
  // 可选字数行）。读文件失败静默退出（兜底不反噬流程）。
  // 新契约：prose-net <root> <absolute>，让 Claude 写后网能从正文向上读取最近的
  // .deslop-whitelist。保留旧单参数形态，便于已部署脚本滚动升级时 fail-open 而非报错。
  const root = args.length >= 2 ? args[0] : ""
  const absolute = args.length >= 2 ? args[1] : args[0]
  emitProseNet(root, absolute)
} else if (command === "prose-net-relative") {
  // Windows Git Bash 不可靠地改写传给原生 node.exe 的多个路径 argv。该窄入口
  // 固定以 Node 继承的 cwd 为项目根，仅从 stdin 接受项目内相对路径；绝对路径、
  // `..` 逃逸和 NUL 全部静默拒绝，不放宽 .deslop-whitelist 的项目边界。
  const rawRelative = readStdin()
  if (!rawRelative || rawRelative.includes("\0")) process.exit(0)
  const normalized = rawRelative.replace(/\\/g, "/")
  if (path.isAbsolute(normalized)) process.exit(0)
  const root = core.existingDir(process.cwd()) || path.resolve(process.cwd())
  const absolute = core.resolveTarget(root, normalized, root)
  const relative = path.relative(root, absolute)
  if (!relative || relative.startsWith("..") || path.isAbsolute(relative)) process.exit(0)
  emitProseNet(root, absolute)
} else if (command === "prose-toxic") {
  // 毒句式确定性检测单跑（供 guard 前置门 / 手工复扫调用；prose-net 已含同一组结果）。
  // 契约：stdout 空 = 干净；非空 = findings 行（每行一条，末行为清零要求 + 完整扫描提示）。
  // 文件读不了或任何内部异常一律 exit 0 静默放行（与本 CLI 的降级哲学一致，兜底不反噬流程）。
  const absolute = args[0]
  try {
    const text = fs.readFileSync(absolute, "utf8")
    const out = core.toxicPhraseFindings(text)
    if (out.length) process.stdout.write(out.join("\n"))
  } catch {
    process.exit(0)
  }
} else if (command === "prose-block-reason") {
  // 写正文前的核心阻断判据，与 OpenCode(plugin.ts) / ZCode(story_zcode_hook.js) /
  // Codex(prose_block_reason) 调的是同一个 core.proseBlockReason。
  //
  // 补这个子命令是为了消掉一处端间不对称：那三端都调核，唯独 Claude Code 的
  // guard-outline-before-prose.sh 只有纯 bash 的细纲检查，于是「首建第 N+1 章前必须
  // 先提交第 N 章追踪事务」这条顺序校验在 Claude 端从不触发——跨章连续性守卫因此
  // 在这一端是开环的（模型不主动跑 tracking_commit.py 就没人拦漂移）。
  //
  // 契约：stdout 空 = 放行；非空 = 阻断理由（单行）。异常一律静默放行，兜底不反噬流程。
  const root = args[0]
  const absolute = args[1]
  try {
    const reason = deploymentAwareProseBlockReason(root, absolute)
    if (reason) process.stdout.write(reason)
  } catch {
    process.exit(0)
  }
} else if (command === "revision-block-reason") {
  const root = args[0]
  const absolute = args[1]
  try {
    const reason = core.revisionBlockReason(root, absolute)
    if (reason) process.stdout.write(reason)
  } catch {
    process.exit(0)
  }
} else if (command === "is-git-commit") {
  // git commit 侦测。命令优先取 STORY_COMMIT_COMMAND，缺省再从 HOOK_INPUT 挖 command/cmd/script。
  // 用共享核 isGitCommitCommand（js 分词语义，与 OpenCode/ZCode 一致；对「引号内分隔符」这类
  // 边界与旧 python shlex 有已文档化、仅 advisory 的差异）。是 git commit → exit 0，否则 exit 1。
  let raw = process.env.STORY_COMMIT_COMMAND || ""
  if (!raw) {
    const hookInput = process.env.HOOK_INPUT || ""
    if (!hookInput) process.exit(1)
    let obj
    try {
      obj = JSON.parse(hookInput)
    } catch {
      obj = {}
    }
    raw = digCommand(obj)
  }
  if (!raw) process.exit(1)
  process.exit(core.isGitCommitCommand(raw) ? 0 : 1)
} else if (command === "continuity") {
  // 跨批连续性兜底：追踪 staleness + 章节标题去重。用共享核 continuityFindings（消息串与旧
  // python 逐字一致；多书/并列去重的排序按 js 语义，仅影响 advisory 顺序）。
  const root = args[0]
  const out = core.continuityFindings(root)
  if (out.length) process.stdout.write(out.join("\n") + "\n")
} else {
  process.exit(2)
}
