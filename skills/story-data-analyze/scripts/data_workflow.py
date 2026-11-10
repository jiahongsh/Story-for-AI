#!/usr/bin/env python3
"""Transactional, evidence-chained workflow for story data analysis.

Every reasoning hand-off is an immutable ``*.attempt-NN.json`` artifact.  The
single mutable file is ``manifest.json``; it is updated atomically under a file
lock and guarded by an explicit ``expected_revision``.  No command in this
module edits novel prose.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import datetime as dt
import fcntl
import hashlib
import json
import math
import os
import pathlib
import re
import sys
import tempfile
from zoneinfo import ZoneInfo
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple


SCRIPT = pathlib.Path(__file__).resolve()
PROJECT_ROOT = SCRIPT.parents[3]
DEFAULT_RUNS_ROOT = PROJECT_ROOT / "数据追踪" / "analysis-runs"
DEFAULT_KNOWLEDGE_ROOT = PROJECT_ROOT / "数据追踪" / "knowledge" / "cases"
DEFAULT_METHOD_KNOWLEDGE_ROOT = PROJECT_ROOT / "数据追踪" / "knowledge" / "methods"
FIXED_MAX_RETURNS = 3

STATES: Tuple[str, ...] = (
    "INIT",
    "RAW_CAPTURED",
    "DATA_QUALIFIED",
    "WINDOW_BOUND",
    "METRICS_READY",
    "ANALYZED",
    "ANALYSIS_VERIFIED",
    "TEXT_DIAGNOSED",
    "SUPERVISED",
    "REPORT_COMPLETE",
)
TERMINAL_STATES = {"REPORT_COMPLETE", "BLOCKED"}

KIND_FLOW: Dict[str, Tuple[str, str, str]] = {
    "raw_capture": ("INIT", "RAW_CAPTURED", "01"),
    "data_quality": ("RAW_CAPTURED", "DATA_QUALIFIED", "02"),
    "window_bound": ("DATA_QUALIFIED", "WINDOW_BOUND", "03"),
    "metrics": ("WINDOW_BOUND", "METRICS_READY", "04"),
    "analysis": ("METRICS_READY", "ANALYZED", "05"),
    "validation": ("ANALYZED", "ANALYSIS_VERIFIED", "06"),
    "text_diagnosis": ("ANALYSIS_VERIFIED", "TEXT_DIAGNOSED", "07"),
    "supervision": ("TEXT_DIAGNOSED", "SUPERVISED", "08"),
}

FATAL_QUALITY = {"LOGIN_INVALID", "PLATFORM_NOT_UPDATED", "SCOPE_UNKNOWN", "CORRUPT"}
QUALITY_STATUSES = {"OK", "PARTIAL", *FATAL_QUALITY}
INSUFFICIENT_STATUSES = {"样本不足", "SAMPLE_INSUFFICIENT"}
ANALYSIS_STATUSES = {
    "改善", "恶化", "无明显变化", "样本不足", "数据未覆盖改动", "样本受自访污染",
    "IMPROVED", "DEGRADED", "NO_CLEAR_CHANGE", "SAMPLE_INSUFFICIENT",
    "CHANGE_NOT_COVERED", "SELF_VISIT_CONTAMINATED",
}
RETURNABLE_STATES = set(STATES[:-2])
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
CASE_ID_RE = RUN_ID_RE
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_PRODUCERS = {
    "raw_capture": "story-data-fetcher",
    "data_quality": "story-data-normalizer",
    "window_bound": "story-data-orchestrator",
    "metrics": "story-data-metric-engine",
    "analysis": "story-data-metrics-analyst",
    "validation": "story-data-method-validator",
    "text_diagnosis": "story-data-text-improvement-planner",
    "supervision": "story-data-supervisor",
    "report": "story-data-supervisor",
    "case_promotion": "story-data-supervisor",
    "method_promotion": "story-data-supervisor",
    "authorization": "story-data-orchestrator",
}
REQUIRED_SUPERVISION_GATES = tuple(f"G{i}" for i in range(1, 9))
REQUIRED_LOGIC_CHECKS = (
    "denominator_integrity", "time_window_alignment", "missing_null_zero",
    "unit_consistency", "linked_metric_coverage", "scope_identity",
)
REQUIRED_METHOD_CHECKS = (
    "official_definition", "anomaly_threshold", "sample_mde",
    "confounders", "causal_claim_cap", "text_read_gate",
)
CANONICAL_DEFINITIONS = {
    "metric_catalog": PROJECT_ROOT / "skills" / "story-data-analyze" / "dictionary" / "metrics.v1.json",
    "metric_tree": PROJECT_ROOT / "skills" / "story-data-analyze" / "dictionary" / "metric-tree.v1.json",
    "diagnostic_routes": PROJECT_ROOT / "skills" / "story-data-analyze" / "dictionary" / "diagnostic-routes.v1.json",
}


class WorkflowError(RuntimeError):
    pass


class RevisionConflict(WorkflowError):
    pass


class IntegrityError(WorkflowError):
    pass


class GateError(WorkflowError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_replace_json(path: pathlib.Path, value: Any) -> None:
    """Atomically replace the one mutable manifest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_bytes(value)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temp = pathlib.Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass
    finally:
        if temp.exists():
            temp.unlink()


def atomic_create_bytes(path: pathlib.Path, data: bytes) -> None:
    """Create an immutable artifact atomically and refuse overwrite."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temp = pathlib.Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            raise IntegrityError(f"immutable artifact already exists: {path}")
        try:
            os.link(temp, path)
        except FileExistsError as exc:
            raise IntegrityError(f"immutable artifact already exists: {path}") from exc
        try:
            os.chmod(path, 0o444)
        except OSError:
            pass
    finally:
        if temp.exists():
            temp.unlink()


def _run_dir(runs_root: pathlib.Path, run_id: str) -> pathlib.Path:
    if not RUN_ID_RE.fullmatch(run_id):
        raise WorkflowError("run_id must match [A-Za-z0-9][A-Za-z0-9._-]{0,127}")
    return runs_root / run_id


def _manifest_path(runs_root: pathlib.Path, run_id: str) -> pathlib.Path:
    return _run_dir(runs_root, run_id) / "manifest.json"


@contextlib.contextmanager
def run_lock(runs_root: pathlib.Path, run_id: str) -> Iterator[None]:
    run_dir = _run_dir(runs_root, run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    lock_path = run_dir / ".manifest.lock"
    with lock_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def load_manifest(runs_root: pathlib.Path, run_id: str) -> Dict[str, Any]:
    path = _manifest_path(runs_root, run_id)
    if not path.exists():
        raise WorkflowError(f"run does not exist: {run_id}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrityError(f"manifest is corrupt: {path}: {exc}") from exc
    _validate_manifest_shape(manifest, run_id)
    return manifest


def _validate_manifest_shape(manifest: Mapping[str, Any], run_id: str) -> None:
    required = {
        "schema_version", "run_id", "stage", "state", "revision", "max_returns",
        "return_count", "return_counts_by_root_cause", "attempts", "chain_head_sha256", "artifact_hashes",
        "artifacts", "history", "quality_status", "usable_fields", "sample_size",
        "sample_size_qualified", "sample_size_authoritative", "authorization",
        "supervisor_verdict", "scope", "scope_sha256", "promoted_cases", "promoted_methods",
    }
    absent = sorted(required - set(manifest))
    if absent:
        raise IntegrityError(f"manifest missing keys: {', '.join(absent)}")
    if manifest.get("run_id") != run_id:
        raise IntegrityError("manifest run_id does not match directory")
    if manifest.get("stage") != manifest.get("state"):
        raise IntegrityError("manifest stage/state aliases disagree")
    if manifest.get("state") not in set(STATES) | {"BLOCKED"}:
        raise IntegrityError(f"unknown stage {manifest.get('state')!r}")
    if not isinstance(manifest.get("revision"), int) or manifest["revision"] < 0:
        raise IntegrityError("manifest revision must be a non-negative integer")
    if manifest.get("max_returns") != FIXED_MAX_RETURNS:
        raise IntegrityError(f"manifest max_returns must be fixed at {FIXED_MAX_RETURNS}")
    if not isinstance(manifest.get("scope"), dict) or not manifest["scope"]:
        raise IntegrityError("manifest scope must be a non-empty object")
    expected_scope_hash = sha256_bytes(canonical_bytes(manifest["scope"]))
    if manifest.get("scope_sha256") != expected_scope_hash:
        raise IntegrityError("manifest scope_sha256 does not match scope")


def _expected_attempts(entries: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for entry in entries:
        kind = entry.get("kind")
        attempt = entry.get("attempt")
        if not isinstance(kind, str) or not isinstance(attempt, int) or attempt != result.get(kind, 0) + 1:
            raise IntegrityError("artifact attempts are not contiguous by kind")
        result[kind] = attempt
    return result


def _verify_manifest_replay(
    runs_root: pathlib.Path,
    run_id: str,
    current: Mapping[str, Any],
    envelopes: Sequence[Mapping[str, Any]],
    *,
    allow_recoverable_missing_knowledge: bool = False,
) -> None:
    replay: Dict[str, Any] = {
        "state": "INIT",
        "stage": "INIT",
        "scope": dict(current["scope"]),
        "scope_sha256": current["scope_sha256"],
        "max_returns": FIXED_MAX_RETURNS,
        "return_count": 0,
        "return_counts_by_root_cause": {},
        "quality_status": None,
        "usable_fields": [],
        "sample_size": None,
        "sample_size_qualified": None,
        "sample_size_authoritative": None,
        "supervisor_verdict": None,
        "blocked_reason": None,
        "authorization": {"status": "NONE", "artifacts": [], "authorized_scope": [], "proposal_ids": []},
        "promoted_cases": [],
        "promoted_methods": [],
        "artifacts": [],
        "artifact_hashes": [],
        "chain_head_sha256": None,
        "_payload_cache": {},
    }
    for entry, envelope in zip(current["artifacts"], envelopes):
        kind = str(entry["kind"])
        producer = str(entry.get("producer", ""))
        if envelope.get("producer") != producer:
            raise IntegrityError(f"artifact producer mismatch: {entry['file']}")
        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            raise IntegrityError(f"artifact payload must be an object: {entry['file']}")
        replay_manifest = {
            **replay,
            "artifact_hashes": list(replay["artifact_hashes"]),
            "chain_head_sha256": replay["chain_head_sha256"],
        }
        if kind in KIND_FLOW:
            _validate_producer(kind, producer)
            expected_state, target_state, _ = KIND_FLOW[kind]
            if replay["state"] != expected_state:
                raise IntegrityError(f"artifact state replay failed: {kind} requires {expected_state}, got {replay['state']}")
            if kind == "raw_capture":
                effective = _validate_raw_capture(payload, replay_manifest)
            else:
                _validate_input_refs(payload, replay_manifest, kind)
                if kind == "data_quality":
                    effective = _validate_data_quality(payload, replay_manifest)
                elif kind == "window_bound":
                    _validate_window(payload, replay_manifest)
                    effective = None
                elif kind == "metrics":
                    _validate_metrics(payload, replay_manifest)
                    effective = None
                elif kind == "analysis":
                    _validate_analysis(payload, replay_manifest)
                    effective = None
                elif kind == "validation":
                    replay_manifest["_payload_cache"] = {
                        "analysis": replay["_payload_cache"].get("analysis", {}),
                        "metrics": replay["_payload_cache"].get("metrics", {}),
                        "data_quality": replay["_payload_cache"].get("data_quality", {}),
                        "window_bound": replay["_payload_cache"].get("window_bound", {}),
                    }
                    _validate_validation(payload, replay_manifest)
                    effective = None
                elif kind == "text_diagnosis":
                    replay_manifest["_payload_cache"] = {
                        "analysis": replay["_payload_cache"].get("analysis", {}),
                        "validation": replay["_payload_cache"].get("validation", {}),
                    }
                    _validate_text_diagnosis(payload, replay_manifest)
                    effective = None
                else:
                    _validate_supervision(payload, replay_manifest)
                    effective = None

            if kind in {"raw_capture", "data_quality"}:
                replay["quality_status"] = effective
                replay["usable_fields"] = sorted(set(payload.get("usable_fields", [])))
                if kind == "data_quality":
                    replay["sample_size"] = payload["sample_size"]
                    replay["sample_size_qualified"] = payload["sample_size_qualified"]
                    replay["sample_size_authoritative"] = payload["sample_size_authoritative"]
                if effective in FATAL_QUALITY:
                    _set_state(replay, "BLOCKED")
                    replay["blocked_reason"] = effective
                else:
                    _set_state(replay, target_state)
            elif kind == "validation":
                decision = payload["decision"]
                if decision == "PASS":
                    _set_state(replay, target_state)
                elif decision == "BLOCKED":
                    _set_state(replay, "BLOCKED")
                    replay["blocked_reason"] = payload.get("reason", "VALIDATION_BLOCKED")
                else:
                    _apply_return(replay, payload["earliest_fault_state"], payload["reason"], payload["root_cause_id"])
            elif kind == "supervision":
                decision = payload["decision"]
                replay["supervisor_verdict"] = decision
                if decision == "PASS":
                    _set_state(replay, target_state)
                elif decision == "BLOCKED":
                    _set_state(replay, "BLOCKED")
                    replay["blocked_reason"] = payload.get("reason", "SUPERVISION_BLOCKED")
                else:
                    _apply_return(replay, payload["earliest_fault_state"], payload["reason"], payload["root_cause_id"])
            else:
                _set_state(replay, target_state)
            replay["_payload_cache"][kind] = payload
        elif kind == "return":
            if producer not in {"story-data-method-validator", "story-data-supervisor"}:
                raise IntegrityError("return artifact producer is not validator/supervisor")
            _validate_input_refs(payload, replay_manifest, kind)
            _required(payload, ("to_state", "reason"), "return")
            _validate_return_metadata(payload, "return")
            expected_state = "ANALYZED" if producer == "story-data-method-validator" else "TEXT_DIAGNOSED"
            if replay["state"] != expected_state:
                raise IntegrityError(f"return producer/state mismatch: {producer} from {replay['state']}")
            _apply_return(replay, payload["to_state"], payload["reason"], payload["root_cause_id"])
        elif kind == "report":
            _validate_producer(kind, producer)
            _validate_input_refs(payload, replay_manifest, kind)
            if replay["state"] != "SUPERVISED" or replay["supervisor_verdict"] != "PASS":
                raise IntegrityError("report artifact exists without supervised PASS")
            report_text = _nonempty_string(payload.get("report"), "report.report")
            supervision = replay["_payload_cache"].get("supervision", {})
            report_claims = supervision.get("report_claims", []) if isinstance(supervision, dict) else []
            approved_ids = [claim.get("claim_id") for claim in report_claims if isinstance(claim, dict)]
            if payload.get("approved_claim_ids") != approved_ids:
                raise IntegrityError("report approved_claim_ids differ from supervision")
            if any(claim.get("text") not in report_text for claim in report_claims if isinstance(claim, dict)):
                raise IntegrityError("report omits a supervisor-approved claim")
            for required_section in ("数据截止日", "结论强度", "关键指标", "瓶颈", "下一步", "证据哈希"):
                if required_section not in report_text:
                    raise IntegrityError(f"report missing required section: {required_section}")
            if supervision.get("final_strength_cap") not in report_text:
                raise IntegrityError("report omits final strength cap")
            _set_state(replay, "REPORT_COMPLETE")
        elif kind == "authorization":
            _validate_producer(kind, producer)
            _validate_input_refs(payload, replay_manifest, kind)
            if replay["state"] not in {"SUPERVISED", "REPORT_COMPLETE"} or replay["supervisor_verdict"] != "PASS":
                raise IntegrityError("authorization artifact exists before supervised PASS")
            _validate_authorization_payload(payload)
            expected_nonce = _authorization_nonce(
                run_id, replay["chain_head_sha256"], payload["user_event_id"], payload["user_message_sha256"]
            )
            if payload["authorization_nonce"] != expected_nonce:
                raise IntegrityError("authorization nonce does not match replayed chain head/user event")
            replay["authorization"] = {
                "status": payload["decision"],
                "artifacts": [*replay["authorization"].get("artifacts", []), entry["file"]],
                "authorized_scope": list(payload["authorized_scope"]) if payload["decision"] == "APPROVED" else [],
                "proposal_ids": list(payload["proposal_ids"]) if payload["decision"] == "APPROVED" else [],
                "confirmed_at": payload["confirmed_at"],
                "authorized_by": payload["authorized_by"],
                "user_event_id": payload["user_event_id"],
                "attestation_status": payload["attestation_status"],
            }
        elif kind in {"case_promotion", "method_promotion"}:
            _validate_producer(kind, producer)
            _validate_input_refs(payload, replay_manifest, kind)
            if replay["state"] != "REPORT_COMPLETE" or replay["supervisor_verdict"] != "PASS":
                raise IntegrityError(f"{kind} exists before REPORT_COMPLETE")
            file_key = "case_file" if kind == "case_promotion" else "method_file"
            hash_key = "case_sha256" if kind == "case_promotion" else "method_sha256"
            promoted_path = pathlib.Path(str(payload.get(file_key, ""))).resolve(strict=False)
            expected_root = (PROJECT_ROOT / "数据追踪" / "knowledge" / ("cases" if kind == "case_promotion" else "methods")).resolve(strict=False)
            if runs_root.resolve(strict=False) == DEFAULT_RUNS_ROOT.resolve(strict=False):
                try:
                    promoted_path.relative_to(expected_root)
                except ValueError as exc:
                    raise IntegrityError(f"{kind} path escapes the knowledge root") from exc
            document = payload.get("knowledge_document")
            document_valid = isinstance(document, dict) and sha256_bytes(canonical_bytes(document)) == payload.get(hash_key)
            if promoted_path.is_file():
                if sha256_file(promoted_path) != payload.get(hash_key):
                    raise IntegrityError(f"{kind} knowledge file hash mismatch")
                if document is not None and not document_valid:
                    raise IntegrityError(f"{kind} embedded recovery document hash mismatch")
            elif not (allow_recoverable_missing_knowledge and document_valid):
                raise IntegrityError(f"{kind} knowledge file missing or not recoverable")
            target_list = "promoted_cases" if kind == "case_promotion" else "promoted_methods"
            replay[target_list].append({
                key: value for key, value in payload.items()
                if key not in {"input_artifact_hashes", "knowledge_document"}
            })
        else:
            raise IntegrityError(f"unknown artifact kind in manifest: {kind}")

        replay["artifact_hashes"].append(entry["sha256"])
        replay["chain_head_sha256"] = entry["sha256"]
        replay["artifacts"].append(dict(entry))

    comparable_fields = (
        "state", "stage", "quality_status", "usable_fields", "sample_size", "sample_size_qualified",
        "sample_size_authoritative", "return_count", "return_counts_by_root_cause",
        "supervisor_verdict", "blocked_reason", "authorization", "promoted_cases", "promoted_methods",
    )
    for field_name in comparable_fields:
        if current.get(field_name) != replay.get(field_name):
            raise IntegrityError(f"manifest field does not match artifact replay: {field_name}")


def verify_integrity(
    runs_root: pathlib.Path,
    run_id: str,
    manifest: Optional[Mapping[str, Any]] = None,
    *,
    allow_orphans: bool = False,
    allow_recoverable_missing_knowledge: bool = False,
) -> Dict[str, Any]:
    current = dict(manifest) if manifest is not None else load_manifest(runs_root, run_id)
    prior: Optional[str] = None
    hashes: List[str] = []
    envelopes: List[Mapping[str, Any]] = []
    run_dir = _run_dir(runs_root, run_id)
    for index, entry in enumerate(current["artifacts"]):
        raw_file = entry.get("file")
        if not isinstance(raw_file, str) or pathlib.Path(raw_file).is_absolute():
            raise IntegrityError("artifact file must be a relative path")
        path = (run_dir / raw_file).resolve(strict=False)
        try:
            path.relative_to(run_dir.resolve(strict=False))
        except ValueError as exc:
            raise IntegrityError(f"artifact path escapes run directory: {raw_file}") from exc
        if not path.is_file():
            raise IntegrityError(f"artifact missing: {entry['file']}")
        actual = sha256_file(path)
        if actual != entry["sha256"]:
            raise IntegrityError(f"artifact hash mismatch: {entry['file']}")
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise IntegrityError(f"artifact JSON corrupt: {entry['file']}") from exc
        if envelope.get("run_id") != run_id:
            raise IntegrityError(f"artifact run_id mismatch: {entry['file']}")
        if envelope.get("prior_artifact_sha256") != prior or entry.get("prior_sha256") != prior:
            raise IntegrityError(f"hash-chain break at artifact {index + 1}: {entry['file']}")
        payload_hash = sha256_bytes(canonical_bytes(envelope.get("payload")))
        if envelope.get("payload_sha256") != payload_hash:
            raise IntegrityError(f"payload hash mismatch: {entry['file']}")
        if envelope.get("kind") != entry.get("kind") or envelope.get("attempt") != entry.get("attempt"):
            raise IntegrityError(f"artifact index metadata mismatch: {entry['file']}")
        prior = actual
        hashes.append(actual)
        envelopes.append(envelope)
    if current.get("chain_head_sha256") != prior:
        raise IntegrityError("manifest chain head does not match artifact chain")
    if current.get("artifact_hashes") != hashes:
        raise IntegrityError("manifest artifact_hashes does not match artifact chain")
    if current.get("revision") != len(current["artifacts"]):
        raise IntegrityError("manifest revision must equal committed artifact count")
    history = current.get("history")
    if not isinstance(history, list) or len(history) != current["revision"] + 1:
        raise IntegrityError("manifest history length does not match revision")
    if [item.get("revision") for item in history if isinstance(item, dict)] != list(range(current["revision"] + 1)):
        raise IntegrityError("manifest history revisions are not contiguous")
    expected_attempts = _expected_attempts(current["artifacts"])
    if current.get("attempts") != expected_attempts:
        raise IntegrityError("manifest attempts do not match artifact attempts")
    referenced = {str(entry["file"]) for entry in current["artifacts"]}
    orphans = {
        path.name for path in run_dir.glob("*.attempt-*.json")
        if path.name not in referenced
    }
    if orphans and not allow_orphans:
        raise IntegrityError(f"uncommitted/orphan artifacts require recovery: {sorted(orphans)}")
    _verify_manifest_replay(
        runs_root, run_id, current, envelopes,
        allow_recoverable_missing_knowledge=allow_recoverable_missing_knowledge,
    )
    return {"ok": True, "artifact_count": len(hashes), "chain_head_sha256": prior}


def recover_run(runs_root: pathlib.Path, run_id: str) -> Dict[str, Any]:
    """Recover only deterministic crash residue; never infer or advance business state.

    Unreferenced attempt files are quarantined (not deleted).  A promoted knowledge
    file may be recreated only from the exact document embedded in an already
    committed, hash-chained promotion artifact.
    """
    with run_lock(runs_root, run_id):
        manifest = load_manifest(runs_root, run_id)
        run_dir = _run_dir(runs_root, run_id)
        referenced = {str(entry["file"]) for entry in manifest["artifacts"]}
        orphans = sorted(
            path for path in run_dir.glob("*.attempt-*.json")
            if path.name not in referenced
        )
        quarantined: List[str] = []
        if orphans:
            stamp = utc_now().replace(":", "-").replace("+", "_")
            recovery_dir = run_dir / "recovery" / stamp
            recovery_dir.mkdir(parents=True, exist_ok=False)
            for orphan in orphans:
                destination = recovery_dir / orphan.name
                os.replace(orphan, destination)
                quarantined.append(str(destination.relative_to(run_dir)))

        # Validate the committed chain before trusting an embedded recovery document.
        verify_integrity(
            runs_root, run_id, manifest,
            allow_recoverable_missing_knowledge=True,
        )
        restored: List[str] = []
        for entry in manifest["artifacts"]:
            if entry.get("kind") not in {"case_promotion", "method_promotion"}:
                continue
            envelope_path = run_dir / str(entry["file"])
            envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
            payload = envelope.get("payload", {})
            if not isinstance(payload, dict):
                raise IntegrityError("promotion artifact payload is not an object")
            file_key = "case_file" if entry["kind"] == "case_promotion" else "method_file"
            hash_key = "case_sha256" if entry["kind"] == "case_promotion" else "method_sha256"
            target = pathlib.Path(str(payload.get(file_key, ""))).resolve(strict=False)
            if target.is_file():
                continue
            document = payload.get("knowledge_document")
            if not isinstance(document, dict):
                raise IntegrityError(f"missing knowledge file has no embedded recovery document: {target}")
            data = canonical_bytes(document)
            if sha256_bytes(data) != payload.get(hash_key):
                raise IntegrityError(f"embedded knowledge recovery hash mismatch: {target}")
            if runs_root.resolve(strict=False) == DEFAULT_RUNS_ROOT.resolve(strict=False):
                expected_root = (
                    DEFAULT_KNOWLEDGE_ROOT if entry["kind"] == "case_promotion"
                    else DEFAULT_METHOD_KNOWLEDGE_ROOT
                ).resolve(strict=False)
                try:
                    target.relative_to(expected_root)
                except ValueError as exc:
                    raise IntegrityError("recovery target escapes the canonical knowledge root") from exc
            atomic_create_bytes(target, data)
            restored.append(str(target))

        result = verify_integrity(runs_root, run_id, manifest)
        return {**result, "quarantined_orphans": quarantined, "restored_knowledge": restored}


def _assert_revision(manifest: Mapping[str, Any], expected_revision: int) -> None:
    if expected_revision != manifest["revision"]:
        raise RevisionConflict(f"revision conflict: expected {expected_revision}, actual {manifest['revision']}")


def _state_index(state: str) -> int:
    try:
        return STATES.index(state)
    except ValueError as exc:
        raise GateError(f"state {state} is not in the normal workflow") from exc


def _set_state(manifest: Dict[str, Any], state: str) -> None:
    manifest["state"] = state
    manifest["stage"] = state


def _commit_manifest(path: pathlib.Path, manifest: Dict[str, Any], event: str, detail: Mapping[str, Any]) -> None:
    manifest["revision"] += 1
    manifest["updated_at"] = utc_now()
    manifest["history"].append(
        {
            "revision": manifest["revision"],
            "at": manifest["updated_at"],
            "event": event,
            **dict(detail),
        }
    )
    atomic_replace_json(path, manifest)


def init_run(
    runs_root: pathlib.Path,
    run_id: str,
    *,
    scope: Optional[Mapping[str, Any]] = None,
    max_returns: int = 3,
) -> Dict[str, Any]:
    if max_returns != FIXED_MAX_RETURNS:
        raise WorkflowError(f"max_returns is fixed at {FIXED_MAX_RETURNS}")
    run_scope = dict(scope or {})
    required_scope = {"platform", "work_type", "work_id", "mode", "question"}
    absent_scope = sorted(required_scope - set(run_scope))
    if absent_scope:
        raise WorkflowError(f"run scope missing keys: {', '.join(absent_scope)}")
    if run_scope["platform"] != "fanqie":
        raise WorkflowError("this workflow currently supports platform=fanqie")
    if run_scope["work_type"] not in {"long", "short", "all"}:
        raise WorkflowError("scope.work_type must be long, short or all")
    if run_scope["mode"] not in {"latest", "snapshot", "method_only"}:
        raise WorkflowError("scope.mode must be latest, snapshot or method_only")
    if not str(run_scope["work_id"]).strip() or not str(run_scope["question"]).strip():
        raise WorkflowError("scope.work_id and scope.question cannot be empty")
    run_scope["work_id"] = str(run_scope["work_id"])
    if run_scope["mode"] != "method_only":
        for key in ("expected_snapshot_date", "expected_data_until"):
            if not isinstance(run_scope.get(key), str) or not run_scope[key]:
                raise WorkflowError(f"scope.{key} is required outside method_only mode")
        try:
            expected_snapshot = dt.date.fromisoformat(run_scope["expected_snapshot_date"])
            expected_cutoff = dt.date.fromisoformat(run_scope["expected_data_until"])
        except ValueError as exc:
            raise WorkflowError("scope expected dates must be ISO calendar dates") from exc
        if expected_cutoff != expected_snapshot - dt.timedelta(days=1):
            raise WorkflowError("scope.expected_data_until must be the day before expected_snapshot_date")
    if "causal_design_verified" in run_scope and not isinstance(run_scope["causal_design_verified"], bool):
        raise WorkflowError("scope.causal_design_verified must be boolean when supplied")
    run_dir = _run_dir(runs_root, run_id)
    manifest_path = run_dir / "manifest.json"
    with run_lock(runs_root, run_id):
        if manifest_path.exists():
            raise WorkflowError(f"run already exists: {run_id}")
        now = utc_now()
        manifest: Dict[str, Any] = {
            "schema_version": 1,
            "run_id": run_id,
            "created_at": now,
            "updated_at": now,
            "stage": "INIT",
            "state": "INIT",
            "revision": 0,
            "scope": run_scope,
            "scope_sha256": sha256_bytes(canonical_bytes(run_scope)),
            "max_returns": FIXED_MAX_RETURNS,
            "return_count": 0,
            "return_counts_by_root_cause": {},
            "attempts": {},
            "chain_head_sha256": None,
            "artifact_hashes": [],
            "artifacts": [],
            "history": [{"revision": 0, "at": now, "event": "INIT"}],
            "quality_status": None,
            "usable_fields": [],
            "sample_size": None,
            "sample_size_qualified": None,
            "sample_size_authoritative": None,
            "authorization": {"status": "NONE", "artifacts": [], "authorized_scope": [], "proposal_ids": []},
            "supervisor_verdict": None,
            "blocked_reason": None,
            "promoted_cases": [],
            "promoted_methods": [],
        }
        atomic_replace_json(manifest_path, manifest)
    return manifest


def _required(payload: Mapping[str, Any], keys: Sequence[str], kind: str) -> None:
    absent = [key for key in keys if key not in payload]
    if absent:
        raise GateError(f"{kind} payload missing required keys: {', '.join(absent)}")


def _quality_status(payload: Mapping[str, Any], kind: str) -> str:
    _required(payload, ("status",), kind)
    status = payload["status"]
    if status not in QUALITY_STATUSES:
        raise GateError(f"{kind}.status must be one of {sorted(QUALITY_STATUSES)}")
    usable = payload.get("usable_fields", [])
    if status == "PARTIAL" and (not isinstance(usable, list) or not usable):
        raise GateError("PARTIAL quality must list at least one usable_fields entry")
    return status


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GateError(f"{label} must be a non-empty string")
    return value


def _iso_date(value: Any, label: str) -> dt.date:
    if not isinstance(value, str):
        raise GateError(f"{label} must be an ISO date")
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise GateError(f"{label} must be an ISO date") from exc


def _iso_datetime(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str):
        raise GateError(f"{label} must be an ISO datetime with timezone")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise GateError(f"{label} must be an ISO datetime with timezone") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise GateError(f"{label} must include a timezone offset")
    return parsed


def _resolve_evidence_path(raw: str) -> pathlib.Path:
    path = pathlib.Path(raw)
    resolved = (path if path.is_absolute() else PROJECT_ROOT / path).resolve(strict=False)
    if not resolved.is_file():
        raise GateError(f"evidence source file does not exist: {raw}")
    return resolved


def _validate_source_files(files: Any, hashes: Any, label: str) -> None:
    if not isinstance(files, list) or not isinstance(hashes, list):
        raise GateError(f"{label} files/hashes must be arrays")
    if not files or len(files) != len(hashes):
        raise GateError(f"{label} files/hashes must be non-empty and have equal length")
    for raw_path, expected_hash in zip(files, hashes):
        _nonempty_string(raw_path, f"{label}.file")
        if not isinstance(expected_hash, str) or not SHA256_RE.fullmatch(expected_hash):
            raise GateError(f"{label} hashes must be lowercase sha256 values")
        actual_hash = sha256_file(_resolve_evidence_path(raw_path))
        if actual_hash != expected_hash:
            raise IntegrityError(f"{label} source hash mismatch: {raw_path}")


def _load_json_evidence(raw_path: str, label: str) -> Mapping[str, Any]:
    path = _resolve_evidence_path(raw_path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrityError(f"{label} is not valid JSON: {raw_path}") from exc
    if not isinstance(value, dict):
        raise GateError(f"{label} must be a JSON object")
    return value


def _json_pointer(value: Any, pointer: str) -> Any:
    if pointer == "":
        return value
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise GateError("sample evidence json_pointer must be an RFC 6901 absolute pointer")
    current = value
    for raw_part in pointer[1:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            if not part.isdigit() or int(part) >= len(current):
                raise GateError(f"sample evidence pointer does not exist: {pointer}")
            current = current[int(part)]
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise GateError(f"sample evidence pointer does not exist: {pointer}")
    return current


def _workflow_endpoint_healthy(value: Any, *, frozen: bool = False) -> bool:
    if not isinstance(value, dict):
        return False
    if frozen:
        return value.get("source_hash_verified") is True
    return bool(
        value.get("http_ok") is True
        and value.get("json_ok") is True
        and value.get("business_code") in (None, 0, "0")
    )


def _workflow_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    if isinstance(value, str):
        try:
            parsed = float(value.strip())
        except ValueError:
            return None
        return parsed if math.isfinite(parsed) else None
    return None


def _validate_input_refs(payload: Mapping[str, Any], manifest: Mapping[str, Any], kind: str) -> None:
    refs = payload.get("input_artifact_hashes")
    if not isinstance(refs, list) or not refs:
        raise GateError(f"{kind}.input_artifact_hashes must be a non-empty array")
    if any(not isinstance(value, str) or not SHA256_RE.fullmatch(value) for value in refs):
        raise GateError(f"{kind}.input_artifact_hashes contains an invalid sha256")
    known = set(manifest.get("artifact_hashes", []))
    if not set(refs).issubset(known):
        raise GateError(f"{kind}.input_artifact_hashes references an unknown artifact")
    if manifest.get("chain_head_sha256") not in refs:
        raise GateError(f"{kind} must cite the current upstream chain head")


def _validate_check_rows(rows: Any, label: str, *, required_ids: Optional[Sequence[str]] = None) -> None:
    if not isinstance(rows, list) or not rows:
        raise GateError(f"{label} must be a non-empty array")
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise GateError(f"{label} entries must be objects")
        _required(row, ("check_id", "status", "evidence"), label)
        check_id = _nonempty_string(row["check_id"], f"{label}.check_id")
        if check_id in seen:
            raise GateError(f"{label} check_id values must be unique")
        seen.add(check_id)
        if row["status"] not in {"PASS", "PARTIAL", "FAIL", "BLOCK"}:
            raise GateError(f"{label}.status is invalid")
        if not isinstance(row["evidence"], list) or not row["evidence"]:
            raise GateError(f"{label}.{check_id} requires evidence")
    if required_ids is not None and set(required_ids) != seen:
        raise GateError(f"{label} must contain exactly {sorted(required_ids)}")


def _validate_producer(kind: str, producer: str) -> None:
    expected = EXPECTED_PRODUCERS.get(kind)
    if expected is not None and producer != expected:
        raise GateError(f"{kind} must be produced by {expected}, got {producer!r}")


def _validate_raw_capture(payload: Mapping[str, Any], manifest: Mapping[str, Any]) -> str:
    status = _quality_status(payload, "raw_capture")
    _required(payload, ("source_files", "source_hashes", "capture_mode", "work_id", "run_scope_sha256"), "raw_capture")
    if payload["run_scope_sha256"] != manifest.get("scope_sha256"):
        raise GateError("raw_capture.run_scope_sha256 does not match the frozen run scope")
    if str(payload["work_id"]) != str(manifest["scope"]["work_id"]):
        raise GateError("raw_capture.work_id does not match run scope")
    if payload["capture_mode"] not in {"platform_pull", "frozen_snapshot"}:
        raise GateError("raw_capture.capture_mode must be platform_pull or frozen_snapshot")
    if status in {"OK", "PARTIAL"}:
        _required(
            payload,
            (
                "snapshot_date", "data_until", "pulled_at", "login_status", "endpoint_status",
                "required_endpoint_names", "usable_fields", "snapshot_file", "snapshot_sha256",
                "snapshot_metadata_verified", "work_identity_status",
            ),
            "raw_capture",
        )
        if payload["capture_mode"] == "platform_pull" and payload["login_status"] != "AUTHENTICATED":
            raise GateError("platform_pull requires login_status=AUTHENTICATED")
        if payload["capture_mode"] == "frozen_snapshot" and payload["login_status"] != "NOT_APPLICABLE":
            raise GateError("frozen_snapshot requires login_status=NOT_APPLICABLE")
        if payload["capture_mode"] == "frozen_snapshot" and status != "PARTIAL":
            raise GateError("a frozen historical snapshot cannot claim raw_capture status OK")
        snapshot = _iso_date(payload["snapshot_date"], "raw_capture.snapshot_date")
        cutoff = _iso_date(payload["data_until"], "raw_capture.data_until")
        if cutoff != snapshot - dt.timedelta(days=1):
            raise GateError("raw_capture.data_until must be the calendar day before snapshot_date")
        _iso_datetime(payload["pulled_at"], "raw_capture.pulled_at")
        if payload["snapshot_date"] != manifest["scope"].get("expected_snapshot_date"):
            return "PLATFORM_NOT_UPDATED"
        if payload["data_until"] != manifest["scope"].get("expected_data_until"):
            return "PLATFORM_NOT_UPDATED"
        endpoints = payload["endpoint_status"]
        if not isinstance(endpoints, dict) or not endpoints:
            raise GateError("raw_capture.endpoint_status must be a non-empty object")
        required_endpoints = payload["required_endpoint_names"]
        if not isinstance(required_endpoints, list) or not required_endpoints or any(
            not isinstance(value, str) or not value for value in required_endpoints
        ):
            raise GateError("raw_capture.required_endpoint_names must be a non-empty string array")
        if not set(required_endpoints).issubset(endpoints):
            raise GateError("raw_capture.endpoint_status omits a required endpoint")
        frozen = payload["capture_mode"] == "frozen_snapshot"
        failed = [
            name for name in required_endpoints
            if not _workflow_endpoint_healthy(endpoints.get(name), frozen=frozen)
        ]
        if status == "OK" and failed:
            raise GateError(f"raw_capture OK contradicts failed endpoints: {failed}")
        if not isinstance(payload["usable_fields"], list) or not payload["usable_fields"]:
            raise GateError("successful raw capture must list usable_fields")
        _validate_source_files(payload["source_files"], payload["source_hashes"], "raw_capture")
        if payload["snapshot_file"] not in payload["source_files"]:
            raise GateError("raw_capture.snapshot_file must be one of source_files")
        snapshot_index = payload["source_files"].index(payload["snapshot_file"])
        if payload["snapshot_sha256"] != payload["source_hashes"][snapshot_index]:
            raise GateError("raw_capture.snapshot_sha256 differs from the source_files entry")
        raw = _load_json_evidence(payload["snapshot_file"], "raw capture snapshot")
        if sha256_file(_resolve_evidence_path(payload["snapshot_file"])) != payload["snapshot_sha256"]:
            raise IntegrityError("raw capture snapshot hash mismatch")
        for key, payload_key in (("date", "snapshot_date"), ("data_until", "data_until")):
            if raw.get(key) != payload[payload_key]:
                raise GateError(f"raw_capture.{payload_key} differs from snapshot.{key}")
        if payload["snapshot_metadata_verified"] is not True:
            raise GateError("successful raw capture requires snapshot_metadata_verified=true")
        raw_work_id = raw.get("novel_id")
        if payload["work_identity_status"] == "VERIFIED_SOURCE":
            if raw_work_id is None or str(raw_work_id) != str(payload["work_id"]):
                raise GateError("VERIFIED_SOURCE requires the snapshot work ID to match")
        elif payload["work_identity_status"] == "VERIFIED_FROZEN_REGISTRY":
            if payload["capture_mode"] != "frozen_snapshot":
                raise GateError("VERIFIED_FROZEN_REGISTRY is only valid for frozen_snapshot")
            _required(payload, ("identity_evidence_files", "identity_evidence_hashes"), "raw_capture")
            _validate_source_files(
                payload["identity_evidence_files"], payload["identity_evidence_hashes"], "raw_capture.identity_evidence"
            )
            registry_match = False
            for evidence_file in payload["identity_evidence_files"]:
                registry = _load_json_evidence(evidence_file, "frozen snapshot registry")
                rows = registry.get("snapshots", [])
                if not isinstance(rows, list):
                    continue
                registry_match = registry_match or any(
                    isinstance(row, dict)
                    and row.get("snapshot_sha256") == payload["snapshot_sha256"]
                    and str(row.get("work_id")) == str(payload["work_id"])
                    and row.get("snapshot_date") == payload["snapshot_date"]
                    and row.get("data_until") == payload["data_until"]
                    for row in rows
                )
            if not registry_match:
                raise GateError("frozen registry contains no hash/date/work match for the snapshot")
        else:
            raise GateError("work_identity_status must be VERIFIED_SOURCE or VERIFIED_FROZEN_REGISTRY")
        if payload["capture_mode"] == "platform_pull":
            raw_endpoints = raw.get("endpoint_status")
            if raw_endpoints != endpoints:
                raise GateError("platform_pull endpoint_status must equal snapshot.endpoint_status")
            if raw.get("schema_version") != 2:
                raise GateError("platform_pull requires a schema_version=2 snapshot")
        else:
            if set(required_endpoints) != {"historical_capture"}:
                raise GateError("frozen_snapshot must use the historical_capture provenance endpoint")
    elif payload["source_files"] or payload["source_hashes"]:
        _validate_source_files(payload["source_files"], payload["source_hashes"], "raw_capture")
    return status


def _validate_data_quality(payload: Mapping[str, Any], manifest: Mapping[str, Any]) -> str:
    status = _quality_status(payload, "data_quality")
    _required(
        payload,
        (
            "snapshot_date", "data_until", "expected_snapshot_date", "expected_data_until",
            "sample_size", "sample_size_qualified", "sample_size_authoritative", "sample_size_basis", "scope_verified",
            "work_id", "expected_work_id", "work_id_verified", "usable_fields", "quality_checks",
            "branch_statuses", "normalizer_version", "normalized_snapshot",
            "normalized_snapshot_sha256", "raw_snapshot_sha256", "sample_size_evidence",
            "sample_aggregation", "sample_unavailability_reasons",
        ),
        "data_quality",
    )
    if not isinstance(payload["sample_size"], int) or payload["sample_size"] < 0:
        raise GateError("data_quality.sample_size must be a non-negative integer")
    if not isinstance(payload["sample_size_qualified"], bool):
        raise GateError("data_quality.sample_size_qualified must be boolean")
    if not isinstance(payload["sample_size_authoritative"], bool):
        raise GateError("data_quality.sample_size_authoritative must be boolean")
    _nonempty_string(payload["sample_size_basis"], "data_quality.sample_size_basis")
    scope = manifest["scope"]
    if payload["expected_snapshot_date"] != scope.get("expected_snapshot_date"):
        raise GateError("data_quality.expected_snapshot_date differs from frozen run scope")
    if payload["expected_data_until"] != scope.get("expected_data_until"):
        raise GateError("data_quality.expected_data_until differs from frozen run scope")
    if str(payload["expected_work_id"]) != str(scope["work_id"]):
        raise GateError("data_quality.expected_work_id differs from frozen run scope")
    normalized = payload["normalized_snapshot"]
    if not isinstance(normalized, dict):
        raise GateError("data_quality.normalized_snapshot must be an object")
    normalized_hash = sha256_bytes(canonical_bytes(normalized))
    if payload["normalized_snapshot_sha256"] != normalized_hash:
        raise IntegrityError("data_quality.normalized_snapshot_sha256 mismatch")
    normalized_quality = normalized.get("quality")
    normalized_source = normalized.get("source")
    if not isinstance(normalized_quality, dict) or not isinstance(normalized_source, dict):
        raise GateError("normalized snapshot lacks source/quality objects")
    if str(payload["normalizer_version"]) != str(normalized.get("normalization_schema_version")):
        raise GateError("data_quality.normalizer_version differs from normalized snapshot")
    raw_capture = _latest_payload_from_entries(manifest, "raw_capture") or {}
    if payload["raw_snapshot_sha256"] != raw_capture.get("snapshot_sha256"):
        raise GateError("data_quality.raw_snapshot_sha256 differs from raw capture")
    if normalized_source.get("sha256") != payload["raw_snapshot_sha256"]:
        raise GateError("normalized snapshot is not derived from the recorded raw snapshot")

    registry_identity = raw_capture.get("work_identity_status") == "VERIFIED_FROZEN_REGISTRY"
    mapped_work_id = str(scope["work_id"]) if registry_identity else normalized_quality.get("work_id")
    mapped_work_verified = True if registry_identity else normalized_quality.get("work_id_verified")
    mapped_scope_verified = True if registry_identity else normalized_quality.get("scope_verified")
    mapped_branches = dict(normalized_quality.get("branch_statuses", {}))
    if registry_identity:
        requested_key = {"long": "long_novel", "short": "short_story", "all": None}[scope["work_type"]]
        if requested_key and mapped_branches.get(requested_key) == "SCOPE_UNKNOWN":
            mapped_branches[requested_key] = "PARTIAL"
        mapped_status = "PARTIAL" if normalized_quality.get("status") == "SCOPE_UNKNOWN" else normalized_quality.get("status")
    else:
        mapped_status = normalized_quality.get("status")
    if payload["status"] != mapped_status:
        raise GateError("data_quality.status differs from deterministic normalized quality")
    exact_fields = {
        "snapshot_date": normalized_quality.get("snapshot_date"),
        "data_until": normalized_quality.get("data_until"),
        "work_id": mapped_work_id,
        "work_id_verified": mapped_work_verified,
        "scope_verified": mapped_scope_verified,
        "branch_statuses": mapped_branches,
        "usable_fields": sorted(set(normalized_quality.get("usable_fields", []))),
    }
    for key, expected in exact_fields.items():
        actual = sorted(set(payload[key])) if key == "usable_fields" else payload[key]
        if actual != expected:
            raise GateError(f"data_quality.{key} differs from normalized evidence")

    sample_evidence = payload["sample_size_evidence"]
    if not isinstance(sample_evidence, list):
        raise GateError("data_quality.sample_size_evidence must be an array")
    reasons = payload["sample_unavailability_reasons"]
    if not isinstance(reasons, list) or any(not isinstance(reason, str) or not reason.strip() for reason in reasons):
        raise GateError("data_quality.sample_unavailability_reasons must be an array of non-empty strings")
    if payload["sample_size_qualified"]:
        if not sample_evidence:
            raise GateError("a qualified sample requires non-empty evidence")
        if reasons:
            raise GateError("a qualified sample cannot carry unavailability reasons")
        if payload["sample_aggregation"] not in {"single", "sum", "max", "min"}:
            raise GateError("qualified sample aggregation is invalid")
    else:
        if payload["sample_size"] != 0 or payload["sample_size_authoritative"] is not False:
            raise GateError("an unavailable sample must use size=0 and authoritative=false")
        if sample_evidence:
            raise GateError("an unavailable sample cannot cite a substitute denominator")
        if payload["sample_aggregation"] != "unavailable" or not reasons:
            raise GateError("an unavailable sample requires aggregation=unavailable and explicit reasons")
    evidence_values: List[int] = []
    evidence_authoritative: List[bool] = []
    seen_evidence = set()
    for row in sample_evidence:
        if not isinstance(row, dict):
            raise GateError("sample_size_evidence rows must be objects")
        _required(row, ("source_sha256", "json_pointer", "value", "authoritative", "role"), "sample evidence")
        source_hash = row["source_sha256"]
        if source_hash == normalized_hash:
            source_value: Any = normalized
        elif source_hash == payload["raw_snapshot_sha256"]:
            source_value = _load_json_evidence(raw_capture["snapshot_file"], "sample evidence raw snapshot")
        else:
            raise GateError("sample evidence source_sha256 is not a frozen upstream source")
        evidence_key = (source_hash, row["json_pointer"])
        if evidence_key in seen_evidence:
            raise GateError("duplicate sample evidence pointers are forbidden")
        seen_evidence.add(evidence_key)
        observed = _json_pointer(source_value, row["json_pointer"])
        if observed != row["value"]:
            raise GateError("sample evidence value differs from the frozen source")
        if isinstance(observed, bool) or not isinstance(observed, int) or observed < 0:
            raise GateError("sample evidence value must be a non-negative integer")
        _nonempty_string(row["role"], "sample evidence role")
        if not isinstance(row["authoritative"], bool):
            raise GateError("sample evidence authoritative must be boolean")
        if "minimum_compatible" in row["json_pointer"]:
            raise GateError("a minimum compatible lower bound cannot qualify as a sample denominator")
        evidence_values.append(observed)
        evidence_authoritative.append(row["authoritative"])
    if payload["sample_size_qualified"]:
        aggregators = {
            "single": lambda values: values[0] if len(values) == 1 else None,
            "sum": sum,
            "max": max,
            "min": min,
        }
        calculated_sample = aggregators[payload["sample_aggregation"]](evidence_values)
        if calculated_sample is None or calculated_sample != payload["sample_size"]:
            raise GateError("data_quality.sample_size is not reproduced by sample evidence")
        if not all(evidence_authoritative) or payload["sample_size_authoritative"] is not True:
            raise GateError("a qualified sample requires wholly authoritative evidence")

    if str(payload["work_id"]) != str(payload["expected_work_id"]) or payload["work_id_verified"] is not True:
        return "SCOPE_UNKNOWN"
    if payload["snapshot_date"] != payload["expected_snapshot_date"]:
        return "PLATFORM_NOT_UPDATED"
    if payload["data_until"] != payload["expected_data_until"]:
        return "PLATFORM_NOT_UPDATED"
    if payload["scope_verified"] is not True:
        return "SCOPE_UNKNOWN"
    if not isinstance(payload["branch_statuses"], dict) or not payload["branch_statuses"]:
        raise GateError("data_quality.branch_statuses must be a non-empty object")
    required_branch = {"long": "long_novel", "short": "short_story", "all": None}[scope["work_type"]]
    if required_branch and required_branch not in payload["branch_statuses"]:
        raise GateError(f"data_quality.branch_statuses missing {required_branch}")
    _validate_check_rows(
        payload["quality_checks"],
        "data_quality.quality_checks",
        required_ids=("freshness", "work_identity", "endpoint_health", "presence_semantics", "formula_consistency", "scope"),
    )
    check_map = {item["check_id"]: item["status"] for item in payload["quality_checks"]}
    issue_codes = {
        item.get("code") for item in normalized_quality.get("issues", []) if isinstance(item, dict)
    }
    requested_branch_values = [
        mapped_branches[key] for key in mapped_branches
        if scope["work_type"] == "all"
        or key == {"long": "long_novel", "short": "short_story"}.get(scope["work_type"])
    ]
    if all(value == "OK" for value in requested_branch_values):
        endpoint_check = "PASS"
    elif any(value == "CORRUPT" for value in requested_branch_values):
        endpoint_check = "FAIL"
    else:
        endpoint_check = "PARTIAL"
    invalid_formula_codes = {
        "COUNT_INVALID", "PERCENT_INVALID", "SCORE_INVALID", "NUMBER_INVALID",
        "SHORT_FUNNEL_MONOTONICITY_INVALID", "SHORT_DAILY_FUNNEL_INVALID", "DATE_RELATION_INVALID",
    }
    expected_checks = {
        "freshness": "PASS" if normalized_quality.get("platform_current") is True and normalized_quality.get("date_relation_valid") is True else "FAIL",
        "work_identity": "PARTIAL" if registry_identity else ("PASS" if mapped_work_verified is True else "FAIL"),
        "endpoint_health": endpoint_check,
        "presence_semantics": "PARTIAL" if issue_codes & {"FIELD_MISSING", "FIELD_NULL", "TYPE_INVALID"} else "PASS",
        "formula_consistency": "FAIL" if issue_codes & invalid_formula_codes else ("PARTIAL" if "MONOTONICITY_VIOLATION" in issue_codes else "PASS"),
        "scope": "PARTIAL" if registry_identity else ("PASS" if mapped_scope_verified is True else "FAIL"),
    }
    if check_map != expected_checks:
        raise GateError(f"data_quality quality_checks differ from deterministic checks: expected {expected_checks}")
    check_statuses = {item["status"] for item in payload["quality_checks"]}
    if status == "OK" and check_statuses != {"PASS"}:
        raise GateError("data_quality OK requires every quality check to PASS")
    if status == "OK" and any(value != "OK" for value in payload["branch_statuses"].values()):
        raise GateError("data_quality OK contradicts a non-OK branch status")
    if not isinstance(payload["usable_fields"], list) or not payload["usable_fields"]:
        raise GateError("data_quality requires at least one usable field")
    _nonempty_string(payload["normalizer_version"], "data_quality.normalizer_version")
    return status


def _verify_window_snapshot_ref(
    ref: Mapping[str, Any], manifest: Mapping[str, Any], label: str
) -> None:
    _required(
        ref,
        (
            "snapshot_date", "data_until", "source_file", "source_sha256",
            "work_id", "work_identity_status",
        ),
        f"window_bound.{label}",
    )
    source_file = _nonempty_string(ref["source_file"], f"window_bound.{label}.source_file")
    if not isinstance(ref["source_sha256"], str) or not SHA256_RE.fullmatch(ref["source_sha256"]):
        raise GateError(f"window_bound.{label}.source_sha256 is invalid")
    path = _resolve_evidence_path(source_file)
    if sha256_file(path) != ref["source_sha256"]:
        raise IntegrityError(f"window_bound.{label} source hash mismatch")
    raw = _load_json_evidence(source_file, f"window_bound.{label}")
    if raw.get("date") != ref["snapshot_date"] or raw.get("data_until") != ref["data_until"]:
        raise GateError(f"window_bound.{label} dates differ from source JSON")
    snapshot_date = _iso_date(ref["snapshot_date"], f"window_bound.{label}.snapshot_date")
    data_until = _iso_date(ref["data_until"], f"window_bound.{label}.data_until")
    if data_until != snapshot_date - dt.timedelta(days=1):
        raise GateError(f"window_bound.{label} has an invalid snapshot/cutoff relationship")
    if str(ref["work_id"]) != str(manifest["scope"]["work_id"]):
        raise GateError(f"window_bound.{label}.work_id differs from run scope")
    raw_work_id = raw.get("novel_id")
    if ref["work_identity_status"] == "VERIFIED_SOURCE":
        if raw_work_id is None or str(raw_work_id) != str(ref["work_id"]):
            raise GateError(f"window_bound.{label} source does not verify work identity")
    elif ref["work_identity_status"] == "VERIFIED_FROZEN_REGISTRY":
        _required(ref, ("identity_evidence_files", "identity_evidence_hashes"), f"window_bound.{label}")
        _validate_source_files(
            ref["identity_evidence_files"], ref["identity_evidence_hashes"],
            f"window_bound.{label}.identity_evidence",
        )
        matched = False
        for registry_file in ref["identity_evidence_files"]:
            registry = _load_json_evidence(registry_file, f"window_bound.{label}.identity registry")
            rows = registry.get("snapshots", [])
            if isinstance(rows, list):
                matched = matched or any(
                    isinstance(row, dict)
                    and row.get("snapshot_sha256") == ref["source_sha256"]
                    and str(row.get("work_id")) == str(ref["work_id"])
                    and row.get("snapshot_date") == ref["snapshot_date"]
                    and row.get("data_until") == ref["data_until"]
                    for row in rows
                )
        if not matched:
            raise GateError(f"window_bound.{label} frozen identity registry does not match")
    else:
        raise GateError(f"window_bound.{label}.work_identity_status is invalid")


def _validate_window(payload: Mapping[str, Any], manifest: Mapping[str, Any]) -> None:
    _required(
        payload,
        ("analysis_mode", "analysis_question", "baseline", "previous_snapshot", "latest_snapshot", "changes", "confounders"),
        "window_bound",
    )
    if payload["analysis_mode"] not in {"modification_effect", "health_only"}:
        raise GateError("window_bound.analysis_mode is invalid")
    _nonempty_string(payload["analysis_question"], "window_bound.analysis_question")
    if payload["analysis_question"] != manifest["scope"]["question"]:
        raise GateError("window_bound.analysis_question differs from frozen run question")
    snapshot_dates = []
    for label in ("baseline", "previous_snapshot", "latest_snapshot"):
        ref = payload[label]
        if not isinstance(ref, dict) or not ref:
            raise GateError(f"window_bound.{label} must be a non-empty object")
        _verify_window_snapshot_ref(ref, manifest, label)
        snapshot_dates.append(_iso_date(ref["data_until"], f"window_bound.{label}.data_until"))
    if not (snapshot_dates[0] < snapshot_dates[1] < snapshot_dates[2]):
        raise GateError("window_bound baseline, previous and latest cutoffs must be strictly ordered")
    raw_capture = _latest_payload_from_entries(manifest, "raw_capture") or {}
    if payload["latest_snapshot"]["source_sha256"] != raw_capture.get("snapshot_sha256"):
        raise GateError("window_bound.latest_snapshot is not the captured latest raw snapshot")
    if not isinstance(payload["changes"], list):
        raise GateError("window_bound.changes must be an array")
    if payload["analysis_mode"] == "modification_effect" and not payload["changes"]:
        raise GateError("modification_effect requires at least one change event")
    allowed = {"PARTIAL_DAY_COVERED", "FULL_DAY_COVERED", "NOT_COVERED"}
    latest_cutoff = snapshot_dates[2]
    baseline_cutoff = snapshot_dates[0]
    known_metric_ids = {
        row.get("id") for row in _load_json_evidence(
            str(CANONICAL_DEFINITIONS["metric_catalog"]), "metric catalog"
        ).get("metrics", []) if isinstance(row, dict)
    }
    seen_change_ids = set()
    for change in payload["changes"]:
        if not isinstance(change, dict) or change.get("coverage_status") not in allowed:
            raise GateError("every change requires a valid coverage_status")
        _required(
            change,
            (
                "change_id", "published_at", "target_metric_ids", "version_status",
                "version_evidence", "coverage_evidence", "concurrent_events",
                "first_covered_data_date", "first_full_data_date",
            ),
            "window_bound.change",
        )
        change_id = _nonempty_string(change["change_id"], "window_bound.change.change_id")
        if change_id in seen_change_ids:
            raise GateError("window_bound.change_id values must be unique")
        seen_change_ids.add(change_id)
        published_raw = _nonempty_string(change["published_at"], "window_bound.change.published_at")
        published_at = _iso_datetime(published_raw, "window_bound.change.published_at")
        local_published = published_at.astimezone(ZoneInfo("Asia/Shanghai"))
        first_covered = local_published.date()
        first_full = (
            first_covered
            if local_published.timetz().replace(tzinfo=None) == dt.time(0, 0)
            else first_covered + dt.timedelta(days=1)
        )
        if _iso_date(change["first_covered_data_date"], "window_bound.change.first_covered_data_date") != first_covered:
            raise GateError("change.first_covered_data_date is not derived from published_at")
        if _iso_date(change["first_full_data_date"], "window_bound.change.first_full_data_date") != first_full:
            raise GateError("change.first_full_data_date is not derived from published_at")
        expected_coverage = (
            "NOT_COVERED" if latest_cutoff < first_covered
            else "PARTIAL_DAY_COVERED" if latest_cutoff < first_full
            else "FULL_DAY_COVERED"
        )
        if change["coverage_status"] != expected_coverage:
            raise GateError(
                f"change.coverage_status must be deterministically {expected_coverage} for the latest cutoff"
            )
        if payload["analysis_mode"] == "modification_effect" and baseline_cutoff >= first_covered:
            raise GateError("modification-effect baseline must end before the change first appears")
        if not isinstance(change["target_metric_ids"], list) or not change["target_metric_ids"]:
            raise GateError("window_bound.change.target_metric_ids must be non-empty")
        if len(set(change["target_metric_ids"])) != len(change["target_metric_ids"]):
            raise GateError("window_bound.change.target_metric_ids must be unique")
        if not set(change["target_metric_ids"]).issubset(known_metric_ids):
            raise GateError("window_bound.change.target_metric_ids contains unknown metric IDs")
        if change["version_status"] not in {"VERIFIED", "UNVERIFIED", "MIXED"}:
            raise GateError("window_bound.change.version_status is invalid")
        if not isinstance(change["version_evidence"], list) or not change["version_evidence"]:
            raise GateError("window_bound.change.version_evidence must be non-empty")
        direct_version_evidence = 0
        for evidence in change["version_evidence"]:
            if not isinstance(evidence, dict):
                raise GateError("window_bound.change.version_evidence entries must be objects")
            _required(
                evidence,
                (
                    "source_file", "source_sha256", "evidence_type", "verification_strength",
                    "record_locator", "assertion",
                ),
                "window_bound.change.version_evidence",
            )
            _validate_source_files(
                [evidence["source_file"]], [evidence["source_sha256"]],
                "window_bound.change.version_evidence",
            )
            if evidence["verification_strength"] not in {"DIRECT", "CORROBORATING", "LIMITATION"}:
                raise GateError("version evidence verification_strength is invalid")
            _nonempty_string(evidence["evidence_type"], "version evidence.evidence_type")
            locator = _nonempty_string(evidence["record_locator"], "version evidence.record_locator")
            _nonempty_string(evidence["assertion"], "version evidence.assertion")
            source_text = _resolve_evidence_path(evidence["source_file"]).read_text(encoding="utf-8")
            if locator not in source_text:
                raise GateError("version evidence record_locator is absent from the frozen source")
            if evidence["verification_strength"] == "DIRECT":
                direct_version_evidence += 1
        if change["version_status"] == "VERIFIED" and direct_version_evidence < 1:
            raise GateError("version_status VERIFIED requires at least one DIRECT frozen evidence record")
        if not isinstance(change["coverage_evidence"], list) or not change["coverage_evidence"]:
            raise GateError("window_bound.change.coverage_evidence must be non-empty")
        if not isinstance(change["concurrent_events"], list):
            raise GateError("window_bound.change.concurrent_events must be an array")
    if not isinstance(payload["confounders"], list) or not payload["confounders"]:
        raise GateError("window_bound.confounders must be a non-empty array, including an explicit none-found record")
    seen_confounders = set()
    for confounder in payload["confounders"]:
        if not isinstance(confounder, dict):
            raise GateError("window_bound.confounders entries must be objects")
        _required(confounder, ("confounder_id", "status", "evidence"), "window_bound.confounder")
        confounder_id = _nonempty_string(confounder["confounder_id"], "window_bound.confounder.confounder_id")
        if confounder_id in seen_confounders:
            raise GateError("window_bound.confounder_id values must be unique")
        seen_confounders.add(confounder_id)
        if confounder["status"] not in {"PRESENT", "ABSENT", "UNKNOWN"}:
            raise GateError("window_bound.confounder.status is invalid")
        if not isinstance(confounder["evidence"], list) or not confounder["evidence"]:
            raise GateError("window_bound.confounder.evidence must be non-empty")


def _tree_node_ids(value: Any) -> set:
    result = set()
    if isinstance(value, dict):
        if isinstance(value.get("id"), str):
            result.add(value["id"])
        for child in value.values():
            result.update(_tree_node_ids(child))
    elif isinstance(value, list):
        for child in value:
            result.update(_tree_node_ids(child))
    return result


def _equivalent_value(left: Any, right: Any) -> bool:
    left_number = _workflow_number(left)
    right_number = _workflow_number(right)
    if left_number is not None and right_number is not None:
        return math.isclose(left_number, right_number, rel_tol=1e-12, abs_tol=1e-12)
    return left == right


def _calculate_metric_value(calculation: Mapping[str, Any], observed_values: Sequence[Any]) -> float:
    _required(calculation, ("mode", "operator", "expression", "input_values"), "metric calculation")
    inputs = calculation["input_values"]
    if not isinstance(inputs, list) or len(inputs) != len(observed_values) or not inputs:
        raise GateError("metric calculation inputs must exactly cover source observations")
    if any(not _equivalent_value(left, right) for left, right in zip(inputs, observed_values)):
        raise GateError("metric calculation inputs differ from frozen observations")
    numbers = [_workflow_number(value) for value in observed_values]
    if any(value is None for value in numbers):
        raise GateError("metric calculation observations must be finite numbers")
    numeric = [float(value) for value in numbers if value is not None]
    operator = calculation["operator"]
    if operator == "identity" and len(numeric) == 1:
        return numeric[0]
    if operator == "difference" and len(numeric) == 2:
        return numeric[0] - numeric[1]
    if operator == "sum":
        return sum(numeric)
    if operator == "ratio_percent" and len(numeric) == 2 and numeric[1] != 0:
        return numeric[0] / numeric[1] * 100
    raise GateError("metric calculation operator/arity is invalid")


def _recalculate_fact_from_frozen_sources(
    fact: Mapping[str, Any], data_quality: Mapping[str, Any], window: Mapping[str, Any]
) -> float:
    observations = fact.get("source_observations")
    if not isinstance(observations, list) or not observations:
        raise GateError("metric fact has no frozen source observations")
    values: List[Any] = []
    for observation in observations:
        if not isinstance(observation, dict):
            raise GateError("metric source observation must be an object")
        _required(observation, ("source_role", "source_sha256", "json_pointer", "value"), "metric observation")
        role = observation["source_role"]
        if role == "normalized_latest":
            source_value = data_quality.get("normalized_snapshot")
            expected_hash = data_quality.get("normalized_snapshot_sha256")
        elif role in {"baseline", "previous_snapshot", "latest_snapshot"}:
            ref = window.get(role, {})
            source_value = _load_json_evidence(ref.get("source_file", ""), f"metric observation {role}")
            expected_hash = ref.get("source_sha256")
        else:
            raise GateError("metric source_role is invalid")
        if observation["source_sha256"] != expected_hash:
            raise GateError("metric observation hash differs from frozen source")
        actual = _json_pointer(source_value, observation["json_pointer"])
        if not _equivalent_value(actual, observation["value"]):
            raise GateError("metric observation value differs from frozen source")
        values.append(actual)
    calculation = fact.get("calculation")
    if not isinstance(calculation, dict):
        raise GateError("metric fact calculation must be an object")
    return _calculate_metric_value(calculation, values)


def _maximum_strength_cap(manifest: Mapping[str, Any]) -> str:
    sample = manifest.get("sample_size")
    if manifest.get("sample_size_qualified") is not True or not isinstance(sample, int) or sample < 30:
        return "OBSERVED_ONLY"
    if sample < 100 or manifest.get("sample_size_authoritative") is not True:
        return "DIRECTIONAL_ONLY"
    if manifest.get("scope", {}).get("causal_design_verified") is True:
        return "CAUSAL_ALLOWED"
    return "NON_CAUSAL_ASSOCIATION"


def _validate_metrics(payload: Mapping[str, Any], manifest: Mapping[str, Any]) -> None:
    _required(
        payload,
        (
            "metric_catalog_version", "definition_artifacts", "facts", "computed_metric_ids",
            "required_nodes_checked", "node_statuses", "quality_summary",
        ),
        "metrics",
    )
    _nonempty_string(payload["metric_catalog_version"], "metrics.metric_catalog_version")
    definitions = payload["definition_artifacts"]
    if not isinstance(definitions, dict) or set(definitions) != {"metric_catalog", "metric_tree", "diagnostic_routes"}:
        raise GateError("metrics.definition_artifacts must contain metric_catalog, metric_tree and diagnostic_routes")
    definition_values: Dict[str, Mapping[str, Any]] = {}
    definition_documents: Dict[str, Mapping[str, Any]] = {}
    for label, value in definitions.items():
        if not isinstance(value, dict):
            raise GateError(f"metrics.definition_artifacts.{label} must be an object")
        _required(value, ("path", "sha256", "version"), f"metrics.definition_artifacts.{label}")
        path = _resolve_evidence_path(_nonempty_string(value["path"], f"metrics.definition_artifacts.{label}.path"))
        if path != CANONICAL_DEFINITIONS[label].resolve(strict=False):
            raise GateError(f"metrics definition must use the canonical project {label} file")
        if not isinstance(value["sha256"], str) or not SHA256_RE.fullmatch(value["sha256"]):
            raise GateError(f"metrics.definition_artifacts.{label}.sha256 is invalid")
        if sha256_file(path) != value["sha256"]:
            raise IntegrityError(f"metrics definition hash mismatch: {value['path']}")
        _nonempty_string(value["version"], f"metrics.definition_artifacts.{label}.version")
        document = _load_json_evidence(str(path), f"metrics definition {label}")
        if str(document.get("schema_version")) != str(value["version"]):
            raise GateError(f"metrics definition version does not match {label}.schema_version")
        definition_values[label] = value
        definition_documents[label] = document
    if payload["metric_catalog_version"] != definitions["metric_catalog"]["version"]:
        raise GateError("metrics.metric_catalog_version differs from catalog artifact version")
    if not isinstance(payload["facts"], list) or not payload["facts"]:
        raise GateError("metrics.facts must be a non-empty fact-row array")
    if not isinstance(payload["computed_metric_ids"], list) or not payload["computed_metric_ids"]:
        raise GateError("metrics.computed_metric_ids must be non-empty")
    catalog = definition_documents["metric_catalog"]
    metric_rows = [item for item in catalog.get("metrics", []) if isinstance(item, dict) and isinstance(item.get("id"), str)]
    known_metrics = {item["id"]: item for item in metric_rows}
    known_ids = set(known_metrics)
    preferred_directions = catalog.get("preferred_direction_by_metric")
    direction_vocabulary = catalog.get("preferred_direction_vocabulary")
    if not isinstance(preferred_directions, dict) or set(preferred_directions) != known_ids:
        raise GateError("metric catalog preferred directions must exactly cover every metric family")
    if not isinstance(direction_vocabulary, dict) or not set(preferred_directions.values()).issubset(direction_vocabulary):
        raise GateError("metric catalog preferred direction vocabulary is incomplete")
    unknown_ids = set(payload["computed_metric_ids"]) - known_ids
    if unknown_ids:
        raise GateError(f"metrics.computed_metric_ids contains unknown IDs: {sorted(unknown_ids)}")
    if not isinstance(payload["required_nodes_checked"], list) or not payload["required_nodes_checked"]:
        raise GateError("metrics.required_nodes_checked must be non-empty")
    tree_document = definition_documents["metric_tree"]
    all_nodes = _tree_node_ids(tree_document.get("trees", []))
    scope_type = manifest["scope"]["work_type"]
    required_nodes = {
        node for node in all_nodes
        if node == "dq" or node.startswith("dq.")
        or scope_type == "all"
        or (scope_type == "long" and (node == "long" or node.startswith("long.")))
        or (scope_type == "short" and (node == "short" or node.startswith("short.")))
    }
    if set(payload["required_nodes_checked"]) != required_nodes:
        raise GateError("metrics.required_nodes_checked must exactly cover the data-quality and in-scope metric tree")
    if not isinstance(payload["node_statuses"], list):
        raise GateError("metrics.node_statuses must be an array")
    node_status_map = {}
    for row in payload["node_statuses"]:
        if not isinstance(row, dict):
            raise GateError("metrics.node_statuses entries must be objects")
        _required(row, ("node_id", "status", "metric_ids", "evidence", "reason"), "metric node status")
        node_id = row["node_id"]
        if node_id in node_status_map:
            raise GateError("metrics.node_statuses contains duplicate node IDs")
        if row["status"] not in {"MEASURED", "DIAGNOSTICALLY_CHECKED", "UNAVAILABLE", "NOT_APPLICABLE"}:
            raise GateError("metric node status is invalid")
        if not isinstance(row["metric_ids"], list) or not isinstance(row["evidence"], list):
            raise GateError("metric node status metric_ids/evidence must be arrays")
        _nonempty_string(row["reason"], "metric node status reason")
        if row["status"] == "MEASURED":
            if not row["metric_ids"] or not row["evidence"]:
                raise GateError("MEASURED metric nodes require metric IDs and evidence")
            if not set(row["metric_ids"]).issubset(set(payload["computed_metric_ids"])):
                raise GateError("MEASURED node cites an uncomputed metric")
            if not set(row["evidence"]).issubset(set(manifest.get("artifact_hashes", []))):
                raise GateError("MEASURED node cites unknown artifact evidence")
        elif row["metric_ids"]:
            raise GateError("only MEASURED metric nodes may list computed metric IDs")
        node_status_map[node_id] = row
    if set(node_status_map) != required_nodes:
        raise GateError("metrics.node_statuses must exactly cover required_nodes_checked")
    if not isinstance(payload["quality_summary"], dict) or payload["quality_summary"].get("status") not in {"OK", "PARTIAL"}:
        raise GateError("metrics.quality_summary must carry status OK or PARTIAL")
    data_quality = _latest_payload_from_entries(manifest, "data_quality") or {}
    window = _latest_payload_from_entries(manifest, "window_bound") or {}
    if payload["quality_summary"].get("status") != data_quality.get("status"):
        raise GateError("metrics.quality_summary.status differs from qualified data")
    if not isinstance(payload["quality_summary"].get("limitations"), list):
        raise GateError("metrics.quality_summary.limitations must be an array")

    computed_ids = set(payload["computed_metric_ids"])
    fact_ids = set()
    fact_keys = set()
    for index, fact in enumerate(payload["facts"]):
        if not isinstance(fact, dict):
            raise GateError("metrics fact rows must be objects")
        _required(
            fact,
            (
                "metric_id", "value", "unit", "time_grain", "dimensions", "quality_status",
                "authoritative", "source_refs", "source_observations", "calculation",
            ),
            f"metrics.facts[{index}]",
        )
        metric_id = fact["metric_id"]
        if metric_id not in known_metrics:
            raise GateError(f"metrics fact has an unknown metric_id: {metric_id}")
        metadata = known_metrics[metric_id]
        if fact["unit"] != metadata.get("unit") or fact["time_grain"] != metadata.get("time_grain"):
            raise GateError(f"metrics fact unit/time_grain differs from catalog: {metric_id}")
        if not isinstance(fact["dimensions"], dict):
            raise GateError("metrics fact dimensions must be an object")
        missing_dimensions = set(metadata.get("dimensions", [])) - set(fact["dimensions"])
        if missing_dimensions:
            raise GateError(f"metrics fact omits dimensions for {metric_id}: {sorted(missing_dimensions)}")
        fact_key = (metric_id, json.dumps(fact["dimensions"], ensure_ascii=False, sort_keys=True))
        if fact_key in fact_keys:
            raise GateError("duplicate metric fact for the same metric/dimensions")
        fact_keys.add(fact_key)
        fact_ids.add(metric_id)
        parent_node = metadata.get("parent_node")
        parent_status = node_status_map.get(parent_node, {})
        if parent_status.get("status") != "MEASURED" or metric_id not in parent_status.get("metric_ids", []):
            raise GateError(f"metric fact parent node is not MEASURED: {metric_id}")
        if fact["quality_status"] not in {"OK", "PARTIAL"} or not isinstance(fact["authoritative"], bool):
            raise GateError("metrics fact quality_status/authoritative is invalid")
        fact_number = _workflow_number(fact["value"])
        if fact_number is None:
            raise GateError("metrics facts recorded as computed must have finite numeric values")
        refs = fact["source_refs"]
        if not isinstance(refs, list) or not refs or not set(refs).issubset(set(manifest.get("artifact_hashes", []))):
            raise GateError("metrics fact source_refs must cite upstream artifact hashes")
        if manifest.get("chain_head_sha256") not in refs:
            raise GateError("metrics fact source_refs must include the current window artifact")
        observations = fact["source_observations"]
        if not isinstance(observations, list) or not observations:
            raise GateError("metrics facts require frozen source observations")
        observed_values = []
        for observation in observations:
            if not isinstance(observation, dict):
                raise GateError("metric source observations must be objects")
            _required(observation, ("source_role", "source_sha256", "json_pointer", "value"), "metric observation")
            role = observation["source_role"]
            if role == "normalized_latest":
                source_value = data_quality.get("normalized_snapshot")
                expected_hash = data_quality.get("normalized_snapshot_sha256")
            elif role in {"baseline", "previous_snapshot", "latest_snapshot"}:
                ref_label = "baseline" if role == "baseline" else role
                snapshot_ref = window.get(ref_label, {})
                source_value = _load_json_evidence(snapshot_ref.get("source_file", ""), f"metric observation {role}")
                expected_hash = snapshot_ref.get("source_sha256")
            else:
                raise GateError("metric source_role is invalid")
            if observation["source_sha256"] != expected_hash:
                raise GateError("metric observation source hash differs from frozen window/data-quality source")
            actual = _json_pointer(source_value, observation["json_pointer"])
            if not _equivalent_value(actual, observation["value"]):
                raise GateError("metric observation value differs from source")
            observed_values.append(observation["value"])
        calculation = fact["calculation"]
        if not isinstance(calculation, dict):
            raise GateError("metrics fact calculation must be an object")
        _required(calculation, ("mode", "operator", "expression", "input_values"), "metrics fact calculation")
        _nonempty_string(calculation["expression"], "metrics fact calculation.expression")
        inputs = calculation["input_values"]
        if not isinstance(inputs, list) or not inputs:
            raise GateError("metrics fact calculation.input_values must be non-empty")
        if any(_workflow_number(value) is None for value in inputs):
            raise GateError("metrics fact calculation inputs must be finite numbers")
        if len(inputs) != len(observed_values) or any(
            not _equivalent_value(left, right) for left, right in zip(inputs, observed_values)
        ):
            raise GateError("metrics fact calculation inputs differ from source observations")
        numbers = [float(_workflow_number(value)) for value in inputs]
        operator = calculation["operator"]
        if operator == "identity" and len(numbers) == 1:
            recalculated = numbers[0]
        elif operator == "difference" and len(numbers) == 2:
            recalculated = numbers[0] - numbers[1]
        elif operator == "sum":
            recalculated = sum(numbers)
        elif operator == "ratio_percent" and len(numbers) == 2 and numbers[1] != 0:
            recalculated = numbers[0] / numbers[1] * 100
        else:
            raise GateError("metrics fact calculation operator/arity is invalid")
        if not math.isclose(fact_number, recalculated, rel_tol=1e-9, abs_tol=1e-9):
            raise GateError("metrics fact value is not reproduced by its calculation")
        mode = calculation["mode"]
        if mode not in {"source", "derived", "lower_bound"}:
            raise GateError("metrics fact calculation.mode is invalid")
        if mode == "lower_bound" and (fact["authoritative"] is not False or not any(
            "minimum_compatible" in observation["json_pointer"] for observation in observations
        )):
            raise GateError("lower_bound facts must be non-authoritative and cite the lower-bound field")
        if mode != "lower_bound" and any("minimum_compatible" in observation["json_pointer"] for observation in observations):
            raise GateError("minimum compatible values must be labelled calculation.mode=lower_bound")
    if fact_ids != computed_ids:
        raise GateError("metrics.computed_metric_ids must exactly equal metric IDs present in facts")


def _validate_analysis(payload: Mapping[str, Any], manifest: Mapping[str, Any]) -> None:
    _required(
        payload,
        (
            "overall_status", "sample_size", "strong_conclusion", "causal_attribution",
            "metric_tree_coverage", "anomalies", "hypotheses", "evidence_refs",
            "linked_metric_checks", "primary_constraint", "primary_constraint_node",
            "sample_metric_id", "sample_evidence_refs", "anomaly_rule_evidence", "change_assessments",
        ),
        "analysis",
    )
    if payload["overall_status"] not in ANALYSIS_STATUSES:
        raise GateError("analysis.overall_status is outside the controlled vocabulary")
    sample = payload["sample_size"]
    if not isinstance(sample, int) or sample < 0:
        raise GateError("analysis.sample_size must be a non-negative integer")
    qualified_sample = manifest.get("sample_size")
    if isinstance(qualified_sample, int) and sample != qualified_sample:
        raise GateError("analysis.sample_size must equal the qualified sample size")
    if manifest.get("sample_size_qualified") is not True:
        if sample != 0 or payload["sample_metric_id"] != "UNAVAILABLE":
            raise GateError("unavailable sample must be represented as sample_size=0 and sample_metric_id=UNAVAILABLE")
        if payload["overall_status"] not in INSUFFICIENT_STATUSES:
            raise GateError("unavailable sample can only conclude 样本不足/SAMPLE_INSUFFICIENT")
        if payload["causal_attribution"] or payload["strong_conclusion"]:
            raise GateError("unavailable sample forbids causal attribution and strong conclusions")
    elif sample < 30:
        if payload["overall_status"] not in INSUFFICIENT_STATUSES:
            raise GateError("sample <30 can only conclude 样本不足/SAMPLE_INSUFFICIENT")
        if payload["causal_attribution"] or payload["strong_conclusion"]:
            raise GateError("sample <30 forbids causal attribution and strong conclusions")
    elif sample < 100 and payload["strong_conclusion"]:
        raise GateError("sample <100 forbids a strong conclusion")
    if not isinstance(payload["strong_conclusion"], bool) or not isinstance(payload["causal_attribution"], bool):
        raise GateError("analysis strong_conclusion and causal_attribution must be boolean")
    if manifest.get("sample_size_authoritative") is not True and (payload["strong_conclusion"] or payload["causal_attribution"]):
        raise GateError("non-authoritative sample size forbids strong or causal conclusions")
    if payload["causal_attribution"] and manifest["scope"].get("causal_design_verified") is not True:
        raise GateError("observational workflow cannot claim causal attribution")
    metrics = _latest_payload_from_entries(manifest, "metrics") or {}
    coverage = payload["metric_tree_coverage"]
    if not isinstance(coverage, dict) or not isinstance(coverage.get("checked_nodes"), list) or not isinstance(coverage.get("missing_nodes"), list):
        raise GateError("analysis.metric_tree_coverage requires checked_nodes and missing_nodes arrays")
    if not coverage["checked_nodes"]:
        raise GateError("analysis.metric_tree_coverage.checked_nodes cannot be empty")
    if set(coverage["checked_nodes"]) != set(metrics.get("required_nodes_checked", [])):
        raise GateError("analysis.metric_tree_coverage must cover the metric-engine node set")
    expected_missing_nodes = {
        item.get("node_id") for item in metrics.get("node_statuses", [])
        if isinstance(item, dict) and item.get("status") == "UNAVAILABLE"
    }
    if set(coverage["missing_nodes"]) != expected_missing_nodes:
        raise GateError("analysis.metric_tree_coverage.missing_nodes differs from metric node statuses")
    missing_reasons = coverage.get("missing_node_reasons")
    if not isinstance(missing_reasons, dict) or set(missing_reasons) != set(coverage["missing_nodes"]):
        raise GateError("analysis.metric_tree_coverage requires one reason for each missing node")
    for reason in missing_reasons.values():
        _nonempty_string(reason, "analysis missing-node reason")
    if not isinstance(payload["evidence_refs"], list) or not payload["evidence_refs"]:
        raise GateError("analysis.evidence_refs must be non-empty")
    if not set(payload["evidence_refs"]).issubset(set(manifest.get("artifact_hashes", []))) or manifest.get("chain_head_sha256") not in payload["evidence_refs"]:
        raise GateError("analysis.evidence_refs must be upstream artifact hashes including the metrics head")
    if not isinstance(payload["sample_evidence_refs"], list) or not payload["sample_evidence_refs"]:
        raise GateError("analysis.sample_evidence_refs must be non-empty")
    if not set(payload["sample_evidence_refs"]).issubset(set(manifest.get("artifact_hashes", []))):
        raise GateError("analysis.sample_evidence_refs contains unknown artifacts")
    metric_facts = [item for item in metrics.get("facts", []) if isinstance(item, dict)]
    if manifest.get("sample_size_qualified") is True:
        sample_facts = [item for item in metric_facts if item.get("metric_id") == payload["sample_metric_id"]]
        if not sample_facts or not any(_equivalent_value(item.get("value"), sample) for item in sample_facts):
            raise GateError("analysis.sample_metric_id does not reproduce the qualified sample size")
    if not isinstance(payload["anomaly_rule_evidence"], list) or not payload["anomaly_rule_evidence"]:
        raise GateError("analysis.anomaly_rule_evidence must be non-empty")
    if not isinstance(payload["linked_metric_checks"], list) or not payload["linked_metric_checks"]:
        raise GateError("analysis.linked_metric_checks must be non-empty")
    _nonempty_string(payload["primary_constraint"], "analysis.primary_constraint")
    if payload["primary_constraint_node"] not in coverage["checked_nodes"]:
        raise GateError("analysis.primary_constraint_node was not checked in the metric tree")
    if not isinstance(payload["anomalies"], list) or not isinstance(payload["hypotheses"], list):
        raise GateError("analysis.anomalies and hypotheses must be arrays")
    if payload["overall_status"] in {"改善", "恶化", "IMPROVED", "DEGRADED"} and not payload["anomalies"]:
        raise GateError("an improvement/degradation conclusion requires at least one anomaly")
    for anomaly in payload["anomalies"]:
        if not isinstance(anomaly, dict):
            raise GateError("analysis anomaly entries must be objects")
        _required(
            anomaly,
            (
                "metric_id", "baseline", "current", "delta", "direction", "effect_size",
                "baseline_fact", "current_fact", "threshold_method", "threshold_result",
                "evidence_refs", "neighbors_checked",
            ),
            "analysis.anomaly",
        )
        if anomaly["metric_id"] not in set(metrics.get("computed_metric_ids", [])):
            raise GateError("analysis anomaly metric was not computed")
        if anomaly["direction"] not in {"UP", "DOWN", "FLAT", "MIXED"}:
            raise GateError("analysis anomaly direction is invalid")
        selectors = []
        selected_facts = []
        for selector_name in ("baseline_fact", "current_fact"):
            selector = anomaly[selector_name]
            if not isinstance(selector, dict):
                raise GateError("analysis anomaly fact selectors must be objects")
            _required(selector, ("metric_id", "dimensions"), f"analysis anomaly {selector_name}")
            if selector["metric_id"] != anomaly["metric_id"] or not isinstance(selector["dimensions"], dict):
                raise GateError("analysis anomaly selector must identify the anomaly metric and exact dimensions")
            matches = [
                fact for fact in metric_facts
                if fact.get("metric_id") == selector["metric_id"] and fact.get("dimensions") == selector["dimensions"]
            ]
            if len(matches) != 1:
                raise GateError("analysis anomaly selector must resolve to exactly one metric fact")
            selectors.append(selector)
            selected_facts.append(matches[0])
        baseline_number = _workflow_number(selected_facts[0].get("value"))
        current_number = _workflow_number(selected_facts[1].get("value"))
        if baseline_number is None or current_number is None:
            raise GateError("analysis anomaly facts must be numeric")
        if not _equivalent_value(anomaly["baseline"], baseline_number) or not _equivalent_value(anomaly["current"], current_number):
            raise GateError("analysis anomaly baseline/current do not match selected facts")
        expected_delta = current_number - baseline_number
        if not _equivalent_value(anomaly["delta"], expected_delta):
            raise GateError("analysis anomaly delta is not current minus baseline")
        if not _equivalent_value(anomaly["effect_size"], expected_delta):
            raise GateError("analysis anomaly effect_size must be the signed, unit-preserving delta")
        expected_direction = "UP" if expected_delta > 0 else "DOWN" if expected_delta < 0 else "FLAT"
        if anomaly["direction"] != expected_direction:
            raise GateError("analysis anomaly direction contradicts the selected facts")
        _nonempty_string(anomaly["threshold_method"], "analysis anomaly threshold_method")
        if anomaly["threshold_result"] not in {"TRIGGERED", "NOT_TRIGGERED", "INCONCLUSIVE"}:
            raise GateError("analysis anomaly threshold_result is invalid")
        if not anomaly["evidence_refs"] or not anomaly["neighbors_checked"]:
            raise GateError("analysis anomalies require evidence_refs and neighbors_checked")
        if not set(anomaly["evidence_refs"]).issubset(set(payload["evidence_refs"])):
            raise GateError("analysis anomaly evidence must be part of analysis.evidence_refs")
        if not isinstance(anomaly["neighbors_checked"], list) or any(
            neighbor not in set(metrics.get("computed_metric_ids", [])) for neighbor in anomaly["neighbors_checked"]
        ):
            raise GateError("analysis anomaly neighbors_checked must name computed metric IDs")
        linked_ids = {
            item.get("metric_id") for item in payload["linked_metric_checks"] if isinstance(item, dict)
        }
        if not set(anomaly["neighbors_checked"]).issubset(linked_ids):
            raise GateError("analysis anomaly neighbors must also appear in linked_metric_checks")
        if (manifest.get("sample_size_qualified") is not True or sample < 30) and anomaly["threshold_result"] == "TRIGGERED":
            raise GateError("an unqualified or sub-30 sample cannot trigger an anomaly threshold")
    if payload["anomalies"] and not payload["hypotheses"]:
        raise GateError("an observed anomaly requires at least one falsifiable hypothesis")
    catalog = _load_json_evidence(str(CANONICAL_DEFINITIONS["metric_catalog"]), "metric catalog")
    preferred = catalog.get("preferred_direction_by_metric", {})
    improvement_by_metric: dict[str, bool] = {}
    degradation_by_metric: dict[str, bool] = {}
    for anomaly in payload["anomalies"]:
        if anomaly.get("threshold_result") != "TRIGGERED":
            continue
        metric_direction = preferred.get(anomaly["metric_id"])
        observed_direction = anomaly["direction"]
        improvement_by_metric[anomaly["metric_id"]] = (
            (metric_direction == "HIGHER_BETTER" and observed_direction == "UP")
            or (metric_direction == "LOWER_BETTER" and observed_direction == "DOWN")
        )
        degradation_by_metric[anomaly["metric_id"]] = (
            (metric_direction == "HIGHER_BETTER" and observed_direction == "DOWN")
            or (metric_direction == "LOWER_BETTER" and observed_direction == "UP")
        )
    if payload["overall_status"] in {"改善", "IMPROVED"} and not any(improvement_by_metric.values()):
        raise GateError("improvement requires a threshold-triggered anomaly in the metric's preferred direction")
    if payload["overall_status"] in {"恶化", "DEGRADED"} and not any(degradation_by_metric.values()):
        raise GateError("degradation requires a threshold-triggered anomaly against the metric's preferred direction")

    window = _latest_payload_from_entries(manifest, "window_bound") or {}
    window_changes = {
        item.get("change_id"): item for item in window.get("changes", []) if isinstance(item, dict)
    }
    assessments = payload["change_assessments"]
    if not isinstance(assessments, list):
        raise GateError("analysis.change_assessments must be an array")
    assessment_by_id = {}
    for assessment in assessments:
        if not isinstance(assessment, dict):
            raise GateError("analysis.change_assessments entries must be objects")
        _required(
            assessment,
            (
                "change_id", "status", "direction", "coverage_status", "version_status",
                "evaluated_metric_ids", "evidence_refs", "rationale",
            ),
            "analysis change assessment",
        )
        change_id = _nonempty_string(assessment["change_id"], "analysis change assessment.change_id")
        if change_id in assessment_by_id:
            raise GateError("analysis.change_assessments change_id values must be unique")
        if assessment["status"] not in ANALYSIS_STATUSES:
            raise GateError("analysis change assessment status is invalid")
        if assessment["direction"] not in {"UP", "DOWN", "FLAT", "MIXED", "UNKNOWN"}:
            raise GateError("analysis change assessment direction is invalid")
        if not isinstance(assessment["evaluated_metric_ids"], list):
            raise GateError("analysis change assessment evaluated_metric_ids must be an array")
        if not isinstance(assessment["evidence_refs"], list) or not assessment["evidence_refs"]:
            raise GateError("analysis change assessment requires evidence_refs")
        if not set(assessment["evidence_refs"]).issubset(set(payload["evidence_refs"])):
            raise GateError("analysis change assessment cites evidence outside the analysis set")
        _nonempty_string(assessment["rationale"], "analysis change assessment rationale")
        change = window_changes.get(change_id)
        if change is None:
            raise GateError("analysis change assessment references an unknown change")
        if assessment["coverage_status"] != change.get("coverage_status"):
            raise GateError("analysis change assessment coverage differs from deterministic window binding")
        if assessment["version_status"] != change.get("version_status"):
            raise GateError("analysis change assessment version differs from window evidence")
        if not set(assessment["evaluated_metric_ids"]).issubset(set(change.get("target_metric_ids", []))):
            raise GateError("analysis change assessment evaluated metrics escape the change targets")
        if change.get("coverage_status") == "NOT_COVERED":
            if assessment["status"] not in {"数据未覆盖改动", "CHANGE_NOT_COVERED"}:
                raise GateError("a not-covered change must be assessed as 数据未覆盖改动")
            if assessment["direction"] != "UNKNOWN":
                raise GateError("a not-covered change must use UNKNOWN direction")
        elif manifest.get("sample_size_qualified") is not True or sample < 30:
            if assessment["status"] not in INSUFFICIENT_STATUSES | {"样本受自访污染", "SELF_VISIT_CONTAMINATED"}:
                raise GateError("an unqualified or sub-30 change can only be sample-insufficient/contaminated")
        if assessment["status"] in {"改善", "IMPROVED", "恶化", "DEGRADED"}:
            if change.get("coverage_status") != "FULL_DAY_COVERED" or change.get("version_status") != "VERIFIED":
                raise GateError("improvement/degradation requires full-day coverage and verified version evidence")
            target_triggered = [
                item for item in payload["anomalies"]
                if item.get("metric_id") in assessment["evaluated_metric_ids"]
                and item.get("threshold_result") == "TRIGGERED"
            ]
            if not target_triggered:
                raise GateError("improvement/degradation requires a triggered target-metric anomaly")
            signal_by_metric = (
                improvement_by_metric
                if assessment["status"] in {"改善", "IMPROVED"}
                else degradation_by_metric
            )
            if not any(signal_by_metric.get(item["metric_id"]) for item in target_triggered):
                raise GateError("change assessment status contradicts target metric preferred direction")
            observed_directions = {item["direction"] for item in target_triggered}
            expected_assessment_direction = (
                next(iter(observed_directions)) if len(observed_directions) == 1 else "MIXED"
            )
            if assessment["direction"] != expected_assessment_direction:
                raise GateError("change assessment direction does not match its triggered target metrics")
        assessment_by_id[change_id] = assessment
    if set(assessment_by_id) != set(window_changes):
        raise GateError("analysis.change_assessments must assess every and only registered change")
    for hypothesis in payload["hypotheses"]:
        if not isinstance(hypothesis, dict):
            raise GateError("analysis hypothesis entries must be objects")
        _required(
            hypothesis,
            (
                "hypothesis_id", "cause", "predicted_neighbor_pattern", "falsification",
                "text_target_candidate", "evidence_level",
            ),
            "analysis hypothesis",
        )
        if hypothesis["evidence_level"] not in {"OBSERVED", "DERIVED", "ASSOCIATION", "HYPOTHESIS", "CAUSAL"}:
            raise GateError("analysis hypothesis evidence_level is invalid")
    for check in payload["linked_metric_checks"]:
        if not isinstance(check, dict):
            raise GateError("analysis linked_metric_checks entries must be objects")
        _required(check, ("metric_id", "status", "evidence_refs", "finding"), "analysis linked metric check")
        if check["status"] not in {"CHECKED", "UNAVAILABLE", "NOT_APPLICABLE"}:
            raise GateError("analysis linked metric check status is invalid")
        if not isinstance(check["evidence_refs"], list) or not check["evidence_refs"]:
            raise GateError("analysis linked metric checks require evidence_refs")
        _nonempty_string(check["finding"], "analysis linked metric finding")


def _validate_validation(payload: Mapping[str, Any], manifest: Mapping[str, Any]) -> None:
    _required(
        payload,
        (
            "decision", "independent_recalculation", "logic_checks", "method_checks",
            "input_hashes_verified", "validator_independent", "causal_strength_cap", "prohibited_claims",
            "reviewed_analysis_sha256", "missing_nodes_assessed", "recalculation_disagreements",
        ),
        "validation",
    )
    if payload["decision"] not in {"PASS", "RETURN", "BLOCKED"}:
        raise GateError("validation.decision must be PASS, RETURN or BLOCKED")
    if payload["decision"] == "PASS":
        if payload.get("input_hashes_verified") is not True or payload.get("validator_independent") is not True:
            raise GateError("validation PASS requires verified hashes and an independent validator")
        if payload["reviewed_analysis_sha256"] != manifest.get("chain_head_sha256"):
            raise GateError("validation.reviewed_analysis_sha256 must equal the analysis chain head")
        _validate_check_rows(
            payload["logic_checks"], "validation.logic_checks", required_ids=REQUIRED_LOGIC_CHECKS
        )
        _validate_check_rows(
            payload["method_checks"], "validation.method_checks", required_ids=REQUIRED_METHOD_CHECKS
        )
        if any(row["status"] != "PASS" for row in [*payload["logic_checks"], *payload["method_checks"]]):
            raise GateError("validation PASS contradicts a failed/partial check")
        recalculation = payload["independent_recalculation"]
        if not isinstance(recalculation, list) or not recalculation:
            raise GateError("validation PASS requires non-empty independent_recalculation")
        metrics = _latest_payload_from_entries(manifest, "metrics") or {}
        facts = [item for item in metrics.get("facts", []) if isinstance(item, dict)]
        expected_fact_keys = {
            (item.get("metric_id"), json.dumps(item.get("dimensions", {}), ensure_ascii=False, sort_keys=True)): item
            for item in facts
        }
        recalculated_keys = set()
        for row in recalculation:
            if not isinstance(row, dict):
                raise GateError("validation recalculation rows must be objects")
            _required(
                row,
                (
                    "metric_id", "dimensions", "formula", "source_refs", "source_observations",
                    "calculation", "recalculated_value",
                ),
                "validation.recalculation",
            )
            if not row["source_refs"]:
                raise GateError("validation recalculation requires source_refs")
            _nonempty_string(row["formula"], "validation recalculation formula")
            fact_key = (
                row["metric_id"], json.dumps(row["dimensions"], ensure_ascii=False, sort_keys=True)
            )
            if fact_key not in expected_fact_keys:
                raise GateError("validation recalculation does not map to a metric fact")
            if fact_key in recalculated_keys:
                raise GateError("duplicate validation recalculation row")
            recalculated_keys.add(fact_key)
            fact = expected_fact_keys[fact_key]
            if row["formula"] != fact.get("calculation", {}).get("expression"):
                raise GateError("validation formula differs from the frozen metric calculation")
            if row["calculation"] != fact.get("calculation"):
                raise GateError("validation calculation differs from the frozen metric calculation")
            if row["source_observations"] != fact.get("source_observations"):
                raise GateError("validation source observations differ from fact provenance")
            if row["source_refs"] != fact.get("source_refs"):
                raise GateError("validation recalculation source_refs must exactly equal fact provenance")
            data_quality = _latest_payload_from_entries(manifest, "data_quality") or {}
            window = _latest_payload_from_entries(manifest, "window_bound") or {}
            independently_recalculated = _recalculate_fact_from_frozen_sources(fact, data_quality, window)
            if not _equivalent_value(row["recalculated_value"], independently_recalculated):
                raise GateError("validation recalculated value is not reproduced from frozen sources")
            if not _equivalent_value(independently_recalculated, fact.get("value")):
                raise GateError("validation independently recalculated value differs from metric fact")
        if recalculated_keys != set(expected_fact_keys):
            raise GateError("validation must independently recalculate every metric fact")
        if not isinstance(payload["recalculation_disagreements"], list) or payload["recalculation_disagreements"]:
            raise GateError("validation PASS requires an explicit empty recalculation_disagreements array")
        analysis = _latest_payload_from_entries(manifest, "analysis")
        missing_nodes = analysis.get("metric_tree_coverage", {}).get("missing_nodes", []) if analysis else []
        assessments = payload["missing_nodes_assessed"]
        if not isinstance(assessments, list):
            raise GateError("validation.missing_nodes_assessed must be an array")
        assessed_ids = set()
        for assessment in assessments:
            if not isinstance(assessment, dict):
                raise GateError("validation missing-node assessments must be objects")
            _required(assessment, ("node_id", "disposition", "reason"), "missing-node assessment")
            if assessment["disposition"] not in {"NON_BLOCKING_LIMITATION", "BLOCKING"}:
                raise GateError("validation missing-node disposition is invalid")
            _nonempty_string(assessment["reason"], "validation missing-node reason")
            assessed_ids.add(assessment["node_id"])
        if assessed_ids != set(missing_nodes):
            raise GateError("validation must assess every and only missing metric-tree node")
        if any(item["disposition"] == "BLOCKING" for item in assessments):
            raise GateError("validation PASS contradicts a BLOCKING missing node")
    if payload["causal_strength_cap"] != _maximum_strength_cap(manifest):
        raise GateError("validation.causal_strength_cap exceeds or differs from the deterministic sample/design cap")
    if not isinstance(payload["prohibited_claims"], list) or not payload["prohibited_claims"]:
        raise GateError("validation.prohibited_claims must be a non-empty array")
    if payload["decision"] == "RETURN":
        _required(payload, ("earliest_fault_state", "reason"), "validation RETURN")
        _validate_return_metadata(payload, "validation RETURN")


def _resolve_project_target(raw: str) -> pathlib.Path:
    path = pathlib.Path(raw)
    resolved = (path if path.is_absolute() else PROJECT_ROOT / path).resolve(strict=False)
    try:
        resolved.relative_to(PROJECT_ROOT.resolve(strict=False))
    except ValueError as exc:
        raise GateError("text proposal target escapes the project root") from exc
    return resolved


def _validate_text_diagnosis(payload: Mapping[str, Any], manifest: Mapping[str, Any]) -> None:
    _required(
        payload,
        (
            "diagnosis_status", "online_version_status", "online_version_evidence",
            "body_modified", "hypotheses_checked", "proposals",
        ),
        "text_diagnosis",
    )
    if payload["diagnosis_status"] not in {"PROPOSAL_READY", "NOT_APPLICABLE", "VERSION_UNVERIFIED"}:
        raise GateError("text_diagnosis.diagnosis_status is invalid")
    if payload["online_version_status"] not in {"VERIFIED", "UNVERIFIED", "MIXED", "NOT_APPLICABLE"}:
        raise GateError("text_diagnosis.online_version_status is invalid")
    if payload["body_modified"] is not False:
        raise GateError("text diagnosis is read-only; body_modified must be false")
    if not isinstance(payload["online_version_evidence"], list):
        raise GateError("text_diagnosis.online_version_evidence must be an array")
    if not isinstance(payload["proposals"], list):
        raise GateError("text_diagnosis.proposals must be an array")
    if not payload["proposals"]:
        if payload["diagnosis_status"] not in {"NOT_APPLICABLE", "VERSION_UNVERIFIED"}:
            raise GateError("an empty proposal list requires NOT_APPLICABLE or VERSION_UNVERIFIED")
        _nonempty_string(payload.get("not_applicable_reason"), "text_diagnosis.not_applicable_reason")
        return
    if payload["diagnosis_status"] != "PROPOSAL_READY" or payload["online_version_status"] != "VERIFIED":
        raise GateError("text proposals require PROPOSAL_READY and a VERIFIED online version")
    if not payload["online_version_evidence"]:
        raise GateError("text proposals require non-empty online_version_evidence")
    for evidence in payload["online_version_evidence"]:
        if not isinstance(evidence, dict):
            raise GateError("online version evidence entries must be objects")
        _required(
            evidence,
            ("source", "checked_at", "work_id", "version_sha256", "evidence_files", "evidence_hashes"),
            "online version evidence",
        )
        if str(evidence["work_id"]) != str(manifest["scope"]["work_id"]):
            raise GateError("online version evidence work_id differs from run scope")
        _iso_datetime(evidence["checked_at"], "online version evidence.checked_at")
        if not isinstance(evidence["version_sha256"], str) or not SHA256_RE.fullmatch(evidence["version_sha256"]):
            raise GateError("online version evidence version_sha256 is invalid")
        _validate_source_files(
            evidence["evidence_files"], evidence["evidence_hashes"], "online_version_evidence"
        )
    if not isinstance(payload["hypotheses_checked"], list) or not payload["hypotheses_checked"]:
        raise GateError("text proposals require checked hypotheses")
    analysis = _latest_payload_from_entries(manifest, "analysis") or {}
    validation = _latest_payload_from_entries(manifest, "validation") or {}
    if validation.get("decision") != "PASS":
        raise GateError("text diagnosis requires validation PASS")
    analysis_hypotheses = {
        item.get("hypothesis_id") for item in analysis.get("hypotheses", []) if isinstance(item, dict)
    }
    checked_hypothesis_ids = set()
    for hypothesis in payload["hypotheses_checked"]:
        if not isinstance(hypothesis, dict):
            raise GateError("text hypotheses_checked entries must be objects")
        _required(hypothesis, ("hypothesis_id", "verdict", "text_evidence_ids", "reason"), "checked hypothesis")
        if hypothesis["hypothesis_id"] not in analysis_hypotheses:
            raise GateError("text diagnosis checked an unknown analyst hypothesis")
        if hypothesis["verdict"] not in {"SUPPORTED", "NOT_SUPPORTED", "INCONCLUSIVE"}:
            raise GateError("checked hypothesis verdict is invalid")
        if not isinstance(hypothesis["text_evidence_ids"], list):
            raise GateError("checked hypothesis text_evidence_ids must be an array")
        _nonempty_string(hypothesis["reason"], "checked hypothesis reason")
        checked_hypothesis_ids.add(hypothesis["hypothesis_id"])
    if checked_hypothesis_ids != analysis_hypotheses:
        raise GateError("text diagnosis must assess every analyst hypothesis")
    catalog = _load_json_evidence(str(CANONICAL_DEFINITIONS["metric_catalog"]), "metric catalog")
    known_metric_ids = {
        item.get("id") for item in catalog.get("metrics", []) if isinstance(item, dict)
    }
    seen = set()
    seen_evidence_ids = set()
    for proposal in payload["proposals"]:
        if not isinstance(proposal, dict):
            raise GateError("every text proposal must be an object")
        _required(
            proposal,
            (
                "proposal_id", "action", "target", "target_sha256_before", "text_evidence",
                "data_trigger", "change_intent", "reader_mechanism", "expected_metric",
                "single_variable", "counterfactual", "do_not_change", "guardrails", "validation_plan",
            ),
            "text proposal",
        )
        proposal_id = proposal["proposal_id"]
        if not isinstance(proposal_id, str) or not proposal_id or proposal_id in seen:
            raise GateError("proposal_id must be unique and non-empty")
        seen.add(proposal_id)
        if proposal["action"] not in {"modify_text", "modify_packaging", "publish"}:
            raise GateError("text proposal action is invalid")
        _nonempty_string(proposal["target"], "text proposal target")
        if not isinstance(proposal["target_sha256_before"], str) or not (
            SHA256_RE.fullmatch(proposal["target_sha256_before"]) or proposal["target_sha256_before"] == "MISSING"
        ):
            raise GateError("text proposal target_sha256_before is invalid")
        if proposal["action"] == "modify_text":
            target = _resolve_project_target(proposal["target"])
            if not target.is_file():
                raise GateError("modify_text target must be an existing project file")
            if sha256_file(target) != proposal["target_sha256_before"]:
                raise IntegrityError("text proposal target_sha256_before differs from current target")
            if proposal["target_sha256_before"] not in {
                evidence.get("version_sha256") for evidence in payload["online_version_evidence"]
                if isinstance(evidence, dict)
            }:
                raise GateError("modify_text target hash is not confirmed by online_version_evidence")
        if not isinstance(proposal["text_evidence"], list) or not proposal["text_evidence"]:
            raise GateError("each proposal requires exact text_evidence")
        for evidence in proposal["text_evidence"]:
            if not isinstance(evidence, dict):
                raise GateError("text_evidence entries must be objects")
            _required(
                evidence,
                ("evidence_id", "path", "path_sha256", "location", "quote", "observation"),
                "text_evidence",
            )
            evidence_id = _nonempty_string(evidence["evidence_id"], "text_evidence.evidence_id")
            if evidence_id in seen_evidence_ids:
                raise GateError("text_evidence.evidence_id must be unique")
            seen_evidence_ids.add(evidence_id)
            evidence_path = _resolve_project_target(_nonempty_string(evidence["path"], "text_evidence.path"))
            if not evidence_path.is_file() or sha256_file(evidence_path) != evidence["path_sha256"]:
                raise IntegrityError("text evidence file is missing or its hash differs")
            quote = _nonempty_string(evidence["quote"], "text_evidence.quote")
            if quote not in evidence_path.read_text(encoding="utf-8"):
                raise GateError("text evidence quote is not present in the frozen file")
            _nonempty_string(evidence["location"], "text_evidence.location")
            _nonempty_string(evidence["observation"], "text_evidence.observation")
        if not isinstance(proposal["data_trigger"], dict):
            raise GateError("text proposal data_trigger must be an object")
        _required(proposal["data_trigger"], ("metric_ids", "analysis_evidence_refs", "hypothesis_ids"), "data_trigger")
        if not isinstance(proposal["data_trigger"]["metric_ids"], list) or not proposal["data_trigger"]["metric_ids"]:
            raise GateError("text proposal data_trigger.metric_ids must be non-empty")
        if not set(proposal["data_trigger"]["metric_ids"]).issubset(known_metric_ids):
            raise GateError("text proposal data_trigger contains unknown metrics")
        if not set(proposal["data_trigger"]["hypothesis_ids"]).issubset(analysis_hypotheses):
            raise GateError("text proposal data_trigger contains unknown hypotheses")
        if not set(proposal["data_trigger"]["analysis_evidence_refs"]).issubset(set(analysis.get("evidence_refs", []))):
            raise GateError("text proposal data_trigger cites unknown analysis evidence")
        _nonempty_string(proposal["change_intent"], "text proposal change_intent")
        _nonempty_string(proposal["reader_mechanism"], "text proposal reader_mechanism")
        _nonempty_string(proposal["expected_metric"], "text proposal expected_metric")
        if proposal["expected_metric"] not in known_metric_ids:
            raise GateError("text proposal expected_metric is not in the metric catalog")
        if proposal["single_variable"] is not True:
            raise GateError("text proposal must be a single-variable experiment")
        _nonempty_string(proposal["counterfactual"], "text proposal counterfactual")
        if not isinstance(proposal["do_not_change"], list) or not proposal["do_not_change"]:
            raise GateError("text proposal do_not_change must be non-empty")
        if not isinstance(proposal["guardrails"], list) or not proposal["guardrails"]:
            raise GateError("text proposal guardrails must be non-empty")
        if not isinstance(proposal["validation_plan"], dict) or not proposal["validation_plan"]:
            raise GateError("text proposal validation_plan must be a non-empty object")
        _required(
            proposal["validation_plan"],
            (
                "main_metric", "guard_metrics", "minimum_sample", "earliest_data_until",
                "decision_rule", "rollback_rule",
            ),
            "text proposal validation_plan",
        )
        if proposal["validation_plan"]["main_metric"] != proposal["expected_metric"]:
            raise GateError("validation_plan.main_metric must equal expected_metric")
        if not isinstance(proposal["validation_plan"]["guard_metrics"], list) or not proposal["validation_plan"]["guard_metrics"]:
            raise GateError("validation_plan.guard_metrics must be non-empty")
        if not isinstance(proposal["validation_plan"]["minimum_sample"], int) or proposal["validation_plan"]["minimum_sample"] < 30:
            raise GateError("validation_plan.minimum_sample must be at least the internal 30-reader attribution floor")
        _iso_date(proposal["validation_plan"]["earliest_data_until"], "validation_plan.earliest_data_until")
        _nonempty_string(proposal["validation_plan"]["decision_rule"], "validation_plan.decision_rule")
        _nonempty_string(proposal["validation_plan"]["rollback_rule"], "validation_plan.rollback_rule")


def _validate_supervision(payload: Mapping[str, Any], manifest: Mapping[str, Any]) -> None:
    _required(
        payload,
        (
            "mode", "decision", "stage_checks", "novel_edits_made", "artifact_hashes_verified",
            "role_separation_verified", "reviewed_chain_head_sha256", "accepted_findings",
            "rejected_findings", "report_claims", "final_strength_cap",
        ),
        "supervision",
    )
    if payload["mode"] != "OBSERVE_ONLY" or payload["novel_edits_made"] is not False:
        raise GateError("supervisor must be OBSERVE_ONLY and must not edit the novel")
    if payload["decision"] not in {"PASS", "RETURN", "BLOCKED"}:
        raise GateError("supervision.decision must be PASS, RETURN or BLOCKED")
    if payload["decision"] == "PASS":
        if payload["artifact_hashes_verified"] is not True or payload["role_separation_verified"] is not True:
            raise GateError("supervision PASS requires hash and role-separation verification")
        if payload["reviewed_chain_head_sha256"] != manifest.get("chain_head_sha256"):
            raise GateError("supervision.reviewed_chain_head_sha256 must equal the text-diagnosis head")
        _validate_check_rows(payload["stage_checks"], "supervision.stage_checks", required_ids=REQUIRED_SUPERVISION_GATES)
        if any(row["status"] != "PASS" for row in payload["stage_checks"]):
            raise GateError("supervision PASS contradicts a failed/partial gate")
        artifacts_by_kind = {
            entry.get("kind"): entry.get("sha256") for entry in manifest.get("artifacts", [])
            if isinstance(entry, dict)
        }
        required_gate_artifacts = {
            "G1": {artifacts_by_kind.get("raw_capture")},
            "G2": {artifacts_by_kind.get("data_quality")},
            "G3": {artifacts_by_kind.get("window_bound")},
            "G4": {artifacts_by_kind.get("metrics")},
            "G5": {artifacts_by_kind.get("analysis")},
            "G6": {artifacts_by_kind.get("validation")},
            "G7": {artifacts_by_kind.get("text_diagnosis")},
            "G8": set(manifest.get("artifact_hashes", [])),
        }
        for row in payload["stage_checks"]:
            evidence_hashes = {value for value in row["evidence"] if isinstance(value, str) and SHA256_RE.fullmatch(value)}
            if not required_gate_artifacts[row["check_id"]].issubset(evidence_hashes):
                raise GateError(f"supervision {row['check_id']} lacks its required artifact evidence")
        for kind, expected_producer in EXPECTED_PRODUCERS.items():
            if kind not in KIND_FLOW or kind == "supervision":
                continue
            actual = [
                entry.get("producer") for entry in manifest.get("artifacts", []) if entry.get("kind") == kind
            ]
            if not actual or any(value != expected_producer for value in actual):
                raise GateError(f"supervision role separation failed for {kind}")
    if not isinstance(payload["accepted_findings"], list) or not isinstance(payload["rejected_findings"], list):
        raise GateError("supervision accepted/rejected findings must be arrays")
    if payload["decision"] == "PASS" and not payload["accepted_findings"]:
        raise GateError("supervision PASS requires at least one accepted finding")
    for label in ("accepted_findings", "rejected_findings"):
        seen_ids = set()
        for finding in payload[label]:
            if not isinstance(finding, dict):
                raise GateError(f"supervision {label} entries must be objects")
            _required(finding, ("finding_id", "source_stage", "claim", "evidence_refs", "reason"), f"supervision {label}")
            finding_id = _nonempty_string(finding["finding_id"], f"supervision {label}.finding_id")
            if finding_id in seen_ids:
                raise GateError(f"duplicate finding_id in supervision {label}")
            seen_ids.add(finding_id)
            if finding["source_stage"] not in {"analysis", "validation", "text_diagnosis"}:
                raise GateError("supervision finding source_stage is invalid")
            _nonempty_string(finding["claim"], "supervision finding claim")
            _nonempty_string(finding["reason"], "supervision finding reason")
            if not isinstance(finding["evidence_refs"], list) or not finding["evidence_refs"]:
                raise GateError("supervision findings require evidence_refs")
            if not set(finding["evidence_refs"]).issubset(set(manifest.get("artifact_hashes", []))):
                raise GateError("supervision finding cites unknown evidence")
    if payload["final_strength_cap"] != _maximum_strength_cap(manifest):
        raise GateError("supervision.final_strength_cap differs from deterministic sample/design cap")
    if not isinstance(payload["report_claims"], list) or not payload["report_claims"]:
        raise GateError("supervision.report_claims must be non-empty")
    allowed_strengths = {
        "OBSERVED_ONLY": {"OBSERVED"},
        "DIRECTIONAL_ONLY": {"OBSERVED", "DERIVED", "DIRECTIONAL"},
        "NON_CAUSAL_ASSOCIATION": {"OBSERVED", "DERIVED", "DIRECTIONAL", "ASSOCIATION"},
        "CAUSAL_ALLOWED": {"OBSERVED", "DERIVED", "DIRECTIONAL", "ASSOCIATION", "CAUSAL"},
    }[payload["final_strength_cap"]]
    for claim in payload["report_claims"]:
        if not isinstance(claim, dict):
            raise GateError("supervision report_claims entries must be objects")
        _required(claim, ("claim_id", "text", "strength", "evidence_refs"), "supervision report claim")
        _nonempty_string(claim["claim_id"], "supervision report claim_id")
        _nonempty_string(claim["text"], "supervision report claim text")
        if claim["strength"] not in allowed_strengths:
            raise GateError("supervision report claim exceeds the final strength cap")
        if not isinstance(claim["evidence_refs"], list) or not claim["evidence_refs"]:
            raise GateError("supervision report claims require evidence_refs")
        if not set(claim["evidence_refs"]).issubset(set(manifest.get("artifact_hashes", []))):
            raise GateError("supervision report claim cites unknown evidence")
    if payload["decision"] == "RETURN":
        _required(payload, ("earliest_fault_state", "reason"), "supervision RETURN")
        _validate_return_metadata(payload, "supervision RETURN")


def _latest_payload_from_entries(manifest: Mapping[str, Any], kind: str) -> Optional[Mapping[str, Any]]:
    """Replay helper populated temporarily by verify/record callers."""
    cache = manifest.get("_payload_cache")
    if isinstance(cache, dict) and isinstance(cache.get(kind), dict):
        return cache[kind]
    return None


def _latest_payload(runs_root: pathlib.Path, run_id: str, manifest: Mapping[str, Any], kind: str) -> Optional[Dict[str, Any]]:
    entries = [entry for entry in manifest["artifacts"] if entry["kind"] == kind]
    if not entries:
        return None
    path = _run_dir(runs_root, run_id) / entries[-1]["file"]
    return json.loads(path.read_text(encoding="utf-8"))["payload"]


def _artifact_filename(kind: str, attempt: int) -> str:
    prefix = KIND_FLOW.get(kind, ("", "", "90"))[2]
    return f"{prefix}_{kind}.attempt-{attempt:02d}.json"


def _append_artifact(
    runs_root: pathlib.Path,
    run_id: str,
    manifest: Dict[str, Any],
    *,
    kind: str,
    payload: Any,
    producer: str,
) -> Dict[str, Any]:
    attempt = int(manifest["attempts"].get(kind, 0)) + 1
    filename = _artifact_filename(kind, attempt)
    prior = manifest["chain_head_sha256"]
    envelope = {
        "schema_version": 1,
        "run_id": run_id,
        "kind": kind,
        "attempt": attempt,
        "created_at": utc_now(),
        "producer": producer,
        "prior_artifact_sha256": prior,
        "payload_sha256": sha256_bytes(canonical_bytes(payload)),
        "payload": payload,
    }
    data = canonical_bytes(envelope)
    digest = sha256_bytes(data)
    path = _run_dir(runs_root, run_id) / filename
    atomic_create_bytes(path, data)
    entry = {
        "kind": kind,
        "attempt": attempt,
        "file": filename,
        "sha256": digest,
        "prior_sha256": prior,
        "created_at": envelope["created_at"],
        "producer": producer,
    }
    manifest["attempts"][kind] = attempt
    manifest["artifacts"].append(entry)
    manifest["artifact_hashes"].append(digest)
    manifest["chain_head_sha256"] = digest
    return entry


def _validate_return_request(manifest: Mapping[str, Any], to_state: str) -> None:
    current = manifest["state"]
    if current in TERMINAL_STATES:
        raise GateError(f"cannot RETURN from terminal state {current}")
    if to_state not in RETURNABLE_STATES:
        raise GateError(f"invalid RETURN target: {to_state}")
    if _state_index(to_state) >= _state_index(current):
        raise GateError(f"RETURN target {to_state} must precede current state {current}")


def _validate_return_metadata(payload: Mapping[str, Any], label: str) -> None:
    _required(
        payload,
        ("root_cause_id", "error_code", "rejected_finding_ids", "repair_requirements"),
        label,
    )
    _nonempty_string(payload["root_cause_id"], f"{label}.root_cause_id")
    _nonempty_string(payload["error_code"], f"{label}.error_code")
    if not isinstance(payload["rejected_finding_ids"], list):
        raise GateError(f"{label}.rejected_finding_ids must be an array")
    if not isinstance(payload["repair_requirements"], list) or not payload["repair_requirements"]:
        raise GateError(f"{label}.repair_requirements must be non-empty")


def _apply_return(manifest: Dict[str, Any], to_state: str, reason: str, root_cause_id: str) -> str:
    _validate_return_request(manifest, to_state)
    counts = manifest.setdefault("return_counts_by_root_cause", {})
    current_count = int(counts.get(root_cause_id, 0))
    if manifest.get("return_count", 0) >= FIXED_MAX_RETURNS or current_count >= FIXED_MAX_RETURNS:
        _set_state(manifest, "BLOCKED")
        manifest["blocked_reason"] = f"RETURN_LIMIT_EXCEEDED[global_or_{root_cause_id}]: {reason}"
        return "BLOCKED"
    counts[root_cause_id] = current_count + 1
    manifest["return_count"] += 1
    _set_state(manifest, to_state)
    manifest["blocked_reason"] = None
    manifest["supervisor_verdict"] = None
    return "RETURN"


def record_artifact(
    runs_root: pathlib.Path,
    run_id: str,
    *,
    kind: str,
    payload: Mapping[str, Any],
    producer: str,
    expected_revision: int,
) -> Dict[str, Any]:
    if kind not in KIND_FLOW:
        raise WorkflowError(f"unknown record kind: {kind}")
    _validate_producer(kind, producer)
    with run_lock(runs_root, run_id):
        manifest = load_manifest(runs_root, run_id)
        _assert_revision(manifest, expected_revision)
        verify_integrity(runs_root, run_id, manifest)
        expected_state, target_state, _ = KIND_FLOW[kind]
        if manifest["state"] != expected_state:
            raise GateError(f"illegal transition: {kind} requires {expected_state}, current {manifest['state']}")

        effective_quality: Optional[str] = None
        if kind == "raw_capture":
            effective_quality = _validate_raw_capture(payload, manifest)
        elif kind == "data_quality":
            _validate_input_refs(payload, manifest, kind)
            quality_manifest = dict(manifest)
            quality_manifest["_payload_cache"] = {
                "raw_capture": _latest_payload(runs_root, run_id, manifest, "raw_capture") or {}
            }
            effective_quality = _validate_data_quality(payload, quality_manifest)
        elif kind == "window_bound":
            _validate_input_refs(payload, manifest, kind)
            window_manifest = dict(manifest)
            window_manifest["_payload_cache"] = {
                "raw_capture": _latest_payload(runs_root, run_id, manifest, "raw_capture") or {}
            }
            _validate_window(payload, window_manifest)
        elif kind == "metrics":
            _validate_input_refs(payload, manifest, kind)
            metrics_manifest = dict(manifest)
            metrics_manifest["_payload_cache"] = {
                "data_quality": _latest_payload(runs_root, run_id, manifest, "data_quality") or {},
                "window_bound": _latest_payload(runs_root, run_id, manifest, "window_bound") or {},
            }
            _validate_metrics(payload, metrics_manifest)
        elif kind == "analysis":
            _validate_input_refs(payload, manifest, kind)
            analysis_manifest = dict(manifest)
            analysis_manifest["_payload_cache"] = {
                "metrics": _latest_payload(runs_root, run_id, manifest, "metrics") or {},
                "window_bound": _latest_payload(runs_root, run_id, manifest, "window_bound") or {},
            }
            _validate_analysis(payload, analysis_manifest)
        elif kind == "validation":
            _validate_input_refs(payload, manifest, kind)
            validation_manifest = dict(manifest)
            validation_manifest["_payload_cache"] = {
                "analysis": _latest_payload(runs_root, run_id, manifest, "analysis") or {},
                "metrics": _latest_payload(runs_root, run_id, manifest, "metrics") or {},
                "data_quality": _latest_payload(runs_root, run_id, manifest, "data_quality") or {},
                "window_bound": _latest_payload(runs_root, run_id, manifest, "window_bound") or {},
            }
            _validate_validation(payload, validation_manifest)
        elif kind == "text_diagnosis":
            _validate_input_refs(payload, manifest, kind)
            text_manifest = dict(manifest)
            text_manifest["_payload_cache"] = {
                "analysis": _latest_payload(runs_root, run_id, manifest, "analysis") or {},
                "validation": _latest_payload(runs_root, run_id, manifest, "validation") or {},
            }
            _validate_text_diagnosis(payload, text_manifest)
        elif kind == "supervision":
            _validate_input_refs(payload, manifest, kind)
            _validate_supervision(payload, manifest)

        if kind in {"validation", "supervision"} and payload.get("decision") == "RETURN":
            _validate_return_request(manifest, payload["earliest_fault_state"])

        mutable = copy.deepcopy(manifest)
        entry = _append_artifact(runs_root, run_id, mutable, kind=kind, payload=dict(payload), producer=producer)
        event = f"RECORD_{kind.upper()}"
        detail: Dict[str, Any] = {"artifact": entry["file"], "artifact_sha256": entry["sha256"]}

        if kind in {"raw_capture", "data_quality"}:
            assert effective_quality is not None
            mutable["quality_status"] = effective_quality
            mutable["usable_fields"] = sorted(set(payload.get("usable_fields", [])))
            if kind == "data_quality":
                mutable["sample_size"] = payload["sample_size"]
                mutable["sample_size_qualified"] = payload["sample_size_qualified"]
                mutable["sample_size_authoritative"] = payload["sample_size_authoritative"]
            if effective_quality in FATAL_QUALITY:
                _set_state(mutable, "BLOCKED")
                mutable["blocked_reason"] = effective_quality
                event = f"QUALITY_BLOCK_{effective_quality}"
            else:
                _set_state(mutable, target_state)
        elif kind == "validation":
            decision = payload["decision"]
            if decision == "PASS":
                _set_state(mutable, target_state)
            elif decision == "BLOCKED":
                _set_state(mutable, "BLOCKED")
                mutable["blocked_reason"] = payload.get("reason", "VALIDATION_BLOCKED")
            else:
                _validate_return_metadata(payload, "validation RETURN")
                outcome = _apply_return(
                    mutable, payload["earliest_fault_state"], payload["reason"], payload["root_cause_id"]
                )
                event = "RETURN" if outcome == "RETURN" else "RETURN_LIMIT_BLOCKED"
                detail.update({"to_state": mutable["state"], "reason": payload["reason"]})
        elif kind == "supervision":
            decision = payload["decision"]
            mutable["supervisor_verdict"] = decision
            if decision == "PASS":
                _set_state(mutable, target_state)
            elif decision == "BLOCKED":
                _set_state(mutable, "BLOCKED")
                mutable["blocked_reason"] = payload.get("reason", "SUPERVISION_BLOCKED")
            else:
                _validate_return_metadata(payload, "supervision RETURN")
                outcome = _apply_return(
                    mutable, payload["earliest_fault_state"], payload["reason"], payload["root_cause_id"]
                )
                event = "RETURN" if outcome == "RETURN" else "RETURN_LIMIT_BLOCKED"
                detail.update({"to_state": mutable["state"], "reason": payload["reason"]})
        else:
            _set_state(mutable, target_state)

        _commit_manifest(_manifest_path(runs_root, run_id), mutable, event, detail)
        return mutable


def return_run(
    runs_root: pathlib.Path,
    run_id: str,
    *,
    to_state: str,
    reason: str,
    root_cause_id: str,
    error_code: str,
    rejected_finding_ids: Sequence[str],
    repair_requirements: Sequence[str],
    producer: str,
    expected_revision: int,
) -> Dict[str, Any]:
    if not reason.strip():
        raise GateError("RETURN requires a non-empty reason")
    if producer not in {"story-data-method-validator", "story-data-supervisor"}:
        raise GateError("RETURN may only be requested by validator or supervisor")
    return_payload = {
        "to_state": to_state,
        "reason": reason,
        "root_cause_id": root_cause_id,
        "error_code": error_code,
        "rejected_finding_ids": list(rejected_finding_ids),
        "repair_requirements": list(repair_requirements),
    }
    _validate_return_metadata(return_payload, "return")
    with run_lock(runs_root, run_id):
        manifest = load_manifest(runs_root, run_id)
        _assert_revision(manifest, expected_revision)
        verify_integrity(runs_root, run_id, manifest)
        return_payload["input_artifact_hashes"] = [manifest["chain_head_sha256"]]
        _validate_return_request(manifest, to_state)
        mutable = copy.deepcopy(manifest)
        expected_state = "ANALYZED" if producer == "story-data-method-validator" else "TEXT_DIAGNOSED"
        if manifest["state"] != expected_state:
            raise GateError(f"{producer} may RETURN only from {expected_state}")
        entry = _append_artifact(runs_root, run_id, mutable, kind="return", payload=return_payload, producer=producer)
        outcome = _apply_return(mutable, to_state, reason, root_cause_id)
        _commit_manifest(
            _manifest_path(runs_root, run_id),
            mutable,
            "RETURN" if outcome == "RETURN" else "RETURN_LIMIT_BLOCKED",
            {"artifact": entry["file"], "to_state": mutable["state"], "reason": reason},
        )
        return mutable


def complete_run(
    runs_root: pathlib.Path,
    run_id: str,
    *,
    report_text: str,
    producer: str,
    expected_revision: int,
) -> Dict[str, Any]:
    if not report_text.strip():
        raise GateError("report cannot be empty")
    _validate_producer("report", producer)
    with run_lock(runs_root, run_id):
        manifest = load_manifest(runs_root, run_id)
        _assert_revision(manifest, expected_revision)
        verify_integrity(runs_root, run_id, manifest)
        if manifest["state"] != "SUPERVISED" or manifest.get("supervisor_verdict") != "PASS":
            raise GateError("only an observe-only supervisor PASS can advance to REPORT_COMPLETE")
        supervision = _latest_payload(runs_root, run_id, manifest, "supervision") or {}
        report_claims = supervision.get("report_claims", [])
        missing_claims = [
            claim.get("claim_id") for claim in report_claims
            if isinstance(claim, dict) and claim.get("text") not in report_text
        ]
        if missing_claims:
            raise GateError(f"report omits supervisor-approved claims: {missing_claims}")
        for required_section in ("数据截止日", "结论强度", "关键指标", "瓶颈", "下一步", "证据哈希"):
            if required_section not in report_text:
                raise GateError(f"report missing required section: {required_section}")
        if supervision.get("final_strength_cap") not in report_text:
            raise GateError("report must state the supervisor final strength cap verbatim")
        mutable = copy.deepcopy(manifest)
        payload = {
            "format": "markdown", "report": report_text,
            "approved_claim_ids": [claim.get("claim_id") for claim in report_claims if isinstance(claim, dict)],
            "input_artifact_hashes": [manifest["chain_head_sha256"]],
        }
        entry = _append_artifact(runs_root, run_id, mutable, kind="report", payload=payload, producer=producer)
        _set_state(mutable, "REPORT_COMPLETE")
        _commit_manifest(
            _manifest_path(runs_root, run_id), mutable, "REPORT_COMPLETE",
            {"artifact": entry["file"], "artifact_sha256": entry["sha256"]},
        )
        return mutable


def _proposal_ids(runs_root: pathlib.Path, run_id: str, manifest: Mapping[str, Any]) -> set:
    payload = _latest_payload(runs_root, run_id, manifest, "text_diagnosis") or {}
    return {item.get("proposal_id") for item in payload.get("proposals", []) if isinstance(item, dict)}


def _validate_authorization_payload(authorization: Mapping[str, Any]) -> None:
    _required(
        authorization,
        (
            "decision", "authorized_by", "user_confirmation", "user_event_id", "user_message_sha256",
            "authorization_nonce", "proposal_ids", "authorized_scope", "authorized_actions", "confirmed_at",
            "attestation_status",
        ),
        "authorization",
    )
    if authorization["decision"] not in {"APPROVED", "REJECTED"}:
        raise GateError("authorization.decision must be APPROVED or REJECTED")
    if authorization["authorized_by"] != "user":
        raise GateError("authorization.authorized_by must be user")
    if authorization["attestation_status"] != "UNATTESTED_PROCEDURAL":
        raise GateError("this runtime can record only UNATTESTED_PROCEDURAL authorization")
    if not isinstance(authorization["user_message_sha256"], str) or not SHA256_RE.fullmatch(authorization["user_message_sha256"]):
        raise GateError("authorization.user_message_sha256 must be sha256")
    _nonempty_string(authorization["user_event_id"], "authorization.user_event_id")
    if not isinstance(authorization["authorization_nonce"], str) or not SHA256_RE.fullmatch(authorization["authorization_nonce"]):
        raise GateError("authorization.authorization_nonce must be sha256")
    if not isinstance(authorization["proposal_ids"], list) or not authorization["proposal_ids"]:
        raise GateError("authorization must list proposal_ids")
    if len(set(authorization["proposal_ids"])) != len(authorization["proposal_ids"]):
        raise GateError("authorization.proposal_ids must be unique")
    if not isinstance(authorization["authorized_scope"], list) or not authorization["authorized_scope"]:
        raise GateError("authorization must list exact authorized_scope paths")
    if len(set(authorization["authorized_scope"])) != len(authorization["authorized_scope"]):
        raise GateError("authorization.authorized_scope must be unique")
    if not isinstance(authorization["authorized_actions"], list) or not authorization["authorized_actions"]:
        raise GateError("authorization must list authorized_actions")
    action_ids = []
    for action in authorization["authorized_actions"]:
        if not isinstance(action, dict):
            raise GateError("authorization.authorized_actions entries must be objects")
        _required(action, ("proposal_id", "action", "target", "target_sha256_before"), "authorized action")
        action_ids.append(action["proposal_id"])
    if len(set(action_ids)) != len(action_ids):
        raise GateError("authorization.authorized_actions proposal_id values must be unique")
    if authorization["decision"] == "APPROVED" and authorization["user_confirmation"] is not True:
        raise GateError("APPROVED requires user_confirmation=true")
    _iso_datetime(authorization["confirmed_at"], "authorization.confirmed_at")


def _authorization_nonce(
    run_id: str, chain_head: str, user_event_id: str, user_message_sha256: str
) -> str:
    return sha256_bytes(f"{run_id}|{chain_head}|{user_event_id}|{user_message_sha256}".encode("utf-8"))


def authorize_run(
    runs_root: pathlib.Path,
    run_id: str,
    *,
    authorization: Mapping[str, Any],
    expected_revision: int,
) -> Dict[str, Any]:
    authorization_payload = dict(authorization)
    _validate_authorization_payload(authorization_payload)

    with run_lock(runs_root, run_id):
        manifest = load_manifest(runs_root, run_id)
        _assert_revision(manifest, expected_revision)
        verify_integrity(runs_root, run_id, manifest)
        if manifest["state"] not in {"SUPERVISED", "REPORT_COMPLETE"} or manifest.get("supervisor_verdict") != "PASS":
            raise GateError("authorization is accepted only after supervisor PASS")
        expected_nonce = _authorization_nonce(
            run_id, manifest["chain_head_sha256"], authorization_payload["user_event_id"],
            authorization_payload["user_message_sha256"],
        )
        if authorization_payload["authorization_nonce"] != expected_nonce:
            raise GateError("authorization nonce is not bound to this run, chain head and user event")
        text_payload = _latest_payload(runs_root, run_id, manifest, "text_diagnosis") or {}
        proposals = {
            item.get("proposal_id"): item for item in text_payload.get("proposals", []) if isinstance(item, dict)
        }
        unknown = set(authorization_payload["proposal_ids"]) - set(proposals)
        if unknown:
            raise GateError(f"authorization references unknown proposal_ids: {sorted(unknown)}")
        action_by_id = {
            item.get("proposal_id"): item for item in authorization_payload["authorized_actions"] if isinstance(item, dict)
        }
        if set(action_by_id) != set(authorization_payload["proposal_ids"]):
            raise GateError("authorization authorized_actions must exactly cover proposal_ids")
        expected_scopes = []
        for proposal_id in authorization_payload["proposal_ids"]:
            proposal = proposals[proposal_id]
            action = action_by_id[proposal_id]
            for key in ("action", "target", "target_sha256_before"):
                if action.get(key) != proposal.get(key):
                    raise GateError(f"authorization action differs from proposal {proposal_id}: {key}")
            expected_scopes.append(proposal["target"])
        if sorted(set(authorization_payload["authorized_scope"])) != sorted(set(expected_scopes)):
            raise GateError("authorization authorized_scope must equal proposal targets")
        authorization_payload["input_artifact_hashes"] = [manifest["chain_head_sha256"]]
        mutable = copy.deepcopy(manifest)
        entry = _append_artifact(
            runs_root, run_id, mutable, kind="authorization", payload=authorization_payload,
            producer=EXPECTED_PRODUCERS["authorization"],
        )
        mutable["authorization"] = {
            "status": authorization_payload["decision"],
            "artifacts": [*manifest["authorization"].get("artifacts", []), entry["file"]],
            "authorized_scope": list(authorization_payload["authorized_scope"]) if authorization_payload["decision"] == "APPROVED" else [],
            "proposal_ids": list(authorization_payload["proposal_ids"]) if authorization_payload["decision"] == "APPROVED" else [],
            "confirmed_at": authorization_payload["confirmed_at"],
            "authorized_by": authorization_payload["authorized_by"],
            "user_event_id": authorization_payload["user_event_id"],
            "attestation_status": authorization_payload["attestation_status"],
        }
        _commit_manifest(
            _manifest_path(runs_root, run_id), mutable, "AUTHORIZATION_RECORDED",
            {"artifact": entry["file"], "decision": authorization_payload["decision"]},
        )
        return mutable


def path_is_authorized(manifest: Mapping[str, Any], target: str) -> bool:
    """Automatic execution requires a host attestation this runtime cannot mint."""
    auth = manifest.get("authorization", {})
    return (
        auth.get("status") == "APPROVED"
        and auth.get("attestation_status") == "HOST_ATTESTED"
        and target in auth.get("authorized_scope", [])
    )


def _validate_case(case: Mapping[str, Any]) -> None:
    required = (
        "case_id", "title", "verification_level", "context", "input_hashes",
        "metric_definition_version", "anomaly", "diagnostic_metrics", "text_evidence",
        "proposal", "outcome", "alternative_explanations", "applicability",
    )
    _required(case, required, "case")
    if not CASE_ID_RE.fullmatch(str(case["case_id"])):
        raise GateError("case_id has unsafe characters")
    _nonempty_string(case["title"], "case.title")
    _nonempty_string(case["metric_definition_version"], "case.metric_definition_version")
    levels = {
        "ANALYSIS_VERIFIED_OUTCOME_UNVERIFIED", "VERIFIED_IMPROVEMENT", "VERIFIED_NO_EFFECT",
        "VERIFIED_REGRESSION", "HIGH_QUALITY_INCONCLUSIVE",
    }
    if case["verification_level"] not in levels:
        raise GateError("case.verification_level is invalid")
    for key in ("context", "anomaly", "proposal", "outcome", "applicability"):
        if not isinstance(case[key], dict) or not case[key]:
            raise GateError(f"case.{key} must be a non-empty object")
    for key in ("diagnostic_metrics", "alternative_explanations"):
        if not isinstance(case[key], list) or not case[key]:
            raise GateError(f"case.{key} must be a non-empty array")
    if not isinstance(case["text_evidence"], list):
        raise GateError("case.text_evidence must be an array")
    if case["proposal"] and not case["text_evidence"]:
        raise GateError("a case with a proposal requires text_evidence")
    outcome_status = case["outcome"].get("status")
    level_by_outcome = {
        "outcome_unverified": "ANALYSIS_VERIFIED_OUTCOME_UNVERIFIED",
        "verified_improvement": "VERIFIED_IMPROVEMENT",
        "verified_no_effect": "VERIFIED_NO_EFFECT",
        "verified_regression": "VERIFIED_REGRESSION",
        "high_quality_inconclusive": "HIGH_QUALITY_INCONCLUSIVE",
    }
    if level_by_outcome.get(outcome_status) != case["verification_level"]:
        raise GateError("case.verification_level must be derived from outcome.status")
    if not isinstance(case["input_hashes"], list) or not case["input_hashes"]:
        raise GateError("case.input_hashes must be non-empty")
    for digest in case["input_hashes"]:
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise GateError("case.input_hashes must contain sha256 values")


def _allowed_run_evidence_hashes(
    runs_root: pathlib.Path, run_id: str, manifest: Mapping[str, Any]
) -> set:
    allowed = set(manifest.get("artifact_hashes", []))
    raw = _latest_payload(runs_root, run_id, manifest, "raw_capture") or {}
    allowed.update(value for value in raw.get("source_hashes", []) if isinstance(value, str))
    metrics = _latest_payload(runs_root, run_id, manifest, "metrics") or {}
    definition_values = (
        metrics.get("definition_artifacts", {}).values()
        if isinstance(metrics.get("definition_artifacts"), dict)
        else []
    )
    for item in definition_values:
        if isinstance(item, dict) and isinstance(item.get("sha256"), str):
            allowed.add(item["sha256"])
    return allowed


def _validate_verified_case_outcome(
    runs_root: pathlib.Path, case: Mapping[str, Any], current_run_id: str
) -> set:
    outcome = case["outcome"]
    status = outcome.get("status")
    if status in {"outcome_unverified", "high_quality_inconclusive"}:
        return set()
    _required(
        outcome,
        (
            "verification_run_ids", "window_coverage_verified", "mde_evaluated",
            "guardrails_pass", "replicated_windows", "change_id",
        ),
        "case.outcome",
    )
    run_ids = outcome["verification_run_ids"]
    if not isinstance(run_ids, list) or len(run_ids) < 2 or len(set(run_ids)) != len(run_ids):
        raise GateError("verified case outcome requires at least two distinct verification_run_ids")
    if outcome["window_coverage_verified"] is not True or outcome["mde_evaluated"] is not True:
        raise GateError("verified case outcome requires coverage and MDE verification")
    if outcome["guardrails_pass"] is not True:
        raise GateError("verified case outcome requires guardrails_pass=true")
    if not isinstance(outcome["replicated_windows"], int) or outcome["replicated_windows"] < 2:
        raise GateError("verified case outcome requires at least two replicated windows")
    expected_analysis_status = {
        "verified_improvement": {"改善", "IMPROVED"},
        "verified_regression": {"恶化", "DEGRADED"},
        "verified_no_effect": {"无明显变化", "NO_CLEAR_CHANGE"},
    }[status]
    allowed_hashes = set()
    verification_windows = set()
    for verification_run_id in run_ids:
        _nonempty_string(verification_run_id, "case.outcome.verification_run_id")
        verified_manifest = load_manifest(runs_root, verification_run_id)
        verify_integrity(runs_root, verification_run_id, verified_manifest)
        if verified_manifest["state"] != "REPORT_COMPLETE" or verified_manifest.get("supervisor_verdict") != "PASS":
            raise GateError(f"verification run is not complete/supervised: {verification_run_id}")
        if verified_manifest.get("sample_size_qualified") is not True or verified_manifest.get("sample_size_authoritative") is not True or int(verified_manifest.get("sample_size") or 0) < 100:
            raise GateError(f"verification run lacks authoritative sample >=100: {verification_run_id}")
        analysis = _latest_payload(runs_root, verification_run_id, verified_manifest, "analysis") or {}
        validation = _latest_payload(runs_root, verification_run_id, verified_manifest, "validation") or {}
        window = _latest_payload(runs_root, verification_run_id, verified_manifest, "window_bound") or {}
        latest_ref = window.get("latest_snapshot", {}) if isinstance(window, dict) else {}
        matching_changes = [
            item for item in window.get("changes", [])
            if isinstance(item, dict) and item.get("change_id") == outcome["change_id"]
        ] if isinstance(window, dict) else []
        if len(matching_changes) != 1:
            raise GateError(f"verification run lacks the exact promoted change_id: {verification_run_id}")
        if matching_changes[0].get("coverage_status") != "FULL_DAY_COVERED" or matching_changes[0].get("version_status") != "VERIFIED":
            raise GateError(f"verification run lacks full-day/version coverage: {verification_run_id}")
        window_key = (latest_ref.get("source_sha256"), latest_ref.get("data_until"))
        if not isinstance(window_key[0], str) or not isinstance(window_key[1], str):
            raise GateError(f"verification run lacks a frozen latest window: {verification_run_id}")
        if window_key in verification_windows:
            raise GateError("verified case outcome cannot clone the same snapshot/cutoff across runs")
        verification_windows.add(window_key)
        if validation.get("decision") != "PASS" or analysis.get("overall_status") not in expected_analysis_status:
            raise GateError(f"verification run does not support outcome status: {verification_run_id}")
        allowed_hashes.update(_allowed_run_evidence_hashes(runs_root, verification_run_id, verified_manifest))
    if outcome["replicated_windows"] != len(verification_windows):
        raise GateError("case.outcome.replicated_windows must equal distinct verified latest windows")
    return allowed_hashes


def promote_case(
    runs_root: pathlib.Path,
    knowledge_root: pathlib.Path,
    run_id: str,
    *,
    case: Mapping[str, Any],
    producer: str,
    expected_revision: int,
) -> Dict[str, Any]:
    _validate_producer("case_promotion", producer)
    _validate_case(case)
    if runs_root.resolve(strict=False) == DEFAULT_RUNS_ROOT.resolve(strict=False) and knowledge_root.resolve(strict=False) != DEFAULT_KNOWLEDGE_ROOT.resolve(strict=False):
        raise GateError("production case promotion must use the project knowledge/cases root")
    with run_lock(runs_root, run_id):
        manifest = load_manifest(runs_root, run_id)
        _assert_revision(manifest, expected_revision)
        verify_integrity(runs_root, run_id, manifest)
        if manifest["state"] != "REPORT_COMPLETE" or manifest.get("supervisor_verdict") != "PASS":
            raise GateError("only a REPORT_COMPLETE run with supervisor PASS may promote a case")
        validation = _latest_payload(runs_root, run_id, manifest, "validation") or {}
        if validation.get("decision") != "PASS":
            raise GateError("case promotion requires independent validation PASS")
        allowed_hashes = _allowed_run_evidence_hashes(runs_root, run_id, manifest)
        allowed_hashes.update(_validate_verified_case_outcome(runs_root, case, run_id))
        unknown_hashes = set(case["input_hashes"]) - allowed_hashes
        if unknown_hashes:
            raise GateError("case.input_hashes must belong to the frozen current/verification runs")
        required_evidence_kinds = {"analysis", "validation", "supervision"}
        if case.get("proposal"):
            required_evidence_kinds.add("text_diagnosis")
        required_evidence_hashes = {
            entry["sha256"] for entry in manifest["artifacts"] if entry.get("kind") in required_evidence_kinds
        }
        if not required_evidence_hashes.issubset(set(case["input_hashes"])):
            raise GateError("case.input_hashes must include analysis, validation, supervision and proposal evidence")

        promoted = dict(case)
        promoted["_provenance"] = {
            "run_id": run_id,
            "run_chain_head_sha256": manifest["chain_head_sha256"],
            "promoted_at": utc_now(),
        }
        case_data = canonical_bytes(promoted)
        case_digest = sha256_bytes(case_data)
        case_path = knowledge_root / f"{case['case_id']}.json"
        if case_path.exists():
            if sha256_file(case_path) != case_digest:
                raise IntegrityError(f"knowledge case is immutable and already differs: {case_path}")

        mutable = copy.deepcopy(manifest)
        payload = {
            "case_id": case["case_id"], "case_file": str(case_path), "case_sha256": case_digest,
            "knowledge_document": promoted,
            "input_artifact_hashes": [manifest["chain_head_sha256"]],
        }
        entry = _append_artifact(runs_root, run_id, mutable, kind="case_promotion", payload=payload, producer=producer)
        mutable["promoted_cases"].append({
            key: value for key, value in payload.items()
            if key not in {"input_artifact_hashes", "knowledge_document"}
        })
        _commit_manifest(
            _manifest_path(runs_root, run_id), mutable, "CASE_PROMOTED",
            {"artifact": entry["file"], "case_id": case["case_id"], "case_sha256": case_digest},
        )
        if not case_path.exists():
            try:
                atomic_create_bytes(case_path, case_data)
            except IntegrityError:
                if not case_path.is_file() or sha256_file(case_path) != case_digest:
                    raise
        return mutable


def _validate_method(method: Mapping[str, Any]) -> None:
    required = (
        "method_id", "version", "title", "scope", "problem", "method_steps",
        "required_inputs", "decision_rules", "limitations", "sources", "status",
    )
    _required(method, required, "method")
    if not RUN_ID_RE.fullmatch(str(method["method_id"])):
        raise GateError("method_id has unsafe characters")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", str(method["version"])):
        raise GateError("method.version has unsafe characters")
    if method["status"] not in {"ACTIVE", "EXPERIMENTAL", "DEPRECATED"}:
        raise GateError("method.status must be ACTIVE, EXPERIMENTAL, or DEPRECATED")
    for key in ("method_steps", "required_inputs", "decision_rules", "limitations", "sources"):
        if not isinstance(method[key], list) or not method[key]:
            raise GateError(f"method.{key} must be a non-empty array")
    if not isinstance(method["scope"], (dict, list, str)):
        raise GateError("method.scope must be an object, array, or string")
    supersedes = method.get("supersedes")
    if supersedes is not None and not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}@[A-Za-z0-9][A-Za-z0-9._-]{0,63}", str(supersedes)
    ):
        raise GateError("method.supersedes must use method_id@version")


def promote_method(
    runs_root: pathlib.Path,
    knowledge_root: pathlib.Path,
    run_id: str,
    *,
    method: Mapping[str, Any],
    producer: str,
    expected_revision: int,
) -> Dict[str, Any]:
    _validate_producer("method_promotion", producer)
    _validate_method(method)
    if runs_root.resolve(strict=False) == DEFAULT_RUNS_ROOT.resolve(strict=False) and knowledge_root.resolve(strict=False) != DEFAULT_METHOD_KNOWLEDGE_ROOT.resolve(strict=False):
        raise GateError("production method promotion must use the project knowledge/methods root")
    with run_lock(runs_root, run_id):
        manifest = load_manifest(runs_root, run_id)
        _assert_revision(manifest, expected_revision)
        verify_integrity(runs_root, run_id, manifest)
        if manifest["state"] != "REPORT_COMPLETE" or manifest.get("supervisor_verdict") != "PASS":
            raise GateError("only a REPORT_COMPLETE run with supervisor PASS may promote a method")
        validation = _latest_payload(runs_root, run_id, manifest, "validation") or {}
        if validation.get("decision") != "PASS":
            raise GateError("method promotion requires independent validation PASS")

        method_key = f"{method['method_id']}@{method['version']}"
        existing = sorted(knowledge_root.glob(f"{method['method_id']}@*.json")) if knowledge_root.exists() else []
        supersedes = method.get("supersedes")
        if existing and not supersedes:
            raise GateError("a later method version must declare supersedes=method_id@version")
        if supersedes:
            superseded_path = knowledge_root / f"{supersedes}.json"
            if not superseded_path.is_file():
                raise GateError(f"superseded method version does not exist: {supersedes}")
            if not str(supersedes).startswith(f"{method['method_id']}@"):
                raise GateError("a method may only supersede an earlier version of the same method_id")

        promoted = dict(method)
        promoted["_provenance"] = {
            "run_id": run_id,
            "run_chain_head_sha256": manifest["chain_head_sha256"],
            "promoted_at": utc_now(),
        }
        method_data = canonical_bytes(promoted)
        method_digest = sha256_bytes(method_data)
        method_path = knowledge_root / f"{method_key}.json"
        if method_path.exists():
            if sha256_file(method_path) != method_digest:
                raise IntegrityError(f"knowledge method version is immutable and already differs: {method_path}")

        mutable = copy.deepcopy(manifest)
        payload = {
            "method_id": method["method_id"],
            "version": method["version"],
            "method_file": str(method_path),
            "method_sha256": method_digest,
            "supersedes": supersedes,
            "knowledge_document": promoted,
            "input_artifact_hashes": [manifest["chain_head_sha256"]],
        }
        entry = _append_artifact(
            runs_root, run_id, mutable, kind="method_promotion", payload=payload, producer=producer
        )
        mutable.setdefault("promoted_methods", []).append(
            {
                key: value for key, value in payload.items()
                if key not in {"input_artifact_hashes", "knowledge_document"}
            }
        )
        _commit_manifest(
            _manifest_path(runs_root, run_id), mutable, "METHOD_PROMOTED",
            {"artifact": entry["file"], "method_id": method_key, "method_sha256": method_digest},
        )
        if not method_path.exists():
            try:
                atomic_create_bytes(method_path, method_data)
            except IntegrityError:
                if not method_path.is_file() or sha256_file(method_path) != method_digest:
                    raise
        return mutable


def read_json(path: pathlib.Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"cannot read JSON payload {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"payload must be a JSON object: {path}")
    return value


def _selftest() -> Dict[str, Any]:
    """Small installed-environment smoke test; the full suite lives in tests/."""
    import normalize_raw

    with tempfile.TemporaryDirectory(prefix="story-data-workflow-") as temp:
        temp_root = pathlib.Path(temp)
        root = temp_root / "runs"
        scope = {
            "platform": "fanqie", "work_type": "long", "work_id": "book-1",
            "mode": "snapshot", "question": "workflow smoke test",
            "expected_snapshot_date": "2026-08-12", "expected_data_until": "2026-08-11",
        }
        manifest = init_run(root, "selftest", scope=scope)
        healthy = {"http_ok": True, "json_ok": True, "business_code": 0}
        raw_value = {
            "schema_version": 2, "date": "2026-08-12", "data_until": "2026-08-11",
            "pulled_at": "2026-08-12T12:00:00+08:00", "novel_id": "book-1",
            "trend_dates": ["08-11"],
            "novel_chapters": [
                {"i": 1, "title": "1", "read": 100, "follow": 50, "loss": 0, "words": 1000},
                {"i": 2, "title": "2", "read": 50, "follow": 0, "loss": 50, "words": 1000},
                {"i": 3, "title": "3", "read": 0, "follow": 0, "loss": 100, "words": 1000},
            ],
            "novel_common": {"reader_uv_daily": 3},
            "novel_metrics": {"阅读人数": [3]}, "novel_traffic": {"搜索": [3]},
            "endpoint_status": {
                name: dict(healthy) for name in (
                    "chapter_list_v1", "book_common_v1", "book_increase_metrics", "book_increase_traffic"
                )
            },
        }
        raw_path = temp_root / "snapshot.json"
        raw_path.write_bytes(canonical_bytes(raw_value))
        raw_sha = sha256_file(raw_path)
        raw_payload = {
            "status": "OK", "source_files": [str(raw_path)], "source_hashes": [raw_sha],
            "snapshot_file": str(raw_path), "snapshot_sha256": raw_sha,
            "capture_mode": "platform_pull", "work_id": "book-1", "run_scope_sha256": manifest["scope_sha256"],
            "snapshot_date": "2026-08-12", "data_until": "2026-08-11",
            "pulled_at": "2026-08-12T12:00:00+08:00", "login_status": "AUTHENTICATED",
            "endpoint_status": raw_value["endpoint_status"],
            "required_endpoint_names": list(raw_value["endpoint_status"]),
            "usable_fields": ["novel_chapters", "novel_metrics", "novel_traffic"],
            "snapshot_metadata_verified": True, "work_identity_status": "VERIFIED_SOURCE",
        }
        manifest = record_artifact(
            root, "selftest", kind="raw_capture", payload=raw_payload,
            producer="story-data-fetcher", expected_revision=manifest["revision"],
        )
        normalized = normalize_raw.normalize_file(
            raw_path, expected_snapshot_date="2026-08-12", expected_data_until="2026-08-11",
            expected_work_id="book-1", scope="long",
        )
        normalized_hash = sha256_bytes(canonical_bytes(normalized))
        checks = [
            {"check_id": check_id, "status": "PASS", "evidence": ["selftest deterministic evidence"]}
            for check_id in ("freshness", "work_identity", "endpoint_health", "presence_semantics", "formula_consistency", "scope")
        ]
        quality = {
            "status": "OK", "snapshot_date": "2026-08-12", "data_until": "2026-08-11",
            "expected_snapshot_date": "2026-08-12", "expected_data_until": "2026-08-11",
            "sample_size": 3, "sample_size_authoritative": True,
            "sample_size_qualified": True,
            "sample_size_basis": "official daily reader UV", "sample_aggregation": "single",
            "sample_unavailability_reasons": [],
            "sample_size_evidence": [{
                "source_sha256": normalized_hash,
                "json_pointer": "/facts/long_novel/common/reader_uv_daily/value",
                "value": 3, "authoritative": True, "role": "qualified latest-day readers",
            }],
            "usable_fields": normalized["quality"]["usable_fields"], "scope_verified": True,
            "work_id": "book-1", "expected_work_id": "book-1", "work_id_verified": True,
            "branch_statuses": normalized["quality"]["branch_statuses"],
            "normalizer_version": str(normalized["normalization_schema_version"]),
            "normalized_snapshot": normalized, "normalized_snapshot_sha256": normalized_hash,
            "raw_snapshot_sha256": raw_sha, "quality_checks": checks,
            "input_artifact_hashes": [manifest["chain_head_sha256"]],
        }
        manifest = record_artifact(
            root, "selftest", kind="data_quality", payload=quality,
            producer="story-data-normalizer", expected_revision=manifest["revision"],
        )
        integrity = verify_integrity(root, "selftest", manifest)
        return {"ok": True, "stage": manifest["state"], "revision": manifest["revision"], **integrity}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=pathlib.Path, default=DEFAULT_RUNS_ROOT)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--run-id", required=True)
    init.add_argument("--scope", type=pathlib.Path, help="JSON object describing work type/book/change scope")
    init.add_argument("--work-type", choices=("long", "short", "all"))
    init.add_argument("--work-id", "--book-id", dest="work_id")
    init.add_argument("--platform", default="fanqie")
    init.add_argument("--mode", choices=("latest", "snapshot", "method_only"))
    init.add_argument("--question")
    init.add_argument("--expected-snapshot-date")
    init.add_argument("--expected-data-until")
    init.add_argument("--max-returns", type=int, default=3)

    status = sub.add_parser("status")
    status.add_argument("--run-id", required=True)
    status.add_argument("--no-verify", action="store_true")

    recover = sub.add_parser("recover")
    recover.add_argument("--run-id", required=True)

    record = sub.add_parser("record")
    record.add_argument("--run-id", required=True)
    record.add_argument("--kind", choices=tuple(KIND_FLOW), required=True)
    record.add_argument("--payload", type=pathlib.Path, required=True)
    record.add_argument("--producer", required=True)
    record.add_argument("--expected-revision", type=int, required=True)

    returned = sub.add_parser("return")
    returned.add_argument("--run-id", required=True)
    returned.add_argument("--to-state", choices=tuple(RETURNABLE_STATES), required=True)
    returned.add_argument("--reason", required=True)
    returned.add_argument("--root-cause-id", required=True)
    returned.add_argument("--error-code", required=True)
    returned.add_argument("--rejected-finding-id", action="append", default=[])
    returned.add_argument("--repair-requirement", action="append", required=True)
    returned.add_argument("--producer", required=True)
    returned.add_argument("--expected-revision", type=int, required=True)

    complete = sub.add_parser("complete")
    complete.add_argument("--run-id", required=True)
    complete.add_argument("--report", type=pathlib.Path, required=True)
    complete.add_argument("--producer", required=True)
    complete.add_argument("--expected-revision", type=int, required=True)

    authorize = sub.add_parser("authorize")
    authorize.add_argument("--run-id", required=True)
    authorize.add_argument("--authorization", type=pathlib.Path, required=True)
    authorize.add_argument("--expected-revision", type=int, required=True)

    promote = sub.add_parser("promote-case")
    promote.add_argument("--run-id", required=True)
    promote.add_argument("--case", type=pathlib.Path, required=True)
    promote.add_argument("--knowledge-root", type=pathlib.Path, default=DEFAULT_KNOWLEDGE_ROOT)
    promote.add_argument("--producer", required=True)
    promote.add_argument("--expected-revision", type=int, required=True)

    promote_method_parser = sub.add_parser("promote-method")
    promote_method_parser.add_argument("--run-id", required=True)
    promote_method_parser.add_argument("--method", type=pathlib.Path, required=True)
    promote_method_parser.add_argument("--knowledge-root", type=pathlib.Path, default=DEFAULT_METHOD_KNOWLEDGE_ROOT)
    promote_method_parser.add_argument("--producer", required=True)
    promote_method_parser.add_argument("--expected-revision", type=int, required=True)

    sub.add_parser("selftest")
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            scope = read_json(args.scope) if args.scope else {}
            if args.work_type:
                scope["work_type"] = args.work_type
            if args.work_id:
                scope["work_id"] = args.work_id
            if args.platform:
                scope.setdefault("platform", args.platform)
            if args.mode:
                scope["mode"] = args.mode
            if args.question:
                scope["question"] = args.question
            if args.expected_snapshot_date:
                scope["expected_snapshot_date"] = args.expected_snapshot_date
            if args.expected_data_until:
                scope["expected_data_until"] = args.expected_data_until
            result = init_run(args.runs_root, args.run_id, scope=scope, max_returns=args.max_returns)
        elif args.command == "status":
            result = load_manifest(args.runs_root, args.run_id)
            if not args.no_verify:
                result = {**result, "integrity": verify_integrity(args.runs_root, args.run_id, result)}
        elif args.command == "recover":
            result = recover_run(args.runs_root, args.run_id)
        elif args.command == "record":
            result = record_artifact(
                args.runs_root, args.run_id, kind=args.kind, payload=read_json(args.payload),
                producer=args.producer, expected_revision=args.expected_revision,
            )
        elif args.command == "return":
            result = return_run(
                args.runs_root, args.run_id, to_state=args.to_state, reason=args.reason,
                root_cause_id=args.root_cause_id, error_code=args.error_code,
                rejected_finding_ids=args.rejected_finding_id, repair_requirements=args.repair_requirement,
                producer=args.producer, expected_revision=args.expected_revision,
            )
        elif args.command == "complete":
            result = complete_run(
                args.runs_root, args.run_id, report_text=args.report.read_text(encoding="utf-8"),
                producer=args.producer, expected_revision=args.expected_revision,
            )
        elif args.command == "authorize":
            result = authorize_run(
                args.runs_root, args.run_id, authorization=read_json(args.authorization),
                expected_revision=args.expected_revision,
            )
        elif args.command == "promote-case":
            result = promote_case(
                args.runs_root, args.knowledge_root, args.run_id, case=read_json(args.case),
                producer=args.producer, expected_revision=args.expected_revision,
            )
        elif args.command == "promote-method":
            result = promote_method(
                args.runs_root, args.knowledge_root, args.run_id, method=read_json(args.method),
                producer=args.producer, expected_revision=args.expected_revision,
            )
        elif args.command == "selftest":
            result = _selftest()
        else:
            raise AssertionError(args.command)
    except (WorkflowError, OSError) as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__, "detail": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
