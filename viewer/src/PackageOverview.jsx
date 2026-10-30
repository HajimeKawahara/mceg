import React, { useState } from 'react';
import { excerpt } from './graph.js';
import { sourceGroups } from './navigation.js';

export default function PackageOverview({ graph, index, sourceId, nodes, matching, openSource, t }) {
  const [page, setPage] = useState(0);
  const source = index.sources.get(sourceId);
  const catalogs = source ? (source.kind === 'catalog' ? [source] : []) : graph.sources.filter(s => s.kind === 'catalog');
  const groups = sourceGroups(nodes, index);
  const matches = new Set(matching.map(n => n.id));
  const visible = groups.filter(group => group.nodes.some(n => matches.has(n.id)));
  const pageIndex = Math.min(page, Math.max(0, Math.ceil(visible.length / 6) - 1));
  const followUps = nodes.filter(n => n.type === 'follow_up');
  return <section className="package-overview panel" aria-label={t.packageOverview}>
    <span className="eyebrow">{t.packageOverview}</span><h2>{source ? `${source.provider} · ${source.path}` : [...new Set(graph.sources.map(s => s.provider))].join(' · ') || t.packageOverview}</h2>
    <p>{t.packageIntro}</p>
    <div className="package-stats">
      <span><b>{groups.length}</b> {t.sourceCount}</span><span><b>{nodes.length}</b> {t.records}</span>
      <span><b>{followUps.filter(n => !index.completed.has(n.id)).length}</b> {t.open}</span>
      <span><b>{followUps.filter(n => index.completed.has(n.id)).length}</b> {t.completedOverview}</span>
    </div>
    {catalogs.map(catalog => <section className="catalog-info" key={catalog.id}>
      <h3>{catalog.path} · {t.catalogIndex}</h3><p>{t.catalogMeaning}</p>
      <p className="muted">{catalog.provider}{catalog.record_version ? ` · ${catalog.record_version}` : ''}
        {catalog.distribution && ` · ${catalog.distribution.name} ${catalog.distribution.version}`}</p>
      <details><summary>{t.provenance}</summary><dl className="fields"><dt>sha256</dt><dd>{catalog.sha256}</dd><dt>format</dt><dd>{catalog.version}</dd></dl></details>
    </section>)}
    {source && source.kind !== 'catalog' && !groups.length && <p>{t.noSourceRecords}</p>}
    <div className="contract-grid">{visible.slice(pageIndex * 6, (pageIndex + 1) * 6).map(group => {
      const entries = graph.selections.filter(s => s.kind === 'catalog_record' && s.model === group.entry.id && (!sourceId || s.origin.source === sourceId));
      return <article className="contract-card" key={group.source.id}>
        <span className="eyebrow">{group.source.path}</span>
        <button onClick={() => openSource(group.source.id)}><strong>{group.entry.label}</strong></button>
        <p className="contract-excerpt">{excerpt(group.entry)}</p>
        <small>{t.open}: {group.open} · {t.completedOverview}: {group.completed}</small>
        {!!entries.length && <details><summary>{t.catalogEntries} · {entries.length}</summary><p className="muted">{t.selectionNote}</p>
          {entries.map((entry, i) => <section key={i}><strong>{entry.catalog_model?.label} / {entry.record?.id}</strong>
            <p>{entry.record?.summary}</p><small>{entry.origin.pointer}</small>
            <p>{t.assessments}: {(entry.assessments ?? []).map(id => index.nodes.get(id)?.label ?? id).join(', ') || '—'}</p></section>)}</details>}
      </article>;
    })}</div>
    {nodes.length > 0 && !visible.length && <p>{t.empty}</p>}
    {visible.length > 6 && <nav className="pager" aria-label={t.sourceCount}>
      <button disabled={!pageIndex} onClick={() => setPage(pageIndex - 1)}>{t.previous}</button><span>{pageIndex * 6 + 1}–{Math.min((pageIndex + 1) * 6, visible.length)} / {visible.length}</span>
      <button disabled={(pageIndex + 1) * 6 >= visible.length} onClick={() => setPage(pageIndex + 1)}>{t.next}</button>
    </nav>}
  </section>;
}
