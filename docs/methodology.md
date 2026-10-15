# Analytics methodology

This is a bounded, locally reproducible Career portfolio analysis, not Ekimetrics
client work. The CAB observations and the entirely synthetic marketing example
are separate datasets, models and currencies. Nothing here is a causal ROI claim,
investment recommendation or reproduction of the original notebook's forecasts.

## Reproduce

Run from `marketing-decision-lab` using Lucy's existing environment:

```bash
/home/lucy/anaconda3/envs/lucy/bin/python scripts/fetch_data.py
/home/lucy/anaconda3/envs/lucy/bin/python scripts/build_data.py
/home/lucy/anaconda3/envs/lucy/bin/python -m pytest -q -o cache_dir=tests/.pytest_cache --basetemp=tests/.tmp
```

`build_data.py` delegates to `build_dashboard.py`; either name is supported.
Fetching downloads only missing files. Subsequent builds are offline by default;
`build_data.py --download` permits fetching missing files. A modified cache is
rejected rather than overwritten. No notebook, live AI model or publication
command is executed, and no extra dependency is installed.

## Sources and provenance

- Primary CAB source: [DataGlacier/DataSets](https://github.com/DataGlacier/DataSets/tree/1fc686d1e8d01d23bd5be9316f77170ac0a7fcd8), pinned to commit `1fc686d1e8d01d23bd5be9316f77170ac0a7fcd8`, resolved with `git ls-remote`.
- Inputs: `Cab_Data.csv`, `Transaction_ID.csv`, `Customer_ID.csv`, `City.csv`.
- Historical source: [LucyNowacki/CAB_EDA, Cab_2.ipynb](https://github.com/LucyNowacki/CAB_EDA/blob/76c2a3115b1c69d49eeddec109990b8ce3fcf842/Cab_2.ipynb), 109 cells, commit `76c2a3115b1c69d49eeddec109990b8ce3fcf842`.
- `data/source_manifest.json` records each immutable URL, SHA-256, byte count,
  row count and source columns. Hashes are calculated from the first HTTPS
  downloads, then enforced on reuse; they are integrity records, not independent
  authentication of the dataset's real-world accuracy.
- `data/manifest.json` and `dist/data/manifest.json` record the notebook's local
  hash, exact runtime versions and generated dashboard hash. Stable sorting and
  no wall-clock timestamps permit byte-identical builds in the recorded runtime.
  Cross-version floating-point identity is not promised.

The public repository is treated as a teaching dataset, not verified operating
records. Licensing/redistribution clearance is not established by this slice.
Raw customer/transaction rows remain only under ignored `data/raw/`. The browser
artifact contains aggregate CAB data and synthetic weekly observations, with no
customer IDs, transaction IDs or demographic values. Publication remains the
parent's responsibility and is not performed here.

## CAB validation and joins

Required fields, nonblank keys/categories, integer positive IDs, finite monetary
and distance fields, date serials, and lookup numeric formats are validated.
Negative price/cost/distance, duplicate transaction/customer/city keys, malformed
comma-separated population counts and invalid dates fail the build. Negative
gross contribution is allowed and is never clipped.

Dates use Excel serial-day origin `1899-12-30`, with a checked 2016-2018 window.
The resulting coverage is **2016-01-02 to 2018-12-31**. This is an explicit
interpretation of the source serial dates, not an assertion about missing days.

Every lookup is a validated many-to-one **left join**. Missing lookup matches do
not remove a CAB row. The report distinguishes unmatched left rows from unused
right-table entries:

| Lookup | Right rows | Matched CAB rows | Unmatched CAB rows | Unused right rows |
| --- | ---: | ---: | ---: | ---: |
| Transactions | 440,098 | 359,392 | 0 | 80,706 |
| Customers | 49,171 | 359,392 | 0 | 3,023 |
| Cities | 20 | 359,392 | 0 | 1 |

All **359,392** CAB rows are retained. The extra city is not a missing CAB city:
the transactions cover 19 cities and the lookup contains 20. The dashboard has
1,368 month/company/city aggregates (36 months, two companies, 19 cities).
City aggregates include source population/users without geocoding. Those lookup
counts are not current census figures or verified market penetration denominators.

## CAB definitions

`gross contribution = Price Charged - Cost of Trip`. It is **not net profit**:
overhead, tax, financing and other costs are not observed. Financial sums retain
source precision; rounding belongs to display, not intermediate aggregation.

| Company | Trips | Revenue (USD) | Gross contribution (USD) | Distinct customers |
| --- | ---: | ---: | ---: | ---: |
| Pink Cab | 84,711 | 26,328,251.33 | 5,307,328.321 | 32,330 |
| Yellow Cab | 274,681 | 125,853,887.19 | 44,020,373.1708 | 39,896 |

Customer totals are unique within a company, not mutually exclusive across
companies. Segments use each identified customer's **full-window, per-company**
trip count: `one-trip`, `2-5`, `6+`. They describe observed frequency, not lifetime
loyalty, prospective features or demographic targeting. A customer ID in the
transaction table remains usable even if its demographic lookup is unmatched.
Trips lacking any customer ID are retained in an explicit `unknown` segment;
its `customers: 0` means no identified customers, not zero unidentified people.

Monthly retention is the intersection of current and previous-calendar-month
customer sets divided by the previous month's customer count. The first month
and empty-denominator cases are `null`, never filled from future observations or
forecasts. Missing customer IDs are excluded from customer-set calculations, not
from trip or revenue aggregates. Retention is descriptive and is not a model input.

## CAB retrospective forecast test

Target: company-level monthly **revenue in USD**, not contribution or return on
investment. There are 36 consecutive observed months. January 2016 through June
2018 (30 months) is training; July through December 2018 (six months) is the one
fixed-origin holdout. Missing months cause an explicit failure rather than silent
interpolation or imputation.

The simple Ridge model uses a linear time index and sine/cosine pairs for annual
harmonics 1 and 2. `StandardScaler` is fitted only on those 30 training months,
followed by `Ridge(alpha=1)`. The specification is fixed, without test-error-based
selection or tuning. Seasonal-naive repeats the same month from the preceding
year; all six baseline values are already observed at the June 2018 origin.

| Company | Model | MAE (USD) | RMSE (USD) | WAPE ratio |
| --- | --- | ---: | ---: | ---: |
| Pink Cab | Ridge trend + seasonality | 132,289.51 | 144,978.63 | 0.13649160 |
| Pink Cab | Seasonal naive | 119,649.59 | 138,729.57 | 0.12345018 |
| Yellow Cab | Ridge trend + seasonality | 555,114.85 | 601,960.51 | 0.13835395 |
| Yellow Cab | Seasonal naive | 507,282.31 | 534,926.45 | 0.12643241 |

**The seasonal-naive baseline beats Ridge for both companies** on this holdout.
This result is retained, not tuned away. WAPE is `sum(abs(error))/sum(abs(actual))`,
stored as a ratio (`0.1` means 10%), and is null for a zero denominator. This is
a small retrospective test with no prediction intervals, rolling-origin study or
claim of generalization to another time period. The exported six points are not
a new forecast beyond the observed dataset.

## What changed from the historical notebook

Notebook cell references below are zero-based JSON cell positions. The notebook
was inspected as source, not executed or repaired.

1. **Incomplete checked-in inputs:** cell 2 expects the four main CSVs, while
   later cells expect `city_data_geo.csv`, `UNRATE.csv`, `GASREGCOVW.csv` and
   intermediate enriched CSVs absent from the notebook checkout. This slice
   fetches only the four pinned primary inputs and omits macro/geocoded enrichment.
2. **Sample shrinkage:** cell 42 uses an exact-date inner join with gasoline
   observations; only matching dates survive. This slice never inner-joins
   enrichment into the CAB sample. The historical loss is not quantified because
   the absent enrichment files and notebook execution were not reconstructed.
3. **Unknown initial retention:** cell 51 forecast-fills the initial unknown
   retention; cell 87 alternatively uses subsequent-month averages. Neither
   establishes an observed previous-period denominator. Initial retention here
   remains unknown, and prefix-invariance tests guard against future filling.
4. **Unvalidated complex forecasts:** cells 102-106 fit the UMAP/XGBoost/Prophet
   pipeline and extrapolate without a held-out temporal evaluation of those
   forecasts. A `train_test_split` import in cell 98 is not itself a holdout.
   This slice does not reproduce, validate or endorse those forecast results.
5. **Unreconciled investment/time units:** cell 98 labels a table monthly while
   grouping with `to_period('D')`; cell 102 then generates monthly future dates
   and multiplies a mean contribution-per-km prediction by predicted distance.
   The numerator's daily/monthly scale and economic meaning are not reconciled
   before comparison with example investments of 100m/400m in cells 104/106.
   These are not validated net-profit/equity returns, so no investment-return
   claim or investment amount is carried into this dashboard.
6. **Date offset:** cell 35 uses `1900-01-01` plus the source day number, shifting
   Excel-serial dates two days forward. The explicit Excel origin here avoids
   that offset and preserves the 36-month 2016-2018 window.

## Synthetic marketing response

The simulation is entirely separate from CAB and uses **simulated GBP**. Seed
`20261015` generates 156 Monday weeks, 2022-01-03 through 2024-12-23. Independent
random campaign variation supplies search/social/video spend; the outcome adds
an intercept, trend, annual seasonality, media response and Gaussian noise.

The model is deliberately correctly specified: decay `(0.35, 0.55, 0.70)` and
half-saturation `(14000, 20000, 26000)` are fixed to known generator settings.
They are not recovered from data or tuned on test results. Generator media
coefficients `(24000, 18000, 14000)` are distinct from fitted coefficients, and
both are labelled in the JSON. This favourable setup is not evidence that an
observational marketing mix model can identify real causal effects.

Unnormalised adstock follows `a[t] = spend[t] + decay * a[t-1]`, initialized at
zero. Hill exponent is one: `a/(half+a)`. `scipy.optimize.lsq_linear` fits six
unconstrained control coefficients (intercept, trend, two annual Fourier pairs)
and three nonnegative media coefficients on the first **130 weeks** only.
The last **26 weeks** are the untouched test period, 2024-07-01 to 2024-12-23.
There is no inner selection, validation split or post-test refit.

Holdout predictions condition on the observed holdout spend. This is conditional
response prediction, not a spend forecast. Adstock carries historical spend
across the boundary but uses no future spend or holdout revenue. Training-week
predictions are in-sample. The seasonal-naive baseline uses revenue 52 weeks
earlier, with all its source weeks in training.

| Model | Holdout MAE (GBP) | Holdout RMSE (GBP) | WAPE ratio |
| --- | ---: | ---: | ---: |
| Nonnegative adstock + Hill regression | 447.13 | 546.38 | 0.00550420 |
| 52-week seasonal naive | 5,100.65 | 5,599.34 | 0.06278994 |

## Budget/browser contract

SLSQP optimizes 19 **weekly** budgets from GBP 10,000 through 100,000 in increments
of 5,000. Channel shares sum to one and each is between 10% and 60%. The same
fitted coefficients and response are used for the feasible equal-third baseline.
The solver must succeed, satisfy the constraints and be no worse than that baseline.

Plans assume constant weekly spend repeated until **steady state**, not an
immediate single-week effect. For each exported channel:

```text
steady_state_multiplier = 1 / (1 - decay)
x = weeklySpend * steady_state_multiplier
incrementalRevenue = coefficient * (x / (half_saturation + x))
```

Sum the three channel responses for the allocation total. This is modelled
incremental revenue versus zero-media steady state; it excludes baseline
trend/seasonality, does not subtract spend, and is not profit or causal ROI.
For example, at GBP 40,000, shares are approximately 40.8481% search, 33.7910%
social and 25.3609% video: response GBP 34,070.04 versus GBP 33,776.65 for equal
shares (a modelled response gain of GBP 293.38, not financial profit).

`train_spend_min`/`train_spend_max` expose each channel's observed training range;
`outside_training_spend_range` flags plans outside any of those ranges. The
frontend can use the same bounds for each currently selected channel allocation.
Range membership does not establish support for the steady-state assumption.
Parameter uncertainty, interactions, auctions, competitive response and additional
commercial constraints are not modelled. No real allocation recommendation follows.

## Validation and artifact boundary

Tests cover duplicate keys, missing fields, malformed numerics/dates, left-join
row preservation, unknown customer handling, behavioural segment reconciliation,
retention gaps and no future filling, training-only scaling/fitting, fixed holdout
predictions under changed test targets, causal adstock prefixes, nonnegative
coefficients, budget boundaries, all-plan browser-formula agreement, multiplier
validation, synthetic/currency flags, output metrics, raw-ID rejection, checksums,
offline cache reuse and byte-identical repeat builds. Full-data integration tests
require the initial local build; they explicitly skip when its artifacts/cache
are absent. The reported local test run includes them.

Source and generated files owned by this slice:

- `src/decision_lab/`: `__init__.py`, `sources.py`, `metrics.py`, `cab.py`,
  `media.py`, `validation.py`, `build.py`.
- `scripts/`: `fetch_data.py`, `build_dashboard.py`, `build_data.py`.
- `tests/`: `conftest.py`, `test_cab.py`, `test_media.py`, `test_build.py`, `.gitignore`.
- `data/`: `source_manifest.json`, `manifest.json`; four ignored CSVs in `raw/`.
- `dist/data/`: `dashboard.json`, `manifest.json`.
- `docs/methodology.md`.

Frontend, README, publication and CV changes are outside this slice. Browser
verification is the parent's work and is not claimed as independently checked here.
