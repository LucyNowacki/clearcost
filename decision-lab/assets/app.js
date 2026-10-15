/* Aggregates are computed by the Python pipeline; review state stays in this browser. */
"use strict";
const $ = (s, p = document) => p.querySelector(s);
const $$ = (s, p = document) => [...p.querySelectorAll(s)];
const esc = (x) =>
  String(x ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const num = (x) =>
  new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 }).format(
    Number(x) || 0,
  );
const pct = (x) => `${(100 * (Number(x) || 0)).toFixed(1)}%`;
const money = (x, currency = "USD", compact = false) =>
  new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency,
    notation: compact ? "compact" : "standard",
    maximumFractionDigits: compact ? 2 : 0,
  }).format(Number(x) || 0);
const icons = () => window.lucide?.createIcons();
const views = {
  overview: "Overview",
  customers: "Customer segments",
  forecast: "Model validation",
  media: "Media lab",
  board: "Decision board",
  evidence: "Evidence & methods",
};
const colours = {
  "Pink Cab": "#e5008b",
  "Yellow Cab": "#d49b16",
  search: "#00b8d4",
  social: "#15966e",
  video: "#593196",
  violet: "#593196",
  plum: "#221331",
  cyan: "#00b8d4",
  ink: "#62596d",
  grid: "#ebe8ef",
};
let data,
  charts = [],
  storageKey,
  state,
  openedRevision;
let filters = {
  company: "All companies",
  city: "All cities",
  year: "All years",
};
let chartMetric = "revenue",
  citySort = "revenue",
  boardSearch = "",
  boardPriority = "All priorities";
let budget = 30000,
  shares = { search: 34, social: 33, video: 33 };
const main = $("#main");
const statuses = ["Backlog", "In progress", "Review", "Done"];
const seeds = [
  {
    id: "EKI-101",
    title: "Validate the CAB data before comparing companies",
    area: "Data quality",
    priority: "P1",
    owner: "Analyst",
    status: "Review",
    view: "evidence",
    hypothesis:
      "Each trip should survive validated joins to its transaction, customer and city records. Row loss would change the commercial comparison.",
    criteria: [
      "Cab transaction keys are unique and required fields are present",
      "Join cardinality and unmatched records are checked",
      "Contribution is labelled as revenue less recorded trip cost",
    ],
  },
  {
    id: "EKI-102",
    title: "Compare contribution and city mix before reallocating spend",
    area: "Commercial strategy",
    priority: "P1",
    owner: "Client sponsor",
    status: "Review",
    view: "overview",
    hypothesis:
      "The company with the greatest revenue need not offer the best incremental growth opportunity. Compare scale, contribution per trip and local mix before recommending a test.",
    criteria: [
      "Review revenue and contribution for both companies",
      "Compare city-level contribution per trip",
      "Record the additional media-spend evidence needed for a budget decision",
    ],
  },
  {
    id: "EKI-103",
    title: "Design a repeat-customer experiment",
    area: "Customer analytics",
    priority: "P2",
    owner: "Analyst",
    status: "In progress",
    view: "customers",
    hypothesis:
      "Behavioural trip-frequency groups can frame a retention test. Observed repeat trips alone do not establish campaign lift or predict lifetime value.",
    criteria: [
      "Check the full observation window and segment definitions",
      "Exclude demographic attributes from targeting decisions",
      "Specify a randomised holdout, outcome and stopping rule",
    ],
  },
  {
    id: "EKI-104",
    title: "Challenge the forecasting model with a seasonal baseline",
    area: "Model validation",
    priority: "P1",
    owner: "Reviewer",
    status: "Review",
    view: "forecast",
    hypothesis:
      "A more complex model should earn its place by performing well on later, unseen periods. Report the baseline alongside the model even if the baseline wins.",
    criteria: [
      "Confirm the chronological training and test periods",
      "Inspect MAE, RMSE and WAPE for both models",
      "Record the small-sample and historical-data limitations",
    ],
  },
  {
    id: "EKI-105",
    title: "Request media, pricing and external-driver data",
    area: "Measurement design",
    priority: "P1",
    owner: "Client sponsor",
    status: "Backlog",
    view: "media",
    hypothesis:
      "CAB contains transactions but no marketing exposures or spend. Real MMM requires aligned time series and a defensible identification strategy.",
    criteria: [
      "Request channel spend, campaign dates and conversions",
      "Define price, promotions, seasonality and external controls",
      "Agree calibration experiments and a data-access boundary",
    ],
  },
  {
    id: "EKI-106",
    title: "Review a budget scenario before planning a live test",
    area: "Media modelling",
    priority: "P2",
    owner: "Reviewer",
    status: "Backlog",
    view: "media",
    hypothesis:
      "The simulated response curves illustrate budget trade-offs. Their allocations are conditional model outputs, not recommendations to spend real money.",
    criteria: [
      "Confirm this is simulated GBP data, separate from CAB USD",
      "Check channel bounds and the steady-state assumption",
      "Document sensitivity and a human approval before any real test",
    ],
  },
  {
    id: "EKI-107",
    title: "Prepare a concise client decision brief",
    area: "Consulting",
    priority: "P2",
    owner: "Analyst",
    status: "In progress",
    view: "overview",
    hypothesis:
      "A useful client brief connects evidence, uncertainty and a next action. It should be possible to trace each recommendation to the analysis.",
    criteria: [
      "Name the business question and source evidence",
      "Explain the limits in plain language",
      "Assign an owner and an acceptance criterion to the next action",
    ],
  },
];
function readState() {
  try {
    const x = JSON.parse(localStorage.getItem(storageKey));
    if (
      x?.version === 1 &&
      Array.isArray(x.issues) &&
      Array.isArray(x.events) &&
      Number.isInteger(x.revision) &&
      x.issues.every(
        (i) =>
          typeof i.id === "string" &&
          typeof i.title === "string" &&
          statuses.includes(i.status) &&
          Array.isArray(i.criteria) &&
          Array.isArray(i.checks),
      )
    )
      return x;
  } catch (_) {
    /* A blocked storage API leaves a usable, unsaved session. */
  }
  return {
    version: 1,
    revision: 0,
    issues: seeds.map((i) => ({
      ...i,
      checks: i.criteria.map(() => false),
      reviewer: "",
      notes: "",
    })),
    events: [],
  };
}
function persist() {
  try {
    localStorage.setItem(storageKey, JSON.stringify(state));
    return true;
  } catch (_) {
    toast("Changes are held in this tab only: browser storage is unavailable.");
    return false;
  }
}
function toast(message) {
  const n = $("#toast");
  n.textContent = message;
  n.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => n.classList.remove("show"), 4500);
}
function destroyCharts() {
  charts.forEach((c) => c.destroy());
  charts = [];
}
function chart(id, type, labels, datasets, extra = {}) {
  const canvas = $(`#${id}`);
  if (!canvas) return;
  const fontFamily = getComputedStyle(canvas).fontFamily;
  charts.push(
    new Chart(canvas, {
      type,
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        color: colours.ink,
        font: { family: fontFamily, size: 12 },
        layout: { padding: { top: 8, right: 8 } },
        interaction: { mode: "index", intersect: false, axis: "x" },
        elements: {
          line: { borderCapStyle: "round", borderJoinStyle: "round" },
          point: {
            hitRadius: 12,
            hoverRadius: 5,
            hoverBorderWidth: 2,
            hoverBorderColor: "#ffffff",
          },
        },
        plugins: {
          legend: {
            display: true,
            position: "bottom",
            labels: {
              usePointStyle: true,
              boxWidth: 9,
              boxHeight: 9,
              padding: 20,
              color: colours.ink,
              font: { family: fontFamily, size: 12, weight: "500" },
            },
          },
          tooltip: {
            mode: "index",
            intersect: false,
            backgroundColor: colours.plum,
            titleColor: "#ffffff",
            bodyColor: "#f5f0fa",
            borderColor: "#594566",
            borderWidth: 1,
            cornerRadius: 8,
            padding: 12,
            titleMarginBottom: 8,
            bodySpacing: 6,
            caretPadding: 8,
            usePointStyle: true,
            boxWidth: 8,
            boxHeight: 8,
            titleFont: { family: fontFamily, size: 13, weight: "600" },
            bodyFont: { family: fontFamily, size: 12 },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              maxTicksLimit: 8,
              maxRotation: 0,
              padding: 8,
              font: { family: fontFamily, size: 11 },
              color: colours.ink,
            },
            border: { display: false },
          },
          y: {
            beginAtZero:
              type === "bar" ||
              id === "performance-chart" ||
              id === "response-chart",
            grid: { color: colours.grid, drawTicks: false },
            border: { display: false },
            ticks: {
              padding: 10,
              maxTicksLimit: 6,
              font: { family: fontFamily, size: 11 },
              color: colours.ink,
              callback: (v) =>
                new Intl.NumberFormat("en-GB", {
                  notation: "compact",
                  maximumFractionDigits: 1,
                }).format(v),
            },
          },
        },
        ...extra,
      },
    }),
  );
}
function pageHead(eyebrow, title, subtitle, extra = "") {
  const pageIcons = {
    overview: "chart-no-axes-combined",
    customers: "users-round",
    forecast: "chart-spline",
    media: "sliders-horizontal",
    board: "columns-3",
    evidence: "files",
  };
  return `<div class="page-heading"><div><p class="eyebrow"><i data-lucide="${pageIcons[currentView()]}"></i>${esc(eyebrow)}</p><h1>${esc(title)}</h1><p class="sub">${esc(subtitle)}</p></div>${extra}</div>`;
}
function badge(s) {
  return `<span class="badge ${s === "Review" ? "review" : s === "Done" ? "done" : s === "In progress" ? "progress" : s === "P1" ? "p1" : s === "P2" ? "p2" : ""}">${esc(s)}</span>`;
}
function field(label, id, options, value) {
  return `<label class="field" for="${id}">${label}<select id="${id}">${options.map((v) => `<option${v === value ? " selected" : ""}>${esc(v)}</option>`).join("")}</select></label>`;
}
function rows() {
  return data.cab.monthly.filter(
    (r) =>
      (filters.company === "All companies" || r.company === filters.company) &&
      (filters.city === "All cities" || r.city === filters.city) &&
      (filters.year === "All years" || r.month.startsWith(filters.year)),
  );
}
function sum(rs, key) {
  return rs.reduce((s, r) => s + (Number(r[key]) || 0), 0);
}
function metric(label, value, note, icon, emphasis = false) {
  return `<div class="metric${emphasis ? " emphasis" : ""}"><div class="metric-label"><i data-lucide="${icon}"></i>${esc(label)}</div><strong>${esc(value)}</strong><small>${esc(note)}</small></div>`;
}
function overview() {
  const rs = rows(),
    totals = {
      trips: sum(rs, "trips"),
      revenue: sum(rs, "revenue"),
      contribution: sum(rs, "contribution"),
    };
  const cities = [...new Set(data.cab.monthly.map((r) => r.city))].sort();
  const cityRows = cities
    .map((city) => {
      const a = rs.filter((r) => r.city === city),
        revenue = sum(a, "revenue"),
        contribution = sum(a, "contribution"),
        trips = sum(a, "trips");
      return {
        city,
        revenue,
        contribution,
        trips,
        per_trip: trips ? contribution / trips : 0,
      };
    })
    .filter((r) => r.trips)
    .sort((a, b) => b[citySort] - a[citySort]);
  const queue = state.issues.filter((i) => i.status === "Review").slice(0, 3);
  const topCity = cityRows[0];
  main.innerHTML =
    pageHead(
      "Cab growth / Commercial performance",
      "Performance overview",
      "From the transaction record to a decision worth testing.",
      `<span class="pill"><i data-lucide="calendar-days"></i> Historical case study</span>`,
    ) +
    `<div class="toolbar">${field("Company", "company-filter", ["All companies", ...data.cab.companies.map((c) => c.company)], filters.company)}${field("City", "city-filter", ["All cities", ...cities], filters.city)}${field("Period", "year-filter", ["All years", "2016", "2017", "2018"], filters.year)}<span class="scope">${num(totals.trips)} trips in selected scope · USD</span></div>
    <div class="metrics">${metric("Recorded trips", num(totals.trips), `${data.meta.date_start} to ${data.meta.date_end}`, "route")}${metric("Revenue", money(totals.revenue, "USD", true), "Recorded price charged · USD", "banknote")}${metric("Gross contribution", money(totals.contribution, "USD", true), "Revenue less recorded trip cost · USD", "chart-no-axes-column-increasing", true)}${metric("Contribution margin", pct(totals.contribution / totals.revenue), "Before overheads, tax and marketing cost", "percent")}</div>
    <div class="grid"><section class="section"><div class="section-head"><div><h2>Commercial performance over time</h2><p class="sub">Monthly totals · ${esc(filters.city)} · USD unless trips selected</p></div><div class="segment-control" aria-label="Chart metric">${["revenue", "contribution", "trips"].map((k) => `<button data-metric="${k}" class="${chartMetric === k ? "active" : ""}" aria-pressed="${chartMetric === k}">${k[0].toUpperCase() + k.slice(1)}</button>`).join("")}</div></div><div class="section-body"><div class="chart-box"><canvas id="performance-chart" role="img" aria-label="Monthly commercial performance by company"></canvas></div></div></section>
    <section class="section"><div class="section-head"><h2>Ready for review</h2><span class="badge review">${state.issues.filter((i) => i.status === "Review").length} tasks</span></div><div class="decision-list">${queue.length ? queue.map((i) => `<div class="decision-row"><span class="issue-type"><i data-lucide="check"></i></span><div><button data-issue="${esc(i.id)}">${esc(i.title)}</button><div class="issue-meta">${esc(i.id)} ${badge(i.priority)}</div></div></div>`).join("") : '<p class="empty">No tasks awaiting review.</p>'}</div><a class="section-link" href="#board">Open decision board <i data-lucide="arrow-right"></i></a></section></div>
    <div class="lower-grid"><section class="section"><div class="section-head"><div><h2>City opportunity comparison</h2><p class="sub">Descriptive evidence for a test plan; no measured campaign lift</p></div><button class="icon-button" id="export-cities" title="Download city comparison CSV" aria-label="Download city comparison CSV"><i data-lucide="download"></i></button></div><div class="table-scroll"><table><thead><tr><th>City</th>${[
      ["trips", "Trips"],
      ["revenue", "Revenue"],
      ["contribution", "Contribution"],
      ["per_trip", "Per trip"],
    ]
      .map(
        ([k, l]) =>
          `<th class="num"><button data-sort="${k}">${l}<i data-lucide="${citySort === k ? "arrow-down" : "arrow-up-down"}"></i></button></th>`,
      )
      .join("")}</tr></thead><tbody>${cityRows
      .slice(0, 7)
      .map(
        (r, i) =>
          `<tr><td class="cell-label"><span class="rank">${String(i + 1).padStart(2, "0")}</span>${esc(r.city)}</td><td class="num">${num(r.trips)}</td><td class="num">${money(r.revenue)}</td><td class="num">${money(r.contribution)}</td><td class="num">${money(r.per_trip)}</td></tr>`,
      )
      .join("")}</tbody></table></div></section>
    <section class="section"><div class="section-head"><h2>From insight to action</h2><i data-lucide="lightbulb"></i></div><div class="takeaway"><p class="eyebrow">Highest ${esc(citySort.replace("per_trip", "contribution per trip"))} in scope</p><p class="big">${esc(topCity?.city || "No observations")}</p><p>${topCity ? `${num(topCity.trips)} recorded trips and ${money(topCity.per_trip)} contribution per trip.` : "Change the selected scope."}</p><p>Check city mix and repeat behaviour. Request channel-spend data, then design a controlled acquisition or retention test.</p><a href="#board">Review the measurement plan →</a><p class="small-note">Observed differences are not causal marketing effects.</p></div></section></div>`;
  const months = [...new Set(rs.map((r) => r.month))].sort();
  const companies = data.cab.companies
    .map((c) => c.company)
    .filter(
      (c) => filters.company === "All companies" || c === filters.company,
    );
  chart(
    "performance-chart",
    "line",
    months,
    companies.map((company) => ({
      label: company,
      data: months.map((month) =>
        sum(
          rs.filter((r) => r.company === company && r.month === month),
          chartMetric,
        ),
      ),
      borderColor: colours[company],
      backgroundColor: `${colours[company]}12`,
      pointBackgroundColor: colours[company],
      borderWidth: 2.5,
      pointRadius: 0,
      pointHoverRadius: 5,
      fill: "origin",
      cubicInterpolationMode: "monotone",
    })),
  );
  $("#export-cities").onclick = () =>
    downloadCSV(cityRows, "city-comparison.csv");
}
function customers() {
  const chosen =
    filters.company === "All companies"
      ? data.cab.companies.map((c) => c.company)
      : [filters.company];
  const segments = data.cab.segments.filter((s) => chosen.includes(s.company));
  const labels = [...new Set(segments.map((s) => s.segment))];
  const totalGroups = sum(segments, "customers");
  const repeat = segments.filter((s) => s.segment !== "one-trip");
  const totalContribution = sum(segments, "contribution");
  const segmentNames = {
    "one-trip": "One trip",
    "2-5": "2–5 trips",
    "6+": "6+ trips",
  };
  const customerSummary = `<div class="metrics customer-metrics" aria-label="Customer summary">${metric("Customer-company groups", num(totalGroups), "Across the selected companies", "users-round")}${metric("Repeat groups", pct(sum(repeat, "customers") / totalGroups), "Two or more recorded trips", "repeat-2")}${metric("Repeat contribution", pct(sum(repeat, "contribution") / totalContribution), "Share of recorded gross contribution", "chart-no-axes-column-increasing", true)}${metric("Contribution / group", money(totalContribution / totalGroups), "Recorded revenue less trip cost · USD", "banknote")}</div>`;
  const segmentMix = `<div class="segment-mix" aria-label="Trip frequency composition">${labels
    .map((label, index) => {
      const group = segments.filter((s) => s.segment === label);
      const share = sum(group, "customers") / totalGroups;
      return `<div class="segment-profile segment-${index}"><div class="segment-profile-head"><span class="segment-dot"></span><h3>${esc(segmentNames[label] || label)}</h3><strong>${pct(share)}</strong></div><div class="mix-track" role="img" aria-label="${esc(segmentNames[label] || label)}: ${pct(share)} of customer-company groups"><span style="width:${share * 100}%"></span></div><div class="segment-profile-foot"><span>${num(sum(group, "customers"))} groups</span><span>${pct(sum(group, "contribution") / totalContribution)} of contribution</span></div></div>`;
    })
    .join("")}</div>`;
  main.innerHTML =
    pageHead(
      "Cab growth / Customer analytics",
      "Understand repeat behaviour",
      "Trip-frequency groups across the full recorded observation window.",
      '<a class="button" href="#board"><i data-lucide="flask-conical"></i> Experiment plan <i data-lucide="arrow-up-right"></i></a>',
    ) +
    `<div class="toolbar">${field("Company", "company-filter", ["All companies", ...data.cab.companies.map((c) => c.company)], filters.company)}<span class="scope">All cities · ${esc(data.meta.date_start)} to ${esc(data.meta.date_end)}</span></div><div class="callout"><i data-lucide="info"></i><p>These are descriptive customer-company groups. A customer using both companies appears in both. Trip counts do not measure campaign response, churn or lifetime value.</p></div><div class="two-cols"><section class="section"><div class="section-head"><h2>Customer groups by trip frequency</h2><span class="pill">No demographic targeting</span></div><div class="section-body"><div class="chart-box tall"><canvas id="segment-chart" role="img" aria-label="Customers in each trip frequency segment"></canvas></div></div></section><section class="section"><div class="section-head"><h2>Contribution per customer-company</h2></div><div class="section-body"><div class="chart-box tall"><canvas id="value-chart" role="img" aria-label="Recorded contribution per customer by trip frequency"></canvas></div></div></section></div><section class="section spaced"><div class="section-head"><h2>Segment evidence</h2><button class="button small" id="export-segments"><i data-lucide="download"></i> CSV</button></div><div class="table-scroll"><table><thead><tr><th>Company</th><th>Trips per customer</th><th class="num">Customer-company groups</th><th class="num">Trips</th><th class="num">Revenue (USD)</th><th class="num">Contribution (USD)</th></tr></thead><tbody>${segments.map((s) => `<tr><td>${esc(s.company)}</td><td>${esc(s.segment)}</td><td class="num">${num(s.customers)}</td><td class="num">${num(s.trips)}</td><td class="num">${money(s.revenue)}</td><td class="num">${money(s.contribution)}</td></tr>`).join("")}</tbody></table></div></section><div class="callout spaced"><i data-lucide="flask-conical"></i><p><strong>Next experiment:</strong> define an eligible cohort and randomise an offer against a holdout. Agree an incremental contribution outcome and a minimum observation window before launch. <a href="#board">EKI-103</a></p></div>`;
  chart(
    "segment-chart",
    "bar",
    labels,
    chosen.map((c) => ({
      label: c,
      data: labels.map((l) =>
        sum(
          segments.filter((s) => s.company === c && s.segment === l),
          "customers",
        ),
      ),
      backgroundColor: colours[c],
      hoverBackgroundColor: `${colours[c]}cc`,
      borderRadius: 5,
      categoryPercentage: 0.7,
      barPercentage: 0.85,
      maxBarThickness: 42,
    })),
  );
  chart(
    "value-chart",
    "bar",
    labels,
    chosen.map((c) => ({
      label: c,
      data: labels.map((l) => {
        const s = segments.find((s) => s.company === c && s.segment === l);
        return s?.customers ? s.contribution / s.customers : 0;
      }),
      backgroundColor: colours[c],
      hoverBackgroundColor: `${colours[c]}cc`,
      borderRadius: 5,
      categoryPercentage: 0.7,
      barPercentage: 0.85,
      maxBarThickness: 42,
    })),
  );
  $("#export-segments").onclick = () =>
    downloadCSV(segments, "customer-segments.csv");
  $(".toolbar").insertAdjacentHTML("afterend", customerSummary + segmentMix);
  const note = $(".callout");
  note.classList.add("customer-definition");
  $(".segment-mix").after(note);
  $$("tbody tr", main).forEach((row, index) => {
    const company = segments[index].company;
    row.cells[0].innerHTML = `<span class="company-label ${company === "Yellow Cab" ? "yellow" : ""}"><i aria-hidden="true"></i>${esc(company)}</span>`;
    row.cells[1].textContent =
      segmentNames[segments[index].segment] || segments[index].segment;
    if (index > 0 && segments[index - 1].company !== company)
      row.classList.add("company-start");
  });
}
function forecast() {
  const company =
    filters.company === "All companies"
      ? data.cab.companies[0].company
      : filters.company;
  const models = data.cab.forecast.filter((m) => m.company === company),
    points = models[0]?.points || [];
  main.innerHTML =
    pageHead(
      "Cab growth / Statistical modelling",
      "Let the baseline challenge the model",
      "Chronological holdout validation on later observations, with no random time-series split.",
    ) +
    `<div class="toolbar">${field(
      "Company",
      "forecast-company",
      data.cab.companies.map((c) => c.company),
      company,
    )}<span class="scope">All cities · Historical monthly revenue · USD</span></div><div class="two-cols"><section class="section"><div class="section-head"><div><h2>Holdout revenue: predicted against observed</h2><p class="sub">${esc(models[0]?.test_start)} to ${esc(models[0]?.test_end)}</p></div></div><div class="section-body"><div class="chart-box tall"><canvas id="forecast-chart" role="img" aria-label="Unseen-period revenue forecasts against observed revenue"></canvas></div></div></section><section class="section"><div class="section-head"><h2>Out-of-sample model comparison</h2></div><div class="table-scroll"><table class="model-table"><thead><tr><th>Model</th><th class="num">MAE (USD)</th><th class="num">RMSE (USD)</th><th class="num">WAPE</th></tr></thead><tbody>${models.map((m) => `<tr><td><strong>${esc(m.model)}</strong></td><td class="num">${money(m.mae)}</td><td class="num">${money(m.rmse)}</td><td class="num">${pct(m.wape)}</td></tr>`).join("")}</tbody></table></div><div class="section-body prose"><p><strong>Training ends:</strong> ${esc(models[0]?.train_end)}. Model parameters and preprocessing are fitted using training observations only.</p><p>MAE is average absolute error; RMSE gives more weight to large errors. WAPE divides absolute error by observed revenue. Lower is better for each measure.</p><p>Only three years of monthly observations are available. These results do not validate an investment valuation or a forecast of today's cab market.</p><a href="#evidence">Read the model specification →</a></div></section></div><div class="callout spaced"><i data-lucide="git-compare-arrows"></i><p><strong>Decision gate:</strong> retain the seasonal comparator in the client discussion. Model complexity is justified by useful validation results, not by the number of algorithms. Review assumptions and failure cases in <a href="#board">EKI-104</a>.</p></div>`;
  chart(
    "forecast-chart",
    "line",
    points.map((p) => p.month),
    [
      {
        label: "Observed revenue",
        data: points.map((p) => p.actual),
        borderColor: colours.plum,
        backgroundColor: colours.plum,
        borderWidth: 3,
        pointRadius: 4,
        pointBorderColor: "#ffffff",
        pointBorderWidth: 2,
      },
      ...models.map((m, i) => ({
        label: m.model,
        data: m.points.map((p) => p.predicted),
        borderColor: i ? colours.cyan : colours.violet,
        backgroundColor: i ? colours.cyan : colours.violet,
        borderDash: i ? [2, 4] : [6, 4],
        borderWidth: 2.5,
        pointRadius: 3.5,
        pointStyle: i ? "triangle" : "rectRot",
        pointBorderColor: "#ffffff",
        pointBorderWidth: 1.5,
      })),
    ],
  );
}
function channelResponse(c, spend) {
  const x = spend * c.steady_state_multiplier;
  return (c.coefficient * x) / (c.half_saturation + x);
}
function currentResponse() {
  return data.media.channels.reduce(
    (s, c) => s + channelResponse(c, (budget * shares[c.id]) / 100),
    0,
  );
}
function media() {
  const m = data.media;
  main.innerHTML =
    pageHead(
      "Media lab / Learning experiment",
      "Explore a marketing budget decision",
      "Adstock, diminishing returns and a constrained allocation in an educational model.",
      '<span class="pill sim"><i data-lucide="flask-conical"></i> Simulated data</span>',
    ) +
    `<div class="callout"><i data-lucide="info"></i><p><strong>Entirely simulated media data, in GBP.</strong> This is separate from the observed CAB case study. Estimated response and allocation depend on the simulated model; they are not measured campaign lift or real spending advice.</p></div><div class="grid"><section class="section"><div class="sim-banner">SIMULATION · Seed ${esc(m.seed)} · Steady weekly spend after carryover settles</div><div class="section-head"><h2>Budget & allocation</h2><button class="button small" id="optimise"><i data-lucide="sparkles"></i> Model allocation</button></div><div class="section-body"><div class="range-row"><div><label for="budget">Weekly media budget</label><div id="budget-value" class="media-budget">${money(budget, "GBP")}</div><input id="budget" type="range" min="10000" max="100000" step="5000" value="${budget}"></div><button class="icon-button" id="reset-allocation" title="Reset to equal allocation" aria-label="Reset to equal allocation"><i data-lucide="rotate-ccw"></i></button></div>${m.channels.map((c) => `<div class="allocation-row"><div><label for="share-${c.id}">${esc(c.name)}<span id="spend-${c.id}"></span></label><input id="share-${c.id}" data-share="${c.id}" type="range" min="10" max="60" step="1" value="${shares[c.id]}"></div><output id="value-${c.id}" for="share-${c.id}">${shares[c.id]}%</output></div>`).join("")}<p class="constraint">Each channel: 10–60% of the budget. Total allocation: 100%. The model assumes unchanged response curves, prices and external conditions.</p><div class="result-grid"><div><small>Modelled incremental revenue / week</small><strong id="response-value"></strong></div><div><small>Equal-split model comparison / week</small><strong id="balanced-value"></strong></div><div><small>Difference from equal split</small><strong id="uplift-value" class="positive"></strong></div></div></div></section><section class="section"><div class="section-head"><div><h2>Diminishing returns</h2><p class="sub">Modelled steady-state response · GBP per week</p></div></div><div class="section-body"><div class="chart-box tall"><canvas id="response-chart" role="img" aria-label="Simulated channel response curves with diminishing returns"></canvas></div><p class="small-note">Curves are conditional model estimates. A live allocation would also need uncertainty, experiments and business constraints.</p></div></section></div><section class="section spaced"><div class="section-head"><div><h2>Simulated revenue and holdout predictions</h2><p class="sub">Final ${m.metrics.holdout_weeks} weeks held out · seed ${esc(m.seed)}</p></div><span class="badge">Educational MMM prototype</span></div><div class="section-body"><div class="chart-box"><canvas id="media-fit-chart" role="img" aria-label="Simulated revenue and model predictions over time"></canvas></div></div><div class="summary-strip"><div><small>Holdout model MAE</small><strong>${money(m.metrics.model_mae, "GBP")}</strong></div><div><small>Holdout baseline MAE</small><strong>${money(m.metrics.baseline_mae, "GBP")}</strong></div><div><small>Holdout model RMSE</small><strong>${money(m.metrics.model_rmse, "GBP")}</strong></div></div></section>`;
  const xs = Array.from({ length: 21 }, (_, i) => i * 5000);
  chart(
    "response-chart",
    "line",
    xs.map((x) => money(x, "GBP", true)),
    m.channels.map((c) => ({
      label: c.name,
      data: xs.map((x) => channelResponse(c, x)),
      borderColor: colours[c.id],
      backgroundColor: colours[c.id],
      pointRadius: 0,
      borderWidth: 2.5,
      cubicInterpolationMode: "monotone",
    })),
  );
  chart(
    "media-fit-chart",
    "line",
    m.weekly.map((r) => r.week),
    [
      {
        label: "Simulated revenue",
        data: m.weekly.map((r) => r.revenue),
        borderColor: "#778692",
        backgroundColor: "#778692",
        pointRadius: 0,
        borderWidth: 1.8,
      },
      {
        label: "Model prediction (holdout)",
        data: m.weekly.map((r) => (r.split === "test" ? r.predicted : null)),
        borderColor: colours.cyan,
        backgroundColor: colours.cyan,
        pointRadius: 0,
        borderWidth: 3,
      },
    ],
  );
  updateScenario();
  const modelNote = document.createElement("p");
  modelNote.className = "small-note";
  modelNote.textContent =
    "Known adstock and saturation settings are supplied to the model. This favourable simulation does not test identification of unknown real-world marketing effects.";
  $(".summary-strip").after(modelNote);
  $("#budget").oninput = (e) => {
    budget = +e.target.value;
    updateScenario();
  };
  $$("[data-share]").forEach(
    (input) =>
      (input.oninput = () => {
        const key = input.dataset.share,
          old = shares[key],
          v = +input.value,
          other = Object.keys(shares).filter((k) => k !== key);
        let remainder = 100 - v;
        let first = Math.round((remainder * shares[other[0]]) / (100 - old));
        first = Math.max(10, Math.min(60, first));
        let second = remainder - first;
        if (second < 10) {
          first -= 10 - second;
          second = 10;
        }
        if (second > 60) {
          first += second - 60;
          second = 60;
        }
        shares = { ...shares, [key]: v, [other[0]]: first, [other[1]]: second };
        updateScenario();
      }),
  );
  $("#optimise").onclick = () => {
    const p = m.plans.find((p) => +p.budget === budget);
    if (!p) {
      toast("No validated model allocation exists for this budget.");
      return;
    }
    const vals = Object.values(p.shares),
      scale = Math.max(...vals) <= 1 ? 100 : 1;
    shares = {
      search: Math.round(p.shares.search * scale),
      social: Math.round(p.shares.social * scale),
      video: 0,
    };
    shares.video = 100 - shares.search - shares.social;
    updateScenario();
    toast(
      "Applied the simulated model allocation. Human review is still required for a real decision.",
    );
  };
  $("#reset-allocation").onclick = () => {
    shares = { search: 34, social: 33, video: 33 };
    updateScenario();
  };
}
function updateScenario() {
  $("#budget-value").textContent = money(budget, "GBP");
  data.media.channels.forEach((c) => {
    $(`#share-${c.id}`).value = shares[c.id];
    $(`#value-${c.id}`).textContent = `${shares[c.id]}%`;
    $(`#spend-${c.id}`).textContent = money(
      (budget * shares[c.id]) / 100,
      "GBP",
    );
  });
  const response = currentResponse(),
    balanced = data.media.channels.reduce(
      (s, c) => s + channelResponse(c, budget / 3),
      0,
    );
  $("#response-value").textContent = money(response, "GBP");
  $("#balanced-value").textContent = money(balanced, "GBP");
  $("#uplift-value").textContent =
    `${response >= balanced ? "+" : ""}${money(response - balanced, "GBP")}`;
  if (!$("#extrapolation-note")) {
    const p = document.createElement("p");
    p.id = "extrapolation-note";
    p.className = "small-note";
    $(".constraint").after(p);
  }
  const outside = data.media.channels.filter((c) => {
    const x = (budget * shares[c.id]) / 100;
    return x < c.train_spend_min || x > c.train_spend_max;
  });
  $("#extrapolation-note").textContent = outside.length
    ? `Extrapolation: ${outside.map((c) => c.name).join(", ")} spend is outside its observed training range. Treat this scenario with extra caution.`
    : "All channel spend values fall within their simulated training ranges.";
  $("#extrapolation-note").classList.toggle("error", outside.length > 0);
}
function issueCard(i) {
  return `<button class="issue" data-issue="${esc(i.id)}"><div class="issue-heading">${esc(i.title)}</div><span class="issue-tag">${esc(i.area)}</span><div class="issue-check-progress"><i data-lucide="list-checks"></i>${i.checks.filter(Boolean).length}/${i.criteria.length} acceptance checks</div><div class="issue-footer"><span class="issue-type"><i data-lucide="check"></i></span>${esc(i.id)} ${badge(i.priority)}<span class="issue-owner" title="${esc(i.owner)}">${esc(
    i.owner
      .split(" ")
      .map((s) => s[0])
      .join(""),
  )}</span></div></button>`;
}
function board() {
  main.innerHTML =
    pageHead(
      "Delivery / Sprint 01",
      "Decision board",
      "Evidence, acceptance criteria and review decisions for the Cab growth project.",
      '<button class="button primary" id="new-task"><i data-lucide="plus"></i> New task</button>',
    ) +
    `<div class="board-toolbar"><label class="search"><i data-lucide="search"></i><input id="board-search" placeholder="Search tasks" aria-label="Search tasks" value="${esc(boardSearch)}"></label><select id="board-priority" aria-label="Filter by priority">${["All priorities", "P1", "P2", "P3"].map((p) => `<option${boardPriority === p ? " selected" : ""}>${p}</option>`).join("")}</select><button class="button" id="export-board"><i data-lucide="download"></i> Jira CSV</button></div><div class="sprint-line"><i data-lucide="iteration-cw"></i><strong>Sprint 01</strong> Evidence & baseline <span>·</span><span id="sprint-progress"></span></div><div class="board" id="board-columns"></div><p class="small-note">Demo decisions are stored in this browser. Reviewer names are self-entered labels, without authentication. Source calculations remain unchanged.</p>`;
  boardColumns();
  $("#board-search").oninput = (e) => {
    boardSearch = e.target.value;
    boardColumns();
    icons();
  };
  $("#board-priority").onchange = (e) => {
    boardPriority = e.target.value;
    boardColumns();
    icons();
  };
  $("#new-task").onclick = () => openIssue(null);
  $("#export-board").onclick = exportBoard;
}
function boardColumns() {
  const matches = state.issues.filter(
    (i) =>
      (boardPriority === "All priorities" || i.priority === boardPriority) &&
      `${i.id} ${i.title} ${i.area} ${i.owner}`
        .toLowerCase()
        .includes(boardSearch.toLowerCase()),
  );
  $("#board-columns").innerHTML = statuses
    .map((status) => {
      const issues = matches.filter((i) => i.status === status);
      return `<section class="column" data-status="${esc(status)}" aria-label="${status}"><div class="column-title"><i class="column-dot"></i>${status}<span>${issues.length}</span></div>${issues.map(issueCard).join("") || '<div class="empty"><i data-lucide="circle-check"></i><span>No tasks</span></div>'}</section>`;
    })
    .join("");
  $("#sprint-progress").textContent =
    `${state.issues.filter((i) => i.status === "Done").length} of ${state.issues.length} tasks done`;
}
function evidence() {
  const meta = data.meta,
    audits = Array.isArray(meta.join_audit)
      ? meta.join_audit.map((a, i) => [
          a.stage || a.join || `Check ${i + 1}`,
          typeof a === "object" ? JSON.stringify(a) : String(a),
        ])
      : Object.entries(meta.join_audit || {});
  const sources = [
    [
      "CAB_EDA / Cab_2.ipynb",
      "Original exploratory analysis by Lucy Nowacki",
      meta.source_notebook_url ||
        "https://github.com/LucyNowacki/CAB_EDA/blob/main/Cab_2.ipynb",
      "notebook",
    ],
    [
      "DataGlacier / DataSets",
      "Pinned public educational case-study source",
      meta.cab_source_url ||
        `https://github.com/DataGlacier/DataSets/tree/${meta.cab_commit}`,
      "database",
    ],
    [
      "Clearcost",
      "Evidence-linked findings and human review workflow",
      "https://lucynowacki.github.io/clearcost/",
      "receipt-text",
    ],
    [
      "Published aggregate data",
      "Reproducible dashboard export; no raw customer rows",
      "data/dashboard.json",
      "file-json",
    ],
    [
      "Ekimetrics / Marketing effectiveness",
      "Company research informing the independent project",
      "https://www.ekimetrics.com/solutions/marketing-effectiveness",
      "external-link",
    ],
  ];
  main.innerHTML =
    pageHead(
      "Project / Evidence & methods",
      "Make the recommendation traceable",
      "The source data, modelling choices and limits behind each decision.",
    ) +
    `<div class="evidence-grid"><section class="section"><div class="section-head"><h2>What this project demonstrates</h2></div><div class="section-body prose"><p>A commercial question from <strong>CAB_EDA</strong> meets the evidence-and-review pattern developed in <strong>Clearcost</strong>: validate the record, compare alternatives, challenge the model and assign a testable next action.</p><h3>Observed CAB analysis</h3><p>${num(meta.row_count)} public case-study trips across ${num(meta.city_count)} cities. Gross contribution means price charged minus recorded trip cost. It excludes overheads, tax, capital costs and marketing spend. Historical USD amounts are not converted into GBP.</p><p>Joins check cardinality and unmatched keys. Missing marketing-spend data is not invented for CAB. Monthly revenue is evaluated with a chronological holdout and a seasonal comparator. Customer segments use observed trip frequency across the recorded window.</p><h3>A separate simulated media experiment</h3><p>All media-spend, revenue and response estimates in the media lab are simulated in GBP. Adstock describes carryover; saturation describes diminishing returns. Non-negative media coefficients, seasonal controls and a held-out time period support a learning exercise. They do not prove real causal effects.</p><ul>${(data.media.methodology || []).map((t) => `<li>${esc(t)}</li>`).join("")}</ul><h3>Decision workflow</h3><p>Tasks move through Backlog, In progress, Review and Done. Finalisation requires checked acceptance criteria, a reviewer label and a written reason. The review history is browser-local and editable by the browser owner; it is not an authenticated enterprise audit system.</p><h3>Responsible AI and reproducibility</h3><p>AI assistants supported implementation and review. Published metrics are calculated by deterministic Python code; no LLM produces or modifies the financial calculations. No API key, live model call or external analytics tracker is required. Client recommendations still require a person's judgement and suitable source evidence.</p><p><strong>Build provenance:</strong> <code>${esc(meta.cab_commit)}</code>. See the repository methodology and test report for source hashes, reproducible commands and limitations.</p></div></section><div><section class="section"><div class="section-head"><h2>Source register</h2></div>${sources.map(([title, desc, url, icon]) => `<div class="source-row"><i data-lucide="${icon}"></i><div><a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(title)} ↗</a><small>${esc(desc)}</small></div></div>`).join("")}</section><section class="section spaced"><div class="section-head"><h2>Browser review history</h2><button class="icon-button" id="export-events" title="Export review history" aria-label="Export review history"><i data-lucide="download"></i></button></div><div class="section-body audit-list">${
      state.events.length
        ? state.events
            .slice()
            .reverse()
            .map(
              (e) =>
                `<div class="audit-item"><strong>${esc(e.id)} · ${esc(e.to)}</strong><br>${esc(e.reviewer)}: ${esc(e.notes)}<br><small>${esc(e.at)}</small></div>`,
            )
            .join("")
        : '<p class="sub">No review decisions recorded in this browser.</p>'
    }</div></section><section class="section spaced"><div class="section-head"><h2>Data checks</h2></div><div class="section-body prose">${audits.map(([k, v]) => `<p><strong>${esc(k)}</strong><br><code>${esc(typeof v === "object" ? JSON.stringify(v) : v)}</code></p>`).join("")}</div></section></div></div>`;
  $("#export-events").onclick = () =>
    download(
      JSON.stringify(state.events, null, 2),
      "review-history.json",
      "application/json",
    );
}
function openIssue(id) {
  state = readState();
  openedRevision = state.revision;
  const existing = state.issues.find((i) => i.id === id),
    next =
      Math.max(100, ...state.issues.map((i) => +i.id.split("-")[1] || 0)) + 1;
  const i = existing || {
    id: `EKI-${next}`,
    title: "",
    area: "Measurement design",
    priority: "P2",
    owner: "Analyst",
    status: "Backlog",
    view: "overview",
    hypothesis: "",
    criteria: [
      "Source evidence reviewed",
      "Assumptions and next action documented",
    ],
    checks: [false, false],
    reviewer: "",
    notes: "",
  };
  const dialog = $("#issue-dialog");
  dialog.innerHTML = `<form id="issue-form"><div class="dialog-head"><div><p class="eyebrow">${esc(i.id)} · ${esc(i.area)}</p><h2 id="issue-title">${existing ? esc(i.title) : "Create a decision task"}</h2></div><button type="button" class="icon-button" id="close-dialog" aria-label="Close task" title="Close"><i data-lucide="x"></i></button></div><div class="dialog-body">${!existing ? '<label class="field">Task title<input id="task-title" required maxlength="140"></label>' : ""}<div class="dialog-grid">${field("Status", "task-status", statuses, i.status)}${field("Priority", "task-priority", ["P1", "P2", "P3"], i.priority)}${field("Owner", "task-owner", ["Analyst", "Reviewer", "Client sponsor"], i.owner)}${field("Evidence view", "task-evidence", Object.keys(views), i.view)}</div><h3>Decision rationale</h3>${existing ? `<p>${esc(i.hypothesis)}</p>` : '<label class="field">Business question<textarea id="task-hypothesis" required maxlength="1500"></textarea></label>'}<a href="#${esc(i.view)}" id="view-evidence" class="button small"><i data-lucide="external-link"></i> Open supporting evidence</a><h3>Acceptance criteria</h3>${i.criteria.map((c, k) => `<label class="check"><input type="checkbox" data-check="${k}"${i.checks[k] ? " checked" : ""}>${esc(c)}</label>`).join("")}<h3>Review decision</h3><div class="dialog-grid"><label class="field">Reviewer label<input id="task-reviewer" value="${esc(i.reviewer)}" maxlength="100" placeholder="Name or reviewer label" required></label><div class="field"><span>Storage</span><span class="pill">This browser only</span></div></div><label class="field spaced">Reason / review notes<textarea id="task-notes" maxlength="3000" required placeholder="Evidence considered, limitations and next action">${esc(i.notes)}</textarea></label><p id="review-error" class="error" role="alert"></p><div class="dialog-actions"><button type="button" class="button" id="cancel-dialog">Cancel</button><button type="submit" class="button primary"><i data-lucide="save"></i> Save decision</button></div></div></form>`;
  icons();
  dialog.showModal();
  const close = () => dialog.close();
  $("#close-dialog").onclick = close;
  $("#cancel-dialog").onclick = close;
  $("#view-evidence").onclick = close;
  $("#issue-form").onsubmit = (e) => {
    e.preventDefault();
    const target = $("#task-status").value,
      checks = $$("[data-check]", dialog).map((c) => c.checked),
      reviewer = $("#task-reviewer").value.trim(),
      notes = $("#task-notes").value.trim();
    if (!reviewer || !notes) {
      $("#review-error").textContent =
        "Add a reviewer label and a reason for this decision.";
      return;
    }
    if (target === "Done" && checks.some((c) => !c)) {
      $("#review-error").textContent =
        "Cannot finalise: every acceptance criterion must be checked before moving this task to Done.";
      return;
    }
    const fresh = readState();
    if (fresh.revision !== openedRevision) {
      $("#review-error").textContent =
        "This board changed in another tab. Close and reopen the task before saving.";
      return;
    }
    const updated = {
      ...i,
      title: existing ? i.title : $("#task-title").value.trim(),
      hypothesis: existing ? i.hypothesis : $("#task-hypothesis").value.trim(),
      status: target,
      priority: $("#task-priority").value,
      owner: $("#task-owner").value,
      view: $("#task-evidence").value,
      checks,
      reviewer,
      notes,
    };
    if (!updated.title || !updated.hypothesis) {
      $("#review-error").textContent =
        "Enter the task title and business question.";
      return;
    }
    state = fresh;
    state.issues = existing
      ? state.issues.map((x) => (x.id === i.id ? updated : x))
      : [...state.issues, updated];
    state.revision++;
    state.events.push({
      id: i.id,
      from: existing?.status || "New",
      to: target,
      reviewer,
      notes,
      at: new Date().toISOString(),
      source_commit: data.meta.cab_commit,
      checks,
    });
    const saved = persist();
    close();
    render();
    if (saved) toast(`${i.id} saved with its review reason.`);
  };
}
function download(content, name, type) {
  const blob = new Blob([content], { type }),
    url = URL.createObjectURL(blob),
    a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function downloadCSV(rs, name) {
  if (!rs.length) {
    toast("No rows in this scope.");
    return;
  }
  const keys = Object.keys(rs[0]),
    cell = (v) => {
      let s = String(v ?? "");
      if (typeof v === "string" && /^[\s]*[=+@-]/.test(s)) s = "'" + s;
      return '"' + s.replace(/"/g, '""') + '"';
    };
  download(
    [
      keys.map(cell).join(","),
      ...rs.map((r) => keys.map((k) => cell(r[k])).join(",")),
    ].join("\r\n"),
    name,
    "text/csv;charset=utf-8",
  );
}
function exportBoard() {
  downloadCSV(
    state.issues.map((i) => ({
      "Issue ID": i.id,
      "Issue Type": "Task",
      Summary: i.title,
      Description: `${i.hypothesis}\nAcceptance criteria:\n${i.criteria.join("\n")}\nReviewer: ${i.reviewer}\nReview notes: ${i.notes}`,
      Status: i.status,
      Priority: i.priority,
      Assignee: i.owner,
    })),
    "decision-lab-jira-import.csv",
  );
}
function exportBrief() {
  const rs = rows(),
    response = data.media ? currentResponse() : 0;
  const text = `# Cab growth | Decision brief\n\nIndependent portfolio project by Lucy Nowacki.\n\n## Business question\nWhere should the team investigate customer growth and contribution opportunities, and what additional evidence is needed before changing marketing spend?\n\n## Selected observed scope\n${filters.company}; ${filters.city}; ${filters.year}. Historical CAB case-study data in USD.\n- Trips: ${num(sum(rs, "trips"))}\n- Revenue: ${money(sum(rs, "revenue"))}\n- Gross contribution: ${money(sum(rs, "contribution"))} (price less recorded trip cost; not net profit)\n\n## Interpretation\nCompare scale, city mix and repeat-trip behaviour. Descriptive differences do not establish incremental marketing return. Request channel spend, pricing/promotions and external controls, then design an experiment.\n\n## Model evidence\n${data.cab.forecast.map((m) => `- ${m.company}, ${m.model}: holdout MAE ${money(m.mae)}, WAPE ${pct(m.wape)}; ${m.test_start} to ${m.test_end}.`).join("\n")}\n\n## Separate simulated media scenario\nBudget: ${money(budget, "GBP")} per week. Search ${shares.search}%, social ${shares.social}%, video ${shares.video}%. Modelled incremental revenue: ${money(response, "GBP")} per week, after carryover settles. These are synthetic model outputs, not campaign results or advice to spend real money.\n\n## Decision tasks\n${state.issues.map((i) => `- ${i.id} [${i.status}] ${i.title} | Owner: ${i.owner}\n  Rationale: ${i.hypothesis}\n  Acceptance: ${i.criteria.join("; ")}\n  Review: ${i.reviewer || "Not reviewed"}. ${i.notes}`).join("\n")}\n\n## Provenance and limits\nCAB source commit: ${data.meta.cab_commit}. Original analysis: ${data.meta.source_notebook_url}. Aggregate export: data/dashboard.json. No raw individual customer rows are published. Review labels are self-entered; review state is stored only in the current browser. No realised savings, real campaign uplift or Ekimetrics affiliation is claimed.\n`;
  download(text, "cab-growth-decision-brief.md", "text/markdown;charset=utf-8");
  toast("Exported the brief with source references and review states.");
}
function currentView() {
  const v = location.hash.slice(1);
  return views[v] ? v : "overview";
}
function render() {
  if (!data) return;
  destroyCharts();
  const v = currentView();
  main.dataset.view = v;
  $("#crumb").textContent = views[v];
  $$("#nav a").forEach((a) => {
    a.classList.toggle("active", a.dataset.view === v);
    a.setAttribute("aria-current", a.dataset.view === v ? "page" : "false");
  });
  $("#board-count").textContent = state.issues.filter(
    (i) => i.status !== "Done",
  ).length;
  ({ overview, customers, forecast, media, board, evidence })[v]();
  icons();
}
document.addEventListener("click", (e) => {
  const issue = e.target.closest("[data-issue]");
  if (issue && data) openIssue(issue.dataset.issue);
  const metricButton = e.target.closest("[data-metric]");
  if (metricButton) {
    chartMetric = metricButton.dataset.metric;
    render();
  }
  const sort = e.target.closest("[data-sort]");
  if (sort) {
    citySort = sort.dataset.sort;
    render();
  }
});
document.addEventListener("change", (e) => {
  const key = {
    "company-filter": "company",
    "city-filter": "city",
    "year-filter": "year",
    "forecast-company": "company",
  }[e.target.id];
  if (key) {
    filters[key] = e.target.value;
    render();
  }
});
window.addEventListener("hashchange", render);
window.addEventListener("storage", (e) => {
  if (e.key === storageKey) {
    state = readState();
    render();
  }
});
$("#export-brief").onclick = () => {
  if (data) exportBrief();
};
async function init() {
  icons();
  try {
    const response = await fetch("data/dashboard.json");
    if (!response.ok) throw Error(`Data response ${response.status}`);
    data = await response.json();
    if (
      !Array.isArray(data?.cab?.monthly) ||
      !data?.media?.synthetic ||
      !data.media.channels.every(
        (c) =>
          Number.isFinite(c.steady_state_multiplier) &&
          Math.abs(c.steady_state_multiplier - 1 / (1 - c.decay)) < 1e-9,
      )
    )
      throw Error(
        "Dashboard data contract is incomplete or has inconsistent adstock parameters.",
      );
    storageKey = `lucy-decision-lab-v1-${data.meta.cab_commit?.slice(0, 10)}`;
    state = readState();
    Chart.defaults.font.family = 'Inter,"Segoe UI",Arial,sans-serif';
    Chart.defaults.color = "#696575";
    render();
  } catch (error) {
    main.innerHTML = `<div class="callout"><i data-lucide="triangle-alert"></i><p><strong>Project evidence could not be loaded.</strong><br>${esc(error.message)}. Please reload the hosted demo, or serve the built project over HTTP.</p></div>`;
    icons();
  }
}
init();
