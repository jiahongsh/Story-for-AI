from pathlib import Path
import json
import subprocess
import hashlib

book = Path(__file__).resolve().parents[2]
work = Path(__file__).resolve().parent
scripts = book.parent / "skills/story-long-write/scripts"
groups = [work / "候选_001-016", work / "候选_017-033/全文", work / "候选_034-050", work / "候选_096-099"]
checks = [
    ("language_gate.js", []),
    ("check-style-hygiene.js", ["--check", "--fail-on=blocking"]),
    ("check-ai-patterns.js", ["--check", "--fail-on=blocking"]),
    ("check-degeneration.js", ["--check", "--language=zh", "--fail-on=blocking"]),
]

results = {}
for group in groups:
    if not group.is_dir():
        continue
    for candidate in sorted(group.glob("第*.md")):
        if "细纲" in candidate.name:
            continue
        original = book / "正文" / candidate.name
        if not original.is_file() or original.read_bytes() == candidate.read_bytes():
            continue
        passes = []
        failures = []
        for script, flags in checks:
            run = subprocess.run(
                ["node", str(scripts / script), *flags, str(candidate)],
                capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            if run.returncode:
                detail = run.stdout + run.stderr
                try:
                    obj = json.loads(detail)
                    findings = obj.get("findings", [])
                    detail = "; ".join(f"{f.get('line')}: {f.get('type')}: {f.get('excerpt')}" for f in findings if f.get("severity") == "blocking") or detail[:900]
                except json.JSONDecodeError:
                    detail = detail[:900]
                failures.append({"gate": script, "detail": detail})
            else:
                passes.append(script)
        results[candidate.name] = {"candidate": candidate.relative_to(book).as_posix(), "sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(), "passed": passes, "failures": failures}

(work / "候选四门汇总.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"changed": len(results), "pass": sum(not v["failures"] for v in results.values()), "failed": {k: v["failures"] for k, v in results.items() if v["failures"]}}, ensure_ascii=False))
