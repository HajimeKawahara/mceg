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

## How to investigate / 調査の進め方

Start with **About this contract** / **この契約について** above the graph. It
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
  Counts describe records, not independent findings. Completed counts include
  both resolved FollowUps and their Resolution records.
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
