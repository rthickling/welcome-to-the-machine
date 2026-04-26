# `products/notes/notes-ios`

`notes-ios` is a **168-byte** Mach-O 64-bit arm64 executable container for the
iOS Notes product target. It is derived from
[`../../../../../experiments/poc-11-apple-mach-o/hello-ios`](../../../../../experiments/poc-11-apple-mach-o/hello-ios.md), with the inline payload changed
to:

```text
NotesGUIiOS
```

This is a Linux-host structural artifact. Real iOS execution, signing, and UI
work remain described in [`mobile-plan.md`](mobile-plan.md).

## Layout

```text
0x000..0x01f    32   mach_header_64
0x020..0x067    72   LC_SEGMENT_64 for __TEXT
0x068..0x07f    24   LC_BUILD_VERSION, platform iOS
0x080..0x097    24   LC_MAIN
0x098..0x09b     4   arm64 code: ret
0x09c..0x0a7    12   "NotesGUIiOS\n"
```

## Key bytes

```text
0x000: cf fa ed fe
0x070: 02 00 00 00
0x098: c0 03 5f d6
0x09c: 4e 6f 74 65 73 47 55 49 69 4f 53 0a
```

## Verification

`test-notes-ios` checks the Mach-O magic, iOS platform word, and product payload
GUI scaffold payload bytes.
