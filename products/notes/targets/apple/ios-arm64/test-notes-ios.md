# `products/notes/test-notes-ios`

`test-notes-ios` is a **344-byte** Linux x86_64 ELF structural verifier for
`./notes-ios`.

It checks:

- `0x000` length 4: `cf fa ed fe`
- `0x070` length 4: `02 00 00 00`
- `0x09c` length 12: `NotesGUIiOS\n`

The verifier opens the sibling Mach-O, reads fixed offsets with `pread64`,
compares with `repe cmpsb`, and exits `0` only if all ranges match.

## Embedded expected bytes

```text
cf fa ed fe
02 00 00 00
4e 6f 74 65 73 47 55 49 69 4f 53 0a
```
