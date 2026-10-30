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

export const inspectionStates = ['not_inspected', 'partial', 'inspected', 'unknown'];
export function isLiterature(node) {
  return node.type === 'evidence' && node.record.kind === 'literature';
}

// Inspection describes an Evidence record's scope, never a DOI as a whole.
// In particular, inspecting implementation code is not inspecting its citations.
export function inspectionState(node) {
  const state = isLiterature(node) ? node.record.provenance?.inspection : null;
  return inspectionStates.includes(state) ? state : 'unknown';
}

export function sameDoiRecords(node, value, index) {
  const doi = doiFrom(value);
  if (!doi) return [];
  return [...index.nodes.values()].filter(n => n.id !== node.id && isLiterature(n) &&
    n.origin.source === node.origin.source && sourceLocators(n).some(s => doiFrom(s) === doi));
}

export function materialEntries(nodes) {
  const literature = nodes.filter(isLiterature);
  const covered = new Set(literature.flatMap(n => sourceLocators(n).map(doiFrom).filter(Boolean)
    .map(doi => JSON.stringify([n.origin.source, doi]))));
  const entries = literature.map(node => ({ node, state: inspectionState(node), locators: sourceLocators(node) }));
  // Keep otherwise unaccounted-for DOI citations visible as unrecorded, rather
  // than assuming that a citation, completed task or numerical test is a review.
  for (const node of nodes.filter(n => !isLiterature(n))) {
    const locators = sourceLocators(node).filter(value => {
      const doi = doiFrom(value);
      return doi && !covered.has(JSON.stringify([node.origin.source, doi]));
    });
    if (locators.length) entries.push({ node, state: 'unknown', locators });
  }
  return entries;
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
