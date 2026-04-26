# `products/notes/notes-macos`

`notes-macos` is a **170-byte** Mach-O 64-bit arm64 executable container for the
macOS Notes product target. It is derived from
[`../../../../../experiments/poc-11-apple-mach-o/hello-macos`](../../../../../experiments/poc-11-apple-mach-o/hello-macos.md), with the inline payload
changed to:

```text
Notes GUI Mac
```

Like the Apple POC, this is a Linux-host-verified structural artifact. A real
AppKit runtime is still tracked in [`apple-desktop-plan.md`](apple-desktop-plan.md).

## Layout

```text
0x000..0x01f    32   mach_header_64
0x020..0x067    72   LC_SEGMENT_64 for __TEXT
0x068..0x07f    24   LC_BUILD_VERSION, platform macOS
0x080..0x097    24   LC_MAIN
0x098..0x09b     4   arm64 code: ret
0x09c..0x0a9    14   "Notes GUI Mac\n"
```

## Key bytes

Header magic at `0x000`:

```text
cf fa ed fe
```

Build-version platform at `0x070`:

```text
01 00 00 00
```

Entry stub at `0x098`:

```text
c0 03 5f d6   ret
```

Payload at `0x09c`:

```text
4e 6f 74 65 73 20 47 55 49 20 4d 61 63 0a
```

## Verification

`test-notes-macos` checks the Mach-O magic, macOS platform word, and product
GUI scaffold payload bytes.
