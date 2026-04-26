# `products/notes/test-notes-linux-arm64`

`test-notes-linux-arm64` is a **344-byte** Linux x86_64 ELF structural verifier
for `./notes-linux-arm64`.

It opens the sibling ARM64 binary and checks:

- `0x000` length 4: `7f 45 4c 46`
- `0x012` length 2: `b7 00` (`EM_AARCH64`)
- `0x098` length 14: `Notes GUI ARM\n`

## Code shape

The verifier uses the same descriptor loop as the other product structural
tests:

```text
open(path, O_RDONLY)
for each descriptor:
    pread64(fd, 0x401000, len, offset)
    repe cmpsb against embedded expected bytes
exit(0) if all match, else exit(1)
```

Syscalls used: `open` (`2`), `pread64` (`17`), and `exit` (`60`).

## Embedded path

```text
notes-linux-arm64
```

## Expected bytes

```text
7f 45 4c 46
b7 00
4e 6f 74 65 73 20 47 55 49 20 41 52 4d 0a
```
