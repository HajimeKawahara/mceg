# MCEG Viewer

A small, read-only interface for humans to inspect model contracts, evidence,
scoped judgments and unfinished investigation work. English / 日本語 can be
switched in the header. Authored scientific text always stays in its original
language.

## Run locally

Requires Node.js 22.12+ and npm. From this directory:

```bash
npm ci
npm run dev
```

Open the printed local URL. Choose **Explore example** / **サンプルを見る** to
inspect the saved H₂ solubility example, or **Open graph JSON** /
**グラフJSONを開く** to read your own export (up to 20 MiB).

Export from a provider environment where MCEG is installed:

```bash
mceg graph --package exogibbs > graph.json
mceg graph --catalog path/to/mceg/index.json > graph.json
mceg graph path/to/contract.yaml > graph.json
mceg graph --case path/to/case.yaml > graph.json
```

For an ExoEOS or ExoGibbs checkout, use its contract or catalog path. The viewer
does not import or execute either provider. JSON files are read in browser
memory, not uploaded or persisted. Only the interface language is saved locally.
Reloading the page requires opening the file again. Clicking an external HTTP(S)
source link opens that site in a new tab; local paths remain recorded text.

## Static hosting

Build on your computer, starting from the MCEG repository root:

```bash
cd viewer
npm ci
npm run build
```

Upload **the entire contents of `viewer/dist/`** to a public directory on an
HTTP(S) server, preserving the directory structure:

```text
mceg-viewer/
├── index.html
├── assets/
│   ├── index-<hash>.js
│   └── index-<hash>.css
└── example-graph.json
```

Open the corresponding URL, for example `https://example.org/mceg-viewer/`.
Relative asset paths support hosting in a subdirectory. Upload the complete
new build when updating, including the hashed files in `assets/`.

The server only serves static files; it needs no PHP, Node.js, Python or MCEG
installation. Node.js is required on the build machine. The UI, graph inspection,
language switching and PDF printing run in the visitor's browser. Optional
Crossref citation lookup still uses the external API after a click.

To preview the production build locally, run `npm run preview` from `viewer/`
and open the printed URL. This is a local check; a deployed static site does
not require a running Vite process.

The build includes the H₂ example. Visitors use **Open graph JSON** to read
their own files locally; a graph previously opened during development is not
embedded in the build. Publishing a specific graph as the initial view would
require a separate data-loading feature.

静的サーバーで公開する場合は、`viewer/` で `npm run build` を実行し、生成された
`dist/` の中身をすべてアップロードしてください。`index.html` だけでなく
`assets/` と `example-graph.json` も必要です。サーバーにPHP・Node.js・Python・MCEGを
導入する必要はありません。アクセス後に「グラフJSONを開く」から閲覧データを選べます。
読み込んだJSONはブラウザー内で処理され、PDF保存も利用できます。

## How to investigate / 調査の進め方

Every import opens **Package overview** / **全体を見る**, listing contracts and
counts of records and open/completed FollowUps. No model is selected implicitly.
Choose a contract card or use search and the record filters; **Package overview**
returns to the collection, and **Back** restores the prior record/source view.
Contract cards are paged six at a time. Their counts describe the whole source
snapshot, while search/filtering determines which cards match.

Choosing a catalog source such as `index.json` also shows a collection view.
Catalogs have selections rather than record nodes: the viewer follows their
explicit `catalog_record` selections to the referenced contract snapshots and
lists the corresponding records. Catalog entries remain individually inspectable
even when multiple entries select the same contract. Index version, provider,
distribution and hash remain accessible.

JSONを開くと最初に「全体を見る」が表示されます。`index.json` は契約を束ねる
カタログの入口として扱い、登録された契約を一覧表示します。契約カードを選ぶと
概要とグラフへ進み、「全体を見る」で戻れます。

After selecting a record, read **About this contract** / **この契約について** above the graph. It
shows the selected record's owning Model name and authored description, including
comparison tables and evidence links when the author supplies them. Open
**Judgments & next steps** for one excerpt each for recorded support, unknown
judgments/domains and pending FollowUps. Expand each group for the remaining
records; click an excerpt to inspect its authored record and evidence.
Completed FollowUps, assumptions/domains/limitations
and catalog summaries are available in separate disclosures.

This overview uses only the selected source snapshot, including when browsing a
multi-contract catalog. Choosing a contract/source also opens its Model; following
a link to another contract updates the overview. Excerpts are authored text, not
generated conclusions. Historical assessments are kept individually, completed
FollowUps are excluded from next steps, and an empty group does not imply that
the science is settled. Catalog summaries remain separate for each explicit
catalog selection. As elsewhere, changing UI language does not translate records.

グラフの上の「この契約について」には、記録者が書いた比較対象・差・資料・
未解明点の説明を表示します。「評価と次の作業を見る」を開くと、各欄にまず1件ずつ
表示し、残りは展開できます。説明中の証拠リンクや項目から元の記録へ進めます。

### Author a useful investigation brief

The existing `model.description` is the entry point for a human reader. A generic
workflow sentence (for example, “separate numerical and physical validation”)
does not explain the particular investigation. Record, in this order:

1. The question and the exact alternatives: species/isomer, dataset/revision,
   energy anchor, thermal functions and reported versus verified source identity.
2. The discrepancy: quantity, numerator/denominator, units, conditions and sample
   coverage. Keep equilibrium-constant and abundance differences separate; name
   whether the solver is shared. Do not turn database agreement into accuracy.
3. The source documents and saved comparison records, with links to Evidence.
4. What is unresolved, including hypotheses that have not been established.

Descriptions can be ordinary text or Markdown with tables. For example:

```yaml
model:
  # Other required Model fields omitted here.
  description: |
    Why do these two inputs disagree under the recorded conditions?

    | Input | Source and scope |
    | --- | --- |
    | Dataset A, pinned revision | Producer-reported source; input not reconstructed |
    | Dataset B, pinned revision | Inspected reference; not assumed physical truth |

    See the [source audit](#evidence/source_audit) for inspected source versions
    and the remaining uncertainty.
```

`#evidence/ID` is a Viewer navigation convention pointing to the Evidence's local
ID in the same source snapshot (URL-encode the ID if needed). It does not add a
scientific support/provenance edge. Keep formal references in the existing
Evidence/Assessment records. Unresolved links are marked visibly. HTTP(S) links
open only when clicked; embedded images and HTML are not loaded or executed.
Rendering uses [react-markdown](https://github.com/remarkjs/react-markdown) with
GFM tables, no raw HTML, and explicit link handling.

The viewer cannot recover a comparison brief from missing records or external
artifact contents. It displays the authored text without synthesizing one from
IDs or status counts. This requires no MCEG schema extension or Viewer dependency
in the provider. After editing a provider contract, regenerate its packaged
catalog and export a fresh graph so the description and source hashes agree.

1. Search for a species (for example `HCN`), record ID, or phrase. Optionally
   filter by contract/source. Search includes record bodies and references.
2. Inspect **Recorded judgments** and **Unknown judgments** to read the stated
   outcome, reasons, and connected target revision, Subject and Context.
3. Open **Open follow-ups** to see next actions, required material and completion
   criteria. **Completed work** shows FollowUps with an explicit Resolution edge
   and Resolution records themselves.
4. Click neighboring nodes or the detail panel's connection buttons to trace
   evidence, comparisons, and upstream sources. **Back** returns to the previous
   record. Nodes and edges also open with Enter or Space when keyboard focused.
5. Expand **Source snapshot** for the provider, path, SHA-256 and RFC 6901 JSON
   Pointer. Expand **Full record JSON** to inspect every field, including fields
   not given a dedicated presentation. **Explicit selections** preserves catalog
   and case choices separately.

日本語では、検索欄に化学種や調査したい語を入力し、「記録された評価」
「不明とされた判断」「未解決の作業」「完了した作業」から記録を選びます。
グラフまたは詳細欄の「つながり」をクリックすると、証拠・対象・条件を
たどれます。「出典のスナップショット」で契約の場所とハッシュを、
「記録のJSON全文」で全項目を確認できます。

### Find literature for pending and completed work

The detail panel's **Papers & materials** / **文献・資料を探す** button jumps to
source locators, citation lookup and Google/Google Scholar searches. FollowUp
sources are visible without opening raw JSON. Evidence and Resolution records
provide the same entry point, including recorded artifact locators.

For pending FollowUps the viewer follows the exact target, incoming assessments
of that target revision, their cited evidence and upstream `derived_from` links.
For completed FollowUps and Resolutions it follows the explicit completion
evidence and upstream sources; it does not expand the resolved target's other
assessments. It does not expand model containment, shared Subjects/Contexts, or
sideways from shared evidence into other investigations. A trace back to the
selected record is available for every linked material. Related materials are
paged three at a time.

Each record retains its own inspection status, page/equation location, scope,
retrieval notes and source URLs. An old failed retrieval and a later supplied
paper remain distinct records. A recorded PDF URL is not a guarantee that it is
currently accessible; a supplied-file SHA-256 URN is not a public download link.
For supplements, inspect the record's description/location to distinguish the
supplement from the main article. A shared DOI alone does not equate these files.

Every DOI shows **Inspection recorded in MCEG**, with download guidance:

- **Not inspected**: obtain the specified article or supplement if needed and
  not already available, then inspect the recorded scope.
- **Partially inspected**: inspect the remaining scope; obtain missing material.
- **Inspected (recorded scope)**: no new download is required for that recorded
  inspection. Obtain it to verify the document yourself or extend the inquiry.
- **Inspection not recorded**: check whether the material has been read before
  deciding what to obtain. A citation or inspected implementation is not itself
  a literature inspection.

These states come from literature Evidence `provenance.inspection`. DOI entries
also link to other literature records for the same DOI **within the same source
snapshot**. For a FollowUp citation this is labelled as related inspection, not
as the task's own status. If inspected or partially inspected scopes exist,
download guidance asks the reader to compare those scopes first. This discovery
does not imply a provenance edge, a shared scope, or completion of a task. Older
not-inspected records keep their original state, including when a later supplied
document has been inspected. The viewer cannot determine which PDFs are on the
reader's computer.

Open **Materials list** / **資料一覧** in the top navigation to browse these
states across the package or a selected contract/catalog. The list includes
literature Evidence and otherwise uncovered DOI citations. Filter by inspection
state or search DOI, description and scope; four records appear per page. Counts
refer to records, not unique papers or outstanding downloads. Main articles,
supplements, historical attempts and records without inspection metadata remain
separate. Open a record to inspect its graph; **Back** returns to the list with
its filters and search preserved.

### Save a linked materials PDF

In **Materials list**, choose the source, search and inspection filter, then
click **Save as PDF**. Select **Save as PDF** in the browser's print dialog
(tested with Chrome). The report contains **all matching records**, including
rows on other pages. Clear the filters to export the whole package. The report
uses the current interface language; authored text stays in its original language.

The A4 report includes a linked contents list, inspection states, scope, reading
locations, notes, download guidance, source paths, JSON Pointers and snapshot
hashes. DOI, PDF/web and Google/Scholar links remain clickable. Related reviews
of the same DOI outside the selected filters appear in a separate appendix, so
a historical failed retrieval does not hide a later inspected document. Internal
links jump between those records within the PDF. Counts describe selected
records; appendix records are listed separately. If an appendix record cites
another DOI, its review context is included as well, within the same contract
snapshot.

Citation metadata already retrieved in this browser session is included. PDF
export does not fetch metadata, download papers or upload graph data. Local paths
and SHA-256 URNs stay plain text; referenced documents are not embedded in the
PDF. Saving or cancelling printing preserves the list's filters and page.

「資料一覧」で必要なら契約・確認状態・検索語を絞り込み、「PDFに保存」を押して、
ブラウザーの印刷画面からPDFとして保存できます。画面の4件だけでなく、絞り込みに
一致する全件を出力します。DOI・PDF・検索リンクと、PDF内の確認記録へのリンクを
利用できます。取得済みの書誌情報、確認状態、読む箇所、入手案内も収録します。
全資料を出力するときは絞り込みを解除してください。

Graph snapshots often contain DOIs without full titles/authors. **Look up
citation** fetches title, authors, publication year and journal information from
the [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)
only after a click, sending just that DOI. Results are checked against the
requested DOI and kept in browser memory; they are labelled external metadata,
not source inspection or a new scientific assessment. DOI and Google/Scholar
links remain usable if Crossref has no record or the lookup fails. Search links
send the displayed DOI/citation to the selected search engine when clicked.
Nothing is fetched automatically and no provider files or project text are sent
by citation lookup. Bibliographic data is not written back into the graph.

未解決・完了作業の詳細から「文献・資料を探す」で、DOI・PDF等のリンクと、
関連記録に残された読む箇所を確認できます。「書誌情報を取得」を押すと、そのDOI
だけをCrossrefへ送り、論文名・著者・年・掲載誌を表示します。Google／Scholar
への検索リンクも利用できます。完了作業では、Resolutionの完了根拠をたどります。
必要な文献自体が記録されていない場合は推測せず、提供元の追記が必要だと表示します。

上部の「資料一覧」から「未確認」「一部確認」「確認済み」「確認状態の記録なし」で
絞り込めます。各DOIのそばにはMCEGの記録に基づく確認状態と、入手・再ダウンロードの
案内を表示します。「確認記録と対象範囲を見る」で、同じ契約内の同一DOIについて
本文・補足資料のどの箇所を確認したかたどれます。過去の未確認記録が残っていても、
確認済み範囲が見つかれば、追加で必要な資料かを先に確認するよう案内します。
書誌情報の取得だけで「確認済み」にはなりません。

Record lists, connections and graph neighbors are paged in groups of eight.
The graph shows one selected record and up to eight immediate neighbors; the
neighbor pager exposes the rest. Search and source filters affect the list,
not the selected record's graph: following a link can cross those filters.
The graph is a local relationship view, not an automatically inferred
investigation scope. Two records citing the same source need not answer the
same question.

## Interpretation boundaries

- Recorded support, numerical execution results, membership classifications and
  source inspection states retain separate labels. No overall validity score is
  calculated. An absent judgment is not automatically called `unknown`.
- **Unknown judgments** selects explicit top-level `status: unknown` or
  `classification: unknown`. Other gaps, including unknown Model domains, remain
  visible in the original fields and searchable text; this is not an exhaustive
  scientific gap detector.
- Completing a FollowUp does not promote a Claim or an Assessment to supported.
  Counts describe records, not independent findings. The sidebar's completed
  record count includes resolved FollowUps and Resolution records. Package and
  contract cards count completed FollowUps once and label that distinction.
- Historical and differently scoped Assessments remain separate. The viewer
  does not select the latest revision or combine catalog/case selections.
- Hashes identify saved source bytes; the viewer does not reopen local files,
  reverify hashes, fetch papers, or rerun scientific calculations. Export a new
  snapshot after changing a provider's records.
- Node and edge IDs are opaque snapshot identities. Unfamiliar types remain
  available with their original names and JSON. Relationships preserve their
  direction, data and origins, including parallel edges.

## Architecture and UI choice

`viewer/` is a standalone npm project with its own source, lockfile, example,
tests and build output. It can be copied into a separate repository. Its only
MCEG runtime contract is `mceg_graph_v1`; it has no Python dependency, no imports
from `../src`, no backend, and no root npm workspace requirement. The Python
package does not depend on or package the viewer.

React + Vite + React Flow provide a compact, static client. React Flow was chosen
for clickable records, pan/zoom, React detail panels and
[keyboard accessibility](https://reactflow.dev/learn/advanced-use/accessibility).
[Cytoscape.js](https://js.cytoscape.org/) is a useful alternative if future work
needs large-network analysis and graph algorithms. This first version prioritizes
reading a small neighborhood, so a deterministic two-column neighborhood layout
avoids introducing an additional layout engine. A full-network overview,
automatic investigation synthesis, edits, and live synchronization are deferred
until actual ExoEOS/ExoGibbs usage clarifies their value.

The lavender, mint, rose and cream palette distinguishes record types without
using color as the sole status indicator. On smaller screens the list, graph
and detail panel stack vertically. Long record bodies and raw JSON are revealed
on demand.

## Build and test

```bash
npm test
npm run build
npm run preview
```

`dist/` is a static site with relative asset paths; serve it over HTTP. All
dependencies and CSS are bundled locally; no external font or asset CDN is used.

Browser checks (first install a browser, or use an existing Chrome executable):

```bash
npx playwright install chromium
npm run test:browser
# Linux alternative using installed Chrome:
MCEG_VIEWER_CHROME=/usr/bin/google-chrome npm run test:browser
```

Tests cover Graph API compatibility, malformed imports, completion semantics,
bounded navigation, unsafe source locators, file loading, bilingual controls,
keyboard navigation and mobile overflow. Browser screenshots go to ignored
`test-results/`.

The bundled `public/example-graph.json` is generated from MCEG's existing
`examples/v02/h2_solubility.yaml`, not a fictional HCN investigation. To regenerate
it from an MCEG checkout (not required to build or use the viewer):

```bash
PYTHONPATH=src python -m mceg graph examples/v02/h2_solubility.yaml --provider mceg > viewer/public/example-graph.json
```

Run that command from the checkout root. The source path/hash in the snapshot
records its provenance. The viewer and bundled example use the repository's
MIT license (a copy is included in this directory for future extraction).
