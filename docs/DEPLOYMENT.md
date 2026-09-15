# GitHub Pages publication

Repository: `LucyNowacki/clearcost`. Site: https://lucynowacki.github.io/clearcost/.

The `main` branch contains source, synthetic inputs, saved extraction examples and tests. The `gh-pages` branch contains only the generated browser edition, including `.nojekyll`. GitHub builds and publishes that branch automatically. This repository does not modify or deploy Lucy's personal website repository.

To update: build and test from `main`; commit and push source changes. Copy the generated contents of `dist/clearcost/` into a checkout of the existing `gh-pages` branch, excluding any `.git` directories. Commit and push that branch without force-pushing. Inspect the Pages build and check the public URL after it completes. Do not copy local SQLite databases, environment files, raw request logs or personal reviews into the publishing branch.

On Lucy's current workstation, `dist/clearcost/` is already a separate Git checkout of `gh-pages`. The build updates its site files while preserving its Git metadata. A fresh clone of `main` does not have that nested checkout; use a separate checkout of `gh-pages` when publishing from another machine.

Reviews live in browser localStorage, scoped to the project path and source dataset. They are not uploaded or shared across browsers. Reset demo clears this application's review key only. Storage on the same origin is not an authentication or security boundary; use synthetic review notes only. The published site runs no Python server and makes no live model calls.
