# `products/notes/notes-winarm64.exe`

`notes-winarm64.exe` is a **1024-byte** `PE32+` Windows ARM64 GUI-subsystem
executable container. It reuses the PE layout from `notes-win64.exe`, changes
the COFF machine type to ARM64, patches the subsystem to `Windows GUI`, and
replaces the entrypoint with a tiny ARM64 return stub.

This is an initial structural Windows ARM64 product artifact. It does not yet
implement the Win32 Notes GUI described in [`windows-plan.md`](windows-plan.md).

## Key bytes

At `0x000`:

```text
4d 5a
```

At `0x084`:

```text
64 aa
```

This is the Windows ARM64 machine type.

At `0x0dc`:

```text
02 00
```

This is the GUI-subsystem marker.

At `0x200`, the entry stub is two AArch64 instructions:

```text
00 00 80 52   mov   w0, #0
c0 03 5f d6   ret
```

### Entry stub encodings

AArch64 instructions are 32-bit words stored little-endian.

- **`00 00 80 52` = word `0x52800000` — `movz w0, #0`.** This is the 32-bit
  (`W`-register) form of the same `MOVZ` opcode used by the Linux ARM64
  greeter: `sf=0` (32-bit) `10 100101` `hw=00`, `imm16 = 0`, `Rd = 0`. It sets
  the return-value register `w0` to `0`. The register-field and immediate
  layout is decoded in full in
  [`experiments/poc-06-linux-arm64/hello.md`](../../../../../experiments/poc-06-linux-arm64/hello.md#instruction-by-instruction-with-encodings)
  (which uses the 64-bit `x`-register `MOVZ`; here `sf=0` selects `w0`).
- **`c0 03 5f d6` = word `0xd65f03c0` — `ret`.** Branch-to-register with
  `Rn = x30` (the link register), decoded bit-by-bit in
  [`experiments/poc-11-apple-mach-o/hello-macos.md`](../../../../../experiments/poc-11-apple-mach-o/hello-macos.md#encoding-bit-by-bit).

So the stub returns `0` to whatever called the PE entry point. Like the Apple
scaffolds, this is a container-correctness artifact: a real Windows ARM64 build
would replace these two words with a Win32 message loop (the same shape as the
[x86_64 sibling](../x86_64/notes-win64.exe.md#code-walkthrough-file-0x200--va-0x140001000),
re-encoded for AArch64).

At `0x230`, the product GUI scaffold string is:

```text
4e 6f 74 65 73 20 47 55 49 20 41 52 4d 0d 0a
```

ASCII:

```text
Notes GUI ARM
```

The retained import-table bytes are inert for the current return stub but keep
the PE section layout identical to the x86_64 sibling while a real ARM64 Win32
GUI path is still pending.

## Verification

`test-notes-winarm64` checks the `MZ` signature, ARM64 machine type, GUI
subsystem, ARM64 entry stub, and product marker string.
