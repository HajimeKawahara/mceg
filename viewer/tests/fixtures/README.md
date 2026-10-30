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
