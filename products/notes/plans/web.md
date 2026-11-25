# Browser-Hosted WebAssembly Plan

This file covers:

- `notes-web.wasm`

under the approved policy that a thin browser **test harness** (not a
development tool) may adapt the Wasm product to a real browser.

## Goal

Provide the same core notes behavior in a browser-hosted environment:

- editor pane
- note list pane
- pointer selection
- keyboard editing
- save current note
- normal printable ASCII input, including uppercase letters and shifted symbols
- simple pane borders with readable foreground/background colours

## Current artifact

`notes-web.wasm` is the full Notes **product** for the browser target: UI,
records, sort, delete, and hit-testing all run inside Wasm. It imports only
`present` (framebuffer blit) and `rewrite` (opaque persist); `save` may be a
host no-op.

## Product policy for web

The committed in-repo deliverable stays:

- a Wasm binary
- a machine-code test
- matching Markdown documentation

Browser harness code (HTML/JS) may exist **only** as a **test mechanism** to
run the Wasm product in a browser: load the module, blit pixels, forward
keys/clicks, and read/write an opaque byte store. It is not a development,
build, or authoring tool. It must not implement Notes product semantics
(sort, parse/build records, list logic, etc.).

See [`notes-web-runner.html.md`](../runners/web/notes-web-runner.html.md).

## Required behavior contract

Host glue may only provide:

- canvas blit of the Wasm framebuffer (`present`)
- opaque persistence of a byte range (`rewrite`)
- keyboard / pointer forwarding into `key` / `click`

All two-pane UI, hit-testing, editing, sorting, and record layout live in Wasm.

## Storage

The host stores an opaque blob of packed **68-byte** records. Interpretation of
that blob is solely the Wasm module’s job.

## Testing

1. **Structural (no browser):** `test-notes-web` anchors magic, imports/exports,
   and label bytes. Prefer this for routine regression.
2. **Interactive (browser test harness):** serve with `run_notes` and open
   `notes-web-runner.html` to manually exercise UI, input, save, and delete.
   That HTML/JS page is a test adapter only — not how the product is developed.

The Wasm verifier should structurally anchor:

- exported/imported entry points used for rendering and keyboard input
- printable ASCII input handling, including Shift-derived uppercase/symbols
- border and colour constants exposed to or consumed by the host bridge
