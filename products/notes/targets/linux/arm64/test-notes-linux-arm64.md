# `products/notes/test-notes-linux-arm64`

`test-notes-linux-arm64` is a **608-byte** Linux x86_64 ELF structural verifier
for `./notes-linux-arm64`. It opens the sibling AArch64 binary, reads fixed byte
ranges with `pread64`, compares them against embedded expected bytes, and exits
`0` only if all match.

When the ARM64 target graduated from a `Notes GUI ARM` scaffold to a full
raw-X11 GUI, this verifier grew from 3 structural descriptors to **17
behavioral** ones that lock down the visible product bytes: window title, pane
labels, colour constants, window geometry, request opcodes, the `notes.db`
string, the `WM_DELETE_WINDOW` atom name, and a printable keymap row.

## Machine code

The executable code (`0x400078..0x4000fc`) is the shared descriptor-driven
verifier documented opcode-by-opcode in
[`products/notes/targets/linux/x86_64/test-notes-linux-x86_64.md`](../x86_64/test-notes-linux-x86_64.md#code-walk-through).
Per-target values only:

| Register | Value | Meaning |
| -------- | ----- | ------- |
| `edi` at `0x40007d` | `0x4000fd` | path string `"notes-linux-arm64\0"` |
| `r12d` at `0x400094` | `0x400120` | descriptor-table base |
| `r13d` at `0x40009a` | `0x11` | descriptor count (17) |

## File layout

`mkelf` wraps a `488`-byte body:

```text
0x000..0x077   120   ELF header + PT_LOAD program header
0x078..0x0fc   133   open + descriptor-driven pread64/compare loop + exits
0x0fd..0x11f    35   path string "notes-linux-arm64\0" (padded)
0x120..0x1eb   204   seventeen 12-byte check descriptors
0x1ec..0x25f   116   embedded expected byte ranges
```

Total file size: `608` bytes.

## Descriptor table (17 × 12 bytes @ `0x400120`)

Each descriptor is `u32 file_offset, u32 length, u32 expected_vaddr`. The
anchored ranges into `notes-linux-arm64`:

```text
file 0x0000 len  4   ELF magic            7f 45 4c 46
file 0x0012 len  2   e_machine            b7 00               (EM_AARCH64)
file 0x0078 len  4   entry branch         bb 00 00 14         (b _start)
file 0x1002 len 14   socket path          /tmp/.X11-unix
file 0x1044 len  4   CreateWindow opcode  01 00 0a 00
file 0x1054 len  4   window geometry      58 02 90 01         (600 x 400)
file 0x1064 len  4   background pixel     20 20 20 00
file 0x1084 len  9   window title         notes-arm
file 0x1090 len  4   CreateGC opcode      37 00 06 00
file 0x10a0 len  8   GC fg / bg pixels    e0 e0 e0 00 20 20 20 00
file 0x10b4 len  4   ImageText8 opcode    4c 40 14 00
file 0x1104 len  4   PolyRectangle opcode 43 00 07 00
file 0x1120 len  5   left pane label      Note:
file 0x1128 len  5   right pane label     Words
file 0x1130 len  9   db filename          notes.db\0
file 0x1158 len 16   close atom name      WM_DELETE_WINDOW
file 0x120a len 16   printable keymap     31 32 33 34 35 36 37 38 39 30 2d 3d 08 00 71 77
```

## Embedded path

At `0x4000fd`:

```text
6e 6f 74 65 73 2d 6c 69 6e 75 78 2d 61 72 6d 36 34 00   ; "notes-linux-arm64"
```

## Syscalls used

Exactly three Linux x86_64 syscalls: `2` = `open`, `17` = `pread64`,
`60` = `exit`.

## Verification

- `./test-notes-linux-arm64` exits `0` on the committed `notes-linux-arm64`.
- Corrupting any anchored range — e.g. flipping a byte of the `notes-arm` title,
  the `CreateGC` colour pixels, or the keymap row — makes it exit `1`.

## What this test proves

It proves the committed ARM64 product binary still contains the product-specific
title, pane labels, colour constants, window geometry, X11 request opcodes,
`notes.db` filename, close-atom name, and printable keymap at the expected
anchored offsets. It does **not** prove full GUI runtime behavior — that depends
on a live X server and is exercised under `qemu-aarch64-static` as described in
[`notes-linux-arm64.md`](notes-linux-arm64.md#verification).
