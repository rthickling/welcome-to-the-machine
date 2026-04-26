# `poc-11/hello-macos` — minimal arm64 Mach-O for macOS

`hello-macos` is a **170-byte** Mach-O 64-bit `arm64` executable container.
It is the repo's first Apple-target artifact and is intentionally a **host-side
structural proof**: on this Linux machine we verify the Mach-O bytes and the
platform metadata, but we do **not** yet claim runtime demonstration on macOS.

The file contains:

- one Mach-O 64-bit header
- one `LC_SEGMENT_64` command describing a tiny `__TEXT` mapping
- one `LC_BUILD_VERSION` command with `platform = macOS`
- one `LC_MAIN` command pointing at a 4-byte entry stub
- one inline greeting payload

The executable entrypoint is just:

```text
ret
```

so the important proof in this step is the Mach-O container shape, not useful
runtime behavior yet.

## Current verification status

On the current Linux host:

- `file hello-macos` reports `Mach-O 64-bit arm64 executable`
- the committed machine-code verifier `test-hello-macos` exits `0`
- corrupting the `LC_BUILD_VERSION` platform byte makes that verifier exit `1`

Real execution on macOS hardware or a macOS VM is explicitly deferred.

## File layout

```text
0x000..0x01f    32   mach_header_64
0x020..0x067    72   LC_SEGMENT_64 for __TEXT
0x068..0x07f    24   LC_BUILD_VERSION (platform = macOS)
0x080..0x097    24   LC_MAIN
0x098..0x09b     4   arm64 code: ret
0x09c..0x0a9    14   "Hello, macOS!\n"
```

Total file size: `170` bytes.

## Mach-O header

The first 32 bytes are:

```text
cf fa ed fe   0c 00 00 01   00 00 00 00   02 00 00 00
03 00 00 00   78 00 00 00   00 00 20 00   00 00 00 00
```

Field by field:

- `cf fa ed fe` = Mach-O 64-bit magic `MH_MAGIC_64`
- `0c 00 00 01` = CPU type `arm64` (`CPU_TYPE_ARM | CPU_ARCH_ABI64`)
- `00 00 00 00` = CPU subtype `ARM64_ALL`
- `02 00 00 00` = file type `MH_EXECUTE`
- `03 00 00 00` = `ncmds = 3`
- `78 00 00 00` = `sizeofcmds = 0x78 = 120`
- `00 00 20 00` = flags `MH_PIE`
- `00 00 00 00` = reserved field of `mach_header_64`

So the loader would interpret this as a position-independent 64-bit arm64
executable with exactly three load commands following the header.

## `LC_SEGMENT_64`

At file offset `0x20`:

```text
19 00 00 00   48 00 00 00
5f 5f 54 45 58 54 00 00 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00
00 10 00 00 00 00 00 00
00 00 00 00 00 00 00 00
aa 00 00 00 00 00 00 00
05 00 00 00
05 00 00 00
00 00 00 00
00 00 00 00
```

This is one `segment_command_64`:

- `19 00 00 00` = `LC_SEGMENT_64`
- `48 00 00 00` = command size `72`
- `5f 5f 54 45 58 54 ...` = segment name `__TEXT`
- `vmaddr = 0`
- `vmsize = 0x1000`
- `fileoff = 0`
- `filesize = 0xaa` (`170`)
- `maxprot = 5` and `initprot = 5` = read + execute
- `nsects = 0`
- `flags = 0`

This says the whole file is treated as one tiny executable text mapping.

## `LC_BUILD_VERSION`

At file offset `0x68`:

```text
32 00 00 00   18 00 00 00   01 00 00 00
00 00 0e 00   00 00 0e 00   00 00 00 00
```

Field by field:

- `32 00 00 00` = `LC_BUILD_VERSION`
- `18 00 00 00` = command size `24`
- `01 00 00 00` = platform `1` = macOS
- `00 00 0e 00` = minimum OS `14.0.0`
- `00 00 0e 00` = SDK `14.0.0`
- `00 00 00 00` = `ntools = 0`

This is the key Apple-platform distinguisher for this POC step. The companion
iOS file uses the same command shape but a different platform value.

## `LC_MAIN`

At file offset `0x80`:

```text
28 00 00 80   18 00 00 00
98 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00
```

Meaning:

- `28 00 00 80` = `LC_MAIN`
- `18 00 00 00` = command size `24`
- `98 00 00 00 00 00 00 00` = `entryoff = 0x98`
- `00 ... 00` = `stacksize = 0`

So the entrypoint is the 4-byte stub starting at file offset `0x98`.

## Code bytes

At file offset `0x98`:

```text
c0 03 5f d6
```

That is one AArch64 instruction:

```text
ret
```

Byte view of the instruction word:

- `c0 03 5f d6` = encoded `ret` (AArch64 `RET` without explicit operand: return to the address in the link register `x30`).

If a macOS loader were to start at `entryoff = 0x98`, the CPU would execute that single **`ret`** and then return to whatever address the loader placed in `lr`—in a real process that is defined by the dynamic loader; this artifact does not model a full user `main`. The proof is the **Mach-O** layout and metadata, not application behavior.

## Greeting payload

At file offset `0x9c`:

```text
48 65 6c 6c 6f 2c 20 6d 61 63 4f 53 21 0a
```

ASCII:

```text
Hello, macOS!
```

with the trailing newline byte `0a`.

The host-side verifier checks these exact 14 bytes.

## Why this is not yet a full macOS app proof

This file is intentionally smaller in scope than a production macOS executable.
It does **not** include:

- code signing
- a bundle
- launch services metadata
- a tested syscall / libc / Objective-C path

For this repo stage, the honest claim is narrower:

- the repo now contains a real `arm64` Mach-O executable artifact
- it is tagged for macOS with `LC_BUILD_VERSION`
- its fixed bytes are machine-code tested on Linux
