const { test, expect } = require("@playwright/test");

async function openPurpose(page) {
  await page.goto("/#overview");
  await page
    .getByRole("button", { name: "Project Purpose", exact: true })
    .click();
  return page.getByRole("dialog", { name: "Project Purpose", exact: true });
}

test("purpose explains the project, routes to every view and preserves pinned state across navigation and filters", async ({
  page,
}) => {
  const panel = await openPurpose(page);
  await expect(panel).toBeVisible();
  await expect(panel).toContainText("359,392 historical cab trips");
  await expect(panel).toContainText("entirely simulated in GBP");
  await expect(panel.locator(".purpose-route a")).toHaveCount(6);
  await panel
    .getByRole("button", { name: "Keep open while navigating" })
    .click();
  await expect(panel.locator("#purpose-pin")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await panel.locator('a[href="#customers"]').click();
  await expect(page).toHaveURL(/#customers$/);
  await expect(panel).toBeVisible();
  // The pinned guide is non-modal: keyboard focus can reach the underlying filter.
  await page.locator("#company-filter").selectOption("Pink Cab");
  await expect(panel).toBeVisible();
  await panel.locator('a[href="#overview"]').click();
  await expect(page.locator("#purpose-open")).toHaveAttribute(
    "aria-expanded",
    "true",
  );
  await panel.locator("#purpose-pin").click();
  await panel.locator('a[href="#forecast"]').click();
  await expect(panel).toBeHidden();
  await expect(
    page.getByRole("heading", { name: "Let the baseline challenge the model" }),
  ).toBeVisible();
});

test("title-bar drag and all eight resize handles use ordinary mouse input", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const panel = await openPurpose(page);
  const initial = await panel.boundingBox();
  const bar = await page.locator("#purpose-titlebar").boundingBox();
  await page.mouse.move(bar.x + 100, bar.y + 25);
  await page.mouse.down();
  await page.mouse.move(bar.x + 170, bar.y + 60, { steps: 6 });
  await page.mouse.up();
  const moved = await panel.boundingBox();
  expect(moved.x - initial.x).toBeCloseTo(70, 0);
  expect(moved.y - initial.y).toBeCloseTo(35, 0);
  for (const edge of ["e", "w", "n", "s", "ne", "se", "sw", "nw"]) {
    const before = await panel.boundingBox();
    const handle = await page.locator(`[data-resize="${edge}"]`).boundingBox();
    const dx = edge.includes("e") ? 18 : edge.includes("w") ? -18 : 0;
    const dy = edge.includes("s") ? 12 : edge.includes("n") ? -12 : 0;
    await page.mouse.move(
      handle.x + handle.width / 2,
      handle.y + handle.height / 2,
    );
    await page.mouse.down();
    await page.mouse.move(
      handle.x + handle.width / 2 + dx,
      handle.y + handle.height / 2 + dy,
      { steps: 5 },
    );
    await page.mouse.up();
    const after = await panel.boundingBox();
    expect(after.width - before.width).toBeCloseTo(Math.abs(dx), 0);
    expect(after.height - before.height).toBeCloseTo(Math.abs(dy), 0);
    if (edge.includes("w"))
      expect(after.x + after.width).toBeCloseTo(before.x + before.width, 0);
    if (edge.includes("n"))
      expect(after.y + after.height).toBeCloseTo(before.y + before.height, 0);
  }
});

test("maximise, restore, opacity, keyboard movement and Escape are usable", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const panel = await openPurpose(page);
  const initial = await panel.boundingBox();
  await page
    .locator("#purpose-titlebar")
    .dblclick({ position: { x: 110, y: 24 } });
  await expect(panel).toHaveClass(/maximised/);
  const expanded = await panel.boundingBox();
  expect(expanded.width).toBe(1416);
  await page
    .getByRole("button", { name: "Restore window", exact: true })
    .click();
  const restored = await panel.boundingBox();
  expect(restored).toEqual(initial);
  await page.getByRole("slider", { name: "Window opacity" }).fill("65");
  await expect(panel).toHaveCSS("opacity", "0.65");
  await expect(page.locator("#purpose-opacity-value")).toHaveText("65%");
  await page.locator("#purpose-titlebar").focus();
  await page.keyboard.press("ArrowRight");
  expect((await panel.boundingBox()).x).toBe(initial.x + 16);
  await page.keyboard.press("Shift+ArrowLeft");
  expect((await panel.boundingBox()).width).toBe(initial.width - 16);
  await page.keyboard.press("Escape");
  await expect(panel).toBeHidden();
  await expect(page.locator("#purpose-open")).toBeFocused();
  await expect(page.locator("#purpose-open")).toHaveAttribute(
    "aria-expanded",
    "false",
  );
  await page.locator("#purpose-open").click();
  await expect(panel).toHaveCSS("opacity", "0.65");
  await page.locator(".breadcrumb-root").click();
  await expect(panel).toBeHidden();
});

for (const width of [390, 320]) {
  test(`purpose window stays usable on a ${width}px mobile viewport and after resizing the viewport`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    const panel = await openPurpose(page);
    let box = await panel.boundingBox();
    expect(box.x).toBeGreaterThanOrEqual(12);
    expect(box.x + box.width).toBeLessThanOrEqual(width - 12);
    expect(box.y + box.height).toBeLessThanOrEqual(844 - 82);
    await expect(
      page.getByRole("slider", { name: "Window opacity" }),
    ).toBeInViewport();
    expect(
      await panel.evaluate((el) => el.scrollWidth <= el.clientWidth),
    ).toBeTruthy();
    await panel.locator('a[href="#evidence"]').scrollIntoViewIfNeeded();
    await expect(panel.locator('a[href="#evidence"]')).toBeInViewport();
    await page.screenshot({
      path: `output/screenshots/purpose-${width}.png`,
      fullPage: true,
    });
    await page.setViewportSize({ width, height: 420 });
    await expect
      .poll(async () => {
        const resized = await panel.boundingBox();
        return resized.y + resized.height;
      })
      .toBeLessThanOrEqual(420 - 82);
    await expect(
      page.getByRole("button", { name: "Close Project Purpose" }),
    ).toBeInViewport();
    await expect(
      page.getByRole("slider", { name: "Window opacity" }),
    ).toBeInViewport();
  });
}
