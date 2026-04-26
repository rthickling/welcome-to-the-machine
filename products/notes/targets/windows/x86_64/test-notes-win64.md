# `products/notes/test-notes-win64`

`test-notes-win64` is a **525-byte** ELF64 x86_64 structural verifier for
`notes-win64.exe`.

The verifier opens the sibling file named:

```text
notes-win64.exe
```

It performs twelve `pread64` checks against fixed byte ranges.

## Checked anchors

```text
0x000, length 0x02   MZ signature
0x084, length 0x02   AMD64 PE machine type
0x0dc, length 0x02   Windows GUI subsystem
0x200, length 0x20   two-pane GUI code prefix
0x800, length 0x07   STATIC parent-window class
0x807, length 0x05   EDIT editor class
0x80c, length 0x08   LISTBOX right-pane class
0x814, length 0x07   BUTTON class
0x82f, length 0x04   Add button label
0x833, length 0x07   Delete button label
0x3f4, length 0x06   LB_DELETESTRING send path
0xa98, length 0x0d   SendMessageA hint/name entry
```

## Behavior

For each descriptor, the executable:

1. Reads the target range from `notes-win64.exe` into a stack buffer.
2. Compares it with the embedded expected byte string.
3. Continues until all descriptors pass.

It exits `0` when every check passes and exits `1` on open, read, or compare
failure.

## Run

```bash
cd products/notes/targets/windows/x86_64
./test-notes-win64
```
