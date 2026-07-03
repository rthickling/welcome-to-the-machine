# `products/notes/test-notes-web`

`test-notes-web` is a **413-byte** Linux x86_64 ELF structural verifier for
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
| `r12d` at `0x400094` | `0x400120` | descriptor-table base |
| `r13d` at `0x40009a` | `0x6` | descriptor count |

## Descriptor table (6 × 12 bytes @ `0x400120`)

```text
0x120: 00 00 00 00  04 00 00 00  68 01 40 00   ; file[0x000] len 4  vs [0x400168]
0x12c: 20 00 00 00  0d 00 00 00  6c 01 40 00   ; file[0x020] len 13 vs [0x40016c]
0x138: 84 00 00 00  0d 00 00 00  79 01 40 00   ; file[0x084] len 13 vs [0x400179]
0x144: 59 01 00 00  05 00 00 00  86 01 40 00   ; file[0x159] len 5  vs [0x400186]
0x150: 63 01 00 00  05 00 00 00  8b 01 40 00   ; file[0x163] len 5  vs [0x40018b]
0x15c: 6e 01 00 00  0d 00 00 00  90 01 40 00   ; file[0x16e] len 13 vs [0x400190]
```

## Embedded expected bytes

```text
0x400168: 00 61 73 6d                                  ; "\0asm" wasm magic
0x40016c: 05 05 6e6f746573 05 636c656172               ; import anchor: "notes" . "clear"
0x400179: 04 696e6974 00 06 03 6b6579 00 07            ; export anchor: "init" fn6, "key" fn7
0x400186: 4e 6f 74 65 3a                               ; "Note:"
0x40018b: 57 6f 72 64 73                               ; "Words"
0x400190: 4e6f746573205765622047554                    ; "Notes Web GUI"
```

The import/export anchors (offsets `0x20` and `0x84`) match the section
encoding decoded in
[`notes-web.wasm.md`](notes-web.wasm.md#import-section-0x1e): checking those
raw LEB128-framed name bytes confirms the `notes.clear` import and the
`init`/`key` exports are present and correctly indexed, not just that the file
is "some wasm".

## Verification

- `./test-notes-web` exits `0` on the committed `notes-web.wasm`
- corrupting any anchored range makes it exit `1`
- `wasmtime compile notes-web.wasm` separately validates the module on hosts
  with Wasmtime
