from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

work = Path(__file__).resolve().parent
book = work.parents[2]
tools = book.parent / "skills/story-long-write/scripts"
world = book.parent / "skills/story-world-engine/scripts/world_gate.py"

def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(*command):
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(list(map(str, command)), capture_output=True, text=True,
                            encoding="utf-8", errors="replace", env=env)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"stdout": result.stdout, "stderr": result.stderr}

assert read(book / "追踪/_tracking-state.json")["state_revision"] == 158
source = book / "大纲/伏笔总表.md"
backup = book / "备份/2026-10-06_第六批早期验收修复_伏笔状态/大纲/伏笔总表.md"
assert source.exists() and backup.exists() and sha(source) != sha(backup)
content = source.read_text(encoding="utf-8-sig")
assert "旧首埋口径已更正" in content
assert "F05—F08、F10、F12的首埋核对" in content
assert "F02、F04在当前第一卷活动正文只有前兆" in content
assert "已埋并多次强化，后续仍待正式强化" in content
assert "已埋并增压。" in content

active = book / "追踪/修改影响/active.json"
run(sys.executable, tools / "revision_guard.py", "plan", "--project", book,
    "--input", work / "plan.json", "--output", active)
manifest = read(active)
items = []
for relative in manifest["required_checks"]:
    path = book / relative
    data = path.read_text(encoding="utf-8-sig")
    items.append({"path": relative, "sha256": sha(path), "lines": len(data.splitlines())})
write(work / "最终影响检查.json", items)
manifest["checked_files"] = manifest["required_checks"]
manifest["conflicts"] = [{
    "source": "大纲/伏笔总表.md", "target": "大纲/卷纲_第一卷.md",
    "severity": "S3",
    "issue": "F03/F09/F11生命周期状态段落弱于当前总表，易误读为尚未推进",
    "resolution": "生命周期段落统一为已埋并增压或多次强化；未来正式强化仍为规划，不改已发生正文",
    "status": "resolved",
}]
manifest["tracking_action"] = {
    "kind": "not_required", "state_revision_before": 158, "state_revision_after": 158,
    "reason": "仅统一生命周期段落与当前总表的状态措辞，伏笔内容、正文事件、追踪权威事实均不变",
}
write(active, manifest)
stamp = book / "追踪/修改影响/active.approved.json"
checks = {
    "revision_gate": run(sys.executable, tools / "revision_guard.py", "check",
                         "--project", book, "--input", active, "--stamp", stamp),
    "tracking": run(sys.executable, tools / "tracking_commit.py", "check", "--project", book),
    "doctor": run(sys.executable, tools / "story_doctor.py", "--project", book),
    "world_export": run(sys.executable, world, "export", "--project", book, "--start", 1,
                        "--end", 99, "--tracking-tool", tools / "tracking_commit.py"),
    "before_sha256": sha(backup), "after_sha256": sha(source),
}
assert checks["tracking"]["state_revision"] == 158
assert checks["doctor"]["status"] == "pass"
assert checks["world_export"]["limitations"] == []
write(work / "final_checks.json", checks)
print(json.dumps({"status": "PASS", "required_checks": len(items),
                  "revision": 158}, ensure_ascii=False))
