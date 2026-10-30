import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

const graph = JSON.parse(readFileSync(new URL('../fixtures/exoeos-graph.json', import.meta.url)));
const ma = graph.sources.find(s => s.path.endsWith('ma_fe_si_o.yaml'));
const catalog = graph.sources.find(s => s.kind === 'catalog');
async function loadList(page, data = graph) {
  await page.goto('/');
  await page.locator('input[type=file]').setInputFiles({ name: 'inspection-graph.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(data)) });
  await page.getByRole('button', { name: 'Materials list', exact: true }).click();
}

test('materials list supports states, catalog scope, paging, Japanese, and return navigation', async ({ page }) => {
  const requests = [];
  page.on('request', r => { if (!r.url().startsWith('http://127.0.0.1:4173/')) requests.push(r.url()); });
  await loadList(page);
  await expect(page.locator('.inventory-count')).toHaveText('13 material records');
  await expect(page.locator('.inventory-card')).toHaveCount(4);
  await page.getByRole('button', { name: 'Next', exact: true }).click();
  await expect(page.locator('.material-inventory .pager')).toContainText('5–8 / 13');
  await page.locator('#material-source').selectOption(ma.id);
  await expect(page.locator('.inventory-count')).toHaveText('11 material records');
  await page.locator('#material-source').selectOption(catalog.id);
  await expect(page.locator('.inventory-count')).toHaveText('13 material records');
  await page.locator('.inspection-filters').getByRole('button', { name: /^Partially inspected/ }).click();
  await expect(page.getByText('No material records match this source, search and inspection filter.')).toBeVisible();
  await page.locator('.inspection-filters').getByRole('button', { name: /^Inspected \(recorded scope\)/ }).click();
  await page.locator('#material-search').fill('supplied Ma (2001) original');
  await expect(page.locator('.inventory-card')).toHaveCount(1);
  await page.locator('.inventory-card h3 button').click();
  await expect(page.locator('.detail h2')).toHaveText('ma_original_supplied_20261029');
  await page.getByRole('button', { name: 'Back', exact: false }).click();
  await expect(page.locator('#material-search')).toHaveValue('supplied Ma (2001) original');
  await expect(page.locator('.inventory-card')).toHaveCount(1);
  await page.getByRole('button', { name: '日本語' }).click();
  await expect(page.getByRole('region', { name: '資料一覧', exact: true })).toBeVisible();
  await expect(page.locator('.inventory-card > .badge')).toHaveText('確認済み（記録の範囲）');
  await expect(page.locator('.inventory-card .download-guidance')).toContainText('再ダウンロードは不要');
  await page.screenshot({ path: 'test-results/materials-list-ja.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/materials-list-mobile.png', fullPage: true });
  expect(requests).toEqual([]);
});

test('historical uninspected DOI keeps its status after citation lookup and links to inspected scopes', async ({ page }) => {
  await page.route('https://api.crossref.org/works/**', route => route.fulfill({ json: { message: {
    DOI: '10.1007/s11663-001-0011-0', title: ['Ma paper — test metadata'],
  } } }));
  await loadList(page);
  await page.locator('.inspection-filters').getByRole('button', { name: /^Not inspected/ }).click();
  await page.locator('#material-search').fill('ma_original_20261021');
  const card = page.locator('.inventory-card');
  await expect(card).toHaveCount(1);
  await expect(card.locator('.doi-inspection > div > .badge')).toHaveText('Not inspected');
  await expect(card.locator('.download-guidance')).toContainText('before downloading');
  await card.getByRole('button', { name: 'Look up citation' }).click();
  await expect(card.locator('.citation')).toContainText('not an inspection of the paper');
  await expect(card.locator('.doi-inspection > div > .badge')).toHaveText('Not inspected');
  await card.locator('.doi-inspection > details > summary').click();
  const supplied = card.locator('.inspection-record').filter({ has: page.getByRole('button', { name: 'ma_original_supplied_20261029', exact: true }) });
  await expect(supplied).toContainText('Eqs. 10-12');
  await supplied.getByRole('button', { name: 'ma_original_supplied_20261029', exact: true }).click();
  await expect(page.locator('.detail h2')).toHaveText('ma_original_supplied_20261029');
  await expect(page.locator('.detail .badges')).toContainText('Inspected (recorded scope)');
});

test('main article and supplement keep separate states for the same DOI', async ({ page }) => {
  await loadList(page);
  await page.locator('#material-search').fill('10.1073/pnas.1505672112');
  await expect(page.locator('.inventory-card')).toHaveCount(4);
  const main = page.locator('.inventory-card').filter({ has: page.locator('h3 button', { hasText: 'badro_main_supplied_20261029' }) });
  const supplement = page.locator('.inventory-card').filter({ has: page.locator('h3 button', { hasText: 'badro_supplement_20261021' }) });
  await expect(main.locator('.doi-inspection > div > .badge')).toHaveText('Inspected (recorded scope)');
  await expect(supplement.locator('.doi-inspection > div > .badge')).toHaveText('Not inspected');
  await supplement.locator('.doi-inspection > details > summary').click();
  await expect(supplement.locator('.doi-inspection')).toContainText('does not replace the uninspected');
  await expect(supplement.locator('.doi-inspection')).toContainText('Supplied 12-page SI');
});

test('partial and absent inspection records provide distinct download advice', async ({ page }) => {
  // Synthetic partial status and isolated DOI exercise missing review coverage.
  const data = structuredClone(graph);
  data.nodes.find(n => n.label === 'young_printed_20261021').record.provenance.inspection = 'partial';
  data.nodes.find(n => n.label === 'reported_domain').record.sources = ['doi:10.1234/unrecorded-test'];
  await loadList(page, data);
  await page.locator('.inspection-filters').getByRole('button', { name: /^Partially inspected/ }).click();
  await expect(page.locator('.inventory-card')).toHaveCount(1);
  await expect(page.locator('.inventory-card .download-guidance')).toContainText('Inspect the remaining scope');
  await page.locator('.inspection-filters').getByRole('button', { name: /^Inspection not recorded/ }).click();
  await expect(page.locator('.inventory-card')).toHaveCount(1);
  await expect(page.locator('.inventory-card .download-guidance')).toContainText('Whether the document was inspected is not recorded');
  await page.getByRole('button', { name: '日本語' }).click();
  await expect(page.locator('.inventory-card > .badge')).toHaveText('確認状態の記録なし');
});
