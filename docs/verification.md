# Verification report

Local verification on 15 October 2026, using `/home/lucy/anaconda3/envs/lucy/bin/python` in the existing `lucy` conda environment. Test counts below describe this checked version, not production usage or independent certification.

## Analytical checks

`python -m pytest -q` passed **68 tests** locally with the pinned raw cache available. Coverage includes malformed and missing fields, invalid numeric values and dates, duplicate join keys, missing lookups without silent row loss, aggregate conservation, initial retention remaining unknown, chronological forecasting, holdout-target perturbations, adstock causality, media parameter validation, constrained budgets, the public data schema, modified source-cache refusal and deterministic offline rebuilds.

The committed aggregate export contains 359,392 trips, 1,368 month/company/city rows and no raw customer identifiers. All 359,392 trip rows survive each lookup join. Source and export hashes are recorded in the manifest. A fresh clone without raw input can run the unit and published-artifact checks; the full repeated-source-build integration test is skipped until the pinned inputs have been fetched.

The seasonal-naive forecast has lower six-month holdout WAPE than Ridge for both CAB companies. This result is retained. Simulated-media holdout errors are deliberately not advertised as real-world model accuracy: the generating decay and saturation parameters are supplied to the fitted model.

## Browser checks

`CHROME_PATH=/opt/google/chrome/chrome npm run test:browser` passed all **8 tests** using a fresh headless Chrome session against the local static app.

- All six analytical views render without JavaScript errors or external runtime requests.
- Chart canvas pixel checks confirm nonblank charts.
- Company/city/year filters match the aggregate data; city CSV export works.
- Unchecked acceptance criteria prevent a task being finalised. Reviewed state and reasons survive reload.
- New tasks and review exports work. HTML-like reviewer text is displayed as text, not executable markup.
- The simulated model allocation sums to 100%, respects share bounds and agrees with the Python optimiser's exported objective within integer-slider rounding.
- A stale review opened in another tab cannot overwrite the newer decision.
- Desktop 1440px and mobile 390px screenshots cover every view, with no page-level horizontal overflow. Wide data tables and board columns scroll inside their own containers.

Overview, board and media screenshots were visually inspected. The published README images are from the verified browser app. Interface colours use Lucy's portfolio purple, magenta and cyan as accents on white work surfaces.

## Scope and remaining limits

Browser reviews have no authenticated identity, server persistence or immutable audit trail. The project does not connect to Jira or execute marketing spend. The media optimiser omits real-world uncertainty and the original CAB investment forecasts are not reproduced. No claim of adoption, revenue improvement, campaign lift or recovered savings is made.

Publication uses an isolated `ekimetrics-decision-lab` source branch and a separate `decision-lab/` directory on the existing Clearcost `gh-pages` branch. The public site is checked after deployment; the local screenshots alone do not verify deployment. A later full replacement of the Clearcost Pages branch must retain this directory or republish it.
