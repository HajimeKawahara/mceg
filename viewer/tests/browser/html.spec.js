import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const example = JSON.parse(readFileSync(new URL('../../public/example-graph.json', import.meta.url)));

async function downloadHtml(page, path) {
  const pending = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Save as HTML', exact: true }).click();
  const download = await pending;
  await download.saveAs(path);
  return download;
}

test('HTML matches the original viewer on desktop and mobile', async ({ page, context }, testInfo) => {
  test.setTimeout(60000);
  await page.goto('/');
  await page.getByRole('button', { name: 'Explore example' }).click();
  const path = testInfo.outputPath('styled-graph.html');
  await downloadHtml(page, path);
  const exported = await context.newPage();
  await exported.goto(pathToFileURL(path).href);
  await expect(exported.locator('.package-overview')).toBeVisible();

  for (const [screen, viewport] of Object.entries({ desktop: { width: 1440, height: 1000 }, mobile: { width: 390, height: 844 } })) {
    for (const browserPage of [page, exported]) {
      await browserPage.setViewportSize(viewport);
      await browserPage.getByRole('button', { name: 'Package overview', exact: true }).click();
    }
    for (const view of ['overview', 'graph', 'materials']) {
      for (const browserPage of [page, exported]) {
        if (view === 'graph') {
          await browserPage.locator('.contract-card > button').first().click();
          await expect(browserPage.locator('.react-flow__node')).toHaveCount(9);
        }
        if (view === 'materials') await browserPage.getByRole('button', { name: 'Materials list', exact: true }).click();
        await browserPage.mouse.move(0, 0);
        await browserPage.evaluate(() => { document.activeElement.blur(); window.scrollTo(0, 0); });
      }
      const original = await page.screenshot({ path: testInfo.outputPath(`${screen}-${view}-original.png`), fullPage: true, animations: 'disabled' });
      await expect.poll(async () => {
        const saved = await exported.screenshot({ path: testInfo.outputPath(`${screen}-${view}-exported.png`), fullPage: true, animations: 'disabled' });
        return saved.equals(original);
      }, { message: `Exported ${screen} ${view} should match the original viewer` }).toBe(true);
    }
  }
});

test('HTML preserves the complete graph and viewer on a static server and offline', async ({ page, context }, testInfo) => {
  test.setTimeout(60000);
  const graph = structuredClone(example);
  const model = graph.nodes.find(node => node.type === 'model');
  model.record.model.description = 'Exported graph: 日本語 </script><script>window.injected = true</script><!-- & < >';
  const filename = 'published-graph.json';
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Save as HTML' })).toHaveCount(0);
  await page.locator('input[type=file]').setInputFiles({ name: filename, mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(graph)) });
  await page.locator('#search').fill('no matching record');
  await page.getByRole('button', { name: '日本語', exact: true }).click();
  const path = testInfo.outputPath('published-graph.html');
  const download = await downloadHtml(page, path);
  expect(download.suggestedFilename()).toBe('published-graph.html');
  await expect(page.locator('#search')).toHaveValue('no matching record');
  const html = readFileSync(path, 'utf8');

  // Serve only the exported HTML at a nested URL; no companion assets exist.
  const hosted = 'http://127.0.0.1:4173/published/research/graph.html';
  const requests = [];
  const errors = [];
  await page.route(hosted, route => route.fulfill({ contentType: 'text/html', body: html }));
  page.on('request', request => requests.push(request.url()));
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(hosted);
  await expect(page.locator('.package-overview')).toBeVisible();
  await expect(page.locator('.dataset')).toContainText(filename);
  await expect(page.locator('html')).toHaveAttribute('lang', 'ja');
  await expect(page.locator('#search')).toHaveValue('');
  expect(await page.locator('#mceg-snapshot').evaluate(element => JSON.parse(element.textContent).graph)).toEqual(graph);
  expect(await page.evaluate(() => window.injected)).toBeUndefined();
  await expect(page.locator('script[src], link[rel=stylesheet]')).toHaveCount(0);
  await page.locator('.contract-card > button').first().click();
  await expect(page.locator('.react-flow__node')).toHaveCount(9);
  await page.getByRole('button', { name: 'EN', exact: true }).click();
  await page.getByRole('button', { name: 'Open follow-ups' }).click();
  await expect(page.locator('.record-card')).toHaveCount(3);
  await page.getByRole('button', { name: 'Materials list', exact: true }).click();
  await expect(page.locator('.material-inventory')).toBeVisible();
  await page.evaluate(() => { window.print = () => { window.printed = true; }; });
  await page.getByRole('button', { name: 'Save as PDF', exact: true }).click();
  expect(await page.evaluate(() => window.printed)).toBe(true);
  await expect(page.locator('.material-print')).toBeAttached();
  await expect(page.locator('.material-print')).toBeHidden();
  await page.emulateMedia({ media: 'print' });
  await expect(page.locator('#root')).toBeHidden();
  await expect(page.locator('.material-print')).toBeVisible();
  await page.emulateMedia({ media: 'screen' });
  await page.evaluate(() => window.dispatchEvent(new Event('afterprint')));
  expect(requests).toEqual([hosted]);

  // Re-export from the hosted snapshot without fetching the original site.
  const secondPath = testInfo.outputPath('copied-graph.html');
  await downloadHtml(page, secondPath);
  await context.setOffline(true);
  await page.goto(pathToFileURL(secondPath).href);
  await expect(page.locator('.package-overview')).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await page.locator('.contract-card > button').first().click();
  await expect(page.locator('.react-flow__node')).toHaveCount(9);
  await page.reload();
  await expect(page.locator('.dataset')).toContainText(filename);
  expect(errors).toEqual([]);
});

test('failed HTML export keeps the graph and allows retry', async ({ page }, testInfo) => {
  test.setTimeout(60000);
  await page.goto('/');
  await page.getByRole('button', { name: 'Explore example' }).click();
  await page.route('**/viewer-export.json', route => route.fulfill({ status: 500 }));
  await page.getByRole('button', { name: 'Save as HTML', exact: true }).click();
  await expect(page.getByRole('alert')).toHaveText('Could not save HTML. Please try again.');
  await expect(page.locator('.contract-card')).toHaveCount(1);
  await expect(page.getByRole('button', { name: 'Save as HTML', exact: true })).toBeEnabled();
  await page.unroute('**/viewer-export.json');
  const download = await downloadHtml(page, testInfo.outputPath('example.html'));
  expect(download.suggestedFilename()).toBe('example-graph.html');
  await expect(page.getByRole('alert')).toHaveCount(0);
});
