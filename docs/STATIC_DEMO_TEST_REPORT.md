# Browser-only demo: local validation

Validated 15 September 2026. Nothing has been published to GitHub.

## Implementation

`build_static.py` runs reconciliation in a disposable database and exports only synthetic findings, planning data, geographic metadata, saved extraction evidence and ten source PDFs. Existing local reviews are not exported. The build goes to `dist/clearcost/` and does not modify the local application's database or personal website.

`web/static-demo.js` supplies the browser pages with precomputed results and stores review events in localStorage. Keys include the application path and dataset fingerprint. Tabs in the same browser share progress; different browser storage profiles start independently. This is a browser-local demonstration, not authenticated accounts or a multi-user database. Pages on the same GitHub origin are not a security isolation boundary; no sensitive data should be entered. The code touches only its own storage key.

Saving uses Web Locks to serialize tab writes and version checks to reject stale edits. Unchanged retries do not add history. Reset requires confirmation and removes only this demo's reviews. Clearing browser site data also removes reviews. Blocked/full/corrupt storage produces an error rather than a false save success. A current browser with Web Locks on HTTPS or localhost is required for saving.

The Python architecture remains described as the original local implementation. The exported introduction and Guidance explain that no Python server or model runs in the browser edition.

## Passed checks

- 40 Python tests, including export validation; 6 JavaScript storage tests.
- Targeted Ruff checks and syntax checks for the runtime and every exported inline script.
- Static HTTP serving at `/clearcost/`: all pages and ten PDFs; review API correctly absent.
- Export has no SQLite database, reviewer fields or home-directory paths; source identity remains stable across rebuilds.
- Browser save: one completed review yields 5% overall / 25% for Northbank.
- Repeated unchanged save retains one history entry.
- Navigating through analysis, geography and back retains saved reviews and consistent counts.
- Pie and line charts render; geographic marker selection and contractor navigation work.
- Stale edit in a second tab is rejected while preserving its unsaved text.
- Reset cancellation keeps history; confirmed reset returns to zero completed reviews.
- Contract link opens the matching PDF; the matching draft link displays Northbank's extracted evidence only.
- Separate storage instances remain independent in automated tests.

## Remaining checks

GitHub repository/Pages configuration and public URL have not been created or tested. The local preview uses a simple file server, not the application server. The primary desktop browser was tested through Codex; Opera, Firefox, Safari and actual mobile devices were not tested. A requested narrow viewport remained 1280 pixels wide in the tool, so that attempt does not establish mobile validation.

## Reproduce

From the Fuse project folder, using the Lucy environment:

```bash
python build_static.py
python -m unittest discover -s tests -q
node --test tests/test_static_store.cjs
python -m http.server 8878 --bind 127.0.0.1 --directory dist
```

Open `http://localhost:8878/clearcost/`. The original Python dashboard remains separate on port 8765. Static hosting must publish the contents of `dist/clearcost/` as the project site's root, with no extra nested `clearcost` directory.
