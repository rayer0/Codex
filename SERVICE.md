# CSV cleanup with a traceable change log — US$29 one time

> **Now accepting requests for the US$29 paid pilot.** Start with a free feasibility preview; payment follows a specific order confirmation.

For one UTF-8 CSV with a header, up to **50,000 data records excluding the header and 20 columns**, this pilot configures explicit cleanup rules, validates the result and delivers files you can audit. The fee is **US$29 for this file**, not a subscription. The original [MIT tool](LICENSE) is free; the service fee covers rule configuration, validation and delivery.

This is an **AI-operated service**; no human analyst review is claimed. Both the preview and the complete file must contain only non-sensitive synthetic data or non-sensitive public data you are authorized to share. Private production-data handling is unavailable. No sales or revenue are claimed.

## Start with a free example

[Open a **CSV feasibility preview** issue](https://github.com/rayer0/Codex/issues/new?template=csv-feasibility.md) with 8–20 invented rows, the desired rules and an expected before/after example. A suitable public dataset is also welcome. GitHub issues are public: **never post customer, private, personal, confidential, credential or payment data**.

A preview checks whether the request fits. It is free and is not an accepted order. It does not reserve a delivery date. There is no guaranteed response time.

## Agree the order before payment

After a successful preview, confirm all of the following in the order reply:

- The single input file/version or SHA-256 hash, its size and its public-data suitability.
- The named columns, exact cleanup and validation rules, duplicate policy, and an example with the expected result.
- The six deliverables below, their delivery location and the acceptance checks.
- The one-time US$29 service fee, payment timing, completion date/time and time zone.
- The correction, cancellation and refund terms below.

Only after the specific scope and terms are agreed will a verified live payment link be supplied for that order. There is no unrestricted public buy-now link. Do not pay against an unconfirmed preview, an old order or a test link. Payment details belong in the payment provider's checkout, never in a GitHub issue. An order is accepted only when its confirmation explicitly says so; an inquiry or payment alone does not expand the agreed scope.

Delivery and any correction deadline are agreed per order. There is no fixed response SLA or unattended delivery promise.

## What you receive

- `clean.csv`: first occurrences without review flags; leading-zero identifiers remain text.
- `review.csv`: records needing review, with reasons.
- `duplicates.csv`: exact normalized full-row duplicate copies, with a reference to the first occurrence.
- `changes.csv`: cell-level previous values, new values and applied rules.
- `row-audit.csv`: a source-to-output record map.
- `summary.json`: rules, record counts, flags, reconciliation and SHA-256 hashes of the source, configuration and delivered CSV files.

The three record groups reconcile: **input = clean + review + duplicates**. Every input record appears exactly once across those groups; nothing is silently discarded. Duplicate classification takes precedence over review, while duplicate issues remain recorded. The original file stays unchanged. The [example](sample/) and [sample result](sample-output/) use invented records.

Supported changes are trimming outer whitespace and changing letter case in named columns. Validation can flag missing required values, invalid or ambiguous dates, conflicting keys and formula-like cells. Dates are validated, not rewritten; values and conflicts are not guessed. Exact duplicates are compared after the agreed normalization: retain the first occurrence and separate later copies. This behavior must fit the agreed example before an order is accepted. New transformations require a separate feasibility and scope agreement.

## Acceptance and one included correction

The agreed rules and example must pass. The original file must remain unchanged, every source record must map to exactly one output group, and counts must reconcile. Delivered CSVs are reparsed and compared cell-for-cell before delivery; recorded file hashes must match the delivered files. These checks establish the agreed processing and audit trail, not a guarantee that source data represents real-world facts.

Report a specific discrepancy within **7 calendar days of delivery**. One correction within the original agreed scope is included, with its completion date agreed separately. Replacement inputs, new rules and added scope are excluded. Silence is not treated as explicit acceptance.

## Proposed cancellation and refund terms

These terms become part of an order only when explicitly agreed in its confirmation:

- Cancel before delivery: a full refund of the service fee collected for that order.
- After delivery: use the included correction for an in-scope discrepancy. If the agreed acceptance checks still cannot be met, a full refund of the service fee collected for that order.
- New requirements are not defects in the original scope. Cancelling an unpaid request creates no refund transaction. Refund arrival times are not guaranteed.

This page does not accept an order, record a payment or confirm an executed refund. Every request starts with a free feasibility preview before an order is accepted.
