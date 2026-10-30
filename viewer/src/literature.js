import { safeUrl } from './graph.js';

export function doiFrom(value) {
  if (typeof value !== 'string') return null;
  let candidate = value.trim().replace(/^doi:\s*/i, '');
  if (safeUrl(candidate)) {
    const url = new URL(candidate);
    if (!['doi.org', 'dx.doi.org'].includes(url.hostname.toLowerCase())) return null;
    try { candidate = decodeURIComponent(url.pathname.slice(1)); } catch { return null; }
  }
  return /^10\.\d{4,9}\/\S+$/i.test(candidate) ? candidate.toLowerCase() : null;
}

export function sourceLocators(node) {
  return [...new Set([...(Array.isArray(node.record.sources) ? node.record.sources : []),
    ...(Array.isArray(node.record.artifacts) ? node.record.artifacts.map(a => a?.source) : [])]
    .filter(value => typeof value === 'string' && value.trim()))];
}

// Directed, scoped traversal: target revision -> its assessments -> their
// declared evidence -> upstream provenance. Never follow evidence sideways to
// other investigations, or expand contains/subject/context edges.
export function relatedMaterials(node, index) {
  if (!node) return [];
  const queue = [{ node, path: [node.id], viaCompletion: node.type === 'resolution' }];
  const visited = new Set();
  const result = [];
  for (let i = 0; i < queue.length; i++) {
    const item = queue[i];
    const current = item.node;
    if (visited.has(current.id)) continue;
    visited.add(current.id);
    if (current.id !== node.id && sourceLocators(current).length) result.push(item);
    const edges = [...(index.adjacent.get(current.id) ?? [])].sort((a, b) => Number(b.type === 'resolves') - Number(a.type === 'resolves'));
    for (const edge of edges) {
      let next;
      if (edge.target === current.id && edge.type === 'resolves' && current.id === node.id) next = edge.source;
      else if (edge.source === current.id && ['uses_evidence', 'derived_from'].includes(edge.type)) next = edge.target;
      else if (edge.source === current.id && edge.type === 'targets' && current.id === node.id && !index.completed.has(node.id)) next = edge.target;
      else if (edge.target === current.id && edge.type === 'assesses' && ['claim', 'condition'].includes(current.type)) next = edge.source;
      // Include a resolved task's own locators without traversing its target.
      else if (edge.source === current.id && edge.type === 'resolves' && node.type === 'resolution') next = edge.target;
      if (next && !visited.has(next)) queue.push({ node: index.nodes.get(next), path: [...item.path, next], viaCompletion: item.viaCompletion || edge.type === 'resolves' });
    }
  }
  return result.sort((a, b) => Number(b.viaCompletion) - Number(a.viaCompletion) ||
    Number(b.node.record.kind === 'literature') - Number(a.node.record.kind === 'literature'));
}

export function parseCitation(payload, doi) {
  const record = payload?.message;
  if (!record || doiFrom(record.DOI) !== doiFrom(doi)) throw new Error('DOI mismatch');
  const title = Array.isArray(record.title) && typeof record.title[0] === 'string' ? record.title[0] : '';
  if (!title) throw new Error('Missing title');
  const authors = (Array.isArray(record.author) ? record.author : []).map(a =>
    [a.given, a.family].filter(v => typeof v === 'string').join(' ') || (typeof a.name === 'string' ? a.name : '')).filter(Boolean);
  const year = record.issued?.['date-parts']?.[0]?.[0];
  return { title, authors, year: Number.isInteger(year) ? String(year) : '',
    journal: typeof record['container-title']?.[0] === 'string' ? record['container-title'][0] : '',
    volume: typeof record.volume === 'string' ? record.volume : '',
    pages: typeof record.page === 'string' ? record.page : '', doi: doiFrom(doi) };
}

export function searchLinks(query) {
  return { google: `https://www.google.com/search?q=${encodeURIComponent(query)}`,
    scholar: `https://scholar.google.com/scholar?q=${encodeURIComponent(query)}` };
}
