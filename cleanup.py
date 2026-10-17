#!/usr/bin/env python3
"""Auditable CSV cleanup using only the Python standard library."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
from itertools import islice, chain, zip_longest
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from datetime import datetime

MAX_ROWS = 50_000
MAX_COLUMNS = 20
ALLOWED_CONFIG = {"delimiter", "trim_columns", "case_columns", "required_columns", "date_columns", "key_columns", "excel_safe"}
DATE_FORMATS = {"%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y", "%Y%m%d"}


class CleanupError(ValueError):
    pass


def formula_risk(value: str) -> bool:
    """Conservative flags; a flag is not a claim that the value is malicious."""
    return value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(("=", "+", "-", "@"))


def excel_safe_cell(value: str) -> str:
    return "'" + value if formula_risk(value) else value


def load_config(path: Path, raw: bytes | None = None) -> dict:
    try:
        config = json.loads((path.read_bytes() if raw is None else raw).decode("utf-8-sig"))
    except (OSError, ValueError) as error:
        raise CleanupError(f"Cannot read config: {error}") from error
    if not isinstance(config, dict):
        raise CleanupError("Config must be a JSON object.")
    unknown = set(config) - ALLOWED_CONFIG
    if unknown:
        raise CleanupError(f"Unknown config keys: {', '.join(sorted(unknown))}")
    for key in ("trim_columns", "required_columns", "key_columns"):
        values = config.get(key, [])
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values) or len(values) != len(set(values)):
            raise CleanupError(f"{key} must be a list of unique column names.")
    case = config.get("case_columns", {})
    if not isinstance(case, dict) or not all(isinstance(k, str) and v in ("lower", "upper") for k, v in case.items()):
        raise CleanupError("case_columns must map column names to lower or upper.")
    dates = config.get("date_columns", {})
    if not isinstance(dates, dict):
        raise CleanupError("date_columns must map column names to explicit date formats.")
    for column, formats in dates.items():
        if not isinstance(column, str) or not isinstance(formats, list) or not formats or not all(isinstance(f, str) and f in DATE_FORMATS for f in formats):
            raise CleanupError(f"Unsupported date format for {column!r}; see README.")
    if "delimiter" in config and config["delimiter"] not in (",", ";", "\t", "|"):
        raise CleanupError("delimiter must be comma, semicolon, tab or pipe.")
    if "excel_safe" in config and not isinstance(config["excel_safe"], bool):
        raise CleanupError("excel_safe must be true or false.")
    return config


def read_source(path: Path, config: dict) -> tuple[bytes, list[str], list[dict], str]:
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
    except (OSError, UnicodeError) as error:
        raise CleanupError(f"Cannot read UTF-8 CSV: {error}") from error
    if not text:
        raise CleanupError("CSV is empty; a header is required.")
    delimiter = config.get("delimiter")
    if delimiter is None:
        try:
            delimiter = csv.Sniffer().sniff(text[:131072], delimiters=",;\t|").delimiter
        except csv.Error:
            # Sniffer can fail on quoted multiline records. Compare logical
            # records, and accept a unique consistent multi-column candidate.
            candidates = []
            for candidate in ",;\t|":
                try:
                    rows = list(islice(csv.reader(io.StringIO(text, newline=""), delimiter=candidate, strict=True), 101))
                    if rows and len(rows[0]) > 1 and all(len(row) == len(rows[0]) for row in rows):
                        candidates.append(candidate)
                except csv.Error:
                    continue
            if len(candidates) == 1:
                delimiter = candidates[0]
            elif not any(character in text.splitlines()[0] for character in ",;\t|"):
                delimiter = ","
            else:
                raise CleanupError("Cannot detect CSV delimiter; set delimiter in config.")
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
    try:
        headers = next(reader)
        if not headers or any(not header.strip() for header in headers):
            raise CleanupError("Every column must have a nonblank header.")
        if len(headers) != len(set(headers)):
            raise CleanupError("Duplicate column headers are not allowed.")
        if len(headers) > MAX_COLUMNS:
            raise CleanupError(f"Service limit: at most {MAX_COLUMNS} columns.")
        configured = set(config.get("trim_columns", [])) | set(config.get("case_columns", {})) | set(config.get("required_columns", [])) | set(config.get("date_columns", {})) | set(config.get("key_columns", []))
        missing = configured - set(headers)
        if missing:
            raise CleanupError(f"Configured columns not found: {', '.join(sorted(missing))}")
        records = []
        previous_line = reader.line_num
        for row_number, values in enumerate(reader, 1):
            start_line, end_line = previous_line + 1, reader.line_num
            previous_line = end_line
            if len(values) != len(headers):
                raise CleanupError(f"Wrong width at data row {row_number} (line {start_line}): expected {len(headers)} cells, got {len(values)}.")
            if row_number > MAX_ROWS:
                raise CleanupError(f"Service limit: at most {MAX_ROWS} data rows.")
            records.append({"source_row": row_number, "source_line": start_line, "source_line_end": end_line, "original": values})
    except (csv.Error, StopIteration) as error:
        raise CleanupError(f"Malformed CSV near line {reader.line_num}: {error}") from error
    return raw, headers, records, delimiter


def date_issue(value: str, formats: list[str]) -> str | None:
    if not value.strip():
        return None
    matches = set()
    for format_string in formats:
        try:
            parsed = datetime.strptime(value, format_string).date()
        except ValueError:
            continue
        # strptime accepts missing zero padding; require the configured spelling.
        if parsed.strftime(format_string) == value:
            matches.add(parsed)
    if not matches:
        return "invalid_date"
    if len(matches) > 1:
        return "ambiguous_date"
    return None


def write_csv(path: Path, headers: list[str], rows, safe: bool = False) -> int:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\r\n")
        transform = lambda row: [excel_safe_cell(str(value)) if safe else str(value) for value in row]
        writer.writerow(transform(headers))
        for row in rows:
            writer.writerow(transform(row))
    # Reparse every emitted record and cell, including multiline fields and
    # formula-safe copies, before publishing any files.
    count = -1
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, strict=True)
        sentinel = object()
        for actual, expected in zip_longest(reader, chain([headers], rows), fillvalue=sentinel):
            if actual is sentinel or expected is sentinel or actual != transform(expected):
                raise CleanupError(f"CSV round-trip verification failed for {path.name}.")
            count += 1
    return count


def clean_csv(source: Path, config_path: Path, output: Path) -> dict:
    """Validate first, partition every record, then atomically publish a new directory."""
    if output.exists():
        raise CleanupError("Output directory already exists; choose a new path to preserve previous results.")
    try:
        config_bytes = config_path.read_bytes()
    except OSError as error:
        raise CleanupError(f"Cannot read config: {error}") from error
    config = load_config(config_path, config_bytes)
    raw, headers, records, delimiter = read_source(source, config)
    columns = {name: index for index, name in enumerate(headers)}
    changes = []
    first_exact = {}
    key_groups = {}
    changed_cells = set()
    formula_cells = []
    for record in records:
        original = record["original"]
        values = original.copy()
        issues = []
        for column in config.get("trim_columns", []):
            index = columns[column]
            new = values[index].strip()
            if new != values[index]:
                changes.append([record["source_row"], record["source_line"], column, values[index], new, "trim_outer_whitespace"])
                changed_cells.add((record["source_row"], column))
                values[index] = new
        for column, rule in config.get("case_columns", {}).items():
            index = columns[column]
            new = values[index].lower() if rule == "lower" else values[index].upper()
            if new != values[index]:
                changes.append([record["source_row"], record["source_line"], column, values[index], new, rule])
                changed_cells.add((record["source_row"], column))
                values[index] = new
        for column in config.get("required_columns", []):
            if not values[columns[column]].strip():
                issues.append(f"missing_required:{column}")
        for column, formats in config.get("date_columns", {}).items():
            issue = date_issue(values[columns[column]], formats)
            if issue:
                issues.append(f"{issue}:{column}")
        for column, index in columns.items():
            if formula_risk(original[index]) or formula_risk(values[index]):
                issues.append(f"formula_risk:{column}")
                formula_cells.append({"source_row": record["source_row"], "column": column})
        exact_key = tuple(values)
        record["duplicate_of"] = first_exact.get(exact_key)
        first_exact.setdefault(exact_key, record["source_row"])
        key_columns = config.get("key_columns", [])
        if key_columns:
            key = tuple(values[columns[column]] for column in key_columns)
            if any(not value.strip() for value in key):
                issues.append("missing_key:" + ",".join(key_columns))
            else:
                key_groups.setdefault(key, []).append(record)
        record.update(values=values, issues=issues)
    conflict_groups = 0
    for group in key_groups.values():
        if len({tuple(record["values"]) for record in group}) > 1:
            conflict_groups += 1
            for record in group:
                record["issues"].append("conflicting_key:" + ",".join(config["key_columns"]))
    prefix = "__audit_"
    while any(prefix + field in headers for field in ("source_row", "source_line", "issues", "duplicate_of")):
        prefix = "_" + prefix
    meta_headers = [prefix + field for field in ("source_row", "source_line", "issues", "duplicate_of")]
    partitions = {"clean": [], "review": [], "duplicates": []}
    audit = []
    for record in records:
        category = "duplicates" if record["duplicate_of"] is not None else "review" if record["issues"] else "clean"
        row = record["values"] if category == "clean" else [record["source_row"], record["source_line"], " | ".join(record["issues"]), record["duplicate_of"] or ""] + record["values"]
        partitions[category].append(row)
        audit.append([record["source_row"], record["source_line"], record["source_line_end"], category + ".csv", len(partitions[category]) + 1, record["duplicate_of"] or "", " | ".join(record["issues"])])
    counts = {key + "_rows": len(rows) for key, rows in partitions.items()}
    summary = {
        "schema_version": 1,
        "source": {"name": source.name, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "encoding": "utf-8-sig", "delimiter": delimiter},
        "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "configuration": config,
        "input_rows": len(records), "columns": headers, **counts,
        "reconciliation": {"input_rows": len(records), "partition_rows": sum(counts.values()), "balanced": len(records) == sum(counts.values())},
        "changed_cells": len(changed_cells), "change_events": len(changes), "conflicting_key_groups": conflict_groups,
        "formula_risk_cells": formula_cells, "formula_risk_headers": [header for header in headers if formula_risk(header)], "audit_metadata_prefix": prefix,
        "excel_safe_copies": config.get("excel_safe", False),
        "notes": ["All source records appear exactly once across clean, review and duplicates.", "Exact duplicates take precedence over review; their issues remain recorded and duplicate_of points to the first source row.", "Canonical CSV values are strings; date validation does not rewrite dates."]
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".csv-cleanup-", dir=output.parent))
    try:
        exports = [("clean.csv", headers, partitions["clean"]), ("review.csv", meta_headers + headers, partitions["review"]), ("duplicates.csv", meta_headers + headers, partitions["duplicates"]),
                   ("changes.csv", ["source_row", "source_line", "column", "original", "new", "rule"], changes),
                   ("row-audit.csv", ["source_row", "source_line", "source_line_end", "output_file", "output_row", "duplicate_of", "issues"], audit)]
        output_rows = {}
        for filename, export_headers, rows in exports:
            output_rows[filename] = write_csv(temporary / filename, export_headers, rows)
        if config.get("excel_safe", False):
            safe_directory = temporary / "excel-safe"
            safe_directory.mkdir()
            for filename, export_headers, rows in exports:
                output_rows["excel-safe/" + filename] = write_csv(safe_directory / filename, export_headers, rows, safe=True)
        summary["output_rows"] = output_rows
        actual_partition_rows = sum(output_rows[name + ".csv"] for name in partitions)
        if actual_partition_rows != len(records):
            raise CleanupError("Written CSV row reconciliation failed.")
        summary["reconciliation"]["verified_output_rows"] = actual_partition_rows
        summary["reconciliation"]["cells_round_trip_verified"] = True
        summary["output_sha256"] = {str(path.relative_to(temporary)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(temporary.rglob("*.csv"))}
        (temporary / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # Same-filesystem rename publishes a complete result; an existing target is never overwritten.
        if output.exists():
            raise CleanupError("Output path appeared during processing; no result was overwritten.")
        os.rename(temporary, output)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        summary = clean_csv(args.source, args.config, args.output)
    except (CleanupError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"input_rows": summary["input_rows"], "clean_rows": summary["clean_rows"], "review_rows": summary["review_rows"], "duplicates_rows": summary["duplicates_rows"], "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
