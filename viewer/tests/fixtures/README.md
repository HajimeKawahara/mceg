# Graph API fixture

`exogibbs-graph.json` is a saved Graph JSON API export of the ExoGibbs packaged
catalog, record version `2026-10-30`, captured for the Viewer overview regression
test. It includes the curated-gas and FastChem HCN follow-up contracts, so tests
can check source switching and ensure that judgments from different contracts
are not combined. Source paths, SHA-256 values, selections and record text are
preserved by the exporter. The numerical study remains the archived 2026-10-28
study; the later catalog adds an authored comparison brief to the description.

Generated from an ExoGibbs checkout with:

```bash
mceg graph --catalog /path/to/exogibbs/src/exogibbs/data/mceg/index.json > exogibbs-graph.json
```

Tests read only this fixture. ExoGibbs, Python and network access are not required
to run the Viewer tests. This fixture is not included in the production bundle.

`exoeos-graph.json` is a reduced snapshot of the user's ExoEOS package graph
(catalog record version `2026-10-30`), retaining the Ma Fe-Si-O and Zhang-Duan H2
contracts, their nodes/edges and explicit catalog entries. Other contracts and
selections were omitted to keep the fixture small. Original identities, source
hashes, origins and historical records were retained; the catalog hash identifies
the original full index rather than a regenerated subset. This fixture exercises
package landing, catalog selection, pending empirical review and completed
primary-source inspections without requiring ExoEOS or downloading papers.
Browser citation tests mock Crossref responses, including failure, to remain
deterministic; they do not fetch external literature.
