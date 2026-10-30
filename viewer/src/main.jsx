import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ReactFlow, Background, Controls, MarkerType } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import './style.css';
import { validateGraph, indexGraph, matchesCategory, excerpt, neighborhood, safeUrl, contractOverview } from './graph.js';
import { translations, typeLabel, edgeLabel } from './i18n.js';
import Narrative from './Narrative.jsx';
import Materials from './Materials.jsx';
import MaterialInventory from './MaterialInventory.jsx';
import { InspectionBadge } from './Inspection.jsx';
import { inspectionState, isLiterature } from './literature.js';
import PackageOverview from './PackageOverview.jsx';
import { scopedNodes } from './navigation.js';

const PAGE = 8;
const MAX_FILE = 20 * 1024 * 1024;
const colors = { evidence: '#e3f3ec', assessment: '#eee6fb', follow_up: '#fff0d7', resolution: '#e3f3ec', claim: '#fce5ed', model: '#e8eafb' };
function Value({ value }) {
  if (value === null || value === undefined) return <span className="muted">—</span>;
  if (typeof value === 'string') {
    const url = safeUrl(value);
    return url ? <a href={url} target="_blank" rel="noopener noreferrer">{value} ↗</a> : <span className="prose">{value}</span>;
  }
  if (Array.isArray(value)) return value.length ? <ul className="values">{value.map((v, i) => <li key={i}><Value value={v} /></li>)}</ul> : <span>—</span>;
  if (typeof value === 'object') return <dl className="fields">{Object.entries(value).map(([k, v]) => <div key={k}><dt>{k}</dt><dd><Value value={v} /></dd></div>)}</dl>;
  return <span>{String(value)}</span>;
}
function Pager({ page, total, setPage, t, size = PAGE }) {
  if (total <= size) return null;
  return <nav className="pager" aria-label={t.show}>
    <button disabled={!page} onClick={() => setPage(page - 1)}>{t.previous}</button>
    <span>{page * size + 1}–{Math.min(total, (page + 1) * size)} {t.of} {total}</span>
    <button disabled={(page + 1) * size >= total} onClick={() => setPage(page + 1)}>{t.next}</button>
  </nav>;
}
function Origin({ origin, index, t }) {
  const source = index.sources.get(origin.source);
  return <div className="origin"><dl className="fields">
    {['provider', 'path', 'sha256', 'kind', 'version'].map(key => <div key={key}><dt>{key}</dt><dd>{source?.[key]}</dd></div>)}
    <div><dt>JSON Pointer</dt><dd><code>{origin.pointer || '""'}</code></dd></div>
  </dl><p className="muted">{t.sourceNote}</p></div>;
}
function Badges({ node, index, t }) {
  const r = node.record;
  return <div className="badges">
    {['status', 'classification', 'result'].map(key => typeof r[key] === 'string' && <span className="badge" key={key}>{t[key]}: {r[key]}</span>)}
    {isLiterature(node) ? <InspectionBadge state={inspectionState(node)} t={t} /> :
      typeof r.provenance?.inspection === 'string' && <span className="badge">{t.inspection}: {r.provenance.inspection}</span>}
    {node.type === 'follow_up' && <span className="badge">{index.completed.has(node.id) ? t.done : t.pending}</span>}
  </div>;
}
function OverviewEntry({ item, select, t, lang }) {
  return <button className="overview-entry" onClick={() => select(item.id)}>
    <small>{t[item.kind] ?? typeLabel(item.kind, lang)}</small>
    <span>{item.text}</span><small className="read-record">{t.readRecord} →</small>
  </button>;
}
function Overview({ overview, select, t, lang }) {
  const { model, source, supported, unknown, open, completed, catalogEntries } = overview;
  const groups = [
    { key: 'supported', title: t.supportedOverview, items: supported },
    { key: 'unknown', title: t.unknownOverview, items: unknown },
    { key: 'open', title: t.openOverview, items: open },
  ];
  return <section className="overview panel" aria-label={t.overview}>
    <div className="overview-heading"><div><span className="eyebrow">{t.overview}</span>
      <h2>{model.label}</h2></div><button className="contract-link" onClick={() => select(model.id)}>{source.provider} · {source.path}</button></div>
    <div className="overview-description"><Narrative text={typeof model.record.model?.description === 'string' ? model.record.model.description : t.noDescription} overview={overview} select={select} t={t} /></div>
    <p className="muted overview-scope">{t.overviewScope}</p>
    <details className="overview-progress"><summary>{t.progressRecords}</summary>
      <div className="overview-grid">{groups.map(group => <section className={`overview-group ${group.key}`} key={group.key}>
      <h3>{group.title} <span>{group.items.length}</span></h3>
      {group.items.length ? <OverviewEntry item={group.items[0]} select={select} t={t} lang={lang} /> : <p className="muted">{t.noOverviewRecords}</p>}
      {group.items.length > 1 && <details><summary>{t.remaining} · {group.items.length - 1}</summary>
        {group.items.slice(1).map((item, i) => <OverviewEntry key={`${item.id}-${i}`} item={item} select={select} t={t} lang={lang} />)}</details>}
    </section>)}</div></details>
    <div className="overview-extras">
      {!!completed.length && <details><summary>{t.completedOverview} · {completed.length}</summary>
        {completed.map(item => <OverviewEntry key={item.id} item={item} select={select} t={t} lang={lang} />)}</details>}
      {['assumptions', 'domains', 'limitations'].some(key => model.record[key]?.length > 0) && <details><summary>{t.contractScope}</summary>
        {['assumptions', 'domains', 'limitations'].filter(key => model.record[key]?.length > 0).map(key => <section key={key}><h3>{t[key]}</h3><Value value={model.record[key]} /></section>)}</details>}
      {!!catalogEntries.length && <details><summary>{t.catalogSummary} · {catalogEntries.length}</summary>{catalogEntries.map((entry, i) => <section key={i}>
        <h3>{entry.record?.id}</h3><Value value={entry.record?.summary} /><p className="muted">{entry.origin.pointer}</p>
        <p className="muted">{t.selectionNote}</p></section>)}</details>}
    </div>
  </section>;
}
function Detail({ node, index, graph, t, lang, select }) {
  const [relationPage, setRelationPage] = useState(0);
  const materialSection = useRef(null);
  const primary = ['summary', 'statement', 'action', 'note', 'description', 'scope', 'reasons', 'requires', 'completion'];
  const relations = index.adjacent.get(node.id);
  const chosen = graph.selections.filter(s => [s.component, s.model, s.subject, s.context, ...(Array.isArray(s.assessments) ? s.assessments : [])].includes(node.id));
  return <article className="detail">
    <span className="eyebrow">{typeLabel(node.type, lang)}</span><h2>{node.label}</h2>
    <Badges node={node} index={index} t={t} />
    {['follow_up', 'resolution', 'evidence'].includes(node.type) && <button className="materials-jump" onClick={() => materialSection.current?.scrollIntoView({ block: 'start' })}>{t.materials} ↓</button>}
    {primary.filter(key => node.record[key] != null).map(key => <section key={key}><h3>{t[key]}</h3><Value value={node.record[key]} /></section>)}
    <div ref={materialSection}><Materials node={node} index={index} select={select} t={t} /></div>
    {['method', 'provenance', 'model', 'assumptions', 'domains', 'limitations'].filter(key => node.record[key] != null).map(key =>
      <details key={key}><summary>{t[key] ?? typeLabel(key, lang)}</summary><Value value={node.record[key]} /></details>)}
    <section><h3>{t.relations} · {relations.length}</h3>
      {relations.slice(relationPage * PAGE, (relationPage + 1) * PAGE).map(edge => {
        const outgoing = edge.source === node.id;
        const other = index.nodes.get(outgoing ? edge.target : edge.source);
        return <div className="relation" key={edge.id}><button className="record-link" onClick={() => select(other.id)}>
          <small>{outgoing ? '→' : '←'} {edgeLabel(edge.type, lang)}</small><span>{other.label}</span></button>
          <details><summary>{t.edgeData}</summary><Value value={edge.data} /><Origin origin={edge.origin} index={index} t={t} /></details></div>;
      })}<Pager page={relationPage} total={relations.length} setPage={setRelationPage} t={t} />
    </section>
    <details><summary>{t.provenance}</summary><Origin origin={node.origin} index={index} t={t} /><Value value={node.ref} /></details>
    <details><summary>{t.selections} · {chosen.length}</summary><p>{t.selectionNote}</p>{chosen.length ? <Value value={chosen} /> : <p>{t.noSelections}</p>}</details>
    <details><summary>{t.raw}</summary><pre>{JSON.stringify(node, null, 2)}</pre></details>
  </article>;
}

function App() {
  const [lang, setLang] = useState(() => {
    try { return localStorage.getItem('mceg-viewer-language') === 'ja' ? 'ja' : 'en'; } catch { return 'en'; }
  });
  const t = translations[lang];
  const [graph, setGraph] = useState(null);
  const [filename, setFilename] = useState('');
  const [demo, setDemo] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [source, setSource] = useState('');
  const [filter, setFilter] = useState('all');
  const [page, setPage] = useState(0);
  const [id, setId] = useState(null);
  const [view, setView] = useState('records');
  const [materialsState, setMaterialsState] = useState({ filter: 'all', query: '', page: 0 });
  const [history, setHistory] = useState([]);
  const [nearPage, setNearPage] = useState(0);
  const [edgeId, setEdgeId] = useState(null);
  const input = useRef(null);
  const detailPanel = useRef(null);
  const request = useRef(0);
  const index = useMemo(() => graph ? indexGraph(graph) : null, [graph]);
  useEffect(() => { document.documentElement.lang = lang; try { localStorage.setItem('mceg-viewer-language', lang); } catch { /* optional preference */ } }, [lang]);
  const navigate = (next, nextSource = source, nextView = 'records') => {
    if (next !== id || nextSource !== source || nextView !== view) {
      setHistory(h => [...h.slice(-49), { id, source, view }]); setId(next); setSource(nextSource); setView(nextView); setNearPage(0); setEdgeId(null);
    }
  };
  const select = next => navigate(next);
  const openSource = sourceId => {
    const records = graph.nodes.filter(n => n.origin.source === sourceId);
    const entry = index.sources.get(sourceId)?.kind === 'catalog' || !sourceId ? null : records.find(n => n.type === 'model') ?? records[0];
    navigate(entry?.id ?? null, sourceId); setPage(0); setQuery(''); setFilter('all');
  };
  useEffect(() => { if (detailPanel.current) detailPanel.current.scrollTop = 0; }, [id]);
  async function load(file) {
    const token = ++request.current;
    setBusy(true); setError('');
    try {
      if (file && file.size > MAX_FILE) throw new Error('size');
      let text;
      if (file) text = await file.text();
      else { const response = await fetch(`${import.meta.env.BASE_URL}example-graph.json`); if (!response.ok) throw new Error('example'); text = await response.text(); }
      const value = validateGraph(JSON.parse(text));
      if (token !== request.current) return;
      setGraph(value); setFilename(file?.name ?? ''); setDemo(!file);
      setId(null); setView('records'); setMaterialsState({ filter: 'all', query: '', page: 0 });
      setHistory([]); setQuery(''); setSource(''); setFilter('all'); setPage(0); setNearPage(0); setEdgeId(null);
    } catch (e) { if (token === request.current) setError(e.message === 'size' ? 'size' : 'error'); }
    finally { if (token === request.current) setBusy(false); }
  }
  const sourceNodes = useMemo(() => graph ? scopedNodes(graph, index, source) : [], [graph, index, source]);
  const scoped = useMemo(() => sourceNodes.filter(n => !query || index.searchable.get(n.id).includes(query.toLocaleLowerCase())), [sourceNodes, index, query]);
  const filtered = scoped.filter(n => matchesCategory(n, index, filter));
  const node = index?.nodes.get(id);
  const overview = useMemo(() => contractOverview(node, index, graph?.selections), [node, index, graph]);
  const edge = graph?.edges.find(e => e.id === edgeId);
  const nearby = useMemo(() => index && id ? neighborhood(id, index, nearPage) : { nodes: [], edges: [], total: 0 }, [index, id, nearPage]);
  const flowNodes = useMemo(() => nearby.nodes.map((n, i) => ({
    id: n.id, data: { label: <><small>{typeLabel(n.type, lang)}</small><strong>{n.label}</strong></> },
    position: i === 0 ? { x: 340, y: 165 } : { x: i % 2 ? 0 : 680, y: Math.floor((i - 1) / 2) * 125 },
    sourcePosition: 'right', targetPosition: 'left', selected: n.id === id,
    style: { background: colors[n.type] ?? '#edf0f6' }, ariaLabel: `${typeLabel(n.type, lang)}: ${n.label}`,
  })), [nearby, id, lang]);
  const flowEdges = useMemo(() => nearby.edges.map((e, i) => ({ id: e.id, source: e.source, target: e.target,
    label: edgeLabel(e.type, lang), markerEnd: { type: MarkerType.ArrowClosed, color: '#8b829e' },
    style: { stroke: '#8b829e' }, type: 'smoothstep', pathOptions: { offset: 18 + i * 6 },
    ariaLabel: `${edgeLabel(e.type, lang)}: ${index.nodes.get(e.source).label} → ${index.nodes.get(e.target).label}`,
  })), [nearby, lang, index]);
  return <>
    <header><a className="brand" href="./"><span className="brand-icon">✿</span><span>MCEG <b>viewer</b><small>{t.tagline}</small></span></a>
      <div className="header-actions"><div className="language" aria-label="Language / 言語"><button aria-pressed={lang === 'en'} onClick={() => setLang('en')}>EN</button><button aria-pressed={lang === 'ja'} onClick={() => setLang('ja')}>日本語</button></div>
        <button className="primary" disabled={busy} onClick={() => input.current.click()}>{t.openFile}</button></div>
      <input ref={input} type="file" accept=".json,application/json" hidden onChange={e => { const file = e.target.files?.[0]; e.target.value = ''; if (file) load(file); }} />
    </header>
    <div className="messages" aria-live="polite">{busy && <p>{t.loading}</p>}{error && <p role="alert">{t[error]}</p>}</div>
    {!graph ? <main className="welcome"><div className="welcome-art" aria-hidden="true"><span>◇</span><i>····</i><span>✿</span><i>····</i><span>?</span></div><span className="eyebrow">MODEL CONTRACTS & EVIDENCE GRAPHS</span><h1>{t.intro}</h1><p>{t.introText}</p>
      <div className="welcome-actions"><button className="primary" disabled={busy} onClick={() => input.current.click()}>{t.openFile}</button><button disabled={busy} onClick={() => load(null)}>{t.demo} →</button></div>
      <p className="muted">{t.format}</p><code>mceg graph --package exogibbs &gt; graph.json</code><p className="muted">{t.local}</p></main> : <main className="workspace">
      <div className="dataset"><div><span className="eyebrow">{demo ? t.example : filename}</span><p>{demo ? t.exampleNote : t.local}</p></div><span className="count">{graph.nodes.length} {t.records}</span></div>
      <nav className="view-navigation" aria-label={t.navigation}>
        <button onClick={() => openSource('')} aria-current={view === 'records' && !id && !source ? 'page' : undefined}>{t.packageOverview}</button>
        <button onClick={() => navigate(null, source, 'materials')} aria-current={view === 'materials' ? 'page' : undefined}>{t.materialInventory}</button>
        {source && <span>{index.sources.get(source)?.path}</span>}
        <button disabled={!history.length} onClick={() => {
          const previous = history.at(-1); setId(previous.id); setSource(previous.source); setView(previous.view); setHistory(h => h.slice(0, -1));
          setNearPage(0); setEdgeId(null); setPage(0); setQuery(''); setFilter('all');
        }}>← {t.back}</button>
      </nav>
      <p className="scope-note">{t.scopeNote}</p>
      {view === 'materials' ? <MaterialInventory graph={graph} nodes={sourceNodes} index={index} source={source}
        changeSource={next => { navigate(null, next, 'materials'); setMaterialsState({ ...materialsState, page: 0 }); }}
        select={select} state={materialsState} setState={setMaterialsState} filename={filename || 'example-graph.json'} t={t} /> : <>
      {overview && <Overview key={overview.model.id} overview={overview} select={next => {
        select(next);
        detailPanel.current?.scrollIntoView({ block: 'start' });
        detailPanel.current?.focus({ preventScroll: true });
      }} t={t} lang={lang} />}
      <div className="panels"><aside className="browser panel"><label className="sr-only" htmlFor="search">{t.search}</label><input id="search" type="search" value={query} placeholder={t.search} onChange={e => { setQuery(e.target.value); setPage(0); }} />
        <label htmlFor="source">{t.source}</label><select id="source" value={source} onChange={e => openSource(e.target.value)}><option value="">{t.allSources}</option>{graph.sources.map(s => <option key={s.id} value={s.id}>{s.provider} · {s.path}{s.kind === 'catalog' ? ` (${t.catalogIndex})` : ''}</option>)}</select>
        <div className="filters">{['all', 'assessments', 'unknown', 'open', 'completed', 'evidence'].map(key => <button key={key} aria-pressed={filter === key} onClick={() => { setFilter(key); setPage(0); }}>{t[key]}<span>{scoped.filter(n => matchesCategory(n, index, key)).length}</span></button>)}</div>
        <div className="record-list">{filtered.slice(page * PAGE, (page + 1) * PAGE).map(n => <button className={`record-card ${n.id === id ? 'active' : ''}`} key={n.id} onClick={() => select(n.id)} aria-current={n.id === id ? 'true' : undefined}><small>{typeLabel(n.type, lang)}</small><strong>{n.label}</strong><span>{excerpt(n)}</span></button>)}{!filtered.length && <p className="muted">{graph.nodes.length ? t.empty : t.noData}</p>}</div>
        <Pager page={page} total={filtered.length} setPage={setPage} t={t} />
      </aside>
      {!node ? <PackageOverview key={source} graph={graph} index={index} sourceId={source} nodes={sourceNodes} matching={filtered} openSource={openSource} t={t} /> : <>
      <section className="graph-panel panel"><div className="graph-title"><div><h2>{t.graph}</h2><p>{t.graphHint}</p></div></div>
        <div className="canvas" onKeyDown={event => {
          if (event.key !== 'Enter' && event.key !== ' ') return;
          const record = event.target.closest('.react-flow__node');
          const relation = event.target.closest('.react-flow__edge');
          if (record || relation) event.preventDefault();
          if (record) select(record.dataset.id);
          else if (relation) setEdgeId(relation.dataset.id);
        }}><ReactFlow key={`${id}-${nearPage}`} nodes={flowNodes} edges={flowEdges} fitView minZoom={0.2} maxZoom={1.6} nodesDraggable={false} nodesConnectable={false} elementsSelectable deleteKeyCode={null}
          onNodeClick={(_, n) => select(n.id)} onEdgeClick={(_, e) => setEdgeId(e.id)}
          ariaLabelConfig={{ 'controls.zoomIn.ariaLabel': t.zoomIn, 'controls.zoomOut.ariaLabel': t.zoomOut, 'controls.fitView.ariaLabel': t.fit, 'node.a11yDescription.default': lang === 'ja' ? 'Tabで移動し、Enterで記録を開きます。' : 'Tab to a record and press Enter to open it.', 'node.a11yDescription.keyboardDisabled': lang === 'ja' ? 'Tabで移動し、Enterで記録を開きます。' : 'Tab to a record and press Enter to open it.', 'edge.a11yDescription.default': lang === 'ja' ? 'Enterで関係の詳細を開きます。' : 'Press Enter to inspect this relationship.' }}>
          <Background color="#ddd5e8" gap={22} /><Controls showInteractive={false} /></ReactFlow></div>
        <div className="graph-footer"><span>{nearby.total} {t.nearby}</span><Pager page={nearPage} total={nearby.total} setPage={setNearPage} t={t} /></div>
        {edge && <div className="edge-detail"><h3>{t.relation}: {edgeLabel(edge.type, lang)}</h3><button onClick={() => select(edge.source)}>{index.nodes.get(edge.source).label}</button> → <button onClick={() => select(edge.target)}>{index.nodes.get(edge.target).label}</button><Value value={edge.data} /><details><summary>{t.origin}</summary><Origin origin={edge.origin} index={index} t={t} /></details></div>}
      </section>
      <section ref={detailPanel} tabIndex={-1} className="detail-panel panel" aria-label={t.details}><Detail key={node.id} node={node} index={index} graph={graph} t={t} lang={lang} select={select} /></section></>}</div></>}
    </main>}
    <footer><span>MCEG viewer · 0.1</span><span>{t.untranslated}</span></footer>
  </>;
}

createRoot(document.getElementById('root')).render(<App />);
