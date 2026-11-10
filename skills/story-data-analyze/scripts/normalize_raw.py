#!/usr/bin/env python3
"""Normalize Fanqie raw snapshots without inventing unavailable facts.

The normal form deliberately wraps every scalar in a presence state so that a
missing field, a JSON null and a measured zero can never collapse into the same
Python false-y value.  Chapter percentages are never presented as authoritative
people counts unless the source contains an explicit cohort base.  A displayed
percentage curve may additionally yield the *smallest compatible integer lower
bound*; that value is labelled non-authoritative and is never called an estimate.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import math
import pathlib
import sys
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


class NormalizationError(ValueError):
    """The source cannot be represented as a trustworthy snapshot."""


MISSING = object()


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _number(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return value
        return int(value) if value.is_integer() else value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return value
        try:
            number = float(stripped)
        except ValueError:
            return value
        if math.isfinite(number) and number.is_integer():
            return int(number)
        return number
    return value


def field(value: Any = MISSING, *, unit: Optional[str] = None) -> Dict[str, Any]:
    """Return an explicit missing/null/zero/present fact wrapper."""
    if value is MISSING:
        result: Dict[str, Any] = {"state": "missing", "value": None}
    elif value is None:
        result = {"state": "null", "value": None}
    else:
        normalized = _number(value)
        state = "zero" if isinstance(normalized, (int, float)) and not isinstance(normalized, bool) and normalized == 0 else "present"
        result = {"state": state, "value": normalized}
    if unit:
        result["unit"] = unit
    return result


def _value(mapping: Mapping[str, Any], key: str, *, unit: Optional[str] = None) -> Dict[str, Any]:
    return field(mapping[key] if key in mapping else MISSING, unit=unit)


def _count_value(
    mapping: Mapping[str, Any], key: str, issues: List[Dict[str, Any]], path: str,
    *, unit: str = "people",
) -> Dict[str, Any]:
    result = _value(mapping, key, unit=unit)
    if result["state"] in {"missing", "null"}:
        return result
    value = result["value"]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        issues.append({"code": "COUNT_INVALID", "field": path, "raw_value": mapping.get(key)})
        return {"state": "invalid", "value": None, "raw_value": mapping.get(key), "unit": unit}
    return result


def _percent_value(
    mapping: Mapping[str, Any], key: str, issues: List[Dict[str, Any]], path: str
) -> Dict[str, Any]:
    result = _value(mapping, key, unit="percent")
    if result["state"] in {"missing", "null"}:
        return result
    value = result["value"]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value < 0 or value > 100:
        issues.append({"code": "PERCENT_INVALID", "field": path, "raw_value": mapping.get(key)})
        return {"state": "invalid", "value": None, "raw_value": mapping.get(key), "unit": "percent"}
    return result


def _valid_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        _dt.date.fromisoformat(value)
        return True
    except ValueError:
        return False


def detect_shape(raw: Mapping[str, Any]) -> str:
    version = raw.get("schema_version")
    if isinstance(version, int) and not isinstance(version, bool) and version == 2:
        return "fanqie_v2"
    if any(key in raw for key in ("novel_common", "novel_metrics", "novel_traffic", "trend_dates")):
        return "legacy_expanded"
    if all(key in raw for key in ("date", "data_until", "novel_chapters", "shorts")):
        return "legacy_minimal"
    return "unknown"


def _list_or_empty(raw: Mapping[str, Any], key: str, issues: List[Dict[str, Any]]) -> List[Any]:
    if key not in raw:
        issues.append({"code": "FIELD_MISSING", "field": key})
        return []
    value = raw[key]
    if value is None:
        issues.append({"code": "FIELD_NULL", "field": key})
        return []
    if not isinstance(value, list):
        issues.append({"code": "TYPE_INVALID", "field": key, "expected": "array"})
        return []
    return value


def _object_or_empty(raw: Mapping[str, Any], key: str, issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    if key not in raw:
        issues.append({"code": "FIELD_MISSING", "field": key})
        return {}
    value = raw[key]
    if value is None:
        issues.append({"code": "FIELD_NULL", "field": key})
        return {}
    if not isinstance(value, dict):
        issues.append({"code": "TYPE_INVALID", "field": key, "expected": "object"})
        return {}
    return value


def _chapter_absolute(chapter: Mapping[str, Any], pct_fact: Mapping[str, Any]) -> Dict[str, Any]:
    """Use explicit UV when available; otherwise refuse or visibly approximate."""
    for key in ("arrival_uv", "read_uv", "chapter_reader_uv"):
        if key in chapter and chapter[key] is not None:
            fact = field(chapter[key], unit="people")
            if (
                fact["state"] in {"present", "zero"}
                and isinstance(fact["value"], int)
                and not isinstance(fact["value"], bool)
                and fact["value"] >= 0
            ):
                return {
                    **fact,
                    "classification": "exact_source_count",
                    "display_only": False,
                    "source_field": key,
                }
    base_key = next((key for key in ("cohort_size", "chapter_cohort_size") if key in chapter and chapter[key] is not None), None)
    pct = pct_fact.get("value")
    base_value = _number(chapter[base_key]) if base_key else None
    if (
        base_key and isinstance(base_value, int) and not isinstance(base_value, bool) and base_value >= 0
        and isinstance(pct, (int, float)) and not isinstance(pct, bool)
    ):
        estimate = round(float(base_value) * float(pct) / 100)
        return {
            "state": "present" if estimate else "zero",
            "value": estimate,
            "unit": "people",
            "classification": "approximate_from_rounded_percentage",
            "display_only": True,
            "source_fields": [base_key, "read"],
            "warning": "Do not use as an exact cohort count or causal attribution base.",
        }
    return {
        "state": "unavailable",
        "value": None,
        "unit": "people",
        "classification": "not_computable",
        "display_only": True,
        "reason": "No authoritative chapter cohort count exists in the snapshot.",
    }


def _display_decimal(value: Any) -> Optional[Tuple[Decimal, int]]:
    """Return displayed percent and displayed decimal places without float loss."""
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    try:
        decimal = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if not decimal.is_finite() or decimal < 0 or decimal > 100:
        return None
    places = max(0, -decimal.as_tuple().exponent)
    return decimal, places


def _possible_counts(base: int, displayed: Decimal, places: int, quantization: str) -> List[int]:
    """Counts compatible with one explicitly named display quantization rule."""
    quantum = Decimal(1).scaleb(-places)
    if quantization == "truncate":
        low_percent = displayed
        high_percent = min(Decimal(100) + quantum, displayed + quantum)
    elif quantization == "round_half_up":
        half = quantum / Decimal(2)
        low_percent = max(Decimal(0), displayed - half)
        high_percent = min(Decimal(100) + half, displayed + half)
    else:
        raise ValueError(f"unknown quantization: {quantization}")
    if displayed == 100:
        return [base]
    low = low_percent * base / Decimal(100)
    high = high_percent * base / Decimal(100)
    first = int(low.to_integral_value(rounding=ROUND_CEILING))
    # Strict upper bound: ceil(high) - 1 also handles exact integer high.
    last = int(high.to_integral_value(rounding=ROUND_CEILING)) - 1
    return [count for count in range(max(0, first), min(base, last) + 1)]


def _consistent_sequences(options: List[List[int]], limit: int = 2) -> List[List[int]]:
    """Find up to ``limit`` non-increasing arrival-count sequences."""
    sequences: List[List[int]] = []

    def visit(position: int, previous: Optional[int], current: List[int]) -> None:
        if len(sequences) >= limit:
            return
        if position == len(options):
            sequences.append(list(current))
            return
        for count in options[position]:
            if previous is None or count <= previous:
                current.append(count)
                visit(position + 1, count, current)
                current.pop()
                if len(sequences) >= limit:
                    return

    visit(0, None, [])
    return sequences


def _minimum_solution_for_mode(
    displayed_curve: List[Tuple[int, Decimal, int]], quantization: str, max_base: int
) -> Optional[Tuple[int, List[List[int]]]]:
    for base in range(1, max_base + 1):
        options = [_possible_counts(base, displayed, places, quantization) for _, displayed, places in displayed_curve]
        if any(not option for option in options):
            continue
        sequences = _consistent_sequences(options, limit=16)
        if sequences:
            return base, sequences
    return None


def infer_minimum_compatible_lower_bound(
    chapters: List[Mapping[str, Any]], *, quantization: Optional[str] = None, max_base: int = 10000
) -> Tuple[Dict[str, Any], Dict[int, Dict[str, Any]]]:
    """Find a *lower bound* compatible with displayed cumulative read rates.

    It is not an estimate of the actual cohort.  With 100/50/0, both 2/1/0 and
    200/100/0 are compatible; only the smallest possible denominator is known.
    When the platform's display rule is absent, both truncation and half-up
    rounding are evaluated instead of silently choosing one.
    """
    displayed_curve: List[Tuple[int, Decimal, int]] = []
    for index, chapter in enumerate(chapters):
        parsed = _display_decimal(chapter.get("read"))
        if parsed is not None:
            displayed_curve.append((index, parsed[0], parsed[1]))
    common = {
        "unit": "people",
        "classification": "minimum_compatible_integer_lower_bound",
        "display_only": True,
        "authoritative": False,
        "basis_fields": ["novel_chapters[].read"],
        "excluded_fields": ["novel_chapters[].follow"],
        "display_quantization": quantization or "unknown_evaluated_as_truncate_and_round_half_up",
        "limitation": "This is only the smallest compatible cohort lower bound, not an estimate. The true cohort may be any larger compatible solution.",
        "follow_denominator_reuse": {
            "allowed": False,
            "reason": "follow is a conditional N→N+1 rate and may refresh asynchronously; it is not used to solve the cumulative read denominator.",
        },
    }
    if len(displayed_curve) < 3:
        return (
            {**common, "state": "unavailable", "value": None, "reason": "At least three displayed read percentages are required."},
            {},
        )
    indices = [chapter.get("i") for chapter in chapters]
    if any(not isinstance(value, int) or isinstance(value, bool) for value in indices) or indices != list(range(1, len(indices) + 1)):
        return (
            {**common, "state": "unavailable", "value": None, "reason": "Chapter indices are missing, duplicated or non-contiguous."},
            {},
        )
    values = [point[1] for point in displayed_curve]
    first_increase = next(
        (index for index, (previous, current) in enumerate(zip(values, values[1:]), start=1) if current > previous),
        None,
    )
    excluded_after_increase = 0
    if first_increase is not None:
        if first_increase < 3:
            return (
                {
                    **common,
                    "state": "unavailable",
                    "value": None,
                    "reason": "The first three cumulative read percentages violate monotonicity.",
                    "candidate_causes": ["field_refresh_lag", "direct_entry_or_skip", "scope_or_cohort_mixture"],
                },
                {},
            )
        excluded_after_increase = len(displayed_curve) - first_increase
        displayed_curve = displayed_curve[:first_increase]
        common["curve_scope"] = "leading_prefix_before_monotonicity_violation"
        common["excluded_points_after_first_increase"] = excluded_after_increase
        common["monotonicity_warning"] = "Later read percentages increased; the suffix is excluded from the lower-bound calculation without assigning a cause."
        common["candidate_causes"] = ["field_refresh_lag", "direct_entry_or_skip", "scope_or_cohort_mixture"]
    else:
        common["curve_scope"] = "full_displayed_read_curve"
    modes = [quantization] if quantization in {"truncate", "round_half_up"} else ["truncate", "round_half_up"]
    solutions = {
        mode: solution for mode in modes
        if (solution := _minimum_solution_for_mode(displayed_curve, mode, max_base)) is not None
    }
    if not solutions:
        return (
            {**common, "state": "unavailable", "value": None, "reason": f"No integer solution found up to base={max_base}."},
            {},
        )
    global_minimum = min(solution[0] for solution in solutions.values())
    minimum_modes = {
        mode: solution for mode, solution in solutions.items() if solution[0] == global_minimum
    }
    if any(len(sequences) != 1 for _, sequences in minimum_modes.values()):
        return (
            {
                **common,
                "state": "unavailable",
                "value": None,
                "candidate_minimum_lower_bound": global_minimum,
                "compatible_minima_by_quantization": {mode: value[0] for mode, value in solutions.items()},
                "reason": "A minimum denominator admits multiple non-increasing arrival sequences.",
            },
            {},
        )
    sequences_by_mode = {mode: value[1][0] for mode, value in minimum_modes.items()}
    estimates: Dict[int, Dict[str, Any]] = {}
    for position, (chapter_index, _, _) in enumerate(displayed_curve):
        counts = [sequence[position] for sequence in sequences_by_mode.values()]
        count = min(counts)
        estimates[chapter_index] = {
            "state": "zero" if count == 0 else "present",
            "value": count,
            **common,
            "minimum_compatible_cohort_lower_bound": global_minimum,
            "compatible_counts_by_quantization": {
                mode: sequence[position] for mode, sequence in sequences_by_mode.items()
            },
        }
    return (
        {
            **common,
            "state": "present",
            "value": global_minimum,
            "solution_unique_at_minimum_per_quantization": True,
            "compatible_minima_by_quantization": {mode: value[0] for mode, value in solutions.items()},
            "chapters_used": len(displayed_curve),
            "excluded_points": excluded_after_increase,
        },
        estimates,
    )


def _normalize_chapters(
    raw: Mapping[str, Any], issues: List[Dict[str, Any]], usable: List[str]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    chapters = _list_or_empty(raw, "novel_chapters", issues)
    object_chapters = [item for item in chapters if isinstance(item, dict)]
    quantization = raw.get("chapter_percentage_quantization")
    if quantization not in {None, "truncate", "round_half_up"}:
        issues.append(
            {
                "code": "QUANTIZATION_METADATA_INVALID",
                "field": "chapter_percentage_quantization",
                "raw_value": quantization,
            }
        )
        quantization = None
    minimum_base, lower_bounds = infer_minimum_compatible_lower_bound(
        object_chapters, quantization=quantization
    )
    if minimum_base.get("monotonicity_warning"):
        issues.append(
            {
                "code": "MONOTONICITY_VIOLATION",
                "field": "novel_chapters[].read",
                "detail": minimum_base["monotonicity_warning"],
                "excluded_points": minimum_base.get("excluded_points", 0),
                "candidate_causes": minimum_base.get("candidate_causes", []),
            }
        )
    normalized = []
    object_index = 0
    for position, item in enumerate(chapters, start=1):
        if not isinstance(item, dict):
            issues.append({"code": "TYPE_INVALID", "field": f"novel_chapters[{position - 1}]", "expected": "object"})
            continue
        read = _percent_value(item, "read", issues, f"novel_chapters[{position - 1}].read")
        follow = _percent_value(item, "follow", issues, f"novel_chapters[{position - 1}].follow")
        normalized.append(
            {
                "index": _count_value(
                    item, "i", issues, f"novel_chapters[{position - 1}].i", unit="chapter_index"
                ),
                "title": _value(item, "title"),
                "read_completion_percent": read,
                "follow_read_percent": follow,
                "loss_percent": _percent_value(item, "loss", issues, f"novel_chapters[{position - 1}].loss"),
                "word_count": _count_value(
                    item, "words", issues, f"novel_chapters[{position - 1}].words", unit="words"
                ),
                "publish_time": _value(item, "publish_time"),
                "arrival_people": _chapter_absolute(item, read),
                "minimum_compatible_arrival_lower_bound": lower_bounds.get(
                    object_index,
                    {
                        "state": "unavailable",
                        "value": None,
                        "unit": "people",
                        "classification": "minimum_compatible_integer_lower_bound",
                        "display_only": True,
                        "authoritative": False,
                        "reason": "No unique minimum compatible lower-bound solution is available for the read curve.",
                    },
                ),
            }
        )
        object_index += 1
    if any(row["read_completion_percent"]["state"] in {"zero", "present"} for row in normalized):
        usable.append("long_novel.chapters.read_completion_percent")
    if any(row["follow_read_percent"]["state"] in {"zero", "present"} for row in normalized):
        usable.append("long_novel.chapters.follow_read_percent")
    if minimum_base["state"] == "present":
        usable.append("long_novel.minimum_compatible_cohort_lower_bound.display_only")
    return normalized, minimum_base


def _normalize_series(
    raw: Mapping[str, Any], key: str, dates: List[Any], issues: List[Dict[str, Any]], usable: List[str]
) -> Dict[str, List[Dict[str, Any]]]:
    source = _object_or_empty(raw, key, issues)
    result: Dict[str, List[Dict[str, Any]]] = {}
    for metric, values in source.items():
        if not isinstance(values, list):
            issues.append({"code": "TYPE_INVALID", "field": f"{key}.{metric}", "expected": "array"})
            continue
        rows = []
        valid_values = 0
        unit = "people"
        if key == "novel_metrics" and metric == "评论次数":
            unit = "count"
        elif key == "novel_metrics" and metric == "作品评分":
            unit = "score"
        width = max(len(values), len(dates))
        for index in range(width):
            raw_value = values[index] if index < len(values) else MISSING
            value_mapping = {"value": raw_value} if raw_value is not MISSING else {}
            if unit == "score":
                normalized_value = _value(value_mapping, "value", unit="score")
                score = normalized_value.get("value")
                if normalized_value["state"] not in {"missing", "null"} and (
                    isinstance(score, bool) or not isinstance(score, (int, float))
                    or not math.isfinite(float(score)) or score < 0 or score > 10
                ):
                    issues.append(
                        {"code": "SCORE_INVALID", "field": f"{key}.{metric}[{index}]", "raw_value": raw_value}
                    )
                    normalized_value = {"state": "invalid", "value": None, "raw_value": raw_value, "unit": "score"}
            else:
                normalized_value = _count_value(
                    value_mapping, "value", issues, f"{key}.{metric}[{index}]", unit=unit
                )
            if normalized_value["state"] in {"zero", "present"}:
                valid_values += 1
            rows.append(
                {
                    "date_label": field(dates[index] if index < len(dates) else MISSING),
                    "value": normalized_value,
                }
            )
        if dates and len(values) != len(dates):
            issues.append(
                {
                    "code": "SERIES_LENGTH_MISMATCH",
                    "field": f"{key}.{metric}",
                    "values": len(values),
                    "dates": len(dates),
                }
            )
        result[metric] = rows
        if valid_values:
            usable.append(f"long_novel.{key}.{metric}")
    return result


def _finite_number_value(
    mapping: Mapping[str, Any], key: str, issues: List[Dict[str, Any]], path: str, *, unit: str
) -> Dict[str, Any]:
    result = _value(mapping, key, unit=unit)
    if result["state"] in {"missing", "null"}:
        return result
    value = result["value"]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        issues.append({"code": "NUMBER_INVALID", "field": path, "raw_value": mapping.get(key)})
        return {"state": "invalid", "value": None, "raw_value": mapping.get(key), "unit": unit}
    return result


def _normalize_common(common: Mapping[str, Any], issues: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    count_units = {"reader_uv_daily": "people", "rank_cat": "rank"}
    percent_units = {
        "reader_uv_daily_incr": "percent", "read_completion_rate": "percent",
        "pursue_read_rate": "percent", "risk_rate": "percent",
    }
    for key, value in common.items():
        if key in count_units:
            result[key] = _count_value(common, key, issues, f"novel_common.{key}", unit=count_units[key])
        elif key in percent_units:
            # Day-over-day change may legitimately be negative or exceed 100%; this is
            # a finite-number check, not a [0, 100] share check.
            result[key] = _finite_number_value(
                common, key, issues, f"novel_common.{key}", unit=percent_units[key]
            )
        elif key == "is_publish":
            result[key] = _value(common, key, unit="status_code")
            if result[key]["state"] not in {"missing", "null"} and (
                isinstance(result[key]["value"], bool) or not isinstance(result[key]["value"], int)
            ):
                issues.append({"code": "STATUS_INVALID", "field": f"novel_common.{key}", "raw_value": value})
                result[key] = {"state": "invalid", "value": None, "raw_value": value, "unit": "status_code"}
        else:
            result[key] = field(value)
    return result


def _has_usable_fact(value: Any) -> bool:
    if isinstance(value, dict):
        if "state" in value and "value" in value:
            return value["state"] in {"zero", "present"}
        return any(_has_usable_fact(child) for child in value.values())
    if isinstance(value, list):
        return any(_has_usable_fact(child) for child in value)
    return False


def _endpoint_healthy(status: Any) -> bool:
    return bool(
        isinstance(status, dict)
        and status.get("http_ok") is True
        and status.get("json_ok") is True
        and status.get("business_code") in (None, 0, "0")
    )


def _ratio(numerator: Dict[str, Any], denominator: Dict[str, Any], label: str) -> Dict[str, Any]:
    n, d = numerator.get("value"), denominator.get("value")
    if numerator.get("state") not in {"zero", "present"} or denominator.get("state") not in {"zero", "present"}:
        return {"state": "unavailable", "value": None, "unit": "percent", "reason": "missing_or_null_count", "label": label}
    if isinstance(n, bool) or isinstance(d, bool) or not isinstance(n, int) or not isinstance(d, int):
        return {"state": "unavailable", "value": None, "unit": "percent", "reason": "invalid_count", "label": label}
    if d == 0:
        return {"state": "unavailable", "value": None, "unit": "percent", "reason": "zero_denominator", "label": label}
    return {
        "state": "present" if n else "zero",
        "value": n / d * 100,
        "unit": "percent",
        "classification": "derived_from_source_counts",
        "display_only": False,
        "label": label,
    }


def _normalize_shorts(raw: Mapping[str, Any], issues: List[Dict[str, Any]], usable: List[str]) -> List[Dict[str, Any]]:
    stories = _list_or_empty(raw, "shorts", issues)
    result = []
    for position, item in enumerate(stories):
        if not isinstance(item, dict):
            issues.append({"code": "TYPE_INVALID", "field": f"shorts[{position}]", "expected": "object"})
            continue
        source_keys = {
            "impressions": "show", "reads": "read", "read_15s": "s15",
            "read_30s": "s30", "read_60s": "s60", "finishes": "fin",
            "day_impressions": "day_show", "day_reads": "day_read",
        }
        counts = {
            label: _count_value(item, source_key, issues, f"shorts[{position}].{source_key}")
            for label, source_key in source_keys.items()
        }
        cumulative_labels = ["impressions", "reads", "read_15s", "read_30s", "read_60s", "finishes"]
        cumulative_values = [counts[label].get("value") for label in cumulative_labels]
        counts_valid = all(
            counts[label]["state"] in {"zero", "present"} for label in cumulative_labels
        )
        monotonic = counts_valid and all(
            left >= right for left, right in zip(cumulative_values, cumulative_values[1:])
        )
        day_valid = all(counts[label]["state"] in {"zero", "present"} for label in ("day_impressions", "day_reads"))
        if day_valid and counts["day_impressions"]["value"] < counts["day_reads"]["value"]:
            day_valid = False
            issues.append(
                {
                    "code": "SHORT_DAILY_FUNNEL_INVALID",
                    "field": f"shorts[{position}]",
                    "detail": "day_show must be greater than or equal to day_read",
                }
            )
        if counts_valid and not monotonic:
            issues.append(
                {
                    "code": "SHORT_FUNNEL_MONOTONICITY_INVALID",
                    "field": f"shorts[{position}]",
                    "values": dict(zip(cumulative_labels, cumulative_values)),
                }
            )
        valid_for_analysis = bool(counts_valid and monotonic and day_valid)
        result.append(
            {
                "id": _value(item, "id"),
                "name": _value(item, "name"),
                "sign_status": _value(item, "sign"),
                "counts": counts,
                "valid_for_analysis": valid_for_analysis,
                "row_status": "OK" if valid_for_analysis else "CORRUPT",
                "funnel_rates": {
                    "impression_to_read": _ratio(counts["reads"], counts["impressions"], "read/impressions"),
                    "read_to_15s": _ratio(counts["read_15s"], counts["reads"], "15s/read"),
                    "15s_to_30s": _ratio(counts["read_30s"], counts["read_15s"], "30s/15s"),
                    "30s_to_60s": _ratio(counts["read_60s"], counts["read_30s"], "60s/30s"),
                    "60s_to_finish": _ratio(counts["finishes"], counts["read_60s"], "finish/60s"),
                },
            }
        )
    if any(item["valid_for_analysis"] for item in result):
        usable.append("short_stories.count_funnel")
    return result


def _presence_inventory(value: Any, path: str = "") -> Tuple[List[str], List[str], List[str]]:
    missing: List[str] = []
    nulls: List[str] = []
    zeros: List[str] = []
    if isinstance(value, dict):
        if "state" in value and "value" in value:
            state = value["state"]
            if state in {"missing", "unavailable"}:
                missing.append(path)
            elif state == "null":
                nulls.append(path)
            elif state == "zero":
                zeros.append(path)
        else:
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else key
                m, n, z = _presence_inventory(child, child_path)
                missing.extend(m)
                nulls.extend(n)
                zeros.extend(z)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            m, n, z = _presence_inventory(child, f"{path}[{index}]")
            missing.extend(m)
            nulls.extend(n)
            zeros.extend(z)
    return missing, nulls, zeros


def normalize_data(
    raw: Mapping[str, Any], *, source_name: str = "<memory>", source_sha256: Optional[str] = None,
    expected_snapshot_date: Optional[str] = None, expected_data_until: Optional[str] = None,
    expected_work_id: Optional[str] = None, scope: str = "all"
) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise NormalizationError("CORRUPT: top-level JSON must be an object")
    declared_version = raw.get("schema_version")
    if declared_version is not None and (
        isinstance(declared_version, bool) or not isinstance(declared_version, int) or declared_version > 2
    ):
        raise NormalizationError(f"CORRUPT: unsupported schema_version={declared_version!r}")
    shape = detect_shape(raw)
    if shape == "unknown":
        raise NormalizationError("CORRUPT: unrecognized raw snapshot shape")
    if not _valid_date(raw.get("date")) or not _valid_date(raw.get("data_until")):
        raise NormalizationError("CORRUPT: date and data_until must be ISO dates")
    if scope not in {"all", "long", "short"}:
        raise NormalizationError("scope must be all, long or short")
    if expected_snapshot_date is not None and not _valid_date(expected_snapshot_date):
        raise NormalizationError("expected_snapshot_date must be an ISO date")
    if expected_data_until is not None and not _valid_date(expected_data_until):
        raise NormalizationError("expected_data_until must be an ISO date")

    issues: List[Dict[str, Any]] = []
    usable: List[str] = []
    dates_source = raw.get("trend_dates", [])
    trend_dates = dates_source if isinstance(dates_source, list) else []
    if dates_source is None:
        issues.append({"code": "FIELD_NULL", "field": "trend_dates"})
    elif not isinstance(dates_source, list):
        issues.append({"code": "TYPE_INVALID", "field": "trend_dates", "expected": "array"})
    elif any(not isinstance(value, str) or not value.strip() for value in dates_source):
        issues.append({"code": "TREND_DATE_LABEL_INVALID", "field": "trend_dates"})

    snapshot_day = _dt.date.fromisoformat(raw["date"])
    data_day = _dt.date.fromisoformat(raw["data_until"])
    date_relation_valid = data_day == snapshot_day - _dt.timedelta(days=1)
    if not date_relation_valid:
        issues.append(
            {
                "code": "DATE_RELATION_INVALID", "field": "date/data_until",
                "snapshot_date": raw["date"], "data_until": raw["data_until"],
                "expected_relation": "data_until = snapshot_date - 1 day",
            }
        )

    facts: Dict[str, Any] = {
        "metadata": {
            "snapshot_date": _value(raw, "date"),
            "data_until": _value(raw, "data_until"),
            "pulled_at": _value(raw, "pulled_at"),
            "timezone": _value(raw, "timezone"),
            "novel_id": _value(raw, "novel_id"),
            "metric_definitions_checked": _value(raw, "metric_definitions_checked"),
            "expected_work_id": field(expected_work_id),
        },
        "long_novel": {},
        "short_stories": [],
    }
    branch_statuses: Dict[str, str] = {}
    endpoint_status = raw.get("endpoint_status")
    if shape == "fanqie_v2" and not isinstance(endpoint_status, dict):
        endpoint_status = {}
        issues.append({"code": "ENDPOINT_STATUS_MISSING", "field": "endpoint_status"})

    long_work_verified = False
    short_work_verified = False
    if scope in {"all", "long"}:
        common = _object_or_empty(raw, "novel_common", issues)
        normalized_common = _normalize_common(common, issues)
        chapters, minimum_base = _normalize_chapters(raw, issues, usable)
        facts["long_novel"] = {
            "chapters": chapters,
            "minimum_compatible_cohort_lower_bound": minimum_base,
            "common": normalized_common,
            "metric_series": _normalize_series(raw, "novel_metrics", trend_dates, issues, usable),
            "traffic_series": _normalize_series(raw, "novel_traffic", trend_dates, issues, usable),
        }
        if _has_usable_fact(normalized_common):
            usable.append("long_novel.common")
        if shape == "legacy_minimal" and isinstance(raw.get("novel_trend_7d"), list):
            facts["long_novel"]["legacy_trend_7d"] = raw["novel_trend_7d"]
            issues.append({"code": "LEGACY_UNLABELED_SERIES", "field": "novel_trend_7d"})
        actual_novel_id = raw.get("novel_id")
        long_work_verified = bool(
            expected_work_id is not None and actual_novel_id is not None
            and str(actual_novel_id) == str(expected_work_id)
        )
        if expected_work_id is None:
            issues.append({"code": "EXPECTED_WORK_ID_MISSING", "field": "expected_work_id", "branch": "long_novel"})
        elif actual_novel_id is None:
            issues.append({"code": "WORK_ID_MISSING", "field": "novel_id", "expected": str(expected_work_id)})
        elif str(actual_novel_id) != str(expected_work_id):
            issues.append(
                {"code": "WORK_ID_MISMATCH", "field": "novel_id", "actual": str(actual_novel_id), "expected": str(expected_work_id)}
            )

        long_usable = any(value.startswith("long_novel.") for value in usable)
        long_status = "OK" if long_usable else "CORRUPT"
        if shape == "fanqie_v2":
            required_long_endpoints = (
                "chapter_list_v1", "book_common_v1", "book_increase_metrics", "book_increase_traffic"
            )
            healthy = [name for name in required_long_endpoints if _endpoint_healthy(endpoint_status.get(name))]
            for name in required_long_endpoints:
                if name not in endpoint_status:
                    issues.append({"code": "ENDPOINT_STATUS_MISSING", "field": f"endpoint_status.{name}"})
                elif not _endpoint_healthy(endpoint_status.get(name)):
                    issues.append(
                        {"code": "ENDPOINT_UNHEALTHY", "field": f"endpoint_status.{name}", "status": endpoint_status.get(name)}
                    )
            if not healthy:
                long_status = "CORRUPT"
            elif len(healthy) != len(required_long_endpoints) and long_status != "CORRUPT":
                long_status = "PARTIAL"
        elif long_status != "CORRUPT":
            long_status = "PARTIAL"
            issues.append({"code": "ENDPOINT_STATUS_UNAVAILABLE", "field": "endpoint_status", "branch": "long_novel"})
        if not long_work_verified and long_status != "CORRUPT":
            long_status = "SCOPE_UNKNOWN"
        branch_statuses["long_novel"] = long_status
    if scope in {"all", "short"}:
        facts["short_stories"] = _normalize_shorts(raw, issues, usable)
        short_rows = facts["short_stories"]
        valid_short_rows = [row for row in short_rows if row.get("valid_for_analysis") is True]
        short_ids = {
            str(row["id"]["value"]) for row in short_rows
            if row.get("id", {}).get("state") in {"zero", "present"}
        }
        short_scope_evidence = raw.get("short_query")
        ui_scope_verified = bool(
            isinstance(short_scope_evidence, dict)
            and short_scope_evidence.get("scope_verified_against_ui") is True
        )
        short_work_verified = bool(
            expected_work_id is not None and str(expected_work_id) in short_ids and ui_scope_verified
        )
        if expected_work_id is None:
            issues.append({"code": "EXPECTED_WORK_ID_MISSING", "field": "expected_work_id", "branch": "short_story"})
        elif str(expected_work_id) not in short_ids:
            issues.append(
                {"code": "WORK_ID_MISMATCH", "field": "shorts[].id", "actual": sorted(short_ids), "expected": str(expected_work_id)}
            )
        if not ui_scope_verified:
            issues.append({"code": "SCOPE_UNKNOWN", "field": "short_query.scope_verified_against_ui"})

        short_status = "OK" if valid_short_rows else "CORRUPT"
        if shape == "fanqie_v2":
            required_short_endpoints = ["short_book_list"] + [f"short_single_by_date:{short_id}" for short_id in short_ids]
            healthy_short = [name for name in required_short_endpoints if _endpoint_healthy(endpoint_status.get(name))]
            for name in required_short_endpoints:
                if name not in endpoint_status:
                    issues.append({"code": "ENDPOINT_STATUS_MISSING", "field": f"endpoint_status.{name}"})
                elif not _endpoint_healthy(endpoint_status.get(name)):
                    issues.append(
                        {"code": "ENDPOINT_UNHEALTHY", "field": f"endpoint_status.{name}", "status": endpoint_status.get(name)}
                    )
            if not healthy_short:
                short_status = "CORRUPT"
            elif len(healthy_short) != len(required_short_endpoints) and short_status != "CORRUPT":
                short_status = "PARTIAL"
        elif short_status != "CORRUPT":
            short_status = "PARTIAL"
            issues.append({"code": "ENDPOINT_STATUS_UNAVAILABLE", "field": "endpoint_status", "branch": "short_story"})
        if not short_work_verified and short_status != "CORRUPT":
            short_status = "SCOPE_UNKNOWN"
        branch_statuses["short_story"] = short_status

    platform_current = True
    if expected_snapshot_date and raw["date"] != expected_snapshot_date:
        platform_current = False
        issues.append({"code": "PLATFORM_NOT_UPDATED", "field": "date", "actual": raw["date"], "expected": expected_snapshot_date})
    if expected_data_until and raw["data_until"] != expected_data_until:
        platform_current = False
        issues.append({"code": "PLATFORM_NOT_UPDATED", "field": "data_until", "actual": raw["data_until"], "expected": expected_data_until})

    if scope == "long":
        work_id_verified = long_work_verified
    elif scope == "short":
        work_id_verified = short_work_verified
    else:
        work_id_verified = long_work_verified and short_work_verified
    scope_verified = work_id_verified

    missing, nulls, zeros = _presence_inventory(facts)
    requested_statuses = list(branch_statuses.values())
    relevant_usable = [
        item for item in usable
        if (scope in {"all", "long"} and item.startswith("long_novel."))
        or (scope in {"all", "short"} and item.startswith("short_stories."))
    ]
    if not date_relation_valid:
        quality_status = "CORRUPT"
    elif not platform_current:
        quality_status = "PLATFORM_NOT_UPDATED"
    elif not scope_verified:
        quality_status = "SCOPE_UNKNOWN"
    elif "CORRUPT" in requested_statuses:
        quality_status = "CORRUPT"
    elif any(status in {"PARTIAL", "SCOPE_UNKNOWN"} for status in requested_statuses) or issues:
        quality_status = "PARTIAL"
    else:
        quality_status = "OK"
    # PARTIAL is useful only if the caller can name what remains usable.
    if quality_status == "PARTIAL" and not relevant_usable:
        quality_status = "CORRUPT"

    return {
        "normalization_schema_version": 2,
        "source": {
            "name": source_name,
            "sha256": source_sha256,
            "detected_shape": shape,
            "declared_schema_version": raw.get("schema_version"),
        },
        "facts": facts,
        "quality": {
            "status": quality_status,
            "snapshot_date": raw["date"],
            "data_until": raw["data_until"],
            "platform_current": platform_current,
            "scope": scope,
            "scope_verified": scope_verified,
            "expected_work_id": str(expected_work_id) if expected_work_id is not None else None,
            "work_id": str(raw.get("novel_id")) if raw.get("novel_id") is not None else None,
            "work_id_verified": work_id_verified,
            "date_relation_valid": date_relation_valid,
            "branch_statuses": branch_statuses,
            "usable_fields": sorted(set(usable)),
            "issues": issues,
            "presence_summary": {
                "missing_paths": missing,
                "null_paths": nulls,
                "zero_paths": zeros,
                "missing_count": len(missing),
                "null_count": len(nulls),
                "zero_count": len(zeros),
            },
        },
    }


def normalize_file(
    path: pathlib.Path, *, expected_snapshot_date: Optional[str] = None,
    expected_data_until: Optional[str] = None, expected_work_id: Optional[str] = None,
    scope: str = "all"
) -> Dict[str, Any]:
    try:
        source = path.read_bytes()
    except OSError as exc:
        raise NormalizationError(f"CORRUPT: cannot read {path}: {exc}") from exc
    try:
        raw = json.loads(source.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NormalizationError(f"CORRUPT: invalid JSON in {path}: {exc}") from exc
    return normalize_data(
        raw,
        source_name=str(path),
        source_sha256=_sha256_bytes(source),
        expected_snapshot_date=expected_snapshot_date,
        expected_data_until=expected_data_until,
        expected_work_id=expected_work_id,
        scope=scope,
    )


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", type=pathlib.Path)
    parser.add_argument("--expected-snapshot-date")
    parser.add_argument("--expected-data-until")
    parser.add_argument("--expected-work-id")
    parser.add_argument("--scope", choices=("all", "long", "short"), default="all")
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args(argv)
    try:
        result = normalize_file(
            args.raw,
            expected_snapshot_date=args.expected_snapshot_date,
            expected_data_until=args.expected_data_until,
            expected_work_id=args.expected_work_id,
            scope=args.scope,
        )
    except NormalizationError as exc:
        print(json.dumps({"quality": {"status": "CORRUPT", "issues": [{"code": "CORRUPT", "detail": str(exc)}]}}, ensure_ascii=False, indent=2))
        return 2
    data = _canonical_bytes(result)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(data)
    else:
        sys.stdout.buffer.write(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
