# `products/notes/notes-linux-arm64`

`notes-linux-arm64` is a **166-byte** Linux ELF64 AArch64 executable. It is the
first ARM64 Notes GUI scaffold artifact: a minimal native scaffold executable derived
from [`../../../../../experiments/poc-06-linux-arm64/hello`](../../../../../experiments/poc-06-linux-arm64/hello.md), with the payload changed to:

```text
Notes GUI ARM
```

This artifact proves the Linux ARM64 executable container and syscall path for a
Notes GUI target. The full raw-X11 GUI behavior remains specified in
[`linux-arm64-plan.md`](linux-arm64-plan.md).

## File layout

```text
0x000..0x03f   64   ELF64 header
0x040..0x077   56   single PT_LOAD program header
0x078..0x097   32   AArch64 code
0x098..0x0a5   14   string "Notes GUI ARM\n"
```

## Code bytes

The code region is unchanged from the ARM64 POC:

```text
01 01 00 10   adr   x1, msg
20 00 80 d2   mov   x0, #1
c2 01 80 d2   mov   x2, #14
08 08 80 d2   mov   x8, #64
01 00 00 d4   svc   #0        ; write(1, msg, 14)
00 00 80 d2   mov   x0, #0
a8 0b 80 d2   mov   x8, #93
01 00 00 d4   svc   #0        ; exit(0)
```

## Product bytes

At file offset `0x98`:

```text
4e 6f 74 65 73 20 47 55 49 20 41 52 4d 0a
```

ASCII:

```text
Notes GUI ARM
```

## Verification

`test-notes-linux-arm64` is a Linux x86_64 structural verifier. It checks the
ELF magic, AArch64 machine type, and GUI scaffold payload bytes.
