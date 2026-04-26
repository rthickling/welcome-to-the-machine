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

At `0x200`, the entry stub is:

```text
00 00 80 52   mov   w0, #0
c0 03 5f d6   ret
```

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
