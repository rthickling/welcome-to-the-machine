# `poc-09/hello` — Android-style AArch64 PIE greeter

`hello` is a **168-byte** `ELF64` **AArch64** binary built as `ET_DYN` rather
than `ET_EXEC`. `file` identifies it as:

```text
ELF 64-bit LSB pie executable, ARM aarch64, version 1 (SYSV), statically linked, no section header
```

That `PIE` / `ET_DYN` shape is the key difference from `poc-06/hello`, and is
the part that makes this target relevant for Android-style native execution.

When run under `qemu-aarch64-static` on the current x86_64 Linux host, it
prints:

```text
Hello, android!
```

and exits `0`.

## How it works (logic)

The eight-instruction program is the same idiom as `poc-06`, but the image is `ET_DYN` with segment base `0x10000`: **`adr x1, msg`** is PC-relative, so the code never assumes a fixed absolute text address. **`mov x0, #1`**, **`mov x2, #16`**, **`mov x8, #64`**, **`svc #0`** implement `write(1, &msg, 16)`; **`mov x0, #0`**, **`mov x8, #93`**, **`svc #0`** implement `exit(0)`. The inline string at vaddr `0x10098` is 16 bytes including the newline.

## Why this target is different from `poc-06`

`poc-06/hello` is a fixed-address Linux ARM64 `ET_EXEC` binary.

`poc-09/hello` is a position-independent `ET_DYN` binary with:

- ELF type `3` (`DYN`)
- entry point `0x10078`
- a loadable segment based at virtual address `0x10000`
- only PC-relative code, so it does not depend on a fixed absolute code address

That is the smallest meaningful step toward Android in this repo: a native
AArch64 PIE executable instead of a fixed-address Linux ARM64 executable.

## Usage

```bash
cd experiments/poc-09-android-elf
qemu-aarch64-static ./hello
```

Verified output:

```text
Hello, android!
```

## File layout

```text
0x000..0x03f   64   ELF64 header
0x040..0x077   56   single PT_LOAD program header
0x078..0x097   32   executable code (8 instructions)
0x098..0x0a7   16   data string "Hello, android!\n"
```

Total size: `64 + 56 + 32 + 16 = 168` bytes.

## ELF header bytes

From the committed file:

```text
7f 45 4c 46 02 01 01 00 00 00 00 00 00 00 00 00
03 00 b7 00 01 00 00 00 78 00 01 00 00 00 00 00
40 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 40 00 38 00 01 00 00 00 00 00 00 00
```

Key fields:

- `03 00` = `ET_DYN`
- `b7 00` = `EM_AARCH64`
- entry = `0x10078`
- program header offset = `0x40`
- ELF header size = `0x40`
- program header entry size = `0x38`
- program header count = `1`

## Program header bytes

```text
01 00 00 00   ; PT_LOAD
07 00 00 00   ; PF_R | PF_W | PF_X
00 00 00 00 00 00 00 00   ; p_offset = 0
00 00 01 00 00 00 00 00   ; p_vaddr  = 0x10000
00 00 01 00 00 00 00 00   ; p_paddr  = 0x10000
a8 00 00 00 00 00 00 00   ; p_filesz = 168
00 20 00 00 00 00 00 00   ; p_memsz  = 0x2000
00 10 00 00 00 00 00 00   ; p_align  = 0x1000
```

`readelf -h -l` reports:

- type `DYN`
- one `LOAD` segment
- `VirtAddr = 0x10000`
- `FileSiz = 0xa8`
- `MemSiz  = 0x2000`

## Code bytes at entry `0x10078`

The 8 AArch64 instructions are:

```text
01 01 00 10   ; adr  x1, msg
20 00 80 d2   ; mov  x0, #1
02 02 80 d2   ; mov  x2, #16
08 08 80 d2   ; mov  x8, #64
01 00 00 d4   ; svc  #0
00 00 80 d2   ; mov  x0, #0
a8 0b 80 d2   ; mov  x8, #93
01 00 00 d4   ; svc  #0
```

Exactly 8 instructions, exactly 32 bytes.

### Instruction-by-instruction, with encodings

Seven of the eight words are **byte-identical** to `poc-06/hello`, whose doc
decodes the `ADR` / `MOVZ` / `SVC` encodings field-by-field —
see [`experiments/poc-06-linux-arm64/hello.md`](../poc-06-linux-arm64/hello.md#instruction-by-instruction-with-encodings).
The only differing word is instruction 3 (the string length: 16 here vs 14).

#### 1. `01 01 00 10` — `adr x1, msg`

Word `0x10000101`, same encoding as poc-06: `immhi = 8`, `immlo = 0`, so the
offset is `(8 << 2) | 0` = 32 bytes forward from the instruction's own PC.
This is the instruction that makes the PIE property real: the address is
computed relative to wherever the segment was actually loaded, never from an
absolute constant. At the link-time base:

```text
x1 = PC + 32 = 0x10078 + 0x20 = 0x10098   ; address of "Hello, android!\n"
```

If the kernel/loader relocates the `ET_DYN` image to base `B`, the same word
yields `B + 0x98` with no relocation records needed.

#### 2. `20 00 80 d2` — `mov x0, #1`

MOVZ word `0xd2800020` (`imm16 = 1`, `Rd = 0`): `x0 = 1`, the stdout fd.

#### 3. `02 02 80 d2` — `mov x2, #16`

MOVZ word `0xd2800202`: `imm16` (bits 20–5) = `0x10` = 16, `Rd` (bits 4–0) =
2. Sets `x2 = 16` — the byte length of `"Hello, android!\n"`. This is the one
word that differs from poc-06 (`0xd28001c2`, length 14): the immediate field
moved from `14 << 5 = 0x1c0` to `16 << 5 = 0x200` inside the word.

#### 4. `08 08 80 d2` — `mov x8, #64`

MOVZ word `0xd2800808` (`imm16 = 64`, `Rd = 8`): Linux AArch64 syscall number
`64 = write` in `x8` — the same generic-syscall-table numbers apply to
Android's Linux kernel.

#### 5. `01 00 00 d4` — `svc #0`

Traps into the kernel:

```text
write(1, x1, 16)     ; x1 = load_base + 0x98
```

#### 6. `00 00 80 d2` — `mov x0, #0`

MOVZ word `0xd2800000`: exit status `0`.

#### 7. `a8 0b 80 d2` — `mov x8, #93`

MOVZ word `0xd2800ba8` (`imm16 = 93`, `Rd = 8`): syscall `93 = exit`.

#### 8. `01 00 00 d4` — `svc #0`

Performs:

```text
exit(0)
```

## Inline data

At file offset `152` / virtual address `0x10098`:

```text
48 65 6c 6c 6f 2c 20 61 6e 64 72 6f 69 64 21 0a
```

ASCII:

```text
Hello, android!\n
```

The string still starts at file offset `152`, just like `poc-06/hello`; only
the ELF type and segment base changed.

## Syscalls used

Exactly two Linux AArch64 syscalls:

| nr | name  | purpose |
| -- | ----- | ------- |
| 64 | write | print greeting |
| 93 | exit  | exit cleanly |

There is:

- no libc
- no dynamic linker
- no interpreter segment
- no absolute code address dependency

## Why this target matters

It proves that the repo can now produce:

- AArch64 PIE machine code
- an `ET_DYN` native executable rather than only `ET_EXEC`
- a small Android-relevant native format step without adding any human-readable
  build source
- a target that still runs under `qemu-aarch64-static` on the current host
