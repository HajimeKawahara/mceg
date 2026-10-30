import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

const example = JSON.parse(readFileSync(new URL('../../public/example-graph.json', import.meta.url)));
const exogibbs = JSON.parse(readFileSync(new URL('../fixtures/exogibbs-graph.json', import.meta.url)));
async function openExample(page) {
  await page.goto('/');
  await page.getByRole('button', { name: 'Explore example' }).click();
  await page.locator('.contract-card > button').first().click();
  await expect(page.locator('.react-flow__node')).toHaveCount(9);
}

test('example navigation, unknown judgments, provenance, and Japanese UI', async ({ page }) => {
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await openExample(page);
  await page.getByRole('button', { name: 'Unknown judgments' }).click();
  await page.locator('.record-card').first().click();
  await expect(page.locator('.detail .badges')).toContainText('unknown');
  await page.getByText('Source snapshot', { exact: true }).click();
  await expect(page.locator('.detail')).toContainText('examples/v02/h2_solubility.yaml');
  await expect(page.locator('.detail')).toContainText(example.sources[0].sha256);
  await page.getByRole('button', { name: '日本語', exact: true }).click();
  await expect(page.getByRole('heading', { name: '近くのつながり' })).toBeVisible();
  await page.getByRole('button', { name: '未解決の作業' }).click();
  await expect(page.locator('.record-card')).toHaveCount(3);
  await page.locator('.record-card').first().click();
  await expect(page.getByRole('heading', { name: '完了条件' })).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('lang', 'ja');
  expect(errors).toEqual([]);
  await page.screenshot({ path: 'test-results/viewer-ja.png', fullPage: true });
});

test('file import is local, malformed files preserve the existing graph, and empty graphs work', async ({ page }) => {
  await page.goto('/');
  const external = [];
  page.on('request', r => { if (!r.url().startsWith('http://127.0.0.1:4173/')) external.push(r.url()); });
  await page.locator('input[type=file]').setInputFiles({ name: 'project.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(example)) });
  await expect(page.locator('.dataset')).toContainText('project.json');
  await page.locator('#search').fill('calibration');
  await expect(page.locator('.record-card').first()).toBeVisible();
  await page.locator('input[type=file]').setInputFiles({ name: 'broken.json', mimeType: 'application/json', buffer: Buffer.from('{') });
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page.locator('.dataset')).toContainText('project.json');
  await page.locator('input[type=file]').setInputFiles({ name: 'empty.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify({ format: 'mceg_graph_v1', sources: [], nodes: [], edges: [], selections: [] })) });
  await expect(page.getByText('The graph contains no records.')).toBeVisible();
  expect(external).toEqual([]);
});

test('keyboard opens graph nodes and back restores the prior record', async ({ page }) => {
  await openExample(page);
  const title = await page.locator('.detail h2').textContent();
  const neighbor = page.locator('.react-flow__node').nth(1);
  const label = await neighbor.locator('strong').textContent();
  await neighbor.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('.detail h2')).toHaveText(label);
  await page.getByRole('button', { name: 'Back', exact: false }).click();
  await expect(page.locator('.detail h2')).toHaveText(title);
  await page.locator('.graph-footer').getByRole('button', { name: 'Next' }).click();
  await expect(page.locator('.graph-footer')).toContainText('9–16');
});

test('mobile layout does not overflow and supports record inspection', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openExample(page);
  await page.getByRole('button', { name: 'Open follow-ups' }).click();
  await page.locator('.record-card').first().click();
  await expect(page.getByRole('heading', { name: 'Completion criterion' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/viewer-mobile.png', fullPage: true });
});

test('HCN contract selection opens an overview with context and traceable next steps', async ({ page }) => {
  await page.goto('/');
  await page.locator('input[type=file]').setInputFiles({ name: 'exogibbs.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(exogibbs)) });
  const source = exogibbs.sources.find(s => s.path.endsWith('fastchem_hcn_followup.yaml'));
  await page.locator('#source').selectOption(source.id);
  const overview = page.getByRole('region', { name: 'About this contract' });
  await expect(overview.getByRole('heading', { level: 2 })).toHaveText('Preliminary FastChem HCN refit and database discrepancy follow-up');
  await expect(overview.locator('.overview-description')).toContainText('Why did preliminary FastChem HCN predictions differ');
  await expect(overview.getByRole('heading', { name: 'Compared HCN inputs' })).toBeVisible();
  await expect(overview.getByRole('cell', { name: 'FastChem preliminary tables', exact: true })).toBeVisible();
  await expect(overview.getByRole('cell', { name: 'ExoGibbs curated-gas-v1', exact: true })).toBeVisible();
  await expect(overview.getByRole('cell', { name: '0.956471 (-4.35%)', exact: true })).toBeVisible();
  await expect(overview.getByRole('heading', { name: 'Sources and unresolved questions' })).toBeVisible();
  await overview.getByRole('button', { name: 'Burcat / ATcT source audit', exact: false }).click();
  await expect(page.locator('.detail h2')).toHaveText('source_audit');
  await overview.getByText('Judgments & next steps', { exact: true }).click();
  await expect(overview.locator('.supported')).toContainText('isolates HCN');
  await expect(overview.locator('.unknown')).toContainText('no independent whole-mixture physical constraint');
  await expect(overview.locator('.open')).toContainText('exact Goos/Burcat source snapshot');
  await expect(overview.locator('.open .overview-entry:visible')).toHaveCount(1);
  await overview.locator('.open .overview-entry').first().click();
  await expect(page.locator('.detail h2')).toHaveText('reconstruct_hcn_refit');
  await expect(overview.getByRole('heading', { level: 2 })).toContainText('HCN');
  await page.getByRole('button', { name: '日本語', exact: true }).click();
  await expect(page.getByRole('region', { name: 'この契約について' })).toBeVisible();
  await page.screenshot({ path: 'test-results/hcn-overview.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const other = exogibbs.nodes.find(n => n.type === 'model' && n.origin.source !== source.id);
  await page.locator('#source').selectOption(other.origin.source);
  await expect(page.locator('.overview h2')).toHaveText(other.label);
  await expect(page.locator('.detail h2')).toHaveText(other.label);
  await expect(page.locator('.overview-description')).toHaveText(other.record.model.description);
});

test('authored Markdown is local, supports evidence navigation, and cannot load embedded content', async ({ page }) => {
  const graph = structuredClone(example);
  const model = graph.nodes.find(n => n.type === 'model');
  const evidence = graph.nodes.find(n => n.type === 'evidence');
  model.record.model.description = `## Investigation brief

[Read evidence](#evidence/${encodeURIComponent(evidence.ref.id)})
[Missing](#evidence/does-not-exist)
[Bad escape](#evidence/%ZZ)
[External](https://example.org/paper)
[Unsafe](javascript:alert%281%29)
[Local](file:///etc/passwd)
![Remote image](https://example.org/tracker.png)
<img src="https://example.org/raw.png" onerror="alert(1)">
<script>alert(1)</script>`;
  await page.goto('/');
  const externalRequests = [];
  page.on('request', r => { if (!r.url().startsWith('http://127.0.0.1:4173/')) externalRequests.push(r.url()); });
  await page.locator('input[type=file]').setInputFiles({ name: 'narrative.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(graph)) });
  await page.locator('.contract-card > button').first().click();
  const narrative = page.locator('.narrative');
  await expect(narrative.locator('img, script')).toHaveCount(0);
  await expect(narrative.locator('.missing-reference')).toHaveCount(2);
  await expect(narrative.getByRole('link')).toHaveCount(1);
  await expect(narrative.getByRole('link', { name: 'External' })).toHaveAttribute('rel', 'noopener noreferrer');
  await narrative.getByRole('button', { name: 'Read evidence' }).click();
  await expect(page.locator('.detail h2')).toHaveText(evidence.label);
  expect(externalRequests).toEqual([]);
});
