# Project record

## Objective

Provide a cross-platform, typed Python library and CLI that keeps Architecture Decision Records in the adr-tools (Nygard) Markdown format consistent: numbering, status changes and supersede links are handled by code instead of by hand.

## Scope

- In scope: creating, listing, linking and superseding ADRs; setting statuses; rendering a Markdown index; a JSON listing from the CLI; the public API documented in [README.md](../README.md), typed and tested.
- Out of scope: HTML output, templates other than the adr-tools format, git integration, the MADR format, and any runtime dependency.

## Timeline

| Date | Event |
|---|---|
| 2026 | Repository created from the factory utility template. |

## Effort metrics

Measured values only; a value that has not been measured stays "pending measurement".

| Metric | Value |
|---|---|
| Tokens (input / output) | 555218 / 96106 |
| Hours (human) | pending measurement |
| Cost (USD) | 0.7887 |

## Factory run u079 (measured from API usage)

| Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|
| generation | claude-sonnet-5-5 | yes | 2520 | 81788 | 0 | 4246 | 0.4119 |
| fix-1 | claude-sonnet-5-5 | no | 16 | 2328 | 8796 | 124449 | 0.0577 |
| fix-2 | claude-sonnet-5-5 | no | 10 | 1015 | 4617 | 73645 | 0.0291 |
| fix-3 | claude-sonnet-5-5 | no | 10 | 1195 | 4726 | 73441 | 0.0311 |
| audit | claude-sonnet-5-5 | no | 10 | 3659 | 32804 | 87351 | 0.1274 |
| fix-4 | claude-sonnet-5-5 | no | 8 | 2357 | 11649 | 63476 | 0.0591 |
| docs | claude-haiku-5-5 | no | 126036 | 3764 | 0 | 0 | 0.0724 |

Total: $0.7887. Prices: Anthropic list prices.
