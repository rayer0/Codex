# Auditable CSV cleanup

Original Python 3 CLI; standard library only. No network requests, dependencies or uploads.

**Proposed fixed service: $29 for one UTF-8 CSV, up to 50,000 data rows and 20 columns.** Customer-selected rules, retained duplicate rows, exception review, a change log and reconciled counts. Currently accepting **free feasibility requests only**; paid orders require an agreed payment route and terms. See [SERVICE.md](SERVICE.md) for scope and the public preview process. This is not evidence of sales.

[Request a free feasibility preview](https://github.com/rayer0/Codex/issues/new?template=csv-feasibility.md) · [See the sample result](sample-output/summary.json) · [Read validation results](QA.txt)

## Run

```sh
python3 -m unittest discover -s tests -v
python3 cleanup.py sample/customers.csv --config sample/config.json --output sample-rerun
```

The supplied result is in `sample-output/`. The command creates a new `sample-rerun/` directory; use another new path for later runs. Existing output directories are rejected. All sample records are fictional.

## Rules

All cells remain strings. Leading-zero IDs, full-width characters and internal whitespace remain intact unless an explicitly configured rule changes them. No numeric conversion, NFKC normalization, fuzzy matching, enrichment or imputation occurs.

Config fields are optional:

- `trim_columns`: column names whose outer whitespace should be removed.
- `case_columns`: map column names to `lower` or `upper`. Trim runs before case conversion. Each change event records its immediate original/new values and rule.
- `required_columns`: flag blank or whitespace-only values.
- `key_columns`: nonblank unique-key fields. Conflicting rows with the same normalized key are all flagged; no winner is chosen.
- `date_columns`: map column names to accepted explicit formats. Supported: `%Y-%m-%d`, `%Y/%m/%d`, `%d/%m/%Y`, `%m/%d/%Y`, `%d-%m-%Y`, `%m-%d-%Y`, `%Y%m%d`. Exact zero padding is required. Dates are validated, never rewritten. A value matching two different dates is flagged as ambiguous. Empty optional dates are allowed; use `required_columns` to disallow them.
- `delimiter`: comma, semicolon, tab or pipe. Omit to attempt detection.
- `excel_safe`: create separate spreadsheet copies when `true`.

Unknown config keys/columns fail. Input is UTF-8 with or without BOM; quoted multiline cells are supported. Duplicate/blank headers, wrong widths, CSV parser errors and size-limit violations are rejected before results are published. Headers are case-sensitive and unchanged.

## Files

| File | Contents |
|---|---|
| `clean.csv` | First occurrences without review issues; original column names |
| `review.csv` | Missing values, date problems, key conflicts and formula-risk rows |
| `duplicates.csv` | Retained exact normalized full-row duplicates; first source row referenced |
| `changes.csv` | Source row/line, column, original/new values and rule |
| `row-audit.csv` | Every input record mapped to its destination file and record number |
| `summary.json` | Source/config and all delivered CSV SHA-256 hashes, rules, counts, flags and reconciliation |
| `excel-safe/` | Optional separate copies of all CSVs with risky fields apostrophe-prefixed |

Exact full-row deduplication is always enabled after the configured normalization rules. Every written CSV is reparsed and compared cell-for-cell before delivery. Every row appears exactly once: `input = clean + review + duplicates`. Duplicate classification takes precedence over review; duplicate issues remain recorded and `duplicate_of` may point to a review row. Original source files are never modified.

Review/duplicate metadata uses `__audit_` names, adding underscores to avoid input-header collisions. `source_row` means 1-based data record excluding the header; `source_line` is its starting physical line. Destination row numbers include the header and count CSV records, not physical lines.

## Spreadsheet handling

Canonical CSVs retain formula-like content. Cells beginning with tab/newline/carriage return, or whose first non-whitespace character is `=`, `+`, `-` or `@`, are conservatively flagged. Legitimate negative numbers can therefore need review. These explicit detection rules do not establish maliciousness or guarantee safety in every spreadsheet application.

`excel_safe: true` prefixes risky fields with `'` in separate copies only, including headers and change-log values. Use these copies when opening in spreadsheets; preserve canonical files for programmatic use. Spreadsheet imports can still convert IDs: import ID columns as **Text** to retain leading zeroes. The CLI itself preserves them.

## Service boundary

$29 covers one file with agreed explicit rules and an auditable result. No invented data, automatic conflict resolution, sensitive-domain conclusions or third-party enrichment. The pilot accepts only synthetic or shareable public examples; private production-data handling is not available. Never publish private/personal data in samples, repositories or public uploads. This project contains synthetic data only. The original tool is available under the [MIT license](LICENSE).
