import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

const graph = JSON.parse(readFileSync(new URL('../fixtures/exoeos-graph.json', import.meta.url)));
async function openList(page, data = graph) {
  // Suppress the OS dialog; inspect the exact DOM passed to window.print, then
  // use Chromium's PDF renderer to verify actual link annotations as well.
  await page.addInitScript(() => { window.print = () => { window.printCalls = (window.printCalls ?? 0) + 1; }; });
  await page.goto('/');
  await page.locator('input[type=file]').setInputFiles({ name: 'package-graph.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(data)) });
  await page.getByRole('button', { name: 'Materials list', exact: true }).click();
}

test('Japanese PDF includes all matching pages, clickable sources and searchable text, without upload', async ({ page }) => {
  const external = [];
  page.on('request', r => { if (!r.url().startsWith('http://127.0.0.1:4173/')) external.push(r.url()); });
  await openList(page);
  await page.getByRole('button', { name: 'Next', exact: true }).click();
  await page.getByRole('button', { name: '日本語' }).click();
  const title = await page.title();
  await page.getByRole('button', { name: 'PDFに保存', exact: true }).click();
  expect(await page.evaluate(() => window.printCalls)).toBe(1);
  await expect(page.locator('.print-results .print-material')).toHaveCount(13);
  await expect(page.locator('.print-appendix')).toHaveCount(0);
  await expect(page.locator('.material-print')).toContainText('確認済み（記録の範囲）');
  await expect(page.locator('.material-print')).toContainText('未確認');
  await expect(page.locator('.material-print')).toContainText('Eqs. 10-12');
  const sourceId = graph.nodes.find(n => n.label === 'ma_original_supplied_20261029').origin.source;
  await expect(page.locator('.print-snapshots')).toContainText(graph.sources.find(s => s.id === sourceId).sha256);
  await page.emulateMedia({ media: 'print' });
  await expect(page.locator('#root')).toBeHidden();
  await expect(page.locator('.material-print')).toBeVisible();
  const pdf = await page.pdf({ path: 'test-results/materials-ja.pdf', preferCSSPageSize: true, printBackground: true });
  expect(pdf.subarray(0, 5).toString()).toBe('%PDF-');
  const raw = pdf.toString('latin1');
  expect(raw).toContain('/URI (https://doi.org/10.1007/s11663-001-0011-0)');
  expect(raw).toContain('/URI (https://faculty.epss.ucla.edu/~eyoung/reprints/Young_etal_2023_Nature.pdf)');
  expect(raw).toContain('/URI (https://scholar.google.com/scholar?q=');
  expect(raw).toContain('/Dest');
  expect(raw).toContain('/ToUnicode');
  expect(external).toEqual([]);
  await page.evaluate(() => window.dispatchEvent(new Event('afterprint')));
  await page.emulateMedia({ media: 'screen' });
  await expect(page.locator('.material-print')).toHaveCount(0);
  await expect(page).toHaveTitle(title);
  await expect(page.locator('.material-inventory .pager')).toContainText('5–8 / 13');
  await expect(page.locator('.inventory-card')).toHaveCount(4);
});

test('filtered PDF keeps review history in an appendix and includes cached citations without a new lookup', async ({ page }) => {
  const requests = [];
  await page.route('https://api.crossref.org/works/**', route => {
    requests.push(route.request().url());
    return route.fulfill({ json: { message: { DOI: '10.1007/s11663-001-0011-0', title: ['Cached Ma citation — test metadata'], author: [{ family: 'Ma' }], issued: { 'date-parts': [[2001]] } } } });
  });
  await openList(page);
  await page.locator('.inspection-filters').getByRole('button', { name: /^Not inspected/ }).click();
  await page.locator('#material-search').fill('ma_original_20261021');
  await page.getByRole('button', { name: 'Look up citation' }).click();
  await expect(page.locator('.citation')).toContainText('Cached Ma citation');
  await page.getByRole('button', { name: 'Save as PDF', exact: true }).click();
  await expect(page.locator('.print-results .print-material')).toHaveCount(1);
  await expect(page.locator('.print-appendix .print-material')).toHaveCount(4);
  await expect(page.locator('.print-results')).toContainText('before downloading');
  await expect(page.locator('.print-results')).toContainText('Cached Ma citation');
  await expect(page.locator('.print-results > article > .badge')).toHaveText('Not inspected');
  await expect(page.locator('.print-appendix')).toContainText('ma_original_supplied_20261029');
  await expect(page.locator('.print-appendix')).toContainText('young_printed_20261021');
  expect(requests).toHaveLength(1);
  const reportLinks = await page.locator('.material-print a[href^="#"]').evaluateAll(links => links.map(a => a.getAttribute('href')));
  for (const target of reportLinks) await expect(page.locator(`.material-print ${target}`)).toHaveCount(1);
  await page.pdf({ path: 'test-results/materials-filtered-en.pdf', preferCSSPageSize: true, printBackground: true });
  await page.evaluate(() => window.dispatchEvent(new Event('afterprint')));
  await expect(page.locator('#material-search')).toHaveValue('ma_original_20261021');
  await page.locator('#material-search').fill('no matching material');
  await expect(page.getByRole('button', { name: 'Save as PDF', exact: true })).toBeDisabled();
});

test('print output keeps authored text inert and uses only safe external or report-local links', async ({ page }) => {
  const data = structuredClone(graph);
  const node = data.nodes.find(n => n.label === 'ma_original_20261021');
  node.record.summary = '<img src="https://example.org/tracker.png">';
  node.record.sources.push('javascript:alert(1)', 'file:///tmp/private.pdf', 'results/local.pdf');
  await openList(page, data);
  await page.getByRole('button', { name: 'Save as PDF', exact: true }).click();
  await expect(page.locator('.material-print img, .material-print script, .material-print button, .material-print details')).toHaveCount(0);
  await expect(page.locator('.material-print')).toContainText('results/local.pdf');
  const links = await page.locator('.material-print a').evaluateAll(anchors => anchors.map(a => a.getAttribute('href')));
  expect(links.every(href => /^(https?:\/\/|#material-)/.test(href))).toBe(true);
  await page.getByRole('button', { name: 'Package overview', exact: true }).click();
  await expect(page.locator('.material-print')).toHaveCount(0);
  await expect(page).not.toHaveTitle('package-graph-materials');
});
