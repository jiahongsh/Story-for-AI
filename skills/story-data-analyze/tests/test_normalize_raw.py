import json
import pathlib
import sys
import tempfile
import unittest


SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]
HISTORICAL_FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "historical"
sys.path.insert(0, str(SCRIPTS))

import normalize_raw as nr  # noqa: E402


class NormalizeRawTest(unittest.TestCase):
    @staticmethod
    def healthy_endpoint():
        return {"http_ok": True, "json_ok": True, "business_code": 0}

    def minimal(self):
        return {
            "date": "2026-08-06",
            "data_until": "2026-08-05",
            "novel_chapters": [
                {"i": 1, "title": "一", "read": "100", "follow": "0", "words": 1000},
                {"i": 2, "title": "二", "read": None, "words": 900},
            ],
            "novel_trend_7d": [["0", "1"]],
            "shorts": [
                {
                    "name": "短篇", "id": "1", "sign": 5, "show": "10", "read": "0",
                    "s15": None, "s30": "0", "s60": "0", "fin": "0",
                    "day_show": "0", "day_read": "0",
                }
            ],
        }

    def expanded(self):
        raw = self.minimal()
        raw.pop("novel_trend_7d")
        raw.update(
            {
                "trend_dates": ["08-04", "08-05"],
                "novel_common": {"reader_uv_daily": "0", "rank_cat": None},
                "novel_metrics": {"阅读人数": ["0", "2"]},
                "novel_traffic": {"搜索": ["0", "2"]},
            }
        )
        return raw

    def v2(self):
        raw = self.expanded()
        endpoint_status = {
            name: self.healthy_endpoint() for name in (
                "chapter_list_v1", "book_common_v1", "book_increase_metrics",
                "book_increase_traffic", "short_book_list", "short_single_by_date:1",
            )
        }
        raw.update(
            {
                "schema_version": 2,
                "pulled_at": "2026-08-06T05:00:00+08:00",
                "timezone": "Asia/Shanghai",
                "novel_id": "book",
                "metric_definitions_checked": "2026-08-06",
                "short_query": {"scope_verified_against_ui": True},
                "endpoint_status": endpoint_status,
            }
        )
        return raw

    def valid_short_v2(self):
        raw = self.v2()
        raw["shorts"] = [{
            "name": "短篇", "id": "1", "sign": 5, "show": 100, "read": 50,
            "s15": 40, "s30": 30, "s60": 20, "fin": 10,
            "day_show": 100, "day_read": 50,
        }]
        return raw

    def test_detects_supported_shapes_and_rejects_future_schema(self):
        self.assertEqual("legacy_minimal", nr.detect_shape(self.minimal()))
        self.assertEqual("legacy_expanded", nr.detect_shape(self.expanded()))
        self.assertEqual("fanqie_v2", nr.detect_shape(self.v2()))
        legacy = nr.normalize_data(self.expanded(), scope="long", expected_work_id="book")
        self.assertEqual("SCOPE_UNKNOWN", legacy["quality"]["status"])
        self.assertTrue(legacy["quality"]["usable_fields"])
        current = nr.normalize_data(self.v2(), scope="long", expected_work_id="book")
        self.assertEqual("OK", current["quality"]["status"])
        future = self.v2()
        future["schema_version"] = 99
        with self.assertRaises(nr.NormalizationError):
            nr.normalize_data(future, scope="long", expected_work_id="book")

    def test_missing_null_zero_and_invalid_remain_distinct(self):
        result = nr.normalize_data(self.minimal(), scope="all", expected_work_id="book")
        first = result["facts"]["long_novel"]["chapters"][0]
        second = result["facts"]["long_novel"]["chapters"][1]
        self.assertEqual("zero", first["follow_read_percent"]["state"])
        self.assertEqual("null", second["read_completion_percent"]["state"])
        self.assertEqual("missing", second["follow_read_percent"]["state"])
        short = result["facts"]["short_stories"][0]
        self.assertEqual("zero", short["counts"]["reads"]["state"])
        self.assertEqual("null", short["counts"]["read_15s"]["state"])
        self.assertFalse(short["valid_for_analysis"])
        self.assertIn("zero_paths", result["quality"]["presence_summary"])

    def test_chapter_people_are_exact_only_with_exact_source(self):
        result = nr.normalize_data(self.expanded(), scope="long", expected_work_id="book")
        absolute = result["facts"]["long_novel"]["chapters"][0]["arrival_people"]
        self.assertEqual("unavailable", absolute["state"])
        self.assertEqual("not_computable", absolute["classification"])

        raw = self.v2()
        raw["novel_chapters"][0]["cohort_size"] = 31
        approximate = nr.normalize_data(raw, scope="long", expected_work_id="book")["facts"]["long_novel"]["chapters"][0]["arrival_people"]
        self.assertEqual("approximate_from_rounded_percentage", approximate["classification"])
        self.assertTrue(approximate["display_only"])

        raw["novel_chapters"][0]["arrival_uv"] = 31
        exact = nr.normalize_data(raw, scope="long", expected_work_id="book")["facts"]["long_novel"]["chapters"][0]["arrival_people"]
        self.assertEqual("exact_source_count", exact["classification"])
        self.assertFalse(exact["display_only"])

    def test_minimum_compatible_solution_is_a_lower_bound_not_an_estimate(self):
        raw = self.v2()
        raw["novel_chapters"] = [
            {"i": 1, "title": "一", "read": "100", "follow": "1", "loss": 0, "words": 1000},
            {"i": 2, "title": "二", "read": "32", "follow": "99.99", "loss": 68, "words": 1000},
            {"i": 3, "title": "三", "read": "28", "follow": "3.14", "loss": 72, "words": 1000},
            {"i": 4, "title": "四", "read": "16", "follow": None, "loss": 84, "words": 1000},
        ]
        result = nr.normalize_data(raw, scope="long", expected_work_id="book")
        base = result["facts"]["long_novel"]["minimum_compatible_cohort_lower_bound"]
        self.assertEqual(25, base["value"])
        self.assertEqual("minimum_compatible_integer_lower_bound", base["classification"])
        self.assertTrue(base["display_only"])
        self.assertFalse(base["authoritative"])
        self.assertIn("not an estimate", base["limitation"])
        chapters = result["facts"]["long_novel"]["chapters"]
        self.assertEqual(
            [25, 8, 7, 4],
            [item["minimum_compatible_arrival_lower_bound"]["value"] for item in chapters],
        )
        for item in raw["novel_chapters"]:
            item["follow"] = "0"
        rerun = nr.normalize_data(raw, scope="long", expected_work_id="book")
        self.assertEqual(25, rerun["facts"]["long_novel"]["minimum_compatible_cohort_lower_bound"]["value"])

        lower_bound, counts = nr.infer_minimum_compatible_lower_bound([
            {"i": 1, "read": 100}, {"i": 2, "read": 50}, {"i": 3, "read": 0},
        ])
        self.assertEqual(2, lower_bound["value"])
        self.assertEqual([2, 1, 0], [counts[index]["value"] for index in range(3)])
        self.assertIn("true cohort may be any larger", lower_bound["limitation"].lower())

    def test_quantization_gap_and_monotonicity_are_explicit(self):
        lower, _ = nr.infer_minimum_compatible_lower_bound([
            {"i": 1, "read": "100.0"}, {"i": 2, "read": "33.3"}, {"i": 3, "read": "0.0"},
        ])
        self.assertEqual({"truncate", "round_half_up"}, set(lower["compatible_minima_by_quantization"]))
        missing_index, _ = nr.infer_minimum_compatible_lower_bound([
            {"i": 1, "read": 100}, {"i": 3, "read": 50}, {"i": 4, "read": 0},
        ])
        self.assertEqual("unavailable", missing_index["state"])
        increasing, _ = nr.infer_minimum_compatible_lower_bound([
            {"i": 1, "read": 100}, {"i": 2, "read": 50}, {"i": 3, "read": 25}, {"i": 4, "read": 30},
        ])
        self.assertIn("monotonicity_warning", increasing)
        self.assertEqual(
            {"field_refresh_lag", "direct_entry_or_skip", "scope_or_cohort_mixture"},
            set(increasing["candidate_causes"]),
        )

    def test_wrong_work_failed_endpoints_and_all_null_are_not_ok(self):
        raw = self.v2()
        wrong = nr.normalize_data(raw, scope="long", expected_work_id="other")
        self.assertEqual("SCOPE_UNKNOWN", wrong["quality"]["status"])

        for value in raw["endpoint_status"].values():
            value.update({"http_ok": False, "json_ok": False})
        failed = nr.normalize_data(raw, scope="long", expected_work_id="book")
        self.assertEqual("CORRUPT", failed["quality"]["status"])
        self.assertEqual("CORRUPT", failed["quality"]["branch_statuses"]["long_novel"])

        empty = self.v2()
        empty["novel_chapters"] = []
        empty["novel_common"] = {"reader_uv_daily": None}
        empty["novel_metrics"] = {}
        empty["novel_traffic"] = {}
        empty_result = nr.normalize_data(empty, scope="long", expected_work_id="book")
        self.assertEqual("CORRUPT", empty_result["quality"]["status"])

    def test_short_funnel_monotonicity_and_counts(self):
        valid = nr.normalize_data(self.valid_short_v2(), scope="short", expected_work_id="1")
        self.assertEqual("OK", valid["quality"]["status"])
        self.assertEqual(50.0, valid["facts"]["short_stories"][0]["funnel_rates"]["impression_to_read"]["value"])

        raw = self.valid_short_v2()
        raw["shorts"][0].update({"show": 10, "read": 20, "s15": -1, "s30": 30, "s60": 40, "fin": 50})
        invalid = nr.normalize_data(raw, scope="short", expected_work_id="1")
        self.assertEqual("CORRUPT", invalid["quality"]["status"])
        self.assertFalse(invalid["facts"]["short_stories"][0]["valid_for_analysis"])
        self.assertNotIn("short_stories.count_funnel", invalid["quality"]["usable_fields"])

    def test_date_relation_refresh_scope_and_file_hash(self):
        stale = nr.normalize_data(
            self.valid_short_v2(), expected_snapshot_date="2026-08-07",
            expected_data_until="2026-08-06", expected_work_id="1", scope="short",
        )
        self.assertEqual("PLATFORM_NOT_UPDATED", stale["quality"]["status"])
        bad_relation = self.v2()
        bad_relation["data_until"] = bad_relation["date"]
        self.assertEqual(
            "CORRUPT",
            nr.normalize_data(bad_relation, scope="long", expected_work_id="book")["quality"]["status"],
        )

        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / "raw.json"
            path.write_text(json.dumps(self.v2(), ensure_ascii=False), encoding="utf-8")
            result = nr.normalize_file(path, scope="long", expected_work_id="book")
            self.assertRegex(result["source"]["sha256"], r"^[0-9a-f]{64}$")
            path.write_text("not json", encoding="utf-8")
            with self.assertRaises(nr.NormalizationError):
                nr.normalize_file(path)

    def test_frozen_legacy_snapshots_are_reproducible_but_scope_downgraded(self):
        for name in ("2026-08-06.json", "2026-08-08.json", "2026-08-11.json"):
            path = HISTORICAL_FIXTURES / "raw" / name
            result = nr.normalize_file(
                path, expected_snapshot_date=name[:-5],
                expected_data_until=str(__import__("datetime").date.fromisoformat(name[:-5]) - __import__("datetime").timedelta(days=1)),
                expected_work_id="1000000000000000000", scope="long",
            )
            self.assertEqual("SCOPE_UNKNOWN", result["quality"]["status"])
            self.assertTrue(result["quality"]["usable_fields"])


if __name__ == "__main__":
    unittest.main()
