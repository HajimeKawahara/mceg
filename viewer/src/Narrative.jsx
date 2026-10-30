import React from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { narrativeEvidence, safeUrl } from './graph.js';

// Author-written prose only. No HTML, remote images, file fetching or inferred
// scientific content. Evidence links resolve within this exact source snapshot.
export default function Narrative({ text, overview, select, t }) {
  const heading = ({ children }) => <h3>{children}</h3>;
  return <div className="narrative"><Markdown remarkPlugins={[remarkGfm]} skipHtml
    components={{
      h1: heading, h2: heading, h3: heading, h4: heading, h5: heading, h6: heading,
      img: ({ alt }) => <span className="muted">{alt}</span>,
      table: ({ children }) => <div className="narrative-table"><table>{children}</table></div>,
      a: ({ href, children }) => {
        const target = narrativeEvidence(href, overview.evidence);
        if (target) return <button className="narrative-link" onClick={() => select(target.id)}>{children} ↗</button>;
        if (href?.startsWith('#evidence/')) return <span className="missing-reference">{children} ({t.missingReference})</span>;
        const url = safeUrl(href);
        return url ? <a href={url} target="_blank" rel="noopener noreferrer">{children} ↗</a> : <span>{children}</span>;
      },
    }}>{text}</Markdown></div>;
}
