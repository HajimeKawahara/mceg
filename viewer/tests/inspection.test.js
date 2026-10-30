import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { indexGraph } from '../src/graph.js';
import { inspectionState, sameDoiRecords, materialEntries } from '../src/literature.js';

const fixture = () => JSON.parse(readFileSync(new URL('./fixtures/exoeos-graph.json', import.meta.url)));
test('inventory preserves historical and differently scoped inspections of the same DOI', () => {
  const graph = fixture();
  const entries = materialEntries(graph.nodes);
  assert.equal(entries.length, 13);
  const stateOf = label => entries.find(e => e.node.label === label).state;
  assert.equal(stateOf('ma_original_20261021'), 'not_inspected');
  assert.equal(stateOf('ma_original_supplied_20261029'), 'inspected');
  assert.equal(stateOf('badro_main_supplied_20261029'), 'inspected');
  assert.equal(stateOf('badro_supplement_20261021'), 'not_inspected');
  assert.equal(stateOf('badro_supplement_supplied_20261029'), 'inspected');
  assert.equal(stateOf('reported_domain'), 'unknown');
  assert.equal(new Set(entries.map(e => e.node.id)).size, entries.length);
});

test('DOI discovery is limited to the same source snapshot and does not promote old records', () => {
  const graph = fixture();
  const main = graph.nodes.find(n => n.label === 'badro_main_supplied_20261029');
  const supplement = graph.nodes.find(n => n.label === 'badro_supplement_20261021');
  const unrelated = { ...structuredClone(main), id: 'different-snapshot', origin: { ...main.origin, source: 'other' } };
  graph.nodes.push(unrelated);
  const matches = sameDoiRecords(supplement, 'doi:10.1073/PNAS.1505672112', indexGraph(graph));
  assert.ok(matches.some(n => n.id === main.id));
  assert.ok(!matches.some(n => n.id === supplement.id || n.id === unrelated.id));
  assert.equal(inspectionState(supplement), 'not_inspected');
  assert.deepEqual(sameDoiRecords(supplement, 'https://example.org/paper', indexGraph(graph)), []);
});

test('partial, missing and non-literature provenance are not promoted to inspected papers', () => {
  const graph = fixture();
  const literature = graph.nodes.find(n => n.label === 'young_printed_20261021');
  literature.record.provenance.inspection = 'partial';
  assert.equal(inspectionState(literature), 'partial');
  delete literature.record.provenance;
  assert.equal(inspectionState(literature), 'unknown');
  const implementation = graph.nodes.find(n => n.label === 'implementation_source_review_20261021');
  implementation.record.sources.push('https://doi.org/10.1234/unreviewed');
  assert.equal(implementation.record.provenance.inspection, 'inspected');
  assert.equal(inspectionState(implementation), 'unknown');
  const entry = materialEntries(graph.nodes).find(e => e.node.id === implementation.id);
  assert.equal(entry.state, 'unknown');
  assert.deepEqual(entry.locators, ['https://doi.org/10.1234/unreviewed']);
});

test('citations without literature evidence remain discoverable and do not borrow other snapshots', () => {
  const graph = fixture();
  const task = graph.nodes.find(n => n.type === 'follow_up' && n.label === 'inspect_ma_original');
  const clone = { ...structuredClone(task), id: 'other-task', origin: { ...task.origin, source: 'other' } };
  const entries = materialEntries([...graph.nodes, clone]);
  assert.ok(!entries.some(e => e.node.id === task.id));
  assert.equal(entries.find(e => e.node.id === clone.id).state, 'unknown');
  assert.deepEqual(materialEntries([]), []);
});
