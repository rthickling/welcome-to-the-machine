# `products/notes/test-notes-win64`

`test-notes-win64` is a **525-byte** Linux x86_64 ELF structural verifier for
`./notes-win64.exe`. It opens the sibling PE, reads twelve fixed byte ranges
with `pread64`, compares each against embedded expected bytes with
`repe cmpsb`, and exits `0` only if every range matches.

## Machine code

The executable code (`0x400078..0x4000fc`) is the shared descriptor-driven
verifier documented opcode-by-opcode in
[`products/notes/targets/linux/x86_64/test-notes-linux-x86_64.md`](../../linux/x86_64/test-notes-linux-x86_64.md#code-walk-through).
This binary carries a longer path and table, so its per-target values are:

| Register | Value | Meaning |
| -------- | ----- | ------- |
| `edi` at `0x40007d` | `0x400100` | path string `"notes-win64.exe\0"` |
| `r12d` at `0x400094` | `0x400110` | descriptor-table base |
| `r13d` at `0x40009a` | `0xc` | descriptor count (12) |

## Descriptor table (12 × 12 bytes @ `0x400110`)

```text
0x110: 00 00 00 00  02 00 00 00  a0 01 40 00   ; file[0x000] len 2  vs [0x4001a0]
0x11c: 84 00 00 00  02 00 00 00  a4 01 40 00   ; file[0x084] len 2  vs [0x4001a4]
0x128: dc 00 00 00  02 00 00 00  a8 01 40 00   ; file[0x0dc] len 2  vs [0x4001a8]
0x134: 00 02 00 00  20 00 00 00  ac 01 40 00   ; file[0x200] len 32 vs [0x4001ac]
0x140: 00 08 00 00  07 00 00 00  cc 01 40 00   ; file[0x800] len 7  vs [0x4001cc]
0x14c: 07 08 00 00  05 00 00 00  d4 01 40 00   ; file[0x807] len 5  vs [0x4001d4]
0x158: 0c 08 00 00  08 00 00 00  dc 01 40 00   ; file[0x80c] len 8  vs [0x4001dc]
0x164: 14 08 00 00  07 00 00 00  e4 01 40 00   ; file[0x814] len 7  vs [0x4001e4]
0x170: 2f 08 00 00  04 00 00 00  ec 01 40 00   ; file[0x82f] len 4  vs [0x4001ec]
0x17c: 33 08 00 00  07 00 00 00  f0 01 40 00   ; file[0x833] len 7  vs [0x4001f0]
0x188: f4 03 00 00  06 00 00 00  f8 01 40 00   ; file[0x3f4] len 6  vs [0x4001f8]
0x194: 98 0a 00 00  0d 00 00 00  00 02 40 00   ; file[0xa98] len 13 vs [0x400200]
```

## Embedded expected bytes

```text
0x4001a0: 4d 5a                              ; "MZ" DOS signature
0x4001a4: 64 86                              ; COFF machine = AMD64
0x4001a8: 02 00                              ; Subsystem = Windows GUI
0x4001ac: 48 81 ec e8 01 00 00 31 c9 48 8d 15 f0 05 00 00   ; 32-byte code prefix
          4c 8d 05 04 06 00 00 41 b9 00 00 cf 10 48 c7 44   ;   (prologue + first CreateWindowExA setup)
0x4001cc: 53 54 41 54 49 43 00               ; "STATIC\0"  (parent class)
0x4001d4: 45 44 49 54 00                     ; "EDIT\0"    (editor class)
0x4001dc: 4c 49 53 54 42 4f 58 00            ; "LISTBOX\0" (list class)
0x4001e4: 42 55 54 54 4f 4e 00               ; "BUTTON\0"  (button class)
0x4001ec: 20 68 65 72                        ; " her"  (slice of "Type notes here.")
0x4001f0: 65 2e 00 41 64 64 00               ; "e.\0Add\0" (end of default text + Add label)
0x4001f8: 89 c7 4c 89 e9 ba                  ; interior code slice of the button-handler path
0x400200: 53 65 6e 64 4d 65 73 73 61 67 65 41 00   ; "SendMessageA\0" import hint/name
```

The class strings, labels, code prefix, and the `SendMessageA` import are all
decoded in context in
[`notes-win64.exe.md`](notes-win64.exe.md#code-walkthrough-file-0x200--va-0x140001000).
Checking the 32-byte code prefix (descriptor 4) and the button-handler slice
(descriptor 11) means a regression in the actual instructions — not just the
strings — fails the test.

## Verification

- `./test-notes-win64` exits `0` on the committed `notes-win64.exe`
- corrupting any anchored range makes it exit `1`
- with Wine installed, `wine notes-win64.exe` runs the GUI itself
