import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

const graph = JSON.parse(readFileSync(new URL('../fixtures/exoeos-graph.json', import.meta.url)));
const catalog = graph.sources.find(s => s.kind === 'catalog');
const ma = graph.sources.find(s => s.path.endsWith('ma_fe_si_o.yaml'));
async function load(page) {
  await page.goto('/');
  await page.locator('input[type=file]').setInputFiles({ name: 'package-graph.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(graph)) });
}

test('opens on package overview, treats index.json as a catalog, and returns from contracts', async ({ page }) => {
  await load(page);
  await expect(page.getByRole('region', { name: 'Package overview' })).toBeVisible();
  await expect(page.locator('.contract-card')).toHaveCount(2);
  await expect(page.locator('.detail')).toHaveCount(0);
  await page.locator('#source').selectOption(catalog.id);
  await expect(page.locator('.package-overview h2')).toContainText('index.json');
  await expect(page.locator('.contract-card')).toHaveCount(2);
  await expect(page.locator('.record-card').first()).toBeVisible();
  await page.locator('.contract-card > button').filter({ hasText: 'Ma Fe-Si-O' }).click();
  await expect(page.locator('.overview h2')).toContainText('Ma Fe-Si-O');
  await page.getByRole('button', { name: 'Back' }).click();
  await expect(page.locator('.package-overview h2')).toContainText('index.json');
  await page.getByRole('button', { name: '日本語' }).click();
  await expect(page.getByRole('region', { name: '全体を見る' })).toBeVisible();
  await page.screenshot({ path: 'test-results/package-overview.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('empirical_scope provides sources and search, with DOI-only citation lookup on request', async ({ page }) => {
  const requests = [];
  await page.route('https://api.crossref.org/works/**', route => {
    requests.push(route.request().url());
    const doi = decodeURIComponent(new URL(route.request().url()).pathname.slice('/works/'.length));
    return route.fulfill({ json: { message: { DOI: doi, title: ['Thermodynamic description for concentrated metallic solutions using interaction parameters'], author: [{ given: 'Z.', family: 'Ma' }], issued: { 'date-parts': [[2001]] }, 'container-title': ['Metallurgical and Materials Transactions B'], volume: '32', page: '87-103' } } });
  });
  await load(page);
  await page.locator('#source').selectOption(ma.id);
  await page.getByRole('button', { name: 'Open follow-ups' }).click();
  await page.locator('.record-card').filter({ hasText: 'empirical_scope' }).click();
  await page.getByRole('button', { name: 'Papers & materials' }).click();
  const own = page.locator('.direct-materials');
  await expect(own.getByRole('link', { name: 'DOI: 10.1007/s11663-001-0011-0' })).toBeVisible();
  await expect(own.getByRole('link', { name: 'Google Scholar', exact: false }).first()).toHaveAttribute('href', /scholar.*10\.1007/);
  expect(requests).toEqual([]);
  await own.getByRole('button', { name: 'Look up citation' }).first().click();
  await expect(own.locator('.citation')).toContainText('concentrated metallic solutions');
  await expect(own.locator('.citation')).toContainText('2001');
  expect(requests).toHaveLength(1);
  expect(decodeURIComponent(requests[0])).toBe('https://api.crossref.org/works/10.1007/s11663-001-0011-0');
  await expect(page.locator('.material-card').first()).toBeVisible();
  await page.screenshot({ path: 'test-results/empirical-materials.png', fullPage: true });
});

test('completed work exposes completion literature, locations, and lookup failure fallback', async ({ page }) => {
  await page.route('https://api.crossref.org/works/**', route => route.fulfill({ status: 503, body: 'Unavailable' }));
  await load(page);
  await page.locator('#source').selectOption(ma.id);
  await page.getByRole('button', { name: 'Completed work', exact: false }).click();
  await page.locator('#search').fill('inspect_ma_original');
  const card = page.locator('.record-card').filter({ has: page.locator('small', { hasText: /^resolution$/ }) });
  await card.click();
  const supplied = page.locator('.material-card').filter({ hasText: 'ma_original_supplied_20261029' });
  await expect(supplied).toContainText('Completion evidence');
  await expect(supplied).toContainText('Eqs. 10-12');
  await expect(supplied.getByRole('link', { name: 'DOI: 10.1007/s11663-001-0011-0' })).toBeVisible();
  await supplied.getByRole('button', { name: 'Look up citation' }).click();
  await expect(supplied.getByRole('status')).toContainText('Could not retrieve');
  await expect(supplied.getByRole('link', { name: 'Google Scholar' })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
