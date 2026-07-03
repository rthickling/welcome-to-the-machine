# `products/notes/targets/wasm/notes-web.wasm`

`notes-web.wasm` is a **771-byte** browser-hosted WebAssembly module for the
Notes product. The module now owns the product behaviour that used to live in
host glue — the note list, first-word derivation, list rendering, and
click-to-load hit-testing are all inside the module:

- imported drawing calls render the note and list panes
- exported `init` paints the initial UI
- exported `key(code)` edits the in-Wasm input buffer
- `Enter` calls the imported `save(ptr, len)` host persistence hook
- exported `load(len)` parses `[u32 length][bytes]` records the host has written
  into exported memory, builds an in-module index (offset, length, first-word
  length per note), and renders the list rows
- exported `click(x, y)` hit-tests the list pane, loads the clicked note back
  into the editor buffer, and repaints

Persistence itself stays host-side (browser `localStorage`), per the approved
web policy in [`web-plan.md`](web-plan.md): the host serialises stored records
into module memory and calls `load`. The committed deliverable is the `.wasm`
binary, its binary test, and this byte-level documentation.

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
| `click(x, y)` | `(i32, i32) -> ()` | Hit-test the list pane; load the clicked note into the editor and repaint. |
| `load(len)` | `(i32) -> ()` | Parse `len` bytes of records from `0x200`, build the list index, and render. |

The host should pass normal printable ASCII bytes to `key`, including uppercase
letters and shifted symbols after browser keyboard translation. The module also
handles `8` as Backspace and `13` as Enter.

### Linear-memory layout

The module fixes these regions in its single 64 KiB page:

| Address | Purpose |
| --- | --- |
| `0x000` | `"Note:"` label bytes (data segment 0) |
| `0x010` | `"Words"` label bytes (data segment 1) |
| `0x040` | `"Notes Web GUI"` product marker (data segment 2) |
| `0x100` | editor input buffer (up to 63 bytes; length in global 0) |
| `0x200` | record staging/storage area — the host writes `[u32 length][bytes]` records here before calling `load` |
| `0x800` | list index table: 12 bytes per note — `[u32 text offset][u32 text length][u32 first-word length]` |

The host contract for `load`: write the concatenated records starting at
`0x200`, then call `load(total_byte_count)`. The module parses in place (it
indexes into the staging area rather than copying), so records must stay below
the index table at `0x800`.

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
Section map of this 771-byte (`0x303`) file:

```text
0x000..0x007  magic "\0asm" + version 1
0x008..0x01d  Type      (id 0x01, 20-byte payload)
0x01e..0x063  Import    (id 0x02, 68-byte payload)
0x064..0x06b  Function  (id 0x03, 6-byte payload)   ; now 5 functions
0x06c..0x070  Memory    (id 0x05, 3-byte payload)
0x071..0x07d  Global    (id 0x06, 11-byte payload)  ; now 2 globals
0x07e..0x0a5  Export    (id 0x07, 38-byte payload)  ; now 5 exports
0x0a6..0x2d8  Code      (id 0x0a, 560-byte payload) ; 5 bodies
0x2d9..0x302  Data      (id 0x0b, 40-byte payload)
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

### Function, memory, and global sections (`0x64`, `0x6c`, `0x71`)

```text
03 06 05 00 00 01 02 01  ; 5 defined functions with type indices 0,0,1,2,1:
                         ;   function 5: () -> ()         (render helper)
                         ;   function 6: () -> ()         (init)
                         ;   function 7: (i32) -> ()      (key)
                         ;   function 8: (i32, i32) -> () (click)
                         ;   function 9: (i32) -> ()      (load)
05 03 01 00 01           ; 1 linear memory, limits: min 1 page (64 KiB)
06 0b 02                 ; global section, payload 11, 2 globals
   7f 01 41 00 0b        ;   global 0: i32, mutable, init (i32.const 0)
   7f 01 41 00 0b        ;   global 1: i32, mutable, init (i32.const 0)
```

Global 0 is the **current input length**; global 1 is the **note count** —
the two pieces of mutable state outside linear memory.

### Export section (`0x7e`)

```text
07 26 05                    ; id, payload length 38, 5 exports
06 6d656d6f7279 02 00       ; "memory" kind 2 (memory), index 0
04 696e6974     00 06       ; "init"   kind 0 (function), index 6
03 6b6579       00 07       ; "key"    function 7
05 636c69636b   00 08       ; "click"  function 8
04 6c6f6164     00 09       ; "load"   function 9
```

## Code section (`0xa6`), instruction by instruction

```text
0a b0 04 05    ; id 0x0a, payload length 560 (LEB128 b0 04), 5 bodies
```

Body sizes: function 5 = 137, function 6 = 4, function 7 = 97, function 8 = 139,
function 9 = 174 bytes (each preceded by its own LEB128 size prefix).

### Function 5 — render helper (`89 01` = 137 bytes)

Wasm is a stack machine: `i32.const` pushes an argument, `call` pops the
callee's arguments. This body draws the static panes, the editor text, and the
`Words` label, then loops over the in-module note index drawing one first-word
row per note.

```text
89 01                 ; body size 137
01 01 7f              ; 1 local group: 1 × i32 (local 0 = loop counter i)
10 00                 call 0                   ; clear()
41 a0 c0 80 01        i32.const 0x202020       ; background
41 e0 c1 83 07        i32.const 0xe0e0e0       ; foreground
10 01                 call 1                   ; style(...)
41 08 41 14 41 ca 02 41 34 10 02   ; rect(8, 20, 330, 52)   left pane
41 de 02 41 14 41 ee 01 41 de 02 10 02  ; rect(350, 20, 238, 350) right pane
41 10 41 1e 41 00 41 05 10 03      ; text(16, 30, 0, 5)     "Note:"
41 10 41 2e 41 80 02 23 00 10 03   ; text(16, 46, 256, global0)  live editor
41 e8 02 41 1e 41 10 41 05 10 03   ; text(360, 30, 16, 5)   "Words"
; --- list loop over notes ---
41 00 21 00           i32.const 0; local.set 0   ; i = 0
02 40                 block
03 40                 loop
  20 00 23 01 4e 0d 01     local.get 0; global.get 1; i32.ge_s; br_if 1  ; i >= count → break
  41 e8 02                 i32.const 360                                 ; x
  20 00 41 10 6c 41 30 6a  local.get 0; i32.const 16; i32.mul; i32.const 48; i32.add  ; y = 48 + i*16
  41 80 10 20 00 41 0c 6c 6a 28 02 00   ; i32.load [0x800 + i*12]       ; note text offset
  41 80 10 20 00 41 0c 6c 6a 28 02 08   ; i32.load offset=8 [0x800+i*12] ; first-word length
  10 03                   call 3                                        ; text(360, y, off, fwlen)
  20 00 41 01 6a 21 00    local.get 0; i32.const 1; i32.add; local.set 0 ; i++
  0c 00                   br 0
0b                    end                        ; loop
0b                    end                        ; block
0b                    end                        ; function
```

### Function 6 — exported `init` (`04` = 4 bytes)

```text
04                    ; body size 4
00                    ; no locals
10 05                 call 5                   ; render
0b                    end
```

### Function 7 — exported `key(code)` (`61` = 97 bytes)

One `if/else` chain on the key code (`local 0`), then an unconditional
repaint. `04 40` is `if` with empty block type; an empty *then* branch
followed immediately by `05` (`else`) is how "do nothing unless" is encoded.

```text
61                    ; body size 97
00                    ; no locals
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
      20 00 41 ff 00 49  local.get 0; i32.const 127; i32.lt_u  ; code <_u 127 ?
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

**Quirk fix:** the previous build's upper-bound test used `41 7f`, which in
*signed* LEB128 decodes to **−1**, so the check `code <_u 0xFFFFFFFF` accepted
every code above 31. This build encodes 127 correctly as the two-byte LEB
`ff 00`, so the printable path now runs only for `31 < code < 127` — exactly
the printable-ASCII range `[32, 126]`.

### Function 8 — exported `click(x, y)` (`8b 01` = 139 bytes)

The parameters are `local 0 = x`, `local 1 = y`; three extra locals hold the
hit-test row, a copy index, and the note length. If the click lands on a list
row the module copies that note's full text into the editor buffer at `0x100`
and sets the editor length (global 0). The `block` acts as an early-exit guard:
any failed bound check `br_if 0` jumps to the final `render`.

```text
8b 01                 ; body size 139
01 03 7f              ; 3 × i32 locals (2 = row, 3 = copy index j, 4 = note length)
02 40                 block
  20 00 41 de 02 48 0d 00   local.get 0; i32.const 350; i32.lt_s; br_if 0  ; x < 350 → skip
  20 00 41 cc 04 4e 0d 00   local.get 0; i32.const 588; i32.ge_s; br_if 0  ; x >= 588 → skip
  20 01 41 30 48 0d 00      local.get 1; i32.const 48;  i32.lt_s; br_if 0  ; y < 48 → skip
  20 01 41 30 6b 41 10 6d 21 02   local.get 1; i32.const 48; i32.sub; i32.const 16; i32.div_s; local.set 2  ; row = (y-48)/16
  20 02 41 00 48 0d 00      local.get 2; i32.const 0; i32.lt_s; br_if 0    ; row < 0 → skip
  20 02 23 01 4e 0d 00      local.get 2; global.get 1; i32.ge_s; br_if 0   ; row >= count → skip
  41 80 10 20 02 41 0c 6c 6a 28 02 04   i32.load offset=4 [0x800 + row*12] ; note length
  21 04                     local.set 4
  20 04 41 3f 4a            local.get 4; i32.const 63; i32.gt_s
  04 40 41 3f 21 04 0b      if (len > 63) { len = 63 }                     ; clamp to buffer
  41 00 21 03               i32.const 0; local.set 3                       ; j = 0
  02 40                     block
  03 40                     loop
    20 03 20 04 4e 0d 01    local.get 3; local.get 4; i32.ge_s; br_if 1    ; j >= len → done
    41 80 02 20 03 6a       i32.const 256; local.get 3; i32.add            ; dst = 0x100 + j
    41 80 10 20 02 41 0c 6c 6a 28 02 00   i32.load [0x800 + row*12]        ; src note offset
    20 03 6a 2d 00 00       local.get 3; i32.add; i32.load8_u             ; src byte
    3a 00 00               i32.store8                                     ; editor[j] = byte
    20 03 41 01 6a 21 03    local.get 3; i32.const 1; i32.add; local.set 3 ; j++
    0c 00                  br 0
  0b                       end                     ; loop
  0b                       end                     ; block
  20 04 24 00              local.get 4; global.set 0   ; editor length = note length
0b                    end                        ; guard block
10 05                 call 5                     ; render
0b                    end
```

### Function 9 — exported `load(len)` (`ae 01` = 174 bytes)

Parses the staging area at `0x200`. `local 0 = len` (total bytes the host
wrote); locals 1–4 are `pos`, `count`, `recLen`, and the first-word scan index
`fw`. For each `[u32 length][bytes]` record it writes a 12-byte index entry at
`0x800 + count*12` (`[offset][length][first-word length]`), where first-word
length is the byte count up to the first space (`0x20`) or the record end.

```text
ae 01                 ; body size 174
01 04 7f              ; 4 × i32 locals (1 = pos, 2 = count, 3 = recLen, 4 = fw)
41 00 21 01           i32.const 0; local.set 1     ; pos = 0
41 00 21 02           i32.const 0; local.set 2     ; count = 0
02 40                 block
03 40                 loop
  20 01 41 04 6a 20 00 4a 0d 01   local.get 1; i32.const 4; i32.add; local.get 0; i32.gt_s; br_if 1  ; pos+4 > len → stop
  41 80 04 20 01 6a 28 02 00 21 03   i32.load [0x200 + pos]; local.set 3   ; recLen
  20 01 41 04 6a 21 01            local.get 1; i32.const 4; i32.add; local.set 1  ; pos += 4
  20 03 41 00 4c 0d 01            local.get 3; i32.const 0; i32.le_s; br_if 1     ; recLen <= 0 → stop
  20 01 20 03 6a 20 00 4a 0d 01   local.get 1; local.get 3; i32.add; local.get 0; i32.gt_s; br_if 1  ; pos+recLen > len → stop
  ; index[count].offset = 0x200 + pos
  41 80 10 20 02 41 0c 6c 6a      i32.const 0x800; local.get 2; i32.const 12; i32.mul; i32.add  ; entry addr
  41 80 04 20 01 6a               i32.const 0x200; local.get 1; i32.add                          ; text offset
  36 02 00                        i32.store
  ; index[count].length = recLen
  41 80 10 20 02 41 0c 6c 6a 20 03 36 02 04   i32.store offset=4  ; entry+4 = recLen
  ; first-word scan
  41 00 21 04           i32.const 0; local.set 4    ; fw = 0
  02 40                 block
  03 40                 loop
    20 04 20 03 4e 0d 01           local.get 4; local.get 3; i32.ge_s; br_if 1   ; fw >= recLen → stop
    41 80 04 20 01 6a 20 04 6a 2d 00 00   i32.load8_u [0x200 + pos + fw]         ; byte
    41 20 46 0d 01                 i32.const 32; i32.eq; br_if 1                 ; space → stop
    20 04 41 01 6a 21 04           local.get 4; i32.const 1; i32.add; local.set 4 ; fw++
    0c 00                          br 0
  0b                    end        ; loop
  0b                    end        ; block
  41 80 10 20 02 41 0c 6c 6a 20 04 36 02 08   i32.store offset=8  ; entry+8 = fw
  20 01 20 03 6a 21 01            local.get 1; local.get 3; i32.add; local.set 1  ; pos += recLen
  20 02 41 01 6a 21 02            local.get 2; i32.const 1; i32.add; local.set 2  ; count++
  0c 00                 br 0
0b                    end          ; loop
0b                    end          ; block
20 02 24 01           local.get 2; global.set 1     ; note count = count
10 05                 call 5                          ; render
0b                    end
```

## Data section (`0x2d9`)

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
- Function section (5 functions, type indices `0,0,1,2,1`)
- `init` / `key` export anchor
- `load` export anchor (the persistence entry point)
- `Note:` data bytes
- `Words` data bytes
- `Notes Web GUI` product bytes

`wasmtime compile notes-web.wasm` validates the module on hosts with Wasmtime.
