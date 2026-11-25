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
0x12c: 2f 00 00 00  0e 00 00 00  84 01 40 00   ; file[0x02f] len 14 vs [0x400184]
0x138: 5c 00 00 00  0f 00 00 00  92 01 40 00   ; file[0x05c] len 15 vs [0x400192]
0x144: 80 00 00 00  0d 00 00 00  a1 01 40 00   ; file[0x080] len 13 vs [0x4001a1]
0x150: 8d 00 00 00  07 00 00 00  ae 01 40 00   ; file[0x08d] len 7  vs [0x4001ae]
0x15c: 3e 08 00 00  05 00 00 00  b5 01 40 00   ; file[0x83e] len 5  vs [0x4001b5]
0x168: 4a 08 00 00  05 00 00 00  ba 01 40 00   ; file[0x84a] len 5  vs [0x4001ba]
0x174: 56 08 00 00  03 00 00 00  bf 01 40 00   ; file[0x856] len 3  vs [0x4001bf]
```

## Embedded expected bytes

```text
0x400180: 00 61 73 6d                                  ; "\0asm" wasm magic
0x400184: 05 6e6f746573 07 7072657365 6e74            ; import anchor: "notes" . "present"
0x400192: 03 0d 0c 03 04 05 04 04 00 00 01 01 01 01 02  ; Function section: 12 funcs
0x4001a1: 04 696e6974 00 09 03 6b6579 00 0a            ; export anchor: "init" fn9, "key" fn10
0x4001ae: 04 6c6f6164 00 0b                            ; export anchor: "load" fn11
0x4001b5: 4e 6f 74 65 3a                               ; "Note:"
0x4001ba: 57 6f 72 64 73                               ; "Words"
0x4001bf: 44 65 6c                                     ; "Del"
```

The import/export anchors match the framebuffer module's `notes.present` import
and `init`/`key`/`load`/`click` exports documented in
[`notes-web.wasm.md`](notes-web.wasm.md).

## Verification

- `./test-notes-web` exits `0` on the committed `notes-web.wasm`
- corrupting any anchored range makes it exit `1`
- `wasmtime compile notes-web.wasm` separately validates the module on hosts
  with Wasmtime
