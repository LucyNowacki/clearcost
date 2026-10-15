/* Application claims stay tied to the published data, not hypothetical client results. */
"use strict";

function applicationQuestions() {
  const models = data.cab.forecast;
  const comparisons = data.cab.companies.map(({ company }) => {
    const ridge = models.find(
      (m) => m.company === company && m.model_name === "ridge",
    );
    const baseline = models.find(
      (m) => m.company === company && m.model_name === "seasonal_naive",
    );
    return `${company}: seasonal baseline ${(baseline.wape * 100).toFixed(2)}% WAPE versus Ridge ${(ridge.wape * 100).toFixed(2)}%`;
  });
  return [
    {
      id: "mmm",
      label: "Understand MMM",
      icon: "chart-spline",
      question:
        'In your own words, what do you understand by "Marketing Mix Modelling"?',
      point:
        "Separate underlying demand from marketing response, then compare decisions.",
      paragraphs: [
        "I think of Marketing Mix Modelling as a way of asking what is driving a business's results, and what might change if its marketing budget were allocated differently. It uses aggregated data over time to estimate the relationship between an outcome, such as sales, marketing activity and other relevant drivers. Seasonality, prices, promotions and external conditions matter: an increase in sales should not automatically be credited to advertising.",
        "Two ideas are especially important: advertising can have a carryover effect after the initial spend, and additional spending can produce diminishing returns. A model can use these relationships to compare budget scenarios. However, a good fit alone does not establish a causal effect; correlated channels, omitted factors and demand-driven spending can bias the estimates. Experiments, business knowledge and uncertainty checks are important.",
        "My project explores these mechanics in a separate simulated media lab. It demonstrates carryover, saturation and constrained allocation, but the response settings are supplied to the model. It is a learning exercise, not evidence of real campaign lift or a production MMM implementation.",
      ],
      links: [
        ["#media", "Explore the MMM experiment"],
        ["#board", "Review the measurement plan"],
      ],
      evidence: [
        "Simulated weekly data only; no marketing-spend data is invented for CAB.",
        "Trend, seasonal terms and media response are modelled; real price, promotion and competitor data are not available.",
      ],
      limitation:
        "Predictive validation is not causal identification. The prototype has no experimental calibration or parameter-uncertainty intervals.",
    },
    {
      id: "problem-solving",
      label: "Solve with data",
      icon: "git-compare-arrows",
      question:
        "Tell us about a time you used data to solve a problem. What tools did you use, what did you learn and what was the outcome?",
      point:
        "A simpler baseline challenged the model; the finding changed the recommendation.",
      paragraphs: [
        `In my CAB_EDA portfolio work, I wanted to compare two cab companies without mistaking revenue for profitability or an observed pattern for a marketing effect. I developed the analysis into Marketing Decision Lab, using Python and pandas to validate and join the transaction, customer and city tables. The checked joins retained all ${num(data.meta.row_count)} teaching-data trips.`,
        `I compared recorded revenue, contribution and repeat-trip behaviour, then used scikit-learn to test a Ridge trend-and-seasonality forecast against a seasonal baseline. Training used the first ${models[0].train_months} months, with the later ${models[0].holdout_months} months held out. The baseline had lower WAPE for both companies, so I kept that result visible rather than presenting complexity as an improvement.`,
        "The outcome was a tested, public dashboard connecting source checks, model comparisons and reviewable next actions. I learnt that useful analysis depends as much on definitions, validation and clear communication as on the algorithm. Because the CAB data has no channel spend, I kept the marketing experiment separate and simulated. AI assistants supported implementation; the metrics come from deterministic code. This is a portfolio result, not a claim of client revenue uplift.",
      ],
      links: [
        ["#forecast", "Inspect the holdout comparison"],
        ["#overview", "Explore the CAB analysis"],
        ["#board", "Inspect review tasks"],
      ],
      evidence: [
        `${num(data.meta.join_audit.retained_rows)} of ${num(data.meta.row_count)} trips retained after checked joins.`,
        ...comparisons,
      ],
      limitation:
        "One retrospective six-month holdout, not proof of future performance. Gross contribution excludes overheads and marketing cost.",
    },
    {
      id: "ekimetrics",
      label: "Why Ekimetrics",
      icon: "messages-square",
      question:
        "Why are you interested in this opportunity at Ekimetrics, specifically in MMM?",
      point:
        "Connect mathematical reasoning to a decision that someone can explain and act on.",
      paragraphs: [
        "What attracts me to Ekimetrics is the connection between rigorous analysis and a practical business decision. Its marketing-effectiveness work focuses on making investment trade-offs explicit, rather than stopping at a model output. MMM interests me for exactly that reason: it asks both what might be driving performance and what a team should test or change next.",
        "My background in mathematics, time-series analysis and Python gives me a foundation I want to develop in that setting. In this project, I have tried to make my reasoning inspectable: preserve the source records, challenge the model with a baseline, distinguish simulated effects from observed data and attach evidence to a review decision. That is the contribution I would bring: curiosity, careful analysis and a willingness to explain the limits of a result.",
        "Ekimetrics' emphasis on ownership, shared learning and purposeful solutions also appeals to me. I would like to learn from experienced colleagues how to work with real marketing data, validate causal assumptions and communicate uncertainty to clients. I see this internship as a chance to turn a strong quantitative foundation into useful marketing judgement, not simply to apply a more complicated model.",
      ],
      links: [
        ["#board", "See evidence-led decisions"],
        ["#media", "Explore the learning experiment"],
      ],
      evidence: [
        "Independent project positioning, informed by Ekimetrics' public marketing-effectiveness and careers pages.",
        "Next learning goals: real-world confounding, experiment calibration, uncertainty and client communication.",
      ],
      limitation:
        "This is Lucy's independent application demonstrator, not Ekimetrics software, client work or an endorsement.",
    },
  ];
}

function applicationOverview() {
  return `<section class="application-route" aria-labelledby="application-route-title">
    <div class="story-heading"><div><p class="eyebrow">Marketing effectiveness / Evidence trail</p><h2 id="application-route-title">From a business question to a defensible decision</h2></div><a href="#evidence/mmm">Application evidence <i data-lucide="arrow-up-right"></i></a></div>
    <div class="story-steps">${applicationQuestions()
      .map(
        (q, i) =>
          `<a href="#evidence/${q.id}"><span class="story-number">0${i + 1}</span><span><strong>${q.label}</strong><small>${q.point}</small></span><i data-lucide="arrow-up-right"></i></a>`,
      )
      .join("")}</div>
    <p class="story-boundary"><span>Historical CAB analysis · USD</span><span>Separate simulated MMM experiment · GBP</span><span>No measured campaign uplift</span></p>
  </section>`;
}

function applicationEvidence() {
  const selected = location.hash.split("/")[1] || "mmm";
  const questions = applicationQuestions();
  const active = questions.some((q) => q.id === selected) ? selected : "mmm";
  return `<section class="application-evidence" aria-labelledby="application-evidence-title">
    <div class="story-heading"><div><p class="eyebrow">Ekimetrics / Application evidence</p><h2 id="application-evidence-title">Three questions, supported by the work</h2><p class="sub">First-person drafts for Lucy's review. Nothing is submitted.</p></div><button class="icon-button" id="download-application" title="Download all three answer drafts" aria-label="Download all three answer drafts"><i data-lucide="download"></i></button></div>
    ${questions
      .map(
        (
          q,
          i,
        ) => `<details class="answer-detail" name="application-evidence" id="answer-${q.id}"${active === q.id ? " open" : ""}>
      <summary><span class="story-number">0${i + 1}</span><span>${esc(q.question)}</span><i data-lucide="chevron-down"></i></summary>
      <div class="answer-layout"><div class="answer-prose"><p class="eyebrow">Draft answer</p>${q.paragraphs.map((p) => `<p>${esc(p)}</p>`).join("")}<div class="answer-actions"><button class="icon-button" data-copy-answer="${q.id}" title="Copy this answer draft" aria-label="Copy ${esc(q.label)} answer"><i data-lucide="copy"></i></button><small>${num(q.paragraphs.join(" ").split(/\s+/).length)} words · Review in your own voice</small></div></div>
      <aside class="answer-proof" aria-label="Supporting evidence for ${esc(q.label)}"><h3>Evidence behind the answer</h3><ul>${q.evidence.map((p) => `<li>${esc(p)}</li>`).join("")}</ul><div class="proof-links">${q.links.map(([href, label]) => `<a href="${href}">${esc(label)} <i data-lucide="arrow-up-right"></i></a>`).join("")}</div><h3>Keep the claim bounded</h3><p>${esc(q.limitation)}</p>${q.id === "ekimetrics" ? '<p class="small-note">Company sources, checked 15 October 2026: <a href="https://www.ekimetrics.com/solutions/marketing-effectiveness" target="_blank" rel="noopener noreferrer">Marketing effectiveness</a> and <a href="https://www.ekimetrics.com/join-ekimetrics" target="_blank" rel="noopener noreferrer">Join Ekimetrics</a>.</p>' : ""}</aside></div>
    </details>`,
      )
      .join("")}
  </section>`;
}

function bindApplicationEvidence() {
  const questions = applicationQuestions();
  $("#download-application").onclick = () =>
    download(
      "Ekimetrics application answers | Drafts for Lucy's review\nNothing submitted.\n\n" +
        questions
          .map(
            (q, i) =>
              `${i + 1}. ${q.question}\n\n${q.paragraphs.join("\n\n")}\n\nEvidence: ${location.origin}${location.pathname}#evidence/${q.id}`,
          )
          .join("\n\n"),
      "lucy-ekimetrics-application-drafts.txt",
      "text/plain;charset=utf-8",
    );
  $$("[data-copy-answer]").forEach((button) => {
    button.onclick = async () => {
      const q = questions.find((item) => item.id === button.dataset.copyAnswer);
      try {
        await navigator.clipboard.writeText(q.paragraphs.join("\n\n"));
        toast("Draft copied. Review it in your own voice before submitting.");
      } catch {
        toast(
          "Clipboard unavailable. Use the download button for the answer drafts.",
        );
      }
    };
  });
}

function mmmIntroduction() {
  return `<section class="mmm-introduction" aria-labelledby="mmm-title">
    <div class="story-heading"><div><p class="eyebrow">Marketing Mix Modelling</p><h2 id="mmm-title">What drove sales, and what should the next pound do?</h2></div><a href="#evidence/mmm">Read my explanation <i data-lucide="arrow-up-right"></i></a></div>
    <p>MMM uses aggregate time-series data to estimate how marketing and other drivers relate to a business outcome. <strong>Adstock</strong> represents activity that can still matter after the initial spend; <strong>saturation</strong> means the next pound may produce less response than the previous one. These relationships support budget scenarios, but causal interpretation needs defensible assumptions and validation.</p>
    <div class="mmm-equation" aria-label="Revenue equals underlying demand plus media response plus unexplained variation"><div><i data-lucide="calendar-range"></i><strong>Underlying demand</strong><small>Trend, seasonality, relevant non-media drivers</small></div><span aria-hidden="true">+</span><div><i data-lucide="radio-tower"></i><strong>Media response</strong><small>Channel activity, carryover, saturation</small></div><span aria-hidden="true">+</span><div><i data-lucide="waves"></i><strong>Unexplained variation</strong><small>Noise and influences the model misses</small></div></div>
    <p class="small-note">This prototype fits trend, annual seasonal terms and three media coefficients. Pricing, promotions and competitor effects would need additional data and a causal rationale. Holdout accuracy alone does not prove incrementality. <a href="https://developers.google.com/meridian/docs/basics/meridian-introduction" target="_blank" rel="noopener noreferrer">MMM reference: Google Meridian</a> (not a dependency).</p>
  </section>`;
}

function carryoverMarkup() {
  return `<section class="section spaced" aria-labelledby="carryover-title"><div class="section-head"><div><h2 id="carryover-title">Why this week's advertising can matter next week</h2><p class="sub">Isolated adstock illustration · not a model refit or a sales estimate</p></div><span class="badge">MMM mechanics</span></div>
    <div class="carryover-layout"><div class="carryover-controls"><label class="field">Example channel<select id="carryover-channel">${data.media.channels.map((c) => `<option value="${esc(c.id)}">${esc(c.name)}</option>`).join("")}</select></label>
    <label for="carryover-decay">Weekly carryover <output id="carryover-decay-value" for="carryover-decay"></output></label><input type="range" id="carryover-decay" min="0" max="0.9" step="0.05" value="${data.media.channels[0].decay}">
    <p>One <strong>£10,000 pulse</strong> in week 1; no new spend afterwards. The adstock stock carries a chosen fraction into each following week.</p><p><code>a[t] = spend[t] + decay × a[t-1]</code></p>
    <div class="carryover-result"><small>Adstock remaining in week 4</small><output id="carryover-week-four"></output></div><p class="small-note">Adstock is a transformed spend input, not additional spending, revenue or ROI. Changing this illustration leaves the fitted budget model above unchanged.</p></div>
    <div class="section-body"><div class="chart-box tall"><canvas id="carryover-chart" role="img" aria-label="One-week advertising pulse and its declining adstock over twelve weeks"></canvas></div><p id="carryover-description" class="small-note" aria-live="polite"></p></div></div></section>`;
}

function bindCarryover() {
  const draw = () => {
    const decay = +$("#carryover-decay").value;
    const retained = Array.from(
      { length: 12 },
      (_, week) => 10000 * decay ** week,
    );
    $("#carryover-decay-value").textContent = pct(decay);
    $("#carryover-week-four").textContent = money(retained[3], "GBP");
    $("#carryover-description").textContent =
      `With ${pct(decay)} weekly carryover, the £10,000 week-1 pulse leaves ${money(retained[3], "GBP")} of adstock in week 4. New spend in weeks 2–12 is £0. These are illustrative transformed-input units, not sales.`;
    const existing = charts.find((c) => c.canvas.id === "carryover-chart");
    if (existing) {
      existing.data.datasets[1].data = retained;
      existing.update("none");
      return;
    }
    chart(
      "carryover-chart",
      "line",
      retained.map((_, i) => `Week ${i + 1}`),
      [
        {
          label: "New spend (GBP)",
          data: [10000, ...Array(11).fill(0)],
          borderColor: colours.plum,
          backgroundColor: colours.plum,
          borderDash: [5, 5],
          pointRadius: 3,
        },
        {
          label: "Adstock (transformed GBP input)",
          data: retained,
          borderColor: colours.cyan,
          backgroundColor: "#00b8d414",
          fill: "origin",
          pointRadius: 3,
          borderWidth: 3,
        },
      ],
      {
        scales: {
          y: {
            beginAtZero: true,
            title: { display: true, text: "GBP / transformed-input units" },
          },
        },
      },
    );
  };
  $("#carryover-decay").oninput = draw;
  $("#carryover-channel").onchange = () => {
    $("#carryover-decay").value = data.media.channels.find(
      (c) => c.id === $("#carryover-channel").value,
    ).decay;
    draw();
  };
  draw();
}
