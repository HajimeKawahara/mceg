// A catalog owns selections, not record nodes. Expand only its declared models.
export function scopedNodes(graph, index, sourceId) {
  if (!sourceId) return graph.nodes;
  if (index.sources.get(sourceId)?.kind !== 'catalog') return graph.nodes.filter(n => n.origin.source === sourceId);
  const sources = new Set(graph.selections
    .filter(s => s.kind === 'catalog_record' && s.origin.source === sourceId)
    .map(s => index.nodes.get(s.model)?.origin.source).filter(Boolean));
  return graph.nodes.filter(n => sources.has(n.origin.source));
}

export function sourceGroups(nodes, index) {
  const groups = new Map();
  for (const node of nodes) {
    const source = index.sources.get(node.origin.source);
    if (!groups.has(source.id)) groups.set(source.id, { source, nodes: [] });
    groups.get(source.id).nodes.push(node);
  }
  return [...groups.values()].map(group => ({ ...group,
    entry: group.nodes.find(n => n.type === 'model') ?? group.nodes.find(n => ['case', 'manual_case'].includes(n.type)) ?? group.nodes[0],
    open: group.nodes.filter(n => n.type === 'follow_up' && !index.completed.has(n.id)).length,
    completed: group.nodes.filter(n => n.type === 'follow_up' && index.completed.has(n.id)).length,
  })).sort((a, b) => `${a.source.provider}/${a.source.path}`.localeCompare(`${b.source.provider}/${b.source.path}`));
}
