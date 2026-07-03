# `poc-06/hello` — Linux ELF AArch64 greeter

`hello` is a **166-byte** statically-linked Linux ELF64 executable for
**AArch64**. When run under a Linux ARM64 kernel, or under
`qemu-aarch64-static` on this x86_64 host, it writes:

```text
Hello, arm64!
```

and exits `0`.

This is the repo's first runnable non-x86 ELF target.

## Usage

```bash
cd experiments/poc-06-linux-arm64
qemu-aarch64-static ./hello
```

Verified output:

```text
Hello, arm64!
```

## File layout

The file is:

```text
0x000..0x03f   64   ELF64 header
0x040..0x077   56   single PT_LOAD program header
0x078..0x097   32   executable code (8 instructions)
0x098..0x0a5   14   data string "Hello, arm64!\n"
```

Total size: `64 + 56 + 32 + 14 = 166` bytes.

The program header maps one segment:

- `p_offset = 0`
- `p_vaddr  = 0x400000`
- `p_filesz = 0x00a6`
- `p_memsz  = 0x2000`
- `p_flags  = R|W|X = 7`
- `p_align  = 0x1000`

Entry point: `0x400078`.

The larger `p_memsz` is not needed by this tiny binary itself, but keeping one
simple 8 KiB loadable segment matches the pattern used by the later ARM64 test.

## ELF header bytes

From the built file:

```text
7f 45 4c 46 02 01 01 00 00 00 00 00 00 00 00 00
02 00 b7 00 01 00 00 00 78 00 40 00 00 00 00 00
40 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 40 00 38 00 01 00 00 00 00 00 00 00
```

Key fields:

- `02 00` = `ET_EXEC`
- `b7 00` = `EM_AARCH64`
- entry = `0x400078`
- program header offset = `0x40`
- ELF header size = `0x40`
- program header entry size = `0x38`
- program header count = `1`

## Program header bytes

```text
01 00 00 00   ; PT_LOAD
07 00 00 00   ; PF_R | PF_W | PF_X
00 00 00 00 00 00 00 00   ; p_offset = 0
00 00 40 00 00 00 00 00   ; p_vaddr  = 0x400000
00 00 40 00 00 00 00 00   ; p_paddr  = 0x400000
a6 00 00 00 00 00 00 00   ; p_filesz = 166
00 20 00 00 00 00 00 00   ; p_memsz  = 0x2000
00 10 00 00 00 00 00 00   ; p_align  = 0x1000
```

## Code bytes at `0x400078`

The body bytes are:

```text
01 01 00 10
20 00 80 d2
c2 01 80 d2
08 08 80 d2
01 00 00 d4
00 00 80 d2
a8 0b 80 d2
01 00 00 d4
```

That is exactly 8 AArch64 instructions.

**Flat listing (hex + mnemonic):**

```text
01 01 00 10   adr   x1, msg
20 00 80 d2   mov   x0, #1
c2 01 80 d2   mov   x2, #14
08 08 80 d2   mov   x8, #64
01 00 00 d4   svc   #0                    ; write(1, msg, 14)
00 00 80 d2   mov   x0, #0
a8 0b 80 d2   mov   x8, #93
01 00 00 d4   svc   #0                    ; exit(0)
```

### Instruction-by-instruction, with encodings

AArch64 instructions are fixed 32-bit words stored **little-endian**, so the
file bytes `01 01 00 10` are the word `0x10000101`. Three encodings cover the
whole program:

- **`ADR Xd, label`** — `0 immlo(2) 10000 immhi(19) Rd(5)`; the PC-relative
  offset is `(immhi << 2) | immlo`.
- **`MOVZ Xd, #imm16`** — `1 10 100101 hw(2) imm16(16) Rd(5)`; with `hw = 00`
  the register is simply set to `imm16` (the top word `0xd28.....` is this
  pattern, which disassemblers print as `mov`).
- **`SVC #imm16`** — `11010100 000 imm16(16) 000 01`; word `0xd4000001` is
  `svc #0`, the Linux syscall trap.

#### 1. `01 01 00 10` — `adr x1, msg`

Word `0x10000101`: bit 31 = `0` (ADR, not ADRP), `immlo` (bits 30–29) = `0`,
`immhi` (bits 23–5) = `8`, `Rd` (bits 4–0) = `1` (`x1`).
Offset = `(8 << 2) | 0` = **32**, so:

```text
x1 = PC + 32 = 0x400078 + 0x20 = 0x400098   ; address of "Hello, arm64!\n"
```

#### 2. `20 00 80 d2` — `mov x0, #1`

Word `0xd2800020`: MOVZ with `hw` (bits 22–21) = `0`, `imm16` (bits 20–5) =
`1`, `Rd` = `0`. Sets `x0 = 1` — the stdout file descriptor (syscall arg 1).

#### 3. `c2 01 80 d2` — `mov x2, #14`

Word `0xd28001c2`: `imm16 = 14`, `Rd = 2`. Sets `x2 = 14` — the byte length
of `"Hello, arm64!\n"` (syscall arg 3).

#### 4. `08 08 80 d2` — `mov x8, #64`

Word `0xd2800808`: `imm16 = 64`, `Rd = 8`. On Linux AArch64 the syscall
number goes in `x8`; `64 = write`. (Note the numbers differ from x86_64,
where `write` is 1.)

#### 5. `01 00 00 d4` — `svc #0`

Traps into the kernel. With `x8 = 64`, `x0 = 1`, `x1 = 0x400098`, `x2 = 14`
this performs:

```text
write(1, 0x400098, 14)
```

The return value comes back in `x0` and is ignored.

#### 6. `00 00 80 d2` — `mov x0, #0`

Word `0xd2800000`: `imm16 = 0`, `Rd = 0`. Prepares exit status `0`.

#### 7. `a8 0b 80 d2` — `mov x8, #93`

Word `0xd2800ba8`: `imm16 = 93`, `Rd = 8`. Linux AArch64 syscall `93 = exit`.

#### 8. `01 00 00 d4` — `svc #0`

Performs:

```text
exit(0)
```

The process terminates here; no instruction after this word is ever fetched
(and none exists — the string data follows immediately).

## Inline data

At file offset `152` / virtual address `0x400098`:

```text
48 65 6c 6c 6f 2c 20 61 72 6d 36 34 21 0a
```

ASCII:

```text
Hello, arm64!\n
```

The greeting begins at file offset **`152`**, which is the fixed value the
binary test uses later.

## Syscalls used

Exactly two Linux syscalls:

| nr | name   | purpose |
| -- | ------ | ------- |
| 64 | write  | print greeting |
| 93 | exit   | exit cleanly |

No libc, no dynamic loader, no interpreter segment.

## Why this target matters

It proves all of the following are now real in the repo:

- non-x86 machine code
- non-x86 ELF generation
- user-mode emulated execution on the current host
- binary tests that are themselves native to the target architecture
