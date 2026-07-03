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

## Whole-file byte decode

Encoding conventions (LEB128 integers, `0x60` signature markers, `0x7f` =
`i32`) are introduced in
[`experiments/poc-05-wasm-wasi/hello.wasm.md`](../../../../experiments/poc-05-wasm-wasi/hello.wasm.md#encoding-conventions-read-this-once).
Section map of this 379-byte (`0x17b`) file:

```text
0x000..0x007  magic "\0asm" + version 1
0x008..0x01d  Type      (id 0x01, 20-byte payload)
0x01e..0x063  Import    (id 0x02, 68-byte payload)
0x064..0x06a  Function  (id 0x03, 5-byte payload)
0x06b..0x06f  Memory    (id 0x05, 3-byte payload)
0x070..0x077  Global    (id 0x06, 6-byte payload)
0x078..0x098  Export    (id 0x07, 31-byte payload)
0x099..0x150  Code      (id 0x0a, 181-byte payload)
0x151..0x17a  Data      (id 0x0b, 40-byte payload)
```

### Type section (`0x08`)

```text
01 14 04              ; id, payload length 20, 4 types
60 00 00              ; type 0: () -> ()
60 01 7f 00           ; type 1: (i32) -> ()
60 02 7f 7f 00        ; type 2: (i32, i32) -> ()
60 04 7f 7f 7f 7f 00  ; type 3: (i32, i32, i32, i32) -> ()
```

### Import section (`0x1e`)

Five imports, all functions from module `notes`. Each entry is
`module-name, field-name, kind 0x00, type index`:

```text
02 44 05                           ; id, payload length 68, 5 imports
05 6e6f746573 05 636c656172 00 00  ; "notes" "clear" func type 0 → function 0
05 6e6f746573 05 7374796c65 00 02  ; "notes" "style" func type 2 → function 1
05 6e6f746573 04 72656374   00 03  ; "notes" "rect"  func type 3 → function 2
05 6e6f746573 04 74657874   00 03  ; "notes" "text"  func type 3 → function 3
05 6e6f746573 04 73617665   00 02  ; "notes" "save"  func type 2 → function 4
```

Imported functions take indices 0–4, so `call 0..4` in the code below are the
host calls, and the module's own functions are indices 5–8.

### Function, memory, and global sections (`0x64`, `0x6b`, `0x70`)

```text
03 05 04 00 00 01 02  ; 4 defined functions with type indices 0,0,1,2:
                      ;   function 5: () -> ()        (render helper)
                      ;   function 6: () -> ()        (init)
                      ;   function 7: (i32) -> ()     (key)
                      ;   function 8: (i32, i32) -> () (click)
05 03 01 00 01        ; 1 linear memory, limits: min 1 page (64 KiB)
06 06 01 7f 01 41 00 0b  ; 1 global: i32, mutable, init = (i32.const 0; end)
```

Global 0 is the **current input length** — the only piece of mutable state
outside linear memory.

### Export section (`0x78`)

```text
07 1f 04                    ; id, payload length 31, 4 exports
06 6d656d6f7279 02 00       ; "memory" kind 2 (memory), index 0
04 696e6974     00 06       ; "init"   kind 0 (function), index 6
03 6b6579       00 07       ; "key"    function 7
05 636c69636b   00 08       ; "click"  function 8
```

## Code section (`0x99`), instruction by instruction

```text
0a b5 01 04    ; id 0x0a, payload length 181 (LEB128 b5 01), 4 bodies
```

### Function 5 — render helper (body at `0x9d`, 72 bytes)

Wasm is a stack machine: `i32.const` pushes an argument, `call` pops the
callee's arguments. Every coordinate below is a pixel.

```text
48 00                 ; body size 72, no locals
10 00                 call 0                   ; clear()
41 a0 c0 80 01        i32.const 0x202020       ; background (LEB128, 4 bytes)
41 e0 c1 83 07        i32.const 0xe0e0e0       ; foreground
10 01                 call 1                   ; style(0x202020, 0xe0e0e0)
41 08 41 14           i32.const 8, 20
41 ca 02 41 34        i32.const 330, 52
10 02                 call 2                   ; rect(8, 20, 330, 52)    left pane
41 de 02 41 14        i32.const 350, 20
41 ee 01 41 de 02     i32.const 238, 350
10 02                 call 2                   ; rect(350, 20, 238, 350) right pane
41 10 41 1e           i32.const 16, 30
41 00 41 05           i32.const 0, 5
10 03                 call 3                   ; text(16, 30, ptr 0, len 5)   "Note:"
41 10 41 2e           i32.const 16, 46
41 80 02              i32.const 256            ; input buffer address
23 00                 global.get 0             ; current input length
10 03                 call 3                   ; text(16, 46, 256, len)  the live input
41 e8 02 41 1e        i32.const 360, 30
41 10 41 05           i32.const 16, 5
10 03                 call 3                   ; text(360, 30, ptr 16, len 5) "Words"
0b                    end
```

### Function 6 — exported `init` (body at `0xe6`, 4 bytes)

```text
04 00                 ; body size 4, no locals
10 05                 call 5                   ; render
0b                    end
```

### Function 7 — exported `key(code)` (body at `0xeb`, 96 bytes)

One `if/else` chain on the key code (`local 0`), then an unconditional
repaint. `04 40` is `if` with empty block type; an empty *then* branch
followed immediately by `05` (`else`) is how "do nothing unless" is encoded.

```text
60 00                 ; body size 96, no locals
; --- Backspace: code == 8 ---
20 00 41 08 46        local.get 0; i32.const 8; i32.eq
04 40                 if
  23 00 45            global.get 0; i32.eqz    ; length == 0 ?
  04 40                if                      ; yes → do nothing
  05                   else
    23 00 41 01 6b     global.get 0; i32.const 1; i32.sub
    24 00              global.set 0            ; length -= 1
  0b                   end
05                    else
  ; --- Enter: code == 13 ---
  20 00 41 0d 46      local.get 0; i32.const 13; i32.eq
  04 40               if
    23 00 45          global.get 0; i32.eqz    ; empty input?
    04 40              if                      ; yes → do nothing
    05                  else
      41 80 02          i32.const 256          ; ptr
      23 00             global.get 0           ; len
      10 04             call 4                 ; save(256, len)
      41 00 24 00       i32.const 0; global.set 0  ; length = 0
    0b                  end
  05                  else
    ; --- printable character path ---
    20 00 41 1f 4b    local.get 0; i32.const 31; i32.gt_u   ; code > 31 ?
    04 40             if
      20 00 41 7f 49  local.get 0; i32.const -1; i32.lt_u   ; code <_u 0xFFFFFFFF ?
      04 40           if
        23 00 41 3f 49  global.get 0; i32.const 63; i32.lt_u ; length < 63 ?
        04 40           if
          41 80 02       i32.const 256
          23 00 6a       global.get 0; i32.add  ; address = 256 + length
          20 00          local.get 0            ; the key code byte
          3a 00 00       i32.store8             ; memory[256+len] = code
          23 00 41 01 6a global.get 0; i32.const 1; i32.add
          24 00          global.set 0           ; length += 1
        0b              end
      0b              end
    0b                end
  0b                  end
0b                    end
10 05                 call 5                   ; render (always)
0b                    end
```

**Encoding quirk, documented deliberately:** the upper-bound test uses
`41 7f`, and in *signed* LEB128 the single byte `0x7f` decodes to **−1**, not
127. So the test is `code <_u 0xFFFFFFFF` — true for every code except
`0xFFFFFFFF` — and the module actually accepts *any* code above 31 that a
host passes, not just ASCII `[32, 126]`. Encoding 127 would need the
two-byte LEB `ff 00`. With well-behaved hosts (the included runner only
forwards single printable characters plus 8/13) the observable behaviour is
the printable-ASCII contract described above.

### Function 8 — exported `click(x, y)` (body at `0x14c`, 4 bytes)

```text
04 00                 ; body size 4, no locals
10 05                 call 5                   ; render (repaint only; both args ignored)
0b                    end
```

Neither parameter is read — click-to-load behaviour lives in the host runner,
which reads the saved records itself.

## Data section (`0x151`)

Three active segments; each is `memory index 0, offset expression
(i32.const N; end), byte count, bytes`:

```text
0b 28 03              ; id 0x0b, payload length 40, 3 segments
00 41 00 0b 05        ; → linear 0x00, 5 bytes
4e 6f 74 65 3a        ;   "Note:"
00 41 10 0b 05        ; → linear 0x10 (16), 5 bytes
57 6f 72 64 73        ;   "Words"
00 41 c0 00 0b 0d     ; → linear 0x40 (64, LEB c0 00), 13 bytes
4e 6f 74 65 73 20 57 65 62 20 47 55 49   ; "Notes Web GUI"
```

The `Notes Web GUI` marker at linear offset 64 is the product-identity string
checked by the binary test; the code never draws it. The input buffer at
linear offset 256 (`0x100`) is *not* in any data segment — fresh Wasm memory
is guaranteed zero-initialised, so the buffer starts empty.

## Verification

`test-notes-web` verifies:

- Wasm magic bytes
- `notes.clear` import anchor
- `init` / `key` export anchor
- `Note:` data bytes
- `Words` data bytes
- `Notes Web GUI` product bytes

`wasmtime compile notes-web.wasm` validates the module on hosts with Wasmtime.
