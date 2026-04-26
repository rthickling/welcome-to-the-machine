# `products/notes/targets/wasm/notes-web.wasm`

`notes-web.wasm` is a **379-byte** browser-hosted WebAssembly MVP module for
the Notes product. Unlike the previous WASI marker, this module exposes an
actual GUI-oriented host ABI:

- imported drawing calls render the note and list panes
- exported `init` paints the initial UI
- exported `key(code)` edits the in-Wasm input buffer
- `Enter` calls the imported `save(ptr, len)` host persistence hook
- exported `click(x, y)` currently repaints the UI

The browser bootstrap remains external to the repo, per [`web-plan.md`](web-plan.md):
the committed deliverable is the `.wasm` binary, its binary test, and this
byte-level documentation.

## Custom host checklist

The module imports five functions from import module `notes`:

| Import | Type | Meaning |
| --- | --- | --- |
| `clear()` | `() -> ()` | Clear the host drawing surface. |
| `style(bg, fg)` | `(i32, i32) -> ()` | Set background and foreground colours. The module passes `0x202020` and `0xe0e0e0`. |
| `rect(x, y, w, h)` | `(i32, i32, i32, i32) -> ()` | Draw a pane border rectangle. |
| `text(x, y, ptr, len)` | `(i32, i32, i32, i32) -> ()` | Draw UTF-8/ASCII bytes from exported memory. |
| `save(ptr, len)` | `(i32, i32) -> ()` | Persist the current note bytes. |

Exports:

| Export | Type | Meaning |
| --- | --- | --- |
| `memory` | memory | One 64 KiB page. |
| `init()` | `() -> ()` | Render the initial two-pane UI. |
| `key(code)` | `(i32) -> ()` | Handle one browser key code / ASCII byte. |
| `click(x, y)` | `(i32, i32) -> ()` | Host click entry point; currently repaints. |

The host should pass normal printable ASCII bytes to `key`, including uppercase
letters and shifted symbols after browser keyboard translation. The module also
handles `8` as Backspace and `13` as Enter.

## How to run with the included local runner

For this runner only, the repo contains a human-readable browser host:

- [`notes-web-runner.html`](../../runners/web/notes-web-runner.html)
- [`run_notes.py`](../../runners/web/run_notes.py)

Run it from the repo root with:

```bash
python3 products/notes/runners/web/run_notes.py
```

Then use the opened browser page:

- type printable text in the canvas
- `Backspace` edits
- `Enter` saves to browser `localStorage`
- click a saved first-word row in the right pane to load it back into the editor

The runner serves `notes-web.wasm` over `http://127.0.0.1:8765/` so browser
`fetch()` can instantiate the module. It implements the `notes` imports with a
canvas drawing surface and persists saved notes under the
`machine-welcome.notes-web.records` local-storage key.

## Host ABI

Because WebAssembly cannot access the browser DOM directly, run this module from
an external browser host page or runner that implements the `notes` imports
above. The host page should:

1. Create a canvas or DOM drawing surface.
2. Instantiate `products/notes/targets/wasm/notes-web.wasm` with the `notes` import object.
3. Implement `clear`, `style`, `rect`, and `text` by drawing to that surface.
4. Implement `save(ptr, len)` by reading bytes from the exported memory and
   storing them in local storage, IndexedDB, or another host store.
5. Call exported `init()` once after instantiation.
6. Forward key presses to exported `key(code)`.
7. Forward pointer clicks to exported `click(x, y)`.

The included runner is one implementation of this host boundary. Other hosts
can provide the same imports without changing the Wasm binary.

## Whole-file sections

The file begins with the standard Wasm magic and version:

```text
00 61 73 6d 01 00 00 00
```

### Type section

```text
01 14 04
60 00 00
60 01 7f 00
60 02 7f 7f 00
60 04 7f 7f 7f 7f 00
```

This defines four signatures:

- type `0`: `() -> ()`
- type `1`: `(i32) -> ()`
- type `2`: `(i32, i32) -> ()`
- type `3`: `(i32, i32, i32, i32) -> ()`

### Import section

The import section starts at file offset `0x1e` and declares:

```text
notes.clear
notes.style
notes.rect
notes.text
notes.save
```

The first anchored import bytes at `0x20` are:

```text
05 05 6e 6f 74 65 73 05 63 6c 65 61 72
```

### Function, memory, global, and export sections

The function section declares four internal functions:

- function index `5`: render helper
- function index `6`: exported `init`
- function index `7`: exported `key`
- function index `8`: exported `click`

The memory section exports one page. A mutable `i32` global holds the current
input length.

The export anchor at file offset `0x84` is:

```text
04 69 6e 69 74 00 06 03 6b 65 79 00 07
```

That is the `init` export followed by the `key` export.

## Code behavior

The render helper:

1. calls `clear`
2. calls `style(0x202020, 0xe0e0e0)`
3. draws a left pane rectangle at `(8, 20, 330, 52)`
4. draws a right pane rectangle at `(350, 20, 238, 350)`
5. draws `Note:` at `(16, 30)`
6. draws the current input buffer at `(16, 46)`
7. draws `Words` at `(360, 30)`

The key handler:

1. if code is `8`, decrements the input length when non-zero
2. if code is `13`, calls `save(256, input_len)` and clears the input length
3. if code is printable ASCII in `[32, 126]` and the buffer has room, stores the
   byte at `memory[256 + input_len]` and increments the length
4. calls render

The input buffer starts at linear-memory offset `256` and is capped at 63 bytes.

## Data section

The data section contains three active segments:

```text
offset 0x00: 4e 6f 74 65 3a                  ; "Note:"
offset 0x10: 57 6f 72 64 73                  ; "Words"
offset 0x40: 4e 6f 74 65 73 20 57 65 62 20 47 55 49
```

The third string is:

```text
Notes Web GUI
```

## Verification

`test-notes-web` verifies:

- Wasm magic bytes
- `notes.clear` import anchor
- `init` / `key` export anchor
- `Note:` data bytes
- `Words` data bytes
- `Notes Web GUI` product bytes

`wasmtime compile notes-web.wasm` validates the module on hosts with Wasmtime.
