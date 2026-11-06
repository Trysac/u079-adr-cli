# Architecture

## Purpose

`trysac-adr-cli` is a small, dependency-free Python package that creates, lists, links and supersedes Architecture Decision Records in the adr-tools Markdown format, using exclusive creates and atomic updates.

## Shape

```text
caller code --> adr_cli (public API in __init__.py)
                    |
                    +-- _core.py: model, parser, AdrRepository
                    +-- __main__.py: argparse CLI, exit codes
```

- **Public API**: the four names in `__all__` of `src/adr_cli/__init__.py`: `Adr`, `AdrError`, `AdrRepository`, `Link`, plus `parse_adr` and `__version__`.
- **Errors**: invalid input raises `AdrError` with a stable `code`. The library does not print or exit; the CLI maps errors to exit codes.
- **I/O**: confined to `AdrRepository`. Creates use `open(path, 'x')`; updates write a temporary file in the same directory and call `os.replace`.
- **Time**: library calls take `today` as a parameter; only the CLI defaults to `date.today()`.

## Quality contract

`scripts/check.py` is the single definition of the gates; `fabrica.json` tells the factory and CI how to run it. See [TESTING.md](TESTING.md).

## Decisions

Architecture decisions are recorded in [decisions/](decisions/) as numbered ADRs.
