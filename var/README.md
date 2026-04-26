# Runtime State and Local Scratch

`var/` separates runtime data from committed binary deliverables.

## `samples/`

`var/samples/` contains small tracked state files that demonstrate outputs or
database formats from earlier runs:

- `greeting.txt`
- `root-notes.db`
- `product-notes.db`

These are examples, not executable deliverables.

## `local/`

`var/local/` is ignored by git. It is for local-only generated files, caches,
virtual environments, temporary WebAssembly text dumps, and other scratch data
that should not be committed under the binary-only rules.
