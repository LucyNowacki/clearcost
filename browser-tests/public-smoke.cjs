const { chromium } = require('@playwright/test');

async function main() {
  const base = process.argv[2];
  if (!base || !/^https:\/\/lucynowacki\.github\.io\//.test(base)) {
    throw new Error('Supply the public portfolio HTTPS URL.');
  }
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
  });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    const views = {
      overview: 'Performance overview',
      customers: 'Understand repeat behaviour',
      forecast: 'Let the baseline challenge the model',
      media: 'Explore a marketing budget decision',
      board: 'Decision board',
      evidence: 'Make the recommendation traceable',
    };
    for (const [view, heading] of Object.entries(views)) {
      const response = await page.goto(`${base}#${view}`);
      if (response && response.status() !== 200) throw new Error(`HTTP ${response.status()} for ${view}`);
      await page.getByRole('heading', {name: heading, exact: true}).waitFor({ state: 'visible' });
      if (await page.locator('.callout').filter({ hasText: 'could not be loaded' }).count()) {
        throw new Error(`Missing data in ${view}`);
      }
      const canvas = page.locator('canvas').first();
      if (await canvas.count()) {
        const ink = await canvas.evaluate(c => {
          const pixels = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
          let nonblank = 0;
          for (let i = 3; i < pixels.length; i += 4) if (pixels[i]) nonblank++;
          return nonblank;
        });
        if (ink < 100) throw new Error(`Blank chart in ${view}`);
      }
      if (view === 'overview') await page.screenshot({ path: 'output/screenshots/public-overview.png', fullPage: true });
      console.log(`${view}: HTTP 200, visible heading and rendered content`);
    }
    if (errors.length) throw new Error(errors.join('\n'));
    console.log('Public smoke check passed; no JavaScript errors.');
  } finally {
    await browser.close();
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
