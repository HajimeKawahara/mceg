import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { validateGraph, indexGraph, category, matchesCategory, neighborhood, safeUrl, contractOverview, narrativeEvidence } from '../src/graph.js';

const example = JSON.parse(readFileSync(new URL('../public/example-graph.json', import.meta.url)));
const fixture = () => structuredClone(example);

test('loads a real Graph API export without modifying scientific records', () => {
  const graph = fixture();
  assert.equal(validateGraph(graph), graph);
  const index = indexGraph(graph);
  assert.equal(graph.nodes.filter(n => category(n, index) === 'open').length, 3);
  assert.equal(graph.nodes.filter(n => matchesCategory(n, index, 'assessments')).length, 6);
  assert.ok(graph.nodes.some(n => matchesCategory(n, index, 'unknown')));
  assert.deepEqual(graph, example);
});

test('rejects broken envelopes, duplicate identities, dangling edges and source pointers', () => {
  for (const change of [
    g => { g.format = 'mceg_graph_v2'; },
    g => { g.sources = null; },
    g => { g.nodes.push(g.nodes[0]); },
    g => { g.edges[0].target = 'absent'; },
    g => { g.nodes[0].origin.source = 'absent'; },
    g => { g.nodes[0].origin.pointer = '/bad~2'; },
    g => { g.nodes[0].record = null; },
    g => { g.selections = [null]; },
  ]) { const graph = fixture(); change(graph); assert.throws(() => validateGraph(graph)); }
});

test('unknown future types, empty graphs, and escaped pointers remain readable', () => {
  const graph = fixture();
  graph.nodes[0].type = 'future_record'; graph.edges[0].type = 'future_relation';
  graph.nodes[0].origin.pointer = '/a~1b/~0';
  assert.equal(validateGraph(graph), graph);
  assert.doesNotThrow(() => validateGraph({ format: 'mceg_graph_v1', nodes: [], edges: [], sources: [], selections: [] }));
});

test('completion requires a resolution edge and never promotes unknown support', () => {
  const graph = fixture();
  const followUp = graph.nodes.find(n => n.type === 'follow_up');
  const assessment = graph.nodes.find(n => n.record.status === 'unknown');
  const resolution = { ...structuredClone(followUp), id: 'resolution', type: 'resolution', record: { note: 'Review completed' } };
  graph.nodes.push(resolution);
  assert.equal(category(followUp, indexGraph(graph)), 'open');
  graph.edges.push({ id: 'resolve', type: 'resolves', source: resolution.id, target: followUp.id, origin: followUp.origin, data: {} });
  const index = indexGraph(validateGraph(graph));
  assert.equal(category(followUp, index), 'completed');
  assert.equal(assessment.record.status, 'unknown');
  assert.ok(matchesCategory(assessment, index, 'unknown'));
  assert.ok(matchesCategory(assessment, index, 'assessments'));
});

test('bounded neighborhoods page through every neighbor, retaining cycles and parallel edge origins', () => {
  const graph = fixture();
  const model = graph.nodes.find(n => n.type === 'model');
  const first = graph.edges.find(e => e.source === model.id);
  graph.edges.push({ ...first, id: 'parallel', data: { quantity: 'another' } });
  graph.edges.push({ ...first, id: 'cycle', source: first.target, target: first.source });
  const index = indexGraph(graph);
  const seen = new Set();
  const total = neighborhood(model.id, index).total;
  for (let page = 0; page < Math.ceil(total / 8); page++) {
    const local = neighborhood(model.id, index, page);
    assert.ok(local.nodes.length <= 9);
    local.nodes.forEach(n => seen.add(n.id));
    local.edges.forEach(e => {
      assert.ok(local.nodes.some(n => n.id === e.source));
      assert.ok(local.nodes.some(n => n.id === e.target));
    });
    if (local.edges.some(e => e.id === first.id)) assert.ok(local.edges.some(e => e.id === 'parallel'));
  }
  assert.equal(seen.size, total + 1);
});

test('only explicit HTTP(S) locators are clickable', () => {
  assert.equal(safeUrl('https://example.org/paper'), 'https://example.org/paper');
  for (const value of ['javascript:alert(1)', 'data:text/html,x', '//example.org', 'file:///etc/passwd', '../source.py', 'https://user:pass@example.org']) assert.equal(safeUrl(value), null);
});

test('HCN overview retains source context, authored judgments, open work and catalog summaries', () => {
  const graph = validateGraph(JSON.parse(readFileSync(new URL('./fixtures/exogibbs-graph.json', import.meta.url))));
  const index = indexGraph(graph);
  const model = graph.nodes.find(n => n.type === 'model' && n.ref.id.includes('hcn_followup'));
  const overview = contractOverview(model, index, graph.selections);
  assert.equal(overview.supported.length, 2);
  assert.equal(overview.unknown.length, 2); // Assessment plus explicitly unknown domain.
  assert.equal(overview.open.length, 2);
  assert.equal(overview.completed.length, 1);
  assert.match(overview.open[0].text, /exact Goos\/Burcat source snapshot/);
  assert.equal(overview.catalogEntries.length, 1);
  assert.match(overview.catalogEntries[0].record.summary, /recorded model sensitivities/);
  const related = index.nodes.get(overview.open[0].id);
  assert.deepEqual(contractOverview(related, index, graph.selections), overview);
  for (const group of ['supported', 'unknown', 'open', 'completed']) {
    for (const item of overview[group]) assert.equal(index.nodes.get(item.id).origin.source, model.origin.source);
  }
  const otherModel = graph.nodes.find(n => n.type === 'model' && n.id !== model.id);
  assert.notEqual(contractOverview(otherModel, index, graph.selections).model.id, model.id);
});

test('overview preserves conflicting historical judgments and does not infer missing support', () => {
  const graph = fixture();
  const assessment = graph.nodes.find(n => n.type === 'assessment' && n.record.status === 'supported');
  const old = structuredClone(assessment);
  old.id = 'historical-unknown'; old.record.status = 'unknown'; old.record.reasons = ['Earlier review lacked evidence.'];
  graph.nodes.push(old);
  const index = indexGraph(validateGraph(graph));
  const overview = contractOverview(assessment, index);
  assert.ok(overview.supported.some(item => item.id === assessment.id));
  assert.ok(overview.unknown.some(item => item.id === old.id));
  assert.equal(contractOverview(null, index), null);
  const orphan = { ...assessment, origin: { ...assessment.origin, source: 'another-source' } };
  assert.equal(contractOverview(orphan, index), null);
  assert.deepEqual(overview.catalogEntries, []);
});

test('narrative references resolve only to evidence in the same contract snapshot', () => {
  const graph = fixture();
  const model = graph.nodes.find(n => n.type === 'model');
  const evidence = graph.nodes.find(n => n.type === 'evidence');
  const other = structuredClone(evidence);
  other.id = 'different-snapshot'; other.origin.source = 'different-source';
  graph.nodes.unshift(other);
  const overview = contractOverview(model, indexGraph(graph));
  assert.equal(narrativeEvidence(`#evidence/${encodeURIComponent(evidence.ref.id)}`, overview.evidence).id, evidence.id);
  for (const href of ['#evidence/missing', '#evidence/%ZZ', 'https://example.org', null]) {
    assert.equal(narrativeEvidence(href, overview.evidence), null);
  }
});
