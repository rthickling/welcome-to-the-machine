# `products/notes/test-notes-ios`

`test-notes-ios` is a **344-byte** Linux x86_64 ELF structural verifier for
`./notes-ios`. It opens the sibling Mach-O, reads fixed byte ranges with
`pread64`, compares them against embedded expected bytes with `repe cmpsb`, and
exits `0` only if all ranges match.

## Machine code

The executable code (`0x400078..0x4000fc`) is the shared descriptor-driven
verifier documented opcode-by-opcode in
[`products/notes/targets/linux/x86_64/test-notes-linux-x86_64.md`](../../linux/x86_64/test-notes-linux-x86_64.md#code-walk-through).
Per-target values only:

| Register | Value | Meaning |
| -------- | ----- | ------- |
| `edi` at `0x40007d` | `0x4000fd` | path string `"notes-ios\0"` |
| `r12d` at `0x400094` | `0x400120` | descriptor-table base |
| `r13d` at `0x40009a` | `0x3` | descriptor count |

## Descriptor table (3 × 12 bytes @ `0x400120`)

```text
0x120: 00 00 00 00  04 00 00 00  44 01 40 00   ; file[0x000] len 4  vs [0x400144]
0x12c: 70 00 00 00  04 00 00 00  48 01 40 00   ; file[0x070] len 4  vs [0x400148]
0x138: 9c 00 00 00  0c 00 00 00  4c 01 40 00   ; file[0x09c] len 12 vs [0x40014c]
```

## Embedded expected bytes

```text
0x400144: cf fa ed fe                        ; MH_MAGIC_64 (Mach-O 64-bit)
0x400148: 02 00 00 00                        ; LC_BUILD_VERSION platform = iOS
0x40014c: 4e 6f 74 65 73 47 55 49 69 4f 53 0a ; "NotesGUIiOS\n"
```

The only differences from the macOS sibling are the platform word (`2` = iOS vs
`1` = macOS) and the 12-byte payload string.

## Verification

- `./test-notes-ios` exits `0` on the committed `notes-ios`
- changing the platform byte at target offset `0x70` makes it exit `1`
