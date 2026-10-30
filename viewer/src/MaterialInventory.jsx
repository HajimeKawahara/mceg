import React, { useMemo } from 'react';
import { doiFrom, inspectionStates, materialEntries } from './literature.js';
import { InspectionBadge, InspectionScope } from './Inspection.jsx';
import { Locators } from './Materials.jsx';

const PAGE = 4;
export default function MaterialInventory({ graph, nodes, index, source, changeSource, select, state, setState, t }) {
  const entries = useMemo(() => materialEntries(nodes), [nodes]);
  const searched = entries.filter(({ node, locators }) =>
    `${index.searchable.get(node.id)} ${locators.join(' ')}`.toLocaleLowerCase().includes(state.query.toLocaleLowerCase()));
  const filtered = searched.filter(entry => state.filter === 'all' || entry.state === state.filter);
  const page = Math.min(state.page, Math.max(0, Math.ceil(filtered.length / PAGE) - 1));
  return <section className="material-inventory panel" aria-label={t.materialInventory}>
    <span className="eyebrow">{t.recordedInspection}</span><h2>{t.materialInventory}</h2>
    <p className="muted">{t.inventoryHint}</p>
    <div className="inventory-controls">
      <div><label htmlFor="material-source">{t.source}</label>
        <select id="material-source" value={source} onChange={e => changeSource(e.target.value)}>
          <option value="">{t.allSources}</option>{graph.sources.map(s => <option key={s.id} value={s.id}>{s.provider} · {s.path}</option>)}
        </select></div>
      <div><label htmlFor="material-search">{t.materialSearch}</label>
        <input id="material-search" type="search" value={state.query} onChange={e => setState({ ...state, query: e.target.value, page: 0 })} /></div>
    </div>
    <div className="inspection-filters" aria-label={t.inspection}>
      {['all', ...inspectionStates].map(filter => <button key={filter} aria-pressed={state.filter === filter}
        onClick={() => setState({ ...state, filter, page: 0 })}>
        {filter === 'all' ? t.allMaterials : t.inspectionStates[filter]} <span>{filter === 'all' ? searched.length : searched.filter(e => e.state === filter).length}</span>
      </button>)}
    </div>
    <p className="muted inventory-count" aria-live="polite">{filtered.length} {t.inspectionRecordCount}</p>
    {!filtered.length && <p>{t.emptyMaterials}</p>}
    <div className="inventory-grid">{filtered.slice(page * PAGE, (page + 1) * PAGE).map(({ node, state: inspection, locators }) => {
      const dois = locators.filter(doiFrom);
      const extra = dois.length ? locators.filter(v => !doiFrom(v)) : [];
      return <article className="inventory-card" key={node.id}>
        <InspectionBadge state={inspection} t={t} />
        <h3><button className="record-link" onClick={() => select(node.id)}>{node.label} →</button></h3>
        <small>{index.sources.get(node.origin.source)?.path}</small>
        <p>{node.record.summary ?? node.record.action ?? node.record.description}</p>
        {!dois.length && <p className="download-guidance">{t.downloadGuidance[inspection]}</p>}
        <details><summary>{t.inspectionScope}</summary><InspectionScope node={node} t={t} /></details>
        <Locators node={node} values={dois.length ? dois : locators} index={index} select={select} t={t} />
        {!!extra.length && <details><summary>{t.otherMaterialLinks} · {extra.length}</summary>
          <Locators node={node} values={extra} index={index} select={select} t={t} /></details>}
      </article>;
    })}</div>
    {filtered.length > PAGE && <nav className="pager" aria-label={t.materialInventory}>
      <button disabled={!page} onClick={() => setState({ ...state, page: page - 1 })}>{t.previous}</button>
      <span>{page * PAGE + 1}–{Math.min((page + 1) * PAGE, filtered.length)} / {filtered.length}</span>
      <button disabled={(page + 1) * PAGE >= filtered.length} onClick={() => setState({ ...state, page: page + 1 })}>{t.next}</button>
    </nav>}
  </section>;
}
