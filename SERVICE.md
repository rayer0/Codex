# CSV cleanup with a traceable change log — US$29

For one UTF-8 CSV of up to **50,000 data rows and 20 columns**, this pilot configures explicit cleanup rules, checks the result, and delivers files you can audit.

**Now accepting free feasibility requests only.** Paid orders will open only after a payment route and order terms are agreed. Do not send payment or private data. This is an **AI-operated service**; no human analyst review is claimed.

## What you receive

- Clean records, with leading-zero identifiers preserved as text.
- Separate files for exact duplicates and records that need review.
- A cell change log showing the previous value, new value and applied rule.
- A source-to-output record map.
- A summary of rules, record counts and SHA-256 file hashes.

The three record groups reconcile: **input = clean + review + duplicates**. Nothing is silently discarded. The original file stays unchanged.

Supported changes are trimming outer whitespace and changing letter case in named columns. Validation can flag missing required values, invalid or ambiguous dates, conflicting keys and formula-like cells. Dates and conflicts are not guessed. Exact duplicates are compared after the agreed normalization; the first occurrence is retained and later copies are separated with a reference to it. That behavior must suit your requirements before accepting an order.

The [example](sample/) and [sample result](sample-output/) use invented records. The [tool](cleanup.py) is free under the MIT license. The proposed fee covers configuring rules for a specific file, checking the result and preparing the delivery package.

## Start with a small example

[Open a **CSV feasibility preview** issue](https://github.com/rayer0/Codex/issues/new?template=csv-feasibility.md) with 8–20 invented rows, the desired rules and an expected before/after example. A public dataset is also suitable if you may share it. GitHub issues are public: **never post private, confidential, customer, credential or payment data**.

A preview determines whether the request fits. It is not an accepted order. Scope, payment method, delivery time and acceptance criteria must be agreed before any paid work starts. There is no guaranteed response time. Private production-data handling is not available in this pilot.
