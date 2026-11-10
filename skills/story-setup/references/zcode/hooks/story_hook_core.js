"use strict"

// oh-story-managed: shared-hook-core

const fs = require("node:fs")
const path = require("node:path")
const crypto = require("node:crypto")
const { spawnSync } = require("node:child_process")

function existingDir(value) {
  if (typeof value !== "string" || !value.trim()) return null
  try {
    const resolved = fs.realpathSync(path.resolve(value))
    return fs.statSync(resolved).isDirectory() ? resolved : null
  } catch {
    return null
  }
}

function safeRelative(root, target) {
  try {
    const rel = path.relative(path.resolve(root), path.resolve(target))
    return rel && !rel.startsWith("..") ? rel.split(path.sep).join("/") : String(target)
  } catch {
    return String(target)
  }
}

function resolveTarget(root, target, base = root) {
  const normalized = String(target || "").replace(/\\/g, "/")
  return path.isAbsolute(normalized) ? path.resolve(normalized) : path.resolve(base || root, normalized)
}

function firstLine(file) {
  try {
    return fs.readFileSync(file, "utf8").split(/\r?\n/, 1)[0].trim()
  } catch {
    return ""
  }
}

function isHistoricalCopySegment(value) {
  const name = String(value || "")
  return name.includes("备份") || name.includes("归档") || /archives?/i.test(name)
}

function isDiscoveryExcludedEntry(entry) {
  return entry.name.startsWith(".")
    || entry.name === "node_modules"
    || (entry.isDirectory() && isHistoricalCopySegment(entry.name))
}

function findFirst(base, maxDepth, predicate) {
  // maxDepth 与 `find -maxdepth N` 一致：root 的直属条目深度为 1，深度 N 的条目可见，N+1 不可见。
  if (maxDepth <= 0) return null
  let entries = []
  try {
    entries = fs.readdirSync(base, { withFileTypes: true })
  } catch {
    return null
  }
  for (const entry of entries) {
    if (isDiscoveryExcludedEntry(entry)) continue
    const full = path.join(base, entry.name)
    if (predicate(full, entry)) return full
  }
  if (maxDepth === 1) return null
  for (const entry of entries) {
    if (!entry.isDirectory() || isDiscoveryExcludedEntry(entry)) continue
    const found = findFirst(path.join(base, entry.name), maxDepth - 1, predicate)
    if (found) return found
  }
  return null
}

function discoverActiveBook(root) {
  const declared = firstLine(path.join(root, ".active-book"))
  if (declared) {
    const candidate = existingDir(resolveTarget(root, declared))
    if (candidate) {
      // root 也要按 realpath 比：existingDir 已把 candidate 解到真实路径，若这里用未解析的
      // root，项目根位于 symlink 下（macOS /tmp、/var，或软链的家目录/工作目录）时 rel 会
      // 假性以 ".." 开头，合法的 .active-book 被静默丢弃。bash 用 pwd -P、python 用
      // root.resolve()，此处对齐两端。
      const rel = path.relative(existingDir(root) || path.resolve(root), candidate)
      const inHistoricalCopy = rel.split(path.sep).filter(Boolean).some(isHistoricalCopySegment)
      if (!rel.startsWith("..") && !path.isAbsolute(rel) && !inHistoricalCopy) return candidate
    }
  }
  const tracking = findFirst(root, 4, (_full, entry) => entry.isDirectory() && entry.name === "追踪")
  if (tracking) return path.dirname(tracking)
  const body = findFirst(root, 4, (_full, entry) => entry.isDirectory() && entry.name === "正文")
  if (body) return path.dirname(body)
  const bodyFile = findFirst(root, 4, (_full, entry) => entry.isFile() && entry.name === "正文.md")
  return bodyFile ? path.dirname(bodyFile) : null
}

function discoverAllBooks(root) {
  const books = new Map()
  function walk(base, depth) {
    if (depth <= 0) return
    let entries = []
    try { entries = fs.readdirSync(base, { withFileTypes: true }) } catch { return }
    for (const entry of entries) {
      if (isDiscoveryExcludedEntry(entry)) continue
      const full = path.join(base, entry.name)
      if (entry.isDirectory() && (entry.name === "追踪" || entry.name === "正文")) {
        books.set(path.dirname(full), path.dirname(full))
      } else if (entry.isFile() && entry.name === "正文.md") {
        books.set(path.dirname(full), path.dirname(full))
      }
    }
    if (depth === 1) return
    for (const entry of entries) {
      if (!entry.isDirectory() || isDiscoveryExcludedEntry(entry)) continue
      walk(path.join(base, entry.name), depth - 1)
    }
  }
  walk(root, 4)
  return [...books.values()]
}

function trackingCheckpointIssue(book, requireState = false, expectedLastCommitted = null) {
  const state = path.join(book, "追踪", "_tracking-state.json")
  if (!fs.existsSync(state)) {
    return requireState
      ? `追踪/_tracking-state.json 缺失；已有正文项目走 /story-import 的「旧追踪项目迁移」重建追踪（不必重跑全书拆解），新书先用 tracking_commit.py init 初始化`
      : null
  }
  let document
  try {
    document = JSON.parse(fs.readFileSync(state, "utf8"))
  } catch {
    return `追踪/_tracking-state.json 无法解析；停止写正文并重新 /story-import，不能猜测或手补状态`
  }
  if (document && typeof document === "object" && !Array.isArray(document) && document.schema_version === 4) {
    return `追踪/_tracking-state.json 仍是 schema_version=4；停止写正文，用 tracking_commit.py migrate-v4 升级并植入长期事实后再 check`
  }
  if (!document || typeof document !== "object" || Array.isArray(document) || document.schema_version !== 5) {
    return `追踪/_tracking-state.json 不是当前 schema_version=5；停止写正文并重新 /story-import，不保留旧结构兼容路径`
  }
  if (!Number.isInteger(document.state_revision)) {
    return `追踪/_tracking-state.json 缺少整数 state_revision；停止写正文并重新 /story-import`
  }
  const context = path.join(book, "追踪", "上下文.md")
  let contextRevision = null
  try {
    const match = fs.readFileSync(context, "utf8").match(/状态修订：(\d+)/)
    if (match) contextRevision = Number(match[1])
  } catch {}
  if (contextRevision !== document.state_revision) {
    const shown = contextRevision === null ? "缺失" : contextRevision
    return `追踪/上下文.md 状态修订 ${shown} 与 _tracking-state.json 的 ${document.state_revision} 不一致；重新提交该章的 mode=revision 事务重建派生视图（expected_state_revision 取 追踪/_tracking-state.json 的 state_revision 字段（check 失败时不输出 JSON））`
  }
  if (expectedLastCommitted !== null) {
    if (!Number.isInteger(document.last_committed_chapter)) {
      return `追踪/_tracking-state.json 缺少整数 last_committed_chapter；停止写正文并重新 /story-import`
    }
    // 章号已在追踪范围内 = 回炉/改名/留原稿备份，不是首建新章：文件名新但章节早已提交过，
    // 顺序校验对它恒为假（workflow-revision 的「备份原稿」步骤必然命中），跳过。
    if (expectedLastCommitted < document.last_committed_chapter) return null
    if (document.last_committed_chapter !== expectedLastCommitted) {
      return `追踪已提交到第${document.last_committed_chapter}章，首建第${expectedLastCommitted + 1}章前必须先提交第${expectedLastCommitted}章追踪事务`
    }
  }
  return null
}

function continuityFindings(root) {
  const messages = []
  for (const book of discoverAllBooks(root)) {
    const bodyDir = path.join(book, "正文")
    let chapters = []
    try {
      chapters = fs.readdirSync(bodyDir)
        .filter((file) => /^第.*章.*\.md$/.test(file))
        .map((file) => path.join(bodyDir, file))
    } catch {}

    const context = path.join(book, "追踪", "上下文.md")
    const checkpointIssue = trackingCheckpointIssue(book, chapters.length > 0)
    if (checkpointIssue) {
      messages.push(`[continuity] ${safeRelative(root, book)}：${checkpointIssue}。`)
    }
    if (chapters.length && fs.existsSync(context)) {
      try {
        const newest = Math.max(...chapters.map((file) => fs.statSync(file).mtimeMs))
        const contextTime = fs.statSync(context).mtimeMs
        if (newest > contextTime + 1000) {
          const latest = chapters.reduce((left, right) => fs.statSync(left).mtimeMs > fs.statSync(right).mtimeMs ? left : right)
          messages.push(`[continuity] ${safeRelative(root, book)}：正文已更新到「${path.basename(latest)}」但续写状态卡更早——为该章提交 tracking_commit.py 事务、check 通过后再续写，禁止分别手改 上下文.md/伏笔.md。`)
        }
      } catch {}
    }

    // 续写状态卡预算：上下文.md 由事务工具整份重建，硬上限 12288 字节。
    if (fs.existsSync(context)) {
      try {
        const contextSize = fs.statSync(context).size
        if (contextSize > 12288) {
          messages.push(`[continuity] ${safeRelative(root, book)}：追踪/上下文.md 已 ${contextSize} 字节，超出续写状态卡预算 12288 字节——提交一份 mode=revision 事务让 tracking_commit.py 整份重建，不要手改也不要继续追加。`)
        }
      } catch {}
    }

    const titles = new Map()
    for (const chapter of chapters) {
      const match = path.basename(chapter, ".md").match(/^第0*\d+章[_\- 　]+(.+)$/)
      if (!match) continue
      const title = match[1].trim()
      if (title) titles.set(title, [...(titles.get(title) || []), path.basename(chapter)])
    }
    for (const [title, files] of titles.entries()) {
      if (files.length > 1) {
        messages.push(`[continuity] ${safeRelative(root, book)}：${files.length} 章标题重复「${title}」（${files.join("、").slice(0, 60)}），建议改名。`)
      }
    }
  }
  return messages
}

function readShellWord(value, start) {
  let word = ""
  let quote = ""
  let escaped = false
  let started = false
  let index = start
  for (; index < value.length; index++) {
    const ch = value[index]
    if (escaped) {
      word += ch
      escaped = false
      started = true
      continue
    }
    if (ch === "\\" && quote !== "'") {
      word += ch
      escaped = true
      started = true
      continue
    }
    if (quote) {
      if (ch === quote) quote = ""
      else word += ch
      started = true
      continue
    }
    if (ch === '"' || ch === "'") {
      quote = ch
      started = true
      continue
    }
    if ([" ", "\t", "\r", "\n", ";", "&", "|", "<", ">", "(", ")"].includes(ch)) break
    word += ch
    started = true
  }
  return { word: started ? word : "", next: index }
}

function readHeredocDelimiter(value, start) {
  let word = ""
  let quote = ""
  let escaped = false
  let started = false
  let index = start
  for (; index < value.length; index++) {
    const ch = value[index]
    if (escaped) {
      word += ch
      escaped = false
      started = true
      continue
    }
    if (ch === "\\" && quote !== "'") {
      const next = value[index + 1] || ""
      if (quote === '"' && !["$", "`", '"', "\\", "\n"].includes(next)) {
        word += ch
      } else {
        escaped = true
      }
      started = true
      continue
    }
    if (quote) {
      if (ch === quote) quote = ""
      else word += ch
      started = true
      continue
    }
    if (ch === '"' || ch === "'") {
      quote = ch
      started = true
      continue
    }
    if ([" ", "\t", "\r", "\n", ";", "&", "|", "<", ">", "(", ")"].includes(ch)) break
    word += ch
    started = true
  }
  return { word: started ? word : "", next: index }
}

function heredocDeclarations(line) {
  const declarations = []
  let quote = ""
  let escaped = false
  for (let index = 0; index < line.length; index++) {
    const ch = line[index]
    if (escaped) {
      escaped = false
      continue
    }
    if (ch === "\\" && quote !== "'") {
      escaped = true
      continue
    }
    if (quote) {
      if (ch === quote) quote = ""
      continue
    }
    if (ch === '"' || ch === "'") {
      quote = ch
      continue
    }
    if (ch !== "<" || line[index + 1] !== "<" || line[index - 1] === "<" || line[index + 2] === "<") continue
    let cursor = index + 2
    let stripTabs = false
    if (line[cursor] === "-") {
      stripTabs = true
      cursor++
    }
    while (line[cursor] === " " || line[cursor] === "\t") cursor++
    const parsed = readHeredocDelimiter(line, cursor)
    if (parsed.word) declarations.push({ delimiter: parsed.word, stripTabs })
    index = Math.max(index, parsed.next - 1)
  }
  return declarations
}

function maskHeredocBodies(command) {
  const pending = []
  return String(command).split("\n").map((line) => {
    if (pending.length) {
      const current = pending[0]
      const comparable = current.stripTabs ? line.replace(/^\t+/, "") : line
      if (comparable === current.delimiter) {
        pending.shift()
        return line
      }
      return " ".repeat(line.length)
    }
    pending.push(...heredocDeclarations(line))
    return line
  }).join("\n")
}

function commandWordIndex(words) {
  let index = 0
  while (index < words.length) {
    while (index < words.length && (/^[A-Za-z_][A-Za-z0-9_]*=/.test(words[index]) || words[index] === "noglob")) index++
    if (words[index] === "command") {
      index++
      while (index < words.length) {
        const option = words[index]
        if (option === "--") { index++; break }
        if (option === "-v" || option === "-V" || /^-[p]*[vV]/.test(option)) return words.length
        if (option === "-p" || /^-p+$/.test(option)) { index++; continue }
        break
      }
      continue
    }
    if (words[index] === "env") {
      index++
      while (index < words.length) {
        const option = words[index]
        if (/^[A-Za-z_][A-Za-z0-9_]*=/.test(option) || ["-i", "--ignore-environment"].includes(option)) {
          index++
          continue
        }
        if (option === "-u" || option === "--unset") {
          index += 2
          continue
        }
        if (option.startsWith("--unset=") || (/^-u.+/.test(option) && option !== "-u")) {
          index++
          continue
        }
        if (option === "--") index++
        break
      }
      continue
    }
    break
  }
  return index
}

function nestedShellCommand(args) {
  const valueOptions = new Set(["-o", "+o", "-O", "+O"])
  for (let index = 0; index < args.length; index++) {
    const option = args[index]
    if (option === "--") return ""
    if (option === "-c" || (/^-[^-]+$/.test(option) && option.slice(1).includes("c"))) {
      return args[index + 1] || ""
    }
    if (valueOptions.has(option)) {
      index++
      continue
    }
    if (!option.startsWith("-") && !option.startsWith("+")) break
  }
  return ""
}

function commandSubstitutions(command) {
  const value = String(command)
  const substitutions = []
  let quote = ""
  let escaped = false
  for (let index = 0; index < value.length; index++) {
    const ch = value[index]
    if (escaped) {
      escaped = false
      continue
    }
    if (ch === "\\" && quote !== "'") {
      escaped = true
      continue
    }
    if (quote === "'") {
      if (ch === "'") quote = ""
      continue
    }
    if (ch === '"') {
      quote = quote === '"' ? "" : '"'
      continue
    }
    if (!quote && ch === "'") {
      quote = "'"
      continue
    }
    if (ch === "$" && value[index + 1] === "(" && value[index + 2] !== "(") {
      let depth = 1
      let innerQuote = ""
      let innerEscaped = false
      let end = index + 2
      for (; end < value.length; end++) {
        const inner = value[end]
        if (innerEscaped) { innerEscaped = false; continue }
        if (inner === "\\" && innerQuote !== "'") { innerEscaped = true; continue }
        if (innerQuote) {
          if (inner === innerQuote) innerQuote = ""
          continue
        }
        if (inner === '"' || inner === "'") { innerQuote = inner; continue }
        if (inner === "(") depth++
        else if (inner === ")" && --depth === 0) break
      }
      if (depth === 0) {
        substitutions.push(value.slice(index + 2, end))
        index = end
      }
      continue
    }
    if (ch === "`") {
      let end = index + 1
      let tickEscaped = false
      for (; end < value.length; end++) {
        const inner = value[end]
        if (tickEscaped) { tickEscaped = false; continue }
        if (inner === "\\") { tickEscaped = true; continue }
        if (inner === "`") break
      }
      if (end < value.length) {
        substitutions.push(value.slice(index + 1, end))
        index = end
      }
    }
  }
  return substitutions
}

function redirectTargets(command) {
  const value = String(command)
  const targets = []
  let quote = ""
  let escaped = false
  for (let index = 0; index < value.length; index++) {
    const ch = value[index]
    if (escaped) { escaped = false; continue }
    if (ch === "\\" && quote !== "'") { escaped = true; continue }
    if (quote) {
      if (ch === quote) quote = ""
      continue
    }
    if (ch === '"' || ch === "'") { quote = ch; continue }
    if (ch !== ">") continue
    let cursor = index + (value[index + 1] === ">" ? 2 : 1)
    if (value[cursor] === "|" || value[cursor] === "&") cursor++
    while (value[cursor] === " " || value[cursor] === "\t") cursor++
    const parsed = readShellWord(value, cursor)
    if (parsed.word.includes("正文")) targets.push(parsed.word)
    index = Math.max(index, parsed.next - 1)
  }
  return targets
}

function writeOperands(command, args) {
  const operands = []
  const valueOptions = command === "touch"
    ? new Set(["-d", "--date", "-r", "--reference", "-t", "--time"])
    : new Set()
  let options = true
  for (let i = 0; i < args.length; i++) {
    const arg = args[i]
    if (options && arg === "--") {
      options = false
      continue
    }
    if (options && valueOptions.has(arg)) {
      i++
      continue
    }
    if (options && [...valueOptions].some((option) => option.startsWith("--") && arg.startsWith(`${option}=`))) continue
    if (options && arg.startsWith("-") && arg !== "-") continue
    operands.push(arg)
  }
  return operands
}

function commandBasename(value) {
  const parts = String(value || "").split(/[\\/]/)
  return parts[parts.length - 1]
}

// 目录形态的落盘目标一律用 "/" 拼：path.join 在 Windows 产出反斜杠，会让三端 parity 的
// 逐字比较在 Windows 上错开（resolveTarget 之后也会把 \ 归一成 /，这里先统一即可）。
function joinPosix(directory, name) {
  return `${String(directory).replace(/[\\/]+$/, "")}/${name}`
}

function isStorySourceTarget(value) {
  return /(^|\/)(正文|大纲|设定)(\/|$)/.test(String(value || "").replace(/\\/g, "/"))
}

function copyLikeTargets(command, args) {
  const positionals = []
  let targetDirectory = ""
  let directoryOnly = false
  let options = true
  for (let i = 0; i < args.length; i++) {
    const arg = args[i]
    if (options && arg === "--") {
      options = false
      continue
    }
    if (options && (arg === "-t" || arg === "--target-directory")) {
      targetDirectory = args[++i] || ""
      continue
    }
    if (options && arg.startsWith("--target-directory=")) {
      targetDirectory = arg.slice("--target-directory=".length)
      continue
    }
    if (options && command === "install" && (arg === "-d" || arg === "--directory")) {
      directoryOnly = true
      continue
    }
    if (options && arg.startsWith("-") && arg !== "-") continue
    positionals.push(arg)
  }
  if (directoryOnly || !positionals.length) return []
  if (targetDirectory) {
    return positionals.map((source) => joinPosix(targetDirectory, commandBasename(source)))
  }
  if (positionals.length < 2) return []
  const destination = positionals[positionals.length - 1]
  const normalized = destination.replace(/\\/g, "/")
  if (normalized.endsWith("/") || normalized.split("/").pop() === "正文") {
    return positionals.slice(0, -1).map((source) => joinPosix(destination, commandBasename(source)))
  }
  return [destination]
}

function extractProseTargets(command, depth = 0) {
  const targets = []
  const scannable = maskHeredocBodies(command)
  if (depth < 8) {
    for (const nested of commandSubstitutions(scannable)) {
      targets.push(...extractProseTargets(nested, depth + 1))
    }
  }
  targets.push(...redirectTargets(scannable))
  for (const raw of shellSegments(scannable)) {
    const segment = beforeShellRedirection(raw)
    // 引号感知分词（同 shellWords）：/\s+/ 会把 cp draft.md "my book/正文/第1章.md" 的目标切碎，
    // 末位取到 book/正文/第1章.md —— 判到另一本书上（那本有细纲就直接放行）。
    const words = shellWords(segment)
    const commandIndex = commandWordIndex(words)
    const commandName = commandBasename(words[commandIndex])
    const commandArgs = words.slice(commandIndex + 1)
    if (["sh", "bash", "dash", "ksh", "zsh"].includes(commandName)) {
      const nested = nestedShellCommand(commandArgs)
      if (nested) targets.push(...extractProseTargets(nested, depth + 1))
    }
    if (commandName === "tee" || commandName === "touch") {
      for (const destination of writeOperands(commandName, commandArgs)) {
        if (isStorySourceTarget(destination)) targets.push(destination)
      }
    }
    if (commandName === "cp" || commandName === "mv" || commandName === "install") {
      for (const destination of copyLikeTargets(commandName, commandArgs)) {
        if (isStorySourceTarget(destination)) targets.push(destination)
      }
    }
  }
  return [...new Set(targets.filter(Boolean))]
}

// apply_patch 目标抽取。只认 Add/Update 会漏掉 `*** Move to:`——它是 Update File 段的子指令
// （apply_patch 的改名/搬家形态），落盘路径是**目的地**，源路径搬完就不存在了。此前
// `*** Update File: draft.md` + `*** Move to: 书/正文/第9章.md` 只抽到 draft.md：细纲门放行
// （draft.md 不是正文），写后兜底网也扫的是已经不存在的源 —— 一份没细纲的草稿能直接搬进 正文/。
// 故 Move 用目的地**顶替**同段的源目标（不是追加：源已不在，拿它去查会误伤/空扫）。
// Delete File 一律不入表（两端一致）：删除不是写入，proseBlockReason 对已存在的正文本就放行、
// 删完文件也不在了没东西可扫，认它只会给「删稿」误报；但 Delete 段也能带 Move to（搬走后删源），
// 那条 Move 的目的地照样要进表，故 Delete 只清掉待顶替的源槽位。
function extractPatchTargets(patchText) {
  const targets = []
  let sourceIndex = -1
  for (const line of String(patchText).split(/\r?\n/)) {
    // apply_patch grammar 的控制行必须从第 0 列开始；diff 上下文行固定以空格开头。
    // 先 trim 会把正文里的 ` *** Move to: notes.md` 伪装成搬家指令，顶掉真实扫描目标。
    const file = line.match(/^\*\*\* (Add|Update|Delete) File: (.+)$/)
    if (file) {
      if (file[1] === "Delete") {
        sourceIndex = -1
        continue
      }
      targets.push(file[2].trim())
      sourceIndex = targets.length - 1
      continue
    }
    const move = line.match(/^\*\*\* Move to: (.+)$/)
    if (move) {
      const destination = move[1].trim()
      if (!destination) continue
      if (sourceIndex >= 0) targets[sourceIndex] = destination
      else targets.push(destination)
      sourceIndex = -1
    }
  }
  return targets
}

function revisionSourceInfo(root, absolute) {
  const target = path.resolve(absolute)
  let relative
  try {
    relative = path.relative(path.resolve(root), target)
  } catch {
    return null
  }
  if (!relative || path.isAbsolute(relative) || relative === ".." || relative.startsWith(`..${path.sep}`)) return null
  const parts = relative.split(path.sep)
  const sourceIndex = parts.findIndex((part) => ["正文", "大纲", "设定"].includes(part))
  if (sourceIndex < 1 || parts.length <= sourceIndex + 1 || !parts[parts.length - 1].endsWith(".md")) return null
  if (parts.slice(sourceIndex + 1, -1).some((part) => part.includes("备份") || ["归档", "archive", "archives"].includes(part) || part.startsWith("."))) return null
  const book = path.join(path.resolve(root), ...parts.slice(0, sourceIndex))
  const statePath = path.join(book, "追踪", "_tracking-state.json")
  if (!fs.existsSync(statePath)) return null
  let state
  try {
    state = JSON.parse(fs.readFileSync(statePath, "utf8"))
  } catch {
    return null
  }
  const lastCommitted = Number.isInteger(state.last_committed_chapter) ? state.last_committed_chapter : null
  const base = parts[parts.length - 1]
  let chapter = null
  if (parts[sourceIndex] === "正文") {
    const match = base.match(/^第0*(\d+)章/)
    if (match) chapter = Number(match[1])
  } else if (parts[sourceIndex] === "大纲") {
    const match = base.match(/^细纲_第0*(\d+)章/)
    if (match) chapter = Number(match[1])
  }
  const activeRelative = parts.slice(sourceIndex).join("/")
  const priorCanon = chapter !== null && lastCommitted !== null
    ? chapter <= lastCommitted
    : fs.existsSync(target)
  return { target, book, activeRelative, chapter, lastCommitted, priorCanon }
}

function revisionApprovalStatus(manifestPath, manifest, manifestBytes) {
  const stampPath = path.join(path.dirname(manifestPath), "active.approved.json")
  let stamp
  try {
    stamp = JSON.parse(fs.readFileSync(stampPath, "utf8"))
  } catch {
    return "pending"
  }
  const digest = crypto.createHash("sha256").update(manifestBytes).digest("hex")
  return stamp && stamp.schema_version === 1 && stamp.status === "PASS"
    && stamp.change_id === manifest.change_id && stamp.manifest_sha256 === digest
    ? "approved"
    : "pending"
}

function revisionBlockReason(root, absolute) {
  const info = revisionSourceInfo(root, absolute)
  if (!info) return null
  const manifestPath = path.join(info.book, "追踪", "修改影响", "active.json")
  if (!fs.existsSync(manifestPath)) {
    if (!info.priorCanon) return null
    return `⛔ 修改旧内容被拦截：${safeRelative(root, info.target)} 属于已提交内容或既有权威源。先调用 revision-governor（phase=plan），再用 revision_guard.py plan 生成 ${safeRelative(root, manifestPath)}；不得只改单章而跳过关联项检查。`
  }

  let manifestBytes
  let manifest
  try {
    manifestBytes = fs.readFileSync(manifestPath)
    manifest = JSON.parse(manifestBytes.toString("utf8"))
  } catch {
    return `⛔ 修改事务被拦截：${safeRelative(root, manifestPath)} 无法解析。修复或重新生成活动修改清单后再写。`
  }
  if (!manifest || manifest.schema_version !== 1 || typeof manifest.change_id !== "string" || !Array.isArray(manifest.changed_files)) {
    return `⛔ 修改事务被拦截：${safeRelative(root, manifestPath)} 缺少有效 schema_version/change_id/changed_files；请重新运行 revision_guard.py plan。`
  }

  const approval = revisionApprovalStatus(manifestPath, manifest, manifestBytes)
  if (approval === "approved") {
    if (!info.priorCanon) return null
    return `⛔ 修改旧内容被拦截：活动事务 ${manifest.change_id} 已验收关闭，不能复用旧批准继续改 ${info.activeRelative}。请重新调用 revision-governor（phase=plan）并生成新的 active.json。`
  }
  if (!manifest.changed_files.includes(info.activeRelative)) {
    return `⛔ 计划外修改被拦截：${info.activeRelative} 不在活动事务 ${manifest.change_id} 的 changed_files 中。先让 revision-governor 重算影响链并重新生成 active.json；事务未关闭前也不得穿插正常续写。`
  }
  return null
}

function proseBlockReason(root, absolute) {
  const base = path.basename(absolute)
  const parent = path.basename(path.dirname(absolute))
  if (base === "正文.md") {
    if (fs.existsSync(absolute)) return null
    const book = path.dirname(absolute)
    if (fs.existsSync(path.join(root, "拆文库", path.basename(book)))) return null
    if (!fs.existsSync(path.join(book, "设定.md"))) return null
    if (!fs.existsSync(path.join(book, "小节大纲.md"))) {
      return `⛔ 写正文被拦截：${safeRelative(root, absolute)} 缺少同目录 小节大纲.md。先按 story-short-write 完成「小节大纲.md」再写正文。`
    }
    return null
  }
  if (parent !== "正文" || !/^第.*章.*\.md$/.test(base)) return null
  const match = base.match(/^第0*(\d+)章/)
  if (!match) return null
  const chapter = match[1]
  const book = path.dirname(path.dirname(absolute))
  const state = path.join(book, "追踪", "_tracking-state.json")
  // 这是守卫的 canonical case：agent 可能在任何脚手架存在前就首建 {书}/正文/第N章.md。
  // 是否“像一本书”不能作为放行条件；相对路径误判应在宿主 adapter 按 cwd 正确解析，而不是
  // 让核心守卫 fail open。
  // story-import 在复制既有正文、尚未执行 tracking init 的窗口可以写；一旦 state 存在，
  // 即进入当前追踪协议，不再因为保留了 拆文库/ 分析资产而永久绕过守卫。
  if (fs.existsSync(path.join(root, "拆文库", path.basename(book))) && !fs.existsSync(state)) return null
  const exists = fs.existsSync(absolute)
  const outlineDir = path.join(book, "大纲")
  let found = false
  if (!exists) {
    try {
      found = fs.readdirSync(outlineDir).some((file) => {
        const candidate = file.match(/^细纲_第0*(\d+)章.*\.md$/)
        return candidate && candidate[1] === chapter
      })
    } catch {}
    if (!found) {
      return `⛔ 写正文被拦截：第 ${chapter} 章缺少细纲（${safeRelative(root, outlineDir)}/细纲_第${chapter}章.md）。先按 story-long-write 单章流程补建细纲再写正文。`
    }
  }
  const checkpointIssue = trackingCheckpointIssue(book, true, exists ? null : Number(chapter) - 1)
  if (checkpointIssue) {
    return `⛔ 写正文被拦截：${safeRelative(root, book)} 的${checkpointIssue}。`
  }
  if (exists) return null
  // 欠账门（无状态）：写第 N 章（首建）前，上一章有未清毒句式时先清再写。
  // 判据现算自上一章文件本身，不落任何状态文件；找不到上一章/读取失败一律放行（宁可漏拦不可误伤）。
  // js↔py 文案由 check-hook-regex-sync.sh 锁同步，判定由 test-prose-net-parity.sh Part E 锁 parity。
  const prevNum = Number(chapter) - 1
  if (prevNum >= 1) {
    let prevFile = null
    try {
      // readdir 顺序在 ext4/overlayfs 上是哈希序：不排序就可能挑中同章号的原稿备份
      // （workflow-revision 的「备份原稿」产物），拿早已被改写掉的旧文本报欠账。
      // 显式排除 _原稿_ 备份并排序，保证四端与各文件系统上取到同一个「上一章」。
      const candidates = fs.readdirSync(path.dirname(absolute))
        .filter((file) => {
          const pm = file.match(/^第0*(\d+)章.*\.md$/)
          return pm && Number(pm[1]) === prevNum && !file.includes("_原稿_")
        })
        .sort()
      if (candidates.length) prevFile = path.join(path.dirname(absolute), candidates[0])
    } catch {}
    if (prevFile) {
      let prevText = null
      try { prevText = fs.readFileSync(prevFile, "utf8") } catch {}
      if (prevText !== null) {
        // 中文语言漂移不属于「去 AI 味风格取舍」，风格跳过不得豁免。
        // 有意保留外语只能通过 .deslop-whitelist 的 token/短句精确登记放行。
        const languageHits = languageLeakRecords(prevText, readDeslopWhitelist(root, prevFile))
          .filter((record) => record.blocking)
        if (languageHits.length) {
          const shown = languageHits.slice(0, 6).map((record) => record.finding)
          const more = languageHits.length - shown.length
          let reason = `⛔ 写正文被拦截：上一章（${path.basename(prevFile)}）有 ${languageHits.length} 处未清中文语言漂移欠账，先改成中文再写第 ${chapter} 章；确需保留的外语逐项写入项目根 .deslop-whitelist 后重试。\n${shown.join("\n")}`
          if (more > 0) reason += `\n（另有 ${more} 处，请执行正文确定性扫描查看全部命中）`
          return reason
        }
      }
      if (prevText !== null) {
        const hits = toxicPhraseFindings(prevText).filter((line) => line.startsWith("第"))
        if (hits.length) {
          const shown = hits.slice(0, 6)
          const more = hits.length - shown.length
          let reason = `⛔ 写正文被拦截：上一章（${path.basename(prevFile)}）有 ${hits.length} 处未清毒句式欠账，先清零再写第 ${chapter} 章；毒句式欠账必须改写清零，正文不得添加 HTML 豁免标记。\n${shown.join("\n")}`
          if (more > 0) reason += `\n（另有 ${more} 处，完整扫描：node <skill>/scripts/check-ai-patterns.js --check 上一章文件）`
          return reason
        }
      }
    }
  }
  return null
}

// 收尾标点集与深扫 oracle check-degeneration.js 的 findTruncation 对齐（[。！？!?…”"』」）)】]）：
// 】 是章尾系统播报模板的收束符（agent-references/hooks-chapter.md 章尾实战模板一/四），ASCII "
// 是 normalize-punctuation.js --quote-mode ascii 的合法收引号，两者都不该被判「疑似截断」。
const TERMINAL = new Set(Array.from("。！？…”』」）)!?.~—】\""))
const QUOTE_OPENERS = new Set(["「", "“", "‘", "『", '"'])
const SOFT_PATTERNS = [
  // 型号后缀（AI语言模型/AI助手/人工智能语言模型/AI模型/AI大模型）必须可选吃掉：否则前视断言
  // 紧跟在「AI」后面看到的是「语」/「助」/「模」，最典型的退化开场整类漏检。
  [/作为(一个)?(AI|人工智能|大?语言模型|智能助手|聊天助手)(?:语言模型|大?模型|助手|机器人)?(?=，|,|。|、|；|;|：|:|！|!|？|\?|\s|）|\)|」|』|"|】|我|无法|不能|没法|$)/, "AI 自指"],
  [/^(Sure|Certainly|Here'?s|As an AI|I (?:cannot|can't|am unable|apologize))/, "英文 AI 腔"],
  [/我(无法|不能)(继续(写|创作|生成|下去|输出)?|生成(内容|文本|正文)?|创作|续写|写作|完成(这个|本)?(章|篇|创作|请求)?)/, "生成拒绝语"],
]
// 中文正文语言网。与 Codex Python hook 同构，fixture 逐字 parity 由
// scripts/test-prose-net-parity.sh 锁定。这张网只在已被宿主判定为「中文正文路径」的
// 文件上运行；英文发行稿不走普通长/短篇正文管道。
//
// 确定性 blocking：中文叙事和台词中的任何外文字母，包括缩写、型号、代号、
// 全角/数学字母和混淆字符，都不得由检测器自动豁免。URL/邮箱/Markdown link
// target/inline code/代码块/路径与文件名只在明确非叙事结构中机械保护。其他
// 外语必须经用户单独确认后，在 .deslop-whitelist 一行一项精确登记。
const LANGUAGE_WORD_RE = /[A-Za-z]+(?:['’][A-Za-z]+)?/g
const LANGUAGE_SEQUENCE_RE = /[A-Za-z]+(?:['’][A-Za-z]+)?(?:[ \t]+[A-Za-z]+(?:['’][A-Za-z]+)?){2,}/g
const LANGUAGE_SENTENCE_RE = /[^。！？!?;；\n]+[。！？!?;；]?/g
const LANGUAGE_CJK_RE = /[\u3400-\u9fff]/
const LANGUAGE_QUOTE_PAIRS = [["「", "」"], ["『", "』"], ["“", "”"], ["‘", "’"], ['"', '"'], ["'", "'"]]
const LANGUAGE_OUTER_QUOTES = /^[\s「」『』“”‘’"']+|[\s「」『』“”‘’"']+$/g
const LANGUAGE_TRAILING_PUNCT = /[。.！？!?,，；;：:…]+$/

function normalizedLanguagePhrase(value) {
  let text = String(value || "").trim().replace(LANGUAGE_OUTER_QUOTES, "").trim()
  text = text.replace(LANGUAGE_TRAILING_PUNCT, "").trim()
  return text.replace(/[ \t\r\n　]+/g, " ")
}

function parseDeslopWhitelist(text) {
  const entries = []
  for (const raw of String(text || "").split(/\r?\n/)) {
    if (/^\s*#/.test(raw)) continue
    const value = raw.replace(/\s+#.*$/, "").trim()
    if (value) entries.push(value)
  }
  return entries
}

function readDeslopWhitelist(root, absolute = "") {
  if (!root) return []
  // macOS 的 /var -> /private/var、用户工作区软链等会让「root 已 realpath、tool path
  // 仍是软链路径」。只用 path.resolve 会把合法正文误判为越界，回退 root 后漏读书目级
  // .deslop-whitelist。已存在目录两边都用 realpath 后再比较。
  const boundary = existingDir(root) || path.resolve(root)
  const absoluteDir = absolute ? path.dirname(path.resolve(absolute)) : boundary
  let current = existingDir(absoluteDir) || absoluteDir
  const relative = path.relative(boundary, current)
  if (relative.startsWith("..") || path.isAbsolute(relative)) current = boundary
  while (true) {
    const candidate = path.join(current, ".deslop-whitelist")
    try { return parseDeslopWhitelist(fs.readFileSync(candidate, "utf8")) } catch {}
    if (current === boundary) break
    const parent = path.dirname(current)
    if (parent === current) break
    const rel = path.relative(boundary, parent)
    if (rel.startsWith("..") || path.isAbsolute(rel)) break
    current = parent
  }
  return []
}

function languageWhitelisted(entries, candidate, singleToken = false) {
  const raw = String(candidate || "").trim()
  if (!raw) return false
  if (singleToken) return entries.some((entry) => entry === raw)
  const normalized = normalizedLanguagePhrase(raw)
  return entries.some((entry) => normalizedLanguagePhrase(entry) === normalized)
}

function languageIsForeignLetter(value) {
  for (const unit of String(value || "").normalize("NFKC")) {
    if (/\p{L}/u.test(unit) && !/\p{Script=Han}/u.test(unit)) return true
  }
  return false
}

function languageWhitelistBoundaryAt(text, index) {
  if (index < 0 || index >= text.length) return false
  const char = String.fromCodePoint(text.codePointAt(index))
  return languageIsForeignLetter(char) || /[0-9_.+/#-]/.test(char)
}

function maskLanguageWhitelist(line, masked, entries) {
  const chars = String(masked).split("")
  for (const entry of entries) {
    if (!entry) continue
    let offset = 0
    while (offset <= line.length - entry.length) {
      const start = line.indexOf(entry, offset)
      if (start < 0) break
      const end = start + entry.length
      const whitespace = (line.slice(end).match(/^\s+/) || [""])[0]
      const followedByForeignWord = whitespace.length > 0
        && languageIsForeignLetter(String.fromCodePoint(line.codePointAt(end + whitespace.length) || 0))
      if (!languageWhitelistBoundaryAt(line, start - 1)
        && !languageWhitelistBoundaryAt(line, end)
        && !followedByForeignWord) {
        for (let index = start; index < end; index++) chars[index] = " "
      }
      offset = start + Math.max(entry.length, 1)
    }
  }
  return chars.join("")
}

function maskLanguageMarkupProtected(text) {
  const source = String(text)
  const chars = source.split("")
  const mask = (pattern) => {
    pattern.lastIndex = 0
    for (const match of source.matchAll(pattern)) {
      for (let index = match.index; index < match.index + match[0].length; index++) chars[index] = " "
    }
  }
  mask(/```[\s\S]*?```|~~~[\s\S]*?~~~/g)
  mask(/`+[^`\n]*`+/g)
  return chars.join("")
}

function maskLanguageProtected(line) {
  const chars = String(line).split("")
  const mask = (start, end) => { for (let i = start; i < end; i++) chars[i] = " " }
  const apply = (regex, range = null) => {
    regex.lastIndex = 0
    let match
    while ((match = regex.exec(line)) !== null) {
      const [start, end] = range ? range(match) : [match.index, match.index + match[0].length]
      mask(start, end)
      if (match[0].length === 0) regex.lastIndex++
    }
  }
  apply(/`+[^`\n]*`+/g)
  apply(/\b(?:https?:\/\/|ftp:\/\/|www\.)[^\s<>"‘’'「」『』“”（）()]+/gi)
  apply(/\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g)
  apply(/\]\(\s*(?:<[^>\r\n]+>|[^)\s\r\n]+)(?:\s+["'][^"'\r\n]*["'])?\s*\)/g, (m) => {
    const open = m[0].indexOf("(")
    return [m.index + open + 1, m.index + m[0].length - 1]
  })
  // Reference-style link 的第二个 id 不是可见正文；第一个 label 仍然会被扫描。
  apply(/\]\s*\[([A-Za-z0-9_.-]+)\]/g, (m) => {
    const offset = m[0].lastIndexOf(m[1])
    return [m.index + offset, m.index + offset + m[1].length]
  })
  // 绝对/相对路径的目录段允许 Unicode，末级也不强制有扩展名。
  apply(/(?:[A-Za-z]:[\\/]|\.{1,2}[\\/]|\/)(?:[^\s/\\<>"'“”‘’「」『』【】()（）,，。；;：:!！?？、]+[\\/])*[^\s/\\<>"'“”‘’「」『』【】()（）,，。；;：:!！?？、]+/g)
  apply(/(?<![A-Za-z0-9])(?:[^\s/\\<>"'“”‘’「」『』【】()（）,，。；;：:!！?？、]+[\\/])+[^\s/\\<>"'“”‘’「」『』【】()（）,，。；;：:!！?？、]+(?![A-Za-z0-9])/g)
  apply(/(?<![A-Za-z0-9])(?:[A-Za-z0-9_-]+\.)+[A-Za-z][A-Za-z0-9]{0,11}(?![A-Za-z0-9])/g)
  apply(/(?<![A-Za-z0-9])\.[A-Za-z][A-Za-z0-9]{0,11}(?![A-Za-z0-9])/g)
  return chars.join("")
}

function languageQuoteSpans(line) {
  const spans = []
  for (const [open, close] of LANGUAGE_QUOTE_PAIRS) {
    let cursor = 0
    while (cursor < line.length) {
      const start = line.indexOf(open, cursor)
      if (start < 0) break
      const end = line.indexOf(close, start + open.length)
      if (end < 0) break
      spans.push([start, end + close.length, start + open.length, end])
      cursor = end + close.length
    }
  }
  return spans.sort((a, b) => a[0] - b[0] || a[1] - b[1])
}

function languageContainingQuote(spans, start, end) {
  return spans.find((span) => start >= span[2] && end <= span[3]) || null
}

function languageWords(value) {
  return [...String(value).matchAll(LANGUAGE_WORD_RE)]
}

function languageOnly(value) {
  const withoutWords = String(value).replace(LANGUAGE_WORD_RE, "")
  return !LANGUAGE_CJK_RE.test(value) && !/[A-Za-z]/.test(withoutWords) &&
    !withoutWords.replace(/[\s\d　「」『』“”‘’"'()[\]{}（）【】<>。.！？!?,，；;：:…—~*_=+-]/g, "")
}

function languageExcerpt(value) {
  return normalizedLanguagePhrase(value).slice(0, 40)
}

function languageRecord(lineNo, start, end, type, excerpt, blocking) {
  const advice = blocking
    ? "中文正文应改成中文；确需逐字保留时，必须经用户单独确认后写入 .deslop-whitelist 精确登记。"
    : "请核对是否为设定中的专名/短词；非有意保留就改成中文，保留则写入 .deslop-whitelist 精确登记。"
  return {
    line: lineNo,
    start,
    end,
    blocking,
    finding: `第${lineNo}行 ${type}：「${excerpt}」——${advice}`,
  }
}

function languageLeakRecords(text, whitelistEntries = []) {
  const entries = Array.isArray(whitelistEntries) ? whitelistEntries : []
  const records = []
  const markupRe = /<!--[\s\S]*?-->|<\/?[A-Za-z][^>]*>|<![A-Za-z][^>]*>|&(?:[A-Za-z][A-Za-z0-9]+|#\d+|#x[0-9A-Fa-f]+);/g
  const markupVisible = maskLanguageMarkupProtected(text)
  for (const match of markupVisible.matchAll(markupRe)) {
    const lineNo = String(text).slice(0, match.index).split("\n").length
    records.push({
      line: lineNo,
      start: match.index,
      end: match.index + match[0].length,
      blocking: true,
      finding: `第${lineNo}行 HTML 标记泄漏：「${match[0].replace(/\s+/g, " ").slice(0, 40)}」——HTML 标签、注释和实体不得进入交付正文。`,
    })
  }
  let fenceChar = ""
  let fenceLength = 0
  String(text).split("\n").forEach((raw, index) => {
    const trimmed = raw.trim()
    const fence = trimmed.match(/^(`{3,}|~{3,})/)
    if (fence) {
      const marker = fence[1]
      if (!fenceChar) {
        fenceChar = marker[0]
        fenceLength = marker.length
      } else if (marker[0] === fenceChar && marker.length >= fenceLength && new RegExp(`^${fenceChar}{${fenceLength},}[ \\t]*$`).test(trimmed)) {
        fenceChar = ""
        fenceLength = 0
      }
      return
    }
    if (fenceChar || skippableLine(trimmed)) return
    // Markdown reference definition 是文档元数据，不是可见正文。
    if (/^\s{0,3}\[[^\]\n]+\]:\s*(?:<[^>\n]+>|\S+)/.test(raw)) return
    const lineNo = index + 1
    const masked = maskLanguageWhitelist(raw, maskLanguageProtected(raw), entries)
    const quotes = languageQuoteSpans(raw)
    const occupied = []
    const overlaps = (start, end) => occupied.some(([left, right]) => start < right && end > left)
    const add = (record) => { records.push(record); occupied.push([record.start, record.end]) }

    // 完整英文台词是硬提醒，不因「在引号里」而跳过。按每个命中的自身 offset
    // 判引号作用域，避免本行别处有引号就把叙述里的英文一起降级。
    for (const span of quotes) {
      const visible = masked.slice(span[2], span[3])
      const words = languageWords(visible)
      if (!words.length || !languageOnly(visible)) continue
      const candidate = raw.slice(span[2], span[3])
      if (languageWhitelisted(entries, candidate, false)) continue
      add(languageRecord(lineNo, span[2], span[3], "完整英文台词泄漏", languageExcerpt(candidate), true))
    }

    LANGUAGE_SENTENCE_RE.lastIndex = 0
    let sentence
    while ((sentence = LANGUAGE_SENTENCE_RE.exec(masked)) !== null) {
      const start = sentence.index
      const end = start + sentence[0].length
      if (overlaps(start, end)) continue
      const words = languageWords(sentence[0])
      if (!words.length || !languageOnly(sentence[0])) continue
      const candidate = raw.slice(start, end)
      if (languageWhitelisted(entries, candidate, words.length === 1)) continue
      const singleSentence = words.length === 1 && /[。！？.!?][ \t]*$/.test(candidate)
      if (words.length >= 2 || singleSentence || /^[a-z]{4,}$/.test(words[0][0])) {
        const type = words.length >= 2 || singleSentence ? "纯英文句段泄漏" : "裸英文词泄漏"
        add(languageRecord(lineNo, start, end, type, languageExcerpt(candidate), true))
      } else {
        add(languageRecord(lineNo, start, end, "裸外文字母泄漏", languageExcerpt(candidate), true))
      }
    }

    LANGUAGE_SEQUENCE_RE.lastIndex = 0
    let sequence
    while ((sequence = LANGUAGE_SEQUENCE_RE.exec(masked)) !== null) {
      const start = sequence.index
      const end = start + sequence[0].length
      if (overlaps(start, end)) continue
      const letters = (sequence[0].match(/[A-Za-z]/g) || []).length
      if (letters < 12 || languageWhitelisted(entries, sequence[0], false)) continue
      add(languageRecord(lineNo, start, end, "连续英文短语泄漏", languageExcerpt(sequence[0]), true))
    }

    LANGUAGE_WORD_RE.lastIndex = 0
    let word
    while ((word = LANGUAGE_WORD_RE.exec(masked)) !== null) {
      const start = word.index
      const end = start + word[0].length
      if (overlaps(start, end) || languageWhitelisted(entries, word[0], true)) continue
      const quote = languageContainingQuote(quotes, start, end)
      add(languageRecord(lineNo, start, end, quote ? "台词外文字母泄漏" : "裸外文字母泄漏", word[0], true))
    }

    // ASCII 以外的外文字母也是硬阻断；NFKC 使全角/数学字母/罗马数字归入同一规则。
    let cursor = 0
    while (cursor < masked.length) {
      const char = String.fromCodePoint(masked.codePointAt(cursor))
      if (/[A-Za-z]/.test(char) || !languageIsForeignLetter(char)) {
        cursor += char.length
        continue
      }
      const start = cursor
      let end = cursor + char.length
      while (end < masked.length) {
        const next = String.fromCodePoint(masked.codePointAt(end))
        if (!languageIsForeignLetter(next) && !/[\p{M}\p{N}_'’.-]/u.test(next)) break
        end += next.length
      }
      if (!overlaps(start, end)) {
        const candidate = raw.slice(start, end)
        if (!languageWhitelisted(entries, candidate, true)) {
          add(languageRecord(lineNo, start, end, "Unicode 外文字母泄漏", candidate, true))
        }
      }
      cursor = end
    }
  })
  return records
}

function languageLeakFindings(text, whitelistEntries = []) {
  return languageLeakRecords(text, whitelistEntries).map((record) => record.finding)
}

const HARD_PATTERNS = [
  [/[（(](此处|以下|这里|下文|后续)?[^）)]{0,10}(省略|略去|略过)[^）)]{0,10}[）)]/, "占位符（括号省略）"],
  [/(TODO|占位符|placeholder|待补充|此处待填|此处待补)/, "占位符"],
  [/(细纲|情节点|卷纲|功能标签|目标情绪|字数目标|章首钩子|章尾钩子|任务描述)/, '工程词泄漏'],
  [/内容概括|情节安排|预算合计|结尾设定|阶段位置|结构公式|压力级|爽点类型|章节定位|\bV\d+-U\d+\b|\b[FE]\d{3,}\b|(?:追踪|大纲|设定|拆文库)\/[^\s，。）】」]+\.md/, '工程词泄漏'],
  // 章号引用的英文缩写：ch13 / Ch.13 / CH 13 / chapter 13。中文工程词表收不到它，
  // 实测有整段「她在 ch13 便学乖了」漏进正文无人拦。这条零误报（\b 前界让 Bach13、
  // A13 不命中）、中文正文里也永不合法，所以进自动网而不是只留在 check-degeneration.js
  // 的工作流步骤里——后者要模型自觉执行，弱模型跳过步骤就等于没有。
  [/\b(?:ch|chap|chapter)\.?\s?\d{1,4}\b/i, "章号引用泄漏"],
  [/�/, "乱码（替换字符）"],
]

function skippableLine(line) {
  return !line || line.startsWith("#") || line === "---" || /^[-—=*·•\s]+$/.test(line)
}

// ── 毒句式（确定性 AI 句式指纹，写后正文网热路径）─────────────────────────────
// 与 check-ai-patterns.js 的同名新规则统一规格：只收确定性、低误报的句式；密度型/
// advisory 检测归 check-ai-patterns.js 深扫，不进这张每次写正文都跑的网。全部正则
// 线性扫描、量词有界，无回溯灾难。台词/弹幕/系统播报不算：逐行把成对引号段等长
// 问号占位（占位天然截断各规则的字符类，规则不会跨引号拼出假命中；见
// maskQuotedSpans 为何用问号而不是句号），占位后仍残留引号字符（跨行对话/未闭合）
// 的行整行跳过。js↔py 同构实现（codex
// story_codex_hook.py）由 scripts/check-hook-regex-sync.sh（规范串逐字锁）与
// scripts/test-prose-net-parity.sh（fixture 逐字 diff）锁 parity，文案以本核为准。
const TOXIC_QUOTE_SPANS = [/「[^」]*」/g, /『[^』]*』/g, /【[^】]*】/g, /“[^”]*”/g, /‘[^’]*’/g, /"[^"]*"/g, /'[^']*'/g]
const TOXIC_QUOTE_CHARS = new Set(Array.from("「」『』【】“”‘’\"'"))
// 分句起点边界（前一字符属于它才认「是A，不是B」的分句首「是」）；同时用作确认语的右边界。
const TOXIC_CLAUSE_BOUNDARY = new Set(Array.from("，,。.！!？?；;：:、…—~ \t　"))
// 疑问尾（是吗/是吧/是嘛）与确认语（是的/是啊/是呀/是呢+边界）里的「是」不是对比句系动词；
// 排除逻辑移植自 check-ai-patterns.js 的 TAG_PARTICLES / AFFIRMATION_TAG_PARTICLES。
const TOXIC_TAG_PARTICLES = new Set(["吗", "吧", "嘛"])
const TOXIC_AFFIRM_PARTICLES = new Set(["的", "啊", "呀", "呢"])
const TOXIC_TRAILER_WINDOW = 600
const TOXIC_SENTENCE_PATTERNS = [
  [/声音(?:并)?不[大高响亮][^。！？!?\n]{0,16}[却但偏]/g, "voice-contrast", "删「不X…却Y」反差腔，直接写具体效果或动作。"],
  [/(?:没有[^。！？!?\n，,]{1,12}[，,]){2}/g, "negation-parade", "「没有…，没有…」排比删到只剩一个或全删，改写正面在场的细节。"],
  [/是[^。！？!?\n，,]{1,12}[，,]\s*(?:而)?不是[^。！？!?\n]{1,20}/g, "reverse-not-is", "删否定铺垫，直接写肯定项，或改成动作细节。"],
  [/不是[^。！？!?\n]{1,16}[，,]\s*(?:而)?是/g, "not-is-comparison", "删否定铺垫，直接写肯定项，或改成动作细节。"],
]
// 「正式拉开序幕/帷幕」是场内事件的报幕式陈述，不是叙述者预告，lookbehind 排除（同 check-ai-patterns.js）。
const TOXIC_TRAILER_PATTERN = /没人知道|谁也不知道|谁也没想到|殊不知|(?:这)?才刚刚开(?:始|头)|正(?:朝着|向着)[^。！？!?\n]{0,24}(?:压|涌|袭|逼)(?:了?过去|了?过来|来)|(?<!正式)拉开(?:序幕|帷幕)|即将(?:开始|来临|降临)/
// 章尾状态总结体：与 trailer-ending 共用文末窗口，盖章过去而非预告将来（同 check-ai-patterns.js）。
// 收的都是 banned-words 已按名禁掉的形态；不收「(这|那)一刻…终于明白」——真人叙述里那是正常认知
// 节拍，短篇第一人称审判句还是卖点。各分支要求落在句末断言位，避免吃进条件从句/动补/成语/及物用法/否定认知。
const TOXIC_TRAILER_SUMMARY_PATTERN = /这一(?:夜|天|刻|战|年|局|役)[，,]?[^。！？!?，,\n]{0,6}(?<!命中)(?<!是)注定[^。！？!?\n]{0,8}[。！]|就这样[，,][^。！？!?，,\n]{0,8}(?:一切|全部)[^。！？!?，,\n]{0,4}(?:结束了|落幕|收场)[。！]|这一切[，,]?[^。！？!?，,\n]{0,6}(?:都)?(?:说明|意味着|结束了)(?!的)(?:(?!什么)[^。！？!?\n]){0,6}[。！]|(?:新的篇章|新的旅程|崭新的篇章|新的人生)[^。！？!?\n]{0,6}(?:开始|拉开|展开)|命运[^。！？!?\n]{0,6}齿轮/
// 「是A，不是B」的反问尾巴（…，不是吗/么/吧）不算对比句；取匹配段最后一个「不是」后的首字判断。
const TOXIC_REVERSE_TAIL = /.*[，,]\s*(?:而)?不是([^。！？!?\n]*)$/

// 占位字符用「？」而不是「。」：占位既要截断各规则的 [^。！？!?…] 否定类（？与句号在每条规则的
// 否定类里等效），又不能落在任何规则的接受位。句号占位会替 trailer-summary 的句末 [。！] 伪造出
// 终止符，让「这一战注定是「血屠」的开端，…」这类引号里放代号/绰号的叙述行被误报，且报出的
// 『这一战注定是。』在原文里 grep 不到。占位长度不变，故 trailer 窗口切点不漂移。
function maskQuotedSpans(line) {
  let out = line
  for (const spans of TOXIC_QUOTE_SPANS) out = out.replace(spans, (m) => "？".repeat(m.length))
  return out
}

// 「是不是」疑问、翻转「是」后跟疑问尾/确认语 → 不算「不是A，(而)是B」对比句。
function toxicNotIsExcluded(line, matched, start) {
  if (start > 0 && line[start - 1] === "是") return true
  const end = start + matched.length
  const c1 = line[end] || ""
  const c2 = line[end + 1] || ""
  if (TOXIC_TAG_PARTICLES.has(c1)) return true
  if (TOXIC_AFFIRM_PARTICLES.has(c1) && (c2 === "" || TOXIC_CLAUSE_BOUNDARY.has(c2))) return true
  return false
}

// 只认分句首的「是A，不是B」：句中「但是/还是/只是/他是…」的「是」一律不算（either-or
// 「不是/就是/也是」与全部「X是」连词/副词合成词都被分句首判定排除）；「是的，不是…」
// 确认语开头、「是不是…」问句起头、「…，不是吗/么/吧」反问尾巴不算（同 check-ai-patterns.js）。
function toxicReverseNotIsExcluded(line, matched, start) {
  const prev = start > 0 ? line[start - 1] : ""
  if (prev !== "" && !TOXIC_CLAUSE_BOUNDARY.has(prev)) return true
  if (line.slice(start + 1, start + 3) === "不是") return true
  const c1 = line[start + 1] || ""
  const c2 = line[start + 2] || ""
  if ((TOXIC_TAG_PARTICLES.has(c1) || TOXIC_AFFIRM_PARTICLES.has(c1)) && (c2 === "" || TOXIC_CLAUSE_BOUNDARY.has(c2))) return true
  const tail = matched.match(TOXIC_REVERSE_TAIL)
  const t1 = tail && tail[1] ? tail[1][0] : ""
  if (t1 === "吗" || t1 === "么" || t1 === "吧") return true
  return false
}

// 每行只报第一条命中的句式规则（复扫到净哲学：改完一处再扫下一处）。
function matchToxicSentence(line) {
  for (const [regex, label, fix] of TOXIC_SENTENCE_PATTERNS) {
    regex.lastIndex = 0
    let match
    while ((match = regex.exec(line)) !== null) {
      if (label === "not-is-comparison" && toxicNotIsExcluded(line, match[0], match.index)) continue
      if (label === "reverse-not-is" && toxicReverseNotIsExcluded(line, match[0], match.index)) continue
      return [label, fix, match[0]]
    }
  }
  return null
}

function toxicPhraseFindings(text) {
  const findings = []
  const content = []
  text.split("\n").forEach((raw, index) => {
    const line = raw.trim()
    if (skippableLine(line)) return
    const masked = maskQuotedSpans(line)
    for (const ch of masked) {
      if (TOXIC_QUOTE_CHARS.has(ch)) return
    }
    content.push([index + 1, masked])
  })
  for (const [lineNo, masked] of content) {
    const hit = matchToxicSentence(masked)
    if (hit) findings.push(`第${lineNo}行 毒句式[${hit[0]}]：『${hit[2].slice(0, 20)}』——${hit[1]}`)
  }
  // trailer-ending 只扫文末 600 字窗口（引号占位后按行累计，边界行整行计入）。
  let acc = 0
  let cut = content.length
  while (cut > 0 && acc < TOXIC_TRAILER_WINDOW) {
    cut -= 1
    acc += Array.from(content[cut][1]).length
  }
  for (let i = cut; i < content.length; i++) {
    const [lineNo, masked] = content[i]
    const match = masked.match(TOXIC_TRAILER_PATTERN)
    if (match) findings.push(`第${lineNo}行 毒句式[trailer-ending]：『${match[0].slice(0, 20)}』——删章尾预告腔，用正在发生的动作或画面收章。`)
    const summary = masked.match(TOXIC_TRAILER_SUMMARY_PATTERN)
    if (summary) findings.push(`第${lineNo}行 毒句式[trailer-summary]：『${summary[0].slice(0, 20)}』——删章尾状态总结句，收束状态是细纲的规划口径，正文落到具体动作、画面或台词上。`)
  }
  if (findings.length) findings.push("毒句式是确定性 AI 指纹：本章须清零后再继续。完整扫描：node <skill>/scripts/check-ai-patterns.js --check <正文文件>")
  return findings
}

function proseNetFindings(text, whitelistEntries = []) {
  const findings = []
  const content = []
  text.split("\n").forEach((raw, index) => {
    const line = raw.trim()
    if (skippableLine(line)) return
    const lineNo = index + 1
    content.push([lineNo, line])
    let hit = false
    if (!QUOTE_OPENERS.has(line[0])) {
      for (const [regex, label] of SOFT_PATTERNS) {
        const match = line.match(regex)
        if (match) {
          findings.push(`第${lineNo}行 元信息泄漏（${label}）：「${match[0].slice(0, 20)}」`)
          hit = true
          break
        }
      }
    }
    if (hit) return
    for (const [regex, label] of HARD_PATTERNS) {
      const match = line.match(regex)
      if (match) {
        findings.push(`第${lineNo}行 ${label}：「${match[0].slice(0, 20)}」`)
        hit = true
        break
      }
    }
    if (hit) return
  })
  for (let i = 1; i < content.length; i++) {
    const previous = content[i - 1][1]
    const [lineNo, current] = content[i]
    if (previous === current && current.length >= 8) findings.push(`第${lineNo}行 紧邻复读：整行与上一行完全相同「${current.slice(0, 20)}」`)
  }
  if (content.length) {
    const [lineNo, last] = content[content.length - 1]
    if (!TERMINAL.has(Array.from(last).pop())) findings.push(`第${lineNo}行 疑似截断：结尾「…${last.slice(-12)}」未以标点收束`)
  }
  // 正文内不使用 HTML 跳过标记；风格跳过也不改变 Hook 的语言与标记检查。
  findings.push(...toxicPhraseFindings(text))
  findings.push(...languageLeakFindings(text, whitelistEntries))
  return findings
}

function isProsePath(absolute) {
  const base = path.basename(absolute)
  const parent = path.basename(path.dirname(absolute))
  if (base === "正文.md") return fs.existsSync(path.join(path.dirname(absolute), "设定.md"))
  if (parent !== "正文" || !/^第.*章.*\.md$/.test(base)) return false
  const book = path.dirname(path.dirname(absolute))
  // 大纲/追踪/设定 must be directories; 设定.md a file — matches the bash oracle
  // check-prose-after-write.sh (`[ -d 大纲 ] || … || [ -f 设定.md ]`).
  return ["大纲", "追踪", "设定"].some((name) => existingDir(path.join(book, name))) || fs.existsSync(path.join(book, "设定.md"))
}

function wordcountFinding(absolute, text) {
  if (path.basename(path.dirname(absolute)) !== "正文") return null
  const match = path.basename(absolute).match(/^第0*(\d+)章/)
  if (!match) return null
  const chapter = match[1]
  const outlineDir = path.join(path.dirname(path.dirname(absolute)), "大纲")
  let target = null
  try {
    for (const file of fs.readdirSync(outlineDir)) {
      const fileMatch = file.match(/^细纲_第0*(\d+)章.*\.md$/)
      if (!fileMatch || fileMatch[1] !== chapter) continue
      const content = fs.readFileSync(path.join(outlineDir, file), "utf8")
      const targetMatch = content.match(/字数目标[^0-9]{0,6}(\d{3,6})/)
      if (targetMatch) target = Number(targetMatch[1])
      break
    }
  } catch {}
  if (!target) return null
  const actual = Array.from(text).length
  return actual < target * 0.9
    ? `字数：第${chapter}章 实际 ${actual} 字 < 目标 ${target} 的 90%（${Math.floor(target * 0.9)}）。对照细纲字数预算定位欠账的密点、一次性重写到配额，别挤牙膏回炉。`
    : null
}

function duplicateTitleFindings(absolute) {
  const bodyDir = path.dirname(absolute)
  if (path.basename(bodyDir) !== "正文") return []
  const titles = new Map()
  try {
    for (const file of fs.readdirSync(bodyDir)) {
      const match = file.replace(/\.md$/, "").match(/^第0*\d+章[_\- 　]+(.+)$/)
      if (!match) continue
      const title = match[1].trim()
      if (title) titles.set(title, [...(titles.get(title) || []), file])
    }
  } catch {}
  const findings = []
  for (const [title, files] of titles.entries()) {
    if (files.length > 1) findings.push(`${files.length} 章标题重复「${title}」（${files.join("、").slice(0, 60)}），建议改名。`)
  }
  return findings
}

function proseAfterWrite(root, absolute) {
  if (!fs.existsSync(absolute) || !isProsePath(absolute)) return ""
  const findings = []
  try {
    const bytes = fs.statSync(absolute).size
    if (bytes < 200) findings.push(`【落盘】正文仅 ${bytes} 字节，疑似未写完/落盘失败（quota/超时中断？），请核对并补写。`)
    const text = fs.readFileSync(absolute, "utf8")
    findings.push(...proseNetFindings(text, readDeslopWhitelist(root, absolute)))
    const wordcount = wordcountFinding(absolute, text)
    if (wordcount) findings.push(wordcount)
  } catch {
    return ""
  }
  findings.push(...duplicateTitleFindings(absolute))
  if (!findings.length) return ""
  return `=== 正文兜底检测（${safeRelative(root, absolute)}）===\n轻量确定性网自动复扫（模型无关，防主会话漏跑收尾）。按类型处理后复扫到净：\n${findings.join("\n")}`
}

// 线性手写分词，不用带歧义交替的正则：旧式 /"(?:\\.|[^"])*"|'[^']*'|[^\s]+/ 里 \\. 与 [^"] 都能吃
// 反斜杠，而调用方先按 [;&|\n] 拆段会拆开引号内的分隔符、留下一个不闭合的 "，此时每个反斜杠让
// 搜索空间翻倍——`git commit -m "fix: 转义覆盖 \\n \\r … | see README"` 这种 130 字命令实测烧掉
// 27s CPU，超过宿主 hook 的 timeoutMs（zcode 15000ms）被杀。逐字符扫描：引号内原样取字（成对
// 引号剥掉，不闭合就取到段尾），ASCII 空白（空格/Tab/CR/LF）分词——U+3000 不是 shell 分词符，
// 故不切。不解 \ 转义：resolveTarget 把 \ 当路径分隔符（Windows 路径）。
function shellWords(segment) {
  const words = []
  let current = ""
  let started = false
  let quote = ""
  let escaped = false
  for (const ch of String(segment)) {
    if (escaped) {
      current += ch
      escaped = false
      started = true
      continue
    }
    if (ch === "\\" && quote !== "'") {
      current += ch
      escaped = true
      started = true
      continue
    }
    if (quote) {
      if (ch === quote) quote = ""
      else current += ch
      continue
    }
    if (ch === '"' || ch === "'") {
      quote = ch
      started = true
      continue
    }
    if (ch === " " || ch === "\t" || ch === "\r" || ch === "\n") {
      if (started) words.push(current)
      current = ""
      started = false
      continue
    }
    started = true
    current += ch
  }
  if (started) words.push(current)
  return words
}

function shellSegments(command) {
  const segments = []
  let current = ""
  let quote = ""
  let escaped = false
  for (const ch of String(command)) {
    if (escaped) {
      current += ch
      escaped = false
      continue
    }
    if (ch === "\\" && quote !== "'") {
      current += ch
      escaped = true
      continue
    }
    if (quote) {
      current += ch
      if (ch === quote) quote = ""
      continue
    }
    if (ch === '"' || ch === "'") {
      quote = ch
      current += ch
      continue
    }
    if (ch === ";" || ch === "&" || ch === "|" || ch === "\n") {
      if (current) segments.push(current)
      current = ""
      continue
    }
    current += ch
  }
  if (current) segments.push(current)
  return segments
}

function beforeShellRedirection(segment) {
  let current = ""
  let quote = ""
  let escaped = false
  for (const ch of String(segment)) {
    if (escaped) {
      current += ch
      escaped = false
      continue
    }
    if (ch === "\\" && quote !== "'") {
      current += ch
      escaped = true
      continue
    }
    if (quote) {
      current += ch
      if (ch === quote) quote = ""
      continue
    }
    if (ch === '"' || ch === "'") {
      quote = ch
      current += ch
      continue
    }
    if (ch === "<" || ch === ">") {
      return current.replace(/\d+$/, "")
    }
    current += ch
  }
  return current
}

function isGitCommitCommand(command) {
  const valueOptions = new Set(["-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--super-prefix", "--config-env"])
  // Flatten subshell/brace grouping to spaces so `(git commit)` / `{ git commit; }` still expose
  // the git verb; split on separators; skip leading shell wrappers and control words
  // (then/do/else/elif) so a commit inside if/for/while is detected. Mirrors the Claude bash
  // oracle validate-story-commit.sh and codex is_git_commit_command.
  for (const rawSegment of String(command).replace(/\r/g, "").replace(/[(){}]/g, " ").split(/[;&|\n]+/)) {
    const words = shellWords(rawSegment)
    let i = 0
    while (i < words.length && (/^[A-Za-z_][A-Za-z0-9_]*=/.test(words[i]) || ["command", "noglob", "then", "do", "else", "elif"].includes(words[i]))) i++
    if (words[i] === "env") {
      i++
      while (i < words.length && (/^[A-Za-z_][A-Za-z0-9_]*=/.test(words[i]) || ["-i", "--ignore-environment"].includes(words[i]))) i++
    }
    if (words[i] !== "git") continue
    i++
    while (i < words.length) {
      const token = words[i]
      if (token === "commit") return true
      if (valueOptions.has(token)) { i += 2; continue }
      if ([...valueOptions].some((option) => option.startsWith("--") && token.startsWith(`${option}=`))) { i++; continue }
      if (token.startsWith("-")) { i++; continue }
      break
    }
  }
  return false
}

// 设定/ 直属的项目级设定件：artifact-protocols.md 规定的 关系.md（正文是「# 角色关系图」）、
// 题材定位.md，以及 文风.md、题材正文提示卡.md 等，它们本来就没有 名字/姓名 字段。
const SETTING_NON_CHARACTER_FILES = new Set(["关系.md", "题材定位.md", "题材正文提示卡.md", "文风.md", "世界规则.md", "世界观.md", "金手指.md", "背景设定.md"])

// 只查角色卡：整棵 设定/ 一刀切会让每次碰设定的提交都刷一屏假警告，把同框的
// 「正文硬编码角色属性」真警告埋掉。判定口径与 validate-story-commit.sh / opencode
// pre-commit.sh 的 case 分支一一对齐（bash↔js↔py 四端同口径，别单边改回一刀切）：
// ① 设定/角色|人物 子目录内的文件 → 角色卡；
// ② 其余 设定/<子目录>/ → 整目录跳过（世界观/势力/报告/原理/人物关系 等）；
// ③ 设定/ 直属的扁平文件 → 除已知项目级设定件外都算角色卡（主角.md/配角.md/反派.md 等自定义命名）。
// bash 的 `*` 跨 `/` 匹配，`设定/角色/*|*/设定/角色/*` 等价于「路径里存在某个 设定 目录段满足该
// 分支」，所以两趟扫描（先全路径找分支①，再全路径找分支②）而不是只看第一个 设定 段就定分支——
// 后者在 设定/其他/设定/角色/x.md 这类嵌套路径上会与 bash 判定分叉。
function isCharacterSheetPath(relative) {
  const segments = relative.split("/")
  const last = segments.length - 1
  // 分支①：某个 设定 段紧跟 角色/人物，且其下还有文件段
  for (let i = 0; i + 1 < last; i++) {
    if (segments[i] === "设定" && (segments[i + 1] === "角色" || segments[i + 1] === "人物")) return true
  }
  // 分支②：某个 设定 段后还有 ≥2 段，即落在非角色子目录里
  for (let i = 0; i + 1 < last; i++) {
    if (segments[i] === "设定") return false
  }
  // 分支③：设定 直属扁平文件（分支②已排掉更深的路径，设定 段只能是倒数第二段）
  return last >= 1 && segments[last - 1] === "设定" && !SETTING_NON_CHARACTER_FILES.has(segments[last])
}

function stagedMarkdownWarnings(root) {
  let output
  try {
    output = spawnSync("git", ["-C", root, "-c", "core.quotepath=false", "diff", "--cached", "--relative", "--name-only", "--diff-filter=ACM", "-z", "--", "."], {
      encoding: "buffer",
      stdio: ["ignore", "pipe", "ignore"],
    })
    if (output.status !== 0 || !output.stdout) return ""
  } catch {
    return ""
  }
  const warnings = []
  for (const relative of output.stdout.toString("utf8").split("\0").filter(Boolean)) {
    if (!relative.endsWith(".md")) continue
    const full = path.join(root, relative)
    let text = ""
    try { text = fs.readFileSync(full, "utf8") } catch { continue }
    if (relative === "正文.md" || relative.includes("/正文.md") || relative.startsWith("正文/") || relative.includes("/正文/")) {
      const hits = []
      text.split(/\r?\n/).forEach((line, index) => {
        if (/(身高|体重|年龄)[\s　]*(：|:)[\s　]*[0-9]+/.test(line)) hits.push(`${index + 1}:${line}`)
      })
      if (hits.length) warnings.push(`⚠ ${relative}: 正文硬编码角色属性，应引用设定文件：\n${hits.join("\n")}`)
    }
    if (isCharacterSheetPath(relative) && !/^[\s　]*(名字|姓名|名称|name)[\s　]*(：|:)/im.test(text)) {
      warnings.push(`⚠ ${relative}: 设定文件缺少 name/名字 必填字段。`)
    }
  }
  return warnings.length ? `=== Story Commit Warnings（advisory only）===\n${warnings.join("\n")}\n=== End Warnings ===` : ""
}

module.exports = {
  existingDir,
  safeRelative,
  resolveTarget,
  firstLine,
  isHistoricalCopySegment,
  findFirst,
  discoverActiveBook,
  discoverAllBooks,
  trackingCheckpointIssue,
  continuityFindings,
  extractProseTargets,
  extractPatchTargets,
  revisionSourceInfo,
  revisionBlockReason,
  proseBlockReason,
  isProsePath,
  wordcountFinding,
  duplicateTitleFindings,
  proseAfterWrite,
  shellWords,
  isGitCommitCommand,
  stagedMarkdownWarnings,
  TERMINAL,
  QUOTE_OPENERS,
  SOFT_PATTERNS,
  HARD_PATTERNS,
  skippableLine,
  proseNetFindings,
  parseDeslopWhitelist,
  readDeslopWhitelist,
  languageLeakRecords,
  languageLeakFindings,
  maskQuotedSpans,
  toxicPhraseFindings,
}
