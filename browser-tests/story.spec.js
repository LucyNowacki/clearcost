const { test, expect } = require("@playwright/test");
const fs = require("node:fs");
const dataset = require("../dist/data/dashboard.json");

test("Overview links the three application questions to inspectable evidence", async ({
  page,
}) => {
  await page.goto("/#overview");
  const route = page.getByRole("region", {
    name: "From a business question to a defensible decision",
  });
  await expect(route.locator(".story-steps a")).toHaveCount(3);
  await route.getByRole("link", { name: /Solve with data/ }).click();
  await expect(page).toHaveURL(/#evidence\/problem-solving$/);
  const answer = page.locator("#answer-problem-solving");
  await expect(answer).toHaveAttribute("open", "");
  await expect(answer).toContainText("359,392");
  for (const company of dataset.cab.companies) {
    const models = dataset.cab.forecast.filter(
      (m) => m.company === company.company,
    );
    for (const model of models)
      await expect(answer).toContainText(`${(model.wape * 100).toFixed(2)}%`);
  }
  await expect(answer).toContainText("not a claim of client revenue uplift");
  await page.reload();
  await expect(answer).toHaveAttribute("open", "");
  await answer
    .getByRole("link", { name: "Inspect the holdout comparison" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Let the baseline challenge the model" }),
  ).toBeVisible();
  await page.goto("/#evidence/ekimetrics");
  await expect(page.locator("#answer-ekimetrics")).toHaveAttribute("open", "");
  await expect(page.locator("#answer-ekimetrics")).toContainText(
    "not Ekimetrics software",
  );
  await expect(page.locator('#nav a[data-view="evidence"]')).toHaveAttribute(
    "aria-current",
    "page",
  );
  await page.goto("/#evidence/unknown");
  await expect(page.locator("#answer-mmm")).toHaveAttribute("open", "");
});

test("answer drafts can be copied and downloaded without proof notes or invented outcomes", async ({
  page,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/#evidence/mmm");
  await page
    .getByRole("button", { name: "Copy Understand MMM answer" })
    .click();
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  expect(copied).toContain("I think of Marketing Mix Modelling");
  expect(copied).toContain("not evidence of real campaign lift");
  expect(copied).not.toContain("Evidence behind the answer");
  const downloadPromise = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Download all three answer drafts" })
    .click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(
    "lucy-ekimetrics-application-drafts.txt",
  );
  const content = fs.readFileSync(await download.path(), "utf8");
  expect(content).toContain("Nothing submitted.");
  expect(content).toContain(
    "Why are you interested in this opportunity at Ekimetrics",
  );
  expect(content).toContain("359,392");
  expect(content).toContain("#evidence/problem-solving");
});

test("clipboard failure offers a download and the accordion works with the keyboard", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: () => Promise.reject(new Error("Denied")) },
    });
  });
  await page.goto("/#evidence/ekimetrics");
  await page
    .getByRole("button", { name: "Copy Why Ekimetrics answer" })
    .click();
  await expect(page.getByRole("status")).toContainText("Clipboard unavailable");
  const first = page.locator("#answer-mmm summary");
  await first.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#answer-mmm")).toHaveAttribute("open", "");
  await expect(page.locator("#answer-ekimetrics")).not.toHaveAttribute(
    "open",
    "",
  );
});

test("adstock illustration responds numerically but never changes the fitted budget scenario", async ({
  page,
}) => {
  await page.goto("/#media");
  await expect(
    page.getByRole("heading", {
      name: "What drove sales, and what should the next pound do?",
    }),
  ).toBeVisible();
  const budgetBefore = await page.locator("#response-value").textContent();
  const slider = page.getByRole("slider", { name: "Weekly carryover" });
  for (const [decay, expected] of [
    ["0", "£0"],
    ["0.5", "£1,250"],
    ["0.9", "£7,290"],
  ]) {
    await slider.fill(decay);
    await expect(page.locator("#carryover-week-four")).toHaveText(expected);
    const chartData = await page
      .locator("#carryover-chart")
      .evaluate(
        (canvas) => window.Chart.getChart(canvas).data.datasets[1].data,
      );
    chartData.forEach((value, week) =>
      expect(value).toBeCloseTo(10000 * Number(decay) ** week, 8),
    );
    await expect(page.locator("#response-value")).toHaveText(budgetBefore);
  }
  for (const channel of dataset.media.channels) {
    await page
      .getByRole("combobox", { name: "Example channel" })
      .selectOption(channel.id);
    await expect(slider).toHaveValue(String(channel.decay));
  }
  await expect(page.locator("#carryover-description")).toContainText(
    "not sales",
  );
  await expect(page.locator("#carryover-chart")).toBeVisible();
  const ink = await page.locator("#carryover-chart").evaluate((canvas) => {
    const pixels = canvas
      .getContext("2d")
      .getImageData(0, 0, canvas.width, canvas.height).data;
    let count = 0;
    for (let i = 3; i < pixels.length; i += 4) if (pixels[i] > 0) count++;
    return count;
  });
  expect(ink).toBeGreaterThan(100);
});

for (const width of [1440, 390, 320]) {
  test(`each application answer fits a ${width}px viewport`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    for (const question of ["mmm", "problem-solving", "ekimetrics"]) {
      await page.goto(`/#evidence/${question}`);
      const detail = page.locator(`#answer-${question}`);
      await expect(detail).toHaveAttribute("open", "");
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
      ).toBeTruthy();
      const box = await detail.boundingBox();
      expect(box.x + box.width).toBeLessThanOrEqual(width);
      await page.screenshot({
        path: `output/screenshots/application-${question}-${width}.png`,
        fullPage: true,
      });
    }
  });
}
