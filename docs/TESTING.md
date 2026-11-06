# Testing

## Running

```sh
uv run pytest --cov=adr_cli   # tests with coverage report
uv run python scripts/check.py      # every gate, as CI and the factory run it
```

## Policy

- Branch coverage of `src/adr_cli` must stay at or above 80 %; the gate fails below it.
- Tests exercise the public API (`import adr_cli`) and the CLI entry point `main()`, asserting return values, raised exceptions, error codes and file bytes.
- Each bug fix starts with a failing test that reproduces it.
- Tests are deterministic: no network, no wall clock, no dependence on test order.

## Layout

`tests/test_adr_cli.py` is the single test module present in the repository. It covers the acceptance behaviours: `new` output bytes, numbering that ignores non-matching filenames, `supersede` with CRLF preservation, terminal state after supersede, sorted `list` and JSON output, malformed headers and invalid statuses, write failure during supersede, and title validation and slugging.
