import React, { useEffect, useRef, useState } from 'react';
import { safeUrl } from './graph.js';
import { doiFrom, sourceLocators, relatedMaterials, parseCitation, searchLinks } from './literature.js';

const citations = new Map();
function Locator({ value, t }) {
  const doi = doiFrom(value);
  const [citation, setCitation] = useState(() => citations.get(doi));
  const [status, setStatus] = useState('');
  const controller = useRef(null);
  useEffect(() => () => controller.current?.abort(), []);
  const url = doi ? `https://doi.org/${doi}` : safeUrl(value);
  const searches = searchLinks(citation ? `${citation.title} ${citation.authors.join(' ')} ${citation.year} ${doi}` : doi ?? value);
  async function lookup() {
    if (citations.has(doi)) { setCitation(citations.get(doi)); return; }
    controller.current = new AbortController();
    const signal = controller.current.signal;
    const timeout = setTimeout(() => controller.current?.abort(), 10000);
    setStatus('loading');
    try {
      const response = await fetch(`https://api.crossref.org/works/${encodeURIComponent(doi)}`, { signal, credentials: 'omit', referrerPolicy: 'no-referrer' });
      if (!response.ok) throw new Error('Lookup failed');
      const value = parseCitation(await response.json(), doi);
      citations.set(doi, value); setCitation(value); setStatus('');
    } catch { setStatus('error'); }
    finally { clearTimeout(timeout); }
  }
  return <div className="locator">
    {citation && <div className="citation"><strong>{citation.title}</strong><p>{citation.authors.join(', ')}{citation.year && ` (${citation.year})`}</p>
      <p>{[citation.journal, citation.volume, citation.pages].filter(Boolean).join(', ')}</p><small>{t.metadataFrom}</small></div>}
    {url ? <a href={url} target="_blank" rel="noopener noreferrer">{doi ? `DOI: ${doi}` : value} ↗</a> : <span className="prose">{value}</span>}
    <div className="locator-actions">
      {doi && !citation && <button disabled={status === 'loading'} onClick={lookup}>{status === 'loading' ? t.lookupLoading : t.lookupCitation}</button>}
      {(doi || (!url && !/^(?:urn:|[./]|.*\.(?:json|yaml|py|xml|log)$)/i.test(value))) && <>
        <a href={searches.google} target="_blank" rel="noopener noreferrer">Google ↗</a>
        <a href={searches.scholar} target="_blank" rel="noopener noreferrer">Google Scholar ↗</a></>}
    </div>
    {status === 'error' && <p role="status" className="muted">{t.lookupError}</p>}
  </div>;
}

function Locators({ node, t }) {
  return <div>{sourceLocators(node).map(value => <Locator key={value} value={value} t={t} />)}</div>;
}

export default function Materials({ node, index, select, t }) {
  const [page, setPage] = useState(0);
  const related = relatedMaterials(node, index);
  const hasOwn = sourceLocators(node).length > 0;
  if (!hasOwn && !related.length && !['follow_up', 'resolution', 'evidence'].includes(node.type)) return null;
  return <section className="materials" aria-label={t.materials}>
    <h3>{t.materials}</h3><p className="muted">{t.materialsHint}</p>
    {hasOwn && <div className="direct-materials"><h4>{t.directMaterials}</h4><Locators node={node} t={t} /></div>}
    {!hasOwn && !related.length && <p>{t.noMaterials}</p>}
    {!!related.length && <><h4>{t.relatedMaterials} · {related.length}</h4><p className="muted">{t.materialsScope}</p>
      {related.slice(page * 3, (page + 1) * 3).map(item => <article className="material-card" key={item.node.id}>
        <span className="eyebrow">{item.viaCompletion ? t.completionEvidence : t.linkedEvidence}</span>
        <button className="record-link" onClick={() => select(item.node.id)}><strong>{item.node.label}</strong></button>
        <p>{item.node.record.summary ?? item.node.record.action}</p>
        {item.node.record.provenance?.inspection && <span className="badge">{t.inspection}: {item.node.record.provenance.inspection}</span>}
        {item.node.record.provenance?.location && <p><b>{t.readLocation}: </b>{item.node.record.provenance.location}</p>}
        <Locators node={item.node} t={t} />
        <details><summary>{t.scopeAndPath}</summary><p>{item.node.record.scope}</p><p>{item.node.record.provenance?.note}</p>
          <nav aria-label={t.tracePath}>{item.path.map((id, i) => <React.Fragment key={id}>{i > 0 && ' › '}<button onClick={() => select(id)}>{index.nodes.get(id).label}</button></React.Fragment>)}</nav></details>
      </article>)}
      {related.length > 3 && <nav className="pager" aria-label={t.materials}><button disabled={!page} onClick={() => setPage(page - 1)}>{t.previous}</button>
        <span>{page * 3 + 1}–{Math.min((page + 1) * 3, related.length)} / {related.length}</span>
        <button disabled={(page + 1) * 3 >= related.length} onClick={() => setPage(page + 1)}>{t.next}</button></nav>}
    </>}
  </section>;
}
