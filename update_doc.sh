#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIRECTORY}"

python -m mceg docs --config docs/mceg.yaml
python -m sphinx -M clean docs docs/_build
python -m sphinx -M html docs docs/_build -E -a "$@"
