# Generate RST and build models and evidence

MCEG generates reStructuredText and CSS from saved contracts and explicitly
selected calculation cases. The consuming repository owns its Sphinx build,
theme, CI and HTML publication. Source generation needs only MCEG's core
requirements; it does not import Sphinx or scientific providers, run numerical
calculations, retrieve papers or create assessments.

For programmatic access to the same recorded relationships, use the
[Graph JSON API](graph.md). The documentation renderer adds presentation labels
and links to the shared graph construction.

## Generate sources

Run this from a provider repository containing `mceg/docs.yaml`:

```bash
python -m mceg docs --config mceg/docs.yaml
```

The installed `mceg docs` command is equivalent. The default configuration path
is `mceg/docs.yaml`. All paths within the configuration resolve from that file,
regardless of the working directory used to invoke the command.

For example, ExoGibbs uses:

```yaml
source_root: ../documents
output: ../documents/mceg/_generated
contracts:
  - provider: exogibbs
    root: ..
    paths:
      - mceg/contracts/*.yaml
cases:
  - ../examples/comparisons/mceg/h2-solubility.yaml
```

`contracts` supplies provider checkouts and explicit files or glob patterns.
Unmatched patterns fail. `cases: []` produces a catalog without calculations.
Contracts selected by cases also enter the catalog. Provider aliases must refer
to the same checkout throughout a build. The default case filename is arbitrary;
use another explicit file to describe a different calculation.

The output must be a dedicated directory inside `source_root`. Generated pages
are `.rst`; the stylesheet is `_static/mceg.css` under the output directory.
Ignore the entire generated directory in Git. Its `.mceg-generated.json`
manifest tracks owned files: regeneration removes obsolete owned pages and
refuses to overwrite unrelated files. Existing manifest-tracked MyST pages are
removed when switching to RST. Never edit generated files directly.

## Build HTML in the consuming repository

Install Sphinx, the repository's documentation dependencies and Graphviz
(`dot` on PATH). Append these settings to its existing `conf.py`:

```python
extensions += ["sphinx.ext.graphviz"]
graphviz_output_format = "svg"
html_static_path += ["mceg/_generated/_static"]
html_css_files = ["mceg.css"]  # Preserve any existing stylesheets too.
```

Include the generated catalog and, if configured, cases in the existing toctree:

```rst
.. toctree::
   :maxdepth: 1

   mceg/_generated/catalog
   mceg/_generated/cases
```

The repository's update script runs generation before Sphinx:

```bash
python -m mceg docs --config mceg/docs.yaml
python -m sphinx -M clean documents documents/_build
python -m sphinx -M html documents documents/_build -E -a
```

Use the standard HTML builder and `.html` suffix. Sphinx rebases SVG links for
nested output directories. Generated RST needs no MCEG Sphinx extension or MyST
parser; HTML compilation can run after generation in a separate environment.
Generation revalidates case pins; compiling previously generated RST alone does
not reload contracts. Use the update script after changing records. A clean HTML
build removes pages for contracts or cases that are no longer selected.

Both ExoGibbs and ExoEOS use `./update_doc.sh`. Their generated entry pages are
`documents/_build/html/mceg/index.html`. ExoGibbs additionally accepts
`-D plot_gallery=0` to skip numerical gallery examples. Its pinned H2 case needs
a sibling ExoEOS checkout. ExoEOS selects all its registered local contracts and
has no default calculation case. Existing provider API documentation may import
provider packages; MCEG source generation does not.

For MCEG's own documentation, install `.[docs]` and run:

```bash
./update_doc.sh -W --keep-going
```

Open `docs/_build/html/index.html`. This repository's authored Markdown guides
still use MyST, separately from the generated RST. Its catalog includes five
reference contracts and the v0.2 H2 example. The original 1700 K manual case and
the v0.2 example's 1750 K assessments retain their distinct scopes.

## Navigate the generated documentation

Model overviews show the purpose, literature-inspection states, an applicability
preview and recorded support. Five child pages separate the details:

- **Applicability:** assumptions, limitations, domains and Conditions.
- **Assessments:** claims and scoped outcomes, with one detail page per
  Assessment for reasons, Evidence links and the recorded method.
- **Evidence:** a source-review index and dependency graph, with individual
  records for sources, scope, audit gaps and ancestry.
- **References:** literature sources, their uses and inspection states.
- **Implementation & records:** implementation identity, Subjects, Contexts and
  the source-contract download.

The overview previews up to two unknown domains and the first two limitations
in authored order, with a link to the complete applicability page. Contracts do
not assign editorial importance to limitations; this preview is not a ranking.
Up to three Assessments are shown with their Subject and Context. Larger
histories link to the complete list without selecting a current result. For
v0.1, up to three declared claims are shown with their scopes; larger sets link
to the full list. Case-specific support is not inferred from those declarations.

Technical records such as hashes, Context settings and assessment methods use
native HTML disclosure controls. Cautions, reasons, source inspections and audit
gaps stay expanded. Anchors remain outside collapsed content. Graphs have
ordinary text links as well as clickable nodes. No extra JavaScript is required.

For readable references, put authors, year and title, when known, in a literature
Evidence's `summary`; put its DOI/URL in `sources`, and relevant equations or
tables in `scope` or `provenance.location`. Record source inspection separately.
The generator neither invents missing bibliographic metadata nor imports
citations found only in provider code.

## Select a calculation

The [documentation case](../../examples/html/case.yaml) is an experimental
composition format separate from the scientific contract schemas. Its provider
roots resolve from the case file. Each registered component requires the exact
contract SHA-256 and matching model ID. A changed pin stops generation; updating
a pin is not scientific reassessment. Omit both path and hash to show a known
unregistered component explicitly.

`components` records selected models and settings. `connections` records the
consumer, dependency, quantity and authored transformation/scope. Dependencies
are not inferred from imports, and transformations are not executed. Optional
`inputs` records scalar calculation inputs with unit-bearing keys such as
`temperature_K`; these do not create an assessed Context.

For v0.2, select both `subject` and `context` and explicitly list `assessments`.
Every selected assessment must belong to that Subject and Context. Missing
selections leave case support unknown. Historical records are not selected by
date or reused automatically.

The optional `legacy_case` adapter pins an existing v0.1 manual example case,
checks its references, and uses its inputs exclusively. The reference H2 example
preserves all nine original judgments. Optional `highlights` selects up to three
manual assessment IDs for the overview using authored titles. The outcome comes
from the referenced record. All judgments remain accessible in the assessment
list and their individual detail pages.

## Python API and interpretation

The CLI uses the same source-only API:

```python
from pathlib import Path
from mceg.documentation import build

checkout = Path("/path/to/exoeos")
build(
    contract_sources=[{
        "provider": "exoeos", "root": checkout,
        "paths": ["mceg/contracts/*.yaml"],
    }],
    case_paths=[],
    output=checkout / "documents/mceg/_generated",
    source_root=checkout / "documents",
)
```

Paths passed directly to this API resolve from the calling process. Case roots
still resolve from their case files. Numerical outcomes, physical support,
reported ranges, source inspection and implementation identity remain separate
records. Graph links do not propagate support to connected models. Repeated
citations are not independent evidence, and a primary citation may be uninspected.

Local RST within the Sphinx tree links to rendered documentation. File-line
locators such as `#L30-L40` use source downloads because rendered HTML does not
preserve source-line anchors. Other files, including Markdown, are also source
downloads. These files contain build-checkout
bytes, which may differ from recorded implementation revisions or artifact
hashes. Use [assessment hash checks](checks.md#verify-local-file-hashes) to verify
those bytes. External URLs are retained but not checked for availability.

The catalog covers explicitly selected contracts, not every model in a provider.
Use [coverage](coverage.md) for registration and source-review gaps. Archived
reviews are separate inputs. Source generation is neither runtime tracing nor
automatic discovery of scientific dependencies.
