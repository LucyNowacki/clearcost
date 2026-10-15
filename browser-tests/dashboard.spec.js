const { test, expect } = require("@playwright/test");
const fs = require("node:fs");
const path = require("node:path");
const dataset = JSON.parse(
  fs.readFileSync(path.join(__dirname, "../dist/data/dashboard.json"), "utf8"),
);

test("all analytical views render without script errors or external runtime requests", async ({
  page,
}) => {
  const errors = [],
    external = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("request", (r) => {
    if (
      !r.url().startsWith("http://127.0.0.1:8879") &&
      !r.url().startsWith("data:")
    )
      external.push(r.url());
  });
  for (const [view, title] of [
    ["overview", "Performance overview"],
    ["customers", "Understand repeat behaviour"],
    ["forecast", "Let the baseline challenge the model"],
    ["media", "Explore a marketing budget decision"],
    ["board", "Decision board"],
    ["evidence", "Make the recommendation traceable"],
  ]) {
    await page.goto("/#" + view);
    await expect(
      page.getByRole("heading", { name: title, exact: true }),
    ).toBeVisible();
    const canvas = page.locator("canvas").first();
    if (await canvas.count()) {
      await expect
        .poll(() =>
          canvas.evaluate((c) => {
            const p = c
              .getContext("2d")
              .getImageData(0, 0, c.width, c.height).data;
            let ink = 0;
            for (let i = 3; i < p.length; i += 4) if (p[i] > 0) ink++;
            return ink;
          }),
        )
        .toBeGreaterThan(100);
    }
  }
  expect(errors).toEqual([]);
  expect(external).toEqual([]);
});

test("company/city/year filters preserve the correct trip count and city CSV export", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Performance overview" }),
  ).toBeVisible();
  await page.locator("#company-filter").selectOption("Pink Cab");
  await page.locator("#city-filter").selectOption("NEW YORK NY");
  await page.locator("#year-filter").selectOption("2018");
  const rows = dataset.cab.monthly.filter(
    (r) =>
      r.company === "Pink Cab" &&
      r.city === "NEW YORK NY" &&
      r.month.startsWith("2018"),
  );
  const total = rows.reduce((s, r) => s + r.trips, 0);
  await expect(page.locator(".scope")).toHaveText(
    `${new Intl.NumberFormat("en-GB").format(total)} trips in selected scope · USD`,
  );
  const download = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Download city comparison CSV" })
    .click();
  expect((await download).suggestedFilename()).toBe("city-comparison.csv");
});

test("customer summaries and composition follow the company filter without counting groups as unique people", async ({
  page,
}) => {
  await page.goto("/#customers");
  for (const company of ["All companies", "Pink Cab", "Yellow Cab"]) {
    await page.locator("#company-filter").selectOption(company);
    const segments = dataset.cab.segments.filter(
      (s) => company === "All companies" || s.company === company,
    );
    const sum = (rows, key) => rows.reduce((total, row) => total + row[key], 0);
    const groups = sum(segments, "customers");
    const contribution = sum(segments, "contribution");
    const repeat = segments.filter((s) => s.segment !== "one-trip");
    const values = page.locator(".customer-metrics .metric > strong");
    await expect(values.nth(0)).toHaveText(
      new Intl.NumberFormat("en-GB").format(groups),
    );
    await expect(values.nth(1)).toHaveText(
      `${((100 * sum(repeat, "customers")) / groups).toFixed(1)}%`,
    );
    await expect(values.nth(2)).toHaveText(
      `${((100 * sum(repeat, "contribution")) / contribution).toFixed(1)}%`,
    );
    await expect(page.locator(".customer-definition")).toContainText(
      "appears in both",
    );
    await expect(page.locator(".segment-profile")).toHaveCount(3);
    const totalBarWidth = await page
      .locator(".mix-track span")
      .evaluateAll((bars) =>
        bars.reduce((total, bar) => total + parseFloat(bar.style.width), 0),
      );
    // Browsers round inline CSS percentages when serialising style.width.
    expect(totalBarWidth).toBeCloseTo(100, 2);
    await expect(page.locator("tbody tr")).toHaveCount(segments.length);
  }
});

test("a task cannot be finalised without acceptance checks; approved state and notes persist", async ({
  page,
}) => {
  await page.goto("/#board");
  await page.locator('[data-issue="EKI-101"]').click();
  await page.locator("#task-status").selectOption("Done");
  await page.locator("#task-reviewer").fill("Test reviewer");
  await page
    .locator("#task-notes")
    .fill("Checked the source record and limitations.");
  await page
    .getByRole("button", { name: "Save decision", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("Cannot finalise");
  for (const checkbox of await page.locator("[data-check]").all())
    await checkbox.check();
  await page
    .getByRole("button", { name: "Save decision", exact: true })
    .click();
  await expect(page.locator("#issue-dialog")).not.toBeVisible();
  await expect(
    page
      .getByRole("region", { name: "Done" })
      .locator('[data-issue="EKI-101"]'),
  ).toBeVisible();
  await page.reload();
  await page.locator('[data-issue="EKI-101"]').click();
  await expect(page.locator("#task-status")).toHaveValue("Done");
  await expect(page.locator("#task-notes")).toHaveValue(
    "Checked the source record and limitations.",
  );
});

test("new tasks and HTML-like reviewer input are stored as text and included in exports", async ({
  page,
}) => {
  await page.goto("/#board");
  await page.getByRole("button", { name: "New task", exact: true }).click();
  await page.locator("#task-title").fill("Test a regional campaign");
  await page
    .locator("#task-hypothesis")
    .fill("A randomised holdout can measure incremental contribution.");
  await page.locator("#task-reviewer").fill("<img src=x onerror=alert(1)>");
  await page
    .locator("#task-notes")
    .fill("Request spend and exposure data before estimating effects.");
  await page
    .getByRole("button", { name: "Save decision", exact: true })
    .click();
  await expect(page.locator('[data-issue="EKI-108"]')).toContainText(
    "Test a regional campaign",
  );
  await page.goto("/#evidence");
  await expect(page.locator(".audit-list")).toContainText(
    "<img src=x onerror=alert(1)>",
  );
  await expect(page.locator(".audit-list img")).toHaveCount(0);
  const brief = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export brief" }).click();
  expect((await brief).suggestedFilename()).toBe(
    "cab-growth-decision-brief.md",
  );
});

test("budget scenarios respect totals and calculate the same response as the Python model", async ({
  page,
}) => {
  await page.goto("/#media");
  await page
    .getByRole("button", { name: "Model allocation", exact: true })
    .click();
  const vals = await page
    .locator("[data-share]")
    .evaluateAll((xs) =>
      Object.fromEntries(xs.map((x) => [x.dataset.share, +x.value])),
    );
  expect(Object.values(vals).reduce((a, b) => a + b, 0)).toBe(100);
  Object.values(vals).forEach((v) => {
    expect(v).toBeGreaterThanOrEqual(10);
    expect(v).toBeLessThanOrEqual(60);
  });
  // Compare the browser result to the Python solver's exported objective. Integer
  // percentage sliders introduce a small rounding loss relative to the solver.
  const objective = dataset.media.plans.find(
    (p) => p.budget === 30000,
  ).incremental_revenue;
  const displayed = Number(
    (await page.locator("#response-value").textContent()).replace(
      /[^\d.-]/g,
      "",
    ),
  );
  expect(Math.abs(displayed - objective)).toBeLessThan(10);
  await page.locator("#share-search").fill("60");
  await page.locator("#share-search").dispatchEvent("input");
  const values = await page
    .locator("[data-share]")
    .evaluateAll((xs) => xs.map((x) => +x.value));
  expect(values.reduce((a, b) => a + b, 0)).toBe(100);
  values.forEach((v) => expect(v).toBeGreaterThanOrEqual(10));
});

test("a concurrent review cannot overwrite a newer decision", async ({
  page,
  context,
}) => {
  await page.goto("/#board");
  const other = await context.newPage();
  await other.goto("/#board");
  await page.locator('[data-issue="EKI-102"]').click();
  await other.locator('[data-issue="EKI-102"]').click();
  await other.locator("#task-reviewer").fill("Reviewer B");
  await other.locator("#task-notes").fill("Newer decision.");
  await other
    .getByRole("button", { name: "Save decision", exact: true })
    .click();
  await page.locator("#task-reviewer").fill("Reviewer A");
  await page.locator("#task-notes").fill("Stale decision.");
  await page
    .getByRole("button", { name: "Save decision", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("changed in another tab");
  await other.close();
});

for (const viewport of [
  { width: 1440, height: 1000 },
  { width: 1024, height: 1000 },
  { width: 390, height: 844 },
  { width: 320, height: 780 },
]) {
  test(`responsive layout and screenshots at ${viewport.width}px`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    for (const view of [
      "overview",
      "customers",
      "forecast",
      "media",
      "board",
      "evidence",
    ]) {
      await page.goto("/#" + view);
      await expect(page.locator("h1")).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
      ).toBeTruthy();
      const heading = page.locator("h1");
      const box = await heading.boundingBox();
      expect(box.x + box.width).toBeLessThanOrEqual(viewport.width);
      await page.screenshot({
        path: `output/screenshots/${view}-${viewport.width}.png`,
        fullPage: true,
      });
    }
  });
}
