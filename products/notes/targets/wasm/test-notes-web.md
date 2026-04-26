# `products/notes/test-notes-web`

`test-notes-web` is a **413-byte** Linux x86_64 ELF structural verifier for
`./notes-web.wasm`.

It checks six anchored byte ranges:

- `0x000` length 4: `00 61 73 6d`
- `0x020` length 13: first import anchor, `notes.clear`
- `0x084` length 13: export anchor for `init` and `key`
- `0x159` length 5: `Note:`
- `0x163` length 5: `Words`
- `0x16e` length 13: `Notes Web GUI`

## Code shape

The verifier opens `notes-web.wasm`, loops over fixed descriptors, reads each
range with `pread64`, compares with `repe cmpsb`, and exits `0` only if all
ranges match.

Syscalls used:

- `2` = `open`
- `17` = `pread64`
- `60` = `exit`

## Embedded expected bytes

```text
00 61 73 6d
05 05 6e 6f 74 65 73 05 63 6c 65 61 72
04 69 6e 69 74 00 06 03 6b 65 79 00 07
4e 6f 74 65 3a
57 6f 72 64 73
4e 6f 74 65 73 20 57 65 62 20 47 55 49
```
