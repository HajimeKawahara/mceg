import { validateGraph } from './graph.js';

export function readSnapshot() {
  const element = document.getElementById('mceg-snapshot');
  if (!element) return {};
  try {
    const snapshot = JSON.parse(element.textContent);
    return { graph: validateGraph(snapshot.graph), filename: String(snapshot.filename ?? ''),
      demo: snapshot.demo === true, lang: snapshot.lang === 'ja' ? 'ja' : 'en' };
  } catch { return { error: 'error' }; }
}

export async function saveHtml(snapshot) {
  let script = document.getElementById('mceg-script')?.textContent;
  let style = document.getElementById('mceg-style')?.textContent;
  if (script === undefined) {
    const response = await fetch(`${import.meta.env.BASE_URL}viewer-export.json`);
    if (!response.ok) throw new Error('export');
    ({ script, style } = await response.json());
  }
  if (typeof script !== 'string' || typeof style !== 'string') throw new Error('export');
  // Keep authored strings inside inert JSON, including HTML closing tags.
  const data = JSON.stringify(snapshot).replace(/</g, '\\u003c');
  const html = `<!doctype html>
<html lang="${snapshot.lang === 'ja' ? 'ja' : 'en'}">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="#f7f4fb"><title>MCEG Viewer</title>
<style id="mceg-style">${style.replace(/<\/style/gi, '<\\/style')}</style></head>
<body><div id="root"></div>
<script id="mceg-snapshot" type="application/json">${data}</script>
<script id="mceg-script" type="module">${script.replace(/<\/script/gi, '<\\/script')}</script>
</body></html>`;
  const url = URL.createObjectURL(new Blob([html], { type: 'text/html;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = `${(snapshot.filename || 'example-graph.json').replace(/\.json$/i, '')}.html`;
  document.body.append(link);
  try { link.click(); }
  finally { link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
}
