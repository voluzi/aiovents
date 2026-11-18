# Contributing to aiovents

[Search existing issues](https://github.com/voluzi/aiovents/issues) before starting. For a
new bug, include the software versions, the device model and firmware if
relevant, and a minimal reproduction. See [SECURITY.md](SECURITY.md) for
vulnerability reports.

## Development

Run these commands from the repository root:

```sh
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
mypy --strict src
pytest -q
python -m build
```

Tests use synthetic protocol traffic; no physical device is needed.

## Pull requests

Keep changes focused. Include a regression test for a behavior change when
practical, and update the README and changelog when users need to know about
the change. Describe what changed and how you verified it.

Use synthetic or redacted logs, configuration and fixtures. Remove private
addresses, hostnames, device identifiers, credentials and location information.
