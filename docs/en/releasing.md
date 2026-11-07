# Releasing MCEG

Package versions and contract schema versions are separate. Keep existing Git
tags immutable and match each release tag to the version in `pyproject.toml`.

## One-time PyPI setup

In the PyPI account that will own MCEG, add a pending publisher at
[Publishing](https://pypi.org/manage/account/publishing/):

| Field | Value |
| --- | --- |
| PyPI project name | `mceg` |
| GitHub owner | `HajimeKawahara` |
| Repository | `mceg` |
| Workflow filename | `release.yml` |
| Environment | `pypi` |

The first successful upload creates the project. Later releases use the same
publisher. No PyPI API token or GitHub secret is needed. See PyPI's
[Trusted Publishing guide](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).

## Publish a release

1. Update the package version, changelog and current-version documentation.
2. Install `.[test,docs]`, `build` and `twine` in a virtual environment. Run
   `python -m pytest -q` and `./update_doc.sh -W --keep-going` with Graphviz
   installed. For the viewer, run `npm ci`, `npm test` and `npm run build` in
   `viewer/`.
3. Run `python -m build` and `python -m twine check --strict dist/*`. Verify the
   wheel in a clean environment outside the checkout.
4. Commit the release changes, push the new `v<version>` tag, and publish its
   GitHub release. Attach the wheel and source distribution.
5. The `Publish to PyPI` workflow checks the tag, runs tests, builds the
   distributions and publishes them using the `pypi` environment. Check the
   workflow result and install the exact version from PyPI to verify it.

If the publisher was not configured before the workflow ran, configure it and
rerun the failed publish job. Keep the original tag and build artifacts.
