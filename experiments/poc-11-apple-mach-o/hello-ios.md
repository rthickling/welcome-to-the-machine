# `poc-11/hello-ios` — minimal arm64 Mach-O for iOS

`hello-ios` is a **168-byte** Mach-O 64-bit `arm64` executable container for
the iOS side of the Apple POC. Like `hello-macos`, it is a **structural
artifact first**: on this Linux host we verify the Mach-O header, load-command
shape, and greeting bytes, but we do **not** yet claim successful execution on
real iOS hardware or an Apple simulator.

The file contains:

- one Mach-O 64-bit header
- one `LC_SEGMENT_64` command for a tiny `__TEXT` mapping
- one `LC_BUILD_VERSION` command with `platform = iOS`
- one `LC_MAIN` command pointing at a 4-byte entry stub
- one inline greeting string

The code stub is again only:

```text
ret
```

The point of this artifact is to prove Apple-target container bytes under the
repo rules, with iOS-specific metadata distinct from the macOS sibling.

## Current verification status

On the current Linux host:

- `file hello-ios` reports `Mach-O 64-bit arm64 executable`
- the committed verifier `test-hello-ios` exits `0`
- corrupting the `LC_BUILD_VERSION` platform byte makes the verifier exit `1`

Real iOS execution, code signing, and packaging are explicitly out of scope for
this host-only step.

## File layout

```text
0x000..0x01f    32   mach_header_64
0x020..0x067    72   LC_SEGMENT_64 for __TEXT
0x068..0x07f    24   LC_BUILD_VERSION (platform = iOS)
0x080..0x097    24   LC_MAIN
0x098..0x09b     4   arm64 code: ret
0x09c..0x0a7    12   "Hello, iOS!\n"
```

Total file size: `168` bytes.

## Mach-O header

The first 32 bytes are:

```text
cf fa ed fe   0c 00 00 01   00 00 00 00   02 00 00 00
03 00 00 00   78 00 00 00   00 00 20 00   00 00 00 00
```

Meaning:

- `cf fa ed fe` = `MH_MAGIC_64`
- `0c 00 00 01` = CPU type `arm64`
- `00 00 00 00` = CPU subtype `ARM64_ALL`
- `02 00 00 00` = file type `MH_EXECUTE`
- `03 00 00 00` = `ncmds = 3`
- `78 00 00 00` = `sizeofcmds = 120`
- `00 00 20 00` = `MH_PIE`
- `00 00 00 00` = reserved

The top-level Mach-O shape therefore matches the macOS sibling exactly. The
important distinction appears in the build-version metadata below.

## `LC_SEGMENT_64`

At file offset `0x20`:

```text
19 00 00 00   48 00 00 00
5f 5f 54 45 58 54 00 00 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00
00 10 00 00 00 00 00 00
00 00 00 00 00 00 00 00
a8 00 00 00 00 00 00 00
05 00 00 00
05 00 00 00
00 00 00 00
00 00 00 00
```

This is one `LC_SEGMENT_64` command with:

- segment name `__TEXT`
- `vmaddr = 0`
- `vmsize = 0x1000`
- `fileoff = 0`
- `filesize = 0xa8` (`168`)
- `maxprot = initprot = 5` (`r-x`)
- `nsects = 0`
- `flags = 0`

So the whole file is again one minimal executable text mapping.

## `LC_BUILD_VERSION`

At file offset `0x68`:

```text
32 00 00 00   18 00 00 00   02 00 00 00
00 00 11 00   00 00 11 00   00 00 00 00
```

Field meaning:

- `32 00 00 00` = `LC_BUILD_VERSION`
- `18 00 00 00` = command size `24`
- `02 00 00 00` = platform `2` = iOS
- `00 00 11 00` = minimum OS `17.0.0`
- `00 00 11 00` = SDK `17.0.0`
- `00 00 00 00` = `ntools = 0`

This is the exact field the Linux verifier uses to distinguish the iOS artifact
from the macOS artifact.

## `LC_MAIN`

At file offset `0x80`:

```text
28 00 00 80   18 00 00 00
98 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00
```

Meaning:

- `LC_MAIN`
- command size `24`
- `entryoff = 0x98`
- `stacksize = 0`

So the entrypoint stub begins at file offset `0x98`, exactly as in the macOS
file.

## Code bytes

At file offset `0x98`:

```text
c0 03 5f d6
```

That one 32-bit AArch64 instruction is:

```text
ret
```

Byte detail:

- `c0 03 5f d6` = encoded `ret` (same **AArch64** `RET` as in `hello-macos`; see that file for the one-line execution story).

The code is intentionally minimal because runtime behavior is not the proof
being claimed yet; container correctness is.

## Greeting payload

At file offset `0x9c`:

```text
48 65 6c 6c 6f 2c 20 69 4f 53 21 0a
```

ASCII:

```text
Hello, iOS!
```

followed by newline byte `0a`.

The Linux verifier checks these exact 12 bytes.

## Why this is a useful first iOS step

This artifact does **not** yet prove:

- iOS app packaging
- code signing
- simulator compatibility
- process launch on Apple tooling

It **does** prove that the repo now contains a literal-byte machine-code
artifact whose Apple metadata says:

- Mach-O 64-bit
- `arm64`
- `MH_EXECUTE`
- `LC_BUILD_VERSION platform = iOS`

That is the correct low-level first milestone before any later bundle or
deployment layer.
