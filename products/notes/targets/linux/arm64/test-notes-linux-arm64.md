# `products/notes/test-notes-linux-arm64`

`test-notes-linux-arm64` is a **344-byte** Linux x86_64 ELF structural verifier
for `./notes-linux-arm64`. It opens the sibling AArch64 binary, reads fixed
byte ranges with `pread64`, compares them against embedded expected bytes, and
exits `0` only if all match.

## Machine code

The executable code (`0x400078..0x4000fc`) is the shared descriptor-driven
verifier documented opcode-by-opcode in
[`products/notes/targets/linux/x86_64/test-notes-linux-x86_64.md`](../x86_64/test-notes-linux-x86_64.md#code-walk-through).
Per-target values only:

| Register | Value | Meaning |
| -------- | ----- | ------- |
| `edi` at `0x40007d` | `0x4000fd` | path string `"notes-linux-arm64\0"` |
| `r12d` at `0x400094` | `0x400120` | descriptor-table base |
| `r13d` at `0x40009a` | `0x3` | descriptor count |

## Descriptor table (3 × 12 bytes @ `0x400120`)

```text
0x120: 00 00 00 00  04 00 00 00  44 01 40 00   ; file[0x000] len 4  vs [0x400144]
0x12c: 12 00 00 00  02 00 00 00  48 01 40 00   ; file[0x012] len 2  vs [0x400148]
0x138: 98 00 00 00  0e 00 00 00  4a 01 40 00   ; file[0x098] len 14 vs [0x40014a]
```

## Embedded expected bytes

```text
0x400144: 7f 45 4c 46                              ; ELF magic
0x400148: b7 00                                    ; e_machine = EM_AARCH64 (0xb7) at ELF offset 0x12
0x40014a: 4e 6f 74 65 73 20 47 55 49 20 41 52 4d 0a ; "Notes GUI ARM\n"
```

The middle check reads the two-byte `e_machine` field at ELF header offset
`0x12`, which must be `b7 00` (`EM_AARCH64`) — this is what distinguishes the
ARM64 product from the x86_64 one.

## Verification

- `./test-notes-linux-arm64` exits `0` on the committed `notes-linux-arm64`
- corrupting the machine-type or payload bytes makes it exit `1`
