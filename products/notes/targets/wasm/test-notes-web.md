# `products/notes/test-notes-web`

`test-notes-web` is a **452-byte** Linux x86_64 ELF structural verifier for
`./notes-web.wasm`. It opens the sibling module, reads fixed byte ranges with
`pread64`, compares them against embedded expected bytes with `repe cmpsb`, and
exits `0` only if all ranges match.

## Machine code

The executable code (`0x400078..0x4000fc`) is the shared descriptor-driven
verifier documented opcode-by-opcode in
[`products/notes/targets/linux/x86_64/test-notes-linux-x86_64.md`](../linux/x86_64/test-notes-linux-x86_64.md#code-walk-through).
Per-target values only:

| Register | Value | Meaning |
| -------- | ----- | ------- |
| `edi` at `0x40007d` | `0x4000fd` | path string `"notes-web.wasm\0"` |
| `r12d` at `0x400096` | `0x400120` | descriptor-table base |
| `r13d` at `0x40009c` | `0x8` | descriptor count |

## Descriptor table (8 × 12 bytes @ `0x400120`)

```text
0x120: 00 00 00 00  04 00 00 00  80 01 40 00   ; file[0x000] len 4  vs [0x400180]
0x12c: 20 00 00 00  0d 00 00 00  84 01 40 00   ; file[0x020] len 13 vs [0x400184]
0x138: 64 00 00 00  08 00 00 00  91 01 40 00   ; file[0x064] len 8  vs [0x400191]
0x144: 8a 00 00 00  0d 00 00 00  99 01 40 00   ; file[0x08a] len 13 vs [0x400199]
0x150: 9f 00 00 00  07 00 00 00  a6 01 40 00   ; file[0x09f] len 7  vs [0x4001a6]
0x15c: e1 02 00 00  05 00 00 00  ad 01 40 00   ; file[0x2e1] len 5  vs [0x4001ad]
0x168: eb 02 00 00  05 00 00 00  b2 01 40 00   ; file[0x2eb] len 5  vs [0x4001b2]
0x174: f6 02 00 00  0d 00 00 00  b7 01 40 00   ; file[0x2f6] len 13 vs [0x4001b7]
```

## Embedded expected bytes

```text
0x400180: 00 61 73 6d                                  ; "\0asm" wasm magic
0x400184: 05 05 6e6f746573 05 636c656172               ; import anchor: "notes" . "clear"
0x400191: 03 06 05 00 00 01 02 01                      ; Function section: 5 funcs, types 0,0,1,2,1
0x400199: 04 696e6974 00 06 03 6b6579 00 07            ; export anchor: "init" fn6, "key" fn7
0x4001a6: 04 6c6f6164 00 09                            ; export anchor: "load" fn9 (persistence entry)
0x4001ad: 4e 6f 74 65 3a                               ; "Note:"
0x4001b2: 57 6f 72 64 73                               ; "Words"
0x4001b7: 4e6f746573205765622047554 9                  ; "Notes Web GUI"
```

The import/export anchors (offsets `0x20`, `0x8a`, `0x9f`) match the section
encoding decoded in
[`notes-web.wasm.md`](notes-web.wasm.md#import-section-0x1e): checking those
raw LEB128-framed name bytes confirms the `notes.clear` import plus the
`init`/`key`/`load` exports are present and correctly indexed. The Function
section anchor (`0x64`) pins the five defined functions and their type indices,
so the new `load` handler and re-typed table cannot regress silently.

## Verification

- `./test-notes-web` exits `0` on the committed `notes-web.wasm`
- corrupting any anchored range makes it exit `1`
- `wasmtime compile notes-web.wasm` separately validates the module on hosts
  with Wasmtime
