# `products/notes/test-notes-winarm64`

`test-notes-winarm64` is a **377-byte** Linux x86_64 ELF structural verifier
for `./notes-winarm64.exe`. It opens the sibling PE, reads fixed byte ranges
with `pread64`, compares them against embedded expected bytes with
`repe cmpsb`, and exits `0` only if all match.

## Machine code

The executable code (`0x400078..0x4000fc`) is the shared descriptor-driven
verifier documented opcode-by-opcode in
[`products/notes/targets/linux/x86_64/test-notes-linux-x86_64.md`](../../linux/x86_64/test-notes-linux-x86_64.md#code-walk-through).
Per-target values only:

| Register | Value | Meaning |
| -------- | ----- | ------- |
| `edi` at `0x40007d` | `0x4000fd` | path string `"notes-winarm64.exe\0"` |
| `r12d` at `0x400094` | `0x400120` | descriptor-table base |
| `r13d` at `0x40009a` | `0x5` | descriptor count |

## Descriptor table (5 × 12 bytes @ `0x400120`)

```text
0x120: 00 00 00 00  02 00 00 00  5c 01 40 00   ; file[0x000] len 2  vs [0x40015c]
0x12c: 84 00 00 00  02 00 00 00  5e 01 40 00   ; file[0x084] len 2  vs [0x40015e]
0x138: dc 00 00 00  02 00 00 00  60 01 40 00   ; file[0x0dc] len 2  vs [0x400160]
0x144: 00 02 00 00  08 00 00 00  62 01 40 00   ; file[0x200] len 8  vs [0x400162]
0x150: 30 02 00 00  0f 00 00 00  6a 01 40 00   ; file[0x230] len 15 vs [0x40016a]
```

## Embedded expected bytes

```text
0x40015c: 4d 5a                                       ; "MZ" DOS signature
0x40015e: 64 aa                                        ; COFF machine = IMAGE_FILE_MACHINE_ARM64
0x400160: 02 00                                        ; Subsystem = IMAGE_SUBSYSTEM_WINDOWS_GUI
0x400162: 00 00 80 52 c0 03 5f d6                       ; entry stub: mov w0,#0 ; ret
0x40016a: 4e6f746573204755492041524d 0d 0a             ; "Notes GUI ARM\r\n"
```

The fourth check is the only *code* check: it matches the two AArch64
instruction words of the entry stub. `00 00 80 52` is `movz w0, #0` and
`c0 03 5f d6` is `ret` — both decoded bit-by-bit in
[`notes-winarm64.exe.md`](notes-winarm64.exe.md#entry-stub-encodings). This
catches a corrupted or mis-assembled stub, not merely a wrong string.

## Verification

- `./test-notes-winarm64` exits `0` on the committed `notes-winarm64.exe`
- corrupting the machine type, subsystem, entry stub, or marker makes it exit `1`
