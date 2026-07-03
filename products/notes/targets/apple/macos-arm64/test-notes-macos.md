# `products/notes/test-notes-macos`

`test-notes-macos` is a **346-byte** Linux x86_64 ELF structural verifier for
`./notes-macos`. It does not execute the Mach-O target; it opens it, reads
fixed byte ranges with `pread64`, and compares them against embedded expected
bytes, exiting `0` only if every range matches.

## Machine code

The executable code (`0x400078..0x4000fc`) is the shared descriptor-driven
verifier documented opcode-by-opcode in
[`products/notes/targets/linux/x86_64/test-notes-linux-x86_64.md`](../../linux/x86_64/test-notes-linux-x86_64.md#code-walk-through).
This binary's only per-target values are:

| Register | Value | Meaning |
| -------- | ----- | ------- |
| `edi` at `0x40007d` | `0x4000fd` | pointer to the path string `"notes-macos\0"` |
| `r12d` at `0x400094` | `0x400120` | descriptor-table base |
| `r13d` at `0x40009a` | `0x3` | descriptor count |

## Descriptor table (3 × 12 bytes @ `0x400120`)

Each descriptor is `{u32 file_offset, u32 length, u32 expected_VA}` (see the
[shared format](../../linux/x86_64/test-notes-linux-x86_64.md#the-shared-descriptor-driven-verifier-canonical-reference)):

```text
0x120: 00 00 00 00  04 00 00 00  44 01 40 00   ; file[0x000] len 4  vs [0x400144]
0x12c: 70 00 00 00  04 00 00 00  48 01 40 00   ; file[0x070] len 4  vs [0x400148]
0x138: 9c 00 00 00  0e 00 00 00  4c 01 40 00   ; file[0x09c] len 14 vs [0x40014c]
```

## Embedded expected bytes

```text
0x400144: cf fa ed fe                              ; MH_MAGIC_64 (Mach-O 64-bit)
0x400148: 01 00 00 00                              ; LC_BUILD_VERSION platform = macOS
0x40014c: 4e 6f 74 65 73 20 47 55 49 20 4d 61 63 0a ; "Notes GUI Mac\n"
```

So the three checks are: the file is a 64-bit Mach-O, its `LC_BUILD_VERSION`
platform word at offset `0x70` is `1` (macOS), and the product payload at
offset `0x9c` is intact.

## Verification

- `./test-notes-macos` exits `0` on the committed `notes-macos`
- flipping the platform byte at target offset `0x70` from `01` to `02` makes it
  exit `1`; restoring it returns to `0`
