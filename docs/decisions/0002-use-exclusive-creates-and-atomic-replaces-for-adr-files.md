# Use exclusive creates and atomic replaces for ADR files

Status: accepted (generated, pending human review)

## Context

ADR numbering, status changes and supersede links are edited by hand, and concurrent or interrupted tools can corrupt files or reuse numbers. The format must stay compatible with adr-tools and run natively on Windows without runtime dependencies.

## Decision

Keep the adr-tools (Nygard) Markdown format and edit it line by line. New files are created with open(path, 'x') so two creates of one number fail with code 'conflict'. Updates write a temporary file in the same directory and os.replace it, rewriting only the lines of the status section and preserving each line's own newline. Superseded is terminal and reachable only through supersede. All limits (256 KiB files, 200-character titles, 60-character slugs, 9999 numbers) are named constants that raise the typed AdrError with a stable code.

## Consequences

Files are never half-written and numbers are never silently reused, and diffs stay minimal in CRLF repositories. A supersede that fails while rewriting the old file leaves the new file behind, which is visible and can be repaired by hand. Numbering is derived from file names, so a gap is never reused. The library is bounded to 9999 ADRs of at most 256 KiB each.
