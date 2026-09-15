# Clearcost — Energy Contractor Cost Reconciliation

[Open the portfolio demo](https://lucynowacki.github.io/clearcost/)

Source code: `main` branch. Published static files: `gh-pages` branch.

A portfolio demo by Lucy Nowacki, using fictional energy contractor invoices. Includes a local Python/SQLite application and a browser-only GitHub Pages edition. Open
`fuse.code-workspace` in VS Code. No hosting, Google Sheets connection or LLM is
required for this stage.

## Run from the VS Code terminal

Python 3.10 or newer:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python reconcile.py
python -m unittest discover -s tests -v
```

The default inputs are the five subfolders of `Data/Contracts`. The earlier
MeterCare example directly under `Data` is preserved but not part of this run.

Outputs:

- `output/reconciliation.sqlite3`: run history, source hashes, extracted terms,
  original visit and invoice records, and line-level findings.
- `output/reconciliation.json`: the latest run, summaries and evidence references.

Each run appends a distinct run ID to SQLite. Filter by that ID when querying;
otherwise repeated runs would be counted more than once. The JSON report is
replaced with the latest completed run. Input files are never modified.

## What is implemented

The engine reads `contract.pdf`, `visits.csv` and `invoice_lines.csv`. It extracts
rates and approvals with a deliberately narrow adapter for the authored August
2026 contract template. It is **not a general PDF interpreter or an LLM**. Changed
wording requires review and extension of the adapter. Some contract rules are
explicitly recognised template assumptions, not inferred legal interpretations.

The contractor's invoice PDF is a visual copy of the CSV and is not independently
parsed by the engine. PDF/CSV agreement was checked when the synthetic data was
created. General invoice extraction and Google Sheets review are later stages.

Checks cover agreed rates, cancellation fees, incomplete work, valid supplements,
duplicate jobs, invoice arithmetic, service dates and missing evidence. Unknown
expected amounts remain JSON null and SQL NULL. Any unverified line makes the
complete expected invoice total and discrepancy unavailable; separately labelled
known subtotals remain available. Flagged amounts are not realised savings.

Each contractor has 15 service records and 16 invoice lines. The five supplied
scenarios have 20 flagged lines and GBP 987.00 in known discrepancies. Tests read
`expected_results.json` as an oracle; the engine never reads it. Tests also cover
missing records, invalid approval references and other edge cases separately.

## Example SQLite query

```sql
SELECT contract_id, SUM(billed_pence) AS billed_pence
FROM invoice_lines
WHERE run_id = (SELECT run_id FROM runs ORDER BY created_at DESC LIMIT 1)
GROUP BY contract_id;
```

Money is stored as integer GBP pence, before VAT. CSV ingestion rejects unsupported
currencies, duplicate identifiers and malformed amounts. This demo supports one
invoice per contract scenario, quantities of one, and no prior-period invoices.
It does not execute payments or supplier communications. Human review decisions are stored separately from the calculated findings.


## Local review dashboard

After running reconciliation, start the dashboard in the VS Code terminal:

```bash
python dashboard.py
```

Open http://localhost:8765. Stop the server with Ctrl+C.

Clearcost is the demo interface name. The green-and-cream workspace provides
contractor and status filters, search, billed/expected comparisons, source PDF
links, review notes, and a decision history. All data is fictional.

Review decisions are appended to `review_events` in the existing SQLite database.
A reviewer name is a self-entered label, not an authenticated identity. Confirmed
errors and valid charges require a written reason. Conflicting edits are rejected;
refresh before retrying. Reviews are tied to evidence hashes, so changed evidence
requires a new review; unchanged reconciliation reruns retain their reviews.
The displayed discrepancy total remains the engine finding, not realised savings.

This server is bound to localhost for a single-machine demonstration. Google
Sheets, LLM integration, Excel export and public hosting remain later steps.

Validation: 15 unit tests cover reconciliation and review persistence, history,
required reasons, stale evidence and conflicting edits. Desktop layout and
contractor filtering were checked in-browser; the narrow layout has no horizontal
overflow at a 390-pixel viewport.

## Phase five: Luna extraction drafts

Implemented as a separately reviewable stage, pending live model evaluation.
`llm_contracts.py` accepts searchable PDF or UTF-8 text, prepares a strict structured
request for GPT-5.6 Luna, and validates field coverage and exact supporting quotes
on their cited pages. This validates evidence location, not semantic correctness.
Conditional charges and exceptions remain textual drafts, never automatic rates.

Offline preparation (no network or credentials required):

```bash
python llm_contracts.py Data/Contracts/01_northbank_meter_services/contract.pdf
```

For a later authorised live test, configure `OPENAI_API_KEY` in your local process
environment and add `--live` to that command. Never paste a key into project files
or commit it. Live mode sends extracted document text to OpenAI's Responses API,
uses low reasoning effort, caps output at 6,000 tokens, and makes no automatic
retries. No live calls have been performed during implementation.

Requests and draft results go under ignored `output/llm/`. Successful identical
requests reuse saved results, keyed by document hash, request and version. API
refusals, incomplete responses and invalid evidence do not produce accepted drafts.
Usage returned by the API is retained with each draft. Scanned/empty documents and
documents above 60,000 characters are rejected by this initial adapter.

The dashboard's **Contract extraction drafts** link shows live draft terms, source
passages, page numbers and uncertainty. It labels changed source documents stale.
The five prepared offline requests are not displayed as model results. Opening
this page never calls the API. Existing reconciliation and invoice-review history
are independent of these drafts.

Remaining phase-five gates: real Luna extraction evaluation on the five contracts
and varied wording, a term approval workflow, and a validated adapter from approved
terms into the reconciliation engine. Arbitrary contract clauses are not executable
rules yet. Current verification: 23 offline unit tests pass, including mocked API
responses, missing/false evidence, incomplete responses, and cached repeated calls.

API reference: https://developers.openai.com/api/docs/guides/structured-outputs

## Local Spark route using your Codex subscription

```bash
conda activate lucy
python spark_contracts.py Data/Contracts/01_northbank_meter_services/contract.pdf
```

This route requires `codex login status` to report ChatGPT sign-in. It removes
API-key environment overrides, ignores user CLI configuration, selects
GPT-5.3-Codex-Spark explicitly, and uses an ephemeral read-only session in a temporary
folder. It consumes Codex allowance rather than making a separate API-key call.
It is for local, trusted use; do not expose this runner through a public dashboard.

The result uses the same evidence validator and drafts viewer as the Luna route.
Repeated identical successful requests reuse the local draft. Rejected results
are retained separately under `output/llm/rejected/` and never shown as accepted
extractions. There are no automatic retries. The first Northbank live attempt
failed quote validation; after tightening the quote instruction, the second passed.
Its extracted core rates agree with the controlled contract: completed GBP45,
cancelled GBP0, incomplete no charge. Other contractors and varied wording have
not yet been evaluated. 25 offline unit tests pass. Term approval and automatic
use of approved extractions in reconciliation remain future work.

### Extracted evidence beside findings

The finding panel now displays saved model terms and their source quotes/pages.
Known finding categories select relevant fields (including all mapped issues on a
line). All remaining extracted terms and warnings stay visible in an expandable
section, so extra conditions are not discarded. Unknown categories or missing
terms are marked for further review. Version two extraction requests allow extra
named charging conditions in addition to the required baseline fields. That new
prompt has not yet been evaluated live; existing saved drafts remain available.

The draft remains unapproved evidence. Calculated amounts still use the original
controlled parser. Arbitrary conditions are not automatically executed or assigned
to particular jobs. No new model calls were made for this display change.
Validation: 29 unit tests pass; browser inspection confirmed that selecting the
Northbank cancellation finding displays the saved cancellation term and page link.

### Data analysis and planning

Open `/analysis` from the sidebar for contractor-filtered coverage, visit outcomes,
issue counts, known financial differences, and inspection workload. Contract rates
and visits come from SQLite for the report's exact run; current decisions use the
latest review event per evidence key. The page checks for updates every three
seconds. Planning rows link to a contractor's review queue. Outstanding difference
means the known difference on inspections still open, not money recoverable or
recovered. Drafts remain unapproved evidence. These charts describe the synthetic
sample, not comparative contractor performance in production.

### Geographic coverage

The Geography tab uses `Data/geography.json`: explicitly fictional service areas
linked to each contract and its visit IDs. Fifteen approximate city-area locations
cover all 75 demo visits. The read-only endpoint validates contract/contractor
identity, coordinates and unique visit assignments; reviews and original evidence
remain intact. Select a marker or area, filter by contractor, and size markers by
recorded visits or remaining inspections. The locally bundled Natural Earth map
needs no API key or network calls in the browser. See `web/MAP_SOURCE.md` for its
public-domain source. Locations are neither customer premises nor legal territories.

## Browser-only portfolio edition

Build and preview with the Lucy Python environment:

```bash
python build_static.py
python -m http.server 8878 --bind 127.0.0.1 --directory dist
```

Open `http://localhost:8878/clearcost/`. This exports synthetic examples and saved model drafts without local review history or live model calls. Reviews remain in the visitor's browser, shared across its tabs, and can be cleared using **Reset demo**. A different browser/device starts independently. The local Python dashboard and its SQLite reviews remain separate.

See [local browser-demo validation](docs/STATIC_DEMO_TEST_REPORT.md) for checks and limits. GitHub Pages publishes the root of the `gh-pages` branch.

Saved, synthetic extraction examples live in `Data/extraction_examples/`. Their source paths are relative so a fresh clone can reproduce the demo without a model call. Local extraction outputs, when present, take precedence over the same example.
