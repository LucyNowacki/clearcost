# Local validation — 15 September 2026

Result: the scoped local validation passed after the fixes below. This is not a
production-readiness or security certification. No model calls or deployment were
performed. Interactive review writes were confined to a disposable copy on port
8877; Lucy's normal dashboard database was not used for test writes.

## Automated checks

- 39 Python unittest tests passed, including eight new HTTP integration tests.
- Ruff checks for Python F and E9 rules passed (not a claim that all Ruff rules pass).
- JavaScript parsing passed for Invoice review, Data analysis and Geography.
- The final Python run emitted no database ResourceWarnings.
- HTTP checks cover all pages, each contract's totals and PDFs, duplicate saves,
  reopening SQLite, latest-review precedence, stale edit rejection, cross-page
  completion counts, local host/origin restrictions, invalid requests, stale
  extraction evidence, damaged draft files, missing report, malformed geography
  and missing database tables.

## Interactive browser checks

Conducted in Codex's Chromium-based in-app browser on an isolated copy.

- A saved review increased completion from four to five in that copy.
- Saving again showed No changes to save and did not add a history record.
- Keep editing in the new in-page dialog retained the original filter and notes.
- Discard changes switched to the requested contractor's matching findings.
- Two tabs edited the same finding: the second saved; the first retained its
  unsaved note and its conflicting save was rejected. Refresh loaded the winner.
- Restarting the isolated server retained the saved reviewer, note, six history
  entries for the test finding, and overall completion count.
- All five analysis contractor scopes showed one contract, fifteen visits,
  sixteen invoice lines and four flagged findings.
- Analysis and Geography were inspected at a 390px viewport without page-wide
  horizontal overflow. Tables retain their intentional local horizontal scroll.
- Geography's outstanding-inspection marker mode showed the updated counts.
- Stopping the isolated server produced a connection warning; restarting it
  restored page data. The revised warning explicitly labels displayed data as
  potentially out of date.

## Fixed during this pass

1. Explicitly closed SQLite connections in the review store and reconciliation
   producer; fixed the same connection-lifetime issue in tests.
2. Added defensive loading for saved draft files. A damaged file no longer hides
   valid drafts; the extraction page reports skipped unreadable files.
3. Returned structured errors for unavailable or malformed data and database
   failures instead of dropping HTTP connections.
4. Made the Geography endpoint read metadata from the active workspace root.
5. Replaced the unreliable native filter-discard prompt with an in-page dialog;
   controls restore their original values while the decision is pending.
6. Replaced raw network failure messages with actionable connection warnings.
7. Removed an unused test import identified by Ruff.

## Remaining before public deployment

- Choose hosting and test persistence/restarts in that actual environment.
- Decide whether public review state is read-only, session-isolated or authenticated.
  The local demo currently shares one database and accepts a typed reviewer name.
- Check the deployed origin/host configuration; the current server intentionally
  permits localhost only and uses Python's local HTTP server.
- Run independent Firefox/WebKit and actual Opera checks if those are release
  targets. This pass did not generate a standalone Playwright trace artifact.
- Complete a dedicated accessibility/keyboard audit and phone-browser check.
  The main review page's phone layout was not independently verified in this pass.
- Extracted terms remain advisory drafts, not approved calculation rules. Closing
  an inspection does not record a supplier credit note or money recovered.

## Reproduce automated checks

From the Fuse project directory, with the project's Python dependencies installed:

```bash
python -m unittest discover -s tests -q
ruff check --select F,E9 .
```

The new integration tests use temporary source copies and SQLite databases. Ruff
was installed into temporary QA tooling for this pass, not the application runtime.
