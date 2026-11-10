import json
import pathlib
import unittest


SKILL_ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTRACTS = SKILL_ROOT / "contracts"
DICTIONARY = SKILL_ROOT / "dictionary"


def collect_ids(value):
    result = set()
    if isinstance(value, dict):
        if isinstance(value.get("id"), str):
            result.add(value["id"])
        for child in value.values():
            result.update(collect_ids(child))
    elif isinstance(value, list):
        for child in value:
            result.update(collect_ids(child))
    return result


class ContractTest(unittest.TestCase):
    def test_every_contract_is_valid_json_with_object_root(self):
        files = sorted(CONTRACTS.glob("*.schema.json"))
        self.assertGreaterEqual(len(files), 10)
        for path in files:
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual("object", document.get("type"), path.name)
            self.assertIsInstance(document.get("required", []), list, path.name)

    def test_runtime_lane_required_fields_are_present_in_contracts(self):
        expected = {
            "raw-capture.schema.json": {
                "status", "source_files", "source_hashes", "capture_mode", "work_id", "run_scope_sha256",
            },
            "data-quality.schema.json": {
                "normalized_snapshot", "normalized_snapshot_sha256", "raw_snapshot_sha256",
                "sample_size_qualified", "sample_size_evidence", "sample_unavailability_reasons",
                "quality_checks", "branch_statuses", "input_artifact_hashes",
            },
            "window-bound.schema.json": {
                "analysis_mode", "analysis_question", "baseline", "previous_snapshot",
                "latest_snapshot", "changes", "confounders", "input_artifact_hashes",
            },
            "metrics.schema.json": {
                "definition_artifacts", "facts", "computed_metric_ids", "required_nodes_checked",
                "node_statuses", "quality_summary", "input_artifact_hashes",
            },
            "analysis.schema.json": {
                "sample_metric_id", "sample_evidence_refs", "metric_tree_coverage", "evidence_refs",
                "anomaly_rule_evidence", "linked_metric_checks", "primary_constraint_node",
                "change_assessments",
            },
            "validation.schema.json": {
                "independent_recalculation", "logic_checks", "method_checks", "validator_independent",
                "reviewed_analysis_sha256", "missing_nodes_assessed", "causal_strength_cap",
            },
            "text-diagnosis.schema.json": {
                "diagnosis_status", "online_version_status", "online_version_evidence",
                "body_modified", "hypotheses_checked", "proposals",
            },
            "supervision.schema.json": {
                "stage_checks", "artifact_hashes_verified", "role_separation_verified",
                "reviewed_chain_head_sha256", "report_claims", "final_strength_cap",
            },
            "authorization.schema.json": {
                "user_event_id", "user_message_sha256", "authorization_nonce",
                "proposal_ids", "authorized_scope", "authorized_actions", "attestation_status",
            },
        }
        for filename, required in expected.items():
            document = json.loads((CONTRACTS / filename).read_text(encoding="utf-8"))
            self.assertTrue(required.issubset(set(document["required"])), filename)

    def test_text_target_representation_matches_runtime_and_hook(self):
        document = json.loads((CONTRACTS / "text-diagnosis.schema.json").read_text(encoding="utf-8"))
        target = document["$defs"]["proposal"]["properties"]["target"]
        self.assertEqual("string", target["type"])
        self.assertEqual(
            "^(?:[0-9a-f]{64}|MISSING)$",
            document["$defs"]["proposal"]["properties"]["target_sha256_before"]["pattern"],
        )

    def test_metric_tree_and_diagnostic_routes_are_referentially_complete(self):
        catalog = json.loads((DICTIONARY / "metrics.v1.json").read_text(encoding="utf-8"))
        tree = json.loads((DICTIONARY / "metric-tree.v1.json").read_text(encoding="utf-8"))
        routes = json.loads((DICTIONARY / "diagnostic-routes.v1.json").read_text(encoding="utf-8"))
        metric_rows = catalog["metrics"]
        metric_ids = [row["id"] for row in metric_rows]
        metric_id_set = set(metric_ids)
        tree_ids = collect_ids(tree["trees"])
        self.assertEqual(56, len(metric_rows))
        self.assertEqual(len(metric_ids), len(metric_id_set))
        self.assertEqual({"data_quality": 12, "long_novel": 29, "short_story": 15}, catalog["counts_by_scope"])
        self.assertEqual(catalog["metric_family_count"], len(metric_rows))
        self.assertEqual(metric_id_set, set(catalog["preferred_direction_by_metric"]))
        self.assertTrue(
            set(catalog["preferred_direction_by_metric"].values()).issubset(
                set(catalog["preferred_direction_vocabulary"])
            )
        )
        for row in metric_rows:
            self.assertIn(row["parent_node"], tree_ids, row["id"])
            self.assertTrue(set(row["must_joint_check"]).issubset(metric_id_set), row["id"])
            self.assertTrue(row["semantic_signature"], row["id"])
            self.assertTrue(row["limitations"], row["id"])
        self.assertEqual(25, len(routes["routes"]))
        self.assertEqual(routes["route_count"], len(routes["routes"]))
        for route in routes["routes"]:
            self.assertTrue(set(route["trigger_metric_ids"]).issubset(metric_id_set), route["id"])
            self.assertTrue(set(route["must_check_metric_ids"]).issubset(metric_id_set), route["id"])
            self.assertTrue(
                route.get("direct_edit_surfaces")
                or route.get("indirect_action_surfaces")
                or route.get("operational_actions"),
                route["id"],
            )
            self.assertTrue(route["cannot_infer"], route["id"])


if __name__ == "__main__":
    unittest.main()
