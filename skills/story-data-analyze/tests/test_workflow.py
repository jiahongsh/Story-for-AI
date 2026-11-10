import copy
import hashlib
import json
import os
import pathlib
import sys
import tempfile
import unittest


SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]
HISTORICAL_FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "historical"
sys.path.insert(0, str(SCRIPTS))

import data_workflow as wf  # noqa: E402
import normalize_raw as nr  # noqa: E402


class WorkflowTest(unittest.TestCase):
    WORK_ID = "book-1"
    CHECK_IDS = ("freshness", "work_identity", "endpoint_health", "presence_semantics", "formula_consistency", "scope")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="story-workflow-test-")
        self.temp_path = pathlib.Path(self.temp.name)
        self.root = self.temp_path / "runs"
        self.contexts = {}
        self.target = PROJECT_ROOT / "skills" / "story-data-analyze" / "tests" / "fixtures" / "text-target.md"
        self.target_rel = self.target.relative_to(PROJECT_ROOT).as_posix()
        self.target_hash = wf.sha256_file(self.target)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def healthy_endpoint():
        return {"http_ok": True, "json_ok": True, "business_code": 0}

    def scope(self):
        return {
            "platform": "fanqie", "work_type": "long", "work_id": self.WORK_ID,
            "mode": "snapshot", "question": "Did the first-chapter revision improve the chapter 1→2 handoff?",
            "expected_snapshot_date": "2026-08-12", "expected_data_until": "2026-08-11",
            "causal_design_verified": False,
        }

    def _snapshot(self, date, cutoff, chapter_1, chapter_2, daily_readers):
        endpoints = {
            name: self.healthy_endpoint() for name in (
                "chapter_list_v1", "book_common_v1", "book_increase_metrics", "book_increase_traffic"
            )
        }
        return {
            "schema_version": 2, "date": date, "data_until": cutoff,
            "pulled_at": f"{date}T12:05:00+08:00", "timezone": "Asia/Shanghai",
            "novel_id": self.WORK_ID, "trend_dates": [cutoff[5:]],
            "novel_chapters": [
                {
                    "i": 1, "title": "第一章", "read": 100, "follow": 50, "loss": 0,
                    "words": 1000, "arrival_uv": chapter_1,
                },
                {
                    "i": 2, "title": "第二章", "read": 50, "follow": 0, "loss": 50,
                    "words": 1000, "arrival_uv": chapter_2,
                },
                {
                    "i": 3, "title": "第三章", "read": 0, "follow": 0, "loss": 100,
                    "words": 1000, "arrival_uv": 0,
                },
            ],
            "novel_common": {"reader_uv_daily": daily_readers},
            "novel_metrics": {"阅读人数": [daily_readers]},
            "novel_traffic": {"搜索": [daily_readers]},
            "endpoint_status": endpoints,
            "shorts": [],
        }

    def _make_context(self, run_id, sample=120):
        evidence_dir = self.temp_path / "evidence" / run_id
        evidence_dir.mkdir(parents=True, exist_ok=True)
        specs = {
            "baseline": ("2026-08-08", "2026-08-07", max(sample - 20, 1), max(round(max(sample - 20, 1) * 0.4), 0), max(sample - 20, 1)),
            "previous_snapshot": ("2026-08-10", "2026-08-09", max(sample - 10, 1), max(round(max(sample - 10, 1) * 0.45), 0), max(sample - 10, 1)),
            "latest_snapshot": ("2026-08-12", "2026-08-11", sample, round(sample * 0.5), sample),
        }
        refs = {}
        raws = {}
        for role, spec in specs.items():
            raw = self._snapshot(*spec)
            path = evidence_dir / f"{role}.json"
            path.write_bytes(wf.canonical_bytes(raw))
            raws[role] = raw
            refs[role] = {
                "snapshot_date": raw["date"], "data_until": raw["data_until"],
                "source_file": str(path), "source_sha256": wf.sha256_file(path),
                "work_id": self.WORK_ID, "work_identity_status": "VERIFIED_SOURCE",
            }
        context = {"sample": sample, "refs": refs, "raws": raws}
        self.contexts[run_id] = context
        return context

    def init(self, run_id="run", sample=120, max_returns=3):
        self._make_context(run_id, sample)
        return wf.init_run(self.root, run_id, scope=self.scope(), max_returns=max_returns)

    @staticmethod
    def _kind_hash(manifest, kind):
        return [entry["sha256"] for entry in manifest["artifacts"] if entry["kind"] == kind][-1]

    def raw_payload(self, manifest, run_id="run", status="OK"):
        context = self.contexts[run_id]
        ref = context["refs"]["latest_snapshot"]
        raw = context["raws"]["latest_snapshot"]
        return {
            "status": status,
            "source_files": [ref["source_file"]], "source_hashes": [ref["source_sha256"]],
            "snapshot_file": ref["source_file"], "snapshot_sha256": ref["source_sha256"],
            "capture_mode": "platform_pull", "work_id": self.WORK_ID,
            "run_scope_sha256": manifest["scope_sha256"], "snapshot_date": raw["date"],
            "data_until": raw["data_until"], "pulled_at": raw["pulled_at"],
            "login_status": "AUTHENTICATED", "endpoint_status": raw["endpoint_status"],
            "required_endpoint_names": list(raw["endpoint_status"]),
            "usable_fields": ["novel_chapters", "novel_metrics", "novel_traffic"],
            "snapshot_metadata_verified": True, "work_identity_status": "VERIFIED_SOURCE",
        }

    def quality_payload(self, manifest, run_id="run"):
        context = self.contexts[run_id]
        ref = context["refs"]["latest_snapshot"]
        normalized = nr.normalize_file(
            pathlib.Path(ref["source_file"]), expected_snapshot_date="2026-08-12",
            expected_data_until="2026-08-11", expected_work_id=self.WORK_ID, scope="long",
        )
        normalized_hash = wf.sha256_bytes(wf.canonical_bytes(normalized))
        checks = [
            {"check_id": check_id, "status": "PASS", "evidence": ["deterministically recomputed"]}
            for check_id in self.CHECK_IDS
        ]
        return {
            "status": "OK", "snapshot_date": "2026-08-12", "data_until": "2026-08-11",
            "expected_snapshot_date": "2026-08-12", "expected_data_until": "2026-08-11",
            "sample_size": context["sample"], "sample_size_qualified": True,
            "sample_size_authoritative": True,
            "sample_size_basis": "exact chapter-1 arrival_uv", "sample_aggregation": "single",
            "sample_unavailability_reasons": [],
            "sample_size_evidence": [{
                "source_sha256": normalized_hash,
                "json_pointer": "/facts/long_novel/chapters/0/arrival_people/value",
                "value": context["sample"], "authoritative": True, "role": "chapter handoff denominator",
            }],
            "scope_verified": True, "work_id": self.WORK_ID,
            "expected_work_id": self.WORK_ID, "work_id_verified": True,
            "usable_fields": normalized["quality"]["usable_fields"],
            "quality_checks": checks, "branch_statuses": normalized["quality"]["branch_statuses"],
            "normalizer_version": str(normalized["normalization_schema_version"]),
            "normalized_snapshot": normalized, "normalized_snapshot_sha256": normalized_hash,
            "raw_snapshot_sha256": ref["source_sha256"],
        }

    def window_payload(self, run_id="run"):
        context = self.contexts[run_id]
        return {
            "analysis_mode": "modification_effect",
            "analysis_question": self.scope()["question"],
            "baseline": context["refs"]["baseline"],
            "previous_snapshot": context["refs"]["previous_snapshot"],
            "latest_snapshot": context["refs"]["latest_snapshot"],
            "changes": [{
                "change_id": "change-1", "published_at": "2026-08-08T01:00:00+08:00",
                "target_metric_ids": ["long_chapter_follow_rate_sync"],
                "first_covered_data_date": "2026-08-08", "first_full_data_date": "2026-08-09",
                "coverage_status": "FULL_DAY_COVERED", "coverage_evidence": ["derived from published_at and latest cutoff"],
                "version_status": "VERIFIED", "version_evidence": [{
                    "source_file": str(self.target), "source_sha256": self.target_hash,
                    "evidence_type": "frozen_target_version", "verification_strength": "DIRECT",
                    "record_locator": "却先回忆了三页家史",
                    "assertion": "fixture target is the version analyzed by the workflow",
                }],
                "concurrent_events": [],
            }],
            "confounders": [{
                "confounder_id": "self_visit", "status": "ABSENT",
                "evidence": ["test fixture explicitly excludes self visits"],
            }],
        }

    @staticmethod
    def _tree_nodes():
        tree = json.loads((PROJECT_ROOT / "skills/story-data-analyze/dictionary/metric-tree.v1.json").read_text(encoding="utf-8"))
        return wf._tree_node_ids(tree["trees"])

    @staticmethod
    def _definition_artifacts():
        result = {}
        for label, path in wf.CANONICAL_DEFINITIONS.items():
            document = json.loads(path.read_text(encoding="utf-8"))
            result[label] = {
                "path": str(path), "sha256": wf.sha256_file(path),
                "version": str(document["schema_version"]),
            }
        return result

    def metrics_payload(self, manifest, run_id="run"):
        context = self.contexts[run_id]
        window_hash = manifest["chain_head_sha256"]
        latest_ref = context["refs"]["latest_snapshot"]
        baseline_ref = context["refs"]["baseline"]
        sample = context["sample"]
        reach_dimensions = {
            "work_id": self.WORK_ID, "chapter_index": 1, "chapter_version": "fixture-v1",
            "data_until": "2026-08-11", "estimate_status": "exact_source_count",
        }
        transition_dimensions = {
            "work_id": self.WORK_ID, "chapter_index": 1, "data_until": "2026-08-11",
            "estimate_status": "exact_source_counts",
        }
        baseline_transition_dimensions = {
            "work_id": self.WORK_ID, "chapter_index": 1, "data_until": "2026-08-07",
            "estimate_status": "exact_source_counts",
        }
        baseline_chapters = context["raws"]["baseline"]["novel_chapters"]
        baseline_rate = baseline_chapters[1]["arrival_uv"] / baseline_chapters[0]["arrival_uv"] * 100
        current_rate = round(sample * 0.5) / sample * 100
        facts = [
            {
                "metric_id": "long_chapter_reach_count", "value": sample,
                "unit": "person", "time_grain": "cumulative_snapshot",
                "dimensions": reach_dimensions, "quality_status": "OK", "authoritative": True,
                "source_refs": [window_hash],
                "source_observations": [{
                    "source_role": "latest_snapshot", "source_sha256": latest_ref["source_sha256"],
                    "json_pointer": "/novel_chapters/0/arrival_uv", "value": sample,
                }],
                "calculation": {"mode": "source", "operator": "identity", "expression": "arrival_uv", "input_values": [sample]},
            },
            {
                "metric_id": "long_chapter_follow_rate_sync", "value": baseline_rate,
                "unit": "percent", "time_grain": "cumulative_snapshot",
                "dimensions": baseline_transition_dimensions, "quality_status": "OK", "authoritative": True,
                "source_refs": [window_hash],
                "source_observations": [
                    {
                        "source_role": "baseline", "source_sha256": baseline_ref["source_sha256"],
                        "json_pointer": "/novel_chapters/1/arrival_uv", "value": baseline_chapters[1]["arrival_uv"],
                    },
                    {
                        "source_role": "baseline", "source_sha256": baseline_ref["source_sha256"],
                        "json_pointer": "/novel_chapters/0/arrival_uv", "value": baseline_chapters[0]["arrival_uv"],
                    },
                ],
                "calculation": {
                    "mode": "derived", "operator": "ratio_percent",
                    "expression": "baseline_chapter2_arrival_uv/baseline_chapter1_arrival_uv*100",
                    "input_values": [baseline_chapters[1]["arrival_uv"], baseline_chapters[0]["arrival_uv"]],
                },
            },
            {
                "metric_id": "long_chapter_follow_rate_sync", "value": current_rate,
                "unit": "percent", "time_grain": "cumulative_snapshot",
                "dimensions": transition_dimensions, "quality_status": "OK", "authoritative": True,
                "source_refs": [window_hash],
                "source_observations": [
                    {
                        "source_role": "latest_snapshot", "source_sha256": latest_ref["source_sha256"],
                        "json_pointer": "/novel_chapters/1/arrival_uv", "value": round(sample * 0.5),
                    },
                    {
                        "source_role": "latest_snapshot", "source_sha256": latest_ref["source_sha256"],
                        "json_pointer": "/novel_chapters/0/arrival_uv", "value": sample,
                    },
                ],
                "calculation": {
                    "mode": "derived", "operator": "ratio_percent",
                    "expression": "chapter2_arrival_uv/chapter1_arrival_uv*100",
                    "input_values": [round(sample * 0.5), sample],
                },
            },
        ]
        all_nodes = {
            node for node in self._tree_nodes()
            if node == "dq" or node.startswith("dq.") or node == "long" or node.startswith("long.")
        }
        measured = {
            "long.activation_depth.chapter_curve": ["long_chapter_reach_count"],
            "long.activation_depth.transition": ["long_chapter_follow_rate_sync"],
        }
        diagnostic = {"dq", "long", "long.golden_three"} | {node for node in all_nodes if node.startswith("dq.")}
        node_statuses = []
        for node in sorted(all_nodes):
            if node in measured:
                status, metric_ids, evidence, reason = "MEASURED", measured[node], [window_hash], "source values available"
            elif node in diagnostic:
                status, metric_ids, evidence, reason = "DIAGNOSTICALLY_CHECKED", [], [window_hash], "governance or parent node checked"
            else:
                status, metric_ids, evidence, reason = "UNAVAILABLE", [], [], "fixture supplies no fact for this node"
            node_statuses.append({
                "node_id": node, "status": status, "metric_ids": metric_ids,
                "evidence": evidence, "reason": reason,
            })
        definitions = self._definition_artifacts()
        return {
            "metric_catalog_version": definitions["metric_catalog"]["version"], "definition_artifacts": definitions,
            "facts": facts,
            "computed_metric_ids": ["long_chapter_reach_count", "long_chapter_follow_rate_sync"],
            "required_nodes_checked": sorted(all_nodes), "node_statuses": node_statuses,
            "quality_summary": {"status": "OK", "limitations": ["cumulative chapter rates are observational"]},
        }

    def analysis_payload(self, manifest, run_id="run"):
        context = self.contexts[run_id]
        sample = context["sample"]
        metrics = self.metrics_payload_from_manifest(manifest, run_id)
        missing = sorted(row["node_id"] for row in metrics["node_statuses"] if row["status"] == "UNAVAILABLE")
        evidence_refs = [self._kind_hash(manifest, "window_bound"), manifest["chain_head_sha256"]]
        base = {
            "overall_status": "SAMPLE_INSUFFICIENT" if sample < 30 else "IMPROVED",
            "sample_size": sample, "strong_conclusion": False, "causal_attribution": False,
            "sample_metric_id": "long_chapter_reach_count",
            "sample_evidence_refs": [self._kind_hash(manifest, "data_quality"), manifest["chain_head_sha256"]],
            "metric_tree_coverage": {
                "checked_nodes": metrics["required_nodes_checked"], "missing_nodes": missing,
                "missing_node_reasons": {node: "no qualified fixture fact" for node in missing},
            },
            "evidence_refs": evidence_refs,
            "anomaly_rule_evidence": [{"rule": "baseline + previous + latest", "result": "evaluated"}],
            "linked_metric_checks": [
                {
                    "metric_id": "long_chapter_reach_count", "status": "CHECKED",
                    "evidence_refs": evidence_refs, "finding": f"chapter-1 denominator is {sample}",
                },
                {
                    "metric_id": "long_chapter_follow_rate_sync", "status": "CHECKED",
                    "evidence_refs": evidence_refs, "finding": "chapter 1→2 synchronous rate is 50%",
                },
            ],
            "primary_constraint": "chapter 1→2 handoff", "primary_constraint_node": "long.activation_depth.transition",
        }
        if sample < 30:
            base.update({"anomalies": [], "hypotheses": []})
        else:
            base.update({
                "anomalies": [{
                    "metric_id": "long_chapter_follow_rate_sync", "baseline": 40, "current": 50,
                    "delta": 10, "direction": "UP", "effect_size": 10,
                    "baseline_fact": {
                        "metric_id": "long_chapter_follow_rate_sync",
                        "dimensions": {
                            "work_id": self.WORK_ID, "chapter_index": 1, "data_until": "2026-08-07",
                            "estimate_status": "exact_source_counts",
                        },
                    },
                    "current_fact": {
                        "metric_id": "long_chapter_follow_rate_sync",
                        "dimensions": {
                            "work_id": self.WORK_ID, "chapter_index": 1, "data_until": "2026-08-11",
                            "estimate_status": "exact_source_counts",
                        },
                    },
                    "threshold_method": "internal minimum effect + sample gate", "threshold_result": "TRIGGERED",
                    "evidence_refs": evidence_refs,
                    "neighbors_checked": ["long_chapter_reach_count"],
                }],
                "hypotheses": [{
                    "hypothesis_id": "h1", "cause": "chapter-one ending now creates a clearer next action",
                    "predicted_neighbor_pattern": "chapter 1→2 improves without lowering chapter-1 reach",
                    "falsification": "no repeated improvement after 30 qualified post-change readers",
                    "text_target_candidate": self.target_rel, "evidence_level": "HYPOTHESIS",
                }],
            })
        base["change_assessments"] = [{
            "change_id": "change-1",
            "status": "SAMPLE_INSUFFICIENT" if sample < 30 else "IMPROVED",
            "direction": "UNKNOWN" if sample < 30 else "UP",
            "coverage_status": "FULL_DAY_COVERED", "version_status": "VERIFIED",
            "evaluated_metric_ids": ["long_chapter_follow_rate_sync"],
            "evidence_refs": evidence_refs,
            "rationale": (
                "qualified change-level sample remains below 30"
                if sample < 30 else
                "the target handoff metric crossed its threshold in the preferred direction"
            ),
        }]
        return base

    def metrics_payload_from_manifest(self, manifest, run_id="run"):
        path = self.root / run_id / [entry["file"] for entry in manifest["artifacts"] if entry["kind"] == "metrics"][-1]
        return json.loads(path.read_text(encoding="utf-8"))["payload"]

    def validation_payload(self, manifest, run_id="run"):
        metrics = self.metrics_payload_from_manifest(manifest, run_id)
        analysis_path = self.root / run_id / [entry["file"] for entry in manifest["artifacts"] if entry["kind"] == "analysis"][-1]
        analysis = json.loads(analysis_path.read_text(encoding="utf-8"))["payload"]
        recalculation = [{
            "metric_id": fact["metric_id"], "dimensions": fact["dimensions"],
            "formula": fact["calculation"]["expression"], "source_refs": fact["source_refs"],
            "source_observations": fact["source_observations"],
            "calculation": fact["calculation"],
            "recalculated_value": fact["value"],
        } for fact in metrics["facts"]]
        return {
            "decision": "PASS", "independent_recalculation": recalculation,
            "logic_checks": [
                {"check_id": check_id, "status": "PASS", "evidence": [manifest["chain_head_sha256"]]}
                for check_id in wf.REQUIRED_LOGIC_CHECKS
            ],
            "method_checks": [
                {"check_id": check_id, "status": "PASS", "evidence": [manifest["chain_head_sha256"]]}
                for check_id in wf.REQUIRED_METHOD_CHECKS
            ],
            "input_hashes_verified": True, "validator_independent": True,
            "reviewed_analysis_sha256": manifest["chain_head_sha256"],
            "missing_nodes_assessed": [{
                "node_id": node, "disposition": "NON_BLOCKING_LIMITATION",
                "reason": "not needed for the bounded chapter-handoff question",
            } for node in analysis["metric_tree_coverage"]["missing_nodes"]],
            "recalculation_disagreements": [],
            "causal_strength_cap": wf._maximum_strength_cap(manifest),
            "prohibited_claims": ["Do not claim causality from aggregate observational snapshots."],
        }

    def text_payload(self, manifest, run_id="run"):
        sample = self.contexts[run_id]["sample"]
        if sample < 30:
            return {
                "diagnosis_status": "NOT_APPLICABLE", "online_version_status": "NOT_APPLICABLE",
                "online_version_evidence": [], "body_modified": False,
                "hypotheses_checked": [], "proposals": [],
                "not_applicable_reason": "No data-supported text hypothesis is allowed below the sample floor.",
            }
        analysis_path = self.root / run_id / [entry["file"] for entry in manifest["artifacts"] if entry["kind"] == "analysis"][-1]
        analysis = json.loads(analysis_path.read_text(encoding="utf-8"))["payload"]
        return {
            "diagnosis_status": "PROPOSAL_READY", "online_version_status": "VERIFIED",
            "online_version_evidence": [{
                "source": "test fixture mirror", "checked_at": "2026-08-12T12:30:00+08:00",
                "work_id": self.WORK_ID, "version_sha256": self.target_hash,
                "evidence_files": [str(self.target)], "evidence_hashes": [self.target_hash],
            }],
            "body_modified": False,
            "hypotheses_checked": [{
                "hypothesis_id": "h1", "verdict": "SUPPORTED", "text_evidence_ids": ["e1"],
                "reason": "the delayed action appears before the measured handoff boundary",
            }],
            "proposals": [{
                "proposal_id": "p1", "action": "modify_text", "target": self.target_rel,
                "target_sha256_before": self.target_hash,
                "text_evidence": [{
                    "evidence_id": "e1", "path": self.target_rel, "path_sha256": self.target_hash,
                    "location": "paragraph 2", "quote": "却先回忆了三页家史",
                    "observation": "the promised action is delayed by backstory",
                }],
                "data_trigger": {
                    "metric_ids": ["long_chapter_follow_rate_sync"],
                    "analysis_evidence_refs": analysis["evidence_refs"], "hypothesis_ids": ["h1"],
                },
                "change_intent": "move the concrete decision before the backstory",
                "reader_mechanism": "reduce the intention-action delay before the next-chapter click",
                "expected_metric": "long_chapter_follow_rate_sync", "single_variable": True,
                "counterfactual": "if delay is causal, an earlier decision should improve the same handoff",
                "do_not_change": ["character motive", "next-chapter opening"],
                "guardrails": ["continuity", "promise payoff", "no new plot facts"],
                "validation_plan": {
                    "main_metric": "long_chapter_follow_rate_sync",
                    "guard_metrics": ["long_chapter_reach_count"], "minimum_sample": 30,
                    "earliest_data_until": "2026-08-12",
                    "decision_rule": "improve beyond historical noise with no reach regression",
                    "rollback_rule": "restore the frozen target if the handoff regresses after the sample floor",
                },
            }],
        }

    def supervision_payload(self, manifest, run_id="run"):
        kind_hashes = {
            kind: self._kind_hash(manifest, kind) for kind in wf.KIND_FLOW if kind != "supervision"
        }
        checks = []
        mapping = {
            "G1": {kind_hashes["raw_capture"]}, "G2": {kind_hashes["data_quality"]},
            "G3": {kind_hashes["window_bound"]}, "G4": {kind_hashes["metrics"]},
            "G5": {kind_hashes["analysis"]}, "G6": {kind_hashes["validation"]},
            "G7": {kind_hashes["text_diagnosis"]}, "G8": set(manifest["artifact_hashes"]),
        }
        for gate in wf.REQUIRED_SUPERVISION_GATES:
            checks.append({"check_id": gate, "status": "PASS", "evidence": sorted(mapping[gate])})
        cap = wf._maximum_strength_cap(manifest)
        claim = (
            "当前仅能确认已观察到数据，样本不足，不能评价改版效果。"
            if cap == "OBSERVED_ONLY"
            else "第1→2章同步转化相对基线上升，但结论仍是非因果关联。"
        )
        return {
            "mode": "OBSERVE_ONLY", "decision": "PASS", "stage_checks": checks,
            "novel_edits_made": False, "artifact_hashes_verified": True,
            "role_separation_verified": True, "reviewed_chain_head_sha256": manifest["chain_head_sha256"],
            "accepted_findings": [{
                "finding_id": "finding-primary", "source_stage": "analysis", "claim": claim,
                "evidence_refs": [kind_hashes["analysis"], kind_hashes["validation"]],
                "reason": "bounded by sample and causal-strength gates",
            }],
            "rejected_findings": [],
            "report_claims": [{
                "claim_id": "claim-primary", "text": claim,
                "strength": "OBSERVED" if cap == "OBSERVED_ONLY" else "ASSOCIATION",
                "evidence_refs": [kind_hashes["analysis"], kind_hashes["validation"]],
            }],
            "final_strength_cap": cap,
        }

    def record(self, manifest, kind, payload, run_id="run", producer=None):
        value = copy.deepcopy(payload)
        if kind != "raw_capture":
            value.setdefault("input_artifact_hashes", [manifest["chain_head_sha256"]])
        return wf.record_artifact(
            self.root, run_id, kind=kind, payload=value,
            producer=producer or wf.EXPECTED_PRODUCERS[kind], expected_revision=manifest["revision"],
        )

    def advance_to_metrics(self, sample=120, run_id="run"):
        manifest = self.init(run_id, sample)
        manifest = self.record(manifest, "raw_capture", self.raw_payload(manifest, run_id), run_id)
        manifest = self.record(manifest, "data_quality", self.quality_payload(manifest, run_id), run_id)
        manifest = self.record(manifest, "window_bound", self.window_payload(run_id), run_id)
        return self.record(manifest, "metrics", self.metrics_payload(manifest, run_id), run_id)

    def advance_to_complete(self, sample=120, run_id="run"):
        manifest = self.advance_to_metrics(sample, run_id)
        manifest = self.record(manifest, "analysis", self.analysis_payload(manifest, run_id), run_id)
        manifest = self.record(manifest, "validation", self.validation_payload(manifest, run_id), run_id)
        manifest = self.record(manifest, "text_diagnosis", self.text_payload(manifest, run_id), run_id)
        manifest = self.record(manifest, "supervision", self.supervision_payload(manifest, run_id), run_id)
        supervision_path = self.root / run_id / [entry["file"] for entry in manifest["artifacts"] if entry["kind"] == "supervision"][-1]
        supervision = json.loads(supervision_path.read_text(encoding="utf-8"))["payload"]
        claim = supervision["report_claims"][0]["text"]
        report = (
            f"# 数据分析报告\n\n数据截止日：2026-08-11\n\n结论强度：{supervision['final_strength_cap']}\n\n"
            f"关键指标：{claim}\n\n瓶颈：第1→2章。\n\n下一步：按实验卡验证。\n\n"
            f"证据哈希：{manifest['chain_head_sha256']}\n"
        )
        return wf.complete_run(
            self.root, run_id, report_text=report, producer="story-data-supervisor",
            expected_revision=manifest["revision"],
        )

    def test_full_workflow_replays_to_report_complete(self):
        manifest = self.advance_to_complete()
        self.assertEqual("REPORT_COMPLETE", manifest["state"])
        self.assertTrue(wf.verify_integrity(self.root, "run", manifest)["ok"])

    def test_frozen_legacy_snapshots_complete_only_as_observed_sample_unavailable(self):
        run_id = "historical-real"
        work_id = "1000000000000000000"
        raw_root = HISTORICAL_FIXTURES / "raw"
        registry = HISTORICAL_FIXTURES / "config" / "frozen-snapshots.v1.json"
        paths = {
            "baseline": raw_root / "2026-08-08.json",
            "previous_snapshot": raw_root / "2026-08-10.json",
            "latest_snapshot": raw_root / "2026-08-11.json",
        }
        raws = {role: json.loads(path.read_text(encoding="utf-8")) for role, path in paths.items()}
        scope = {
            "platform": "fanqie", "work_type": "long", "work_id": work_id,
            "mode": "snapshot", "question": "Did the first-chapter revision improve the first-three-chapter handoff?",
            "expected_snapshot_date": "2026-08-11", "expected_data_until": "2026-08-10",
            "causal_design_verified": False,
        }
        manifest = wf.init_run(self.root, run_id, scope=scope)
        latest = paths["latest_snapshot"]
        latest_hash = wf.sha256_file(latest)
        raw_payload = {
            "status": "PARTIAL", "source_files": [str(latest)], "source_hashes": [latest_hash],
            "snapshot_file": str(latest), "snapshot_sha256": latest_hash,
            "capture_mode": "frozen_snapshot", "work_id": work_id,
            "run_scope_sha256": manifest["scope_sha256"], "snapshot_date": "2026-08-11",
            "data_until": "2026-08-10", "pulled_at": "2026-08-11T13:20:00+08:00",
            "login_status": "NOT_APPLICABLE",
            "endpoint_status": {"historical_capture": {"source_hash_verified": True}},
            "required_endpoint_names": ["historical_capture"],
            "usable_fields": ["novel_chapters.read", "novel_metrics", "novel_traffic"],
            "snapshot_metadata_verified": True, "work_identity_status": "VERIFIED_FROZEN_REGISTRY",
            "identity_evidence_files": [str(registry)],
            "identity_evidence_hashes": [wf.sha256_file(registry)],
        }
        manifest = self.record(manifest, "raw_capture", raw_payload, run_id)

        normalized = nr.normalize_file(
            latest, expected_snapshot_date="2026-08-11", expected_data_until="2026-08-10",
            expected_work_id=work_id, scope="long",
        )
        normalized_hash = wf.sha256_bytes(wf.canonical_bytes(normalized))
        quality_checks = [
            {"check_id": "freshness", "status": "PASS", "evidence": ["snapshot/date relation recomputed"]},
            {"check_id": "work_identity", "status": "PARTIAL", "evidence": ["legacy hash registry only"]},
            {"check_id": "endpoint_health", "status": "PARTIAL", "evidence": ["legacy endpoint status unavailable"]},
            {"check_id": "presence_semantics", "status": "PASS", "evidence": ["missing/null/zero preserved"]},
            {"check_id": "formula_consistency", "status": "PARTIAL", "evidence": ["chapter curve monotonicity warning"]},
            {"check_id": "scope", "status": "PARTIAL", "evidence": ["legacy identity is registry-bound"]},
        ]
        quality_payload = {
            "status": "PARTIAL", "snapshot_date": "2026-08-11", "data_until": "2026-08-10",
            "expected_snapshot_date": "2026-08-11", "expected_data_until": "2026-08-10",
            "sample_size": 0, "sample_size_qualified": False, "sample_size_authoritative": False,
            "sample_size_basis": "authoritative first-three-chapter cohort unavailable",
            "sample_size_evidence": [], "sample_aggregation": "unavailable",
            "sample_unavailability_reasons": [
                "legacy snapshot exposes display percentages but no authoritative chapter cohort count"
            ],
            "scope_verified": True, "work_id": work_id, "expected_work_id": work_id,
            "work_id_verified": True, "usable_fields": normalized["quality"]["usable_fields"],
            "quality_checks": quality_checks, "branch_statuses": {"long_novel": "PARTIAL"},
            "normalizer_version": str(normalized["normalization_schema_version"]),
            "normalized_snapshot": normalized, "normalized_snapshot_sha256": normalized_hash,
            "raw_snapshot_sha256": latest_hash,
        }
        manifest = self.record(manifest, "data_quality", quality_payload, run_id)

        registry_hash = wf.sha256_file(registry)
        refs = {}
        for role, path in paths.items():
            raw = raws[role]
            refs[role] = {
                "snapshot_date": raw["date"], "data_until": raw["data_until"],
                "source_file": str(path), "source_sha256": wf.sha256_file(path),
                "work_id": work_id, "work_identity_status": "VERIFIED_FROZEN_REGISTRY",
                "identity_evidence_files": [str(registry)], "identity_evidence_hashes": [registry_hash],
            }
        change_log = HISTORICAL_FIXTURES / "番茄数据日志.md"
        window_payload = {
            "analysis_mode": "modification_effect", "analysis_question": scope["question"],
            "baseline": refs["baseline"], "previous_snapshot": refs["previous_snapshot"],
            "latest_snapshot": refs["latest_snapshot"],
            "changes": [{
                "change_id": "chapter-1-ending-2026-08-08", "published_at": "2026-08-08T01:19:00+08:00",
                "first_covered_data_date": "2026-08-08", "first_full_data_date": "2026-08-09",
                "coverage_status": "FULL_DAY_COVERED",
                "target_metric_ids": ["long_chapter_reach_rate", "long_chapter_follow_rate_sync"],
                "version_status": "VERIFIED", "version_evidence": [{
                    "source_file": str(change_log), "source_sha256": wf.sha256_file(change_log),
                    "evidence_type": "project_change_log", "verification_strength": "DIRECT",
                    "record_locator": "2026-08-08 01:19–01:20",
                    "assertion": "the project log records the first-chapter publication time and edit scope",
                }],
                "coverage_evidence": ["latest cutoff is after the first full data date"],
                "concurrent_events": ["continued chapter publication"],
            }],
            "confounders": [{
                "confounder_id": "search-self-visit", "status": "UNKNOWN",
                "evidence": ["search traffic dominates and visitor identity is unavailable"],
            }],
        }
        manifest = self.record(manifest, "window_bound", window_payload, run_id)

        facts = []
        for role in ("baseline", "previous_snapshot", "latest_snapshot"):
            raw = raws[role]
            display_value = raw["novel_chapters"][1]["read"]
            dimensions = {
                "work_id": work_id, "chapter_index": 2, "chapter_version": "legacy-mixed-or-unknown",
                "data_until": raw["data_until"],
            }
            facts.append({
                "metric_id": "long_chapter_reach_rate", "value": float(display_value),
                "unit": "percent", "time_grain": "cumulative_snapshot", "dimensions": dimensions,
                "quality_status": "PARTIAL", "authoritative": True,
                "source_refs": [manifest["chain_head_sha256"]],
                "source_observations": [{
                    "source_role": role, "source_sha256": refs[role]["source_sha256"],
                    "json_pointer": "/novel_chapters/1/read", "value": display_value,
                }],
                "calculation": {
                    "mode": "source", "operator": "identity", "expression": "displayed_chapter_2_reach_rate",
                    "input_values": [display_value],
                },
            })
        all_nodes = {
            node for node in self._tree_nodes()
            if node == "dq" or node.startswith("dq.") or node == "long" or node.startswith("long.")
        }
        node_statuses = []
        diagnostic_nodes = {"dq", "long", "long.golden_three"} | {
            node for node in all_nodes if node.startswith("dq.")
        }
        for node in sorted(all_nodes):
            if node == "long.activation_depth.chapter_curve":
                status, metric_ids, evidence, reason = (
                    "MEASURED", ["long_chapter_reach_rate"], [manifest["chain_head_sha256"]],
                    "displayed reach-rate facts are available",
                )
            elif node in diagnostic_nodes:
                status, metric_ids, evidence, reason = (
                    "DIAGNOSTICALLY_CHECKED", [], [manifest["chain_head_sha256"]],
                    "quality or parent node checked",
                )
            else:
                status, metric_ids, evidence, reason = (
                    "UNAVAILABLE", [], [], "no authoritative metric fact in the legacy snapshot",
                )
            node_statuses.append({
                "node_id": node, "status": status, "metric_ids": metric_ids,
                "evidence": evidence, "reason": reason,
            })
        definitions = self._definition_artifacts()
        metrics_payload = {
            "metric_catalog_version": definitions["metric_catalog"]["version"],
            "definition_artifacts": definitions, "facts": facts,
            "computed_metric_ids": ["long_chapter_reach_rate"],
            "required_nodes_checked": sorted(all_nodes), "node_statuses": node_statuses,
            "quality_summary": {
                "status": "PARTIAL",
                "limitations": ["chapter cohort denominator unavailable; only displayed rates are usable"],
            },
        }
        manifest = self.record(manifest, "metrics", metrics_payload, run_id)
        missing = sorted(row["node_id"] for row in node_statuses if row["status"] == "UNAVAILABLE")
        evidence_refs = [self._kind_hash(manifest, "window_bound"), manifest["chain_head_sha256"]]
        analysis_payload = {
            "overall_status": "SAMPLE_INSUFFICIENT", "sample_size": 0,
            "strong_conclusion": False, "causal_attribution": False,
            "sample_metric_id": "UNAVAILABLE",
            "sample_evidence_refs": [self._kind_hash(manifest, "data_quality")],
            "metric_tree_coverage": {
                "checked_nodes": sorted(all_nodes), "missing_nodes": missing,
                "missing_node_reasons": {node: "legacy snapshot has no qualified fact" for node in missing},
            },
            "anomalies": [], "hypotheses": [], "evidence_refs": evidence_refs,
            "anomaly_rule_evidence": [{
                "rule": "no qualified denominator => descriptive rates only", "result": "INCONCLUSIVE"
            }],
            "linked_metric_checks": [{
                "metric_id": "long_chapter_reach_rate", "status": "CHECKED",
                "evidence_refs": evidence_refs,
                "finding": "chapter-2 displayed reach rate is 35% at baseline and 32% latest",
            }],
            "primary_constraint": "qualified first-three-chapter cohort is unavailable",
            "primary_constraint_node": "long.activation_depth.chapter_curve",
            "change_assessments": [{
                "change_id": "chapter-1-ending-2026-08-08",
                "status": "SAMPLE_INSUFFICIENT", "direction": "UNKNOWN",
                "coverage_status": "FULL_DAY_COVERED", "version_status": "VERIFIED",
                "evaluated_metric_ids": ["long_chapter_reach_rate"],
                "evidence_refs": evidence_refs,
                "rationale": "the display rate changed, but an authoritative chapter cohort is unavailable",
            }],
        }
        manifest = self.record(manifest, "analysis", analysis_payload, run_id)
        recalculation = [{
            "metric_id": fact["metric_id"], "dimensions": fact["dimensions"],
            "formula": fact["calculation"]["expression"], "source_refs": fact["source_refs"],
            "source_observations": fact["source_observations"], "calculation": fact["calculation"],
            "recalculated_value": fact["value"],
        } for fact in facts]
        validation_payload = {
            "decision": "PASS", "independent_recalculation": recalculation,
            "logic_checks": [{
                "check_id": check_id, "status": "PASS", "evidence": [manifest["chain_head_sha256"]]
            } for check_id in wf.REQUIRED_LOGIC_CHECKS],
            "method_checks": [{
                "check_id": check_id, "status": "PASS", "evidence": [manifest["chain_head_sha256"]]
            } for check_id in wf.REQUIRED_METHOD_CHECKS],
            "input_hashes_verified": True, "validator_independent": True,
            "reviewed_analysis_sha256": manifest["chain_head_sha256"],
            "missing_nodes_assessed": [{
                "node_id": node, "disposition": "NON_BLOCKING_LIMITATION",
                "reason": "the report is explicitly limited to observed display rates",
            } for node in missing],
            "recalculation_disagreements": [], "causal_strength_cap": "OBSERVED_ONLY",
            "prohibited_claims": [
                "Do not subtract percentage-derived lower bounds or claim that the revision improved."
            ],
        }
        manifest = self.record(manifest, "validation", validation_payload, run_id)
        text_payload = {
            "diagnosis_status": "NOT_APPLICABLE", "online_version_status": "NOT_APPLICABLE",
            "online_version_evidence": [], "body_modified": False,
            "hypotheses_checked": [], "proposals": [],
            "not_applicable_reason": "No qualified anomaly or data-supported text hypothesis exists.",
        }
        manifest = self.record(manifest, "text_diagnosis", text_payload, run_id)
        kind_hashes = {
            kind: self._kind_hash(manifest, kind) for kind in wf.KIND_FLOW if kind != "supervision"
        }
        mapping = {
            "G1": {kind_hashes["raw_capture"]}, "G2": {kind_hashes["data_quality"]},
            "G3": {kind_hashes["window_bound"]}, "G4": {kind_hashes["metrics"]},
            "G5": {kind_hashes["analysis"]}, "G6": {kind_hashes["validation"]},
            "G7": {kind_hashes["text_diagnosis"]}, "G8": set(manifest["artifact_hashes"]),
        }
        claim = (
            "只能确认第2章展示到达率由基线35%变为最新32%；权威章节 cohort 不可得，"
            "不能评价第1章改版是否改善。"
        )
        supervision_payload = {
            "mode": "OBSERVE_ONLY", "decision": "PASS",
            "stage_checks": [{
                "check_id": gate, "status": "PASS", "evidence": sorted(mapping[gate])
            } for gate in wf.REQUIRED_SUPERVISION_GATES],
            "novel_edits_made": False, "artifact_hashes_verified": True,
            "role_separation_verified": True,
            "reviewed_chain_head_sha256": manifest["chain_head_sha256"],
            "accepted_findings": [{
                "finding_id": "historical-descriptive-rate", "source_stage": "analysis",
                "claim": claim, "evidence_refs": [kind_hashes["analysis"], kind_hashes["validation"]],
                "reason": "the qualified sample gate caps the claim at observed display rates",
            }],
            "rejected_findings": [], "report_claims": [{
                "claim_id": "historical-observed-only", "text": claim, "strength": "OBSERVED",
                "evidence_refs": [kind_hashes["analysis"], kind_hashes["validation"]],
            }],
            "final_strength_cap": "OBSERVED_ONLY",
        }
        manifest = self.record(manifest, "supervision", supervision_payload, run_id)
        report = (
            "# 历史快照回放\n\n数据截止日：2026-08-10\n\n结论强度：OBSERVED_ONLY\n\n"
            f"关键指标：{claim}\n\n瓶颈：权威章节 cohort 缺失。\n\n"
            "下一步：等待平台直接人数或明确 cohort 后再判断。\n\n"
            f"证据哈希：{manifest['chain_head_sha256']}\n"
        )
        manifest = wf.complete_run(
            self.root, run_id, report_text=report, producer="story-data-supervisor",
            expected_revision=manifest["revision"],
        )
        self.assertEqual("REPORT_COMPLETE", manifest["state"])
        self.assertFalse(manifest["sample_size_qualified"])
        self.assertTrue(wf.verify_integrity(self.root, run_id, manifest)["ok"])

    def test_illegal_skip_and_wrong_producer_are_rejected(self):
        manifest = self.init()
        with self.assertRaises(wf.GateError):
            self.record(manifest, "metrics", {}, producer="story-data-metric-engine")
        with self.assertRaises(wf.GateError):
            self.record(manifest, "raw_capture", self.raw_payload(manifest), producer="same-agent")
        self.assertEqual(0, wf.load_manifest(self.root, "run")["revision"])

    def test_fake_missing_mismatched_raw_is_rejected(self):
        manifest = self.init()
        payload = self.raw_payload(manifest)
        payload["snapshot_file"] = str(self.temp_path / "missing.json")
        payload["source_files"] = [payload["snapshot_file"]]
        with self.assertRaises(wf.GateError):
            self.record(manifest, "raw_capture", payload)
        payload = self.raw_payload(manifest)
        payload["source_hashes"] = []
        with self.assertRaises(wf.GateError):
            self.record(manifest, "raw_capture", payload)
        payload = self.raw_payload(manifest)
        payload["source_hashes"] = ["f" * 64]
        payload["snapshot_sha256"] = "f" * 64
        with self.assertRaises(wf.IntegrityError):
            self.record(manifest, "raw_capture", payload)

    def test_empty_window_metrics_validation_and_supervision_cannot_pass(self):
        manifest = self.init()
        manifest = self.record(manifest, "raw_capture", self.raw_payload(manifest))
        manifest = self.record(manifest, "data_quality", self.quality_payload(manifest))
        with self.assertRaises(wf.GateError):
            self.record(manifest, "window_bound", {
                "analysis_mode": "modification_effect", "analysis_question": self.scope()["question"],
                "baseline": {}, "previous_snapshot": {}, "latest_snapshot": {}, "changes": [], "confounders": [],
            })
        manifest = self.record(manifest, "window_bound", self.window_payload())
        bad_metrics = self.metrics_payload(manifest)
        bad_metrics["facts"] = []
        with self.assertRaises(wf.GateError):
            self.record(manifest, "metrics", bad_metrics)
        manifest = self.record(manifest, "metrics", self.metrics_payload(manifest))
        manifest = self.record(manifest, "analysis", self.analysis_payload(manifest))
        bad_validation = self.validation_payload(manifest)
        bad_validation["independent_recalculation"] = []
        with self.assertRaises(wf.GateError):
            self.record(manifest, "validation", bad_validation)
        manifest = self.record(manifest, "validation", self.validation_payload(manifest))
        manifest = self.record(manifest, "text_diagnosis", self.text_payload(manifest))
        bad_supervision = self.supervision_payload(manifest)
        bad_supervision["stage_checks"] = []
        with self.assertRaises(wf.GateError):
            self.record(manifest, "supervision", bad_supervision)

    def test_future_change_cannot_be_claimed_as_covered(self):
        manifest = self.init()
        manifest = self.record(manifest, "raw_capture", self.raw_payload(manifest))
        manifest = self.record(manifest, "data_quality", self.quality_payload(manifest))
        bad = self.window_payload()
        bad["changes"][0].update({
            "published_at": "2099-01-01T01:00:00+08:00",
            "first_covered_data_date": "2099-01-01",
            "first_full_data_date": "2099-01-02",
            "coverage_status": "FULL_DAY_COVERED",
        })
        with self.assertRaises(wf.GateError):
            self.record(manifest, "window_bound", bad)

    def test_lower_bound_cannot_qualify_as_sample_denominator(self):
        manifest = self.init()
        manifest = self.record(manifest, "raw_capture", self.raw_payload(manifest))
        payload = self.quality_payload(manifest)
        lower = payload["normalized_snapshot"]["facts"]["long_novel"]["minimum_compatible_cohort_lower_bound"]["value"]
        payload.update({
            "sample_size": lower,
            "sample_size_qualified": True,
            "sample_size_authoritative": True,
            "sample_size_basis": "forbidden display-derived lower bound",
            "sample_size_evidence": [{
                "source_sha256": payload["normalized_snapshot_sha256"],
                "json_pointer": "/facts/long_novel/minimum_compatible_cohort_lower_bound/value",
                "value": lower, "authoritative": True, "role": "forbidden substitute denominator",
            }],
        })
        with self.assertRaises(wf.GateError):
            self.record(manifest, "data_quality", payload)

        unavailable = self.quality_payload(manifest)
        unavailable.update({
            "sample_size": 0, "sample_size_qualified": False,
            "sample_size_authoritative": False, "sample_size_basis": "authoritative cohort unavailable",
            "sample_size_evidence": [], "sample_aggregation": "unavailable",
            "sample_unavailability_reasons": ["only display percentages are available"],
        })
        manifest = self.record(manifest, "data_quality", unavailable)
        self.assertFalse(manifest["sample_size_qualified"])

    def test_manifest_state_tampering_is_detected_by_replay(self):
        manifest = self.init()
        path = self.root / "run" / "manifest.json"
        tampered = json.loads(path.read_text(encoding="utf-8"))
        tampered.update({"state": "SUPERVISED", "stage": "SUPERVISED", "supervisor_verdict": "PASS"})
        path.write_bytes(wf.canonical_bytes(tampered))
        with self.assertRaises(wf.IntegrityError):
            wf.verify_integrity(self.root, "run")

    def test_hash_tampering_is_detected(self):
        manifest = self.init()
        manifest = self.record(manifest, "raw_capture", self.raw_payload(manifest))
        artifact = self.root / "run" / manifest["artifacts"][0]["file"]
        os.chmod(artifact, 0o644)
        artifact.write_text("{}\n", encoding="utf-8")
        with self.assertRaises(wf.IntegrityError):
            wf.verify_integrity(self.root, "run")

    def test_orphan_artifact_is_quarantined_by_recovery(self):
        manifest = self.init()
        manifest = self.record(manifest, "raw_capture", self.raw_payload(manifest))
        orphan = self.root / "run" / "99_crash.attempt-01.json"
        orphan.write_text('{"incomplete":true}\n', encoding="utf-8")
        with self.assertRaises(wf.IntegrityError):
            wf.verify_integrity(self.root, "run")
        recovered = wf.recover_run(self.root, "run")
        self.assertEqual(1, len(recovered["quarantined_orphans"]))
        self.assertFalse(orphan.exists())
        self.assertTrue(wf.verify_integrity(self.root, "run")["ok"])

    def test_max_returns_is_fixed_globally_even_when_root_ids_change(self):
        with self.assertRaises(wf.WorkflowError):
            self.init(max_returns=999)
        manifest = self.advance_to_metrics()
        for attempt in range(1, 4):
            manifest = self.record(manifest, "analysis", self.analysis_payload(manifest))
            manifest = wf.return_run(
                self.root, "run", to_state="METRICS_READY", reason=f"repair {attempt}",
                root_cause_id=f"metric-window-{attempt}", error_code="WINDOW_MISMATCH",
                rejected_finding_ids=["finding-primary"], repair_requirements=["rebind window"],
                producer="story-data-method-validator", expected_revision=manifest["revision"],
            )
            self.assertEqual("METRICS_READY", manifest["state"])
        manifest = self.record(manifest, "analysis", self.analysis_payload(manifest))
        manifest = wf.return_run(
            self.root, "run", to_state="METRICS_READY", reason="fourth repair",
            root_cause_id="different-fourth-root", error_code="WINDOW_MISMATCH",
            rejected_finding_ids=["finding-primary"], repair_requirements=["rebind window"],
            producer="story-data-method-validator", expected_revision=manifest["revision"],
        )
        self.assertEqual("BLOCKED", manifest["state"])
        self.assertIn("RETURN_LIMIT_EXCEEDED", manifest["blocked_reason"])

    def test_under_30_forbids_improvement_and_causality(self):
        manifest = self.advance_to_metrics(sample=29)
        bad = self.analysis_payload(manifest)
        bad.update({"overall_status": "IMPROVED", "causal_attribution": True})
        with self.assertRaises(wf.GateError):
            self.record(manifest, "analysis", bad)
        bad_change = self.analysis_payload(manifest)
        bad_change["change_assessments"][0].update({"status": "IMPROVED", "direction": "UP"})
        with self.assertRaises(wf.GateError):
            self.record(manifest, "analysis", bad_change)
        manifest = self.record(manifest, "analysis", self.analysis_payload(manifest))
        self.assertEqual("ANALYZED", manifest["state"])

    def test_change_assessments_are_exhaustive_target_bound_and_direction_aware(self):
        manifest = self.advance_to_metrics()
        missing = self.analysis_payload(manifest)
        missing["change_assessments"] = []
        with self.assertRaises(wf.GateError):
            self.record(manifest, "analysis", missing)

        unknown = self.analysis_payload(manifest)
        unknown["change_assessments"][0]["change_id"] = "invented-change"
        with self.assertRaises(wf.GateError):
            self.record(manifest, "analysis", unknown)

        escaped = self.analysis_payload(manifest)
        escaped["change_assessments"][0]["evaluated_metric_ids"] = ["long_chapter_reach_count"]
        with self.assertRaises(wf.GateError):
            self.record(manifest, "analysis", escaped)

        wrong_direction = self.analysis_payload(manifest)
        wrong_direction["change_assessments"][0]["direction"] = "DOWN"
        with self.assertRaises(wf.GateError):
            self.record(manifest, "analysis", wrong_direction)

    def test_analysis_delta_and_validator_formula_are_recomputed(self):
        manifest = self.advance_to_metrics()
        bad_analysis = self.analysis_payload(manifest)
        bad_analysis["anomalies"][0]["delta"] = 999
        with self.assertRaises(wf.GateError):
            self.record(manifest, "analysis", bad_analysis)
        manifest = self.record(manifest, "analysis", self.analysis_payload(manifest))
        bad_validation = self.validation_payload(manifest)
        bad_validation["independent_recalculation"][0]["formula"] = "copied result without formula"
        with self.assertRaises(wf.GateError):
            self.record(manifest, "validation", bad_validation)

    def test_procedural_authorization_is_bound_but_cannot_auto_execute(self):
        manifest = self.advance_to_complete()
        proposal = json.loads((self.root / "run" / [entry["file"] for entry in manifest["artifacts"] if entry["kind"] == "text_diagnosis"][-1]).read_text(encoding="utf-8"))["payload"]["proposals"][0]
        message_hash = hashlib.sha256(b"user approves p1 exactly").hexdigest()
        authorization = {
            "decision": "APPROVED", "authorized_by": "user", "user_confirmation": True,
            "attestation_status": "UNATTESTED_PROCEDURAL",
            "user_event_id": "event-1", "user_message_sha256": message_hash,
            "authorization_nonce": wf._authorization_nonce("run", manifest["chain_head_sha256"], "event-1", message_hash),
            "proposal_ids": ["p1"], "authorized_scope": [proposal["target"]],
            "authorized_actions": [{
                "proposal_id": "p1", "action": proposal["action"], "target": proposal["target"],
                "target_sha256_before": proposal["target_sha256_before"],
            }],
            "confirmed_at": "2026-08-12T13:00:00+08:00",
        }
        bad = dict(authorization)
        bad["authorization_nonce"] = "0" * 64
        with self.assertRaises(wf.GateError):
            wf.authorize_run(self.root, "run", authorization=bad, expected_revision=manifest["revision"])
        manifest = wf.authorize_run(
            self.root, "run", authorization=authorization, expected_revision=manifest["revision"]
        )
        self.assertFalse(wf.path_is_authorized(manifest, self.target_rel))
        self.assertFalse(wf.path_is_authorized(manifest, "another.md"))
        wf.verify_integrity(self.root, "run", manifest)

    def case_payload(self, manifest):
        required_kinds = {"analysis", "validation", "text_diagnosis", "supervision"}
        return {
            "case_id": "case-1", "title": "verified workflow, outcome pending",
            "verification_level": "ANALYSIS_VERIFIED_OUTCOME_UNVERIFIED",
            "context": {"work_id": self.WORK_ID, "question": self.scope()["question"]},
            "input_hashes": [entry["sha256"] for entry in manifest["artifacts"] if entry["kind"] in required_kinds],
            "metric_definition_version": "metrics.v1",
            "anomaly": {"metric_id": "long_chapter_follow_rate_sync", "delta_pp": 10},
            "diagnostic_metrics": ["long_chapter_reach_count", "long_chapter_follow_rate_sync"],
            "text_evidence": [{"path": self.target_rel, "sha256": self.target_hash}],
            "proposal": {"proposal_id": "p1", "target": self.target_rel},
            "outcome": {"status": "outcome_unverified", "reason": "not published"},
            "alternative_explanations": ["traffic mix", "returning-reader mix"],
            "applicability": {"work_type": "long", "boundary": "first-three chapter handoff"},
        }

    def test_case_promotion_requires_real_evidence_and_rejects_fake_verified_improvement(self):
        manifest = self.advance_to_complete()
        knowledge = self.temp_path / "knowledge"
        case = self.case_payload(manifest)
        promoted = wf.promote_case(
            self.root, knowledge, "run", case=case, producer="story-data-supervisor",
            expected_revision=manifest["revision"],
        )
        self.assertTrue((knowledge / "case-1.json").is_file())
        wf.verify_integrity(self.root, "run", promoted)
        (knowledge / "case-1.json").unlink()
        with self.assertRaises(wf.IntegrityError):
            wf.verify_integrity(self.root, "run", promoted)
        recovery = wf.recover_run(self.root, "run")
        self.assertEqual([str((knowledge / "case-1.json").resolve())], recovery["restored_knowledge"])
        self.assertTrue((knowledge / "case-1.json").is_file())

        fake = self.case_payload(manifest)
        fake.update({"case_id": "fake", "verification_level": "VERIFIED_IMPROVEMENT"})
        fake["outcome"] = {
            "status": "verified_improvement", "verification_run_ids": ["run", "run"],
            "window_coverage_verified": True, "mde_evaluated": True,
            "guardrails_pass": True, "replicated_windows": 2,
        }
        with self.assertRaises(wf.GateError):
            wf.promote_case(
                self.root, knowledge, "run", case=fake, producer="story-data-supervisor",
                expected_revision=promoted["revision"],
            )

    def test_method_promotion_is_versioned(self):
        manifest = self.advance_to_complete()
        method = {
            "method_id": "chapter-funnel-drilldown", "version": "v1",
            "title": "chapter funnel drilldown", "scope": {"work_type": "long"},
            "problem": "locate the earliest valid handoff anomaly",
            "method_steps": ["quality gate", "recalculate", "check neighbors"],
            "required_inputs": ["metric catalog", "chapter snapshot"],
            "decision_rules": ["do not attribute below the sample floor"],
            "limitations": ["aggregate snapshots are not new-reader cohorts"],
            "sources": [{"kind": "official_definition", "title": "chapter follow rate"}],
            "status": "ACTIVE",
        }
        knowledge = self.temp_path / "methods"
        manifest = wf.promote_method(
            self.root, knowledge, "run", method=method, producer="story-data-supervisor",
            expected_revision=manifest["revision"],
        )
        self.assertTrue((knowledge / "chapter-funnel-drilldown@v1.json").is_file())
        bad_v2 = dict(method)
        bad_v2["version"] = "v2"
        with self.assertRaises(wf.GateError):
            wf.promote_method(
                self.root, knowledge, "run", method=bad_v2, producer="story-data-supervisor",
                expected_revision=manifest["revision"],
            )


if __name__ == "__main__":
    unittest.main()
