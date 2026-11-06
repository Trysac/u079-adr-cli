# Security notes

## Threat model

`trysac-adr-cli` reads and writes ADR files under a single directory. The threats below are the ones the code addresses and the limits that remain.

### Defended

- **Path traversal from names**: every path is `root / generated filename`; only names matching `NNNN-slug.md` are treated as ADRs.
- **Symlinks**: symlinked ADR files are refused with code `format`; non-regular files are refused.
- **Oversized input**: files above 256 KiB raise `too_large`; reads stop at the limit.
- **Overwriting on create**: new files use exclusive create, so an existing number yields `conflict`.
- **Torn updates**: updates write a temporary file in the same directory, fsync it, and `os.replace` it over the original.
- **Hostile titles and relations**: control characters, brackets and empty values are rejected; error messages quote at most 200 characters with non-printable characters replaced.
- **Terminal state**: superseded ADRs cannot be changed through the API.

### Not defended

- Concurrent writers outside the library: there is no file locking, so two processes can race on the same supersede or link.
- Directory listing size: `list()` reads up to 9999 entries; the limit is enforced after scanning the directory.
- Local attackers with write access to the ADR directory can still alter content that the library reads as valid.
- Supply chain: the package has no runtime dependencies, but build and CI tooling are external.

## Publishing

Releases are published to PyPI with trusted publishing (OIDC) when available, never with a long-lived token stored in the repository.

To report a vulnerability, see [SECURITY.md](../SECURITY.md).
