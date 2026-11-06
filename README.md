# adr-cli

[![PyPI version](https://img.shields.io/pypi/v/trysac-adr-cli)](https://pypi.org/project/trysac-adr-cli/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-adr-cli)](LICENSE)
[![CI](https://github.com/Trysac/u079-adr-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u079-adr-cli/actions/workflows/ci.yml)

Create, list, link and supersede Architecture Decision Records in the adr-tools Markdown format, with exclusive creates and atomic updates.

## Problem

Architecture Decision Records live as numbered Markdown files, but numbering, status changes and supersede links are maintained by hand and break silently. adr-tools defines the common format but is a Bash script that does not run natively on Windows and has no machine-readable output. adr-cli is a cross-platform Python CLI with a typed library that keeps ADRs consistent and scriptable.

## Install

```sh
pip install trysac-adr-cli
# or
uv add trysac-adr-cli
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
from datetime import date
from pathlib import Path

from adr_cli import AdrRepository

repo = AdrRepository(Path("doc/adr"))
adr = repo.create("Use Postgres", today=date(2026, 11, 5))
print(adr.path, adr.status)
print(repo.render_index())
```

### Public API

- `AdrRepository(root: Path)`: `list()`, `get(number)`, `create(title, *, today, status="Proposed")`, `set_status(number, status)`, `supersede(old, new_title, *, today)`, `link(source, target, relation)`, `render_index()`.
- `parse_adr(text, path)`: parses one ADR file.
- `Adr` and `Link`: frozen dataclasses.
- `AdrError`: carries a `code`, plus `path` and `line` when known. Codes: `not_found`, `format`, `invalid_status`, `invalid_title`, `duplicate_link`, `self_link`, `already_superseded`, `conflict`, `number_exhausted`, `too_large`, `write_failed`.

Limits: files over 256 KiB are rejected, titles are at most 200 characters, slugs at most 60, relations at most 100, and numbers run up to 9999. Settable statuses are Proposed, Accepted, Rejected and Deprecated; Superseded is reached only through `supersede` and is terminal. Symlinked ADR files are refused.

### CLI

```sh
adr-cli [--dir doc/adr] init
adr-cli new TITLE [--status S] [--date YYYY-MM-DD]
adr-cli list [--format text|json]
adr-cli status N STATUS
adr-cli supersede N TITLE [--date YYYY-MM-DD]
adr-cli link N M --relation TEXT
adr-cli index
```

`python -m adr_cli` is equivalent. Exit codes: 0 ok, 1 domain failure, 2 usage, I/O or parse error.

## Why not adr-tools

adr-tools uses the same file format but is a Bash script without native Windows support and without machine-readable output. adr-cli reads and writes the same format and adds JSON output and an importable API.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
