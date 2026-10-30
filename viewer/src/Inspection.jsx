import React from 'react';
import { inspectionState, isLiterature, sameDoiRecords } from './literature.js';

export function InspectionBadge({ state, t }) {
  return <span className={`badge inspection-badge ${state}`}>{t.inspectionStates[state]}</span>;
}

export function InspectionScope({ node, t }) {
  return <>
    {node.record.provenance?.location && <p><b>{t.readLocation}: </b>{node.record.provenance.location}</p>}
    {node.record.scope && <p><b>{t.scope}: </b>{node.record.scope}</p>}
    {node.record.provenance?.note && <p>{node.record.provenance.note}</p>}
  </>;
}

export default function DoiInspection({ node, value, index, select, t }) {
  const own = isLiterature(node);
  const state = inspectionState(node);
  const others = sameDoiRecords(node, value, index);
  const inspected = others.some(n => inspectionState(n) === 'inspected');
  const partial = others.some(n => inspectionState(n) === 'partial');
  const records = (own ? [node, ...others] : others).sort((a, b) => {
    const order = { inspected: 0, partial: 1, not_inspected: 2, unknown: 3 };
    return order[inspectionState(a)] - order[inspectionState(b)];
  });
  // Related reviews help the reader find material; they never promote this
  // record, resolve its task, or conflate the main article and supplement.
  const linkedState = inspected ? 'inspected' : partial ? 'partial' : others.some(n => inspectionState(n) === 'not_inspected') ? 'not_inspected' : 'unknown';
  const guidance = own && state === 'inspected' ? t.downloadGuidance.inspected : inspected || partial
    ? t.checkOtherInspections : t.downloadGuidance[own ? state : linkedState];
  return <div className="doi-inspection">
    <div><small>{t.recordedInspection}</small>{own || !records.length
      ? <InspectionBadge state={state} t={t} />
      : <span className="badge inspection-badge linked">{t.linkedInspectionStates[linkedState]}</span>}</div>
    <p className="download-guidance">{guidance}</p>
    {!!records.length && <details><summary>{t.inspectionRecords} · {records.length}</summary>
      <p className="muted">{t.sameDoiScope}</p>
      {records.map(record => <div className="inspection-record" key={record.id}>
        <InspectionBadge state={inspectionState(record)} t={t} />
        <button className="record-link" onClick={() => select(record.id)}>{record.label}</button>
        <p>{record.record.summary}</p><InspectionScope node={record} t={t} />
      </div>)}
    </details>}
  </div>;
}
