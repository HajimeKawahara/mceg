import React from 'react';
import { safeUrl } from './graph.js';
import { doiFrom, doiInspection, inspectionState, materialReport, searchLinks } from './literature.js';
import { InspectionBadge, InspectionScope } from './Inspection.jsx';
import './print.css';

function PrintLocator({ value, node, index, numbers, citations, t }) {
  const doi = doiFrom(value);
  const url = doi ? `https://doi.org/${doi}` : safeUrl(value);
  const citation = citations.get(doi);
  const searches = searchLinks(citation ? `${citation.title} ${citation.authors.join(' ')} ${citation.year} ${doi}` : doi ?? value);
  const review = doi ? doiInspection(node, value, index) : null;
  const related = review?.records.filter(n => n.id !== node.id && numbers.has(n.id)) ?? [];
  return <div className="print-locator">
    {citation && <div className="print-citation"><b>{citation.title}</b>
      <p>{[citation.authors.join(', '), citation.year, citation.journal, citation.volume, citation.pages].filter(Boolean).join(' · ')}</p>
      <small>{t.metadataFrom}</small></div>}
    {url ? <a href={url}>{doi ? `DOI: ${doi}` : value}</a> : <span>{value}</span>}
    {doi && <>
      <div className="print-search"><a href={searches.google}>Google</a> · <a href={searches.scholar}>Google Scholar</a></div>
      <p>{review.guidance === 'related' ? t.checkOtherInspections : t.downloadGuidance[review.guidance]}</p>
      {!!related.length && <p>{t.inspectionRecords}: {related.map((record, i) => <React.Fragment key={record.id}>{i > 0 && ' · '}
        <a href={`#material-${numbers.get(record.id)}`}>[{numbers.get(record.id)}] {record.label} ({t.inspectionStates[inspectionState(record)]})</a>
      </React.Fragment>)}</p>}
    </>}
  </div>;
}

export default function MaterialPrint({ entries, index, filename, source, state, citations, created, t }) {
  const report = materialReport(entries, index);
  const sources = [...new Set(report.all.map(e => e.node.origin.source))].map(id => index.sources.get(id));
  const printEntry = ({ node, state: inspection, locators }) => {
    const number = report.numbers.get(node.id);
    const origin = index.sources.get(node.origin.source);
    return <article className="print-material" id={`material-${number}`} key={node.id}>
      <h2>[{number}] {node.label}</h2><InspectionBadge state={inspection} t={t} />
      <p className="print-origin">{origin.provider} · {origin.path} · JSON Pointer: {node.origin.pointer || '""'}</p>
      <p>{node.record.summary ?? node.record.action ?? node.record.description}</p>
      <InspectionScope node={node} t={t} />
      {!locators.some(doiFrom) && <p>{t.downloadGuidance[inspection]}</p>}
      <h3>{t.sources}</h3>
      {locators.map(value => <PrintLocator key={value} value={value} node={node} index={index} numbers={report.numbers} citations={citations} t={t} />)}
    </article>;
  };
  return <main className="material-print">
    <div className="print-cover"><span className="eyebrow">MCEG viewer</span><h1>{t.materialInventory}</h1>
      <p>{filename} · {created}</p>
      <dl><dt>{t.source}</dt><dd>{source ? `${index.sources.get(source).provider} · ${index.sources.get(source).path}` : t.allSources}</dd>
        <dt>{t.inspection}</dt><dd>{state.filter === 'all' ? t.allMaterials : t.inspectionStates[state.filter]}</dd>
        {state.query && <><dt>{t.materialSearch}</dt><dd>{state.query}</dd></>}
        <dt>{t.printIncluded}</dt><dd>{entries.length} {t.inspectionRecordCount}</dd></dl>
      <p>{t.inventoryHint}</p><p>{t.printLinksNote}</p><p>{t.sameDoiScope}</p>
      {!!report.appendix.length && <p>{t.printAppendixNote} ({report.appendix.length})</p>}
      <ol className="print-contents">{entries.map(entry => <li key={entry.node.id}>
        <a href={`#material-${report.numbers.get(entry.node.id)}`}>{entry.node.label}</a> — {t.inspectionStates[entry.state]}
      </li>)}</ol>
    </div>
    <section className="print-results">{entries.map(printEntry)}</section>
    {!!report.appendix.length && <section className="print-appendix"><h1>{t.printAppendix}</h1><p>{t.printAppendixNote}</p>{report.appendix.map(printEntry)}</section>}
    <section className="print-snapshots"><h1>{t.provenance}</h1><p>{t.sourceNote}</p>
      {sources.map(origin => <div key={origin.id}><h2>{origin.provider} · {origin.path}</h2><p>SHA-256: {origin.sha256}</p></div>)}
    </section>
  </main>;
}
