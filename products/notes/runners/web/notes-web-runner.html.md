# `products/notes/runners/web/notes-web-runner.html`

Browser **test harness** for [`notes-web.wasm`](../../targets/wasm/notes-web.wasm.md).

## Role

This page exists so a human (or AI) can **exercise** the Wasm Notes product in a
real browser: load the module, see the framebuffer, type, click, and confirm
persistence. It is **not** a development tool, build step, assembler, or place
to implement product behaviour.

Allowed host duties only:

- `WebAssembly.instantiate` of `notes-web.wasm`
- `present` → blit linear memory to `<canvas>`
- `rewrite` → opaque `localStorage` byte blob
- forward keyboard / pointer into `key` / `click`

All Notes semantics stay in the Wasm binary. The committed HTML/JS is an
exception to the usual “binaries only” rule solely for this browser-platform
**test** adapter (see [`web-plan.md`](../../plans/web.md)).

## How to use

```bash
./products/notes/runners/web/run_notes
```

That serves the product tree and opens this page. Hard-refresh after changing
`notes-web.wasm`.

## What not to do

- Do not grow this file with sort, parse, list, or editor logic.
- Do not treat it as the source of truth for Notes behaviour.
- Prefer [`test-notes-web`](../../targets/wasm/test-notes-web.md) for
  always-on structural regression; use this harness for interactive checks.
