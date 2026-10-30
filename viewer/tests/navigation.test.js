import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { indexGraph, validateGraph } from '../src/graph.js';
import { scopedNodes, sourceGroups } from '../src/navigation.js';
import { relatedMaterials, sourceLocators, doiFrom, parseCitation, searchLinks } from '../src/literature.js';

const fixture = () => JSON.parse(readFileSync(new URL('./fixtures/exoeos-graph.json', import.meta.url)));
test('catalog selection expands declared source snapshots, not empty catalog-origin nodes', () => {
  const graph = validateGraph(fixture());
  const index = indexGraph(graph);
  const catalog = graph.sources.find(s => s.kind === 'catalog');
  assert.equal(graph.nodes.filter(n => n.origin.source === catalog.id).length, 0);
  assert.equal(scopedNodes(graph, index, catalog.id).length, graph.nodes.length);
  assert.equal(sourceGroups(scopedNodes(graph, index, catalog.id), index).length, 2);
  const selection = graph.selections[0];
  const source = index.nodes.get(selection.model).origin.source;
  assert.ok(scopedNodes(graph, index, source).every(n => n.origin.source === source));
  const narrow = { ...graph, selections: [selection] };
  assert.deepEqual(scopedNodes(narrow, index, catalog.id), scopedNodes(graph, index, source));
  assert.equal(sourceGroups([], index).length, 0);
});

test('open empirical_scope follows exact target assessments to papers and retains trace paths', () => {
  const graph = fixture();
  const index = indexGraph(graph);
  const task = graph.nodes.find(n => n.type === 'follow_up' && n.label === 'empirical_scope' && n.ref.path.endsWith('ma_fe_si_o.yaml'));
  assert.deepEqual(sourceLocators(task).map(doiFrom), ['10.1007/s11663-001-0011-0', '10.1038/s41586-023-05823-0']);
  const materials = relatedMaterials(task, index);
  assert.ok(materials.some(m => m.node.label === 'ma_original_supplied_20261029'));
  assert.ok(materials.some(m => sourceLocators(m.node).some(s => s.includes('Young_etal_2023_Nature.pdf'))));
  assert.ok(materials.every(m => m.path[0] === task.id && m.path.at(-1) === m.node.id));
  assert.ok(materials.every(m => m.node.ref.path === task.ref.path));
});

test('completion points to the supplied paper, without treating all related work as complete', () => {
  const graph = fixture(); const index = indexGraph(graph);
  for (const type of ['follow_up', 'resolution']) {
    const node = graph.nodes.find(n => n.type === type && n.label === 'inspect_ma_original');
    const materials = relatedMaterials(node, index);
    const supplied = materials.find(m => m.node.label === 'ma_original_supplied_20261029');
    assert.ok(supplied?.viaCompletion);
    assert.equal(supplied.node.record.provenance.inspection, 'inspected');
    assert.match(supplied.node.record.provenance.location, /Eqs\. 10-12/);
    assert.ok(!materials.some(m => m.node.label === 'test_run'));
  }
  const empirical = graph.nodes.find(n => n.type === 'follow_up' && n.label === 'empirical_scope' && n.ref.path.endsWith('ma_fe_si_o.yaml'));
  assert.ok(!index.completed.has(empirical.id));
});

test('provenance traversal handles cycles and never expands sideways via shared evidence', () => {
  const graph = fixture();
  const evidence = graph.nodes.find(n => n.type === 'evidence' && n.label === 'ma_original_supplied_20261029');
  const unrelated = { ...structuredClone(evidence), id: 'unrelated', type: 'assessment' };
  graph.nodes.push(unrelated);
  graph.edges.push({ ...graph.edges[0], id: 'shared', type: 'uses_evidence', source: unrelated.id, target: evidence.id });
  graph.edges.push({ ...graph.edges[0], id: 'self-loop', type: 'derived_from', source: evidence.id, target: evidence.id });
  const materials = relatedMaterials(evidence, indexGraph(graph));
  assert.ok(!materials.some(m => m.node.id === unrelated.id));
  assert.equal(new Set(materials.map(m => m.node.id)).size, materials.length);
});

test('DOI recognition and metadata identity checks prevent accidental or unsafe lookups', () => {
  assert.equal(doiFrom('https://doi.org/10.1007/s11663-001-0011-0'), '10.1007/s11663-001-0011-0');
  assert.equal(doiFrom('doi:10.1234/ABC'), '10.1234/abc');
  for (const value of ['https://example.org/10.1234/paper', 'javascript:10.1234/x', 'file:///tmp/10.1234/x', 'paper.pdf', null]) assert.equal(doiFrom(value), null);
  const payload = { message: { DOI: '10.1234/abc', title: ['A paper'], author: [{ given: 'A.', family: 'Author' }], issued: { 'date-parts': [[2001]] }, 'container-title': ['Journal'] } };
  assert.equal(parseCitation(payload, '10.1234/abc').year, '2001');
  assert.throws(() => parseCitation(payload, '10.1234/other'));
  assert.throws(() => parseCitation({}, '10.1234/abc'));
  assert.equal(new URL(searchLinks('Title & DOI').google).searchParams.get('q'), 'Title & DOI');
});
