# adr-cli

[![PyPI version](https://img.shields.io/pypi/v/trysac-adr-cli)](https://pypi.org/project/trysac-adr-cli/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-adr-cli)](LICENSE)
[![CI](https://github.com/Trysac/u079-adr-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u079-adr-cli/actions/workflows/ci.yml)

Create, list, link and supersede Architecture Decision Records in the adr-tools Markdown format, with exclusive creates and atomic updates

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-adr-cli
# or
uv add trysac-adr-cli
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import adr_cli

# normalize() trims surrounding whitespace and lower-cases the text.
print(adr_cli.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    adr_cli.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
