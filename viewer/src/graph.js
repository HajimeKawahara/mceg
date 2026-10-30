// This module depends only on the public mceg_graph_v1 envelope, not Python.
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const text = value => typeof value === 'string';

export function validateGraph(value) {
  const fail = message => { throw new Error(message); };
  if (!object(value) || value.format !== 'mceg_graph_v1') fail('format');
  for (const key of ['sources', 'nodes', 'edges', 'selections']) {
    if (!Array.isArray(value[key])) fail(key);
  }
  function identities(items, name) {
    const ids = new Set();
    for (const item of items) {
      if (!object(item) || !text(item.id) || !item.id || ids.has(item.id)) fail(name);
      ids.add(item.id);
    }
    return ids;
  }
  const sources = identities(value.sources, 'sources.id');
  const nodes = identities(value.nodes, 'nodes.id');
  identities(value.edges, 'edges.id');
  const origin = item => object(item) && sources.has(item.source) && text(item.pointer) &&
    (item.pointer === '' || (item.pointer.startsWith('/') && !/~(?![01])/u.test(item.pointer)));
  for (const source of value.sources) {
    for (const key of ['provider', 'path', 'sha256', 'kind', 'version']) {
      if (!text(source[key])) fail(`sources.${key}`);
    }
  }
  for (const node of value.nodes) {
    if (!text(node.type) || !text(node.label) || !object(node.record) ||
        !object(node.ref) || !origin(node.origin)) fail('nodes');
  }
  for (const edge of value.edges) {
    if (!text(edge.type) || !nodes.has(edge.source) || !nodes.has(edge.target) ||
        !object(edge.data) || !origin(edge.origin)) fail('edges');
  }
  for (const selection of value.selections) {
    if (!object(selection) || !origin(selection.origin)) fail('selections');
  }
  return value;
}

export function indexGraph(graph) {
  const nodes = new Map(graph.nodes.map(node => [node.id, node]));
  const sources = new Map(graph.sources.map(source => [source.id, source]));
  const adjacent = new Map(graph.nodes.map(node => [node.id, []]));
  const completed = new Set();
  for (const edge of graph.edges) {
    adjacent.get(edge.source).push(edge);
    if (edge.target !== edge.source) adjacent.get(edge.target).push(edge);
    if (edge.type === 'resolves' && nodes.get(edge.source).type === 'resolution' &&
        nodes.get(edge.target).type === 'follow_up') completed.add(edge.target);
  }
  const searchable = new Map(graph.nodes.map(node => [node.id,
    JSON.stringify([node.label, node.type, node.ref, node.record]).toLocaleLowerCase()]));
  return { nodes, sources, adjacent, completed, searchable };
}

export function category(node, index) {
  if (node.type === 'follow_up') return index.completed.has(node.id) ? 'completed' : 'open';
  if (node.type === 'resolution') return 'completed';
  if (node.type === 'assessment' || node.type === 'manual_assessment') return 'assessments';
  return node.type === 'evidence' ? 'evidence' : 'all';
}

// Only explicit unknown judgments; missing fields are not inferred judgments.
export function matchesCategory(node, index, filter) {
  if (filter === 'all') return true;
  if (filter === 'unknown') return node.record.status === 'unknown' || node.record.classification === 'unknown';
  return category(node, index) === filter;
}

export function excerpt(node) {
  const r = node.record;
  const value = r.summary ?? r.statement ?? r.action ?? r.note ?? r.description ?? r.model?.description ?? r.reasons?.[0];
  return typeof value === 'string' ? value : node.label;
}

// Summarize one source snapshot, never merge different contracts or choose a
// "current" assessment. Every excerpt links back to its authored record.
export function contractOverview(node, index, selections = []) {
  if (!node) return null;
  const records = [...index.nodes.values()].filter(n => n.origin.source === node.origin.source)
    .sort((a, b) => a.origin.pointer.localeCompare(b.origin.pointer, 'en', { numeric: true }));
  const model = records.find(n => n.type === 'model');
  if (!model) return null;
  const supported = [];
  const unknown = [];
  for (const record of records) {
    if (!['assessment', 'claim'].includes(record.type)) continue;
    const status = record.record.status ?? record.record.classification;
    if (!['supported', 'unknown'].includes(status)) continue;
    const targetEdge = index.adjacent.get(record.id).find(e => e.source === record.id && e.type === 'assesses');
    const target = targetEdge ? index.nodes.get(targetEdge.target) : null;
    const reasons = record.record.reasons;
    const reason = Array.isArray(reasons) ? reasons.find(r => typeof r === 'string') : null;
    const item = { id: record.id, text: reason || (target && excerpt(target)) || excerpt(record), kind: record.type };
    (status === 'supported' ? supported : unknown).push(item);
  }
  for (const domain of Array.isArray(model.record.domains) ? model.record.domains : []) {
    if (domain?.status === 'unknown' && typeof domain.description === 'string') {
      unknown.push({ id: model.id, text: domain.description, kind: 'domains' });
    }
  }
  const open = records.filter(n => n.type === 'follow_up' && !index.completed.has(n.id))
    .map(n => ({ id: n.id, text: excerpt(n), kind: n.type }));
  const completed = records.filter(n => n.type === 'follow_up' && index.completed.has(n.id))
    .map(n => ({ id: n.id, text: excerpt(n), kind: n.type }));
  return { model, source: index.sources.get(model.origin.source), supported, unknown, open, completed,
    evidence: records.filter(n => n.type === 'evidence'),
    catalogEntries: selections.filter(s => s.kind === 'catalog_record' && s.model === model.id),
  };
}

export function narrativeEvidence(href, evidence) {
  if (typeof href !== 'string' || !href.startsWith('#evidence/')) return null;
  try {
    const id = decodeURIComponent(href.slice('#evidence/'.length));
    return evidence.find(n => n.ref.id === id) ?? null;
  } catch { return null; }
}

export function neighborhood(id, index, page = 0, size = 8) {
  const relations = index.adjacent.get(id) ?? [];
  const neighbors = [...new Set(relations.map(edge => edge.source === id ? edge.target : edge.source))]
    .filter(other => other !== id);
  const visible = new Set([id, ...neighbors.slice(page * size, (page + 1) * size)]);
  return {
    nodes: [...visible].map(key => index.nodes.get(key)).filter(Boolean),
    edges: relations.filter(edge => visible.has(edge.source) && visible.has(edge.target)),
    total: neighbors.length,
  };
}

export function safeUrl(value) {
  if (typeof value !== 'string' || !/^https?:\/\//i.test(value)) return null;
  try { const url = new URL(value); return url.username || url.password ? null : url.href; }
  catch { return null; }
}
