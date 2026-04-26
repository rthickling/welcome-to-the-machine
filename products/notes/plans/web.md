# Browser-Hosted WebAssembly Plan

This file covers:

- `notes-web.wasm`

under the approved policy that browser host glue may remain external to the
committed repo artifacts.

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

`notes-web.wasm` now implements the browser-hosted GUI contract boundary: it
imports drawing/storage functions from module `notes`, exports `init`, `key`,
and `click`, owns the editor buffer in linear memory, and renders the note/list
pane chrome through host callbacks.

## Product policy for web

The committed in-repo deliverable stays:

- a Wasm binary
- a machine-code test
- matching Markdown documentation

The browser bootstrap layer can remain external host glue, because the user
explicitly approved that policy while planning.

## Required behavior contract

The web implementation should expose host-call or import boundaries for:

- rendering the two-pane note UI
- list hit-testing
- keyboard text entry
- browser-side persistence
- border drawing / styling for the editor and list panes
- foreground/background colour selection matching the product contrast policy

## Storage

The logical note format should still match the shared product contract, even if
the browser host persists the bytes via IndexedDB, local storage, or a custom
host bridge.

## Testing

The Wasm verifier should structurally anchor:

- exported/imported entry points used for rendering and keyboard input
- printable ASCII input handling, including Shift-derived uppercase/symbols
- border and colour constants exposed to or consumed by the host bridge
