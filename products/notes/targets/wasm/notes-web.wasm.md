# `products/notes/targets/wasm/notes-web.wasm`

`notes-web.wasm` is the browser-hosted Notes **product** binary (currently
~2975 bytes). It owns all product behaviour: 600×400 RGBA framebuffer UI,
8×8 font text, list rows, Del, editor caret, 68-byte records, sort-on-save,
delete compaction, and click hit-testing.

The HTML page under `runners/web/` is a **browser test harness** only (blit +
opaque `localStorage` + input forwarding) — not a development tool. Sorting,
record parse/build, and list logic are **not** in that page. See
[`notes-web-runner.html.md`](../../runners/web/notes-web-runner.html.md).

## Host imports (`notes`)

| Import | Type | Meaning |
| --- | --- | --- |
| `present()` | `() -> ()` | Blit linear memory `0x0` (600×400 RGBA) to the canvas. |
| `save(ptr, len)` | `(i32, i32) -> ()` | Unused by the product path; may be a host no-op. |
| `rewrite(ptr, len)` | `(i32, i32) -> ()` | Replace the opaque host store with `len` bytes from `ptr`. |

Exports: `memory` (16 pages), `init`, `key`, `click`, `load`.

## Product behaviours (in Wasm)

- **Enter** — stages a 68-byte record (`u32 0x40` + 64 NUL-padded bytes),
  appends it at `0xED000`, bubble-sorts all records by text bytes, then
  `rewrite` + `load`.
- **load(len)** — treats `0xED000` as a packed array of 68-byte records,
  builds the index at `0xEE000`, stores blob length at `0xEC0F0`, repaints.
- **Del** — shifts remaining 68-byte slots down, updates length, `rewrite` +
  `load`.
- **Click** — list hit-test; load-row copies text until NUL into the editor.

## Linear-memory layout

| Address | Purpose |
| --- | --- |
| `0x000000` | Framebuffer 600×400×4 RGBA (`0xAARRGGBB` LE) |
| `0x0EB800` | 8×8 font (96 glyphs × 8, ASCII 32–127, MSB leftmost) |
| `0x0EC000` | Editor buffer (≤63 bytes; length in global 0) |
| `0x0EC040` | 68-byte save staging |
| `0x0EC0F0` | `u32` current blob length at `0xED000` |
| `0x0ED000` | Record store (packed 68-byte records; max 4096 bytes) |
| `0x0EE000` | Index `[ptr][len=64][first-word len]` × note |
| `0x0EF000` | Sort scratch (68 bytes) |
| `0x0F0000` | `"Note:"`, `"Words"`, `"Del"`, `"Notes Web GUI"` |

### Hit-testing

- List pane: `350 ≤ x < 588`, `y ≥ 48`, row `(y−48)/16`
- Load row: `x < 544`; delete: `x ≥ 544`

## How to test interactively

```bash
./products/notes/runners/web/run_notes
```

Opens the browser **test** page [`notes-web-runner.html`](../../runners/web/notes-web-runner.html)
so you can exercise the Wasm UI. That page is not used to author or build the
module.

## Verification

`test-notes-web` anchors magic, `notes.present`, the function table,
`init`/`key`/`load` exports, and `"Note:"` / `"Words"` / `"Del"` data bytes
(at current file offsets `0x83e` / `0x84a` / `0x856`).
`wasmtime compile notes-web.wasm` validates the module.

The runnable [`notes-web.wasm`](notes-web.wasm) **is** the source. Patch font
or code bytes in that file directly (e.g. font data at file offset `0x776`);
there is no separate `.hex` source.
