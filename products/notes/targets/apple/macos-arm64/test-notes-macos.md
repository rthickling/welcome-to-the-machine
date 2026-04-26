# `products/notes/test-notes-macos`

`test-notes-macos` is a **346-byte** Linux x86_64 ELF structural verifier for
`./notes-macos`.

It checks:

- `0x000` length 4: `cf fa ed fe`
- `0x070` length 4: `01 00 00 00`
- `0x09c` length 14: `Notes GUI Mac\n`

The verifier uses only `open`, `pread64`, and `exit`.

## Embedded expected bytes

```text
cf fa ed fe
01 00 00 00
4e 6f 74 65 73 20 47 55 49 20 4d 61 63 0a
```
