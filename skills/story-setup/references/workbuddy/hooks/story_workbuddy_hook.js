#!/usr/bin/env node
"use strict"

// oh-story WorkBuddy / CodeBuddy hook adapter for writing projects. It has
// no third-party dependencies and emits only fields accepted by CodeBuddy's
// hook output schema. Diagnostics go to stderr; healthy no-op keeps stdout empty.

const fs = require("node:fs")
const path = require("node:path")
const { spawnSync } = require("node:child_process")
const core = require("./story_hook_core.js")
const {
  existingDir,
  safeRelative,
  resolveTarget,
  firstLine,
  findFirst,
  discoverActiveBook,
  discoverAllBooks,
  continuityFindings,
  extractProseTargets,
  extractPatchTargets,
  revisionBlockReason,
  proseBlockReason,
  isProsePath,
  wordcountFinding,
  duplicateTitleFindings,
  proseAfterWrite,
  shellWords,
  isGitCommitCommand,
  stagedMarkdownWarnings,
  skippableLine,
  proseNetFindings,
} = core

let hookInput = {}
let hookInputError = null
try {
  const raw = fs.readFileSync(0, "utf8")
  if (raw.trim()) {
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error("hook input root must be a JSON object")
    }
    hookInput = parsed
  }
} catch (error) {
  hookInput = {}
  hookInputError = error instanceof Error ? error : new Error(String(error))
}

function emit(value) {
  if (value && typeof value === "object") {
    process.stdout.write(JSON.stringify({ continue: true, ...value }))
  }
}

function hookContext(event, text) {
  return {
    hookSpecificOutput: {
      hookEventName: event,
      additionalContext: text,
    },
  }
}

function deployedWorkspaceRoot() {
  try {
    const hooksDir = __dirname
    if (path.basename(hooksDir) === "hooks" && path.basename(path.dirname(hooksDir)) === ".codebuddy") {
      return path.dirname(path.dirname(hooksDir))
    }
  } catch {}
  return null
}

function projectRoot() {
  for (const name of ["CODEBUDDY_PROJECT_DIR", "CLAUDE_PROJECT_DIR"]) {
    const candidate = existingDir(process.env[name])
    if (candidate) return candidate
  }
  const deployed = deployedWorkspaceRoot()
  if (deployed) return deployed
  const inputCwd = existingDir(hookInput.cwd)
  const cwd = inputCwd || process.cwd()
  try {
    const result = spawnSync("git", ["rev-parse", "--show-toplevel"], {
      cwd,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    })
    if (result.status === 0 && result.stdout.trim()) return path.resolve(result.stdout.trim())
  } catch {}
  return path.resolve(cwd)
}

function runtimeTargetEnabled(root, targetName) {
  // Plugin runners live under the plugin package rather than the project's
  // .codebuddy/hooks directory, so a project sentinel must not disable them.
  if (!deployedWorkspaceRoot()) return true
  const sentinel = path.join(root, ".story-deployed")
  if (!fs.existsSync(sentinel)) return true
  let text = ""
  try { text = fs.readFileSync(sentinel, "utf8") } catch { return true }
  const match = text.match(/^target_cli:\s*(.+)$/m)
  if (!match) return true
  return match[1].split(",").map((item) => item.trim()).includes(targetName)
}

const WORKBUDDY_AGENTS_VERSION = 39

function workbuddyAgentsVersionFindings(sentinelText) {
  const match = String(sentinelText || "").match(/^agents_version:\s*(.*?)\s*$/m)
  if (!match || !/^[0-9]+$/.test(match[1])) {
    return [`[story-setup] .story-deployed 的 agents_version 缺失或无效；当前 WorkBuddy 适配要求版本 ${WORKBUDDY_AGENTS_VERSION}，请重新运行 /story-setup。`]
  }
  const deployed = Number(match[1])
  if (deployed < WORKBUDDY_AGENTS_VERSION) {
    return [`[story-setup] WorkBuddy Agents 版本 ${deployed} 低于当前要求的 ${WORKBUDDY_AGENTS_VERSION}；请重新运行 /story-setup 升级。`]
  }
  if (deployed > WORKBUDDY_AGENTS_VERSION) {
    return [`[story-setup] WorkBuddy Agents 版本 ${deployed} 高于当前适配器支持的 ${WORKBUDDY_AGENTS_VERSION}；请先更新 oh-story / WorkBuddy 适配器，勿用旧适配器降级覆盖。`]
  }
  return []
}

function sessionStart() {
  const root = projectRoot()
  const messages = []
  const sentinel = path.join(root, ".story-deployed")
  if (deployedWorkspaceRoot() && fs.existsSync(sentinel)) {
    let text = ""
    try { text = fs.readFileSync(sentinel, "utf8") } catch {}
    messages.push(...workbuddyAgentsVersionFindings(text))
    const match = text.match(/^target_cli:\s*(.+)$/m)
    if (!match) {
      messages.push("[story-setup] .story-deployed 缺少 target_cli；建议重新运行 /story-setup。")
    } else if (!match[1].split(",").map((item) => item.trim()).includes("workbuddy")) {
      messages.push("[story-setup] 当前部署标记未包含 workbuddy；如需 WorkBuddy / CodeBuddy Code 项目适配，请重新运行 /story-setup 并选择 WorkBuddy / CodeBuddy Code。")
    }
  }
  const book = discoverActiveBook(root)
  if (book) {
    const context = path.join(book, "追踪", "上下文.md")
    if (fs.existsSync(context)) {
      messages.push(`[story context] 当前书目：${safeRelative(root, book)}。继续长篇写作前先读取 ${safeRelative(root, context)}。`)
    } else {
      messages.push(`[story context] 检测到写作项目：${safeRelative(root, book)}。`)
    }
  }
  messages.push(...continuityFindings(root))
  if (messages.length) emit(hookContext("SessionStart", messages.join("\n")))
}

function toolName(input) {
  return String(input.tool_name || input.toolName || input.tool || input.name || "")
}

function toolPayload(input) {
  for (const key of ["tool_input", "toolInput", "input", "parameters", "args"]) {
    const value = input[key]
    if (value && typeof value === "object" && !Array.isArray(value)) return value
  }
  return {}
}

function isPathInside(root, candidate, pathApi = path) {
  const relation = pathApi.relative(root, candidate)
  return relation === "" || (
    !pathApi.isAbsolute(relation)
    && relation !== ".."
    && !relation.startsWith(`..${pathApi.sep}`)
  )
}

// TRAE exposes shell execution as one standardized RunCommand tool on every OS.
// Parse the statically knowable PowerShell write forms in addition to the shared
// POSIX parser. Deliberately do not try to evaluate variables, splatting, call
// operators, script blocks or .NET APIs: those remain Skill self-check + explicit
// manual rescan territory rather than a misleading hard guarantee.
function unifiedPowerShellSegments(command) {
  const segments = []
  let current = ""
  let quote = ""
  let escaped = false
  for (const ch of String(command || "")) {
    if (escaped) {
      current += ch
      escaped = false
      continue
    }
    if (ch === "`") {
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
    if (ch === ";" || ch === "|" || ch === "&" || ch === "\n") {
      if (current.trim()) segments.push(current)
      current = ""
      continue
    }
    current += ch
  }
  if (current.trim()) segments.push(current)
  return segments
}

function unifiedPowerShellNamedValue(args, names) {
  const wanted = new Set(names.map((name) => name.toLowerCase()))
  for (let index = 0; index < args.length; index++) {
    const token = String(args[index])
    const colon = token.match(/^-([^:=]+)[:=](.*)$/)
    if (colon && wanted.has(colon[1].toLowerCase()) && colon[2]) return colon[2]
    const plain = token.match(/^-([^:=]+)$/)
    if (plain && wanted.has(plain[1].toLowerCase())) return args[index + 1] || ""
  }
  return ""
}

function unifiedPowerShellPositionals(args, valueOptions) {
  const options = new Set(valueOptions.map((name) => name.toLowerCase()))
  const positionals = []
  for (let index = 0; index < args.length; index++) {
    const token = String(args[index])
    if (token === "--%") {
      positionals.push(...args.slice(index + 1))
      break
    }
    const option = token.match(/^-([^:=]+)(?:[:=](.*))?$/)
    if (!option) {
      positionals.push(token)
      continue
    }
    if (options.has(option[1].toLowerCase()) && option[2] === undefined) index++
  }
  return positionals
}

function unifiedPowerShellBasename(value) {
  const parts = String(value || "").replace(/\\/g, "/").split("/")
  return parts[parts.length - 1]
}

function unifiedPowerShellJoin(directory, name) {
  return `${String(directory || "").replace(/[\\/]+$/, "")}/${name}`
}

function unifiedExistingDirectory(root, base, destination) {
  if (!root || !base || !destination) return false
  try {
    const candidate = resolveTarget(root, destination, base)
    const stat = fs.lstatSync(candidate)
    if (!stat.isDirectory() || stat.isSymbolicLink()) return false
    return isPathInside(fs.realpathSync(root), fs.realpathSync(candidate))
  } catch {
    return false
  }
}

function unifiedPowerShellDestination(destination, source, context = {}) {
  const normalized = String(destination || "").replace(/\\/g, "/")
  const basename = normalized.split("/").pop().toLowerCase()
  const isDirectory = normalized.endsWith("/")
    || basename === "正文"
    || unifiedExistingDirectory(context.root, context.base, destination)
  return isDirectory
    ? unifiedPowerShellJoin(destination, unifiedPowerShellBasename(source))
    : destination
}

function isStaticUnifiedPowerShellPath(value) {
  const text = String(value || "").trim()
  return Boolean(text)
    && !text.includes("$")
    && !text.includes("`")
    && !text.startsWith("@")
    && !/[?*]/.test(text)
    && !/[(){}]/.test(text)
}

function isUnifiedPowerShellManagedTarget(value) {
  const text = String(value || "")
  return /(^|[\\/])正文\.md$/i.test(text)
    || /(^|[\\/])(正文|大纲|设定)([\\/]|$)/.test(text)
}

function unifiedPowerShellWhatIf(args) {
  for (const raw of args) {
    const match = String(raw).match(/^-whatif(?::(.*))?$/i)
    if (!match) continue
    if (match[1] === undefined || /^(?:\$?true|1)$/i.test(match[1])) return true
  }
  return false
}

function extractUnifiedPowerShellTargets(command, context = {}) {
  const targets = []
  const commonValueOptions = [
    "erroraction", "errorvariable", "informationaction", "informationvariable",
    "outbuffer", "outvariable", "pipelinevariable", "progressaction",
    "warningaction", "warningvariable",
  ]
  const contentOptions = ["path", "literalpath", "value", "encoding", "filter", "include", "exclude", "stream", ...commonValueOptions]
  const fileOptions = ["filepath", "inputobject", "encoding", "width", ...commonValueOptions]
  const itemOptions = ["path", "literalpath", "destination", "filter", "include", "exclude", "name", "value", "itemtype", ...commonValueOptions]
  const aliases = new Map([
    ["sc", "set-content"], ["ac", "add-content"], ["clc", "clear-content"],
    ["ni", "new-item"], ["cp", "copy-item"], ["cpi", "copy-item"],
    ["mv", "move-item"], ["mi", "move-item"], ["ren", "rename-item"],
    ["rni", "rename-item"], ["tee", "tee-object"],
  ])
  for (const segment of unifiedPowerShellSegments(command)) {
    const words = shellWords(segment.trim())
    if (!words.length) continue
    const rawCommandName = unifiedPowerShellBasename(words[0]).replace(/\.exe$/i, "").toLowerCase()
    const commandName = aliases.get(rawCommandName) || rawCommandName
    const args = words.slice(1)
    if (unifiedPowerShellWhatIf(args)) continue
    let target = ""
    if (["set-content", "add-content", "clear-content"].includes(commandName)) {
      target = unifiedPowerShellNamedValue(args, ["path", "literalpath"])
        || unifiedPowerShellPositionals(args, contentOptions)[0]
    } else if (["out-file", "tee-object"].includes(commandName)) {
      target = unifiedPowerShellNamedValue(args, ["filepath", "literalpath"])
        || unifiedPowerShellPositionals(args, fileOptions)[0]
    } else if (commandName === "new-item") {
      const base = unifiedPowerShellNamedValue(args, ["path", "literalpath"])
        || unifiedPowerShellPositionals(args, itemOptions)[0]
      const name = unifiedPowerShellNamedValue(args, ["name"])
      target = name && base && !/\.md$/i.test(base) ? unifiedPowerShellJoin(base, name) : base
    } else if (["copy-item", "move-item"].includes(commandName)) {
      const positionals = unifiedPowerShellPositionals(args, itemOptions)
      const namedSource = unifiedPowerShellNamedValue(args, ["path", "literalpath"])
      const source = namedSource || positionals[0] || ""
      const destination = unifiedPowerShellNamedValue(args, ["destination"])
        || (namedSource && positionals.length
          ? positionals[positionals.length - 1]
          : (positionals.length > 1 ? positionals[positionals.length - 1] : ""))
      target = unifiedPowerShellDestination(destination, source, context)
    } else if (commandName === "rename-item") {
      const positionals = unifiedPowerShellPositionals(args, itemOptions)
      const namedSource = unifiedPowerShellNamedValue(args, ["path", "literalpath"])
      const source = namedSource || positionals[0] || ""
      const destination = unifiedPowerShellNamedValue(args, ["newname"])
        || (namedSource && positionals.length
          ? positionals[positionals.length - 1]
          : (positionals.length > 1 ? positionals[positionals.length - 1] : ""))
      const normalizedDestination = String(destination).replace(/\\/g, "/")
      const normalizedSource = String(source).replace(/\\/g, "/")
      target = destination && !normalizedDestination.includes("/")
        ? unifiedPowerShellJoin(normalizedSource.split("/").slice(0, -1).join("/"), destination)
        : destination
    }
    if (isStaticUnifiedPowerShellPath(target) && isUnifiedPowerShellManagedTarget(target)) targets.push(target)
  }
  return [...new Set(targets)]
}

function powerShellSegments(command) {
  const segments = []
  let current = ""
  let quote = ""
  let escaped = false
  for (const ch of String(command || "")) {
    if (escaped) {
      current += ch
      escaped = false
      continue
    }
    if (ch === "`") {
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
    if (ch === ";" || ch === "|" || ch === "\n") {
      if (current.trim()) segments.push(current)
      current = ""
      continue
    }
    current += ch
  }
  if (current.trim()) segments.push(current)
  return segments
}

function powerShellNamedValue(args, names) {
  const wanted = new Set(names.map((name) => name.toLowerCase()))
  for (let index = 0; index < args.length; index++) {
    const token = String(args[index])
    const colon = token.match(/^-([^:=]+)[:=](.*)$/)
    if (colon && wanted.has(colon[1].toLowerCase()) && colon[2]) return colon[2]
    const plain = token.match(/^-([^:=]+)$/)
    if (plain && wanted.has(plain[1].toLowerCase())) return args[index + 1] || ""
  }
  return ""
}

function powerShellPositionals(args, valueOptions) {
  const options = new Set(valueOptions.map((name) => name.toLowerCase()))
  const positionals = []
  for (let index = 0; index < args.length; index++) {
    const token = String(args[index])
    if (token === "--%") {
      positionals.push(...args.slice(index + 1))
      break
    }
    const option = token.match(/^-([^:=]+)(?:[:=](.*))?$/)
    if (!option) {
      positionals.push(token)
      continue
    }
    if (options.has(option[1].toLowerCase()) && option[2] === undefined) index++
  }
  return positionals
}

function powerShellBasename(value) {
  const parts = String(value || "").replace(/\\/g, "/").split("/")
  return parts[parts.length - 1]
}

function powerShellJoin(directory, name) {
  return `${String(directory || "").replace(/[\\/]+$/, "")}/${name}`
}

function powerShellDestination(destination, source) {
  const normalized = String(destination || "").replace(/\\/g, "/")
  return normalized.endsWith("/") || normalized.split("/").pop() === "正文"
    ? powerShellJoin(destination, powerShellBasename(source))
    : destination
}

function isPowerShellStoryTarget(value) {
  return /(^|[\\/])(正文|大纲|设定)([\\/]|$)/.test(String(value || ""))
}

function extractPowerShellTargets(command) {
  const targets = [...extractProseTargets(command)]
  const contentOptions = ["path", "literalpath", "value", "encoding", "filter", "include", "exclude", "stream"]
  const fileOptions = ["filepath", "inputobject", "encoding", "width"]
  const itemOptions = ["path", "literalpath", "destination", "filter", "include", "exclude", "name", "value", "itemtype"]
  const aliases = new Map([
    ["sc", "set-content"], ["ac", "add-content"], ["clc", "clear-content"],
    ["ni", "new-item"], ["cp", "copy-item"], ["cpi", "copy-item"],
    ["mv", "move-item"], ["mi", "move-item"], ["ren", "rename-item"],
    ["rni", "rename-item"], ["tee", "tee-object"],
  ])
  for (const segment of powerShellSegments(command)) {
    const words = shellWords(segment.trim())
    if (!words.length) continue
    const rawCommandName = powerShellBasename(words[0]).replace(/\.exe$/i, "").toLowerCase()
    const commandName = aliases.get(rawCommandName) || rawCommandName
    const args = words.slice(1)
    let target = ""
    if (["set-content", "add-content", "clear-content"].includes(commandName)) {
      target = powerShellNamedValue(args, ["path", "literalpath"])
        || powerShellPositionals(args, contentOptions)[0]
    } else if (["out-file", "tee-object"].includes(commandName)) {
      target = powerShellNamedValue(args, ["filepath", "literalpath"])
        || powerShellPositionals(args, fileOptions)[0]
    } else if (commandName === "new-item") {
      const base = powerShellNamedValue(args, ["path", "literalpath"])
        || powerShellPositionals(args, itemOptions)[0]
      const name = powerShellNamedValue(args, ["name"])
      target = name && base && !/\.md$/i.test(base) ? powerShellJoin(base, name) : base
    } else if (["copy-item", "move-item"].includes(commandName)) {
      const positionals = powerShellPositionals(args, itemOptions)
      const namedSource = powerShellNamedValue(args, ["path", "literalpath"])
      const source = namedSource || positionals[0] || ""
      const destination = powerShellNamedValue(args, ["destination"])
        || (namedSource && positionals.length
          ? positionals[positionals.length - 1]
          : (positionals.length > 1 ? positionals[positionals.length - 1] : ""))
      target = powerShellDestination(destination, source)
    } else if (commandName === "rename-item") {
      const positionals = powerShellPositionals(args, itemOptions)
      const namedSource = powerShellNamedValue(args, ["path", "literalpath"])
      const source = namedSource || positionals[0] || ""
      const destination = powerShellNamedValue(args, ["newname"])
        || (namedSource && positionals.length
          ? positionals[positionals.length - 1]
          : (positionals.length > 1 ? positionals[positionals.length - 1] : ""))
      const normalizedDestination = String(destination).replace(/\\/g, "/")
      const normalizedSource = String(source).replace(/\\/g, "/")
      target = destination && !normalizedDestination.includes("/")
        ? powerShellJoin(normalizedSource.split("/").slice(0, -1).join("/"), destination)
        : destination
    }
    if (target && isPowerShellStoryTarget(target)) targets.push(target)
  }
  return [...new Set(targets.filter(Boolean))]
}

function targetPaths(input) {
  const root = projectRoot()
  const inputCwd = existingDir(input.cwd)
  const base = inputCwd && isPathInside(root, inputCwd) ? inputCwd : root
  const name = toolName(input)
  const payload = toolPayload(input)
  const rawTargets = []
  for (const key of ["file_path", "filePath", "path", "target", "filename"]) {
    if (typeof payload[key] === "string") rawTargets.push(payload[key])
  }
  const command = typeof payload.command === "string" ? payload.command : ""
  if (command) {
    if (/powershell/i.test(name)) rawTargets.push(...extractPowerShellTargets(command))
    else if (/bash/i.test(name)) rawTargets.push(...extractProseTargets(command))
    else rawTargets.push(...extractPatchTargets(command), ...extractProseTargets(command))
  }
  if (command && String(name).toLowerCase() === "runcommand") {
    rawTargets.push(...extractUnifiedPowerShellTargets(command, { root, base }))
  }
  for (const key of ["patch", "content", "text"]) {
    if (typeof payload[key] === "string" && /applypatch|patch/i.test(name)) rawTargets.push(...extractPatchTargets(payload[key]))
  }
  return [...new Set(rawTargets.filter(Boolean).map((value) => resolveTarget(root, value, base)))]
}

function preToolProseGuard() {
  const root = projectRoot()
  const targets = targetPaths(hookInput)
  for (const target of targets) {
    const reason = revisionBlockReason(root, target) || proseBlockReason(root, target)
    if (reason) {
      emit({
        hookSpecificOutput: {
          hookEventName: "PreToolUse",
          permissionDecision: "deny",
          permissionDecisionReason: reason,
        },
      })
      return
    }
  }
}

function preToolCommitAdvisory() {
  const payload = toolPayload(hookInput)
  const command = typeof payload.command === "string" ? payload.command : ""
  if (!command || !isGitCommitCommand(command)) return
  const warnings = stagedMarkdownWarnings(projectRoot())
  if (warnings) emit({ systemMessage: warnings })
}

function postToolProseCheck() {
  const root = projectRoot()
  const notes = targetPaths(hookInput).map((target) => proseAfterWrite(root, target)).filter(Boolean)
  if (notes.length) emit(hookContext("PostToolUse", notes.join("\n\n")))
}

function main(event = process.argv[2] || "") {
  try {
    if (hookInputError && event === "pre-tool-prose-guard") throw hookInputError
    if (!runtimeTargetEnabled(projectRoot(), "workbuddy")) return
    if (event === "session-start") sessionStart()
    else if (event === "pre-tool-prose-guard") preToolProseGuard()
    else if (event === "pre-tool-commit-advisory") preToolCommitAdvisory()
    else if (event === "post-tool-prose-check") postToolProseCheck()
    else {
      process.stderr.write(`unknown oh-story WorkBuddy hook event: ${event}\n`)
      process.exitCode = 2
    }
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error)
    process.stderr.write(`[oh-story workbuddy hook] ${detail}\n`)
    if (event === "pre-tool-prose-guard") {
      emit({
        hookSpecificOutput: {
          hookEventName: "PreToolUse",
          permissionDecision: "deny",
          permissionDecisionReason: "oh-story WorkBuddy PreToolUse 机械门意外失败；为避免受保护写入绕过，已按 fail-closed 拒绝。请检查 hook stderr 并重新运行 story-setup。",
        },
      })
    }
  }
}

if (require.main === module) main()

module.exports = {
  continuityFindings,
  proseNetFindings,
  extractProseTargets,
  extractPatchTargets,
  isGitCommitCommand,
  isPathInside,
  runtimeTargetEnabled,
  workbuddyAgentsVersionFindings,
  extractPowerShellTargets,
  main,
}

module.exports.extractUnifiedPowerShellTargets = extractUnifiedPowerShellTargets
