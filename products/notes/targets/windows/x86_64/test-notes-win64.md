# `products/notes/test-notes-win64`

`test-notes-win64` is a **553-byte** Linux x86_64 ELF structural verifier for
`./notes-win64.exe`. It opens the sibling PE, reads fourteen fixed byte ranges
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
| `r13d` at `0x40009a` | `0xe` | descriptor count (14) |

## Descriptor table (14 × 12 bytes @ `0x400110`)

```text
0x110: 00 00 00 00  02 00 00 00  b8 01 40 00   ; file[0x000] len 2  vs [0x4001b8]
0x11c: 84 00 00 00  02 00 00 00  ba 01 40 00   ; file[0x084] len 2  vs [0x4001ba]
0x128: dc 00 00 00  02 00 00 00  bc 01 40 00   ; file[0x0dc] len 2  vs [0x4001bc]
0x134: 00 02 00 00  20 00 00 00  be 01 40 00   ; file[0x200] len 32 vs [0x4001be]
0x140: 00 08 00 00  07 00 00 00  de 01 40 00   ; file[0x800] len 7  vs [0x4001de]
0x14c: 07 08 00 00  05 00 00 00  e5 01 40 00   ; file[0x807] len 5  vs [0x4001e5]
0x158: 0c 08 00 00  08 00 00 00  ea 01 40 00   ; file[0x80c] len 8  vs [0x4001ea]
0x164: 14 08 00 00  07 00 00 00  f2 01 40 00   ; file[0x814] len 7  vs [0x4001f2]
0x170: 2f 08 00 00  04 00 00 00  f9 01 40 00   ; file[0x82f] len 4  vs [0x4001f9]
0x17c: 33 08 00 00  07 00 00 00  fd 01 40 00   ; file[0x833] len 7  vs [0x4001fd]
0x188: f6 03 00 00  05 00 00 00  04 02 40 00   ; file[0x3f6] len 5  vs [0x400204]
0x194: 9a 0a 00 00  0d 00 00 00  09 02 40 00   ; file[0xa9a] len 13 vs [0x400209]
0x1a0: 00 0b 00 00  08 00 00 00  16 02 40 00   ; file[0xb00] len 8  vs [0x400216]
0x1ac: 62 06 00 00  0b 00 00 00  1e 02 40 00   ; file[0x662] len 11 vs [0x40021e]
```

## Embedded expected bytes

```text
0x4001b8: 4d 5a                              ; "MZ" DOS signature
0x4001ba: 64 86                              ; COFF machine = AMD64
0x4001bc: 02 00                              ; Subsystem = Windows GUI
0x4001be: 48 81 ec e8 01 00 00 31 c9 48 8d 15 f0 05 00 00   ; 32-byte code prefix
          4c 8d 05 04 06 00 00 41 b9 00 00 cf 10 48 c7 44   ;   (prologue + first CreateWindowExA setup)
0x4001de: 53 54 41 54 49 43 00               ; "STATIC\0"  (parent class)
0x4001e5: 45 44 49 54 00                     ; "EDIT\0"    (editor class)
0x4001ea: 4c 49 53 54 42 4f 58 00            ; "LISTBOX\0" (list class)
0x4001f2: 42 55 54 54 4f 4e 00               ; "BUTTON\0"  (button class)
0x4001f9: 20 68 65 72                        ; " her"  (slice of "Type notes here.")
0x4001fd: 65 2e 00 41 64 64 00               ; "e.\0Add\0" (end of default text + Add label)
0x400204: e8 05 07 00 00                     ; the `call load_notes` that replaced the seed block
0x400209: 53 65 6e 64 4d 65 73 73 61 67 65 41 00   ; "SendMessageA\0" import name
0x400216: 56 48 81 ec 40 01 00 00            ; load_notes prologue (push rsi; sub rsp,0x140)
0x40021e: 43 72 65 61 74 65 46 69 6c 65 41   ; "CreateFileA" new KERNEL32 import name
```

The class strings, labels, code prefix, and imports are decoded in context in
[`notes-win64.exe.md`](notes-win64.exe.md#code-walkthrough-file-0x200--va-0x140001000).
Descriptor 4 pins the 32-byte code prefix, descriptor 11 pins the `call
load_notes` that replaced the two seed strings, descriptor 13 pins the
`load_notes` prologue, and descriptor 14 pins the added `CreateFileA` import —
so a regression in the persistence wiring (not just the UI strings) fails the
test.

## Verification

- `./test-notes-win64` exits `0` on the committed `notes-win64.exe`
- corrupting any anchored range makes it exit `1`
- with Wine installed, `wine notes-win64.exe` runs the GUI itself
